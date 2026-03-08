"""
gemini_engine.py -- Shared async Gemini grounded search infrastructure.

Eliminates duplication across compound_discovery.py, cost_finder.py,
lifecycle_monitor.py, deep_verification.py, named_tracker.py, and
capacity_queries.py.

All modules import from here instead of maintaining their own copies
of the aiohttp POST / retry / grounding extraction logic.
"""

import asyncio
import aiohttp
import os
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
MAX_CONCURRENT = 15
RETRY_DELAY = 60
MAX_RETRY = 3


async def query_one(session, semaphore, query_obj, system_prompt, attempt=0):
    """Send one query to Gemini grounded search.

    Args:
        session: aiohttp.ClientSession
        semaphore: asyncio.Semaphore for concurrency control
        query_obj: dict with at least a "query" key; all other keys pass through
        system_prompt: system instruction text for Gemini
        attempt: retry counter (internal)

    Returns:
        dict with keys:
          text: str — raw text from Gemini response
          grounding_urls: list[dict] — [{url, title}] from groundingMetadata
          query: dict — the original query_obj (pass-through)
          error: str|None — error message if failed
    """
    async with semaphore:
        payload = {
            "contents": [{"parts": [{"text": query_obj["query"]}]}],
            # Grounding disabled — Google Search costs $35/1000 queries
            "generationConfig": {"temperature": 0.1},
            "systemInstruction": {"parts": [{"text": system_prompt}]},
        }
        url = f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}"

        try:
            async with session.post(
                url, json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return _parse_raw(data, query_obj)
                elif resp.status == 429 and attempt < MAX_RETRY:
                    logger.warning(
                        f"Rate limited, waiting {RETRY_DELAY}s "
                        f"(attempt {attempt + 1})"
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    return await query_one(
                        session, semaphore, query_obj,
                        system_prompt, attempt + 1
                    )
                else:
                    text = await resp.text()
                    return {
                        "text": "",
                        "grounding_urls": [],
                        "query": query_obj,
                        "error": f"Gemini {resp.status}: {text[:300]}",
                    }
        except asyncio.TimeoutError:
            return {
                "text": "",
                "grounding_urls": [],
                "query": query_obj,
                "error": "Timeout after 120s",
            }
        except Exception as e:
            return {
                "text": "",
                "grounding_urls": [],
                "query": query_obj,
                "error": str(e),
            }


def _parse_raw(api_response, query_obj):
    """Extract text and grounding URLs from raw Gemini API response."""
    candidates = api_response.get("candidates", [])
    if not candidates:
        return {
            "text": "",
            "grounding_urls": [],
            "query": query_obj,
            "error": None,
        }

    parts = candidates[0].get("content", {}).get("parts", [])
    text = " ".join(p.get("text", "") for p in parts).strip()

    grounding = candidates[0].get("groundingMetadata", {})
    grounding_urls = []
    for chunk in grounding.get("groundingChunks", []):
        web = chunk.get("web", {})
        if web.get("uri"):
            grounding_urls.append({
                "url": web["uri"],
                "title": web.get("title", ""),
            })

    return {
        "text": text,
        "grounding_urls": grounding_urls,
        "query": query_obj,
        "error": None,
    }


async def run_batch(queries, system_prompt, max_concurrent=MAX_CONCURRENT,
                    tag="BATCH"):
    """Run all queries concurrently with semaphore control.

    Args:
        queries: list of query dicts (each must have "query" key)
        system_prompt: system instruction for all queries
        max_concurrent: max parallel requests
        tag: prefix for log/print messages

    Returns:
        list of result dicts from query_one (same order as queries)
    """
    if not GEMINI_API_KEY:
        print(f"  [{tag}] No GEMINI_API_KEY -- skipping.")
        return []

    if not queries:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)
    print(f"  [{tag}] Running {len(queries)} queries, "
          f"{max_concurrent}x parallelism...")

    async with aiohttp.ClientSession() as session:
        tasks = [
            query_one(session, semaphore, q, system_prompt)
            for q in queries
        ]

        results = []
        # Use gather for parallel execution
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = 0
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                errors += 1
                results.append({
                    "text": "",
                    "grounding_urls": [],
                    "query": queries[i],
                    "error": str(r),
                })
            else:
                if r.get("error"):
                    errors += 1
                results.append(r)

            if (i + 1) % 50 == 0:
                print(f"  [{tag}] {i + 1}/{len(queries)} done")

    print(f"  [{tag}] Complete: {len(queries)} queries "
          f"({errors} errors)")
    return results


def run_batch_sync(queries, system_prompt, max_concurrent=MAX_CONCURRENT,
                   tag="BATCH"):
    """Synchronous wrapper for run_batch.

    Handles running/not-running event loops and nest_asyncio.
    """
    if not queries:
        return []

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                run_batch(queries, system_prompt, max_concurrent, tag)
            )
        else:
            return asyncio.run(
                run_batch(queries, system_prompt, max_concurrent, tag)
            )
    except RuntimeError:
        return asyncio.run(
            run_batch(queries, system_prompt, max_concurrent, tag)
        )
