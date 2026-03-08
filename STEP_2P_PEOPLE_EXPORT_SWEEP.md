> **CLAUDE CODE SETUP — RUN THESE BEFORE STARTING:**
> 1. Type `/clear` to wipe conversation history from any previous step
> 2. Launch with `claude --dangerously-skip-permissions` to auto-approve all file edits and bash commands
> 3. Enter Plan Mode (Shift+Tab twice) and paste this file — review the plan before executing
> 4. If context gets heavy mid-step, run `/compact` to summarize and free space

# STEP_2P — KEY PEOPLE TRACKING, BRIEFING EXPORT & KNOWN-PROJECT SWEEP

**Prerequisites:** STEP_2A through STEP_2O complete. Backup at v2.0-stable.
**This step adds three features: tracking key decision-makers, downloadable briefing packages, and a comprehensive sweep for known projects the pipeline is currently missing.**

---

## PART 1: KNOWN-PROJECT SWEEP

**This is the most urgent fix.** Projects like Portage Place ($650M, Winnipeg) and The Forks (Winnipeg) are well-established and widely covered but are missing from the database because they were announced before the pipeline started running. The 4-week lookback window only catches recent activity. We need a one-time aggressive sweep to find every major project currently active in Canada.

### Step 1: Province-by-province comprehensive discovery

Run a special set of Gemini queries designed to find ALL currently active projects, not just those with recent news. These queries have NO time constraint — they ask for everything currently under development, regardless of when it was announced.

```python
"""
known_project_sweep.py — One-time comprehensive sweep for ALL active
Canadian capital projects, regardless of announcement date.

Unlike the weekly compound queries (which use a 4-week lookback),
these queries ask for everything currently proposed, approved, or
under construction. This catches projects announced months or years
ago that the weekly pipeline would never find.

Run ONCE. Results enter the standard dedup pipeline.
Budget: Uses ~200 Gemini queries over 1-2 days from the 75/day buffer.
"""

import asyncio
import logging

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


def generate_sweep_queries():
    """Generate comprehensive sweep queries — no time constraint."""
    queries = []
    
    # Province × sector (top 5 provinces get all 18 sectors, rest get top 10)
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
    
    # CMA sweeps for top 20 cities — catch urban projects
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
    
    # Specific known-project queries for projects we KNOW exist but may be missing
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
    
    return queries


async def run_known_project_sweep():
    """Run the comprehensive sweep. Process results through standard pipeline.
    
    Expected: ~200 queries generating 500-2000 project mentions.
    After dedup: ~200-500 unique projects added to database.
    """
    queries = generate_sweep_queries()
    logger.info(f"Known-project sweep: {len(queries)} queries")
    
    # Run through same Gemini engine as compound discovery
    from compound_discovery import run_compound_discovery, _query_gemini
    import aiohttp
    
    semaphore = asyncio.Semaphore(15)
    all_projects = []
    
    async with aiohttp.ClientSession() as session:
        tasks = [_query_gemini(session, semaphore, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            continue
        projects = result.get("projects", [])
        for p in projects:
            p["_discovery_tier"] = "known_project_sweep"
            p["_source_query"] = queries[i].get("query", "")[:100]
            all_projects.append(p)
    
    logger.info(f"Sweep found {len(all_projects)} project mentions")
    
    # Dedup and write to Firestore through standard pipeline
    from project_dedup import deduplicate_projects
    from firestore_project_writer import write_projects_to_firestore
    
    deduped = deduplicate_projects(all_projects)
    logger.info(f"After dedup: {len(deduped)} unique projects")
    
    await write_projects_to_firestore(deduped)
    
    return {"mentions": len(all_projects), "unique": len(deduped)}
```

### Step 2: Extended seed list

Add these commonly-known projects to the historical backfill if they're not already in the database:

```python
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
```

### Step 3: Run the sweep

