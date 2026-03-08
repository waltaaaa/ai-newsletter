"""
backfill_project_fields.py — One-time backfill of display_confidence and missing project_type.

Computes display_confidence from existing confidence + evidence_count fields.
Classifies project_type for the ~200 projects missing it using name heuristics.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import re
from datetime import date
from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa:
        cred = credentials.Certificate(json.loads(sa))
    else:
        cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()


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
    print("[BACKFILL] Loading all projects from Firestore...")
    docs = list(db.collection('projects').stream())
    print(f"  {len(docs)} projects loaded")

    batch = db.batch()
    batch_count = 0
    total_updated = 0
    type_classified = 0

    for doc in docs:
        d = doc.to_dict()
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
            batch.update(doc.reference, updates)
            batch_count += 1
            total_updated += 1

        # Commit every 490 (Firestore batch limit is 500)
        if batch_count >= 490:
            batch.commit()
            print(f"  Committed batch ({total_updated} so far)...")
            batch = db.batch()
            batch_count = 0

    # Final batch
    if batch_count > 0:
        batch.commit()

    print(f"\n[BACKFILL] Complete:")
    print(f"  Total updated: {total_updated}")
    print(f"  project_type classified: {type_classified}")
    print(f"  display_confidence set: {total_updated}")


if __name__ == "__main__":
    backfill_all()
