"""
pipeline_config.py — Core configuration for CAN-MACRO dashboard pipeline.

Central place for: model routing, project schema, GDP thresholds,
province/NAICS definitions, status normalization, deduplication,
newsletter section schema, and Gemini search flag.

Imported by update_dashboard.py, seed_projects_v2.py, and other modules.
"""

import os
import re
from datetime import date
from difflib import SequenceMatcher
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

TODAY = date.today().isoformat()

# ══════════════════════════════════════════════════════════════════════════════
# MODEL ROUTING
# ══════════════════════════════════════════════════════════════════════════════
#
# Opus 4.5 — Flagship writing only (~$7/year)
#   Executive summary (500w), national analysis (500w), global vectors (300w x4),
#   indicator context lines. Paragraph-length prose where narrative quality matters.
#
# Sonnet 4.5 — Extraction + secondary writing + citation checks (~$25/year)
#   Project extraction from GDELT articles and RSS press releases.
#   Provincial writing (bullets). Industry writing (bullets). Citation spot-checks.
#   Catches 10-15% more projects than Flash on ambiguous extraction.
#
# Gemini 2.5 Flash — Mechanical high-volume tasks (~$5/year)
#   Wayback snapshot parsing, JSON repair, unsourced claims detection.
#   Structured extraction at 10x lower cost.
#
# No AI — All API calls, URL verification, Wayback archival, RSS monitoring,
#   deduplication, status normalization, threshold filtering, assembly, Firestore writes.

OPUS_MODEL   = os.environ.get('OPUS_MODEL',   'claude-opus-4-6')
SONNET_MODEL = os.environ.get('SONNET_MODEL', 'claude-sonnet-4-6')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')


# ══════════════════════════════════════════════════════════════════════════════
# ELIGIBLE PROJECT STATUSES
# ══════════════════════════════════════════════════════════════════════════════

ELIGIBLE_STATUSES = {
    "Proposed", "Under Review", "Approved",
    "Under Construction", "Paused", "Expansion",
}

# Exclude: Completed, Cancelled, Abandoned, Operational (unless major expansion)


# ══════════════════════════════════════════════════════════════════════════════
# STATUS NORMALIZATION
# ══════════════════════════════════════════════════════════════════════════════

def norm_status(raw: str) -> str:
    """Map raw status string to one of the 6 eligible statuses."""
    raw_lower = raw.lower().strip()
    if any(k in raw_lower for k in [
        "propos", "planned", "conceptual", "pre-feasibility", "early stage", "filed",
    ]):
        return "Proposed"
    if any(k in raw_lower for k in [
        "review", "assessment", "evaluation", "regulatory", "consultation", "hearing",
    ]):
        return "Under Review"
    if any(k in raw_lower for k in [
        "approved", "authorized", "permitted", "licensed", "sanctioned", "green light",
    ]):
        return "Approved"
    if any(k in raw_lower for k in [
        "construction", "building", "underway", "in progress", "site prep",
        "breaking ground", "under development",
    ]):
        return "Under Construction"
    if any(k in raw_lower for k in [
        "pause", "suspend", "halt", "delay", "on hold", "deferred",
    ]):
        return "Paused"
    if any(k in raw_lower for k in [
        "expan", "retrofit", "upgrade", "moderniz", "refurbish", "retool",
    ]):
        return "Expansion"
    return "Proposed"  # default


# ══════════════════════════════════════════════════════════════════════════════
# NAICS 2-DIGIT SECTOR MAP (StatCan Table 36-10-0434-02)
# ══════════════════════════════════════════════════════════════════════════════

NAICS_MAP = {
    "11":    "Agriculture, forestry, fishing and hunting",
    "21":    "Mining, quarrying, and oil and gas extraction",
    "22":    "Utilities",
    "23":    "Construction",
    "31-33": "Manufacturing",
    "41":    "Wholesale trade",
    "44-45": "Retail trade",
    "48-49": "Transportation and warehousing",
    "51":    "Information and cultural industries",
    "52":    "Finance and insurance",
    "53":    "Real estate and rental and leasing",
    "54":    "Professional, scientific and technical services",
    "55":    "Management of companies and enterprises",
    "56":    "Administrative and support, waste management and remediation services",
    "61":    "Educational services",
    "62":    "Health care and social assistance",
    "71":    "Arts, entertainment and recreation",
    "72":    "Accommodation and food services",
    "81":    "Other services (except public administration)",
    "91":    "Public administration",
}


