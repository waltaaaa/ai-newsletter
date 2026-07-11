"""
gov_sources.py — Government data source fetchers for EconF Weekly

Provides:
  fetch_statcan_indicators()          — StatCan key economic indicators JSON feed (71 national)
  save_statcan_indicators(db, ...)    — Write snapshot to Firestore
  fetch_registry_projects()           — Scrape government project registries
                                        (IAAC, BC EAO, NRCan, Infrastructure Canada,
                                         BuyAndSell contracts, provincial EA registries)
"""

import re
import sys
import time
import urllib.parse
import requests
from datetime import date

# patch-1.2: shared HTTP client (browser UA, certifi TLS, per-host retry).
# Routing all scraper fetches through this clears the uniform 403 bot-blocks
# and the Windows CERTIFICATE_VERIFY_FAILED errors (D-7/D-8/D-9).
import http_client

try:
    from pipeline_store import cache as _cache
except ImportError:
    _cache = None

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False
    print("[gov_sources] beautifulsoup4 not installed — HTML parsing will be limited")

# P1 (quality-pass-1.4): non-project DOCUMENT-type filter at ingestion.
# EA registries emit rows that are filings (Forest Management Plans, EIS,
# terms of reference, public notices), not capital projects. Rows whose name
# matches AND that carry no dollar value are skipped before they ever reach
# the upsert. The regex lives in db.py so export and ingestion stay in sync.
try:
    from db import is_non_project_doctype
except ImportError:
    def is_non_project_doctype(name):  # fallback: filter disabled
        return False

# Dollar amount embedded in a registry row name (e.g. "... $120M expansion")
_NAME_DOLLAR_RE = re.compile(r'\$\s*\d')


def _skip_non_project_filing(name: str, value=None) -> bool:
    """True if this registry row is a document filing with no dollar value."""
    if value:
        return False
    if _NAME_DOLLAR_RE.search(name or ''):
        return False
    return is_non_project_doctype(name)

# ── StatCan indicators ────────────────────────────────────────────────────────

_STATCAN_IND_URL = "https://www150.statcan.gc.ca/n1/dai-quo/ssi/homepage/ind-econ.json"

_MONTHS = {
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
}


def _en(field) -> str:
    """Extract English string from a {en: ..., fr: ...} field, or cast to str."""
    if isinstance(field, dict):
        return str(field.get('en') or '')
    return str(field or '')


def _clean(s: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s or '')).strip()


def _infer_frequency(refper: str) -> str:
    lower = (refper or '').lower()
    if 'quarter' in lower:
        return 'Quarterly'
    if any(m in lower for m in _MONTHS):
        return 'Monthly'
    return 'Annual'


def _make_abs_url(path: str) -> str:
    if not path:
        return ''
    if path.startswith('http'):
        return path
    return f"https://www150.statcan.gc.ca{path}"


def _completeness(ind: dict) -> int:
    """Score an indicator record: higher = more data fields populated."""
    return sum([
        bool(ind.get('value')),
        bool(ind.get('change')),
        bool(ind.get('refPer')),
        bool(ind.get('releaseDate')),
        bool(ind.get('changeDetail')),
        bool(ind.get('tableUrl')),
        bool(ind.get('dailyUrl')),
    ])


def fetch_statcan_indicators() -> list[dict]:
    """
    Fetch StatCan key economic indicators from the JSON feed.
    Returns a list of indicator dicts. Returns [] (never raises) on failure.

    The feed contains geo-breakdown records (geo_code 0 = national, 1-13 = provinces/
    territories). We keep only geo_code == 0 (national level), then deduplicate by
    indicator name, keeping the record with the most populated fields.

    Each dict:
        name         str   — indicator name (English)
        value        str   — current value, HTML stripped
        change       str   — growth rate string, e.g. "+1.2%"
        arrow        int   — 1=up, 2=down, 0=flat/neutral
        changeDetail str   — human description, e.g. "rose 1.2%"
        refPer       str   — reference period, e.g. "January 2026"
        releaseDate  str   — ISO date of publication, e.g. "2026-02-14"
        frequency    str   — Monthly | Quarterly | Annual
        tableUrl     str   — link to StatCan data table
        dailyUrl     str   — link to The Daily release
        dailyTitle   str   — title of The Daily release
    """
    print("  Fetching StatCan key indicators...")

    # Check cache (6-hour TTL — StatCan updates daily)
    if _cache:
        cached = _cache.get("statcan:key_indicators")
        if cached is not None:
            print(f"  [StatCan] Using cached data ({len(cached)} indicators)")
            return cached

    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS)
        resp = http_client.get(_STATCAN_IND_URL, timeout=20)
        if resp is None:
            print(f"  [StatCan][TIER 1] FAILED status=network from {_STATCAN_IND_URL[:60]}")
            return []
        if resp.status_code >= 400:
            print(f"  [StatCan][TIER 1] FAILED status={resp.status_code} from {_STATCAN_IND_URL[:60]}")
            return []
        raw_all = resp.json().get('results', {}).get('indicators', [])

        # Step 1: keep only national (geo_code == 0) records
        raw_national = [r for r in raw_all if int(r.get('geo_code') or 0) == 0]
        print(f"  [StatCan] {len(raw_all)} raw records -> {len(raw_national)} national (geo_code=0)")

        # Step 2: parse each record
        parsed: list[dict] = []
        for ind in raw_national:
            name = _clean(_en(ind.get('title')))
            if not name:
                continue  # skip rows with no name

            refper = _clean(_en(ind.get('refper')))
            if not refper:
                continue  # skip section-header/footnote rows with no period

            value    = _clean(_en(ind.get('value')))
            rel_date = str(ind.get('release_date') or '')

            gr            = ind.get('growth_rate') or {}
            change        = _clean(_en(gr.get('growth')))
            arrow         = int(gr.get('arrow_direction') or 0)
            change_detail = _clean(_en(gr.get('details')))

            # Skip rows with neither a value nor a growth figure
            if not value and not change:
                continue

            daily_url   = _make_abs_url(_clean(_en(ind.get('daily_url'))))
            daily_title = _clean(_en(ind.get('daily_title')))

            source    = str(ind.get('source') or '').strip()
            table_url = (
                f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={source}01"
                if source else ''
            )

            parsed.append({
                'name':         name,
                'value':        value,
                'change':       change,
                'arrow':        arrow,
                'changeDetail': change_detail,
                'refPer':       refper,
                'releaseDate':  rel_date,
                'frequency':    _infer_frequency(refper),
                'tableUrl':     table_url,
                'dailyUrl':     daily_url,
                'dailyTitle':   daily_title,
            })

        # Step 3: deduplicate by name (keep most complete record)
        seen: dict[str, dict] = {}
        for ind in parsed:
            key = ind['name'].lower().strip()
            if key not in seen or _completeness(ind) > _completeness(seen[key]):
                seen[key] = ind
        indicators = list(seen.values())

        # Step 4: sanity-check count
        n = len(indicators)
        if n > 75:
            from collections import Counter
            name_counts = Counter(i['name'].lower().strip() for i in parsed)
            suspects = sorted(
                [(nm, cnt) for nm, cnt in name_counts.items() if cnt > 1],
                key=lambda x: -x[1]
            )
            print(f"  [StatCan] WARNING: {n} indicators after dedup (expected 65-75). Suspect duplicates:")
            for nm, cnt in suspects[:10]:
                print(f"    [{cnt}x] {nm!r}")
        elif n < 65:
            print(f"  [StatCan] WARNING: only {n} indicators after dedup (expected 65-75). Check feed.")

        _print_indicators(indicators)
        if _cache:
            _cache.set("statcan:key_indicators", indicators, ttl_hours=6)
        return indicators

    except Exception as e:
        print(f"  [WARN] StatCan indicators fetch failed: {e}")
        return []


def _print_indicators(indicators: list[dict]) -> None:
    """Print indicator names alphabetically (safe for all console encodings)."""
    n = len(indicators)
    print(f"  Fetched {n} StatCan indicators (national level):")
    for ind in sorted(indicators, key=lambda x: x['name']):
        safe = ind['name'].encode('ascii', errors='replace').decode('ascii')
        print(f"    {safe}")


def save_statcan_indicators(conn, indicators: list[dict]) -> None:
    """
    Write StatCan indicators snapshot to statcan_indicators/latest.

    Args:
        conn: sqlite3.Connection from db.py (preferred) or Firestore client
              (backward compatible — detected by duck-typing)

    Skips write if indicators list is empty (preserves cached data). Never raises.
    """
    if not indicators:
        print("  [StatCan] No fresh indicators — skipping write (cached data preserved).")
        return
    try:
        if hasattr(conn, 'execute'):
            from db import save_dashboard_state
            save_dashboard_state(conn, "statcan_indicators_latest", {
                'updatedAt': date.today().isoformat(),
                'indicators': indicators,
            })
        else:
            conn.collection('statcan_indicators').document('latest').set({
                'updatedAt': date.today().isoformat(),
                'indicators': indicators,
            })
        print(f"  [StatCan] Saved {len(indicators)} indicators.")
    except Exception as e:
        print(f"  [StatCan] Write failed (non-critical): {e}")


# ── Government Registry Scrapers ──────────────────────────────────────────────

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0; +https://econf.ca)',
    'Accept':     'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def _get_html(url: str, timeout: int = 20) -> str | None:
    """Fetch HTML from URL. Returns None on failure.

    patch-1.2: routes through http_client (browser UA, certifi TLS, retry).
    Emits a structured per-source FAILED line on >=400 / network error.
    """
    resp = http_client.get(url, timeout=timeout)
    if resp is None:
        print(f"  [Registry] GET {url[:60]} FAILED status=network")
        return None
    if resp.status_code >= 400:
        print(f"  [Registry] GET {url[:60]} FAILED status={resp.status_code}")
        return None
    return resp.text


def _soup(html: str):
    """Parse HTML with BeautifulSoup, preferring lxml."""
    if not _HAS_BS4:
        return None
    try:
        return BeautifulSoup(html, 'lxml')
    except Exception:
        return BeautifulSoup(html, 'html.parser')


def _extract_with_tavily(url: str, tavily_client) -> str:
    """Fall back to Tavily Extract API for a single URL. Returns text or ''."""
    try:
        result = tavily_client.extract(urls=[url])
        for r in result.get('results', []):
            raw = r.get('raw_content') or r.get('content') or ''
            if raw:
                return raw[:4000]
    except Exception:
        pass
    return ''


# ── IAAC (Impact Assessment Agency of Canada) ────────────────────────────────

_IAAC_URL = "https://iaac-aeic.gc.ca/050/evaluations/exploration?culture=en-CA"

# IAAC requires a Chrome-like User-Agent (returns 404 with simple UA)
_IAAC_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept':     'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Map common province/territory strings found in IAAC location text
_IAAC_PROV_MAP = {
    'alberta': 'Alberta', 'british columbia': 'British Columbia',
    'saskatchewan': 'Saskatchewan', 'manitoba': 'Manitoba',
    'ontario': 'Ontario', 'quebec': 'Quebec', 'québec': 'Quebec',
    'new brunswick': 'New Brunswick', 'nova scotia': 'Nova Scotia',
    'prince edward island': 'Prince Edward Island',
    'newfoundland': 'Newfoundland and Labrador', 'labrador': 'Newfoundland and Labrador',
    'yukon': 'Yukon', 'northwest territories': 'Northwest Territories',
    'nunavut': 'Nunavut',
}

