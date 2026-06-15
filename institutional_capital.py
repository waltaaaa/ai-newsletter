"""
institutional_capital.py — Tier 14: institutional capital plan discovery.
Universities, polytechnics, hospitals, transit agencies, airports, ports.

REBUILT 2026-06-11 (audit C6). The old tier scraped ~57 institution websites
directly and returned 0 every run: every endpoint had rotted to 404 or was
bot-blocked — YVR / Port Vancouver / Port Montreal block on TLS fingerprint,
so no requests-based client can ever get through, and "live-verified" paths
(UOttawa, Queen's, UManitoba, ...) 404'd again within days of verification.

New approach: ALL discovery goes through Google News RSS (news.google.com —
one stable, free, unlimited endpoint; immune to per-institution bot blocks
and URL rot). Per institution, up to three feeds:

  1. name query  — '"<name>" ("million" OR "billion") (<capital terms>)'
                   Third-party coverage. Dollar-biased so the ~100-entry feed
                   cap is spent on stories that can pass the value gate.
  2. site query  — 'site:<institution domain>' — the institution's own
                   newsroom releases, as indexed by Google News.
  3. fr query    — French-edition name query for Québec institutions.

Item gates (title-based — Google News summaries are just the title rehashed):
  * capital-project keyword required
  * parsed dollar value >= the province GDP threshold. Tier 13 (municipal)
    gates the same way, and tools/export_dashboard.py drops priced
    below-threshold rows from publish anyway — emitting them would only
    re-pollute what the 2026-06-11 project-list cleanup deleted.
  * name-query items must mention an institution alias in the title (kills
    wrong-institution hits, e.g. foreign port stories in a port query).
  * URL hard gate: no link, no project.

Same-announcement coverage from multiple outlets is merged within the tier
(key: institution + rounded value) — evidence arrays append, never overwrite.

Per-source failure logging mirrors the Tier 13 municipal scoreboard: one
"[TIER 14] source results: ..." line per run plus a DEGRADED line on zero
yield, so a dead tier is distinguishable from a quiet week.

Public API (stable — phases/discovery.py depends on it):
  scrape_institutional_capital() -> list[dict]
"""

import logging
import os
import re
import time
import urllib.parse
from datetime import date

import feedparser

import http_client

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"

try:
    from pipeline_config import PROVINCE_GDP_THRESHOLDS as _THRESHOLDS_DOLLARS
    _THRESHOLDS_M = {k: v / 1_000_000 for k, v in _THRESHOLDS_DOLLARS.items()}
except Exception:  # pragma: no cover - keep the tier alive if config moves
    _THRESHOLDS_M = {
        "ON": 500, "QC": 250, "AB": 200, "BC": 175, "SK": 45, "MB": 40,
        "NS": 25, "NB": 20, "NL": 17, "PE": 5, "YT": 3, "NT": 3, "NU": 3,
    }

# Capital-keyword terms per institution category, used in the name queries.
_TERMS_EN = {
    "education": '(construction OR expansion OR campus OR building OR residence OR revitalization)',
    "healthcare": '(construction OR expansion OR redevelopment OR hospital OR tower OR wing)',
    "transit": '(construction OR extension OR station OR LRT OR subway OR "light rail")',
    "airport": '(terminal OR expansion OR runway OR construction OR upgrade)',
    "port": '(terminal OR expansion OR berth OR construction OR infrastructure)',
}
_TERMS_FR = {
    "education": '(construction OR agrandissement OR campus OR pavillon)',
    "healthcare": '(construction OR agrandissement OR hôpital OR modernisation)',
    "transit": '(construction OR prolongement OR station OR tramway OR métro)',
    "airport": '(aérogare OR agrandissement OR piste OR construction)',
    "port": '(terminal OR agrandissement OR quai OR construction)',
}
# 18-sector taxonomy keys + 2-digit NAICS per category.
_SECTOR_KEY = {
    "education": "education", "healthcare": "healthcare",
    "transit": "transport_logistics", "airport": "transport_logistics",
    "port": "transport_logistics",
}
_NAICS = {
    "education": "61", "healthcare": "62", "transit": "48-49",
    "airport": "48-49", "port": "48-49",
}

