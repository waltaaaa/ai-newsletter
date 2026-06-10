"""
canary_recall_check.py — Weekly recall scorecard against the canary set.

Loads config/canary_projects.json (curated known-real Canadian capital
projects) and fuzzy-matches each canary against the live `projects` table.
For every canary the verdict is one of:

  found_with_correct_status — a DB row matches AND its status rank equals the
                              canary's expected lifecycle stage rank
  found                     — a DB row matches but the status rank differs
  missed                    — no DB row matches

Matching reuses tools/dedup_projects_fuzzy.py primitives (normalize_name,
fuzzy_match, distinctive_tokens, is_generic_name, norm_province, status_rank)
so the recall test and the dedup engine cannot drift apart. Generic-name
gating applies: canaries whose normalized name carries no project-identifying
token only match on exact normalized name + CMA agreement, never on fuzzy
ratio alone.

The projects table is READ-ONLY for this tool. The snapshot is persisted to
dashboard_state via db.save_dashboard_state under key
`canary_recall_<YYYYMMDD>` (fallback: .audit/canary_recall_<date>.json).

Usage (from backend/):
    python tools/canary_recall_check.py            # score + persist snapshot
    python tools/canary_recall_check.py --no-save  # score only, no persistence
    python tools/canary_recall_check.py --db path/to/dashboard.db
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from tools.dedup_projects_fuzzy import (  # noqa: E402
    normalize_name,
    fuzzy_match,
    distinctive_tokens,
    is_generic_name,
    norm_province,
    status_rank,
)

CANARY_PATH = _BACKEND_ROOT / "config" / "canary_projects.json"

# Minimum SequenceMatcher ratio for a fuzzy name match (mirrors the dedup
# tool's default threshold).
FUZZY_THRESHOLD = 0.85
# Minimum Jaccard overlap of distinctive tokens for a fuzzy match.
JACCARD_THRESHOLD = 0.5


# ── Pure matching logic (unit-testable, no DB) ──────────────────────────────

def _name_keys(canary: dict) -> list[str]:
    """All normalized name keys for a canary (name + aliases), deduped."""
    keys = []
    for raw in [canary.get("name", "")] + list(canary.get("aliases") or []):
        n = normalize_name(raw)
        if n and n not in keys:
            keys.append(n)
    return keys


def _names_match(canary_norm: str, project_norm: str,
                 canary_cma: str = "", project_cma: str = "") -> bool:
    """Does one normalized canary name match one normalized project name?"""
    if not canary_norm or not project_norm:
        return False
    if canary_norm == project_norm:
        if is_generic_name(canary_norm):
            # Generic vocabulary ("water treatment plant") is not identity —
            # require CMA agreement as corroboration.
            c, p = canary_cma.strip().lower(), project_cma.strip().lower()
            return bool(c and p and c == p)
        return True
    # Generic names never match on fuzzy ratio.
    if is_generic_name(canary_norm) or is_generic_name(project_norm):
        return False
    t1, t2 = distinctive_tokens(canary_norm), distinctive_tokens(project_norm)
    if not (t1 and t2):
        return False
    shared = t1 & t2
    if not shared:
        return False
    jacc = len(shared) / max(1, len(t1 | t2))
    if jacc < JACCARD_THRESHOLD:
        return False
    return fuzzy_match(canary_norm, project_norm) >= FUZZY_THRESHOLD


def match_canary(canary: dict, projects_by_prov: dict) -> dict:
    """Match one canary against the project rows of its province.

    `projects_by_prov` maps province code -> list of dicts with at least
    {name, norm (precomputed), status, cma}. Returns a result record:
    {name, province, sector, verdict, matched_name, matched_status,
     expected_status}.
    """
    prov = norm_province(canary.get("province", ""))
    expected_status = canary.get("lifecycle_stage", "")
    result = {
        "name": canary.get("name", ""),
        "province": prov,
        "sector": canary.get("sector", ""),
        "expected_status": expected_status,
        "verdict": "missed",
        "matched_name": None,
        "matched_status": None,
    }
    candidates = projects_by_prov.get(prov, [])
    canary_cma = canary.get("cma") or ""
    best = None
    best_ratio = -1.0
    for ckey in _name_keys(canary):
        for proj in candidates:
            if _names_match(ckey, proj["norm"], canary_cma, proj.get("cma") or ""):
                r = fuzzy_match(ckey, proj["norm"])
                if r > best_ratio:
                    best, best_ratio = proj, r
        if best is not None and best_ratio >= 0.999:
            break  # exact normalized hit — no better match possible
    if best is None:
        return result
    result["matched_name"] = best["name"]
    result["matched_status"] = best.get("status") or ""
    if status_rank(result["matched_status"]) == status_rank(expected_status):
        result["verdict"] = "found_with_correct_status"
    else:
        result["verdict"] = "found"
    return result


def score_canaries(canaries: list[dict], projects: list[dict]) -> dict:
    """Score every canary against the project rows. Pure function.

    `projects`: list of dicts with at least {name, province, status, cma}.
    Returns the full snapshot dict (results + by_province + by_sector +
    totals).
    """
    by_prov = defaultdict(list)
    for p in projects:
        by_prov[norm_province(p.get("province", ""))].append({
            "name": p.get("name", ""),
            "norm": normalize_name(p.get("name", "")),
            "status": p.get("status", ""),
            "cma": p.get("cma", "") or "",
        })

    results = [match_canary(c, by_prov) for c in canaries]

    def _bucket(keyfn):
        agg = defaultdict(lambda: {"found_with_correct_status": 0,
                                   "found": 0, "missed": 0, "total": 0})
        for r in results:
            b = agg[keyfn(r)]
            b[r["verdict"]] += 1
            b["total"] += 1
        return dict(sorted(agg.items()))

    totals = {"found_with_correct_status": 0, "found": 0, "missed": 0}
    for r in results:
        totals[r["verdict"]] += 1
    n = max(1, len(results))
    totals["total"] = len(results)
    totals["recall"] = round((totals["found"] + totals["found_with_correct_status"]) / n, 3)
    totals["status_accurate_recall"] = round(totals["found_with_correct_status"] / n, 3)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canary_count": len(canaries),
        "totals": totals,
        "by_province": _bucket(lambda r: r["province"]),
        "by_sector": _bucket(lambda r: r["sector"]),
        "results": results,
    }


# ── DB I/O ───────────────────────────────────────────────────────────────────

def load_canaries(path: Path = CANARY_PATH) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["canaries"]


def load_projects_readonly(db_path: str) -> list[dict]:
    """Read name/province/status/cma from the projects table, read-only."""
    import sqlite3
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(
            "SELECT name, province, status, cma FROM projects").fetchall()
        return [{"name": r[0], "province": r[1], "status": r[2], "cma": r[3]}
                for r in rows]
    finally:
        conn.close()


def persist_snapshot(snapshot: dict, db_path: str) -> str:
    """Persist via db.save_dashboard_state; fall back to .audit/ JSON file."""
    key = f"canary_recall_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    try:
        import sqlite3
        import db as dbmod
        conn = sqlite3.connect(db_path)
        try:
            dbmod.save_dashboard_state(conn, key, snapshot)
        finally:
            conn.close()
        return f"dashboard_state:{key}"
    except Exception as e:  # pragma: no cover — environment-dependent
        audit_dir = _BACKEND_ROOT / ".audit"
        audit_dir.mkdir(exist_ok=True)
        out = audit_dir / f"{key}.json"
        out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        return f"{out} (db save failed: {e})"


# ── Report ───────────────────────────────────────────────────────────────────

def print_report(snapshot: dict) -> None:
    t = snapshot["totals"]
    print(f"\nCANARY RECALL SCORECARD — {snapshot['generated_at'][:10]}")
    print(f"Canaries: {t['total']}  |  recall: {t['recall']:.1%}  |  "
          f"status-accurate recall: {t['status_accurate_recall']:.1%}")
    print(f"  found_with_correct_status: {t['found_with_correct_status']}")
    print(f"  found (status mismatch):   {t['found']}")
    print(f"  missed:                    {t['missed']}")

    def table(title, bucket):
        print(f"\n{title}")
        print(f"  {'key':<22} {'ok':>3} {'found':>6} {'miss':>5} {'total':>6}")
        for k, b in bucket.items():
            print(f"  {k:<22} {b['found_with_correct_status']:>3} "
                  f"{b['found']:>6} {b['missed']:>5} {b['total']:>6}")

    table("By province", snapshot["by_province"])
    table("By sector", snapshot["by_sector"])

    misses = [r for r in snapshot["results"] if r["verdict"] == "missed"]
    if misses:
        print("\nMissed canaries:")
        for r in misses:
            print(f"  [{r['province']}] {r['name']}")
    mismatches = [r for r in snapshot["results"] if r["verdict"] == "found"]
    if mismatches:
        print("\nStatus mismatches (found, wrong status):")
        for r in mismatches:
            print(f"  [{r['province']}] {r['name']}: expected "
                  f"{r['expected_status']!r}, DB has {r['matched_status']!r} "
                  f"(row: {r['matched_name']!r})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(_BACKEND_ROOT / "dashboard.db"),
                    help="Path to dashboard.db (default: backend/dashboard.db)")
    ap.add_argument("--canaries", default=str(CANARY_PATH),
                    help="Path to canary_projects.json")
    ap.add_argument("--no-save", action="store_true",
                    help="Do not persist the snapshot")
    args = ap.parse_args(argv)

    canaries = load_canaries(Path(args.canaries))
    projects = load_projects_readonly(args.db)
    print(f"Loaded {len(canaries)} canaries, {len(projects)} project rows.")

    snapshot = score_canaries(canaries, projects)
    print_report(snapshot)

    if not args.no_save:
        where = persist_snapshot(snapshot, args.db)
        print(f"\nSnapshot persisted to {where}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