# ══════════════════════════════════════════════════════════════════════════════
# PROVINCES + GDP-PROPORTIONAL THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

PROVINCES = [
    {"name": "Ontario",                       "gdelt": "Ontario",               "threshold": "$500M", "threshold_val": 500_000_000},
    {"name": "Quebec",                        "gdelt": "Quebec",                "threshold": "$250M", "threshold_val": 250_000_000},
    {"name": "Alberta",                       "gdelt": "Alberta",               "threshold": "$200M", "threshold_val": 200_000_000},
    {"name": "British Columbia",              "gdelt": "British Columbia",      "threshold": "$175M", "threshold_val": 175_000_000},
    {"name": "Saskatchewan",                  "gdelt": "Saskatchewan",          "threshold": "$45M",  "threshold_val":  45_000_000},
    {"name": "Manitoba",                      "gdelt": "Manitoba",              "threshold": "$40M",  "threshold_val":  40_000_000},
    {"name": "Nova Scotia",                   "gdelt": "Nova Scotia",           "threshold": "$25M",  "threshold_val":  25_000_000},
    {"name": "New Brunswick",                 "gdelt": "New Brunswick",         "threshold": "$20M",  "threshold_val":  20_000_000},
    {"name": "Newfoundland and Labrador",     "gdelt": "Newfoundland Labrador", "threshold": "$17M",  "threshold_val":  17_000_000},
    {"name": "Prince Edward Island",          "gdelt": "Prince Edward Island",  "threshold": "$5M",   "threshold_val":   5_000_000},
    {"name": "Yukon",                         "gdelt": "Yukon",                 "threshold": "$3M",   "threshold_val":   3_000_000},
    {"name": "Northwest Territories",         "gdelt": "Northwest Territories", "threshold": "$3M",   "threshold_val":   3_000_000},
    {"name": "Nunavut",                       "gdelt": "Nunavut",              "threshold": "$3M",   "threshold_val":   3_000_000},
]


# ══════════════════════════════════════════════════════════════════════════════
# NAICS INFERENCE (from project name / sector text)
# ══════════════════════════════════════════════════════════════════════════════

def infer_naics(name: str, sector: str = '') -> tuple[str, str]:
    """Guess NAICS 2-digit code from project name/sector. Returns (code, name)."""
    t = (name + ' ' + (sector or '')).lower()
    if any(x in t for x in ('mine', 'mining', 'oil', 'gas', 'lng', 'pipeline', 'potash',
                              'lithium', 'copper', 'gold', 'nickel', 'coal', 'quarry')):
        return '21', NAICS_MAP['21']
    if any(x in t for x in ('wind', 'solar', 'hydro', 'nuclear', 'utility', 'power plant',
                              'hydrogen', 'carbon capture', 'transmission', 'dam', 'smr')):
        return '22', NAICS_MAP['22']
    if any(x in t for x in ('transit', 'lrt', 'subway', 'brt', 'rapid transit', 'highway',
                              'bridge', 'road', 'port', 'airport', 'rail', 'pipeline trans',
                              'interchange', 'terminal', 'logistics', 'warehouse')):
        return '48-49', NAICS_MAP['48-49']
    if any(x in t for x in ('hospital', 'health', 'medical', 'clinic', 'care', 'long-term')):
        return '62', NAICS_MAP['62']
    if any(x in t for x in ('school', 'university', 'college', 'campus', 'institute')):
        return '61', NAICS_MAP['61']
    if any(x in t for x in ('data centre', 'data center', 'semiconductor', 'ai campus',
                              'telecom', 'broadband', 'fibre', 'fiber', '5g')):
        return '51', NAICS_MAP['51']
    if any(x in t for x in ('manufacturing', 'factory', 'plant', 'assembly', 'steel mill',
                              'auto plant', 'battery', 'ev ', 'aerospace', 'pharma')):
        return '31-33', NAICS_MAP['31-33']
    if any(x in t for x in ('housing', 'residential', 'apartment', 'condo', 'rental',
                              'affordable', 'mixed-use', 'tower')):
        return '53', NAICS_MAP['53']
    if any(x in t for x in ('farm', 'agriculture', 'forestry', 'aquaculture', 'agri')):
        return '11', NAICS_MAP['11']
    if any(x in t for x in ('military', 'defence', 'defense', 'dnd', 'base', 'correctional',
                              'prison', 'government building', 'border', 'embassy')):
        return '91', NAICS_MAP['91']
    if any(x in t for x in ('stadium', 'arena', 'casino', 'entertainment', 'cultural',
                              'museum', 'concert', 'recreation', 'theme park')):
        return '71', NAICS_MAP['71']
    if any(x in t for x in ('hotel', 'resort', 'convention', 'conference center', 'restaurant')):
        return '72', NAICS_MAP['72']
    if any(x in t for x in ('waste', 'recycling', 'remediation', 'treatment plant', 'landfill')):
        return '56', NAICS_MAP['56']
    if any(x in t for x in ('shopping', 'retail', 'mall', 'fulfillment')):
        return '44-45', NAICS_MAP['44-45']
    if any(x in t for x in ('research', 'lab', 'innovation', 'r&d')):
        return '54', NAICS_MAP['54']
    if any(x in t for x in ('commercial', 'office', 'corporate', 'headquarters')):
        return '53', NAICS_MAP['53']
    if 'construction' in t or 'infrastructure' in t:
        return '23', NAICS_MAP['23']
    return '23', NAICS_MAP['23']  # default: construction


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION
# ══════════════════════════════════════════════════════════════════════════════

