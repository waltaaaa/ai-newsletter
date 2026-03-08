"""
known_project_sweep.py — One-time comprehensive sweep for ALL active
Canadian capital projects, regardless of announcement date.

Unlike the weekly compound queries (which use a 4-week lookback),
these queries ask for everything currently proposed, approved, or
under construction. This catches projects announced months or years
ago that the weekly pipeline would never find.

Run ONCE via:  python update_dashboard.py --known-sweep
Results enter the standard dedup pipeline.
Budget: Uses ~200 Gemini queries over 1-2 days from the 75/day buffer.
"""

import asyncio
import aiohttp
import logging
import os
import sys

logger = logging.getLogger(__name__)

PROVINCES = {
    "ON": "Ontario", "QC": "Quebec", "AB": "Alberta", "BC": "British Columbia",
    "SK": "Saskatchewan", "MB": "Manitoba", "NS": "Nova Scotia",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "PE": "Prince Edward Island", "YT": "Yukon",
    "NT": "Northwest Territories", "NU": "Nunavut",
}

SECTORS_18 = [
    "oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
    "transport_logistics", "healthcare", "education", "residential",
    "commercial_mixed", "agriculture", "forestry", "defence", "telecom",
    "indigenous", "environment", "tourism_culture", "government",
]

SECTOR_NAMES = {
    "oil_gas": "oil, gas, hydrogen, LNG, pipeline, refinery, and carbon capture",
    "mining": "mining, critical minerals, smelting, and mineral processing",
    "infrastructure": "highways, bridges, transit, water treatment, flood protection, and municipal infrastructure",
    "power_energy": "power generation, transmission, solar, wind, hydro, nuclear, SMR, battery storage, and grid modernization",
    "manufacturing": "manufacturing, factories, data centres, EV battery plants, semiconductor, food processing, and pharmaceutical",
    "transport_logistics": "airports, ports, rail, ferry terminals, logistics hubs, and intermodal facilities",
    "healthcare": "hospitals, medical centres, long-term care, mental health facilities, and health science centres",
    "education": "schools, universities, colleges, research centres, and campus construction",
    "residential": "residential towers, housing developments, affordable housing, office-to-residential conversions, and adaptive reuse for housing",
    "commercial_mixed": "mixed-use developments, commercial towers, entertainment districts, convention centres, sports arenas, downtown redevelopments, waterfront revitalizations, and mall transformations",
    "agriculture": "grain terminals, food processing plants, greenhouses, fertilizer plants, and aquaculture",
    "forestry": "sawmills, pulp mills, mass timber manufacturing, and biomass plants",
    "defence": "military bases, naval shipyards, coast guard, RCMP, correctional facilities, and border crossings",
    "telecom": "data centres, fibre optic networks, broadband, 5G, satellite ground stations, and AI computing facilities",
    "indigenous": "First Nations housing, on-reserve water treatment, Indigenous cultural centres, clean energy, and economic reconciliation projects",
    "environment": "recycling facilities, waste-to-energy, brownfield remediation, contaminated site cleanup, and mine reclamation",
    "tourism_culture": "museums, performing arts centres, recreation centres, ski resorts, casinos, heritage restorations, and park revitalizations",
    "government": "courthouses, government buildings, fire stations, Parliament renovations, civic centres, and seismic upgrades",
}

# ── Extended seed list of known major projects ──────────────────────────────

