# Requirements: CAN-MACRO Strategic Dashboard

**Defined:** 2026-03-07
**Core Value:** Automated, factual, source-cited weekly intelligence on Canadian capital projects and economic conditions

## v2.0 Requirements

Requirements for milestone v2.0: Infrastructure Overhaul — SQLite, GitHub Pages, Search Layer.

### Database Migration (DB)

- [x] **DB-01**: db.py module provides single interface to SQLite — no direct sqlite3 calls in other modules
- [x] **DB-02**: All 14 Firestore collections mapped to SQLite tables with correct schema
- [x] **DB-03**: FTS5 virtual table on projects for full-text search
- [ ] **DB-04**: One-time migration script reads all Firestore data and populates SQLite
- [ ] **DB-05**: Migration report verifies row counts match Firestore document counts
- [x] **DB-06**: upsert_project() preserves evidence merge (never loses URLs), status non-regression, confidence-only-increases
- [ ] **DB-07**: All ~40 Python files updated to import from db.py instead of firebase_admin/firestore
- [ ] **DB-08**: firebase-admin removed from requirements.txt
- [ ] **DB-09**: Pipeline run logging works via SQLite (replaces Firestore pipeline_runs)
- [ ] **DB-10**: Tavily credit tracking works via SQLite dashboard_state (replaces Firestore pipeline_state)

### Static Export (EXP)

- [ ] **EXP-01**: export_dashboard.py generates all static JSON files from SQLite
- [ ] **EXP-02**: Per-province project files (13 provinces) respect GDP thresholds
- [ ] **EXP-03**: No-value projects included as "unconfirmed" in exports
- [ ] **EXP-04**: Latest briefing, briefing archive, indicators, trends, events, microscope history all exported
- [ ] **EXP-05**: Export runs as final step of weekly pipeline automatically

### Frontend (FE)

- [ ] **FE-01**: All Firebase SDK imports removed from frontend
- [ ] **FE-02**: All data loads via fetch() to static JSON files
- [ ] **FE-03**: Province filtering triggers correct per-province JSON file fetch
- [ ] **FE-04**: All existing UI features preserved (project cards, filters, charts, briefing, V-code search)
- [ ] **FE-05**: Firebase API key removed from frontend code
- [ ] **FE-06**: Loading indicators shown while JSON files download

### Deployment (DEP)

- [ ] **DEP-01**: deploy_to_github.py copies public/ + data/ to docs/ directory
- [ ] **DEP-02**: GitHub Pages serves the dashboard from docs/ on main branch
- [ ] **DEP-03**: Weekly pipeline runs via GitHub Actions (Monday 5:30 AM ET)
- [ ] **DEP-04**: Daily indicator refresh runs via GitHub Actions (midnight ET)
- [ ] **DEP-05**: GitHub Actions workflows use secrets for API keys
- [ ] **DEP-06**: Firebase Cloud Functions, firebase.json, firestore configs archived

### User Submissions (SUB)

- [ ] **SUB-01**: Missing project form submits via Google Form instead of Firestore
- [ ] **SUB-02**: Pipeline reads Google Form submissions from connected Google Sheet
- [ ] **SUB-03**: Project correction form submits via Google Form

### Cleanup (CLN)

- [ ] **CLN-01**: All .bak files deleted (gemini_pro_reasoning.py.bak, compound_discovery.py.bak, etc.)
- [ ] **CLN-02**: All Firebase references removed from documentation (CLAUDE.md, spec)
- [ ] **CLN-03**: No firebase_admin or google.cloud.firestore imports remain in any .py file

## v1.2 Requirements (Superseded by v2.0)

v1.2 was defined but never executed (0% progress). Some goals are addressed differently in v2.0:
- OPS-01/02/03 (pipeline logging, Tavily tracking) → DB-09, DB-10 (via SQLite instead of Firestore)
- FEND-04 (frontend modularization) → Already done (JS extracted to app.js)
- FEND-05/07 (pipeline status, cost widgets) → FE-04 (preserved in frontend rewrite)

Remaining v1.2 items deferred to future:
- **DISC-01**: RSS feed validation — audit 85 test feeds
- **DISC-03/04**: Tavily enrichment effectiveness tracking and prioritization

## v1.1 Requirements (Complete)

All 12 requirements verified complete on 2026-03-07.

### Search Layer (Complete)

- [x] **SRCH-01**: Pipeline uses Google News RSS (759 queries) as primary discovery
- [x] **SRCH-02**: Google News RSS articles flow through existing 6-layer filter
- [x] **SRCH-03**: Tavily performs targeted enrichment within 1000/mo budget
- [x] **SRCH-04**: All reasoning tasks use Claude Sonnet
- [x] **SRCH-05**: Gemini Pro code paths removed
- [x] **SRCH-06**: Pipeline completes using only free Gemini Flash + paid Claude Sonnet + free Tavily

### Frontend (Complete)

- [x] **FEND-01**: Province names normalize correctly across all dashboard views
- [x] **FEND-02**: GDP thresholds in frontend match pipeline_config.py values
- [x] **FEND-03**: Projects load filtered by province with 5000 project display limit

### Data Quality (Complete)

- [x] **DATA-01**: Dedup audit identifies and merges duplicate projects in Firestore
- [x] **DATA-02**: Interactive indicator chart with category/indicator/province selectors
- [x] **DATA-03**: Chart supports time range selection and displays latest value callout

## Out of Scope

| Feature | Reason |
|---------|--------|
| Gemini grounded search | Caused $136/day in charges — permanently removed |
| Gemini Pro | Removed. All reasoning through Claude Sonnet only. |
| Perplexity in weekly pipeline | Removed from weekly runs. |
| GDELT as primary discovery | Reduced role due to network issues + cost. |
| Mobile app | Web-first static SPA is sufficient. |
| Real-time updates | Weekly cadence is the design. |
| Dual-write migration period | Solo developer, weekly cadence allows clean cutover. |
| Server-side form processing | Static site — Google Forms handles user submissions. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | Phase 13 | Complete |
| DB-02 | Phase 13 | Complete |
| DB-03 | Phase 13 | Complete |
| DB-04 | Phase 13 | Pending |
| DB-05 | Phase 13 | Pending |
| DB-06 | Phase 13 | Complete |
| DB-07 | Phase 13 | Pending |
| DB-08 | Phase 13 | Pending |
| DB-09 | Phase 13 | Pending |
| DB-10 | Phase 13 | Pending |
| EXP-01 | Phase 14 | Pending |
| EXP-02 | Phase 14 | Pending |
| EXP-03 | Phase 14 | Pending |
| EXP-04 | Phase 14 | Pending |
| EXP-05 | Phase 14 | Pending |
| FE-01 | Phase 15 | Pending |
| FE-02 | Phase 15 | Pending |
| FE-03 | Phase 15 | Pending |
| FE-04 | Phase 15 | Pending |
| FE-05 | Phase 15 | Pending |
| FE-06 | Phase 15 | Pending |
| DEP-01 | Phase 16 | Pending |
| DEP-02 | Phase 16 | Pending |
| DEP-03 | Phase 16 | Pending |
| DEP-04 | Phase 16 | Pending |
| DEP-05 | Phase 16 | Pending |
| DEP-06 | Phase 16 | Pending |
| SUB-01 | Phase 17 | Pending |
| SUB-02 | Phase 17 | Pending |
| SUB-03 | Phase 17 | Pending |
| CLN-01 | Phase 18 | Pending |
| CLN-02 | Phase 18 | Pending |
| CLN-03 | Phase 18 | Pending |

**Coverage:**
- v2.0 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 after v2.0 milestone definition*
