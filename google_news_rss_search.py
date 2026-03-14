"""
google_news_rss_search.py — Replaces Gemini grounded search with
Google News RSS feed polling.

Each compound query from compound_queries_final.json is converted
to a concise Google News RSS URL.  feedparser reads the feed and
returns articles that flow through the existing 3-layer filter
from article_filter.py.

Cost: $0.  Google News RSS is free and unlimited.
"""

import asyncio
import aiohttp
import feedparser
import json
import logging
import urllib.parse
from datetime import datetime

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"

# Sector keyword mapping (concise terms for RSS queries)
SECTOR_KEYWORDS = {
    "oil_gas": "oil gas LNG pipeline",
    "mining": "mining mine mineral",
    "infrastructure": "infrastructure transit highway bridge",
    "power_energy": "power energy solar wind hydro nuclear",
    "manufacturing": "manufacturing factory plant",
    "transport_logistics": "port airport rail terminal",
    "healthcare": "hospital healthcare medical centre",
    "education": "university school campus college",
    "residential": "housing residential condo tower",
    "commercial_mixed": "development mixed-use redevelopment commercial",
    "agriculture": "agriculture greenhouse food processing",
    "forestry": "forestry sawmill pulp mill lumber",
    "defence": "military defence naval shipyard",
    "telecom": "data centre broadband fibre 5G",
    "indigenous": "Indigenous First Nations infrastructure",
    "environment": "remediation cleanup waste recycling",
    "tourism_culture": "museum arena recreation cultural centre",
    "government": "government building courthouse civic",
}

PROV_NAMES = {
    "ON": "Ontario", "QC": "Québec", "AB": "Alberta",
    "BC": "British Columbia", "SK": "Saskatchewan", "MB": "Manitoba",
    "NS": "Nova Scotia", "NB": "New Brunswick",
    "NL": "Newfoundland", "PE": "PEI",
    "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut",
    # Full names map to themselves
    "Ontario": "Ontario", "Quebec": "Quebec", "Québec": "Québec",
    "Alberta": "Alberta", "British Columbia": "British Columbia",
    "Saskatchewan": "Saskatchewan", "Manitoba": "Manitoba",
    "Nova Scotia": "Nova Scotia", "New Brunswick": "New Brunswick",
    "Newfoundland and Labrador": "Newfoundland",
    "Prince Edward Island": "PEI",
    "Yukon": "Yukon", "Northwest Territories": "Northwest Territories",
    "Nunavut": "Nunavut",
}


def build_google_news_url(query_text, language="en"):
    """Convert a search query to a Google News RSS URL."""
    params = {
        "q": query_text,
        "hl": "fr-CA" if language == "fr" else "en-CA",
        "gl": "CA",
        "ceid": "CA:fr" if language == "fr" else "CA:en",
    }
    return f"{GOOGLE_NEWS_RSS_BASE}?{urllib.parse.urlencode(params)}"


def load_compound_queries(json_path="compound_queries_final.json"):
    """Load compound queries from JSON file."""
    with open(json_path, "r") as f:
        data = json.load(f)
    return data.get("queries", data) if isinstance(data, dict) else data


def _shorten_query(query_text, query_meta):
    """Shorten a verbose Gemini query to concise Google News RSS keywords.

    Gemini: "Find all major mining projects in Saskatchewan..."
    RSS:    "mining mine mineral project Saskatchewan 2026"
    """
    province = query_meta.get("province", "")
    sector = query_meta.get("sector", "")
    language = query_meta.get("language", "en")
    geo_tier = query_meta.get("geo_tier", "")

    sector_kw = SECTOR_KEYWORDS.get(sector, sector.replace("_", " "))
    geo_name = PROV_NAMES.get(province, province)

    # CMA queries use the CMA name directly
    if geo_tier == "cma":
        geo_name = query_meta.get("cma", geo_name)

    year = datetime.now().year

    if language == "fr":
        return f"projet {sector_kw} {geo_name} {year}"
    else:
        return f"{sector_kw} project {geo_name} {year}"


