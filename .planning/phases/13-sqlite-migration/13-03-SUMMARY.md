---
phase: 13-sqlite-migration
plan: "03"
subsystem: pipeline-infrastructure
tags: [sqlite, pipeline-logging, tavily, pipeline-state, firestore-removal]
dependency_graph:
  requires: [db.py from 13-01]
  provides: [pipeline_logging.py SQLite, tavily_search.py SQLite, pipeline_state.py SQLite]
  affects: [13-04, 13-05, update_dashboard.py, all callers of these three modules]
tech_stack:
  added: []
  patterns: [module-level connection singleton, backward-compat db param (ignored), optional conn for testability, in-memory dict + SQLite write pattern]
key_files:
  created: []
  modified:
    - pipeline_logging.py
    - tavily_search.py
    - pipeline_state.py
decisions:
  - "PipelineRunLogger keeps in-memory _discovery and _api_usage dicts, writing full JSON to SQLite on every update — avoids SQLite read-modify-write per field, matches Firestore dict update semantics"
  - "tavily_search.py uses module-level _tracking_conn singleton; set_tracking_db() accepts both sqlite3.Connection and legacy Firestore objects (ignored) for backward compat"
  - "pipeline_state.py store/get_follow_up_queries keep db param for backward compat but add optional conn param to allow in-memory test connections without changing existing callers"
metrics:
  duration_seconds: 169
  completed_date: "2026-03-08"
  tasks_completed: 2
  files_modified: 3
  lines_written: 390
---

# Phase 13 Plan 03: Pipeline Infrastructure SQLite Migration Summary

**One-liner:** Rewrote pipeline_logging.py, tavily_search.py, and pipeline_state.py to use SQLite via db.py, eliminating all Firestore imports from the pipeline's operational infrastructure modules.

## What Was Built

Three operational infrastructure modules were rewritten with zero Firestore imports. All persistence now routes through `db.py`.

### pipeline_logging.py — PipelineRunLogger

| Before | After |
|---|---|
| `from google.cloud.firestore_v1 import ArrayUnion, Increment` | `from db import get_db, save_pipeline_run, update_pipeline_run` |
| `__init__(self, db=None, run_type)` — db=Firestore client | `__init__(self, conn=None, run_type)` — conn=sqlite3.Connection |
| `db.collection("pipeline_runs").add(doc_data)` | `save_pipeline_run(conn, doc_data)` returns `run_id` |
| `doc_ref.update({"steps_completed": ArrayUnion(...)})` | `update_pipeline_run(conn, run_id, {"steps_completed": json.dumps(...)})` |
| `doc_ref.update({f"{category}.{key}": Increment(amount)})` | In-memory dict increment, then `update_pipeline_run(conn, run_id, {category: json.dumps(dict)})` |

Key design: maintains in-memory `_discovery` and `_api_usage` dicts. Every `log_metric`/`increment_metric` call updates the dict and writes the full JSON to SQLite in one `UPDATE`. This avoids read-modify-write per field.

### tavily_search.py — Credit Tracking

| Before | After |
|---|---|
| `db.collection("pipeline_state").document("tavily_credits").get()` | `get_tavily_credits(conn)` from db.py |
| `from google.cloud.firestore_v1 import Increment; ref.update({"used": Increment(credits)})` | `increment_tavily_credits(conn, credits)` from db.py |
| `_tracking_db = None` (Firestore client) | `_tracking_conn = None` (sqlite3.Connection) |
| `set_tracking_db(db)` stores Firestore client | `set_tracking_db(db)` detects sqlite3.Connection vs legacy; calls `get_db()` for legacy |

Monthly auto-reset is handled entirely within `db.py`'s `get_tavily_credits()` — if stored month differs from current month, returns `{"month": current, "used": 0}`.

### pipeline_state.py — Follow-up Queries

| Before | After |
|---|---|
| `db.collection("pipeline_state").document("follow_up_queries").set(...)` | `_save_follow_up_queries(conn, queries)` from db.py |
| `db.collection("pipeline_state").document("follow_up_queries").get()` | `_get_follow_up_queries(conn)` from db.py |
| `db` param = Firestore client | `db` param kept but ignored; new `conn` param for sqlite3.Connection |

`parse_json_response()` unchanged — no Firestore dependency.

## Verification Results

```
python -c "from pipeline_logging import PipelineRunLogger; from db import init_db; \
  conn = init_db(':memory:'); r = PipelineRunLogger(conn=conn); \
  r.start(); r.log_step('test'); r.finalize('success'); print('OK')"
# Output:   [LOG] Run logging started: run_id=1
#           [LOG] Run finalized: success (0s, 1 steps, 0 errors)
#           OK

python -c "from pipeline_logging import PipelineRunLogger; from tavily_search import can_use_tavily; \
  from pipeline_state import store_follow_up_queries; print('All three modules import cleanly')"
# Output: All three modules import cleanly

grep "firebase_admin\|google.cloud.firestore" pipeline_logging.py tavily_search.py pipeline_state.py
# (no output — zero Firestore imports)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added optional `conn` parameter to pipeline_state.py functions**
- **Found during:** Task 2 smoke test
- **Issue:** `store_follow_up_queries()` and `get_follow_up_queries()` called `get_db()` unconditionally, opening a new connection to the default `dashboard.db` file. This broke in-memory test isolation — callers passing an `:memory:` connection got a different connection writing to a non-existent table.
- **Fix:** Added optional `conn=None` parameter to both functions. If provided, uses it; otherwise falls back to `get_db()`. Existing callers unchanged (they pass `db` as positional, not `conn`).
- **Files modified:** `pipeline_state.py`
- **Commit:** 3a4023c (same Task 2 commit)

## Self-Check: PASSED
