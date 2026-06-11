"""
canadian_markets.py -- Canadian-specific commodity and market indicators
beyond standard Yahoo Finance tickers.

Fetches Canadian commodity benchmarks and construction input prices,
then generates market commentary connecting price movements to the
project database via Claude Sonnet.
"""

import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _yf_close(obj):
    """Coerce a yfinance 'Close' slice into a flat numeric Series.

    yfinance >=1.x returns MultiIndex columns even for single-ticker
    downloads, so df['Close'] is a 1-column DataFrame and float(x.iloc[-1])
    raises "not 'Series'". Squeeze 1-col frames to a Series (multi-col → first
    column); pass real Series through. Returns a NaN-dropped float Series, or
    None if unusable.
    """
    try:
        import pandas as pd
        if obj is None:
            return None
        if isinstance(obj, pd.DataFrame):
            if obj.shape[1] == 0:
                return None
            obj = obj.iloc[:, 0]
        s = pd.to_numeric(obj, errors="coerce").dropna()
        return s if len(s) else None
    except Exception:
        return None


# ── StatCan WDS fetch (canola — no free market feed exists) ──────────
# Mirrors _fetch_wds() in statcan_extended.py: same endpoint, headers,
# 3 attempts with backoff. Kept local because this module is otherwise
# yfinance-only and imports requests lazily.

_STATCAN_WDS_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
_WDS_HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)',
}
_WDS_BACKOFF = [5, 15]  # seconds between the 3 total attempts


def _fetch_statcan_monthly(vector_id, n=14):
    """Fetch the last N monthly observations for one StatCan vector.

    Returns [{'refPer': 'YYYY-MM-DD', 'value': float}] sorted by date,
    or [] on failure (logged, never raises).
    """
    import time
    import requests

    payload = [{"vectorId": vector_id, "latestN": n}]
    for attempt in range(3):
        try:
            resp = requests.post(_STATCAN_WDS_URL, json=payload,
                                 timeout=40, headers=_WDS_HEADERS)
            resp.raise_for_status()
            for item in resp.json():
                if item.get('status') != 'SUCCESS':
                    continue
                return sorted(
                    [{'refPer': p.get('refPer', ''), 'value': float(p['value'])}
                     for p in item.get('object', {}).get('vectorDataPoint', [])
                     if p.get('value') is not None],
                    key=lambda x: x['refPer'])
            return []
        except Exception as e:
            if attempt < 2:
                time.sleep(_WDS_BACKOFF[attempt])
            else:
                logger.warning(
                    f"StatCan WDS vector {vector_id} failed after 3 attempts: {e}")
    return []


# ── Canadian commodity indicator definitions ─────────────────────────