def convert_queries_to_rss_urls(queries):
    """Convert all compound queries to Google News RSS URLs.

    Deduplicates by final RSS URL — many compound queries collapse to the
    same shortened form after _shorten_query().
    """
    rss_feeds = []
    seen_urls = set()
    total = len(queries)

    for q in queries:
        query_text = q.get("query", "")
        language = q.get("language", "en")
        short_query = _shorten_query(query_text, q)
        url = build_google_news_url(short_query, language)

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
            "type": "google_news_rss",
        })

    logger.info(f"{total} queries → {len(rss_feeds)} unique RSS URLs after dedup")
    return rss_feeds


async def fetch_rss_feed(session, feed, semaphore):
    """Fetch a single Google News RSS feed. Returns list of article dicts."""
    async with semaphore:
        try:
            async with session.get(
                feed["url"],
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    parsed = feedparser.parse(text)

                    articles = []
                    for entry in parsed.entries[:15]:
                        articles.append({
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                            "url": entry.get("link", ""),
                            "published": entry.get("published", ""),
                            "source": entry.get("source", {}).get(
                                "title", ""
                            ),
                            "summary": entry.get("summary", ""),
                            # Metadata for downstream processing
                            "_province": feed.get("province"),
                            "_sector": feed.get("sector"),
                            "_language": feed.get("language"),
                            "_discovery_tier": "google_news_rss",
                            "_query": feed.get("short_query"),
                        })
                    return articles
                else:
                    logger.warning(
                        f"RSS fetch {resp.status}: {feed['short_query']}"
                    )
                    return []
        except Exception as e:
            logger.warning(
                f"RSS fetch error: {feed['short_query']}: {e}"
            )
            return []


async def run_google_news_discovery(json_path="compound_queries_final.json"):
    """Run all compound queries via Google News RSS.

    Returns deduplicated list of article dicts.
    """
    queries = load_compound_queries(json_path)
    rss_feeds = convert_queries_to_rss_urls(queries)

    logger.info(f"Google News RSS discovery: {len(queries)} queries → {len(rss_feeds)} unique feeds")
    print(f"  [GOOGLE-NEWS] {len(queries)} queries → {len(rss_feeds)} unique RSS feeds")

    semaphore = asyncio.Semaphore(30)
    all_articles = []

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_rss_feed(session, feed, semaphore)
            for feed in rss_feeds
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)

    # Dedup by URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        url = article.get("link", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)

    print(
        f"  [GOOGLE-NEWS] {len(all_articles)} total → "
        f"{len(unique_articles)} unique articles"
    )
    return unique_articles


def run_google_news_search(gemini_client=None):
    """Synchronous wrapper matching run_compound_search() interface.

    1. Fetches Google News RSS for all compound queries (deduped by URL)
    2. Passes results through the 3-layer article filter
    3. Returns filtered articles ready for Tavily text extraction +
       Flash project extraction

    Args:
        gemini_client: Gemini client for Layer 3 prescreen (optional)

    Returns:
        list of article dicts that passed the filter
    """
    from article_filter import filter_articles

    # Fetch RSS feeds
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            articles = loop.run_until_complete(
                run_google_news_discovery()
            )
        else:
            articles = asyncio.run(run_google_news_discovery())
    except RuntimeError:
        articles = asyncio.run(run_google_news_discovery())

    if not articles:
        print("  [GOOGLE-NEWS] No articles found")
        return []

    # Run through 3-layer filter
    filtered = filter_articles(
        articles,
        gemini_client=gemini_client,
        skip_layer1=False,
        skip_layer2=False,
    )

    print(
        f"  [GOOGLE-NEWS] {len(articles)} articles → "
        f"{len(filtered)} passed filter"
    )

    # Tag discovery source
    for art in filtered:
        art["_discovery_tier"] = "google_news_rss"
        art["discovery_source"] = "google_news_rss"

    # Record documents for fetch tracking
    try:
        from db import get_db, insert_document
        conn = get_db()
        for art in filtered:
            insert_document(conn, art.get('url') or art.get('link', ''),
                            title=art.get('title', ''),
                            source_tier='tier_2', source_type='google_news',
                            published_date=art.get('published', ''))
        conn.close()
    except Exception:
        pass

    return filtered
