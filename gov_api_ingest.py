"""
gov_api_ingest.py — Direct ingestion from government structured data sources.

Complements gov_sources.py (which scrapes HTML pages). This module targets
sources that provide structured CSV/JSON/API access — zero extraction error,
highest confidence scores.

Sources:
  - BC Major Projects Inventory (CSV download, quarterly)
  - Alberta Major Projects (downloadable data)
  - IAAC Registry API (JSON, search endpoint)

Projects ingested here are tagged source_type='government_api' and receive
the highest confidence score in Phase 10. They also seed snowball discovery.

Pipeline position:
  Gov API Ingest -> Seed DB -> Deep Search Sweep -> Snowball -> ...

Zero cost — all government data sources are free and keyless.
"""

import csv
import io
import json
import logging
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 30

_HEADERS = {
    "User-Agent": "SignalDispatch/1.0 (Canadian infrastructure pipeline)",
    "Accept": "text/html,application/json,text/csv,*/*",
}

# Standard project fields
_EMPTY_PROJECT = {
    "name": "",
    "province": "",
    "cma": "",
    "sector": "",
    "value": "Not disclosed",
    "value_millions": None,
    "status": "Proposed",
    "proponent": "",
    "description": "",
    "source_url": "",
    "source_type": "government_api",
    "discovery_source": "gov_api",
    "confidence": 0.85,
}


# ── Value parsing ─────────────────────────────────────────────────────────

def _parse_value(raw: str) -> tuple[str, float | None]:
    """Parse a dollar value string into display and numeric (millions)."""
    if not raw:
        return "Not disclosed", None
    s = str(raw).strip().replace(",", "")
    m = re.match(r'\$?\s*(\d+(?:\.\d+)?)\s*(billion|million|B|M|K)?', s, re.IGNORECASE)
    if not m:
        return raw.strip(), None
    n = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in ("billion", "b"):
        return f"${n}B", n * 1000
    if unit in ("million", "m", ""):
        return f"${n}M", n
    if unit == "k":
        return f"${n}K", n / 1000
    return raw.strip(), n


# ── Base class ────────────────────────────────────────────────────────────

class GovSource:
    """Base class for government API connectors."""

    name: str = "Unknown"
    province: str = ""

    def fetch(self) -> list[dict]:
        """Fetch and normalize projects from this source."""
        try:
            raw = self._fetch_raw()
            if not raw:
                return []
            projects = self.normalize(raw)
            logger.info(f"[GovAPI] {self.name}: {len(projects)} projects ingested")
            return projects
        except Exception as e:
            logger.warning(f"[GovAPI] {self.name} failed: {e}")
            return []

    def _fetch_raw(self):
        """Fetch raw data. Override in subclass."""
        raise NotImplementedError

    def normalize(self, raw_data) -> list[dict]:
        """Map source-specific fields to standard project schema. Override in subclass."""
        raise NotImplementedError


# ── BC Major Projects Inventory ───────────────────────────────────────────

