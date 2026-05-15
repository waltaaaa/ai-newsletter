"""
nim_deep_search.py — Deep web search for Canadian capital projects using SearXNG + NIM.

Replaces Kimi's execution engine (Moonshot API + $web_search) with:
  1. SearXNG — unlimited free web search (local Docker or public fallback)
  2. NIM reranker — filter search results by relevance before extraction
  3. trafilatura — full-text extraction from top URLs
  4. NIM K2.5 (thinking mode) — structured project extraction with reasoning

Query generation logic preserved from kimi_deep_search.py:
  Same SECTORS, PROVINCES, CMAs, NATIONAL_QUERIES, JSON_INSTRUCTIONS.

Dependencies:
  - searxng_search.py (Phase 1) — search_unified_sync
  - nim_client.py (Phase 0) — get_client() for rerank + K2.5 chat

Usage:
    python nim_deep_search.py
    python nim_deep_search.py --dry-run          # Print queries without calling API
    python nim_deep_search.py --max-queries 10   # Limit number of queries
    python nim_deep_search.py --no-thinking      # Disable K2.5 thinking mode (faster)
    python nim_deep_search.py --start-from 50    # Resume from query index
    python nim_deep_search.py --resume-csv path  # Pre-load prior CSV for dedup
"""

import os
import sys
import json
import csv
import logging
import argparse
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from searxng_search import search_unified_sync
from nim_client import get_client
from pipeline_config import NIM_RERANK_ENABLED, NIM_THINKING_MODE

# ── Configuration ──────────────────────────────────────────────────────────
RERANK_TOP_N = 5           # Keep top N results after reranking
MAX_PAGE_TEXT_CHARS = 3000  # Max chars per page to send to K2.5
MAX_CONTEXT_PAGES = 5      # Max pages to include in K2.5 context
FETCH_TIMEOUT = 15         # Seconds for page fetch
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H%M")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"nim_search_results_{TIMESTAMP}.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(OUTPUT_DIR, f"nim_search_{TIMESTAMP}.log")),
    ],
)
logger = logging.getLogger(__name__)

# K2.5 system prompt (adapted — K2.5 analyzes provided text, not its own search)
SYSTEM_PROMPT = (
    "You are a research assistant specializing in Canadian capital projects "
    "and infrastructure development. Analyze the provided web search results "
    "and extract structured data about real projects. Always return valid JSON arrays. "
    "Only include projects that are clearly described in the provided sources."
)

# Check trafilatura availability
try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False
    logger.info("trafilatura not installed, using BeautifulSoup fallback for page extraction")

_HEADERS = {
    "User-Agent": "SignalDispatch/1.0 (Canadian infrastructure pipeline)",
}

