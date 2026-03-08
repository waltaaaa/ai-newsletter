"""
key_people_tracker.py — Monitor key decision-makers for project and policy signals.

Tracks federal ministers, provincial premiers, municipal mayors, and crown corp
leaders via RSS feeds. Their announcements bypass keyword filtering (government
source bypass) since anything these officials say about projects is high-authority.

Integration:
  - RSS feeds from key people are added to rss_monitor.py's feed list
  - Processed through government source bypass (skip_layer1=True, skip_layer2=True)
  - Google Alerts terms generated for X/Twitter proxy monitoring
"""

import logging

logger = logging.getLogger(__name__)

# ── Key people database ────────────────────────────────────────────────────

KEY_PEOPLE = {
    "federal": [
        {
            "name": "Prime Minister of Canada",
            "role": "PM",
            "scope": "national",
            "rss_sources": ["https://pm.gc.ca/en/news/rss"],
            "relevance": "Federal infrastructure spending, housing policy, trade policy, Indigenous reconciliation",
        },
        {
            "name": "Minister of Finance",
            "role": "Finance Minister",
            "scope": "national",
            "rss_sources": [
                "https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentfinance&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Department%20of%20Finance%20Canada",
            ],
            "relevance": "Federal budget, tax incentives, economic policy",
        },
        {
            "name": "Minister of Housing and Infrastructure",
            "role": "Housing/Infrastructure Minister",
            "scope": "national",
            "rss_sources": [
                "https://api.io.canada.ca/io-server/gc/news/en/v2?dept=officeinfrastructure&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Infrastructure%20Canada",
            ],
            "relevance": "Infrastructure funding, housing programs, HAF, ACLA",
        },
        {
            "name": "Minister of Energy and Natural Resources",
            "role": "NRCan Minister",
            "scope": "national",
            "rss_sources": [
                "https://api.io.canada.ca/io-server/gc/news/en/v2?dept=naturalresourcescanada&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Natural%20Resources%20Canada",
            ],
            "relevance": "Energy projects, mining approvals, critical minerals strategy",
        },
        {
            "name": "Minister of Transport",
            "role": "Transport Minister",
            "scope": "national",
            "rss_sources": [
                "https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentoftransport&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=50&format=atom&atomtitle=Transport%20Canada",
            ],
            "relevance": "Port expansions, airport upgrades, rail projects, CER decisions",
        },
    ],

    "premiers": [
        {"name": "Premier of Ontario", "province": "ON",
         "rss_sources": ["https://news.ontario.ca/en/rss"]},
        {"name": "Premier of Quebec", "province": "QC",
         "rss_sources": ["https://www.quebec.ca/nouvelles/rss"]},
        {"name": "Premier of Alberta", "province": "AB",
         "rss_sources": ["https://www.alberta.ca/release.cfm?xID=894838DC5D411-C981-BAB5-C04B78F2CCFE3B39"]},
        {"name": "Premier of British Columbia", "province": "BC",
         "rss_sources": ["https://news.gov.bc.ca/feed"]},
        {"name": "Premier of Saskatchewan", "province": "SK",
         "rss_sources": ["https://www.saskatchewan.ca/rss"]},
        {"name": "Premier of Manitoba", "province": "MB",
         "rss_sources": ["https://news.gov.mb.ca/news/rss"]},
        {"name": "Premier of Nova Scotia", "province": "NS",
         "rss_sources": ["https://novascotia.ca/news/rss/"]},
        {"name": "Premier of New Brunswick", "province": "NB",
         "rss_sources": ["https://www2.gnb.ca/content/gnb/en/news.rss"]},
        {"name": "Premier of Newfoundland and Labrador", "province": "NL",
         "rss_sources": ["https://www.gov.nl.ca/releases/feed/"]},
        {"name": "Premier of PEI", "province": "PE",
         "rss_sources": ["https://www.princeedwardisland.ca/en/news/rss.xml"]},
        {"name": "Premier of Yukon", "province": "YT",
         "rss_sources": ["https://yukon.ca/en/news/rss.xml"]},
        {"name": "Premier of NWT", "province": "NT",
         "rss_sources": ["https://www.gov.nt.ca/en/newsroom/rss.xml"]},
        {"name": "Premier of Nunavut", "province": "NU",
         "rss_sources": ["https://gov.nu.ca/news/feed"]},
    ],

    "mayors": [
        {"name": "Mayor of Toronto", "city": "Toronto", "province": "ON", "rss_sources": []},
        {"name": "Mayor of Montreal", "city": "Montreal", "province": "QC", "rss_sources": []},
        {"name": "Mayor of Vancouver", "city": "Vancouver", "province": "BC", "rss_sources": []},
        {"name": "Mayor of Calgary", "city": "Calgary", "province": "AB", "rss_sources": []},
        {"name": "Mayor of Edmonton", "city": "Edmonton", "province": "AB", "rss_sources": []},
        {"name": "Mayor of Ottawa", "city": "Ottawa", "province": "ON", "rss_sources": []},
        {"name": "Mayor of Winnipeg", "city": "Winnipeg", "province": "MB", "rss_sources": []},
        {"name": "Mayor of Quebec City", "city": "Quebec City", "province": "QC", "rss_sources": []},
        {"name": "Mayor of Hamilton", "city": "Hamilton", "province": "ON", "rss_sources": []},
        {"name": "Mayor of Halifax", "city": "Halifax", "province": "NS", "rss_sources": []},
        {"name": "Mayor of Saskatoon", "city": "Saskatoon", "province": "SK", "rss_sources": []},
        {"name": "Mayor of Regina", "city": "Regina", "province": "SK", "rss_sources": []},
        {"name": "Mayor of St. John's", "city": "St. John's", "province": "NL", "rss_sources": []},
        {"name": "Mayor of Fredericton", "city": "Fredericton", "province": "NB", "rss_sources": []},
        {"name": "Mayor of Charlottetown", "city": "Charlottetown", "province": "PE", "rss_sources": []},
    ],

    "crown_corp_leaders": [
        {"name": "CEO of Canada Infrastructure Bank",
         "relevance": "CIB investment decisions", "rss_sources": []},
        {"name": "CEO of CMHC",
         "relevance": "Housing programs, affordable housing funding", "rss_sources": []},
        {"name": "President of Metrolinx", "province": "ON",
         "relevance": "Ontario transit projects", "rss_sources": []},
        {"name": "CEO of Hydro-Québec", "province": "QC",
         "relevance": "Quebec energy projects", "rss_sources": []},
        {"name": "CEO of BC Hydro", "province": "BC",
         "relevance": "BC energy projects, Site C", "rss_sources": []},
        {"name": "President of VIA Rail",
         "relevance": "HFR project", "rss_sources": []},
    ],
}

