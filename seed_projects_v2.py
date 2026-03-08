"""
seed_projects_v2.py — Complete rebuild of /projects Firestore collection.

Pipeline:
  0. Backup  — export all /projects docs to timestamped JSON
  1. Wipe    — delete every document in /projects
  2. Tier 1  — Government registry scrapers (IAAC, BC EAO, NRCan, Infra Canada)
  3. Tier 2  — GDELT (~2,047 queries) + Tavily Extract (<=195 URLs) + Claude Sonnet
  4. Tier 3  — Government RSS feed network (rss_feeds.json) + Tavily + Claude Sonnet
  5. Post    — URL verification, threshold, dedup, Wayback archival
  6. Write   — batch-insert all verified projects to Firestore
  7. Report  — save seed_audit_[date].txt

Perplexity gap-fill is DISABLED — hook left in pipeline_config.py.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

import csv
import io
import json
import os
import re
import time
from datetime import date, timedelta, timezone, datetime
from urllib.parse import urlparse

import requests
import anthropic as _anthropic_module
from dotenv import load_dotenv

# ── Step 1 modules ────────────────────────────────────────────────────────────
from pipeline_config import (
    SONNET_MODEL, ELIGIBLE_STATUSES, NAICS_MAP, PROVINCES,
    norm_status as _norm_status, infer_naics as _infer_naics,
    norm_key as _norm_key, fuzzy_match as _fuzzy_match,
    parse_value as _parse_value, make_project as _make_project_cfg,
    TODAY, GDELT_MAX_ARTICLES, RSS_MAX_ARTICLES,
    GEMINI_SEARCH_ENABLED,
)
from url_verify import verify_url as _verify_url_full, quick_reject
from wayback import save_page as _wayback_save, backfill_project_history as _wayback_backfill
from db import init_db, get_all_projects, upsert_project

# ── optional deps ─────────────────────────────────────────────────────────────
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

try:
    from tavily import TavilyClient as _TavilyClient
    _HAS_TAVILY = True
except ImportError:
    _HAS_TAVILY = False

try:
    from gdeltdoc import Filters
    from gdeltdoc.helpers import load_json
    from gdeltdoc.errors import raise_response_error
    from gdeltdoc import GdeltDoc
    _HAS_GDELT = True
except ImportError:
    _HAS_GDELT = False

try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False

# ── load env ──────────────────────────────────────────────────────────────────
load_dotenv()
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
TAVILY_API_KEY     = os.environ.get("TAVILY_API_KEY", "").strip()

# ── DB init (SQLite) ──────────────────────────────────────────────────────────
# NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
# db variable holds the SQLite connection; callers use duck-typing (hasattr conn, 'execute')
db = init_db()

# ── API clients ───────────────────────────────────────────────────────────────
anthropic_client = _anthropic_module.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
tavily_client    = _TavilyClient(api_key=TAVILY_API_KEY) if (_HAS_TAVILY and TAVILY_API_KEY) else None

# ── Watchlist ─────────────────────────────────────────────────────────────────
_WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), 'watchlist.json')
_RSS_FEEDS_PATH = os.path.join(os.path.dirname(__file__), 'rss_feeds.json')

def _load_watchlist() -> dict:
    if os.path.exists(_WATCHLIST_PATH):
        with open(_WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _load_rss_feeds() -> dict:
    if os.path.exists(_RSS_FEEDS_PATH):
        with open(_RSS_FEEDS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

WATCHLIST  = _load_watchlist()
RSS_CONFIG = _load_rss_feeds()

# GDELT query templates — {p} = province gdelt name
# ~140 per province covering all 20 NAICS sectors + cross-sector catch-alls.
_GDELT_TMPL = [
    # ── NAICS 11 — Agriculture, Forestry, Fishing, Hunting ─────────────────
    "{p} farm agriculture investment million",
    "{p} forestry lumber mill facility",
    "{p} aquaculture fish farm expansion",
    "{p} food processing plant construction",
    "{p} grain terminal elevator project",
    "{p} greenhouse vertical farm facility",
    # ── NAICS 21 — Mining, Quarrying, Oil and Gas ──────────────────────────
    "{p} mine development approved construction",
    "{p} mining project billion investment",
    "{p} gold copper lithium mine proposed",
    "{p} oil sands expansion project",
    "{p} LNG terminal facility export",
    "{p} offshore drilling exploration project",
    "{p} potash uranium rare earth mine",
    "{p} quarry aggregate mining facility",
    "{p} pipeline construction approved",
    "{p} carbon capture sequestration project",
    # ── NAICS 22 — Utilities ───────────────────────────────────────────────
    "{p} power plant generation construction",
    "{p} hydro dam hydroelectric project",
    "{p} nuclear reactor SMR project",
    "{p} wind farm solar farm approved",
    "{p} electricity transmission line project",
    "{p} battery storage energy project",
    "{p} water treatment plant construction",
    "{p} wastewater sewage plant upgrade",
    "{p} hydrogen production facility",
    "{p} grid modernization utility investment",
    # ── NAICS 23 — Construction (mega projects) ───────────────────────────
    "{p} mega development construction billion",
    "{p} residential towers approved construction",
    "{p} commercial complex development",
    "{p} institutional building construction",
    "{p} infrastructure project awarded contract",
    # ── NAICS 31-33 — Manufacturing ────────────────────────────────────────
    "{p} manufacturing plant construction new",
    "{p} auto assembly plant investment",
    "{p} EV battery plant gigafactory",
    "{p} aerospace facility expansion",
    "{p} steel mill smelter facility",
    "{p} pharmaceutical plant biomanufacturing",
    "{p} semiconductor chip fabrication plant",
    "{p} food beverage processing facility",
    "{p} pulp paper mill investment",
    "{p} petrochemical refinery upgrader project",
    # ── NAICS 41 — Wholesale Trade ─────────────────────────────────────────
    "{p} distribution center wholesale hub",
    "{p} cold storage facility construction",
    "{p} trade logistics wholesale facility",
    # ── NAICS 44-45 — Retail Trade ─────────────────────────────────────────
    "{p} shopping center retail development",
    "{p} fulfillment center ecommerce warehouse",
    "{p} outlet mall retail complex construction",
    # ── NAICS 48-49 — Transportation and Warehousing ───────────────────────
    "{p} transit LRT subway BRT project",
    "{p} rail expansion freight corridor",
    "{p} airport terminal expansion construction",
    "{p} port terminal expansion upgrade",
    "{p} highway interchange bridge construction",
    "{p} intermodal terminal logistics park",
    "{p} pipeline construction NEB approved",
    "{p} ferry terminal marine infrastructure",
    # ── NAICS 51 — Information and Cultural Industries ─────────────────────
    "{p} data center construction hyperscale",
    "{p} telecom broadband fiber network",
    "{p} film studio production facility",
    "{p} broadcast tower telecommunications",
    # ── NAICS 52 — Finance and Insurance ───────────────────────────────────
    "{p} bank tower headquarters construction",
    "{p} financial district office development",
    "{p} fintech campus technology hub",
    # ── NAICS 53 — Real Estate ─────────────────────────────────────────────
    "{p} mixed-use development tower approved",
    "{p} condo tower highrise construction",
    "{p} purpose-built rental housing project",
    "{p} commercial real estate office development",
    "{p} master planned community development",
    "{p} transit oriented development TOD",
    # ── NAICS 54 — Professional, Scientific, Technical ─────────────────────
    "{p} research campus innovation hub",
    "{p} R&D laboratory facility construction",
    "{p} science park technology campus",
    # ── NAICS 55 — Management of Companies ─────────────────────────────────
    "{p} corporate headquarters relocation new",
    "{p} head office tower campus construction",
    # ── NAICS 56 — Admin Support, Waste Management ─────────────────────────
    "{p} waste recycling facility construction",
    "{p} waste-to-energy incineration plant",
    "{p} contaminated site remediation project",
    "{p} composting organics processing facility",
    # ── NAICS 61 — Educational Services ────────────────────────────────────
    "{p} university campus expansion construction",
    "{p} new school construction project",
    "{p} college trades training facility",
    "{p} research institute building project",
    # ── NAICS 62 — Health Care ─────────────────────────────────────────────
    "{p} hospital construction new expansion",
    "{p} long-term care home project",
    "{p} medical center health campus",
    "{p} mental health addiction treatment facility",
    "{p} cancer center research facility",
    # ── NAICS 71 — Arts, Entertainment, Recreation ─────────────────────────
    "{p} stadium arena construction project",
    "{p} entertainment district development",
    "{p} casino resort gaming facility",
    "{p} cultural center museum gallery",
    "{p} recreation center aquatic facility",
    # ── NAICS 72 — Accommodation and Food Services ─────────────────────────
    "{p} hotel resort construction development",
    "{p} convention center expansion project",
    "{p} tourism destination resort investment",
    # ── NAICS 81 — Other Services ──────────────────────────────────────────
    "{p} community center facility construction",
    "{p} place of worship religious facility",
    "{p} service hub civic building project",
    # ── NAICS 91 — Public Administration ───────────────────────────────────
    "{p} military base DND facility construction",
    "{p} government building federal provincial",
    "{p} correctional facility prison construction",
    "{p} border crossing customs facility",
    "{p} embassy consulate construction",
    "{p} RCMP police fire station construction",
    "{p} courthouse justice facility project",
    # ── Cross-sector catch-alls ────────────────────────────────────────────
    "{p} billion dollar project announced",
    "{p} major project approved construction",
    "{p} capital investment new facility announced",
    "{p} infrastructure funding awarded contract",
    "{p} environmental assessment project proposed",
    "{p} breaking ground construction start",
    "{p} project milestone completion update",
    "{p} construction tender RFP awarded",
    "{p} public-private partnership P3 project",
    "{p} Indigenous partnership project development",
]

# CMA-level queries — loaded from watchlist.json CMA_Watchlist (30 CMAs)
_CMA_TMPL = [
    "{c} major project construction billion",
    "{c} development approved project million",
    "{c} infrastructure transit expansion",
]

def _get_cma_cities() -> list[str]:
    """Get all CMA names from watchlist, fallback to top-10."""
    cma_list = WATCHLIST.get('cma_list', [])
    if cma_list:
        return [c['cma_name'] for c in cma_list]
    return ["Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
            "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Halifax"]

# CMA -> Province mapping (built from watchlist or hardcoded fallback)
def _build_cma_prov_map() -> dict[str, str]:
    """Map CMA names to province names."""
    cma_list = WATCHLIST.get('cma_list', [])
    # Map jurisdiction abbreviations to full province names
    _abbr = {
        'BC': 'British Columbia', 'AB': 'Alberta', 'SK': 'Saskatchewan',
        'MB': 'Manitoba', 'ON': 'Ontario', 'QC': 'Quebec',
        'NB': 'New Brunswick', 'NS': 'Nova Scotia', 'PE': 'Prince Edward Island',
        'NL': 'Newfoundland and Labrador', 'YT': 'Yukon',
        'NT': 'Northwest Territories', 'NU': 'Nunavut',
    }
    m = {}
    for c in cma_list:
        jur = c.get('jurisdiction', '')
        prov = _abbr.get(jur, jur)
        m[c['cma_name']] = prov
    # Hardcoded fallbacks for any missing
    m.setdefault('Toronto', 'Ontario')
    m.setdefault('Ottawa-Gatineau', 'Ontario')
    m.setdefault('Hamilton', 'Ontario')
    m.setdefault('Montreal', 'Quebec')
    m.setdefault('Quebec City', 'Quebec')
    m.setdefault('Vancouver', 'British Columbia')
    m.setdefault('Calgary', 'Alberta')
    m.setdefault('Edmonton', 'Alberta')
    m.setdefault('Winnipeg', 'Manitoba')
    m.setdefault('Halifax', 'Nova Scotia')
    return m

# Industry publication domain-biased queries (run once, not per province)
_TRADE_QUERIES = [
    "Canada major project ReNew infrastructure",
    "Canada construction Daily Commercial News",
    "Canada mining project Northern Miner",
    "Canada energy project pipeline approved",
    "Canada P3 public private partnership infrastructure",
    "Canada defence procurement military project",
    "Canada Indigenous economic development project",
]

# Section D: Company queries from watchlist
def _build_company_queries() -> tuple[list[tuple[str, str]], list[str]]:
    """
    Build company-specific GDELT queries from watchlist.
    Returns (provincial_queries: [(keyword, province)], national_queries: [keyword]).
    """
    prov_queries = []
    nat_queries = []
    seen_companies = set()

    # Provincial companies: 2 queries each, scoped to province
    _abbr = {
        'BC': 'British Columbia', 'AB': 'Alberta', 'SK': 'Saskatchewan',
        'MB': 'Manitoba', 'ON': 'Ontario', 'QC': 'Quebec',
        'NB': 'New Brunswick', 'NS': 'Nova Scotia', 'PE': 'Prince Edward Island',
        'NL': 'Newfoundland and Labrador', 'YT': 'Yukon',
        'NT': 'Northwest Territories', 'NU': 'Nunavut',
    }
    for c in WATCHLIST.get('provincial_companies', []):
        name = c.get('company_name', '').strip()
        jur  = c.get('jurisdiction', '').strip()
        prov = _abbr.get(jur, jur)
        if not name or not prov:
            continue
        # Use short name (first 2-3 words) to keep GDELT queries concise
        short = ' '.join(name.split()[:3])
        prov_queries.append((f"{short} {prov} project investment", prov))
        prov_queries.append((f"{short} {prov} expansion construction", prov))
        seen_companies.add(name.lower())

    # Industry companies: 1 query each, national scope (dedup against provincial)
    for c in WATCHLIST.get('industry_companies', []):
        name = c.get('company_name', '').strip()
        if not name or name.lower() in seen_companies:
            continue
        short = ' '.join(name.split()[:3])
        nat_queries.append(f"{short} Canada project expansion investment")
        seen_companies.add(name.lower())

    return prov_queries, nat_queries

# Module-level CMA + company query data (loaded once from watchlist)
_CMA_CITIES   = _get_cma_cities()
_CMA_PROV_MAP = _build_cma_prov_map()

# 20 NAICS-aligned industry search vectors for GDELT discovery
INDUSTRY_VECTORS = [
    "farm agriculture forestry billion million investment",
    "mine mining quarry oil gas LNG extraction development",
    "power plant hydro nuclear wind solar utility transmission",
    "construction megaproject residential commercial institutional build",
    "manufacturing plant factory assembly production facility",
    "warehouse distribution center logistics hub wholesale",
    "retail shopping center mall fulfillment center development",
    "transit rail subway LRT airport port terminal expansion",
    "data center telecom broadband fiber network infrastructure",
    "bank headquarters financial campus tower development",
    "condo tower mixed-use rental housing development approved",
    "research campus innovation hub laboratory R&D facility",
    "corporate headquarters office campus relocation expansion",
    "waste recycling treatment remediation facility plant",
    "university college school campus expansion new building",
    "hospital long-term care medical center health facility",
    "stadium arena entertainment district concert venue casino",
    "hotel resort convention center tourism development",
    "community center recreation facility cultural center",
    "military base defense DND government building correctional",
]

# Preferred Canadian news domains for article ranking
_CA_PRIORITY_DOMAINS = frozenset([
    'globeandmail.com', 'theglobeandmail.com', 'nationalpost.com', 'financialpost.com',
    'cbc.ca', 'thestar.com', 'biv.com', 'calgaryherald.com', 'montrealgazette.com',
    'winnipegfreepress.com', 'saltwire.com', 'ctvnews.ca', 'rcinet.ca',
    'macleans.ca', 'canadianbusiness.com', 'ipolitics.ca', 'ledevoir.com', 'lapresse.ca',
    'northernminer.com', 'mining.com', 'dailycommercialnews.com', 'constructioncanada.net',
    'therecord.com', 'theconversation.com', 'energynow.ca',
])
_CA_GOV_PATTERNS = ['.gov.bc.ca', '.alberta.ca', '.ontario.ca', '.gouv.qc.ca',
                    '.gov.sk.ca', '.gov.mb.ca', '.novascotia.ca', '.gnb.ca',
                    '.gov.nl.ca', '.princeedwardisland.ca', '.gov.yk.ca',
                    '.gov.nt.ca', '.gov.nu.ca', 'canada.ca', 'gc.ca']

# Perplexity query templates — {p} = province name
_PERP_QUERIES = [
    "What major resource and energy projects (mining, oil, gas, LNG, pipeline) are currently proposed, approved, or under construction in {p} as of March 2026? List project name, proponent, value, status, location.",
    "What major infrastructure and transit projects (highways, rail, transit, ports, airports) are proposed, approved, or under construction in {p} as of March 2026? List project name, proponent, value, status.",
    "What major construction, housing, and real estate developments are proposed or under construction in {p} as of March 2026? List project name, developer, value, status, location.",
    "What major manufacturing, technology, and institutional projects (hospitals, universities, data centers, military) are proposed or under construction in {p} as of March 2026? List project name, proponent, value, status.",
]

# Claude model — use centralized constants from pipeline_config
_CLAUDE_SONNET = SONNET_MODEL
_CLAUDE_SONNET = SONNET_MODEL  # unified — no more Haiku

# Perplexity (disabled by default — hook left for future use)
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()

# ── Shared request headers ────────────────────────────────────────────────────
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/2.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# Helpers _norm_status, _infer_naics, _norm_key, _fuzzy_match, _parse_value
# are imported from pipeline_config.py above.


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: BACKUP
# ══════════════════════════════════════════════════════════════════════════════

def backup_projects(db) -> list[dict]:
    """Export all /projects docs to JSON backup file. Returns the data list."""
    print("\n[BACKUP] Exporting /projects collection...")
    out = get_all_projects(db)

    backup_file = f'projects_backup_{TODAY}.json'
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Backed up {len(out)} documents → {backup_file}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: WIPE
# ══════════════════════════════════════════════════════════════════════════════

def wipe_projects(db) -> int:
    """Delete all documents in /projects. Returns count deleted."""
    print("\n[WIPE] Deleting all /projects documents from SQLite...")
    cursor = db.execute("SELECT COUNT(*) FROM projects")
    row = cursor.fetchone()
    deleted = row[0] if row else 0
    db.execute("DELETE FROM projects")
    db.commit()
    print(f"  [WIPE] {deleted} documents deleted.")
    return deleted


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: TIER 1 — REGISTRY SCRAPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get(url: str, timeout: int = 20) -> requests.Response | None:
    try:
        r = requests.get(url, timeout=timeout, headers=_HEADERS)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [T1] GET {url[:70]} failed: {type(e).__name__}", file=sys.stderr)
        return None


def _soup(html: str):
    if not _HAS_BS4:
        return None
    try:
        return BeautifulSoup(html, 'lxml')
    except Exception:
        return BeautifulSoup(html, 'html.parser')


def _make_project(
    name, province, status, source_url, discovery_source,
    naics_code='', naics_name='', value='Not disclosed',
    proponent='', cma='', tags=None, detail=''
) -> dict:
    """Build a standardized project dict."""
    if not naics_code:
        naics_code, naics_name = _infer_naics(name, '')
    elif not naics_name:
        naics_name = NAICS_MAP.get(naics_code, '')
    eligible_status = _norm_status(status)
    if not eligible_status:
        return {}  # ineligible
    path_segs = [s for s in urlparse(source_url or '').path.split('/') if s]
    url_quality = 'direct' if len(path_segs) >= 2 else 'relevant'
    return {
        'name':             name.strip(),
        'province':         province,
        'cma':              cma,
        'sector':           naics_name,
        'naics_code':       naics_code,
        'naics_name':       naics_name,
        'tags':             tags or [],
        'value':            value or 'Not disclosed',
        'status':           eligible_status,
        'proponent':        proponent,
        'confidence':       'verified',
        'discovery_source': discovery_source,
        'source_url_quality': url_quality,
        'firstTracked':     TODAY,
        'lastUpdated':      TODAY,
        'lastSeen':         TODAY,
        'statusHistory': [{
            'status': eligible_status,
            'date':   TODAY,
            'detail': detail or f'Project in {eligible_status} status as of {TODAY}.',
            'source': {
                'title': f'{discovery_source} registry',
                'url': source_url or '',
                'verified': True,
                'verified_date': TODAY,
            },
        }],
    }


# ── IAAC ─────────────────────────────────────────────────────────────────────

_IAAC_URL = "https://iaac-aeic.gc.ca/050/evaluations"

def _scrape_iaac() -> list[dict]:
    r = _get(_IAAC_URL)
    if not r:
        return []
    soup = _soup(r.text)
    if not soup:
        return []
    projects = []
    rows = soup.select('table tbody tr')
    for row in rows[:100]:
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
        name_el = row.find('a')
        name = name_el.get_text(strip=True) if name_el else (cells[0].get_text(strip=True) if cells else '')
        if not name or len(name) < 5:
            continue
        href = name_el.get('href', '') if name_el else ''
        url = href if href.startswith('http') else (f"https://iaac-aeic.gc.ca{href}" if href else _IAAC_URL)
        province = cells[2].get_text(strip=True) if len(cells) > 2 else ''
        status_txt = cells[3].get_text(strip=True) if len(cells) > 3 else ''
        proj = _make_project(
            name=name, province=province, status=status_txt or 'Under Review',
            source_url=url, discovery_source='iaac_registry',
            detail=f'IAAC assessment: {status_txt}. Source: {url}'
        )
        if proj:
            projects.append(proj)
    print(f"  [IAAC] {len(projects)} eligible projects")
    return projects


# ── BC EAO ────────────────────────────────────────────────────────────────────

_BCEAO_API = (
    "https://www.projects.eao.gov.bc.ca/api/v2/projects"
    "?fields=name,eacDecision,status,proponent,description&pageSize=100"
)

def _scrape_bc_eao() -> list[dict]:
    r = _get(_BCEAO_API)
    if not r:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    rows = data if isinstance(data, list) else data.get('data', data.get('projects', []))
    projects = []
    for p in rows[:100]:
        name = (p.get('name') or '').strip()
        if not name:
            continue
        eac  = ((p.get('eacDecision') or {}).get('decisionLabel') or '').lower()
        # Map BC EAO decision to status
        if 'approved' in eac or 'issued' in eac:
            status = 'Approved'
        elif 'refused' in eac or 'rejected' in eac:
            continue  # skip refused
        elif 'under construction' in eac:
            status = 'Under Construction'
        else:
            status = 'Under Review'
        proponent = ((p.get('proponent') or {}).get('name') or '')
        pid  = p.get('_id') or p.get('id') or ''
        url  = f"https://projects.eao.gov.bc.ca/project/{pid}" if pid else ''
        desc = (p.get('description') or '')[:300]
        proj = _make_project(
            name=name, province='British Columbia', status=status,
            source_url=url, discovery_source='bc_eao',
            proponent=proponent, detail=desc or f'BC EAO project in {status} status.'
        )
        if proj:
            projects.append(proj)
    print(f"  [BC EAO] {len(projects)} eligible projects")
    return projects


# ── Infrastructure Canada ─────────────────────────────────────────────────────

_INFRA_CA_JSON = (
    "https://infrastructure.gc.ca/alt-format/opendata/"
    "project-list-liste-de-projets-bil.json"
)
_INFRA_CA_PAGE = "https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html"

def _scrape_infra_canada() -> list[dict]:
    r = _get(_INFRA_CA_JSON, timeout=30)
    if not r:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    if isinstance(data, dict):
        records = (data.get('data') or data.get('records') or
                   data.get('projects') or (list(data.values())[0] if data else []))
    else:
        records = data if isinstance(data, list) else []

    projects = []
    for row in (records or [])[:300]:
        if not isinstance(row, dict):
            continue
        name = (row.get('Project_Name_EN') or row.get('Project_Name')
                or row.get('project_name_en') or row.get('project_name') or '').strip()
        if not name or len(name) < 5:
            continue
        province  = (row.get('Province_Territory_EN') or row.get('Province_Territory')
                     or row.get('province') or row.get('province_en') or '')
        val_str   = str(row.get('Federal_Contribution') or row.get('FederalContribution')
                        or row.get('total_funding') or row.get('Total_Funding') or '')
        try:
            v = float(re.sub(r'[^\d.]', '', val_str))
            value = f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.0f}M"
        except Exception:
            value = 'Not disclosed'
        status_raw = (row.get('Project_Status_EN') or row.get('Project_Status') or 'Approved')
        proponent  = (row.get('Recipient_Name') or row.get('recipient_name') or '')
        proj = _make_project(
            name=name, province=province, status=status_raw,
            source_url=_INFRA_CA_PAGE, discovery_source='infrastructure_canada',
            value=value, proponent=proponent,
            detail=f'Infrastructure Canada funded project. Status: {status_raw}. Federal contribution: {value}.'
        )
        if proj:
            # url_quality is 'relevant' since we link to the map page not individual project
            proj['source_url_quality'] = 'relevant'
            projects.append(proj)
    print(f"  [Infrastructure Canada] {len(projects)} eligible projects")
    return projects


# ── NRCan Major Projects Inventory ───────────────────────────────────────────

_NRCAN_PAGE = (
    "https://natural-resources.canada.ca/science-and-data/"
    "data-and-analysis/major-projects-inventory/22218"
)

def _scrape_nrcan() -> list[dict]:
    r = _get(_NRCAN_PAGE)
    if not r:
        return []
    soup = _soup(r.text)
    if not soup:
        return []
    projects = []
    for el in (soup.select('table tbody tr') + soup.select('.field-items li'))[:80]:
        name_el = el.find('a') or el.find('strong')
        name    = name_el.get_text(strip=True) if name_el else el.get_text(strip=True)[:150]
        name    = re.sub(r'\s+', ' ', name).strip()
        if not name or len(name) < 5:
            continue
        href = ''
        if name_el and name_el.name == 'a':
            href = name_el.get('href', '')
        url = href if href.startswith('http') else (f"https://natural-resources.canada.ca{href}" if href else _NRCAN_PAGE)
        cells = el.find_all('td') if el.name == 'tr' else []
        province = cells[1].get_text(strip=True) if len(cells) > 1 else ''
        status_raw = cells[2].get_text(strip=True) if len(cells) > 2 else 'Proposed'
        proj = _make_project(
            name=name, province=province, status=status_raw or 'Proposed',
            source_url=url, discovery_source='nrcan',
            detail=f'NRCan Major Projects Inventory. Status: {status_raw}.'
        )
        if proj:
            projects.append(proj)
    print(f"  [NRCan] {len(projects)} eligible projects")
    return projects


# ── BuyAndSell / CanadaBuys ────────────────────────────────────────────────

_CANADABUYS_CSV = (
    "https://canadabuys.canada.ca/opendata/pub/"
    "contractHistoryComplete-contratsOctroyesComplet.csv"
)
_CANADABUYS_PAGE = "https://canadabuys.canada.ca/en/procurement-and-contracting-data"

def _scrape_buyandsell() -> list[dict]:
    """
    Fetch recent large awarded contracts from CanadaBuys (formerly BuyAndSell).
    Downloads the open-data CSV (first 2 MB) and filters for contracts >= $5M.
    Returns list of project dicts with discovery_source='buyandsell'.
    """
    try:
        resp = requests.get(_CANADABUYS_CSV, timeout=60, headers=_HEADERS, stream=True)
        resp.raise_for_status()

        import csv as _csv
        # Read first 2 MB to avoid downloading the full multi-GB file
        raw = b''
        for chunk in resp.iter_content(chunk_size=65536):
            raw += chunk
            if len(raw) >= 2_097_152:
                break
        text = raw.decode('utf-8', errors='replace')
        reader = _csv.DictReader(io.StringIO(text))

        projects = []
        for i, row in enumerate(reader):
            if i > 5000:
                break
            name = (row.get('description_en') or row.get('description')
                     or row.get('commodity_description') or '')
            val_str = str(row.get('contract_value') or row.get('value_contract') or '0')
            try:
                val_num = float(re.sub(r'[^\d.]', '', val_str))
            except Exception:
                val_num = 0
            if val_num < 5_000_000:
                continue

            value  = f"${val_num/1e9:.1f}B" if val_num >= 1e9 else f"${val_num/1e6:.0f}M"
            dept   = row.get('buyer_name') or row.get('department_en') or ''
            vendor = row.get('supplier_legal_name') or row.get('vendor_name') or ''
            proj_name = name or f"{dept} contract — {vendor}"

            proj = _make_project(
                name=proj_name, province='Canada', status='Approved',
                source_url=_CANADABUYS_PAGE, discovery_source='buyandsell',
                value=value, proponent=vendor,
                detail=f'CanadaBuys contract awarded. Dept: {dept}. Vendor: {vendor}. Value: {value}.'
            )
            if proj:
                proj['source_url_quality'] = 'relevant'
                projects.append(proj)
            if len(projects) >= 50:
                break

        print(f"  [CanadaBuys] {len(projects)} large contracts (>=$5M)")
        return projects

    except Exception as e:
        print(f"  [CanadaBuys] Failed: {e}", file=sys.stderr)
        return []


def run_tier1() -> list[dict]:
    print("\n[TIER 1] Government registry scrapers...")
    all_projs: list[dict] = []
    for label, fn in [
        ("IAAC",                  _scrape_iaac),
        ("BC EAO",                _scrape_bc_eao),
        ("Infrastructure Canada", _scrape_infra_canada),
        ("NRCan",                 _scrape_nrcan),
        ("CanadaBuys",            _scrape_buyandsell),
    ]:
        try:
            all_projs.extend(fn())
        except Exception as e:
            print(f"  [{label}] Error: {e}", file=sys.stderr)
        time.sleep(1)
    # Filter: must have name and province
    all_projs = [p for p in all_projs if p.get('name') and p.get('province')]
    print(f"  [Tier 1] {len(all_projs)} total eligible projects from registries")
    return all_projs


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: TIER 2 — GDELT + TAVILY + CLAUDE SONNET
# ══════════════════════════════════════════════════════════════════════════════

# ── GDELT patched client ──────────────────────────────────────────────────────

_GDELT_BASE    = "http://api.gdeltproject.org/api/v2/doc/doc"
_GDELT_TIMEOUT = (15, 60)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/2.0"
_GDELT_NE = object()  # network-error sentinel


class _GdeltPatched(GdeltDoc if _HAS_GDELT else object):
    """GdeltDoc subclass with HTTP (not HTTPS) and browser UA to avoid TCP blocking."""
    def _query(self, mode: str, query_string: str) -> dict:
        valid_modes = ['artlist', 'timelinevol', 'timelinevolraw',
                       'timelinetone', 'timelinelang', 'timelinesourcecountry']
        if mode not in valid_modes:
            raise ValueError(f"Mode {mode} not supported")
        resp = requests.get(
            f"{_GDELT_BASE}?query={query_string}&mode={mode}&format=json",
            headers={'User-Agent': _UA},
            timeout=_GDELT_TIMEOUT,
        )
        raise_response_error(response=resp)
        if 'text/html' in resp.headers.get('content-type', ''):
            raise ValueError(f"GDELT returned HTML: {resp.text[:200]}")
        return load_json(resp.content, self.max_depth_json_parsing)


def _gdelt_query(keyword: str, province: str, days_back: int = 365, max_records: int = 50):
    """Run one GDELT search. Returns list[dict] or _GDELT_NE sentinel on network error."""
    if not _HAS_GDELT:
        return []
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    try:
        gd = _GdeltPatched()
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
                'province':      province,
                'keyword':       keyword,
            })
        return results
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            print(f"  [GDELT] 429 rate-limit on '{keyword[:35]}' — backing off 30s", file=sys.stderr)
            time.sleep(30)
            return _GDELT_NE  # signal caller to retry or skip
        print(f"  [GDELT] '{keyword[:35]}' HTTP error: {e}", file=sys.stderr)
        return _GDELT_NE
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        print(f"  [GDELT] '{keyword[:35]}' network error: {type(e).__name__}", file=sys.stderr)
        return _GDELT_NE
    except Exception as e:
        print(f"  [GDELT] '{keyword[:35]}' failed: {e}", file=sys.stderr)
        return []


def _domain_rank(domain: str) -> int:
    """Lower = higher priority. 0=CA priority news, 1=CA gov, 2=CA other, 3=rest."""
    if any(d in domain for d in _CA_PRIORITY_DOMAINS):
        return 0
    if any(p in domain for p in _CA_GOV_PATTERNS):
        return 1
    if domain.endswith('.ca'):
        return 2
    return 3


def run_gdelt_queries(days_back: int = 365) -> tuple[dict[str, list[dict]], int]:
    """
    Run ~2,047 GDELT queries across 4 sections:
      A: ~140 per province × 13 provinces  (Section A)
      B: 3 per CMA × 30 CMAs              (Section B)
      C: 7 trade publication queries       (Section C)
      D: ~130 company queries from watchlist (Section D)
    Returns (dict {province_name: [article_dicts]}, total_queries_run),
    deduplicated by URL across ALL queries.
    """
    if not _HAS_GDELT:
        print("  [GDELT] gdeltdoc not available — skipping Tier 2 GDELT.")
        return {}, 0

    # Build Section D company queries from watchlist
    company_prov_q, company_nat_q = _build_company_queries()

    prov_queries = len(_GDELT_TMPL) * len(PROVINCES)
    cma_queries  = len(_CMA_TMPL) * len(_CMA_CITIES)
    trade_count  = len(_TRADE_QUERIES)
    company_count = len(company_prov_q) + len(company_nat_q)
    total_queries = prov_queries + cma_queries + trade_count + company_count
    print(f"\n  [GDELT] Running {total_queries} queries "
          f"(A:{len(_GDELT_TMPL)}x{len(PROVINCES)}={prov_queries} prov "
          f"+ B:{cma_queries} CMA + C:{trade_count} trade "
          f"+ D:{company_count} company, last {days_back}d, 0.5s delay)...")

    seen_urls: set[str] = set()
    articles_by_prov: dict[str, list[dict]] = {p['name']: [] for p in PROVINCES}
    articles_by_prov['_national'] = []  # catch-all for trade/national queries
    consecutive_errors = 0
    q_num = 0

    # ── Section A: Province × industry queries ─────────────────────────────
    for prov in PROVINCES:
        prov_name  = prov['name']
        gdelt_name = prov['gdelt']

        for tmpl in _GDELT_TMPL:
            q_num += 1
            keyword = tmpl.format(p=gdelt_name)

            result = _gdelt_query(keyword, prov_name, days_back=days_back)
            if result is _GDELT_NE:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print(f"  [GDELT] 5 consecutive network errors — GDELT unreachable. Stopping.", file=sys.stderr)
                    return articles_by_prov, q_num
            else:
                consecutive_errors = 0
                for art in result:
                    if art['url'] not in seen_urls:
                        seen_urls.add(art['url'])
                        articles_by_prov[prov_name].append(art)

            time.sleep(0.5)

        n = len(articles_by_prov[prov_name])
        print(f"  [GDELT] {prov_name}: {n} unique articles")

    # ── Section B: CMA city queries ────────────────────────────────────────
    print(f"\n  [GDELT] Section B: {cma_queries} CMA-level city queries...")
    for city in _CMA_CITIES:
        prov_name = _CMA_PROV_MAP.get(city, '_national')
        for tmpl in _CMA_TMPL:
            q_num += 1
            keyword = tmpl.format(c=city)
            result = _gdelt_query(keyword, prov_name, days_back=days_back)
            if result is _GDELT_NE:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print(f"  [GDELT] 5 consecutive errors — stopping CMA queries.", file=sys.stderr)
                    break
            else:
                consecutive_errors = 0
                for art in result:
                    if art['url'] not in seen_urls:
                        seen_urls.add(art['url'])
                        art['province'] = prov_name
                        articles_by_prov.setdefault(prov_name, []).append(art)
            time.sleep(0.5)
    print(f"  [GDELT] Section B done")

    # ── Section C: Trade publication queries ───────────────────────────────
    print(f"  [GDELT] Section C: {trade_count} trade publication queries...")
    for kw in _TRADE_QUERIES:
        q_num += 1
        result = _gdelt_query(kw, '_national', days_back=days_back)
        if result is not _GDELT_NE:
            consecutive_errors = 0
            for art in result:
                if art['url'] not in seen_urls:
                    seen_urls.add(art['url'])
                    articles_by_prov['_national'].append(art)
        else:
            consecutive_errors += 1
        time.sleep(0.5)

    # ── Section D: Company queries from watchlist ──────────────────────────
    if company_prov_q or company_nat_q:
        print(f"  [GDELT] Section D: {company_count} company queries from watchlist...")
        # D1: Provincial company queries (scoped to province)
        for kw, prov_name in company_prov_q:
            q_num += 1
            result = _gdelt_query(kw, prov_name, days_back=days_back)
            if result is _GDELT_NE:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print(f"  [GDELT] 5 consecutive errors — stopping company queries.", file=sys.stderr)
                    break
            else:
                consecutive_errors = 0
                for art in result:
                    if art['url'] not in seen_urls:
                        seen_urls.add(art['url'])
                        articles_by_prov.setdefault(prov_name, []).append(art)
            time.sleep(0.5)

        # D2: National industry company queries
        for kw in company_nat_q:
            q_num += 1
            result = _gdelt_query(kw, '_national', days_back=days_back)
            if result is not _GDELT_NE:
                consecutive_errors = 0
                for art in result:
                    if art['url'] not in seen_urls:
                        seen_urls.add(art['url'])
                        articles_by_prov['_national'].append(art)
            else:
                consecutive_errors += 1
            time.sleep(0.5)
        print(f"  [GDELT] Section D done")

    total = sum(len(v) for v in articles_by_prov.values())
    print(f"  [GDELT] {total} total unique articles across {q_num} queries")
    return articles_by_prov, q_num


def _select_top_articles(articles_by_prov: dict, max_per_prov: int = 15, max_total: int = 195) -> dict[str, list[dict]]:
    """Select top articles per province: prefer CA priority domains + CA gov domains."""
    selected: dict[str, list[dict]] = {}
    total = 0
    for prov_name, arts in articles_by_prov.items():
        if prov_name == '_national':
            continue  # handle national separately
        sorted_arts = sorted(arts, key=lambda a: _domain_rank(a.get('domain', '')))
        take = min(max_per_prov, max_total - total)
        if take <= 0:
            break
        selected[prov_name] = sorted_arts[:take]
        total += len(selected[prov_name])
    # Add national/trade articles to remaining budget
    national = articles_by_prov.get('_national', [])
    if national and total < max_total:
        take = min(len(national), max_total - total)
        selected['_national'] = sorted(national, key=lambda a: _domain_rank(a.get('domain', '')))[:take]
        total += len(selected.get('_national', []))
    return selected


def _tavily_extract(urls: list[str]) -> dict[str, dict]:
    """Batch-extract article text via Tavily. Returns {url: {url, title, text}}."""
    if not tavily_client:
        return {}
    result_map: dict[str, dict] = {}
    for i in range(0, len(urls), 5):
        batch = urls[i:i + 5]
        try:
            resp = tavily_client.extract(urls=batch)
            for r in (resp.get('results') or []):
                url  = r.get('url') or ''
                text = r.get('raw_content') or r.get('content') or ''
                if url and text:
                    result_map[url] = {
                        'url':   url,
                        'title': r.get('title') or '',
                        'text':  text[:7000],
                    }
        except Exception as e:
            print(f"  [Tavily] Batch {i//5 + 1} failed: {e}")
        time.sleep(0.3)
    return result_map


_CLAUDE_PROJ_SCHEMA = """{
  "projects": [
    {
      "name": "Exact project name as stated in article",
      "province": "Province name",
      "cma": "Nearest city or Census Metropolitan Area",
      "naics_code": "Best-fit 2-digit NAICS code (11/21/22/23/31-33/41/44-45/48-49/51/52/53/54/55/56/61/62/71/72/81/91)",
      "naics_name": "NAICS sector name",
      "sector": "Short sector description",
      "value": "Exact dollar amount as stated (e.g. '$1.2B', '$350M') or 'Not disclosed'",
      "status": "ONE OF: Proposed | Under Review | Approved | Under Construction | Paused | Expansion",
      "proponent": "Company or government entity name, exactly as stated",
      "tags": ["keyword1", "keyword2", "keyword3"],
      "statusHistory_detail": "2-3 sentences pulled VERBATIM or near-verbatim from the article. What stage is the project at? What is the timeline? Who is involved? What happens next? DO NOT add any information not in the article.",
      "source_title": "Exact article headline",
      "source_url": "EXACT article URL as provided — do NOT modify"
    }
  ]
}"""


def _claude_extract_from_articles(
    province: str, threshold: str, articles: list[dict], today: str
) -> list[dict]:
    """
    Send province articles to Claude Sonnet for project extraction.
    Returns list of project dicts.
    """
    if not anthropic_client or not articles:
        return []

    # Build article blocks
    art_blocks = []
    for i, art in enumerate(articles, 1):
        art_blocks.append(
            f"--- ARTICLE {i} ---\n"
            f"URL: {art['url']}\n"
            f"Title: {art.get('title','(no title)')}\n"
            f"Text:\n{art.get('text','(no text extracted)')[:4000]}\n"
        )
    articles_text = "\n".join(art_blocks)

    naics_list = '\n'.join(f"  {k}: {v}" for k, v in NAICS_MAP.items())

    system = (
        "You are a Canadian capital project data extractor. "
        "Extract ONLY real, specific capital projects explicitly described in the provided articles. "
        "DO NOT invent any details not stated in the article text. "
        "DO NOT include completed, cancelled, or operational projects. "
        "Return only valid JSON, no markdown fences."
    )

    user = f"""Province: {province}
