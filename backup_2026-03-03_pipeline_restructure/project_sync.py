"""
project_sync.py — Cumulative Project Tracker for CAN-MACRO

Manages a persistent /projects Firestore collection that grows over time
instead of being overwritten each pipeline run.

Usage in update_dashboard.py:
    from project_sync import upsert_projects

    # After Gemini generates the payload...
    if payload.get('provinces'):
        upsert_projects(db, payload['provinces'])
"""

import re
from datetime import date
from difflib import SequenceMatcher


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


def _update_project(doc_ref, doc_data: dict, new_data: dict, today: str):
    """Update an existing project document with new data from Gemini."""
    updates = {'lastSeen': today}

    # Update description if provided
    new_desc = new_data.get('description')
    if new_desc:
        updates['description'] = new_desc

    # Update scalar fields
    if new_data.get('sector'):
        updates['sector'] = new_data['sector']
    if new_data.get('cma'):
        updates['cma'] = new_data['cma']
    if new_data.get('tags'):
        updates['tags'] = new_data['tags']
    if new_data.get('sources'):
        updates['sources'] = new_data['sources']
    if new_data.get('source'):
        updates['source'] = new_data['source']

    # Detect tracked changes for history entry
    change_notes = []

    new_val = new_data.get('value')
    old_val = doc_data.get('value', '—')
    if new_val and new_val != old_val and new_val != '—':
        updates['value'] = new_val
        change_notes.append(f"Cost: {old_val} → {new_val}")

    new_completion = new_data.get('completionDate')
    old_completion = doc_data.get('completionDate')
    if new_completion and new_completion != old_completion:
        updates['completionDate'] = new_completion
        change_notes.append(f"Timeline: {old_completion or 'TBD'} → {new_completion}")

    new_status = new_data.get('status')
    status_changed = new_status and new_status != doc_data.get('status')
    if status_changed:
        updates['status'] = new_status
        updates['lastUpdated'] = today

    # Append a history entry if status or any tracked field changed
    if status_changed or change_notes:
        history = list(doc_data.get('statusHistory', []))
        entry = {'date': today}
        if status_changed:
            entry['status'] = new_status
            change_notes.insert(0, f"Status: {doc_data.get('status', '?')} → {new_status}")
        if change_notes:
            entry['note'] = ' · '.join(change_notes)
        # Carry through sources for this update
        if new_data.get('sources'):
            entry['sources'] = new_data['sources']
        elif new_data.get('source'):
            entry['source'] = new_data['source']
        history.append(entry)
        updates['statusHistory'] = history
        if not status_changed:
            updates['lastUpdated'] = today

        if status_changed:
            print(f"  [STATUS CHANGE] {doc_data['province']}: {doc_data['name']} -> {new_status}")
        if change_notes:
            print(f"  [UPDATED] {doc_data['province']}: {doc_data['name']} — {' · '.join(change_notes)}")

    doc_ref.update(updates)


