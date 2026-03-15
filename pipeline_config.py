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
# Claude Sonnet 4.6 — ALL reasoning and writing (~$55/year)
#   Executive summary, national analysis, global vectors, indicator context,
#   industry/provincial analysis, project extraction, citation checks,
#   gap analysis, extraction recovery, dedup QA, signal investigation.
#
# Gemini 2.5 Flash — Mechanical high-volume tasks (FREE)
#   Classification, extraction, JSON repair, rehash detection.
#
# No AI — All API calls, URL verification, RSS monitoring,
#   deduplication, status normalization, threshold filtering, assembly, writes.

SONNET_MODEL = os.environ.get('SONNET_MODEL', 'claude-sonnet-4-6')
OPUS_MODEL = os.environ.get('OPUS_MODEL', 'claude-opus-4-6')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

# Per-model cost rates (USD per million tokens)
MODEL_RATES = {
    'claude-opus-4-6':   {'input': 15.0, 'output': 75.0},
    'claude-sonnet-4-6': {'input': 3.0,  'output': 15.0},
}


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
# SECTOR CANONICAL MAP — maps government source categories to 18 pipeline sectors
# Used by backfill_projects.py to normalize sector values from all 6 sources
# ══════════════════════════════════════════════════════════════════════════════

SECTOR_CANONICAL_MAP = {
    # ── Infrastructure Canada categories ──
    "public transit": "infrastructure",
    "highways and roads": "infrastructure",
    "active transportation": "infrastructure",
    "marine": "transport_logistics",
    "regional and local airports": "transport_logistics",
    "shortline rail": "transport_logistics",
    "border infrastructure": "infrastructure",
    "drinking water": "infrastructure",
    "wastewater": "infrastructure",
    "solid waste management": "environment",
    "brownfield remediation and redevelopment": "environment",
    "green energy": "power_energy",
    "healthcare infrastructure": "healthcare",
    "education, training and childcare": "education",
    "culture": "tourism_culture",
    "recreation": "tourism_culture",
    "sport": "tourism_culture",
    "tourism": "tourism_culture",
    "affordable and temporary housing": "residential",
    "broadband and connectivity": "telecom",
    "disaster mitigation": "infrastructure",
    "innovation": "manufacturing",
    "capacity building": "government",
    "administration, emergency and public works": "government",
    "ventilation": "government",
    "other": "infrastructure",

    # ── Ontario Builds categories ──
    "communities": "infrastructure",
    "transit": "infrastructure",
    "roads and bridges": "infrastructure",
    "health care": "healthcare",
    "education": "education",
    "child care": "education",
    "recreation": "tourism_culture",

    # ── NRCan sectors ──
    "energy": "power_energy",
    "mining": "mining",
    "forest": "forestry",

    # ── BC MPI categories ──
    "manufacturing": "manufacturing",
    "mining & oil & gas extraction": "oil_gas",
    "other services": "commercial_mixed",
    "public services": "government",
    "residential/commercial": "residential",
    "transportation & warehousing": "transport_logistics",
    "utilities (incl sewage treatment)": "power_energy",
    # BC MPI PROJECT_TYPE granular
    "residential": "residential",
    "commercial": "commercial_mixed",
    "commercial/industrial": "manufacturing",
    "commercial/retail": "commercial_mixed",
    "retail": "commercial_mixed",
    "accommodation": "tourism_culture",
    "accommodation/commercial": "commercial_mixed",
    "accommodation/residential": "residential",
    "accommodation/retail": "commercial_mixed",
    "mixed use - commercial/retail/ industrial/residential": "commercial_mixed",
    "mixed use - residential/commercial/retail/ industrial": "commercial_mixed",
    "residential/accommodation": "residential",
    "residential/commercial": "residential",
    "residential/commercial/retail": "commercial_mixed",
    "residential/retail": "residential",
    "retail/residential": "residential",
    "resort": "tourism_culture",
    "resort/residential": "tourism_culture",
    "seniors housing": "residential",
    "seniors housing": "residential",
    "social housing": "residential",
    "educational services": "education",
    "health care and social assistance": "healthcare",
    "public administration": "government",
    "arts, entertainment & recreation": "tourism_culture",
    "airport operations": "transport_logistics",
    "port and harbour facilities": "transport_logistics",
    "general warehousing and storage": "transport_logistics",
    "transportation": "transport_logistics",
    "oil and gas extraction": "oil_gas",
    "crude oil pipeline": "oil_gas",
    "natural gas pipeline": "oil_gas",
    "natural gas processing": "oil_gas",
    "liquefied natural gas": "oil_gas",
    "liquefied natural gas - natural gas pipeline": "oil_gas",
    "petrochemical manufacturing": "oil_gas",
    "sewage treatment facilities": "infrastructure",
    "water, sewage, and other systems": "infrastructure",
    "utilities": "power_energy",
    "wood products manufacturing": "forestry",
    "skiing facilities": "tourism_culture",
    "skiing facilities/residential": "tourism_culture",

    # ── Alberta sectors ──
    "oil and gas": "oil_gas",
    "pipeline": "oil_gas",
    "power": "power_energy",
    "industrial": "manufacturing",
    "institutional": "government",
    "infrastructure": "infrastructure",
    "mixed-use": "commercial_mixed",
    "tourism / recreation": "tourism_culture",

    # ── Quebec sectors ──
    "administration gouvernementale": "government",
    "culture": "tourism_culture",
    "developpement du sport": "tourism_culture",
    "développement du sport": "tourism_culture",
    "developpement du territoire nordique et des communautes autochtones": "indigenous",
    "développement du territoire nordique et des communautés autochtones": "indigenous",
    "enseignement superieur": "education",
    "enseignement supérieur": "education",
    "environnement": "environment",
    "logements sociaux et communautaires": "residential",
    "municipalites": "infrastructure",
    "municipalités": "infrastructure",
    "recherche": "education",
    "reseau routier": "infrastructure",
    "réseau routier": "infrastructure",
    "sante et services sociaux": "healthcare",
    "santé et services sociaux": "healthcare",
    "tourisme et activites recreatives": "tourism_culture",
    "tourisme et activités récréatives": "tourism_culture",
    "transport collectif": "infrastructure",
    "transports maritime, aerien, ferroviaire et autres": "transport_logistics",
    "transports maritime, aérien, ferroviaire et autres": "transport_logistics",
    "education": "education",
    "éducation": "education",
}

