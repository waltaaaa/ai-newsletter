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
from collections import Counter
from datetime import date
from difflib import SequenceMatcher
from project_schema import normalize_project_type, is_brownfield, normalize_status
from db import (upsert_project, get_project, get_all_projects,
                insert_evidence, insert_project_event,
                resolve_organization, link_project_organization,
                insert_project_identifier)


# Province sanity-check used by the upsert boundary (D-2). Anything that
# survives PROV_NAMES normalization should fall into this set; otherwise the
# row is rejected before it reaches db.upsert_project. Source of truth is
# google_news_rss_search.PROV_NAMES but we don't import that here to avoid
# pulling the RSS module into the upsert path.
_CANONICAL_PROVINCES = {
    "Alberta", "British Columbia", "Manitoba", "New Brunswick",
    "Newfoundland and Labrador", "Northwest Territories", "Nova Scotia",
    "Nunavut", "Ontario", "Prince Edward Island", "Quebec",
    "Saskatchewan", "Yukon", "National", "Canada",
}


def _project_has_url(project: dict) -> bool:
    """D-2 URL hard gate at the flat-upsert boundary.

    Returns True iff at least one URL string is present in `sources` or
    `evidence`. Counts as a URL: any non-empty string in sources, or any
    evidence entry whose `url` field is non-empty (and starts with 'http').

    The db.upsert_project gate already enforces this, but it emits silent
    rejection counts. We pre-check here so we can produce a per-reason
    rejection breakdown for the operator.
    """
    for src in (project.get("sources") or []):
        if isinstance(src, str) and src.strip():
            return True
        if isinstance(src, dict) and (src.get("url") or "").strip():
            return True
    for ev in (project.get("evidence") or []):
        if isinstance(ev, dict) and (ev.get("url") or "").strip():
            return True
        if isinstance(ev, str) and ev.strip():
            return True
    return False


def _get_project_rowid(conn, norm_key: str) -> int | None:
    """Get the rowid for a project by its norm_key."""
    row = conn.execute("SELECT rowid FROM projects WHERE norm_key = ?", (norm_key,)).fetchone()
    return row[0] if row else None


