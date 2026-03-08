"""
backfill_project_values.py — Standalone script to fill missing project values via Gemini.

Queries Firestore for projects where value is "Not disclosed" or empty,
then uses Gemini grounded search to find capital cost information.

Usage:
    python backfill_project_values.py [--limit N] [--dry-run]
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import asyncio
import argparse
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore
import aiohttp

from gemini_engine import query_one
from pipeline_config import parse_value, PROVINCES

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Province threshold lookup
THRESHOLDS = {p["name"]: p["threshold_val"] for p in PROVINCES}

BACKFILL_SYSTEM_PROMPT = """You are a Canadian infrastructure research assistant.
Given a query about a specific Canadian capital project, find its estimated or
announced capital cost / investment value.

Respond in JSON format:
{
  "value": "$XXM" or "$X.XB",
  "value_numeric_millions": 123.0,
  "source_url": "https://...",
  "source_title": "Source name",
  "confidence": "high|medium|low",
  "notes": "Brief context about the value"
}

Rules:
- Only report values you can verify from credible sources (news, government, corporate).
- If the project cost is truly unknown or not publicly available, respond: {"value": null}
- Use Canadian dollars unless the source explicitly states otherwise.
- Include the source URL where you found the information."""

DEFAULT_LIMIT = 100
CONCURRENCY = 10


def _init_firebase():
    if not firebase_admin._apps:
        sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa:
            cred = credentials.Certificate(json.loads(sa))
        else:
            cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    return firestore.client()


def _fetch_projects_needing_values(db, limit):
    """Fetch projects with missing or 'Not disclosed' values, prioritized."""
    projects = []
    docs = db.collection('projects').stream()

    for doc in docs:
        p = doc.to_dict()
        p['_doc_id'] = doc.id

        val = p.get('value', '')
        val_m = p.get('value_millions')

        # Skip projects that already have a meaningful value
        if val_m and val_m > 0:
            continue
        if val and val.strip().lower() not in ('not disclosed', 'unknown', '', 'n/a'):
            parsed = parse_value(val)
            if parsed and parsed > 0:
                continue

        projects.append(p)

    # Prioritize: projects with a proponent (more searchable), then by lastSeen
    def sort_key(p):
        has_proponent = 1 if p.get('proponent') else 0
        last_seen = p.get('lastSeen', '') or ''
        return (-has_proponent, -len(last_seen), p.get('name', ''))

    projects.sort(key=sort_key)
    return projects[:limit]


def _build_query(project):
    """Build a Gemini search query for a project's value."""
    name = project.get('name', 'Unknown')
    province = project.get('province', '')
    cma = project.get('cma', '')
    proponent = project.get('proponent', '')

    location = f"{cma}, {province}" if cma else province

    parts = [f"What is the capital cost or investment value of the {name} project"]
    if location:
        parts[0] += f" in {location}, Canada"
    parts[0] += "?"

    if proponent:
        parts.append(f"The project proponent is {proponent}.")

    parts.append("Provide the dollar value in Canadian dollars and your source.")

    return {
        "query": " ".join(parts),
        "type": "backfill",
        "project_name": name,
        "project_province": province,
        "_doc_id": project['_doc_id'],
    }


def _parse_backfill_response(result):
    """Parse Gemini response to extract value information."""
    import re

    text = result.get('text', '')
    if not text:
        return None

    # Try JSON parse
    json_match = re.search(r'\{[\s\S]*?"value"[\s\S]*?\}', text)
    if not json_match:
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None

    value_str = data.get('value')
    if not value_str or value_str == 'null':
        return None

    # Parse the value string
    parsed = parse_value(str(value_str))
    if not parsed or parsed <= 0:
        return None

    value_millions = data.get('value_numeric_millions')
    if not value_millions:
        value_millions = parsed / 1e6

    return {
        'value': value_str,
        'value_millions': value_millions,
        'source_url': data.get('source_url', ''),
        'source_title': data.get('source_title', ''),
        'confidence_note': data.get('confidence', 'medium'),
        'notes': data.get('notes', ''),
    }


async def backfill(db, limit, dry_run):
    """Main backfill routine."""
    print(f"\n{'=' * 60}")
    print(f"PROJECT VALUE BACKFILL {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 60}")

    # 1. Fetch projects needing values
    print(f"\n[1/3] Fetching projects with missing values (limit={limit})...")
    projects = _fetch_projects_needing_values(db, limit)
    print(f"  Found {len(projects)} projects needing value enrichment")

    if not projects:
        print("  Nothing to do.")
        return

    # Show sample
    for p in projects[:5]:
        print(f"  - {p.get('name', '?')[:60]} ({p.get('province', '?')})"
              f" [proponent: {p.get('proponent', 'unknown')[:30]}]")
    if len(projects) > 5:
        print(f"  ... and {len(projects) - 5} more")

    # 2. Query Gemini
    print(f"\n[2/3] Querying Gemini for {len(projects)} projects...")
    queries = [_build_query(p) for p in projects]

    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = []

    async with aiohttp.ClientSession() as session:
        tasks = [
            query_one(session, semaphore, q, BACKFILL_SYSTEM_PROMPT)
            for q in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. Parse and apply
    print(f"\n[3/3] Processing results...")
    updated = 0
    skipped = 0
    failed = 0
    below_threshold = 0

    for i, result in enumerate(results):
        query = queries[i]
        doc_id = query['_doc_id']
        name = query['project_name']
        province = query['project_province']

        if isinstance(result, Exception):
            failed += 1
            logger.debug(f"  Query failed for {name}: {result}")
            continue

        if result.get('error'):
            failed += 1
            logger.debug(f"  Error for {name}: {result['error'][:100]}")
            continue

        parsed = _parse_backfill_response(result)
        if not parsed:
            skipped += 1
            continue

        value = parsed['value']
        value_millions = parsed['value_millions']
        threshold = THRESHOLDS.get(province, 0)

        # Check if value meets province threshold
        value_dollars = value_millions * 1e6
        meets = value_dollars >= threshold if threshold else True

        status = "ABOVE" if meets else "below"
        print(f"  {name[:50]:50s} → {value:>10s} ({status} {province} threshold)")

        if dry_run:
            updated += 1
            continue

        # Update Firestore
        try:
            update_data = {
                'value': value,
                'value_millions': value_millions,
                '_value_source': 'gemini_backfill',
                '_value_updated': datetime.now(timezone.utc).isoformat(),
            }

            if parsed.get('source_url'):
                update_data['_value_source_url'] = parsed['source_url']

            db.collection('projects').document(doc_id).update(update_data)
            updated += 1
        except Exception as e:
            logger.error(f"  Firestore update failed for {doc_id}: {e}")
            failed += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"BACKFILL COMPLETE {'(DRY RUN)' if dry_run else ''}")
    print(f"  Processed: {len(projects)}")
    print(f"  Updated:   {updated}")
    print(f"  Skipped:   {skipped} (no value found)")
    print(f"  Failed:    {failed}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description='Backfill missing project values via Gemini')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT,
                        help=f'Max projects to process (default: {DEFAULT_LIMIT})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be updated without writing to Firestore')
    args = parser.parse_args()

    db = _init_firebase()
    asyncio.run(backfill(db, args.limit, args.dry_run))


if __name__ == "__main__":
    main()
