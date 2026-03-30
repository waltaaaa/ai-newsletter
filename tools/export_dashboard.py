"""
export_dashboard.py — Static JSON export for CAN-MACRO Dashboard.

Reads all dashboard data from SQLite via db.py and writes static JSON files
to docs/data/ (default). These files represent the complete dataset the frontend
needs to render without any database connection.

Usage:
    python export_dashboard.py                    # export to docs/data/
    python export_dashboard.py --out /tmp/data    # export to custom directory

This is the bridge between the SQLite backend (Phase 13) and the static
frontend (Phase 15).
"""

import argparse
import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

# Ensure project root is importable (for standalone runs)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

logger = logging.getLogger(__name__)

# ── Province slug list (matches PROVINCES in pipeline_config.py) ─────────────

PROVINCE_SLUGS = [
    "ontario",
    "quebec",
    "alberta",
    "british_columbia",
    "saskatchewan",
    "manitoba",
    "nova_scotia",
    "new_brunswick",
    "newfoundland_and_labrador",
    "prince_edward_island",
    "yukon",
    "northwest_territories",
    "nunavut",
]

# Known timeseries series names (from update_dashboard.py append_to_timeseries)
_TIMESERIES_NAMES = [
    "boc_rate",
    "tsx_composite",
    "comm_wti",
    "comm_brent",
    "comm_natgas",
    "comm_gold",
    "comm_silver",
    "comm_platinum",
    "comm_palladium",
    "comm_copper",
    "comm_aluminum",
    "comm_wheat",
    "comm_corn",
    "comm_rice",
    "comm_soybeans",
    "comm_coffee",
    "comm_cocoa",
    "comm_sugar",
    "comm_cotton",
    "comm_soyoil",
    "comm_soymeal",
    "comm_coal",
    "comm_propane",
    "idx_sp500",
    "idx_djia",
    "idx_nasdaq",
    "idx_ftse",
    "idx_dax",
    "idx_nikkei",
    "idx_hangseng",
    "idx_shanghai",
]


# ═══════════════════════════════════════════════════════════════════════════════
# VALUE PARSING
# ═══════════════════════════════════════════════════════════════════════════════


def _parse_value(value_str) -> float | None:
    """Parse project value strings into float (in dollars).

    Handles forms like:
      "$1.2B", "$600M", "$2.5 billion", "$350 million", "$1,200K"

    Returns:
        float in dollars, or None if not disclosed / empty / unparseable.
    """
    if not value_str:
        return None
    s = str(value_str).strip()
    if s.lower() in ("not disclosed", "unknown", "tbd", "n/a", ""):
        return None

    # Handle written-out forms: "2.5 billion", "350 million"
    written = re.match(
        r"\$?([\d,]+\.?\d*)\s*(billion|million|thousand)", s, re.IGNORECASE
    )
    if written:
        num = float(written.group(1).replace(",", ""))
        unit = written.group(2).lower()
        if unit == "billion":
            return num * 1e9
        elif unit == "million":
            return num * 1e6
        elif unit == "thousand":
            return num * 1e3

    # Handle abbreviated forms: "$1.2B", "$600M", "$1,200K"
    abbrev = re.match(r"\$?([\d,]+\.?\d*)\s*(B|M|K)?", s, re.IGNORECASE)
    if abbrev:
        num_str = abbrev.group(1).replace(",", "")
        try:
            num = float(num_str)
        except ValueError:
            return None
        unit = (abbrev.group(2) or "").upper()
        if unit == "B":
            return num * 1e9
        elif unit == "M":
            return num * 1e6
        elif unit == "K":
            return num * 1e3
        # No unit — treat as raw dollars only if it looks significant (≥1000)
        if num >= 1000:
            return num

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SHAPE FOR EXPORT
# ═══════════════════════════════════════════════════════════════════════════════


