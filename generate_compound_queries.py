#!/usr/bin/env python3
"""
COMPOUND QUERY TEMPLATE SYSTEM — FINAL VERSION
=================================================
~759 compound queries per week covering:
- 13 provinces × 18 NAICS sectors (English)
- French queries for QC (full), NB (full), NS/PE/ON (light)
- 35 CMAs × 8 urban sectors
- Regional resource/agricultural/corridor clusters
- 4-week lookback window in every query
- Lifecycle and cross-cutting queries

$0/year — fits within Gemini 500 RPD free tier at ~16% utilization.
"""

import json
import os
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

LOOKBACK_WEEKS = 4
YEAR_RANGE = "2025-2026"

GDP_THRESHOLDS = {
    "ON": 500, "QC": 250, "AB": 200, "BC": 175, "SK": 45, "MB": 40,
    "NS": 25, "NB": 20, "NL": 17, "PE": 5, "YT": 3, "NT": 3, "NU": 3,
}

PROVINCES_META = {
    "ON": {"en": "Ontario"},
    "QC": {"en": "Quebec"},
    "AB": {"en": "Alberta"},
    "BC": {"en": "British Columbia"},
    "SK": {"en": "Saskatchewan"},
    "MB": {"en": "Manitoba"},
    "NS": {"en": "Nova Scotia"},
    "NB": {"en": "New Brunswick"},
    "NL": {"en": "Newfoundland and Labrador"},
    "PE": {"en": "Prince Edward Island"},
    "YT": {"en": "Yukon"},
    "NT": {"en": "Northwest Territories"},
    "NU": {"en": "Nunavut"},
}

# ============================================================================
# PROVINCE × SECTOR AFFINITY
# ============================================================================

