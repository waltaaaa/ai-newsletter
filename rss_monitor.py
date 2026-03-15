"""
rss_monitor.py — RSS/Atom feed aggregator for the CAN-MACRO pipeline (Tier 4).

Fetches news from government newsrooms (~40 feeds) AND major Canadian media
(CBC, CTV, Global, Postmedia, specialty — ~95 feeds). Feed inventory stored
in rss_feeds.json.

Three-layer relevance filter (from article_filter.py):
  L1 — Compound keyword co-occurrence
  L2 — Negative keyword exclusion
  L3 — Gemini Flash batch pre-screen

Usage:
    import rss_monitor
    items = rss_monitor.fetch_all_feeds(days_back=7)
    proj  = rss_monitor.filter_project_relevant(items)
    ctx   = rss_monitor.format_for_context(items, province_filter='Ontario')
"""

import json
import os
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

    # ── STEP 2G: Crown corporation news releases ─────────────────────────
    'metrolinx_news': {
        'name': 'Metrolinx News',
        'url': 'https://www.metrolinx.com/en/news/rss',
        'level': 'provincial', 'province': 'Ontario', 'category': 'infrastructure',
    },
    'translink_news': {
        'name': 'TransLink News',
        'url': 'https://www.translink.ca/news/rss',
        'level': 'provincial', 'province': 'British Columbia', 'category': 'infrastructure',
    },
    'hydro_quebec_news': {
        'name': 'Hydro-Québec News',
        'url': 'https://news.hydroquebec.com/en/press-releases/rss/',
        'level': 'provincial', 'province': 'Quebec', 'category': 'energy',
    },
    'opg_news': {
        'name': 'Ontario Power Generation News',
        'url': 'https://www.opg.com/media-releases/feed/',
        'level': 'provincial', 'province': 'Ontario', 'category': 'energy',
    },
    'bc_hydro_news': {
        'name': 'BC Hydro News',
        'url': 'https://www.bchydro.com/news/rss.xml',
        'level': 'provincial', 'province': 'British Columbia', 'category': 'energy',
    },
    'cib_news': {
        'name': 'Canada Infrastructure Bank News',
        'url': 'https://cib-bic.ca/en/news/feed/',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
    'via_rail_news': {
        'name': 'VIA Rail Media',
        'url': 'https://media.viarail.ca/en/rss',
        'level': 'federal', 'province': None, 'category': 'infrastructure',
    },
}

# ---------------------------------------------------------------------------
# EXPANDED FEEDS from rss_feeds.json (Tier 4 media feeds)
# ---------------------------------------------------------------------------

_RSS_FEEDS_PATH = os.path.join(os.path.dirname(__file__), 'rss_feeds.json')