def _scrape_iaac(tavily_client=None) -> list[dict]:
    """
    Scrape IAAC project registry for active and recently decided assessments.
    Fetches the exploration page with browser-like headers and parses article cards.
    Returns list of project dicts with discovery_source='iaac_registry'.

    Warehouse instrumentation (RC-6): records the attempt in connection_runs
    ('iaac_registry') without altering behavior — an exception is recorded as
    failed and re-raised; an empty result is recorded as failed; a non-empty
    result is recorded ok with the project count.
    """
    result = None
    try:
        result = _scrape_iaac_impl(tavily_client=tavily_client)
        return result
    finally:
        try:
            from data_warehouse import record_run
            if result is None:
                record_run("iaac_registry", "failed",
                           error="_scrape_iaac raised (see pipeline log)")
            elif not result:
                record_run("iaac_registry", "failed",
                           error="0 projects from IAAC registry (fetch/parse failure)")
            else:
                record_run("iaac_registry", "ok",
                           items_fetched=len(result), items_saved=len(result))
        except Exception as _wh_e:
            print(f"  [WAREHOUSE] iaac_registry recording failed (non-critical): {_wh_e}")


def _scrape_iaac_impl(tavily_client=None) -> list[dict]:
    # patch-1.2: route through shared http_client (browser UA + certifi TLS + retry)
    resp = http_client.get(_IAAC_URL, timeout=20)
    if resp is None:
        print(f"  [IAAC][TIER 1] FAILED status=network from {_IAAC_URL}")
        return []
    if resp.status_code != 200:
        print(f"  [IAAC][TIER 1] FAILED status={resp.status_code} from {_IAAC_URL}")
        return []
    html = resp.text

    projects = []
    try:
        soup = _soup(html)
        if not soup:
            print(f"  [IAAC] Could not parse HTML ({len(html)} bytes)")
            return []

        # IAAC renders project cards as <article> elements inside div.results-jobs
        articles = soup.select('article')
        if not articles:
            print(f"  [IAAC] No <article> elements found (HTML={len(html)} bytes)")
            return []

        for art in articles:
            # Project name from h3 > span.noctitle
            name_el = art.select_one('h3 span.noctitle')
            name = name_el.get_text(strip=True) if name_el else ''
            if not name or len(name) < 5:
                continue

            # URL from the article's main link
            link = art.select_one('a.resultJobItem')
            url = ''
            if link:
                href = link.get('href', '')
                url = href if href.startswith('http') else f"https://iaac-aeic.gc.ca{href}"

            # Location — parse province from parenthetical text
            province = ''
            loc_el = art.select_one('li.location')
            if loc_el:
                loc_text = loc_el.get_text(strip=True).lower()
                for keyword, prov_name in _IAAC_PROV_MAP.items():
                    if keyword in loc_text:
                        province = prov_name
                        break

            # Status and assessment type from <li> elements with <strong> labels
            status_text = ''
            for li in art.select('li'):
                li_text = li.get_text(strip=True)
                if li_text.startswith('Status:'):
                    status_text = li_text.replace('Status:', '').strip()

            status = 'Under Review'
            sl = status_text.lower()
            if 'decision' in sl or 'approved' in sl or 'designated' in sl:
                status = 'Approved'
            elif 'withdrawn' in sl or 'terminated' in sl:
                status = 'Cancelled'
            elif 'under construction' in sl or 'operational' in sl:
                status = 'Under Construction'
            elif 'suspend' in sl:
                status = 'Suspended'

            projects.append({
                'name':             name,
                'province':         province,
                'status':           status,
                'source_url':       url,
                'discovery_source': 'iaac_registry',
                'sector':           _infer_sector_from_name(name),
            })

    except Exception as e:
        print(f"  [IAAC] Parse error: {type(e).__name__}: {e}")

    print(f"  [IAAC] {len(projects)} projects from registry")
    return projects


# ── BC Environmental Assessment Office ───────────────────────────────────────

# Live-verified 2026-06-09 (D-7): the EAO's EPIC public-search API returns
# HTTP 200 JSON in exactly the shape the parser expects —
# [{"searchResults": [...], "meta": [...]}] with per-project name/eacDecision/
# proponent/currentPhaseName keys (eacDecision and proponent are objects, which
# the parser already handles). The old /api/v2/projects path 404s and the
# previously suspected api-public.eao.gov.bc.ca host does not resolve in DNS.
_BC_EAO_API = "https://projects.eao.gov.bc.ca/api/public/search?dataset=Project&pageNum=0&pageSize=1000"

# Retired endpoints (additive-only — kept for the record, do not reuse):
#   https://www.projects.eao.gov.bc.ca/api/v2/projects?fields=...&pageSize=200  (404)
#   https://api-public.eao.gov.bc.ca/api/projects?fields=...&pageSize=200       (DNS-dead)
_BC_EAO_API_CANDIDATE = _BC_EAO_API  # superseded; the live endpoint is verified

