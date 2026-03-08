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
import requests
from datetime import date

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False
    print("[gov_sources] beautifulsoup4 not installed — HTML parsing will be limited")

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
    try:
        resp = requests.get(
            _STATCAN_IND_URL, timeout=20,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; EconF/1.0)'}
        )
        resp.raise_for_status()
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
                f"https://www150.statcan.gc.ca/t1/tbl1/en/table/0{source}-eng"
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


def save_statcan_indicators(db, indicators: list[dict]) -> None:
    """
    Write StatCan indicators snapshot to Firestore statcan_indicators/latest.
    Overwrites on each run. Skips write if indicators list is empty (preserves cached data).
    Never raises.
    """
    if not indicators:
        print("  [StatCan] No fresh indicators — skipping Firestore write (cached data preserved).")
        return
    try:
        db.collection('statcan_indicators').document('latest').set({
            'updatedAt':  date.today().isoformat(),
            'indicators': indicators,
        })
        print(f"  [StatCan] Saved {len(indicators)} indicators to Firestore.")
    except Exception as e:
        print(f"  [StatCan] Firestore write failed (non-critical): {e}")


# ── Government Registry Scrapers ──────────────────────────────────────────────

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0; +https://econf.ca)',
    'Accept':     'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def _get_html(url: str, timeout: int = 20) -> str | None:
    """Fetch HTML from URL. Returns None on failure."""
    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  [Registry] GET {url[:60]} failed: {e}", file=sys.stderr)
        return None


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

_IAAC_URL = "https://iaac-aeic.gc.ca/050/evaluations"

def _scrape_iaac(tavily_client=None) -> list[dict]:
    """
    Scrape IAAC project registry for active and recently decided assessments.
    Returns list of project dicts with discovery_source='iaac_registry'.
    """
    html = _get_html(_IAAC_URL)
    if not html:
        return []

    projects = []
    try:
        soup = _soup(html)
        if not soup:
            return []

        rows = soup.select('table tbody tr') or soup.select('.project-item') or []

        for row in rows[:50]:
            cells = row.find_all('td') if row.name == 'tr' else [row]
            if not cells:
                continue

            name_el = (row.find('a') or (cells[0] if cells else None))
            name = name_el.get_text(strip=True) if name_el else ''
            if not name or len(name) < 5:
                continue

            url = ''
            if name_el and name_el.name == 'a':
                href = name_el.get('href', '')
                url = href if href.startswith('http') else f"https://iaac-aeic.gc.ca{href}"

            province = ''
            if len(cells) > 2:
                province = cells[2].get_text(strip=True)

            status_text = ''
            if len(cells) > 3:
                status_text = cells[3].get_text(strip=True)

            status = 'Under Review'
            sl = status_text.lower()
            if 'decision' in sl or 'approved' in sl or 'designated' in sl:
                status = 'Approved'
            elif 'withdrawn' in sl or 'terminated' in sl:
                status = 'Cancelled'
            elif 'under construction' in sl or 'operational' in sl:
                status = 'Under Construction'

            projects.append({
                'name':             name,
                'province':         province,
                'status':           status,
                'source_url':       url,
                'discovery_source': 'iaac_registry',
                'sector':           _infer_sector_from_name(name),
            })

    except Exception as e:
        print(f"  [IAAC] Parse error: {e}", file=sys.stderr)

    print(f"  [IAAC] {len(projects)} projects from registry")
    return projects


# ── BC Environmental Assessment Office ───────────────────────────────────────

_BC_EAO_API = "https://www.projects.eao.gov.bc.ca/api/v2/projects?&fields=name,eacDecision,status,proponent&pageSize=50"

def _scrape_bc_eao(tavily_client=None) -> list[dict]:
    """
    Fetch BC EAO project list via their public JSON API.
    Returns list of project dicts with discovery_source='provincial_ea'.
    """
    try:
        resp = requests.get(_BC_EAO_API, timeout=20, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        rows = data if isinstance(data, list) else data.get('data', data.get('projects', []))

        projects = []
        for p in rows[:50]:
            name = p.get('name') or ''
            if not name:
                continue
            eac = (p.get('eacDecision') or {}).get('decisionLabel') or ''
            status = 'Under Review'
            el = eac.lower()
            if 'approved' in el or 'issued' in el:
                status = 'Approved'
            elif 'refused' in el or 'rejected' in el:
                status = 'Cancelled'

            proponent = (p.get('proponent') or {}).get('name') or ''
            pid = p.get('_id') or p.get('id') or ''
            url = f"https://projects.eao.gov.bc.ca/project/{pid}" if pid else ''

            projects.append({
                'name':             name,
                'province':         'British Columbia',
                'status':           status,
                'proponent':        proponent,
                'source_url':       url,
                'discovery_source': 'provincial_ea',
                'sector':           _infer_sector_from_name(name),
            })

        print(f"  [BC EAO] {len(projects)} projects from registry")
        return projects

    except Exception as e:
        print(f"  [BC EAO] Failed: {e}", file=sys.stderr)
        return []


# ── Infrastructure Canada ─────────────────────────────────────────────────────

_INFRA_CANADA_PAGE = "https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html"
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
        resp = requests.get(_INFRA_CANADA_API, timeout=30, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

        # The JSON may be a list of records or a dict with a key
        if isinstance(data, dict):
            records = (data.get('data') or data.get('records')
                       or data.get('projects') or list(data.values())[0]
                       if data else [])
        else:
            records = data  # top-level list

        if not isinstance(records, list):
            records = []

        projects = []
        for row in records[:150]:
            if not isinstance(row, dict):
                continue
            # Try various field name conventions (bilingual JSON may use either)
            name = (row.get('Project_Name_EN') or row.get('Project_Name')
                    or row.get('project_name_en') or row.get('project_name') or '')
            if not name or len(name) < 5:
                continue

            province  = (row.get('Province_Territory_EN') or row.get('Province_Territory')
                         or row.get('province') or '')
            value_str = str(row.get('Federal_Contribution') or row.get('FederalContribution')
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
        print(f"  [Infrastructure Canada] Failed: {e}", file=sys.stderr)
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
        resp = requests.get(_CANADABUYS_CSV, timeout=60, headers=_HEADERS, stream=True)
        resp.raise_for_status()

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
        print(f"  [BuyAndSell] Failed: {e}", file=sys.stderr)
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
    ]

    for label, fn in scrapers:
        try:
            results = fn(tavily_client=tavily_client)
            all_projects.extend(results)
        except Exception as e:
            print(f"  [{label}] Scraper error: {e}", file=sys.stderr)
        time.sleep(1)

    all_projects = [p for p in all_projects if p.get('name') and len(p['name']) > 5]

    print(f"  [Registries] Total: {len(all_projects)} projects across all sources")
    return all_projects
