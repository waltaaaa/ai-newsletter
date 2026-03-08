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
"""

import asyncio
import os
import logging

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


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
