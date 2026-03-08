"""
dedup_audit.py — One-time audit to find and merge duplicate projects in Firestore.

Checks for exact name+province duplicates and merges them:
- Keeps highest evidence count as primary
- Merges evidence arrays (never loses URLs)
- Keeps highest value_millions
- Keeps most advanced status
- Deletes secondary documents

Usage:
    python dedup_audit.py              # Dry run (report only)
    python dedup_audit.py --merge      # Actually merge duplicates
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import re
from collections import defaultdict
from datetime import datetime
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

# Status ordering for "most advanced" logic
STATUS_ORDER = {
    'Proposed': 0, 'Under Review': 1, 'Approved': 2,
    'Under Construction': 3, 'Paused': 3, 'Expansion': 3,
    'Operational': 4, 'Completed': 5, 'Cancelled': -1,
}

NAME_TO_CODE = {
    'British Columbia': 'BC', 'Alberta': 'AB', 'Saskatchewan': 'SK',
    'Manitoba': 'MB', 'Ontario': 'ON', 'Quebec': 'QC', 'Québec': 'QC',
    'New Brunswick': 'NB', 'Nova Scotia': 'NS',
    'Prince Edward Island': 'PE', 'PEI': 'PE',
    'Newfoundland and Labrador': 'NL', 'Newfoundland': 'NL',
    'Yukon': 'YT', 'Northwest Territories': 'NT', 'Nunavut': 'NU',
    'BC': 'BC', 'AB': 'AB', 'SK': 'SK', 'MB': 'MB', 'ON': 'ON',
    'QC': 'QC', 'NB': 'NB', 'NS': 'NS', 'PE': 'PE', 'NL': 'NL',
    'YT': 'YT', 'NT': 'NT', 'NU': 'NU',
}


def norm_province(raw):
    if not raw:
        return ''
    raw = raw.strip()
    return NAME_TO_CODE.get(raw, raw[:2].upper())


def parse_value(val_str):
    """Parse a value string like 'C$1.2B' or 'C$500M' to millions."""
    if not val_str or val_str == 'Not disclosed':
        return 0
    val_str = str(val_str).replace(',', '').strip()
    try:
        m = re.search(r'[\$]?\s*([\d.]+)\s*([BbMm])', val_str)
        if m:
            num = float(m.group(1))
            unit = m.group(2).upper()
            return num * 1000 if unit == 'B' else num
        return float(re.sub(r'[^\d.]', '', val_str))
    except (ValueError, TypeError):
        return 0


def merge_evidence(primary_ev, secondary_ev):
    """Merge evidence arrays without losing URLs."""
    seen_urls = set()
    merged = []
    for ev in (primary_ev or []):
        url = ev.get('url', '')
        if url:
            seen_urls.add(url)
        merged.append(ev)
    for ev in (secondary_ev or []):
        url = ev.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(ev)
    return merged


def merge_sources(primary_src, secondary_src):
    """Merge sources arrays without losing URLs."""
    seen_urls = set()
    merged = []
    for s in (primary_src or []):
        url = s.get('url', '')
        if url:
            seen_urls.add(url)
        merged.append(s)
    for s in (secondary_src or []):
        url = s.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(s)
    return merged


def audit_duplicates(do_merge=False):
    """Find and optionally merge duplicate projects."""
    print("[DEDUP AUDIT] Loading all projects from Firestore...")
    projects = []
    for doc in db.collection("projects").stream():
        data = doc.to_dict()
        data["_id"] = doc.id
        data["_ref"] = doc.reference
        projects.append(data)

    print(f"  Total projects: {len(projects)}")

    # Group by normalized name + province code
    groups = defaultdict(list)
    for p in projects:
        name = (p.get("name") or "").lower().strip()
        prov = norm_province(p.get("province", ""))
        key = f"{prov}:{name}"
        groups[key].append(p)

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    unique_keys = len(groups)
    dup_groups = len(duplicates)
    dup_projects = sum(len(v) for v in duplicates.values())

    print(f"  Unique name+province keys: {unique_keys}")
    print(f"  Duplicate groups: {dup_groups}")
    print(f"  Projects in duplicate groups: {dup_projects}")
    print(f"  Projects that would be removed: {dup_projects - dup_groups}")

    if not duplicates:
        print("\n[DEDUP AUDIT] No duplicates found.")
        return

    # Show top 20 duplicate groups
    print(f"\n  Top duplicate groups (showing up to 20):")
    sorted_dupes = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)
    for key, dupes in sorted_dupes[:20]:
        print(f"    {key}: {len(dupes)} copies")
        for d in dupes[:3]:
            val = d.get("value", "?")
            ev = len(d.get("evidence", []))
            st = d.get("status", "?")
            print(f"      - {d['_id']}: value={val}, evidence={ev}, status={st}")

    if not do_merge:
        print(f"\n[DEDUP AUDIT] Dry run complete. Run with --merge to merge duplicates.")
        return

    # Merge duplicates
    print(f"\n[DEDUP AUDIT] Merging {dup_groups} duplicate groups...")
    merged_count = 0
    deleted_count = 0

    for key, dupes in duplicates.items():
        # Sort: highest evidence count first, then highest value
        dupes.sort(key=lambda x: (
            len(x.get("evidence", [])),
            parse_value(x.get("value")),
            STATUS_ORDER.get(x.get("status", ""), 0),
        ), reverse=True)

        primary = dupes[0]
        primary_ref = primary["_ref"]

        for secondary in dupes[1:]:
            # Merge evidence arrays
            merged_ev = merge_evidence(
                primary.get("evidence"), secondary.get("evidence"))

            # Merge sources
            merged_src = merge_sources(
                primary.get("sources"), secondary.get("sources"))

            # Merge discovery_sources
            disc_src = list(set(
                (primary.get("discovery_sources") or []) +
                (secondary.get("discovery_sources") or [])
            ))

            # Keep highest value
            prim_val = parse_value(primary.get("value"))
            sec_val = parse_value(secondary.get("value"))
            best_value = primary.get("value") if prim_val >= sec_val else secondary.get("value")

            # Keep most advanced status
            prim_status_rank = STATUS_ORDER.get(primary.get("status", ""), 0)
            sec_status_rank = STATUS_ORDER.get(secondary.get("status", ""), 0)
            best_status = primary.get("status") if prim_status_rank >= sec_status_rank else secondary.get("status")

            # Update primary
            update = {
                "evidence": merged_ev,
                "evidence_count": len(merged_ev),
                "sources": merged_src,
                "discovery_sources": disc_src,
                "value": best_value,
                "status": best_status,
            }

            # Merge proponent if primary is missing it
            if not primary.get("proponent") and secondary.get("proponent"):
                update["proponent"] = secondary["proponent"]

            # Merge description if primary is missing it
            if not primary.get("description") and secondary.get("description"):
                update["description"] = secondary["description"]

            primary_ref.update(update)

            # Update primary dict for subsequent merges in same group
            primary["evidence"] = merged_ev
            primary["sources"] = merged_src
            primary["value"] = best_value
            primary["status"] = best_status

            # Delete secondary
            secondary["_ref"].delete()
            deleted_count += 1

        merged_count += 1

    print(f"  Merged {merged_count} groups, deleted {deleted_count} duplicate documents")
    print(f"\n[DEDUP AUDIT] Complete.")


if __name__ == "__main__":
    do_merge = "--merge" in sys.argv
    audit_duplicates(do_merge=do_merge)
