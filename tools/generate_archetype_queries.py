"""
generate_archetype_queries.py — Generate archetype-specific compound queries.

Produces ~900-1,000 new queries from 18 project archetypes applied across
national, provincial, and CMA geographic levels plus French variants.
Appends to compound_queries_final.json with dedup against existing queries.
"""

import json
import re
from pathlib import Path

# ── Geographic reference data ──

PROVINCES = [
    "Ontario", "Quebec", "Alberta", "British Columbia", "Saskatchewan",
    "Manitoba", "Nova Scotia", "New Brunswick", "Newfoundland and Labrador",
    "Prince Edward Island", "Yukon", "Northwest Territories", "Nunavut",
]

PROVINCE_SHORT = {
    "Ontario": "Ontario", "Quebec": "Quebec", "Alberta": "Alberta",
    "British Columbia": "BC", "Saskatchewan": "Saskatchewan",
    "Manitoba": "Manitoba", "Nova Scotia": "Nova Scotia",
    "New Brunswick": "New Brunswick", "Newfoundland and Labrador": "Newfoundland",
    "Prince Edward Island": "PEI", "Yukon": "Yukon",
    "Northwest Territories": "NWT", "Nunavut": "Nunavut",
}

PROVINCE_THRESHOLDS = {
    "Ontario": 500, "Quebec": 250, "Alberta": 200, "British Columbia": 175,
    "Saskatchewan": 45, "Manitoba": 40, "Nova Scotia": 25, "New Brunswick": 20,
    "Newfoundland and Labrador": 17, "Prince Edward Island": 5,
    "Yukon": 3, "Northwest Territories": 3, "Nunavut": 3,
}

CMAS_35 = [
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
    "Ottawa", "Winnipeg", "Quebec City", "Hamilton",
    "Kitchener-Waterloo", "London Ontario", "Halifax", "Victoria",
    "Windsor Ontario", "Oshawa", "Saskatoon", "Regina",
    "St. Catharines-Niagara", "Barrie", "Kelowna",
    "Abbotsford", "Sherbrooke", "Guelph", "Moncton",
    "Saint John NB", "St. John's NL", "Fredericton",
    "Sudbury", "Thunder Bay", "Trois-Rivieres",
    "Brantford", "Peterborough", "Lethbridge", "Red Deer", "Kamloops",
]

CMAS_FRENCH = ["Montréal", "Québec", "Sherbrooke", "Trois-Rivières", "Gatineau"]

# CMA to province mapping for threshold lookup
CMA_PROVINCE = {
    "Toronto": "Ontario", "Montreal": "Quebec", "Vancouver": "British Columbia",
    "Calgary": "Alberta", "Edmonton": "Alberta", "Ottawa": "Ontario",
    "Winnipeg": "Manitoba", "Quebec City": "Quebec", "Hamilton": "Ontario",
    "Kitchener-Waterloo": "Ontario", "London Ontario": "Ontario",
    "Halifax": "Nova Scotia", "Victoria": "British Columbia",
    "Windsor Ontario": "Ontario", "Oshawa": "Ontario", "Saskatoon": "Saskatchewan",
    "Regina": "Saskatchewan", "St. Catharines-Niagara": "Ontario",
    "Barrie": "Ontario", "Kelowna": "British Columbia",
    "Abbotsford": "British Columbia", "Sherbrooke": "Quebec",
    "Guelph": "Ontario", "Moncton": "New Brunswick",
    "Saint John NB": "New Brunswick", "St. John's NL": "Newfoundland and Labrador",
    "Fredericton": "New Brunswick", "Sudbury": "Ontario",
    "Thunder Bay": "Ontario", "Trois-Rivieres": "Quebec",
    "Brantford": "Ontario", "Peterborough": "Ontario",
    "Lethbridge": "Alberta", "Red Deer": "Alberta", "Kamloops": "British Columbia",
}

# French CMA to province
FRENCH_CMA_PROVINCE = {
    "Montréal": "Quebec", "Québec": "Quebec", "Sherbrooke": "Quebec",
    "Trois-Rivières": "Quebec", "Gatineau": "Quebec",
}