# Province GDP thresholds as a simple code → value dict (for filtering)
PROVINCE_GDP_THRESHOLDS = {
    "ON": 500_000_000, "QC": 250_000_000, "AB": 200_000_000, "BC": 175_000_000,
    "SK": 45_000_000, "MB": 40_000_000, "NS": 25_000_000, "NB": 20_000_000,
    "NL": 17_000_000, "PE": 5_000_000, "YT": 3_000_000, "NT": 3_000_000,
    "NU": 3_000_000, "CA": 500_000_000,
}


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

# Tier 3B — Perplexity REMOVED. Do not re-enable.
PERPLEXITY_ENABLED = False


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

# GDELT disabled — module never integrated into pipeline
# GDELT_MAX_ARTICLES       = int(os.environ.get('GDELT_MAX_ARTICLES', '195'))
RSS_MAX_ARTICLES         = int(os.environ.get('RSS_MAX_ARTICLES', '100'))
WAYBACK_MAX_SNAPSHOTS_SEED = int(os.environ.get('WAYBACK_MAX_SNAPSHOTS_SEED', '800'))

# Claude API cost cap per pipeline run (USD).
# Opus 4.6: $15/MTok input, $75/MTok output (calls 1-3, briefing, market, microscope).
# Sonnet 4.6: $3/MTok input, $15/MTok output (call 4, gap analysis, dedup QA).
# Normal run ≈ $3-5 with Opus writing. Cap prevents runaway costs.
CLAUDE_COST_CAP_USD = float(os.environ.get('CLAUDE_COST_CAP_USD', '8.00'))
