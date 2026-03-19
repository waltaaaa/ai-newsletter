"""
dedup_merge.py — One-time deduplication merge for dashboard.db.

Merges verified duplicate project pairs. For each pair:
  1. Keeps the project with more data (higher value, more evidence, longer description)
  2. Merges evidence arrays (never loses URLs)
  3. Advances status to highest (non-regression rule)
  4. Archives the duplicate to projects_archive
  5. Logs the merge

Run: python dedup_merge.py [--dry-run]
"""

import json
import sqlite3
import sys
from datetime import date

DB_PATH = "dashboard.db"

# ── Verified true duplicate pairs ──────────────────────────────────────────
# Format: (keep_rowid, merge_rowid, reason)
# Carefully reviewed — only genuine same-project duplicates.
# Phase I/II, different stations, different schools, different locations are EXCLUDED.

MERGE_PAIRS = [
    # Exact or near-exact name duplicates
    (36355, 36402, "Canada Defence Industrial Strategy — exact duplicate"),
    (34073, 34083, "Yellowhead Trail Freeway Conversion — with/without 'Project'"),
    (34769, 34786, "Belleville Terminal Redevelopment — with/without 'Project'"),
    (36356, 36381, "Venture Newfoundland III — with/without 'Investment'"),
    (34934, 34939, "Pointe du Bois Renewable Energy — with/without '(PREP)'"),
    (36418, 36386, "Sherbrooke Economic Strategy — formatting difference"),
    (36403, 36379, "Winnipeg Transit Polycarbonate Shelter — 'Bus Shelter' vs 'Shelter'"),
    (36351, 36401, "R.W. Tomlinson Trap Rock — with/without 'Ltd.'"),
    (36413, 36377, "Hydro One Indigenous Equity Purchase — 'One' vs 'One Line'"),
    (36376, 36353, "Calgary Japanese Community Assoc Centre — '(CJCA)' vs full name"),
    (36358, 36382, "Taltson Hydroelectric — 'Facility' vs 'Plant'"),
    (36400, 36369, "Brome-Missisquoi Transit — with/without 'Funding'"),
    (36350, 36411, "Vancouver Hotel near Stanley Park — with/without 'Proposal'"),
    (36383, 36426, "Arctic Defence Spending — with/without 'and Arctic Infrastructure'"),
    (36361, 36416, "Fort McPherson Social Housing — with/without 'Modular'"),
    (36398, 36364, "Port of Algoma — with/without 'City of'"),
    (36425, 36380, "Winnipeg Sky Economy — with/without 'Aviation'"),
    (34948, 34953, "Portage Area Capacity Enhancement(s) — singular vs plural"),
    (34130, 34131, "Central East Transmission Development — Area vs Transfer Out"),
    (34759, 34758, "Eagle Mountain-Woodfibre Pipeline — 'Gas Pipeline' vs 'LNG Gas Pipeline Projects'"),

    # Same station with/without 'GO' suffix
    (36260, 36215, "Weston GO Station — with/without 'GO'"),
    (36266, 36263, "Downsview Park Station — with/without 'GO'"),
    (36259, 36214, "Bloor GO Station — with/without 'GO'"),

    # Same project different name formatting
    (36388, 36374, "Northern Defence Infrastructure Investment — with/without 'Yukon'"),
    (34570, 34915, "Pacific Future Energy Refinery — 'Oil Refinery' vs 'Refinery'"),
    (34734, 34710, "Crown Mountain Coal Project — 'Coal' vs 'Coking Coal'"),

    # Same project, one is funding portion (merge into main)
    (34577, 34638, "Surrey Langley SkyTrain — main ($6.0B) + ICIP funding ($1.4B)"),
    (35264, 35286, "Finch West LRT — main ($3.6B) + duplicate ($1.2B)"),

    # Un toit pour tous — 4 entries for same project (keep most detailed)
    (36407, 36384, "Un toit pour tous Phase 1 Longueuil — duplicate entry 1"),
    (36407, 36366, "Un toit pour tous Phase 1 Longueuil — duplicate entry 2"),
    (36407, 36417, "Un toit pour tous Phase 1 Longueuil — duplicate entry 3"),
]


def merge_evidence(keep_evidence_str: str, merge_evidence_str: str) -> str:
    """Combine evidence arrays, dedup by URL."""
    try:
        keep_ev = json.loads(keep_evidence_str) if keep_evidence_str else []
    except json.JSONDecodeError:
        keep_ev = []
    try:
        merge_ev = json.loads(merge_evidence_str) if merge_evidence_str else []
    except json.JSONDecodeError:
        merge_ev = []

    seen_urls = set()
    combined = []
    for ev in keep_ev + merge_ev:
        url = ev.get("url", "") if isinstance(ev, dict) else str(ev)
        if url and url not in seen_urls:
            combined.append(ev)
            seen_urls.add(url)
    return json.dumps(combined)


def merge_json_arrays(a_str: str, b_str: str) -> str:
    """Merge two JSON arrays, dedup by string representation."""
    try:
        a = json.loads(a_str) if a_str else []
    except json.JSONDecodeError:
        a = []
    try:
        b = json.loads(b_str) if b_str else []
    except json.JSONDecodeError:
        b = []
    seen = set(json.dumps(x, sort_keys=True) for x in a)
    for item in b:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            a.append(item)
            seen.add(key)
    return json.dumps(a)