def upsert_projects(db, provinces_data: list[dict]):
    """
    Merge Gemini-generated projects into the persistent /projects collection.

    Args:
        db: Firestore client instance (google.cloud.firestore.Client)
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
    projects_ref = db.collection('projects')

    # ── 1. Load all existing projects into memory ────────────────
    existing_docs = {}               # normalized_key -> (doc_ref, doc_data)
    existing_names_by_province = {}  # province -> [project_names]

    for doc_snap in projects_ref.stream():
        data = doc_snap.to_dict()
        key = normalize_key(data['name'], data['province'])
        existing_docs[key] = (doc_snap.reference, data)

        prov = data['province']
        if prov not in existing_names_by_province:
            existing_names_by_province[prov] = []
        existing_names_by_province[prov].append(data['name'])

    new_count = 0
    updated_count = 0

    # ── 2. Process each province's projects ──────────────────────
    for province in provinces_data:
        prov_name = province.get('name', '')
        if not prov_name:
            continue

        for project in province.get('projects', []):
            proj_name = project.get('name', '')
            if not proj_name:
                continue

            # Try exact normalized match first
            exact_key = normalize_key(proj_name, prov_name)

            if exact_key in existing_docs:
                doc_ref, doc_data = existing_docs[exact_key]
                _update_project(doc_ref, doc_data, project, today)
                updated_count += 1
                continue

            # Try fuzzy match within same province
            candidates = existing_names_by_province.get(prov_name, [])
            fuzzy_name = fuzzy_match(proj_name, candidates)

            if fuzzy_name:
                fuzzy_key = normalize_key(fuzzy_name, prov_name)
                if fuzzy_key in existing_docs:
                    doc_ref, doc_data = existing_docs[fuzzy_key]
                    _update_project(doc_ref, doc_data, project, today)
                    updated_count += 1
                    print(f"  [FUZZY] Matched '{proj_name}' -> '{fuzzy_name}'")
                    continue

            # No match found — create new project document
            new_doc = {
                'name': proj_name,
                'description': project.get('description', ''),
                'province': prov_name,
                'sector': project.get('sector', 'General'),
                'value': project.get('value', '—'),
                'status': project.get('status', 'Announced'),
                'completionDate': project.get('completionDate', ''),
                'cma': project.get('cma', ''),
                'tags': project.get('tags', []),
                'sources': project.get('sources', []),
                'source': project.get('source', ''),
                'firstTracked': today,
                'lastUpdated': today,
                'lastSeen': today,
                'statusHistory': [
                    {'status': project.get('status', 'Announced'), 'date': today, 'note': 'First tracked'}
                ],
            }
            projects_ref.add(new_doc)
            new_count += 1

            # Update local cache so subsequent projects in same run can match
            key = normalize_key(proj_name, prov_name)
            # We don't have a doc ref for the newly created doc, but that's fine
            # since we won't need to update it again in the same run
            if prov_name not in existing_names_by_province:
                existing_names_by_province[prov_name] = []
            existing_names_by_province[prov_name].append(proj_name)

            print(f"  [NEW] {prov_name}: {proj_name}")

    total_gemini = sum(len(p.get('projects', [])) for p in provinces_data)
    print(f"\nProject sync complete:")
    print(f"  Existing in DB: {len(existing_docs)}")
    print(f"  From Gemini:    {total_gemini}")
    print(f"  New:            {new_count}")
    print(f"  Updated:        {updated_count}")


def upsert_flat_projects(db, projects: list[dict]):
    """
    Merge a flat list of project dicts into the persistent /projects collection.
    Each dict must have a 'province' field alongside the standard project fields.
    Used by the weekly project research pipeline in update_dashboard.py.
    """
    today = date.today().isoformat()
    projects_ref = db.collection('projects')

    # ── Load all existing projects into memory ────────────────────
    existing_docs = {}
    existing_names_by_province = {}

    for doc_snap in projects_ref.stream():
        data = doc_snap.to_dict()
        key = normalize_key(data['name'], data['province'])
        existing_docs[key] = (doc_snap.reference, data)
        existing_names_by_province.setdefault(data['province'], []).append(data['name'])

    new_count = 0
    updated_count = 0
    skipped = 0

    for project in projects:
        proj_name = (project.get('name') or '').strip()
        prov_name = (project.get('province') or '').strip()
        if not proj_name or not prov_name:
            skipped += 1
            continue

        exact_key = normalize_key(proj_name, prov_name)

        if exact_key in existing_docs:
            doc_ref, doc_data = existing_docs[exact_key]
            _update_project(doc_ref, doc_data, project, today)
            updated_count += 1
            continue

        candidates = existing_names_by_province.get(prov_name, [])
        fuzzy_name = fuzzy_match(proj_name, candidates)

        if fuzzy_name:
            fuzzy_key = normalize_key(fuzzy_name, prov_name)
            if fuzzy_key in existing_docs:
                doc_ref, doc_data = existing_docs[fuzzy_key]
                _update_project(doc_ref, doc_data, project, today)
                updated_count += 1
                print(f"  [FUZZY] Matched '{proj_name}' -> '{fuzzy_name}'")
                continue

        # Normalize announced date
        announced = (project.get('announced') or today).strip()
        if len(announced) == 7:
            announced += '-01'
        elif len(announced) == 4:
            announced += '-01-01'
        elif len(announced) < 4:
            announced = today

        new_doc = {
            'name':           proj_name,
            'description':    project.get('description') or '',
            'province':       prov_name,
            'sector':         project.get('sector') or 'Other',
            'naics_code':     project.get('naics_code') or '',
            'cma':            project.get('cma') or '',
            'tags':           project.get('tags') or [],
            'value':          project.get('value') or '\u2014',
            'status':         project.get('status') or 'Announced',
            'completionDate': project.get('completionDate') or '',
            'sources':        project.get('sources') or [],
            'source':         '',
            'firstTracked':   announced,
            'lastUpdated':    today,
            'lastSeen':       today,
            'statusHistory':  [
                {'status': project.get('status') or 'Announced', 'date': announced, 'note': 'First tracked'}
            ],
        }
        _, new_ref = projects_ref.add(new_doc)
        new_count += 1

        existing_names_by_province.setdefault(prov_name, []).append(proj_name)
        existing_docs[exact_key] = (new_ref, new_doc)
        print(f"  [NEW] {prov_name}: {proj_name}")

    print(f"\nFlat project sync complete:")
    print(f"  Existing in DB: {len(existing_docs)}")
    print(f"  Processed:      {len(projects)}")
    print(f"  New:            {new_count}")
    print(f"  Updated:        {updated_count}")
    print(f"  Skipped:        {skipped}")
