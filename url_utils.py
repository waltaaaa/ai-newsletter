"""
url_utils.py -- URL validation, normalization, and authority classification.

Cross-cutting utility for STEP_2F: every project must have at least one
verifiable source URL before entering Firestore.
"""

import re
from urllib.parse import urlparse

# Domains known to be real Canadian news/government sources
KNOWN_GOOD_DOMAINS = {
    # National news
    'cbc.ca', 'globalnews.ca', 'thestar.com', 'theglobeandmail.com',
    'nationalpost.com', 'bnnbloomberg.ca', 'reuters.com', 'bloomberg.com',
    # French media
    'ici.radio-canada.ca', 'lapresse.ca', 'ledevoir.com', 'journaldemontreal.com',
    'tvanouvelles.ca', 'lactualite.com',
    # Provincial/regional news
    'calgaryherald.com', 'edmontonjournal.com', 'vancouversun.com',
    'winnipegsun.com', 'winnipegfreepress.com', 'thechronicleherald.ca',
    'telegraphjournal.com', 'acadienouvelle.com', 'thetelegram.com',
    'leaderpost.com', 'thestarphoenix.com', 'timescolonist.com',
    'peicanada.com', 'saltwire.com',
    # Industry
    'dailycommercialnews.com', 'constructconnect.com', 'on-sitemag.com',
    'canadianminingjournal.com', 'northernminer.com', 'mining.com',
    'oilsandsmagazine.com', 'jwnenergy.com', 'renewcanada.net',
    'electricenergyonline.com', 'realestatemagazine.ca',
    # Government (federal)
    'canada.ca', 'gc.ca',
}

# Domain patterns for government sources (match subdomains)
GOV_DOMAIN_PATTERNS = [
    r'\.gc\.ca$', r'\.gov\.\w{2}\.ca$',
    # Anchored so 'radio-canada.ca' / 'notcanada.ca' don't match
    r'(^|\.)canada\.ca$',
    r'news\.ontario\.ca', r'quebec\.ca', r'alberta\.ca', r'gov\.bc\.ca',
    r'saskatchewan\.ca', r'gov\.mb\.ca', r'novascotia\.ca', r'gnb\.ca',
    r'gov\.nl\.ca', r'princeedwardisland\.ca', r'yukon\.ca',
    r'gov\.nt\.ca', r'gov\.nu\.ca',
    # Municipal
    r'toronto\.ca', r'montreal\.ca', r'vancouver\.ca', r'calgary\.ca',
    r'edmonton\.ca', r'ottawa\.ca', r'winnipeg\.ca', r'halifax\.ca',
]

_GOV_PATTERNS_COMPILED = [re.compile(p) for p in GOV_DOMAIN_PATTERNS]


