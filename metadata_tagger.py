"""
Article metadata tagger — pre-classifies sector and geography using
available metadata signals. Zero API cost, runs before LLM layers.

Signals used (in priority order):
1. Source domain -> sector mapping (highest confidence)
2. RSS feed label from rss_feeds.json (high confidence)
3. RSS category/tag fields (medium confidence)
4. URL path segments (medium confidence)
5. Headline geographic mentions (provinces, cities, CMAs)
6. Headline sector keyword scan (lowest confidence, additive only)

Output: adds `meta_sectors` and `meta_provinces` fields to each article dict.
These are hints, not final classifications — Claude still makes the final call.
"""
import re
from urllib.parse import urlparse

# ── Source domain -> sector mapping ──
# High-confidence: if an article comes from one of these domains, it's almost
# certainly about that sector. Maps to NAICS keys from pipeline_config.py.
DOMAIN_SECTOR_MAP = {
    # Oil & Gas
    "dailyoilbulletin.com": ["oil_gas"],
    "jwnenergy.com": ["oil_gas"],
    "oilsandsmagazine.com": ["oil_gas"],
    "rigzone.com": ["oil_gas"],
    "worldoil.com": ["oil_gas"],
    "petroleumworld.com": ["oil_gas"],
    # Mining
    "mining.com": ["mining"],
    "northernminer.com": ["mining"],
    "miningweekly.com": ["mining"],
    "canadianminingjournal.com": ["mining"],
    "mining-journal.com": ["mining"],
    "intellimines.com": ["mining"],
    # Power & Energy
    "renewableenergyworld.com": ["power_energy"],
    "electricenergyonline.com": ["power_energy"],
    "windpowermonthly.com": ["power_energy"],
    "pv-magazine.com": ["power_energy"],
    "nuclearnewswire.com": ["power_energy"],
    # Infrastructure & Transport
    "infrastructuremagazine.com.au": ["infrastructure"],
    "railwayage.com": ["transport_logistics"],
    "todaystrucking.com": ["transport_logistics"],
    # Construction & Real Estate
    "dailycommercialnews.com": ["infrastructure", "residential", "commercial_mixed"],
    "canadianarchitect.com": ["commercial_mixed", "residential"],
    "renx.ca": ["commercial_mixed", "residential"],
    "storeys.com": ["residential"],
    "buzzbuzzhome.com": ["residential"],
    "livabl.com": ["residential"],
    # Agriculture & Forestry
    "producer.com": ["agriculture"],
    "realagriculture.com": ["agriculture"],
    "grainews.ca": ["agriculture"],
    "canadianforestindustries.ca": ["forestry"],
    # Healthcare
    "healthcarecan.ca": ["healthcare"],
    # Defence
    "canadiandefencereview.com": ["defence"],
    "espritdecorps.ca": ["defence"],
    "vanguardcanada.com": ["defence"],
    # Telecom
    "itworldcanada.com": ["telecom"],
    "cartt.ca": ["telecom"],
    # Manufacturing
    "canadianmanufacturing.com": ["manufacturing"],
    "plant.ca": ["manufacturing"],
}

# ── Province detection ──
# Maps keywords to province codes. Includes major cities and CMAs.
PROVINCE_KEYWORDS = {
    "ON": ["ontario", "toronto", "ottawa", "mississauga", "hamilton", "brampton",
           "kitchener", "waterloo", "london ont", "windsor", "gta", "queen's park"],
    "QC": ["quebec", "montréal", "montreal", "laval", "gatineau", "sherbrooke",
           "trois-rivières", "québec city", "longueuil"],
    "BC": ["british columbia", "vancouver", "victoria", "surrey", "burnaby",
           "kelowna", "nanaimo", "kamloops", "prince george"],
    "AB": ["alberta", "calgary", "edmonton", "red deer", "lethbridge",
           "fort mcmurray", "oil sands", "oilsands", "athabasca"],
    "SK": ["saskatchewan", "saskatoon", "regina", "prince albert", "potash"],
    "MB": ["manitoba", "winnipeg", "brandon", "churchill"],
    "NS": ["nova scotia", "halifax", "dartmouth", "cape breton", "sydney ns"],
    "NB": ["new brunswick", "moncton", "saint john", "fredericton"],
    "NL": ["newfoundland", "labrador", "st. john's", "corner brook", "hibernia",
           "bay du nord", "come by chance"],
    "PE": ["prince edward island", "charlottetown", "pei"],
    "YT": ["yukon", "whitehorse", "dawson city"],
    "NT": ["northwest territories", "yellowknife", "nwt"],
    "NU": ["nunavut", "iqaluit"],
}