def norm_key(name: str, province: str) -> str:
    """Normalize a project name + province into a dedup key."""
    n = re.sub(r'[^a-z0-9]', '', name.lower())
    p = re.sub(r'[^a-z0-9]', '', province.lower())
    return f"{n}__{p}"


def fuzzy_match(new_name: str, existing_names: list[str], threshold: float = 0.85) -> str | None:
    """Return first fuzzy-matched existing name, or None if no match at threshold."""
    nl = new_name.lower()
    for ex in existing_names:
        if SequenceMatcher(None, nl, ex.lower()).ratio() >= threshold:
            return ex
    return None


def parse_value(val_str: str) -> float | None:
    """Parse '$1.2B' or '$350M' to float. Returns None on failure."""
    if not val_str or val_str.strip().lower() in ('not disclosed', 'unknown', ''):
        return None
    try:
        s = val_str.replace(',', '').strip()
        m = re.match(r'\$?([\d.]+)\s*(B|M|K)?', s, re.IGNORECASE)
        if not m:
            return None
        num = float(m.group(1))
        unit = (m.group(2) or '').upper()
        if unit == 'B':
            return num * 1e9
        elif unit == 'M':
            return num * 1e6
        elif unit == 'K':
            return num * 1e3
        return num
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT SCHEMA (Firestore /projects)
# ══════════════════════════════════════════════════════════════════════════════
#
# Required fields:
#   name              : str — Exact name from source
#   province          : str — Province/territory name
#   cma               : str — Census Metropolitan Area or region
#   sector            : str — Primary sector description
#   naics_code        : str — 2-digit NAICS code
#   naics_name        : str — NAICS sector name from StatCan table
#   tags              : list[str] — Keywords
#   value             : str — Dollar value from source or 'Not disclosed'
#   status            : str — One of ELIGIBLE_STATUSES
#   proponent         : str — Company or government body
#   confidence        : str — Always 'verified'
#   discovery_source  : str — iaac_registry | bc_eao | nrcan | infrastructure_canada |
#                              buyandsell | provincial_ea | gdelt_news | rss_feed
#   source_url_quality: str — 'direct' | 'relevant'
#   firstTracked      : str — ISO date
#   lastUpdated       : str — ISO date
#   lastSeen          : str — ISO date
#   history_backfilled: bool — True if Wayback snapshots were added
#   history_earliest_date: str — ISO date of earliest known snapshot
#   statusHistory     : list[dict] — Each entry:
#       status        : str
#       date          : str — ISO date
#       detail        : str — 2-3 sentences from source
#       source:
#           title         : str — Exact headline or registry page title
#           url           : str — Direct link to specific page
#           archive_url   : str — Wayback Machine archive URL (if available)
#           type          : str — article | government | api | press_release | registry
#           verified      : bool
#           verified_date : str — ISO date


