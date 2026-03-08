---
phase: 15-frontend-rewrite
plan: "01"
subsystem: frontend-data-layer
tags: [firebase-removal, static-json, fetch-api, export]
dependency_graph:
  requires: [14-static-json-export]
  provides: [firebase-free-frontend, projects_all.json, pipeline_status.json]
  affects: [public/js/app.js, export_dashboard.py, docs/data/]
tech_stack:
  added: [fetch API, in-memory JSON cache]
  patterns: [static-file data layer, province slug mapping, graceful 404 handling]
key_files:
  created:
    - docs/data/projects_all.json
    - docs/data/pipeline_status.json
  modified:
    - export_dashboard.py
    - tests/test_export_dashboard.py
    - public/js/app.js
    - public/index.html
    - docs/data/manifest.json
decisions:
  - "fetchJSON() caches responses in module-level _cache object — avoids re-fetching same file for multiple render functions"
  - "PROV_SLUGS lookup table maps province codes to filename slugs at startup — avoids repeated string operations"
  - "policy.json and commodities.json: try/catch fetch with silent hide — these sections disappear gracefully if files do not exist"
  - "submitMissedProject and submitProjectCorrection: replaced Firestore writes with operator-contact message — Google Forms solution deferred to later plan"
  - "index.html script tag: removed type=module since no ES module imports remain"
metrics:
  duration: "~45 minutes"
  completed: "2026-03-08"
  tasks: 2
  files_modified: 5
  files_created: 2
requirements: [FE-01, FE-02, FE-03, FE-05]
---

# Phase 15 Plan 01: Firebase Removal and Static JSON Data Layer Summary

**One-liner:** Replaced all 33 Firebase SDK references in app.js with fetch() calls to static JSON files, and extended export_dashboard.py with projects_all.json and pipeline_status.json exports.

## What Was Done

### Task 1: Extend export_dashboard.py

Added two new export functions and wired them into `export_all()`:

**`export_all_projects(conn, output_dir)`**
- Queries all projects from SQLite with no province or threshold filter
- Sorts by lastSeen DESC, limits to 5000 rows
- Shapes each project identically to `export_province_projects` output (via `_project_for_export`)
- Writes `docs/data/projects_all.json` in compact JSON

**`export_pipeline_status(conn, output_dir)`**
- Queries most recent pipeline run from `pipeline_runs` table
- Aggregates Claude token usage from last 4 runs
- Reads Tavily credits from `dashboard_state` table (`tavily_credits` key)
- Writes `docs/data/pipeline_status.json` with `last_run`, `tavily`, `claude_tokens`, `recent_runs` keys

Both functions listed in `manifest.json`. Ran `export_all()` to regenerate `docs/data/`.

**New tests added to `tests/test_export_dashboard.py`:**
- `TestExportAllProjects::test_export_all_projects_creates_file` — 3 projects across 2 provinces, verifies all 3 present
- `TestExportPipelineStatus::test_export_pipeline_status_creates_file` — inserts run + tavily state, verifies structure

All 21 tests pass.

### Task 2: Rewrite app.js

Removed all Firebase SDK usage (33 references across 5 areas):

**Removed:**
- `import { initializeApp }` from firebase-app.js
- `import { getAuth, signInAnonymously, onAuthStateChanged }` from firebase-auth.js
- `import { getFirestore, doc, getDoc, ... }` from firebase-firestore.js
- `initializeApp({ apiKey: "AIzaSy..." })` — hardcoded API key
- `const auth = getAuth(app), db = getFirestore(app)`
- All `getDoc`, `getDocs`, `addDoc`, `collection(db`, `doc(db` calls
- `signInAnonymously`, `onAuthStateChanged`, auth timeout

**Added:**
- `fetchJSON(path)` utility — fetches from `data/` directory, caches responses in `_cache` object
- `PROV_SLUGS` mapping — code → slug (e.g., `'BC' → 'british_columbia'`)
- Direct `loadAll()` call at initialization (no auth gate)

**Data loading rewrites:**

| Function | Old | New |
|---|---|---|
| `loadNewsletter` | `getDoc(db,'newsletters','latest')` | `fetchJSON('briefing_latest.json')` |
| `loadEditionList` | `getDocs(query(...newsletters...))` | `fetchJSON('briefing_archive.json')` |
| `loadIndicators` | `getDoc(db,'statcan_indicators','latest')` | `fetchJSON('indicators.json')` |
| `loadProjects(prov)` | Firestore query by province | `fetchJSON('projects_{slug}.json')` or `projects_all.json` |
| `loadTimeseries(id)` | `getDoc(db,'timeseries',id)` | `fetchJSON('timeseries.json')[id]` |
| `loadIndExpData` | Two Firestore queries | Client-side filter on `indicators.json` |
| `renderTrendSummary` | `getDoc(db,'dashboard_state','latest_briefing')` | `fetchJSON('briefing_latest.json')` |
| `renderPipelineStatus` | `getDocs(pipeline_runs)` | `fetchJSON('pipeline_status.json')` |
| `renderCostMonitor` | Two Firestore queries | `fetchJSON('pipeline_status.json')` |
| `renderMicroscopeHistory` | `getDoc(db,'dashboard_state','microscope_history')` | `fetchJSON('microscope.json')` |
| `renderMicroscope` | `getDoc(db,'dashboard_state','microscope_current')` | `fetchJSON('microscope.json')` |
| `renderPolicySection` | `getDocs(policy_developments)` | `fetchJSON('policy.json')` with 404 hide |
| `renderCanadianCommodities` | `getDoc(db,'dashboard_state','canadian_commodities')` | `fetchJSON('commodities.json')` with 404 hide |

**Also updated:** `public/index.html` — removed `type="module"` from script tag (no ES module imports).

## Verification

```
grep -c -i "firebase|apiKey|AIzaSy|getFirestore|getAuth" public/js/app.js
# → 0

grep -c "fetchJSON|fetch(" public/js/app.js
# → 16

ls docs/data/projects_all.json docs/data/pipeline_status.json
# → both exist

python -m pytest tests/test_export_dashboard.py -x -q
# → 21 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] bSnap variable referenced after Firebase removal in renderTrendSummary**
- **Found during:** Task 2 rewrite of renderTrendSummary
- **Issue:** After removing `getDoc(db,'dashboard_state','latest_briefing')` → `bSnap`, the download buttons code still referenced `bSnap.exists()` and `bSnap.data()`
- **Fix:** Changed to read `briefing.pdf_url` and `briefing.docx_url` directly from the already-loaded `briefing_latest.json` object
- **Files modified:** `public/js/app.js`
- **Commit:** e8f44ab

**2. [Rule 2 - Missing functionality] submitMissedProject and submitProjectCorrection had no replacement**
- **Found during:** Task 2 — two `addDoc` calls required a write path
- **Issue:** No write-capable backend in static mode
- **Fix:** Replaced with an operator-contact message explaining static mode limitation. Google Forms replacement is specified in a later plan.
- **Files modified:** `public/js/app.js`
- **Commit:** e8f44ab

## Commits

| Hash | Message |
|---|---|
| f326a76 | feat(15-01): add export_all_projects and export_pipeline_status |
| e8f44ab | feat(15-01): rewrite app.js — remove all Firebase SDK references |

## Self-Check: PASSED

All files exist and all commits verified:
- public/js/app.js: FOUND
- docs/data/projects_all.json: FOUND
- docs/data/pipeline_status.json: FOUND
- .planning/phases/15-frontend-rewrite/15-01-SUMMARY.md: FOUND
- Commit f326a76: FOUND
- Commit e8f44ab: FOUND
