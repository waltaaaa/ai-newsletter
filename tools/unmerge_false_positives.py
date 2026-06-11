"""
unmerge_false_positives.py — Undo dedup merges that joined DISTINCT MB licence
filings (disjoint licence file numbers in gov.mb.ca evidence URLs).

Restores both sides of each false-positive cluster to their pre-merge state
from dashboard.db.predupe_20260611T120739:
  - keeper row: all columns reverted to backup values (matched by norm_key)
  - dropped row: re-inserted with its original rowid (free — no inserts since)
  - normalized `evidence` table rows re-pointed back to the restored rowid
    when their URL belongs to the restored row's evidence set

Usage (from backend/):
    python tools/unmerge_false_positives.py          # dry run
    python tools/unmerge_false_positives.py --apply
"""
import argparse
import json
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRE = "dashboard.db.predupe_20260611T120739"
LIVE = "dashboard.db"


def urls_of(evidence_json):
    out = []
    try:
        arr = json.loads(evidence_json or "[]")
    except Exception:
        arr = []
    for e in arr:
        u = e.get("url") if isinstance(e, dict) else str(e)
        if u:
            out.append(u)
    return out


def licence_ids(urls):
    ids = set()
    for u in urls:
        if "gov.mb.ca" not in u:
            continue
        fname = u.rstrip("/").split("/")[-1]
        for tok in re.findall(r"\d{3,4}", fname):
            ids.add(tok)
        m = re.search(r"registries/(\d+)", u)
        if m:
            ids.add(m.group(1))
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    pre = sqlite3.connect(PRE)
    pre.row_factory = sqlite3.Row
    live = sqlite3.connect(LIVE)
    live.row_factory = sqlite3.Row

    live_keys = {r[0] for r in live.execute("select norm_key from projects")}
    pre_rows = pre.execute("select rowid as rid, * from projects").fetchall()
    gone = [r for r in pre_rows if r["norm_key"] not in live_keys]

    to_restore = []  # (dropped_row, keeper_norm_key or None)
    for g in gone:
        gu = urls_of(g["evidence"])
        keeper = None
        for u in gu:
            hit = live.execute(
                "select norm_key, rowid as rid, evidence from projects "
                "where evidence like ? and province=?",
                (f"%{u}%", g["province"]),
            ).fetchone()
            if hit:
                keeper = hit
                break
        if keeper is None:
            # URL lost in merge — must restore to honour the URL-preservation invariant
            to_restore.append((g, None, "evidence URL lost in merge"))
            continue
        ku_own = [u for u in urls_of(keeper["evidence"]) if u not in gu]
        gid, kid = licence_ids(gu), licence_ids(ku_own)
        if g["province"] == "MB" and gid and kid and not (gid & kid):
            to_restore.append((g, keeper["norm_key"], "disjoint MB licence numbers"))

    print(f"Dropped rows in pre-merge backup: {len(gone)}")
    print(f"False-positive merges to restore: {len(to_restore)}")
    for g, k, why in to_restore:
        print(f"  restore #{g['rid']} {g['name']!r} (keeper={k}) — {why}")

    if not args.apply:
        print("\nDRY RUN — no changes. Re-run with --apply.")
        return

    pcols = [r[1] for r in live.execute("PRAGMA table_info(projects)")]
    restored, reverted, repointed = 0, 0, 0
    for g, keeper_key, _why in to_restore:
        # 1. re-insert dropped row with original rowid
        vals = [g[c] for c in pcols]
        qm = ",".join("?" * len(pcols))
        collist = ",".join(f'"{c}"' for c in pcols)
        live.execute(f"insert into projects ({collist}) values ({qm})", vals)
        restored += 1

        # 2. revert keeper to backup state
        if keeper_key:
            kb = pre.execute("select * from projects where norm_key=?", (keeper_key,)).fetchone()
            if kb:
                sets = ",".join(f'"{c}"=?' for c in pcols if c != "rowid")
                live.execute(
                    f"update projects set {sets} where norm_key=?",
                    [kb[c] for c in pcols if c != "rowid"] + [keeper_key],
                )
                reverted += 1
                # 3. re-point normalized evidence rows back to restored rowid
                keeper_rid = live.execute(
                    "select rowid from projects where norm_key=?", (keeper_key,)
                ).fetchone()[0]
                for u in urls_of(g["evidence"]):
                    cur = live.execute(
                        "update evidence set project_id=? where project_id=? and url=?",
                        (g["rid"], keeper_rid, u),
                    )
                    repointed += cur.rowcount

    live.commit()
    print(f"\nRestored {restored} dropped rows, reverted {reverted} keepers, "
          f"re-pointed {repointed} evidence rows.")
    print("Live project count:", live.execute("select count(*) from projects").fetchone()[0])


if __name__ == "__main__":
    main()
