"""
bing_news_rss_search.py — Bing News RSS feed polling.

Mirrors google_news_rss_search.py: takes the same compound + NAICS query set,
issues per-query RSS pulls against Bing's news search RSS endpoint, and returns
articles in the same dict shape so the existing 3-layer article filter in
article_filter.py can consume them transparently.

Why a second source: Google News RSS aggressively rate-limits programmatic
access (12-24h soft IP bans after bursty pulls). Running Bing in parallel keeps
discovery alive when Google is banning, and otherwise broadens coverage —
Bing surfaces Canadian outlets (Canadian Mining Journal, BNN Bloomberg, MSN,
Globe & Mail) that don't always appear in Google News results.

Cost: $0. Bing News RSS is free, no API key.
"""

import asyncio
import logging
import os
import urllib.parse
from datetime import datetime

import aiohttp
import feedparser

# Reuse query loaders + shorteners from the Google module so both sources stay
# in lockstep on what they're searching for. Each module owns its own circuit
# breaker (per-IP-per-endpoint state).
from google_news_rss_search import (
    load_compound_queries,
    _load_naics_queries,
    _shorten_query,
    _BROWSER_HEADERS,
    _Circuit,
)

logger = logging.getLogger(__name__)

BING_NEWS_RSS_BASE = "https://www.bing.com/news/search"

_CIRCUIT = _Circuit(threshold=20)


def build_bing_news_url(query_text, language="en"):
    """Convert a search query into a Bing News RSS URL (Canada-localized)."""
    params = {
        "q": query_text,
        "format": "rss",
        "setlang": "fr-CA" if language == "fr" else "en-CA",
        "cc": "CA",
    }
    return f"{BING_NEWS_RSS_BASE}?{urllib.parse.urlencode(params)}"


def convert_queries_to_rss_urls(queries):
    """Convert compound/NAICS queries into Bing RSS URLs, deduped by final URL."""
    rss_feeds = []
    seen_urls = set()
    for q in queries:
        query_text = q.get("query", "")
        language = q.get("language", "en")
        short_query = _shorten_query(query_text, q)
        url = build_bing_news_url(short_query, language)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        rss_feeds.append({
            "url": url,
            "short_query": short_query,
            "original_query": query_text,
            "province": q.get("province"),
            "sector": q.get("sector"),
            "language": language,
            "geo_tier": q.get("geo_tier"),
            "type": "bing_news_rss",
        })
    logger.info(f"{len(queries)} queries → {len(rss_feeds)} unique Bing RSS URLs after dedup")
    return rss_feeds


async def fetch_rss_feed(session, feed, semaphore, circuit=None):
    """Fetch one Bing News RSS feed. Returns list of article dicts."""
    cb = circuit or _CIRCUIT
    if cb.tripped:
        await cb.warn_once(label="Bing News RSS")
        return []
    async with semaphore:
        if cb.tripped:
            await cb.warn_once(label="Bing News RSS")
            return []
        try:
            async with session.get(
                feed["url"],
                headers=_BROWSER_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    await cb.record_ok()
                    text = await resp.text()
                    parsed = feedparser.parse(text)

                    articles = []
                    for entry in parsed.entries[:15]:
                        # Bing wraps the real article URL inside its
                        # bing.com/news/apiclick.aspx redirector. The redirector
                        # URL is unique per query/session, so dedup downstream
                        # has to be tolerant; we keep the redirector here so
                        # the click telemetry the publisher sees stays clean.
                        articles.append({
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                            "url": entry.get("link", ""),
                            "published": entry.get("published", ""),
                            "source": (entry.get("source", {}) or {}).get("title", ""),
                            "summary": entry.get("summary", ""),
                            "_province": feed.get("province"),
                            "_sector": feed.get("sector"),
                            "_language": feed.get("language"),
                            "_discovery_tier": "bing_news_rss",
                            "_query": feed.get("short_query"),
                        })
                    return articles
                else:
                    if resp.status in (429, 503):
                        await cb.record_503()
                    logger.warning(f"Bing RSS fetch {resp.status}: {feed['short_query']}")
                    return []
        except Exception as e:
            logger.warning(f"Bing RSS fetch error: {feed['short_query']}: {e}")
            return []


async def run_bing_news_discovery(json_path=None):
    """Run all compound + NAICS queries via Bing News RSS.

    Mirrors run_google_news_discovery():
      Pass 1: Compound queries
      Pass 2: NAICS expansion (skip URLs already seen in compound pass)

    Returns deduplicated list of article dicts.
    """
    queries = load_compound_queries(json_path) if json_path else load_compound_queries()

    naics_queries = []
    try:
        naics_queries = _load_naics_queries()
        if naics_queries:
            logger.info(f"Loaded {len(naics_queries)} NAICS expansion queries (Bing)")
    except Exception as e:
        logger.warning(f"NAICS query expansion failed (non-fatal): {e}")

    compound_feeds = convert_queries_to_rss_urls(queries)
    print(f"  [BING-NEWS] Pass 1: {len(queries)} compound queries → {len(compound_feeds)} unique feeds")

    # Concurrency intentionally low — same reasoning as Google. Bing is more
    # tolerant in practice but the circuit breaker means we want fewer in-flight
    # so the breaker can trip *fast* if a soft-ban kicks in.
    p1_concurrency = int(os.environ.get('BING_NEWS_CONCURRENCY', '3'))
    semaphore_p1 = asyncio.Semaphore(p1_concurrency)
    all_articles = []
    seen_urls = set()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_rss_feed(session, feed, semaphore_p1) for feed in compound_feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            for article in result:
                url = article.get("link", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(article)

    p1_count = len(all_articles)
    print(f"  [BING-NEWS] Pass 1: {p1_count} unique articles")

    if naics_queries:
        naics_feeds = convert_queries_to_rss_urls(naics_queries)
        compound_urls = {f["url"] for f in compound_feeds}
        naics_feeds = [f for f in naics_feeds if f["url"] not in compound_urls]

        if naics_feeds:
            print(f"  [BING-NEWS] Pass 2: {len(naics_feeds)} new NAICS feeds (after compound dedup)")
            semaphore_p2 = asyncio.Semaphore(p1_concurrency)
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_rss_feed(session, feed, semaphore_p2) for feed in naics_feeds]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            naics_new = 0
            for result in results:
                if isinstance(result, list):
                    for article in result:
                        url = article.get("link", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_articles.append(article)
                            naics_new += 1

            print(f"  [BING-NEWS] Pass 2: {naics_new} new articles from NAICS expansion")

    total_feeds = len(compound_feeds) + (len(naics_feeds) if naics_queries else 0)
    print(f"  [BING-NEWS] Total: {total_feeds} feeds → {len(all_articles)} unique articles")
    return all_articles


def run_bing_news_search():
    """Synchronous wrapper. Returns list of article dicts ready for the
    standard 3-layer article filter (same shape as Google News output)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(run_bing_news_discovery())
        return asyncio.run(run_bing_news_discovery())
    except RuntimeError:
        return asyncio.run(run_bing_news_discovery())
