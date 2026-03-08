---
phase: 13-sqlite-migration
plan: 05
subsystem: database-migration
tags: [sqlite, firestore-removal, backfill-scripts, seed-scripts, audit-scripts, db-07, db-08]
dependency_graph:
  requires: [13-04]
  provides: [DB-07, DB-08, firestore-free-codebase]
  affects: [backfill-scripts, seed-scripts, audit-scripts, requirements.txt]
tech_stack:
  added: []
  patterns: [init_db-conn-pattern, upsert_project, get_all_projects, save_indicator, save_dashboard_state]
key_files:
  created: []
  modified:
    - backfill_indicator_history.py
    - backfill_frontend_data.py
    - backfill_descriptions.py
    - backfill_project_values.py
    - backfill_project_fields.py
    - backfill_global_indicators.py
    - backfill_commodity_timeseries.py
    - backfill_timeseries.py
    - seed_projects.py
    - seed_projects_v2.py
    - seed_newsletter.py
    - known_project_sweep.py
    - historical_backfill.py
    - dedup_audit.py
    - coverage_audit.py
    - requirements.txt
decisions:
  - "All 15 backfill/seed/audit scripts migrated to db.py using same conn = init_db() / upsert_project() pattern as pipeline modules"
  - "seed_projects_v2.py wipe_projects() replaced with direct SQLite DELETE — no batch cursor needed"
  - "backfill_timeseries.py reads dashboard_state keys via raw cursor LIKE 'newsletter_%' — no new db.py function needed"
  - "firebase-admin removed from requirements.txt (DB-08); SQLite is stdlib, no new dependency"
  - "dedup_audit.py secondary doc deletion uses raw conn.execute DELETE WHERE norm_key when keys differ — safe because upsert handles same-key merges"
metrics:
  duration_minutes: 11
  completed_date: "2026-03-07"
  tasks_completed: 3
  files_modified: 16
---

# Phase 13 Plan 05: Backfill/Seed/Audit Scripts SQLite Migration Summary

Completed DB-07 (all active Python files use db.py) and DB-08 (firebase-admin removed from requirements.txt). Migrated all 15 remaining utility scripts from Firestore to SQLite, making the entire codebase Firestore-free.

## What Was Done

### Task 1a: 8 Backfill Scripts Migrated

All 8 backfill scripts had their firebase_admin init block removed and replaced with `conn = init_db()`:

- **backfill_indicator_history.py**: Replaced `db.batch().set()` loops with `save_indicator(conn, {...})` calls for BoC, StatCan, Yahoo Finance, OEA, and ISQ data sources
- **backfill_frontend_data.py**: Replaced `db.collection("dashboard_state").document().get/set()` with `get_dashboard_state()`/`save_dashboard_state()`
- **backfill_descriptions.py**: Replaced Firestore stream+update pattern with `get_all_projects(conn)` + `upsert_project(conn, updated)`
- **backfill_project_values.py**: Replaced `db.collection('projects').stream()` + `.update()` with `get_all_projects()` + `upsert_project()`
- **backfill_project_fields.py**: Replaced stream+batch.update with `get_all_projects()` + `upsert_project()` per document
- **backfill_global_indicators.py**: Replaced Firestore newsletter/latest read/write with `get_dashboard_state()`/`save_dashboard_state()`
- **backfill_commodity_timeseries.py**: Replaced `ts_ref.document().set()` with `save_dashboard_state(conn, f"ts_{doc_id}", {...})`
- **backfill_timeseries.py**: Replaced Firestore stream with raw `conn.execute("SELECT key, value FROM dashboard_state WHERE key LIKE 'newsletter_%'")` cursor; replaced ArrayUnion with read-append-write

### Task 1b: 7 Seed/Audit/Sweep Scripts Migrated

- **seed_projects.py**: Replaced `projects_ref.add(new_doc)` with `upsert_project(conn, new_doc)`; replaced `projects_ref.stream()` with `get_all_projects(conn)`
- **seed_projects_v2.py**: Five separate Firestore patterns replaced: backup (stream→get_all_projects), wipe (batch delete→DELETE SQL), write_to_firestore (batch.set→upsert_project), stale flagging (snap.reference.update→upsert_project), sentiment save (collection.set→save_dashboard_state), audit_citations (stream→get_all_projects, newsletter get→get_dashboard_state)
- **seed_newsletter.py**: Replaced `db.collection().document().set()` with `save_dashboard_state(conn, key, data)`
- **dedup_audit.py**: Replaced stream with `get_all_projects(conn)`; replaced ref.update/delete with `upsert_project()`/raw `conn.execute("DELETE...")`
- **coverage_audit.py**: Removed inline Firestore init from `__main__` block; replaced stream with `init_db()/get_all_projects()`
- **known_project_sweep.py**: Removed Firestore init from `__main__` block; replaced with `init_db()`
- **historical_backfill.py**: Removed Firestore init from `__main__` block; replaced with `init_db()`

### Task 2: Firebase-Admin Removed from requirements.txt

- Removed `firebase-admin` from `requirements.txt`
- Full codebase sweep verified: zero `firebase_admin` or `google.cloud.firestore` imports in any active `.py` file (only `migrate_firestore_to_sqlite.py` is the expected exception)
- SQLite is Python stdlib — no new dependency introduced

## Verification Results

```
All 8 backfill scripts Firestore-free
All 7 seed/audit/sweep scripts Firestore-free
requirements.txt clean
Codebase Firestore-free
SQLite works
```

## DB Requirements Satisfied

- **DB-07**: All active `.py` files use `db.py` — no file imports `firebase_admin` or `google.cloud.firestore`
- **DB-08**: `firebase-admin` and `google-cloud-firestore` removed from `requirements.txt`

## Commits

| Hash | Message |
|------|---------|
| b4bd752 | feat(13-sqlite-migration-05): rewrite 8 backfill scripts to use db.py |
| 78f1192 | feat(13-sqlite-migration-05): rewrite 7 seed/audit/sweep scripts to use db.py |
| e8b62ce | feat(13-sqlite-migration-05): remove firebase-admin from requirements.txt (DB-08) |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- All 17 expected files exist (15 migrated scripts + requirements.txt + SUMMARY.md)
- All 3 commits verified: b4bd752, 78f1192, e8b62ce
- Zero firebase_admin/google.cloud.firestore references in any active .py file
- requirements.txt contains no firebase-admin entry
- `python -c "from db import init_db; conn = init_db(':memory:'); print('SQLite works')"` succeeds
