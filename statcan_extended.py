"""
statcan_extended.py — Extended StatCan WDS data collection.

Fetches investment, employment, trade, and housing indicators from 8 additional
StatCan tables beyond the base building permit data in statcan_permits.py.

Uses the same WDS REST API endpoint (getDataFromVectorsAndLatestNPeriods)
and parsing pattern as statcan_permits.py and phases/data_collection.py.

All indicators go to indicator_history via db.save_indicator() for
cross-referencing, trend analysis, and the weekly briefing.

Tables fetched:
  34-10-0175  Investment in building construction (quarterly)
  18-10-0135  Non-residential building construction price index (quarterly)
  34-10-0035  Capital and repair expenditures by industry (annual)
  14-10-0022  Employment by industry, monthly SA
  14-10-0326  Job vacancies by industry sector (quarterly)
  12-10-0163  Merchandise exports by commodity (monthly)
  34-10-0143  Housing starts by type and province (monthly)
  18-10-0205  New housing price index (monthly)

Zero cost — StatCan WDS API is free, no registration required.
"""

import logging
import time
import requests
from datetime import datetime

from db import save_indicator, format_indicator_change

logger = logging.getLogger(__name__)

_STATCAN_WDS_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
_WDS_HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)',
}

# ─────────────────────────────────────────────────────────────────────────────
# Extended indicator table definitions
# ─────────────────────────────────────────────────────────────────────────────
# Each group: table PID, frequency, and a dict mapping indicator names to
# (vector_id, unit, category) tuples.
#
# Vector IDs are for national-level aggregate series.
# If a vector returns no data, the code logs a warning and skips it.

# ── Investment & Capital Expenditure ──────────────────────────────────────────

# Table 34-10-0293-01: Investment in building construction (MONTHLY)
# Geography=Canada, current dollars. Active successor to the ARCHIVED quarterly
# cube 34-10-0175 (cubeEndDate 2023-10-01 — its vectors froze residential /
# non_residential building investment at 2023-Q4). Repointed 2026-06-15:
#   residential_building_investment      1014954064 -> 1705315946 (coord 1.2.1.3.0.0.0.0.0.0)
#   non_residential_building_investment  1014954170 -> 1705316166 (coord 1.13.1.3.0.0.0.0.0.0)
# Live-verified 2026-06-15: latest refPer 2026-03-01 = $15,521.9M / $7,039.5M.
# The new cube is MONTHLY (old was quarterly); values are still raw CAD → /1e6 for $M.
INVESTMENT_BUILDING_MONTHLY = {
    "table": "34-10-0293",
    "frequency": "monthly",
    "raw_dollars": True,  # values are in raw CAD, divide by 1e6 for $M
    "vectors": {
        "residential_building_investment":      (1705315946, "$M", "Investment"),
        "non_residential_building_investment":   (1705316166, "$M", "Investment"),
    },
}

# Table 34-10-0175-01: Investment in building construction (quarterly) — ARCHIVED.
# Cube end date 2023-10-01. residential / non_residential were migrated to the
# active monthly successor 34-10-0293 above (2026-06-15). The remaining three
# sub-sector vectors have no confirmed successor mapping yet and stay on the
# archived cube definition (the monthly freshness gate skips their stale obs —
# their state is unchanged from before the migration; not in scope of this fix).
INVESTMENT_BUILDING = {
    "table": "34-10-0175",
    "frequency": "quarterly",
    "raw_dollars": True,  # values are in raw CAD, divide by 1e6 for $M
    "vectors": {
        "industrial_building_investment":        (1014954182, "$M", "Investment"),
        "commercial_building_investment":        (1014954234, "$M", "Investment"),
        "institutional_building_investment":     (1014954316, "$M", "Investment"),
    },
}

# Table 18-10-0135-01: Non-residential building construction price index (quarterly)
# DISCONTINUED — no active vectors found via WDS coordinate search (2026-03-31).
# Old vector 18710109 returned year-2000 data. Kept as reference but not re-enabled.
CONSTRUCTION_PRICE_INDEX = {
    "table": "18-10-0135",
    "frequency": "quarterly",
    "vectors": {},  # empty — table discontinued
}

# Table 34-10-0035-01: Capital and repair expenditures by industry (annual)
# Geography=Canada, all industries, current dollars
# Vectors refreshed 2026-03-31 via WDS coordinate lookup (old vectors returned 2011 data)
CAPITAL_EXPENDITURES = {
    "table": "34-10-0035",
    "frequency": "annual",
    "vectors": {
        "total_capex":          (95923552, "$M", "Investment"),
        "construction_capex":   (95923606, "$M", "Investment"),
        "machinery_capex":      (95923660, "$M", "Investment"),
    },
}

# ── Employment (leading indicators) ──────────────────────────────────────────

