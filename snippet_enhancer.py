"""
Snippet enhancer using trafilatura article extraction + sumy summarization.
For RSS articles with missing or truncated descriptions, fetches the full page
and extracts the 2-3 most representative sentences. Zero API cost, no LLM needed.

Primary extractor: trafilatura (purpose-built for news article text extraction).
Fallback extractor: BeautifulSoup paragraph extraction (if trafilatura unavailable).

Used as a pre-step before RSS filtering — gives L4 and L6 more text to work with.
Falls back gracefully: if fetch fails or sumy fails, returns the original snippet.

E-7: extracted page text is cached in the SQLite `cache` table (category
'page_text', key = normalized URL, 14-day TTL) when a DB connection is
supplied — a cache hit avoids re-fetching the page. No-op when no conn.
"""
import logging

import requests
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

logger = logging.getLogger(__name__)

# Check trafilatura availability at import time
try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False
    logger.info("[SNIPPET] trafilatura not installed, using BeautifulSoup fallback")

# Minimum snippet length (chars) before we bother enhancing
MIN_SNIPPET_LENGTH = 80
# Number of sentences to extract
SENTENCE_COUNT = 3
# Timeout for fetching article pages
FETCH_TIMEOUT = 8

_summarizer = None

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (CAN-MACRO/1.0; +https://github.com/can-macro)"
}


def _get_summarizer():
    """Lazy-load the summarizer."""
    global _summarizer
    if _summarizer is None:
        _summarizer = LexRankSummarizer()
    return _summarizer


def _page_text_cache_key(url):
    """E-7: stable cache key for a fetched page — normalized URL."""
    try:
        from url_utils import normalize_url
        return normalize_url(url) or url
    except Exception:
        return url


def _get_pipeline_cache(conn):
    """Best-effort PipelineCache over the supplied conn. None when unavailable."""
    if conn is None:
        return None
    try:
        from pipeline_cache import PipelineCache
        return PipelineCache(conn)
    except Exception:
        return None


def _fetch_article_text_trafilatura(url, timeout=FETCH_TIMEOUT):
    """Fetch article text using trafilatura's extractor on requests-fetched HTML.

    trafilatura.fetch_url() does NOT honor any caller timeout (uses its own
    long internal default), which can hang the entire pipeline on a single
    slow URL. We fetch the HTML ourselves with a hard timeout, then hand the
    raw bytes to trafilatura.extract() which is purely parser-side and won't
    block on the network.
    """
    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS)
        resp.raise_for_status()
        text = trafilatura.extract(resp.text, favor_recall=True,
                                   include_comments=False)
        return (text or "").strip()
    except Exception as e:
        logger.debug(f"[SNIPPET] trafilatura extraction failed for {url}: {e}")
        return ""


def _fetch_article_text_bs4(url, timeout=FETCH_TIMEOUT):
    """Fetch a URL and extract the main text content via BeautifulSoup.

    Fallback extractor when trafilatura is unavailable or fails.
    """
    resp = requests.get(url, timeout=timeout, headers=_HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    # Remove script, style, nav, footer elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Try <article> first, fall back to <main>, then <body>
    main = soup.find("article") or soup.find("main") or soup.find("body")
    if main is None:
        return ""

    # Extract paragraph text
    paragraphs = main.find_all("p")
    text = " ".join(p.get_text(strip=True) for p in paragraphs)
    return text.strip()


def _fetch_article_text(url, timeout=FETCH_TIMEOUT, cache=None):
    """Fetch article text — trafilatura primary, BS4 fallback.

    E-7: when a PipelineCache is supplied, extracted text is served from /
    stored to the 'page_text' cache (14-day TTL, key = normalized URL).
    """
    cache_key = None
    if cache is not None:
        cache_key = _page_text_cache_key(url)
        try:
            cached = cache.get(cache_key, "page_text")
        except Exception:
            cached = None
        if isinstance(cached, str) and cached:
            return cached

    if _HAS_TRAFILATURA:
        text = _fetch_article_text_trafilatura(url, timeout=timeout)
        if text and len(text) >= 100:
            if cache is not None:
                try:
                    cache.set(cache_key, text, "page_text")
                except Exception:
                    pass  # caching is best-effort
            return text
        # trafilatura returned nothing useful — fall through to BS4

    text = _fetch_article_text_bs4(url, timeout=timeout)
    if cache is not None and text:
        try:
            cache.set(cache_key, text, "page_text")
        except Exception:
            pass  # caching is best-effort
    return text


def enhance_snippet(url, existing_snippet="", timeout=FETCH_TIMEOUT, cache=None):
    """
    If existing_snippet is too short, fetch the article page and extract
    key sentences via LexRank. Returns the enhanced snippet or the original
    if enhancement fails.

    Args:
        url: Article URL to fetch
        existing_snippet: Current snippet/description (may be empty or truncated)
        timeout: HTTP fetch timeout in seconds
        cache: optional PipelineCache — enables the persistent page-text
            cache (E-7). Degrades gracefully to a direct fetch when absent.

    Returns:
        str: Enhanced snippet (2-3 sentences) or original snippet on failure
    """
    # Don't enhance if we already have a decent snippet
    if existing_snippet and len(existing_snippet) >= MIN_SNIPPET_LENGTH:
        return existing_snippet

    try:
        text = _fetch_article_text(url, timeout=timeout, cache=cache)
        if not text or len(text) < 100:
            return existing_snippet or ""

        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = _get_summarizer()
        sentences = summarizer(parser.document, SENTENCE_COUNT)
        enhanced = " ".join(str(s) for s in sentences).strip()

        if len(enhanced) > len(existing_snippet or ""):
            return enhanced
        return existing_snippet or ""

    except Exception as e:
        logger.debug(f"[SNIPPET] Enhancement failed for {url}: {e}")
        return existing_snippet or ""


def enhance_batch(articles, url_key="url", snippet_key="snippet",
                  max_enhance=50, skip_gov=True, conn=None):
    """
    Enhance snippets for a batch of articles. Only processes articles with
    short or missing snippets, up to max_enhance to avoid stalling the pipeline.

    Args:
        articles: List of article dicts
        url_key: Key for the URL field in each dict
        snippet_key: Key for the snippet/description field
        max_enhance: Maximum number of articles to enhance per batch
        skip_gov: If True, skip government-sourced articles (they bypass filters anyway)
        conn: optional SQLite connection — enables the persistent page-text
            cache (E-7). Callers without a DB connection keep working.

    Returns:
        List of articles with enhanced snippets (modifies in place and returns)
    """
    enhanced_count = 0
    skipped_count = 0
    extractor = "trafilatura" if _HAS_TRAFILATURA else "bs4"
    cache = _get_pipeline_cache(conn)

    for article in articles:
        if enhanced_count >= max_enhance:
            break

        url = article.get(url_key, "")
        snippet = article.get(snippet_key, "") or ""

        if not url:
            continue

        if len(snippet) >= MIN_SNIPPET_LENGTH:
            skipped_count += 1
            continue

        # Skip government sources — they already bypass L1+L2 filters
        if skip_gov:
            source_level = article.get("source_level", "")
            if source_level and source_level not in ("media",):
                skipped_count += 1
                continue

        result = enhance_snippet(url, snippet, cache=cache)
        if result != snippet:
            article[snippet_key] = result
            enhanced_count += 1

    if enhanced_count > 0:
        print(f"[SNIPPET] Enhanced {enhanced_count} articles ({extractor}), "
              f"skipped {skipped_count} (already had snippets or gov)")

    return articles
