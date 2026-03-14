"""
Snippet enhancer using sumy extractive summarization.
For RSS articles with missing or truncated descriptions, fetches the full page
and extracts the 2-3 most representative sentences. Zero API cost, no LLM needed.

Used as a pre-step before RSS filtering — gives L4 and L6 more text to work with.
Falls back gracefully: if fetch fails or sumy fails, returns the original snippet.
"""
import requests
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import logging

logger = logging.getLogger(__name__)

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


def _fetch_article_text(url, timeout=FETCH_TIMEOUT):
    """Fetch a URL and extract the main text content via BeautifulSoup."""
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
        print(f"[SNIPPET] Enhanced {enhanced_count} articles, "
              f"skipped {skipped_count} (already had snippets or gov)")

    return articles
