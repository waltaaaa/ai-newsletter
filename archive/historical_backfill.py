"""
historical_backfill.py -- One-time seed of major Canadian infrastructure projects.

Seeds the Firestore /projects collection with well-known mega-projects from
ReNew Canada Top 100, government announcements, and industry databases.

Usage:
    python historical_backfill.py          # dry-run (prints what would be added)
    python historical_backfill.py --apply  # writes to Firestore
"""

import sys
import os

# ── Seed data: major Canadian infrastructure projects ──────────────────────

SEED_PROJECTS = [
    # Energy & Resources
    {"name": "LNG Canada Phase 1", "province": "British Columbia", "sector": "Energy", "value": "C$18.0B", "status": "Under Construction", "cma": "Kitimat", "project_type": "new_build", "description": "Shell-led LNG export facility in Kitimat, BC. Phase 1 capacity 14 Mtpa."},
    {"name": "LNG Canada Phase 2", "province": "British Columbia", "sector": "Energy", "value": "C$18.0B", "status": "Proposed", "cma": "Kitimat", "project_type": "expansion", "description": "Second phase of LNG Canada facility, doubling capacity to 28 Mtpa."},
    {"name": "Coastal GasLink Pipeline", "province": "British Columbia", "sector": "Energy", "value": "C$14.5B", "status": "Under Construction", "project_type": "new_build", "description": "670 km natural gas pipeline from Dawson Creek to Kitimat LNG facility."},
    {"name": "Trans Mountain Pipeline Expansion", "province": "Alberta", "sector": "Energy", "value": "C$34.2B", "status": "Completed", "cma": "Edmonton", "project_type": "expansion", "description": "Twinning of existing pipeline from Edmonton to Burnaby, tripling capacity to 890,000 bpd."},
    {"name": "Site C Clean Energy Project", "province": "British Columbia", "sector": "Energy", "value": "C$16.0B", "status": "Under Construction", "cma": "Fort St. John", "project_type": "new_build", "description": "BC Hydro 1,100 MW hydroelectric dam on Peace River."},
    {"name": "Bruce Power Major Component Replacement", "province": "Ontario", "sector": "Energy", "value": "C$13.0B", "status": "Under Construction", "cma": "Bruce County", "project_type": "refurbishment", "description": "Refurbishment of Units 3-8 at Bruce Nuclear Generating Station."},
    {"name": "Darlington Nuclear Refurbishment", "province": "Ontario", "sector": "Energy", "value": "C$12.8B", "status": "Under Construction", "cma": "Clarington", "project_type": "refurbishment", "description": "Ontario Power Generation refurbishment of 4 CANDU reactors at Darlington."},
    {"name": "Cedar LNG", "province": "British Columbia", "sector": "Energy", "value": "C$3.0B", "status": "Under Construction", "cma": "Kitimat", "project_type": "new_build", "description": "Floating LNG facility by Pembina Pipeline and Haisla Nation."},
    {"name": "Woodfibre LNG", "province": "British Columbia", "sector": "Energy", "value": "C$1.6B", "status": "Under Construction", "cma": "Squamish", "project_type": "new_build", "description": "Small-scale LNG export facility near Squamish, BC."},
    {"name": "Bay du Nord Offshore Oil Project", "province": "Newfoundland and Labrador", "sector": "Energy", "value": "C$9.0B", "status": "Approved", "project_type": "new_build", "description": "Equinor-led deepwater oil development, 500 km east of St. John's."},
    {"name": "Muskrat Falls Hydroelectric", "province": "Newfoundland and Labrador", "sector": "Energy", "value": "C$13.1B", "status": "Completed", "project_type": "new_build", "description": "824 MW hydroelectric generating facility on Lower Churchill River."},

    # Transit & Transportation
    {"name": "Ontario Line", "province": "Ontario", "sector": "Transit", "value": "C$19.0B", "status": "Under Construction", "cma": "Toronto", "project_type": "new_build", "description": "15.6 km subway line from Ontario Science Centre to Exhibition Place."},
    {"name": "Eglinton Crosstown LRT", "province": "Ontario", "sector": "Transit", "value": "C$12.8B", "status": "Under Construction", "cma": "Toronto", "project_type": "new_build", "description": "19 km LRT along Eglinton Avenue with 25 stations."},
    {"name": "Scarborough Subway Extension", "province": "Ontario", "sector": "Transit", "value": "C$5.5B", "status": "Under Construction", "cma": "Toronto", "project_type": "extension", "description": "7.8 km extension of Line 2 to Scarborough Town Centre."},
    {"name": "Yonge North Subway Extension", "province": "Ontario", "sector": "Transit", "value": "C$5.6B", "status": "Under Construction", "cma": "Toronto", "project_type": "extension", "description": "8 km extension of Line 1 from Finch to Richmond Hill."},
    {"name": "REM (Reseau express metropolitain)", "province": "Quebec", "sector": "Transit", "value": "C$7.9B", "status": "Under Construction", "cma": "Montreal", "project_type": "new_build", "description": "67 km automated light metro system with 26 stations."},
    {"name": "REM de l'Est", "province": "Quebec", "sector": "Transit", "value": "C$10.0B", "status": "Proposed", "cma": "Montreal", "project_type": "new_build", "description": "32 km eastern extension of Montreal's automated light metro."},
    {"name": "Gordie Howe International Bridge", "province": "Ontario", "sector": "Transportation", "value": "C$6.4B", "status": "Under Construction", "cma": "Windsor", "project_type": "new_build", "description": "New cable-stayed bridge connecting Windsor, ON to Detroit, MI."},
    {"name": "Calgary Green Line LRT", "province": "Alberta", "sector": "Transit", "value": "C$5.5B", "status": "Under Construction", "cma": "Calgary", "project_type": "new_build", "description": "46 km LRT line through central Calgary."},
    {"name": "Edmonton Valley Line West LRT", "province": "Alberta", "sector": "Transit", "value": "C$2.6B", "status": "Under Construction", "cma": "Edmonton", "project_type": "extension", "description": "14 km LRT extension from downtown to Lewis Farms."},
    {"name": "Surrey-Langley SkyTrain", "province": "British Columbia", "sector": "Transit", "value": "C$4.0B", "status": "Under Construction", "cma": "Vancouver", "project_type": "extension", "description": "16 km extension of Expo Line from King George to Langley."},
    {"name": "Broadway Subway (Millennium Line Extension)", "province": "British Columbia", "sector": "Transit", "value": "C$2.8B", "status": "Under Construction", "cma": "Vancouver", "project_type": "extension", "description": "5.7 km underground extension from VCC-Clark to Arbutus."},

    # Healthcare
    {"name": "New Civic Hospital Campus", "province": "Ontario", "sector": "Healthcare", "value": "C$2.8B", "status": "Under Construction", "cma": "Ottawa", "project_type": "new_build", "description": "Replacement campus for The Ottawa Hospital Civic Campus."},
    {"name": "St. Paul's Hospital Replacement", "province": "British Columbia", "sector": "Healthcare", "value": "C$2.2B", "status": "Under Construction", "cma": "Vancouver", "project_type": "new_build", "description": "New acute care hospital at the former False Creek Flats."},
    {"name": "Centre hospitalier de l'Universite de Montreal (CHUM)", "province": "Quebec", "sector": "Healthcare", "value": "C$3.6B", "status": "Completed", "cma": "Montreal", "project_type": "new_build", "description": "Major academic health center in downtown Montreal."},
    {"name": "McGill University Health Centre (MUHC) Glen Site", "province": "Quebec", "sector": "Healthcare", "value": "C$2.3B", "status": "Completed", "cma": "Montreal", "project_type": "new_build", "description": "Super-hospital complex in NDG neighborhood."},

    # Mining
    {"name": "Cote Gold Mine", "province": "Ontario", "sector": "Mining", "value": "C$2.0B", "status": "Under Construction", "project_type": "new_build", "description": "IAMGOLD open-pit gold mine near Gogama, Ontario."},
    {"name": "Greenstone Gold Mine", "province": "Ontario", "sector": "Mining", "value": "C$1.3B", "status": "Under Construction", "project_type": "new_build", "description": "Equinox Gold open-pit mine near Geraldton, Ontario."},
    {"name": "BHP Jansen Potash Mine", "province": "Saskatchewan", "sector": "Mining", "value": "C$14.0B", "status": "Under Construction", "project_type": "new_build", "description": "World's largest potash mine, 140 km east of Saskatoon."},

    # Water & Wastewater
    {"name": "Ashbridges Bay Treatment Plant Outfall", "province": "Ontario", "sector": "Water", "value": "C$3.2B", "status": "Under Construction", "cma": "Toronto", "project_type": "new_build", "description": "New outfall tunnel for Toronto's largest wastewater treatment plant."},

    # Defence
    {"name": "Canadian Surface Combatant (CSC)", "province": "Nova Scotia", "sector": "Defence", "value": "C$77.3B", "status": "Under Construction", "cma": "Halifax", "project_type": "new_build", "description": "15 Type 26 frigates for the Royal Canadian Navy, built at Irving Shipbuilding."},
    {"name": "Arctic and Offshore Patrol Ships (AOPS)", "province": "Nova Scotia", "sector": "Defence", "value": "C$4.3B", "status": "Under Construction", "cma": "Halifax", "project_type": "new_build", "description": "6 Harry DeWolf-class patrol vessels for the Royal Canadian Navy."},
]


