"""
tavily_search.py — Tavily API integration for targeted web searches.

Budget: 1,000 credits/month free tier.
Basic search = 1 credit each.

Used for:
- Cost-finding for valueless projects (~300/month)
- Named project tracking (~200/month)
- Deep verification (~200/month)
- Enrichment (~150/month)
- Signal investigation / follow-up queries (~100/month)
- Buffer (~50/month)

Credit tracking uses SQLite via db.py — no Firestore dependency.
"""

import asyncio
import os
import logging
from datetime import datetime

from db import get_db, get_tavily_credits, increment_tavily_credits

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_MONTHLY_BUDGET = 1000
TAVILY_BUDGET_BUFFER = 50  # stop enrichment when this many credits remain


# ── Credit tracking ──────────────────────────────────────────────

# Module-level SQLite connection for credit tracking (set by pipeline)
_tracking_conn = None


def set_tracking_db(db):
    """Set the database connection for credit tracking.

    Accepts either a sqlite3.Connection (new) or a legacy Firestore client
    (ignored — a new SQLite connection is obtained via get_db() instead).

    Args:
        db: sqlite3.Connection or any legacy object (ignored if not sqlite3.Connection).
    """
    global _tracking_conn
    import sqlite3
    if isinstance(db, sqlite3.Connection):
        _tracking_conn = db
    else:
        # Legacy Firestore client passed — obtain a real SQLite connection
        _tracking_conn = get_db()


def _get_tracking_conn():
    """Return the active tracking connection, creating one if needed."""
    global _tracking_conn
    if _tracking_conn is None:
        _tracking_conn = get_db()
    return _tracking_conn


def get_tavily_credits_used(db=None):
    """Get Tavily credits used this month from SQLite.

    The ``db`` parameter is accepted for backward compatibility but ignored.
    Credit data is read from SQLite via db.py.

    Returns:
        dict with 'month' (str) and 'used' (int)
    """
    try:
        conn = _get_tracking_conn()
        return get_tavily_credits(conn)
    except Exception as e:
        logger.warning(f"Failed to read Tavily credits: {e}")
        return {"month": datetime.utcnow().strftime("%Y-%m"), "used": 0}


def record_tavily_credit(db=None, credits=1):
    """Record Tavily credit usage in SQLite.

    The ``db`` parameter is accepted for backward compatibility but ignored.
    Writes to SQLite via db.py.

    Args:
        db: Ignored (kept for backward compatibility).
        credits: Number of credits to record (default 1).
    """
    try:
        conn = _get_tracking_conn()
        increment_tavily_credits(conn, credits)
    except Exception as e:
        logger.warning(f"Failed to record Tavily credit: {e}")


def can_use_tavily(db=None, buffer=None):
    """Check if Tavily budget allows more searches.

    The ``db`` parameter is accepted for backward compatibility but ignored.
    Credit data is read from SQLite via db.py.

    Args:
        db: Ignored (kept for backward compatibility).
        buffer: credits to keep in reserve (default: TAVILY_BUDGET_BUFFER)

    Returns:
        True if credits_used < (TAVILY_MONTHLY_BUDGET - buffer)
    """
    if buffer is None:
        buffer = TAVILY_BUDGET_BUFFER
    credits = get_tavily_credits_used()
    remaining = TAVILY_MONTHLY_BUDGET - credits["used"]
    if remaining <= buffer:
        print(f"  [TAVILY] Budget exhausted: {credits['used']}/{TAVILY_MONTHLY_BUDGET} "
              f"credits used this month (buffer={buffer})")
        return False
    return True


# ── Search functions ─────────────────────────────────────────────

async def tavily_search(query, max_results=5, search_depth="basic"):
    """Execute a single Tavily search.

    Args:
        query: Search query string
        max_results: Number of results (1-10)
        search_depth: "basic" (1 credit) or "advanced" (2 credits)

    Returns:
        list of result dicts with title, url, content, score
    """
    if not TAVILY_API_KEY:
        logger.error("TAVILY_API_KEY not set")
        return []

    import aiohttp

    credits = 2 if search_depth == "advanced" else 1

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TAVILY_SEARCH_URL, json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    logger.info(
                        f"Tavily: '{query[:50]}' → {len(results)} results"
                    )
                    record_tavily_credit(credits=credits)
                    return results
                else:
                    text = await resp.text()
                    logger.error(f"Tavily error {resp.status}: {text[:200]}")
                    return []
    except Exception as e:
        logger.error(f"Tavily exception: {e}")
        return []


async def tavily_cost_search(project_name, province, city=None):
    """Search for a project's cost/budget/value."""
    location = f"{city} {province}" if city else province
    query = f"{project_name} {location} budget cost million billion investment"
    return await tavily_search(query, max_results=5, search_depth="basic")


async def tavily_status_search(project_name, province):
    """Search for a project's current status."""
    query = f"{project_name} {province} construction update status 2026"
    return await tavily_search(query, max_results=3, search_depth="basic")


async def tavily_verify_project(project_name, province):
    """Search for second-source confirmation of a project."""
    query = f'"{project_name}" {province} project'
    return await tavily_search(query, max_results=5, search_depth="basic")


def tavily_search_sync(query, max_results=5, search_depth="basic"):
    """Synchronous wrapper for tavily_search."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                tavily_search(query, max_results, search_depth)
            )
        else:
            return asyncio.run(
                tavily_search(query, max_results, search_depth)
            )
    except RuntimeError:
        return asyncio.run(
            tavily_search(query, max_results, search_depth)
        )


def tavily_cost_search_sync(project_name, province, city=None):
    """Synchronous wrapper for tavily_cost_search."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                tavily_cost_search(project_name, province, city)
            )
        else:
            return asyncio.run(
                tavily_cost_search(project_name, province, city)
            )
    except RuntimeError:
        return asyncio.run(
            tavily_cost_search(project_name, province, city)
        )