AFFINITY = {
    "ON": ["oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "forestry", "defence", "telecom",
           "indigenous", "environment", "tourism_culture", "government"],
    "QC": ["mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "forestry", "defence", "telecom",
           "indigenous", "environment", "tourism_culture", "government"],
    "AB": ["oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "forestry", "telecom",
           "indigenous", "environment", "tourism_culture", "government"],
    "BC": ["oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "forestry", "defence", "telecom",
           "indigenous", "environment", "tourism_culture", "government"],
    "SK": ["oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "indigenous", "environment", "government"],
    "MB": ["mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "indigenous", "environment",
           "tourism_culture", "government"],
    "NS": ["mining", "infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "defence", "telecom",
           "indigenous", "environment", "tourism_culture", "government"],
    "NB": ["infrastructure", "power_energy", "manufacturing",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "agriculture", "forestry", "defence",
           "indigenous", "environment", "tourism_culture", "government"],
    "NL": ["oil_gas", "mining", "infrastructure", "power_energy",
           "transport_logistics", "healthcare", "education", "residential",
           "commercial_mixed", "defence", "indigenous", "environment", "government"],
    "PE": ["infrastructure", "power_energy", "healthcare", "education",
           "residential", "commercial_mixed", "agriculture",
           "indigenous", "environment", "tourism_culture", "government"],
    "YT": ["mining", "infrastructure", "power_energy", "healthcare",
           "residential", "indigenous", "environment", "tourism_culture", "government"],
    "NT": ["oil_gas", "mining", "infrastructure", "power_energy", "healthcare",
           "residential", "indigenous", "environment", "government"],
    "NU": ["mining", "infrastructure", "power_energy", "healthcare",
           "residential", "indigenous", "environment", "government"],
}

# ============================================================================
# SECTOR COMPOUND PROMPTS — English
# ============================================================================

SECTOR_PROMPTS_EN = {
    "oil_gas": {
        "name": "Oil, Gas & Hydrogen",
        "scope": (
            "oil sands projects, natural gas processing plants, LNG facilities and expansions, "
            "pipelines (new and expansions), refineries (new and modernizations), hydrogen "
            "production facilities, carbon capture and storage (CCS/CCUS) projects, upgraders, "
            "tank farms, offshore drilling platforms, gas plants, bitumen processing, "
            "petrochemical facilities, wellsite reclamation, and remediation projects"
        ),
    },
    "mining": {
        "name": "Mining & Critical Minerals",
        "scope": (
            "new mines, mine expansions, mine life extensions, smelters, mineral processing "
            "plants, critical minerals projects (lithium, nickel, cobalt, graphite, rare earths, "
            "uranium, copper), potash mines, gold mines, iron ore projects, diamond mines, "
            "mine restarts and reopenings, tailings management facilities, mine remediation "
            "and reclamation, and mineral refining facilities"
        ),
    },
    "infrastructure": {
        "name": "Civil Infrastructure",
        "scope": (
            "highways, bridges, overpasses, interchanges, tunnels, water treatment plants, "
            "wastewater treatment plants, dams, flood protection, stormwater systems, public "
            "transit (LRT, BRT, subway, commuter rail — new lines and extensions), road "
            "reconstructions, sewer upgrades, water main replacements, and major municipal "
            "infrastructure programs"
        ),
    },
    "power_energy": {
        "name": "Power Generation, Transmission & Clean Energy",
        "scope": (
            "power plants, solar farms, wind farms, hydroelectric dams and stations, small "
            "modular reactors (SMR), nuclear refurbishments, battery storage facilities, "
            "electricity transmission lines, substations, geothermal projects, biomass plants, "
            "tidal energy, pumped hydro storage, hydrogen electrolyzers, grid modernization, "
            "coal-to-gas conversions, and power plant decommissions or replacements"
        ),
    },
    "manufacturing": {
        "name": "Manufacturing & Industrial",
        "scope": (
            "factories, manufacturing plants, EV battery gigafactories, automotive assembly "
            "plants, semiconductor fabrication, food processing plants, pharmaceutical "
            "manufacturing, aerospace manufacturing, steel mills, cement plants, data centres, "
            "plant modernizations, factory expansions, production line retoolings, and "
            "industrial facility conversions or repurposing"
        ),
    },
    "transport_logistics": {
        "name": "Ports, Airports & Logistics",
        "scope": (
            "airport terminals (new and expansions), port terminals, container terminals, "
            "rail lines and rail yards, intermodal facilities, ferry terminals, cruise terminals, "
            "logistics hubs, cargo facilities, high-speed rail, airport runway extensions, "
            "port dredging and capacity upgrades, and rail yard modernizations"
        ),
    },
    "healthcare": {
        "name": "Healthcare & Life Sciences",
        "scope": (
            "hospitals (new and expansions), medical centres, long-term care homes, mental "
            "health facilities, cancer treatment centres, urgent care centres, research "
            "laboratories, pharmaceutical research facilities, biotech facilities, seniors "
            "care facilities, hospital campus redevelopments, emergency department renovations, "
            "and health sciences centre modernizations"
        ),
    },
    "education": {
        "name": "Education & Research",
        "scope": (
            "schools (new and renovations), university buildings, college campuses, research "
            "centres, student residences, libraries, training centres, campus modernizations, "
            "school seismic upgrades, campus sustainability retrofits, and research facility "
            "expansions"
        ),
    },
    "residential": {
        "name": "Residential & Housing Development",
        "scope": (
            "residential towers, housing developments, affordable housing projects, condo "
            "towers, social housing, Indigenous housing, master-planned communities, "
            "purpose-built rentals, mixed-income housing, office-to-residential conversions, "
            "hotel conversions to housing, mall redevelopments into housing, heritage building "
            "conversions, adaptive reuse for housing, public housing revitalizations, and "
            "co-op housing renovations"
        ),
    },
    "commercial_mixed": {
        "name": "Commercial & Mixed-Use Development",
        "scope": (
            "mixed-use developments, commercial towers, office towers, entertainment districts, "
            "convention centres, hotels and resorts, sports arenas and stadiums (new and "
            "replacements), downtown redevelopments, waterfront revitalizations, mall "
            "transformations, brownfield site redevelopments, heritage district revitalizations, "
            "and casino or resort developments"
        ),
    },
    "agriculture": {
        "name": "Agriculture & Agri-Food Processing",
        "scope": (
            "grain terminals and elevators, food processing plants, greenhouses, fertilizer "
            "plants, canola crushing plants, meat processing plants, dairy processing, "
            "aquaculture facilities, breweries and distilleries, cannabis facilities, "
            "grain elevator upgrades, and agricultural facility modernizations"
        ),
    },
    "forestry": {
        "name": "Forestry & Wood Products",
        "scope": (
            "sawmills, pulp mills, lumber mills, mass timber manufacturing, pellet plants, "
            "OSB plants, plywood plants, sawmill modernizations, pulp mill conversions, "
            "mill restarts, and biomass conversion projects"
        ),
    },
    "defence": {
        "name": "Defence, Security & Federal Facilities",
        "scope": (
            "military bases, naval shipyards, coast guard facilities, defence procurement "
            "facilities, military housing, RCMP facilities, correctional facilities, border "
            "crossings, military base modernizations, shipyard expansions, and federal "
            "infrastructure upgrades"
        ),
    },
    "telecom": {
        "name": "Telecommunications & Digital Infrastructure",
        "scope": (
            "data centres (new and expansions), fibre optic networks, broadband infrastructure, "
            "5G network deployment, undersea cables, satellite ground stations, AI computing "
            "facilities, colocation facilities, network upgrades, and rural connectivity projects"
        ),
    },
    "indigenous": {
        "name": "Indigenous Infrastructure & Reconciliation",
        "scope": (
            "First Nations housing, Indigenous community infrastructure, on-reserve water "
            "treatment plants, Indigenous cultural centres, Inuit community infrastructure, "
            "Métis housing, Indigenous clean energy projects, First Nations schools, Indigenous "
            "broadband, economic reconciliation projects, on-reserve infrastructure upgrades, "
            "residential school site remediation, and Indigenous heritage restoration"
        ),
    },
    "environment": {
        "name": "Environmental & Remediation",
        "scope": (
            "recycling facilities, waste-to-energy facilities, composting facilities, landfill "
            "construction and closures, hazardous waste facilities, wetland restoration, "
            "brownfield remediation and cleanup, contaminated site redevelopment, industrial "
            "site environmental remediation, and mine site reclamation"
        ),
    },
    "tourism_culture": {
        "name": "Tourism, Culture & Recreation",
        "scope": (
            "museums (new and renovations), art galleries, performing arts centres, recreation "
            "centres, aquatic centres, ski resort developments, theme parks, casinos, sports "
            "complexes, community centres, heritage site restorations, arena renovations, "
            "park revitalizations, and waterfront park redevelopments"
        ),
    },
    "government": {
        "name": "Government & Institutional Buildings",
        "scope": (
            "courthouses, government buildings, fire stations, police stations, municipal "
            "buildings, Parliament and legislature renovations, civic centres, government "
            "building modernizations, city hall renovations, seismic upgrades to civic "
            "buildings, and federal building renovations"
        ),
    },
}

# ============================================================================
# SECTOR COMPOUND PROMPTS — French
# ============================================================================

SECTOR_PROMPTS_FR = {
    "oil_gas": {
        "name": "Pétrole, gaz et hydrogène",
        "scope": (
            "projets de sables bitumineux, usines de traitement du gaz naturel, installations "
            "de GNL, pipelines, raffineries, usines d'hydrogène, captage et stockage du "
            "carbone (CSC), installations pétrochimiques, terminaux pétroliers et projets "
            "de remise en état de sites"
        ),
    },
    "mining": {
        "name": "Mines et minéraux critiques",
        "scope": (
            "nouvelles mines, agrandissement de mines, fonderies, usines de traitement de "
            "minerai, projets de minéraux critiques (lithium, nickel, cobalt, graphite, "
            "terres rares, uranium), mines de potasse, mines d'or, mines de cuivre, minerai "
            "de fer, redémarrage de mines, gestion des résidus miniers, restauration et "
            "remise en état de sites miniers, et raffineries de minéraux"
        ),
    },
    "infrastructure": {
        "name": "Infrastructures civiles et transport",
        "scope": (
            "autoroutes, ponts, échangeurs, tunnels, usines de traitement de l'eau, usines "
            "d'épuration, barrages, protection contre les inondations, transport en commun "
            "(métro, tramway, SRB, train de banlieue — nouvelles lignes et prolongements), "
            "reconstruction de routes, mise à niveau des égouts et aqueducs"
        ),
    },
    "power_energy": {
        "name": "Énergie et électricité",
        "scope": (
            "centrales électriques, parcs solaires, parcs éoliens, centrales hydroélectriques, "
            "petits réacteurs modulaires (PRM), réfection nucléaire, stockage par batteries, "
            "lignes de transport d'électricité, postes de transformation, géothermie, biomasse, "
            "énergie marémotrice, électrolyseurs d'hydrogène et modernisation du réseau"
        ),
    },
    "manufacturing": {
        "name": "Fabrication et industrie",
        "scope": (
            "usines de fabrication, giga-usines de batteries VÉ, assemblage automobile, "
            "semi-conducteurs, transformation alimentaire, fabrication pharmaceutique, "
            "aérospatiale, aciéries, cimenteries, centres de données, modernisation d'usines, "
            "agrandissement et reconversion d'installations industrielles"
        ),
    },
    "transport_logistics": {
        "name": "Ports, aéroports et logistique",
        "scope": (
            "terminaux aéroportuaires, terminaux portuaires, terminaux à conteneurs, lignes "
            "ferroviaires, cours de triage, installations intermodales, traversiers, centres "
            "logistiques, train à grande vitesse, prolongement de pistes, dragage de ports "
            "et modernisation ferroviaire"
        ),
    },
    "healthcare": {
        "name": "Santé et sciences de la vie",
        "scope": (
            "hôpitaux, centres médicaux, CHSLD, établissements de santé mentale, centres de "
            "traitement du cancer, cliniques, laboratoires de recherche, installations de "
            "biotechnologie, résidences pour aînés, agrandissement d'hôpitaux, réaménagement "
            "de campus hospitaliers, rénovation d'urgences et modernisation de centres de "
            "sciences de la santé"
        ),
    },
    "education": {
        "name": "Éducation et recherche",
        "scope": (
            "écoles, bâtiments universitaires, campus de cégeps, centres de recherche, "
            "résidences étudiantes, bibliothèques, centres de formation, modernisation de "
            "campus, mise à niveau parasismique et rénovation écoénergétique"
        ),
    },
    "residential": {
        "name": "Habitation et logement",
        "scope": (
            "tours résidentielles, projets d'habitation, logement abordable, condos, logement "
            "social, logement autochtone, communautés planifiées, immeubles locatifs, "
            "conversion de bureaux en logements, réaménagement de centres commerciaux en "
            "logements, conversion de bâtiments patrimoniaux, revitalisation de HLM et "
            "rénovation de coopératives d'habitation"
        ),
    },
    "commercial_mixed": {
        "name": "Commercial et usage mixte",
        "scope": (
            "développements à usage mixte, tours de bureaux, quartiers de divertissement, "
            "centres de congrès, hôtels et complexes touristiques, arénas et stades, "
            "réaménagement du centre-ville, revitalisation du front de mer, transformation "
            "de centres commerciaux, friches industrielles et quartiers patrimoniaux"
        ),
    },
    "agriculture": {
        "name": "Agriculture et agroalimentaire",
        "scope": (
            "terminaux céréaliers, usines de transformation alimentaire, serres, usines "
            "d'engrais, usines de trituration, transformation de viande, transformation "
            "laitière, aquaculture, brasseries et distilleries, production de cannabis "
            "et modernisation d'installations agricoles"
        ),
    },
    "forestry": {
        "name": "Foresterie et produits du bois",
        "scope": (
            "scieries, usines de pâtes et papiers, bois d'œuvre, bois massif, usines de "
            "granules, panneaux OSB, contreplaqué, modernisation de scieries, conversion "
            "d'usines de pâtes, redémarrage d'usines et conversion à la biomasse"
        ),
    },
    "defence": {
        "name": "Défense et installations fédérales",
        "scope": (
            "bases militaires, chantiers navals, Garde côtière, logements militaires, "
            "installations de la GRC, établissements correctionnels, postes frontaliers, "
            "modernisation de bases et agrandissement de chantiers navals"
        ),
    },
    "telecom": {
        "name": "Télécommunications et numérique",
        "scope": (
            "centres de données, réseaux de fibre optique, large bande, 5G, câbles "
            "sous-marins, stations satellites, installations de calcul d'IA, colocation "
            "et connectivité rurale"
        ),
    },
    "indigenous": {
        "name": "Infrastructures autochtones et réconciliation",
        "scope": (
            "logement des Premières Nations, infrastructures communautaires autochtones, "
            "traitement de l'eau dans les réserves, centres culturels autochtones, "
            "infrastructures inuites, logements métis, énergie propre autochtone, écoles "
            "des Premières Nations, connectivité autochtone, réconciliation économique, "
            "remise en état de sites de pensionnats et restauration du patrimoine autochtone"
        ),
    },
    "environment": {
        "name": "Environnement et décontamination",
        "scope": (
            "centres de recyclage, valorisation énergétique des déchets, compostage, "
            "sites d'enfouissement, déchets dangereux, restauration de milieux humides, "
            "décontamination de friches industrielles, réhabilitation de sites contaminés "
            "et restauration de sites miniers"
        ),
    },
    "tourism_culture": {
        "name": "Tourisme, culture et loisirs",
        "scope": (
            "musées, galeries d'art, salles de spectacle, centres de loisirs, centres "
            "aquatiques, stations de ski, parcs thématiques, casinos, complexes sportifs, "
            "centres communautaires, restauration de sites patrimoniaux, rénovation d'arénas "
            "et revitalisation de parcs"
        ),
    },
    "government": {
        "name": "Édifices gouvernementaux et institutionnels",
        "scope": (
            "palais de justice, édifices gouvernementaux, casernes de pompiers, postes de "
            "police, édifices municipaux, rénovation du Parlement et de l'Assemblée nationale, "
            "centres civiques, modernisation d'édifices gouvernementaux, rénovation d'hôtels "
            "de ville et mise à niveau parasismique"
        ),
    },
}

# ============================================================================
# FRENCH COVERAGE MAP
# ============================================================================

FRENCH_COVERAGE = {
    "QC": {
        "level": "full",
        "geo_name": "au Québec",
        "sectors": "ALL",
        "rationale": "20% of GDP, many projects only in French media",
    },
    "NB": {
        "level": "full",
        "geo_name": "au Nouveau-Brunswick",
        "sectors": "ALL",
        "rationale": "Officially bilingual, ~33% francophone, L'Acadie Nouvelle coverage",
    },
    "NS": {
        "level": "light",
        "geo_name": "en Nouvelle-Écosse et dans les communautés acadiennes",
        "sectors": ["infrastructure", "healthcare", "education", "residential",
                    "commercial_mixed", "indigenous", "government", "tourism_culture"],
        "rationale": "Acadian communities in Clare, Argyle, Chéticamp, Isle Madame",
    },
    "PE": {
        "level": "light",
        "geo_name": "à l'Île-du-Prince-Édouard",
        "sectors": ["infrastructure", "healthcare", "education", "residential",
                    "indigenous", "government", "tourism_culture", "agriculture"],
        "rationale": "Evangeline region francophone community, $5M threshold",
    },
    "ON": {
        "level": "light",
        "geo_name": "dans le nord de l'Ontario et la région d'Ottawa-Gatineau",
        "sectors": ["infrastructure", "healthcare", "education", "residential",
                    "commercial_mixed", "indigenous", "government", "mining"],
        "rationale": "Hearst, Kapuskasing, Sturgeon Falls, Sudbury Franco-Ontarian, Ottawa-Gatineau",
    },
}

# ============================================================================
# CMA AND REGIONAL CLUSTERS
# ============================================================================

URBAN_SECTORS = [
    "infrastructure", "transport_logistics", "healthcare", "education",
    "residential", "commercial_mixed", "tourism_culture", "government",
]

MAJOR_CMAS = [
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton", "Ottawa-Gatineau",
    "Winnipeg", "Quebec City", "Hamilton", "Kitchener-Waterloo",
    "Halifax", "Victoria", "Saskatoon", "Regina", "St. John's",
    "London Ontario", "Windsor Ontario", "Oshawa-Durham", "Barrie",
    "Kelowna", "Abbotsford", "Saint John New Brunswick",
    "Moncton", "Greater Sudbury", "Thunder Bay", "Sherbrooke",
    "Trois-Rivières", "Saguenay", "Lethbridge", "Red Deer",
    "Charlottetown", "Fredericton", "Kamloops", "Prince George", "Nanaimo",
]

RESOURCE_SECTORS = [
    "oil_gas", "mining", "power_energy", "forestry",
    "agriculture", "indigenous", "environment",
]

REGIONAL_CLUSTERS = [
    "Northern BC and Kitimat", "Peace River and northeast BC",
    "Okanagan BC", "Vancouver Island", "Kootenays BC",
    "Fort McMurray and Wood Buffalo Alberta", "Grande Prairie Alberta",
    "Banff-Canmore corridor Alberta",
    "Northern Saskatchewan", "Estevan-Weyburn Saskatchewan",
    "Northern Manitoba and Thompson", "Brandon Manitoba",
    "Niagara Region Ontario", "Windsor-Essex Ontario",
    "Northern Ontario Sudbury Timmins", "Ring of Fire Ontario",
    "Beauce Québec", "Gaspésie Québec", "Abitibi-Témiscamingue Québec",
    "Côte-Nord Québec", "Bas-Saint-Laurent Québec", "Saguenay-Lac-Saint-Jean Québec",
    "Cape Breton Nova Scotia", "Annapolis Valley Nova Scotia",
    "Northern New Brunswick", "Western Newfoundland", "Labrador",
    "Whitehorse Yukon", "Yellowknife NWT", "Iqaluit Nunavut",
]

# ============================================================================
# QUERY BUILDERS
# ============================================================================

def build_en_province_query(province_name, sector_key, sector, threshold):
    return {
        "query": (
            f"List all major {sector['name']} projects in {province_name} "
            f"that have been announced, approved, begun construction, reached a milestone, "
            f"been delayed, cancelled, or completed in the past four weeks or are currently "
            f"under development in {YEAR_RANGE}. Include both new builds (greenfield) and "
            f"redevelopments, renovations, expansions, conversions, modernizations, and "
            f"adaptive reuse projects (brownfield). Specifically include: {sector['scope']}. "
            f"For each project provide: project name, proponent/developer, location, "
            f"estimated value in dollars, current status (proposed, approved, under "
            f"construction, completed, delayed, cancelled), and the source of the information."
        ),
        "province": province_name,
        "sector": sector_key,
        "language": "en",
        "geo_tier": "province",
        "threshold_m": threshold,
    }


def build_fr_province_query(geo_name, sector_key, sector_fr, threshold, province_code):
    return {
        "query": (
            f"Énumérez tous les projets majeurs en {sector_fr['name']} {geo_name} "
            f"qui ont été annoncés, approuvés, dont la construction a commencé, qui ont "
            f"atteint une étape importante, qui ont été retardés, annulés ou achevés au "
            f"cours des quatre dernières semaines ou qui sont actuellement en développement "
            f"en {YEAR_RANGE}. Incluez les nouvelles constructions et les projets de "
            f"réaménagement, rénovation, agrandissement, conversion, modernisation et "
            f"réutilisation adaptative. Incluez spécifiquement : {sector_fr['scope']}. "
            f"Pour chaque projet, indiquez : nom du projet, promoteur, emplacement, "
            f"valeur estimée en dollars, statut actuel (proposé, approuvé, en construction, "
            f"achevé, retardé, annulé) et la source de l'information."
        ),
        "province": province_code,
        "sector": sector_key,
        "language": "fr",
        "geo_tier": "province",
        "threshold_m": threshold,
    }


def build_cma_query(cma_name, sector_key, sector):
    return {
        "query": (
            f"List all major {sector['name']} projects in {cma_name} and surrounding area "
            f"that have been announced, approved, under construction, delayed, or completed "
            f"in the past four weeks or currently under development in {YEAR_RANGE}. "
            f"Include new builds, redevelopments, renovations, expansions, conversions, "
            f"and adaptive reuse. Include: {sector['scope']}. "
            f"For each: project name, proponent, location, estimated value, status, source."
        ),
        "cma": cma_name,
        "sector": sector_key,
        "language": "en",
        "geo_tier": "cma",
    }


def build_regional_query(cluster_name, sector_key, sector):
    return {
        "query": (
            f"List all major {sector['name']} projects in the {cluster_name} region "
            f"announced, approved, under construction, or completed in the past four weeks "
            f"or currently under development in {YEAR_RANGE}. Include new projects and "
            f"expansions, upgrades, modernizations, restarts, remediation, and closures. "
            f"Include: {sector['scope']}. "
            f"For each: project name, proponent, location, estimated value, status, source."
        ),
        "region": cluster_name,
        "sector": sector_key,
        "language": "en",
        "geo_tier": "regional_cluster",
    }


def build_lifecycle_queries():
    queries = []
    for prov_code, prov in PROVINCES_META.items():
        name = prov["en"]
        queries.append({
            "query": (
                f"What major capital projects in {name} have been newly announced, "
                f"approved, or received government funding in the past four weeks? "
                f"Include projects from all sectors — infrastructure, energy, mining, "
                f"healthcare, housing, commercial, industrial, and Indigenous. Include "
                f"both new construction and redevelopments, renovations, or expansions. "
                f"For each: name, proponent, value, sector, status, source."
            ),
            "province": prov_code,
            "sector": "lifecycle_new",
            "language": "en",
            "geo_tier": "province",
        })
        queries.append({
            "query": (
                f"What major capital projects in {name} have been delayed, cancelled, "
                f"experienced cost overruns, or had significant status changes in the "
                f"past four weeks? Include all sectors. "
                f"For each: name, proponent, original and revised value, status change, source."
            ),
            "province": prov_code,
            "sector": "lifecycle_changes",
            "language": "en",
            "geo_tier": "province",
        })

    for prov_code, geo_name in [("QC", "au Québec"), ("NB", "au Nouveau-Brunswick")]:
        queries.append({
            "query": (
                f"Quels projets majeurs d'immobilisations {geo_name} ont été nouvellement "
                f"annoncés, approuvés ou ont reçu du financement gouvernemental au cours "
                f"des quatre dernières semaines ? Incluez tous les secteurs — infrastructure, "
                f"énergie, mines, santé, habitation, commercial, industriel et autochtone. "
                f"Incluez les nouvelles constructions et les réaménagements. "
                f"Pour chaque projet : nom, promoteur, valeur, secteur, statut, source."
            ),
            "province": prov_code,
            "sector": "lifecycle_new",
            "language": "fr",
            "geo_tier": "province",
        })
        queries.append({
            "query": (
                f"Quels projets majeurs d'immobilisations {geo_name} ont été retardés, "
                f"annulés, ont connu des dépassements de coûts ou ont subi des changements "
                f"importants de statut au cours des quatre dernières semaines ? "
                f"Pour chaque projet : nom, promoteur, valeur originale et révisée, "
                f"changement de statut, source."
            ),
            "province": prov_code,
            "sector": "lifecycle_changes",
            "language": "fr",
            "geo_tier": "province",
        })

    return queries


# ============================================================================
# MAIN GENERATOR
# ============================================================================

def generate_all_queries():
    queries = []
    stats = defaultdict(int)

    # 1. Province × Sector (English)
    for prov_code, sectors in AFFINITY.items():
        prov_name = PROVINCES_META[prov_code]["en"]
        threshold = GDP_THRESHOLDS[prov_code]
        for sector_key in sectors:
            sector = SECTOR_PROMPTS_EN[sector_key]
            q = build_en_province_query(prov_name, sector_key, sector, threshold)
            queries.append(q)
            stats["en_province_sector"] += 1

    # 2. French Province × Sector
    for prov_code, config in FRENCH_COVERAGE.items():
        geo_name = config["geo_name"]
        threshold = GDP_THRESHOLDS[prov_code]
        if config["sectors"] == "ALL":
            sector_keys = list(SECTOR_PROMPTS_FR.keys())
        else:
            sector_keys = config["sectors"]
        for sector_key in sector_keys:
            if sector_key in SECTOR_PROMPTS_FR:
                sector_fr = SECTOR_PROMPTS_FR[sector_key]
                q = build_fr_province_query(geo_name, sector_key, sector_fr, threshold, prov_code)
                queries.append(q)
                stats["fr_province_sector"] += 1

    # 3. CMA × Urban Sector
    for cma in MAJOR_CMAS:
        for sector_key in URBAN_SECTORS:
            sector = SECTOR_PROMPTS_EN[sector_key]
            q = build_cma_query(cma, sector_key, sector)
            queries.append(q)
            stats["cma_sector"] += 1

    # 4. Regional Cluster × Resource Sector
    for cluster in REGIONAL_CLUSTERS:
        for sector_key in RESOURCE_SECTORS:
            sector = SECTOR_PROMPTS_EN[sector_key]
            q = build_regional_query(cluster, sector_key, sector)
            queries.append(q)
            stats["regional_sector"] += 1

    # 5. Lifecycle queries
    lifecycle = build_lifecycle_queries()
    queries.extend(lifecycle)
    stats["lifecycle"] = len(lifecycle)

    return queries, stats


def main():
    queries, stats = generate_all_queries()
    total = len(queries)
    daily = total / 7

    print("=" * 80)
    print("COMPOUND QUERY SYSTEM — FINAL STATISTICS")
    print("=" * 80)
    print(f"\n  TOTAL COMPOUND QUERIES: {total}")
    print(f"  Daily average: {daily:.0f} queries/day")
    print(f"  Gemini free tier: 500 RPD")
    print(f"  Utilization: {daily/500*100:.0f}%")
    print(f"  Status: {'FITS' if daily <= 500 else 'OVER'}")

    print(f"\n  BY CATEGORY:")
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"    {cat:<30} {count:>6}  ({count/total*100:>5.1f}%)")

    lang_counts = defaultdict(int)
    for q in queries:
        lang_counts[q["language"]] += 1
    print(f"\n  BY LANGUAGE:")
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
        print(f"    {lang:<10} {count:>6}  ({count/total*100:>5.1f}%)")

    # Export
    output = {
        "generated": "2026-03-04",
        "lookback_weeks": LOOKBACK_WEEKS,
        "total_queries": total,
        "daily_average": round(daily),
        "fits_free_tier": daily <= 500,
        "annual_cost": 0,
        "stats": dict(stats),
        "queries": queries,
    }

    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compound_queries_final.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Exported to {filepath}")
    print(f"\n  {total} queries, {lang_counts.get('en', 0)} EN + {lang_counts.get('fr', 0)} FR")


if __name__ == "__main__":
    main()