Minimum value threshold: {threshold} CAD
Today's date: {today}

NAICS 2-digit sector codes — assign the BEST-FIT code from this complete list:
{naics_list}

Valid NAICS codes: 11, 21, 22, 23, 31-33, 41, 44-45, 48-49, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 91.
Every project MUST receive exactly one naics_code from the list above.

ELIGIBLE STATUSES ONLY: Proposed | Under Review | Approved | Under Construction | Paused | Expansion
DO NOT include: Completed | Cancelled | Abandoned | Operational

For each article below:
- If it describes a specific capital project that meets or exceeds {threshold} CAD: extract it
- If the project value is not stated, include it only if the article clearly implies a major capital project
- If the article does not describe a specific capital project: skip it entirely
- DO NOT invent any information not explicitly stated in the article
- The source_url MUST be the EXACT article URL provided — copy it verbatim

Return JSON matching this exact schema. If no valid projects found, return {{"projects": []}}.

{_CLAUDE_PROJ_SCHEMA}

ARTICLES:
{articles_text}
"""

    for attempt in range(3):
        try:
            msg = anthropic_client.messages.create(
                model=_CLAUDE_SONNET,
                max_tokens=4096,
                system=system,
                messages=[{'role': 'user', 'content': user}],
            )
            raw = msg.content[0].text.strip()
            if raw.startswith('```'):
                raw = re.sub(r'^```[a-z]*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            parsed = json.loads(raw)
            return parsed.get('projects', []) if isinstance(parsed, dict) else []
        except json.JSONDecodeError as e:
            if attempt == 2:
                print(f"  [Claude T2] JSON error {province}: {e}")
            time.sleep(1)
        except Exception as e:
            if attempt == 2:
                print(f"  [Claude T2] Error {province}: {e}")
            time.sleep(2 ** attempt)
    return []


def run_tier2(days_back: int = 365) -> tuple[list[dict], int, int, int]:
    """
    Run GDELT + Tavily + Claude Sonnet extraction.
    Returns (project_list, gdelt_queries_run, unique_articles_found, articles_sent_to_tavily).
    """
    print("\n[TIER 2] GDELT + Tavily + Claude Sonnet...")

    # 2a: GDELT queries
    articles_by_prov, gdelt_queries_run = run_gdelt_queries(days_back=days_back)
    if not articles_by_prov:
        return [], gdelt_queries_run, 0, 0

    unique_articles = sum(len(v) for v in articles_by_prov.values())

    # 2b: Select top articles per province (15/prov, 195 total)
    selected = _select_top_articles(articles_by_prov, max_per_prov=15, max_total=195)
    total_selected = sum(len(v) for v in selected.values())
    print(f"\n  [Tier 2] Selected {total_selected} articles for Tavily extraction")

    # 2c: Tavily extraction
    all_urls = [art['url'] for arts in selected.values() for art in arts]
    print(f"  [Tavily] Extracting {len(all_urls)} URLs...")
    extracted = _tavily_extract(all_urls)
    print(f"  [Tavily] Got text from {len(extracted)}/{len(all_urls)} URLs")

    # 2d: Claude extraction per province
    all_projects: list[dict] = []
    for prov in PROVINCES:
        prov_name = prov['name']
        threshold = prov['threshold']
        prov_arts = selected.get(prov_name, [])
        if not prov_arts:
            continue

        # Merge extracted text into article dicts
        enriched = []
        for art in prov_arts:
            ext = extracted.get(art['url'])
            enriched.append({
                'url':   art['url'],
                'title': (ext or {}).get('title') or art.get('title', ''),
                'text':  (ext or {}).get('text', ''),
            })

        print(f"  [Claude T2] {prov_name} ({len(enriched)} articles, threshold {threshold})...", end='', flush=True)
        raw_projs = _claude_extract_from_articles(prov_name, threshold, enriched, TODAY)
        print(f" -> {len(raw_projs)} raw", end='')

        accepted = 0
        for rp in raw_projs:
            name = (rp.get('name') or '').strip()
            if not name:
                continue
            status = _norm_status(rp.get('status', ''))
            if not status:
                continue
            src_url = (rp.get('source_url') or '').strip()
            naics_c = (rp.get('naics_code') or '').strip()
            naics_n = rp.get('naics_name') or NAICS_MAP.get(naics_c, '')
            if not naics_c:
                naics_c, naics_n = _infer_naics(name, rp.get('sector', ''))
            path_segs = [s for s in urlparse(src_url).path.split('/') if s]
            url_quality = 'direct' if len(path_segs) >= 2 else 'relevant'
            proj = {
                'name':             name,
                'province':         prov_name,
                'cma':              (rp.get('cma') or '').strip(),
                'sector':           (rp.get('sector') or naics_n).strip(),
                'naics_code':       naics_c,
                'naics_name':       naics_n,
                'tags':             rp.get('tags') or [],
                'value':            (rp.get('value') or 'Not disclosed').strip(),
                'status':           status,
                'proponent':        (rp.get('proponent') or '').strip(),
                'confidence':       'verified',
                'discovery_source': 'gdelt_news',
                'source_url_quality': url_quality,
                'firstTracked':     TODAY,
                'lastUpdated':      TODAY,
                'lastSeen':         TODAY,
                'statusHistory': [{
                    'status': status,
                    'date':   TODAY,
                    'detail': (rp.get('statusHistory_detail') or f'{name} is {status}.').strip(),
                    'source': {
                        'title': (rp.get('source_title') or '').strip(),
                        'url':   src_url,
                        'verified': True,
                        'verified_date': TODAY,
                    },
                }],
            }
            all_projects.append(proj)
            accepted += 1

        print(f", {accepted} accepted")

    # Also extract from _national (trade pub articles)
    nat_arts = selected.get('_national', [])
    if nat_arts:
        enriched = []
        for art in nat_arts:
            ext = extracted.get(art['url'])
            enriched.append({
                'url':   art['url'],
                'title': (ext or {}).get('title') or art.get('title', ''),
                'text':  (ext or {}).get('text', ''),
            })
        print(f"  [Claude T2] National/trade ({len(enriched)} articles)...", end='', flush=True)
        raw_projs = _claude_extract_from_articles('Canada', '$100M', enriched, TODAY)
        print(f" -> {len(raw_projs)} raw", end='')
        accepted = 0
        for rp in raw_projs:
            name = (rp.get('name') or '').strip()
            if not name:
                continue
            status = _norm_status(rp.get('status', ''))
            src_url = (rp.get('source_url') or '').strip()
            naics_c = (rp.get('naics_code') or '').strip()
            naics_n = rp.get('naics_name') or NAICS_MAP.get(naics_c, '')
            if not naics_c:
                naics_c, naics_n = _infer_naics(name, rp.get('sector', ''))
            province = (rp.get('province') or '').strip()
            if not province:
                province = 'Canada'
            path_segs = [s for s in urlparse(src_url).path.split('/') if s]
            url_quality = 'direct' if len(path_segs) >= 2 else 'relevant'
            proj = {
                'name':             name,
                'province':         province,
                'cma':              (rp.get('cma') or '').strip(),
                'sector':           (rp.get('sector') or naics_n).strip(),
                'naics_code':       naics_c,
                'naics_name':       naics_n,
                'tags':             rp.get('tags') or [],
                'value':            (rp.get('value') or 'Not disclosed').strip(),
                'status':           status,
                'proponent':        (rp.get('proponent') or '').strip(),
                'confidence':       'verified',
                'discovery_source': 'gdelt_news',
                'source_url_quality': url_quality,
                'firstTracked':     TODAY,
                'lastUpdated':      TODAY,
                'lastSeen':         TODAY,
                'statusHistory': [{
                    'status': status,
                    'date':   TODAY,
                    'detail': (rp.get('statusHistory_detail') or f'{name} is {status}.').strip(),
                    'source': {
                        'title': (rp.get('source_title') or '').strip(),
                        'url':   src_url,
                        'verified': True,
                        'verified_date': TODAY,
                    },
                }],
            }
            all_projects.append(proj)
            accepted += 1
        print(f", {accepted} accepted")

    print(f"  [Tier 2] {len(all_projects)} total projects from GDELT+Claude")
    return all_projects, gdelt_queries_run, unique_articles, len(all_urls)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: TIER 3 — PERPLEXITY + URL VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

# === PERPLEXITY GAP FILL -- DISABLED ===
# To enable: set ENABLE_PERPLEXITY=true in .env
# When enabled, this runs AFTER Tiers 1-2 and asks Perplexity Sonar Pro
# about NAICS sectors with zero projects found per province.
# All Perplexity-sourced projects must pass the same URL verification.
# If coverage gaps persist after 4 weekly runs, consider enabling this.
#
# Estimated cost if enabled: ~$37/year (Sonar Pro) or ~$83/year (Deep Research)
#
# To enable for writing layer: set PERPLEXITY_WRITING=true in .env
# This adds Deep Research contextual briefs to Claude Sonnet writing calls.
# Only worth enabling if article context from GDELT proves insufficient.
#
# Required env var: PERPLEXITY_API_KEY
#
# def _perplexity_gap_fill(provinces, existing_projects):
#     """Query Perplexity for NAICS sectors with zero coverage per province."""
#     pass
#
# def _perplexity_writing_brief(section, date_range):
#     """Generate Deep Research contextual brief for writing layer."""
#     pass
# === END PERPLEXITY HOOK ===


def _DISABLED_perplexity_query(query: str) -> tuple[str, list[str]]:
    """Query Perplexity Sonar Pro. DISABLED — left for reference."""
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': 'sonar-pro',
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You are a Canadian infrastructure and capital markets researcher. '
                    'Give factual, specific information about real capital projects in Canada. '
                    'Only include projects that are currently proposed, under review, approved, '
                    'under construction, paused, or in an expansion phase. '
                    'Do NOT include completed, cancelled, or purely operational projects.'
                ),
            },
            {'role': 'user', 'content': query},
        ],
        'max_tokens': 2500,
    }
    for attempt in range(4):
        try:
            r = requests.post(
                'https://api.perplexity.ai/chat/completions',
                headers=headers, json=payload, timeout=60,
            )
            r.raise_for_status()
            d = r.json()
            return d['choices'][0]['message']['content'], d.get('citations', [])
        except Exception as e:
            if attempt == 3:
                print(f"  [Perplexity] query failed: {e}")
                return '', []
            time.sleep(2 ** attempt)
    return '', []


# Old _REJECT_URL_PATTERNS and _verify_url removed — now imported from url_verify.py
# (see imports at top: from url_verify import verify_url as _verify_url_full, quick_reject)


def _DISABLED_sonnet_parse_perplexity(text: str, province: str, threshold: str, citations: list[str]) -> list[dict]:
    """Use Claude Sonnet to parse Perplexity text into project list."""
    if not anthropic_client or not text.strip():
        return []
    cite_block = ''
    if citations:
        numbered = '\n'.join(f'[{i+1}] {u}' for i, u in enumerate(citations))
        cite_block = f'\nVERIFIED CITATION URLS:\n{numbered}\n'
    naics_list = '\n'.join(f'  {k}: {v}' for k, v in NAICS_MAP.items())
    schema = """{
  "projects": [
    {
      "name": "exact project name",
      "province": "province name",
      "cma": "nearest city",
      "naics_code": "2-digit NAICS",
      "naics_name": "NAICS sector name",
      "sector": "short description",
      "value": "$XXM or 'Not disclosed'",
      "status": "Proposed|Under Review|Approved|Under Construction|Paused|Expansion",
      "proponent": "company or government",
      "tags": ["tag1","tag2"],
      "best_citation_url": "most relevant citation URL from the list above, or ''",
      "detail": "1-2 sentences from source text describing project stage, timeline, proponent"
    }
  ]
}"""
    user = f"""Province: {province}