# ── Sector definitions (preserved from kimi_deep_search.py) ───────────────
SECTORS = {
    "oil_gas": "Oil, Gas & Hydrogen (oil sands, LNG, pipelines, refineries, hydrogen, CCUS, petrochemical, gas plants)",
    "mining": "Mining & Critical Minerals (mines, smelters, mineral processing, lithium, nickel, cobalt, graphite, rare earths, uranium, copper, potash, gold, iron ore)",
    "infrastructure": "Civil Infrastructure (highways, bridges, tunnels, water/wastewater treatment, dams, flood protection, transit — LRT, BRT, subway, commuter rail)",
    "power_energy": "Power Generation, Transmission & Clean Energy (power plants, solar, wind, hydro, nuclear, SMR, battery storage, transmission lines, geothermal, biomass, grid modernization)",
    "manufacturing": "Manufacturing & Industrial (factories, EV battery gigafactories, automotive, semiconductor, food processing, pharma, aerospace, steel, cement, data centres)",
    "transport_logistics": "Ports, Airports, Rail & Logistics (airport terminals, port terminals, rail lines/yards, intermodal, ferry/cruise terminals, logistics hubs, high-speed rail)",
    "healthcare": "Healthcare & Life Sciences (hospitals, medical centres, long-term care, mental health, cancer centres, research labs, pharma/biotech facilities, seniors care)",
    "education": "Education & Research (schools, universities, colleges, research centres, student residences, libraries, training centres, campus modernizations)",
    "residential": "Residential & Housing (residential towers, affordable housing, condo, social housing, Indigenous housing, purpose-built rental, mixed-income, office-to-residential conversions)",
    "commercial_mixed": "Commercial & Mixed-Use (mixed-use developments, office towers, entertainment districts, convention centres, hotels, sports arenas, downtown redevelopments, waterfront revitalization)",
    "agriculture": "Agriculture & Agri-Food (agricultural processing, grain terminals, food manufacturing, irrigation, greenhouses, vertical farms, aquaculture, livestock facilities)",
    "forestry": "Forestry & Wood Products (pulp mills, sawmills, wood pellet plants, cross-laminated timber, bioenergy from forest residue, forest management infrastructure)",
    "defence": "Defence & Military (military bases, naval shipyards, defence manufacturing, radar installations, ammunition plants, military housing, DND facilities)",
    "telecom": "Telecommunications & Digital (data centres, fibre/broadband networks, 5G towers, satellite ground stations, submarine cables, digital infrastructure)",
    "indigenous": "Indigenous-Led Development (Indigenous economic development, First Nations infrastructure, Inuit housing, Métis development corporations, duty-to-consult projects)",
    "environment": "Environmental & Remediation (brownfield remediation, contaminated site cleanup, waste management, recycling facilities, environmental monitoring, conservation infrastructure)",
    "tourism_culture": "Tourism, Culture & Recreation (stadiums, arenas, casinos, museums, cultural centres, convention centres, resorts, theme parks, recreation centres, ski facilities)",
    "government": "Government & Institutional (government buildings, courthouses, correctional facilities, border infrastructure, embassies, public works, municipal facilities)",
}

# ── Province tiers (preserved from kimi_deep_search.py) ───────────────────
# Big 4: all 18 sectors
BIG_PROVINCES = ["Ontario", "Quebec", "Alberta", "British Columbia"]

# Medium: 10 key sectors
MID_PROVINCES = ["Saskatchewan", "Manitoba", "Nova Scotia", "New Brunswick", "Newfoundland and Labrador"]
MID_SECTORS = [
    "oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
    "transport_logistics", "healthcare", "education", "residential", "agriculture",
]

# Small/territories: 6 key sectors
SMALL_PROVINCES = ["Prince Edward Island", "Yukon", "Northwest Territories", "Nunavut"]
SMALL_SECTORS = ["mining", "infrastructure", "power_energy", "healthcare", "education", "indigenous"]

# ── CMA (Census Metropolitan Area) queries (preserved from kimi_deep_search.py) ──
CMAS = {
    "Ontario": [
        "Toronto", "Ottawa", "Hamilton", "Kitchener-Waterloo", "London",
        "Windsor", "Oshawa", "St. Catharines-Niagara", "Barrie", "Kingston",
        "Sudbury", "Thunder Bay", "Guelph", "Peterborough", "Brantford",
    ],
    "Quebec": [
        "Montreal", "Quebec City", "Gatineau", "Sherbrooke", "Trois-Rivières",
        "Saguenay", "Lévis", "Laval", "Longueuil", "Drummondville",
    ],
    "Alberta": [
        "Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat",
        "Grande Prairie", "Fort McMurray",
    ],
    "British Columbia": [
        "Vancouver", "Victoria", "Kelowna", "Kamloops", "Nanaimo",
        "Prince George", "Abbotsford", "Chilliwack",
    ],
    "Saskatchewan": ["Saskatoon", "Regina"],
    "Manitoba": ["Winnipeg", "Brandon"],
    "Nova Scotia": ["Halifax"],
    "New Brunswick": ["Moncton", "Saint John", "Fredericton"],
    "Newfoundland and Labrador": ["St. John's", "Happy Valley-Goose Bay"],
}

CMA_SECTORS = [
    "infrastructure", "residential", "commercial_mixed", "healthcare",
    "transport_logistics",
]

