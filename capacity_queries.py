"""
capacity_queries.py -- Tiers 2, 3, 5, 6 query generators and runner.

Tier 2: Provincial broad sweeps (15 queries)
Tier 3: CMA deep dives (50 queries)
Tier 5: Federal/interprovincial (25 queries)
Tier 6: Emerging sector watchlists (25 queries)

All use the same EXTRACTION_SYSTEM_PROMPT as compound_discovery.py and return
project dicts compatible with upsert_flat_projects().
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


# ── Tier 2: Provincial Broad Sweeps ──────────────────────────────────────────

PROVINCES = {
    "ON": ("Ontario", 500), "QC": ("Quebec", 250), "AB": ("Alberta", 200),
    "BC": ("British Columbia", 175), "SK": ("Saskatchewan", 45),
    "MB": ("Manitoba", 40), "NS": ("Nova Scotia", 25),
    "NB": ("New Brunswick", 20), "NL": ("Newfoundland and Labrador", 17),
    "PE": ("Prince Edward Island", 5), "YT": ("Yukon", 3),
    "NT": ("Northwest Territories", 3), "NU": ("Nunavut", 3),
}


def build_provincial_sweep_queries():
    """Tier 2: 13 EN + 2 FR = 15 cross-sector sweep queries."""
    queries = []

    for code, (name, threshold) in PROVINCES.items():
        queries.append({
            "query": (
                f"List ALL major capital projects in {name}, Canada that have had "
                f"any news, announcements, approvals, construction milestones, delays, "
                f"cancellations, funding decisions, or status changes in the past four weeks. "
                f"Include projects from ALL sectors: infrastructure, energy, mining, oil and gas, "
                f"manufacturing, healthcare, education, housing, commercial development, "
                f"transit, ports, airports, telecommunications, data centres, Indigenous, "
                f"military, environmental, and cultural/recreation. "
                f"Include both new construction (greenfield) and redevelopments, renovations, "
                f"expansions, conversions, and adaptive reuse (brownfield). "
                f"Only include projects valued at C${threshold} million or above. "
                f"For each: project name, proponent, location, estimated value, sector, "
                f"current status, what changed recently, and the source URL."
            ),
            "province": name,
            "sector": "broad_sweep",
            "language": "en",
            "geo_tier": "provincial_sweep",
        })

    # French sweeps for QC and NB
    for code, geo_fr, threshold in [("QC", "au Quebec", 250), ("NB", "au Nouveau-Brunswick", 20)]:
        name = PROVINCES[code][0]
        queries.append({
            "query": (
                f"Enumerez TOUS les projets majeurs d'immobilisations {geo_fr} qui ont "
                f"fait l'objet de nouvelles, d'annonces, d'approbations, d'etapes de "
                f"construction, de retards, d'annulations ou de changements de statut au "
                f"cours des quatre dernieres semaines. Incluez tous les secteurs : "
                f"infrastructure, energie, mines, petrole et gaz, fabrication, sante, "
                f"education, habitation, developpement commercial, transport en commun, "
                f"ports, aeroports, telecommunications, centres de donnees, autochtone, "
                f"militaire, environnement et culture/loisirs. "
                f"Seulement les projets de {threshold} millions $ et plus. "
                f"Pour chaque projet : nom, promoteur, emplacement, valeur estimee, "
                f"secteur, statut actuel, changement recent et URL source."
            ),
            "province": name,
            "sector": "broad_sweep",
            "language": "fr",
            "geo_tier": "provincial_sweep",
        })

    return queries


# ── Tier 3: CMA Deep Dives ──────────────────────────────────────────────────

TOP_10_CMAS = [
    ("Toronto", "ON"), ("Montreal", "QC"), ("Vancouver", "BC"),
    ("Calgary", "AB"), ("Edmonton", "AB"), ("Ottawa-Gatineau", "ON"),
    ("Winnipeg", "MB"), ("Quebec City", "QC"), ("Hamilton", "ON"),
    ("Halifax", "NS"),
]

MEDIUM_CMAS = [
    ("Kitchener-Waterloo", "ON"), ("Victoria", "BC"), ("Saskatoon", "SK"),
    ("Regina", "SK"), ("St. John's", "NL"), ("London", "ON"),
    ("Windsor", "ON"), ("Oshawa-Durham", "ON"), ("Barrie", "ON"),
    ("Kelowna", "BC"), ("Moncton", "NB"), ("Saint John", "NB"),
    ("Sudbury", "ON"), ("Thunder Bay", "ON"), ("Lethbridge", "AB"),
    ("Red Deer", "AB"), ("Nanaimo", "BC"), ("Kamloops", "BC"),
    ("Brantford", "ON"), ("Guelph", "ON"),
]

CMA_SECTOR_CUTS = [
    ("cleantech and data centres",
     "data centre, AI computing facility, EV battery plant, hydrogen facility, "
     "solar farm, wind farm, carbon capture, clean energy, electric vehicle"),
    ("affordable housing and residential",
     "affordable housing, rental apartment, social housing, supportive housing, "
     "student housing, seniors residence, mixed-use residential"),
    ("institutional healthcare and education",
     "hospital, long-term care home, medical centre, university campus, "
     "college building, school, research facility, laboratory"),
]


def build_cma_deep_dive_queries():
    """Tier 3: Top 10 CMAs x 3 sector cuts + 20 medium CMA sweeps = ~50 queries."""
    queries = []

    # Top 10 CMAs: targeted sector cuts
    for cma, prov in TOP_10_CMAS:
        for sector_label, keywords in CMA_SECTOR_CUTS:
            queries.append({
                "query": (
                    f"List all major {sector_label} projects in {cma} and surrounding area, "
                    f"Canada that have been announced, approved, under construction, delayed, "
                    f"or completed in the past four weeks or currently under development. "
                    f"Include: {keywords}. "
                    f"Include new builds, redevelopments, renovations, expansions, and conversions. "
                    f"For each: project name, proponent, location, estimated value, status, source URL."
                ),
                "cma": cma,
                "province": PROVINCES.get(prov, (prov,))[0] if prov in PROVINCES else prov,
                "sector": sector_label.split(" and ")[0],
                "language": "en",
                "geo_tier": "cma_deep",
            })

    # Medium CMAs: broad sweep
    for cma, prov in MEDIUM_CMAS:
        queries.append({
            "query": (
                f"List all major capital projects in {cma} and surrounding area, Canada "
                f"that have had any news or status changes in the past four weeks. "
                f"Include all sectors and both new builds and redevelopments. "
                f"For each: project name, proponent, location, value, sector, status, source URL."
            ),
            "cma": cma,
            "province": PROVINCES.get(prov, (prov,))[0] if prov in PROVINCES else prov,
            "sector": "broad_sweep",
            "language": "en",
            "geo_tier": "cma_deep",
        })

    return queries


# ── Tier 5: Federal & Interprovincial ────────────────────────────────────────

def build_federal_queries():
    """Tier 5: 25 queries for federal programs and cross-border projects."""
    queries = []

    # Cross-border infrastructure
    cross_border = [
        ("interprovincial pipeline projects including new pipelines, expansions, "
         "reversals, and decommissions crossing provincial boundaries or connecting to US",
         "federal_pipelines"),
        ("interprovincial electricity transmission line projects including new lines, "
         "capacity upgrades, and interconnections between provincial grids",
         "federal_transmission"),
        ("interprovincial rail projects including new rail lines, high-frequency rail, "
         "high-speed rail, and major rail yards serving multiple provinces",
         "federal_rail"),
        ("interprovincial highway and bridge projects including international border "
         "crossings, interprovincial bridges, and Trans-Canada Highway upgrades",
         "federal_highways"),
    ]

    for desc, sector in cross_border:
        queries.append({
            "query": (
                f"List all active {desc} in Canada. "
                f"For each: project name, proponent, provinces involved, "
                f"estimated value, current status, and source URL."
            ),
            "sector": sector,
            "language": "en",
            "geo_tier": "federal",
        })

    # Federal programs
    federal_programs = [
        ("federal government construction and facility projects above $100 million "
         "including Parliament Hill renovations, federal buildings, military facilities, "
         "coast guard stations, RCMP facilities, correctional facilities, and border infrastructure",
         "federal_buildings"),
        ("Canadian military procurement and construction projects including naval shipbuilding "
         "(Canadian Surface Combatant, Arctic patrol vessels), military base construction, "
         "fighter jet infrastructure, and defence facility projects",
         "federal_defence"),
        ("Canadian Coast Guard, icebreaker, and marine infrastructure projects including "
         "ship construction, port facilities, and marine safety infrastructure",
         "federal_marine"),
        ("projects funded by the Canada Infrastructure Bank with updates in the past four weeks "
         "including transit, broadband, clean power, green infrastructure, and trade/transportation",
         "federal_cib"),
        ("major housing projects receiving federal funding through the Housing Accelerator Fund, "
         "Apartment Construction Loan Program, or other CMHC programs in the past four weeks",
         "federal_housing"),
        ("major Indigenous infrastructure projects receiving federal funding or reaching milestones "
         "in the past four weeks including clean water, housing, schools, healthcare, broadband, "
         "clean energy, and cultural centres on First Nations, Inuit, and Metis communities",
         "federal_indigenous"),
    ]

    for desc, sector in federal_programs:
        queries.append({
            "query": (
                f"List all major {desc} in Canada. "
                f"For each: project name, lead department or agency, location, "
                f"estimated value, current status, and source URL."
            ),
            "sector": sector,
            "language": "en",
            "geo_tier": "federal",
        })

    # Broad federal (French)
    queries.append({
        "query": (
            "Quels sont les projets federaux majeurs de construction et d'infrastructure "
            "au Canada qui ont eu des mises a jour au cours des quatre dernieres semaines? "
            "Incluez les projets interprovinciaux, les batiments federaux, les installations "
            "militaires, les projets de la Banque de l'infrastructure du Canada, et les "
            "programmes de logement federaux. Pour chaque projet : nom, emplacement, "
            "valeur, statut et URL source."
        ),
        "sector": "federal_broad",
        "language": "fr",
        "geo_tier": "federal",
    })

    # Additional specific federal queries
    specific = [
        ("major broadband and rural connectivity infrastructure projects funded by the "
         "Universal Broadband Fund or provincial programs in the past four weeks",
         "federal_broadband"),
        ("major clean energy projects receiving federal funding through the Clean Economy "
         "Investment Tax Credits, Strategic Innovation Fund, or Net Zero Accelerator",
         "federal_clean_energy"),
        ("major port and airport expansion projects in Canada that have had updates "
         "in the past four weeks including container terminal expansions, runway projects, "
         "and new terminal buildings",
         "federal_ports_airports"),
        ("major water and wastewater infrastructure projects receiving federal funding "
         "in the past four weeks including treatment plants, water mains, and stormwater",
         "federal_water"),
        ("major public transit projects receiving federal funding through the Permanent "
         "Transit Fund or Canada Community-Building Fund in the past four weeks",
         "federal_transit"),
        ("major research and innovation facilities under construction or announced in Canada "
         "including synchrotrons, supercomputing centres, space facilities, and research labs",
         "federal_research"),
        ("major nuclear projects in Canada including SMR sites, uranium processing, "
         "nuclear waste management, and reactor refurbishments with recent updates",
         "federal_nuclear"),
        ("major dam safety, flood mitigation, and climate adaptation infrastructure "
         "projects in Canada with recent updates",
         "federal_climate_adapt"),
    ]

    for desc, sector in specific:
        queries.append({
            "query": (
                f"List all {desc} in Canada. "
                f"For each: project name, location, proponent, value, status, source URL."
            ),
            "sector": sector,
            "language": "en",
            "geo_tier": "federal",
        })

    return queries[:25]  # Cap at 25


# ── Tier 6: Emerging Sector Watchlists ───────────────────────────────────────

def build_emerging_sector_queries():
    """Tier 6: 25 queries for fast-evolving sectors."""
    queries = []

    sectors = [
        ("data centre projects announced, approved, or under construction in Canada "
         "including hyperscale data centres, AI computing facilities, colocation facilities. "
         "For each: project name, operator, location, power capacity (MW), estimated value, status",
         "emerging_data_centres"),
        ("electric vehicle battery manufacturing, battery component, and EV assembly plant "
         "projects in Canada with updates. Include gigafactories, cathode/anode plants, "
         "battery recycling. For each: project name, company, location, value, jobs, status",
         "emerging_ev_battery"),
        ("critical minerals processing and refining facility projects in Canada with updates. "
         "Include lithium, nickel, cobalt, graphite, rare earth, copper, uranium processing. "
         "For each: project name, company, location, mineral(s), value, status",
         "emerging_critical_minerals"),
        ("small modular reactor (SMR) and nuclear energy projects in Canada with updates. "
         "Include SMR sites, nuclear fuel facilities, nuclear refurbishments, waste storage. "
         "For each: project name, developer, technology type, location, value, regulatory status",
         "emerging_nuclear"),
        ("hydrogen production and carbon capture (CCUS) projects in Canada with updates. "
         "Include blue hydrogen, green hydrogen, hydrogen hubs, carbon capture, CO2 pipelines. "
         "For each: project name, company, location, type, value, status",
         "emerging_hydrogen_ccus"),
        ("semiconductor fabrication, chip packaging, and advanced manufacturing facilities "
         "in Canada with updates. Include wafer fab, chip assembly, photonics, quantum computing. "
         "For each: project name, company, location, value, status",
         "emerging_semiconductor"),
        ("major broadband, fibre optic, and rural connectivity infrastructure in Canada with "
         "updates. Include UBF projects, provincial programs, undersea cables, satellite ground stations. "
         "For each: project name, provider, region, value, status",
         "emerging_broadband"),
        ("LNG export terminal and natural gas liquefaction facility projects in Canada with updates. "
         "Include East Coast and West Coast, floating LNG, associated pipelines. "
         "For each: project name, proponent, location, capacity (MTPA), value, status",
         "emerging_lng"),
        ("large-scale renewable energy projects above $100 million in Canada with updates. "
         "Include offshore wind, large solar, pumped hydro storage, battery energy storage (BESS), "
         "geothermal, tidal. For each: project name, developer, location, capacity (MW), value, status",
         "emerging_renewables"),
        ("mass timber buildings, modular construction factories, and prefabricated housing "
         "facilities in Canada. Include CLT/glulam plants, modular factories, mass timber buildings. "
         "For each: project name, company, location, value, status",
         "emerging_mass_timber"),
        ("major capital projects in Canada announced, approved, or begun construction in the "
         "past month that received limited media coverage. Include smaller provinces, rural areas, "
         "Indigenous communities, and niche sectors. For each: project name, proponent, location, "
         "value, sector",
         "gap_detection"),
        ("Indigenous infrastructure and economic development projects announced or reaching "
         "milestones in the past month. Include First Nations, Inuit, Metis projects for housing, "
         "water, energy, schools, health, broadband, cultural facilities. "
         "For each: project name, community, location, value, status",
         "gap_indigenous"),
    ]

    for desc, sector in sectors:
        queries.append({
            "query": (
                f"List all {desc}, and source URL. "
                f"Only include projects in Canada in the past four weeks."
            ),
            "sector": sector,
            "language": "en",
            "geo_tier": "national",
        })

    # French emerging
    queries.append({
        "query": (
            "Enumerez tous les projets de centres de donnees, d'usines de batteries "
            "pour vehicules electriques, de mineraux critiques et d'hydrogene au "
            "Quebec et dans l'Est du Canada qui ont eu des mises a jour au cours "
            "des quatre dernieres semaines. Pour chaque projet : nom, entreprise, "
            "emplacement, valeur, statut et URL source."
        ),
        "sector": "emerging_tech_fr",
        "language": "fr",
        "geo_tier": "national",
    })

    return queries[:25]  # Cap at 25


# ── Shared Parse & Normalize ─────────────────────────────────────────────────

_STATUS_MAP = {
    "proposed": "Proposed", "approved": "Approved",
    "under_construction": "Under Construction", "completed": "Completed",
    "delayed": "Paused", "cancelled": "Cancelled", "on_hold": "Paused",
}


def _normalize_status(raw):
    return _STATUS_MAP.get(raw, raw.title() if raw else "Proposed")


def _format_value(val_millions):
    if val_millions is None:
        return "Not disclosed"
    try:
        v = float(val_millions)
        if v >= 1000:
            return f"C${v/1000:.1f}B"
        return f"C${v:.0f}M"
    except (TypeError, ValueError):
        return "Not disclosed"


def parse_capacity_results(raw_results, tier_tag="CAPACITY"):
    """Parse gemini_engine batch results into flat project dicts.

    Uses the same JSON schema as compound_discovery.py's EXTRACTION_SYSTEM_PROMPT.
    Returns list of project dicts compatible with upsert_flat_projects().
    """
    all_projects = []

    for result in raw_results:
        if result.get("error"):
            continue

        text = result.get("text", "")
        grounding_urls_raw = result.get("grounding_urls", [])
        query = result.get("query", {})

        # Strip markdown fences
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        if not text:
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            obj_start = text.find('{')
            if obj_start < 0:
                continue
            depth = 0
            for i in range(obj_start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(text[obj_start:i + 1])
                        except json.JSONDecodeError:
                            continue
                        break
            else:
                continue

        if isinstance(data, list):
            data = {"projects": data}

        # Build grounding URL set
        grounding_uri_set = set()
        grounding_url_dicts = []
        for g in grounding_urls_raw:
            url = g["url"] if isinstance(g, dict) else g
            title = g.get("title", "") if isinstance(g, dict) else ""
            grounding_url_dicts.append({"url": url, "name": title})
            grounding_uri_set.add(url)

        for rp in data.get("projects", []):
            name = (rp.get("name") or "").strip()
            if not name or len(name) < 3:
                continue

            loc = rp.get("location", {}) if isinstance(rp.get("location"), dict) else {}
            province = loc.get("province") or query.get("province", "")
            cma = loc.get("cma") or loc.get("city") or query.get("cma", "")

            source_url = (rp.get("source_url") or "").strip()
            source_name = (rp.get("source_name") or "").strip()

            # Build evidence array
            evidence = []
            existing_urls = set()
            if source_url and source_url.startswith("http"):
                evidence.append({
                    "url": source_url, "name": source_name,
                    "date": rp.get("date_reported", ""),
                    "source_type": "gemini_extracted",
                })
                existing_urls.add(source_url)
            for g in grounding_url_dicts:
                if g["url"] not in existing_urls:
                    evidence.append({
                        "url": g["url"], "name": g["name"],
                        "date": "", "source_type": "gemini_grounding",
                    })
                    existing_urls.add(g["url"])

            grounded = source_url in grounding_uri_set if source_url else False

            all_projects.append({
                "name": name,
                "value": _format_value(rp.get("value_millions")),
                "value_numeric": rp.get("value_millions"),
                "proponent": (rp.get("proponent") or "Unknown").strip(),
                "province": province,
                "cma": cma,
                "naics_2digit": (rp.get("naics_2digit") or "").strip(),
                "status": _normalize_status(rp.get("status", "")),
                "description": (rp.get("description") or "").strip(),
                "source_url": source_url,
                "source_title": source_name,
                "discovery_source": f"gemini_{tier_tag.lower()}",
                "confidence": "verified" if grounded else "unverified",
                "project_type": rp.get("project_type", ""),
                "geo_tier": query.get("geo_tier", ""),
                "_evidence": evidence,
            })

    # Dedup within results
    seen = set()
    unique = []
    for p in all_projects:
        key = (p["name"].lower().strip(), p.get("province", "").lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return unique


def run_capacity_discovery(db, budgets=None):
    """Run Tiers 2, 3, 5, 6 within provided budget.

    Args:
        db: Firestore client (used for upsert after discovery)
        budgets: dict with tier caps, e.g. {"T2": 15, "T3": 50, "T5": 25, "T6": 25}

    Returns:
        list of normalized project dicts (not yet upserted -- caller handles that)
    """
    from gemini_engine import run_batch_sync
    # EXTRACTION_SYSTEM_PROMPT formerly imported from compound_discovery (now removed)
    EXTRACTION_SYSTEM_PROMPT = """You are a Canadian capital projects research assistant. Find and list major capital projects based on the user's query.