Minimum value: {threshold} CAD
{cite_block}
NAICS 2-digit sector codes — assign the BEST-FIT code from this complete list:
{naics_list}

Valid NAICS codes: 11, 21, 22, 23, 31-33, 41, 44-45, 48-49, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 91.
Every project MUST receive exactly one naics_code from the list above.

Only include ACTIVE projects (Proposed/Under Review/Approved/Under Construction/Paused/Expansion).
Do NOT include: Completed, Cancelled, Operational.
Return JSON only (no markdown):
{schema}

SOURCE TEXT:
{text[:3000]}"""
    for attempt in range(3):
        try:
            msg = anthropic_client.messages.create(
                model=_CLAUDE_SONNET,
                max_tokens=3000,
                messages=[{'role': 'user', 'content': user}],
            )
            raw = msg.content[0].text.strip()
            if raw.startswith('```'):
                raw = re.sub(r'^```[a-z]*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            parsed = json.loads(raw)
            return parsed.get('projects', []) if isinstance(parsed, dict) else []
        except Exception as e:
            if attempt == 2:
                print(f"  [Sonnet T3] {province}: {e}")
            time.sleep(1)
    return []


def _DISABLED_run_tier3(known_keys: set[str], known_names_by_prov: dict[str, list[str]]) -> tuple[list[dict], list[dict]]:
    """
    Run Perplexity gap fill for all provinces × 4 queries.
    Verify every URL. Returns (accepted_projects, rejected_log).
    """
    if not PERPLEXITY_API_KEY:
        print("  [Tier 3] PERPLEXITY_API_KEY not set — skipping.")
        return [], []

    print(f"\n[TIER 3] Perplexity gap fill ({len(_PERP_QUERIES)} queries × {len(PROVINCES)} provinces)...")

    accepted_all: list[dict] = []
    rejected_log: list[dict] = []
    total_urls_tested = 0

    for prov in PROVINCES:
        prov_name  = prov['name']
        threshold  = prov['threshold']
        print(f"\n  {prov_name} ({threshold}+)")

        for q_tmpl in _PERP_QUERIES:
            query = q_tmpl.format(p=prov_name)
            text, citations = _perplexity_query(query)
            time.sleep(2)
            if not text:
                continue

            raw_projs = _sonnet_parse_perplexity(text, prov_name, threshold, citations)
            if not raw_projs:
                continue

            print(f"    → {len(raw_projs)} candidates from Perplexity")

            for rp in raw_projs:
                name = (rp.get('name') or '').strip()
                if not name or len(name) < 5:
                    continue

                # Check against existing dedup cache
                key = _norm_key(name, prov_name)
                if key in known_keys:
                    continue
                existing = known_names_by_prov.get(prov_name, [])
                if _fuzzy_match(name, existing):
                    continue

                status = _norm_status(rp.get('status', ''))
                if not status:
                    rejected_log.append({
                        'name': name, 'province': prov_name,
                        'reason': f"Ineligible status: {rp.get('status')}",
                        'url_tested': '', 'query': query[:80],
                    })
                    continue

                # Pick best citation URL for this project
                candidate_url = (rp.get('best_citation_url') or '').strip()
                if not candidate_url and citations:
                    candidate_url = citations[0]

                # Verify URL
                total_urls_tested += 1
                ok, reason, excerpt = _verify_url(candidate_url, name)

                if not ok:
                    # Try other citations
                    found = False
                    for alt_url in citations[1:4]:
                        if alt_url == candidate_url:
                            continue
                        total_urls_tested += 1
                        ok2, reason2, excerpt2 = _verify_url(alt_url, name)
                        if ok2:
                            candidate_url = alt_url
                            reason = reason2
                            excerpt = excerpt2
                            found = True
                            break
                    if not found:
                        print(f"    [REJECT] {name[:50]}: {reason}")
                        rejected_log.append({
                            'name': name, 'province': prov_name,
                            'reason': reason, 'url_tested': candidate_url, 'query': query[:80],
                        })
                        continue

                # Accepted
                naics_c = (rp.get('naics_code') or '').strip()
                naics_n = rp.get('naics_name') or NAICS_MAP.get(naics_c, '')
                if not naics_c:
                    naics_c, naics_n = _infer_naics(name, rp.get('sector', ''))
                path_segs = [s for s in urlparse(candidate_url).path.split('/') if s]
                url_quality = 'direct' if len(path_segs) >= 2 else 'relevant'
                detail = (rp.get('detail') or excerpt or f'{name} is {status}.').strip()[:600]
                proj = {
                    'name':             name,
                    'province':         prov_name,
                    'cma':              (rp.get('cma') or '').strip(),
                    'sector':           (rp.get('sector') or naics_n).strip(),
                    'naics_code':       naics_c,
                    'naics_name':       naics_n,
                    'tags':             rp.get('tags') or [],
                    'value':            (rp.get('value') or 'Not disclosed').strip(),
                    'status':           status,
                    'proponent':        (rp.get('proponent') or '').strip(),
                    'confidence':       'verified',
                    'discovery_source': 'perplexity_verified',
                    'source_url_quality': url_quality,
                    'firstTracked':     TODAY,
                    'lastUpdated':      TODAY,
                    'lastSeen':         TODAY,
                    'statusHistory': [{
                        'status': status,
                        'date':   TODAY,
                        'detail': detail,
                        'source': {'title': name, 'url': candidate_url},
                    }],
                }
                accepted_all.append(proj)
                known_keys.add(key)
                known_names_by_prov.setdefault(prov_name, []).append(name)
                print(f"    [OK] {name[:60]}")

    print(f"\n  [Tier 3] {len(accepted_all)} accepted, {len(rejected_log)} rejected")
    print(f"  [Tier 3] {total_urls_tested} URLs tested")
    return accepted_all, rejected_log, total_urls_tested


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4b: TIER 3 — GOVERNMENT RSS FEED NETWORK
# ══════════════════════════════════════════════════════════════════════════════

def _rss_matches_keywords(entry_text: str, keywords: list[str]) -> bool:
    """Check if RSS entry text matches any feed keywords."""
    text_lower = entry_text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _rss_entry_to_article(entry, feed_cfg: dict) -> dict | None:
    """Convert a feedparser entry to an article dict suitable for Tavily/Claude."""
    url = (entry.get('link') or entry.get('id') or '').strip()
    if not url or not url.startswith('http'):
        return None
    title = (entry.get('title') or '').strip()
    summary = (entry.get('summary') or entry.get('description') or '').strip()
    # Combine title + summary for keyword matching
    combined = f"{title} {summary}"
    keywords = feed_cfg.get('keywords', [])
    if keywords and not _rss_matches_keywords(combined, keywords):
        return None
    # Quick-reject obviously bad URLs
    if quick_reject(url):
        return None
    return {
        'url':      url,
        'title':    title,
        'text':     summary[:3000],
        'domain':   urlparse(url).netloc,
        'province': feed_cfg.get('jurisdiction', ''),
        'feed_id':  feed_cfg.get('id', ''),
        'feed_name': feed_cfg.get('name', ''),
    }


def _save_rss_health(all_feeds: list[dict], health: dict[str, dict]) -> None:
    """Save RSS feed health snapshot to file. Flags feeds failing 3+ consecutive weeks."""
    health_file = f'rss_health_{TODAY}.txt'
    try:
        lines = [f"RSS Feed Health — {TODAY}\n{'='*60}\n"]
        ok_count = sum(1 for v in health.values() if v.get('status') == 'ok')
        err_count = len(health) - ok_count
        lines.append(f"Working: {ok_count}  |  Failed: {err_count}  |  Total: {len(health)}\n")
        for feed in all_feeds:
            fid = feed.get('id', '?')
            h = health.get(fid, {})
            status = h.get('status', 'unknown')
            items = h.get('items', 0)
            latest = h.get('latest', '')
            icon = 'OK' if status == 'ok' else 'XX'
            lines.append(f"  [{icon}] {fid:<25} items={items:<4} latest={latest}")
            if h.get('error'):
                lines.append(f"       Error: {h['error']}")
        with open(health_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    except Exception:
        pass  # non-critical


def run_tier3_rss(seen_urls: set[str] | None = None) -> tuple[list[dict], int, int]:
    """
    Tier 3: Process government RSS feeds from rss_feeds.json.
    Fetches feeds via requests+feedparser, filters by keywords,
    extracts article text via Tavily, sends to Claude Sonnet for project extraction.
    Returns (project_list, feeds_processed, articles_found).
    """
    if not _HAS_FEEDPARSER:
        print("  [Tier 3] feedparser not available — skipping RSS tier.")
        return [], 0, 0
    if not RSS_CONFIG:
        print("  [Tier 3] No rss_feeds.json loaded — skipping RSS tier.")
        return [], 0, 0
    if not os.environ.get('RSS_ENABLED', 'true').lower() in ('true', '1', 'yes'):
        print("  [Tier 3] RSS_ENABLED=false — skipping RSS tier.")
        return [], 0, 0

    if seen_urls is None:
        seen_urls = set()

    print("\n[TIER 3] Government RSS feed network...")

    # Collect all enabled feeds across sections
    all_feeds = []
    for section in ('federal', 'provincial', 'municipal'):
        for feed in RSS_CONFIG.get(section, []):
            if feed.get('enabled', True):
                feed['_section'] = section
                all_feeds.append(feed)

    print(f"  [RSS] {len(all_feeds)} enabled feeds to process")

    # Fetch and parse all feeds
    rss_articles: list[dict] = []
    feeds_ok = 0
    feeds_err = 0
    feed_health: dict[str, dict] = {}  # {feed_id: {status, items, latest_date}}

    for feed in all_feeds:
        url = feed.get('url', '')
        fid = feed.get('id', '?')
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=15, headers=_HEADERS)
            parsed = feedparser.parse(resp.content)
            entries = parsed.get('entries', [])
            feed_articles = 0
            latest_date = ''
            for entry in entries[:30]:  # limit per feed
                # Track latest date for health reporting
                if not latest_date:
                    pub = (entry.get('published') or entry.get('updated') or '')
                    if pub:
                        latest_date = pub[:25]
                art = _rss_entry_to_article(entry, feed)
                if art and art['url'] not in seen_urls:
                    seen_urls.add(art['url'])
                    rss_articles.append(art)
                    feed_articles += 1
            feeds_ok += 1
            feed_health[fid] = {'status': 'ok', 'items': len(entries), 'latest': latest_date}
            if feed_articles:
                print(f"  [RSS] {feed.get('name','')[:35]}: {feed_articles} articles")
        except Exception as e:
            feeds_err += 1
            feed_health[fid] = {'status': 'error', 'items': 0, 'latest': '', 'error': str(e)[:60]}
            print(f"  [RSS] {feed.get('name','')[:35]}: FAILED ({type(e).__name__})")
        time.sleep(0.3)

    print(f"  [RSS] {len(rss_articles)} total articles from {feeds_ok} feeds ({feeds_err} failed)")

    # Save feed health snapshot (lightweight, every run)
    _save_rss_health(all_feeds, feed_health)

    if not rss_articles:
        return [], feeds_ok + feeds_err, 0

    # Select top articles (budget: RSS_MAX_ARTICLES)
    max_rss = int(os.environ.get('RSS_MAX_ARTICLES', '100'))
    # Prioritize by feed priority (lower = better)
    rss_articles.sort(key=lambda a: next(
        (f.get('priority', 99) for f in all_feeds if f.get('id') == a.get('feed_id')), 99
    ))
    selected = rss_articles[:max_rss]
    print(f"  [RSS] Selected {len(selected)} articles for extraction (budget: {max_rss})")

    # Tavily extraction for RSS articles
    rss_urls = [a['url'] for a in selected]
    extracted = _tavily_extract(rss_urls) if tavily_client else {}
    print(f"  [Tavily RSS] Got text from {len(extracted)}/{len(rss_urls)} URLs")

    # Group articles by province for Claude extraction
    by_prov: dict[str, list[dict]] = {}
    for art in selected:
        prov = art.get('province', '') or '_national'
        # Try to map jurisdiction to province name
        if prov and prov not in [p['name'] for p in PROVINCES]:
            # Check if it's in CMA map or needs mapping
            for p in PROVINCES:
                if prov.lower() in p['name'].lower() or p['name'].lower() in prov.lower():
                    prov = p['name']
                    break
        by_prov.setdefault(prov, []).append(art)

    # Claude extraction per province group
    all_projects: list[dict] = []
    for prov_name, arts in by_prov.items():
        # Find threshold for this province
        threshold = '$100M'  # default
        for p in PROVINCES:
            if p['name'] == prov_name:
                threshold = p['threshold']
                break

        # Enrich with Tavily text
        enriched = []
        for art in arts:
            ext = extracted.get(art['url'])
            enriched.append({
                'url':   art['url'],
                'title': (ext or {}).get('title') or art.get('title', ''),
                'text':  (ext or {}).get('text') or art.get('text', ''),
            })

        if not enriched:
            continue

        label = prov_name if prov_name != '_national' else 'National/Federal'
        print(f"  [Claude T3] {label} ({len(enriched)} articles)...", end='', flush=True)
        raw_projs = _claude_extract_from_articles(
            prov_name if prov_name != '_national' else 'Canada',
            threshold, enriched, TODAY
        )
        print(f" -> {len(raw_projs)} raw", end='')

        accepted = 0
        for rp in raw_projs:
            name = (rp.get('name') or '').strip()
            if not name:
                continue
            status = _norm_status(rp.get('status', ''))
            if not status:
                continue
            src_url = (rp.get('source_url') or '').strip()
            naics_c = (rp.get('naics_code') or '').strip()
            naics_n = rp.get('naics_name') or NAICS_MAP.get(naics_c, '')
            if not naics_c:
                naics_c, naics_n = _infer_naics(name, rp.get('sector', ''))
            province = rp.get('province') or prov_name
            if province == '_national':
                province = 'Canada'
            path_segs = [s for s in urlparse(src_url).path.split('/') if s]
            url_quality = 'direct' if len(path_segs) >= 2 else 'relevant'
            proj = {
                'name':             name,
                'province':         province,
                'cma':              (rp.get('cma') or '').strip(),
                'sector':           (rp.get('sector') or naics_n).strip(),
                'naics_code':       naics_c,
                'naics_name':       naics_n,
                'tags':             rp.get('tags') or [],
                'value':            (rp.get('value') or 'Not disclosed').strip(),
                'status':           status,
                'proponent':        (rp.get('proponent') or '').strip(),
                'confidence':       'verified',
                'discovery_source': 'rss_gov',
                'source_url_quality': url_quality,
                'firstTracked':     TODAY,
                'lastUpdated':      TODAY,
                'lastSeen':         TODAY,
                'statusHistory': [{
                    'status': status,
                    'date':   TODAY,
                    'detail': (rp.get('statusHistory_detail') or f'{name} is {status}.').strip(),
                    'source': {
                        'title': (rp.get('source_title') or '').strip(),
                        'url':   src_url,
                        'verified': True,
                        'verified_date': TODAY,
                    },
                }],
            }
            all_projects.append(proj)
            accepted += 1

        print(f", {accepted} accepted")

    print(f"  [Tier 3] {len(all_projects)} total projects from RSS feeds")
    return all_projects, feeds_ok + feeds_err, len(rss_articles)


# ══════════════════════════════════════════════════════════════════════════════
# POST-EXTRACTION: URL VERIFICATION + WAYBACK ARCHIVAL
# ══════════════════════════════════════════════════════════════════════════════

def _post_verify_and_archive(projects: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Post-extraction pass: verify source URLs via url_verify module,
    archive verified URLs via Wayback Machine.
    Returns (verified_projects, rejected_log).
    """
    verified = []
    rejected = []
    wayback_saved = 0

    print(f"\n[POST] URL verification + Wayback archival for {len(projects)} projects...")

    for proj in projects:
        name = proj.get('name', '')
        # Get the primary source URL from statusHistory
        src_url = ''
        if proj.get('statusHistory'):
            src_url = (proj['statusHistory'][0].get('source', {}).get('url') or '').strip()

        # Registry projects (Tier 1) get automatic pass — they come from verified sources
        if proj.get('discovery_source') in ('iaac_registry', 'bc_eao', 'infrastructure_canada', 'nrcan'):
            verified.append(proj)
            # Still try Wayback save for archival
            if src_url:
                archive_url = _wayback_save(src_url)
                if archive_url:
                    proj['archive_url'] = archive_url
                    wayback_saved += 1
            continue

        # For GDELT/RSS discovered projects, verify the source URL
        if src_url and not quick_reject(src_url):
            result = _verify_url_full(src_url, name)
            if result.get('accepted'):
                proj['source_url_quality'] = result.get('status', 'relevant').lower()
                if result.get('excerpt'):
                    proj['source_excerpt'] = result['excerpt'][:500]
                verified.append(proj)
                # Wayback save for verified URLs
                archive_url = _wayback_save(src_url)
                if archive_url:
                    proj['archive_url'] = archive_url
                    wayback_saved += 1
            else:
                rejected.append({
                    'name': name,
                    'province': proj.get('province', ''),
                    'reason': result.get('reason', 'URL verification failed'),
                    'url_tested': src_url,
                    'discovery_source': proj.get('discovery_source', ''),
                })
        elif not src_url:
            # No source URL — still accept but mark quality
            proj['source_url_quality'] = 'none'
            verified.append(proj)
        else:
            rejected.append({
                'name': name,
                'province': proj.get('province', ''),
                'reason': f'URL quick-rejected: {src_url[:60]}',
                'url_tested': src_url,
                'discovery_source': proj.get('discovery_source', ''),
            })

    print(f"  [POST] Verified: {len(verified)}, Rejected: {len(rejected)}, Wayback saved: {wayback_saved}")
    return verified, rejected


