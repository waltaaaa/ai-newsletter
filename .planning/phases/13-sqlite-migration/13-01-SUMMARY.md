---
phase: 13-sqlite-migration
plan: "01"
subsystem: database
tags: [sqlite, db, foundation, fts5, upsert, crud]
dependency_graph:
  requires: []
  provides: [db.py, SQLite interface, all CRUD functions, FTS5 search]
  affects: [13-02, 13-03, 13-04, 13-05, all pipeline modules]
tech_stack:
  added: [sqlite3 (stdlib), FTS5 virtual tables]
  patterns: [singleton connection, Row factory, executescript schema, JSON columns, STATUS_ORDER non-regression, evidence merge via normalize_url]
key_files:
  created:
    - db.py
    - test_db.py
  modified: []
decisions:
  - "Used executescript() for schema creation to support multi-statement trigger blocks — plain execute() with split-by-semicolon breaks FTS5 trigger bodies"
  - "FTS5 table uses content=projects with INSERT/UPDATE/DELETE triggers for automatic sync"
  - "save_indicator() auto-remaps Firestore field names (indicator->indicator_name, date->period) so callers migrated in Plans 13-04/13-05 require no changes"
  - "Terminal states (Cancelled, On Hold, Suspended, Paused) always override forward status regardless of STATUS_ORDER to handle project cancellations"
  - "Tavily credits stored in dashboard_state table with key 'tavily_credits' — no separate table needed; auto-reset on month change"
metrics:
  duration_seconds: 294
  completed_date: "2026-03-08"
  tasks_completed: 2
  files_created: 2
  lines_written: 1688
  tests_passing: 53
---

# Phase 13 Plan 01: SQLite Interface Module (db.py) Summary

**One-liner:** SQLite interface module with 14-table schema, FTS5 full-text search, and business-rule-aware upsert (evidence merge, status non-regression, confidence floor) replacing all Firestore collection access.

## What Was Built

`db.py` is the single-module SQLite interface for the entire CAN-MACRO pipeline. No other module needs to import `sqlite3` directly. All 14 Firestore collections are mapped to SQLite tables.

### Tables Created (14)

| Table | Replaces Firestore Collection | Purpose |
|---|---|---|
| `projects` | `projects` | Main project database with all fields |
| `projects_fts` | — | FTS5 virtual table for full-text search |
| `indicator_history` | `indicator_history` | Economic indicator time series |
| `trend_snapshots` | `trend_snapshots` | Weekly trend analysis snapshots |
| `weekly_briefings` | `weekly_briefings` | Generated briefings with sections JSON |
| `dashboard_state` | `dashboard_state` | Key-value store (latest_briefing, tavily_credits, follow_up_queries, microscope_*) |
| `pipeline_runs` | `pipeline_runs` | Structured run logs |
| `missed_projects` | `missed_projects` | User-submitted missing projects |
| `pipeline_improvements` | `pipeline_improvements` | Adaptive learning improvements |
| `statcan_indicators` | `statcan_indicators` | StatCan latest indicator values |
| `timeseries` | `timeseries` | Commodity/market time series |
| `newsletters` | `newsletters` | Legacy newsletter collection |
| `pipeline_state` | `pipeline_state` | Follow-up queries and state tracking |
| `projects_archive` | — | Soft-deleted / superseded projects |

### Exported Functions (22)

```python
# Connection
get_db(path=None) -> Connection
init_db(path=None) -> Connection

# Projects
upsert_project(conn, project_dict) -> str
get_projects(conn, province=None, sector=None, limit=5000) -> list
get_project(conn, norm_key) -> dict | None
get_all_projects(conn) -> list
search_projects(conn, query, limit=50) -> list

# Indicators
save_indicator(conn, indicator_dict)
get_indicators(conn, category=None, province=None) -> list
get_latest_indicators(conn) -> list

# Briefings
save_briefing(conn, briefing_dict) -> int
get_latest_briefing(conn) -> dict | None
get_briefing_archive(conn, limit=52) -> list

# Dashboard State
save_dashboard_state(conn, key, value)
get_dashboard_state(conn, key) -> Any

# Pipeline Runs
save_pipeline_run(conn, run_dict) -> int
update_pipeline_run(conn, run_id, updates)
get_pipeline_runs(conn, limit=20) -> list

# Tavily Credits
save_tavily_credits(conn, month, used)
get_tavily_credits(conn) -> dict
increment_tavily_credits(conn, amount=1)

# Follow-up Queries
save_follow_up_queries(conn, queries)
get_follow_up_queries(conn) -> list

# Other Collections
save_missed_project(conn, project_dict) -> int
save_pipeline_improvement(conn, improvement_dict) -> int
save_trend_snapshot(conn, snapshot_dict) -> int
get_trend_snapshots(conn, limit=12) -> list
```

### Business Rules Enforced in upsert_project()

1. **Evidence merge** — existing URLs kept, new URLs appended, no duplicates via `normalize_url()`
2. **Status non-regression** — status never goes backward (Proposed never overwrites Approved); exception: Cancelled/On Hold/Suspended/Paused always apply
3. **Confidence floor** — `resolved_conf = max(existing_conf, new_conf)` — confidence never decreases

### FTS5 Search

`projects_fts` is a content-synchronized virtual table on `(name, description, province, sector, proponent)` with three SQL triggers (AFTER INSERT, AFTER DELETE, AFTER UPDATE) to keep it in sync. `search_projects()` uses `MATCH` query ordered by FTS5 rank.

### Indicator Field Remapping

`save_indicator()` auto-remaps Firestore-style field names:
- `indicator` → `indicator_name`
- `date` → `period`
- Also accepts: `unit`, `frequency`, `description`, `backfilled`

This allows callers in Plans 13-04 and 13-05 to pass Firestore-shaped dicts without modification.

## Test Results

53 tests passing in `test_db.py` covering:
- All 14 table existence checks
- All required column sets
- FTS5 virtual table usability
- `init_db()` idempotency
- `upsert_project()` — insert, merge, status non-regression, confidence floor, statusHistory append
- `get_projects()` — province and sector filters
- `search_projects()` — FTS5 match and no-match cases
- `save_indicator()` — both SQLite-shaped and Firestore-shaped dicts, extra fields
- `save_briefing()` / `get_latest_briefing()` — round-trip, most-recent ordering
- `save_dashboard_state()` / `get_dashboard_state()` — round-trip, missing key, overwrite
- `save_pipeline_run()` / `get_pipeline_runs()` — round-trip
- Tavily credits — save, auto-reset on new month, increment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Schema split-by-semicolon breaks FTS5 trigger bodies**
- **Found during:** Task 1 GREEN phase — first test run
- **Issue:** Splitting `_SCHEMA_SQL` by ";" produced incomplete SQL fragments because trigger bodies contain semicolons (e.g., `BEGIN ... INSERT ... ; END`). `conn.execute()` raised `sqlite3.OperationalError: incomplete input`.
- **Fix:** Replaced the loop over `_SCHEMA_SQL.split(";")` with a single `conn.executescript(_SCHEMA_SQL)` call, which correctly handles multi-statement blocks.
- **Files modified:** `db.py` (init_db function)
- **Commit:** f770136 (same GREEN commit)

## Self-Check: PASSED
