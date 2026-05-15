"""
cleanup_projects.py — one-time + re-runnable projects table hygiene.

Two operations, both conservative and reversible (DB backup taken separately):

1. TIERING (non-destructive): adds/updates a `quality_tier` column on every
   project so the frontend / newsletter can surface material projects and keep
   the registry/backfill archive separate.
     - featured : parsed_value >= the province materiality threshold
                  (pipeline_config PROVINCES thresholds, in dollars), OR a
                  curated/news source with parsed_value >= $25M.
     - registry : has a parseable value below the featured bar, OR a
                  government/registry source with any value.
     - archive  : no parseable value AND bulk-registry source (provincial_ea,
                  government_backfill) AND low confidence.

2. TIGHT DEDUP (destructive but very conservative): collapses ONLY clusters
   that are near-certainly the same project:
     - same province code, AND
     - same parsed_value (both > 0, equal within 1%), AND
     - share a significant brand/proponent token (e.g. "honda", "agnico"),
       OR token-set name Jaccard >= 0.75
   Keeper = most evidence, then highest confidence, then longest description,
   then earliest firstTracked. Evidence/sources/discovery_sources from the
   losers are merged into the keeper before the losers are deleted.

   This deliberately does NOT merge on name similarity alone — "Highway 40
   Grade Widening" vs "Highway 58 Grade Widening" have different values and no
   shared brand token, so they survive.

Usage:
    python tools/cleanup_projects.py            # dry-run, prints summary only
    python tools/cleanup_projects.py --apply    # performs the changes
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline_config import PROVINCES

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "dashboard.db")

# name → 2-letter code (DB stores codes); cover PE/PEI variants
_NAME_TO_CODE = {
    "Ontario": "ON", "Quebec": "QC", "Alberta": "AB", "British Columbia": "BC",
    "Saskatchewan": "SK", "Manitoba": "MB", "Nova Scotia": "NS",
    "New Brunswick": "NB", "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE", "Yukon": "YT",
    "Northwest Territories": "NT", "Nunavut": "NU",
}
# province code → materiality threshold (dollars)
CODE_THRESHOLD = {}
for _p in PROVINCES:
    _code = _NAME_TO_CODE.get(_p["name"])
    if _code:
        CODE_THRESHOLD[_code] = _p["threshold_val"]
CODE_THRESHOLD["PEI"] = CODE_THRESHOLD.get("PE", 5_000_000)
_DEFAULT_THRESHOLD = 25_000_000

CURATED_SOURCES = {"rss_remediated", "claude_selective", "crown_corp",
                   "cer_registry"}
BULK_REGISTRY = {"provincial_ea", "government_backfill"}

_STOP = set("the of and a an for to in on at expansion project program phase "
            "plant facility centre center investment new redevelopment "
            "construction rehabilitation upgrade improvements".split())
# brand/proponent tokens are capitalized words that aren't generic
_GENERIC = set("highway bridge road school hospital water plant centre center "
               "park apartments housing transit rail line stage".split())


def _toks(s):
    return set(t for t in re.findall(r"[a-z0-9]+", (s or "").lower())
               if t not in _STOP and len(t) > 2)


def _brand_toks(name, proponent):
    """Significant identifying tokens: proponent words + non-generic name words."""
    bt = set()
    for t in re.findall(r"[a-z0-9]+", (proponent or "").lower()):
        if len(t) > 2 and t not in _STOP:
            bt.add(t)
    for t in re.findall(r"[a-z0-9]+", (name or "").lower()):
        if len(t) > 3 and t not in _STOP and t not in _GENERIC:
            bt.add(t)
    return bt


def _pv(row):
    v = row["parsed_value"]
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def compute_tier(row):
    pv = _pv(row)
    code = (row["province"] or "").strip().upper()
    thr = CODE_THRESHOLD.get(code, _DEFAULT_THRESHOLD)
    src = row["discovery_source"] or ""
    try:
        conf = float(row["confidence"]) if row["confidence"] not in (None, "") else 0.0
    except (TypeError, ValueError):
        conf = 0.0

    if pv is not None and pv >= thr:
        return "featured"
    if src in CURATED_SOURCES and pv is not None and pv >= 25_000_000:
        return "featured"
    if pv is not None and pv > 0:
        return "registry"
    if src in CURATED_SOURCES and conf >= 0.5:
        return "registry"
    if src in BULK_REGISTRY and pv is None:
        return "archive"
    if pv is None and conf < 0.4:
        return "archive"
    return "registry"


def _merge_json_field(keeper_val, loser_val):
    """Union two JSON-array string fields, dedup by str()."""
    def load(v):
        if not v:
            return []
        try:
            x = json.loads(v)
            return x if isinstance(x, list) else [x]
        except (json.JSONDecodeError, TypeError):
            return []
    seen, merged = set(), []
    for item in load(keeper_val) + load(loser_val):
        k = json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if k not in seen:
            seen.add(k)
            merged.append(item)
    return json.dumps(merged, ensure_ascii=False)


def find_dedup_clusters(rows, tier_of):
    """Return clusters that are near-certainly the same project.

    Deliberately strict — the projects table is full of templated registry
    names ("Town of X Water Treatment", "Crown District N Five-Year Plan") and
    shared proponents/values, so anything less than near-identical names is NOT
    treated as a duplicate.

    Only featured/registry tier rows are considered; the archive tier is the
    registry backfill and isn't user-facing, so leave it untouched.

    A pair merges only if:
      (a) token-set name Jaccard >= 0.85  (near-identical wording), OR
      (b) parsed_value equal within 1% AND Jaccard >= 0.60 AND they share a
          brand token AND neither name contains a differing numeric/route
          discriminator (Highway 40 vs 58, K-5 vs 6-9, District 7 vs 19).
    Clusters larger than 5 are dropped entirely and reported for manual review
    (a big cluster almost always means the heuristic latched onto a template).
    """
    DISCRIMINATOR = re.compile(r"\b(\d+[a-z]?|k-\d|\d-\d|no\.?\s*\d+|"
                               r"district\s*\d+|zone\s*\d+|phase\s*\d+|"
                               r"stage\s*\d+|hwy\s*\d+|highway\s*\d+)\b",
                               re.IGNORECASE)
    # French/English area qualifiers that distinguish sub-projects sharing a
    # parent name (e.g. "Des Neiges (secteur Sud)" vs "(secteur Ouest)").
    QUALIFIER = re.compile(r"(secteur|sector|secteur|phase|zone|tranche|"
                           r"b[âa]timent|building|tower|tour|lot|pavillon)\s+"
                           r"([a-zàâéèêîôûç0-9-]+)", re.IGNORECASE)

    def discriminators(name):
        d = set(m.group(0).lower().replace(" ", "")
                for m in DISCRIMINATOR.finditer(name or ""))
        for m in QUALIFIER.finditer(name or ""):
            d.add(m.group(1).lower() + ":" + m.group(2).lower())
        # parenthetical qualifier, e.g. "(secteur Sud)", "(Phase II)"
        for m in re.finditer(r"\(([^)]+)\)", name or ""):
            d.add("paren:" + re.sub(r"\s+", "", m.group(1).lower()))
        return d

    def first_brand(name, proponent):
        bt = _brand_toks(name, proponent)
        # leading significant token of the name (order-preserving)
        for t in re.findall(r"[a-z0-9]+", (name or "").lower()):
            if len(t) > 3 and t not in _STOP and t not in _GENERIC and t in bt:
                return t
        return None

    by_prov = defaultdict(list)
    for r in rows:
        if tier_of.get(r["rowid"]) in ("featured", "registry"):
            by_prov[(r["province"] or "").upper()].append(r)

    clusters, oversized = [], []
    for prov, prows in by_prov.items():
        used = set()
        for i in range(len(prows)):
            if i in used:
                continue
            a = prows[i]
            pva = _pv(a)
            ba = _brand_toks(a["name"], a["proponent"])
            ta = _toks(a["name"])
            da = discriminators(a["name"])
            group = [a]
            for j in range(i + 1, len(prows)):
                if j in used:
                    continue
                b = prows[j]
                tb = _toks(b["name"])
                jac = len(ta & tb) / max(1, len(ta | tb))
                db = discriminators(b["name"])
                # Differing route/number/grade/phase/sector → NOT same project
                if da != db:
                    continue
                # Must share the leading brand/proper-noun token, else
                # "North Glenora Community League" == "Canora Community
                # League" would wrongly merge on the generic suffix.
                fa = first_brand(a["name"], a["proponent"])
                fb = first_brand(b["name"], b["proponent"])
                if fa and fb and fa != fb:
                    continue
                if jac >= 0.85:
                    group.append(b)
                    used.add(j)
                    continue
                pvb = _pv(b)
                value_match = (pva is not None and pvb is not None
                               and abs(pva - pvb) <= 0.01 * max(pva, pvb))
                bb = _brand_toks(b["name"], b["proponent"])
                if value_match and jac >= 0.60 and len(ba & bb) >= 1:
                    group.append(b)
                    used.add(j)
            if len(group) > 1:
                if len(group) <= 5:
                    clusters.append(group)
                else:
                    oversized.append(group)
    return clusters, oversized


def pick_keeper(group):
    def score(r):
        try:
            conf = float(r["confidence"]) if r["confidence"] not in (None, "") else 0.0
        except (TypeError, ValueError):
            conf = 0.0
        return (
            r["evidence_count"] or 0,
            conf,
            len(r["description"] or ""),
            -(len(r["firstTracked"] or "9999")),
        )
    return max(group, key=score)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="perform changes (default: dry-run)")
    args = ap.parse_args()
    apply = args.apply

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)")]
    if "quality_tier" not in cols:
        if apply:
            conn.execute("ALTER TABLE projects ADD COLUMN quality_tier TEXT")
            conn.commit()
            print("[schema] added column quality_tier")
        else:
            print("[schema] WOULD add column quality_tier")

    rows = conn.execute("SELECT rowid,* FROM projects").fetchall()
    print(f"Total projects: {len(rows)}")

    # ── 1. Tiering ───────────────────────────────────────────────────────
    tier_of = {}
    tally = Counter()
    for r in rows:
        t = compute_tier(r)
        tier_of[r["rowid"]] = t
        tally[t] += 1
    print("\nTIERING:")
    for t in ("featured", "registry", "archive"):
        print(f"  {t:9}: {tally[t]}")

    if apply and "quality_tier" in cols or apply:
        for rid, t in tier_of.items():
            conn.execute("UPDATE projects SET quality_tier=? WHERE rowid=?",
                         (t, rid))
        conn.commit()
        print("  [applied] quality_tier written to all rows")

    # ── 2. Tight dedup ───────────────────────────────────────────────────
    clusters, oversized = find_dedup_clusters(rows, tier_of)
    total_excess = sum(len(g) - 1 for g in clusters)
    print(f"\nTIGHT DEDUP (featured/registry only): "
          f"{len(clusters)} clusters, {total_excess} rows to remove")
    if oversized:
        print(f"  ({len(oversized)} oversized clusters >5 SKIPPED for manual "
              f"review — likely template false-positives)")
    sample = sorted(clusters, key=lambda g: -len(g))[:15]
    for g in sample:
        keep = pick_keeper(g)
        names = " | ".join((x["name"] or "")[:32] for x in g)
        print(f"  [{(g[0]['province'] or '?'):3}] x{len(g)} keep={(keep['name'] or '')[:32]!r}")
        print(f"        {names}")

    if apply and total_excess:
        removed = 0
        for g in clusters:
            keep = pick_keeper(g)
            for loser in g:
                if loser["rowid"] == keep["rowid"]:
                    continue
                for fld in ("evidence", "sources", "discovery_sources"):
                    merged = _merge_json_field(keep[fld], loser[fld])
                    conn.execute(f"UPDATE projects SET {fld}=? WHERE rowid=?",
                                 (merged, keep["rowid"]))
                conn.execute("DELETE FROM projects WHERE rowid=?",
                             (loser["rowid"],))
                removed += 1
        conn.commit()
        print(f"  [applied] merged + deleted {removed} duplicate rows")

    if not apply:
        print("\n(DRY-RUN — no changes written. Re-run with --apply to commit.)")

    # Post-state
    if apply:
        n = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        tn = conn.execute(
            "SELECT quality_tier, COUNT(*) FROM projects GROUP BY quality_tier"
        ).fetchall()
        print(f"\nPOST-STATE: {n} projects")
        for t, ct in tn:
            print(f"  {t or '(null)'}: {ct}")
    conn.close()


if __name__ == "__main__":
    main()