ADDITIONAL_KNOWN_PROJECTS = [
    # Manitoba
    {"name": "Portage Place Redevelopment", "province": "MB", "city": "Winnipeg", "value_millions": 650, "sector": "commercial_mixed", "project_type": "redevelopment", "status": "under_construction"},
    {"name": "The Forks Market Renovation", "province": "MB", "city": "Winnipeg", "value_millions": None, "sector": "tourism_culture", "project_type": "major_renovation", "status": "under_construction"},
    {"name": "Wehwehneh Bahgahkinahgohn", "province": "MB", "city": "Winnipeg", "value_millions": 140, "sector": "indigenous", "project_type": "adaptive_reuse", "status": "under_construction"},
    {"name": "Manitoba Museum Transformation", "province": "MB", "city": "Winnipeg", "value_millions": 165, "sector": "tourism_culture", "project_type": "major_renovation", "status": "under_construction"},

    # Ontario
    {"name": "Ontario Place Redevelopment", "province": "ON", "city": "Toronto", "value_millions": 3500, "sector": "commercial_mixed", "project_type": "redevelopment", "status": "approved"},
    {"name": "Ontario Line", "province": "ON", "city": "Toronto", "value_millions": 19000, "sector": "infrastructure", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Eglinton Crosstown LRT", "province": "ON", "city": "Toronto", "value_millions": 12800, "sector": "infrastructure", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Scarborough Subway Extension", "province": "ON", "city": "Toronto", "value_millions": 5500, "sector": "infrastructure", "project_type": "expansion", "status": "under_construction"},
    {"name": "Finch West LRT", "province": "ON", "city": "Toronto", "value_millions": 2500, "sector": "infrastructure", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Yonge North Subway Extension", "province": "ON", "city": "Toronto", "value_millions": 5600, "sector": "infrastructure", "project_type": "expansion", "status": "under_construction"},
    {"name": "LeBreton Flats", "province": "ON", "city": "Ottawa", "value_millions": 4000, "sector": "commercial_mixed", "project_type": "redevelopment", "status": "under_construction"},
    {"name": "Zibi Development", "province": "ON", "city": "Ottawa", "value_millions": 1500, "sector": "commercial_mixed", "project_type": "remediation", "status": "under_construction"},
    {"name": "Parliament Hill Rehabilitation", "province": "ON", "city": "Ottawa", "value_millions": 5000, "sector": "government", "project_type": "restoration", "status": "under_construction"},
    {"name": "SickKids Project Horizon", "province": "ON", "city": "Toronto", "value_millions": 1300, "sector": "healthcare", "project_type": "expansion", "status": "under_construction"},
    {"name": "VIA HFR (High Frequency Rail)", "province": "ON", "city": "National", "value_millions": 12000, "sector": "infrastructure", "project_type": "greenfield", "status": "proposed"},
    {"name": "Gordie Howe International Bridge", "province": "ON", "city": "Windsor", "value_millions": 6400, "sector": "infrastructure", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Ring of Fire Road Infrastructure", "province": "ON", "city": "Northern Ontario", "value_millions": 3500, "sector": "infrastructure", "project_type": "greenfield", "status": "proposed"},

    # Quebec
    {"name": "REM (Réseau express métropolitain)", "province": "QC", "city": "Montreal", "value_millions": 7950, "sector": "infrastructure", "project_type": "greenfield", "status": "under_construction"},
    {"name": "REM de l'Est", "province": "QC", "city": "Montreal", "value_millions": 10000, "sector": "infrastructure", "project_type": "greenfield", "status": "proposed"},
    {"name": "Blue Line Extension", "province": "QC", "city": "Montreal", "value_millions": 6400, "sector": "infrastructure", "project_type": "expansion", "status": "under_construction"},
    {"name": "New Champlain Bridge / Samuel De Champlain", "province": "QC", "city": "Montreal", "value_millions": 4200, "sector": "infrastructure", "project_type": "decommission_replace", "status": "completed"},
    {"name": "CHUM Hospital", "province": "QC", "city": "Montreal", "value_millions": 3600, "sector": "healthcare", "project_type": "greenfield", "status": "completed"},
    {"name": "Contrecoeur Container Terminal", "province": "QC", "city": "Contrecoeur", "value_millions": 950, "sector": "transport_logistics", "project_type": "expansion", "status": "under_construction"},
    {"name": "Northvolt Battery Plant", "province": "QC", "city": "McMasterville", "value_millions": 7000, "sector": "manufacturing", "project_type": "greenfield", "status": "delayed"},

    # Alberta
    {"name": "Calgary Event Centre", "province": "AB", "city": "Calgary", "value_millions": 800, "sector": "commercial_mixed", "project_type": "decommission_replace", "status": "under_construction"},
    {"name": "Calgary Green Line LRT", "province": "AB", "city": "Calgary", "value_millions": 5500, "sector": "infrastructure", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Edmonton Valley Line West LRT", "province": "AB", "city": "Edmonton", "value_millions": 2600, "sector": "infrastructure", "project_type": "expansion", "status": "under_construction"},
    {"name": "Trans Mountain Expansion", "province": "AB", "city": "Edmonton to Burnaby", "value_millions": 34200, "sector": "oil_gas", "project_type": "expansion", "status": "completed"},

    # British Columbia
    {"name": "LNG Canada Phase 1", "province": "BC", "city": "Kitimat", "value_millions": 40000, "sector": "oil_gas", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Coastal GasLink Pipeline", "province": "BC", "city": "Dawson Creek to Kitimat", "value_millions": 14500, "sector": "oil_gas", "project_type": "greenfield", "status": "completed"},
    {"name": "Site C Dam", "province": "BC", "city": "Peace River", "value_millions": 16000, "sector": "power_energy", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Broadway SkyTrain Extension", "province": "BC", "city": "Vancouver", "value_millions": 2830, "sector": "infrastructure", "project_type": "expansion", "status": "under_construction"},
    {"name": "SkyTrain Surrey-Langley Extension", "province": "BC", "city": "Surrey", "value_millions": 4000, "sector": "infrastructure", "project_type": "expansion", "status": "under_construction"},
    {"name": "Roberts Bank Terminal 2", "province": "BC", "city": "Delta", "value_millions": 3500, "sector": "transport_logistics", "project_type": "expansion", "status": "approved"},
    {"name": "Woodfibre LNG", "province": "BC", "city": "Squamish", "value_millions": 3000, "sector": "oil_gas", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Cedar LNG", "province": "BC", "city": "Kitimat", "value_millions": 3000, "sector": "oil_gas", "project_type": "greenfield", "status": "approved"},
    {"name": "Pattullo Bridge Replacement", "province": "BC", "city": "New Westminster", "value_millions": 1377, "sector": "infrastructure", "project_type": "decommission_replace", "status": "under_construction"},

    # Saskatchewan
    {"name": "BHP Jansen Potash Mine", "province": "SK", "city": "Jansen", "value_millions": 12000, "sector": "mining", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Regina Bypass", "province": "SK", "city": "Regina", "value_millions": 1880, "sector": "infrastructure", "project_type": "greenfield", "status": "completed"},

    # Nova Scotia
    {"name": "Halifax Cogswell District", "province": "NS", "city": "Halifax", "value_millions": 2000, "sector": "commercial_mixed", "project_type": "redevelopment", "status": "under_construction"},
    {"name": "Irving Shipbuilding — CSC Program", "province": "NS", "city": "Halifax", "value_millions": 60000, "sector": "defence", "project_type": "greenfield", "status": "under_construction"},

    # New Brunswick
    {"name": "Point Lepreau SMR", "province": "NB", "city": "Point Lepreau", "value_millions": 3000, "sector": "power_energy", "project_type": "expansion", "status": "proposed"},

    # Newfoundland
    {"name": "Bay du Nord Offshore", "province": "NL", "city": "Offshore", "value_millions": 12000, "sector": "oil_gas", "project_type": "greenfield", "status": "approved"},
    {"name": "Muskrat Falls", "province": "NL", "city": "Churchill Falls", "value_millions": 13000, "sector": "power_energy", "project_type": "greenfield", "status": "completed"},

    # National / Federal
    {"name": "Canadian Surface Combatant", "province": "NS", "city": "Halifax", "value_millions": 77300, "sector": "defence", "project_type": "greenfield", "status": "under_construction"},
    {"name": "Arctic Offshore Patrol Ships", "province": "NS", "city": "Halifax", "value_millions": 4300, "sector": "defence", "project_type": "greenfield", "status": "under_construction"},

    # Territories
    {"name": "Diavik Mine Closure", "province": "NT", "city": "Lac de Gras", "value_millions": 1000, "sector": "environment", "project_type": "remediation", "status": "under_construction"},
]


# ── Sweep query generator ──────────────────────────────────────────────────

def generate_sweep_queries():
    """Generate comprehensive sweep queries — no time constraint."""
    queries = []

    # Province × sector (top 5 get all 18 sectors, rest get top 10)
    top_provinces = ["ON", "QC", "AB", "BC", "SK"]

    for prov_code, prov_name in PROVINCES.items():
        sectors = SECTORS_18 if prov_code in top_provinces else SECTORS_18[:10]

        for sector in sectors:
            queries.append({
                "query": (
                    f"List ALL major {SECTOR_NAMES[sector]} projects in {prov_name}, Canada "
                    f"that are currently proposed, approved, under construction, or recently "
                    f"completed (within the past 2 years). Include projects at ANY stage "
                    f"regardless of when they were first announced. Include both new builds "
                    f"and redevelopments, renovations, expansions, conversions, and adaptive reuse. "
                    f"For each: project name, proponent/developer, city, estimated value in dollars, "
                    f"current status, project type, and the source URL for the information."
                ),
                "province": prov_code,
                "sector": sector,
                "language": "en",
                "geo_tier": "sweep",
                "type": "known_project_sweep",
            })

    # CMA sweeps for top 20 cities
    top_cmas = [
        "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
        "Ottawa-Gatineau", "Winnipeg", "Quebec City", "Hamilton", "Halifax",
        "Kitchener-Waterloo", "Victoria", "Saskatoon", "Regina", "St. John's",
        "London Ontario", "Windsor Ontario", "Moncton", "Fredericton", "Charlottetown",
    ]

    for cma in top_cmas:
        queries.append({
            "query": (
                f"List ALL major capital projects currently active in {cma} and surrounding area. "
                f"Include everything proposed, approved, under construction, or completed in "
                f"the past 2 years. Cover all sectors: infrastructure, transit, healthcare, "
                f"education, housing, commercial development, mixed-use, redevelopments, "
                f"revitalizations, renovations, conversions, and adaptive reuse projects. "
                f"Include projects of any size above $10 million. "
                f"For each: project name, proponent, specific location, estimated value, "
                f"status, project type (new build or brownfield subtype), and source URL."
            ),
            "cma": cma,
            "sector": "all_sectors",
            "language": "en",
            "geo_tier": "sweep",
            "type": "known_project_sweep",
        })

    # French sweeps for QC and NB
    for prov_code, geo_name in [("QC", "au Québec"), ("NB", "au Nouveau-Brunswick")]:
        queries.append({
            "query": (
                f"Énumérez TOUS les projets majeurs d'immobilisations actuellement actifs "
                f"{geo_name}. Incluez tout ce qui est proposé, approuvé, en construction ou "
                f"achevé au cours des deux dernières années. Couvrez tous les secteurs : "
                f"infrastructure, transport, santé, éducation, habitation, développement "
                f"commercial, usage mixte, réaménagements, revitalisations, rénovations, "
                f"conversions et réutilisations adaptatives. "
                f"Pour chaque projet : nom, promoteur, emplacement, valeur estimée, "
                f"statut, type de projet et URL source."
            ),
            "province": prov_code,
            "sector": "all_sectors",
            "language": "fr",
            "geo_tier": "sweep",
            "type": "known_project_sweep",
        })

    # Specific known-project queries
    known_missing = [
        "Portage Place Redevelopment Winnipeg Manitoba",
        "The Forks Winnipeg Manitoba development projects",
        "Winnipeg major construction and redevelopment projects currently active",
        "Manitoba major capital projects 2024 2025 2026",
        "Canadian major infrastructure projects currently under construction 2026",
        "Canada largest construction projects currently active billion dollar",
        "Canadian megaprojects under construction 2026",
        "ReNew Canada Top 100 infrastructure projects 2025 2026",
        "Major brownfield redevelopment projects Canada currently active",
        "Office to residential conversions Canada active projects",
        "Canadian arena stadium entertainment district projects active",
        "Major hospital construction projects Canada 2025 2026",
        "Canadian LRT subway transit projects under construction",
        "Major mining projects Canada under construction or approved",
        "Canadian data centre projects announced or under construction",
        "First Nations Indigenous infrastructure projects Canada major",
    ]

    for kp in known_missing:
        queries.append({
            "query": (
                f"Find information about: {kp}. "
                f"List all matching projects with: project name, proponent, location "
                f"(city, province), estimated value in dollars, current status, "
                f"project type, description, and source URL."
            ),
            "sector": "known_sweep",
            "language": "en",
            "geo_tier": "sweep",
            "type": "known_project_sweep",
        })

    logger.info(f"Generated {len(queries)} sweep queries")
    return queries


# ── Seed known projects ────────────────────────────────────────────────────

def seed_known_projects(db):
    """Write ADDITIONAL_KNOWN_PROJECTS to Firestore via standard dedup pipeline.

    Each project gets confidence=0.3 and needs_enrichment=True so the
    enrichment pipeline fills in current status and source URLs.
    """
    from project_sync import upsert_flat_projects

    tagged = []
    for p in ADDITIONAL_KNOWN_PROJECTS:
        proj = dict(p)
        proj['discovery_source'] = 'known_project_sweep'
        proj['discovery_sources'] = ['known_project_sweep']
        proj['confidence'] = 0.3
        proj['needs_enrichment'] = True
        if proj.get('value_millions'):
            proj['value'] = f"C${proj['value_millions'] / 1000:.1f}B" if proj['value_millions'] >= 1000 else f"C${proj['value_millions']:.0f}M"
        tagged.append(proj)

    print(f"\n[KNOWN-SWEEP] Seeding {len(tagged)} known projects...")
    upsert_flat_projects(db, tagged)
    print(f"[KNOWN-SWEEP] Seed complete: {len(tagged)} projects upserted")
    return len(tagged)


# ── Async Gemini sweep ─────────────────────────────────────────────────────

# Reuse extraction prompt from compound_discovery
SWEEP_SYSTEM_PROMPT = """You are a Canadian capital projects research assistant. Find and list major capital projects based on the user's query.

Return a JSON object with this structure:
{
  "projects": [
    {
      "name": "Project name",
      "proponent": "Company or organization",
      "location": {
        "city": "City name",
        "province": "Two-letter code (ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU)",
        "cma": "Census Metropolitan Area name or null"
      },
      "value_millions": 650,
      "currency": "CAD",
      "status": "proposed | approved | under_construction | completed | delayed | cancelled | on_hold",
      "project_type": "greenfield | redevelopment | adaptive_reuse | major_renovation | expansion | retrofit | restoration | remediation | conversion | modernization | decommission_replace",
      "sector": "Sector description",
      "naics_2digit": "Best-fit 2-digit NAICS code",
      "description": "One-sentence project description",
      "source_url": "URL of the source article or announcement",
      "source_name": "Publication or organization name",
      "date_reported": "YYYY-MM-DD",
      "confidence_notes": "Any caveats (unconfirmed value, rumoured, etc.)"
    }
  ]
}

RULES:
1. Only include projects with VERIFIED information from search results. Never fabricate.
2. If no matching projects found, return {"projects": []}.
3. Include BOTH greenfield (new builds) AND brownfield (redevelopments, renovations, expansions, conversions, adaptive reuse, modernizations).
4. Always include source_url with a real, complete URL starting with https://. If you cannot provide a real source URL, DO NOT include that project.
5. Values in millions CAD. Note approximations in confidence_notes.
6. Return ONLY the JSON object. No markdown, no preamble.
7. Every project MUST have a name and source_url at minimum.
8. This is a COMPREHENSIVE sweep — include ALL projects you can find, even older ones still active."""


async def _query_one(session, semaphore, query_obj):
    """Send one sweep query to Gemini via gemini_engine."""
    from gemini_engine import query_one
    try:
        result = await query_one(session, semaphore, query_obj, SWEEP_SYSTEM_PROMPT)
        if result.get("error"):
            logger.warning(f"Sweep query error: {result['error']}")
            return []
        return _parse_projects(result, query_obj)
    except Exception as e:
        logger.warning(f"Sweep query exception: {e}")
        return []


def _parse_projects(result, query_obj):
    """Parse structured project JSON from Gemini response."""
    import json
    import re

    text = result.get("text", "")
    grounding_urls = result.get("grounding_urls", [])

    # Extract JSON from response
    projects = []
    try:
        # Try direct parse
        data = json.loads(text)
        projects = data.get("projects", [])
    except json.JSONDecodeError:
        # Try extracting JSON block
        match = re.search(r'\{[\s\S]*"projects"[\s\S]*\}', text)
        if match:
            try:
                data = json.loads(match.group())
                projects = data.get("projects", [])
            except json.JSONDecodeError:
                pass

    # Tag each project
    tagged = []
    for p in projects:
        if not p.get("name"):
            continue
        if not p.get("source_url"):
            # Try to assign a grounding URL
            if grounding_urls:
                p["source_url"] = grounding_urls[0].get("url", "")
            else:
                continue  # skip projects without any URL

        # Normalize location
        loc = p.get("location", {})
        if isinstance(loc, dict):
            p["city"] = loc.get("city", "")
            p["province"] = loc.get("province", query_obj.get("province", ""))
            p["cma"] = loc.get("cma")
        elif not p.get("province"):
            p["province"] = query_obj.get("province", "")

        p["discovery_source"] = "known_project_sweep"
        p["discovery_sources"] = ["known_project_sweep"]
        p["_discovery_tier"] = "known_project_sweep"
        p["needs_enrichment"] = True

        # Build evidence
        p["_evidence"] = [{
            "url": p.get("source_url", ""),
            "name": p.get("source_name", "Gemini Sweep"),
            "source_type": "search",
        }]

        tagged.append(p)

    return tagged


async def run_known_project_sweep():
    """Run the comprehensive sweep asynchronously.

    Returns dict with counts: {"mentions": N, "unique": M}
    """
    queries = generate_sweep_queries()
    logger.info(f"[KNOWN-SWEEP] Running {len(queries)} queries...")
    print(f"\n[KNOWN-SWEEP] Starting comprehensive sweep: {len(queries)} queries")

    semaphore = asyncio.Semaphore(15)
    all_projects = []

    async with aiohttp.ClientSession() as session:
        tasks = [_query_one(session, semaphore, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            continue
        if isinstance(result, list):
            all_projects.extend(result)

    print(f"[KNOWN-SWEEP] Found {len(all_projects)} project mentions")
    logger.info(f"Sweep found {len(all_projects)} project mentions")

    return all_projects


def run_known_project_sweep_sync(db):
    """Synchronous wrapper: sweep + dedup + Firestore write."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            all_projects = loop.run_until_complete(run_known_project_sweep())
        else:
            all_projects = asyncio.run(run_known_project_sweep())
    except RuntimeError:
        all_projects = asyncio.run(run_known_project_sweep())

    if not all_projects:
        print("[KNOWN-SWEEP] No projects found")
        return {"mentions": 0, "unique": 0}

    # Dedup
    from project_dedup import deduplicate_projects
    deduped = deduplicate_projects(all_projects)
    print(f"[KNOWN-SWEEP] After dedup: {len(deduped)} unique projects")

    # Write to SQLite
    from project_sync import upsert_flat_projects
    upsert_flat_projects(db, deduped)
    print(f"[KNOWN-SWEEP] Written to SQLite: {len(deduped)} projects")

    return {"mentions": len(all_projects), "unique": len(deduped)}


# ── Standalone execution ───────────────────────────────────────────────────
# NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
# This is a one-time sweep script.

if __name__ == "__main__":
    from dotenv import load_dotenv
    from db import init_db as _init_db

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    db = _init_db()

    if "--seed-only" in sys.argv:
        seed_known_projects(db)
    else:
        seed_known_projects(db)
        result = run_known_project_sweep_sync(db)
        print(f"\nSweep complete: {result}")

    db.close()