# Keywords that indicate a project or policy announcement
ANNOUNCEMENT_KEYWORDS = [
    "announce", "invest", "fund", "approve", "construction", "build",
    "project", "million", "billion", "infrastructure", "development",
    "redevelopment", "expansion", "renovation", "transit", "housing",
    "hospital", "school", "mine", "pipeline", "facility", "plant",
    "breaking ground", "shovels in the ground", "green light",
    "budget", "capital plan", "economic statement",
    # French
    "annoncer", "investir", "financer", "approuver", "construction",
    "projet", "millions", "milliards", "infrastructure",
]


def get_key_people_feeds():
    """Return RSS feed configs for key people, compatible with rss_monitor.

    Returns list of dicts with: id, url, name, level, province, category.
    Only includes people who have working RSS sources.
    """
    feeds = []
    seen_urls = set()

    for category, people in KEY_PEOPLE.items():
        for person in people:
            for feed_url in person.get("rss_sources", []):
                if not feed_url or feed_url in seen_urls:
                    continue
                seen_urls.add(feed_url)

                fid = f"kp_{person['name'].lower().replace(' ', '_')[:30]}"
                feeds.append({
                    "id": fid,
                    "url": feed_url,
                    "name": person.get("name", "Key Person"),
                    "level": "key_people",
                    "province": person.get("province"),
                    "category": "key_people",
                    "source_type": "key_person",
                    "authority": "government",
                    "bypass_filters": True,
                })

    logger.info(f"Key people feeds: {len(feeds)} with RSS sources")
    return feeds


def generate_people_google_alerts():
    """Generate Google Alert search terms for key people.

    Returns list of search query strings to set up at google.com/alerts.
    """
    alerts = []

    for category, people in KEY_PEOPLE.items():
        for person in people:
            name = person.get("name", "")
            if not name:
                continue
            # Only generate alerts for categories where RSS is limited
            if category in ("mayors", "crown_corp_leaders"):
                alerts.append(
                    f'"{name}" announces OR investment OR construction '
                    f'OR infrastructure OR project OR million OR billion Canada'
                )

    return alerts
