"""Add targeted discovery queries for underrepresented sectors.

Additive only — never removes existing queries.
Targets: defence, agriculture, forestry, telecom, environment, indigenous.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CONFIG = Path(__file__).parent.parent / "config" / "compound_queries_final.json"

NEW_QUERIES = [
    # ── DEFENCE (was 16 queries) ──
    {"query": 'Canada "Canadian Surface Combatant" shipbuilding construction', "province": "National"},
    {"query": 'Canada "Arctic Offshore Patrol Ship" construction delivery', "province": "National"},
    {"query": 'Canada "Joint Support Ship" naval construction', "province": "National"},
    {"query": 'Canada "NORAD modernization" construction infrastructure', "province": "National"},
    {"query": 'Canada DND "infrastructure project" construction base', "province": "National"},
    {"query": 'Canada "fighter jet" facility construction hangar', "province": "National"},
    {"query": 'Canada "military housing" construction project', "province": "National"},
    {"query": '"CFB Esquimalt" infrastructure construction project', "province": "British Columbia"},
    {"query": '"CFB Halifax" OR "HMC Dockyard" infrastructure construction', "province": "Nova Scotia"},
    {"query": '"CFB Petawawa" OR "CFB Trenton" OR "CFB Borden" construction project', "province": "Ontario"},
    {"query": '"CFB Edmonton" OR "CFB Cold Lake" OR "CFB Suffield" construction', "province": "Alberta"},
    {"query": '"CFB Gagetown" OR "CFB Shilo" construction infrastructure project', "province": "New Brunswick"},
    {"query": '"CFB Valcartier" OR "CFB Bagotville" construction projet', "province": "Quebec"},
    {"query": '"Irving Shipbuilding" OR "Seaspan" OR "Davie" shipyard construction', "province": "National"},
    {"query": 'Canada defence procurement infrastructure billion million construction', "province": "National"},
    {"query": 'Canada "defence infrastructure" renovation expansion base', "province": "National"},
    {"query": '"5 Wing Goose Bay" OR "CFB Comox" OR "CFB Greenwood" infrastructure', "province": "National"},
    {"query": 'Canada cybersecurity facility data centre military construction', "province": "National"},
    {"query": 'Canada "Royal Canadian Navy" facility upgrade construction', "province": "National"},
    {"query": 'Canada "munitions" OR "ammunition" facility plant construction', "province": "National"},

    # ── AGRICULTURE (was 145 queries but 0 DB projects) ──
    {"query": 'Canada "agri-food processing" plant construction million', "province": "National"},
    {"query": 'Canada "canola crushing" plant facility construction', "province": "National"},
    {"query": 'Canada "grain terminal" OR "grain elevator" expansion construction', "province": "National"},
    {"query": 'Canada "meat processing" OR "abattoir" plant construction million', "province": "National"},
    {"query": 'Canada "dairy processing" plant facility expansion construction', "province": "National"},
    {"query": 'Canada "greenhouse" facility construction expansion million', "province": "Ontario"},
    {"query": 'Canada "vertical farm" OR "indoor agriculture" facility construction', "province": "National"},
    {"query": 'Canada "potato processing" plant construction expansion', "province": "National"},
    {"query": 'Canada "oat processing" OR "plant protein" facility construction', "province": "National"},
    {"query": 'Saskatchewan "canola" OR "pulse" processing plant construction', "province": "Saskatchewan"},
    {"query": 'Alberta "cattle" OR "beef" processing plant construction expansion', "province": "Alberta"},
    {"query": 'Manitoba "grain" OR "oilseed" processing facility construction', "province": "Manitoba"},
    {"query": 'Ontario "food processing" plant facility construction million', "province": "Ontario"},
    {"query": 'Quebec "food processing" usine transformation alimentaire construction', "province": "Quebec"},
    {"query": 'British Columbia "aquaculture" OR "fish processing" facility construction', "province": "British Columbia"},
    {"query": 'Canada "cannabis" facility production expansion construction million', "province": "National"},
    {"query": 'Prince Edward Island "potato" OR "seafood" processing plant', "province": "Prince Edward Island"},
    {"query": 'Canada "grain handling" OR "seed processing" facility construction', "province": "National"},
    {"query": 'New Brunswick "aquaculture" OR "seafood" processing construction', "province": "New Brunswick"},
    {"query": 'Newfoundland "fish" OR "crab" OR "shrimp" processing plant construction', "province": "Newfoundland and Labrador"},

    # ── FORESTRY (was 35) ──
    {"query": 'Canada "pulp mill" construction expansion renovation million', "province": "National"},
    {"query": 'Canada "sawmill" construction modernization expansion project', "province": "National"},
    {"query": 'Canada "wood pellet" plant facility construction', "province": "National"},
    {"query": 'Canada "mass timber" OR "cross-laminated timber" facility production', "province": "National"},
    {"query": 'Canada "paper mill" conversion modernization construction', "province": "National"},
    {"query": 'British Columbia "sawmill" OR "lumber" mill construction expansion', "province": "British Columbia"},
    {"query": 'Quebec scierie OR "usine de pates" construction expansion', "province": "Quebec"},
    {"query": 'Canada "bioenergy" OR "biomass" wood facility construction', "province": "National"},
    {"query": 'Ontario "lumber" OR "wood products" facility construction million', "province": "Ontario"},
    {"query": 'New Brunswick "forestry" OR "lumber" mill construction expansion', "province": "New Brunswick"},

    # ── TELECOM (was 88) ──
    {"query": 'Canada "data centre" OR "data center" construction billion million', "province": "National"},
    {"query": 'Canada "hyperscale" data centre facility construction', "province": "National"},
    {"query": 'Ontario "data centre" construction project million billion', "province": "Ontario"},
    {"query": 'Quebec "centre de donnees" construction projet', "province": "Quebec"},
    {"query": 'Canada "fibre optic" OR "fiber optic" broadband construction project', "province": "National"},
    {"query": 'Canada "5G" tower infrastructure construction deployment', "province": "National"},
    {"query": 'Canada "Universal Broadband" fund project construction', "province": "National"},
    {"query": 'Canada "satellite" ground station facility construction', "province": "National"},
    {"query": 'Canada "subsea cable" OR "submarine cable" construction project', "province": "National"},
    {"query": 'Canada "cloud" infrastructure facility data centre construction', "province": "National"},
    {"query": 'Alberta "data centre" OR "data center" construction project', "province": "Alberta"},
    {"query": 'British Columbia "data centre" construction project million', "province": "British Columbia"},

    # ── ENVIRONMENT (was 508 queries but only 12 DB projects) ──
    {"query": 'Canada "contaminated site" remediation cleanup construction million', "province": "National"},
    {"query": 'Canada "tailings" remediation cleanup project million', "province": "National"},
    {"query": 'Canada "landfill" construction expansion remediation project', "province": "National"},
    {"query": 'Canada "recycling" facility plant construction million', "province": "National"},
    {"query": 'Canada "carbon capture" facility construction project billion', "province": "National"},
    {"query": 'Canada "wastewater treatment" plant construction upgrade million', "province": "National"},
    {"query": 'Canada "water treatment" plant construction upgrade million', "province": "National"},

    # ── INDIGENOUS (was 138 but only 5 DB projects) ──
    {"query": 'Canada "First Nation" infrastructure project construction million', "province": "National"},
    {"query": 'Canada "Indigenous" community infrastructure construction housing', "province": "National"},
    {"query": 'Canada "Inuit" infrastructure housing construction project', "province": "Nunavut"},
    {"query": 'Canada "Metis" infrastructure construction project', "province": "National"},
    {"query": 'Canada "Indigenous" clean water infrastructure construction', "province": "National"},
    {"query": 'Canada "First Nation" "economic development" facility construction', "province": "National"},
]


def main():
    with open(CONFIG) as f:
        data = json.load(f)

    queries = data["queries"]
    existing_texts = {(q.get("query", "") if isinstance(q, dict) else str(q)).lower() for q in queries}

    added = 0
    for nq in NEW_QUERIES:
        if nq["query"].lower() not in existing_texts:
            queries.append(nq)
            existing_texts.add(nq["query"].lower())
            added += 1

    data["queries"] = queries
    data["total_queries"] = len(queries)

    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Added {added} new queries (skipped {len(NEW_QUERIES) - added} duplicates)")
    print(f"Total queries: {len(queries)}")

    # Show new sector distribution
    sector_keywords = {
        "defence": ["defence", "defense", "military", "DND", "naval", "CFB", "shipbuilding", "NORAD", "fighter", "munitions"],
        "agriculture": ["agri", "farm", "grain", "canola", "dairy", "food processing", "meat", "potato", "aquaculture", "greenhouse", "cannabis", "abattoir", "seafood", "fish"],
        "forestry": ["forestry", "pulp", "lumber", "sawmill", "wood", "timber", "pellet", "scierie", "biomass", "mass timber"],
        "telecom": ["telecom", "broadband", "fibre", "fiber", "5G", "data cent", "satellite", "subsea cable", "cloud infra"],
        "environment": ["remediation", "cleanup", "contaminated", "waste", "recycling", "brownfield", "landfill", "carbon capture", "tailings", "wastewater", "water treatment"],
        "indigenous": ["indigenous", "First Nation", "Inuit", "Metis", "Aboriginal"],
    }
    print("\nUpdated sector query counts:")
    for sector in sorted(sector_keywords.keys()):
        kws = sector_keywords[sector]
        count = sum(1 for q in queries
                    if any(kw.lower() in (q.get("query", "") if isinstance(q, dict) else str(q)).lower()
                           for kw in kws))
        print(f"  {sector:<15s}: {count} queries")


if __name__ == "__main__":
    main()