def _sync_evidence_and_org(conn, norm_key: str, project_dict: dict, existing: dict | None):
    """Dual-write evidence to evidence table, insert events on changes, resolve org."""
    project_id = _get_project_rowid(conn, norm_key)
    if not project_id:
        return

    # Dual-write evidence rows
    evidence = project_dict.get('evidence', [])
    if isinstance(evidence, str):
        import json
        try:
            evidence = json.loads(evidence)
        except Exception:
            evidence = []
    discovery_source = project_dict.get('discovery_source', '')
    for ev in evidence:
        url = ev.get('url', '')
        if url:
            insert_evidence(conn, project_id, url,
                            discovery_source=ev.get('source', discovery_source),
                            published_date=ev.get('date', ''))

    # Also add sources list as evidence
    for src_url in (project_dict.get('sources') or []):
        if isinstance(src_url, str) and src_url:
            insert_evidence(conn, project_id, src_url,
                            discovery_source=discovery_source)

    # Insert events on status/value changes
    if existing:
        old_status = existing.get('status', '')
        new_status = project_dict.get('status', old_status)
        if new_status and new_status != old_status:
            insert_project_event(conn, project_id, 'status_change',
                                 status_before=old_status,
                                 status_after=new_status,
                                 summary=f"Status changed from {old_status} to {new_status}",
                                 is_material=True)

        old_value = existing.get('value', '')
        new_value = project_dict.get('value', '')
        if new_value and new_value != old_value and new_value != '\u2014':
            insert_project_event(conn, project_id, 'cost_revision',
                                 cost_before=old_value,
                                 cost_after=new_value,
                                 summary=f"Value changed from {old_value} to {new_value}")

        if evidence:
            insert_project_event(conn, project_id, 'new_evidence',
                                 summary=f"{len(evidence)} evidence entries added")
    else:
        # New project — record announcement event
        insert_project_event(conn, project_id, 'announcement',
                             status_after=project_dict.get('status', 'Proposed'),
                             summary='First tracked')

    # Write official identifiers (Phase 5)
    official_ids = project_dict.get('official_ids', {})
    if isinstance(official_ids, str):
        import json as _json
        try:
            official_ids = _json.loads(official_ids)
        except Exception:
            official_ids = {}
    if isinstance(official_ids, dict):
        source_url = project_dict.get('source_url', '')
        for id_type, id_value in official_ids.items():
            if id_value:
                insert_project_identifier(conn, project_id, id_type,
                                          str(id_value), source_url)

    # Resolve organization
    proponent = project_dict.get('proponent', '')
    if proponent:
        org_id = resolve_organization(conn, proponent)
        if org_id:
            link_project_organization(conn, project_id, org_id, 'proponent')


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
                norm_key = upsert_project(conn, proj_dict)
                _sync_evidence_and_org(conn, norm_key, proj_dict, existing)
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

    Per audit D-2 + D-4, this boundary now:
      - Hard-gates rows without any URL (no_url bucket)
      - Normalizes status to canonical enum (D-4) before forwarding
      - Aggregates rejection reasons in a Counter for operator visibility
    """
    today = date.today().isoformat()
    new_count = 0
    updated_count = 0
    skipped = 0
    new_keys = []
    rejections_by_reason: Counter = Counter()

    for project in projects:
        proj_name = (project.get('name') or '').strip()
        prov_name = (project.get('province') or '').strip()

        # D-2 hard gates \u2014 checked BEFORE we pay normalization cost.
        if not proj_name:
            rejections_by_reason['no_name'] += 1
            skipped += 1
            continue
        if not prov_name:
            rejections_by_reason['no_province'] += 1
            skipped += 1
            continue
        if prov_name not in _CANONICAL_PROVINCES:
            # Caller forgot to normalize via PROV_NAMES. Don't silently relabel
            # it National \u2014 surface the rejection so the upstream scraper can
            # be fixed.
            rejections_by_reason['invalid_province'] += 1
            skipped += 1
            continue
        if not _project_has_url(project):
            rejections_by_reason['no_url'] += 1
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

        # D-4: canonicalize status at the boundary. Maps Proposed\u2192Announced,
        # Complete\u2192Completed, On Hold\u2192Paused, In Service\u2192Operational. db.py
        # may apply its own normalization too; that's fine \u2014 this is idempotent.
        raw_status = project.get('status') or 'Announced'
        status = normalize_status(raw_status)

        # Check if project already exists to count new vs updated
        key = normalize_key(proj_name, prov_name)
        existing = get_project(conn, key)
        _is_new = existing is None

        proj_dict = {
            'name':              proj_name,
            'description':       project.get('description') or '',
            'province':          prov_name,
            'sector':            project.get('sector') or 'Other',
            'naics_code':        project.get('naics_code') or '',
            'cma':               project.get('cma') or '',
            'tags':              project.get('tags') or [],
            'value':             project.get('value') or '\u2014',
            'status':            status,
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
            norm_key = upsert_project(conn, proj_dict)
            if norm_key is None:
                # db.py rejected the row \u2014 most likely province-normalize fail
                # or value-cap fail. We don't have the specific reason here;
                # bucket it under db_rejected.
                rejections_by_reason['db_rejected'] += 1
                skipped += 1
                continue
            _sync_evidence_and_org(conn, norm_key, proj_dict, existing)
            if _is_new:
                new_count += 1
                new_keys.append(norm_key)
                print(f"  [NEW] {prov_name}: {proj_name}")
            else:
                updated_count += 1
        except Exception as e:
            print(f"  [ERROR] Upsert failed for '{proj_name}': {e}")
            rejections_by_reason['exception'] += 1
            skipped += 1

    n_processed = len(projects)
    print(f"\nFlat project sync complete:")
    print(f"  [UPSERT] {n_processed} processed, {new_count} new, "
          f"{updated_count} updated, {skipped} skipped")
    if rejections_by_reason:
        print(f"  Rejection reasons: {dict(rejections_by_reason)}")
    else:
        print(f"  Rejection reasons: {{}}")

    return {
        "new": new_count, "updated": updated_count, "skipped": skipped,
        "new_keys": new_keys,
        "rejections_by_reason": dict(rejections_by_reason),
    }
