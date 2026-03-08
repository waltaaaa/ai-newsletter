---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: "— Infrastructure Overhaul: SQLite, GitHub Pages, Search Layer"
status: completed
stopped_at: Completed 16-02-PLAN.md
last_updated: "2026-03-08T15:36:01.572Z"
last_activity: "2026-03-08 — Completed 15-02: loading/error UX, disabled submissions, human verification passed"
progress:
  total_phases: 12
  completed_phases: 4
  total_plans: 11
  completed_plans: 11
  percent: 30
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-07)

**Core value:** Automated, factual, source-cited weekly intelligence on Canadian capital projects and economic conditions
**Current focus:** Milestone v2.0 — Infrastructure Overhaul — SQLite, GitHub Pages, Search Layer

## Current Position

Phase: 15 — Frontend Rewrite (complete)
Plan: 15-02 complete — Phase 16 (GitHub Pages + Actions) is next
Status: All three infrastructure phases complete — SQLite, Static JSON export, Firebase-free frontend
Last activity: 2026-03-08 — Completed 15-02: loading/error UX, disabled submissions, human verification passed

Progress: [███░░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: N/A
- Total execution time: N/A

**By Phase (v2.0):**

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 13. SQLite Migration | 0/? | Not started | — |
| 14. Static JSON Export | 0/? | Not started | — |
| 15. Frontend Rewrite | 0/? | Not started | — |
| 16. GitHub Pages + Actions | 0/? | Not started | — |
| 17. Missing Project Form | 0/? | Not started | — |
| 18. Cleanup | 0/? | Not started | — |
| Phase 13-sqlite-migration P01 | 294 | 2 tasks | 2 files |
| Phase 13-sqlite-migration P02 | 900 | 1 tasks | 1 files |
| Phase 13-sqlite-migration P03 | 169 | 2 tasks | 3 files |
| Phase 13-sqlite-migration P04 | 180 | 3 tasks | 22 files |
| Phase 13-sqlite-migration P05 | 11 | 3 tasks | 16 files |
| Phase 14-static-json-export P01 | 3 | 2 tasks | 23 files |
| Phase 14-static-json-export P02 | 8 | 2 tasks | 2 files |
| Phase 15-frontend-rewrite P01 | 45 | 2 tasks | 7 files |
| Phase 15-frontend-rewrite P02 | 15 | 1 task | 1 file |
| Phase 16-github-pages-actions P01 | 6 | 3 tasks | 14 files |
| Phase 16-github-pages-actions P02 | 0 | 1 tasks | 0 files |

## Accumulated Context

### Decisions

- [v1.1]: Gemini grounded search replaced with Google News RSS after $136/day cost incident
- [v1.1]: Gemini Pro removed entirely — all reasoning routed through Claude Sonnet
- [v1.1]: Tavily capped at 1,000 credits/month free tier
- [v1.2]: Frontend JS extracted to app.js — resolved 1,776-line OOM issue
- [v2.0]: Firestore → SQLite via db.py single interface module
- [v2.0]: Firebase Hosting → GitHub Pages from docs/ directory
- [v2.0]: Cloud Functions → GitHub Actions (free 2,000 min/month)
- [v2.0]: Live Firestore queries → Static JSON export via export_dashboard.py
- [v2.0]: Google Forms replaces Firestore writes for user submissions
- [Phase 13-sqlite-migration]: Used executescript() for schema creation to support multi-statement FTS5 trigger blocks
- [Phase 13-sqlite-migration]: save_indicator() auto-remaps Firestore field names (indicator->indicator_name, date->period) for zero-migration-cost callers
- [Phase 13-sqlite-migration]: Terminal states (Cancelled, On Hold, Suspended, Paused) always override forward project status regardless of STATUS_ORDER
- [Phase 13-sqlite-migration]: PipelineRunLogger keeps in-memory _discovery and _api_usage dicts, writing full JSON to SQLite on every update — avoids read-modify-write per field
- [Phase 13-sqlite-migration]: tavily_search.py set_tracking_db() accepts sqlite3.Connection or legacy Firestore objects (ignored) for zero-friction backward compat
- [Phase 13-sqlite-migration]: pipeline_state.py store/get_follow_up_queries add optional conn param for testability without breaking existing callers
- [Phase 13-sqlite-migration]: Paginated cursor-based Firestore streaming (200 docs/page) with exponential backoff replaces single list(stream()) to prevent 300s timeout on large collections
- [Phase 13-sqlite-migration]: pipeline_state and statcan_indicators collections both migrate into dashboard_state table keyed by doc_id — no separate tables needed
- [13-04]: Duck-typing pattern (hasattr(conn, 'execute')) used uniformly across all 22 migrated modules for Firestore backward compatibility without a breaking API change
- [13-04]: briefing_export.py Firebase Storage upload deferred to Phase 16 — local file save used as interim replacement
- [13-04]: JSON string serialization for SQLite array fields (evidence, statusHistory) — reads use json.loads(row["field"] or "[]"), writes use json.dumps(list)
- [Phase 13-sqlite-migration]: All 15 backfill/seed/audit scripts migrated to db.py completing DB-07 requirement
- [Phase 13-sqlite-migration]: firebase-admin removed from requirements.txt completing DB-08 requirement; SQLite is stdlib
- [Phase 14-static-json-export]: export_all uses init_db() not get_db() to ensure schema exists on empty databases
- [Phase 14-static-json-export]: Province files use compact JSON; briefing/manifest use indent=2 for readability
- [Phase 14-static-json-export]: Projects with unparseable or missing values included with value_confirmed=false
- [Phase 14-static-json-export]: Export step placed after Tavily usage logging and before run_log.finalize so conn is still valid
- [Phase 14-static-json-export]: Daily indicators-only mode also runs export so GitHub Pages site stays fresh after every daily run
- [Phase 15-frontend-rewrite]: fetchJSON() caches responses in _cache — avoids re-fetching same file for multiple render functions
- [Phase 15-frontend-rewrite]: policy.json and commodities.json: try/catch fetch with silent hide — sections disappear gracefully if files absent
- [Phase 15-frontend-rewrite]: submitMissedProject/submitProjectCorrection: replaced Firestore writes with operator-contact message in static mode
- [Phase 15-frontend-rewrite]: loadSection() sets skeleton then renders or shows inline error+retry — each section fails independently
- [Phase 15-frontend-rewrite]: submitMissedProject and submitProjectCorrection replaced with amber migration banner (FE-04, FE-06 fulfilled)
- [Phase 16-github-pages-actions]: deploy_to_github.py uses shutil.copytree(dirs_exist_ok=True) for idempotent docs/ population without touching docs/data/
- [Phase 16-github-pages-actions]: Both GitHub Actions workflows set GEMINI_SEARCH_ENABLED=false to prevent accidental grounded search charges
- [Phase 16-github-pages-actions]: Firebase configs moved to archive/firebase/ — functions/ directory removed; Cloud Functions replaced by GitHub Actions free tier
- [Phase 16-github-pages-actions]: GitHub Pages enabled on main branch /docs folder — serves static dashboard at https://waltaaaa.github.io/ai-newsletter/

### Pending Todos

None.

### Blockers/Concerns

- GitHub Actions needs ANTHROPIC, TAVILY, GEMINI as repository secrets before Phase 16 can deploy
- Phase 16 requires GitHub repository to exist and GitHub Pages to be enabled on the main branch

## Session Continuity

Last session: 2026-03-08T15:36:01.561Z
Stopped at: Completed 16-02-PLAN.md
Resume at: `/gsd:execute-phase 16` — begin GitHub Pages and Actions deployment
