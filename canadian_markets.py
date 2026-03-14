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
        "description": "Uranium spot price proxy (URA ETF)",
        "relevance": "Determines Saskatchewan uranium mine expansion viability and SMR project economics.",
        "affected_sectors": ["Mining & O&G", "Utilities"],
        "affected_provinces": ["SK", "ON", "NB"],
        "tickers": ["URA"],
    },
    "nickel": {
        "description": "Nickel price proxy (NIKL ETF)",
        "relevance": "Affects Ontario and Quebec nickel mine projects and EV battery supply chain.",
        "affected_sectors": ["Mining & O&G"],
        "affected_provinces": ["ON", "QC", "NL", "MB"],
        "tickers": ["JJN"],  # iPath nickel ETN
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
        "tickers": ["LBS=F"],
    },
    "tsx_infrastructure": {
        "description": "Canadian infrastructure companies basket",
        "relevance": "Market valuation of infrastructure companies signals investment appetite.",
        "affected_sectors": ["Utilities", "Transportation"],
        "tickers": ["BIP-UN.TO", "AQN.TO", "BEPC.TO", "TRP.TO", "ENB.TO"],
        "compute": "basket_avg",
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
            if compute == "basket_avg":
                # Average of multiple tickers
                prices = []
                for ticker in tickers:
                    data = yf.download(ticker, period="1y", progress=False)
                    if data is not None and len(data) > 0:
                        prices.append(data["Close"])
                if not prices:
                    continue
                import pandas as pd
                combined = pd.concat(prices, axis=1).mean(axis=1)
                current = float(combined.iloc[-1])
                week_ago = float(combined.iloc[-6]) if len(combined) > 5 else current
                month_ago = float(combined.iloc[-22]) if len(combined) > 21 else current
                year_ago = float(combined.iloc[0]) if len(combined) > 200 else current

            elif compute == "spread":
                # Difference between two tickers
                data_list = []
                for ticker in tickers[:2]:
                    data = yf.download(ticker, period="1y", progress=False)
                    data_list.append(data)
                if len(data_list) < 2:
                    continue
                spread = data_list[0]["Close"] - data_list[1]["Close"]
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
                if data is None or len(data) == 0:
                    continue
                current = float(data["Close"].iloc[-1])
                week_ago = float(data["Close"].iloc[-6]) if len(data) > 5 else current
                month_ago = float(data["Close"].iloc[-22]) if len(data) > 21 else current
                year_ago = float(data["Close"].iloc[0]) if len(data) > 200 else current

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
        "You are a Canadian commodity and market analyst focused on implications "
        "for capital investment and construction activity. Connect price changes to "
        "specific Canadian economic impacts. Be specific about thresholds and "
        "reference specific projects from the database when possible. "
        "If trade policy developments (tariffs, export controls, trade agreements) "
        "occurred this week, note them alongside affected commodity price movements "
        "and the number of projects in affected sectors. State the policy change "
        "and the data — do not speculate on impact. "
        "Write 200-300 words."
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

Write a concise market commentary for a Canadian economic intelligence briefing.
Focus on what matters for capital investment decisions.
Lead with the most significant market development this week."""

    return await reason_with_claude_tracked(
        system, user_prompt, task_name="market_commentary", max_tokens=1500,
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

    # Store in SQLite
    if conn and hasattr(conn, 'execute'):
        try:
            from db import save_dashboard_state
            save_dashboard_state(conn, "canadian_commodities", {
                "indicators": data,
                "updated_at": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.warning(f"Failed to store commodities: {e}")

    return data