# EMPLOYMENT_INDUSTRY (hardcoded-vector group for construction/manufacturing/
# mining_og employment from Table 14-10-0022) was DELETED 2026-06-19 (dead
# code). Its vectors were wrong (reliability audit C1: 2057622 resolved to
# "NL; Total employed" = 243k shipped mislabelled as Manufacturing). The group
# was already commented out of ALL_TABLE_GROUPS, and its three series are now
# name-resolved from the same cube in META_RESOLVED_GROUPS (construction_/
# manufacturing_/mining_og_employment) so a member rename fails loudly.

# Table 14-10-0326-01: Job vacancies by industry sector (quarterly)
# Geography=Canada, all employee sizes
JOB_VACANCIES = {
    "table": "14-10-0326",
    "frequency": "quarterly",
    "vectors": {
        "construction_vacancies":    (45169837, "count", "Employment"),
        "mining_vacancies":          (45169829, "count", "Employment"),
    },
}

# ── Trade ─────────────────────────────────────────────────────────────────────

# Table 12-10-0163-01: International merchandise trade by commodity, monthly
# Exports, balance of payments basis, seasonally adjusted, current $M.
# Re-resolved 2026-06-09 (D-15): the old vectors pointed at Table 12-10-0129,
# which is actually "Canadian domestic export CONCENTRATION" (ratios/indexes)
# and ended in 2003 — the root cause of agri_exports being frozen at 2003.
# 12-10-0121 (the prior commodity-trade cube) is archived (ended 2023-09);
# 12-10-0163 is its active successor (latest refPer 2026-04 at verification).
# NAPCS sections: Farm/fishing/intermediate food; Energy products; Metal ores
# and non-metallic minerals; Forestry products and building/packaging materials.
MERCHANDISE_EXPORTS = {
    "table": "12-10-0163",
    "frequency": "monthly",
    "vectors": {
        "energy_exports":    (1566911351, "$M", "Trade"),
        "mineral_exports":   (1566911365, "$M", "Trade"),
        "forestry_exports":  (1566911406, "$M", "Trade"),
        "agri_exports":      (1566911339, "$M", "Trade"),
    },
}

# ── Housing ───────────────────────────────────────────────────────────────────

# Table 34-10-0143-01: Housing starts, by type and province (monthly)
# Geography=Canada, all areas
# Vectors refreshed 2026-03-31 via WDS coordinate lookup (old vectors returned 2009-2011 data)
HOUSING_STARTS = {
    "table": "34-10-0143",
    "frequency": "monthly",
    "vectors": {
        "housing_starts_total":    (729949, "units", "Housing"),
        "housing_starts_single":   (729996, "units", "Housing"),
        "housing_starts_multi":    (13946611, "units", "Housing"),
    },
}

# Table 18-10-0205-01: New housing price index (monthly)
# Geography=Canada, total (house + land), 201612=100
# Vector refreshed 2026-03-31 via WDS coordinate lookup (old vector 111350082 was terminated)
HOUSING_PRICE_INDEX = {
    "table": "18-10-0205",
    "frequency": "monthly",
    "vectors": {
        "new_housing_price_index":    (111955442, "index", "Housing"),
    },
}

# ── Metadata-resolved national & sector series (2026-06-11) ──────────────────
#
# Replaces the dormant 2026-04-19 "NATIONAL_* placeholder" groups that sat
# behind _NATIONAL_LFS_VERIFIED=False waiting for hand-verified vector IDs.
# (National LFS rates and wage growth are NOT duplicated here — Phase 1
# data_collection.py already fetches participationRate / employmentRate /
# unemployment / wageGrowth at province='national'.)
#
# These series are resolved AT RUNTIME from cube metadata instead of
# hardcoded vectors: getCubeMetadata → match dimension members BY NAME →
# getDataFromCubePidCoordAndLatestNPeriods. Every observation must then pass
# (a) a plausibility range for the series and (b) the freshness gate before
# being saved. A renamed member, archived cube, or wrong match fails loudly
# and saves nothing — the failure mode that froze agri_exports at 2003 data
# (D-15) cannot recur silently through this path.
#
# indicator_name keys deliberately match what the frontend Key Indicators
# tables (IND_KEY_INDICATORS in docs/js/app.js) already reference.
#
# Per-series spec: members = name patterns (exact match preferred, then
# prefix, case-insensitive — one per cube dimension; unmatched dimensions
# abort the series), unit, category, range = inclusive plausibility bounds
# AFTER scalar normalization ($-series are normalized to $M).

_LFS_COMMON = ["Canada", "Employment", "Both sexes", "Total - Gender", "15 years and over"]