def _load_media_feeds() -> dict[str, dict]:
    """
    Load media feeds from rss_feeds.json (CBC, CTV, Global, Postmedia, etc.).
    Returns them in FEEDS_CONFIG format keyed by feed ID.
    """
    if not os.path.exists(_RSS_FEEDS_PATH):
        return {}

    try:
        with open(_RSS_FEEDS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {}

    extra = {}
    google_alert_total = 0
    google_alert_placeholder = 0
    # Process each media category
    for category in ('cbc', 'ctv', 'global_news', 'postmedia', 'independent', 'wire_services', 'industry', 'regional_media', 'regional_media_fr', 'business_media', 'key_people', 'google_alerts', 'corporate_ir', 'corporate_epc', 'institutional', 'corporate_newswire', 'regulatory'):
        feeds = data.get(category, [])
        for feed in feeds:
            if not feed.get('enabled', True):
                if category == 'google_alerts':
                    google_alert_total += 1
                    url = feed.get('url', '')
                    if 'PASTE_FEED_URL_HERE' in url or not url.startswith('http'):
                        google_alert_placeholder += 1
                continue
            fid = feed.get('id', '')
            if not fid or not feed.get('url'):
                continue
            # Skip placeholder URLs (e.g. unconfigured Google Alert feeds)
            url = feed.get('url', '')
            if 'PASTE_FEED_URL_HERE' in url or 'XXXX' in url:
                if category == 'google_alerts':
                    google_alert_total += 1
                    google_alert_placeholder += 1
                logger.warning(f"  [{fid}] Skipped — placeholder URL not configured")
                continue
            if category == 'google_alerts':
                google_alert_total += 1
            # key_people and regulatory feeds use special levels for government bypass
            if category == 'key_people':
                level = 'key_people'
            elif category == 'regulatory':
                level = 'regulatory'
            else:
                level = 'media'
            extra[fid] = {
                'name': feed.get('name', fid),
                'url': feed['url'],
                'level': level,
                'province': feed.get('province_map') or feed.get('jurisdiction'),
                'category': category,
                'priority': feed.get('priority', 3),
                'test': feed.get('test', False),
            }

    if google_alert_total > 0 and google_alert_placeholder == google_alert_total:
        print("[Tier 12] Skipped — no Google Alert feeds configured")

    return extra


# Build combined config: government feeds (hardcoded) + media feeds (from JSON)
MEDIA_FEEDS = _load_media_feeds()
ALL_FEEDS = {**FEEDS_CONFIG, **MEDIA_FEEDS}


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
    elif hasattr(entry, 'content') and entry.content and len(entry.content) > 0:
        first = entry.content[0]
        summary = first.get('value', '') if isinstance(first, dict) else str(first)
    summary = _clean_html(summary)[:500]

    url = getattr(entry, 'link', '') or ''

    pub_date = ''
    for attr in ('published', 'updated', 'created'):
        val = getattr(entry, attr, None)
        if val:
            pub_date = val[:25]  # truncate long ISO strings
            break

    # Extract RSS-level category/tag fields for metadata tagger
    entry_tags = []
    if hasattr(entry, 'tags') and entry.tags:
        for tag in entry.tags:
            term = tag.get('term') or tag.get('label') or ''
            if term:
                entry_tags.append(term)

    return {
        'title':        title,
        'summary':      summary,
        'url':          url,
        'published':    pub_date,
        'source_name':  meta['name'],
        'source_level': meta['level'],
        'province':     meta.get('province'),
        'category':     meta.get('category', 'general'),
        'tags':         entry_tags,
    }


# ---------------------------------------------------------------------------
# Canadian relevance pre-filter for global newswire feeds
# ---------------------------------------------------------------------------

_NEWSWIRE_DOMAINS = frozenset({
    'globenewswire.com', 'prnewswire.com',
})

CANADIAN_INDICATORS = [
    # Company suffixes
    "ltd.", "inc.", "corp.", "limited",
    # Exchanges
    "tsx", "tsx-v", "cse",
    # Geography
    "canada", "canadian", "alberta", "ontario", "quebec", "british columbia",
    "saskatchewan", "manitoba", "nova scotia", "new brunswick",
    "newfoundland", "pei", "yukon", "nwt", "nunavut",
    # Cities (top 20 by project volume)
    "toronto", "vancouver", "calgary", "edmonton", "montreal",
    "ottawa", "winnipeg", "halifax", "saskatoon", "regina",
    "victoria", "hamilton", "kitchener", "london on",
    "st. john's", "moncton", "fredericton", "sudbury",
    # Canadian-specific terms
    "first nation", "indigenous", "crown land", "provincial",
]


def _is_newswire_article(item):
    """Check if article comes from a global newswire (needs Canadian filter)."""
    url = item.get('url') or item.get('link') or ''
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().replace('www.', '')
        return any(domain.endswith(d) for d in _NEWSWIRE_DOMAINS)
    except Exception:
        return False


def is_canadian_content(article):
    """Quick check if a newswire article is Canadian-relevant."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    return any(indicator in text for indicator in CANADIAN_INDICATORS)


_HEADERS = {'User-Agent': 'Mozilla/5.0 (CAN-MACRO/1.0; +https://github.com/can-macro)'}


def _persist_feed_health(feed_results: dict):
    """Persist per-feed health to dashboard_state for monitoring.

    Tracks: last_success, consecutive_failures, total_checks.
    Alerts when previously healthy feeds go dead (>=3 consecutive failures).
    """
    try:
        import json
        from datetime import date as _date
        from db import get_dashboard_state, save_dashboard_state

        conn = __import__("db").get_db()
        try:
            existing = get_dashboard_state(conn, "feed_health")
            health = existing if isinstance(existing, dict) else {}

            today = _date.today().isoformat()
            newly_dead = []

            for fid, result in feed_results.items():
                entry = health.get(fid, {"last_success": "", "consecutive_failures": 0, "total_checks": 0})
                entry["total_checks"] = entry.get("total_checks", 0) + 1

                if result["alive"]:
                    entry["last_success"] = today
                    entry["consecutive_failures"] = 0
                    entry["items"] = result["items"]
                else:
                    entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
                    # Alert if a previously healthy feed has failed 3+ times
                    if entry.get("last_success") and entry["consecutive_failures"] >= 3:
                        newly_dead.append(fid)

                health[fid] = entry

            save_dashboard_state(conn, "feed_health", health)

            if newly_dead:
                print(f"  [FEED HEALTH] {len(newly_dead)} feeds newly dead: {', '.join(newly_dead[:5])}")
        finally:
            conn.close()
    except Exception:
        pass  # feed health tracking is non-critical


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

def fetch_all_feeds(
    days_back: int = 7,
    include_media: bool = True,
) -> list[dict]:
    """
    Fetch all configured RSS/Atom feeds concurrently (16 workers).

    Args:
        days_back: Include items published within this many days
                   (7 for weekly pipeline, 30 for monthly deep sweep).
        include_media: If True, also fetch CBC, CTV, Global, Postmedia, etc.

    Returns:
        Flat list of news-item dicts sorted oldest-to-newest within each feed.
        Each item: {title, summary, url, published, source_name,
                    source_level, province, category}
    """
    feeds = ALL_FEEDS if include_media else FEEDS_CONFIG
    all_items: list[dict] = []
    alive = 0
    dead = 0

    label = "all" if include_media else "government"
    print(f"  [RSS] Fetching {len(feeds)} {label} feeds (last {days_back}d)...",
          end=' ', flush=True)

    feed_results = {}  # feed_id → {"alive": bool, "items": int}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futures = {
            ex.submit(_fetch_one, fid, meta, days_back): fid
            for fid, meta in feeds.items()
        }
        for future in concurrent.futures.as_completed(futures, timeout=300):
            fid = futures[future]
            try:
                items = future.result(timeout=60)
                if items:
                    alive += 1
                    all_items.extend(items)
                    feed_results[fid] = {"alive": True, "items": len(items)}
                else:
                    dead += 1
                    feed_results[fid] = {"alive": False, "items": 0}
            except (concurrent.futures.TimeoutError, Exception):
                dead += 1
                feed_results[fid] = {"alive": False, "items": 0}

    print(f"{len(all_items)} items from {alive}/{alive + dead} feeds")

    # Persist feed health to DB for monitoring
    _persist_feed_health(feed_results)

    # Record documents for fetch tracking
    try:
        from db import get_db, insert_document
        doc_conn = get_db()
        try:
            for item in all_items:
                insert_document(doc_conn, item.get('url', ''),
                                title=item.get('title', ''),
                                source_tier='tier_4', source_type='rss_feed',
                                published_date=item.get('published', ''))
        finally:
            doc_conn.close()
    except Exception:
        pass

    return all_items


def fetch_and_filter(
    days_back: int = 7,
    include_media: bool = True,
    gemini_client=None,
    prefetched_items: list = None,
) -> list[dict]:
    """
    Fetch all feeds (or reuse prefetched_items), then run three-layer relevance filter.

    Government feed bypass rules (STEP_2B):
      - Infrastructure/procurement feeds: skip L1 + L2 (already narrowly scoped)
      - Other government feeds (economic/general): skip L1, run L2 + L3

    Args:
        prefetched_items: If provided, skip the fetch step and filter these items
                          directly. Avoids double-fetching when Phase 1 already fetched.

    Returns:
        List of filtered news items likely to describe capital projects.
    """
    if prefetched_items is not None:
        all_items = list(prefetched_items)  # shallow copy to avoid mutating caller's list
    else:
        all_items = fetch_all_feeds(days_back=days_back, include_media=include_media)
    if not all_items:
        return []

    # Pre-filter step 1: Metadata tagging (zero API cost)
    try:
        from metadata_tagger import tag_batch
        tag_batch(all_items)
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] Metadata tagging failed in fetch_and_filter: {e}")

    # Pre-filter step 2: enhance short/missing snippets via sumy (zero API cost)
    try:
        from snippet_enhancer import enhance_batch
        all_items = enhance_batch(
            all_items, url_key="url", snippet_key="summary",
            max_enhance=50, skip_gov=True,
        )
    except ImportError:
        print("[WARN] sumy not installed, skipping snippet enhancement")
    except Exception as e:
        print(f"[WARN] Snippet enhancement failed, continuing with original snippets: {e}")

    # Pre-filter step 3: Canadian relevance filter for global newswire feeds
    # GlobeNewswire and PRNewswire are global — drop non-Canadian articles
    # before they burn LLM classification tokens. Canada Newswire is already
    # Canadian-only so it skips this check.
    pre_newswire = len(all_items)
    all_items = [
        item for item in all_items
        if not _is_newswire_article(item) or is_canadian_content(item)
    ]
    newswire_dropped = pre_newswire - len(all_items)
    if newswire_dropped:
        print(f"  [RSS] Newswire Canadian filter: dropped {newswire_dropped} non-Canadian articles")

    # Pre-filter step 4: Regulatory relevance filter for CanLII feeds
    # CanLII feeds include many non-project decisions (family law, criminal, etc.)
    # Require >=2 keyword matches before entering the main pipeline
    regulatory_items = [i for i in all_items if i.get('source_level') == 'regulatory']
    non_regulatory = [i for i in all_items if i.get('source_level') != 'regulatory']
    if regulatory_items:
        from article_filter import is_regulatory_relevant, extract_regulatory_signal
        pre_reg = len(regulatory_items)
        regulatory_items = [i for i in regulatory_items if is_regulatory_relevant(i)]
        reg_dropped = pre_reg - len(regulatory_items)
        if reg_dropped:
            print(f"  [RSS] Regulatory pre-filter: {pre_reg} -> {len(regulatory_items)} "
                  f"(dropped {reg_dropped} non-project legal decisions)")
        # Extract status signals and attach to articles for downstream use
        for item in regulatory_items:
            signal = extract_regulatory_signal(item)
            if signal:
                item['regulatory_signal'] = signal
        sig_count = sum(1 for i in regulatory_items if i.get('regulatory_signal'))
        if sig_count:
            print(f"  [RSS] Regulatory signals: {sig_count} status signals extracted")
    all_items = non_regulatory + regulatory_items

    # Split into four tiers: infra-gov (+ key_people), regulatory, other-gov, media
    _INFRA_CATS = {'infrastructure', 'procurement', 'key_people'}
    gov_infra = [i for i in all_items
                 if i.get('source_level') not in ('media', 'regulatory')
                 and (i.get('category') in _INFRA_CATS
                      or i.get('source_level') == 'key_people')]
    gov_regulatory = [i for i in all_items
                      if i.get('source_level') == 'regulatory']
    gov_other = [i for i in all_items
                 if i.get('source_level') not in ('media', 'key_people', 'regulatory')
                 and i.get('category') not in _INFRA_CATS]
    media_items = [i for i in all_items if i.get('source_level') == 'media']

    from article_filter import filter_articles

    # Infrastructure/procurement gov feeds: skip L1 + L2, only run L3
    filtered_gov_infra = filter_articles(
        gov_infra, gemini_client=gemini_client,
        skip_layer1=True, skip_layer2=True,
    ) if gov_infra else []

    # Regulatory feeds: already pre-filtered for relevance, skip L1 + L2
    filtered_regulatory = filter_articles(
        gov_regulatory, gemini_client=gemini_client,
        skip_layer1=True, skip_layer2=True,
    ) if gov_regulatory else []

    # Other government feeds: skip L1, run L2 + L3
    filtered_gov_other = filter_articles(
        gov_other, gemini_client=gemini_client,
        skip_layer1=True, skip_layer2=False,
    ) if gov_other else []

    # Media feeds: run all three layers
    filtered_media = filter_articles(
        media_items, gemini_client=gemini_client,
        skip_layer1=False, skip_layer2=False,
    ) if media_items else []

    combined = filtered_gov_infra + filtered_regulatory + filtered_gov_other + filtered_media
    print(f"  [RSS] After filter: {len(combined)} project-relevant items "
          f"(gov-infra={len(filtered_gov_infra)}, regulatory={len(filtered_regulatory)}, "
          f"gov-other={len(filtered_gov_other)}, media={len(filtered_media)})")
    return combined


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
        item_url = item.get('url') or item.get('link') or ''
        url_tag = f"\n  URL: {item_url}" if item_url else ''
        lines.append(
            f"• [{item['source_name']}{prov_tag}{date_tag}] {item['title']}\n"
            f"  {item['summary'][:220]}{url_tag}"
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
    Prints a detailed report grouped by level/category.
    Returns a dict: {feed_id: {'status': str, 'http': int, 'items': int}}
    """
    results: dict[str, dict] = {}

    print(f"\n{'='*66}")
    print(f"  RSS FEED TEST — {len(ALL_FEEDS)} feeds")
    print(f"{'='*66}\n")

    by_level: dict[str, list] = {}
    for fid, meta in ALL_FEEDS.items():
        level = meta.get('level', 'unknown')
        by_level.setdefault(level, []).append((fid, meta))

    for level in sorted(by_level.keys()):
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
    test_count = sum(1 for fid, meta in ALL_FEEDS.items() if meta.get('test'))
    print(f"\n  {'='*62}")
    print(f"  SUMMARY: {ok}/{len(results)} feeds live  |  {bad} dead/broken/no-content")
    if test_count:
        test_ok = sum(1 for fid in results if ALL_FEEDS.get(fid, {}).get('test')
                       and results[fid]['status'] == 'ok')
        print(f"  TEST FEEDS: {test_ok}/{test_count} working (marked 'test' in rss_feeds.json)")
    print(f"  {'='*62}\n")
    return results
