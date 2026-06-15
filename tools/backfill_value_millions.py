"""
backfill_value_millions.py — One-time heal: populate value_millions from parsed_value.

value_millions was schema-defined but never written by the pipeline (only the
Tavily cost batch set it), so ranking surfaces that sort by value_millions —
under_the_microscope candidate selection, briefing value rollups — treated
priced projects as $0. db.upsert_project now keeps the two columns in lockstep;
this script heals the existing rows.

Usage (from backend/):
    python tools/backfill_value_millions.py            # dry run, prints counts
    python tools/backfill_value_millions.py --apply    # write changes
"""
import argparse
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run(apply: bool):
    conn = sqlite3.connect('dashboard.db')
    try:
        n_candidates = conn.execute(
            "SELECT COUNT(*) FROM projects "
            "WHERE parsed_value IS NOT NULL AND parsed_value > 0 "
            "AND (value_millions IS NULL OR value_millions = 0)"
        ).fetchone()[0]
        n_priced = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE parsed_value IS NOT NULL AND parsed_value > 0"
        ).fetchone()[0]
        print(f"Projects with parsed_value: {n_priced}")
        print(f"Projects needing value_millions backfill: {n_candidates}")
        if not apply:
            print("[DRY RUN] Re-run with --apply to write.")
            return
        with conn:
            cur = conn.execute(
                "UPDATE projects SET value_millions = ROUND(parsed_value / 1000000.0, 3) "
                "WHERE parsed_value IS NOT NULL AND parsed_value > 0 "
                "AND (value_millions IS NULL OR value_millions = 0)"
            )
        print(f"Backfilled value_millions on {cur.rowcount} rows.")
    finally:
        conn.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true', help='Write changes (default: dry run)')
    run(p.parse_args().apply)