CANADIAN_COMMODITY_INDICATORS = {
    # Oil -- Canadian-specific
    "wcs_discount": {
        "description": "Western Canadian Select discount to WTI",
        "relevance": "Determines Alberta oil sands profitability. Wide (>$15) makes heavy oil uneconomic. Narrow (<$10) signals strong pipeline capacity.",
        "affected_sectors": ["Mining & O&G"],
        "affected_provinces": ["AB", "SK"],
        "tickers": ["WCS=F", "CL=F"],  # WCS future vs WTI
        "compute": "spread",
    },
    "uranium_spot": {
        # Real physical-uranium proxy: Sprott Physical Uranium Trust holds
        # physical U3O8, so its unit price tracks the uranium spot price —
        # far closer to spot than URA (a basket of uranium *equities*).
        "description": "Uranium spot price proxy (Sprott Physical Uranium Trust)",
        "relevance": "Determines Saskatchewan uranium mine expansion viability and SMR project economics.",
        "affected_sectors": ["Mining & O&G", "Utilities"],
        "affected_provinces": ["SK", "ON", "NB"],
        "tickers": ["U-UN.TO"],
    },
    "nickel": {
        "description": "Nickel price proxy",
        "relevance": "Affects Ontario and Quebec nickel mine projects and EV battery supply chain.",
        "affected_sectors": ["Mining & O&G"],
        "affected_provinces": ["ON", "QC", "NL", "MB"],
        # 2026-04-18: JJN (iPath nickel ETN) delisted. FM.TO (First Quantum
        # Minerals) is a Canadian nickel+copper producer — cleanest free proxy.
        "tickers": ["FM.TO"],
    },
    "canola": {
        # Yahoo has no free canola feed (RS=F futures delisted), so this is
        # the one indicator sourced from StatCan WDS instead of yfinance.
        # Table 32-10-0077-01 (farm product prices) has no Canada-level
        # geography — provincial only — so Saskatchewan, the largest canola
        # producer, is the benchmark. Vector resolved 2026-06-11 via
        # getCubeMetadata + getSeriesInfoFromCubePidCoord (coordinate
        # 8.18.0.0.0.0.0.0.0.0): v31212214 = "Saskatchewan; Canola (including
        # rapeseed)", $/tonne, monthly, current (latest refPer 2026-04).
        "description": "Canola farm price, Saskatchewan (StatCan 32-10-0077-01)",
        "relevance": "Canola is Saskatchewan and Alberta's dominant oilseed crop.",
        "affected_sectors": ["Agriculture"],
        "affected_provinces": ["SK", "AB", "MB"],
        "tickers": [],
        "statcan_vector": 31212214,
        "unit": "$/tonne",
    },
    "iron_ore": {
        "description": "Iron ore price proxy (Vale SA)",
        "relevance": "Vale is the world's largest iron ore producer. Affects steel input costs for infrastructure and manufacturing projects.",
        "affected_sectors": ["Mining & O&G", "Construction"],
        "affected_provinces": ["QC", "NL"],
        "tickers": ["VALE"],
    },
    "steel": {
        "description": "Steel price proxy (SLX ETF)",
        "relevance": "Major input cost for infrastructure and building construction.",
        "affected_sectors": ["Construction", "Transportation"],
        "tickers": ["SLX"],
    },
    "lumber": {
        "description": "Lumber futures",
        "relevance": "Key input for residential construction. BC forestry sector bellwether.",
        "affected_sectors": ["Construction", "Real Estate"],
        "affected_provinces": ["BC", "QC", "ON"],
        # 2026-04-18: LBS=F (mini contract) delisted on Yahoo Finance; LBR=F
        # (physical/classic lumber) is the working ticker.
        "tickers": ["LBR=F"],
    },
    "tsx_infrastructure": {
        "description": "Canadian infrastructure companies basket",
        "relevance": "Market valuation of infrastructure companies signals investment appetite.",
        "affected_sectors": ["Utilities", "Transportation"],
        "tickers": ["BIP-UN.TO", "AQN.TO", "BEPC.TO", "TRP.TO", "ENB.TO"],
        "compute": "basket_avg",
    },
    "potash_nutrien": {
        "description": "Nutrien Ltd (potash/fertilizer)",
        "relevance": "World's largest potash producer. Saskatchewan economy proxy. Fertilizer prices affect agriculture project economics.",
        "affected_sectors": ["Mining & O&G", "Agriculture"],
        "affected_provinces": ["SK", "AB"],
        "tickers": ["NTR.TO"],
    },
    "cameco_uranium": {
        "description": "Cameco Corp (uranium mining)",
        "relevance": "Largest Canadian uranium producer. Proxy for uranium sector activity and SMR supply chain.",
        "affected_sectors": ["Mining & O&G", "Utilities"],
        "affected_provinces": ["SK", "ON"],
        "tickers": ["CCO.TO"],
    },
    "sprott_uranium": {
        "description": "Sprott Physical Uranium Trust (spot price proxy)",
        "relevance": "Closest free proxy for uranium spot price. TSX-listed. Tracks physical uranium holdings.",
        "affected_sectors": ["Mining & O&G", "Utilities"],
        "affected_provinces": ["SK", "ON", "NB"],
        "tickers": ["U-UN.TO"],
    },
}


