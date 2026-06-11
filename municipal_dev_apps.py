"""
municipal_dev_apps.py — Municipal development application scrapers.

Tier 13 in the CAN-MACRO discovery pipeline.

Development applications are the earliest project signal — months/years before
groundbreaking or media coverage. Scrapes top CMAs by GDP via Open Data APIs
(Socrata/CKAN) and HTML portals, filtering by province-specific value thresholds.

Priority order:
  1. Open Data APIs (Vancouver, Calgary, Edmonton, Winnipeg) — structured JSON/CSV
  2. HTML portals (Toronto, Ottawa, Halifax, etc.) — BeautifulSoup parsing
"""

import asyncio
import logging
import re
import ssl
from datetime import datetime, date

import aiohttp

# patch-1.2 (D-8): reuse the shared browser-like header set so the async
# municipal scrapers stop getting bot-blocked (HTTP 403) on the default
# aiohttp User-Agent, and verify TLS against certifi's CA bundle (fixes
# CERTIFICATE_VERIFY_FAILED on Windows OpenSSL stores).
import http_client

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CONTEXT = None

logger = logging.getLogger(__name__)

# Browser-like headers shared with http_client (single source of truth for UA).
_BROWSER_HEADERS = dict(http_client.DEFAULT_HEADERS)

# GDP-proportional thresholds (millions CAD) for filtering permits
GDP_THRESHOLDS = {
    'ON': 500, 'QC': 250, 'AB': 200, 'BC': 175, 'SK': 45, 'MB': 40,
    'NS': 25, 'NB': 20, 'NL': 17, 'PE': 5, 'YT': 3, 'NT': 3, 'NU': 3,
}