STATUS_ORDER = {
    "Proposed": 0, "Under Review": 1, "Approved": 2,
    "Under Construction": 3, "Partially Complete": 4, "Complete": 5,
    "Cancelled": 10, "On Hold": 10, "Suspended": 10, "Paused": 10,
}


def do_merge(conn, keep_id: int, merge_id: int, reason: str, dry_run: bool):
    """Merge merge_id into keep_id."""
    keep = conn.execute("SELECT * FROM projects WHERE rowid = ?", (keep_id,)).fetchone()
    merge = conn.execute("SELECT * FROM projects WHERE rowid = ?", (merge_id,)).fetchone()

    if not keep:
        print(f"  SKIP: keep_id {keep_id} not found")
        return False
    if not merge:
        print(f"  SKIP: merge_id {merge_id} not found (already merged?)")
        return False

    keep = dict(keep)
    merge = dict(merge)

    # Determine what to update on the keep record
    updates = {}

    # Merge evidence (never lose URLs)
    combined_ev = merge_evidence(keep.get("evidence", "[]"), merge.get("evidence", "[]"))
    if combined_ev != keep.get("evidence", "[]"):
        updates["evidence"] = combined_ev

    # Merge discovery_sources
    combined_ds = merge_json_arrays(
        keep.get("discovery_sources", "[]"),
        merge.get("discovery_sources", "[]"),
    )
    if combined_ds != keep.get("discovery_sources", "[]"):
        updates["discovery_sources"] = combined_ds

    # Merge sources
    combined_src = merge_json_arrays(
        keep.get("sources", "[]"), merge.get("sources", "[]"),
    )
    if combined_src != keep.get("sources", "[]"):
        updates["sources"] = combined_src

    # Status: advance to highest (non-regression)
    keep_status_ord = STATUS_ORDER.get(keep.get("status", ""), 0)
    merge_status_ord = STATUS_ORDER.get(merge.get("status", ""), 0)
    if merge_status_ord > keep_status_ord and merge_status_ord < 10:
        updates["status"] = merge["status"]

    # Fill missing fields from merge
    for field in ["proponent", "description", "cma", "sector", "completionDate"]:
        if not keep.get(field) and merge.get(field):
            updates[field] = merge[field]

    # Use higher value
    keep_val = keep.get("value", "Not disclosed")
    merge_val = merge.get("value", "Not disclosed")
    if keep_val in ("Not disclosed", "", "—") and merge_val not in ("Not disclosed", "", "—"):
        updates["value"] = merge_val

    # Update evidence count
    try:
        new_count = len(json.loads(updates.get("evidence", keep.get("evidence", "[]"))))
        updates["evidence_count"] = new_count
    except (json.JSONDecodeError, TypeError):
        pass

    # Update lastUpdated
    updates["lastUpdated"] = date.today().isoformat()

    keep_name = keep.get("name", "?")[:50]
    merge_name = merge.get("name", "?")[:50]

    if dry_run:
        print(f"  DRY-RUN: Would merge #{merge_id} ({merge_name}) into #{keep_id} ({keep_name})")
        print(f"           Reason: {reason}")
        if updates:
            for k, v in updates.items():
                if k == "evidence":
                    print(f"           evidence: +merged")
                elif k in ("discovery_sources", "sources"):
                    print(f"           {k}: +merged")
                else:
                    print(f"           {k}: {str(keep.get(k, ''))[:30]} -> {str(v)[:30]}")
        return True

    # Apply updates to keep record
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [keep_id]
        conn.execute(f"UPDATE projects SET {set_clause} WHERE rowid = ?", values)

    # Archive the merge record
    # projects_archive schema: id, original_id, norm_key, name, province, data, archived_at, reason
    archive_data = json.dumps({
        k: merge[k] for k in merge.keys()
        if k not in ("rowid",) and merge[k] is not None
    })
    conn.execute(
        "INSERT INTO projects_archive (original_id, norm_key, name, province, data, archived_at, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            merge_id,
            merge.get("norm_key", ""),
            merge.get("name", ""),
            merge.get("province", ""),
            archive_data,
            date.today().isoformat(),
            f"dedup_merge: merged into #{keep_id} — {reason}",
        ),
    )

    # Delete the duplicate
    conn.execute("DELETE FROM projects WHERE rowid = ?", (merge_id,))

    print(f"  MERGED: #{merge_id} ({merge_name}) -> #{keep_id} ({keep_name})")
    return True


def main():
    dry_run = "--dry-run" in sys.argv

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    before = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"Projects before: {before}")
    print(f"Merge pairs: {len(MERGE_PAIRS)}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MERGE'}")
    print()

    merged = 0
    skipped = 0
    for keep_id, merge_id, reason in MERGE_PAIRS:
        if do_merge(conn, keep_id, merge_id, reason, dry_run):
            merged += 1
        else:
            skipped += 1

    if not dry_run:
        conn.commit()

    after = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"\nResults:")
    print(f"  Merged: {merged}")
    print(f"  Skipped: {skipped}")
    print(f"  Projects before: {before}")
    print(f"  Projects after:  {after}")
    print(f"  Removed: {before - after}")

    conn.close()


if __name__ == "__main__":
    main()
