"""
backfill_project_fields.py — One-time backfill of display_confidence and missing project_type.

Computes display_confidence from existing confidence + evidence_count fields.
Classifies project_type for projects missing it using name heuristics.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import re
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from db import init_db, get_all_projects, upsert_project


def compute_display_confidence(confidence: float, evidence_count: int) -> str:
    """Compute human-readable confidence label."""
    try:
        confidence = float(confidence) if confidence else 0.0
    except (TypeError, ValueError):
        confidence = 0.0
    try:
        evidence_count = int(evidence_count) if evidence_count else 0
    except (TypeError, ValueError):
        evidence_count = 0

    # Score: weighted combination of confidence and evidence
    score = (confidence * 0.6) + (min(evidence_count, 10) / 10.0 * 0.4)

    if score >= 0.7:
        return "High"
    elif score >= 0.4:
        return "Medium"
    elif score >= 0.15:
        return "Low"
    else:
        return "Unverified"


def classify_project_type(name: str, description: str, sector: str) -> str:
    """Heuristic classification of project_type from name/description."""
    text = f"{name} {description} {sector}".lower()

    # Expansion/extension patterns
    if any(kw in text for kw in ['expansion', 'extension', 'phase 2', 'phase 3',
                                   'phase ii', 'phase iii', 'expand', 'twinning',
                                   'widening', 'additional']):
        return "expansion"

    # Refurbishment/renovation patterns
    if any(kw in text for kw in ['refurbish', 'renovation', 'retrofit', 'upgrade',
                                   'moderniz', 'rehabilitat', 'remediat', 'restore',
                                   'replacement', 'overhaul', 'repair']):
        return "refurbishment"

    # Brownfield/redevelopment
    if any(kw in text for kw in ['redevelop', 'brownfield', 'adaptive reuse',
                                   'conversion', 'repurpos']):
        return "brownfield"

    # Default to greenfield/new build
    return "greenfield"


def backfill_all():
    conn = init_db()
    print("[BACKFILL] Loading all projects from SQLite...")
    docs = get_all_projects(conn)
    print(f"  {len(docs)} projects loaded")

    total_updated = 0
    type_classified = 0

    for d in docs:
        updates = {}

        # Compute display_confidence
        conf = d.get('confidence', 0.0)
        ev_count = d.get('evidence_count', 0)
        display_conf = compute_display_confidence(conf, ev_count)
        updates['display_confidence'] = display_conf

        # Classify project_type if missing
        if not d.get('project_type'):
            pt = classify_project_type(
                d.get('name', ''),
                d.get('description', ''),
                d.get('sector', ''),
            )
            updates['project_type'] = pt
            updates['is_brownfield'] = pt in ('brownfield', 'refurbishment')
            type_classified += 1

        # Ensure is_brownfield is set
        if 'is_brownfield' not in d and 'is_brownfield' not in updates:
            pt = d.get('project_type', '')
            updates['is_brownfield'] = pt in ('brownfield', 'refurbishment')

        if updates:
            updated_project = dict(d)
            updated_project.update(updates)
            upsert_project(conn, updated_project)
            total_updated += 1

    conn.close()
    print(f"\n[BACKFILL] Complete:")
    print(f"  Total updated: {total_updated}")
    print(f"  project_type classified: {type_classified}")
    print(f"  display_confidence set: {total_updated}")


if __name__ == "__main__":
    backfill_all()