# Live-verified 2026-06-09 (D-8): every city probed; moved pages re-resolved
# (see per-entry comments). Kitchener now uses its ArcGIS FeatureServer layer
# (the old CSV-download item id was retired). London/Victoria machine endpoints
# exist (maps.london.ca Planning_Application_Sites; maps.victoria.ca
# OpenData_PlanningAndDevelopment layer 18) but carry NO dollar-value fields,
# so they cannot pass the value gate — their HTML viewer pages are kept as the
# listed source instead. Hamilton/St. Catharines ArcGIS layers likewise lack
# value fields. Kelowna remains bot-blocked (403) to non-browser clients.
MUNICIPAL_SOURCES = {
    # ── Open Data API cities ─────────────────────────────────────────────────
    "vancouver": {
        "name": "Vancouver Building Permits",
        "province": "BC",
        "cma": "Vancouver",
        "url": "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/issued-building-permits/records",
        "approach": "ckan_v2",
        "params": {
            "limit": 100,
            # 2026-06-11: dataset dropped issueyear/issuemonth (HTTP 400
            # "Unknown field: issuemonth"); order on issuedate directly.
            "order_by": "issuedate DESC",
            "where": "projectvalue > 175000000",
        },
        "field_map": {
            "name": "projectdescription",
            "value": "projectvalue",
            "address": "address",
            "type": "typeofwork",
            "date": "issuedate",
        },
    },
    "calgary": {
        "name": "Calgary Building Permits",
        "province": "AB",
        "cma": "Calgary",
        # 2026-06-11: 6933-unw5 (development permits) no longer carries any
        # cost column (HTTP 400 "No such column: estimatedprojectcost") and
        # never will — switched to the Building Permits dataset c2es-76ed,
        # which has estprojectcost. Ordered by applieddate (always populated;
        # issueddate is NULL for pending permits and Socrata sorts NULLs
        # first on DESC, which would bury recent rows).
        "url": "https://data.calgary.ca/resource/c2es-76ed.json",
        "approach": "socrata",
        "params": {
            "$limit": 100,
            "$order": "applieddate DESC",
            "$where": "estprojectcost > 200000000",
        },
        "field_map": {
            "name": "description",
            # description is blank on some large pending permits — fall back
            # to the permit class (e.g. "3510 - Recreation Facility").
            "name_alt": "permitclass",
            "value": "estprojectcost",
            "address": "originaladdress",
            "type": "workclassgroup",
            "date": "applieddate",
        },
    },
    "edmonton": {
        "name": "Edmonton Building Permits",
        "province": "AB",
        "cma": "Edmonton",
        "url": "https://data.edmonton.ca/resource/24uj-dj8v.json",
        "approach": "socrata",
        "params": {
            "$limit": 100,
            "$order": "issue_date DESC",
            # 2026-06-11: job_value renamed to construction_value (HTTP 400
            # "No such column: job_value"); the column is text-typed now, so
            # cast to number — a raw text compare would silently drop 10-digit
            # ($1B+) values.
            "$where": "construction_value::number > 200000000",
        },
        "field_map": {
            "name": "job_description",
            "value": "construction_value",
            "address": "address",
            "type": "permit_type",
            "date": "issue_date",
        },
    },
    "winnipeg": {
        "name": "Winnipeg Building Permits",
        "province": "MB",
        "cma": "Winnipeg",
        # 2026-06-11: m4wt-mqkb was rebuilt as a ward/neighbourhood/year
        # AGGREGATE (HTTP 400 "No such column: total_project_value") — no
        # per-permit rows. Switched to it4w-cpf4 (Detailed Building Permit
        # Data, updated weekly). NO Winnipeg permit-level dataset carries a
        # dollar column anymore, so the value gate cannot apply; instead the
        # $where pre-filters on the city's own major_project = 'Yes' flag
        # (Winnipeg's significance designation) and no_value_field admits
        # the records with value "Not disclosed".
        "url": "https://data.winnipeg.ca/resource/it4w-cpf4.json",
        "approach": "socrata",
        "no_value_field": True,
        "params": {
            "$limit": 100,
            "$order": "issue_date DESC",
            "$where": "major_project = 'Yes'",
        },
        "field_map": {
            "name": "permit_type",
            "name_alt": "work_type",
            "value": "",
            "address": "address",
            "type": "work_type",
            "date": "issue_date",
        },
    },
    # ── HTML portal cities (scraped with BeautifulSoup) ──────────────────────
    "toronto": {
        "name": "Toronto Application Information Centre",
        "province": "ON",
        "cma": "Toronto",
        "url": "https://www.toronto.ca/city-government/planning-development/application-information-centre/",
        "approach": "html_scrape",
    },
    "ottawa": {
        "name": "Ottawa Development Applications",
        "province": "ON",
        "cma": "Ottawa-Gatineau",
        "url": "https://devapps.ottawa.ca/en/",
        "approach": "html_scrape",
    },
    "montreal": {
        "name": "Montreal OCPM Consultations",
        "province": "QC",
        "cma": "Montreal",
        "url": "https://ocpm.qc.ca/fr/consultations-publiques",
        "approach": "html_scrape",
    },
    "hamilton": {
        "name": "Hamilton Planning Applications",
        "province": "ON",
        "cma": "Hamilton",
        # 2026-06-09: /develop-property/ section renamed /build-invest-grow/
        "url": "https://www.hamilton.ca/build-invest-grow/planning-development/planning-applications",
        "approach": "html_scrape",
    },
    "halifax": {
        "name": "Halifax Development Activity",
        "province": "NS",
        "cma": "Halifax",
        "url": "https://www.halifax.ca/business/planning-development/applications",
        "approach": "html_scrape",
    },
    "quebec_city": {
        "name": "Ville de Québec Permits",
        "province": "QC",
        "cma": "Quebec City",
        # 2026-06-09: /citoyens/permis/ 404s; current page is reglements_permis.
        # A weekly CKAN permits CSV exists on donneesquebec.ca (vdq-permis.csv)
        # but has no value column, so it cannot pass the value gate.
        "url": "https://www.ville.quebec.qc.ca/citoyens/reglements_permis/index.aspx",
        "approach": "html_scrape",
    },
    "saskatoon": {
        "name": "Saskatoon Development Permits",
        "province": "SK",
        "cma": "Saskatoon",
        # 2026-06-09: planning section restructured under development-regulation
        "url": "https://www.saskatoon.ca/business-development/development-regulation/developers-homebuilders/land-use-applications",
        "approach": "html_scrape",
    },
    "regina": {
        "name": "Regina Building Permits",
        "province": "SK",
        "cma": "Regina",
        # 2026-06-09: permits page moved under land-property-development/planning
        "url": "https://www.regina.ca/business-development/land-property-development/planning/proposed-development/",
        "approach": "html_scrape",
    },
    "st_johns": {
        "name": "St. John's Development Applications",
        "province": "NL",
        "cma": "St. John's",
        # 2026-06-09: site dropped /en/ + .aspx; new business-development path
        "url": "https://www.stjohns.ca/business-development/planning-and-development/development-planning-applications/",
        "approach": "html_scrape",
    },
    "fredericton": {
        "name": "Fredericton Development Permits",
        "province": "NB",
        "cma": "Fredericton",
        # 2026-06-09: moved under business-development/planning-development
        "url": "https://www.fredericton.ca/en/business-development/planning-development/development-applications",
        "approach": "html_scrape",
    },
    "charlottetown": {
        "name": "Charlottetown Building Permits",
        "province": "PE",
        "cma": "Charlottetown",
        # 2026-06-09: department page retired; weekly permit-approval summaries
        "url": "https://www.charlottetown.ca/resident_services/permits_applications/building_permit_approvals",
        "approach": "html_scrape",
    },
    # ── Phase 7 CMA additions ─────────────────────────────────────────────
    "kitchener": {
        "name": "Kitchener Building Permits",
        "province": "ON",
        "cma": "Kitchener-Cambridge-Waterloo",
        # 2026-06-09: old open-data CSV item retired (HTTP 400); current source
        # is the Building_Permits FeatureServer (updated daily, carries
        # CONSTRUCTION_VALUE). where-clause pre-filters at the ON threshold.
        "url": "https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Building_Permits/FeatureServer/0/query",
        "approach": "arcgis",
        "params": {
            "where": "CONSTRUCTION_VALUE > 500000000",
            "outFields": "PERMIT_DESCRIPTION,CONSTRUCTION_VALUE,FOLDERNAME,WORK_TYPE,ISSUE_DATE,PERMIT_STATUS",
            "orderByFields": "ISSUE_DATE DESC",
            "resultRecordCount": 100,
            "f": "json",
        },
        "field_map": {
            "name": "PERMIT_DESCRIPTION",
            "value": "CONSTRUCTION_VALUE",
            "address": "FOLDERNAME",
            "type": "WORK_TYPE",
            "date": "ISSUE_DATE",
        },
    },
    "london_on": {
        "name": "London ON Building Permits",
        "province": "ON",
        "cma": "London",
        "url": "https://opendata.london.ca/datasets/building-permits/explore",
        "approach": "html_scrape",
    },
    "oshawa": {
        "name": "Oshawa Planning Applications",
        "province": "ON",
        "cma": "Oshawa",
        # 2026-06-09: site dropped /en/ + .aspx
        "url": "https://www.oshawa.ca/business-development/planning-and-development/development-applications/",
        "approach": "html_scrape",
    },
    "st_catharines": {
        "name": "St. Catharines Development Applications",
        "province": "ON",
        "cma": "St. Catharines-Niagara",
        # 2026-06-09: /build-and-renovate/ renamed /planning-and-development/
        "url": "https://www.stcatharines.ca/en/planning-and-development/development-applications.aspx",
        "approach": "html_scrape",
    },
    "victoria": {
        "name": "Victoria Development Tracker",
        "province": "BC",
        "cma": "Victoria",
        "url": "https://opendata.victoria.ca/datasets/development-tracker/explore",
        "approach": "html_scrape",
    },
    "moncton": {
        "name": "Moncton Building Permits",
        "province": "NB",
        "cma": "Moncton",
        "url": "https://www.moncton.ca/building-permits",
        "approach": "html_scrape",
    },
    "kelowna": {
        "name": "Kelowna Development Applications",
        "province": "BC",
        "cma": "Kelowna",
        # 2026-06-09: page moved under property-development; host still
        # bot-blocks non-browser clients (403) — kept for when the WAF relaxes
        "url": "https://www.kelowna.ca/homes-building/property-development/current-development-applications",
        "approach": "html_scrape",
    },
    "barrie": {
        "name": "Barrie Development Applications",
        "province": "ON",
        "cma": "Barrie",
        # 2026-06-09: renamed to proposed-developments under a new section
        "url": "https://www.barrie.ca/planning-building-infrastructure/development/proposed-developments",
        "approach": "html_scrape",
    },
    "guelph": {
        "name": "Guelph Development Applications",
        "province": "ON",
        "cma": "Guelph",
        "url": "https://guelph.ca/city-hall/planning-and-development/community-plans-studies/development-applications/",
        "approach": "html_scrape",
    },
    "abbotsford": {
        "name": "Abbotsford Development Applications",
        "province": "BC",
        "cma": "Abbotsford-Mission",
        # 2026-06-09: renamed to instream-development-applications
        "url": "https://www.abbotsford.ca/business-development/development-planning/instream-development-applications",
        "approach": "html_scrape",
    },
}