# Which archetypes apply to which geographies
MINING_PROVINCES = [
    "Ontario", "Quebec", "Alberta", "British Columbia", "Saskatchewan",
    "Manitoba", "Newfoundland and Labrador", "Northwest Territories", "Yukon",
]
MINING_CMAS = [
    "Sudbury", "Thunder Bay", "Red Deer", "Kamloops", "Lethbridge",
    "St. John's NL", "Fredericton", "Saskatoon", "Halifax",
]
PIPELINE_PROVINCES = [
    "Alberta", "British Columbia", "Saskatchewan", "Ontario",
    "Quebec", "Newfoundland and Labrador",
]
LNG_PROVINCES = ["British Columbia", "Alberta", "Saskatchewan", "Ontario"]
DEFENCE_PROVINCES = ["Nova Scotia", "British Columbia", "Ontario", "Quebec", "Alberta"]
PORT_AIRPORT_CMAS = [
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
    "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Halifax",
    "Victoria", "Windsor Ontario", "St. John's NL", "Saint John NB",
    "Thunder Bay", "Moncton", "Fredericton", "Saskatoon", "Regina",
]
INDIGENOUS_PROVINCES = [
    "Ontario", "Quebec", "Alberta", "British Columbia", "Saskatchewan",
    "Manitoba", "Nova Scotia", "New Brunswick", "Newfoundland and Labrador",
    "Northwest Territories",
]
INDIGENOUS_CMAS = [
    "Winnipeg", "Edmonton", "Vancouver", "Calgary", "Saskatoon",
    "Regina", "Thunder Bay", "Sudbury", "Ottawa", "Toronto",
    "Halifax", "Moncton", "Fredericton", "Victoria", "Kamloops",
]
DATA_CENTRE_CMAS = [
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
    "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Halifax",
    "Victoria", "Kitchener-Waterloo", "London Ontario", "Saskatoon", "Regina",
]

# Sector mapping for each archetype
ARCHETYPE_SECTORS = {
    1: "commercial_mixed",
    2: "residential",
    3: "transport_logistics",
    4: "healthcare",
    5: "tourism_culture",
    6: "education",
    7: "mining",
    8: "power_energy",
    9: "oil_gas",
    10: "oil_gas",
    11: "manufacturing",
    12: "telecom",
    13: "transport_logistics",
    14: "infrastructure",
    15: "defence",
    16: "indigenous",
    17: "power_energy",
    18: "tourism_culture",
}


def _make_entry(query, province, sector, language, geo_tier, threshold_m):
    return {
        "query": query,
        "province": province,
        "sector": sector,
        "language": language,
        "geo_tier": geo_tier,
        "threshold_m": threshold_m,
    }