def _safe_json_loads(value, default):
    """Parse a JSON string field safely, returning default on failure."""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value  # already parsed
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _project_for_export(proj_dict: dict) -> dict:
    """Convert a db.py project dict for JSON export.

    - Parses JSON string fields (evidence, statusHistory, etc.) into real lists.
    - Adds value_confirmed: bool field.
    - Returns only the fields the frontend needs.
    """
    parsed_value = _parse_value(proj_dict.get("value"))
    value_confirmed = parsed_value is not None

    return {
        "name": proj_dict.get("name", ""),
        "province": proj_dict.get("province", ""),
        "cma": proj_dict.get("cma", ""),
        "sector": proj_dict.get("sector", ""),
        "naics_code": proj_dict.get("naics_code", ""),
        "naics_name": proj_dict.get("naics_name", ""),
        "value": proj_dict.get("value", "Not disclosed"),
        "value_confirmed": value_confirmed,
        "status": proj_dict.get("status", ""),
        "confidence": proj_dict.get("confidence", 0.0),
        "project_type": proj_dict.get("project_type", ""),
        "is_brownfield": bool(proj_dict.get("is_brownfield", False)),
        "proponent": proj_dict.get("proponent", ""),
        "description": proj_dict.get("description", ""),
        "completionDate": proj_dict.get("completionDate", ""),
        "firstTracked": proj_dict.get("firstTracked", ""),
        "lastUpdated": proj_dict.get("lastUpdated", ""),
        "lastSeen": proj_dict.get("lastSeen", ""),
        "evidence": _safe_json_loads(proj_dict.get("evidence"), []),
        "statusHistory": _safe_json_loads(proj_dict.get("statusHistory"), []),
        "discovery_source": proj_dict.get("discovery_source", ""),
        "evidence_count": proj_dict.get("evidence_count", 0),
        "has_government_source": bool(proj_dict.get("has_government_source", False)),
        "tags": _safe_json_loads(proj_dict.get("tags"), []),
        "sources": _safe_json_loads(proj_dict.get("sources"), []),
        "discovery_sources": _safe_json_loads(proj_dict.get("discovery_sources"), []),
        "announcement_date": proj_dict.get("announcement_date", ""),
        "start_date": proj_dict.get("start_date", ""),
        "parsed_value": proj_dict.get("parsed_value"),
        "provinces_additional": proj_dict.get("provinces_additional", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def export_province_projects(conn, province_name: str, threshold_val: int, output_dir: str) -> str:
    """Export projects for a single province, filtered by GDP threshold.

    Inclusion rules:
    - value is None (Not disclosed / unparseable) → include with value_confirmed=false
    - value >= threshold_val → include with value_confirmed=true
    - value < threshold_val → EXCLUDE

    Returns the path of the written file.
    """
    from db import get_projects

    raw_projects = get_projects(conn, province=province_name)
    included = []

    for raw in raw_projects:
        # sqlite3.Row → plain dict
        if hasattr(raw, "keys"):
            proj = dict(raw)
        else:
            proj = raw

        parsed_value = _parse_value(proj.get("value"))

        # Exclusion rule: known value below threshold
        if parsed_value is not None and parsed_value < threshold_val:
            continue

        shaped = _project_for_export(proj)
        included.append(shaped)

    slug = province_name.lower().replace(" ", "_")
    out_path = os.path.join(output_dir, f"projects_{slug}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        # Compact JSON for province files (can be large)
        json.dump(included, f, ensure_ascii=False, separators=(",", ":"))

    return out_path


def _build_market_data_from_indicators(conn) -> dict:
    """Build financialMarkets + commodities + yieldCurve from indicator_history."""
    rows = conn.execute("""
        SELECT indicator_name, value, unit
        FROM indicator_history
        WHERE indicator_name IN (
            'tsx_composite','sp500','djia','nasdaq','ftse100','dax','nikkei225',
            'cadusd','eurusd','usdcny','usdjpy',
            'wti','brent','natural_gas','coal','propane',
            'gold','silver','platinum','palladium',
            'copper','aluminum',
            'wheat','corn','rice','soybeans','coffee','cocoa','sugar','cotton',
            'soybean_oil','soybean_meal','lumber',
            'goc_2y_yield','goc_5y_yield','goc_10y_yield'
        )
        GROUP BY indicator_name
        HAVING fetched_at = MAX(fetched_at)
    """).fetchall()

    vals = {}
    for r in rows:
        vals[r[0]] = {'value': r[1], 'unit': r[2] or ''}

    def _fmt(name, decimals=2):
        v = vals.get(name, {}).get('value')
        if v is None:
            return None
        try:
            f = float(str(v).replace(',', ''))
            return f"{f:,.{decimals}f}" if f < 1000 else f"{f:,.0f}"
        except (ValueError, TypeError):
            return str(v)

    # Indices
    IDX = [
        ('tsx_composite', 'S&P/TSX', 'Canada'),
        ('sp500', 'S&P 500', 'USA'),
        ('djia', 'Dow Jones', 'USA'),
        ('nasdaq', 'NASDAQ', 'USA'),
        ('ftse100', 'FTSE 100', 'UK'),
        ('dax', 'DAX', 'Germany'),
        ('nikkei225', 'Nikkei 225', 'Japan'),
    ]
    indices = []
    for key, label, region in IDX:
        v = _fmt(key, 0)
        if v:
            indices.append({'name': label, 'value': v, 'region': region, 'change': '', 'day': '', 'yy': ''})

    # FX
    FX = [('cadusd', 'CAD/USD'), ('eurusd', 'EUR/USD'), ('usdcny', 'USD/CNY'), ('usdjpy', 'USD/JPY')]
    fx = []
    for key, label in FX:
        v = _fmt(key, 4)
        if v:
            fx.append({'name': label, 'value': v, 'day': '', 'yy': ''})

    # Commodities
    COMMS = {
        'Energy': [('wti', 'Crude Oil (WTI)', 'bbl'), ('brent', 'Crude Oil (Brent)', 'bbl'),
                   ('natural_gas', 'Natural Gas', 'MMBtu'), ('coal', 'Coal (Newcastle)', 't'),
                   ('propane', 'Propane', 'gal')],
        'Precious Metals': [('gold', 'Gold', 'troy oz'), ('silver', 'Silver', 'troy oz'),
                            ('platinum', 'Platinum', 'troy oz'), ('palladium', 'Palladium', 'troy oz')],
        'Base Metals': [('copper', 'Copper', 'lb'), ('aluminum', 'Aluminum', 'lb')],
        'Agriculture - Grains': [('wheat', 'Wheat', 'bu'), ('corn', 'Corn', 'bu'),
                                  ('rice', 'Rice', 'cwt'), ('soybeans', 'Soybeans', 'bu')],
        'Agriculture - Softs': [('coffee', 'Coffee', 'lb'), ('cocoa', 'Cocoa', 't'),
                                 ('sugar', 'Sugar #11', 'lb'), ('cotton', 'Cotton', 'lb')],
        'Agriculture - Oils & Meals': [('soybean_oil', 'Soybean Oil', 'lb'), ('soybean_meal', 'Soybean Meal', 'ton')],
        'Forest Products': [('lumber', 'Lumber', 'MBF')],
    }
    commodities = []
    for cat, items in COMMS.items():
        cat_items = []
        for key, label, unit in items:
            v = vals.get(key, {}).get('value')
            if v is not None:
                cat_items.append({'name': label, 'val': str(v), 'unit': unit, 'yy': '', 'day': ''})
        if cat_items:
            commodities.append({'category': cat, 'items': cat_items})

    # Yield curve
    yieldCurve = []
    for term in ['2Y', '5Y', '10Y']:
        v = vals.get(f'goc_{term.lower()}_yield', {}).get('value')
        if v is not None:
            yieldCurve.append({'term': term, 'yield': str(v)})

    return {
        'financialMarkets': {'indices': indices, 'fx': fx},
        'commodities': commodities,
        'yieldCurve': yieldCurve,
    }


def export_briefings(conn, output_dir: str) -> tuple[str, str]:
    """Export briefing_latest.json and briefing_archive.json."""
    from db import get_briefing_archive, get_latest_briefing, get_dashboard_state

    # Latest briefing — prefer full newsletter payload from dashboard_state
    # (includes provinces, industries, executive_summary from Claude analysis)
    # Falls back to weekly_briefings table (briefing text only)
    latest = get_dashboard_state(conn, 'newsletter_latest')
    if not latest or not isinstance(latest, dict):
        latest = get_latest_briefing(conn)
    if latest is None:
        latest = {}
    # Merge in briefing sections from weekly_briefings if not in newsletter payload
    if not latest.get('sections'):
        briefing = get_latest_briefing(conn)
        if briefing:
            for key in ('id', 'week_of', 'headline', 'sections', 'word_count',
                        'generated_at', 'pdf_url', 'docx_url'):
                if briefing.get(key) and not latest.get(key):
                    latest[key] = briefing[key]

    # Merge market data from indicator_history if not already in briefing
    if not latest.get('financialMarkets') or not latest.get('commodities'):
        market_data = _build_market_data_from_indicators(conn)
        if not latest.get('financialMarkets'):
            latest['financialMarkets'] = market_data['financialMarkets']
        if not latest.get('commodities'):
            latest['commodities'] = market_data['commodities']
        if not latest.get('yieldCurve'):
            latest['yieldCurve'] = market_data['yieldCurve']

    # Merge infographic directives if available
    if not latest.get('infographic_directives'):
        infographic_directives = get_dashboard_state(conn, 'infographic_directives')
        if infographic_directives and isinstance(infographic_directives, list):
            latest['infographic_directives'] = infographic_directives

    latest_path = os.path.join(output_dir, "briefing_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    # Archive — metadata only (no full sections to keep file small)
    archive_raw = get_briefing_archive(conn, limit=52)
    archive = []
    for entry in archive_raw:
        if hasattr(entry, "keys"):
            entry = dict(entry)
        archive.append(
            {
                "week_of": entry.get("week_of", ""),
                "headline": entry.get("headline", ""),
                "word_count": entry.get("word_count", 0),
                "generated_at": entry.get("generated_at", ""),
            }
        )

    archive_path = os.path.join(output_dir, "briefing_archive.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    return latest_path, archive_path


def export_indicators(conn, output_dir: str) -> str:
    """Export indicators.json with full history for the indicator explorer chart."""
    from db import get_dashboard_state, get_latest_indicators

    indicators = get_latest_indicators(conn)
    # Convert sqlite3.Row objects to plain dicts
    indicators_list = []
    for ind in indicators:
        if hasattr(ind, "keys"):
            row = dict(ind)
            # Parse metadata JSON string if present
            if "metadata" in row and isinstance(row["metadata"], str):
                row["metadata"] = _safe_json_loads(row["metadata"], {})
            indicators_list.append(row)
        else:
            indicators_list.append(ind)

    # Export full indicator history (last 5 years) for the explorer chart
    # Deduplicate by keeping one value per indicator+province+period
    import sqlite3 as _sql
    old_rf = conn.row_factory
    conn.row_factory = _sql.Row
    history_rows = conn.execute("""
        SELECT indicator_name, province, period, value, unit, source
        FROM indicator_history
        WHERE period >= date('now', '-5 years')
        GROUP BY indicator_name, province, period
        ORDER BY indicator_name, province, period
    """).fetchall()
    conn.row_factory = old_rf

    # Normalize province names to 2-letter codes (frontend uses codes)
    _PROV_NORMALIZE = {
        'Newfoundland and Labrador': 'NL', 'Newfoundland': 'NL',
        'Prince Edward Island': 'PE', 'PEI': 'PE',
        'Nova Scotia': 'NS', 'New Brunswick': 'NB',
        'Quebec': 'QC', 'Ontario': 'ON',
        'Manitoba': 'MB', 'Saskatchewan': 'SK',
        'Alberta': 'AB', 'British Columbia': 'BC',
        'Yukon': 'YT', 'Northwest Territories': 'NT', 'Nunavut': 'NU',
        'National': 'national', 'national': 'national', 'global': 'national',
    }
    # Skip duplicate legacy names (e.g. cpi_national, unemployment_national)
    _SKIP_INDICATORS = {'cpi_national', 'unemployment_national', 'cpi_date', 'cpi_prev',
                        'unemployment_date', 'unemployment_prev', 'gdp_date',
                        'housingStarts_date', 'housingStarts_prev'}
    history_list = []
    for r in history_rows:
        row = dict(r)
        if row['indicator_name'] in _SKIP_INDICATORS:
            continue
        prov = row.get('province', 'national')
        row['province'] = _PROV_NORMALIZE.get(prov, prov)
        # Ensure value is numeric where possible
        try:
            row['value'] = float(str(row['value']).replace(',', '').replace('%', '').replace('+', ''))
        except (ValueError, TypeError):
            pass
        history_list.append(row)

    # Include StatCan key economic indicators from dashboard_state
    statcan_latest = get_dashboard_state(conn, "statcan_indicators_latest") or get_dashboard_state(conn, "statcan_latest")

    output = {
        "indicators": indicators_list,
        "history": history_list,
        "statcan_latest": statcan_latest,
    }

    out_path = os.path.join(output_dir, "indicators.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return out_path


def export_trends(conn, output_dir: str) -> str:
    """Export trends.json from get_trend_snapshots."""
    from db import get_trend_snapshots

    snapshots_raw = get_trend_snapshots(conn, limit=12)
    snapshots = []
    for snap in snapshots_raw:
        if hasattr(snap, "keys"):
            row = dict(snap)
            # snapshot field is stored as JSON string
            if "snapshot" in row and isinstance(row["snapshot"], str):
                row["snapshot"] = _safe_json_loads(row["snapshot"], {})
            snapshots.append(row)
        else:
            snapshots.append(snap)

    out_path = os.path.join(output_dir, "trends.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, ensure_ascii=False, indent=2)

    return out_path


def export_events(conn, output_dir: str) -> str:
    """Export events.json from get_upcoming_events (30-day window)."""
    from event_calendar import get_upcoming_events

    events = get_upcoming_events(conn=conn, days_ahead=30)

    out_path = os.path.join(output_dir, "events.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    return out_path


def export_microscope(conn, output_dir: str) -> str:
    """Export microscope.json from get_dashboard_state microscope_history."""
    from db import get_dashboard_state

    history = get_dashboard_state(conn, "microscope_history")

    out_path = os.path.join(output_dir, "microscope.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return out_path


def export_policy(conn, output_dir: str) -> str:
    """Export policy.json from policy_snapshots table and dashboard_state."""
    from db import get_dashboard_state

    # Try policy_snapshots table first (from Prompt 15 policy tracker)
    weeks = []
    try:
        rows = conn.execute("""
            SELECT week_of, summary FROM policy_snapshots
            ORDER BY week_of DESC LIMIT 8
        """).fetchall()
        for row in rows:
            weeks.append({
                "week_of": row[0],
                "summary": _safe_json_loads(row[1], {}),
            })
    except Exception:
        pass  # Table may not exist yet

    # Fallback: dashboard_state policy_developments keys
    if not weeks:
        row = conn.execute("""
            SELECT value FROM dashboard_state
            WHERE key LIKE 'policy_developments_%'
            ORDER BY key DESC LIMIT 1
        """).fetchone()
        if row:
            data = _safe_json_loads(row[0], {})
        else:
            data = {"articles": [], "count": 0}
    else:
        data = {
            "weeks": weeks,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    out_path = os.path.join(output_dir, "policy.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return out_path


def export_commodities(conn, output_dir: str) -> str:
    """Export commodities.json from canadian_commodities in dashboard_state."""
    from db import get_dashboard_state

    data = get_dashboard_state(conn, "canadian_commodities")
    if not data or not isinstance(data, dict):
        data = {"indicators": {}}

    out_path = os.path.join(output_dir, "commodities.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return out_path


def export_timeseries(conn, output_dir: str) -> str:
    """Export timeseries.json as a single bundled object keyed by series_name."""
    from db import get_timeseries

    bundle = {}
    for series_name in _TIMESERIES_NAMES:
        rows = get_timeseries(conn, series_name, limit=52)
        points = []
        for row in rows:
            if hasattr(row, "keys"):
                points.append(dict(row))
            else:
                points.append(row)
        if points:
            bundle[series_name] = points

    # Also build sparkline data from indicator_history for market data
    # Uses the new naming convention (wti, sp500, etc.)
    _IH_SERIES = [
        'tsx_composite', 'sp500', 'djia', 'nasdaq', 'ftse100', 'dax', 'nikkei225',
        'cadusd', 'eurusd', 'usdcny', 'usdjpy',
        'wti', 'brent', 'natural_gas', 'gold', 'silver', 'platinum', 'palladium',
        'copper', 'aluminum', 'wheat', 'corn', 'soybeans', 'coffee', 'cocoa',
        'sugar', 'cotton', 'lumber',
        # New: FRED commodities + bond spreads
        'iron_ore', 'nickel', 'zinc', 'tin', 'lead', 'lng_asia',
        'ig_spread', 'hy_spread', 'yield_curve_10y2y',
        # New: crypto, shipping, Canadian mining/agriculture
        'bitcoin', 'ethereum', 'dry_bulk_shipping',
        'potash_nutrien', 'cameco_uranium', 'sprott_uranium', 'canola',
        'coal', 'propane', 'rice', 'soybean_oil', 'soybean_meal',
    ]
    for name in _IH_SERIES:
        if name in bundle:
            continue  # already have timeseries data
        rows = conn.execute("""
            SELECT period AS date, value, unit, source
            FROM indicator_history
            WHERE indicator_name = ? AND period IS NOT NULL
            ORDER BY period DESC LIMIT 260
        """, (name,)).fetchall()
        if rows:
            bundle[name] = [dict(r) for r in rows]

    # Province-level indicator history for theme line charts
    # Export as {provCode}_{indicator} keys (e.g. AB_unemployment, QC_exports)
    _PROV_CODES = ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'ON', 'PEI', 'QC', 'SK']
    _PROV_INDICATORS = ['unemployment', 'cpi']
    for prov in _PROV_CODES:
        for ind in _PROV_INDICATORS:
            key = f"{prov}_{ind}"
            rows = conn.execute("""
                SELECT period AS date, value, unit, source
                FROM indicator_history
                WHERE indicator_name = ? AND province = ? AND period IS NOT NULL
                ORDER BY period DESC LIMIT 260
            """, (ind, prov)).fetchall()
            if rows:
                bundle[key] = [dict(r) for r in rows]

    # Ontario detailed series (quarterly GDP components)
    for ind in ['on_exports', 'on_imports', 'on_real_capital_investment',
                'on_gdp_goods', 'on_real_consumption', 'on_real_household']:
        key = f"ON_{ind}"
        rows = conn.execute("""
            SELECT period AS date, value, unit, source
            FROM indicator_history
            WHERE indicator_name = ? AND province = 'ON' AND period IS NOT NULL
            ORDER BY period DESC LIMIT 60
        """, (ind,)).fetchall()
        if rows:
            bundle[key] = [dict(r) for r in rows]

    # Quebec detailed series
    for ind in ['qc_exports', 'qc_imports', 'qc_business_investment',
                'qc_manufacturing_sales', 'qc_housing_starts', 'qc_employment',
                'qc_unemployment_rate', 'qc_bldg_permits_res', 'qc_bldg_permits_nonres',
                'qc_real_gdp', 'qc_intl_exports', 'qc_intl_imports', 'qc_retail_sales']:
        key = f"QC_{ind}"
        rows = conn.execute("""
            SELECT period AS date, value, unit, source
            FROM indicator_history
            WHERE indicator_name = ? AND province = 'QC' AND period IS NOT NULL
            ORDER BY period DESC LIMIT 60
        """, (ind,)).fetchall()
        if rows:
            bundle[key] = [dict(r) for r in rows]

    out_path = os.path.join(output_dir, "timeseries.json")
    with open(out_path, "w", encoding="utf-8") as f:
        # Compact for potentially large commodity data
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))

    return out_path


def _project_for_export_slim(proj_dict: dict) -> dict:
    """Like _project_for_export but trims evidence/sources to reduce file size.

    Used for projects_all.json which contains thousands of projects.
    Keeps only the first evidence URL and drops full evidence text.
    """
    shaped = _project_for_export(proj_dict)
    # Trim evidence array: keep only first 2 entries, drop full text
    ev = shaped.get("evidence", [])
    shaped["evidence"] = [
        {"url": e.get("url", ""), "source": e.get("source", "")}
        for e in ev[:2]
        if e.get("url")
    ]
    shaped["evidence_count"] = len(ev)
    # Drop full statusHistory (keep count only)
    sh = shaped.get("statusHistory", [])
    shaped["statusHistory"] = sh[-1:] if sh else []
    # Drop tags and discovery_sources
    shaped.pop("tags", None)
    shaped.pop("discovery_sources", None)
    shaped.pop("sources", None)
    return shaped


def export_all_projects(conn, output_dir: str) -> str:
    """Export projects_all.json — all projects across all provinces, no threshold filter.

    Sorts by lastSeen desc, no row limit (exports all projects).
    Uses slim export shape to keep file size manageable.

    Returns the path of the written file.
    """
    rows = conn.execute(
        """
        SELECT * FROM projects
        ORDER BY lastSeen DESC
        """
    ).fetchall()

    included = []
    for raw in rows:
        if hasattr(raw, "keys"):
            proj = dict(raw)
        else:
            proj = raw
        shaped = _project_for_export_slim(proj)
        included.append(shaped)

    out_path = os.path.join(output_dir, "projects_all.json")
    with open(out_path, "w", encoding="utf-8") as f:
        # Compact JSON for potentially large file
        json.dump(included, f, ensure_ascii=False, separators=(",", ":"))

    return out_path


def export_pipeline_status(conn, output_dir: str) -> str:
    """Export pipeline_status.json — latest run info, tavily credits, claude token aggregation.

    Structure:
    {
      "last_run": { "started_at": "...", "status": "...", "duration_seconds": N,
                    "discovery": {...}, "errors": [...] },
      "tavily": { "used": N, "month": "..." },
      "claude_tokens": { "input": N, "output": N },
      "recent_runs": [...]
    }

    Returns the path of the written file.
    """
    from db import get_dashboard_state, get_pipeline_runs

    # Most recent pipeline run
    runs = get_pipeline_runs(conn, limit=4)

    last_run = {}
    if runs:
        r = runs[0]
        last_run = {
            "started_at": r.get("started_at", ""),
            "status": r.get("status", "unknown"),
            "duration_seconds": r.get("duration_seconds", 0),
            "discovery": r.get("discovery", {}),
            "errors": r.get("errors", []),
        }

    # Aggregate Claude tokens from last 4 runs
    claude_input = 0
    claude_output = 0
    for r in runs:
        api = r.get("api_usage", {})
        claude_input += api.get("claude_sonnet_input_tokens", 0)
        claude_output += api.get("claude_sonnet_output_tokens", 0)

    # Tavily credits from dashboard_state
    tavily_data = get_dashboard_state(conn, "tavily_credits") or {}
    if isinstance(tavily_data, dict):
        tavily_used = tavily_data.get("used", 0)
        tavily_month = tavily_data.get("month", "")
    else:
        tavily_used = 0
        tavily_month = ""

    # Recent runs summary (all 4, trimmed for size)
    recent_runs = []
    for r in runs:
        recent_runs.append({
            "started_at": r.get("started_at", ""),
            "status": r.get("status", "unknown"),
            "duration_seconds": r.get("duration_seconds", 0),
            "discovery": r.get("discovery", {}),
        })

    # Check if latest newsletter payload has incomplete analysis flag
    latest_newsletter = get_dashboard_state(conn, "newsletter_latest") or {}
    analysis_incomplete = bool(
        latest_newsletter.get("_analysis_incomplete")
        if isinstance(latest_newsletter, dict) else False
    )

    output = {
        "last_run": last_run,
        "analysis_incomplete": analysis_incomplete,
        "tavily": {"used": tavily_used, "month": tavily_month},
        "claude_tokens": {"input": claude_input, "output": claude_output},
        "recent_runs": recent_runs,
    }

    out_path = os.path.join(output_dir, "pipeline_status.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def export_all(conn=None, output_dir: str = "docs/data") -> dict:
    """Export all dashboard data to static JSON files.

    Args:
        conn: sqlite3.Connection from db.py. If None, creates one via get_db().
        output_dir: Directory to write JSON files. Created if it does not exist.

    Returns:
        dict with keys: file_count, output_dir, files_written
    """
    from db import get_db, init_db
    from pipeline_config import PROVINCES

    _own_conn = False
    if conn is None:
        conn = init_db()
        _own_conn = True

    os.makedirs(output_dir, exist_ok=True)

    files_written = []

    # Province files
    for prov in PROVINCES:
        path = export_province_projects(
            conn,
            prov["name"],
            prov["threshold_val"],
            output_dir,
        )
        files_written.append(os.path.basename(path))

    # Briefings
    latest_path, archive_path = export_briefings(conn, output_dir)
    files_written.extend([
        os.path.basename(latest_path),
        os.path.basename(archive_path),
    ])

    # Indicators
    path = export_indicators(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Trends
    path = export_trends(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Events
    path = export_events(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Microscope
    path = export_microscope(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Timeseries
    path = export_timeseries(conn, output_dir)
    files_written.append(os.path.basename(path))

    # All projects (combined, no threshold)
    path = export_all_projects(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Pipeline status (run info + cost data)
    path = export_pipeline_status(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Policy developments
    path = export_policy(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Canadian commodity indicators
    path = export_commodities(conn, output_dir)
    files_written.append(os.path.basename(path))

    # Manifest
    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "province_count": len(PROVINCES),
        "file_count": len(files_written),
        "file_list": sorted(files_written),
    }
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    files_written.append("manifest.json")

    print(f"[EXPORT] Wrote {len(files_written)} files to {output_dir}/")

    if _own_conn:
        conn.close()

    return {
        "file_count": len(files_written),
        "output_dir": output_dir,
        "files_written": files_written,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE VALIDATION (run after export_all in __main__)
# ═══════════════════════════════════════════════════════════════════════════════


def _validate_output(output_dir: str) -> bool:
    """Load each JSON file and print a summary line per file."""
    json_files = sorted(glob.glob(os.path.join(output_dir, "*.json")))
    if not json_files:
        print(f"[VALIDATE] No JSON files found in {output_dir}/")
        return False

    all_ok = True
    print(f"\n[VALIDATE] Checking {len(json_files)} files in {output_dir}/")
    print(f"{'File':<45} {'Size (KB)':>10} {'Entries':>10}")
    print("-" * 70)

    for fpath in json_files:
        fname = os.path.basename(fpath)
        size_kb = os.path.getsize(fpath) / 1024
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                entry_count = len(data)
            elif isinstance(data, dict):
                entry_count = len(data)
            else:
                entry_count = 1
            print(f"{fname:<45} {size_kb:>9.1f}K {entry_count:>10}")
        except json.JSONDecodeError as e:
            print(f"{fname:<45} INVALID JSON: {e}")
            all_ok = False

    print("-" * 70)
    status = "PASSED" if all_ok else "FAILED"
    print(f"[VALIDATE] {status} — all files valid JSON\n")
    return all_ok


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Export CAN-MACRO dashboard data to static JSON files."
    )
    parser.add_argument(
        "--out",
        default="docs/data",
        help="Output directory (default: docs/data)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (default: dashboard.db or DB_PATH env var)",
    )
    args = parser.parse_args()

    from db import init_db

    db_conn = init_db(args.db)
    result = export_all(conn=db_conn, output_dir=args.out)
    _validate_output(args.out)
    db_conn.close()

    sys.exit(0)
