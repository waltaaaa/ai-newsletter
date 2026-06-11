"""
remove_below_threshold.py — Archive + remove projects whose known value is below
the province GDP threshold (CLAUDE.md "Province GDP Thresholds").

Rules:
  - Only projects with a KNOWN value are judged (value_millions > 0).
    Unknown-value projects are untouched — absence of a value is not evidence
    the project is small.
  - Effective value = max(value_millions, value_high) so a stated range whose
    top end clears the bar is kept.
  - value_scope='phase' rows are SKIPPED — a single phase below threshold says
    nothing about the program total.
  - Removed rows go to projects_archive (full row JSON, reason
    'below_province_threshold') plus a JSON dump file; child rows in evidence,
    project_events, project_organizations, project_identifiers,
    project_changes, project_alerts are deleted with them.

Usage (from backend/):
    python tools/remove_below_threshold.py            # dry run
    python tools/remove_below_threshold.py --apply
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THRESH = {
    "ON": 500, "QC": 250, "AB": 200, "BC": 175, "SK": 45, "MB": 40,
    "NS": 25, "NB": 20, "NL": 17, "PE": 5, "YT": 3, "NT": 3, "NU": 3, "CA": 3,
}

CHILD_TABLES = [
    ("project_events", "project_id"),
    ("project_organizations", "project_id"),
    ("project_identifiers", "project_id"),
    ("project_changes", "project_id"),
    ("project_alerts", "project_id"),
    ("evidence", "project_id"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect("dashboard.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute(
        "select rowid, * from projects where value_millions is not null and value_millions > 0"
    ).fetchall()

    to_remove, skipped_phase, skipped_range = [], 0, 0
    for r in rows:
        t = THRESH.get(r["province"])
        if t is None:
            continue
        vm = r["value_millions"] or 0
        vh = r["value_high"] or 0
        eff = max(vm, vh)
        if vm >= t:
            continue
        if (r["value_scope"] or "") == "phase":
            skipped_phase += 1
            continue
        if eff >= t:
            skipped_range += 1
            continue
        to_remove.append(r)

    print(f"Candidates below threshold: {len(to_remove)}")
    print(f"Skipped (phase-scoped value): {skipped_phase}")
    print(f"Skipped (range top clears threshold): {skipped_range}")

    by_prov, by_tier = {}, {}
    for r in to_remove:
        by_prov[r["province"]] = by_prov.get(r["province"], 0) + 1
        by_tier[r["quality_tier"]] = by_tier.get(r["quality_tier"], 0) + 1
    print("By province:", dict(sorted(by_prov.items())))
    print("By quality_tier:", by_tier)
    feat = [r for r in to_remove if r["quality_tier"] == "featured"]
    if feat:
        print("\nFEATURED rows in removal set (review!):")
        for r in feat[:20]:
            print(f"  [{r['province']}] {r['name']} — ${r['value_millions']}M, {r['status']}")

    if not args.apply:
        print("\nDRY RUN — no changes. Re-run with --apply.")
        return

    now = datetime.now(timezone.utc).isoformat()
    dump_path = f"tools/removed_below_threshold_{now[:10]}.json"
    dump = []
    rowids = [r["rowid"] for r in to_remove]

    for r in to_remove:
        d = {k: r[k] for k in r.keys()}
        dump.append(d)
        c.execute(
            "insert into projects_archive (original_id, norm_key, name, province, data, archived_at, reason) "
            "values (?,?,?,?,?,?,?)",
            (r["rowid"], r["norm_key"], r["name"], r["province"],
             json.dumps(d, default=str), now, "below_province_threshold"),
        )

    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=1, default=str)

    qmarks = ",".join("?" * len(rowids))
    child_counts = {}
    for tbl, col in CHILD_TABLES:
        n = c.execute(f"delete from {tbl} where {col} in ({qmarks})", rowids).rowcount
        child_counts[tbl] = n
    n_proj = c.execute(f"delete from projects where rowid in ({qmarks})", rowids).rowcount
    conn.commit()

    print(f"\nRemoved {n_proj} projects (archived to projects_archive + {dump_path})")
    print("Child rows deleted:", child_counts)

    orphans = c.execute(
        "select count(*) from evidence where project_id not in (select rowid from projects)"
    ).fetchone()[0]
    print("Orphaned evidence rows after delete:", orphans)


if __name__ == "__main__":
    main()