# Every institution from the pre-rebuild source list is preserved (additive-
# only): same ~60 institutions, different access method. `domain` drives the
# site-scoped query (None = name query only, e.g. ETS lives on the city-wide
# edmonton.ca domain). `aliases[0]` is the quoted name-query term; the full
# alias list gates name-query titles. `fr`: also run a French-edition query.
INSTITUTIONAL_SOURCES = [
    # ── U15 research-intensive universities ─────────────────────────────────
    {"name": "University of Toronto", "category": "education", "province": "ON",
     "cma": "Toronto", "domain": "utoronto.ca",
     "aliases": ["University of Toronto", "U of T", "UofT"]},
    {"name": "UBC", "category": "education", "province": "BC",
     "cma": "Vancouver", "domain": "ubc.ca",
     "aliases": ["UBC", "University of British Columbia"]},
    {"name": "McGill University", "category": "education", "province": "QC",
     "cma": "Montreal", "domain": "mcgill.ca", "fr": True,
     "aliases": ["McGill"]},
    {"name": "Université de Montréal", "category": "education", "province": "QC",
     "cma": "Montreal", "domain": "umontreal.ca", "fr": True,
     "aliases": ["Université de Montréal", "Universite de Montreal", "UdeM"]},
    {"name": "University of Alberta", "category": "education", "province": "AB",
     "cma": "Edmonton", "domain": "ualberta.ca",
     "aliases": ["University of Alberta", "U of A"]},
    {"name": "University of Calgary", "category": "education", "province": "AB",
     "cma": "Calgary", "domain": "ucalgary.ca",
     "aliases": ["University of Calgary", "UCalgary"]},
    {"name": "McMaster University", "category": "education", "province": "ON",
     "cma": "Hamilton", "domain": "mcmaster.ca",
     "aliases": ["McMaster"]},
    {"name": "University of Ottawa", "category": "education", "province": "ON",
     "cma": "Ottawa-Gatineau", "domain": "uottawa.ca",
     "aliases": ["University of Ottawa", "uOttawa"]},
    {"name": "Université Laval", "category": "education", "province": "QC",
     "cma": "Quebec City", "domain": "ulaval.ca", "fr": True,
     "aliases": ["Université Laval", "Universite Laval", "Laval University"]},
    {"name": "Queen's University", "category": "education", "province": "ON",
     "cma": "Kingston", "domain": "queensu.ca",
     "aliases": ["Queen's University", "Queens University"]},
    {"name": "University of Manitoba", "category": "education", "province": "MB",
     "cma": "Winnipeg", "domain": "umanitoba.ca",
     "aliases": ["University of Manitoba"]},
    {"name": "Dalhousie University", "category": "education", "province": "NS",
     "cma": "Halifax", "domain": "dal.ca",
     "aliases": ["Dalhousie"]},
    {"name": "University of Saskatchewan", "category": "education", "province": "SK",
     "cma": "Saskatoon", "domain": "usask.ca",
     "aliases": ["University of Saskatchewan", "USask"]},
    {"name": "Western University", "category": "education", "province": "ON",
     "cma": "London", "domain": "uwo.ca",
     "aliases": ["Western University"]},
    {"name": "University of Waterloo", "category": "education", "province": "ON",
     "cma": "Kitchener-Cambridge-Waterloo", "domain": "uwaterloo.ca",
     "aliases": ["University of Waterloo", "UWaterloo"]},
    # ── Polytechnics and colleges ────────────────────────────────────────────
    {"name": "BCIT", "category": "education", "province": "BC",
     "cma": "Vancouver", "domain": "bcit.ca", "aliases": ["BCIT"]},
    {"name": "SAIT", "category": "education", "province": "AB",
     "cma": "Calgary", "domain": "sait.ca", "aliases": ["SAIT"]},
    {"name": "George Brown College", "category": "education", "province": "ON",
     "cma": "Toronto", "domain": "georgebrown.ca",
     "aliases": ["George Brown"]},
    {"name": "Seneca Polytechnic", "category": "education", "province": "ON",
     "cma": "Toronto", "domain": "senecapolytechnic.ca",
     "aliases": ["Seneca"]},
    {"name": "Humber College", "category": "education", "province": "ON",
     "cma": "Toronto", "domain": "humber.ca",
     "aliases": ["Humber"]},
    {"name": "Algonquin College", "category": "education", "province": "ON",
     "cma": "Ottawa-Gatineau", "domain": "algonquincollege.com",
     "aliases": ["Algonquin College"]},
    {"name": "Fanshawe College", "category": "education", "province": "ON",
     "cma": "London", "domain": "fanshawec.ca",
     "aliases": ["Fanshawe"]},
    {"name": "Mohawk College", "category": "education", "province": "ON",
     "cma": "Hamilton", "domain": "mohawkcollege.ca",
     "aliases": ["Mohawk College"]},
    {"name": "Conestoga College", "category": "education", "province": "ON",
     "cma": "Kitchener-Cambridge-Waterloo", "domain": "conestogac.on.ca",
     "aliases": ["Conestoga"]},
    {"name": "Red River College Polytechnic", "category": "education", "province": "MB",
     "cma": "Winnipeg", "domain": "rrc.ca",
     "aliases": ["Red River College", "RRC Polytech"]},
    {"name": "Saskatchewan Polytechnic", "category": "education", "province": "SK",
     "cma": "Saskatoon", "domain": "saskpolytech.ca",
     "aliases": ["Saskatchewan Polytechnic", "Sask Polytech"]},
    {"name": "NAIT", "category": "education", "province": "AB",
     "cma": "Edmonton", "domain": "nait.ca", "aliases": ["NAIT"]},
    # ── Healthcare institutions ──────────────────────────────────────────────
    {"name": "SickKids Hospital", "category": "healthcare", "province": "ON",
     "cma": "Toronto", "domain": "sickkids.ca",
     "aliases": ["SickKids", "Hospital for Sick Children"]},
    {"name": "MUHC (McGill University Health Centre)", "category": "healthcare",
     "province": "QC", "cma": "Montreal", "domain": "muhc.ca", "fr": True,
     "aliases": ["MUHC", "McGill University Health Centre"]},
    {"name": "University Health Network", "category": "healthcare", "province": "ON",
     "cma": "Toronto", "domain": "uhn.ca",
     "aliases": ["University Health Network", "UHN"]},
    {"name": "Sunnybrook Health Sciences Centre", "category": "healthcare",
     "province": "ON", "cma": "Toronto", "domain": "sunnybrook.ca",
     "aliases": ["Sunnybrook"]},
    {"name": "Hamilton Health Sciences", "category": "healthcare", "province": "ON",
     "cma": "Hamilton", "domain": "hamiltonhealthsciences.ca",
     "aliases": ["Hamilton Health Sciences"]},
    {"name": "CHUM (Centre hospitalier de l'Université de Montréal)",
     "category": "healthcare", "province": "QC", "cma": "Montreal",
     "domain": "chumontreal.qc.ca", "fr": True, "aliases": ["CHUM"]},
    {"name": "BC Children's Hospital", "category": "healthcare", "province": "BC",
     "cma": "Vancouver", "domain": "bcchildrens.ca",
     "aliases": ["BC Children's"]},
    {"name": "Alberta Health Services", "category": "healthcare", "province": "AB",
     "cma": "Calgary", "domain": "albertahealthservices.ca",
     "aliases": ["Alberta Health Services", "AHS"]},
    {"name": "Saskatchewan Health Authority", "category": "healthcare",
     "province": "SK", "cma": "Saskatoon", "domain": "saskhealthauthority.ca",
     "aliases": ["Saskatchewan Health Authority"]},
    {"name": "NL Health Services", "category": "healthcare", "province": "NL",
     "cma": "St. John's", "domain": "nlhealthservices.ca",
     "aliases": ["NL Health Services", "Newfoundland and Labrador Health Services"]},
    {"name": "IWK Health Centre", "category": "healthcare", "province": "NS",
     "cma": "Halifax", "domain": "iwkhealth.ca", "aliases": ["IWK"]},
    # ── Transit agencies ─────────────────────────────────────────────────────
    {"name": "Metrolinx", "category": "transit", "province": "ON",
     "cma": "Toronto", "domain": "metrolinx.com",
     "aliases": ["Metrolinx", "GO Transit", "GO Expansion", "Ontario Line"]},
    {"name": "TransLink", "category": "transit", "province": "BC",
     "cma": "Vancouver", "domain": "translink.ca", "aliases": ["TransLink"]},
    {"name": "STM (Société de transport de Montréal)", "category": "transit",
     "province": "QC", "cma": "Montreal", "domain": "stm.info", "fr": True,
     "aliases": ["STM", "Société de transport de Montréal"]},
    {"name": "OC Transpo (Ottawa)", "category": "transit", "province": "ON",
     "cma": "Ottawa-Gatineau", "domain": "octranspo.com",
     "aliases": ["OC Transpo"]},
    {"name": "Calgary Transit", "category": "transit", "province": "AB",
     "cma": "Calgary", "domain": "calgarytransit.com",
     "aliases": ["Calgary Transit", "Green Line"]},
    # ETS pages live on the city-wide edmonton.ca domain — a site: query would
    # pull every City of Edmonton story, so this source is name-query only.
    {"name": "Edmonton Transit Service", "category": "transit", "province": "AB",
     "cma": "Edmonton", "domain": None,
     "aliases": ["Edmonton Transit", "Valley Line"]},
    {"name": "Winnipeg Transit", "category": "transit", "province": "MB",
     "cma": "Winnipeg", "domain": "winnipegtransit.com",
     "aliases": ["Winnipeg Transit"]},
    # ── Airport authorities ──────────────────────────────────────────────────
    {"name": "Greater Toronto Airports Authority", "category": "airport",
     "province": "ON", "cma": "Toronto", "domain": "torontopearson.com",
     "aliases": ["Toronto Pearson", "Pearson airport", "GTAA"]},
    {"name": "Vancouver Airport Authority", "category": "airport", "province": "BC",
     "cma": "Vancouver", "domain": "yvr.ca",
     "aliases": ["YVR", "Vancouver International Airport", "Vancouver airport"]},
    {"name": "Aéroports de Montréal", "category": "airport", "province": "QC",
     "cma": "Montreal", "domain": "admtl.com", "fr": True,
     "aliases": ["Montréal-Trudeau", "Montreal-Trudeau", "Aéroports de Montréal", "ADM"]},
    {"name": "Calgary Airport Authority", "category": "airport", "province": "AB",
     "cma": "Calgary", "domain": "yyc.com",
     "aliases": ["YYC", "Calgary International Airport", "Calgary airport"]},
    {"name": "Edmonton International Airport", "category": "airport",
     "province": "AB", "cma": "Edmonton", "domain": "flyeia.com",
     "aliases": ["Edmonton International Airport", "YEG"]},
    {"name": "Ottawa International Airport", "category": "airport", "province": "ON",
     "cma": "Ottawa-Gatineau", "domain": "yow.ca",
     "aliases": ["Ottawa International Airport", "Ottawa airport", "YOW"]},
    {"name": "Winnipeg Airport Authority", "category": "airport", "province": "MB",
     "cma": "Winnipeg", "domain": "ywg.ca",
     "aliases": ["Winnipeg Richardson", "Winnipeg airport", "YWG"]},
    {"name": "Halifax Stanfield International Airport", "category": "airport",
     "province": "NS", "cma": "Halifax", "domain": "halifaxstanfield.ca",
     "aliases": ["Halifax Stanfield", "Halifax airport"]},
    # ── Port authorities ─────────────────────────────────────────────────────
    {"name": "Vancouver Fraser Port Authority", "category": "port", "province": "BC",
     "cma": "Vancouver", "domain": "portvancouver.com",
     "aliases": ["Port of Vancouver", "Vancouver Fraser Port", "Vancouver port"]},
    {"name": "Port of Montreal", "category": "port", "province": "QC",
     "cma": "Montreal", "domain": "port-montreal.com", "fr": True,
     "aliases": ["Port of Montreal", "Port de Montréal", "Montreal port"]},
    {"name": "Port of Halifax", "category": "port", "province": "NS",
     "cma": "Halifax", "domain": "porthalifax.ca",
     "aliases": ["Port of Halifax", "Halifax port"]},
    {"name": "Port of Saint John", "category": "port", "province": "NB",
     "cma": "Saint John", "domain": "sjport.com",
     "aliases": ["Port of Saint John", "Saint John port"]},
    {"name": "Port of Hamilton-Oshawa", "category": "port", "province": "ON",
     "cma": "Hamilton", "domain": "hopaports.ca",
     "aliases": ["HOPA", "Port of Hamilton", "Port of Oshawa", "Hamilton port"]},
    {"name": "Port of Thunder Bay", "category": "port", "province": "ON",
     "cma": "Thunder Bay", "domain": "portofthunderbay.ca",
     "aliases": ["Port of Thunder Bay"]},
    {"name": "Port of Prince Rupert", "category": "port", "province": "BC",
     "cma": "Prince Rupert", "domain": "rupertport.com",
     "aliases": ["Port of Prince Rupert", "Prince Rupert port"]},
]