def _scrape_bc_eao(tavily_client=None) -> list[dict]:
    """
    Fetch BC EAO project list via their public JSON API.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS)
        resp = http_client.get(_BC_EAO_API, timeout=20)
        if resp is None:
            print("  [BC EAO][TIER 1] FAILED status=network")
            return []
        if resp.status_code >= 400:
            print(f"  [BC EAO][TIER 1] FAILED status={resp.status_code} from {_BC_EAO_API[:70]}")
            return []
        data = resp.json()

        # Response is [{"searchResults": [...], "meta": [...]}]
        if isinstance(data, list) and len(data) >= 1 and isinstance(data[0], dict):
            rows = data[0].get('searchResults', [])
        elif isinstance(data, dict):
            rows = data.get('searchResults', data.get('data', data.get('projects', [])))
        else:
            rows = data if isinstance(data, list) else []

        if not rows:
            keys = list(data[0].keys())[:5] if isinstance(data, list) and data and isinstance(data[0], dict) else []
            print(f"  [BC EAO] No rows found. Type={type(data).__name__}, keys={keys}")

        projects = []
        for p in rows:
            name = p.get('name') or ''
            if not name:
                continue

            # Status from eacDecision
            eac_name = ''
            eac = p.get('eacDecision')
            if isinstance(eac, dict):
                eac_name = eac.get('name') or eac.get('decisionLabel') or ''
            ea_status = (p.get('eaStatus') or '').lower()
            status_raw = (p.get('status') or '').lower()

            status = 'Under Review'
            el = eac_name.lower()
            if 'approved' in el or 'issued' in el or 'certificate issued' in el:
                status = 'Approved'
            elif 'refused' in el or 'rejected' in el or 'withdrawn' in el:
                status = 'Cancelled'
            elif 'complete' in ea_status or 'complete' in status_raw:
                status = 'Completed'

            proponent = ''
            prop = p.get('proponent')
            if isinstance(prop, dict):
                proponent = prop.get('name') or ''
            elif isinstance(prop, str):
                proponent = prop

            pid = p.get('_id') or p.get('id') or ''
            url = f"https://projects.eao.gov.bc.ca/project/{pid}" if pid else ''

            sector_raw = p.get('sector') or ''
            sector = _infer_sector_from_name(name) if not sector_raw else sector_raw

            projects.append({
                'name':             name,
                'province':         'British Columbia',
                'status':           status,
                'proponent':        proponent,
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           sector,
            })

        print(f"  [BC EAO] {len(projects)} projects from registry")
        return projects

    except Exception as e:
        print(f"  [BC EAO] Failed: {type(e).__name__}: {e}")
        return []


# ── Infrastructure Canada ─────────────────────────────────────────────────────

_INFRA_CANADA_PAGE = "https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html"
_PROV_CODE_MAP = {
    'ab': 'Alberta', 'bc': 'British Columbia', 'mb': 'Manitoba',
    'nb': 'New Brunswick', 'nl': 'Newfoundland and Labrador',
    'ns': 'Nova Scotia', 'nt': 'Northwest Territories', 'nu': 'Nunavut',
    'on': 'Ontario', 'pe': 'Prince Edward Island', 'qc': 'Quebec',
    'sk': 'Saskatchewan', 'yt': 'Yukon',
    'alberta': 'Alberta', 'british columbia': 'British Columbia',
    'manitoba': 'Manitoba', 'new brunswick': 'New Brunswick',
    'newfoundland and labrador': 'Newfoundland and Labrador',
    'nova scotia': 'Nova Scotia', 'northwest territories': 'Northwest Territories',
    'nunavut': 'Nunavut', 'ontario': 'Ontario',
    'prince edward island': 'Prince Edward Island', 'quebec': 'Quebec',
    'saskatchewan': 'Saskatchewan', 'yukon': 'Yukon',
}

_INFRA_CANADA_API  = (
    "https://infrastructure.gc.ca/alt-format/opendata/"
    "project-list-liste-de-projets-bil.json"
)

def _scrape_infrastructure_canada(tavily_client=None) -> list[dict]:
    """
    Fetch Infrastructure Canada open data for funded projects.
    Uses the official JSON export from infrastructure.gc.ca.
    """
    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS)
        resp = http_client.get(_INFRA_CANADA_API, timeout=30)
        if resp is None:
            print("  [Infrastructure Canada][TIER 1] FAILED status=network")
            return []
        if resp.status_code >= 400:
            print(f"  [Infrastructure Canada][TIER 1] FAILED status={resp.status_code}")
            return []
        data = None
        try:
            data = resp.json()
        except Exception:
            pass

        if data is None:
            # Infra Canada JSON is severely malformed (CSV quoting, empty values,
            # trailing commas). Extract header + parse records robustly.
            import csv, io as _io
            text = resp.text
            # Extract indexTitles from the header portion
            m = re.search(r'"indexTitles"\s*:\s*(\[[^\]]+\])', text)
            if not m:
                print("  [Infrastructure Canada] Could not find indexTitles in response")
                return []
            import json as _json
            titles = _json.loads(m.group(1))
            # Extract the data portion — everything between "data":[ and the final ]}
            data_start = text.find('"data":[')
            if data_start < 0:
                print("  [Infrastructure Canada] Could not find data array in response")
                return []
            # Extract the data array portion
            data_arr_start = text.find('[', data_start + 6)  # find [ after "data":
            if data_arr_start < 0:
                print("  [Infrastructure Canada] Could not find data array start")
                return []
            # Use regex to split on ],[ pattern to get individual rows
            data_text = text[data_arr_start:]
            # Find matching ] for the outer array by simple splitting on row boundaries
            row_texts = re.split(r'\],\s*\[', data_text)
            records = []
            for j, rt in enumerate(row_texts):
                # Reconstruct the row as a proper JSON array
                row_str = rt.strip()
                if not row_str.startswith('['):
                    row_str = '[' + row_str
                if not row_str.endswith(']'):
                    # Remove trailing ]} at end of file
                    row_str = re.sub(r'\]\s*\}\s*$', '', row_str)
                    row_str = row_str.rstrip().rstrip(',')
                    row_str = row_str + ']'
                # Fix common malformed JSON issues
                row_str = row_str.replace('""', "'")
                while ',,' in row_str:
                    row_str = row_str.replace(',,', ',null,')
                row_str = re.sub(r',\s*\]', ']', row_str)
                try:
                    parsed_row = _json.loads(row_str)
                    if isinstance(parsed_row, list) and len(parsed_row) > 1:
                        records.append(dict(zip(titles, parsed_row + [None]*(len(titles)-len(parsed_row)))))
                except Exception:
                    pass  # skip unfixable rows
            print(f"  [Infrastructure Canada] Parsed {len(records)} records from malformed JSON")

        # Standard processing for well-formed JSON
        if data is not None:
            if isinstance(data, dict):
                keys = list(data.keys())[:5]
                if 'indexTitles' in data and 'data' in data:
                    titles = data['indexTitles']
                    raw_rows = data['data']
                    print(f"  [Infrastructure Canada] indexTitles format: {len(titles)} cols, {len(raw_rows)} rows")
                    records = []
                    for row in raw_rows:
                        if isinstance(row, list):
                            records.append(dict(zip(titles, row + [None]*(len(titles)-len(row)))))
                else:
                    records = (data.get('data') or data.get('records')
                               or data.get('projects') or (list(data.values())[0] if data else []))
                    if not records:
                        print(f"  [Infrastructure Canada] Dict keys: {keys}, no matching key found")
            else:
                records = data

        if not isinstance(records, list):
            print(f"  [Infrastructure Canada] records is {type(records).__name__}, not list")
            records = []
        elif records:
            sample_keys = list(records[0].keys())[:8] if isinstance(records[0], dict) else []
            print(f"  [Infrastructure Canada] {len(records)} raw records, sample keys: {sample_keys}")

        projects = []
        for row in records[:500]:
            if not isinstance(row, dict):
                continue
            # Try various field name conventions (bilingual JSON, indexTitles format)
            name = (row.get('projectTitle_en') or row.get('Project_Name_EN')
                    or row.get('Project_Name') or row.get('project_name_en')
                    or row.get('project_name') or '')
            if not name or len(name) < 5:
                continue

            raw_prov  = (row.get('region') or row.get('Province_Territory_EN')
                         or row.get('Province_Territory') or row.get('province') or '')
            province  = _PROV_CODE_MAP.get(raw_prov.lower().strip(), raw_prov)
            value_str = str(row.get('federalContribution') or row.get('totalEligibleCost')
                            or row.get('Federal_Contribution') or row.get('FederalContribution')
                            or row.get('total_funding') or '')
            try:
                val_num = float(re.sub(r'[^\d.]', '', value_str))
                value   = f"${val_num/1e9:.1f}B" if val_num >= 1e9 else f"${val_num/1e6:.0f}M"
            except Exception:
                value = ''

            status = (row.get('Project_Status_EN') or row.get('Project_Status')
                      or row.get('status') or 'Announced')

            projects.append({
                'name':             name,
                'province':         province,
                'status':           _map_status(status),
                'value':            value,
                'source_url':       _INFRA_CANADA_PAGE,
                'discovery_source': 'infrastructure_canada',
                'sector':           _infer_sector_from_name(name),
            })

        print(f"  [Infrastructure Canada] {len(projects)} projects from open data")
        return projects

    except Exception as e:
        print(f"  [Infrastructure Canada] Failed: {type(e).__name__}: {e}")
        return []


# ── BuyAndSell.gc.ca — Recent Awarded Contracts ──────────────────────────────

_CANADABUYS_CSV = (
    "https://canadabuys.canada.ca/opendata/pub/"
    "contractHistoryComplete-contratsOctroyesComplet.csv"
)
_CANADABUYS_PAGE = "https://canadabuys.canada.ca/en/procurement-and-contracting-data"

def _scrape_buyandsell(tavily_client=None) -> list[dict]:
    """
    Fetch recent large awarded contracts from CanadaBuys (formerly BuyAndSell).
    Downloads the open-data CSV and filters for contracts >= $5M.
    """
    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS).
        # stream=True flows through to requests; we still cap the download below.
        resp = http_client.get(_CANADABUYS_CSV, timeout=60, stream=True)
        if resp is None:
            print("  [CanadaBuys][TIER 1] FAILED status=network")
            return []
        if resp.status_code >= 400:
            print(f"  [CanadaBuys][TIER 1] FAILED status={resp.status_code}")
            return []

        import csv, io
        # Read first 2 MB to avoid downloading the full multi-GB file
        raw = b''
        for chunk in resp.iter_content(chunk_size=65536):
            raw += chunk
            if len(raw) >= 2_097_152:
                break
        text = raw.decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(text))

        projects = []
        for i, row in enumerate(reader):
            if i > 5000:  # safety cap
                break
            # Field names vary; try common variants
            name      = (row.get('description_en') or row.get('description')
                         or row.get('commodity_description') or '')
            value_str = str(row.get('contract_value') or row.get('value_contract') or '0')
            try:
                val_num = float(re.sub(r'[^\d.]', '', value_str))
            except Exception:
                val_num = 0

            if val_num < 5_000_000:
                continue

            value  = f"${val_num/1e9:.1f}B" if val_num >= 1e9 else f"${val_num/1e6:.0f}M"
            dept   = row.get('buyer_name') or row.get('department_en') or ''
            vendor = row.get('supplier_legal_name') or row.get('vendor_name') or ''

            projects.append({
                'name':             name or f"{dept} contract — {vendor}",
                'province':         'Canada',
                'status':           'Approved',
                'value':            value,
                'source_url':       _CANADABUYS_PAGE,
                'discovery_source': 'buyandsell',
                'sector':           _infer_sector_from_name(name),
                'proponent':        vendor,
            })
            if len(projects) >= 50:
                break

        print(f"  [CanadaBuys] {len(projects)} large contracts scraped")
        return projects

    except Exception as e:
        print(f"  [CanadaBuys] Failed: {type(e).__name__}: {e}")
        return []


# ── NRCan Major Projects Inventory ───────────────────────────────────────────

_NRCAN_PAGE = (
    "https://natural-resources.canada.ca/science-and-data/"
    "data-and-analysis/major-projects-inventory/22218"
)
_NRCAN_XLSX = (
    "https://ftp.maps.canada.ca/pub/nrcan_rncan/"
    "Natural-resources_Ressources-naturelles/major_projects_inventory/"
    "MPI_2024_Active_Projects_en.xlsx"
)

def _scrape_nrcan(tavily_client=None) -> list[dict]:
    """
    Fetch NRCan Major Projects Inventory.
    Primary: XLSX from NRCan FTP (openpyxl or Tavily fallback).
    Falls back to HTML scraping of the inventory page.
    """
    # Try HTML page first (lighter weight)
    html = _get_html(_NRCAN_PAGE)
    if html:
        try:
            soup = _soup(html)
            if soup:
                projects = []
                for el in (soup.select('table tbody tr') + soup.select('.field-items li'))[:60]:
                    name_el = el.find('a') or el.find('strong')
                    name    = name_el.get_text(strip=True) if name_el else el.get_text(strip=True)[:120]
                    if not name or len(name) < 5:
                        continue
                    url = ''
                    if name_el and name_el.name == 'a':
                        href = name_el.get('href', '')
                        url  = href if href.startswith('http') else f"https://natural-resources.canada.ca{href}"
                    projects.append({
                        'name':             name,
                        'province':         '',
                        'status':           'Announced',
                        'source_url':       url or _NRCAN_PAGE,
                        'discovery_source': 'nrcan',
                        'sector':           _infer_sector_from_name(name),
                    })
                if projects:
                    print(f"  [NRCan] {len(projects)} projects from inventory page")
                    return projects
        except Exception:
            pass

    # Fallback: Tavily extract
    if tavily_client:
        text = _extract_with_tavily(_NRCAN_PAGE, tavily_client)
        result = _parse_nrcan_text(text)
        if result:
            return result

    print("  [NRCan] No projects retrieved (page structure not parseable)", file=sys.stderr)
    return []


def _parse_nrcan_text(text: str) -> list[dict]:
    """Parse plain text from NRCan page (Tavily fallback)."""
    if not text:
        return []
    projects = []
    for line in text.split('\n'):
        line = line.strip()
        if len(line) > 20 and any(kw in line.lower() for kw in
                                   ('project', 'pipeline', 'mine', 'facility', 'terminal')):
            projects.append({
                'name':             line[:150],
                'province':         '',
                'status':           'Announced',
                'source_url':       _NRCAN_PAGE,
                'discovery_source': 'nrcan',
                'sector':           _infer_sector_from_name(line),
            })
    return projects[:30]


# ── Canada Energy Regulator (CER) ────────────────────────────────────────────

_CER_PROJECTS_URL = "https://www.cer-rec.gc.ca/en/applications-hearings/view-applications-projects/"

def _scrape_cer(tavily_client=None) -> list[dict]:
    """
    Scrape CER project list page for active and recent energy project filings.
    Returns list of project dicts with discovery_source='cer_registry'.
    """
    html = _get_html(_CER_PROJECTS_URL)
    if not html:
        print(f"  [CER] No HTML returned from {_CER_PROJECTS_URL}")
        return []

    projects = []
    try:
        soup = _soup(html)
        if not soup:
            return []

        seen_urls = set()
        # Skip category/meta links
        _SKIP_SLUGS = (
            'integrated-impact-assessment', 'export-licence-applications',
            'import-licence-applications', 'index',
        )

        for link in soup.select('a[href*="view-applications-projects/"]'):
            href = link.get('href', '')
            name = link.get_text(strip=True)

            # Filter out navigation, category, and short links
            if not name or len(name) < 12:
                continue
            if any(slug in href for slug in _SKIP_SLUGS):
                continue

            url = href if href.startswith('http') else f"https://www.cer-rec.gc.ca{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            projects.append({
                'name':             name,
                'province':         _infer_cer_province(name),
                'status':           'Under Review',
                'source_url':       url,
                'discovery_source': 'cer_registry',
                'sector':           'Energy',
            })

    except Exception as e:
        print(f"  [CER] Parse error: {type(e).__name__}: {e}")

    print(f"  [CER] {len(projects)} projects from applications page")
    return projects


def _infer_cer_province(name: str) -> str:
    """Guess province from CER project name (most are AB/BC pipeline projects)."""
    n = name.lower()
    if any(x in n for x in ('trans mountain', 'westcoast', 'british columbia', 'bc hydro')):
        return 'British Columbia'
    if any(x in n for x in ('ngtl', 'grande prairie', 'nova gas', 'enbridge mainline',
                             'keystone', 'alberta', 'atco', 'apex utilities')):
        return 'Alberta'
    if any(x in n for x in ('trans québec', 'trans quebec', 'maritimes & northeast',
                             'énergie saguenay', 'gazoduq')):
        return 'Quebec'
    if any(x in n for x in ('niagara', 'ontario', 'imperial oil ontario')):
        return 'Ontario'
    if any(x in n for x in ('saskpower', 'saskatchewan')):
        return 'Saskatchewan'
    if any(x in n for x in ('northwest', 'inuvialuit', 'imperial oil resources nwt',
                             'mackenzie')):
        return 'Northwest Territories'
    if any(x in n for x in ('cedar lng', 'woodfibre', 'pacific trail', 'coastal gaslink')):
        return 'British Columbia'
    return ''


# ── Ontario Environmental Registry (ERO) ─────────────────────────────────────

_ERO_SEARCH_URL = "https://ero.ontario.ca/search"

def _scrape_ontario_ero(tavily_client=None) -> list[dict]:
    """
    Scrape Ontario ERO for open infrastructure-relevant proposals.
    Returns list of project dicts with discovery_source='ontario_ero'.
    """
    projects = []
    seen_urls = set()
    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS)
        resp = http_client.get(
            _ERO_SEARCH_URL,
            params={'status': 'open', 'sort': 'posted_desc'},
            timeout=20,
        )
        if resp is None:
            print("  [Ontario ERO][TIER 1] FAILED status=network")
            return []
        if resp.status_code != 200:
            print(f"  [Ontario ERO][TIER 1] FAILED status={resp.status_code}")
            return []

        soup = _soup(resp.text)
        if not soup:
            return []

        for row in soup.select('.views-row')[:30]:
            title_el = row.select_one('h3 a') or row.select_one('a')
            if not title_el:
                continue
            name = title_el.get_text(strip=True)
            if not name or len(name) < 10:
                continue

            # Only keep infrastructure-relevant proposals
            sector = _infer_sector_from_name(name)
            if sector == 'Other':
                continue

            href = title_el.get('href', '')
            url = href if href.startswith('http') else f"https://ero.ontario.ca{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            projects.append({
                'name':             name,
                'province':         'Ontario',
                'status':           'Under Review',
                'source_url':       url,
                'discovery_source': 'ontario_ero',
                'sector':           sector,
            })

    except Exception as e:
        print(f"  [Ontario ERO] Failed: {type(e).__name__}: {e}")

    print(f"  [Ontario ERO] {len(projects)} infrastructure proposals")
    return projects


# ── Canada Infrastructure Bank (CIB) ─────────────────────────────────────────

_CIB_INVESTMENTS_URL = "https://cib-bic.ca/en/investments/"

def _scrape_cib(tavily_client=None) -> list[dict]:
    """
    Scrape CIB investment listings. The page is JS-rendered so we try
    Tavily extraction first, then fall back to parsing any static links.
    Returns list of project dicts with discovery_source='cib_investments'.
    """
    projects = []
    try:
        # CIB page is JS-rendered — try Tavily extract first
        if tavily_client:
            text = _extract_with_tavily(_CIB_INVESTMENTS_URL, tavily_client)
            if text:
                for line in text.split('\n'):
                    line = line.strip()
                    if len(line) < 15:
                        continue
                    # Look for lines that look like project names
                    if any(kw in line.lower() for kw in
                           ('project', 'transit', 'energy', 'broadband', 'bus',
                            'infrastructure', 'water', 'highway', 'rail', 'wind',
                            'solar', 'hydro', 'irrigation', 'housing', 'port',
                            'bridge', 'battery', 'ev charging', 'district energy')):
                        projects.append({
                            'name':             line[:150],
                            'province':         '',
                            'status':           'Approved',
                            'source_url':       _CIB_INVESTMENTS_URL,
                            'discovery_source': 'cib_investments',
                            'sector':           _infer_sector_from_name(line),
                        })
                        if len(projects) >= 50:
                            break

        # Fallback: try static HTML parsing
        if not projects:
            html = _get_html(_CIB_INVESTMENTS_URL)
            if html:
                soup = _soup(html)
                if soup:
                    seen_urls = set()
                    for link in soup.select('a[href*="invest"]'):
                        href = link.get('href', '')
                        name = link.get_text(strip=True)
                        if not name or len(name) < 10:
                            continue
                        if name.lower() in ('investments', 'investment process',
                                             'see all', 'learn more', 'back'):
                            continue
                        url = href if href.startswith('http') else f"https://cib-bic.ca{href}"
                        if url in seen_urls or url == _CIB_INVESTMENTS_URL:
                            continue
                        seen_urls.add(url)
                        projects.append({
                            'name':             name,
                            'province':         '',
                            'status':           'Approved',
                            'source_url':       url,
                            'discovery_source': 'cib_investments',
                            'sector':           _infer_sector_from_name(name),
                        })

    except Exception as e:
        print(f"  [CIB] Failed: {type(e).__name__}: {e}")

    print(f"  [CIB] {len(projects)} investment projects")
    return projects


# ── Quebec BAPE (Bureau d'audiences publiques sur l'environnement) ────────────

_BAPE_URL = "https://www.bape.gouv.qc.ca/fr/dossiers/"

def _scrape_quebec_bape(tavily_client=None) -> list[dict]:
    """
    Scrape Quebec BAPE for environmental assessment mandates/dossiers.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    try:
        html = _get_html(_BAPE_URL)
        if not html:
            # Try Tavily fallback
            if tavily_client:
                text = _extract_with_tavily(_BAPE_URL, tavily_client)
                if text:
                    for line in text.split('\n'):
                        line = line.strip()
                        if len(line) < 15 or len(line) > 200:
                            continue
                        sector = _infer_sector_from_name(line)
                        if sector != 'Other' or any(kw in line.lower() for kw in
                                ('projet', 'project', 'parc', 'mine', 'pipeline',
                                 'route', 'barrage', 'usine', 'terminal', 'port')):
                            projects.append({
                                'name':             line[:150],
                                'province':         'Quebec',
                                'status':           'Under Review',
                                'source_url':       _BAPE_URL,
                                'discovery_source': 'provincial_ea',
                                'sector':           sector if sector != 'Other' else 'Infrastructure',
                            })
                            if len(projects) >= 30:
                                break
            print(f"  [QC BAPE] {len(projects)} projects (Tavily fallback)")
            return projects

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        # BAPE dossiers are typically listed as links in article/card elements
        for link in soup.select('a[href*="/dossiers/"]'):
            name = link.get_text(strip=True)
            if not name or len(name) < 10:
                continue
            href = link.get('href', '')
            url = href if href.startswith('http') else f"https://www.bape.gouv.qc.ca{href}"
            if url in seen or url == _BAPE_URL:
                continue
            seen.add(url)
            projects.append({
                'name':             name,
                'province':         'Quebec',
                'status':           'Under Review',
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           _infer_sector_from_name(name),
            })

    except Exception as e:
        print(f"  [QC BAPE] Failed: {type(e).__name__}: {e}")

    print(f"  [QC BAPE] {len(projects)} projects from registry")
    return projects