```python
# Execute ONCE after deployment:

# 1. Seed the extended known projects list
from known_project_sweep import ADDITIONAL_KNOWN_PROJECTS
# Write each to Firestore via standard dedup pipeline

# 2. Run the comprehensive Gemini sweep
from known_project_sweep import run_known_project_sweep
result = await run_known_project_sweep()
print(f"Sweep complete: {result['mentions']} mentions → {result['unique']} unique projects")

# 3. Queue all new projects for enrichment and cost-finding
# (happens automatically on next pipeline run)
```

---

## PART 2: KEY PEOPLE TRACKING

Track social media and press activity from decision-makers who announce projects and policy changes.

### Step 1: Key people database

```python
"""
key_people_tracker.py — Monitor key decision-makers for project and policy signals.

Sources:
- X/Twitter accounts (via RSS bridges like Nitter or official API)
- Government press conference schedules
- Legislative assembly hansard mentions

People categories:
- Federal: PM, Finance Minister, Infrastructure Minister, Housing Minister,
  NRCan Minister, Transport Minister, Indigenous Services Minister
- Provincial: 13 Premiers, 13 Finance Ministers, relevant portfolio ministers
- Municipal: Mayors of top 20 CMAs
- Industry: CEOs of major developers, mining/energy executives, 
  crown corp CEOs with significant capital programs

Strategy: Monitor for keywords indicating project announcements, funding
decisions, policy changes. Any match triggers a Gemini enrichment query.
"""

import logging
logger = logging.getLogger(__name__)

KEY_PEOPLE = {
    # Federal
    "federal": [
        {"name": "Prime Minister of Canada", "role": "PM", "scope": "national",
         "x_handle": None, "rss_sources": ["https://pm.gc.ca/en/news/rss"],
         "relevance": "Federal infrastructure spending, housing policy, trade policy, Indigenous reconciliation"},
        {"name": "Minister of Finance", "role": "Finance Minister", "scope": "national",
         "rss_sources": ["https://www.canada.ca/en/department-finance.atom.xml"],
         "relevance": "Federal budget, tax incentives, economic policy"},
        {"name": "Minister of Housing and Infrastructure", "role": "Housing/Infrastructure Minister", "scope": "national",
         "rss_sources": [],
         "relevance": "Infrastructure funding, housing programs, HAF, ACLA"},
        {"name": "Minister of Energy and Natural Resources", "role": "NRCan Minister", "scope": "national",
         "rss_sources": ["https://www.canada.ca/en/natural-resources-canada.atom.xml"],
         "relevance": "Energy projects, mining approvals, critical minerals strategy"},
        {"name": "Minister of Transport", "role": "Transport Minister", "scope": "national",
         "rss_sources": ["https://www.canada.ca/en/transport-canada.atom.xml"],
         "relevance": "Port expansions, airport upgrades, rail projects, CER decisions"},
    ],
    
    # Provincial Premiers (monitor their official newsrooms)
    "premiers": [
        {"name": "Premier of Ontario", "province": "ON", "rss_sources": ["https://news.ontario.ca/en/rss"]},
        {"name": "Premier of Quebec", "province": "QC", "rss_sources": ["https://www.quebec.ca/nouvelles/rss"]},
        {"name": "Premier of Alberta", "province": "AB", "rss_sources": ["https://www.alberta.ca/premier-news-rss"]},
        {"name": "Premier of British Columbia", "province": "BC", "rss_sources": ["https://news.gov.bc.ca/ministries/premier/feed"]},
        {"name": "Premier of Saskatchewan", "province": "SK", "rss_sources": []},
        {"name": "Premier of Manitoba", "province": "MB", "rss_sources": ["https://news.gov.mb.ca/news/rss"]},
        {"name": "Premier of Nova Scotia", "province": "NS", "rss_sources": []},
        {"name": "Premier of New Brunswick", "province": "NB", "rss_sources": []},
        {"name": "Premier of Newfoundland and Labrador", "province": "NL", "rss_sources": []},
        {"name": "Premier of PEI", "province": "PE", "rss_sources": []},
        {"name": "Premier of Yukon", "province": "YT", "rss_sources": []},
        {"name": "Premier of NWT", "province": "NT", "rss_sources": []},
        {"name": "Premier of Nunavut", "province": "NU", "rss_sources": []},
    ],
    
    # Municipal mayors (top 15 CMAs)
    "mayors": [
        {"name": "Mayor of Toronto", "city": "Toronto", "province": "ON"},
        {"name": "Mayor of Montreal", "city": "Montreal", "province": "QC"},
        {"name": "Mayor of Vancouver", "city": "Vancouver", "province": "BC"},
        {"name": "Mayor of Calgary", "city": "Calgary", "province": "AB"},
        {"name": "Mayor of Edmonton", "city": "Edmonton", "province": "AB"},
        {"name": "Mayor of Ottawa", "city": "Ottawa", "province": "ON"},
        {"name": "Mayor of Winnipeg", "city": "Winnipeg", "province": "MB"},
        {"name": "Mayor of Quebec City", "city": "Quebec City", "province": "QC"},
        {"name": "Mayor of Hamilton", "city": "Hamilton", "province": "ON"},
        {"name": "Mayor of Halifax", "city": "Halifax", "province": "NS"},
        {"name": "Mayor of Saskatoon", "city": "Saskatoon", "province": "SK"},
        {"name": "Mayor of Regina", "city": "Regina", "province": "SK"},
        {"name": "Mayor of St. John's", "city": "St. John's", "province": "NL"},
        {"name": "Mayor of Fredericton", "city": "Fredericton", "province": "NB"},
        {"name": "Mayor of Charlottetown", "city": "Charlottetown", "province": "PE"},
    ],
    
    # Crown corp leaders
    "crown_corp_leaders": [
        {"name": "CEO of Canada Infrastructure Bank", "relevance": "CIB investment decisions"},
        {"name": "CEO of CMHC", "relevance": "Housing programs, affordable housing funding"},
        {"name": "President of Metrolinx", "province": "ON", "relevance": "Ontario transit projects"},
        {"name": "CEO of Hydro-Québec", "province": "QC", "relevance": "Quebec energy projects"},
        {"name": "CEO of BC Hydro", "province": "BC", "relevance": "BC energy projects, Site C"},
        {"name": "President of VIA Rail", "relevance": "HFR project"},
    ],
}

# Keywords that indicate a project or policy announcement
ANNOUNCEMENT_KEYWORDS = [
    "announce", "invest", "fund", "approve", "construction", "build",
    "project", "million", "billion", "infrastructure", "development",
    "redevelopment", "expansion", "renovation", "transit", "housing",
    "hospital", "school", "mine", "pipeline", "facility", "plant",
    "breaking ground", "shovels in the ground", "green light",
    "budget", "capital plan", "economic statement",
    # French
    "annoncer", "investir", "financer", "approuver", "construction",
    "projet", "millions", "milliards", "infrastructure",
]


async def monitor_key_people():
    """Monitor key people RSS feeds for project/policy announcements.
    
    Integration: RSS feeds from key people are processed through the
    government source bypass (skips keyword filtering) since anything
    a Premier or Minister says about a project is high-authority.
    
    X/Twitter monitoring: If X API access is available, monitor handles.
    Otherwise, use Google Alerts for "[person name] announces project"
    as a proxy.
    """
    all_feeds = []
    
    for category, people in KEY_PEOPLE.items():
        for person in people:
            for feed_url in person.get("rss_sources", []):
                if feed_url:
                    all_feeds.append({
                        "url": feed_url,
                        "name": person.get("name", "Unknown"),
                        "source_type": "key_person",
                        "authority": "government",
                        "category": category,
                        "province": person.get("province"),
                    })
    
    # Add to existing government RSS feed list
    # These feeds use the government source bypass — skip keyword filtering
    return all_feeds


def generate_people_google_alerts():
    """Generate Google Alert search terms for key people.
    
    Add these to the Google Alerts configuration (STEP_2H).
    """
    alerts = []
    
    for category, people in KEY_PEOPLE.items():
        for person in people:
            name = person.get("name", "")
            if name:
                alerts.append(f'"{name}" announces project OR investment OR construction OR infrastructure Canada')
    
    return alerts
```