# Dollar regex for extracting values from HTML descriptions
_DOLLAR_RE = re.compile(
    r'\$\s*([\d,.]+)\s*(million|billion|m\b|b\b)',
    re.IGNORECASE,
)


def _parse_dollar_value(text: str) -> float | None:
    """Extract dollar value in millions from text. Returns None if not found."""
    if not text:
        return None
    # Try numeric first (from API — already in dollars)
    try:
        val = float(str(text).replace(',', '').replace('$', ''))
        if val > 10_000:  # Assume raw dollars, convert to millions
            return val / 1_000_000
        return val  # Already in millions
    except (ValueError, TypeError):
        pass
    # Try text pattern
    m = _DOLLAR_RE.search(str(text))
    if m:
        num = float(m.group(1).replace(',', ''))
        unit = m.group(2).lower()
        if unit.startswith('b'):
            return num * 1000
        return num
    return None


def _build_project(raw: dict, source: dict, field_map: dict) -> dict | None:
    """Convert a raw API record into a standardized project dict."""
    name_field = field_map.get("name", "")
    name = str(raw.get(name_field, "") or "").strip()
    if not name:
        # 2026-06-11: optional fallback field — e.g. Calgary leaves
        # description blank on some large pending permits (permitclass used
        # instead); Winnipeg detail rows have no description at all.
        alt_field = field_map.get("name_alt", "")
        name = str(raw.get(alt_field, "") or "").strip() if alt_field else ""
    if not name:
        return None

    value_raw = raw.get(field_map.get("value", ""), "")
    value_millions = _parse_dollar_value(value_raw)
    address = str(raw.get(field_map.get("address", ""), "")).strip()
    permit_type = str(raw.get(field_map.get("type", ""), "")).strip()
    date_str = str(raw.get(field_map.get("date", ""), "")).strip()

    # Build display name from address + description
    display_name = name[:120]
    if address and address.lower() not in name.lower():
        display_name = f"{address} — {name[:80]}"

    return {
        "name": display_name,
        "province": source["province"],
        "cma": source.get("cma", ""),
        "sector": "Other",
        "naics_code": "",
        "tags": [],
        "value": f"${value_millions:.0f}M" if value_millions else "Not disclosed",
        "value_millions": value_millions,
        "status": "Proposed",
        "description": f"{permit_type}: {name}" if permit_type else name,
        "discovery_source": "municipal_dev_app",
        "source_url": source.get("url", ""),
        "source_title": source["name"],
        "sources": [{"id": 1, "title": source["name"], "url": source.get("url", "")}],
        "announced": date_str[:10] if date_str else date.today().isoformat(),
        "completionDate": "",
        "_discovery_tier": "municipal_dev_app",
        "_source_type": "government",
        "confidence": 0.7,
        "_evidence": [{
            "url": source.get("url", ""),
            "name": source["name"],
            "source_type": "municipal_permit",
            "authority": "government",
        }],
    }


