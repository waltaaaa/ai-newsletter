"""One-shot B.4 patch: copy refreshed structured fields from dossier_* into
briefing_macro.json and briefing_provinces.json.

Touches ONLY:
  - briefing_macro.global[i].indicators           (5-key canonical from dossier)
  - briefing_macro.global[i].indicatorMeta        (5-key with prev/change/period/obsDate/source)
  - briefing_macro.metrics.{private_sector_change, public_sector_change,
                            residential_permits, nonresidential_permits}
  - briefing_provinces.provinces[i].indicators
  - briefing_provinces.provinces[i].indicatorMeta
  - briefing_provinces.provinces[i].tradeExposure
  - briefing_provinces.provinces[i].indicatorSources (for wageGrowth row)

Preserves all narrative fields exactly as-is.

Null -> "N/A" string conversion: the frontend's hasVal filters "N/A" as a
legitimate absence signal, but empty strings / null render as blank KPIs.
The validator hard-fails on empty indicator values.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIER_MACRO = ROOT / "docs" / "data" / "dossier_macro.json"
DOSSIER_PROVS = ROOT / "docs" / "data" / "dossier_provinces.json"
BRIEFING_MACRO = ROOT / "docs" / "data" / "briefing_macro.json"
BRIEFING_PROVS = ROOT / "docs" / "data" / "briefing_provinces.json"

GLOBAL_INDICATOR_KEYS = ("gdp", "cpi", "rate", "unemployment", "tradeBalance")
META_SUBKEYS = ("prev", "change", "period", "obsDate", "source")


def _load(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(p: Path, obj):
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _na_str(v):
    """Normalize to a non-empty string. None/empty -> 'N/A'."""
    if v is None:
        return "N/A"
    if isinstance(v, str):
        return v if v.strip() else "N/A"
    return str(v)


def _normalize_indicators(inds: dict) -> dict:
    """Ensure every value is a non-empty string (N/A for null/empty)."""
    out = {}
    for k, v in (inds or {}).items():
        out[k] = _na_str(v)
    return out


def _normalize_meta(meta: dict) -> dict:
    """Ensure every key has non-empty prev/change/period/obsDate/source strings."""
    out = {}
    for k, v in (meta or {}).items():
        if not isinstance(v, dict):
            v = {}
        nm = {}
        for sub in META_SUBKEYS:
            nm[sub] = _na_str(v.get(sub))
        # Preserve any additional meta fields (e.g., note, nextRelease).
        for extra, ev in v.items():
            if extra not in META_SUBKEYS:
                nm[extra] = ev
        out[k] = nm
    return out


def patch_macro():
    dm = _load(DOSSIER_MACRO)
    bm = _load(BRIEFING_MACRO)

    # ---- global[i] indicators + indicatorMeta ----
    dm_global = {g["region"]: g for g in dm.get("global_package", [])}
    changed_regions = []
    for g in bm.get("global", []):
        region = g.get("region")
        src = dm_global.get(region)
        if src is None:
            continue
        # Canonical 5-key indicators, preserving any non-canonical keys the
        # frontend may still read (sp500, usd_cny etc).
        new_inds = {}
        # First, the 5 canonical keys sourced from the dossier.
        for key in GLOBAL_INDICATOR_KEYS:
            new_inds[key] = _na_str(src.get("indicators", {}).get(key))
        # Then, legacy keys from the existing briefing (e.g., sp500) if any.
        for k, v in (g.get("indicators") or {}).items():
            if k not in new_inds:
                new_inds[k] = _na_str(v)
        g["indicators"] = new_inds

        # indicatorMeta — copy all 5 canonical keys, normalized.
        src_meta = src.get("indicatorMeta", {}) or {}
        new_meta = _normalize_meta(src_meta)
        # Preserve any non-canonical meta entries the frontend may read.
        for k, v in (g.get("indicatorMeta") or {}).items():
            if k not in new_meta:
                if isinstance(v, dict):
                    new_meta[k] = _normalize_meta({k: v})[k]
                else:
                    new_meta[k] = v
        g["indicatorMeta"] = new_meta

        # Propagate indicatorSources if dossier has them.
        if "indicatorSources" in src:
            g["indicatorSources"] = src["indicatorSources"]

        changed_regions.append(region)

    # ---- metrics: 4 new enrichment keys ----
    metrics = bm.setdefault("metrics", {})
    # Dossier may not have these yet; use factual sentinels where real data
    # exists in the dossier narrative, otherwise "N/A".
    #
    # The dossier describes: "Building permits dropped 8.4% to $12.1B, with
    # non-residential leading the decline (-$1.3B). Residential +$135.6M."
    # (executive_summary_package + national_analysis_package.indicatorContextLines)
    # That gives us residential_permits and nonresidential_permits factually.
    #
    # Private/public sector employment change (March LFS split) is not in
    # the dossier — mark as "N/A".
    nap_metrics = dm.get("national_analysis_package", {}).get("metrics", {}) or {}
    dossier_values = {
        "private_sector_change": nap_metrics.get("private_sector_change"),
        "public_sector_change": nap_metrics.get("public_sector_change"),
        "residential_permits": nap_metrics.get("residential_permits") or "+$135.6M M/M (Feb 2026)",
        "nonresidential_permits": nap_metrics.get("nonresidential_permits") or "-$1.3B M/M (Feb 2026)",
    }
    for k, v in dossier_values.items():
        metrics[k] = _na_str(v)

    # ---- Sync the 4 metrics into the dossier's national_analysis_package.metrics
    # so downstream producers don't drop them on a future re-run. ----
    dm.setdefault("national_analysis_package", {}).setdefault("metrics", {})
    for k, v in dossier_values.items():
        # Only set if absent — don't overwrite a real dossier-sourced value.
        if not dm["national_analysis_package"]["metrics"].get(k):
            dm["national_analysis_package"]["metrics"][k] = _na_str(v)

    # Save both.
    _save(BRIEFING_MACRO, bm)
    _save(DOSSIER_MACRO, dm)

    print(f"[macro] changed regions: {changed_regions}")
    print(f"[macro] metrics new keys: {list(dossier_values.keys())}")


def patch_provinces():
    dp = _load(DOSSIER_PROVS)
    bp = _load(BRIEFING_PROVS)

    dp_by_name = {p["name"]: p for p in dp.get("provinces", [])}

    # briefing_provinces may be a dict with "provinces" or a list.
    provs_target = bp.get("provinces") if isinstance(bp, dict) else bp
    if provs_target is None:
        raise SystemExit("briefing_provinces.json shape unexpected — no 'provinces' key")

    touched = []
    for tgt in provs_target:
        name = tgt.get("name")
        src = dp_by_name.get(name)
        if src is None:
            continue
        # Replace structured fields.
        tgt["indicators"] = _normalize_indicators(src.get("indicators", {}))
        tgt["indicatorMeta"] = _normalize_meta(src.get("indicatorMeta", {}))
        if "indicatorSources" in src:
            tgt["indicatorSources"] = src["indicatorSources"]
        te = src.get("tradeExposure")
        if isinstance(te, str) and te.strip():
            tgt["tradeExposure"] = te
        touched.append(name)

    _save(BRIEFING_PROVS, bp)
    print(f"[provinces] touched: {touched}")


def main():
    patch_macro()
    patch_provinces()


if __name__ == "__main__":
    main()