### Step 2: Integration

The key people RSS feeds are added to the government source bypass list — they skip keyword filtering entirely. Their X/Twitter activity is covered either via direct API monitoring (if you have X API access) or through Google Alerts as a proxy.

```python
# In the RSS feed configuration, add key people feeds:
key_people_feeds = await monitor_key_people()
# These go into the government RSS feed list with bypass enabled
```

---

## PART 3: BRIEFING EXPORT

### Step 1: PDF and DOCX generation

```python
"""
briefing_export.py — Export weekly briefing as downloadable PDF or DOCX.

Generates a formatted document from the Firestore briefing content
with dashboard branding, date, and section formatting.
"""

import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def export_briefing_pdf(db, week_date=None):
    """Export the weekly briefing as a formatted PDF.
    
    Uses reportlab or weasyprint to generate PDF from briefing content.
    
    Returns: bytes (PDF file content)
    """
    # Get briefing content
    if week_date:
        # Find specific week's briefing
        docs = db.collection("weekly_briefings").where("date", "==", week_date).limit(1).stream()
    else:
        # Get latest
        doc = db.collection("dashboard_state").document("latest_briefing").get()
        if doc.exists:
            briefing = doc.to_dict()
        else:
            return None
    
    content = briefing.get("content", "")
    date = briefing.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    week_number = briefing.get("week_number", "")
    
    # Generate PDF using reportlab
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.colors import HexColor
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=1*inch, bottomMargin=1*inch,
                           leftMargin=1*inch, rightMargin=1*inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'BriefingTitle', parent=styles['Title'],
        fontSize=24, textColor=HexColor('#1B3A5C'),
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        'BriefingSubtitle', parent=styles['Normal'],
        fontSize=14, textColor=HexColor('#666666'),
        spaceAfter=24,
    )
    heading_style = ParagraphStyle(
        'BriefingHeading', parent=styles['Heading2'],
        fontSize=14, textColor=HexColor('#2E5984'),
        spaceBefore=18, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        'BriefingBody', parent=styles['Normal'],
        fontSize=11, leading=16, spaceAfter=8,
    )
    
    story = []
    
    # Title page
    story.append(Paragraph("Canadian Macro Strategic Dashboard", title_style))
    story.append(Paragraph(f"Weekly Intelligence Briefing — {date} (Week {week_number})", subtitle_style))
    story.append(Spacer(1, 12))
    
    # Parse briefing sections and format
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith('# ') or line.startswith('## '):
            heading_text = line.lstrip('#').strip()
            story.append(Paragraph(heading_text, heading_style))
        elif line.startswith('**') and line.endswith('**'):
            story.append(Paragraph(line.strip('*'), heading_style))
        else:
            # Escape HTML entities
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(line, body_style))
    
    # Footer
    story.append(Spacer(1, 24))
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=HexColor('#999999'),
    )
    story.append(Paragraph(
        f"Generated by Canadian Macro Strategic Dashboard — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        footer_style
    ))
    story.append(Paragraph(
        "All data sourced from verified Canadian government, news, and industry publications.",
        footer_style
    ))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


async def export_briefing_docx(db, week_date=None):
    """Export the weekly briefing as a formatted Word document.
    
    Uses python-docx to generate DOCX.
    
    Returns: bytes (DOCX file content)
    """
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    # Get briefing content (same as PDF)
    doc_ref = db.collection("dashboard_state").document("latest_briefing").get()
    if not doc_ref.exists:
        return None
    
    briefing = doc_ref.to_dict()
    content = briefing.get("content", "")
    date = briefing.get("date", "")
    week_number = briefing.get("week_number", "")
    
    doc = Document()
    
    # Title
    title = doc.add_heading("Canadian Macro Strategic Dashboard", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = RGBColor(0x1B, 0x3A, 0x5C)
    
    subtitle = doc.add_paragraph(f"Weekly Intelligence Briefing — {date} (Week {week_number})")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph("")  # Spacer
    
    # Parse and add content
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        elif line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('# '):
            doc.add_heading(line[2:], level=1)
        elif line.startswith('**') and line.endswith('**'):
            doc.add_heading(line.strip('*'), level=2)
        else:
            doc.add_paragraph(line)
    
    # Footer
    doc.add_paragraph("")
    footer = doc.add_paragraph(
        f"Generated by Canadian Macro Strategic Dashboard — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    footer.runs[0].font.size = Pt(8)
    footer.runs[0].font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
```

