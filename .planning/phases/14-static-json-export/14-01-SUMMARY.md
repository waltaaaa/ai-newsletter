---
phase: 14-static-json-export
plan: "01"
subsystem: export
tags: [sqlite, json-export, static-site, tdd]
dependency_graph:
  requires: [db.py, pipeline_config.py, event_calendar.py]
  provides: [export_dashboard.py, docs/data/]
  affects: [phase-15-frontend-rewrite]
tech_stack:
  added: []
  patterns: [TDD red-green, sqlite-to-json, compact-json-for-large-files]
key_files:
  created:
    - export_dashboard.py
    - tests/test_export_dashboard.py
    - docs/data/manifest.json
    - docs/data/briefing_latest.json
    - docs/data/briefing_archive.json
    - docs/data/indicators.json
    - docs/data/trends.json
    - docs/data/events.json
    - docs/data/microscope.json
    - docs/data/timeseries.json
    - docs/data/projects_ontario.json (+ 12 other province files)
  modified:
    - export_dashboard.py (init_db fix applied in Task 2)
decisions:
  - "export_all uses init_db() not get_db() to ensure schema exists on empty databases"
  - "Province files use compact JSON (no indent); briefing/manifest use indent=2 for readability"
  - "Projects with unparseable or missing values included with value_confirmed=false (never silently excluded)"
  - "export_timeseries bundles all 31 known series into single timeseries.json keyed by series_name"
  - "Briefing archive exports metadata-only (week_of, headline, word_count, generated_at) to keep file small"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_created: 23
  completed_date: "2026-03-08"
---

# Phase 14 Plan 01: Static JSON Export Summary

**One-liner:** SQLite-to-static-JSON bridge via export_dashboard.py exporting 21 files (13 province + 8 data files) with GDP threshold filtering and value_confirmed field for frontend rendering without database connections.

## What Was Built

`export_dashboard.py` is a standalone script that reads all dashboard data from SQLite via `db.py` and writes static JSON files to `docs/data/`. This is the bridge between the SQLite backend (Phase 13) and the static frontend (Phase 15).

### Functions Implemented

| Function | Output | Description |
|---|---|---|
| `_parse_value(val_str)` | `float | None` | Parses "$1.2B", "$600M", "2.5 billion" to float; None for not-disclosed/unparseable |
| `_project_for_export(proj_dict)` | `dict` | Converts db.py row to export shape; parses JSON string fields; adds value_confirmed |
| `export_province_projects(conn, province, threshold, dir)` | `projects_{slug}.json` | GDP threshold filter: include if value >= threshold OR value is None |
| `export_briefings(conn, dir)` | `briefing_latest.json`, `briefing_archive.json` | Latest full briefing + archive metadata-only |
| `export_indicators(conn, dir)` | `indicators.json` | Latest indicators + statcan_latest from dashboard_state |
| `export_trends(conn, dir)` | `trends.json` | Trend snapshots (last 12 weeks) |
| `export_events(conn, dir)` | `events.json` | Upcoming events (30-day window) via event_calendar.py |
| `export_microscope(conn, dir)` | `microscope.json` | Microscope history from dashboard_state |
| `export_timeseries(conn, dir)` | `timeseries.json` | All 31 known series bundled as single object |
| `export_all(conn, output_dir)` | All files + `manifest.json` | Main orchestrator; creates output_dir; returns file_count |

### Output Files

21 JSON files written to `docs/data/`:
- 13 province files: `projects_{slug}.json` (compact JSON, GDP-filtered)
- `briefing_latest.json`, `briefing_archive.json`
- `indicators.json`, `trends.json`, `events.json`, `microscope.json`, `timeseries.json`
- `manifest.json` (exported_at timestamp, file_list)

## Test Coverage

15 unit tests in `tests/test_export_dashboard.py` using in-memory SQLite:

- `_parse_value`: 7 tests covering billions, millions, written forms, None/empty/unparseable
- `export_province_projects`: 4 tests — above-threshold included, below excluded, not-disclosed unconfirmed, TBD unconfirmed, JSON arrays parsed
- `export_all`: 3 tests — all expected files created, all valid JSON, manifest has required fields

All 15 pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] export_all used get_db() which does not create schema on empty databases**
- **Found during:** Task 2 (real database validation)
- **Issue:** `get_db()` opens a connection but does not run `_SCHEMA_SQL`. On an empty `dashboard.db`, the first `get_projects()` call raised `sqlite3.OperationalError: no such table: projects`.
- **Fix:** Changed `export_all` and the `__main__` CLI block to use `init_db()` instead of `get_db()`. `init_db()` calls `executescript(_SCHEMA_SQL)` which is idempotent (CREATE TABLE IF NOT EXISTS).
- **Files modified:** `export_dashboard.py`
- **Commit:** b4b77f8

## Validation Results

Real database export (empty dashboard.db, schema freshly initialized):
- 21 files written to `docs/data/`
- All 21 files confirmed valid JSON
- `events.json`: 7 upcoming BoC/StatsCan events for March 2026 (live calendar data)
- Province project files: empty arrays (pipeline not yet run against SQLite — expected at this migration stage)
- `manifest.json`: `exported_at` timestamp + complete `file_list`

## Self-Check: PASSED

All created files verified:

```
export_dashboard.py ........... FOUND
tests/test_export_dashboard.py  FOUND
docs/data/manifest.json ....... FOUND
docs/data/events.json ......... FOUND
docs/data/briefing_latest.json  FOUND
docs/data/timeseries.json ..... FOUND
docs/data/projects_ontario.json FOUND
```

Commits verified:
```
8ffaac2  test(14-01): add failing tests for export_dashboard.py
3357106  feat(14-01): implement export_dashboard.py with all export functions
b4b77f8  feat(14-01): validate export against real database, auto-fix init_db usage
```
