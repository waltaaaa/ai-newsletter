"""
searxng_search.py — SearXNG search integration with public instance fallback.

Unlimited free web search. No API key, no credit tracking.

Search chain:
  1. Local SearXNG (Docker) — primary, fastest
  2. Public SearXNG instance — fallback, no signup
  3. Empty results — graceful degradation

Used by:
- nim_deep_search.py (Phase 2) — primary search for K2.5 extraction
- snowball discovery (Phase 6) — adaptive follow-up queries
- cost_finder.py — can supplement Tavily for cost verification

No rate limit on local SearXNG. Public instances may throttle — retry with backoff.
"""

import asyncio
import logging
import time
import threading
from urllib.parse import quote_plus

import aiohttp

from pipeline_config import SEARXNG_ENABLED, SEARXNG_URL, SEARXNG_FALLBACK_URL
import service_health

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30
HEALTH_CHECK_TTL_SECONDS = 300  # cache health check for 5 minutes
BATCH_CONCURRENCY = 5  # parallel SearXNG queries (no rate limit for localhost)
PUBLIC_RETRY_BACKOFF = [1.0, 3.0]  # seconds to wait on 429 from public instance

# Headers for public instances (some block bare requests)
_HEADERS = {
    "User-Agent": "SignalDispatch/1.0 (Canadian infrastructure pipeline)",
    "Accept": "application/json",
}


# ── Health check (cached) ──────────────────────────────────────

_health_cache = {"local": None, "local_ts": 0.0, "fallback": None, "fallback_ts": 0.0}


