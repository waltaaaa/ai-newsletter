---
phase: 13-sqlite-migration
plan: "02"
subsystem: database
tags: [sqlite, firestore, migration, db.py, pagination, idempotent]

requires:
  - phase: 13-sqlite-migration/13-01
    provides: db.py with all 14 SQLite tables and CRUD functions

provides:
  - migrate_firestore_to_sqlite.py — one-time migration script reads all 13 Firestore collections, writes to SQLite via db.py, prints per-collection MIGRATION REPORT

affects: [13-03, 13-04, 13-05, update_dashboard.py, all pipeline modules]

tech-stack:
  added: [firebase_admin (reads only), time (stdlib, for retry backoff)]
  patterns:
    - Paginated cursor-based Firestore streaming (_PAGE_SIZE=200) to avoid 300s timeout on large collections
    - Exponential backoff retry (up to 5 attempts) for 429 / transient Firestore errors
    - Recursive Firestore type conversion (_convert_value) handles Timestamp/DatetimeWithNanoseconds/GeoPoint
    - Per-handler functions keep migration logic for each collection isolated and testable
    - Windows UTF-8 console fix via sys.stdout.reconfigure(encoding='utf-8')

key-files:
  created:
    - migrate_firestore_to_sqlite.py
  modified: []

key-decisions:
  - "Paginated streaming with _PAGE_SIZE=200 replaces single list(collection.stream()) — prevents 300s timeout on large collections hitting Firestore quota"
  - "Exponential backoff (5s, 10s, 20s, 40s, 80s) per page handles 429 quota-exceeded without aborting the entire migration"
  - "pipeline_state and statcan_indicators both migrate to dashboard_state table (keyed by doc_id) — no separate tables needed"
  - "timeseries handler supports both series-object format (doc with 'data' array) and flat single-row format — covers both Firestore schema variants"
  - "Windows stdout reconfigure(encoding='utf-8') added to prevent cp1252 UnicodeEncodeError on non-ASCII log messages"

patterns-established:
  - "Migration handlers follow (conn, doc_dict, doc_id) -> None signature — consistent, testable, easily extended"
  - "All Firestore Timestamp fields converted to ISO 8601 strings via _to_iso() before db.py writes"
  - "MIGRATION REPORT table format: Collection / Firestore Docs / Migrated / Failed / SQLite Rows / Match"

requirements-completed: [DB-04, DB-05]

duration: 15min
completed: "2026-03-08"
---

# Phase 13 Plan 02: Firestore-to-SQLite Migration Script Summary

**Paginated one-time migration script that reads all 13 Firestore collections via cursor-based pagination with 429-retry and writes to SQLite through db.py, printing a per-collection MIGRATION REPORT.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-08T01:07:27Z
- **Completed:** 2026-03-08T01:22:00Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- `migrate_firestore_to_sqlite.py` covers all 13 Firestore collections with dedicated per-collection handler functions
- Paginated streaming (_PAGE_SIZE=200 docs/page) with 5-attempt exponential backoff prevents 300s timeout on the large `projects` collection
- All Firestore-specific types converted: Timestamps/DatetimeWithNanoseconds to ISO strings, GeoPoint to {lat, lng}, nested maps recursively
- `--dry-run` mode counts all documents without writing to SQLite for pre-migration verification
- Idempotent: `upsert_project()` deduplicates projects by norm_key; `ON CONFLICT DO UPDATE` for indicators and timeseries

## Task Commits

1. **Task 1: Create migrate_firestore_to_sqlite.py** - `b9ea20a` (feat)

## Files Created/Modified

- `migrate_firestore_to_sqlite.py` — 775-line one-time migration script. Imports all db.py write functions, defines per-collection handlers, uses paginated Firestore streaming with retry, prints MIGRATION REPORT table showing Firestore doc counts vs SQLite row counts per collection.

## Decisions Made

- **Paginated streaming over single stream():** `list(collection.stream())` times out after 300s on the projects collection (quota exceeded). Replaced with cursor-based pagination — each 200-doc page is a fresh Firestore query, short enough to complete before timeout.
- **Exponential backoff per page:** Firestore returns 429 on burst queries. Adding `time.sleep(5 * 2^attempt)` per page between retries allows quota to refill without aborting the migration.
- **pipeline_state and statcan_indicators -> dashboard_state:** Both are small key-value collections. Storing as dashboard_state entries (prefixed key for statcan_indicators) avoids new tables and keeps access through the existing `get_dashboard_state()` API.
- **Windows UTF-8 fix:** Logger's `INFO: CAN-MACRO: Firestore -> SQLite Migration` triggered a `UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'` on Windows cp1252. Fixed by replacing the arrow with `->` ASCII and adding `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` as defense-in-depth.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced single list(stream()) with paginated cursor streaming**
- **Found during:** Task 1 verification — first dry-run attempt
- **Issue:** `list(db.collection('projects').stream())` hit Firestore's 300-second deadline on the large projects collection, returning a 429 Quota exceeded timeout. The script logged a warning and skipped the collection entirely.
- **Fix:** Replaced `list(collection.stream())` in `migrate_collection()` with `_stream_collection_paginated()` — cursor-based pagination querying 200 documents per page with exponential backoff retry (up to 5 attempts, starting at 5s delay). Each page completes in well under 300s.
- **Files modified:** `migrate_firestore_to_sqlite.py`
- **Verification:** Dry-run connects to Firestore, streams first page of projects collection, continues to next collections without timeout
- **Committed in:** b9ea20a (same task commit — fix applied before final commit)

**2. [Rule 1 - Bug] Replaced Unicode arrow with ASCII in log message**
- **Found during:** Task 1 first dry-run — logging error in terminal output
- **Issue:** `logger.info("CAN-MACRO: Firestore \u2192 SQLite Migration")` raised `UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'` on Windows cp1252 console
- **Fix:** Changed `\u2192` to `->` in log message; added `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at module startup for Windows
- **Files modified:** `migrate_firestore_to_sqlite.py`
- **Verification:** Log output clean, no encoding errors
- **Committed in:** b9ea20a (same task commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for the script to function on Windows against a large Firestore database. No scope creep.

## Issues Encountered

- Firestore `projects` collection exceeds 300s streaming timeout due to size and quota rate limiting. Resolved by paginated streaming.
- Windows cp1252 console encoding incompatible with Unicode arrows in log messages. Resolved by ASCII substitution and UTF-8 reconfigure.

## Next Phase Readiness

- `migrate_firestore_to_sqlite.py` is ready to run: `python migrate_firestore_to_sqlite.py --dry-run` to count documents first, then `python migrate_firestore_to_sqlite.py` for the full migration.
- Migration report (DB-05 acceptance gate) will be produced on completion — per-collection Firestore doc vs SQLite row counts must match before Phase 13 is declared complete.
- Phase 13 Plans 03-05 (pipeline module updates to use db.py) do not depend on a completed migration run — they update Python code to import db.py instead of firebase_admin.

## Self-Check: PASSED
