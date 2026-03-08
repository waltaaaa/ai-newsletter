"""
project_sync.py — Cumulative Project Tracker for CAN-MACRO

Manages a persistent /projects Firestore collection that grows over time
instead of being overwritten each pipeline run.

STEP_2C: Added project_type, is_brownfield, confidence, discovery_sources,
and evidence fields to new project documents.

Usage in update_dashboard.py:
    from project_sync import upsert_projects

    # After Gemini generates the payload...
    if payload.get('provinces'):
        upsert_projects(db, payload['provinces'])
"""

import re
from datetime import date
from difflib import SequenceMatcher
from project_schema import normalize_project_type, is_brownfield


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

    # STEP_2C: Update taxonomy fields
    if new_data.get('project_type'):
        ptype = normalize_project_type(new_data['project_type'])
        updates['project_type'] = ptype
        updates['is_brownfield'] = is_brownfield(ptype)
    if new_data.get('confidence'):
        # Only update if new confidence is higher
        old_conf = _to_numeric_confidence(doc_data.get('confidence', 0))
        new_conf = _to_numeric_confidence(new_data['confidence'])
        if new_conf > old_conf:
            updates['confidence'] = new_conf
    # Merge evidence (use normalized URLs to avoid near-duplicates)
    if new_data.get('evidence'):
        from url_utils import normalize_url
        existing_ev = list(doc_data.get('evidence', []))
        existing_urls = set()
        for e in existing_ev:
            norm = normalize_url(e.get('url', ''))
            if norm:
                existing_urls.add(norm)
        for ev in new_data['evidence']:
            norm = normalize_url(ev.get('url', ''))
            if norm and norm not in existing_urls:
                existing_ev.append(ev)
                existing_urls.add(norm)
        updates['evidence'] = existing_ev
        updates['evidence_count'] = len(existing_ev)
        updates['has_government_source'] = any(
            e.get('authority') == 'government' for e in existing_ev
        )
        updates['has_known_source'] = any(
            e.get('is_known_source') for e in existing_ev
        )
    # Merge discovery_sources
    if new_data.get('discovery_sources'):
        existing_ds = list(doc_data.get('discovery_sources', []))
        for ds in new_data['discovery_sources']:
            if ds not in existing_ds:
                existing_ds.append(ds)
        updates['discovery_sources'] = existing_ds

    # Detect tracked changes for history entry
    change_notes = []

    new_val = new_data.get('value')
    old_val = doc_data.get('value', '—')
    if new_val and new_val != old_val and new_val != '—':
        updates['value'] = new_val
        change_notes.append(f"Cost: {old_val} -> {new_val}")

    new_completion = new_data.get('completionDate')
    old_completion = doc_data.get('completionDate')
    if new_completion and new_completion != old_completion:
        updates['completionDate'] = new_completion
        change_notes.append(f"Timeline: {old_completion or 'TBD'} -> {new_completion}")

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
            change_notes.insert(0, f"Status: {doc_data.get('status', '?')} -> {new_status}")
        if change_notes:
            entry['note'] = ' . '.join(change_notes)
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
            print(f"  [UPDATED] {doc_data['province']}: {doc_data['name']} -- {' . '.join(change_notes)}")

    # ── Anomaly detection ──
    anomalies = list(doc_data.get('anomalies', []))
    _STATUS_ORDER = {
        'rumoured': 0, 'proposed': 1, 'announced': 1, 'approved': 2,
        'under review': 1.5, 'under construction': 3, 'completed': 4,
        'delayed': 2.5, 'on hold': 2.5, 'suspended': 2.5, 'cancelled': -1,
    }

    # Value change >30%
    if new_val and old_val and old_val != '—' and new_val != old_val:
        old_m = _parse_value_millions(old_val)
        new_m = _parse_value_millions(new_val)
        if old_m > 0 and new_m > 0:
            pct = abs(new_m - old_m) / old_m
            if pct > 0.30:
                atype = 'value_spike' if new_m > old_m else 'value_drop'
                anomalies.append({
                    'type': atype,
                    'detail': f"Value changed from {old_val} to {new_val} ({pct:.0%})",
                    'date': today,
                })

    # Status regression
    if status_changed:
        old_order = _STATUS_ORDER.get((doc_data.get('status') or '').lower(), 0)
        new_order = _STATUS_ORDER.get((new_status or '').lower(), 0)
        if new_order >= 0 and new_order < old_order:
            anomalies.append({
                'type': 'status_regression',
                'detail': f"Status went from '{doc_data.get('status')}' to '{new_status}'",
                'date': today,
            })

    # Proponent change
    old_prop = (doc_data.get('proponent') or '').strip().lower()
    new_prop = (new_data.get('proponent') or '').strip().lower()
    if old_prop and new_prop and old_prop != new_prop:
        if old_prop not in new_prop and new_prop not in old_prop:
            anomalies.append({
                'type': 'proponent_change',
                'detail': f"Proponent: {doc_data.get('proponent')} -> {new_data.get('proponent')}",
                'date': today,
            })

    if anomalies != list(doc_data.get('anomalies', [])):
        updates['anomalies'] = anomalies
        updates['has_anomalies'] = len(anomalies) > 0

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

        ptype = normalize_project_type(project.get('project_type', ''))
        new_doc = {
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