# ── National thematic queries (preserved from kimi_deep_search.py) ────────
NATIONAL_QUERIES = [
    # Critical minerals & mining
    "Search for all critical minerals and rare earth mining projects across Canada announced, approved, or under development between March 2024 and March 2026. Include lithium, nickel, cobalt, graphite, rare earths, uranium, and copper projects. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status (proposed/approved/under construction/completed/paused/cancelled), proponent/developer company, a brief description, and the source URL where you found this information.",
    # LNG & hydrogen
    "Search for all LNG terminals, natural gas, and hydrogen production projects across Canada announced, approved, or under development between March 2024 and March 2026. Include LNG export/import terminals, hydrogen electrolyzers, blue/green hydrogen plants, and natural gas processing expansions. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Nuclear & SMR
    "Search for all small modular reactor (SMR), nuclear refurbishment, and nuclear energy projects across Canada announced, approved, or under development between March 2024 and March 2026. Include SMR deployment sites, reactor refurbishments (e.g. Bruce, Darlington, Point Lepreau), new nuclear plants, and uranium processing facilities. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Data centres & AI
    "Search for all data centre, AI campus, and semiconductor fabrication projects across Canada announced, approved, or under development between March 2024 and March 2026. Include hyperscale data centres, colocation facilities, chip manufacturing, and AI research campuses. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # EV & automotive
    "Search for all EV battery gigafactory, electric vehicle manufacturing, and automotive plant projects across Canada announced, approved, or under development between March 2024 and March 2026. Include battery cell manufacturing, cathode/anode material plants, EV assembly plants, and auto sector retooling. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Federal infrastructure
    "Search for all major federal infrastructure projects across Canada announced, approved, or under development between March 2024 and March 2026. Include federal bridges, highways, border crossings, transit funding recipients, and Infrastructure Canada funded projects over $100 million. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Indigenous-led
    "Search for all major Indigenous-led economic development and infrastructure projects across Canada announced, approved, or under development between March 2024 and March 2026. Include First Nations, Inuit, and Métis development projects, Indigenous housing initiatives, Indigenous-owned energy projects, and equity partnership projects. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Defence & military
    "Search for all defence, military base, and Canadian Armed Forces infrastructure projects across Canada announced, approved, or under development between March 2024 and March 2026. Include naval shipbuilding (NSS, CSC), military base upgrades, NORAD modernization, defence manufacturing facilities, and DND construction. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # CCUS
    "Search for all carbon capture, utilization and storage (CCUS) projects across Canada announced, approved, or under development between March 2024 and March 2026. Include direct air capture, industrial CCUS, CO2 pipelines, storage hubs, and enhanced oil recovery with carbon capture. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Ports, airports, rail
    "Search for all major port expansion, airport terminal, and high-speed rail projects across Canada announced, approved, or under development between March 2024 and March 2026. Include container terminal expansions, cruise terminals, airport terminal builds/renovations, new rail corridors, and intermodal hubs. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Wind & solar mega-projects
    "Search for all large-scale wind farm and solar farm projects in Canada (over $50 million) announced, approved, or under development between March 2024 and March 2026. Include onshore wind, offshore wind, utility-scale solar, and solar-plus-storage projects. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Hospital & healthcare mega-projects
    "Search for all major hospital construction, medical campus, and healthcare facility projects in Canada (over $100 million) announced, approved, or under development between March 2024 and March 2026. Include new hospitals, hospital expansions, cancer centres, children's hospitals, mental health facilities, and medical research institutes. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Transit mega-projects
    "Search for all major public transit projects in Canada (over $500 million) announced, approved, or under construction between March 2024 and March 2026. Include LRT lines, subway extensions, BRT systems, commuter rail, and rapid transit projects in Toronto, Montreal, Vancouver, Calgary, Edmonton, Ottawa, and other cities. For each project provide: project name, province, city, estimated value in Canadian dollars, current status, proponent, a brief description, and the source URL.",
    # Oil sands & pipelines
    "Search for all oil sands, pipeline, and refinery projects across Canada announced, approved, or under development between March 2024 and March 2026. Include new oil sands mines, SAGD expansions, pipeline projects (TMX, Keystone, Coastal GasLink, others), refinery upgrades, and bitumen upgraders. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Affordable & social housing
    "Search for all major affordable housing, social housing, and public housing projects across Canada (over $50 million) announced, approved, or under construction between March 2024 and March 2026. Include CMHC-funded projects, provincial housing programs, co-operative housing, Indigenous housing, modular housing initiatives, and office-to-residential conversions. For each project provide: project name, province, city, estimated value in Canadian dollars, current status, proponent, a brief description, and the source URL.",
    # University & campus development
    "Search for all major university and college campus development projects across Canada (over $50 million) announced, approved, or under construction between March 2024 and March 2026. Include new buildings, research centres, student residences, campus expansions, and facility modernizations. For each project provide: project name, province, city, estimated value in Canadian dollars, current status, institution/proponent, a brief description, and the source URL.",
    # Pulp, paper & forestry
    "Search for all major forestry, pulp mill, sawmill, and wood products projects across Canada announced, approved, or under development between March 2024 and March 2026. Include new mills, mill conversions, biomass energy projects, CLT manufacturing, and wood pellet plants. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Waste & recycling
    "Search for all major waste management, recycling, and remediation projects across Canada (over $25 million) announced, approved, or under development between March 2024 and March 2026. Include waste-to-energy plants, recycling facilities, landfill expansions, contaminated site cleanups, and water treatment upgrades. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Telecom & broadband
    "Search for all major telecommunications, broadband, and digital infrastructure projects across Canada announced, approved, or under development between March 2024 and March 2026. Include fibre-to-the-home rollouts, 5G tower deployments, rural broadband initiatives, submarine cables, satellite ground stations, and CRTC-funded connectivity projects. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Food processing & agriculture
    "Search for all major food processing, agricultural, and agri-food projects across Canada (over $25 million) announced, approved, or under development between March 2024 and March 2026. Include food manufacturing plants, grain terminals, greenhouses, vertical farms, canola crushing plants, dairy processing, meat processing, and irrigation infrastructure. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Mega-projects over $1B
    "Search for all mega-projects in Canada with estimated costs over $1 billion that are currently proposed, approved, or under construction as of March 2026. Include all sectors: energy, mining, transit, infrastructure, manufacturing, healthcare, and commercial development. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Recently cancelled or paused
    "Search for all major capital projects in Canada (over $100 million) that were cancelled, paused, shelved, or indefinitely delayed between March 2024 and March 2026. Include all sectors. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status (cancelled/paused/shelved), proponent/developer, reason for cancellation or pause if known, and the source URL.",
    # Crown corporation projects
    "Search for all major Crown corporation capital projects across Canada announced, approved, or under development between March 2024 and March 2026. Include projects by Canada Post, CBC, VIA Rail, Export Development Canada, Canadian National Railway (if applicable), Hydro-Québec, BC Hydro, Ontario Power Generation, SaskPower, Manitoba Hydro, and other provincial Crown corporations. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, Crown corporation name, a brief description, and the source URL.",
    # Shipbuilding & marine
    "Search for all major shipbuilding, naval, and marine infrastructure projects across Canada announced, approved, or under development between March 2024 and March 2026. Include National Shipbuilding Strategy vessels, coast guard ships, ferry construction, drydock facilities, and marine terminal projects. For each project provide: project name, province, city/region, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
    # Casino, resort & entertainment
    "Search for all major casino, resort, theme park, and entertainment venue projects across Canada (over $50 million) announced, approved, or under development between March 2024 and March 2026. Include new casinos, casino relocations, resort expansions, waterpark hotels, entertainment districts, and theme park developments. For each project provide: project name, province, city, estimated value in Canadian dollars, current status, proponent/developer, a brief description, and the source URL.",
]