def run_historical_backfill(db, dry_run=True):
    """Seed Firestore with well-known mega-projects.

    Uses upsert_flat_projects() to leverage existing dedup logic (fuzzy matching).

    Args:
        db: Firestore client
        dry_run: If True, only prints what would be added without writing
    """
    from project_sync import upsert_flat_projects

    # Tag all seed projects
    tagged = []
    for p in SEED_PROJECTS:
        proj = dict(p)
        proj['discovery_source'] = 'historical_backfill'
        proj['discovery_sources'] = ['historical_backfill']
        proj['confidence'] = 0.7  # high base confidence for well-known projects
        proj['announced'] = '2020-01-01'  # approximate; will be refined by lifecycle monitor
        tagged.append(proj)

    if dry_run:
        print(f"\n[BACKFILL] DRY RUN - would upsert {len(tagged)} projects:")
        for p in tagged:
            print(f"  {p['province']:25s} {p['name']:45s} {p.get('value', ''):>12s}")
        print("\nRun with --apply to write to Firestore.")
        return {"total": len(tagged), "dry_run": True}

    print(f"\n[BACKFILL] Upserting {len(tagged)} seed projects...")
    upsert_flat_projects(db, tagged)
    return {"total": len(tagged), "dry_run": False}


if __name__ == "__main__":
    # NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
    # This is a one-time/annual seeding script.
    apply = "--apply" in sys.argv

    from db import init_db as _init_db
    db = _init_db()
    result = run_historical_backfill(db, dry_run=not apply)
    db.close()
    print(f"\nResult: {result}")
