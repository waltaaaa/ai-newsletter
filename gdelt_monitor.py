"""
gdelt_monitor.py — GDELT DOC 2.0 API validation layer for CAN-MACRO pipeline (Tier 3).

Demoted from primary discovery to validation + gap-filling.
Gemini grounded search (Tier 2) is now the primary discovery engine.

Reduced query set (~200 queries):
  A  Province catch-all (13 × 5 = 65)
  B  CMA queries (30 × 2 = 60)
  C  Sector queries (20 × 2 = 40)
  D  Top company queries (30)
  E  Publication catch-all (5)
  Total: ~200 queries

After deduplication: ~300-600 unique URLs.
Three-layer filter applied before Tavily extraction.

Usage:
    from gdelt_monitor import fetch_gdelt_articles, filter_gdelt_articles
    articles = fetch_gdelt_articles(days_back=7)
    filtered = filter_gdelt_articles(articles, gemini_client=gc)
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
_BAIL_THRESHOLD = 8         # consecutive failures before declaring API unreachable

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
# Search configurations — REDUCED SET (Tier 3 validation, ~200 queries)
# ---------------------------------------------------------------------------

# Section A: Province catch-all (13 provinces × 5 keywords = 65)
_PROVINCE_NAMES = [
    "Ontario", "Quebec", "Alberta", "British Columbia", "Saskatchewan",
    "Manitoba", "Nova Scotia", "New Brunswick", "Newfoundland Labrador",
    "Prince Edward Island", "Yukon", "Northwest Territories", "Nunavut",
]

_PROV_KEYWORDS = [
    "major project construction billion approved",
    "capital investment facility expansion million",
    "redevelopment revitalization mixed-use project",
    "infrastructure transit bridge highway project",
    "new facility plant mine announced approved",
]

def _build_province_searches() -> list[tuple[str, str]]:
    out = []
    for prov in _PROVINCE_NAMES:
        for kw in _PROV_KEYWORDS:
            out.append((f"{prov} {kw}", "project"))
    return out

# Section B: CMA queries (30 CMAs × 2 keywords = 60)
_CMA_NAMES = [
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
    "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Kitchener Waterloo",
    "London Ontario", "Halifax", "Victoria BC", "Windsor Ontario", "Oshawa",
    "Saskatoon", "Regina", "St Catharines Niagara", "Barrie Ontario", "Kelowna",
    "Abbotsford", "Sherbrooke", "Guelph", "Moncton", "Saint John NB",
    "St Johns NL", "Fredericton", "Saguenay", "Trois-Rivieres", "Brantford",
]

_CMA_KEYWORDS = [
    "major development project construction",
    "redevelopment expansion approved million",
]

def _build_cma_searches() -> list[tuple[str, str]]:
    out = []
    for cma in _CMA_NAMES:
        for kw in _CMA_KEYWORDS:
            out.append((f"{cma} {kw}", "project"))
    return out

# Section C: Sector queries (20 sectors × 2 = 40)
_SECTOR_QUERIES = [
    "Agriculture forestry", "Mining oil gas", "Utilities power", "Construction",
    "Manufacturing plant", "Wholesale trade", "Retail trade", "Transportation warehousing",
    "Information technology", "Finance insurance", "Real estate", "Professional services",
    "Management companies", "Waste management", "Education university",
    "Healthcare hospital", "Arts entertainment", "Accommodation food", "Other services",
    "Public administration government",
]

_SECTOR_KEYWORDS = [
    "Canada project construction investment 2025 2026",
    "Canada facility expansion billion million",
]

def _build_sector_searches() -> list[tuple[str, str]]:
    out = []
    for sector in _SECTOR_QUERIES:
        for kw in _SECTOR_KEYWORDS:
            out.append((f"{sector} {kw}", "project"))
    return out

# Section D: Top company queries (30)
_COMPANY_QUERIES = [
    "TC Energy Canada project", "Enbridge pipeline project", "TransAlta power project",
    "Brookfield Canada development", "CPPIB infrastructure project",
    "SNC-Lavalin Canada project", "Aecon Group Canada project",
    "EllisDon construction Canada", "PCL Construction Canada project",
    "Tridel development Toronto", "Concord Pacific Vancouver project",
    "Mattamy Homes development", "Dream Unlimited Canada project",
    "Fortis Canada energy project", "Ontario Power Generation nuclear",
    "Cameco uranium Canada", "Teck Resources mine project",
    "Nutrien potash expansion", "Lundin Mining Canada",
    "Samsung Canada EV battery plant", "Stellantis Canada plant",
    "Volkswagen Canada battery plant", "Honda Canada facility",
    "Amazon Canada warehouse", "Google Canada data center",
    "Microsoft Canada data center", "Hydro-Quebec project",
    "CDPQ Infra Canada project", "Devimco Montreal development",
    "Bird Construction Canada project",
]

def _build_company_searches() -> list[tuple[str, str]]:
    return [(q, "project") for q in _COMPANY_QUERIES]

# Section E: Publication catch-all (5)
_CATCHALL_SEARCHES = [
    ("Canada major project ReNew infrastructure Daily Commercial News", "project"),
    ("Canada mining project Northern Miner approved",                   "project"),
    ("Canada energy project pipeline LNG approved",                     "project"),
    ("Canada P3 Indigenous economic development project",               "project"),
    ("Canada construction procurement contract awarded billion",        "project"),
]

# Section F: Archetype national queries (18)
_ARCHETYPE_NATIONAL = [
    ("Canada redevelopment construction",          "project"),
    ("Canada mixed-use development",               "project"),
    ("Canada transit LRT construction",            "project"),
    ("Canada hospital construction expansion",     "project"),
    ("Canada arena stadium construction",          "project"),
    ("Canada university campus construction",      "project"),
    ("Canada mine approved construction",          "project"),
    ("Canada wind farm solar construction",        "project"),
    ("Canada pipeline transmission approved",      "project"),
    ("Canada LNG petrochemical plant",             "project"),
    ("Canada manufacturing factory plant",         "project"),
    ("Canada data centre construction",            "project"),
    ("Canada airport port expansion",              "project"),
    ("Canada water treatment construction",        "project"),
    ("Canada military defence construction",       "project"),
    ("Canada Indigenous development project",      "project"),
    ("Canada hydrogen carbon capture",             "project"),
    ("Canada museum library construction",         "project"),
]

# Section G: Archetype provincial queries (top 5 archetypes per province)
_ARCHETYPE_PROV_KEYWORDS = [
    "redevelopment construction",
    "hospital construction",
    "transit construction",
    "manufacturing plant",
    "clean energy project",
]

def _build_archetype_prov_searches() -> list[tuple[str, str]]:
    out = []
    for prov in _PROVINCE_NAMES:
        for kw in _ARCHETYPE_PROV_KEYWORDS:
            out.append((f"{prov} {kw}", "project"))
    return out

# Section H: Archetype CMA queries (2 per CMA)
_ARCHETYPE_CMA_KEYWORDS = [
    "construction project",
    "development investment",
]

def _build_archetype_cma_searches() -> list[tuple[str, str]]:
    out = []
    for cma in _CMA_NAMES:
        for kw in _ARCHETYPE_CMA_KEYWORDS:
            out.append((f"{cma} {kw}", "project"))
    return out

# Section I: French archetype queries (5)
_FRENCH_ARCHETYPE_SEARCHES = [
    ('"projet investissement" Quebec OR Montréal',          "project"),
    ('"construction" "milliard" Québec',                    "project"),
    ('"mise en chantier" Québec OR Montréal',               "project"),
    ('"agrandissement usine" Québec',                       "project"),
    ('"infrastructure" projet Québec approuvé',             "project"),
]

# Economy searches (retained for context, not project discovery)
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

    # Build the full query set (~343 project + 8 economy)
    all_searches = (
        _build_province_searches()          # 65
        + _build_cma_searches()             # 60
        + _build_sector_searches()          # 40
        + _build_company_searches()         # 30
        + list(_CATCHALL_SEARCHES)          # 5
        + list(_ARCHETYPE_NATIONAL)         # 18
        + _build_archetype_prov_searches()  # 65
        + _build_archetype_cma_searches()   # 60
        + list(_FRENCH_ARCHETYPE_SEARCHES)  # 5
    )
    if include_economy:
        all_searches += list(_ECONOMY_SEARCHES)  # 8

    print(f"  [GDELT] Running {len(all_searches)} searches (last {days_back}d)...")

    raw_articles: list[dict] = []
    consecutive_errors = 0  # network errors only; empty results don't count

    for i, (keyword, topic) in enumerate(all_searches):
        result = _gdelt_search(keyword, topic, days_back)
        if result is _NETWORK_ERROR:
            consecutive_errors += 1
            # Bail out early if the API is consistently unreachable
            if consecutive_errors >= _BAIL_THRESHOLD:
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

    # Record documents for fetch tracking
    try:
        from db import get_db, insert_document
        conn = get_db()
        for art in unique:
            insert_document(conn, art.get('url', ''),
                            title=art.get('title', ''),
                            source_tier='tier_3', source_type='gdelt',
                            published_date=art.get('seendate', ''))
        conn.close()
    except Exception:
        pass

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


def filter_gdelt_articles(
    articles: list[dict],
    gemini_client=None,
) -> list[dict]:
    """
    Run GDELT articles through the three-layer relevance filter
    before Tavily extraction. Prevents spending credits on non-project articles.
    """
    if not articles:
        return []

    from article_filter import filter_articles

    # Convert GDELT article format to filter format
    filter_input = []
    for art in articles:
        filter_input.append({
            'title': art.get('title', ''),
            'summary': '',  # GDELT articles don't have summaries
            '_original': art,
        })

    filtered = filter_articles(
        filter_input,
        gemini_client=gemini_client,
        skip_layer1=False,
    )

    # Recover original GDELT dicts
    return [f['_original'] for f in filtered if '_original' in f]


def log_gdelt_unique(
    gdelt_projects: list[dict],
    gemini_names: set[str],
):
    """Log projects found by GDELT but not by Gemini (for prompt improvement)."""
    from datetime import date
    today = date.today().isoformat()
    unique = [p for p in gdelt_projects
              if p.get('name', '').lower().strip() not in gemini_names]
    if not unique:
        return
    try:
        path = f'gdelt_unique_{today}.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"GDELT-unique projects — {today}\n{'='*60}\n")
            f.write("Projects found by GDELT but NOT by Gemini search.\n")
            f.write("Review these to improve Gemini query templates.\n\n")
            for p in unique:
                f.write(f"{p.get('province', '?')}: {p.get('name', '?')}\n")
                f.write(f"  URL: {p.get('source_url', 'N/A')}\n\n")
        print(f"  [GDELT] {len(unique)} unique projects logged to {path}")
    except Exception:
        pass