JSON_INSTRUCTIONS = (
    "For each project found, provide:\n"
    "- project_name: exact name of the project\n"
    "- province: province or territory\n"
    "- city: city or region where the project is located\n"
    "- sector: sector category\n"
    "- estimated_value: estimated cost in Canadian dollars (e.g. \"$1.2B\", \"$350M\") or \"Not disclosed\"\n"
    "- status: one of Proposed, Approved, Under Construction, Completed, Paused, Cancelled\n"
    "- proponent: company or government body leading the project\n"
    "- description: 1-2 sentence description of the project\n"
    "- source_url: the URL where you found this information\n\n"
    "Return your answer as a JSON array of objects with these exact field names. "
    "If you find no projects, return an empty array: []\n"
    "IMPORTANT: Only include real projects you can verify with web sources. Do not fabricate."
)


# ── Query builders (preserved from kimi_deep_search.py) ───────────────────

def build_query(province: str, sector_key: str) -> str:
    """Build a structured extraction prompt for a province x sector combination."""
    sector_desc = SECTORS[sector_key]
    return (
        f"Search the web for all major {sector_desc} projects in {province}, Canada "
        f"that were announced, approved, began construction, reached a milestone, "
        f"were delayed, paused, cancelled, or completed between March 2024 and March 2026. "
        f"Include both new builds (greenfield) and redevelopments, renovations, expansions, "
        f"conversions, modernizations, and adaptive reuse projects (brownfield). "
        f"{JSON_INSTRUCTIONS}"
    )


