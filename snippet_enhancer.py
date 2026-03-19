"""
Snippet enhancer using trafilatura article extraction + sumy summarization.
For RSS articles with missing or truncated descriptions, fetches the full page
and extracts the 2-3 most representative sentences. Zero API cost, no LLM needed.

Primary extractor: trafilatura (purpose-built for news article text extraction).
Fallback extractor: BeautifulSoup paragraph extraction (if trafilatura unavailable).

Used as a pre-step before RSS filtering — gives L4 and L6 more text to work with.
Falls back gracefully: if fetch fails or sumy fails, returns the original snippet.
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


def _fetch_article_text_trafilatura(url, timeout=FETCH_TIMEOUT):
    """Fetch article text using trafilatura (purpose-built for news extraction).

    Returns the extracted article body text, or empty string on failure.
    trafilatura handles: varied HTML layouts, boilerplate removal, paywall stubs,
    navigation/sidebar/comment stripping, and multi-page articles.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, favor_recall=True,
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


def _fetch_article_text(url, timeout=FETCH_TIMEOUT):
    """Fetch article text — trafilatura primary, BS4 fallback."""
    if _HAS_TRAFILATURA:
        text = _fetch_article_text_trafilatura(url, timeout=timeout)
        if text and len(text) >= 100:
            return text
        # trafilatura returned nothing useful — fall through to BS4

    return _fetch_article_text_bs4(url, timeout=timeout)


def enhance_snippet(url, existing_snippet="", timeout=FETCH_TIMEOUT):
    """
    If existing_snippet is too short, fetch the article page and extract
    key sentences via LexRank. Returns the enhanced snippet or the original
    if enhancement fails.

    Args:
        url: Article URL to fetch
        existing_snippet: Current snippet/description (may be empty or truncated)
        timeout: HTTP fetch timeout in seconds

    Returns:
        str: Enhanced snippet (2-3 sentences) or original snippet on failure
    """
    # Don't enhance if we already have a decent snippet
    if existing_snippet and len(existing_snippet) >= MIN_SNIPPET_LENGTH:
        return existing_snippet

    try:
        text = _fetch_article_text(url, timeout=timeout)
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
                  max_enhance=50, skip_gov=True):
    """
    Enhance snippets for a batch of articles. Only processes articles with
    short or missing snippets, up to max_enhance to avoid stalling the pipeline.

    Args:
        articles: List of article dicts
        url_key: Key for the URL field in each dict
        snippet_key: Key for the snippet/description field
        max_enhance: Maximum number of articles to enhance per batch
        skip_gov: If True, skip government-sourced articles (they bypass filters anyway)

    Returns:
        List of articles with enhanced snippets (modifies in place and returns)
    """
    enhanced_count = 0
    skipped_count = 0
    extractor = "trafilatura" if _HAS_TRAFILATURA else "bs4"

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

        result = enhance_snippet(url, snippet)
        if result != snippet:
            article[snippet_key] = result
            enhanced_count += 1

    if enhanced_count > 0:
        print(f"[SNIPPET] Enhanced {enhanced_count} articles ({extractor}), "
              f"skipped {skipped_count} (already had snippets or gov)")

    return articles
