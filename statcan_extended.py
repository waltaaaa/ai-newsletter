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
  12-10-0129  Merchandise exports by commodity (monthly)
  34-10-0143  Housing starts by type and province (monthly)
  18-10-0205  New housing price index (monthly)

Zero cost — StatCan WDS API is free, no registration required.
"""

import logging
import time
import requests
from datetime import datetime

from db import save_indicator

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

# Table 34-10-0175-01: Investment in building construction (quarterly)
# Geography=Canada, seasonally adjusted, current dollars
# Vectors refreshed 2026-03-31 via WDS coordinate lookup (old vectors returned 2012 data)
# Note: values are in raw dollars (not $M) — converted to $M in _fetch_table_group
INVESTMENT_BUILDING = {
    "table": "34-10-0175",
    "frequency": "quarterly",
    "raw_dollars": True,  # values are in raw CAD, divide by 1e6 for $M
    "vectors": {
        "residential_building_investment":      (1014954064, "$M", "Investment"),
        "non_residential_building_investment":   (1014954170, "$M", "Investment"),
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

# Table 14-10-0022-01: Employment by industry, monthly, SA
# Geography=Canada, both sexes, 15 years and over
EMPLOYMENT_INDUSTRY = {
    "table": "14-10-0022",
    "frequency": "monthly",
    "vectors": {
        "construction_employment":    (2057614, "thousands", "Employment"),
        "mining_og_employment":       (2057606, "thousands", "Employment"),
        "manufacturing_employment":   (2057622, "thousands", "Employment"),
    },
}

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

# Table 12-10-0129-01: Merchandise exports by commodity, monthly
# Domestic exports, current dollars, SA
MERCHANDISE_EXPORTS = {
    "table": "12-10-0129",
    "frequency": "monthly",
    "vectors": {
        "energy_exports":    (21837355, "$M", "Trade"),
        "mineral_exports":   (21837395, "$M", "Trade"),
        "forestry_exports":  (21837439, "$M", "Trade"),
        "agri_exports":      (21837343, "$M", "Trade"),
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

# ── National LFS Aggregates (added 2026-04-19) ───────────────────────────────
#
# Added to close gaps identified in the 2026-04-18 schema audit. The pipeline
# currently tracks employment rate, participation rate, and wage growth per
# province but not at the national level, which leaves 7 national series blank
# on the frontend. Building permits, trade balance, manufacturing sales, and
# retail sales national totals are also missing from timeseries.json.
#
# Vector IDs below MUST be verified via StatCan WDS coordinate lookup before
# enabling. See statcan_permits.py for the coordinate lookup pattern
# (getSeriesInfoFromCubePidCoord). Until verified, this group is NOT included
# in ALL_TABLE_GROUPS — activation requires setting _NATIONAL_LFS_VERIFIED=True
# after confirming each vector returns data with a recent refPer.

_NATIONAL_LFS_VERIFIED = False  # flip to True after vector coordinate lookup

# Table 14-10-0287-01: Labour force characteristics, monthly, seasonally adjusted
# Geography=Canada, both sexes, 15 years and over
NATIONAL_LFS_AGGREGATES = {
    "table": "14-10-0287",
    "frequency": "monthly",
    "vectors": {
        # TODO(vector-verify): run WDS coordinate lookup before enabling
        "national_employment_rate":     (0, "%", "Labour"),          # coord [1,2,5,1,1]
        "national_participation_rate":  (0, "%", "Labour"),          # coord [1,2,4,1,1]
    },
}

# Table 14-10-0064-01: Employee wages by industry, annual
# (Or table 14-10-0222 for monthly average hourly wages.) National totals.
NATIONAL_WAGE_GROWTH = {
    "table": "14-10-0222",
    "frequency": "monthly",
    "vectors": {
        "national_wage_growth_yoy":    (0, "%", "Labour"),  # TODO(vector-verify)
    },
}

# Table 34-10-0066-01: Building permits, value, monthly, SA — national total
NATIONAL_BUILDING_PERMITS = {
    "table": "34-10-0066",
    "frequency": "monthly",
    "vectors": {
        "national_building_permits_total":    (0, "$M", "Housing"),  # TODO(vector-verify)
    },
}

# Table 12-10-0011-01: Merchandise trade, exports and imports, monthly, SA
# National total trade balance = exports - imports (can compute from two vectors).
NATIONAL_TRADE_BALANCE = {
    "table": "12-10-0011",
    "frequency": "monthly",
    "vectors": {
        "national_total_exports":    (0, "$M", "Trade"),  # TODO(vector-verify)
        "national_total_imports":    (0, "$M", "Trade"),  # TODO(vector-verify)
        # Downstream: trade_balance = national_total_exports - national_total_imports
    },
}

# Table 16-10-0048-01: Manufacturing sales, monthly, SA — Canada total
NATIONAL_MANUFACTURING_SALES = {
    "table": "16-10-0048",
    "frequency": "monthly",
    "vectors": {
        "national_manufacturing_sales":    (0, "$M", "Manufacturing"),  # TODO(vector-verify)
    },
}

# Table 20-10-0008-01: Retail trade, sales, monthly, SA — Canada total
NATIONAL_RETAIL_SALES = {
    "table": "20-10-0008",
    "frequency": "monthly",
    "vectors": {
        "national_retail_sales":    (0, "$M", "Retail"),  # TODO(vector-verify)
    },
}

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
#   EMPLOYMENT_INDUSTRY   — vectors 2057614, 2057606, 2057622
#   JOB_VACANCIES         — vectors 45169837, 45169829
#   MERCHANDISE_EXPORTS   — vectors 21837355, 21837395, 21837439, 21837343

ALL_TABLE_GROUPS = [
    INVESTMENT_BUILDING,
    # CONSTRUCTION_PRICE_INDEX,   # disabled — table 18-10-0135 discontinued
    CAPITAL_EXPENDITURES,
    EMPLOYMENT_INDUSTRY,
    JOB_VACANCIES,
    MERCHANDISE_EXPORTS,
    HOUSING_STARTS,
    HOUSING_PRICE_INDEX,
]

# National aggregates — appended only after vector IDs are verified. See the
# NATIONAL_* groups above for the 7 series that close the 2026-04-18 audit gap.
if _NATIONAL_LFS_VERIFIED:
    ALL_TABLE_GROUPS.extend([
        NATIONAL_LFS_AGGREGATES,
        NATIONAL_WAGE_GROWTH,
        NATIONAL_BUILDING_PERMITS,
        NATIONAL_TRADE_BALANCE,
        NATIONAL_MANUFACTURING_SALES,
        NATIONAL_RETAIL_SALES,
    ])

# Frequency classification for mode-aware skipping
_MONTHLY_TABLES = {
    "14-10-0022", "12-10-0129", "34-10-0143", "18-10-0205",
    "14-10-0287", "14-10-0222", "34-10-0066",
    "12-10-0011", "16-10-0048", "20-10-0008",
}
_QUARTERLY_TABLES = {"34-10-0175", "18-10-0135", "14-10-0326"}
_ANNUAL_TABLES = {"34-10-0035"}


# ─────────────────────────────────────────────────────────────────────────────
# WDS fetch — mirrors _fetch_wds() in statcan_permits.py
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_wds(vector_ids: list, n: int = 14) -> dict:
    """Fetch last N observations from StatCan WDS for a list of vector IDs.

    Returns {vectorId: [{'refPer': 'YYYY-MM-DD', 'value': float}]} sorted by date.
    Retries once after 5s on failure (same pattern as data_collection.py).
    """
    payload = [{"vectorId": vid, "latestN": n} for vid in vector_ids]

    def _do_fetch():
        resp = requests.post(
            _STATCAN_WDS_URL, json=payload, timeout=25,
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

    try:
        r = _do_fetch()
        if r:
            return r
    except Exception as e:
        print(f"  [STATCAN-EXT] First attempt failed: {e}")

    time.sleep(5)
    try:
        return _do_fetch()
    except Exception as e:
        print(f"  [STATCAN-EXT] Retry failed: {e}")
        return {}


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

        # Convert raw dollars to millions if needed
        if raw_dollars and unit == "$M":
            value = round(value / 1_000_000, 1)

        fetched += 1

        # Compute period-over-period change if enough data
        prev_value = None
        change = None
        if len(points) >= 2:
            prev_value = points[-2].get('value')
            if raw_dollars and unit == "$M" and prev_value is not None:
                prev_value = round(prev_value / 1_000_000, 1)
            if prev_value and prev_value != 0:
                change = f"{((value - prev_value) / abs(prev_value)) * 100:+.1f}%"

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
            logger.debug(f"[STATCAN-EXT] Failed to save {indicator_name}: {e}")

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

    print(f"  [STATCAN-EXT] Done: {tables_succeeded} tables OK, "
          f"{tables_failed} failed, {total_saved}/{total_fetched} indicators saved")

    return {
        "statcan_extended_fetched": total_fetched,
        "statcan_extended_saved": total_saved,
        "statcan_extended_tables_ok": tables_succeeded,
        "statcan_extended_tables_failed": tables_failed,
    }