# ── Sector keywords for headline scanning ──
# Lower confidence than domain mapping — used as additive signal only.
SECTOR_HEADLINE_KEYWORDS = {
    "oil_gas": ["lng", "pipeline", "refinery", "bitumen", "crude", "petrochemical",
                "natural gas", "fracking", "wellhead", "upgrader"],
    "mining": ["mine ", "mining", "lithium", "nickel", "copper", "gold mine",
               "potash", "rare earth", "smelter", "ore "],
    "infrastructure": ["highway", "bridge", "water treatment", "transit",
                       "interchange", "overpass", "wastewater", "broadband"],
    "power_energy": ["solar farm", "wind farm", "hydroelectric", "nuclear",
                     "battery storage", "grid", "substation", "turbine",
                     "renewable", "electrification", "smr ", "reactor"],
    "residential": ["condo", "condominium", "housing", "apartment", "subdivision",
                    "townhouse", "residential tower", "purpose-built rental"],
    "commercial_mixed": ["office tower", "mixed-use", "shopping centre", "mall ",
                         "retail complex", "commercial development"],
    "manufacturing": ["factory", "plant expansion", "assembly", "manufacturing facility"],
    "transport_logistics": ["airport", "port expansion", "rail ", "terminal",
                           "intermodal", "logistics hub", "shipping"],
    "healthcare": ["hospital", "health centre", "medical campus", "long-term care"],
    "education": ["university", "campus", "college", "school construction"],
    "defence": ["military base", "dnd ", "caf ", "shipbuilding", "frigate",
                "defence procurement"],
    "agriculture": ["grain terminal", "food processing", "agri-food", "greenhouse",
                    "dairy", "canola crushing"],
    "telecom": ["data centre", "data center", "fibre optic", "5g ", "cell tower"],
}

# ── RSS category -> sector mapping ──
# RSS feeds often include category tags. Map common ones to NAICS keys.
CATEGORY_SECTOR_MAP = {
    "energy": ["power_energy", "oil_gas"],
    "oil": ["oil_gas"],
    "gas": ["oil_gas"],
    "mining": ["mining"],
    "metals": ["mining"],
    "real estate": ["residential", "commercial_mixed"],
    "property": ["residential", "commercial_mixed"],
    "housing": ["residential"],
    "construction": ["infrastructure", "residential", "commercial_mixed"],
    "infrastructure": ["infrastructure"],
    "transport": ["transport_logistics"],
    "transportation": ["transport_logistics"],
    "manufacturing": ["manufacturing"],
    "agriculture": ["agriculture"],
    "health": ["healthcare"],
    "defence": ["defence"],
    "defense": ["defence"],
    "technology": ["telecom"],
    "telecom": ["telecom"],
}


def tag_article(article, feed_metadata=None):
    """
    Tag a single article with sector and geography hints from metadata.

    Args:
        article: dict with keys like 'link'/'url', 'title'/'headline',
                 'summary'/'snippet'/'description', 'tags'/'categories'
        feed_metadata: optional dict with feed-level info from rss_feeds.json
                       (e.g. {'sector': 'mining', 'source_type': 'industry_trade'})

    Returns:
        article dict with added 'meta_sectors' and 'meta_provinces' fields.
        Each is a list of strings (NAICS keys for sectors, province codes for geography).
    """
    sectors = []
    provinces = []

    url = article.get("link") or article.get("url") or ""
    title = (article.get("title") or article.get("headline") or "").lower()
    snippet = (article.get("summary") or article.get("snippet") or
               article.get("description") or "").lower()
    text = f"{title} {snippet}"

    # Signal 1: Source domain (highest confidence)
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        for mapped_domain, mapped_sectors in DOMAIN_SECTOR_MAP.items():
            if domain.endswith(mapped_domain):
                sectors.extend(mapped_sectors)
                break
    except Exception:
        pass

    # Signal 2: Feed-level metadata from rss_feeds.json
    if feed_metadata:
        feed_sector = feed_metadata.get("sector")
        if feed_sector and feed_sector not in sectors:
            sectors.append(feed_sector)

    # Signal 3: RSS category/tag fields
    categories = article.get("tags") or article.get("categories") or []
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",")]
    for cat in categories:
        cat_lower = cat.lower().strip()
        if cat_lower in CATEGORY_SECTOR_MAP:
            for s in CATEGORY_SECTOR_MAP[cat_lower]:
                if s not in sectors:
                    sectors.append(s)

    # Signal 4: URL path segments
    try:
        path = urlparse(url).path.lower()
        for sector_key, keywords in SECTOR_HEADLINE_KEYWORDS.items():
            for kw in keywords:
                if kw.strip() in path and sector_key not in sectors:
                    sectors.append(sector_key)
    except Exception:
        pass

    # Signal 5: Geographic mentions in headline + snippet
    for prov_code, keywords in PROVINCE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                if prov_code not in provinces:
                    provinces.append(prov_code)
                break

    # Signal 6: Sector keywords in headline + snippet (lowest confidence, additive)
    for sector_key, keywords in SECTOR_HEADLINE_KEYWORDS.items():
        if sector_key not in sectors:
            for kw in keywords:
                if kw in text:
                    sectors.append(sector_key)
                    break

    article["meta_sectors"] = sectors
    article["meta_provinces"] = provinces
    return article


def tag_batch(articles, feed_metadata=None):
    """
    Tag a batch of articles. Returns the same list with metadata fields added.

    Args:
        articles: list of article dicts
        feed_metadata: optional dict of feed-level metadata (applied to all articles
                       in the batch — use when processing a single feed's output)
    """
    tagged = 0
    for article in articles:
        tag_article(article, feed_metadata)
        if article.get("meta_sectors") or article.get("meta_provinces"):
            tagged += 1

    if articles:
        print(f"[METADATA] Tagged {tagged}/{len(articles)} articles with sector/geography hints")

    return articles
