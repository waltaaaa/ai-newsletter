"""
institutional_capital.py — University and major institution capital plan monitoring.

Scrapes capital project pages from Canada's U15 research universities,
major polytechnics, and healthcare institutions. These list approved and
planned construction projects often worth hundreds of millions each.

Strategy: annual full scrape + quarterly news feed checks. Integrates into
the RSS filter pipeline for ongoing monitoring.
"""

import logging
import re
from datetime import date

import requests

logger = logging.getLogger(__name__)

UNIVERSITY_SOURCES = [
    # ── U15 research-intensive universities ──────────────────────────────────
    {"name": "University of Toronto", "province": "ON", "cma": "Toronto",
     "url": "https://www.fs.utoronto.ca/capital-projects/"},
    {"name": "UBC", "province": "BC", "cma": "Vancouver",
     "url": "https://planning.ubc.ca/"},
    {"name": "McGill University", "province": "QC", "cma": "Montreal",
     "url": "https://www.mcgill.ca/facilities/"},
    {"name": "Université de Montréal", "province": "QC", "cma": "Montreal",
     "url": "https://di.umontreal.ca/"},
    {"name": "University of Alberta", "province": "AB", "cma": "Edmonton",
     "url": "https://www.ualberta.ca/facilities-operations/"},
    {"name": "University of Calgary", "province": "AB", "cma": "Calgary",
     "url": "https://www.ucalgary.ca/facilities/"},
    {"name": "McMaster University", "province": "ON", "cma": "Hamilton",
     "url": "https://facilities.mcmaster.ca/"},
    {"name": "University of Ottawa", "province": "ON", "cma": "Ottawa-Gatineau",
     "url": "https://www.uottawa.ca/facilities/"},
    {"name": "Université Laval", "province": "QC", "cma": "Quebec City",
     "url": "https://www.ulaval.ca/"},
    {"name": "Queen's University", "province": "ON", "cma": "Kingston",
     "url": "https://www.queensu.ca/pps/"},
    {"name": "University of Manitoba", "province": "MB", "cma": "Winnipeg",
     "url": "https://umanitoba.ca/physical-plant/"},
    {"name": "Dalhousie University", "province": "NS", "cma": "Halifax",
     "url": "https://www.dal.ca/dept/facilities-management.html"},
    {"name": "University of Saskatchewan", "province": "SK", "cma": "Saskatoon",
     "url": "https://facilities.usask.ca/"},
    {"name": "Western University", "province": "ON", "cma": "London",
     "url": "https://www.uwo.ca/facilities/"},
    {"name": "University of Waterloo", "province": "ON", "cma": "Kitchener-Cambridge-Waterloo",
     "url": "https://uwaterloo.ca/plant-operations/"},
    # ── Major polytechnics ───────────────────────────────────────────────────
    {"name": "BCIT", "province": "BC", "cma": "Vancouver",
     "url": "https://www.bcit.ca/about/"},
    {"name": "SAIT", "province": "AB", "cma": "Calgary",
     "url": "https://www.sait.ca/about-sait"},
    {"name": "George Brown College", "province": "ON", "cma": "Toronto",
     "url": "https://www.georgebrown.ca/about"},
    # ── Healthcare research institutions ─────────────────────────────────────
    {"name": "SickKids Hospital — Project Horizon", "province": "ON", "cma": "Toronto",
     "url": "https://www.sickkids.ca/en/about/project-horizon/"},
    {"name": "MUHC (McGill University Health Centre)", "province": "QC", "cma": "Montreal",
     "url": "https://muhc.ca/"},
]

# Dollar regex for extracting values from page text
_DOLLAR_RE = re.compile(
    r'\$\s*([\d,.]+)\s*(million|billion|m\b|b\b)',
    re.IGNORECASE,
)


def _parse_dollar(text: str) -> float | None:
    """Extract dollar value in millions from text."""
    m = _DOLLAR_RE.search(text)
    if not m:
        return None
    num = float(m.group(1).replace(',', ''))
    if m.group(2).lower().startswith('b'):
        return num * 1000
    return num


def scrape_institutional_capital() -> list[dict]:
    """Scrape university and institution capital project pages.

    Returns list of project dicts ready for dedup and Firestore upsert.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not installed, skipping institutional scrape")
        return []

    all_projects = []

    for source in UNIVERSITY_SOURCES:
        try:
            resp = requests.get(
                source["url"],
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/1.0"},
            )
            if resp.status_code != 200:
                logger.warning(f"  {source['name']}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            projects = _extract_projects_from_page(soup, source)
            all_projects.extend(projects)
            if projects:
                logger.info(f"  {source['name']}: {len(projects)} capital projects found")

        except Exception as e:
            logger.warning(f"  {source['name']} failed: {e}")

    logger.info(f"Institutional scraping complete: {len(all_projects)} total projects")
    return all_projects


def _extract_projects_from_page(soup, source: dict) -> list[dict]:
    """Extract capital projects from a parsed HTML page.

    Looks for project headings/sections with associated dollar values.
    Uses heuristics — each institution's page structure differs.
    """
    projects = []
    seen_names = set()

    # Strategy: find headings (h2, h3, h4) or list items near dollar values
    for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
        text = heading.get_text(strip=True)
        if not text or len(text) < 5 or len(text) > 200:
            continue

        # Look for dollar value in the heading itself or the next sibling block
        context = text
        next_sib = heading.find_next_sibling()
        if next_sib:
            context += " " + next_sib.get_text(separator=" ", strip=True)[:500]

        value = _parse_dollar(context)
        if not value or value < 10:  # Skip anything under $10M
            continue

        name_key = text.lower().strip()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        # Get link if heading contains one
        link = heading.find("a", href=True)
        url = link["href"] if link else source["url"]
        if url.startswith("/"):
            from urllib.parse import urljoin
            url = urljoin(source["url"], url)

        display_name = f"{source['name']} — {text}"

        projects.append({
            "name": display_name,
            "province": source["province"],
            "cma": source.get("cma", ""),
            "sector": "61",  # Education (NAICS 61) or 62 for healthcare
            "naics_code": "62" if "hospital" in source["name"].lower() or "health" in source["name"].lower() else "61",
            "tags": [],
            "value": f"${value:.0f}M",
            "value_millions": value,
            "status": "Proposed",
            "description": context[:200],
            "discovery_source": "institutional_capital",
            "source_url": url,
            "source_title": source["name"],
            "sources": [{"id": 1, "title": source["name"], "url": url}],
            "announced": date.today().isoformat(),
            "completionDate": "",
            "_discovery_tier": "institutional_capital",
            "_source_type": "government",
            "confidence": 0.65,
            "_evidence": [{
                "url": url,
                "name": source["name"],
                "source_type": "institutional_capital",
                "authority": "government",
            }],
        })

    return projects


# RSS feeds for ongoing monitoring of university news
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
