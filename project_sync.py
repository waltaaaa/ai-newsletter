"""
project_sync.py — Cumulative Project Tracker for CAN-MACRO

Manages a persistent /projects SQLite table that grows over time
instead of being overwritten each pipeline run.

Delegates all persistence to db.py's upsert_project() which enforces:
  - Evidence merge (no URL duplicates)
  - Status non-regression
  - Confidence floor

Usage in update_dashboard.py:
    from project_sync import upsert_projects, upsert_flat_projects

    # After Gemini generates the payload...
    if payload.get('provinces'):
        upsert_projects(conn, payload['provinces'])
"""

import re
from datetime import date
from difflib import SequenceMatcher
from project_schema import normalize_project_type, is_brownfield
from db import upsert_project, get_project, get_all_projects


def _to_numeric_confidence(val) -> float:
    """Convert confidence value to float. Handles string labels and numeric values."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.lower().strip()
        if s == 'verified':
            return 0.8
        elif s == 'unverified':
            return 0.3
        try:
            return float(s)
        except ValueError:
            return 0.3
    return 0.3


def _parse_value_millions(val_str: str) -> float:
    """Parse a value string like 'C$650M' or '$2.1B' into millions float."""
    if not val_str:
        return 0
    s = str(val_str).upper().replace(',', '').replace('$', '').replace('C', '')
    m = re.match(r'\s*(\d+(?:\.\d+)?)\s*(B|M|K)?', s)
    if not m:
        return 0
    n = float(m.group(1))
    unit = (m.group(2) or 'M')
    if unit == 'B':
        n *= 1000
    elif unit == 'K':
        n /= 1000
    return n


def normalize_key(name: str, province: str) -> str:
    """Create a stable lookup key from name + province."""
    name_clean = re.sub(r'[^a-z0-9]', '', name.lower())
    prov_clean = re.sub(r'[^a-z0-9]', '', province.lower())
    return f"{name_clean}__{prov_clean}"


def fuzzy_match(new_name: str, existing_names: list, threshold: float = 0.85) -> str | None:
    """
    Find the closest match for a project name in the existing list.
    Handles minor AI wording variations like:
      - "Trans Mountain Pipeline Expansion" vs "Trans Mountain Expansion"
      - "LNG Canada Phase 2" vs "LNG Canada — Phase II"
    """
    best_match = None
    best_ratio = 0.0
    for existing in existing_names:
        ratio = SequenceMatcher(None, new_name.lower(), existing.lower()).ratio()
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = existing
    return best_match


def upsert_projects(conn, provinces_data: list[dict]):
    """
    Merge Gemini-generated projects into the persistent projects table.

    Args:
        conn: sqlite3.Connection from db.py
        provinces_data: List of province dicts from Gemini output, e.g.:
            [
                {
                    "name": "Alberta",
                    "news": "...",
                    "projects": [
                        {"name": "...", "sector": "...", "value": "...", "status": "..."}
                    ]
                }
            ]
    """
    today = date.today().isoformat()
    new_count = 0
    updated_count = 0

    for province in provinces_data:
        prov_name = province.get('name', '')
        if not prov_name:
            continue

        for project in province.get('projects', []):
            proj_name = project.get('name', '')
            if not proj_name:
                continue

            # Build a normalized project dict for upsert_project
            ptype = normalize_project_type(project.get('project_type', ''))

            # Check if project already exists to count new vs updated
            key = normalize_key(proj_name, prov_name)
            existing = get_project(conn, key)

            proj_dict = {
                'name': proj_name,
                'province': prov_name,
                'description': project.get('description', ''),
                'sector': project.get('sector', 'General'),
                'cma': project.get('cma', ''),
                'tags': project.get('tags', []),
                'sources': project.get('sources', []),
                'source': project.get('source', ''),
                'value': project.get('value', '\u2014'),
                'status': project.get('status', 'Announced'),
                'completionDate': project.get('completionDate', ''),
                'project_type': ptype,
                'is_brownfield': is_brownfield(ptype),
                'confidence': project.get('confidence', 0.3),
                'evidence': project.get('evidence', []),
                'discovery_source': project.get('discovery_source', 'gemini_analysis'),
                'discovery_sources': project.get('discovery_sources', []),
                'lastSeen': today,
            }

            try:
                upsert_project(conn, proj_dict)
                if existing is None:
                    new_count += 1
                    print(f"  [NEW] {prov_name}: {proj_name}")
                else:
                    updated_count += 1
            except Exception as e:
                print(f"  [ERROR] Upsert failed for '{proj_name}': {e}")

    total_gemini = sum(len(p.get('projects', [])) for p in provinces_data)
    print(f"\nProject sync complete:")
    print(f"  From Gemini:    {total_gemini}")
    print(f"  New:            {new_count}")
    print(f"  Updated:        {updated_count}")


def upsert_flat_projects(conn, projects: list[dict]):
    """
    Merge a flat list of project dicts into the persistent projects table.
    Each dict must have a 'province' field alongside the standard project fields.
    Used by the weekly project research pipeline in update_dashboard.py.

    Args:
        conn: sqlite3.Connection from db.py
        projects: list of project dicts with 'name' and 'province' required
    """
    today = date.today().isoformat()
    new_count = 0
    updated_count = 0
    skipped = 0

    for project in projects:
        proj_name = (project.get('name') or '').strip()
        prov_name = (project.get('province') or '').strip()
        if not proj_name or not prov_name:
            skipped += 1
            continue

        # Normalize announced date
        announced = (project.get('announced') or today).strip()
        if len(announced) == 7:
            announced += '-01'
        elif len(announced) == 4:
            announced += '-01-01'
        elif len(announced) < 4:
            announced = today

        ptype = normalize_project_type(project.get('project_type', ''))

        # Check if project already exists to count new vs updated
        key = normalize_key(proj_name, prov_name)
        existing = get_project(conn, key)

        proj_dict = {
            'name':              proj_name,
            'description':       project.get('description') or '',
            'province':          prov_name,
            'sector':            project.get('sector') or 'Other',
            'naics_code':        project.get('naics_code') or '',
            'cma':               project.get('cma') or '',
            'tags':              project.get('tags') or [],
            'value':             project.get('value') or '\u2014',
            'status':            project.get('status') or 'Announced',
            'completionDate':    project.get('completionDate') or '',
            'sources':           project.get('sources') or [],
            'source':            '',
            'firstTracked':      announced,
            'lastUpdated':       today,
            'lastSeen':          today,
            'project_type':      ptype,
            'is_brownfield':     is_brownfield(ptype),
            'discovery_source':  project.get('discovery_source', ''),
            'discovery_sources': project.get('discovery_sources', []),
            'confidence':        project.get('confidence', 0.3),
            'evidence':          project.get('evidence', []),
            'evidence_count':    project.get('evidence_count', len(project.get('evidence', []))),
            'has_government_source': project.get('has_government_source', False),
            'has_known_source':  project.get('has_known_source', False),
        }

        try:
            upsert_project(conn, proj_dict)
            if existing is None:
                new_count += 1
                print(f"  [NEW] {prov_name}: {proj_name}")
            else:
                updated_count += 1
        except Exception as e:
            print(f"  [ERROR] Upsert failed for '{proj_name}': {e}")
            skipped += 1

    print(f"\nFlat project sync complete:")
    print(f"  Processed:      {len(projects)}")
    print(f"  New:            {new_count}")
    print(f"  Updated:        {updated_count}")
    print(f"  Skipped:        {skipped}")

    return {"new": new_count, "updated": updated_count, "skipped": skipped}