def fetch_canadian_commodities():
    """Fetch Canadian commodity prices via yfinance.

    Returns dict of indicator_id -> {current, week_ago, month_ago, year_ago, pct_changes}
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed, skipping commodity fetch")
        return {}

    results = {}
    now = datetime.utcnow()

    for ind_id, info in CANADIAN_COMMODITY_INDICATORS.items():
        tickers = info.get("tickers", [])
        compute = info.get("compute", "single")

        try:
            if info.get("statcan_vector"):
                # StatCan WDS monthly series (canola). Needs >=2 points for a
                # period-over-period comparison; otherwise honest N/A (skip).
                pts = _fetch_statcan_monthly(info["statcan_vector"])
                if len(pts) < 2:
                    continue
                vals = [p["value"] for p in pts]
                current = float(vals[-1])
                # Monthly series — no weekly resolution. week_ago = current
                # keeps the dict shape (pct_1w reads 0.0); 'frequency' below
                # marks the series monthly for downstream consumers.
                week_ago = current
                month_ago = float(vals[-2])
                year_ago = float(vals[-13]) if len(vals) >= 13 else float(vals[0])
                results[ind_id] = {
                    "description": info["description"],
                    "current": round(current, 2),
                    "week_ago": round(week_ago, 2),
                    "month_ago": round(month_ago, 2),
                    "year_ago": round(year_ago, 2),
                    "pct_1w": 0.0,
                    "pct_1m": round((current - month_ago) / abs(month_ago) * 100, 1) if month_ago else 0,
                    "pct_1y": round((current - year_ago) / abs(year_ago) * 100, 1) if year_ago else 0,
                    "affected_sectors": info.get("affected_sectors", []),
                    "affected_provinces": info.get("affected_provinces", []),
                    "relevance": info["relevance"],
                    "frequency": "monthly",
                    "unit": info.get("unit", ""),
                    "monthly_points": pts,
                }
                continue

            if compute == "basket_avg":
                # Average of multiple tickers
                prices = []
                for ticker in tickers:
                    data = yf.download(ticker, period="1y", progress=False)
                    try:
                        s = _yf_close(data["Close"]) if data is not None and len(data) else None
                    except Exception:
                        s = None
                    if s is not None and len(s) > 0:
                        prices.append(s)
                if not prices:
                    continue
                import pandas as pd
                combined = pd.concat(prices, axis=1).mean(axis=1).dropna()
                if len(combined) == 0:
                    continue
                current = float(combined.iloc[-1])
                week_ago = float(combined.iloc[-6]) if len(combined) > 5 else current
                month_ago = float(combined.iloc[-22]) if len(combined) > 21 else current
                year_ago = float(combined.iloc[0]) if len(combined) > 200 else current

            elif compute == "spread":
                # Difference between two tickers
                closes = []
                for ticker in tickers[:2]:
                    closes.append(_yf_close(yf.download(ticker, period="1y", progress=False)["Close"]))
                if len(closes) < 2 or any(c is None for c in closes):
                    continue
                spread = (closes[0] - closes[1]).dropna()
                if len(spread) == 0:
                    continue
                current = float(spread.iloc[-1])
                week_ago = float(spread.iloc[-6]) if len(spread) > 5 else current
                month_ago = float(spread.iloc[-22]) if len(spread) > 21 else current
                year_ago = float(spread.iloc[0]) if len(spread) > 200 else current

            else:
                # Single ticker
                ticker = tickers[0] if tickers else None
                if not ticker:
                    continue
                data = yf.download(ticker, period="1y", progress=False)
                col = _yf_close(data["Close"]) if data is not None and len(data) else None
                if col is None or len(col) == 0:
                    continue
                current = float(col.iloc[-1])
                week_ago = float(col.iloc[-6]) if len(col) > 5 else current
                month_ago = float(col.iloc[-22]) if len(col) > 21 else current
                year_ago = float(col.iloc[0]) if len(col) > 200 else current

            results[ind_id] = {
                "description": info["description"],
                "current": round(current, 2),
                "week_ago": round(week_ago, 2),
                "month_ago": round(month_ago, 2),
                "year_ago": round(year_ago, 2),
                "pct_1w": round((current - week_ago) / abs(week_ago) * 100, 1) if week_ago else 0,
                "pct_1m": round((current - month_ago) / abs(month_ago) * 100, 1) if month_ago else 0,
                "pct_1y": round((current - year_ago) / abs(year_ago) * 100, 1) if year_ago else 0,
                "affected_sectors": info.get("affected_sectors", []),
                "affected_provinces": info.get("affected_provinces", []),
                "relevance": info["relevance"],
            }

        except Exception as e:
            logger.debug(f"Commodity {ind_id} fetch failed: {e}")

    return results


async def generate_market_commentary(market_data, project_data, policy_context,
                                     trade_policy=None):
    """Generate weekly market commentary connecting prices to projects via Claude Sonnet."""
    from claude_reasoning import reason_with_claude_tracked

    system = (
        "You are a Canadian commodity and market reporter. Report price movements "
        "factually and state the number of tracked projects affected. "
        "Use short paragraphs (2-3 sentences each). "
        "NEVER forecast, predict, or editorialize. NEVER use 'looking ahead', "
        "'expected to', 'is likely to', 'outlook', 'encouraging', 'concerning'. "
        "State what happened: prices moved, policy changed, X projects are in affected sectors. "
        "If trade policy developments occurred, state the policy change and the data. "
        "Reference specific projects from the database when possible. "
        "Write 200-300 words in short paragraphs."
    )

    by_sector = project_data.get("by_sector", {}) if isinstance(project_data, dict) else {}

    user_prompt = f"""CANADIAN MARKET DATA (current vs 1w / 1m / 1y):
{json.dumps(market_data, indent=2)}