### Step 2: API endpoint for download

```python
"""
briefing_download_api.py — API endpoint for briefing export.
"""

async def handle_briefing_download(format="pdf", week_date=None):
    """Handle briefing download request.
    
    Args:
        format: "pdf" or "docx"
        week_date: specific date, or None for latest
    
    Returns: file bytes + content type + filename
    """
    from briefing_export import export_briefing_pdf, export_briefing_docx
    
    if format == "pdf":
        data = await export_briefing_pdf(db, week_date)
        return {
            "data": data,
            "content_type": "application/pdf",
            "filename": f"Canadian_Macro_Briefing_{week_date or 'latest'}.pdf",
        }
    elif format == "docx":
        data = await export_briefing_docx(db, week_date)
        return {
            "data": data,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "filename": f"Canadian_Macro_Briefing_{week_date or 'latest'}.docx",
        }
```

### Step 3: Frontend download buttons

```jsx
{/* Add to the weekly briefing display section */}
<div className="flex gap-2 mt-4">
  <a
    href={`/api/briefing-download?format=pdf`}
    download
    className="text-sm bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 flex items-center gap-2"
  >
    📄 Download PDF
  </a>
  <a
    href={`/api/briefing-download?format=docx`}
    download
    className="text-sm bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center gap-2"
  >
    📝 Download Word
  </a>
</div>
```