def build_cma_query(city: str, province: str, sector_key: str) -> str:
    """Build an extraction prompt for a specific city/CMA x sector."""
    sector_desc = SECTORS[sector_key]
    return (
        f"Search the web for all major {sector_desc} projects in or near {city}, {province}, Canada "
        f"that were announced, approved, began construction, reached a milestone, "
        f"were delayed, paused, cancelled, or completed between March 2024 and March 2026. "
        f"Include both greenfield and brownfield projects (redevelopments, renovations, expansions, "
        f"conversions, modernizations, adaptive reuse). "
        f"{JSON_INSTRUCTIONS}"
    )


def _to_search_query(query_info: dict) -> str:
    """Convert a query dict to a short SearXNG-optimized search query.

    The full extraction prompt is too long for web search — this extracts
    the core topic as a concise search string.
    """
    if query_info["type"] == "national":
        prompt = query_info["query"]
        match = re.search(
            r'(?:Search for all|all)\s+(.+?)\s+(?:across Canada|in Canada)',
            prompt, re.IGNORECASE,
        )
        if match:
            topic = match.group(1)
            words = topic.split()[:10]
            return f"Canada {' '.join(words)} 2024 2025 2026"
        return prompt[:120]

    province = query_info["province"]
    sector_short = SECTORS[query_info["sector"]].split("(")[0].strip()

    if query_info["type"] == "cma_sector":
        city = query_info.get("cma", "")
        return f"{city} {province} {sector_short} projects construction development 2024 2025 2026"

    return f"{province} Canada {sector_short} projects construction development 2024 2025 2026"


def build_all_queries() -> list[dict]:
    """Build the full query matrix: province x sector + CMA x sector + national thematic."""
    queries = []

    # ── Tier 1: Big 4 provinces x all 18 sectors ──
    for prov in BIG_PROVINCES:
        for sector in SECTORS:
            queries.append({
                "query": build_query(prov, sector),
                "province": prov,
                "sector": sector,
                "type": "province_sector",
            })

    # ── Tier 2: Medium provinces x 10 sectors ──
    for prov in MID_PROVINCES:
        for sector in MID_SECTORS:
            queries.append({
                "query": build_query(prov, sector),
                "province": prov,
                "sector": sector,
                "type": "province_sector",
            })

    # ── Tier 3: Small provinces/territories x 6 sectors ──
    for prov in SMALL_PROVINCES:
        for sector in SMALL_SECTORS:
            queries.append({
                "query": build_query(prov, sector),
                "province": prov,
                "sector": sector,
                "type": "province_sector",
            })

    # ── Tier 4: CMA-level queries (major cities x key sectors) ──
    for prov, cities in CMAS.items():
        for city in cities:
            for sector in CMA_SECTORS:
                queries.append({
                    "query": build_cma_query(city, prov, sector),
                    "province": prov,
                    "sector": sector,
                    "type": "cma_sector",
                    "cma": city,
                })

    # ── Tier 5: National thematic queries ──
    for i, q in enumerate(NATIONAL_QUERIES):
        queries.append({
            "query": q,
            "province": "National",
            "sector": f"thematic_{i+1}",
            "type": "national",
        })

    return queries


