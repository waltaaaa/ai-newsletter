---
phase: 17-missing-project-form
plan: 01
subsystem: pipeline
tags: [github-issues, urllib, issue-templates, user-submissions]

requires:
  - phase: 13-sqlite-migration
    provides: "db.py with save_missed_project, get/save_dashboard_state"
  - phase: 15-frontend-rewrite
    provides: "Static frontend with disabled submission forms"
provides:
  - "GitHub Issues reader module (github_issues_reader.py)"
  - "Structured issue templates for missing projects and corrections"
  - "Pipeline Step 2J integration before Step 2K enrichment"
affects: [17-missing-project-form]

tech-stack:
  added: [urllib.request]
  patterns: [github-issues-as-form, structured-issue-template-parsing]

key-files:
  created:
    - github_issues_reader.py
    - .github/ISSUE_TEMPLATE/missing-project.yml
    - .github/ISSUE_TEMPLATE/project-correction.yml
  modified:
    - update_dashboard.py

key-decisions:
  - "Used urllib.request (stdlib) for GitHub API — no new dependencies"
  - "save_dashboard_state used for tracking processed issue numbers (not set_dashboard_state)"
  - "Province display names mapped to abbreviations (AB, BC, etc.) for database consistency"
  - "Sector display names mapped to internal codes (oil_gas, mining, etc.)"

patterns-established:
  - "GitHub Issues as user submission form: structured YAML templates parsed via ### header splitting"
  - "Optional issue closing: requires GITHUB_TOKEN env var, skips gracefully without it"

requirements-completed: [SUB-02]

duration: 7min
completed: 2026-03-09
---

# Phase 17 Plan 01: GitHub Issues Reader Summary

**GitHub Issues reader module with structured templates replacing Firestore-based user submissions, integrated as pipeline Step 2J before enrichment**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-09T16:18:18Z
- **Completed:** 2026-03-09T16:25:03Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created github_issues_reader.py with fetch_issue_submissions() using stdlib urllib.request
- Created structured issue templates for missing projects (7 fields) and corrections (5 fields)
- Integrated as Step 2J in update_dashboard.py, feeding into existing Step 2K enrichment flow
- URL hard gate enforced — submissions without source URL are skipped
- Processed issue tracking via dashboard_state prevents re-processing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create issue templates and github_issues_reader.py module** - `69f5c94` (feat)
2. **Task 2: Integrate Issues reader into pipeline before Step 2K** - `3d02a6c` (feat)

## Files Created/Modified
- `github_issues_reader.py` - GitHub Issues API reader, parses structured templates, saves via db.save_missed_project()
- `.github/ISSUE_TEMPLATE/missing-project.yml` - Issue template with name, province, sector, value, proponent, description, source URL
- `.github/ISSUE_TEMPLATE/project-correction.yml` - Issue template with project name, field to correct, new value, source URL, notes
- `update_dashboard.py` - Added Step 2J (GitHub Issues reader) before Step 2K (enrichment)

## Decisions Made
- Used urllib.request (stdlib) instead of requests/aiohttp — no new dependencies needed
- Province and sector display names mapped to internal codes for database consistency
- Corrections saved as missed_projects with type='correction' in data JSON field
- Issue closing is optional — only attempted when GITHUB_TOKEN env var is available

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. GitHub Issues templates work automatically on public repos. GITHUB_TOKEN is optional (only needed for auto-closing issues).

## Next Phase Readiness
- GitHub Issues reader is ready for pipeline use
- Plan 17-02 (frontend links to issue templates) can proceed
- GITHUB_TOKEN should be added as a repository secret for auto-closing functionality

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 17-missing-project-form*
*Completed: 2026-03-09*
