"""
coverage_audit.py — Compare SQLite projects against known major project lists.
STEP_2D: Run after first full pipeline execution to measure brownfield coverage.

Includes typed miss classification (Phase 6) — identifies WHY projects were missed.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.

Usage:
    python coverage_audit.py              # Uses SQLite (default)
    python coverage_audit.py --offline    # Uses local project list from last pipeline run
    python coverage_audit.py --classify   # Run miss-type classification and store results
"""

import sys
import os
import json
from urllib.parse import urlparse

# Miss-type classification taxonomy
MISS_TYPES = {
    'source_gap':     'No feed or registry covers this source',
    'parser_gap':     'Feed exists but extraction failed or was skipped',
    'filter_gap':     'Article fetched but filtered out (L1-L6)',
    'extraction_gap': 'Classified relevant but extraction produced no project',
    'matching_gap':   'Extracted but incorrectly deduped or merged',
    'threshold_gap':  'Filtered out by province GDP value threshold',
    'language_gap':   'Source is in a language not covered by queries/feeds',
    'timeliness_gap': 'Project discovered but too late (>30 days after announcement)',
}

# Known major Canadian projects (benchmark list)
BENCHMARK_PROJECTS = [
    # Greenfield
    {"name": "Coastal GasLink Pipeline", "province": "BC", "value_millions": 14500, "type": "greenfield", "sector": "oil_gas"},
    {"name": "Site C Dam", "province": "BC", "value_millions": 16000, "type": "greenfield", "sector": "power_energy"},
    {"name": "Gordie Howe International Bridge", "province": "ON", "value_millions": 6400, "type": "greenfield", "sector": "infrastructure"},
    {"name": "Ontario Line", "province": "ON", "value_millions": 19000, "type": "greenfield", "sector": "infrastructure"},
    {"name": "Eglinton Crosstown LRT", "province": "ON", "value_millions": 12800, "type": "greenfield", "sector": "infrastructure"},
    {"name": "REM Montreal", "province": "QC", "value_millions": 7950, "type": "greenfield", "sector": "infrastructure"},
    {"name": "Trans Mountain Pipeline", "province": "AB", "value_millions": 34200, "type": "expansion", "sector": "oil_gas"},
    {"name": "LNG Canada", "province": "BC", "value_millions": 40000, "type": "greenfield", "sector": "oil_gas"},
    {"name": "Bay du Nord", "province": "NL", "value_millions": 12000, "type": "greenfield", "sector": "oil_gas"},
    {"name": "Scarborough Subway Extension", "province": "ON", "value_millions": 5500, "type": "greenfield", "sector": "infrastructure"},
    # Brownfield / renovation / redevelopment
    {"name": "Portage Place", "province": "MB", "value_millions": 650, "type": "redevelopment", "sector": "commercial_mixed"},
    {"name": "Ontario Place", "province": "ON", "value_millions": 3500, "type": "redevelopment", "sector": "tourism_culture"},
    {"name": "Cogswell District", "province": "NS", "value_millions": 2000, "type": "redevelopment", "sector": "commercial_mixed"},
    {"name": "LeBreton Flats", "province": "ON", "value_millions": 4000, "type": "redevelopment", "sector": "commercial_mixed"},
    {"name": "Calgary Event Centre", "province": "AB", "value_millions": 800, "type": "decommission_replace", "sector": "tourism_culture"},
    {"name": "Zibi", "province": "ON", "value_millions": 1500, "type": "redevelopment", "sector": "commercial_mixed"},
    {"name": "The Well", "province": "ON", "value_millions": 3000, "type": "redevelopment", "sector": "commercial_mixed"},
    {"name": "Sugar Wharf", "province": "ON", "value_millions": 2000, "type": "redevelopment", "sector": "residential"},
]

# RSS feed domains we monitor (subset for domain matching)
_KNOWN_FEED_DOMAINS = {
    'gc.ca', 'canada.ca', 'cbc.ca', 'globalnews.ca', 'theglobeandmail.com',
    'nationalpost.com', 'bnnbloomberg.ca', 'reuters.com', 'constructionlinks.ca',
    'dailycommercialnews.com', 'renewcanada.net', 'mining.com', 'jwnenergy.com',
}


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