# ── Title parsing ─────────────────────────────────────────────────────────────

# "$3 Billion", "$42.5M", "$15.3-million", "$13.9B"
_DOLLAR_EN = re.compile(
    r'\$\s?(\d[\d,]*(?:\.\d+)?)\s?-?\s?(billion|million|bn|[MB])\b',
    re.IGNORECASE,
)
# French-press forms: "13,9 G$", "450 M$", "1,5 milliard (de dollars)"
_DOLLAR_FR = re.compile(
    r'(\d[\d\s,]*(?:[.,]\d+)?)\s?(G\$|M\$|milliards?|millions?)',
    re.IGNORECASE,
)

_CAPITAL_KW = re.compile(
    r'(construct|expansion|expand|redevelop|renovat|retrofit|rebuild|revitaliz|'
    r'new (building|campus|tower|terminal|wing|hospital|facility|plant|berth|'
    r'runway|residence|station|garage|line)|'
    r'capital (project|plan|program)|infrastructure|breaks? ground|groundbreaking|'
    r'moderni[sz]ation|upgrade|terminal|berth|runway|campus|light rail|LRT\b|subway|'
    # French capital signals (Québec sources)
    r'agrandiss|chantier|réaménag|reamenag|modernis|pavillon|prolongement|aérogare)',
    re.IGNORECASE,
)

