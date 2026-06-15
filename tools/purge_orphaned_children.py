"""
purge_orphaned_children.py — Delete child rows referencing deleted projects.

Earlier cleanup passes deleted project rows over raw connections (SQLite
foreign_keys defaults OFF), stranding ~23k evidence rows and ~15k event rows
whose project_id no longer exists. Their URLs were already merged into keeper
rows' evidence JSON before deletion, so removing the orphans loses nothing.
Both merge tools now re-point children before deleting, so this is a one-time
heal plus an occasional hygiene check.

Usage (from backend/):
    python tools/purge_orphaned_children.py            # dry run
    python tools/purge_orphaned_children.py --apply
"""
import argparse
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CHILDREN = ('evidence', 'project_events', 'project_organizations',
            'project_identifiers')


def run(apply: bool):
    db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'dashboard.db')
    conn = sqlite3.connect(db)
    try:
        for t in CHILDREN:
            try:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {t} c LEFT JOIN projects p "
                    f"ON p.rowid = c.project_id WHERE p.rowid IS NULL"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                continue
            print(f"{t}: {n} orphaned rows")
            if apply and n:
                with conn:
                    conn.execute(
                        f"DELETE FROM {t} WHERE project_id NOT IN "
                        f"(SELECT rowid FROM projects)")
                print(f"  deleted.")
        if not apply:
            print("[DRY RUN] re-run with --apply")
    finally:
        conn.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    run(p.parse_args().apply)