Return a JSON object with this structure:
{
  "projects": [
    {
      "name": "Project name",
      "proponent": "Company or organization",
      "location": {"city": "City", "province": "Two-letter code", "cma": "CMA name or null"},
      "value_millions": 650,
      "currency": "CAD",
      "status": "proposed | approved | under_construction | completed | delayed | cancelled | on_hold",
      "project_type": "greenfield | redevelopment | expansion | retrofit | restoration | remediation | conversion | modernization",
      "sector": "Sector description",
      "naics_2digit": "Best-fit 2-digit NAICS code",
      "description": "One-sentence project description",
      "source_url": "URL of the source article",
      "source_name": "Publication name",
      "date_reported": "YYYY-MM-DD",
      "confidence_notes": "Any caveats"
    }
  ]
}

RULES:
1. Only include projects with VERIFIED information. Never fabricate.
2. If no matching projects found, return {"projects": []}.
3. Include BOTH greenfield AND brownfield projects.
4. Every project MUST have a source_url with a real URL starting with https://.
5. Values in millions CAD.
6. Return ONLY the JSON object. No markdown, no preamble."""

    budgets = budgets or {"T2": 15, "T3": 50, "T5": 25, "T6": 25}

    # Build all queries
    t2 = build_provincial_sweep_queries()[:budgets.get("T2", 15)]
    t3 = build_cma_deep_dive_queries()[:budgets.get("T3", 50)]
    t5 = build_federal_queries()[:budgets.get("T5", 25)]
    t6 = build_emerging_sector_queries()[:budgets.get("T6", 25)]

    all_queries = t2 + t3 + t5 + t6
    if not all_queries:
        return []

    print(f"\n[CAPACITY] Running {len(all_queries)} queries "
          f"(T2={len(t2)}, T3={len(t3)}, T5={len(t5)}, T6={len(t6)})")

    raw_results = run_batch_sync(
        all_queries, EXTRACTION_SYSTEM_PROMPT,
        max_concurrent=15, tag="CAPACITY"
    )

    projects = parse_capacity_results(raw_results, "capacity")
    print(f"  [CAPACITY] {len(projects)} unique projects from {len(all_queries)} queries")
    return projects