def make_project(
    name: str,
    province: str,
    status: str,
    source_url: str,
    discovery_source: str,
    naics_code: str = '',
    naics_name: str = '',
    value: str = 'Not disclosed',
    proponent: str = '',
    cma: str = '',
    tags: list | None = None,
    detail: str = '',
    source_title: str = '',
    source_type: str = 'article',
    archive_url: str = '',
) -> dict:
    """Build a standardized project dict matching the Firestore schema."""
    if not naics_code:
        naics_code, naics_name = infer_naics(name, '')
    elif not naics_name:
        naics_name = NAICS_MAP.get(naics_code, '')

    eligible_status = norm_status(status)
    path_segs = [s for s in urlparse(source_url or '').path.split('/') if s]
    url_quality = 'direct' if len(path_segs) >= 2 else 'relevant'

    return {
        'name':                name.strip(),
        'province':            province,
        'cma':                 cma,
        'sector':              naics_name,
        'naics_code':          naics_code,
        'naics_name':          naics_name,
        'tags':                tags or [],
        'value':               value or 'Not disclosed',
        'status':              eligible_status,
        'proponent':           proponent,
        'confidence':          'verified',
        'discovery_source':    discovery_source,
        'source_url_quality':  url_quality,
        'firstTracked':        TODAY,
        'lastUpdated':         TODAY,
        'lastSeen':            TODAY,
        'history_backfilled':  False,
        'history_earliest_date': '',
        'statusHistory': [{
            'status': eligible_status,
            'date':   TODAY,
            'detail': detail or f'Project in {eligible_status} status as of {TODAY}.',
            'source': {
                'title':         source_title or f'{discovery_source} registry',
                'url':           source_url or '',
                'archive_url':   archive_url,
                'type':          source_type,
                'verified':      True,
                'verified_date': TODAY,
            },
        }],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NEWSLETTER SECTION SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
#
# Every section in the newsletter JSON must include:
#   section       : str — "executive" | "national" | "provincial" | "global" | "industry"
#   content       : str — HTML with <sup>[1]</sup> footnote references
#   sources       : list[dict] — Each:
#       id            : int — Sequential footnote number
#       title         : str — Exact headline or page title
#       url           : str — Direct verified URL
#       archive_url   : str — Wayback archive URL (if available)
#       type          : str — article | government | api | press_release
#       verified      : bool
#       verified_date : str — ISO date
#   citation_audit: dict —
#       total_claims    : int
#       total_cited     : int
#       total_verified  : int
#       removed_claims  : int
#       audit_passed    : bool


# ══════════════════════════════════════════════════════════════════════════════
# DISCOVERY TIER FLAGS
# ══════════════════════════════════════════════════════════════════════════════
#
# Tier 2 — Google News RSS (primary discovery, 759 queries/week)
# Gemini grounded search REMOVED ($136/day cost). Replaced by Google News RSS (free).
# This flag kept for backwards compat — must remain false.
GEMINI_SEARCH_ENABLED = os.environ.get('GEMINI_SEARCH_ENABLED', 'false').lower() == 'true'

# Tier 3B — Perplexity Sonar Pro (monthly gap-fill, --deep-sweep only)
# 13 queries/month, catches projects missed by Tiers 1-3. ~$0.50-0.80/year.
PERPLEXITY_ENABLED = os.environ.get('PERPLEXITY_ENABLED', 'true').lower() == 'true'


# ══════════════════════════════════════════════════════════════════════════════
# CLI FLAGS (for documentation — actual argparse in each script)
# ══════════════════════════════════════════════════════════════════════════════
#
# python update_dashboard.py                    # Weekly: 7-day lookback, new project backfill,
#                                               #   full citation audit, Wayback save all URLs
# python update_dashboard.py --deep-sweep       # Monthly: 12-month GDELT + full registry +
#                                               #   Perplexity gap-fill + re-attempt backfill
# python update_dashboard.py --test-feeds       # Test all RSS URLs, report working/broken
# python update_dashboard.py --seed-projects    # Full project seed + Wayback backfill
# python update_dashboard.py --test-queries     # Dry run GDELT queries, report hit counts
# python update_dashboard.py --audit-citations  # Link rot audit: re-verify ALL URLs in DB,
#                                               #   dead+archive=link_rotted_archived,
#                                               #   dead+no archive=attempt save
# python update_dashboard.py --test-sentiment   # Run sentiment collection only, print results


# ══════════════════════════════════════════════════════════════════════════════
# BUDGETS (from .env)
# ══════════════════════════════════════════════════════════════════════════════

GDELT_MAX_ARTICLES       = int(os.environ.get('GDELT_MAX_ARTICLES', '195'))
RSS_MAX_ARTICLES         = int(os.environ.get('RSS_MAX_ARTICLES', '100'))
WAYBACK_MAX_SNAPSHOTS_SEED = int(os.environ.get('WAYBACK_MAX_SNAPSHOTS_SEED', '800'))