# Status from title wording. Bare "groundbreaking" is intentionally NOT a
# status signal — headlines use it figuratively ("groundbreaking approach").
_STATUS_PATTERNS = [
    (re.compile(r'\b(complete[ds]?|completion|officially open(s|ed)?)\b', re.I),
     "Complete"),
    (re.compile(r'(breaks? ground|construction (begins|starts|underway|to begin|'
                r'kicks off)|(enters?|moves? into) construction|under construction|'
                r'shovels in the ground)', re.I),
     "Under Construction"),
    (re.compile(r'\b(approve[ds]?|approval|green.?lights?)\b', re.I), "Approved"),
]
# Mirrors db.STATUS_ORDER forward states (local copy — keep the tier import-light).
_STATUS_RANK = {"Proposed": 1, "Under Review": 2, "Approved": 3,
                "Under Construction": 4, "Partially Complete": 5, "Complete": 6}

_TAG_RE = re.compile(r'<[^>]+>')


def _parse_dollar(text: str) -> float | None:
    """Extract a dollar value in millions from headline text (EN + FR forms)."""
    m = _DOLLAR_EN.search(text)
    if m:
        num = float(m.group(1).replace(',', ''))
        unit = m.group(2).lower()
        return num * 1000 if unit.startswith('b') else num
    m = _DOLLAR_FR.search(text)
    if m:
        raw = m.group(1).replace(' ', ' ').strip()
        # French numerics: comma is the decimal ("13,9"), space groups
        # thousands ("13 900").
        raw = raw.replace(' ', '')
        if ',' in raw and '.' not in raw:
            raw = raw.replace(',', '.')
        else:
            raw = raw.replace(',', '')
        try:
            num = float(raw)
        except ValueError:
            return None
        unit = m.group(2).lower()
        return num * 1000 if unit.startswith(('g', 'milliard')) else num
    return None