META_RESOLVED_GROUPS = [
    {
        # LFS employment by industry — extends the 3 hardcoded sectors in
        # EMPLOYMENT_INDUSTRY to the sectors the frontend tables reference.
        # (Finance, real estate, information, and admin/support are LFS
        # aggregates with no standalone series at this granularity — the
        # frontend intentionally omits or footnotes those.)
        "table": "14-10-0022",
        "frequency": "monthly",
        "series": {
            "ag_employment":                 {"members": _LFS_COMMON + ["Agriculture"], "unit": "thousands", "category": "Employment", "range": (100, 450)},
            "utilities_employment":          {"members": _LFS_COMMON + ["Utilities"], "unit": "thousands", "category": "Employment", "range": (60, 300)},
            "wholesale_employment":          {"members": _LFS_COMMON + ["Wholesale trade"], "unit": "thousands", "category": "Employment", "range": (300, 1000)},
            "retail_employment":             {"members": _LFS_COMMON + ["Retail trade"], "unit": "thousands", "category": "Employment", "range": (1600, 3100)},
            "transportation_employment":     {"members": _LFS_COMMON + ["Transportation and warehousing"], "unit": "thousands", "category": "Employment", "range": (600, 1700)},
            "professional_employment":       {"members": _LFS_COMMON + ["Professional, scientific and technical services"], "unit": "thousands", "category": "Employment", "range": (1200, 2800)},
            "education_employment":          {"members": _LFS_COMMON + ["Educational services"], "unit": "thousands", "category": "Employment", "range": (1000, 2300)},
            "healthcare_employment":         {"members": _LFS_COMMON + ["Health care and social assistance"], "unit": "thousands", "category": "Employment", "range": (1900, 3900)},
            "accommodation_food_employment": {"members": _LFS_COMMON + ["Accommodation and food services"], "unit": "thousands", "category": "Employment", "range": (700, 1800)},
            "other_services_employment":     {"members": _LFS_COMMON + ["Other services"], "unit": "thousands", "category": "Employment", "range": (450, 1300)},
            "public_admin_employment":       {"members": _LFS_COMMON + ["Public administration"], "unit": "thousands", "category": "Employment", "range": (800, 1900)},
            # C1 (reliability audit 2026-06-15): construction/manufacturing/mining
            # were previously fetched via the HARDCODED EMPLOYMENT_INDUSTRY group,
            # whose vectors were WRONG (2057622 = "Newfoundland & Labrador; Total
            # employed" = 243k shipped mislabelled as Manufacturing and range-
            # passed). Resolve by member NAME from the same cube instead, so a
            # member rename fails loudly (skips) rather than shipping garbage.
            "construction_employment":       {"members": _LFS_COMMON + ["Construction"], "unit": "thousands", "category": "Employment", "range": (1400, 1900)},
            "manufacturing_employment":      {"members": _LFS_COMMON + ["Manufacturing"], "unit": "thousands", "category": "Employment", "range": (1400, 2000)},
            "mining_og_employment":          {"members": _LFS_COMMON + ["Forestry, fishing, mining, quarrying, oil and gas"], "unit": "thousands", "category": "Employment", "range": (250, 500)},
        },
    },
    {
        # Average hourly wage, all industries — national level (provincial
        # equivalents already fetched via hardcoded vectors in Phase 1).
        "table": "14-10-0063",
        "frequency": "monthly",
        "series": {
            "nat_avg_hourly_wage": {
                "members": ["Canada", "Average hourly wage rate",
                            "Both full- and part-time employees",
                            "Total employees, all industries",
                            "Total - Gender", "Both sexes", "15 years and over"],
                "unit": "$/hr", "category": "Labour", "range": (25, 70),
            },
        },
    },
    {
        # Job vacancies, monthly SA (SEPH-based) — the table the frontend
        # cites (14-10-0372), not the quarterly JVWS sector cube (14-10-0326)
        # already covered above.
        "table": "14-10-0372",
        "frequency": "monthly",
        "series": {
            "job_vacancies_total": {
                "members": ["Canada", "Job vacancies"],
                "unit": "units", "category": "Employment", "range": (200_000, 1_500_000),
            },
        },
    },
    {
        # Manufacturers' sales, SA, Canada total.
        "table": "16-10-0047",
        "frequency": "monthly",
        "series": {
            "manufacturing_sales_national": {
                "members": ["Canada", "Sales of goods manufactured",
                            "Seasonally adjusted", "Total, manufacturing", "Manufacturing"],
                "unit": "$M", "category": "Manufacturing", "range": (40_000, 110_000),
            },
        },
    },
    {
        # Retail trade sales, SA, Canada total.
        "table": "20-10-0008",
        "frequency": "monthly",
        "series": {
            "retail_sales_national": {
                "members": ["Canada", "Retail trade", "Seasonally adjusted"],
                "unit": "$M", "category": "Retail", "range": (40_000, 120_000),
            },
        },
    },
    {
        # Wholesale trade sales, SA, Canada total.
        "table": "20-10-0074",
        "frequency": "monthly",
        "series": {
            "wholesale_sales_national": {
                "members": ["Canada", "Wholesale trade", "Seasonally adjusted"],
                "unit": "$M", "category": "Wholesale", "range": (40_000, 140_000),
            },
        },
    },
    {
        # Building permits value, Canada, SA — same active cube (34-10-0292)
        # whose provincial vectors were resolved + validated live 2026-06-09
        # in phases/data_collection.py.
        "table": "34-10-0292",
        "frequency": "monthly",
        "series": {
            "bldg_permits_res_national": {
                "members": ["Canada", "Total residential", "Types of work, total",
                            "Value of permits", "Seasonally adjusted"],
                "unit": "$M", "category": "Housing", "range": (2_000, 18_000),
            },
            "bldg_permits_nonres_national": {
                "members": ["Canada", "Total non-residential", "Types of work, total",
                            "Value of permits", "Seasonally adjusted"],
                "unit": "$M", "category": "Housing", "range": (1_000, 12_000),
            },
        },
    },
    {
        # Household sector accounts, quarterly (income at SAAR).
        "table": "36-10-0112",
        "frequency": "quarterly",
        "series": {
            "household_disposable_income_national": {
                "members": ["Canada", "Household disposable income",
                            "Seasonally adjusted at annual rates", "Seasonally adjusted"],
                "unit": "$M", "category": "Household", "range": (250_000, 3_000_000),
            },
            "household_savings_rate_national": {
                "members": ["Canada", "Household saving rate",
                            "Seasonally adjusted at annual rates", "Seasonally adjusted"],
                "unit": "%", "category": "Household", "range": (-10, 35),
            },
        },
    },
    # ── Quebec provincial series (2026-06-19) ────────────────────────────────
    # Fetched every run via WDS metadata resolution, replacing the dead
    # out-of-band ISQ Excel scrape that left QC_qc_* monthly series ~138 days
    # stale (refresh_provincial_oea_isq.py). Each series sets province='QC' so
    # the saver writes it under that geography and the dashboard exporter
    # (tools/export_dashboard.py: WHERE province='QC' → key "QC_"+indicator)
    # picks it up as QC_qc_bldg_permits_res etc. indicator_name therefore has
    # NO "QC_" prefix — it matches the existing rows (qc_intl_exports, ...) the
    # export query reads. Geography member is "Quebec" on each cube. If a QC
    # member name or coordinate cannot be matched at runtime, the resolver +
    # plausibility/freshness gates SKIP LOUDLY rather than write wrong data
    # (the intended safe failure — these coordinates are unverified against
    # live WDS, validated only at runtime).
    {
        # QC building permits value, SA — same active cube (34-10-0292) as the
        # national bldg_permits_*_national entries above, Quebec geography.
        "table": "34-10-0292",
        "frequency": "monthly",
        "series": {
            "qc_bldg_permits_res": {
                "members": ["Quebec", "Total residential", "Types of work, total",
                            "Value of permits", "Seasonally adjusted"],
                "unit": "$M", "category": "Housing", "range": (200, 4_000),
                "province": "QC",
            },
            "qc_bldg_permits_nonres": {
                "members": ["Quebec", "Total non-residential", "Types of work, total",
                            "Value of permits", "Seasonally adjusted"],
                "unit": "$M", "category": "Housing", "range": (100, 3_000),
                "province": "QC",
            },
        },
    },
    {
        # QC international merchandise trade, Balance of Payments basis, SA —
        # cube 12-10-0163 (same cube as MERCHANDISE_EXPORTS), Quebec geography,
        # exports vs imports member.
        "table": "12-10-0163",
        "frequency": "monthly",
        "series": {
            "qc_intl_exports": {
                "members": ["Quebec", "Domestic exports", "Export",
                            "Balance of payments", "Seasonally adjusted"],
                "unit": "$M", "category": "Trade", "range": (3_000, 20_000),
                "province": "QC",
            },
            "qc_intl_imports": {
                "members": ["Quebec", "Import",
                            "Balance of payments", "Seasonally adjusted"],
                "unit": "$M", "category": "Trade", "range": (3_000, 20_000),
                "province": "QC",
            },
        },
    },
    {
        # QC retail trade sales, SA — cube 20-10-0008 (same cube as
        # retail_sales_national), Quebec geography.
        "table": "20-10-0008",
        "frequency": "monthly",
        "series": {
            "qc_retail_sales": {
                "members": ["Quebec", "Retail trade", "Seasonally adjusted"],
                "unit": "$M", "category": "Retail", "range": (5_000, 30_000),
                "province": "QC",
            },
        },
    },
]