def _run_history_backfill(projects: list[dict]) -> int:
    """
    Run Wayback history backfill for all projects that haven't been backfilled yet.
    Modifies projects in-place (adds statusHistory from snapshots).
    Returns count of projects backfilled.
    """
    import os
    if not os.environ.get('WAYBACK_BACKFILL_ENABLED', 'true').lower() in ('true', '1', 'yes'):
        print("  [Backfill] WAYBACK_BACKFILL_ENABLED=false — skipping.")
        return 0

    max_total = int(os.environ.get('WAYBACK_MAX_SNAPSHOTS_SEED', '800'))
    total_snapshots_used = 0
    backfilled = 0

    print(f"\n[BACKFILL] Wayback history backfill ({len(projects)} projects, budget: {max_total} snapshots)...")

    for proj in projects:
        if proj.get('history_backfilled'):
            continue
        if total_snapshots_used >= max_total:
            print(f"  [Backfill] Snapshot budget exhausted ({total_snapshots_used}/{max_total})")
            break

        name = proj.get('name', '')
        province = proj.get('province', '')
        src_url = ''
        current_status = proj.get('status', '')
        current_detail = ''
        if proj.get('statusHistory'):
            src_url = (proj['statusHistory'][-1].get('source', {}).get('url') or '').strip()
            current_detail = proj['statusHistory'][-1].get('detail', '')

        if not src_url:
            continue

        result = _wayback_backfill(
            project_name=name,
            source_url=src_url,
            province=province,
            current_status=current_status,
            current_detail=current_detail,
            today=TODAY,
        )

        snapshots_used = result.get('snapshots_processed', 0)
        total_snapshots_used += snapshots_used

        if result.get('statusHistory'):
            # Prepend historical entries before current status entry
            current_history = proj.get('statusHistory', [])
            proj['statusHistory'] = result['statusHistory'] + current_history
            proj['history_backfilled'] = True
            proj['history_earliest_date'] = result.get('history_earliest_date', TODAY)
            backfilled += 1
            print(f"  [Backfill] {name[:45]}: {len(result['statusHistory'])} historical entries ({snapshots_used} snapshots)")
        else:
            proj['history_backfilled'] = True
            proj['history_earliest_date'] = TODAY

    print(f"  [Backfill] {backfilled} projects backfilled, {total_snapshots_used} snapshots used")
    return backfilled


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: WRITE TO FIRESTORE
# ══════════════════════════════════════════════════════════════════════════════

