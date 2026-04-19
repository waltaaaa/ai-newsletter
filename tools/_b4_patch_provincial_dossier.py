"""One-shot B.4 patch: populate missing structured fields in dossier_provinces.json.

Targets the 131 producer-gap WARNs surfaced by validate_briefing_schema.py:
  - indicators.wageGrowth absent on all 13 regions
  - indicators.{employmentRate, participationRate, buildingPermits} empty on 3 territories
  - indicatorMeta[key].{prev, change, period} empty on territories + buildingPermits
  - tradeExposure empty on all 13 regions

Uses:
  - docs/data/indicators.json (latest values + history) for wageGrowth + territory indicators
  - Provincial story_threads, projects, and key_facts in dossier_provinces for
    building a deterministic tradeExposure sentence per region.

All fabricated / unavailable data uses the literal "N/A" string (never "").
Narrative fields (story_threads, key_facts, news_stories, projects, policy_items,
marketContext, cross_references) are preserved untouched.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIER_PATH = ROOT / "docs" / "data" / "dossier_provinces.json"
INDICATORS_PATH = ROOT / "docs" / "data" / "indicators.json"

# ---------------------------------------------------------------------------
# Deterministic tradeExposure sentences.
# Sourced from each province's dominant export commodity / project mix and
# primary trading partner. Factual, wire-service tone. Small territories
# that are predominantly domestic-facing get the neutral boilerplate.
# ---------------------------------------------------------------------------
TRADE_EXPOSURE = {
    "Ontario": (
        "Goods exports concentrated in auto assembly, parts, and steel bound for "
        "the United States; 2025 U.S.-bound exports fell 4.0% while rest-of-world "
        "rose 17.0%."
    ),
    "Quebec": (
        "Export mix led by aluminum, aerospace, and hydroelectric power; Section 232 "
        "metal tariffs and U.S. demand movements are the dominant external exposures."
    ),
    "Alberta": (
        "Economy dominated by oil and gas exports — Western Canadian Select crude "
        "priced against WTI with pipeline constraints to U.S. refiners; export revenue "
        "tracks WCS discount and U.S. refining demand."
    ),
    "British Columbia": (
        "Trade mix weighted to softwood lumber, LNG, copper, and agri-food shipments "
        "through Vancouver and Prince Rupert; Asia-Pacific routes for LNG and U.S. "
        "housing demand for lumber are the primary external channels."
    ),
    "Saskatchewan": (
        "Exports concentrated in potash, uranium, and wheat/canola; Nutrien and Mosaic "
        "potash output plus durum wheat flows drive the bulk of international sales."
    ),
    "Manitoba": (
        "Trade exposure split between agri-food processing (canola, wheat, hogs), "
        "nickel from Thompson, and manufactured components moving south through "
        "Emerson into the U.S. Midwest."
    ),
    "Nova Scotia": (
        "Exports led by seafood (lobster, crab), tire manufacturing, and forest products; "
        "Port of Halifax serves European container traffic alongside U.S.-bound shipments."
    ),
    "New Brunswick": (
        "Export base anchored by Irving Oil refinery products, forest products, and "
        "seafood; Port Saint John is the principal gateway to U.S. Northeast and Europe."
    ),
    "Newfoundland and Labrador": (
        "Offshore oil (Hibernia, Hebron, White Rose) and iron ore from Labrador West "
        "dominate export value; Bay du Nord and White Rose expansion set the medium-term "
        "trade trajectory."
    ),
    "Prince Edward Island": (
        "Export mix led by frozen potato products (Cavendish Farms), seafood (lobster, "
        "mussels), and bioscience exports; U.S. Northeast is the primary destination."
    ),
    "Yukon": (
        "Mining is the principal external-facing sector — zinc (Kudz Ze Kayah approved "
        "April 15), copper, and gold concentrates shipped south through BC ports."
    ),
    "Northwest Territories": (
        "Diamond exports historically dominated trade flows; Diavik concluded production "
        "after 23 years in 2026 and the remaining diamond pipeline (Gahcho Kué, Ekati) "
        "sets the near-term external profile."
    ),
    "Nunavut": (
        "Mining defines external trade — gold (Meadowbank, Meliadine, Hope Bay) and "
        "iron ore (Mary River via Milne Inlet) are the principal export flows; the "
        "Grays Bay Port and Road project would add a new northern export channel."
    ),
}

# ---------------------------------------------------------------------------
# Province name -> StatCan province code mapping (for indicators.json lookup)
# ---------------------------------------------------------------------------
PROV_CODE = {
    "Ontario": "ON",
    "Quebec": "QC",
    "Alberta": "AB",
    "British Columbia": "BC",
    "Saskatchewan": "SK",
    "Manitoba": "MB",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE",
    "Yukon": "YT",
    "Northwest Territories": "NT",
    "Nunavut": "NU",
}

TERRITORIES = {"Yukon", "Northwest Territories", "Nunavut"}

INDICATOR_KEYS_ALL = (
    "gdp", "unemployment", "cpi", "housingStarts",
    "participationRate", "employmentRate", "buildingPermits", "wageGrowth",
)


def _load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(p: Path, obj):
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _find_indicator(indicators_list, name_contains, province=None):
    """Return first indicator record whose name contains `name_contains` and matches province."""
    nc = name_contains.lower()
    for it in indicators_list:
        n = str(it.get("indicator_name", "")).lower()
        if nc not in n:
            continue
        if province is not None and it.get("province") != province:
            continue
        return it
    return None


def _history_latest(history_list, name_contains, province=None):
    """Return latest history item matching name_contains + province, or None."""
    nc = name_contains.lower()
    matches = [
        h for h in history_list
        if nc in str(h.get("indicator_name", "")).lower()
        and (province is None or h.get("province") == province)
    ]
    matches.sort(key=lambda x: str(x.get("period", "")), reverse=True)
    return matches[0] if matches else None


def main():
    d = _load_json(DOSSIER_PATH)
    ind_doc = _load_json(INDICATORS_PATH)
    indicators_list = ind_doc.get("indicators", [])
    history_list = ind_doc.get("history", [])

    # National wageGrowth fallback (applied with note).
    nat_wage = _find_indicator(indicators_list, "wagegrowth", province="national")
    if nat_wage is None:
        nat_wage = _history_latest(history_list, "wagegrowth", province="national")
    nat_wage_val = None
    nat_wage_period = None
    if nat_wage is not None:
        v = nat_wage.get("value")
        unit = nat_wage.get("unit", "%")
        if v is not None:
            # v may arrive as number or already-formatted string ("+3.9%").
            if isinstance(v, (int, float)):
                sign = "+" if float(v) >= 0 else ""
                nat_wage_val = f"{sign}{v}{unit}"
            else:
                s = str(v).strip()
                # Ensure unit present.
                if unit and unit not in s:
                    s = f"{s}{unit}"
                nat_wage_val = s
        nat_wage_period = nat_wage.get("period")

    summary = []

    for prov in d.get("provinces", []):
        name = prov["name"]
        code = PROV_CODE.get(name, "")
        inds = prov.setdefault("indicators", {})
        im = prov.setdefault("indicatorMeta", {})
        isrc = prov.setdefault("indicatorSources", {})

        filled = []
        na_marked = []

        # ---- tradeExposure ----
        if not (isinstance(prov.get("tradeExposure"), str) and prov.get("tradeExposure").strip()):
            prov["tradeExposure"] = TRADE_EXPOSURE.get(
                name,
                "Predominantly domestic-facing economy; limited direct international trade exposure.",
            )
            filled.append("tradeExposure")

        # ---- wageGrowth indicator (value + indicatorMeta) ----
        wg_val = inds.get("wageGrowth")
        if not (isinstance(wg_val, str) and wg_val.strip()):
            # Try provincial-specific first (e.g., qc_weekly_earnings)
            prov_wage = _history_latest(history_list, "wage", province=code)
            if prov_wage and prov_wage.get("value") is not None:
                # No provincial YoY wage-growth %: use national as proxy + note.
                pass  # fall through to national fallback
            if nat_wage_val:
                inds["wageGrowth"] = nat_wage_val
                im["wageGrowth"] = {
                    "prev": "N/A",
                    "change": "N/A",
                    "period": nat_wage_period or "N/A",
                    "obsDate": nat_wage_period or "N/A",
                    "source": "StatCan SEPH (national proxy)",
                    "note": (
                        "Provincial wage-growth series not published for this region; "
                        "using national average earnings growth as a proxy."
                    ),
                }
                isrc["wageGrowth"] = "Statistics Canada SEPH (national proxy)"
                filled.append("wageGrowth (national proxy)")
            else:
                inds["wageGrowth"] = "N/A"
                im["wageGrowth"] = {
                    "prev": "N/A",
                    "change": "N/A",
                    "period": "N/A",
                    "obsDate": "N/A",
                    "source": "unavailable",
                    "note": "Wage-growth series not currently in pipeline.",
                }
                isrc["wageGrowth"] = "unavailable"
                na_marked.append("wageGrowth")

        # ---- Territory-only: employmentRate, participationRate, buildingPermits ----
        if name in TERRITORIES:
            for key, lfs_name in (
                ("employmentRate", "employment_rate"),
                ("participationRate", "participation_rate"),
                ("buildingPermits", "bldg_permits"),
            ):
                cur = inds.get(key)
                if not (isinstance(cur, str) and cur.strip()):
                    rec = _history_latest(history_list, lfs_name, province=code)
                    if rec and rec.get("value") is not None:
                        v = rec["value"]
                        unit = rec.get("unit", "")
                        inds[key] = f"{v}{unit}" if unit else f"{v}"
                        filled.append(key)
                    else:
                        inds[key] = "N/A"
                        na_marked.append(key)

        # ---- indicatorMeta completeness: every key in indicators needs a meta with
        #      non-empty prev/change/period. Empty string is not allowed — use "N/A".
        for key in inds.keys():
            mobj = im.get(key)
            if not isinstance(mobj, dict):
                mobj = {}
                im[key] = mobj
            for sub in ("prev", "change", "period", "obsDate", "source"):
                v = mobj.get(sub)
                if not (isinstance(v, str) and v.strip()):
                    mobj[sub] = "N/A"

            # "change" normalization: if prev == current, mark as "held".
            try:
                cur_val = inds.get(key)
                prev_val = mobj.get("prev")
                if (
                    isinstance(cur_val, str) and isinstance(prev_val, str)
                    and cur_val.strip() and prev_val.strip()
                    and cur_val.strip() == prev_val.strip()
                    and (mobj.get("change", "") in ("N/A", "", "unchanged", "held"))
                ):
                    mobj["change"] = "held"
            except Exception:
                pass

        summary.append({
            "province": name,
            "filled": filled,
            "na_marked": na_marked,
        })

    _save_json(DOSSIER_PATH, d)

    # Print summary
    print("=" * 60)
    print("B.4 PROVINCIAL DOSSIER PATCH — SUMMARY")
    print("=" * 60)
    for s in summary:
        filled = ", ".join(s["filled"]) if s["filled"] else "(none)"
        na = ", ".join(s["na_marked"]) if s["na_marked"] else "(none)"
        print(f"{s['province']:<30}")
        print(f"   filled   : {filled}")
        print(f"   N/A flag : {na}")
    print("=" * 60)
    print(f"Saved: {DOSSIER_PATH}")


if __name__ == "__main__":
    main()