def generate_all_queries():
    """Generate all archetype queries and return (queries_list, log_dict)."""
    queries = []
    log = {}

    def add(archetype_num, level, q, province, language, geo_tier, threshold_m):
        sector = ARCHETYPE_SECTORS[archetype_num]
        queries.append(_make_entry(q, province, sector, language, geo_tier, threshold_m))
        key = f"{archetype_num}_{level}"
        log[key] = log.get(key, 0) + 1

    # ── Archetype 1: Downtown redevelopment / mixed-use ──
    a = 1
    for q in [
        'Canada "redevelopment" project construction million',
        'Canada "mixed-use" development approved OR proposed',
        'Canada "urban renewal" OR "revitalization" project investment',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" redevelopment project construction',
            f'"{prov}" "mixed-use" development million OR billion',
            f'"{prov}" "downtown" OR "city centre" revitalization project',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" redevelopment project',
            f'"{cma}" "mixed-use" development construction',
            f'"{cma}" downtown revitalization project',
            f'"{cma}" "urban renewal" OR "master plan" development',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        for q in [
            f'"{cma_fr}" réaménagement projet construction',
            f'"{cma_fr}" "usage mixte" développement',
            f'"{cma_fr}" revitalisation centre-ville',
        ]:
            add(a, "french", q, "Quebec", "fr", "cma", 250)

    # ── Archetype 2: Residential mega-project ──
    a = 2
    for q in [
        'Canada "condo tower" OR "residential tower" construction',
        'Canada "affordable housing" development million OR billion',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "residential" development construction million',
            f'"{prov}" "affordable housing" OR "social housing" project',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" "condo" OR "condominium" tower construction',
            f'"{cma}" "residential" development project million',
            f'"{cma}" "purpose-built rental" OR "affordable housing" construction',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        for q in [
            f'"{cma_fr}" "tour résidentielle" OR "condo" construction',
            f'"{cma_fr}" "logement abordable" projet construction',
        ]:
            add(a, "french", q, "Quebec", "fr", "cma", 250)

    # ── Archetype 3: Transit and transportation ──
    a = 3
    for q in [
        'Canada "LRT" OR "light rail" construction approved',
        'Canada "subway" OR "commuter rail" extension project',
        'Canada "highway" expansion OR widening billion',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "transit" expansion OR construction project',
            f'"{prov}" "LRT" OR "light rail" OR "BRT" project',
            f'"{prov}" "highway" OR "interchange" OR "bridge" construction',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" "transit" expansion OR extension project',
            f'"{cma}" "LRT" OR "light rail" OR "subway" construction',
            f'"{cma}" "highway" OR "bridge" OR "interchange" construction',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        for q in [
            f'"{cma_fr}" "transport en commun" expansion projet',
            f'"{cma_fr}" "tramway" OR "métro" OR "SRB" construction',
            f'"{cma_fr}" "autoroute" OR "pont" OR "échangeur" construction',
        ]:
            add(a, "french", q, "Quebec", "fr", "cma", 250)

    # ── Archetype 4: Hospital and healthcare ──
    a = 4
    for q in [
        'Canada "hospital" construction OR expansion million',
        'Canada "health centre" OR "cancer centre" new construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "hospital" construction OR expansion OR redevelopment',
            f'"{prov}" "health" OR "medical" facility new OR expansion',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" "hospital" construction OR expansion project',
            f'"{cma}" "health centre" OR "medical centre" new construction',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        for q in [
            f'"{cma_fr}" "hôpital" construction OR agrandissement',
            f'"{cma_fr}" "centre de santé" OR "CLSC" projet construction',
        ]:
            add(a, "french", q, "Quebec", "fr", "cma", 250)

    # ── Archetype 5: Arena, stadium, entertainment ──
    a = 5
    for q in [
        'Canada "arena" OR "stadium" construction project',
        'Canada "convention centre" OR "event centre" construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "arena" OR "stadium" OR "event centre" construction',
            prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" "arena" OR "stadium" construction project',
            f'"{cma}" "convention centre" OR "entertainment district" project',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        add(a, "french",
            f'"{cma_fr}" "aréna" OR "stade" OR "centre des congrès" construction',
            "Quebec", "fr", "cma", 250)

    # ── Archetype 6: Educational institution ──
    a = 6
    for q in [
        'Canada "university" campus construction expansion',
        'Canada "college" OR "polytechnic" construction million',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "university" OR "college" construction OR expansion project',
            prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" "university" campus construction OR expansion',
            f'"{cma}" "college" OR "school" construction project million',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        add(a, "french",
            f'"{cma_fr}" "université" OR "cégep" construction agrandissement',
            "Quebec", "fr", "cma", 250)

    # ── Archetype 7: Mine and resource extraction ──
    a = 7
    for q in [
        'Canada "mine" approved OR construction investment',
        'Canada "mining" project billion OR million new',
        'Canada "critical minerals" mine OR processing facility',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in MINING_PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "mine" approved OR construction OR expansion',
            f'"{prov}" "mining" project investment million',
            f'"{prov}" "mineral" processing OR smelter OR refinery',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for cma in MINING_CMAS:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "cma",
            f'"{cma}" "mine" OR "mining" project construction',
            prov, "en", "cma", t)

    for q in [
        'Québec "mine" investissement OR approbation',
        'Québec "minéral" traitement construction',
    ]:
        add(a, "french", q, "Quebec", "fr", "province", 250)

    # ── Archetype 8: Energy generation ──
    a = 8
    for q in [
        'Canada "wind farm" approved OR construction',
        'Canada "solar farm" OR "solar park" approved OR construction',
        'Canada "nuclear" OR "SMR" project construction',
        'Canada "hydroelectric" OR "dam" construction project',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "wind farm" OR "solar farm" approved OR construction',
            f'"{prov}" "power plant" OR "generating station" construction',
            f'"{prov}" "battery storage" OR "energy storage" project',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for q in [
        'Québec "parc éolien" approuvé OR construction',
        'Québec "parc solaire" approuvé OR construction',
        'Québec "barrage" OR "centrale" hydroélectrique construction',
        'Québec "stockage énergie" OR "batterie" projet',
    ]:
        add(a, "french", q, "Quebec", "fr", "province", 250)

    # ── Archetype 9: Pipeline and transmission ──
    a = 9
    for q in [
        'Canada "pipeline" project approved OR construction',
        'Canada "transmission line" project approved',
        'Canada "natural gas" pipeline expansion',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PIPELINE_PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "pipeline" construction OR expansion project',
            f'"{prov}" "transmission line" OR "interconnection" project',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    # ── Archetype 10: LNG and petrochemical ──
    a = 10
    for q in [
        'Canada "LNG" terminal OR export facility construction',
        'Canada "petrochemical" plant construction OR expansion',
        'Canada "fertilizer" plant OR "upgrader" construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in LNG_PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "LNG" OR "petrochemical" facility construction',
            f'"{prov}" "refinery" OR "upgrader" expansion OR construction',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    # ── Archetype 11: Manufacturing and industrial ──
    a = 11
    for q in [
        'Canada "manufacturing" plant new OR expansion million',
        'Canada "EV battery" OR "gigafactory" plant construction',
        'Canada "food processing" plant construction OR expansion',
        'Canada "auto" plant OR "assembly plant" investment',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "manufacturing" plant construction OR expansion',
            f'"{prov}" "factory" OR "plant" new investment million',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "cma",
            f'"{cma}" "factory" OR "plant" OR "manufacturing" construction investment',
            prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        for q in [
            f'"{cma_fr}" "usine" construction OR agrandissement',
            f'"{cma_fr}" "manufacture" OR "installation" investissement',
        ]:
            add(a, "french", q, "Quebec", "fr", "cma", 250)

    # ── Archetype 12: Data centre and digital infrastructure ──
    a = 12
    for q in [
        'Canada "data centre" OR "data center" construction',
        'Canada "hyperscale" facility construction',
        'Canada "broadband" OR "fibre" infrastructure project',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "data centre" OR "data center" construction',
            prov, "en", "province", t)

    for cma in DATA_CENTRE_CMAS:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "cma",
            f'"{cma}" "data centre" OR "data center" construction',
            prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH[:3]:  # Montréal, Québec, Sherbrooke
        add(a, "french",
            f'"{cma_fr}" "centre de données" construction projet',
            "Quebec", "fr", "cma", 250)

    # ── Archetype 13: Port, airport, logistics ──
    a = 13
    for q in [
        'Canada "airport" terminal expansion construction',
        'Canada "port" expansion OR terminal construction',
        'Canada "distribution centre" OR "logistics hub" construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "airport" OR "port" expansion OR construction project',
            prov, "en", "province", t)

    for cma in PORT_AIRPORT_CMAS:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{cma}" "airport" terminal OR expansion construction',
            f'"{cma}" "warehouse" OR "distribution" OR "logistics" construction',
        ]:
            add(a, "cma", q, prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH[:3]:
        for q in [
            f'"{cma_fr}" "aéroport" agrandissement OR terminal construction',
            f'"{cma_fr}" "port" expansion OR terminal construction',
        ]:
            add(a, "french", q, "Quebec", "fr", "cma", 250)

    # ── Archetype 14: Water and wastewater ──
    a = 14
    add(a, "national",
        'Canada "water treatment" OR "wastewater" plant construction',
        "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "water treatment" OR "wastewater" construction upgrade',
            prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "cma",
            f'"{cma}" "water treatment" OR "wastewater" OR "sewer" construction',
            prov, "en", "cma", t)

    # ── Archetype 15: Defence and military ──
    a = 15
    for q in [
        'Canada "military" base construction OR expansion',
        'Canada "shipbuilding" OR "naval" construction contract',
        'Canada "defence" facility OR depot construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in DEFENCE_PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "military" OR "defence" facility construction',
            prov, "en", "province", t)

    # ── Archetype 16: Indigenous-led development ──
    a = 16
    for q in [
        'Canada "Indigenous" OR "First Nation" project construction investment',
        'Canada "Indigenous" economic development project',
        'Canada "First Nation" OR "Métis" development project million',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in INDIGENOUS_PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "Indigenous" OR "First Nation" development project construction',
            prov, "en", "province", t)

    for cma in INDIGENOUS_CMAS:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "cma",
            f'"{cma}" "Indigenous" OR "First Nation" development project',
            prov, "en", "cma", t)

    # ── Archetype 17: Clean energy transition ──
    a = 17
    for q in [
        'Canada "hydrogen" plant OR facility construction',
        'Canada "carbon capture" OR "CCUS" project construction',
        'Canada "EV charging" infrastructure project',
        'Canada "clean fuel" OR "biofuel" facility construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        for q in [
            f'"{prov}" "hydrogen" OR "carbon capture" project construction',
            f'"{prov}" "clean energy" OR "net zero" facility construction',
        ]:
            add(a, "provincial", q, prov, "en", "province", t)

    for q in [
        'Québec "hydrogène" usine OR installation construction',
        'Québec "captage carbone" OR "biocarburant" projet',
    ]:
        add(a, "french", q, "Quebec", "fr", "province", 250)

    # ── Archetype 18: Institutional and cultural ──
    a = 18
    for q in [
        'Canada "museum" OR "library" construction expansion',
        'Canada "community centre" OR "cultural centre" construction',
    ]:
        add(a, "national", q, "National", "en", "national", 0)

    for prov in PROVINCES:
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "provincial",
            f'"{prov}" "museum" OR "library" OR "community centre" construction',
            prov, "en", "province", t)

    for cma in CMAS_35:
        prov = CMA_PROVINCE[cma]
        t = PROVINCE_THRESHOLDS[prov]
        add(a, "cma",
            f'"{cma}" "museum" OR "library" OR "community centre" construction project',
            prov, "en", "cma", t)

    for cma_fr in CMAS_FRENCH:
        add(a, "french",
            f'"{cma_fr}" "musée" OR "bibliothèque" OR "centre communautaire" construction',
            "Quebec", "fr", "cma", 250)

    return queries, log


def normalize_query(q):
    """Normalize a query string for dedup comparison."""
    return re.sub(r'\s+', ' ', q.lower().strip())


def main():
    queries, log = generate_all_queries()
    print(f"Generated {len(queries)} raw archetype queries")

    # Load existing
    path = Path(__file__).resolve().parent.parent / "config" / "compound_queries_final.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("queries", [])
    existing_normalized = {normalize_query(q["query"]) for q in existing}
    print(f"Existing queries: {len(existing)}")

    # Dedup and append
    new_count = 0
    dupes = 0
    for q in queries:
        nq = normalize_query(q["query"])
        if nq not in existing_normalized:
            existing.append(q)
            existing_normalized.add(nq)
            new_count += 1
        else:
            dupes += 1

    data["queries"] = existing
    data["total_queries"] = len(existing)

    # Update stats
    if "stats" not in data:
        data["stats"] = {}
    data["stats"]["archetype_queries"] = new_count

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDedup: {dupes} duplicates skipped")
    print(f"New queries added: {new_count}")
    print(f"Total queries now: {len(existing)}")

    # Generation log
    print(f"\n{'='*60}")
    print("  GENERATION LOG — Queries per archetype × level")
    print(f"{'='*60}")

    archetype_names = {
        1: "Redevelopment", 2: "Residential", 3: "Transit", 4: "Hospital",
        5: "Arena", 6: "Education", 7: "Mining", 8: "Energy",
        9: "Pipeline", 10: "LNG", 11: "Manufacturing", 12: "Data centre",
        13: "Port/airport", 14: "Water", 15: "Defence", 16: "Indigenous",
        17: "Clean energy", 18: "Cultural",
    }

    for a_num in range(1, 19):
        name = archetype_names[a_num]
        nat = log.get(f"{a_num}_national", 0)
        prov = log.get(f"{a_num}_provincial", 0)
        cma = log.get(f"{a_num}_cma", 0)
        fr = log.get(f"{a_num}_french", 0)
        total = nat + prov + cma + fr
        print(f"  {a_num:2d}. {name:20s}  nat={nat:3d}  prov={prov:3d}  cma={cma:3d}  fr={fr:2d}  total={total:4d}")

    print(f"\n  GRAND TOTAL: {len(queries)} raw, {new_count} new after dedup")


if __name__ == "__main__":
    main()