# ── All table groups ──────────────────────────────────────────────────────────
# Vectors refreshed 2026-03-31 via WDS getSeriesInfoFromCubePidCoord.
#
# Re-enabled (4 of 5 previously disabled):
#   INVESTMENT_BUILDING   — new vectors (1014954064 etc.), Q3 2023 latest
#   CAPITAL_EXPENDITURES  — new vectors (95923552 etc.), 2026 intentions data
#   HOUSING_STARTS        — new vectors (729949 etc.), Dec 2025 latest
#   HOUSING_PRICE_INDEX   — new vector (111955442), Feb 2026 latest
#
# Still disabled:
#   CONSTRUCTION_PRICE_INDEX — table 18-10-0135 appears discontinued, no active vectors found
#
# Previously working (unchanged):
#   JOB_VACANCIES         — vectors 45169837, 45169829
#
# Re-resolved 2026-06-09 (D-15):
#   MERCHANDISE_EXPORTS   — now Table 12-10-0163 vectors 1566911339/51/65/406
#                           (see the MERCHANDISE_EXPORTS block above; the old
#                           21837xxx vectors pointed at the dead 12-10-0129
#                           concentration cube frozen at 2003)

ALL_TABLE_GROUPS = [
    INVESTMENT_BUILDING_MONTHLY,   # 34-10-0293 (active monthly successor to 34-10-0175)
    INVESTMENT_BUILDING,
    # CONSTRUCTION_PRICE_INDEX,   # disabled — table 18-10-0135 discontinued
    CAPITAL_EXPENDITURES,
    # EMPLOYMENT_INDUSTRY removed 2026-06-15 (reliability audit C1): its
    # hardcoded vectors (2057614/2057606/2057622) were WRONG — manufacturing
    # resolved to "NL; Total employed" (243k) and shipped range-passed.
    # construction/manufacturing/mining employment are now name-resolved in
    # META_RESOLVED_GROUPS (same cube 14-10-0022) so drift fails loudly.
    JOB_VACANCIES,
    MERCHANDISE_EXPORTS,
    HOUSING_STARTS,
    HOUSING_PRICE_INDEX,
]