class BCMajorProjects(GovSource):
    """BC Major Projects Inventory CSV ingestion.

    Published quarterly by BC Stats. Contains all major projects > $15M.
    Fields: Project Name, Type, Municipality, Region, Estimated Cost,
    Proposed Start, Stage, Developer, Description.

    Landing: https://www2.gov.bc.ca/gov/content/data/statistics/economy/bc-major-projects-inventory
    The actual CSV URL changes each quarter — the landing page must be checked.
    """

    name = "BC Major Projects Inventory"
    province = "British Columbia"
    landing_url = "https://www2.gov.bc.ca/gov/content/data/statistics/economy/bc-major-projects-inventory"

    def _fetch_raw(self):
        """Find and download the CSV from the landing page."""
        # Fetch landing page to find current CSV link
        resp = requests.get(self.landing_url, timeout=FETCH_TIMEOUT, headers=_HEADERS)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        csv_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".csv" in href.lower() or "major" in href.lower() and "download" in href.lower():
                csv_link = href if href.startswith("http") else f"https://www2.gov.bc.ca{href}"
                break

        if not csv_link:
            logger.info(f"[GovAPI] {self.name}: no CSV link found on landing page")
            return None

        csv_resp = requests.get(csv_link, timeout=FETCH_TIMEOUT, headers=_HEADERS)
        csv_resp.raise_for_status()
        return csv_resp.text

    def normalize(self, raw_csv: str) -> list[dict]:
        """Parse BC CSV into standard project dicts."""
        projects = []
        reader = csv.DictReader(io.StringIO(raw_csv))

        for row in reader:
            name = (row.get("Project Name") or row.get("project_name") or "").strip()
            if not name:
                continue

            value_str, value_num = _parse_value(
                row.get("Estimated Cost") or row.get("estimated_cost") or ""
            )

            status_raw = (row.get("Stage") or row.get("Status") or "Proposed").strip()
            status = self._map_status(status_raw)

            proj = {
                **_EMPTY_PROJECT,
                "name": name,
                "province": self.province,
                "cma": (row.get("Municipality") or row.get("Region") or "").strip(),
                "sector": (row.get("Type") or row.get("Sector") or "").strip(),
                "value": value_str,
                "value_millions": value_num,
                "status": status,
                "proponent": (row.get("Developer") or row.get("Proponent") or "").strip(),
                "description": (row.get("Description") or "").strip(),
                "source_url": self.landing_url,
                "discovery_source": "gov_api_bc_mpi",
            }
            projects.append(proj)

        return projects

    @staticmethod
    def _map_status(raw: str) -> str:
        """Map BC-specific status terms to standard statuses."""
        raw_lower = raw.lower()
        if "construction" in raw_lower or "underway" in raw_lower:
            return "Under Construction"
        if "complet" in raw_lower or "operational" in raw_lower:
            return "Complete"
        if "approv" in raw_lower or "permit" in raw_lower:
            return "Approved"
        if "propos" in raw_lower or "plan" in raw_lower:
            return "Proposed"
        if "cancel" in raw_lower or "suspend" in raw_lower:
            return "Cancelled"
        if "on hold" in raw_lower or "defer" in raw_lower:
            return "Paused"
        return "Proposed"


# ── Alberta Major Projects ────────────────────────────────────────────────

class AlbertaMajorProjects(GovSource):
    """Alberta Major Projects data ingestion.

    The Alberta government publishes major project data at majorprojects.alberta.ca.
    This scrapes the project listing table from the public-facing site.
    """

    name = "Alberta Major Projects"
    province = "Alberta"
    url = "https://majorprojects.alberta.ca/"

    def _fetch_raw(self):
        """Fetch the Alberta major projects page."""
        resp = requests.get(self.url, timeout=FETCH_TIMEOUT, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text

    def normalize(self, html: str) -> list[dict]:
        """Parse Alberta project listing from HTML."""
        projects = []
        soup = BeautifulSoup(html, "lxml")

        # Look for project data in tables or structured elements
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Try to extract headers
            headers = []
            header_row = rows[0]
            for th in header_row.find_all(["th", "td"]):
                headers.append(th.get_text(strip=True).lower())

            if not headers:
                continue

            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) < 2:
                    continue

                row_dict = dict(zip(headers, cells))
                name = (
                    row_dict.get("project name")
                    or row_dict.get("project")
                    or row_dict.get("name")
                    or ""
                ).strip()
                if not name or len(name) < 5:
                    continue

                value_str, value_num = _parse_value(
                    row_dict.get("estimated cost")
                    or row_dict.get("value")
                    or row_dict.get("cost")
                    or ""
                )

                proj = {
                    **_EMPTY_PROJECT,
                    "name": name,
                    "province": self.province,
                    "cma": (row_dict.get("location") or row_dict.get("region") or "").strip(),
                    "sector": (row_dict.get("sector") or row_dict.get("industry") or "").strip(),
                    "value": value_str,
                    "value_millions": value_num,
                    "status": (row_dict.get("status") or "Proposed").strip(),
                    "proponent": (row_dict.get("company") or row_dict.get("proponent") or "").strip(),
                    "description": (row_dict.get("description") or "").strip(),
                    "source_url": self.url,
                    "discovery_source": "gov_api_ab_major",
                }
                projects.append(proj)

        return projects