def _split_publisher(raw_title: str) -> tuple[str, str]:
    """Google News titles end with ' - Publisher'. Return (title, publisher)."""
    if " - " in raw_title:
        title, _, publisher = raw_title.rpartition(" - ")
        return title.strip(), publisher.strip()
    return raw_title.strip(), ""


def _title_mentions(aliases: list[str], title: str) -> bool:
    for alias in aliases:
        if re.search(rf'\b{re.escape(alias)}\b', title, re.IGNORECASE):
            return True
    return False


def _infer_status(title: str) -> str:
    for pattern, status in _STATUS_PATTERNS:
        if pattern.search(title):
            return status
    return "Proposed"


def _entry_date(entry) -> str:
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            return date(parsed[0], parsed[1], parsed[2]).isoformat()
        except Exception:
            pass
    return date.today().isoformat()


# ── Query construction ────────────────────────────────────────────────────────

def _gn_rss_url(query: str, language: str = "en") -> str:
    params = {
        "q": query,
        "hl": "fr-CA" if language == "fr" else "en-CA",
        "gl": "CA",
        "ceid": "CA:fr" if language == "fr" else "CA:en",
    }
    return f"{GOOGLE_NEWS_RSS_BASE}?{urllib.parse.urlencode(params)}"


def _build_queries(source: dict, window_days: int) -> list[tuple[str, str, str]]:
    """Return [(kind, language, rss_url)] for one institution."""
    category = source["category"]
    primary = source["aliases"][0]
    queries = [(
        "name", "en",
        _gn_rss_url(f'"{primary}" ("million" OR "billion") '
                    f'{_TERMS_EN[category]} when:{window_days}d'),
    )]
    if source.get("domain"):
        queries.append((
            "site", "en",
            _gn_rss_url(f'site:{source["domain"]} when:{window_days}d'),
        ))
    if source.get("fr"):
        queries.append((
            "name", "fr",
            _gn_rss_url(f'"{primary}" ("millions" OR "milliards") '
                        f'{_TERMS_FR[category]} when:{window_days}d', "fr"),
        ))
    return queries