# National aggregates and the wider sector-employment set live in
# META_RESOLVED_GROUPS above — resolved at runtime from cube metadata and
# gated by range + freshness, fetched by run_extended_statcan after the
# vector groups.

# Frequency classification for mode-aware skipping
# (12-10-0129 removed 2026-06-12 — dead concentration cube, no group uses it;
# its successor 12-10-0163 is listed.)
_MONTHLY_TABLES = {
    "14-10-0022", "12-10-0163", "34-10-0143", "18-10-0205",
    "14-10-0287", "14-10-0222", "14-10-0063", "14-10-0372", "34-10-0066",
    "12-10-0011", "16-10-0047", "16-10-0048", "20-10-0008", "20-10-0074",
    "34-10-0292", "34-10-0293",
}
_QUARTERLY_TABLES = {"34-10-0175", "18-10-0135", "14-10-0326", "36-10-0112"}
_ANNUAL_TABLES = {"34-10-0035"}

# ── Freshness gate ────────────────────────────────────────────────────────────
# Maximum acceptable age (days) of the LATEST observation by frequency. An
# observation older than this means the vector/cube is stale, archived, or
# wrong (the agri_exports-frozen-at-2003 failure mode) — it is NOT saved, and
# the skip is logged loudly so the run output shows exactly what went dark.
_MAX_OBS_AGE_DAYS = {"monthly": 120, "quarterly": 300, "annual": 730}


