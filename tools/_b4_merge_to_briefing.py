"""One-shot B.4 merge: overlay refreshed structured fields from
briefing_macro.json + briefing_provinces.json into briefing_latest.json.

Scope — narrow. Only structured fields, never narrative:
  - global[i].indicators, global[i].indicatorMeta, global[i].indicatorSources
  - metrics.{private_sector_change, public_sector_change,
             residential_permits, nonresidential_permits}
  - provinces[i].indicators, provinces[i].indicatorMeta,
    provinces[i].indicatorSources, provinces[i].tradeExposure

Everything else in briefing_latest.json (insightCharts, callouts, narratives,
sources arrays, watchlist, etc.) is preserved exactly as-is.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFING_MACRO = ROOT / "docs" / "data" / "briefing_macro.json"
BRIEFING_PROVS = ROOT / "docs" / "data" / "briefing_provinces.json"
BRIEFING_LATEST = ROOT / "docs" / "data" / "briefing_latest.json"

METRICS_KEYS = (
    "private_sector_change",
    "public_sector_change",
    "residential_permits",
    "nonresidential_permits",
)


def _load(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(p: Path, obj):
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def main():
    bm = _load(BRIEFING_MACRO)
    bp = _load(BRIEFING_PROVS)
    bl = _load(BRIEFING_LATEST)

    # ---- Metrics (new 4 enrichment keys) ----
    metrics = bl.setdefault("metrics", {})
    for k in METRICS_KEYS:
        if k in bm.get("metrics", {}):
            metrics[k] = bm["metrics"][k]

    # ---- Global indicators + indicatorMeta ----
    bm_global = {g.get("region"): g for g in bm.get("global", [])}
    for g in bl.get("global", []):
        region = g.get("region")
        src = bm_global.get(region)
        if src is None:
            continue
        g["indicators"] = src.get("indicators", g.get("indicators"))
        g["indicatorMeta"] = src.get("indicatorMeta", g.get("indicatorMeta"))
        if "indicatorSources" in src:
            g["indicatorSources"] = src["indicatorSources"]

    # ---- Provinces indicators + indicatorMeta + tradeExposure ----
    bp_list = bp.get("provinces") if isinstance(bp, dict) else bp
    bp_by_name = {p.get("name"): p for p in (bp_list or [])}
    for p in bl.get("provinces", []):
        name = p.get("name")
        src = bp_by_name.get(name)
        if src is None:
            continue
        # Preserve any existing indicator sub-keys the latest briefing may
        # have beyond the canonical 8 (e.g., capitalInvestment_qq). Merge
        # the refreshed set over the top so empty/null values get upgraded.
        existing = dict(p.get("indicators") or {})
        existing.update(src.get("indicators") or {})
        p["indicators"] = existing
        # indicatorMeta: same merge strategy — new keys win, extras preserved.
        existing_meta = dict(p.get("indicatorMeta") or {})
        for mk, mv in (src.get("indicatorMeta") or {}).items():
            existing_meta[mk] = mv
        p["indicatorMeta"] = existing_meta
        if "indicatorSources" in src:
            # Shallow merge — extend, don't replace
            existing_src = dict(p.get("indicatorSources") or {})
            existing_src.update(src["indicatorSources"])
            p["indicatorSources"] = existing_src
        te = src.get("tradeExposure")
        if isinstance(te, str) and te.strip():
            p["tradeExposure"] = te

    _save(BRIEFING_LATEST, bl)
    print(f"[latest] merged macro global + provinces structured fields into {BRIEFING_LATEST.name}")


if __name__ == "__main__":
    main()