ACTIVE PROJECT PIPELINE SUMMARY:
- Total projects: {project_data.get('total', 0) if isinstance(project_data, dict) else 0}
- Energy: {by_sector.get('Mining & O&G', {}).get('count', 0)} projects
- Construction: {by_sector.get('Construction', {}).get('count', 0)} projects
- Real Estate: {by_sector.get('Real Estate', {}).get('count', 0)} projects
- Utilities: {by_sector.get('Utilities', {}).get('count', 0)} projects

RECENT POLICY CONTEXT:
{json.dumps(policy_context[:3], indent=2) if policy_context else 'No significant policy changes this week.'}

TRADE POLICY DEVELOPMENTS:
{json.dumps([{'title': t.get('title', ''), 'categories': t.get('policy_categories', []), 'affected_sectors': t.get('affected_sectors', [])} for t in (trade_policy or [])[:5]], indent=2) if trade_policy else 'No trade policy changes this week.'}

Write a factual market report for a Canadian economic intelligence briefing.
Report price movements and their connection to tracked projects.
Lead with the largest price movement this week. Short paragraphs only."""

    from claude_reasoning import OPUS_WRITING_MODEL
    return await reason_with_claude_tracked(
        system, user_prompt, task_name="market_commentary", max_tokens=1500,
        model=OPUS_WRITING_MODEL,
    )


def fetch_and_store_commodities(conn=None, db=None):
    """Fetch Canadian commodities and store in SQLite.

    Args:
        conn: sqlite3.Connection from db.py (preferred)
        db: deprecated Firestore client; ignored (kept for backward compatibility)

    Returns the commodity data dict.
    """
    print("\n[MARKETS] Fetching Canadian commodity indicators...")
    data = fetch_canadian_commodities()

    if not data:
        print("  [MARKETS] No commodity data fetched")
        return {}

    print(f"  [MARKETS] {len(data)} commodity indicators fetched")

    # Store in SQLite dashboard_state (for frontend/export)
    if conn and hasattr(conn, 'execute'):
        try:
            from db import save_dashboard_state
            save_dashboard_state(conn, "canadian_commodities", {
                "indicators": data,
                "updated_at": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.warning(f"Failed to store commodities: {e}")

        # Also persist key Canadian commodity values to timeseries table
        # so they appear in historical trend charts alongside standard commodities
        try:
            from db import save_timeseries_point
            today_str = datetime.utcnow().strftime('%Y-%m-%d')
            ts_count = 0

            # Map canadian_markets indicator IDs to timeseries series names
            COMMODITY_TS_MAP = {
                'uranium_spot':       ('comm_uranium',    '$', 'Sprott Physical Uranium Trust (U-UN.TO)'),
                'nickel':             ('comm_nickel',     '$', 'yfinance (JJN ETN)'),
                'steel':              ('comm_steel',      '$', 'yfinance (SLX ETF)'),
                'lumber':             ('comm_lumber',     '$/mbf', 'yfinance (LBR=F)'),
                'wcs_discount':       ('comm_wcs_discount', '$/bbl', 'yfinance (WCS-WTI)'),
                'tsx_infrastructure': ('comm_tsx_infra',  '$', 'yfinance (basket avg)'),
            }
            # Red-team 2.4 (2026-06-11): do NOT mirror U-UN.TO onto the
            # canonical 'uranium' key. The trust's UNIT PRICE (~$25-35) is a
            # different quantity than the series' existing U3O8 SPOT point
            # (~$86/lb) — appending it creates a fake cliff in the series the
            # validator and chart agent treat as ground truth. The fund price
            # keeps accruing under 'comm_uranium' (map below); the canonical
            # 'uranium' key stays empty until a true spot feed is wired.

            # Canola (2026-06-11): StatCan farm-price vector is monthly, so
            # write each observation under its own refPer date (not today's)
            # to the CANONICAL 'canola' key the chart agent reads. The upsert
            # is ON CONFLICT DO NOTHING, so re-appending the last 14 months
            # every week backfills history once and is idempotent after that.
            for pt in data.get('canola', {}).get('monthly_points') or []:
                save_timeseries_point(
                    conn, 'canola', pt['refPer'], pt['value'], '$/tonne',
                    'StatCan 32-10-0077-01 v31212214 (Saskatchewan canola farm price)')
                ts_count += 1

            for ind_id, (series_name, unit, source) in COMMODITY_TS_MAP.items():
                if ind_id in data and data[ind_id].get('current') is not None:
                    save_timeseries_point(
                        conn, series_name, today_str,
                        data[ind_id]['current'], unit, source
                    )
                    ts_count += 1

            if ts_count:
                print(f"  [MARKETS] {ts_count} commodity values saved to timeseries")
        except Exception as e:
            logger.warning(f"Failed to save commodity timeseries: {e}")

    return data