def _is_fresh(ref_per: str, frequency: str) -> bool:
    """True when the observation date is within the freshness window."""
    try:
        obs_date = datetime.strptime(ref_per[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    max_age = _MAX_OBS_AGE_DAYS.get(frequency, 120)
    return (datetime.now() - obs_date).days <= max_age


# ─────────────────────────────────────────────────────────────────────────────
# WDS fetch — mirrors _fetch_wds() in statcan_permits.py
# ─────────────────────────────────────────────────────────────────────────────

_WDS_CHUNK = 40       # vectors per request — large batches time out on WDS
_WDS_TIMEOUT = 40     # was 25; WDS is slow under load
_WDS_BACKOFF = [5, 15]  # seconds between the 3 total attempts


def _fetch_wds(vector_ids: list, n: int = 14) -> dict:
    """Fetch last N observations from StatCan WDS for a list of vector IDs.

    Returns {vectorId: [{'refPer': 'YYYY-MM-DD', 'value': float}]} sorted by date.

    Resilience: vectors are chunked (large single payloads reliably time out on
    www150), each chunk gets 3 attempts with exponential backoff, and a chunk
    failure no longer loses the whole group — successful chunks are kept.
    """
    def _fetch_chunk(vids: list) -> dict:
        payload = [{"vectorId": vid, "latestN": n} for vid in vids]
        resp = requests.post(
            _STATCAN_WDS_URL, json=payload, timeout=_WDS_TIMEOUT,
            headers=_WDS_HEADERS,
        )
        resp.raise_for_status()
        result = {}
        for item in resp.json():
            if item.get('status') != 'SUCCESS':
                continue
            obj = item.get('object', {})
            vid = obj.get('vectorId')
            points = sorted(
                [{'refPer': p.get('refPer', ''), 'value': p.get('value')}
                 for p in obj.get('vectorDataPoint', [])
                 if p.get('value') is not None],
                key=lambda x: x['refPer']
            )
            result[vid] = points
        return result

    merged: dict = {}
    for start in range(0, len(vector_ids), _WDS_CHUNK):
        chunk = vector_ids[start:start + _WDS_CHUNK]
        for attempt in range(3):
            try:
                merged.update(_fetch_chunk(chunk))
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(_WDS_BACKOFF[attempt])
                else:
                    print(f"  [STATCAN-EXT] Chunk {start//_WDS_CHUNK + 1} "
                          f"({len(chunk)} vectors) failed after 3 attempts: {e}")
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Fetch + save for a single table group
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_table_group(conn, group: dict) -> tuple[int, int]:
    """Fetch all vectors for a table group and save to indicator_history.

    Returns (fetched_count, saved_count).
    """
    table_pid = group["table"]
    frequency = group["frequency"]
    vectors = group["vectors"]

    # Build vector ID → indicator name mapping
    vid_to_info = {}
    all_vids = []
    for indicator_name, (vid, unit, category) in vectors.items():
        vid_to_info[vid] = (indicator_name, unit, category)
        all_vids.append(vid)

    # Fetch — use more periods for monthly (14 = 1yr+), fewer for quarterly/annual
    n = 14 if frequency == "monthly" else 8 if frequency == "quarterly" else 4
    data = _fetch_wds(all_vids, n=n)

    fetched = 0
    saved = 0

    # Some tables (34-10-0175) return raw dollars, need conversion to $M
    raw_dollars = group.get("raw_dollars", False)

    for vid, points in data.items():
        info = vid_to_info.get(vid)
        if not info or not points:
            continue

        indicator_name, unit, category = info
        latest = points[-1]
        ref_per = latest.get('refPer', '')[:10]  # YYYY-MM-DD
        value = latest.get('value')

        if value is None:
            continue

        if not _is_fresh(ref_per, frequency):
            print(f"  [STATCAN-EXT][STALE] {indicator_name} (v{vid}, {table_pid}): "
                  f"latest obs {ref_per} exceeds the {frequency} freshness window "
                  f"— NOT saved. Vector may be terminated or cube archived.")
            continue

        # Convert raw dollars to millions if needed
        if raw_dollars and unit == "$M":
            value = round(value / 1_000_000, 1)

        fetched += 1

        # Compute period-over-period change if enough data.
        # D11: semantics come from the shared UNIT-aware helper — %-unit
        # series (e.g. household savings rate) get pp differences, levels
        # get relative % change. Historical rows are not rewritten.
        prev_value = None
        change = None
        if len(points) >= 2:
            prev_value = points[-2].get('value')
            if raw_dollars and unit == "$M" and prev_value is not None:
                prev_value = round(prev_value / 1_000_000, 1)
            change = format_indicator_change(value, prev_value, unit=unit,
                                             indicator_name=indicator_name)

        try:
            save_indicator(conn, {
                'indicator': indicator_name,
                'province': 'National',
                'date': ref_per,
                'value': str(value),
                'previous_value': str(prev_value) if prev_value is not None else None,
                'change': change,
                'unit': unit,
                'source': f'StatCan {table_pid}',
                'frequency': frequency,
                'category': category,
                'backfilled': False,
                'source_meta': {
                    'authority': 'Statistics Canada',
                    'reference_period': ref_per,
                    'source_url': f'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_pid.replace("-", "")}',
                    'table_id': table_pid,
                    'vector_id': vid,
                },
            })
            saved += 1
        except Exception as e:
            # D13c: loud failure — this module's doctrine is that wrong/missed
            # writes must never be quiet.
            logger.warning(f"[STATCAN-EXT] Failed to save {indicator_name}: {e}")

    return fetched, saved


# ─────────────────────────────────────────────────────────────────────────────
# Metadata-resolved fetch — coordinate resolution by dimension-member name
# ─────────────────────────────────────────────────────────────────────────────

_WDS_CUBE_META_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata"
_WDS_COORD_DATA_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods"


def _get_cube_metadata(pid: int) -> dict | None:
    """Fetch cube metadata (dimensions + members) for a product ID."""
    for attempt in range(3):
        try:
            resp = requests.post(
                _WDS_CUBE_META_URL, json=[{"productId": pid}],
                timeout=_WDS_TIMEOUT, headers=_WDS_HEADERS,
            )
            resp.raise_for_status()
            body = resp.json()
            if body and body[0].get("status") == "SUCCESS":
                return body[0].get("object", {})
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(_WDS_BACKOFF[attempt])
            else:
                logger.warning(f"[STATCAN-EXT] getCubeMetadata({pid}) failed: {e}")
    return None


def _resolve_coordinate(cube_meta: dict, patterns: list) -> tuple[str | None, list]:
    """Match one member per cube dimension against the name patterns.

    Matching is case-insensitive: an exact name match anywhere in the pattern
    list wins; otherwise the first pattern that is a prefix of a member name.
    Each pattern is consumed at most once. Unused patterns are fine (they let
    one spec cover naming variants across cubes, e.g. 'Both sexes' vs
    'Total - Gender'); an UNMATCHED DIMENSION is not — the series aborts.

    Returns (coordinate_string, unmatched_dimension_names). The coordinate is
    None unless every dimension matched.
    """
    dims = cube_meta.get("dimension", []) or []
    pats = [(p, p.strip().lower()) for p in patterns]
    used = set()
    coord = []
    unmatched = []
    for dim in dims:
        members = dim.get("member", []) or []
        chosen = None
        # Pass 1: exact name match
        for orig, pl in pats:
            if orig in used:
                continue
            for m in members:
                if (m.get("memberNameEn") or "").strip().lower() == pl:
                    chosen = m
                    used.add(orig)
                    break
            if chosen:
                break
        # Pass 2: prefix match
        if chosen is None:
            for orig, pl in pats:
                if orig in used:
                    continue
                for m in members:
                    if (m.get("memberNameEn") or "").strip().lower().startswith(pl):
                        chosen = m
                        used.add(orig)
                        break
                if chosen:
                    break
        if chosen is None:
            unmatched.append(dim.get("dimensionNameEn", "?"))
            coord.append(None)
        else:
            coord.append(int(chosen["memberId"]))
    if unmatched or not coord:
        return None, unmatched
    # WDS coordinates are always 10 dotted positions, zero-padded
    parts = [str(c) for c in coord] + ["0"] * (10 - len(coord))
    return ".".join(parts[:10]), []


def _normalize_obs_value(raw: float, scalar_code, unit: str) -> float:
    """Normalize a WDS observation to the unit the spec declares.

    scalarFactorCode is a power of ten (0=units, 3=thousands, 6=millions).
    $-series normalize to $M; 'thousands' (persons) to thousands; 'units' to
    raw count. Rates/index/$-per-hour values pass through unscaled.
    """
    try:
        factor = 10 ** int(scalar_code or 0)
    except (ValueError, TypeError):
        factor = 1
    if unit == "$M":
        return raw * factor / 1_000_000
    if unit == "thousands":
        return raw * factor / 1_000
    if unit == "units":
        return raw * factor
    return raw


def _fetch_meta_group(conn, group: dict) -> tuple[int, int]:
    """Fetch a metadata-resolved table group. Returns (fetched, saved).

    Each series resolves its coordinate from cube metadata by member name,
    then must pass the plausibility range and freshness gate before saving.
    All failure modes are loud skips — wrong data is never written quietly.
    """
    table_pid = group["table"]
    frequency = group["frequency"]
    pid = int(table_pid.replace("-", ""))

    cube_meta = _get_cube_metadata(pid)
    if not cube_meta:
        print(f"  [STATCAN-EXT][META] {table_pid}: cube metadata unavailable — skipped")
        return 0, 0

    # Resolve all coordinates first, then batch the data request
    resolved = {}  # coordinate -> indicator_name
    specs = {}
    for indicator_name, spec in group["series"].items():
        coord, unmatched = _resolve_coordinate(cube_meta, spec["members"])
        if coord is None:
            print(f"  [STATCAN-EXT][META] {table_pid} {indicator_name}: unmatched "
                  f"dimension(s) {unmatched} — series skipped (amend member patterns)")
            continue
        resolved[coord] = indicator_name
        specs[indicator_name] = spec

    if not resolved:
        return 0, 0

    n = 14 if frequency == "monthly" else 8 if frequency == "quarterly" else 4
    payload = [{"productId": pid, "coordinate": coord, "latestN": n}
               for coord in resolved]
    data = None
    for attempt in range(3):
        try:
            resp = requests.post(
                _WDS_COORD_DATA_URL, json=payload,
                timeout=_WDS_TIMEOUT, headers=_WDS_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(_WDS_BACKOFF[attempt])
            else:
                print(f"  [STATCAN-EXT][META] {table_pid}: data fetch failed: {e}")
    if not data:
        return 0, 0

    fetched = 0
    saved = 0
    for item in data:
        if item.get("status") != "SUCCESS":
            continue
        obj = item.get("object", {})
        coord = obj.get("coordinate", "")
        indicator_name = resolved.get(coord)
        if not indicator_name:
            continue
        spec = specs[indicator_name]
        unit = spec["unit"]
        points = sorted(
            [p for p in obj.get("vectorDataPoint", []) if p.get("value") is not None],
            key=lambda x: x.get("refPer", ""),
        )
        if not points:
            print(f"  [STATCAN-EXT][META] {table_pid} {indicator_name}: no observations")
            continue
        latest = points[-1]
        ref_per = (latest.get("refPer") or "")[:10]
        value = _normalize_obs_value(float(latest["value"]),
                                     latest.get("scalarFactorCode"), unit)
        fetched += 1

        lo, hi = spec["range"]
        if not (lo <= value <= hi):
            print(f"  [STATCAN-EXT][META][RANGE] {table_pid} {indicator_name}: "
                  f"{value} outside plausibility [{lo}, {hi}] — NOT saved "
                  f"(member match may be wrong)")
            continue
        if not _is_fresh(ref_per, frequency):
            print(f"  [STATCAN-EXT][META][STALE] {table_pid} {indicator_name}: "
                  f"latest obs {ref_per} exceeds the {frequency} freshness window — NOT saved")
            continue

        prev_value = None
        change = None
        if len(points) >= 2:
            prev_value = _normalize_obs_value(float(points[-2]["value"]),
                                              points[-2].get("scalarFactorCode"), unit)
            # D11: UNIT-aware change semantics (pp for %-series, relative %
            # for levels) via the shared helper — fixes savings rate
            # 3.4 → 3.5 being stored as "+2.9%" instead of "+0.1pp".
            change = format_indicator_change(value, prev_value, unit=unit,
                                             indicator_name=indicator_name)

        value = round(value, 4)
        # Province defaults to 'National'; provincial series (e.g. the QC_*
        # timeseries the dashboard exporter reads via province='QC') set
        # "province" in their spec so the same metadata-resolved path with its
        # range + freshness gates can write them under the correct geography.
        province = spec.get("province", "National")
        try:
            save_indicator(conn, {
                'indicator': indicator_name,
                'province': province,
                'date': ref_per,
                'value': str(value),
                'previous_value': str(round(prev_value, 4)) if prev_value is not None else None,
                'change': change,
                'unit': unit,
                'source': f'StatCan {table_pid}',
                'frequency': frequency,
                'category': spec["category"],
                'backfilled': False,
                'source_meta': {
                    'authority': 'Statistics Canada',
                    'reference_period': ref_per,
                    'source_url': f'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_pid.replace("-", "")}01',
                    'table_id': table_pid,
                    'coordinate': coord,
                    'vector_id': obj.get('vectorId'),
                },
            })
            saved += 1
        except Exception as e:
            # D13c: loud failure over silent debug logging.
            logger.warning(f"[STATCAN-EXT][META] Failed to save {indicator_name}: {e}")

    return fetched, saved


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_extended_statcan(conn, mode: str = "weekly") -> dict:
    """Fetch all extended StatCan tables and save to indicator_history.

    Args:
        conn: SQLite connection (from db.get_db()).
        mode: Pipeline mode. If "indicators-only", skip annual and quarterly
              tables — only fetch monthly ones. Weekly/deep-sweep fetches all.

    Returns:
        dict with fetch results for pipeline context.
    """
    print("\n  [STATCAN-EXT] Fetching extended StatCan indicators...")

    total_fetched = 0
    total_saved = 0
    tables_succeeded = 0
    tables_failed = 0

    for group in ALL_TABLE_GROUPS:
        table_pid = group["table"]
        frequency = group["frequency"]

        # Mode-aware skipping: daily/indicators-only runs skip slow-updating tables
        if mode == "indicators-only":
            if table_pid in _ANNUAL_TABLES or table_pid in _QUARTERLY_TABLES:
                continue

        try:
            fetched, saved = _fetch_table_group(conn, group)
            if fetched > 0:
                tables_succeeded += 1
                total_fetched += fetched
                total_saved += saved
                print(f"    {table_pid}: {fetched} indicators fetched, {saved} saved")
            else:
                tables_failed += 1
                print(f"    {table_pid}: no data returned")
        except Exception as e:
            tables_failed += 1
            print(f"    {table_pid}: failed — {e}")

        # Rate-limit: 1-second delay between table fetches
        time.sleep(1)

    # Metadata-resolved groups (coordinate resolution by member name + range
    # and freshness gates — see META_RESOLVED_GROUPS)
    for group in META_RESOLVED_GROUPS:
        table_pid = group["table"]

        if mode == "indicators-only":
            if table_pid in _ANNUAL_TABLES or table_pid in _QUARTERLY_TABLES:
                continue

        try:
            fetched, saved = _fetch_meta_group(conn, group)
            if fetched > 0:
                tables_succeeded += 1
                total_fetched += fetched
                total_saved += saved
                print(f"    {table_pid} (meta): {fetched} indicators fetched, {saved} saved")
            else:
                tables_failed += 1
                print(f"    {table_pid} (meta): no data returned")
        except Exception as e:
            tables_failed += 1
            print(f"    {table_pid} (meta): failed — {e}")

        time.sleep(1)

    print(f"  [STATCAN-EXT] Done: {tables_succeeded} tables OK, "
          f"{tables_failed} failed, {total_saved}/{total_fetched} indicators saved")

    return {
        "statcan_extended_fetched": total_fetched,
        "statcan_extended_saved": total_saved,
        "statcan_extended_tables_ok": tables_succeeded,
        "statcan_extended_tables_failed": tables_failed,
    }