# ── Alberta Environmental Assessment ─────────────────────────────────────────

_AB_EA_CURRENT_URL = "https://www.alberta.ca/environmental-impact-assessments-current-projects"
_AB_EA_HISTORICAL_URL = "https://www.alberta.ca/environmental-impact-assessments-historical-projects"

def _scrape_alberta_ea(tavily_client=None) -> list[dict]:
    """
    Scrape Alberta EPEA active and historical environmental assessments.
    Projects listed as h3 headings with proponent/stage in sibling paragraphs.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    for url, default_status in [(_AB_EA_CURRENT_URL, 'Under Review'),
                                 (_AB_EA_HISTORICAL_URL, 'Completed')]:
        try:
            html = _get_html(url, timeout=25)
            if not html:
                continue
            soup = _soup(html)
            if not soup:
                continue

            for h3 in soup.select('h3'):
                name = h3.get_text(strip=True)
                if not name or len(name) < 8:
                    continue

                proponent = ''
                status = default_status
                # Walk sibling <p> elements for metadata
                for sib in h3.find_next_siblings(['p', 'ul', 'h3'], limit=5):
                    if sib.name == 'h3':
                        break
                    sib_text = sib.get_text(strip=True)
                    if 'Proponent:' in sib_text or 'proponent:' in sib_text:
                        proponent = re.sub(r'(?i)proponent:\s*', '', sib_text).strip()
                    if 'Project stage:' in sib_text or 'project stage:' in sib_text:
                        stage = re.sub(r'(?i)project stage:\s*', '', sib_text).strip()
                        status = _map_status(stage)

                projects.append({
                    'name':             name,
                    'province':         'Alberta',
                    'status':           status,
                    'proponent':        proponent,
                    'source_url':       url,
                    'discovery_source': 'provincial_ea',
                    'sector':           _infer_sector_from_name(name),
                })

        except Exception as e:
            print(f"  [AB EA] Error on {url[:50]}: {type(e).__name__}: {e}")

    print(f"  [AB EA] {len(projects)} projects from registry")
    return projects


# ── Saskatchewan Environmental Assessment ────────────────────────────────────

_SK_EA_URL = "https://www.saskatchewan.ca/business/environmental-protection-and-sustainability/environmental-assessment/environmental-assessment-projects"

def _scrape_saskatchewan_ea(tavily_client=None) -> list[dict]:
    """
    Scrape Saskatchewan EA projects page for recent activity entries.
    The page has a chronological activity log with project names and decisions.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    try:
        html = _get_html(_SK_EA_URL, timeout=25)
        if not html:
            if tavily_client:
                text = _extract_with_tavily(_SK_EA_URL, tavily_client)
                if text:
                    return _parse_text_for_projects(text, 'Saskatchewan', 'provincial_ea', _SK_EA_URL)
            return []

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        # Parse activity log entries and links to project pages
        for link in soup.select('a[href*="publications.saskatchewan.ca"], a[href*="environmental-assessment"]'):
            name = link.get_text(strip=True)
            if not name or len(name) < 10 or name.lower() in seen:
                continue
            seen.add(name.lower())
            href = link.get('href', '')
            url = href if href.startswith('http') else f"https://www.saskatchewan.ca{href}"

            projects.append({
                'name':             name,
                'province':         'Saskatchewan',
                'status':           'Under Review',
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           _infer_sector_from_name(name),
            })

        # Also parse plain-text activity log entries (e.g., "Project X receives Ministerial Approval")
        for p_tag in soup.select('p, li'):
            text = p_tag.get_text(strip=True)
            if not text or len(text) < 20:
                continue
            for keyword in ('receives ministerial', 'approved', 'registration', 'technical review'):
                if keyword.lower() in text.lower():
                    # Extract project name (usually before the keyword)
                    idx = text.lower().index(keyword.lower())
                    candidate = text[:idx].strip().rstrip('–—-').strip()
                    if candidate and len(candidate) > 10 and candidate.lower() not in seen:
                        seen.add(candidate.lower())
                        status = 'Approved' if 'approv' in keyword.lower() else 'Under Review'
                        projects.append({
                            'name':             candidate[:150],
                            'province':         'Saskatchewan',
                            'status':           status,
                            'source_url':       _SK_EA_URL,
                            'discovery_source': 'provincial_ea',
                            'sector':           _infer_sector_from_name(candidate),
                        })
                    break

    except Exception as e:
        print(f"  [SK EA] Failed: {type(e).__name__}: {e}")

    print(f"  [SK EA] {len(projects)} projects from registry")
    return projects


# ── Manitoba Environment Act Proposals ───────────────────────────────────────

_MB_EA_URL = "https://www.gov.mb.ca/sd/eal/registries/"

