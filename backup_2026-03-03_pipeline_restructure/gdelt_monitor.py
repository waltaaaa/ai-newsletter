"""
gdelt_monitor.py — GDELT DOC 2.0 API news discovery for CAN-MACRO pipeline.

Uses the free gdeltdoc package (no API key required) to search for Canadian
news articles from the last 7 days. Returns article metadata for Tavily extraction.

Searches:
  - Project/infrastructure discovery (10 topic + 13 provincial = 23 searches)
  - National/global economy context (8 searches)
  Total: ~37 searches × 50 articles each = up to 1,850 raw results
  After deduplication: ~300-600 unique URLs

Note on User-Agent:
  The default gdeltdoc UA ("GDELT DOC Python API client ...") is throttled/blocked
  by the GDELT API on some networks. We subclass GdeltDoc to inject a browser-like
  UA and explicit timeouts (connect=15s, read=60s). The API can take 15-20s per
  request; do not use a read timeout shorter than 30s.

Usage:
    from gdelt_monitor import fetch_gdelt_articles
    articles = fetch_gdelt_articles(days_back=7)
    # articles: list of {url, title, domain, seendate, sourcecountry, topic}
"""

import sys
import time
import requests
from datetime import datetime, timedelta, timezone

try:
    from gdeltdoc import GdeltDoc, Filters
    from gdeltdoc.helpers import load_json
    from gdeltdoc.errors import raise_response_error
    _HAS_GDELT = True
except ImportError:
    _HAS_GDELT = False

# ---------------------------------------------------------------------------
# Browser-like User-Agent to avoid GDELT API throttling
# ---------------------------------------------------------------------------
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/1.0"
_GDELT_TIMEOUT = (15, 60)   # (connect_s, read_s)
_BAIL_THRESHOLD = 3         # consecutive failures before declaring API unreachable

# GDELT API base URL — use HTTP because port 443 (HTTPS) can be TCP-blocked by ISPs
# while port 80 (HTTP) remains accessible. The API supports both protocols.
_GDELT_BASE = "http://api.gdeltproject.org/api/v2/doc/doc"


# ---------------------------------------------------------------------------
# Patched GdeltDoc subclass
# ---------------------------------------------------------------------------
class _GdeltDocPatched(GdeltDoc):
    """GdeltDoc with browser UA and explicit request timeouts."""

    def _query(self, mode: str, query_string: str) -> dict:
        if mode not in [
            "artlist", "timelinevol", "timelinevolraw",
            "timelinetone", "timelinelang", "timelinesourcecountry",
        ]:
            raise ValueError(f"Mode {mode} not in supported API modes")

        response = requests.get(
            f"{_GDELT_BASE}?query={query_string}&mode={mode}&format=json",
            headers={"User-Agent": _UA},
            timeout=_GDELT_TIMEOUT,
        )
        raise_response_error(response=response)
        if "text/html" in response.headers.get("content-type", ""):
            raise ValueError(
                f"GDELT returned HTML (invalid query): {response.text[:200]}"
            )
        return load_json(response.content, self.max_depth_json_parsing)


# ---------------------------------------------------------------------------
# Canadian domain priority list — prefer these sources in ranking
# ---------------------------------------------------------------------------
_CA_DOMAINS = frozenset({
    'globeandmail.com', 'theglobeandmail.com', 'nationalpost.com',
    'financialpost.com', 'cbc.ca', 'thestar.com', 'torontostar.com',
    'calgaryherald.com', 'vancouversun.com', 'montrealgazette.com',
    'ottawacitizen.com', 'edmontonjournal.com', 'ledevoir.com',
    'lapresse.ca', 'biv.com', 'ctvnews.ca', 'business.financialpost.com',
    'therecord.com', 'theconversation.com', 'ipolitics.ca',
    'constructioncanada.net', 'dailycommercialnews.com',
    'mining.com', 'miningweekly.com', 'northernminer.com',
    'oilandgas360.com', 'rigzone.com', 'energynow.ca',
    'rcinet.ca', 'macleans.ca', 'canadianbusiness.com',
})

# ---------------------------------------------------------------------------
# Search configurations
# ---------------------------------------------------------------------------
_PROJECT_SEARCHES = [
    ("infrastructure project Canada",        "project"),
    ("construction project billion Canada",  "project"),
    ("mine development Canada",              "project"),
    ("pipeline project Canada",              "project"),
    ("energy project approved Canada",       "project"),
    ("transit project Canada",               "project"),
    ("housing development Canada",           "project"),
    ("military base Canada",                 "project"),
    ("carbon capture Canada",                "project"),
    ("data centre investment Canada",        "project"),
]

_PROVINCE_PROJECT_SEARCHES = [
    ("Ontario major project",               "project"),
    ("Quebec major project",                "project"),
    ("Alberta major project",               "project"),
    ("British Columbia major project",      "project"),
    ("Saskatchewan major project",          "project"),
    ("Manitoba major project",              "project"),
    ("Nova Scotia major project",           "project"),
    ("New Brunswick major project",         "project"),
    ("Newfoundland Labrador major project", "project"),
    ("Prince Edward Island major project",  "project"),
    ("Yukon major project",                 "project"),
    ("Northwest Territories project",       "project"),
    ("Nunavut project",                     "project"),
]