# ── Extraction helpers (preserved from kimi_deep_search.py) ───────────────

def extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from response text, handling markdown code blocks."""
    if not text:
        return []

    # Try to find ```json ... ``` blocks
    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a raw JSON array
    bracket_match = re.search(r'\[[\s\S]*\]', text)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try parsing the entire text as JSON
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "projects" in result:
            return result["projects"]
    except json.JSONDecodeError:
        pass

    logger.warning(f"Could not extract JSON from response ({len(text)} chars)")
    return []


def normalize_project(proj: dict, query_province: str, query_sector: str) -> dict:
    """Normalize a project dict to consistent CSV fields."""
    return {
        "project_name": (proj.get("project_name") or proj.get("name") or "").strip(),
        "province": (proj.get("province") or query_province).strip(),
        "city": (proj.get("city") or proj.get("location") or proj.get("region") or "").strip(),
        "sector": (proj.get("sector") or query_sector).strip(),
        "estimated_value": (proj.get("estimated_value") or proj.get("value") or "Not disclosed").strip(),
        "status": (proj.get("status") or "Proposed").strip(),
        "proponent": (proj.get("proponent") or proj.get("developer") or proj.get("company") or "").strip(),
        "description": (proj.get("description") or proj.get("details") or "").strip(),
        "source_url": (proj.get("source_url") or proj.get("url") or proj.get("source") or "").strip(),
        "search_province": query_province,
        "search_sector": query_sector,
    }


def dedup_key(proj: dict) -> str:
    """Create a dedup key from project name + province."""
    name = re.sub(r'[^a-z0-9]', '', (proj.get("project_name") or "").lower())
    prov = re.sub(r'[^a-z0-9]', '', (proj.get("province") or "").lower())
    return f"{name}__{prov}"


# ── Page text extraction (pattern from snippet_enhancer.py) ───────────────

def fetch_page_text(url: str) -> str:
    """Fetch full article text via trafilatura (primary) or BS4 (fallback).

    Returns extracted text or empty string on failure.
    """
    # Try trafilatura first. NOTE: trafilatura.fetch_url() ignores timeout —
    # we fetch the HTML ourselves with a hard timeout, then hand to extract().
    if _HAS_TRAFILATURA:
        try:
            resp = requests.get(url, timeout=FETCH_TIMEOUT, headers=_HEADERS)
            resp.raise_for_status()
            text = trafilatura.extract(
                resp.text, favor_recall=True, include_comments=False,
            )
            if text and len(text) >= 100:
                return text.strip()
        except Exception as e:
            logger.debug(f"trafilatura failed for {url}: {e}")

    # Fallback to BeautifulSoup
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers=_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if main:
            paragraphs = main.find_all("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs)
            if len(text) >= 100:
                return text.strip()
    except Exception as e:
        logger.debug(f"BS4 fallback failed for {url}: {e}")

    return ""


# ── Search + Rerank + Extract engine (NEW — replaces call_kimi) ───────────

def search_and_extract(query_info: dict, thinking: bool = True) -> list[dict]:
    """Execute the full search-rerank-extract pipeline for one query.

    Pipeline:
      1. SearXNG search (short query) -> 10 web results
      2. NIM rerank -> top 5 most relevant (optional)
      3. trafilatura -> extract full text from top URLs
      4. NIM K2.5 (thinking mode) -> structured project extraction
      5. extract_json_array() -> parse response

    Args:
        query_info: Query dict from build_all_queries().
        thinking: Enable K2.5 thinking mode for better extraction.

    Returns:
        List of raw project dicts from K2.5 response.
    """
    search_query = query_info.get("search_query") or _to_search_query(query_info)
    extraction_prompt = query_info["query"]
    client = get_client()

    # Step 1: SearXNG search
    results = search_unified_sync(search_query, max_results=10)
    if not results:
        logger.debug(f"No search results for: {search_query[:60]}")
        return []

    # Step 2: NIM rerank (optional — filter to top N most relevant)
    if NIM_RERANK_ENABLED and len(results) > RERANK_TOP_N:
        try:
            passages = [
                f"{r.get('title', '')} {r.get('content', '')}" for r in results
            ]
            ranked = client.rerank_sync(search_query, passages, top_n=RERANK_TOP_N)
            # Reorder results by ranking
            reranked = []
            for item in ranked:
                idx = item.get("index", 0)
                if idx < len(results):
                    reranked.append(results[idx])
            if reranked:
                results = reranked
        except Exception as e:
            logger.warning(f"Rerank failed, using original order: {e}")
            results = results[:RERANK_TOP_N]
    else:
        results = results[:RERANK_TOP_N]

    # Step 3: Fetch full text from top URLs via trafilatura
    page_texts = []
    for r in results[:MAX_CONTEXT_PAGES]:
        url = r.get("url", "")
        if not url:
            continue
        text = fetch_page_text(url)
        if text:
            page_texts.append(
                f"Source: {url}\nTitle: {r.get('title', '')}\n\n"
                f"{text[:MAX_PAGE_TEXT_CHARS]}"
            )
        elif r.get("content"):
            # Use SearXNG snippet as lightweight fallback
            page_texts.append(
                f"Source: {url}\nTitle: {r.get('title', '')}\n\n"
                f"{r['content']}"
            )

    if not page_texts:
        logger.debug("No page text extracted for any search result")
        return []

    combined_text = "\n\n---\n\n".join(page_texts)

    # Step 4: K2.5 extraction
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{extraction_prompt}\n\n"
                f"Here are the web search results to analyze:\n\n"
                f"{combined_text}"
            ),
        },
    ]

    try:
        response = client.chat_sync(
            messages=messages,
            thinking=thinking,
            max_tokens=8192,
            temperature=0.3,
        )
    except Exception as e:
        logger.error(f"K2.5 extraction failed: {e}")
        return []

    # Step 5: Parse response
    return extract_json_array(response)


# ── Pipeline integration ──────────────────────────────────────────────────

def run_deep_search(conn=None, max_queries: int = 0, thinking: bool = None,
                    start_from: int = 0) -> list[dict]:
    """Run NIM deep search and return normalized project list.

    For use by update_dashboard.py via --nim-sweep flag.

    Args:
        conn: SQLite connection (reserved for future dedup against DB).
        max_queries: Limit queries (0 = all).
        thinking: Override thinking mode (None = use config).
        start_from: Skip first N queries.

    Returns:
        List of normalized project dicts ready for project_sync.upsert_flat_projects().
    """
    if thinking is None:
        thinking = NIM_THINKING_MODE

    queries = build_all_queries()
    logger.info(f"NIM deep search: {len(queries)} total queries")

    if start_from > 0:
        queries = queries[start_from:]
    if max_queries > 0:
        queries = queries[:max_queries]

    all_projects = []
    seen_keys = set()

    for i, q in enumerate(queries):
        label = f"[{i+1}/{len(queries)}] {q['province']} x {q['sector']}"
        logger.info(f"{label} — searching...")

        raw_projects = search_and_extract(q, thinking=thinking)

        if not raw_projects:
            continue

        new_count = 0
        for proj in raw_projects:
            normalized = normalize_project(proj, q["province"], q["sector"])
            if not normalized["project_name"]:
                continue
            key = dedup_key(normalized)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_projects.append(normalized)
            new_count += 1

        logger.info(f"{label} — {len(raw_projects)} found, {new_count} new (total: {len(all_projects)})")

    logger.info(f"NIM deep search complete: {len(all_projects)} unique projects")
    return all_projects


# ── CLI entry point ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NIM deep search for Canadian capital projects (SearXNG + NIM rerank + K2.5)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print queries without calling API")
    parser.add_argument("--max-queries", type=int, default=0, help="Limit number of queries (0 = all)")
    parser.add_argument("--start-from", type=int, default=0, help="Skip first N queries (resume)")
    parser.add_argument("--resume-csv", type=str, default="", help="Path to prior CSV to pre-load for dedup")
    parser.add_argument("--no-thinking", action="store_true", help="Disable K2.5 thinking mode (faster)")
    args = parser.parse_args()

    thinking = NIM_THINKING_MODE and not args.no_thinking

    queries = build_all_queries()
    total = len(queries)
    logger.info(f"Built {total} queries")

    if args.max_queries > 0:
        queries = queries[:args.max_queries]
        logger.info(f"Limited to {len(queries)} queries")

    if args.start_from > 0:
        queries = queries[args.start_from:]
        logger.info(f"Starting from query {args.start_from}, {len(queries)} remaining")

    if args.dry_run:
        for i, q in enumerate(queries):
            search_q = _to_search_query(q)
            print(f"\n{'='*80}")
            print(f"Query {i+1}/{len(queries)}: {q['province']} x {q['sector']}")
            print(f"SearXNG query: {search_q}")
            print(f"{'='*80}")
            print(q["query"][:300] + "...")
        print(f"\nTotal: {len(queries)} queries")
        print(f"Estimated NIM calls: ~{len(queries) * 2} (rerank + extract per query)")
        print(f"Thinking mode: {'ON' if thinking else 'OFF'}")
        return

    # ── Run searches ───────────────────────────────────────────────────
    all_projects = []
    seen_keys = set()
    errors = 0
    empty = 0

    CSV_FIELDS = [
        "project_name", "province", "city", "sector", "estimated_value",
        "status", "proponent", "description", "source_url",
        "search_province", "search_sector",
    ]

    # Pre-load prior CSV for dedup if resuming
    if args.resume_csv:
        resume_path = args.resume_csv
        if os.path.exists(resume_path):
            with open(resume_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = dedup_key(row)
                    seen_keys.add(key)
                    all_projects.append(row)
            logger.info(f"Loaded {len(all_projects)} projects from {resume_path} for dedup")
            OUTPUT_CSV_FINAL = resume_path
        else:
            logger.warning(f"Resume CSV not found: {resume_path}")
            OUTPUT_CSV_FINAL = OUTPUT_CSV
    else:
        OUTPUT_CSV_FINAL = OUTPUT_CSV

    # Write CSV header only if new file
    if OUTPUT_CSV_FINAL != args.resume_csv:
        with open(OUTPUT_CSV_FINAL, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

    logger.info(f"Output CSV: {OUTPUT_CSV_FINAL}")
    logger.info(f"Starting search ({len(queries)} queries, thinking={'ON' if thinking else 'OFF'})...")

    for i, q in enumerate(queries):
        label = f"[{i+1}/{len(queries)}] {q['province']} x {q['sector']}"
        logger.info(f"{label} — searching...")

        try:
            raw_projects = search_and_extract(q, thinking=thinking)
        except Exception as e:
            logger.error(f"{label} — search failed: {e}")
            errors += 1
            continue

        if not raw_projects:
            logger.info(f"{label} — no projects found")
            empty += 1
            continue

        # Normalize and dedup
        new_count = 0
        for proj in raw_projects:
            normalized = normalize_project(proj, q["province"], q["sector"])
            if not normalized["project_name"]:
                continue
            key = dedup_key(normalized)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_projects.append(normalized)
            new_count += 1

        # Append to CSV incrementally
        if new_count > 0:
            with open(OUTPUT_CSV_FINAL, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                for proj in all_projects[-new_count:]:
                    writer.writerow(proj)

        logger.info(f"{label} — found {len(raw_projects)} projects, {new_count} new (total: {len(all_projects)})")

    # ── Summary ────────────────────────────────────────────────────────
    logger.info(f"\n{'='*80}")
    logger.info("SEARCH COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Total queries: {len(queries)}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Empty results: {empty}")
    logger.info(f"Total unique projects: {len(all_projects)}")
    logger.info(f"Output: {OUTPUT_CSV_FINAL}")

    # Province breakdown
    prov_counts: dict[str, int] = {}
    for p in all_projects:
        prov = p["province"]
        prov_counts[prov] = prov_counts.get(prov, 0) + 1
    logger.info("\nBy province:")
    for prov, count in sorted(prov_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {prov}: {count}")

    # Sector breakdown
    sector_counts: dict[str, int] = {}
    for p in all_projects:
        sec = p["sector"]
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
    logger.info("\nBy sector:")
    for sec, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {sec}: {count}")


if __name__ == "__main__":
    main()