def _extract_domain(url):
    """Extract clean domain from URL."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def validate_url(url):
    """Validate a URL is well-formed and likely real.

    Returns dict with: valid, domain, is_known_source, warning
    """
    if not url or not isinstance(url, str):
        return {"valid": False, "domain": "", "is_known_source": False, "warning": "Empty or non-string URL"}

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {"valid": False, "domain": "", "is_known_source": False, "warning": "Missing scheme or domain"}
        if parsed.scheme not in ("http", "https"):
            return {"valid": False, "domain": parsed.netloc, "is_known_source": False, "warning": f"Bad scheme: {parsed.scheme}"}
    except Exception:
        return {"valid": False, "domain": "", "is_known_source": False, "warning": "URL parse error"}

    domain = _extract_domain(url)

    # Reject Gemini grounded search redirect URLs — not real sources
    if "vertexaisearch.cloud.google.com" in url or "vertexaisearch.cloud.goog" in url:
        return {"valid": False, "domain": domain, "is_known_source": False,
                "warning": "Gemini grounded search redirect URL — not a real source"}

    is_known = domain in KNOWN_GOOD_DOMAINS or any(
        p.search(domain) for p in _GOV_PATTERNS_COMPILED
    )

    warning = None
    if len(url) > 500:
        warning = "Suspiciously long URL"
    elif re.search(r'example\.com|placeholder|test\.', url):
        warning = "Likely placeholder URL"
    elif not re.search(r'\.\w{2,}', domain):
        warning = "Malformed domain"

    return {
        "valid": True,
        "domain": domain,
        "is_known_source": is_known,
        "warning": warning,
    }


def normalize_url(url):
    """Normalize URL for deduplication (strip tracking params, fragments).

    Only strips known tracking parameters. Preserves meaningful query params
    (e.g. StatCan ?pid=...) to avoid merging distinct resources.
    """
    if not url:
        return ""
    try:
        from urllib.parse import parse_qs, urlencode
        parsed = urlparse(url)
        # Only strip known tracking parameters
        _TRACKING_PARAMS = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'gclsrc', 'dclid', 'msclkid',
            'mc_cid', 'mc_eid', 'ref', 'referrer',
            '_ga', '_gl', 'yclid', 'twclid', 'ttclid',
        }
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
            if filtered:
                clean_query = urlencode(filtered, doseq=True)
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{clean_query}"
            else:
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        else:
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return clean.rstrip("/")
    except Exception:
        return url


# Listing/inventory-page URL patterns. A "listing" URL points at a multi-project
# index (registry search page, Major Projects Inventory PDF, budget document) —
# it satisfies the URL hard gate but is NOT a project-specific deep link, and it
# must never be used as a shared-URL dedup signal (hundreds of distinct projects
# legitimately share one inventory URL). Canonical copy — tools/dedup_projects_fuzzy.py
# imports this and keeps a local fallback for standalone use.
_LISTING_URL_PATTERNS = (
    '/major-projects-inventory',
    '/major_projects_inventory',
    '/projects-list',
    '/project-list',
    '/projects.aspx',
    '/registry/projects',
    '/inventory.pdf',
    '/mpi-',
    '/budget-',
    '/budget2',
    '/page=',
    '?search=',
)


def is_listing_url(url):
    """True if the URL is clearly a multi-project listing page, not a specific project page."""
    if not url:
        return True
    u_low = url.lower()
    return any(p in u_low for p in _LISTING_URL_PATTERNS)


def classify_url_quality(url):
    """Classify a single URL as 'deep' | 'listing' | 'homepage' (S2, 2026-06-08 audit).

    - homepage: no meaningful path (e.g. https://example.com/)
    - listing:  matches a known multi-project listing/inventory pattern
    - deep:     anything else — a path that plausibly identifies one resource
    """
    if not url:
        return ''
    try:
        parsed = urlparse(url)
    except Exception:
        return ''
    path = (parsed.path or '').strip('/')
    if not path and not parsed.query:
        return 'homepage'
    if is_listing_url(url):
        return 'listing'
    return 'deep'


def best_link_quality(urls):
    """Best quality across a set of URLs: deep > listing > homepage > ''. """
    rank = {'deep': 3, 'listing': 2, 'homepage': 1, '': 0}
    best = ''
    for u in urls or []:
        q = classify_url_quality(u)
        if rank[q] > rank[best]:
            best = q
        if best == 'deep':
            break
    return best


def classify_source_authority(url):
    """Classify a source URL by authority level for confidence scoring.

    Returns: 'government', 'major_news', 'industry', 'regional_news', 'other'
    """
    if not url:
        return "other"

    domain = _extract_domain(url)

    # Government sources
    if any(p.search(domain) for p in _GOV_PATTERNS_COMPILED):
        return "government"
    if '.gc.ca' in domain or '.gov.' in domain:
        return "government"

    # Major national news
    major_news = {'cbc.ca', 'globalnews.ca', 'thestar.com', 'theglobeandmail.com',
                  'nationalpost.com', 'bnnbloomberg.ca', 'reuters.com', 'bloomberg.com',
                  'ici.radio-canada.ca', 'lapresse.ca', 'ledevoir.com'}
    if domain in major_news:
        return "major_news"

    # Industry publications
    industry = {'dailycommercialnews.com', 'constructconnect.com', 'on-sitemag.com',
                'canadianminingjournal.com', 'northernminer.com', 'renewcanada.net',
                'jwnenergy.com', 'oilsandsmagazine.com'}
    if domain in industry:
        return "industry"

    # Regional news
    if domain in KNOWN_GOOD_DOMAINS:
        return "regional_news"

    return "other"
