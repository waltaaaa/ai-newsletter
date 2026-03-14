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


async def is_rehash(session, semaphore, article_text, existing_project_summary):
    """Use Gemini Flash to determine if article adds new information vs existing project.

    Free (Flash) — reduces unnecessary Sonnet extraction calls.

    Args:
        session: aiohttp.ClientSession
        semaphore: asyncio.Semaphore
        article_text: article title + text (truncated to 2000 chars)
        existing_project_summary: 200-word summary of the most similar existing project

    Returns:
        bool: True if article is a rehash (no new info), False if it has new info
    """
    prompt = (
        "Compare this article to an existing project summary.\n"
        "Does the article contain ANY new information not in the summary?\n"
        "New information includes: updated cost, new timeline, status change, "
        "new partners, new approvals, new opposition, regulatory updates.\n\n"
        f"Existing project summary:\n{existing_project_summary[:1000]}\n\n"
        f"Article:\n{article_text[:2000]}\n\n"
        'Respond with ONLY "NEW" or "REHASH".'
    )

    query_obj = {"query": prompt}
    result = await query_one(session, semaphore, query_obj,
                             "You classify whether articles contain new project information.",
                             attempt=0)
    text = (result.get("text") or "").strip().upper()
    return text == "REHASH"


async def filter_rehashes(articles, existing_projects, max_concurrent=10):
    """Filter out articles that are rehashes of known projects.

    Args:
        articles: list of article dicts (url, title, text/summary)
        existing_projects: list of project dicts (name, description, province, value)

    Returns:
        list of articles that contain genuinely new information
    """
    if not GEMINI_API_KEY or not articles or not existing_projects:
        return articles

    from difflib import SequenceMatcher

    # Build project summaries for matching
    project_summaries = {}
    for p in existing_projects:
        name = (p.get('name') or '').lower()
        summary = (
            f"Project: {p.get('name', '')}\n"
            f"Province: {p.get('province', '')}\n"
            f"Value: {p.get('value', 'Not disclosed')}\n"
            f"Status: {p.get('status', '')}\n"
            f"Proponent: {p.get('proponent', '')}\n"
            f"Description: {p.get('description', '')}"
        )
        project_summaries[name] = summary

    project_names = list(project_summaries.keys())
    semaphore = asyncio.Semaphore(max_concurrent)
    kept = []

    async with aiohttp.ClientSession() as session:
        for article in articles:
            title = (article.get('title') or '').lower()
            text = article.get('text') or article.get('summary') or ''
            combined = title + ' ' + text[:500]

            # Find most similar existing project by name
            best_match = None
            best_ratio = 0
            for pname in project_names:
                # Check if project name appears in article
                if pname and len(pname) > 5 and pname in combined.lower():
                    best_match = pname
                    best_ratio = 1.0
                    break
                ratio = SequenceMatcher(None, pname, title).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = pname

            # Only check rehash if there's a reasonable match
            if best_ratio < 0.4 or not best_match:
                kept.append(article)
                continue

            article_text = f"{article.get('title', '')}\n{text}"
            try:
                rehash = await is_rehash(session, semaphore, article_text,
                                         project_summaries[best_match])
                if not rehash:
                    kept.append(article)
                else:
                    logger.debug(f"Rehash filtered: {article.get('title', '')[:60]}")
            except Exception:
                kept.append(article)  # on error, keep the article

    filtered = len(articles) - len(kept)
    if filtered:
        print(f"  [REHASH] Filtered {filtered}/{len(articles)} rehash articles")
    return kept


def filter_rehashes_sync(articles, existing_projects, max_concurrent=10):
    """Synchronous wrapper for filter_rehashes."""
    if not articles:
        return articles
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                filter_rehashes(articles, existing_projects, max_concurrent)
            )
        else:
            return asyncio.run(
                filter_rehashes(articles, existing_projects, max_concurrent)
            )
    except RuntimeError:
        return asyncio.run(
            filter_rehashes(articles, existing_projects, max_concurrent)
        )


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