# ── Entry → project ───────────────────────────────────────────────────────────

def _entry_to_project(entry, source: dict, kind: str) -> dict | None:
    """Convert one feed entry to a project dict, or None if it fails a gate."""
    title, publisher = _split_publisher(entry.get("title", ""))
    if not title or len(title) < 15:
        return None
    link = (entry.get("link") or "").strip()
    if not link:  # URL hard gate
        return None

    value = _parse_dollar(title)
    if value is None:
        return None
    threshold = _THRESHOLDS_M.get(source["province"], 40)
    if value < threshold:
        return None
    if not _CAPITAL_KW.search(title):
        return None
    # Name-query results can surface other institutions' (or other countries')
    # stories — require an alias in the title. Site-query results are already
    # attributed by domain (the institution is the publisher).
    if kind == "name" and not _title_mentions(source["aliases"], title):
        return None

    category = source["category"]
    inst = source["name"]
    project_name = title if _title_mentions(source["aliases"], title) \
        else f"{inst} — {title}"
    project_name = project_name[:140]

    summary_text = _TAG_RE.sub(" ", entry.get("summary", "") or "")
    description = re.sub(r'\s+', ' ', f"{title}. {summary_text}").strip()[:200]

    # Institution newsrooms count as institutional/government authority;
    # third-party press is media.
    authority = "government" if kind == "site" else "media"

    return {
        "name": project_name,
        "province": source["province"],
        "cma": source.get("cma", ""),
        "sector": _SECTOR_KEY[category],
        "naics_code": _NAICS[category],
        "tags": [],
        "value": f"${value:.0f}M",
        "value_millions": value,
        "status": _infer_status(title),
        "description": description,
        "discovery_source": "institutional_capital",
        "source_url": link,
        "source_title": publisher or inst,
        "sources": [{"id": 1, "title": publisher or inst, "url": link}],
        "announced": _entry_date(entry),
        "completionDate": "",
        "_discovery_tier": "institutional_capital",
        "_source_type": authority,
        "confidence": 0.6 if authority == "government" else 0.5,
        "_evidence": [{
            "url": link,
            "name": publisher or inst,
            "source_type": "institutional_capital",
            "authority": authority,
        }],
    }