def _scrape_manitoba_ea(tavily_client=None) -> list[dict]:
    """
    Scrape Manitoba Environment Act proposals registry.
    Page has tabbed tables with File Number, Proponent, Project Name, etc.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    skipped_doctype = 0
    try:
        html = _get_html(_MB_EA_URL, timeout=25)
        if not html:
            return []

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        tables = soup.select('table')
        for table in tables:
            rows = table.select('tr')
            for row in rows[1:]:  # Skip header
                cells = row.select('td')
                if len(cells) < 3:
                    continue

                # Table columns vary but Project Name is usually column 2 or 3
                name = ''
                proponent = ''
                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    if not text:
                        continue
                    # First substantial text cell after file number is usually proponent
                    if i == 1 and len(text) > 3:
                        proponent = text
                    # Project name is usually the longest cell or contains project keywords
                    if i == 2 and len(text) > 5:
                        name = text

                if not name or len(name) < 5 or name.lower() in seen:
                    continue
                seen.add(name.lower())

                # P1: skip value-less document filings (FMPs, EIS, notices)
                if _skip_non_project_filing(name):
                    skipped_doctype += 1
                    continue

                # Try to get link
                link = row.select_one('a')
                url = ''
                if link:
                    href = link.get('href', '')
                    url = href if href.startswith('http') else f"https://www.gov.mb.ca{href}"

                # P2 (2026-06-08 audit): pull status from the registry row
                # where it states one, instead of blanket-stamping every
                # filing 'Under Review' (1,952/2,037 MB rows were stuck
                # there). Default stays Under Review — a filed Environment
                # Act proposal IS under review when the row says nothing.
                row_status = 'Under Review'
                for cell in cells[3:]:
                    cell_text = cell.get_text(strip=True)
                    if cell_text and re.search(
                            r'(?i)\b(approv|licen[cs]e|issued|construction|'
                            r'complete|operational|cancel|withdraw|refus|'
                            r'suspend|on hold|deferred)\w*', cell_text):
                        row_status = _map_status(cell_text)
                        break

                projects.append({
                    'name':             name[:200],
                    'province':         'Manitoba',
                    'status':           row_status,
                    'proponent':        proponent,
                    'source_url':       url or _MB_EA_URL,
                    'discovery_source': 'provincial_ea',
                    'sector':           _infer_sector_from_name(name),
                })

    except Exception as e:
        print(f"  [MB EA] Failed: {type(e).__name__}: {e}")

    if skipped_doctype:
        print(f"  [MB EA] skipped {skipped_doctype} non-project filings")
    print(f"  [MB EA] {len(projects)} projects from registry")
    return projects


# ── Nova Scotia Environmental Assessment ─────────────────────────────────────

_NS_EA_URL = "https://novascotia.ca/nse/ea/projects.asp"

def _scrape_nova_scotia_ea(tavily_client=None) -> list[dict]:
    """
    Scrape Nova Scotia EA projects table.
    Two tables: 'Projects under review' and 'Completed reviews'.
    Columns: Project Name (linked), Proponent, Date.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    try:
        html = _get_html(_NS_EA_URL, timeout=25)
        if not html:
            return []

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        # Track which section we're in for status
        current_status = 'Under Review'
        tables = soup.select('table')

        for table_idx, table in enumerate(tables):
            # Second table is typically completed reviews
            if table_idx >= 1:
                current_status = 'Completed'

            rows = table.select('tr')
            for row in rows[1:]:  # Skip header
                cells = row.select('td')
                if not cells:
                    continue

                # First cell usually has project name (linked)
                name_cell = cells[0]
                link = name_cell.select_one('a')
                if link:
                    name = link.get_text(strip=True)
                    href = link.get('href', '')
                    url = href if href.startswith('http') else f"https://novascotia.ca/nse/ea/{href}"
                else:
                    name = name_cell.get_text(strip=True)
                    url = _NS_EA_URL

                if not name or len(name) < 5 or name.lower() in seen:
                    continue
                seen.add(name.lower())

                proponent = cells[1].get_text(strip=True) if len(cells) > 1 else ''

                projects.append({
                    'name':             name,
                    'province':         'Nova Scotia',
                    'status':           current_status,
                    'proponent':        proponent,
                    'source_url':       url,
                    'discovery_source': 'provincial_ea',
                    'sector':           _infer_sector_from_name(name),
                })

    except Exception as e:
        print(f"  [NS EA] Failed: {type(e).__name__}: {e}")

    print(f"  [NS EA] {len(projects)} projects from registry")
    return projects


# ── New Brunswick Environmental Impact Assessment ────────────────────────────

# Live-verified 2026-06-09 (D-7): GNB migrated the EA program to www.gnb.ca
# under /en/topic/environment-resources/. The new landing page links to
# 'projects.html' (current EA projects) and 'registered-eia.html' (registry),
# both confirmed 200. The old www2.gnb.ca landing page still serves 200, but
# its relative /en/topic/... links resolve only on www.gnb.ca — which is why
# sub-page scraping returned 404s when prefixed with the old host. Sub-links
# are now resolved against the landing page's own host via urljoin.
# Retired (additive-only, kept for the record):
#   https://www2.gnb.ca/content/gnb/en/departments/elg/environment/content/environmental_impactassessment.html
#   (the underscore variant 'environmental_impact_assessment.html' 404s)
_NB_EIA_URL = "https://www.gnb.ca/en/topic/environment-resources/environmental-assessment.html"
# Current EA projects are listed as <h2> sections on this page (one heading per
# project, e.g. "NB Power — ARC Clean Technology — Advanced Small Modular
# Reactor"). registered-eia.html is only an explainer, not a registry listing.
_NB_EIA_CURRENT_PROJECTS_URL = ("https://www.gnb.ca/en/topic/environment-resources/"
                                "environmental-assessment/projects/current.html")

# Page-chrome headings on GNB pages that are not project names.
_NB_BOILERPLATE = frozenset({
    'on this page', 'get help', 'overview', 'related links', 'contact',
    'example 1', 'example 2', 'example 3',
})


def _scrape_nb_ea(tavily_client=None) -> list[dict]:
    """
    Scrape New Brunswick EIA current-projects page for project listings.
    Falls back to crawling EA-section links off the landing page if the
    current-projects page yields nothing (page structure drift guard).
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    seen = set()

    def _add(name: str, url: str):
        key = name.lower()
        if len(name) < 10 or key in seen or key in _NB_BOILERPLATE or '(pdf' in key:
            return
        seen.add(key)
        projects.append({
            'name':             name[:200],
            'province':         'New Brunswick',
            'status':           'Under Review',
            'source_url':       url,
            'discovery_source': 'provincial_ea',
            'sector':           _infer_sector_from_name(name),
        })

    try:
        # Primary: the current-projects page — one <h2> per project.
        html = _get_html(_NB_EIA_CURRENT_PROJECTS_URL, timeout=25)
        if html:
            soup = _soup(html)
            if soup:
                main = soup.select_one('main') or soup
                for h in main.select('h2, h3'):
                    _add(h.get_text(strip=True), _NB_EIA_CURRENT_PROJECTS_URL)
        else:
            print(f"  [NB EIA] current-projects page unreachable (404/timeout): "
                  f"{_NB_EIA_CURRENT_PROJECTS_URL}")

        if not projects:
            # Fallback: crawl EA-section sub-pages linked off the landing page.
            # Restrict to hrefs inside the environmental-assessment section so
            # GNB's site-wide nav links don't pollute the project list (the
            # generic crawl previously ingested "Business and economy" etc.).
            html = _get_html(_NB_EIA_URL, timeout=25)
            if not html:
                print("  [NB EIA] registry endpoint dead (404) — needs manual re-point")
            soup = _soup(html) if html else None
            sub_urls = []
            if soup:
                for link in soup.select('a'):
                    href = link.get('href', '')
                    text = link.get_text(strip=True).lower()
                    if 'environmental-assessment' not in href:
                        continue
                    if any(kw in text for kw in ('determination', 'comprehensive',
                                                 'registration', 'registered', 'project')):
                        # Resolve relative links against the landing page's own
                        # host (paths 404 on the old www2.gnb.ca host).
                        full = href if href.startswith('http') else urllib.parse.urljoin(_NB_EIA_URL, href)
                        if full not in sub_urls and full != _NB_EIA_URL:
                            sub_urls.append(full)

            for sub_url in sub_urls[:4]:
                try:
                    sub_html = _get_html(sub_url, timeout=20)
                    sub_soup = _soup(sub_html) if sub_html else None
                    if not sub_soup:
                        continue
                    main = sub_soup.select_one('main') or sub_soup
                    for el in main.select('h2, h3, table tr td a, ul li a'):
                        name = el.get_text(strip=True)
                        href = el.get('href', '') if el.name == 'a' else ''
                        url = (href if href.startswith('http')
                               else urllib.parse.urljoin(sub_url, href)) if href else sub_url
                        _add(name, url)
                    time.sleep(0.5)
                except Exception:
                    pass

    except Exception as e:
        print(f"  [NB EIA] Failed: {type(e).__name__}: {e}")

    print(f"  [NB EIA] {len(projects)} projects from registry")
    return projects


# ── Newfoundland and Labrador Environmental Assessment ───────────────────────

_NL_EA_URL = "https://www.gov.nl.ca/ecc/env-assessment/projects-list/"

def _scrape_nl_ea(tavily_client=None) -> list[dict]:
    """
    Scrape Newfoundland EA projects table.
    WordPress table: Reg.#, Title/Proponent, Date Registered, Status, Release Date.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    skipped_doctype = 0
    try:
        html = _get_html(_NL_EA_URL, timeout=25)
        if not html:
            # Try main EA page
            html = _get_html("https://www.gov.nl.ca/ecc/env-assessment/", timeout=25)
            if not html:
                return []

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        for row in soup.select('table tr'):
            cells = row.select('td')
            if len(cells) < 3:
                continue

            # Title is usually in second cell, may contain link
            name_cell = cells[1] if len(cells) > 1 else cells[0]
            link = name_cell.select_one('a')
            if link:
                name = link.get_text(strip=True)
                href = link.get('href', '')
                url = href if href.startswith('http') else f"https://www.gov.nl.ca{href}"
            else:
                name = name_cell.get_text(strip=True)
                url = _NL_EA_URL

            if not name or len(name) < 8 or name.lower() in seen:
                continue

            # P1: skip value-less document filings (FMPs, EIS, notices)
            if _skip_non_project_filing(name):
                skipped_doctype += 1
                continue

            # Extract proponent if embedded (often "Proponent: CompanyName")
            proponent = ''
            name_text = name_cell.get_text('\n', strip=True)
            for part in name_text.split('\n'):
                if 'proponent' in part.lower():
                    proponent = re.sub(r'(?i)proponent:\s*', '', part).strip()

            # Status from later cell
            status = 'Under Review'
            if len(cells) > 3:
                status_text = cells[3].get_text(strip=True)
                status = _map_status(status_text)

            seen.add(name.lower())
            projects.append({
                'name':             name[:200],
                'province':         'Newfoundland and Labrador',
                'status':           status,
                'proponent':        proponent,
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           _infer_sector_from_name(name),
            })

    except Exception as e:
        print(f"  [NL EA] Failed: {type(e).__name__}: {e}")

    if skipped_doctype:
        print(f"  [NL EA] skipped {skipped_doctype} non-project filings")
    print(f"  [NL EA] {len(projects)} projects from registry")
    return projects


# ── Yukon YESAB Registry ────────────────────────────────────────────────────

# Live-verified 2026-06-11: yesabregistry.ca is a React SPA whose /projects
# page serves only an empty JS shell ("You need to enable JavaScript") — which
# is why the old HTML scrape returned 0 with no error. The app bundle
# (main.*.chunk.js) calls a public JSON API:
#   GET https://yesabregistry.ca/api/projects/search
#     -> {"projects": [{projectId, projectNumber, title, proponentName,
#                       stageId, locations, ...}], "districtCount": N}
#   GET https://yesabregistry.ca/api/projects/stages
#     -> [{stageId, name, stageGrouping, ...}]  (73 stages across 3 streams)
# Live yield 2026-06-11: 207 active projects. Project detail pages resolve at
# https://yesabregistry.ca/projects/{projectId}.
_YESAB_URL = "https://yesabregistry.ca/projects"
_YESAB_API_SEARCH = "https://yesabregistry.ca/api/projects/search"
_YESAB_API_STAGES = "https://yesabregistry.ca/api/projects/stages"

