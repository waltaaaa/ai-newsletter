"""
backfill_descriptions.py
One-time script to populate the 'description' field on all existing
projects in SQLite that are missing it.
Sends projects to Gemini in batches of 30 to stay well within token limits.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import os
import time

from google import genai
from google.genai import types

from db import init_db, get_all_projects, upsert_project

# ── Auth ──────────────────────────────────────────────────────────
apiKey = os.environ.get("GEMINI_API_KEY", "DISABLED_KEY_REMOVED")

client = genai.Client(api_key=apiKey)

BATCH_SIZE = 30

def get_descriptions(batch):
    """Ask Gemini to return one-sentence descriptions for a batch of projects."""
    items = "\n".join(
        f'{i+1}. [{p["province"]}] {p["name"]} ({p.get("sector","")}, {p.get("value","—")}, {p.get("status","")})'
        for i, p in enumerate(batch)
    )
    prompt = f"""For each numbered Canadian capital project below, write a single concise sentence (max 20 words) describing what the project is and who is building or operating it. Be specific — name the proponent if known.

Projects:
{items}

Respond ONLY with a JSON array of objects in this exact format, one per project, in the same order:
[{{"id": 1, "description": "..."}}, {{"id": 2, "description": "..."}}, ...]

No markdown fences. No extra text."""

    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    max_output_tokens=8192,
                )
            )
            result = json.loads(response.text)
            if isinstance(result, list):
                return {item['id']: item['description'] for item in result if 'id' in item and 'description' in item}
            return {}
        except Exception as e:
            if attempt == 4:
                print(f"  [ERROR] Gemini failed: {e}")
                return {}
            time.sleep(2 ** attempt)
    return {}


def backfill():
    conn = init_db()
    print("Loading projects from SQLite...")
    all_projects = get_all_projects(conn)

    needs_desc = [p for p in all_projects if not p.get('description')]

    print(f"  Total projects:        {len(all_projects)}")
    print(f"  Missing descriptions:  {len(needs_desc)}")

    if not needs_desc:
        print("Nothing to backfill.")
        conn.close()
        return

    updated = 0
    failed = 0

    for batch_start in range(0, len(needs_desc), BATCH_SIZE):
        batch = needs_desc[batch_start:batch_start + BATCH_SIZE]

        print(f"\nBatch {batch_start // BATCH_SIZE + 1} — projects {batch_start + 1}–{batch_start + len(batch)} of {len(needs_desc)}...")
        desc_map = get_descriptions(batch)

        for local_idx, project in enumerate(batch):
            gemini_id = local_idx + 1
            desc = desc_map.get(gemini_id, '').strip()
            if desc:
                updated_project = dict(project)
                updated_project['description'] = desc
                upsert_project(conn, updated_project)
                print(f"  [OK] {project['province']}: {project['name'][:60]}")
                updated += 1
            else:
                print(f"  [SKIP] No description returned for: {project['name'][:60]}")
                failed += 1

        time.sleep(2)  # polite pause between batches

    conn.close()
    print(f"\n{'='*52}")
    print(f"  BACKFILL COMPLETE")
    print(f"{'='*52}")
    print(f"  Updated:  {updated}")
    print(f"  Skipped:  {failed}")


if __name__ == "__main__":
    backfill()
