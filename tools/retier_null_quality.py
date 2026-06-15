"""
retier_null_quality.py — Heal NULL quality_tier rows and apply upgrades.

quality_tier was added with no column DEFAULT, so pipeline-inserted rows
carried NULL and the exporter sorted them after 'archive'. db.upsert_project
now tiers at write time; this heals existing rows:
  - NULL tier -> computed tier
  - computed tier ranks higher than stored tier -> upgrade (never downgrade)

Usage (from backend/):
    python tools/retier_null_quality.py            # dry run
    python tools/retier_null_quality.py --apply
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from tools.cleanup_projects import compute_tier

RANK = {'featured': 2, 'registry': 1, 'archive': 0}


def run(apply: bool):
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'dashboard.db'))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT rowid, name, province, parsed_value, discovery_source, "
        "confidence, quality_tier FROM projects").fetchall()
    healed, upgraded = [], []
    for r in rows:
        computed = compute_tier(r)
        stored = r['quality_tier']
        if stored is None or stored == '':
            healed.append((r['rowid'], computed, r['name']))
        elif RANK.get(computed, 0) > RANK.get(stored, -1):
            upgraded.append((r['rowid'], computed, stored, r['name']))
    print(f"NULL tiers to heal: {len(healed)}")
    for rowid, tier, name in healed[:10]:
        print(f"  -> {tier}: {name[:70]}")
    print(f"Upgrades: {len(upgraded)}")
    for rowid, tier, old, name in upgraded[:15]:
        print(f"  {old} -> {tier}: {name[:70]}")
    if not apply:
        print("[DRY RUN] re-run with --apply")
        return
    with conn:
        for rowid, tier, _ in healed:
            conn.execute("UPDATE projects SET quality_tier=? WHERE rowid=?", (tier, rowid))
        for rowid, tier, _, _ in upgraded:
            conn.execute("UPDATE projects SET quality_tier=? WHERE rowid=?", (tier, rowid))
    print(f"Applied: {len(healed)} healed, {len(upgraded)} upgraded.")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    run(p.parse_args().apply)