async def _check_instance(url: str) -> bool:
    """Ping a SearXNG instance to verify it's alive and returning JSON."""
    try:
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            async with session.get(
                f"{url}/search",
                params={"q": "test", "format": "json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return "results" in data
                return False
    except Exception:
        return False


async def is_available(check_fallback: bool = False) -> bool:
    """Check if SearXNG (local or fallback) is reachable. Cached for 5 minutes.

    Args:
        check_fallback: If True, check the fallback instance instead of local.

    Returns:
        True if the instance is reachable and returning JSON.
    """
    if not SEARXNG_ENABLED:
        return False

    key = "fallback" if check_fallback else "local"
    ts_key = f"{key}_ts"
    now = time.monotonic()

    # Return cached result if fresh
    if _health_cache[key] is not None and (now - _health_cache[ts_key]) < HEALTH_CHECK_TTL_SECONDS:
        return _health_cache[key]

    url = SEARXNG_FALLBACK_URL if check_fallback else SEARXNG_URL
    result = await _check_instance(url)
    _health_cache[key] = result
    _health_cache[ts_key] = now

    if not result:
        logger.info(f"SearXNG {key} ({url}) is not available")

    return result


# ── Response normalization ──────────────────────────────────────

def _normalize_results(raw_results: list[dict]) -> list[dict]:
    """Normalize SearXNG results to standard format.

    SearXNG returns: {url, title, content, engine, score, ...}
    We normalize to: {title, url, content, score}
    """
    normalized = []
    for r in raw_results:
        url = r.get("url", "")
        if not url:
            continue
        normalized.append({
            "title": r.get("title", ""),
            "url": url,
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        })
    return normalized


# ── Core search ─────────────────────────────────────────────────

async def _searxng_raw(url: str, query: str, max_results: int = 10,
                       categories: str = "general") -> list[dict]:
    """Execute a search against a specific SearXNG instance.

    Args:
        url: SearXNG instance base URL.
        query: Search query string.
        max_results: Number of results to return.
        categories: SearXNG categories (default: general).

    Returns:
        List of raw result dicts from SearXNG, or empty list on failure.
    """
    params = {
        "q": query,
        "format": "json",
        "categories": categories,
    }

    try:
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            async with session.get(
                f"{url}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    results = data.get("results", [])
                    return results[:max_results]
                elif resp.status == 429:
                    logger.warning(f"SearXNG rate limited at {url}")
                    return []
                else:
                    text = await resp.text()
                    logger.warning(f"SearXNG {resp.status} from {url}: {text[:200]}")
                    return []
    except asyncio.TimeoutError:
        logger.warning(f"SearXNG timeout ({REQUEST_TIMEOUT_SECONDS}s) from {url}")
        return []
    except Exception as e:
        logger.warning(f"SearXNG error from {url}: {e}")
        return []


async def searxng_search(query: str, max_results: int = 10,
                         categories: str = "general") -> list[dict]:
    """Execute a single SearXNG search against the local instance.

    Args:
        query: Search query string.
        max_results: Number of results (default 10).
        categories: SearXNG categories (default: general).

    Returns:
        List of normalized result dicts: {title, url, content, score}.
        Empty list on failure.
    """
    if not SEARXNG_ENABLED:
        return []

    health = service_health.get()
    if not health.is_available("searxng"):
        return []

    raw = await _searxng_raw(SEARXNG_URL, query, max_results, categories)

    if raw:
        health.record_success("searxng")
        logger.info(f"SearXNG: '{query[:50]}' -> {len(raw)} results")
        return _normalize_results(raw)
    else:
        health.record_failure("searxng", f"No results for: {query[:50]}")
        return []


# ── Unified search with fallback ────────────────────────────────

async def search_unified(query: str, max_results: int = 10,
                         categories: str = "general") -> list[dict]:
    """Search with automatic fallback chain.

    Chain: local SearXNG -> public SearXNG fallback -> empty list.

    Args:
        query: Search query string.
        max_results: Number of results (default 10).
        categories: SearXNG categories (default: general).

    Returns:
        List of normalized result dicts: {title, url, content, score}.
    """
    if not SEARXNG_ENABLED:
        return []

    # Try local instance first
    health = service_health.get()
    if health.is_available("searxng"):
        raw = await _searxng_raw(SEARXNG_URL, query, max_results, categories)
        if raw:
            health.record_success("searxng")
            logger.info(f"SearXNG local: '{query[:50]}' -> {len(raw)} results")
            return _normalize_results(raw)

    # Fallback to public instance
    if SEARXNG_FALLBACK_URL:
        for attempt, backoff in enumerate(PUBLIC_RETRY_BACKOFF):
            raw = await _searxng_raw(SEARXNG_FALLBACK_URL, query, max_results, categories)
            if raw:
                logger.info(
                    f"SearXNG fallback: '{query[:50]}' -> {len(raw)} results"
                )
                return _normalize_results(raw)
            # Brief pause before retry (public instance may throttle)
            if attempt < len(PUBLIC_RETRY_BACKOFF) - 1:
                await asyncio.sleep(backoff)

        logger.warning(f"SearXNG fallback exhausted for: '{query[:50]}'")

    return []


# ── Batch search (parallel) ─────────────────────────────────────

async def search_batch(queries: list[str], max_concurrent: int = BATCH_CONCURRENCY,
                       max_results: int = 10) -> dict[str, list[dict]]:
    """Fire multiple SearXNG queries concurrently.

    No rate limit on local SearXNG. Public instances may be slower.
    For 421 queries at 5 concurrent, search time drops from ~7 min to ~1.5 min.

    Args:
        queries: List of search query strings.
        max_concurrent: Max parallel requests (default 5).
        max_results: Results per query (default 10).

    Returns:
        Dict mapping query string -> list of normalized results.
    """
    if not queries:
        return {}

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def _search_one(query: str):
        async with semaphore:
            result = await search_unified(query, max_results)
            results[query] = result

    await asyncio.gather(*[_search_one(q) for q in queries])

    total_results = sum(len(v) for v in results.values())
    queries_with_results = sum(1 for v in results.values() if v)
    logger.info(
        f"SearXNG batch: {len(queries)} queries, "
        f"{queries_with_results} with results, {total_results} total results"
    )

    return results


# ── Sync wrappers ───────────────────────────────────────────────

_sync_loop = None


def _run_sync(coro):
    """Run an async coroutine synchronously using a background event loop thread."""
    global _sync_loop

    if _sync_loop is None or _sync_loop.is_closed():
        _sync_loop = asyncio.new_event_loop()
        t = threading.Thread(target=_sync_loop.run_forever, daemon=True)
        t.start()

    future = asyncio.run_coroutine_threadsafe(coro, _sync_loop)
    return future.result(timeout=REQUEST_TIMEOUT_SECONDS + 10)


def searxng_search_sync(query: str, max_results: int = 10, **kwargs) -> list[dict]:
    """Synchronous wrapper for searxng_search."""
    return _run_sync(searxng_search(query, max_results, **kwargs))


def search_unified_sync(query: str, max_results: int = 10, **kwargs) -> list[dict]:
    """Synchronous wrapper for search_unified."""
    return _run_sync(search_unified(query, max_results, **kwargs))


def search_batch_sync(queries: list[str], **kwargs) -> dict[str, list[dict]]:
    """Synchronous wrapper for search_batch."""
    return _run_sync(search_batch(queries, **kwargs))
