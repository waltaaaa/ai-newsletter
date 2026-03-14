"""
url_verifier.py -- Async batch URL verification via HEAD requests.

Run after deduplication and before Firestore write.
Marks each evidence URL as verified/broken without removing the project.
"""

import asyncio
import aiohttp
import logging

from url_utils import normalize_url

logger = logging.getLogger(__name__)

MAX_CONCURRENT_CHECKS = 30
TIMEOUT_SECONDS = 10


async def verify_urls_batch(projects):
    """Verify all evidence URLs across all projects.

    Mutates projects in place -- adds 'url_verified' field to each evidence entry.
    Returns count of verified vs broken URLs.
    """
    # Collect all unique URLs to check
    url_to_projects = {}  # url -> list of (project_index, evidence_index)
    for pi, project in enumerate(projects):
        for ei, ev in enumerate(project.get("evidence", [])):
            url = ev.get("url", "")
            if url and url.startswith("http"):
                url_to_projects.setdefault(url, []).append((pi, ei))

    unique_urls = list(url_to_projects.keys())
    if not unique_urls:
        return {"verified": 0, "broken": 0, "total": 0}

    logger.info(f"Verifying {len(unique_urls)} unique URLs across {len(projects)} projects")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    async with aiohttp.ClientSession() as session:
        tasks = [_check_url(session, semaphore, url) for url in unique_urls]
        checks = await asyncio.gather(*tasks, return_exceptions=True)

    verified = 0
    broken = 0

    for url, check in zip(unique_urls, checks):
        reachable = check if isinstance(check, bool) else False

        # Mark all evidence entries for this URL
        for pi, ei in url_to_projects[url]:
            projects[pi]["evidence"][ei]["url_verified"] = reachable
            projects[pi]["evidence"][ei]["url_checked"] = True

        if reachable:
            verified += 1
        else:
            broken += 1

    logger.info(f"URL verification: {verified} verified, {broken} broken out of {len(unique_urls)}")
    return {"verified": verified, "broken": broken, "total": len(unique_urls)}


async def _check_url(session, semaphore, url):
    """HEAD request to check if URL is reachable."""
    async with semaphore:
        try:
            async with session.head(
                url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/1.0"},
            ) as resp:
                return resp.status < 400
        except Exception:
            # Try GET as fallback (some servers reject HEAD)
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/1.0"},
                ) as resp:
                    return resp.status < 400
            except Exception:
                return False


def verify_urls_sync(projects):
    """Synchronous wrapper for verify_urls_batch."""
    if not projects:
        return {"verified": 0, "broken": 0, "total": 0}

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(verify_urls_batch(projects))
        else:
            return asyncio.run(verify_urls_batch(projects))
    except RuntimeError:
        return asyncio.run(verify_urls_batch(projects))