def _merge_into(merged: dict, key: tuple, proj: dict) -> bool:
    """Merge same-announcement coverage. Returns True if `proj` was new."""
    existing = merged.get(key)
    if existing is None:
        merged[key] = proj
        return True
    # Evidence/source arrays APPEND, never overwrite (pipeline invariant).
    known_urls = {e["url"] for e in existing["_evidence"]}
    if proj["source_url"] not in known_urls:
        existing["_evidence"].extend(proj["_evidence"])
        existing["sources"].append({
            "id": len(existing["sources"]) + 1,
            "title": proj["source_title"],
            "url": proj["source_url"],
        })
        existing["confidence"] = min(0.7, existing["confidence"] + 0.05)
    # Institution-newsroom attribution beats media attribution.
    if proj["_source_type"] == "government" and existing["_source_type"] != "government":
        existing["_source_type"] = "government"
        existing["confidence"] = max(existing["confidence"], 0.6)
    # Status only advances (non-regression).
    if _STATUS_RANK.get(proj["status"], 0) > _STATUS_RANK.get(existing["status"], 0):
        existing["status"] = proj["status"]
    # Keep the earliest sighting date.
    if proj["announced"] < existing["announced"]:
        existing["announced"] = proj["announced"]
    return False


# ── Main entry point ──────────────────────────────────────────────────────────

