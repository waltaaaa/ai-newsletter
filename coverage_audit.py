"""
coverage_audit.py — Compare SQLite projects against known major project lists.
STEP_2D: Run after first full pipeline execution to measure brownfield coverage.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.

Usage:
    python coverage_audit.py              # Uses SQLite (default)
    python coverage_audit.py --offline    # Uses local project list from last pipeline run
"""

import sys
import os
import json

# Known major Canadian projects (benchmark list)
BENCHMARK_PROJECTS = [
    # Greenfield
    {"name": "Coastal GasLink Pipeline", "province": "BC", "value_millions": 14500, "type": "greenfield"},
    {"name": "Site C Dam", "province": "BC", "value_millions": 16000, "type": "greenfield"},
    {"name": "Gordie Howe International Bridge", "province": "ON", "value_millions": 6400, "type": "greenfield"},
    {"name": "Ontario Line", "province": "ON", "value_millions": 19000, "type": "greenfield"},
    {"name": "Eglinton Crosstown LRT", "province": "ON", "value_millions": 12800, "type": "greenfield"},
    {"name": "REM Montreal", "province": "QC", "value_millions": 7950, "type": "greenfield"},
    {"name": "Trans Mountain Pipeline", "province": "AB", "value_millions": 34200, "type": "expansion"},
    {"name": "LNG Canada", "province": "BC", "value_millions": 40000, "type": "greenfield"},
    {"name": "Bay du Nord", "province": "NL", "value_millions": 12000, "type": "greenfield"},
    {"name": "Scarborough Subway Extension", "province": "ON", "value_millions": 5500, "type": "greenfield"},
    # Brownfield / renovation / redevelopment
    {"name": "Portage Place", "province": "MB", "value_millions": 650, "type": "redevelopment"},
    {"name": "Ontario Place", "province": "ON", "value_millions": 3500, "type": "redevelopment"},
    {"name": "Cogswell District", "province": "NS", "value_millions": 2000, "type": "redevelopment"},
    {"name": "LeBreton Flats", "province": "ON", "value_millions": 4000, "type": "redevelopment"},
    {"name": "Calgary Event Centre", "province": "AB", "value_millions": 800, "type": "decommission_replace"},
    {"name": "Zibi", "province": "ON", "value_millions": 1500, "type": "redevelopment"},
    {"name": "The Well", "province": "ON", "value_millions": 3000, "type": "redevelopment"},
    {"name": "Sugar Wharf", "province": "ON", "value_millions": 2000, "type": "redevelopment"},
]


def _fuzzy_match(name, project_names):
    """Check if a known project name matches any project in the database."""
    name_lower = name.lower()
    for fn in project_names:
        fn_lower = fn.lower()
        if name_lower in fn_lower or fn_lower in name_lower:
            return fn
        # Check core words (first 2 significant words)
        name_words = [w for w in name_lower.split() if len(w) > 2][:2]
        if all(w in fn_lower for w in name_words):
            return fn
    return None


def run_coverage_audit(all_projects):
    """Compare SQLite projects against known major projects.

    Args:
        all_projects: list of project dicts from SQLite
    """
    project_names = [p.get("name", "") for p in all_projects if p.get("name")]

    found = 0
    missing = []

    print(f"\n{'=' * 60}")
    print(f"  COVERAGE AUDIT — {len(BENCHMARK_PROJECTS)} benchmark projects")
    print(f"  vs {len(project_names)} SQLite projects")
    print(f"{'=' * 60}\n")

    for known in BENCHMARK_PROJECTS:
        match = _fuzzy_match(known["name"], project_names)

        if match:
            found += 1
            print(f"  [FOUND] {known['name']} ({known['province']}, {known['type']}) -> '{match}'")
        else:
            missing.append(known)
            print(f"  [MISS]  {known['name']} ({known['province']}, {known['type']})")

    total = len(BENCHMARK_PROJECTS)
    greenfield_total = sum(1 for k in BENCHMARK_PROJECTS if k["type"] == "greenfield")
    brownfield_total = total - greenfield_total

    greenfield_found = sum(1 for k in BENCHMARK_PROJECTS
                          if k["type"] == "greenfield"
                          and _fuzzy_match(k["name"], project_names))
    brownfield_found = found - greenfield_found

    print(f"\n  {'=' * 60}")
    print(f"  COVERAGE: {found}/{total} ({found/total*100:.0f}%)")
    print(f"  Greenfield: {greenfield_found}/{greenfield_total} "
          f"({greenfield_found/greenfield_total*100:.0f}%)")
    print(f"  Brownfield: {brownfield_found}/{brownfield_total} "
          f"({brownfield_found/brownfield_total*100:.0f}%)")
    print(f"  {'=' * 60}")

    if missing:
        print(f"\n  MISSING PROJECTS ({len(missing)}):")
        for m in missing:
            print(f"    - {m['name']} ({m['province']}, ${m['value_millions']}M, {m['type']})")

    return {
        "total": total,
        "found": found,
        "greenfield_found": greenfield_found,
        "greenfield_total": greenfield_total,
        "brownfield_found": brownfield_found,
        "brownfield_total": brownfield_total,
        "missing": missing,
    }


if __name__ == "__main__":
    if "--offline" in sys.argv:
        # Look for a local projects dump
        dump_path = os.path.join(os.path.dirname(__file__), "projects_dump.json")
        if os.path.exists(dump_path):
            with open(dump_path, "r", encoding="utf-8") as f:
                projects = json.load(f)
            run_coverage_audit(projects)
        else:
            print(f"  No offline dump found at {dump_path}")
            print("  Run the pipeline first, or use without --offline for SQLite")
    else:
        # Load from SQLite
        try:
            from db import init_db, get_all_projects
            conn = init_db()
            projects = get_all_projects(conn)
            conn.close()
            print(f"  Loaded {len(projects)} projects from SQLite")
            run_coverage_audit(projects)
        except Exception as e:
            print(f"  Error loading from SQLite: {e}")
            print("  Try: python coverage_audit.py --offline")
