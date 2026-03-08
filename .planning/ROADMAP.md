# Roadmap: CAN-MACRO Strategic Dashboard

---

## Milestone v1.2 (Phases 7-12)

### Overview

Milestone v1.2 hardens the operational foundation laid by v1.1. It adds pipeline run logging and Tavily credit tracking (preventing budget overruns), validates 85 untested RSS feeds, modularizes the frontend past its OOM deployment threshold, optimizes enrichment budget allocation, and surfaces pipeline health and cost data on the dashboard. Six phases execute in dependency order: logging infrastructure first (foundation for tracking), then credit tracking, RSS validation and frontend modularization (parallelizable), enrichment optimization, and finally the operational dashboard widgets.

### Phases

**Phase Numbering:**
- Continues from v1.1 (phases 1-6 complete)
- Integer phases (7, 8, 9): Planned milestone work
- Decimal phases (7.1, 7.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 7: Pipeline Run Logging** - Add structured run logs to Firestore for every pipeline execution
- [ ] **Phase 8: Tavily Credit Tracking** - Track and enforce the 1,000 credit/month Tavily cap
- [ ] **Phase 9: RSS Feed Validation** - Audit 85 test feeds and expand municipal coverage
- [ ] **Phase 10: Frontend Modularization** - Extract JS from index.html, fix OOM deployment
- [ ] **Phase 11: Enrichment Optimization** - Confidence-weighted Tavily budget + effectiveness tracking
- [ ] **Phase 12: Operational Dashboard** - Pipeline health, cost widgets, backup automation, tests

### Phase Details

#### Phase 7: Pipeline Run Logging
**Goal**: Every pipeline run writes structured logs (timing, step completion, errors, counts) to a `pipeline_runs` Firestore collection
**Depends on**: Nothing (first phase)
**Requirements**: OPS-01
**Success Criteria** (what must be TRUE):
  1. `update_dashboard.py` creates a run document at start, updates it after each major step, and finalizes it on completion or error
  2. Run document includes: start_time, end_time, duration, steps_completed, errors, articles_found, projects_added, projects_updated
  3. Failed runs still write a document with error details and the step that failed
  4. Run logs are queryable by date range in Firestore
**Plans**: TBD

#### Phase 8: Tavily Credit Tracking
**Goal**: Tavily credit consumption is tracked per run and enrichment halts when approaching the monthly cap
**Depends on**: Phase 7 (logs to same pipeline_runs collection)
**Requirements**: OPS-02, OPS-03
**Success Criteria** (what must be TRUE):
  1. Each Tavily search call increments a credit counter tracked in Firestore (`pipeline_state/tavily_credits`)
  2. Before each enrichment search, the pipeline checks remaining monthly credits and skips if < 50 credits remain
  3. Per-run Tavily credit usage and Claude Sonnet token usage are recorded in the run log document
  4. Credit counter resets automatically at the start of each calendar month
**Plans**: TBD

#### Phase 9: RSS Feed Validation
**Goal**: All 85 `test=true` RSS feeds are audited for validity and relevance; municipal category is expanded
**Depends on**: Nothing (independent)
**Requirements**: DISC-01, DISC-02
**Success Criteria** (what must be TRUE):
  1. A validation script fetches each `test=true` feed URL and checks: resolves (HTTP 200), returns valid RSS/Atom XML, contains at least 1 article from the last 30 days
  2. Valid feeds have `test` flag removed (promoted to production); dead/irrelevant feeds are removed from `rss_feeds.json`
  3. Municipal category has feeds for at least 5 major CMAs (Vancouver, Calgary, Edmonton, Ottawa, Toronto)
  4. Validation results are logged with per-feed status (alive/dead/irrelevant/promoted)
**Plans**: TBD

#### Phase 10: Frontend Modularization
**Goal**: JavaScript extracted from index.html into separate files; HTML stays under 500 lines; OOM deployment issue resolved
**Depends on**: Nothing (independent)
**Requirements**: FEND-04, FEND-06
**Success Criteria** (what must be TRUE):
  1. `public/index.html` contains only HTML structure and is under 500 lines
  2. JavaScript is split into logical modules (`app.js`, `charts.js`, `projects.js`) loaded via `<script>` tags
  3. `firebase deploy` succeeds without `--max-old-space-size=4096` workaround
  4. All existing dashboard functionality works identically after modularization
  5. ARIA labels added to all interactive elements; keyboard navigation works for tab switching and filters
**Plans**: TBD

#### Phase 11: Enrichment Optimization
**Goal**: Tavily enrichment budget is allocated by confidence score and effectiveness is tracked
**Depends on**: Phase 8 (needs credit tracking infrastructure)
**Requirements**: DISC-03, DISC-04
**Success Criteria** (what must be TRUE):
  1. Projects are sorted by confidence score before enrichment; high-confidence projects missing one field are enriched first
  2. Each enrichment search logs whether it filled a gap (found cost/proponent/status) or returned nothing useful
  3. Per-run enrichment hit rate (successful fills / total searches) is recorded in the run log
  4. Enrichment skips projects below a configurable minimum confidence threshold
**Plans**: TBD

#### Phase 12: Operational Dashboard
**Goal**: Dashboard displays pipeline health and cost data; automated backups and basic tests are in place
**Depends on**: Phases 7, 8, 10 (needs run logs, cost data, and modularized frontend)
**Requirements**: OPS-04, OPS-05, FEND-05, FEND-07
**Success Criteria** (what must be TRUE):
  1. Dashboard shows a pipeline status widget: last run date, articles processed, projects added/updated, errors
  2. Dashboard shows a cost monitor widget: month-to-date Tavily credits used, Claude Sonnet tokens used
  3. A Cloud Function exports projects, indicator_history, and weekly_briefings collections to Cloud Storage weekly
  4. Integration tests cover the core pipeline path (RSS fetch → filter → extraction → dedup) with mocked external APIs
**Plans**: TBD

### Progress (v1.2)

**Execution Order:**
Phases 7, 9, 10 can execute in parallel (no dependencies).
Phase 8 follows Phase 7. Phase 11 follows Phase 8. Phase 12 follows Phases 7, 8, and 10.

Recommended sequence: 7 → 8 → 9 (parallel with 8) → 10 (parallel with 8/9) → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7. Pipeline Run Logging | — | Pending | — |
| 8. Tavily Credit Tracking | — | Pending | — |
| 9. RSS Feed Validation | — | Pending | — |
| 10. Frontend Modularization | — | Pending | — |
| 11. Enrichment Optimization | — | Pending | — |
| 12. Operational Dashboard | — | Pending | — |

---

## Milestone v2.0 — Infrastructure Overhaul: SQLite, GitHub Pages, Search Layer (Phases 13-18)

**Milestone goal:** Replace the entire infrastructure layer (Firestore → SQLite, Firebase Hosting → GitHub Pages, Cloud Functions → GitHub Actions) while keeping all business logic intact. Eliminates Google Cloud dependency and deployment complexity.

**Coverage:** 33/33 v2.0 requirements mapped. No orphans.

### Phases

- [x] **Phase 13: SQLite Migration** — Replace all Firestore access with a single db.py SQLite interface across the entire codebase (completed 2026-03-08)
- [ ] **Phase 14: Static JSON Export** — Build export_dashboard.py to generate all static JSON files consumed by the frontend
- [ ] **Phase 15: Frontend Rewrite** — Replace Firebase SDK with fetch() to static JSON while preserving all existing UI features
- [ ] **Phase 16: GitHub Pages + Actions** — Deploy dashboard to GitHub Pages and automate the pipeline via GitHub Actions
- [ ] **Phase 17: Missing Project Form** — Replace Firestore-based user submissions with Google Form + Sheet integration
- [ ] **Phase 18: Cleanup** — Remove all .bak files, Firebase configs, dead imports, and documentation references

### Phase Details

#### Phase 13: SQLite Migration
**Goal**: The entire pipeline reads from and writes to SQLite through a single db.py interface — no module touches Firestore or firebase_admin directly
**Depends on**: Nothing (first phase of milestone)
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, DB-07, DB-08, DB-09, DB-10
**Success Criteria** (what must be TRUE):
  1. Running `python update_dashboard.py` completes a full pipeline run without any Firestore connection or firebase_admin import being invoked
  2. A migration report printed after the one-time migration script shows SQLite row counts matching Firestore document counts for all 14 collections
  3. Adding a new project via upsert_project() preserves the evidence array (URLs never dropped), does not regress status, and does not decrease confidence score
  4. Full-text search on the projects table returns relevant results using SQLite FTS5
  5. Pipeline run logs and Tavily credit usage are visible in the SQLite database via db.py queries
**Plans:** 5/5 plans complete
Plans:
- [ ] 13-01-PLAN.md — Create db.py SQLite interface with schemas, FTS5, and upsert business rules
- [ ] 13-02-PLAN.md — One-time Firestore-to-SQLite migration script with verification report
- [ ] 13-03-PLAN.md — Rewrite pipeline_logging, tavily_search, pipeline_state for SQLite
- [ ] 13-04-PLAN.md — Rewrite all core pipeline modules to use db.py
- [ ] 13-05-PLAN.md — Rewrite backfill/seed/audit scripts and remove firebase-admin from requirements.txt

#### Phase 14: Static JSON Export
**Goal**: The pipeline produces a complete set of static JSON files that represent the full dashboard state — ready for a browser to consume without any database connection
**Depends on**: Phase 13
**Requirements**: EXP-01, EXP-02, EXP-03, EXP-04, EXP-05
**Success Criteria** (what must be TRUE):
  1. Running export_dashboard.py produces JSON files for all 13 provinces, the latest briefing, briefing archive, indicators, trends, events, and microscope history in the docs/data/ directory
  2. Province JSON files contain only projects meeting that province's GDP threshold, plus unconfirmed (no-value) projects labeled as such
  3. Export runs automatically as the final step of the weekly Monday pipeline without manual intervention
  4. All exported JSON files are valid (parseable by JSON.parse with no errors) and contain non-empty data after a full pipeline run
**Plans:** 1/2 plans executed
Plans:
- [ ] 14-01-PLAN.md — Create export_dashboard.py with all export functions and validation
- [ ] 14-02-PLAN.md — Integrate export as final pipeline step in update_dashboard.py

#### Phase 15: Frontend Rewrite
**Goal**: The dashboard loads entirely from static JSON files — no Firebase SDK, no API key in the browser, all existing UI features intact
**Depends on**: Phase 14
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06
**Success Criteria** (what must be TRUE):
  1. Opening the dashboard HTML file in a browser with no Firebase project configured still loads and displays all data correctly
  2. Selecting a different province from the filter dropdown triggers a fetch() call to the correct per-province JSON file and updates the project list
  3. All existing UI features work: project cards, sector filter, Chart.js indicator charts, weekly briefing display, V-code search, and briefing download buttons
  4. No Firebase API key, firebase_admin credential, or google.cloud reference appears anywhere in the frontend HTML or JS source
  5. A loading spinner or indicator is visible while province JSON files are being fetched
**Plans**: TBD

#### Phase 16: GitHub Pages + Actions
**Goal**: The dashboard is live on GitHub Pages and the pipeline runs automatically every week and every day via GitHub Actions — no local execution required
**Depends on**: Phase 15
**Requirements**: DEP-01, DEP-02, DEP-03, DEP-04, DEP-05, DEP-06
**Success Criteria** (what must be TRUE):
  1. The public dashboard URL (github.io) serves the fully functional dashboard from the docs/ directory on the main branch
  2. A GitHub Actions workflow run appears in the Actions tab every Monday at approximately 5:30 AM ET completing the full weekly pipeline
  3. A GitHub Actions workflow run appears every midnight ET completing the daily indicator refresh
  4. API keys (ANTHROPIC, TAVILY, GEMINI) are stored as GitHub repository secrets and never appear in any committed file
  5. All Firebase Cloud Functions, firebase.json, and Firestore rule files are archived and removed from the active codebase
**Plans**: TBD

#### Phase 17: Missing Project Form
**Goal**: Users can submit missing projects and corrections via Google Forms — no Firestore dependency for user submissions, and the pipeline reads those submissions automatically
**Depends on**: Nothing (independent of phases 13-16)
**Requirements**: SUB-01, SUB-02, SUB-03
**Success Criteria** (what must be TRUE):
  1. Clicking the "Missing Project" button on the dashboard opens the Google Form in a new tab and the submission reaches the connected Google Sheet
  2. Running the pipeline after a form submission picks up entries from the Google Sheet and creates or updates the corresponding project in SQLite
  3. Clicking the "Project Correction" form link opens the correct Google Form and the submission routes to the pipeline's Google Sheet reader
**Plans**: TBD

#### Phase 18: Cleanup
**Goal**: The repository contains no dead code, no .bak files, no Firebase references in documentation or imports — the codebase reflects exactly what runs in production
**Depends on**: Phase 13, Phase 14, Phase 15, Phase 16, Phase 17 (runs after all others complete)
**Requirements**: CLN-01, CLN-02, CLN-03
**Success Criteria** (what must be TRUE):
  1. Running `find . -name "*.bak"` returns no results — all archived backup files have been deleted
  2. Searching CLAUDE.md, the system specification, and all documentation for "Firestore", "Firebase", "firebase_admin" returns only historical past-tense references, not active instructions
  3. Running `grep -r "firebase_admin\|google.cloud.firestore" --include="*.py"` across the project returns no matches in any active Python file
**Plans**: TBD

### Progress (v2.0)

**Execution Order:**
13 → 14 → 15 → 16 (sequential chain). Phase 17 is independent. Phase 18 runs last after all others.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 13. SQLite Migration | 5/5 | Complete    | 2026-03-08 |
| 14. Static JSON Export | 1/2 | In Progress|  |
| 15. Frontend Rewrite | 0/? | Not started | — |
| 16. GitHub Pages + Actions | 0/? | Not started | — |
| 17. Missing Project Form | 0/? | Not started | — |
| 18. Cleanup | 0/? | Not started | — |

### Requirement Coverage (v2.0)

| Requirement | Phase | Description |
|-------------|-------|-------------|
| DB-01 | 13 | db.py single interface module |
| DB-02 | 13 | All 14 collections mapped to SQLite tables |
| DB-03 | 13 | FTS5 virtual table on projects |
| DB-04 | 13 | One-time migration script |
| DB-05 | 13 | Migration report verifying row counts |
| DB-06 | 13 | upsert_project() preserves evidence/status/confidence |
| DB-07 | 13 | All ~40 Python files updated to import from db.py |
| DB-08 | 13 | firebase-admin removed from requirements.txt |
| DB-09 | 13 | Pipeline run logging via SQLite |
| DB-10 | 13 | Tavily credit tracking via SQLite |
| EXP-01 | 14 | export_dashboard.py generates all static JSON |
| EXP-02 | 14 | Per-province files respect GDP thresholds |
| EXP-03 | 14 | No-value projects included as "unconfirmed" |
| EXP-04 | 14 | All briefing/indicator/trend/event data exported |
| EXP-05 | 14 | Export runs as final pipeline step automatically |
| FE-01 | 15 | Firebase SDK imports removed |
| FE-02 | 15 | All data loads via fetch() to static JSON |
| FE-03 | 15 | Province filter fetches correct per-province JSON |
| FE-04 | 15 | All existing UI features preserved |
| FE-05 | 15 | Firebase API key removed from frontend code |
| FE-06 | 15 | Loading indicators shown during fetch |
| DEP-01 | 16 | deploy_to_github.py copies to docs/ |
| DEP-02 | 16 | GitHub Pages serves from docs/ on main |
| DEP-03 | 16 | Weekly pipeline via GitHub Actions Monday 5:30 AM ET |
| DEP-04 | 16 | Daily indicator refresh via GitHub Actions midnight ET |
| DEP-05 | 16 | GitHub Actions workflows use secrets for API keys |
| DEP-06 | 16 | Firebase Cloud Functions and configs archived |
| SUB-01 | 17 | Missing project form via Google Form |
| SUB-02 | 17 | Pipeline reads Google Form submissions from Sheet |
| SUB-03 | 17 | Project correction form via Google Form |
| CLN-01 | 18 | All .bak files deleted |
| CLN-02 | 18 | Firebase references removed from documentation |
| CLN-03 | 18 | No firebase_admin imports in any .py file |

**Total: 33/33 v2.0 requirements mapped. No orphans.**

---

*Roadmap last updated: 2026-03-08*
*Current milestone: v2.0*
*Next: `/gsd:execute-phase 14` to begin Static JSON Export*