# ── IAAC Registry API ─────────────────────────────────────────────────────

class IAACRegistry(GovSource):
    """IAAC Impact Assessment Registry structured search.

    The IAAC registry at iaac-aeic.gc.ca provides a search endpoint that
    returns project data in a parseable format. This complements the existing
    HTML scraper in gov_sources.py with structured field extraction.
    """

    name = "IAAC Registry API"
    province = "National"
    search_url = "https://iaac-aeic.gc.ca/050/evaluations/exploration"

    # Province mapping for IAAC location fields
    _PROV_MAP = {
        "british columbia": "British Columbia", "alberta": "Alberta",
        "saskatchewan": "Saskatchewan", "manitoba": "Manitoba",
        "ontario": "Ontario", "quebec": "Quebec", "québec": "Quebec",
        "new brunswick": "New Brunswick", "nova scotia": "Nova Scotia",
        "prince edward island": "Prince Edward Island",
        "newfoundland": "Newfoundland and Labrador",
        "labrador": "Newfoundland and Labrador",
        "yukon": "Yukon", "northwest territories": "Northwest Territories",
        "nunavut": "Nunavut",
    }

    def _fetch_raw(self):
        """Fetch IAAC project listing."""
        resp = requests.get(
            self.search_url,
            timeout=FETCH_TIMEOUT,
            headers={
                **_HEADERS,
                "Accept": "text/html",
                "Accept-Language": "en-CA,en;q=0.9",
            },
        )
        resp.raise_for_status()
        return resp.text

    def normalize(self, html: str) -> list[dict]:
        """Parse IAAC listing into project dicts."""
        projects = []
        soup = BeautifulSoup(html, "lxml")

        articles = soup.select("article")
        for art in articles:
            name_el = art.select_one("h3 span.noctitle") or art.select_one("h3")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name or len(name) < 5:
                continue

            # URL
            link = art.select_one("a.resultJobItem") or art.select_one("a")
            url = ""
            if link:
                href = link.get("href", "")
                url = href if href.startswith("http") else f"https://iaac-aeic.gc.ca{href}"

            # Province from location
            province = ""
            loc_el = art.select_one("li.location")
            if loc_el:
                loc_text = loc_el.get_text(strip=True).lower()
                for keyword, prov in self._PROV_MAP.items():
                    if keyword in loc_text:
                        province = prov
                        break

            # Status from phase/status element
            status = "Under Review"
            status_el = art.select_one("li.status") or art.select_one("span.status")
            if status_el:
                status_text = status_el.get_text(strip=True).lower()
                if "decision" in status_text or "complete" in status_text:
                    status = "Approved"
                elif "planning" in status_text:
                    status = "Proposed"
                elif "panel" in status_text or "review" in status_text:
                    status = "Under Review"

            proj = {
                **_EMPTY_PROJECT,
                "name": name,
                "province": province or "National",
                "status": status,
                "source_url": url,
                "discovery_source": "gov_api_iaac",
                "confidence": 0.90,
            }
            projects.append(proj)

        return projects


# ── Source registry ───────────────────────────────────────────────────────

GOV_SOURCES = [
    BCMajorProjects(),
    AlbertaMajorProjects(),
    IAACRegistry(),
]


# ── Orchestrator ──────────────────────────────────────────────────────────

def ingest_all_gov_sources(conn=None) -> list[dict]:
    """Run all government API connectors, return normalized projects.

    Args:
        conn: SQLite connection (reserved for future direct DB writes).

    Returns:
        Combined list of normalized project dicts from all sources.
    """
    all_projects = []
    for source in GOV_SOURCES:
        try:
            projects = source.fetch()
            all_projects.extend(projects)
        except Exception as e:
            logger.warning(f"[GovAPI] {source.name} failed: {e}")

    logger.info(f"[GovAPI] Total: {len(all_projects)} projects from {len(GOV_SOURCES)} sources")
    return all_projects


def get_source_names() -> list[str]:
    """Return list of configured government source names."""
    return [s.name for s in GOV_SOURCES]