# Red-team fix 2026-06-11: the raw search API returns ~207 ACTIVE assessments,
# most of which are not capital projects — individual placer-mining
# operations, guided hiking / rafting / hunting concessions, and wildlife
# research permits. Unfiltered, they would inject ~200 unpriced rows into YT
# (threshold $3M) and inflate the briefing's "new projects" count. The filter
# below keeps only capital-relevant assessments.

# Titles that indicate recreation / research / placer activity — excluded.
_YESAB_EXCLUDE_TITLE_RE = re.compile(
    r"(?i)(placer\b|outfitt|hiking|rafting|expeditions?\b|hunting|"
    r"trapping|tourism\s+concession|research|study|monitoring|survey|"
    r"harassment|camp\b|trail\b|guided|recreation|filming)")

# Strong capital keywords — a title matching one of these is kept even when
# the proponent looks like a private individual.
_YESAB_CAPITAL_TITLE_RE = re.compile(
    r"(?i)(mine\b|quartz|road\b|bridge|power|hydro|dam\b|subdivision|"
    r"quarry|airport|pipeline|transmission|wind|solar|sewage|"
    r"water\s+treatment)")

# Organization tokens — a proponent containing any of these is NOT treated
# as a private individual.
_YESAB_ORG_TOKEN_RE = re.compile(
    r"(?i)\b(corp|inc|ltd|lt[ée]e|mining|energy|resources|government|"
    r"first\s+nation|corporation|company)\b")


def _yesab_is_individual_proponent(proponent: str) -> bool:
    """Heuristic: proponent looks like a private individual — two or three
    capitalized words with no organization token (Corp/Inc/Ltd/Mining/...)."""
    p = (proponent or '').strip()
    if not p:
        return False
    if _YESAB_ORG_TOKEN_RE.search(p):
        return False
    words = [w for w in p.split() if w]
    return (2 <= len(words) <= 3
            and all(w[:1].isupper() for w in words))


# Red-team fix 2026-06-11 (sector labels): _infer_sector_from_name returns
# non-canonical display labels ('Mining', 'Clean Energy', 'Ports & Logistics')
# and has substring traps ('Airport' matches 'port'). Other scrapers still
# call it, so it is left untouched; the YESAB boundary maps its output to the
# canonical 18 lowercase NAICS keys here, with word-boundary pre-checks for
# the known traps.
_YESAB_SECTOR_CANONICAL = {
    'Mining': 'mining',
    'Energy': 'power_energy',
    'Clean Energy': 'power_energy',
    'Ports & Logistics': 'transport_logistics',
    'Transit & Rail': 'transport_logistics',
    'Infrastructure': 'infrastructure',
    'Housing': 'residential',
    'Healthcare': 'healthcare',
    'Education': 'education',
    'Defence': 'defence',
    'Water & Wastewater': 'infrastructure',
    'Telecommunications': 'telecom',
    'Technology & Data': 'telecom',
}


def _yesab_canonical_sector(name: str) -> str:
    """Canonical lowercase NAICS sector for a YESAB title."""
    n = name or ''
    # Word-boundary pre-checks before the substring-based inferrer:
    # 'Airport' would otherwise match 'port' → Ports & Logistics.
    if re.search(r'(?i)\bairports?\b', n):
        return 'transport_logistics'
    if re.search(r'(?i)\b(placer|quartz)\b', n):
        return 'mining'
    raw = _infer_sector_from_name(n)
    if raw in _YESAB_SECTOR_CANONICAL:
        return _YESAB_SECTOR_CANONICAL[raw]
    # Unknown/'Other' fallback per Yukon reality: most assessments are mineral.
    if re.search(r'(?i)\bmin(e|es|ing)\b', n):
        return 'mining'
    return 'infrastructure'


def _scrape_yukon_yesab(tavily_client=None) -> list[dict]:
    """
    Fetch YESAB project registry via its public JSON search API (the
    /projects page itself is a JS-rendered SPA shell with no server-side
    content). Falls back to Tavily extraction of the SPA page if the API
    fails. Logs HTTP status and parsed counts so failures are never silent.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    try:
        resp = http_client.get(_YESAB_API_SEARCH, timeout=25)
        status = 'network' if resp is None else resp.status_code
        print(f"  [YESAB] API search HTTP status={status}")
        if resp is not None and resp.status_code < 400:
            data = resp.json()
            rows = data.get('projects', []) if isinstance(data, dict) else []
            print(f"  [YESAB] API returned {len(rows)} raw project rows")

            # Stage map for status mapping (stageId -> name + grouping).
            # Failure-tolerant: on any error all projects default to Under Review.
            stage_map = {}
            try:
                sresp = http_client.get(_YESAB_API_STAGES, timeout=20)
                if sresp is not None and sresp.status_code < 400:
                    for s in sresp.json():
                        sid = s.get('stageId')
                        if sid:
                            stage_map[sid] = (s.get('name') or '',
                                              s.get('stageGrouping') or '')
            except Exception as se:
                print(f"  [YESAB] stages lookup failed ({type(se).__name__}) "
                      "— defaulting all statuses to Under Review")

            excluded = 0
            for p in rows:
                name = (p.get('title') or '').strip()
                if not name or len(name) < 5:
                    continue
                proponent = (p.get('proponentName') or '').strip()

                # Red-team fix: capital-relevance filter. Recreation /
                # research / placer titles are excluded outright; private-
                # individual proponents are excluded unless the title carries
                # a strong capital keyword.
                strong_capital = bool(_YESAB_CAPITAL_TITLE_RE.search(name))
                if _YESAB_EXCLUDE_TITLE_RE.search(name):
                    excluded += 1
                    continue
                if (_yesab_is_individual_proponent(proponent)
                        and not strong_capital):
                    excluded += 1
                    continue

                stage_name, grouping = stage_map.get(p.get('stageId'), ('', ''))
                sl = f"{stage_name} {grouping}".lower()
                status_val = 'Under Review'
                if 'decision document issued' in sl:
                    status_val = 'Approved'
                elif 'not proceeding' in sl or 'withdrawn before screening' in sl:
                    # Red-team fix: "Project Not Proceeding To Screening" is
                    # an assessment-track determination, NOT a project
                    # cancellation — Cancelled is terminal under the status
                    # non-regression rule. Park these as On Hold.
                    status_val = 'On Hold'
                elif 'withdrawn' in sl:
                    # Explicit withdrawal by the proponent — terminal.
                    status_val = 'Cancelled'
                elif 'discontinued' in sl:
                    # "Assessment Discontinued" / "Panel Discontinued" are
                    # likewise assessment-track outcomes, not confirmed
                    # project cancellations.
                    status_val = 'On Hold'
                pid = p.get('projectId') or ''
                url = f"https://yesabregistry.ca/projects/{pid}" if pid else _YESAB_URL
                projects.append({
                    'name':             name[:200],
                    'province':         'Yukon',
                    'status':           status_val,
                    'proponent':        proponent[:200],
                    'source_url':       url,
                    'discovery_source': 'provincial_ea',
                    'sector':           _yesab_canonical_sector(name),
                })
            print(f"  [YESAB] {len(rows)} assessments -> {len(projects)} "
                  f"capital-relevant (excluded {excluded} "
                  "recreation/research/placer)")

        if not projects and tavily_client:
            # Legacy fallback: Tavily extraction of the SPA page.
            print("  [YESAB] API yielded 0 — falling back to Tavily extraction")
            text = _extract_with_tavily(_YESAB_URL, tavily_client)
            if text:
                projects = _parse_text_for_projects(text, 'Yukon', 'provincial_ea', _YESAB_URL)

    except Exception as e:
        print(f"  [YESAB] Failed: {type(e).__name__}: {e}")

    if not projects:
        print("  [YESAB] registry API unreachable or schema drift — needs manual re-point")
    print(f"  [YESAB] {len(projects)} projects from registry")
    return projects


# ── Mackenzie Valley Review Board (NWT) ──────────────────────────────────────

_MVRB_URL = "https://new.reviewboard.ca/en/registry"

def _scrape_nwt_mvrb(tavily_client=None) -> list[dict]:
    """
    Scrape Mackenzie Valley Review Board project registry.
    Modern web app with project listings.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    try:
        html = _get_html(_MVRB_URL, timeout=25)
        if not html:
            if tavily_client:
                text = _extract_with_tavily(_MVRB_URL, tavily_client)
                if text:
                    return _parse_text_for_projects(text, 'Northwest Territories', 'provincial_ea', _MVRB_URL)
            return []

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        # Projects appear as links or h4 elements with EA reference numbers
        for el in soup.select('a[href*="/registry/ea"], a[href*="/registry/"], h4 a, h3 a'):
            name = el.get_text(strip=True)
            if not name or len(name) < 8 or name.lower() in seen:
                continue
            # Skip navigation links
            if name.lower() in ('registry', 'home', 'search', 'about', 'contact'):
                continue
            seen.add(name.lower())
            href = el.get('href', '')
            url = href if href.startswith('http') else f"https://new.reviewboard.ca{href}"
            projects.append({
                'name':             name,
                'province':         'Northwest Territories',
                'status':           'Under Review',
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           _infer_sector_from_name(name),
            })

    except Exception as e:
        print(f"  [MVRB] Failed: {type(e).__name__}: {e}")

    print(f"  [MVRB] {len(projects)} projects from registry")
    return projects


# ── Nunavut Impact Review Board (NIRB) ───────────────────────────────────────
# Live-probed 2026-06-10 (quality-pass-1.4 G3): nirb.ca is server-rendered
# Drupal; the public registry search is a PHP portal. POSTing
# registry-search-results.php with whattosearchfor=project +
# searchonlyactive=on returns a page that embeds a `geometry_layer`
# JS array carrying application_id / nirb_file_number / project_name /
# proponent_name / activity_type — parseable without any JS execution.

_NIRB_URL = "https://www.nirb.ca/"
_NIRB_SEARCH_URL = "https://www.nirb.ca/portal/registry-search-results.php"

_NIRB_GEOMETRY_RE = re.compile(
    r"geometry_layer\s*=\s*eval\('\((\[.*?\])\)'\)", re.DOTALL)