def classify_miss(known_project, conn):
    """Determine WHY a known project was missed by the pipeline.

    Args:
        known_project: dict with name, province, sector
        conn: sqlite3.Connection with documents table

    Returns:
        tuple of (miss_type, description)
    """
    name = known_project['name']
    province = known_project.get('province', '')
    name_lower = name.lower()
    name_words = [w for w in name_lower.split() if len(w) > 3]

    # Check documents table for matching documents
    try:
        # Search by name similarity in title
        docs = conn.execute("""
            SELECT url, title, is_relevant, classification_json, fetch_date
            FROM documents
            WHERE title IS NOT NULL
            ORDER BY fetch_date DESC
            LIMIT 10000
        """).fetchall()
    except Exception:
        docs = []

    matching_docs = []
    for doc in docs:
        title = (doc['title'] or '').lower()
        # Check if at least 2 name words appear in the title
        matches = sum(1 for w in name_words if w in title)
        if matches >= 2 or name_lower in title:
            matching_docs.append(dict(doc))

    if matching_docs:
        # Document exists — check what happened to it
        relevant_docs = [d for d in matching_docs if d.get('is_relevant')]
        irrelevant_docs = [d for d in matching_docs if not d.get('is_relevant')]

        if relevant_docs:
            # Classified relevant but no project created
            return ('extraction_gap',
                    f'Document found and classified relevant but no project extracted. '
                    f'Title: "{relevant_docs[0].get("title", "")[:80]}"')
        elif irrelevant_docs:
            # Classified irrelevant — filter gap
            return ('filter_gap',
                    f'Document found but classified as irrelevant. '
                    f'Title: "{irrelevant_docs[0].get("title", "")[:80]}"')

    # No matching documents — check if source domain is covered
    # Quebec projects may be language gaps
    if province == 'QC':
        return ('language_gap',
                f'Quebec project "{name}" — may require French-language queries/feeds')

    # Check if the source domain is in our feed list
    return ('source_gap',
            f'No matching documents found for "{name}" — '
            f'source may not be covered by current feeds/queries')


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


def run_miss_classification(conn):
    """Classify WHY each missing benchmark project was missed.

    Args:
        conn: sqlite3.Connection from db.py

    Returns:
        list of miss classification dicts
    """
    from db import get_all_projects
    all_projects = get_all_projects(conn)
    project_names = [p.get("name", "") for p in all_projects if p.get("name")]

    # Find missing projects
    missing = [
        known for known in BENCHMARK_PROJECTS
        if not _fuzzy_match(known["name"], project_names)
    ]

    if not missing:
        print("  [MISS AUDIT] All benchmark projects found — no gaps to classify")
        return []

    print(f"\n{'=' * 60}")
    print(f"  MISS-TYPE CLASSIFICATION — {len(missing)} missing projects")
    print(f"{'=' * 60}\n")

    results = []
    for known in missing:
        miss_type, description = classify_miss(known, conn)

        result = {
            'province': known['province'],
            'sector': known.get('sector', ''),
            'miss_type': miss_type,
            'description': description,
            'suggested_action': MISS_TYPES.get(miss_type, ''),
        }
        results.append(result)

        print(f"  [{miss_type.upper()}] {known['name']} ({known['province']})")
        print(f"    {description}")

    # Store results in miss_audit_results table
    for r in results:
        try:
            conn.execute("""
                INSERT INTO miss_audit_results
                (province, sector, miss_type, description, suggested_action)
                VALUES (?, ?, ?, ?, ?)
            """, (r['province'], r['sector'], r['miss_type'],
                  r['description'], r['suggested_action']))
        except Exception as e:
            print(f"  [WARN] Failed to store miss result: {e}")
    conn.commit()

    # Summary by type
    from collections import Counter
    type_counts = Counter(r['miss_type'] for r in results)
    print(f"\n  {'=' * 60}")
    print(f"  MISS-TYPE SUMMARY:")
    for mt, count in type_counts.most_common():
        print(f"    {mt}: {count} ({MISS_TYPES.get(mt, '')})")
    print(f"  {'=' * 60}")

    return results


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
    elif "--classify" in sys.argv:
        try:
            from db import init_db
            conn = init_db()
            run_miss_classification(conn)
            conn.close()
        except Exception as e:
            print(f"  Error: {e}")
    else:
        # Load from SQLite
        try:
            from db import init_db, get_all_projects
            conn = init_db()
            projects = get_all_projects(conn)
            print(f"  Loaded {len(projects)} projects from SQLite")
            result = run_coverage_audit(projects)
            # Also run miss classification if there are missing projects
            if result.get('missing'):
                run_miss_classification(conn)
            conn.close()
        except Exception as e:
            print(f"  Error loading from SQLite: {e}")
            print("  Try: python coverage_audit.py --offline")
