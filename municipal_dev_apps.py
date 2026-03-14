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
from datetime import datetime, date

import aiohttp

logger = logging.getLogger(__name__)

# GDP-proportional thresholds (millions CAD) for filtering permits
GDP_THRESHOLDS = {
    'ON': 500, 'QC': 250, 'AB': 200, 'BC': 175, 'SK': 45, 'MB': 40,
    'NS': 25, 'NB': 20, 'NL': 17, 'PE': 5, 'YT': 3, 'NT': 3, 'NU': 3,
}

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
            "order_by": "issueyear DESC, issuemonth DESC",
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
        "name": "Calgary Development Permits",
        "province": "AB",
        "cma": "Calgary",
        "url": "https://data.calgary.ca/resource/6933-unw5.json",
        "approach": "socrata",
        "params": {
            "$limit": 100,
            "$order": "issueddate DESC",
            "$where": "estimatedprojectcost > 200000000",
        },
        "field_map": {
            "name": "description",
            "value": "estimatedprojectcost",
            "address": "communityname",
            "type": "workclassgroup",
            "date": "issueddate",
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
            "$where": "job_value > 200000000",
        },
        "field_map": {
            "name": "job_description",
            "value": "job_value",
            "address": "address",
            "type": "permit_type",
            "date": "issue_date",
        },
    },
    "winnipeg": {
        "name": "Winnipeg Building Permits",
        "province": "MB",
        "cma": "Winnipeg",
        "url": "https://data.winnipeg.ca/resource/m4wt-mqkb.json",
        "approach": "socrata",
        "params": {
            "$limit": 100,
            "$order": "issue_date DESC",
            "$where": "total_project_value > 40000000",
        },
        "field_map": {
            "name": "work_description",
            "value": "total_project_value",
            "address": "address",
            "type": "permit_type",
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
        "url": "https://www.hamilton.ca/develop-property/planning-applications",
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
        "url": "https://www.ville.quebec.qc.ca/citoyens/permis/",
        "approach": "html_scrape",
    },
    "saskatoon": {
        "name": "Saskatoon Development Permits",
        "province": "SK",
        "cma": "Saskatoon",
        "url": "https://www.saskatoon.ca/business-development/planning/development-permits",
        "approach": "html_scrape",
    },
    "regina": {
        "name": "Regina Building Permits",
        "province": "SK",
        "cma": "Regina",
        "url": "https://www.regina.ca/business-development/building-property-maintenance/building-permits/",
        "approach": "html_scrape",
    },
    "st_johns": {
        "name": "St. John's Development Applications",
        "province": "NL",
        "cma": "St. John's",
        "url": "https://www.stjohns.ca/en/business-investment/development-applications.aspx",
        "approach": "html_scrape",
    },
    "fredericton": {
        "name": "Fredericton Development Permits",
        "province": "NB",
        "cma": "Fredericton",
        "url": "https://www.fredericton.ca/en/building-renovating",
        "approach": "html_scrape",
    },
    "charlottetown": {
        "name": "Charlottetown Building Permits",
        "province": "PE",
        "cma": "Charlottetown",
        "url": "https://www.charlottetown.ca/departments/planning-and-heritage",
        "approach": "html_scrape",
    },
    # ── Phase 7 CMA additions ─────────────────────────────────────────────
    "kitchener": {
        "name": "Kitchener Development Applications",
        "province": "ON",
        "cma": "Kitchener-Cambridge-Waterloo",
        "url": "https://open-kitchenergis.opendata.arcgis.com/api/download/v1/items/3ee5ccb0b6f4488e858522d858e3e508/csv?layers=0",
        "approach": "html_scrape",
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
        "url": "https://www.oshawa.ca/en/building-and-development/planning-applications.aspx",
        "approach": "html_scrape",
    },
    "st_catharines": {
        "name": "St. Catharines Development Applications",
        "province": "ON",
        "cma": "St. Catharines-Niagara",
        "url": "https://www.stcatharines.ca/en/build-and-renovate/planning-applications.aspx",
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
        "url": "https://www.kelowna.ca/homes-building/building-permits-inspections/development-applications",
        "approach": "html_scrape",
    },
    "barrie": {
        "name": "Barrie Development Applications",
        "province": "ON",
        "cma": "Barrie",
        "url": "https://www.barrie.ca/planning-and-development/planning-applications",
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
        "url": "https://www.abbotsford.ca/business-development/planning-development/development-applications",
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
    name = str(raw.get(name_field, "")).strip()
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
                         threshold_millions: float) -> list[dict]:
    """Fetch permits from a Socrata Open Data API."""
    params = dict(source.get("params", {}))
    field_map = source.get("field_map", {})

    try:
        async with session.get(
            source["url"], params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  Socrata {source['name']}: HTTP {resp.status}")
                return []
            records = await resp.json()
    except Exception as e:
        logger.warning(f"  Socrata {source['name']}: {e}")
        return []

    projects = []
    for rec in records:
        proj = _build_project(rec, source, field_map)
        if proj and (proj.get("value_millions") or 0) >= threshold_millions:
            projects.append(proj)
    return projects


async def _fetch_ckan(session: aiohttp.ClientSession, source: dict,
                      threshold_millions: float) -> list[dict]:
    """Fetch permits from a CKAN / OpenData v2 API."""
    params = dict(source.get("params", {}))
    field_map = source.get("field_map", {})

    try:
        async with session.get(
            source["url"], params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  CKAN {source['name']}: HTTP {resp.status}")
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"  CKAN {source['name']}: {e}")
        return []

    # CKAN v2.1 wraps results in "results" key
    records = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        records = []

    projects = []
    for rec in records:
        proj = _build_project(rec, source, field_map)
        if proj and (proj.get("value_millions") or 0) >= threshold_millions:
            projects.append(proj)
    return projects


async def _scrape_html_portal(session: aiohttp.ClientSession, source: dict,
                              threshold_millions: float) -> list[dict]:
    """Scrape an HTML development application portal.

    HTML portals are highly varied in structure. This fetches the listing page
    and attempts to extract project entries. For cities where the structure is
    unknown, returns empty and logs a notice.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.info(f"  {source['name']}: BeautifulSoup not installed, skipping HTML scrape")
        return []

    try:
        async with session.get(
            source["url"],
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/1.0"},
        ) as resp:
            if resp.status != 200:
                logger.warning(f"  HTML {source['name']}: HTTP {resp.status}")
                return []
            html = await resp.text()
    except Exception as e:
        logger.warning(f"  HTML {source['name']}: {e}")
        return []

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

    return projects


async def scrape_municipal_applications() -> list[dict]:
    """Scrape municipal development portals for major projects.

    Returns list of project dicts ready for dedup and Firestore upsert.
    """
    all_projects = []

    async with aiohttp.ClientSession() as session:
        for city_key, source in MUNICIPAL_SOURCES.items():
            try:
                prov = source["province"]
                threshold = GDP_THRESHOLDS.get(prov, 40)
                approach = source.get("approach", "html_scrape")

                if approach == "socrata":
                    projects = await _fetch_socrata(session, source, threshold)
                elif approach in ("ckan_v2", "ckan"):
                    projects = await _fetch_ckan(session, source, threshold)
                else:
                    projects = await _scrape_html_portal(session, source, threshold)

                all_projects.extend(projects)
                logger.info(f"  {city_key}: {len(projects)} projects above ${threshold}M")

            except Exception as e:
                logger.warning(f"  {city_key} failed: {e}")

    logger.info(f"Municipal scraping complete: {len(all_projects)} total projects")
    return all_projects


def scrape_municipal_applications_sync() -> list[dict]:
    """Synchronous wrapper for use in update_dashboard.py pipeline."""
    return asyncio.run(scrape_municipal_applications())