def _scrape_nunavut_nirb(tavily_client=None) -> list[dict]:
    """
    Scrape the NIRB public registry for active Nunavut assessments.
    POST search (server-side PHP) — Live-verified 2026-06-10.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    import json as _json
    projects = []
    try:
        payload = {
            'lang': 'en', 'action': 'search',
            'polygonpoints': '', 'searchpolygon': '',
            'whattosearchfor': 'project',
            'searchkeywords': '',
            'searchonlyactive': 'on',
        }
        resp = requests.post(
            _NIRB_SEARCH_URL, data=payload, timeout=60,
            headers={'User-Agent': http_client.USER_AGENT})
        if resp.status_code != 200:
            print(f"  [NIRB][TIER 1] FAILED status={resp.status_code}")
            raise RuntimeError(f"status {resp.status_code}")

        m = _NIRB_GEOMETRY_RE.search(resp.text)
        if not m:
            print("  [NIRB] geometry_layer block not found in results page")
            raise RuntimeError("no geometry_layer")

        entries = _json.loads(m.group(1))
        seen_ids = set()
        for entry in entries:
            app_id = str(entry.get('application_id') or '')
            name = (entry.get('project_name') or '').strip()
            if not app_id or app_id in seen_ids or len(name) < 4:
                continue
            seen_ids.add(app_id)
            activity = (entry.get('activity_type') or '').strip()
            if _skip_non_project_filing(name):
                continue
            sector = _infer_sector_from_name(f"{name} {activity}")
            projects.append({
                'name':             name[:200],
                'province':         'Nunavut',
                'status':           'Under Review',
                'proponent':        (entry.get('proponent_name') or '')[:120],
                'source_url':       f"https://www.nirb.ca/project/{app_id}",
                'discovery_source': 'provincial_ea',
                'sector':           sector if sector != 'Other' else 'Infrastructure',
            })
            if len(projects) >= 200:
                break

    except Exception as e:
        print(f"  [NIRB] Failed: {type(e).__name__}: {e}")
        # Tavily fallback, same pattern as YESAB
        if not projects and tavily_client:
            try:
                text = _extract_with_tavily(_NIRB_URL, tavily_client)
                if text:
                    projects = _parse_text_for_projects(
                        text, 'Nunavut', 'provincial_ea', _NIRB_URL)
            except Exception:
                pass

    print(f"  [NIRB] {len(projects)} projects from registry")
    return projects


# ── Mackenzie Valley Land and Water Board (NWT) ──────────────────────────────
# Live-probed 2026-06-10 (quality-pass-1.4 G3): mvlwb.com/registry is a
# server-rendered Drupal table (Company / Activity / File Number / Start Date /
# Expiry Date, 50 rows per page). The water licence / land use permit registry
# is an EARLIER signal than the MVRB review board (permits precede EAs).
# Sorting by start date desc surfaces the most recent authorizations.

_MVLWB_URL = ("https://mvlwb.com/registry"
              "?search_api_views_fulltext=&order=date_start&sort=desc")

def _scrape_nwt_mvlwb(tavily_client=None) -> list[dict]:
    """
    Scrape Mackenzie Valley Land and Water Board permit registry (most
    recent authorizations first). Live-verified 2026-06-10.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    projects = []
    try:
        html = _get_html(_MVLWB_URL, timeout=40)
        if not html:
            if tavily_client:
                text = _extract_with_tavily(_MVLWB_URL, tavily_client)
                if text:
                    return _parse_text_for_projects(
                        text, 'Northwest Territories', 'provincial_ea', _MVLWB_URL)
            return []

        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        for row in soup.select('table tr'):
            cells = row.select('td')
            if len(cells) < 4:
                continue
            company = cells[0].get_text(strip=True)
            activity = cells[1].get_text(strip=True)
            file_cell = cells[2]
            file_no = file_cell.get_text(strip=True)
            if not file_no or file_no.lower() in seen:
                continue
            # Skip ancient/blank-proponent rows — not actionable discoveries
            if not company or company.upper() == '(NONE)':
                continue
            seen.add(file_no.lower())
            link = file_cell.select_one('a') or row.select_one('a[href*="/registry/"]')
            href = link.get('href', '') if link else ''
            url = (href if href.startswith('http')
                   else f"https://mvlwb.com{href}") if href else _MVLWB_URL
            name = f"{company} — {activity} ({file_no})"
            sector = _infer_sector_from_name(f"{company} {activity}")
            projects.append({
                'name':             name[:200],
                'province':         'Northwest Territories',
                'status':           'Approved',   # registry lists issued authorizations
                'proponent':        company[:120],
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           sector if sector != 'Other' else 'Infrastructure',
            })
            if len(projects) >= 50:
                break

    except Exception as e:
        print(f"  [MVLWB] Failed: {type(e).__name__}: {e}")

    print(f"  [MVLWB] {len(projects)} permits from registry")
    return projects


# ── ISC Indigenous Community Infrastructure (federal) ────────────────────────
# Live-probed 2026-06-10 (quality-pass-1.4 G3): open.canada.ca CKAN dataset
# 62155d6f-9167-4972-b77c-b90734b628dc (org isc-sac) — "Indigenous Community
# Infrastructure". The machine-readable resource is a CSV inside a zip on
# data.sac-isc.gc.ca (28,974 rows). Ongoing rows carry no dollar values
# (verified: zero Ongoing rows have investment >= $1M populated), so the
# filter is category + construction-keyword based, capped per run.

_ISC_INFRA_CSV_ZIP = (
    "https://data.sac-isc.gc.ca/geomatics/rest/directories/arcgisoutput/"
    "DonneesOuvertes_OpenData/Infrastructure_communaute_autochtone_"
    "Indigenous_community_infrastructure/Indigenous_Community_Infrastructure_CSV.zip"
)
_ISC_DATASET_URL = ("https://open.canada.ca/data/en/dataset/"
                    "62155d6f-9167-4972-b77c-b90734b628dc")

# Capital infrastructure categories (excludes Housing — 10,932 rows of
# band-level micro-grants — and admin/program categories).
_ISC_CAPITAL_CATEGORIES = frozenset({
    'Water and wastewater', 'Health infrastructure', 'Education infrastructure',
    'Roads and bridges', 'Energy systems', 'Structural mitigation',
    'Urban infrastructure', 'Band administrative buildings',
    'Culture and recreation', 'Fire protection on reserves', 'Connectivity',
})

_ISC_CONSTRUCTION_RE = re.compile(
    r'construction|new |build|expansion|upgrade|replacement|renovation'
    r'|subdivision|treatment plant|school|health centre|health center'
    r'|water plant|lagoon|retrofit|addition', re.IGNORECASE)

# Program/study/equipment rows that are not capital projects
_ISC_SKIP_RE = re.compile(
    r'^(capacity enhancement|feasibility|study|training|workshop'
    r'|asset management|operation and maintenance|acquisition|purchase)',
    re.IGNORECASE)

_ISC_MAX_PROJECTS = 400

# ISC CSV uses non-breaking spaces in some province names
def _isc_norm_province(raw: str) -> str:
    return (raw or '').replace('\xa0', ' ').strip()

_ISC_SECTOR_BY_CATEGORY = {
    'Water and wastewater':          'Water & Wastewater',
    'Health infrastructure':         'Healthcare',
    'Education infrastructure':      'Education',
    'Roads and bridges':             'Infrastructure',
    'Energy systems':                'Clean Energy',
    'Structural mitigation':         'Infrastructure',
    'Urban infrastructure':          'Infrastructure',
    'Band administrative buildings': 'Infrastructure',
    'Culture and recreation':        'Infrastructure',
    'Fire protection on reserves':   'Infrastructure',
    'Connectivity':                  'Telecommunications',
}


def _fetch_isc_infrastructure(tavily_client=None) -> list[dict]:
    """
    Fetch Indigenous Services Canada community infrastructure projects
    (national CSV, all provinces/territories). Live-verified 2026-06-10.
    Returns list of project dicts with discovery_source='federal_registry'.
    """
    import csv as _csv
    import io as _io
    import zipfile as _zipfile

    projects = []
    try:
        resp = http_client.get(_ISC_INFRA_CSV_ZIP, timeout=90)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"  [ISC Infrastructure][TIER 1] FAILED status={status}")
            return []

        content = resp.content
        if content[:2] == b'PK':
            zf = _zipfile.ZipFile(_io.BytesIO(content))
            csv_names = [n for n in zf.namelist() if n.lower().endswith('.csv')]
            if not csv_names:
                print("  [ISC Infrastructure] zip contains no CSV")
                return []
            text = zf.read(csv_names[0]).decode('utf-8-sig', errors='replace')
        else:
            text = content.decode('utf-8-sig', errors='replace')

        seen = set()
        territory_rows, other_rows = [], []
        for row in _csv.DictReader(_io.StringIO(text)):
            if (row.get('Project Status') or '').strip() != 'Ongoing':
                continue
            category = (row.get('Infrastructure Category') or '').strip()
            if category not in _ISC_CAPITAL_CATEGORIES:
                continue
            name = (row.get('Project Name') or '').strip()
            descr = (row.get('Description') or '').strip()
            if len(name) < 6 or _ISC_SKIP_RE.search(name):
                continue
            if not _ISC_CONSTRUCTION_RE.search(f"{name} {descr}"):
                continue
            proj_no = (row.get('Internal Project Number') or '').strip()
            community = (row.get('Community') or '').strip()
            dedup_key = proj_no or f"{community}|{name}".lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            province = _isc_norm_province(row.get('Province/Territory'))
            display_name = f"{community} — {name}" if community else name
            project = {
                'name':             display_name[:200],
                'province':         province,
                'status':           'Under Construction',  # Ongoing in ISC terms
                'proponent':        community[:120],
                'source_url':       _ISC_DATASET_URL,
                'discovery_source': 'federal_registry',
                'sector':           _ISC_SECTOR_BY_CATEGORY.get(category, 'Infrastructure'),
                'description':      descr[:300],
            }
            inv = (row.get('ISC Departmental Investment') or '').strip()
            if inv and inv.lower() != 'not available':
                project['value'] = inv
            # Northern coverage first: territories get queue priority
            if province in ('Nunavut', 'Northwest Territories', 'Yukon'):
                territory_rows.append(project)
            else:
                other_rows.append(project)

        projects = (territory_rows + other_rows)[:_ISC_MAX_PROJECTS]

    except Exception as e:
        print(f"  [ISC Infrastructure] Failed: {type(e).__name__}: {e}")

    print(f"  [ISC Infrastructure] {len(projects)} projects from ISC dataset")
    return projects


# ── SEDAR+ Securities Filings ────────────────────────────────────────────────

_SEDAR_URL = "https://www.sedarplus.ca/csa-party/records/record.html?lang=en"

def _scrape_sedar(tavily_client=None) -> list[dict]:
    """
    Search SEDAR+ for NI 43-101 technical reports and material change reports
    that disclose capital projects. SEDAR+ blocks simple requests, so we use
    Tavily extraction as the primary approach.
    Returns list of project dicts with discovery_source='sedar_filings'.
    """
    projects = []
    try:
        # SEDAR+ blocks automated requests — use Tavily if available
        search_urls = [
            "https://www.sedarplus.ca/csa-party/records/record.html?lang=en",
        ]

        if tavily_client:
            for url in search_urls:
                text = _extract_with_tavily(url, tavily_client)
                if not text:
                    continue
                # Look for NI 43-101 report titles which follow standard format:
                # "Technical Report for [Project Name], [Location]"
                for line in text.split('\n'):
                    line = line.strip()
                    if len(line) < 20:
                        continue
                    ll = line.lower()
                    if any(kw in ll for kw in ('43-101', 'technical report',
                                                'feasibility', 'material change',
                                                'construction', 'mine', 'project')):
                        # Try to extract project name from report title
                        name = line[:200]
                        # Clean up common prefixes
                        for prefix in ('NI 43-101 ', 'Technical Report for ',
                                       'Technical Report on the ', 'Feasibility Study for '):
                            if name.startswith(prefix):
                                name = name[len(prefix):]

                        if len(name) > 10:
                            projects.append({
                                'name':             name[:200],
                                'province':         '',
                                'status':           'Announced',
                                'source_url':       url,
                                'discovery_source': 'sedar_filings',
                                'sector':           _infer_sector_from_name(name),
                            })
                            if len(projects) >= 30:
                                break

    except Exception as e:
        print(f"  [SEDAR+] Failed: {type(e).__name__}: {e}")

    print(f"  [SEDAR+] {len(projects)} projects from filings")
    return projects