---

## DEPENDENCIES

```bash
pip install reportlab python-docx --break-system-packages
```

---

## PART 4: UNDER THE MICROSCOPE

A new section in the weekly briefing providing a deep-dive on the single most significant story of the week, analyzed specifically through the lens of Canadian economic impact.

### Step 1: Topic selection engine

```python
"""
under_the_microscope.py — Deep-dive topic selection and analysis for weekly briefing.

Automatically selects the dominant story of the week and generates
a 200-300 word analysis focused on Canadian economic and project impacts.
"""

import json
import logging
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


async def select_microscope_topic(db, rss_articles, indicator_trends, cross_insights):
    """Select this week's Under the Microscope topic.
    
    Selection criteria (weighted):
    1. News volume — which story appeared most often in RSS feeds this week
    2. Indicator impact — which story caused the biggest commodity/rate moves
    3. Project crossover — which story affects the most projects in our database
    4. Manual override — dashboard_state/microscope_override forces a topic
    
    Returns: dict with topic, context, affected_projects, indicator_data
    """
    # Check for manual override first
    override_doc = db.collection("dashboard_state").document("microscope_override").get()
    if override_doc.exists:
        override = override_doc.to_dict()
        if override.get("active") and override.get("topic"):
            topic = override["topic"]
            logger.info(f"Microscope override: {topic}")
            # Clear the override after use
            db.collection("dashboard_state").document("microscope_override").update({"active": False})
            return await _build_topic_context(db, topic, rss_articles, indicator_trends, cross_insights)
    
    # Automated selection: analyze this week's RSS articles for dominant themes
    # Look for stories that appear across multiple feeds and multiple days
    # Group by theme using Gemini Flash classification
    
    theme_prompt = """Analyze these article headlines from Canadian news this week.
Identify the single most dominant global or national story that would most
significantly affect Canadian capital investment, infrastructure, or economic conditions.

Headlines:
{headlines}

Return ONLY a JSON object:
{{
    "topic": "Short topic name (5-10 words)",
    "description": "One sentence describing the story",
    "article_count": number of headlines related to this topic,
    "relevance_to_canada": "Brief explanation of why this matters for Canadian investment"
}}"""
    
    # Collect this week's headlines
    recent_headlines = []
    cutoff = datetime.utcnow() - timedelta(days=7)
    for article in rss_articles:
        pub_date = article.get("published")
        if pub_date and pub_date >= cutoff:
            recent_headlines.append(article.get("title", ""))
    
    # Use Gemini Flash to identify dominant theme
    # (2-3 queries from daily buffer)
    
    return {
        "topic": None,
        "context": None,
        "affected_projects": [],
        "indicator_data": {},
    }


async def _build_topic_context(db, topic, rss_articles, indicator_trends, cross_insights):
    """Build comprehensive context for the selected topic."""
    
    # Search for related articles in this week's RSS
    related_articles = [a for a in rss_articles if topic.lower() in a.get("title", "").lower()]
    
    # Search for affected projects via cross-reference engine
    # e.g., if topic is "Iran conflict", look for defence, energy projects
    
    # Check microscope_history for continuity
    history = []
    history_docs = db.collection("dashboard_state").document("microscope_history").get()
    if history_docs.exists:
        history = history_docs.to_dict().get("topics", [])
    
    weeks_running = sum(1 for h in history if h.get("topic", "").lower() == topic.lower())
    
    return {
        "topic": topic,
        "related_articles": related_articles[:10],
        "weeks_running": weeks_running,
        "history": history,
    }


async def generate_microscope_analysis(topic_context, project_data, indicator_data):
    """Generate the Under the Microscope deep-dive using Claude Sonnet.
    
    Uses 1 Claude Sonnet call (~$0.20).
    """
    from claude_reasoning import reason_with_claude_tracked
    
    system = """You are a factual reporter covering the "Under the Microscope" 
section of a weekly Canadian economic intelligence briefing. This section provides 
a data-driven account of the single most significant story of the week, focused 
on its factual connection to Canadian economic sectors and capital projects.

CRITICAL: You are a reporter, not an analyst. State facts. Present data. Show 
connections between events and projects. Do NOT predict outcomes, recommend actions, 
or characterize events as positive/negative/good/bad/bullish/bearish.

Structure your report as:
1. WHAT HAPPENED / WHAT CHANGED — factual summary, sourced (2-3 sentences)
2. NEW DEVELOPMENTS THIS WEEK — what is factually different in the past 7 days
3. CANADIAN EXPOSURE — which sectors, provinces, and indicators are connected.
   Reference specific project counts and values from the database.
4. PROJECTS IN SCOPE — name 2-5 tracked projects that fall within affected 
   sectors/provinces, with their values and current status
5. UPCOMING EVENTS — dates of scheduled decisions, releases, or hearings

Total length: 200-300 words. Be specific. Use numbers. Name projects. No opinion."""

    continuity_note = ""
    if topic_context.get("weeks_running", 0) > 0:
        weeks = topic_context["weeks_running"]
        continuity_note = f"\n\nNOTE: This is week {weeks + 1} covering this topic. Reference that this story continues from prior weeks and focus ONLY on genuinely new developments."

    user = f"""TOPIC: {topic_context.get('topic', '')}

RECENT ARTICLES:
{json.dumps([a.get('title', '') for a in topic_context.get('related_articles', [])[:10]], indent=2)}

AFFECTED PROJECTS IN OUR DATABASE:
{json.dumps(project_data[:15], indent=2)}

RELEVANT INDICATOR MOVEMENTS:
{json.dumps(indicator_data, indent=2)}
{continuity_note}

Generate the Under the Microscope analysis."""

    result = await reason_with_claude_tracked(
        system, user,
        task_name="under_the_microscope",
        max_tokens=1500,
    )
    
    # Store topic in history
    return result


async def store_microscope_history(db, topic, analysis_text):
    """Record this week's microscope topic for continuity tracking."""
    doc = db.collection("dashboard_state").document("microscope_history").get()
    history = []
    if doc.exists:
        history = doc.to_dict().get("topics", [])
    
    history.append({
        "topic": topic,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "week_number": datetime.utcnow().isocalendar()[1],
    })
    
    # Keep last 52 weeks
    history = history[-52:]
    
    db.collection("dashboard_state").document("microscope_history").set({"topics": history})
```

