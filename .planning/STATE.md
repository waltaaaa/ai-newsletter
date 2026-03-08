---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: "— Infrastructure Overhaul: SQLite, GitHub Pages, Search Layer"
status: planning
stopped_at: Completed 13-sqlite-migration/13-03-PLAN.md
last_updated: "2026-03-08T01:11:05.713Z"
last_activity: 2026-03-07 — Roadmap created for v2.0
progress:
  total_phases: 12
  completed_phases: 0
  total_plans: 5
  completed_plans: 2
  percent: 20
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-07)

**Core value:** Automated, factual, source-cited weekly intelligence on Canadian capital projects and economic conditions
**Current focus:** Milestone v2.0 — Infrastructure Overhaul — SQLite, GitHub Pages, Search Layer

## Current Position

Phase: 13 — SQLite Migration (not started)
Plan: —
Status: Roadmap defined, ready for Phase 13 planning
Last activity: 2026-03-07 — Roadmap created for v2.0

Progress: [██░░░░░░░░] 20%

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
| Phase 13-sqlite-migration P03 | 169 | 2 tasks | 3 files |

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

### Pending Todos

None.

### Blockers/Concerns

- 14 Firestore collections to migrate — ~40 Python files reference firebase_admin/google.cloud.firestore
- Frontend app.js has Firebase API key hardcoded — must be removed in Phase 15
- GitHub Actions needs ANTHROPIC, TAVILY, GEMINI as repository secrets before Phase 16
- Migration report (DB-05) must confirm row counts before declaring Phase 13 complete

## Session Continuity

Last session: 2026-03-08T01:10:55.877Z
Stopped at: Completed 13-sqlite-migration/13-03-PLAN.md
Resume at: `/gsd:plan-phase 13` — SQLite Migration