# ── Metrolinx Project Tracker ────────────────────────────────────────────────

_METROLINX_URL = "https://www.metrolinx.com/en/projects-and-programs"

def _scrape_metrolinx(tavily_client=None) -> list[dict]:
    """
    Scrape Metrolinx project tracker page. Next.js site with embedded JSON data.
    Returns list of project dicts with discovery_source='crown_corp'.
    """
    projects = []
    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS)
        resp = http_client.get(_METROLINX_URL, timeout=25)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"  [Metrolinx][TIER 7] FAILED status={status}")
            if tavily_client:
                text = _extract_with_tavily(_METROLINX_URL, tavily_client)
                if text:
                    return _parse_text_for_projects(text, 'Ontario', 'crown_corp', _METROLINX_URL)
            return []

        html = resp.text
        soup = _soup(html)
        if not soup:
            return []

        seen = set()
        # Try to find JSON data embedded in Next.js __NEXT_DATA__ script
        for script in soup.select('script#__NEXT_DATA__'):
            import json as _json
            try:
                data = _json.loads(script.string or '')
                # Walk the JSON tree for project entries
                _extract_metrolinx_from_json(data, projects, seen)
            except (ValueError, TypeError):
                pass

        # Fallback: parse links and headings
        if not projects:
            for link in soup.select('a[href*="/projects/"], a[href*="/programs/"]'):
                name = link.get_text(strip=True)
                if not name or len(name) < 8 or name.lower() in seen:
                    continue
                if name.lower() in ('projects', 'programs', 'see all', 'learn more',
                                     'projects and programs', 'back to top'):
                    continue
                seen.add(name.lower())
                href = link.get('href', '')
                url = href if href.startswith('http') else f"https://www.metrolinx.com{href}"
                projects.append({
                    'name':             name,
                    'province':         'Ontario',
                    'status':           'Under Construction',
                    'source_url':       url,
                    'discovery_source': 'crown_corp',
                    'sector':           'Transit & Rail',
                })

    except Exception as e:
        print(f"  [Metrolinx] Failed: {type(e).__name__}: {e}")

    print(f"  [Metrolinx] {len(projects)} projects from tracker")
    return projects


def _extract_metrolinx_from_json(obj, projects, seen):
    """Recursively walk Next.js JSON data for project entries."""
    if isinstance(obj, dict):
        # Look for objects that look like project entries
        name = obj.get('title') or obj.get('name') or obj.get('heading') or ''
        href = obj.get('href') or obj.get('url') or obj.get('link') or ''
        if name and len(name) > 8 and name.lower() not in seen:
            # Skip if it's clearly not a project
            if not any(skip in name.lower() for skip in ('cookie', 'privacy', 'contact', 'menu')):
                seen.add(name.lower())
                url = href if href.startswith('http') else f"https://www.metrolinx.com{href}" if href else _METROLINX_URL
                projects.append({
                    'name':             name,
                    'province':         'Ontario',
                    'status':           'Under Construction',
                    'source_url':       url,
                    'discovery_source': 'crown_corp',
                    'sector':           'Transit & Rail',
                })
        for v in obj.values():
            _extract_metrolinx_from_json(v, projects, seen)
    elif isinstance(obj, list):
        for item in obj:
            _extract_metrolinx_from_json(item, projects, seen)


# ── Text-based project extraction helper ─────────────────────────────────────

def _parse_text_for_projects(text: str, province: str, discovery_source: str,
                              source_url: str) -> list[dict]:
    """Parse plain text (from Tavily extraction) for project-like entries."""
    projects = []
    seen = set()
    skipped_doctype = 0
    for line in text.split('\n'):
        line = line.strip()
        if len(line) < 15 or len(line) > 250:
            continue
        # Skip obvious non-project lines
        ll = line.lower()
        if any(skip in ll for skip in ('cookie', 'privacy', 'copyright', 'sign in',
                                        'login', 'menu', 'navigation', 'footer',
                                        'header', 'skip to', 'toggle')):
            continue
        # P1: skip value-less document filings (FMPs, EIS, terms of reference)
        # — this helper is shared by several scrapers, the filter is doctype-
        # based so gating here covers them all.
        if _skip_non_project_filing(line):
            skipped_doctype += 1
            continue
        sector = _infer_sector_from_name(line)
        if sector != 'Other' or any(kw in ll for kw in
                ('project', 'mine', 'pipeline', 'facility', 'plant', 'terminal',
                 'expansion', 'construction', 'development', 'assessment',
                 'highway', 'bridge', 'transit', 'station', 'dam', 'refinery')):
            if line.lower() not in seen:
                seen.add(line.lower())
                projects.append({
                    'name':             line[:200],
                    'province':         province,
                    'status':           'Under Review',
                    'source_url':       source_url,
                    'discovery_source': discovery_source,
                    'sector':           sector if sector != 'Other' else 'Infrastructure',
                })
                if len(projects) >= 30:
                    break
    if skipped_doctype:
        print(f"  [{province} EA] skipped {skipped_doctype} non-project filings")
    return projects


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_status(raw: str) -> str:
    """Map varied status strings to canonical project statuses."""
    r = (raw or '').lower()
    if any(x in r for x in ('under construction', 'construction', 'building')):
        return 'Under Construction'
    if any(x in r for x in ('complete', 'operational', 'open', 'finished')):
        return 'Completed'
    if any(x in r for x in ('approved', 'approval granted', 'permit issued')):
        return 'Approved'
    if any(x in r for x in ('cancel', 'rejected', 'refused', 'withdrawn', 'terminated')):
        return 'Cancelled'
    if any(x in r for x in ('suspend', 'paused', 'on hold', 'deferred')):
        return 'Suspended'
    return 'Announced'


def _infer_sector_from_name(name: str) -> str:
    """Guess a project sector from its name."""
    n = (name or '').lower()
    if any(x in n for x in ('oil', 'gas', 'pipeline', 'lng', 'refinery', 'petrochemical')):
        return 'Energy'
    if any(x in n for x in ('mine', 'mining', 'potash', 'lithium', 'gold', 'copper', 'nickel')):
        return 'Mining'
    if any(x in n for x in ('wind', 'solar', 'hydro', 'nuclear', 'hydrogen', 'carbon capture')):
        return 'Clean Energy'
    if any(x in n for x in ('transit', 'lrt', 'subway', 'brt', 'rapid transit', 'rail')):
        return 'Transit & Rail'
    if any(x in n for x in ('highway', 'bridge', 'road', 'interchange', 'tunnel', 'expressway')):
        return 'Infrastructure'
    if any(x in n for x in ('housing', 'residential', 'apartment', 'affordable')):
        return 'Housing'
    if any(x in n for x in ('hospital', 'health', 'medical', 'clinic', 'care')):
        return 'Healthcare'
    if any(x in n for x in ('data centre', 'data center', 'semiconductor', 'ai campus')):
        return 'Technology & Data'
    if any(x in n for x in ('port', 'terminal', 'wharf', 'container', 'logistics')):
        return 'Ports & Logistics'
    if any(x in n for x in ('school', 'university', 'college', 'campus')):
        return 'Education'
    if any(x in n for x in ('military', 'defence', 'defense', 'dnd', 'base', 'coast guard')):
        return 'Defence'
    if any(x in n for x in ('water', 'wastewater', 'sewage', 'treatment plant')):
        return 'Water & Wastewater'
    if any(x in n for x in ('telecom', 'broadband', 'fibre', 'fiber', '5g', 'wireless')):
        return 'Telecommunications'
    return 'Other'


# ── Master registry fetcher ───────────────────────────────────────────────────

def fetch_registry_projects(tavily_client=None) -> list[dict]:
    """
    Scrape all government project registries.
    Returns a flat list of project dicts. Never raises.

    Each dict has at minimum:
        name, province, status, source_url, discovery_source, sector
    Optional: value, proponent

    Args:
        tavily_client: Optional Tavily client for fallback extraction.
    """
    print("\n[STEP 2b] Scraping government project registries...")
    all_projects: list[dict] = []

    scrapers = [
        ("IAAC",                  _scrape_iaac),
        ("BC EAO",                _scrape_bc_eao),
        ("Infrastructure Canada", _scrape_infrastructure_canada),
        ("BuyAndSell",            _scrape_buyandsell),
        ("NRCan",                 _scrape_nrcan),
        ("CER",                   _scrape_cer),
        ("Ontario ERO",           _scrape_ontario_ero),
        ("CIB",                   _scrape_cib),
        # STEP 2G: Provincial EA registries
        ("QC BAPE",               _scrape_quebec_bape),
        ("AB EA",                 _scrape_alberta_ea),
        ("SK EA",                 _scrape_saskatchewan_ea),
        ("MB EA",                 _scrape_manitoba_ea),
        ("NS EA",                 _scrape_nova_scotia_ea),
        ("NB EIA",                _scrape_nb_ea),
        ("NL EA",                 _scrape_nl_ea),
        ("YESAB",                 _scrape_yukon_yesab),
        ("MVRB",                  _scrape_nwt_mvrb),
        # quality-pass-1.4 G3: Northern & Indigenous coverage (live-verified 2026-06-10)
        ("NIRB",                  _scrape_nunavut_nirb),
        ("MVLWB",                 _scrape_nwt_mvlwb),
        ("ISC Infrastructure",    _fetch_isc_infrastructure),
        # STEP 2G: Structured databases
        # SEDAR+ disabled — scraper targets login portal, returns 0 results. Needs endpoint audit.
        # ("SEDAR+",                _scrape_sedar),
        ("Metrolinx",             _scrape_metrolinx),
    ]

    # patch-1.2: track per-source counts so a dead source is distinguishable
    # from a quiet week, and so the tier-level DEGRADE line is accurate.
    per_source: dict[str, int] = {}
    for label, fn in scrapers:
        try:
            results = fn(tavily_client=tavily_client)
            per_source[label] = len(results)
            all_projects.extend(results)
        except Exception as e:
            per_source[label] = 0
            print(f"  [{label}][TIER 1] FAILED status=exception {type(e).__name__}: {e}",
                  file=sys.stderr)
        time.sleep(1)

    all_projects = [p for p in all_projects if p.get('name') and len(p['name']) > 5]

    # patch-1.2: min-yield DEGRADE logging. A whole-tier zero means a dead source,
    # not a quiet week. Also surface any individual source that produced zero.
    zero_sources = [lbl for lbl, n in per_source.items() if n == 0]
    if zero_sources:
        print(f"  [Registries] Sources returning 0 this run: {', '.join(zero_sources)}")
    if not all_projects:
        print("  [TIER 1 DEGRADED] 0 items — all government registries returned zero")

    # Record documents for fetch tracking
    try:
        from db import get_db, insert_document
        conn = get_db()
        for proj in all_projects:
            src_url = proj.get('source_url', '')
            if src_url:
                insert_document(conn, src_url,
                                title=proj.get('name', ''),
                                source_tier='tier_1',
                                source_type=proj.get('discovery_source', 'federal_registry'))
        conn.close()
    except Exception:
        pass

    print(f"  [Registries] Total: {len(all_projects)} projects across all sources")
    return all_projects
