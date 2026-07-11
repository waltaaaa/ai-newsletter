#!/usr/bin/env python3
"""warehouse_report.py — connection-health report from the data warehouse.

Prints a per-connection health table (last success, status, consecutive
failures, overdue series) and writes docs/data/warehouse_status.json
(mirrored to public/data/ when present — deploy syncs public/ -> docs/).

Usage:
    python tools/warehouse_report.py            # report + write JSON
    python tools/warehouse_report.py --no-write # report only
    python tools/warehouse_report.py --json     # dump full JSON to stdout

Exit codes: 0 always (monitoring is informational; the deploy gate lives in
tools/validate_briefing_schema.py). Reads DB_PATH env var like db.py.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_warehouse import check_health, write_status_json, log_health_summary  # noqa: E402


def _fmt(v, width):
    s = "—" if v is None or v == "" else str(v)
    return s[:width].ljust(width)


def main() -> int:
    ap = argparse.ArgumentParser(description="Data-warehouse connection health report")
    ap.add_argument("--no-write", action="store_true",
                    help="Do not write warehouse_status.json")
    ap.add_argument("--json", action="store_true",
                    help="Dump full health JSON to stdout instead of a table")
    args = ap.parse_args()

    health = check_health()

    if args.json:
        print(json.dumps(health, indent=2, default=str))
    else:
        s = health["summary"]
        print(f"DATA WAREHOUSE — connection health as of {health['generated_at']}")
        print(f"  {s['ok']} ok / {s['warn']} warn / {s['critical']} critical / "
              f"{s['unknown']} never-recorded — "
              f"{s['overdue_series_total']} overdue series\n")
        header = (_fmt("CONNECTION", 26) + _fmt("HEALTH", 9) + _fmt("LAST STATUS", 12)
                  + _fmt("LAST SUCCESS", 21) + _fmt("FAILS", 6) + "OVERDUE SERIES")
        print(header)
        print("-" * len(header))
        order = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}
        for con in sorted(health["connections"],
                          key=lambda c: (order.get(c["health"], 9), c["id"])):
            overdue = ", ".join(
                f"{x['name']} (latest {x['latest_period'] or 'none'})"
                for x in con["overdue_series"]) or "—"
            succ = con["last_success_at"] or "never"
            if con["days_since_success"] is not None:
                succ = f"{succ[:10]} ({con['days_since_success']}d)"
            print(_fmt(con["id"], 26) + _fmt(con["health"], 9)
                  + _fmt(con["last_status"], 12) + _fmt(succ, 21)
                  + _fmt(con["consecutive_failures"], 6) + overdue)
        print()
        log_health_summary(health)

    if not args.no_write:
        paths = write_status_json(health=health)
        for p in paths:
            print(f"[WAREHOUSE] wrote {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