def write_to_firestore(db, projects: list[dict]) -> int:
    """Batch-write all projects to SQLite via upsert_project. Returns count written."""
    if not projects:
        return 0
    written = 0
    for p in projects:
        upsert_project(db, p)
        written += 1
        if written % 400 == 0:
            print(f"  [SQLite] Written {written}/{len(projects)}...")
    db.commit()
    print(f"  [SQLite] Written {written}/{len(projects)}...")
    return written


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: QUALITY REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(
    all_projects: list[dict],
    rejected_log: list[dict],
    merge_log: list[dict],
    stats: dict,
    report_path: str | None = None,
) -> None:
    from collections import Counter

    if report_path is None:
        report_path = f'seed_audit_{TODAY}.txt'

    lines = []
    def L(s=''):
        lines.append(s)
        print(s)

    L(f"{'='*70}")
    L(f"  SEED AUDIT REPORT -- {TODAY}")
    L(f"{'='*70}")
    L(f"  Total projects written to Firestore: {len(all_projects)}")
    L()

    # ══════════════════════════════════════════════════════════════════════
    # PROJECT COVERAGE
    # ══════════════════════════════════════════════════════════════════════

    # ── By province ────────────────────────────────────────────────────────
    L("-- Projects by Province --")
    by_prov = Counter(p['province'] for p in all_projects)
    low_prov = []
    for prov, cnt in sorted(by_prov.items()):
        flag = '  <<< LOW COVERAGE' if cnt < 3 else ''
        L(f"  {prov:<35} {cnt:>4}{flag}")
        if cnt < 3:
            low_prov.append(prov)
    L()

    # ── By NAICS ───────────────────────────────────────────────────────────
    L("-- Projects by NAICS Code --")
    by_naics = Counter(p.get('naics_code','?') for p in all_projects)
    missing_naics = []
    for code in sorted(NAICS_MAP.keys()):
        cnt = by_naics.get(code, 0)
        flag = '  <<< COVERAGE GAP' if cnt == 0 else ''
        L(f"  {code:<8} {NAICS_MAP[code]:<60} {cnt:>4}{flag}")
        if cnt == 0:
            missing_naics.append(f"{code}: {NAICS_MAP[code]}")
    L()

    # ── By discovery source ────────────────────────────────────────────────
    L("-- Projects by Discovery Source --")
    by_src = Counter(p.get('discovery_source','?') for p in all_projects)
    for src, cnt in sorted(by_src.items(), key=lambda x: -x[1]):
        L(f"  {src:<30} {cnt:>4}")
    L()

    # ── By status ──────────────────────────────────────────────────────────
    L("-- Projects by Status --")
    by_status = Counter(p.get('status','?') for p in all_projects)
    for st, cnt in sorted(by_status.items(), key=lambda x: -x[1]):
        L(f"  {st:<30} {cnt:>4}")
    L()

    # ── Value stats ────────────────────────────────────────────────────────
    nd_count = sum(1 for p in all_projects if (p.get('value') or '').strip() == 'Not disclosed')
    total = max(len(all_projects), 1)
    L(f"-- Value = 'Not disclosed': {nd_count}/{len(all_projects)} ({100*nd_count//total}%)")
    L()

    # ── URL quality ────────────────────────────────────────────────────────
    direct_count = sum(1 for p in all_projects if p.get('source_url_quality') == 'direct')
    L(f"-- Source URL quality: {direct_count} direct, {len(all_projects)-direct_count} relevant")
    L()

    # ══════════════════════════════════════════════════════════════════════
    # DISCOVERY STATS
    # ══════════════════════════════════════════════════════════════════════
    L("-- Discovery Statistics --")
    L(f"  GDELT queries executed:        {stats.get('gdelt_queries', 0)}")
    L(f"  Unique articles found:         {stats.get('unique_articles', 0)}")
    L(f"  Articles sent to Tavily:       {stats.get('articles_to_tavily', 0)}")
    L(f"  RSS feeds processed:           {stats.get('t3_feeds', 0)}")
    L(f"  RSS articles found:            {stats.get('t3_articles', 0)}")
    L(f"  Projects extracted (raw):      {stats.get('raw_extracted', 0)}")
    L(f"  Projects after URL verify:     {stats.get('url_verified', len(all_projects))}")
    L(f"  Post-verify rejected:          {stats.get('post_rejected', 0)}")
    L(f"  Projects rejected (total):     {len(rejected_log)}")
    L(f"  Dedup merges:                  {len(merge_log)}")
    L(f"  Tier 1 (registries):           {stats.get('t1_added', 0)}")
    L(f"  Tier 2 (GDELT+Claude):         {stats.get('t2_added', 0)}")
    L(f"  Tier 3 (RSS feeds):            {stats.get('t3_added', 0)}")
    L(f"  Perplexity:                    DISABLED")
    L(f"  Sentiment topics:              {stats.get('sentiment_topics', 0)}")
    L(f"  Sentiment index:               {stats.get('sentiment_index', 'N/A')}")
    L()

    # ── Rejection reasons breakdown ───────────────────────────────────────
    if rejected_log:
        L("-- Rejection Reasons --")
        by_reason = Counter(r.get('reason', 'unknown') for r in rejected_log)
        for reason, cnt in sorted(by_reason.items(), key=lambda x: -x[1]):
            L(f"  {reason:<50} {cnt:>4}")
        L()

    # ══════════════════════════════════════════════════════════════════════
    # WAYBACK STATS
    # ══════════════════════════════════════════════════════════════════════
    backfilled = stats.get('backfilled', 0)
    backfill_attempted = sum(1 for p in all_projects if p.get('history_backfilled'))
    no_history = sum(1 for p in all_projects if not p.get('history_backfilled'))
    earliest_dates = [p.get('history_earliest_date', '') for p in all_projects if p.get('history_earliest_date')]
    avg_earliest = ''
    if earliest_dates:
        sorted_dates = sorted(d for d in earliest_dates if d)
        avg_earliest = sorted_dates[len(sorted_dates) // 2] if sorted_dates else ''

    L("-- Wayback History Stats --")
    L(f"  Backfill attempted:            {backfill_attempted}")
    L(f"  Backfill with history:         {backfilled}")
    L(f"  Not yet backfilled:            {no_history}")
    L(f"  Median earliest date:          {avg_earliest or 'N/A'}")
    # Count total statusHistory entries from backfill
    total_hist_entries = sum(
        len([h for h in (p.get('statusHistory') or []) if h.get('date', '') < p.get('firstTracked', TODAY)])
        for p in all_projects if p.get('history_backfilled')
    )
    L(f"  Historical entries added:      {total_hist_entries}")
    L()

    # ══════════════════════════════════════════════════════════════════════
    # COVERAGE GAPS
    # ══════════════════════════════════════════════════════════════════════
    has_gaps = missing_naics or low_prov
    if has_gaps:
        L("-- Coverage Gaps --")
        if missing_naics:
            for m in missing_naics:
                L(f"  COVERAGE GAP: Consider enabling Perplexity gap fill for {m}")
        if low_prov:
            for prov in low_prov:
                cnt = by_prov.get(prov, 0)
                L(f"  LOW COVERAGE: {prov} has only {cnt} project(s) — consider additional discovery sources")
        L()

    # ══════════════════════════════════════════════════════════════════════
    # REJECTED ITEMS (detailed)
    # ══════════════════════════════════════════════════════════════════════
    if rejected_log:
        L(f"-- Rejected Projects ({len(rejected_log)}) --")
        for r in rejected_log[:50]:  # Cap at 50 for readability
            L(f"  [{r.get('province','?')[:15]:<15}] {r.get('name','?')[:50]}")
            L(f"           Reason: {r.get('reason','?')}")
            if r.get('url_tested'):
                L(f"           URL:    {r['url_tested'][:80]}")
        if len(rejected_log) > 50:
            L(f"  ... ({len(rejected_log) - 50} more rejected)")
        L()

    # ── Merge log ──────────────────────────────────────────────────────────
    if merge_log:
        L(f"-- Dedup Merges ({len(merge_log)}) --")
        for m in merge_log[:30]:
            L(f"  KEPT: {m.get('kept','?')[:50]}")
            L(f"  MERGED: {m.get('merged','?')[:50]}  (reason: {m.get('reason','')})")
        if len(merge_log) > 30:
            L(f"  ... ({len(merge_log) - 30} more merges)")
        L()

    # ══════════════════════════════════════════════════════════════════════
    # ANNUAL COST SUMMARY
    # ══════════════════════════════════════════════════════════════════════
    L("-- Annual Cost Estimate --")
    L(f"  Government registries + GDELT + RSS + Wayback CDX  = Free")
    L(f"  Tavily Extract (~295 articles + ~100 RSS + ~800 snapshots seed)")
    L(f"                                                      = ~$65/yr")
    L(f"  Claude Opus (macro writing: exec summary + national + global)")
    L(f"                                                      = ~$7/yr")
    L(f"  Claude Sonnet (extraction + provincial/industry + citations)")
    L(f"                                                      = ~$25/yr")
    L(f"  Gemini 2.5 Flash (snapshots + JSON fallback + unsourced)")
    L(f"                                                      = ~$5/yr")
    L(f"  {'─'*50}")
    L(f"  TOTAL                                               = ~$102/yr")
    L()

    L(f"{'='*70}")

    # Save to file
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\n[Report] Saved to {report_path}")


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY UPDATE (incremental — does NOT wipe /projects)
# ══════════════════════════════════════════════════════════════════════════════

def weekly_update(days_back: int = 7, province_filter: str = '', re_backfill: bool = False):
    """
    Incremental project update — discovers new projects and updates existing ones.
    Does NOT wipe /projects collection. Uses upsert_flat_projects() for merging.

    Weekly (default): 7-day GDELT + RSS lookback.
    Deep sweep: 365-day lookback + re-attempt backfill for unbackfilled projects.
    """
    from project_sync import upsert_flat_projects as _upsert_flat

    mode = "DEEP SWEEP" if days_back > 30 else "WEEKLY UPDATE"
    mode_label = f"{mode}: {province_filter}" if province_filter else mode
    print(f"\n{'#'*70}")
    print(f"  seed_projects_v2.py — {mode_label}")
    print(f"  {TODAY}  (lookback: {days_back}d)")
    print(f"{'#'*70}\n")

    rejected_log: list[dict] = []

    # Province filter helper
    _pf = province_filter.strip().lower() if province_filter else ''
    def _prov_ok(proj):
        if not _pf:
            return True
        return (proj.get('province') or '').lower().startswith(_pf)

    # ── STEP 1: Tier 1 — Government Registries ──────────────────────────
    t1_projs = run_tier1()
    if _pf:
        t1_projs = [p for p in t1_projs if _prov_ok(p)]

    # ── STEP 2: Tier 2 — GDELT + Tavily + Claude ────────────────────────
    t2_result = run_tier2(days_back=days_back)
    t2_projs, gdelt_queries, unique_articles, tavily_sent = t2_result
    if _pf:
        t2_projs = [p for p in t2_projs if _prov_ok(p)]

    # ── STEP 3: Tier 3 — Government RSS Feed Network ────────────────────
    seen_urls: set[str] = set()
    for proj in t1_projs + t2_projs:
        for sh in (proj.get('statusHistory') or []):
            u = (sh.get('source', {}).get('url') or '').strip()
            if u:
                seen_urls.add(u)

    t3_projs, t3_feeds_processed, t3_articles = run_tier3_rss(seen_urls=seen_urls)
    if _pf:
        t3_projs = [p for p in t3_projs if _prov_ok(p)]

    # ── STEP 3b: Consumer Sentiment ──────────────────────────────────────
    sentiment_result = None
    try:
        from sentiment import collect_sentiment, SENTIMENT_ENABLED
        if SENTIMENT_ENABLED:
            print(f"\n[TIER 4] Consumer sentiment collection...")
            sentiment_result = collect_sentiment()
            if sentiment_result:
                print(f"  [Sentiment] {len(sentiment_result.get('topics', []))} topics, "
                      f"index={sentiment_result.get('sentiment_index', 'N/A')}")
    except ImportError:
        pass
    except Exception as e:
        print(f"  [Sentiment] Failed (non-critical): {type(e).__name__}")

    # ── STEP 4: Post-extraction URL verification ─────────────────────────
    all_discovered = t1_projs + t2_projs + t3_projs
    verified_projects, post_rejected = _post_verify_and_archive(all_discovered)
    rejected_log.extend(post_rejected)

    # ── STEP 4b: Wayback history backfill (new projects only) ────────────
    backfilled_count = _run_history_backfill(verified_projects)

    print(f"\n{'-'*55}")
    print(f"  DISCOVERED: {len(verified_projects)} verified projects")
    print(f"    Tier 1 (registries):        {len(t1_projs)}")
    print(f"    Tier 2 (GDELT+Claude):      {len(t2_projs)}")
    print(f"    Tier 3 (RSS feeds):         {len(t3_projs)}")
    print(f"    Post-verify rejected:       {len(post_rejected)}")
    print(f"    History backfilled:         {backfilled_count}")
    print(f"{'-'*55}")

    # ── STEP 5: Incremental upsert to Firestore ─────────────────────────
    print(f"\n[UPSERT] Merging {len(verified_projects)} projects into Firestore...")
    _upsert_flat(db, verified_projects)

    # ── STEP 5b: Stale project flagging ──────────────────────────────────
    stale_warned = 0
    stale_unknown = 0
    four_weeks_ago = (date.today() - timedelta(weeks=4)).isoformat()
    three_months_ago = (date.today() - timedelta(days=90)).isoformat()

    for doc in get_all_projects(db):
        last_seen = doc.get('lastSeen', '')
        if not last_seen:
            continue
        if last_seen < three_months_ago:
            if not doc.get('stale_warning'):
                updated = dict(doc)
                updated['stale_warning'] = True
                updated['stale_since'] = last_seen
                upsert_project(db, updated)
                stale_warned += 1
        elif last_seen < four_weeks_ago:
            if doc.get('status') not in ('Unknown', 'Completed', 'Cancelled'):
                updated = dict(doc)
                updated['status'] = 'Unknown'
                upsert_project(db, updated)
                stale_unknown += 1

    if stale_warned or stale_unknown:
        print(f"  [Stale] {stale_unknown} flagged Unknown (4+ wk), "
              f"{stale_warned} warned (3+ mo)")

    # ── STEP 5c: Re-attempt backfill for unbackfilled (deep sweep only) ──
    if re_backfill:
        print(f"\n[DEEP SWEEP] Re-attempting backfill for unbackfilled projects...")
        unbackfilled = [doc for doc in get_all_projects(db)
                        if not doc.get('history_backfilled')]
        if unbackfilled:
            rebf = _run_history_backfill(unbackfilled)
            # Write backfill results back to SQLite
            for proj in unbackfilled:
                if proj.get('history_backfilled'):
                    updated = dict(proj)
                    updated['history_backfilled'] = True
                    updated['history_earliest_date'] = proj.get('history_earliest_date', TODAY)
                    upsert_project(db, updated)
            print(f"  [Deep Sweep] Re-backfilled {rebf} projects")

    # ── STEP 5d: Write sentiment ─────────────────────────────────────────
    if sentiment_result:
        try:
            from db import save_dashboard_state as _save_ds
            _save_ds(db, 'latest_sentiment', {
                'updatedAt': TODAY,
                'consumer_sentiment': sentiment_result,
            })
            print(f"  [Sentiment] Saved to SQLite")
        except Exception as e:
            print(f"  [Sentiment] Write failed: {e}")

    # ── STEP 6: Quality report ───────────────────────────────────────────
    stats = {
        'gdelt_queries': gdelt_queries,
        'unique_articles': unique_articles,
        'articles_to_tavily': tavily_sent,
        'raw_extracted': len(t2_projs) + len(t3_projs),
        'url_verified': len(verified_projects),
        't1_added': len(t1_projs),
        't2_added': len(t2_projs),
        't3_added': len(t3_projs),
        't3_feeds': t3_feeds_processed,
        't3_articles': t3_articles,
        'post_rejected': len(post_rejected),
        'backfilled': backfilled_count,
        'sentiment_topics': len(sentiment_result.get('topics', [])) if sentiment_result else 0,
        'sentiment_index': sentiment_result.get('sentiment_index') if sentiment_result else None,
    }
    generate_report(verified_projects, rejected_log, [], stats)

    print(f"\n[DONE] {mode} complete. {len(verified_projects)} projects processed.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN (full seed — wipes and rebuilds /projects)
# ══════════════════════════════════════════════════════════════════════════════

def main(days_back: int = 365, province_filter: str = ''):
    mode_label = f"PROVINCE: {province_filter}" if province_filter else "FULL PROJECT REBUILD"
    print(f"\n{'#'*70}")
    print(f"  seed_projects_v2.py -- {mode_label}")
    print(f"  {TODAY}  (lookback: {days_back}d)")
    print(f"{'#'*70}\n")

    # ── STEP 0: Backup ────────────────────────────────────────────────────────
    backup_projects(db)

    # ── STEP 1: Wipe ──────────────────────────────────────────────────────────
    wipe_projects(db)

    # ── Shared dedup state ────────────────────────────────────────────────────
    known_keys: set[str] = set()
    known_names_by_prov: dict[str, list[str]] = {}
    # Store projects in a dict keyed by norm_key for merge support
    projects_map: dict[str, dict] = {}
    merge_log: list[dict] = []
    rejected_log: list[dict] = []

    def _url_quality_rank(q: str) -> int:
        """Lower = better. direct=0, relevant=1, other=2."""
        if q == 'direct':
            return 0
        if q == 'relevant':
            return 1
        return 2

    def _add(proj: dict) -> bool:
        """
        Add to projects_map if not a duplicate.
        If duplicate found: merge — keep entry with higher-quality source URL,
        append the other source to statusHistory.
        Returns True if a new entry was added (not merged).
        """
        name = (proj.get('name') or '').strip()
        prov = (proj.get('province') or '').strip()
        if not name or not prov:
            return False
        key = _norm_key(name, prov)

        # ── Primary: exact normalize_key match ────────────────────────────
        if key in projects_map:
            _merge(projects_map[key], proj, 'exact key match', merge_log)
            return False

        # ── Secondary: fuzzy name match within province (0.85) ────────────
        existing_names = known_names_by_prov.get(prov, [])
        fuzzy_hit = _fuzzy_match(name, existing_names)
        if fuzzy_hit:
            existing_key = _norm_key(fuzzy_hit, prov)
            if existing_key in projects_map:
                _merge(projects_map[existing_key], proj, f'fuzzy name ({fuzzy_hit})', merge_log)
                return False

        # ── Tertiary: same province + sector + value within 20% ───────────
        new_val = _parse_value(proj.get('value', ''))
        new_naics = proj.get('naics_code', '')
        if new_val and new_naics:
            for ekey, eproj in projects_map.items():
                if eproj.get('province') != prov:
                    continue
                if eproj.get('naics_code') != new_naics:
                    continue
                ev = _parse_value(eproj.get('value', ''))
                if ev and abs(ev - new_val) / max(ev, 1) < 0.20:
                    _merge(eproj, proj, f'prov+sector+value~20%', merge_log)
                    return False

        # No duplicate — add as new
        known_keys.add(key)
        known_names_by_prov.setdefault(prov, []).append(name)
        projects_map[key] = proj
        return True

    def _merge(existing: dict, incoming: dict, reason: str, log: list):
        """Merge incoming into existing: keep higher-quality URL, append statusHistory."""
        merge_log.append({
            'kept': existing.get('name', ''),
            'merged': incoming.get('name', ''),
            'reason': reason,
        })
        # If incoming has better URL quality, swap source info
        eq = _url_quality_rank(existing.get('source_url_quality', ''))
        iq = _url_quality_rank(incoming.get('source_url_quality', ''))
        if iq < eq:
            # Incoming is better — swap primary source
            old_hist = existing.get('statusHistory', [])
            existing['source_url_quality'] = incoming.get('source_url_quality', '')
            if incoming.get('statusHistory'):
                existing['statusHistory'] = incoming['statusHistory'] + old_hist
        else:
            # Append incoming history to existing
            if incoming.get('statusHistory'):
                existing.setdefault('statusHistory', []).extend(incoming['statusHistory'])
        # Update lastSeen
        existing['lastSeen'] = TODAY
        existing['lastUpdated'] = TODAY

    # Province filter helper
    _pf = province_filter.strip().lower() if province_filter else ''
    def _prov_ok(proj):
        if not _pf:
            return True
        return (proj.get('province') or '').lower().startswith(_pf)

    # ── STEP 2: Tier 1 — Government Registries ─────────────────────────────
    t1_projs = run_tier1()
    if _pf:
        t1_projs = [p for p in t1_projs if _prov_ok(p)]
    t1_added = sum(1 for p in t1_projs if _add(p))
    print(f"  [Tier 1] Added {t1_added}/{len(t1_projs)} (deduped)")

    # ── STEP 3: Tier 2 — GDELT + Tavily + Claude ─────────────────────────────
    t2_result = run_tier2(days_back=days_back)
    t2_projs, gdelt_queries, unique_articles, tavily_sent = t2_result
    if _pf:
        t2_projs = [p for p in t2_projs if _prov_ok(p)]
    t2_added = sum(1 for p in t2_projs if _add(p))
    print(f"  [Tier 2] Added {t2_added}/{len(t2_projs)} (deduped)")

    # ── STEP 4a: Tier 3 — Government RSS Feed Network ────────────────────────
    # Collect all URLs already seen from Tiers 1-2 to avoid RSS duplicates
    seen_urls_t3: set[str] = set()
    for proj in projects_map.values():
        for sh in (proj.get('statusHistory') or []):
            u = (sh.get('source', {}).get('url') or '').strip()
            if u:
                seen_urls_t3.add(u)

    t3_projs, t3_feeds_processed, t3_articles = run_tier3_rss(seen_urls=seen_urls_t3)
    if _pf:
        t3_projs = [p for p in t3_projs if _prov_ok(p)]
    t3_added = sum(1 for p in t3_projs if _add(p))
    print(f"  [Tier 3] Added {t3_added}/{len(t3_projs)} (deduped)")

    # ── Perplexity: REMOVED (replaced by Gemini grounded search) ──────────────
    print(f"\n  [Perplexity] REMOVED — replaced by Gemini grounded search (Tier 2)")

    # ── TIER 4: Consumer Sentiment Collection ─────────────────────────────────
    sentiment_result = None
    try:
        from sentiment import collect_sentiment, SENTIMENT_ENABLED
        if SENTIMENT_ENABLED:
            print(f"\n[TIER 4] Consumer sentiment collection...")
            sentiment_result = collect_sentiment()
            if sentiment_result:
                topic_count = len(sentiment_result.get('topics', []))
                print(f"  [Sentiment] Collected {topic_count} topics, "
                      f"index={sentiment_result.get('sentiment_index', 'N/A')}")
            else:
                print(f"  [Sentiment] No sentiment data collected")
        else:
            print(f"\n  [Sentiment] DISABLED (set SENTIMENT_ENABLED=true in .env)")
    except ImportError:
        print(f"\n  [Sentiment] sentiment.py not found — skipping")
    except Exception as e:
        print(f"\n  [Sentiment] Collection failed (non-critical): {e}")

    # ── STEP 4b: Post-extraction URL verification + Wayback archival ─────────
    raw_projects = list(projects_map.values())
    verified_projects, post_rejected = _post_verify_and_archive(raw_projects)
    rejected_log.extend(post_rejected)

    # Rebuild projects_map with only verified projects
    projects_map.clear()
    known_keys.clear()
    known_names_by_prov.clear()
    for proj in verified_projects:
        name = (proj.get('name') or '').strip()
        prov = (proj.get('province') or '').strip()
        if name and prov:
            key = _norm_key(name, prov)
            projects_map[key] = proj
            known_keys.add(key)
            known_names_by_prov.setdefault(prov, []).append(name)

    all_projects = list(projects_map.values())

    # ── STEP 4c: Wayback history backfill ───────────────────────────────────────
    backfilled_count = _run_history_backfill(all_projects)

    print(f"\n{'-'*55}")
    print(f"  TOTAL PROJECTS: {len(all_projects)}")
    print(f"    Tier 1 (registries):        {t1_added}")
    print(f"    Tier 2 (GDELT+Claude):      {t2_added}")
    print(f"    Tier 3 (RSS feeds):         {t3_added}")
    print(f"    Post-verify rejected:       {len(post_rejected)}")
    print(f"    History backfilled:         {backfilled_count}")
    print(f"    Dedup merges:               {len(merge_log)}")
    print(f"{'-'*55}")

    # ── STEP 5: Write to SQLite ───────────────────────────────────────────────
    print(f"\n[WRITE] Writing {len(all_projects)} projects to SQLite...")
    written = write_to_firestore(db, all_projects)
    print(f"  [WRITE] {written} documents written.")

    # Write sentiment data if collected
    if sentiment_result:
        try:
            from db import save_dashboard_state as _save_ds2
            _save_ds2(db, 'latest_sentiment', {
                'updatedAt': TODAY,
                'consumer_sentiment': sentiment_result,
            })
            print(f"  [WRITE] Sentiment data saved to SQLite")
        except Exception as e:
            print(f"  [WRITE] Sentiment write failed (non-critical): {e}")

    # ── STEP 6: Quality report ────────────────────────────────────────────────
    stats = {
        'gdelt_queries': gdelt_queries,
        'unique_articles': unique_articles,
        'articles_to_tavily': tavily_sent,
        'raw_extracted': len(t2_projs) + len(t3_projs),
        'url_verified': len(all_projects),
        't1_added': t1_added,
        't2_added': t2_added,
        't3_added': t3_added,
        't3_feeds': t3_feeds_processed,
        't3_articles': t3_articles,
        'post_rejected': len(post_rejected),
        'backfilled': backfilled_count,
        'sentiment_topics': len(sentiment_result.get('topics', [])) if sentiment_result else 0,
        'sentiment_index': sentiment_result.get('sentiment_index') if sentiment_result else None,
    }
    generate_report(all_projects, rejected_log, merge_log, stats)

    print(f"\n[DONE] Rebuild complete. {len(all_projects)} projects in /projects collection.")


def test_queries():
    """Quick smoke-test: print all GDELT query strings without hitting APIs."""
    print(f"\n{'='*70}")
    print(f"  --test-queries: GDELT + RSS query inventory")
    print(f"{'='*70}\n")

    # Section A: Province templates
    print(f"Section A: _GDELT_TMPL ({len(_GDELT_TMPL)} templates per province):")
    for i, tmpl in enumerate(_GDELT_TMPL, 1):
        print(f"  {i:>3}. {tmpl}")

    # Section D: Company queries from watchlist
    company_prov_q, company_nat_q = _build_company_queries()
    company_count = len(company_prov_q) + len(company_nat_q)

    prov_total = len(_GDELT_TMPL) * len(PROVINCES)
    cma_total  = len(_CMA_TMPL) * len(_CMA_CITIES)
    trade_total = len(_TRADE_QUERIES)
    grand_total = prov_total + cma_total + trade_total + company_count

    print(f"\n  Section A (province):  {len(_GDELT_TMPL)} x {len(PROVINCES)} = {prov_total}")
    print(f"  Section B (CMA):       {len(_CMA_TMPL)} x {len(_CMA_CITIES)} = {cma_total}")
    print(f"  Section C (trade):     {trade_total}")
    print(f"  Section D (company):   {len(company_prov_q)} prov + {len(company_nat_q)} nat = {company_count}")
    print(f"  GRAND TOTAL:           {grand_total} GDELT queries\n")

    print(f"CMA cities ({len(_CMA_CITIES)}):")
    for c in _CMA_CITIES:
        prov = _CMA_PROV_MAP.get(c, '?')
        print(f"  {c:<30} -> {prov}")
    print(f"\nCMA templates ({len(_CMA_TMPL)}):")
    for tmpl in _CMA_TMPL:
        print(f"  {tmpl}")

    print(f"\nTrade publication queries ({trade_total}):")
    for i, q in enumerate(_TRADE_QUERIES, 1):
        print(f"  {i}. {q}")

    # Company queries
    print(f"\nSection D: Company queries from watchlist ({company_count}):")
    print(f"  Provincial company queries ({len(company_prov_q)}):")
    for kw, prov in company_prov_q[:10]:
        print(f"    [{prov[:15]:<15}] {kw}")
    if len(company_prov_q) > 10:
        print(f"    ... ({len(company_prov_q) - 10} more)")
    print(f"  National company queries ({len(company_nat_q)}):")
    for kw in company_nat_q[:10]:
        print(f"    {kw}")
    if len(company_nat_q) > 10:
        print(f"    ... ({len(company_nat_q) - 10} more)")

    print(f"\nINDUSTRY_VECTORS ({len(INDUSTRY_VECTORS)} vectors):")
    for i, v in enumerate(INDUSTRY_VECTORS, 1):
        print(f"  {i:>2}. {v}")

    print(f"\nNAICS_MAP ({len(NAICS_MAP)} sectors):")
    for code, name in NAICS_MAP.items():
        print(f"  {code:<8} {name}")

    print(f"\nProvinces ({len(PROVINCES)}):")
    for p in PROVINCES:
        print(f"  {p['name']:<30} gdelt={p['gdelt']:<25} threshold={p['threshold']}")

    # RSS feeds
    rss_count = 0
    for section in ('federal', 'provincial', 'municipal'):
        feeds = [f for f in RSS_CONFIG.get(section, []) if f.get('enabled', True)]
        rss_count += len(feeds)
    print(f"\nRSS feeds ({rss_count} enabled):")
    for section in ('federal', 'provincial', 'municipal'):
        feeds = [f for f in RSS_CONFIG.get(section, []) if f.get('enabled', True)]
        print(f"  {section}: {len(feeds)} feeds")
        for f in feeds[:5]:
            print(f"    {f.get('id',''):<25} {f.get('name','')[:40]}")
        if len(feeds) > 5:
            print(f"    ... ({len(feeds) - 5} more)")

    # Sample expanded queries for first province
    sample_prov = PROVINCES[0]
    print(f"\nSample expanded queries for {sample_prov['name']} (first 10):")
    for tmpl in _GDELT_TMPL[:10]:
        print(f"  {tmpl.format(p=sample_prov['gdelt'])}")
    print(f"  ... ({len(_GDELT_TMPL) - 10} more)")

    print(f"\n{'='*70}")
    print(f"  All {grand_total} GDELT queries + {rss_count} RSS feeds + {len(INDUSTRY_VECTORS)} industry vectors OK")
    print(f"{'='*70}")


def audit_citations():
    """
    Link rot audit: re-verify ALL URLs in /projects collection.
    Dead + has archive → link_rotted_archived.
    Dead + no archive → attempt Wayback save, mark link_rotted_unarchived.
    Log to link_audit_{date}.txt.
    """
    print(f"\n{'='*70}")
    print(f"  --audit-citations: Link Rot Audit (projects + newsletter)")
    print(f"{'='*70}\n")

    total = 0
    passed = 0
    dead_archived = 0
    dead_unarchived = 0
    failures = []

    for doc in get_all_projects(db):
        name = doc.get('name', '(unnamed)')
        needs_update = False

        import json as _json
        status_history = doc.get('statusHistory') or []
        if isinstance(status_history, str):
            try:
                status_history = _json.loads(status_history)
            except Exception:
                status_history = []

        for entry in status_history:
            src = entry.get('source', {})
            url = src.get('url', '')
            if not url:
                continue
            total += 1
            if quick_reject(url):
                continue

            result = _verify_url_full(url, name)
            if result.get('accepted'):
                passed += 1
            else:
                # Dead link — check for existing archive
                archive_url = src.get('archive_url', '')
                if archive_url:
                    entry['link_status'] = 'link_rotted_archived'
                    dead_archived += 1
                else:
                    # Attempt Wayback save
                    saved = _wayback_save(url)
                    if saved:
                        src['archive_url'] = saved
                        entry['link_status'] = 'link_rotted_archived'
                        dead_archived += 1
                        needs_update = True
                    else:
                        entry['link_status'] = 'link_rotted_unarchived'
                        dead_unarchived += 1
                        needs_update = True

                failures.append({
                    'name': name,
                    'url': url,
                    'reason': result.get('reason', 'dead'),
                    'has_archive': entry.get('link_status') == 'link_rotted_archived',
                })
                print(f"  [DEAD] {name[:45]} -> {result.get('reason', 'dead')}")

        # Write back link_status updates
        if needs_update:
            updated_doc = dict(doc)
            updated_doc['statusHistory'] = status_history
            upsert_project(db, updated_doc)

    # Also check newsletter citation URLs
    print(f"\n  Checking latest newsletter citations...")
    nl_total = 0
    from db import get_dashboard_state as _get_ds
    payload = _get_ds(db, 'latest')
    if payload:
        for section_key in ('national', 'global', 'goodsIndustries', 'servicesIndustries'):
            data = payload.get(section_key)
            if not data:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                for src_list_key in ('sources', 'industrySources'):
                    for src in (item.get(src_list_key) or []):
                        url = src.get('url', '')
                        if url and not quick_reject(url):
                            nl_total += 1
                            result = _verify_url_full(url, src.get('title', ''))
                            if not result.get('accepted'):
                                failures.append({
                                    'name': f'newsletter:{section_key}',
                                    'url': url,
                                    'reason': result.get('reason', 'dead'),
                                    'has_archive': False,
                                })
    if nl_total:
        print(f"    Checked {nl_total} newsletter citation URLs")

    dead_total = dead_archived + dead_unarchived
    print(f"\n{'─'*55}")
    print(f"  Total URLs checked: {total + nl_total}")
    print(f"  Passed:             {passed}")
    print(f"  Dead (archived):    {dead_archived}")
    print(f"  Dead (unarchived):  {dead_unarchived}")
    print(f"{'─'*55}")

    if failures:
        audit_file = f'link_audit_{TODAY}.txt'
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write(f"Link Rot Audit — {TODAY}\n{'='*60}\n\n")
            for fl in failures:
                archive_note = ' [has archive]' if fl.get('has_archive') else ' [NO archive]'
                f.write(f"Project: {fl['name']}\n  URL: {fl['url']}\n  "
                        f"Reason: {fl['reason']}{archive_note}\n\n")
            f.write(f"\nSummary: {passed} OK, {dead_archived} dead+archived, "
                    f"{dead_unarchived} dead+unarchived out of {total + nl_total}\n")
        print(f"\n  Report saved to {audit_file}")


def test_feeds():
    """Test RSS feed health: check each feed URL, report working/broken/stale."""
    import feedparser

    print(f"\n{'='*70}")
    print(f"  --test-feeds: RSS Feed Health Check")
    print(f"{'='*70}\n")

    results = []
    for section in ('federal', 'provincial', 'municipal'):
        feeds = RSS_CONFIG.get(section, [])
        for feed in feeds:
            if not feed.get('enabled', True):
                continue
            fid = feed.get('id', '?')
            url = feed.get('url', '')
            name = feed.get('name', fid)
            status = 'unknown'
            item_count = 0
            latest_date = ''
            error_msg = ''

            try:
                resp = requests.get(url, timeout=15, headers={
                    'User-Agent': 'CAN-Macro-Dashboard/1.0'
                })
                if resp.status_code != 200:
                    status = 'broken'
                    error_msg = f'HTTP {resp.status_code}'
                else:
                    parsed = feedparser.parse(resp.content)
                    entries = parsed.entries or []
                    item_count = len(entries)
                    if item_count == 0:
                        status = 'empty'
                    else:
                        status = 'working'
                        # Check most recent entry date
                        for e in entries[:3]:
                            pub = e.get('published', '') or e.get('updated', '')
                            if pub:
                                latest_date = pub[:25]
                                break
                        if not latest_date:
                            status = 'working (no dates)'
            except requests.exceptions.SSLError:
                status = 'ssl_error'
                error_msg = 'SSL certificate error'
            except requests.exceptions.ConnectionError:
                status = 'connection_error'
                error_msg = 'Connection refused'
            except requests.exceptions.Timeout:
                status = 'timeout'
                error_msg = 'Request timed out (15s)'
            except Exception as e:
                status = 'error'
                error_msg = str(e)[:60]

            results.append({
                'section': section, 'id': fid, 'name': name,
                'status': status, 'items': item_count,
                'latest': latest_date, 'error': error_msg,
            })

            icon = '  ' if status.startswith('working') else 'X '
            print(f"  {icon}[{section[:4]:>4}] {fid:<25} {status:<20} items={item_count:<4} {latest_date}")

    working = sum(1 for r in results if r['status'].startswith('working'))
    broken  = sum(1 for r in results if r['status'] in ('broken','ssl_error','connection_error','timeout','error'))
    empty   = sum(1 for r in results if r['status'] == 'empty')

    print(f"\n{'─'*55}")
    print(f"  Working: {working}  |  Broken: {broken}  |  Empty: {empty}  |  Total: {len(results)}")
    print(f"{'─'*55}")

    # Save health report
    health_file = f'rss_health_{TODAY}.txt'
    with open(health_file, 'w', encoding='utf-8') as f:
        f.write(f"RSS Feed Health Report -- {TODAY}\n{'='*60}\n\n")
        for r in results:
            f.write(f"[{r['section']}] {r['id']}\n")
            f.write(f"  Name:   {r['name']}\n")
            f.write(f"  Status: {r['status']}\n")
            f.write(f"  Items:  {r['items']}\n")
            if r['latest']:
                f.write(f"  Latest: {r['latest']}\n")
            if r['error']:
                f.write(f"  Error:  {r['error']}\n")
            f.write('\n')
        f.write(f"\nSummary: {working} working, {broken} broken, {empty} empty out of {len(results)} feeds\n")
    print(f"\n  Health report saved to {health_file}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='seed_projects_v2.py -- Full project rebuild')
    parser.add_argument('--test-queries', action='store_true',
                        help='Dry run: print all GDELT queries, report counts per NAICS sector')
    parser.add_argument('--test-feeds', action='store_true',
                        help='Test RSS feed health: check each feed, report working/broken/stale')
    parser.add_argument('--deep-sweep', action='store_true',
                        help='Monthly: 12-month GDELT lookback + full registry re-scrape + re-attempt backfill')
    parser.add_argument('--seed-projects', action='store_true',
                        help='Full project seed: registries -> GDELT 12-month -> build from scratch')
    parser.add_argument('--audit-citations', action='store_true',
                        help='Re-verify all source URLs currently in /projects, report dead links')
    parser.add_argument('--weekly', action='store_true',
                        help='Weekly run: 7-day GDELT lookback (default mode)')
    parser.add_argument('--province', type=str, default='',
                        help='Filter to single province (e.g., "British Columbia" for mini seed test)')
    args = parser.parse_args()

    pf = args.province or ''

    if args.test_queries:
        test_queries()
    elif args.test_feeds:
        test_feeds()
    elif args.audit_citations:
        audit_citations()
    elif args.seed_projects:
        # Full rebuild: wipe + rebuild from all sources
        main(days_back=365, province_filter=pf)
    elif args.deep_sweep:
        # Monthly deep sweep: 12-month lookback, incremental, re-attempt backfill
        os.environ.setdefault('WAYBACK_BACKFILL_ENABLED', 'true')
        weekly_update(days_back=365, province_filter=pf, re_backfill=True)
    elif args.weekly:
        # Weekly incremental: 7-day lookback, upsert only
        weekly_update(days_back=7, province_filter=pf)
    else:
        # Default: weekly incremental mode
        weekly_update(days_back=7, province_filter=pf)
