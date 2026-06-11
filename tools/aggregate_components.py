"""
aggregate_components.py — Consolidate projects split across phase/stage
components into a single program entry.

For each group: primary = highest-value component, renamed to the program
name; value = sum of component values (value_scope='program'); sources and
evidence merged unique-by-URL; status = most advanced; the component split is
recorded in description and value_notes. Secondary rows are archived to
projects_archive and their child rows re-pointed to the primary.

Usage (from backend/):
    python tools/aggregate_components.py          # dry run
    python tools/aggregate_components.py --apply
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# rowids verified 2026-06-11; program display names chosen per source naming
GROUPS = [
    {"name": "Luna Solar Project", "rowids": [34087, 34088]},
    {"name": "Nunavut Broadband (National Satellite Initiative)", "rowids": [35227, 35240]},
    {"name": "Highway 175 Widening (Québec–Saguenay)", "rowids": [35448, 35462]},
    {"name": "Jansen Potash Project", "rowids": [35801, 35802]},
]

STATUS_ORDER = {
    "Cancelled": -1, "Proposed": 0, "Under Review": 1, "Approved": 2,
    "Under Construction": 3, "On Hold": 3, "Partially Complete": 4, "Complete": 5,
}

CHILD_TABLES = ["evidence", "project_events", "project_organizations",
                "project_identifiers", "project_changes", "project_alerts"]


def jload(s):
    try:
        v = json.loads(s or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def merge_by_url(*lists):
    seen, out = set(), []
    for lst in lists:
        for e in lst:
            u = (e.get("url") if isinstance(e, dict) else str(e)) or ""
            key = u or json.dumps(e, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                out.append(e)
    return out


def fmt_value(millions):
    if millions >= 1000:
        return f"C${millions/1000:.1f}B"
    return f"C${millions:.0f}M"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect("dashboard.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    for g in GROUPS:
        rows = [c.execute("select rowid, * from projects where rowid=?", (rid,)).fetchone()
                for rid in g["rowids"]]
        rows = [r for r in rows if r]
        if len(rows) < 2:
            print(f"!! group {g['name']}: components missing, skipping")
            continue
        rows.sort(key=lambda r: -(r["value_millions"] or 0))
        primary, secondaries = rows[0], rows[1:]

        total = sum(r["value_millions"] or 0 for r in rows)
        comp_desc = "; ".join(
            f"{r['name']} ({fmt_value(r['value_millions'] or 0)}, {r['status']})" for r in rows
        )
        note = (f"Aggregated program entry — split across {len(rows)} components: {comp_desc}. "
                f"Component values summed; components tracked as one project as of 2026-06-11.")

        status = max(rows, key=lambda r: STATUS_ORDER.get(r["status"], 0))["status"]
        evidence = merge_by_url(*[jload(r["evidence"]) for r in rows])
        sources = merge_by_url(*[jload(r["sources"]) for r in rows])
        disc = []
        for r in rows:
            for d in jload(r["discovery_sources"]):
                if d not in disc:
                    disc.append(d)
        hist = []
        seenh = set()
        for r in rows:
            for h in jload(r["statusHistory"]):
                k = json.dumps(h, sort_keys=True, default=str)
                if k not in seenh:
                    seenh.add(k)
                    hist.append(h)
        oids = []
        for r in rows:
            for o in jload(r["official_ids"]):
                if o not in oids:
                    oids.append(o)

        first = min((r["firstTracked"] or "9999" for r in rows))
        last = max((r["lastSeen"] or "" for r in rows))
        conf = max(r["confidence"] or 0 for r in rows)

        print(f"== {g['name']}: {len(rows)} components -> #{primary['rowid']}, "
              f"total {fmt_value(total)}, status {status}")
        print(f"   note: {note}")

        if not args.apply:
            continue

        desc = (primary["description"] or "").strip()
        new_desc = (note + (" | " + desc if desc else ""))[:2000]
        c.execute(
            """update projects set name=?, value=?, value_millions=?, parsed_value=?,
               value_scope='program', value_notes=?, status=?, evidence=?, sources=?,
               discovery_sources=?, statusHistory=?, official_ids=?, description=?,
               confidence=?, display_confidence=?, firstTracked=?, lastSeen=?,
               lastUpdated=?, evidence_count=? where rowid=?""",
            (g["name"], fmt_value(total), total, total * 1e6, note, status,
             json.dumps(evidence, default=str), json.dumps(sources, default=str),
             json.dumps(disc), json.dumps(hist, default=str), json.dumps(oids),
             new_desc, conf, conf, first, last, now, len(evidence), primary["rowid"]),
        )
        for s in secondaries:
            d = {k: s[k] for k in s.keys()}
            c.execute(
                "insert into projects_archive (original_id, norm_key, name, province, data, archived_at, reason) "
                "values (?,?,?,?,?,?,?)",
                (s["rowid"], s["norm_key"], s["name"], s["province"],
                 json.dumps(d, default=str), now,
                 f"component_aggregation: merged into #{primary['rowid']} — {g['name']}"),
            )
            for tbl in CHILD_TABLES:
                try:
                    c.execute(f"update {tbl} set project_id=? where project_id=?",
                              (primary["rowid"], s["rowid"]))
                except Exception:
                    pass
            c.execute("delete from projects where rowid=?", (s["rowid"],))
            print(f"   archived + removed component #{s['rowid']} {s['name']!r}")

    if args.apply:
        conn.commit()
        print("\nDone. Live count:", c.execute("select count(*) from projects").fetchone()[0])
    else:
        print("\nDRY RUN — no changes. Re-run with --apply.")


if __name__ == "__main__":
    main()