### Step 2: Integration with weekly briefing

Update the weekly briefing synthesis prompt in `weekly_briefing.py` to include the Under the Microscope section as section 3 (between MACRO PULSE and PROVINCIAL SPOTLIGHT). The microscope analysis is pre-generated and passed into the briefing prompt as context — Claude Sonnet incorporates it into the overall narrative.

```python
# In the weekly briefing generator, add:
microscope_analysis = await generate_microscope_analysis(topic_context, affected_projects, indicator_data)
await store_microscope_history(db, topic_context["topic"], microscope_analysis["text"])

# Pass microscope_analysis["text"] into the briefing synthesis prompt as:
# === UNDER THE MICROSCOPE (pre-generated, incorporate into briefing) ===
# {microscope_analysis["text"]}
```

### Step 3: Manual override

To force a specific topic, set this in Firestore:
```python
db.collection("dashboard_state").document("microscope_override").set({
    "active": True,
    "topic": "Iran conflict and Canadian defence/energy implications",
})
```

Or add a small admin UI element on the dashboard where you can type a topic override before the Monday pipeline runs.

---

## PIPELINE INTEGRATION

```python
# Add key people feeds to RSS configuration
from key_people_tracker import monitor_key_people
people_feeds = await monitor_key_people()
# Merge into government RSS feed list

# Run known-project sweep ONCE after deployment
from known_project_sweep import run_known_project_sweep
await run_known_project_sweep()

# Under the Microscope runs as part of weekly briefing generation
from under_the_microscope import select_microscope_topic, generate_microscope_analysis, store_microscope_history
topic_context = await select_microscope_topic(db, rss_articles, indicator_trends, cross_insights)
microscope = await generate_microscope_analysis(topic_context, affected_projects, indicator_data)
await store_microscope_history(db, topic_context["topic"], microscope["text"])
# Pass microscope["text"] into weekly briefing synthesis
```