_ECONOMY_SEARCHES = [
    ("Canada economy",                      "economy"),
    ("Bank of Canada interest rate",        "economy"),
    ("Canada trade tariffs",                "economy"),
    ("US economy Canada impact",            "economy"),
    ("China Canada trade",                  "economy"),
    ("EU Canada trade",                     "economy"),
    ("Canada inflation CPI",                "economy"),
    ("Canada unemployment jobs",            "economy"),
]

_PROVINCE_ECONOMY_SEARCHES = [
    ("Ontario economy",                     "economy"),
    ("Quebec economy",                      "economy"),
    ("Alberta economy",                     "economy"),
    ("British Columbia economy",            "economy"),
    ("Saskatchewan economy",                "economy"),
    ("Manitoba economy",                    "economy"),
]


# ---------------------------------------------------------------------------
# Core search function
# ---------------------------------------------------------------------------

_NETWORK_ERROR = object()  # sentinel: network failure (not just empty results)


def _gdelt_search(keyword: str, topic: str, days_back: int, max_records: int = 50):
    """
    Run a single GDELT DOC 2.0 article search.

    Returns:
        list[dict]  — articles found (may be empty if query has no matches)
        _NETWORK_ERROR sentinel — on connection/timeout failure (triggers bail-out)
    """
    if not _HAS_GDELT:
        return []

    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    try:
        gd = _GdeltDocPatched()
        # Omit country= filter — it is too restrictive and returns empty results
        # for multi-word phrase queries. The keyword already contains "Canada".
        f  = Filters(
            keyword=keyword,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            num_records=max_records,
        )
        df = gd.article_search(f)
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            url = str(row.get('url') or row.get('url_mobile') or '')
            if not url or not url.startswith('http'):
                continue
            results.append({
                'url':           url,
                'title':         str(row.get('title') or ''),
                'domain':        str(row.get('domain') or ''),
                'seendate':      str(row.get('seendate') or ''),
                'sourcecountry': str(row.get('sourcecountry') or ''),
                'topic':         topic,
                'keyword':       keyword,
            })
        return results

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        print(f"  [GDELT] Search '{keyword[:40]}' network error: {type(e).__name__}",
              file=sys.stderr)
        return _NETWORK_ERROR
    except Exception as e:
        print(f"  [GDELT] Search '{keyword[:40]}' failed: {e}", file=sys.stderr)
        return _NETWORK_ERROR


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_gdelt_articles(days_back: int = 7, include_economy: bool = True) -> list[dict]:
    """
    Run all GDELT searches and return deduplicated article list.

    Args:
        days_back:       Days of history to search (7 for weekly, 30 for deep sweep).
        include_economy: If True, include general economic context searches.

    Returns:
        Deduplicated list of article dicts, sorted by Canadian domain first.
        Each dict: {url, title, domain, seendate, sourcecountry, topic, keyword}
    """
    if not _HAS_GDELT:
        print("  [GDELT] gdeltdoc package not available — skipping GDELT searches.")
        return []

    all_searches = list(_PROJECT_SEARCHES) + list(_PROVINCE_PROJECT_SEARCHES)
    if include_economy:
        all_searches += list(_ECONOMY_SEARCHES) + list(_PROVINCE_ECONOMY_SEARCHES)

    print(f"  [GDELT] Running {len(all_searches)} searches (last {days_back}d)...")

    raw_articles: list[dict] = []
    consecutive_errors = 0  # network errors only; empty results don't count

    for i, (keyword, topic) in enumerate(all_searches):
        result = _gdelt_search(keyword, topic, days_back)
        if result is _NETWORK_ERROR:
            consecutive_errors += 1
            # Bail out early if the API is consistently unreachable
            if i < _BAIL_THRESHOLD and consecutive_errors >= _BAIL_THRESHOLD:
                print("  [GDELT] API unreachable — skipping remaining searches.",
                      file=sys.stderr)
                break
        else:
            consecutive_errors = 0
            raw_articles.extend(result)
        # Be gentle with the free GDELT API
        if i < len(all_searches) - 1:
            time.sleep(0.5)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for art in raw_articles:
        url = art['url']
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append(art)

    # Sort: Canadian domains first, then by date (newest first)
    def _sort_key(art):
        is_ca = any(dom in art['domain'] for dom in _CA_DOMAINS)
        return (0 if is_ca else 1, art.get('seendate', ''))

    unique.sort(key=_sort_key)

    n_project = sum(1 for a in unique if a['topic'] == 'project')
    n_economy = sum(1 for a in unique if a['topic'] == 'economy')
    n_ca      = sum(1 for a in unique if any(dom in a['domain'] for dom in _CA_DOMAINS))
    print(f"  [GDELT] {len(unique)} unique articles "
          f"(project={n_project}, economy={n_economy}, Canadian={n_ca})")

    return unique


def top_articles(
    articles: list[dict],
    max_total: int = 100,
    topic_filter: str | None = None,
) -> list[dict]:
    """
    Return the top N most relevant articles for Tavily extraction.
    Prioritises Canadian domains and project-related articles.
    """
    filtered = articles
    if topic_filter:
        filtered = [a for a in articles if a['topic'] == topic_filter]

    ca  = [a for a in filtered if any(dom in a['domain'] for dom in _CA_DOMAINS)]
    non = [a for a in filtered if a not in ca]
    return (ca + non)[:max_total]
