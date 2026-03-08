"""
rss_monitor.py — Government RSS/Atom feed aggregator for the CAN-MACRO pipeline.

Fetches news releases from federal, provincial, and municipal Canadian government
sources. Returns standardized items used to:
  - Replace the old 3-feed news_context with 46-feed coverage
  - Provide province-specific context to Perplexity queries
  - Extract structured capital project data via Haiku (free, no Perplexity call)

Usage:
    import rss_monitor
    items = rss_monitor.fetch_all_feeds(days_back=7)
    proj  = rss_monitor.filter_project_relevant(items)
    ctx   = rss_monitor.format_for_context(items, province_filter='Ontario')
"""

import re
import concurrent.futures
from datetime import datetime, timezone, timedelta

import feedparser
import requests

# ---------------------------------------------------------------------------
# Feed configuration
# ---------------------------------------------------------------------------
# Each entry: url, name, level (federal/provincial/municipal), province, category
# category: economic | infrastructure | procurement | general

FEEDS_CONFIG = {
    # ── Federal: economic & statistical ──────────────────────────────────────
    'statcan_daily': {
        'name': 'Statistics Canada Daily',
        'url': 'https://www150.statcan.gc.ca/n1/rss/dai-quo/0-eng.atom',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'boc_press': {
        'name': 'Bank of Canada — Press Releases',
        'url': 'https://www.bankofcanada.ca/content_type/press-releases/feed/',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'boc_publications': {
        'name': 'Bank of Canada — Publications',
        'url': 'https://www.bankofcanada.ca/content_type/publications/feed/',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    # ── Federal: departments (Canada.ca news API — verified working) ─────────
    'infrastructure_canada': {
        'name': 'Infrastructure Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=officeinfrastructure&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Infrastructure%20Canada',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
    'finance_canada': {
        'name': 'Department of Finance Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentfinance&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Department%20of%20Finance%20Canada',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'ised': {
        'name': 'Innovation, Science and Economic Development Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofindustry&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Innovation,%20Science%20and%20Economic%20Development%20Canada',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'nrcan': {
        'name': 'Natural Resources Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=naturalresourcescanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Natural%20Resources%20Canada',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
    'transport_canada': {
        'name': 'Transport Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentoftransport&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Transport%20Canada',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
    'pspc': {
        'name': 'Public Services and Procurement Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofpublicworksandgovernmentservices&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Public%20Services%20and%20Procurement%20Canada',
        'level': 'federal', 'province': None, 'category': 'procurement',
    },
    'esdc': {
        'name': 'Employment and Social Development Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofemploymentandsocialdevelopment&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Employment%20and%20Social%20Development%20Canada',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'ircc': {
        'name': 'Immigration, Refugees and Citizenship Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofcitizenshipandimmigration&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Immigration,%20Refugees%20and%20Citizenship%20Canada',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    'cer': {
        'name': 'Canada Energy Regulator',
        'url': 'https://www.cer-rec.gc.ca/rss/rssfd.aspx?l=e&c=catNR',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
    'iaac': {
        'name': 'Impact Assessment Agency of Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=impactassessmentagency&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Impact%20Assessment%20Agency%20of%20Canada',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
    'treasury_board': {
        'name': 'Treasury Board Secretariat',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=treasuryboardsecretariat&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Treasury%20Board%20of%20Canada%20Secretariat',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    # ── Federal: additional departments ─────────────────────────────────────
    'cmhc': {
        'name': 'Canada Mortgage and Housing Corporation',
        'url': 'https://www.cmhc-schl.gc.ca/rss/news-releases.xml',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'environment_canada': {
        'name': 'Environment and Climate Change Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=environmentcanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Environment%20and%20Climate%20Change%20Canada',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    'health_canada': {
        'name': 'Health Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=healthcanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Health%20Canada',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    'dnd': {
        'name': 'National Defence',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=nationaldepartmentofdefence&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=National%20Defence',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    'canada_revenue': {
        'name': 'Canada Revenue Agency',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=revenuecanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Canada%20Revenue%20Agency',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'global_affairs': {
        'name': 'Global Affairs Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=foreignaffairstradedev&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Global%20Affairs%20Canada',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'agriculture_canada': {
        'name': 'Agriculture and Agri-Food Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=agricultureagrifoodcanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Agriculture%20and%20Agri-Food%20Canada',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    'fisheries': {
        'name': 'Fisheries and Oceans Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=fisheriesoceans&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Fisheries%20and%20Oceans%20Canada',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    'indigenous_services': {
        'name': 'Indigenous Services Canada',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=indigenousservicescanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Indigenous%20Services%20Canada',
        'level': 'federal', 'province': None, 'category': 'general',
    },
    'innovation_canada': {
        'name': 'Canada Innovation Corporation',
        'url': 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofindustry&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Canada%20Innovation',
        'level': 'federal', 'province': None, 'category': 'economic',
    },
    # ── Provincial ───────────────────────────────────────────────────────────
    'bc': {
        'name': 'BC Government News',
        'url': 'https://news.gov.bc.ca/feed',
        'level': 'provincial', 'province': 'British Columbia', 'category': 'general',
    },
    'alberta': {
        'name': 'Government of Alberta',
        'url': 'https://www.alberta.ca/albertaca.rss',
        'level': 'provincial', 'province': 'Alberta', 'category': 'general',
    },
    'ontario': {
        'name': 'Government of Ontario',
        'url': 'https://news.ontario.ca/en/atom',
        'level': 'provincial', 'province': 'Ontario', 'category': 'general',
    },
    'ontario_fin': {
        'name': 'Ontario Ministry of Finance',
        'url': 'https://news.ontario.ca/en/atom?ministry=finance',
        'level': 'provincial', 'province': 'Ontario', 'category': 'economic',
    },
    'quebec': {
        'name': 'Gouvernement du Quebec',
        'url': 'https://www.quebec.ca/fil-de-presse.rss',
        'level': 'provincial', 'province': 'Quebec', 'category': 'general',
    },
    'saskatchewan': {
        'name': 'Government of Saskatchewan',
        'url': 'https://www.saskatchewan.ca/Feeds/NewsFeed.ashx',
        'level': 'provincial', 'province': 'Saskatchewan', 'category': 'general',
    },
    'manitoba': {
        'name': 'Government of Manitoba',
        'url': 'https://news.gov.mb.ca/news/rss/en.rss',
        'level': 'provincial', 'province': 'Manitoba', 'category': 'general',
    },
    'nova_scotia': {
        'name': 'Government of Nova Scotia',
        'url': 'https://novascotia.ca/news/rss/',
        'level': 'provincial', 'province': 'Nova Scotia', 'category': 'general',
    },
    'new_brunswick': {
        'name': 'Government of New Brunswick',
        'url': 'https://www2.gnb.ca/content/gnb/en/news.rss.html',
        'level': 'provincial', 'province': 'New Brunswick', 'category': 'general',
    },
    'newfoundland': {
        'name': 'Government of Newfoundland and Labrador',
        'url': 'https://www.gov.nl.ca/releases/feed/',
        'level': 'provincial', 'province': 'Newfoundland and Labrador', 'category': 'general',
    },
    'pei': {
        'name': 'Government of Prince Edward Island',
        'url': 'https://www.princeedwardisland.ca/en/news.rss',
        'level': 'provincial', 'province': 'Prince Edward Island', 'category': 'general',
    },
    'yukon': {
        'name': 'Government of Yukon',
        'url': 'https://yukon.ca/en/news/rss.xml',
        'level': 'provincial', 'province': 'Yukon', 'category': 'general',
    },
    'nwt': {
        'name': 'Government of Northwest Territories',
        'url': 'https://www.gov.nt.ca/en/rss',
        'level': 'provincial', 'province': 'Northwest Territories', 'category': 'general',
    },
    # ── Municipal ────────────────────────────────────────────────────────────
    'toronto': {
        'name': 'City of Toronto',
        'url': 'https://www.toronto.ca/news/feed/',
        'level': 'municipal', 'province': 'Ontario', 'category': 'general',
    },
    'toronto_budget': {
        'name': 'City of Toronto — Budget',
        'url': 'https://www.toronto.ca/city-government/budget-finances/city-budget/feed/',
        'level': 'municipal', 'province': 'Ontario', 'category': 'economic',
    },
    'ottawa': {
        'name': 'City of Ottawa',
        'url': 'https://ottawa.ca/en/news/rss.xml',
        'level': 'municipal', 'province': 'Ontario', 'category': 'general',
    },
    'mississauga': {
        'name': 'City of Mississauga',
        'url': 'https://www.mississauga.ca/news-and-events/feed/',
        'level': 'municipal', 'province': 'Ontario', 'category': 'general',
    },
    'calgary': {
        'name': 'City of Calgary Newsroom',
        'url': 'https://newsroom.calgary.ca/feed/',
        'level': 'municipal', 'province': 'Alberta', 'category': 'general',
    },
    'edmonton': {
        'name': 'City of Edmonton',
        'url': 'https://www.edmonton.ca/city_government/news_centre/rss',
        'level': 'municipal', 'province': 'Alberta', 'category': 'general',
    },
    'vancouver': {
        'name': 'City of Vancouver',
        'url': 'https://vancouver.ca/news-calendar/news.rss',
        'level': 'municipal', 'province': 'British Columbia', 'category': 'general',
    },
    'surrey': {
        'name': 'City of Surrey',
        'url': 'https://www.surrey.ca/rss/news',
        'level': 'municipal', 'province': 'British Columbia', 'category': 'general',
    },
    'montreal': {
        'name': 'Ville de Montreal',
        'url': 'https://montreal.ca/rss/actualites',
        'level': 'municipal', 'province': 'Quebec', 'category': 'general',
    },
    'quebec_city': {
        'name': 'Ville de Quebec',
        'url': 'https://www.ville.quebec.qc.ca/rss/nouvelles/',
        'level': 'municipal', 'province': 'Quebec', 'category': 'general',
    },
    'winnipeg': {
        'name': 'City of Winnipeg',
        'url': 'https://www.winnipeg.ca/rss/en/media-releases.xml',
        'level': 'municipal', 'province': 'Manitoba', 'category': 'general',
    },
    'halifax': {
        'name': 'Halifax Regional Municipality',
        'url': 'https://www.halifax.ca/news/rss-feed',
        'level': 'municipal', 'province': 'Nova Scotia', 'category': 'general',
    },
    'saskatoon': {
        'name': 'City of Saskatoon',
        'url': 'https://www.saskatoon.ca/news-releases/feed',
        'level': 'municipal', 'province': 'Saskatchewan', 'category': 'general',
    },
    'regina': {
        'name': 'City of Regina',
        'url': 'https://www.regina.ca/news/rss.xml',
        'level': 'municipal', 'province': 'Saskatchewan', 'category': 'general',
    },
    'victoria': {
        'name': 'City of Victoria',
        'url': 'https://www.victoria.ca/EN/main/city/news.rss',
        'level': 'municipal', 'province': 'British Columbia', 'category': 'general',
    },
    'kelowna': {
        'name': 'City of Kelowna',
        'url': 'https://www.kelowna.ca/rss/news.xml',
        'level': 'municipal', 'province': 'British Columbia', 'category': 'general',
    },
    'london_on': {
        'name': 'City of London (ON)',
        'url': 'https://london.ca/news/rss.xml',
        'level': 'municipal', 'province': 'Ontario', 'category': 'general',
    },
    'hamilton': {
        'name': 'City of Hamilton',
        'url': 'https://www.hamilton.ca/news-events/news-releases/rss.xml',
        'level': 'municipal', 'province': 'Ontario', 'category': 'general',
    },
    'brampton': {
        'name': 'City of Brampton',
        'url': 'https://www.brampton.ca/EN/MediaRoom/News-Releases/RSS/Pages/default.aspx',
        'level': 'municipal', 'province': 'Ontario', 'category': 'general',
    },
    'moncton': {
        'name': 'City of Moncton',
        'url': 'https://www.moncton.ca/rss/news.xml',
        'level': 'municipal', 'province': 'New Brunswick', 'category': 'general',
    },
    'fredericton': {
        'name': 'City of Fredericton',
        'url': 'https://www.fredericton.ca/en/rss/news',
        'level': 'municipal', 'province': 'New Brunswick', 'category': 'general',
    },
    'stjohns': {
        'name': "City of St. John's",
        'url': 'https://www.stjohns.ca/news/feed',
        'level': 'municipal', 'province': 'Newfoundland and Labrador', 'category': 'general',
    },
    'charlottetown': {
        'name': 'City of Charlottetown',
        'url': 'https://www.charlottetown.ca/news/rss.xml',
        'level': 'municipal', 'province': 'Prince Edward Island', 'category': 'general',
    },
    'whitehorse': {
        'name': 'City of Whitehorse',
        'url': 'https://www.whitehorse.ca/news/rss.xml',
        'level': 'municipal', 'province': 'Yukon', 'category': 'general',
    },
}

# ---------------------------------------------------------------------------
# Project-relevance keyword filter
# ---------------------------------------------------------------------------
_PROJECT_KEYWORDS = frozenset({
    'project', 'infrastructure', 'investment', 'construction', 'funding',
    'billion', 'million', 'announced', 'approved', 'contract', 'development',
    'expansion', 'mine', 'pipeline', 'transit', 'housing', 'energy',
    'highway', 'bridge', 'hospital', 'school', 'airport', 'port',
    'procurement', 'awarded', 'tender', 'build', 'built', 'facility',
    'centre', 'center', 'corridor', 'broadband', 'fibre', 'fiber',
    'transmission', 'generation', 'refinery', 'terminal', 'reactor',
    'desalination', 'wastewater', 'transit', 'arena', 'stadium',
    'affordable', 'subsidy', 'grant', 'loan',
})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_recent(entry, days_back: int) -> bool:
    """Return True if a feedparser entry was published within days_back days."""
    for attr in ('published_parsed', 'updated_parsed', 'created_parsed'):
        t = getattr(entry, attr, None)
        if t is not None:
            try:
                pub = datetime(*t[:6], tzinfo=timezone.utc)
                return (datetime.now(timezone.utc) - pub) <= timedelta(days=days_back)
            except Exception:
                pass
    return True  # include if date is unknown


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r'<[^>]+>', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()


def _entry_to_item(entry, meta: dict) -> dict:
    """Convert a feedparser entry + feed metadata to a standardized news item."""
    title = _clean_html(getattr(entry, 'title', '') or '')

    # Prefer summary; fall back to first content block
    summary = ''
    if hasattr(entry, 'summary') and entry.summary:
        summary = entry.summary
    elif hasattr(entry, 'content') and entry.content:
        summary = entry.content[0].get('value', '')
    summary = _clean_html(summary)[:500]

    url = getattr(entry, 'link', '') or ''

    pub_date = ''
    for attr in ('published', 'updated', 'created'):
        val = getattr(entry, attr, None)
        if val:
            pub_date = val[:25]  # truncate long ISO strings
            break

    return {
        'title':        title,
        'summary':      summary,
        'url':          url,
        'published':    pub_date,
        'source_name':  meta['name'],
        'source_level': meta['level'],
        'province':     meta.get('province'),
        'category':     meta.get('category', 'general'),
    }


_HEADERS = {'User-Agent': 'Mozilla/5.0 (CAN-MACRO/1.0; +https://github.com/can-macro)'}


def _fetch_one(feed_id: str, meta: dict, days_back: int) -> list[dict]:
    """Fetch a single RSS/Atom feed and return recent items. Never raises.

    Uses requests for the HTTP layer (handles SSL certs + User-Agent correctly),
    then passes raw content to feedparser for parsing.
    """
    url = meta['url']
    try:
        resp = requests.get(url, timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        content_type = resp.headers.get('content-type', '')
        feed = feedparser.parse(resp.content, response_headers={'content-type': content_type})
        # bozo=True with no entries → truly broken (e.g. non-RSS HTML page)
        if feed.bozo and not feed.entries:
            return []
        return [
            _entry_to_item(e, meta)
            for e in feed.entries
            if _is_recent(e, days_back)
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_all_feeds(days_back: int = 7) -> list[dict]:
    """
    Fetch all configured RSS/Atom feeds concurrently (16 workers).

    Args:
        days_back: Include items published within this many days
                   (7 for weekly pipeline, 30 for monthly deep sweep).

    Returns:
        Flat list of news-item dicts sorted oldest-to-newest within each feed.
        Each item: {title, summary, url, published, source_name,
                    source_level, province, category}
    """
    all_items: list[dict] = []
    alive = 0
    dead = 0

    print(f"  [RSS] Fetching {len(FEEDS_CONFIG)} government feeds (last {days_back}d)...",
          end=' ', flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futures = {
            ex.submit(_fetch_one, fid, meta, days_back): fid
            for fid, meta in FEEDS_CONFIG.items()
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                items = future.result()
                if items:
                    alive += 1
                    all_items.extend(items)
                else:
                    dead += 1
            except Exception:
                dead += 1

    print(f"{len(all_items)} items from {alive}/{alive + dead} feeds")
    return all_items


def filter_project_relevant(items: list[dict]) -> list[dict]:
    """
    Filter news items that likely describe a capital project, funding
    announcement, or major infrastructure event.
    """
    out = []
    for item in items:
        text = (item['title'] + ' ' + item['summary']).lower()
        if any(kw in text for kw in _PROJECT_KEYWORDS):
            out.append(item)
    return out


def format_for_context(
    items: list[dict],
    max_items: int = 50,
    province_filter: str | None = None,
    level_filter: str | None = None,
) -> str:
    """
    Format news items as a compact text block for Claude / Perplexity context.

    Args:
        items:           Full list of news items from fetch_all_feeds().
        max_items:       Cap on number of items included.
        province_filter: If set, only include items from this province
                         (matches provincial feeds AND municipal feeds for that province).
        level_filter:    If set ('federal'/'provincial'/'municipal'), filter by level.

    Returns:
        Multi-line string, one bullet per item.  Empty string if nothing matches.
    """
    filtered = items
    if province_filter:
        filtered = [i for i in filtered if i.get('province') == province_filter]
    if level_filter:
        filtered = [i for i in filtered if i.get('source_level') == level_filter]
    if not filtered:
        return ''

    lines = []
    for item in filtered[:max_items]:
        prov_tag = f" [{item['province']}]" if item['province'] else ''
        date_tag = f" ({item['published'][:10]})" if item.get('published') else ''
        lines.append(
            f"• [{item['source_name']}{prov_tag}{date_tag}] {item['title']}\n"
            f"  {item['summary'][:220]}"
        )
    return '\n'.join(lines)


def province_context(items: list[dict], province: str, max_items: int = 12) -> str:
    """
    Return a compact context string for a specific province:
    provincial + municipal items for that province, plus top federal items.
    Used to enrich Perplexity province queries.
    """
    prov_items = [i for i in items if i.get('province') == province]
    fed_items  = [i for i in items if i.get('source_level') == 'federal'][:8]
    combined   = prov_items + [f for f in fed_items if f not in prov_items]
    return format_for_context(combined, max_items=max_items)


# ---------------------------------------------------------------------------
# --test-feeds CLI utility
# ---------------------------------------------------------------------------

def test_feeds() -> dict:
    """
    Test every feed URL — HEAD request first, then full parse if reachable.
    Prints a detailed report grouped by federal / provincial / municipal.
    Returns a dict: {feed_id: {'status': str, 'http': int, 'items': int}}
    """
    results: dict[str, dict] = {}

    print(f"\n{'='*66}")
    print(f"  RSS FEED TEST — {len(FEEDS_CONFIG)} feeds")
    print(f"{'='*66}\n")

    by_level: dict[str, list] = {'federal': [], 'provincial': [], 'municipal': []}
    for fid, meta in FEEDS_CONFIG.items():
        by_level.setdefault(meta['level'], []).append((fid, meta))

    for level in ('federal', 'provincial', 'municipal'):
        feed_list = sorted(by_level.get(level, []), key=lambda x: x[1]['name'])
        print(f"  {'─'*62}")
        print(f"  {level.upper()} ({len(feed_list)} feeds)")
        print(f"  {'─'*62}")

        for fid, meta in feed_list:
            url = meta['url']
            status = 'unknown'
            http_code = 0
            n_items = 0

            try:
                r = requests.get(url, timeout=12, allow_redirects=True, headers=_HEADERS)
                http_code = r.status_code

                if http_code >= 400:
                    status = 'dead'
                else:
                    content_type = r.headers.get('content-type', '')
                    feed = feedparser.parse(r.content, response_headers={'content-type': content_type})
                    if feed.bozo and not feed.entries:
                        status = 'no_rss'
                    else:
                        status = 'ok'
                        n_items = len(feed.entries)

            except requests.exceptions.Timeout:
                status = 'timeout'
            except Exception:
                status = 'error'

            _STATUS_ICON = {
                'ok': 'OK', 'dead': 'DEAD', 'no_rss': 'NO_RSS',
                'timeout': 'TIMEOUT', 'error': 'ERROR', 'unknown': '?',
            }
            icon = _STATUS_ICON.get(status, '?')
            prov_tag = f" ({meta['province']})" if meta.get('province') else ''

            print(f"  [{icon:>7}] {meta['name']}{prov_tag}")
            if status == 'ok':
                print(f"           {n_items} entries  |  {url}")
            else:
                info = f"HTTP {http_code}  |  " if http_code else ''
                print(f"           {info}{url}")

            results[fid] = {'status': status, 'http': http_code, 'items': n_items}

    ok  = sum(1 for r in results.values() if r['status'] == 'ok')
    bad = len(results) - ok
    print(f"\n  {'='*62}")
    print(f"  SUMMARY: {ok}/{len(results)} feeds live  |  {bad} dead/broken/no-content")
    print(f"  {'='*62}\n")
    return results