async def _fetch_socrata(session: aiohttp.ClientSession, source: dict,
                         threshold_millions: float) -> tuple[list[dict], str | None]:
    """Fetch permits from a Socrata Open Data API.

    Returns (projects, failure_reason). failure_reason is None on success.
    """
    params = dict(source.get("params", {}))
    field_map = source.get("field_map", {})

    try:
        async with session.get(
            source["url"], params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  [TIER 13][{source['name']}] FAILED status={resp.status} (socrata)")
                return [], str(resp.status)
            records = await resp.json()
    except Exception as e:
        logger.warning(f"  [TIER 13][{source['name']}] FAILED status=exception (socrata) {type(e).__name__}: {e}")
        return [], type(e).__name__

    # 2026-06-11: datasets with no dollar column (Winnipeg it4w-cpf4) set
    # no_value_field — the $where clause already pre-filters significance
    # (e.g. the city's major_project flag), so the value gate is skipped.
    skip_value_gate = bool(source.get("no_value_field"))

    projects = []
    for rec in records:
        proj = _build_project(rec, source, field_map)
        if proj and (skip_value_gate
                     or (proj.get("value_millions") or 0) >= threshold_millions):
            projects.append(proj)
    return projects, None


async def _fetch_ckan(session: aiohttp.ClientSession, source: dict,
                      threshold_millions: float) -> tuple[list[dict], str | None]:
    """Fetch permits from an Opendatasoft explore v2.1 API (e.g. Vancouver).

    Query params are explore-v2.1 style: where / order_by / limit
    (NOT the legacy q/rows search syntax).
    Returns (projects, failure_reason). failure_reason is None on success.
    """
    params = dict(source.get("params", {}))
    field_map = source.get("field_map", {})

    try:
        async with session.get(
            source["url"], params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  [TIER 13][{source['name']}] FAILED status={resp.status} (ckan)")
                return [], str(resp.status)
            data = await resp.json()
    except Exception as e:
        logger.warning(f"  [TIER 13][{source['name']}] FAILED status=exception (ckan) {type(e).__name__}: {e}")
        return [], type(e).__name__

    # Opendatasoft explore v2.1 wraps results in "results" key
    records = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        records = []

    projects = []
    for rec in records:
        proj = _build_project(rec, source, field_map)
        if proj and (proj.get("value_millions") or 0) >= threshold_millions:
            projects.append(proj)
    return projects, None


async def _fetch_arcgis(session: aiohttp.ClientSession, source: dict,
                        threshold_millions: float) -> tuple[list[dict], str | None]:
    """Fetch permits from an ArcGIS REST FeatureServer/MapServer query endpoint.

    Response shape: {"features": [{"attributes": {...}}, ...]} — the attributes
    dicts feed _build_project exactly like Socrata records. Added 2026-06-09
    when Kitchener's open-data CSV download item was retired in favour of a
    FeatureServer layer carrying CONSTRUCTION_VALUE.

    Returns (projects, failure_reason). failure_reason is None on success.
    """
    params = dict(source.get("params", {}))
    params.setdefault("f", "json")
    field_map = source.get("field_map", {})

    try:
        async with session.get(
            source["url"], params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  [TIER 13][{source['name']}] FAILED status={resp.status} (arcgis)")
                return [], str(resp.status)
            data = await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"  [TIER 13][{source['name']}] FAILED status=exception (arcgis) {type(e).__name__}: {e}")
        return [], type(e).__name__

    if isinstance(data, dict) and data.get("error"):
        logger.warning(f"  [TIER 13][{source['name']}] FAILED (arcgis) {str(data['error'])[:120]}")
        return [], "arcgis_error"

    projects = []
    for feat in (data.get("features", []) if isinstance(data, dict) else []):
        rec = feat.get("attributes", {})
        proj = _build_project(rec, source, field_map)
        if proj and (proj.get("value_millions") or 0) >= threshold_millions:
            projects.append(proj)
    return projects, None


async def _scrape_html_portal(session: aiohttp.ClientSession, source: dict,
                              threshold_millions: float) -> tuple[list[dict], str | None]:
    """Scrape an HTML development application portal.

    HTML portals are highly varied in structure. This fetches the listing page
    and attempts to extract project entries. For cities where the structure is
    unknown, returns empty and logs a notice.

    Returns (projects, failure_reason). failure_reason is None on success.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.info(f"  {source['name']}: BeautifulSoup not installed, skipping HTML scrape")
        return [], "no_bs4"

    try:
        # patch-1.2: rely on the session's shared browser headers (set in
        # scrape_municipal_applications) instead of the old thin UA that got
        # 403-blocked.
        async with session.get(
            source["url"],
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  [TIER 13][{source['name']}] FAILED status={resp.status}")
                return [], str(resp.status)
            html = await resp.text()
    except Exception as e:
        logger.warning(f"  [TIER 13][{source['name']}] FAILED status=exception {type(e).__name__}: {e}")
        return [], type(e).__name__

    soup = BeautifulSoup(html, "html.parser")
    projects = []

    # Generic extraction: look for tables or lists with dollar values
    # Each city's structure differs, so we use a best-effort approach
    for tag in soup.find_all(["tr", "li", "div", "article"]):
        text = tag.get_text(separator=" ", strip=True)
        if not text or len(text) < 20:
            continue

        value = _parse_dollar_value(text)
        if value and value >= threshold_millions:
            # Extract a link if available
            link = tag.find("a", href=True)
            url = link["href"] if link else source["url"]
            if url.startswith("/"):
                # Make relative URLs absolute
                from urllib.parse import urljoin
                url = urljoin(source["url"], url)

            title = link.get_text(strip=True) if link else text[:100]

            projects.append({
                "name": title,
                "province": source["province"],
                "cma": source.get("cma", ""),
                "sector": "Other",
                "naics_code": "",
                "tags": [],
                "value": f"${value:.0f}M",
                "value_millions": value,
                "status": "Proposed",
                "description": text[:200],
                "discovery_source": "municipal_dev_app",
                "source_url": url,
                "source_title": source["name"],
                "sources": [{"id": 1, "title": source["name"], "url": url}],
                "announced": date.today().isoformat(),
                "completionDate": "",
                "_discovery_tier": "municipal_dev_app",
                "_source_type": "government",
                "confidence": 0.6,
                "_evidence": [{
                    "url": url,
                    "name": source["name"],
                    "source_type": "municipal_permit",
                    "authority": "government",
                }],
            })

    return projects, None


async def _health_check(session: aiohttp.ClientSession, url: str) -> bool:
    """HEAD request with 5-second timeout to verify endpoint is reachable."""
    try:
        # patch-1.2: use session browser headers (set on the ClientSession).
        async with session.head(
            url,
            timeout=aiohttp.ClientTimeout(total=5),
            allow_redirects=True,
        ) as resp:
            return resp.status < 500
    except Exception:
        return False


async def scrape_municipal_applications() -> list[dict]:
    """Scrape municipal development portals for major projects.

    Returns list of project dicts ready for dedup and Firestore upsert.
    """
    all_projects = []
    cities_skipped = 0
    cities_total = len(MUNICIPAL_SOURCES)
    # 2026-06-11: per-city outcome aggregation — successes as "City N",
    # failures as "City(reason)" — printed as ONE line at the end of the tier
    # run so dead cities are visible at a glance in the pipeline output.
    city_counts: dict[str, int] = {}
    city_failures: dict[str, str] = {}

    # patch-1.2: browser headers on the session (clears 403 bot-blocks) +
    # certifi-backed TLS via a connector (clears CERTIFICATE_VERIFY_FAILED).
    connector = aiohttp.TCPConnector(ssl=_SSL_CONTEXT) if _SSL_CONTEXT else None
    async with aiohttp.ClientSession(headers=_BROWSER_HEADERS,
                                     connector=connector) as session:
        for city_key, source in MUNICIPAL_SOURCES.items():
            city_label = city_key.replace("_", " ").title()
            try:
                # Health check: verify endpoint is reachable before full scrape
                if not await _health_check(session, source["url"]):
                    logger.warning(f"  [Municipal] {city_key} skipped — endpoint unreachable")
                    cities_skipped += 1
                    city_failures[city_label] = "unreachable"
                    continue

                prov = source["province"]
                threshold = GDP_THRESHOLDS.get(prov, 40)
                approach = source.get("approach", "html_scrape")

                if approach == "socrata":
                    projects, failure = await _fetch_socrata(session, source, threshold)
                elif approach in ("ckan_v2", "ckan"):
                    projects, failure = await _fetch_ckan(session, source, threshold)
                elif approach == "arcgis":
                    projects, failure = await _fetch_arcgis(session, source, threshold)
                else:
                    projects, failure = await _scrape_html_portal(session, source, threshold)

                if failure is not None:
                    city_failures[city_label] = failure
                    continue

                all_projects.extend(projects)
                city_counts[city_label] = len(projects)
                logger.info(f"  {city_key}: {len(projects)} projects above ${threshold}M")

            except Exception as e:
                logger.warning(f"  {city_key} failed: {e}")
                cities_skipped += 1
                city_failures[city_label] = type(e).__name__

    if cities_skipped == cities_total:
        logger.warning("[Municipal] All cities failed health check — tier skipped entirely")
    else:
        logger.info(f"Municipal scraping complete: {len(all_projects)} total projects "
                     f"({cities_skipped}/{cities_total} cities skipped)")
    # 2026-06-11: one-line per-city scoreboard (successes + failures) so a
    # dead city is visible without scrolling through individual error lines.
    results_part = ", ".join(f"{c} {n}" for c, n in city_counts.items()) or "none"
    failed_part = ", ".join(f"{c}({r})" for c, r in city_failures.items()) or "none"
    print(f"[TIER 13] city results: {results_part} | FAILED: {failed_part}")
    # patch-1.2: min-yield DEGRADE log so a dead tier is distinguishable from a
    # quiet week (0 items != green run). Printed (not just logged) so it surfaces
    # in the pipeline run output alongside the other tiers.
    if not all_projects:
        print("[TIER 13 DEGRADED] 0 items — no municipal development applications returned")
    return all_projects


def scrape_municipal_applications_sync() -> list[dict]:
    """Synchronous wrapper for use in update_dashboard.py pipeline."""
    return asyncio.run(scrape_municipal_applications())