def scrape_institutional_capital() -> list[dict]:
    """Discover institutional capital projects via Google News RSS.

    Returns a list of project dicts ready for cross-tier dedup and upsert.
    Signature is stable — phases/discovery.py calls this directly.
    """
    window_days = int(os.environ.get("INSTITUTIONAL_LOOKBACK_DAYS", "90"))
    delay = float(os.environ.get("INSTITUTIONAL_FETCH_DELAY", "0.6"))

    merged: dict[tuple, dict] = {}
    seen_links: set[str] = set()
    source_counts: dict[str, int] = {}
    source_entries: dict[str, int] = {}
    source_failures: dict[str, str] = {}

    # Circuit breaker: consecutive 429/503s mean Google News is rate-limiting
    # this IP — hammering the remaining sources prolongs the ban.
    consecutive_ratelimit = 0
    tripped = False

    for source in INSTITUTIONAL_SOURCES:
        name = source["name"]
        if tripped:
            source_failures[name] = "skipped(rate-limit)"
            continue

        entries_n = 0
        kept = 0
        ok_fetches = 0
        last_fail = None

        for kind, language, url in _build_queries(source, window_days):
            try:
                resp = http_client.get(url, timeout=20)
                if resp is None:
                    last_fail = "network"
                    continue
                if resp.status_code != 200:
                    last_fail = str(resp.status_code)
                    if resp.status_code in (429, 503):
                        consecutive_ratelimit += 1
                        if consecutive_ratelimit >= 6:
                            tripped = True
                            logger.warning(
                                "  [TIER 14] circuit breaker TRIPPED — "
                                "6 consecutive 429/503s from Google News; "
                                "skipping remaining sources")
                            break
                    continue
                consecutive_ratelimit = 0
                ok_fetches += 1
                parsed = feedparser.parse(resp.text)
                entries_n += len(parsed.entries)
                for entry in parsed.entries:
                    link = (entry.get("link") or "").strip()
                    if not link or link in seen_links:
                        continue
                    proj = _entry_to_project(entry, source, kind)
                    if proj is None:
                        continue
                    seen_links.add(link)
                    key = (name, int(round(proj["value_millions"])))
                    if _merge_into(merged, key, proj):
                        kept += 1
            except Exception as e:
                last_fail = type(e).__name__
                logger.warning(f"  [TIER 14][{name}] FAILED "
                               f"status=exception {type(e).__name__}: {e}")
            finally:
                time.sleep(delay)

        if ok_fetches == 0:
            source_failures[name] = last_fail or "unknown"
            logger.warning(f"  [TIER 14][{name}] FAILED status={last_fail}")
        else:
            source_counts[name] = kept
            source_entries[name] = entries_n
            if kept:
                logger.info(f"  {name}: {kept} capital projects "
                            f"(from {entries_n} feed entries)")

    all_projects = list(merged.values())

    # One-line per-source scoreboard (Tier 13 pattern): yields, quiet sources,
    # and failures — a dead source is visible without scrolling error lines.
    hits_part = ", ".join(
        f"{n} {k}" for n, k in source_counts.items() if k) or "none"
    quiet_n = sum(1 for k in source_counts.values() if k == 0)
    quiet_entries = sum(source_entries[n] for n, k in source_counts.items()
                        if k == 0)
    failed_part = ", ".join(
        f"{n}({r})" for n, r in source_failures.items()) or "none"
    print(f"[TIER 14] source results: {hits_part} | quiet: {quiet_n} sources "
          f"(0 kept of {quiet_entries} entries scanned) | FAILED: {failed_part}")

    logger.info(f"Institutional discovery complete: {len(all_projects)} projects "
                f"from {len(source_counts)} sources "
                f"({len(source_failures)} failed)")
    # Min-yield DEGRADE log (0 items != green run).
    if not all_projects:
        print("[TIER 14 DEGRADED] 0 items — no institutional capital projects returned")
    return all_projects


# Legacy constant retained for compatibility (additive-only). Not consumed by
# any current pipeline path; the rss.xml endpoints for UofT/McGill now 404.
INSTITUTIONAL_RSS_FEEDS = [
    {"id": "uoft_news", "name": "University of Toronto News", "url": "https://www.utoronto.ca/news/rss.xml",
     "source_type": "industry", "jurisdiction": "Ontario", "priority": 3, "enabled": True},
    {"id": "ubc_news", "name": "UBC News", "url": "https://news.ubc.ca/feed/",
     "source_type": "industry", "jurisdiction": "British Columbia", "priority": 3, "enabled": True},
    {"id": "mcgill_news", "name": "McGill News", "url": "https://www.mcgill.ca/newsroom/rss",
     "source_type": "industry", "jurisdiction": "Quebec", "priority": 3, "enabled": True},
    {"id": "ualberta_news", "name": "UAlberta News", "url": "https://www.ualberta.ca/news-and-events/rss-feeds.html",
     "source_type": "industry", "jurisdiction": "Alberta", "priority": 3, "enabled": True},
]


if __name__ == "__main__":
    # Standalone live verification: scrape and print, no DB writes.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    projects = scrape_institutional_capital()
    print(f"\n{len(projects)} projects:")
    for p in projects:
        print(f"  [{p['province']}] {p['value']:>9} {p['status']:<18} "
              f"{p['name'][:90]}")
        for ev in p["_evidence"]:
            print(f"      <{ev['authority']}> {ev['url'][:100]}")