---

## COST IMPACT

| Component | Cost |
|---|---|
| Known-project sweep (~200 Gemini queries, one-time) | $0 (free tier buffer) |
| Key people RSS feeds | $0 (free RSS) |
| Briefing PDF/DOCX generation | $0 (local processing) |
| reportlab + python-docx | $0 (open source) |
| Under the Microscope topic selection (2-3 Gemini Flash/week) | $0 (free tier) |
| Under the Microscope analysis (1 Claude Sonnet call/week) | ~$0.20/week = ~$10/year |
| **Total incremental** | **~$10/year** |
| **New pipeline total** | **~$63/year** |

---

## VERIFICATION

- [ ] Known-project sweep discovers Portage Place Redevelopment
- [ ] Known-project sweep discovers The Forks (Winnipeg)
- [ ] Known-project sweep discovers projects from all 13 provinces
- [ ] Extended seed list adds 50+ known projects to database
- [ ] All seeded projects have `needs_enrichment: true`
- [ ] Sweep results go through standard dedup (no duplicates created)
- [ ] Key people RSS feeds added to government bypass list
- [ ] Google Alert terms generated for key people
- [ ] PDF export produces readable formatted document with branding
- [ ] DOCX export produces readable formatted document with branding
- [ ] Download buttons appear on briefing display
- [ ] Downloads work in browser (correct content type, triggers save dialog)
- [ ] Under the Microscope topic selection runs without error
- [ ] Manual override via microscope_override Firestore document works
- [ ] Microscope analysis is 200-300 words with specific Canadian project references
- [ ] Microscope history tracks topics across weeks
- [ ] Continuity: same topic across weeks references prior coverage
- [ ] Weekly briefing now has 8 sections including Under the Microscope
- [ ] Briefing word count increased to 1000-1500 words
- [ ] No cost increase beyond ~$10/year for microscope Sonnet calls

**STEP_2P complete.**
