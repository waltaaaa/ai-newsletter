"""
perplexity_search.py — Tier 3B Perplexity monthly gap-fill for CAN-MACRO pipeline.

Runs ONLY on monthly deep-sweep (--deep-sweep flag). 13 queries, one per province.
Uses Perplexity Sonar Pro for multi-source synthesis that catches projects none of
the other tiers find.

Budget: ~$0.50-0.80/year (13 queries/month × Sonar Pro pricing).
"""

import json
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY', '').strip()
PERPLEXITY_ENABLED = os.environ.get('PERPLEXITY_ENABLED', 'true').lower() == 'true'
PERPLEXITY_MODEL = 'sonar-pro'
PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'

# Province definitions (mirrors gemini_search.py)
PROVINCES = [
    {'name': 'Ontario',                     'code': 'ON', 'threshold': '$500M'},
    {'name': 'Quebec',                      'code': 'QC', 'threshold': '$250M'},
    {'name': 'Alberta',                     'code': 'AB', 'threshold': '$200M'},
    {'name': 'British Columbia',            'code': 'BC', 'threshold': '$175M'},
    {'name': 'Saskatchewan',                'code': 'SK', 'threshold': '$45M'},
    {'name': 'Manitoba',                    'code': 'MB', 'threshold': '$40M'},
    {'name': 'Nova Scotia',                 'code': 'NS', 'threshold': '$25M'},
    {'name': 'New Brunswick',               'code': 'NB', 'threshold': '$20M'},
    {'name': 'Newfoundland and Labrador',   'code': 'NL', 'threshold': '$17M'},
    {'name': 'Prince Edward Island',        'code': 'PE', 'threshold': '$5M'},
    {'name': 'Yukon',                       'code': 'YT', 'threshold': '$3M'},
    {'name': 'Northwest Territories',       'code': 'NT', 'threshold': '$3M'},
    {'name': 'Nunavut',                     'code': 'NU', 'threshold': '$3M'},
]

_PROMPT_TEMPLATE = """List every major capital project worth over C{threshold} currently proposed, approved, under review, or under construction in {province}, Canada.

For each project include: project name, estimated value, proponent/developer, city/municipality, current status, and a source URL.

Include all sectors: energy, mining, manufacturing, real estate, mixed-use redevelopment, infrastructure, transit, healthcare, education, technology, defense, agriculture, and entertainment. Include both new construction and redevelopments/conversions.

Be thorough — check government announcements, news articles, company press releases, municipal development permits, budget documents, and industry publications.

Return your answer as a JSON array where each element has:
{{"name": "...", "value": "...", "proponent": "...", "cma": "...", "status": "...", "source_url": "...", "source_title": "...", "description": "..."}}

Return [] if no projects found."""


def _query_perplexity(prompt: str) -> dict | None:
    """Send a single query to Perplexity Sonar Pro. Returns parsed JSON response."""
    if not PERPLEXITY_API_KEY:
        return None

    try:
        resp = requests.post(
            PERPLEXITY_API_URL,
            headers={
                'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': PERPLEXITY_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'return_citations': True,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        citations = data.get('citations', [])
        return {'content': content, 'citations': citations}
    except Exception as e:
        print(f"  [Perplexity] API error: {type(e).__name__}: {e}")
        return None


def _parse_projects(response: dict, province_name: str, province_code: str) -> list[dict]:
    """Parse projects from Perplexity response."""
    if not response:
        return []

    content = response.get('content', '')
    # Try to extract JSON array from response
    try:
        # Look for JSON array in the content
        match = re.search(r'\[[\s\S]*\]', content)
        if match:
            raw = json.loads(match.group())
        else:
            raw = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw, list):
        return []

    projects = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = (item.get('name') or '').strip()
        if not name:
            continue

        projects.append({
            'name': name,
            'value': item.get('value') or 'Not disclosed',
            'proponent': (item.get('proponent') or 'Unknown').strip(),
            'province': province_name,
            'cma': (item.get('cma') or '').strip(),
            'status': (item.get('status') or 'Proposed').strip(),
            'description': (item.get('description') or '').strip(),
            'source_url': (item.get('source_url') or '').strip(),
            'source_title': (item.get('source_title') or '').strip(),
            'discovery_source': 'perplexity_gap_fill',
            'confidence': 'unverified',
        })

    return projects


def run_perplexity_gap_fill() -> list[dict]:
    """
    Run Perplexity gap-fill across all 13 provinces.
    Only runs if PERPLEXITY_ENABLED and API key is set.

    Returns:
        List of project dicts (not yet deduplicated).
    """
    if not PERPLEXITY_ENABLED:
        print("  [Perplexity] Disabled (set PERPLEXITY_ENABLED=true in .env)")
        return []

    if not PERPLEXITY_API_KEY:
        print("  [Perplexity] No API key — skipping gap-fill.")
        return []

    print(f"\n[TIER 3B] Perplexity gap-fill (13 provinces)...")

    all_projects = []
    for prov in PROVINCES:
        prompt = _PROMPT_TEMPLATE.format(
            threshold=prov['threshold'],
            province=prov['name'],
        )

        response = _query_perplexity(prompt)
        projects = _parse_projects(response, prov['name'], prov['code'])
        all_projects.extend(projects)

        if projects:
            print(f"  [Perplexity] {prov['code']}: {len(projects)} projects")
        time.sleep(1)

    print(f"  [Perplexity] Complete: {len(all_projects)} total projects")
    return all_projects


def log_perplexity_unique(projects: list[dict], existing_names: set[str]):
    """Log projects found by Perplexity but not in other tiers."""
    from datetime import date
    today = date.today().isoformat()
    unique = [p for p in projects if p['name'].lower().strip() not in existing_names]
    if not unique:
        return
    try:
        path = f'perplexity_unique_{today}.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"Perplexity-unique projects — {today}\n{'='*60}\n\n")
            for p in unique:
                f.write(f"{p.get('province', '?')}: {p['name']} ({p.get('value', '?')})\n")
                f.write(f"  Status: {p.get('status', '?')} | Source: {p.get('source_url', 'N/A')}\n\n")
        print(f"  [Perplexity] {len(unique)} unique projects logged to {path}")
    except Exception:
        pass
