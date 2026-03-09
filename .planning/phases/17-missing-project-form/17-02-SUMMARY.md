---
phase: 17-missing-project-form
plan: 02
subsystem: ui
tags: [github-issues, frontend, forms, external-links]

# Dependency graph
requires:
  - phase: 17-missing-project-form
    provides: "GitHub Issues templates and reader (17-01)"
  - phase: 15-frontend-rewrite
    provides: "Static frontend with app.js extraction"
provides:
  - "Working GitHub Issues links replacing disabled in-page submission forms"
  - "Report a Missing Project button linking to GitHub issue template"
  - "Report correction links on project cards with prefilled project name"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "External GitHub Issues links replace in-page form submissions"

key-files:
  created: []
  modified:
    - public/index.html
    - public/js/app.js

key-decisions:
  - "Direct anchor links for missing project (no JS needed) vs window.open for corrections (prefills project name)"

patterns-established:
  - "User submissions route through GitHub Issues with YAML form templates"

requirements-completed: [SUB-01, SUB-03]

# Metrics
duration: 5min
completed: 2026-03-09
---

# Phase 17 Plan 02: GitHub Issues Frontend Links Summary

**Replaced disabled in-page submission forms with working GitHub Issues external links for missing projects and corrections**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-09T23:19:29Z
- **Completed:** 2026-03-09T23:20:00Z
- **Tasks:** 2 (1 auto + 1 checkpoint)
- **Files modified:** 2

## Accomplishments
- Removed old in-page form HTML (dropdowns, inputs, submit buttons) from index.html
- Replaced "Report a Missing Project" with direct link to GitHub Issues missing-project template
- Replaced inline correction forms on project cards with "Report correction" links to GitHub Issues with project name prefilled in title
- Eliminated all amber "being migrated" banner text from app.js

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace in-page form with GitHub Issues links** - `93f6079` (feat)
2. **Task 2: Verify GitHub Issues link integration** - checkpoint approved by user

## Files Created/Modified
- `public/index.html` - Replaced missedProjectSection form HTML with GitHub Issues anchor link
- `public/js/app.js` - Replaced submitMissedProject/submitProjectCorrection with GitHub Issues link functions; removed old dropdown population code and inline correction form builder

## Decisions Made
- Used direct `<a>` anchor for missing project button (no JavaScript needed, simpler)
- Used `window.open` with `encodeURIComponent` for correction links to prefill project name in issue title

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 17 (Missing Project Form) is complete - both plans executed
- GitHub Issues templates created (17-01) and frontend links connected (17-02)
- Ready for Phase 18 (Cleanup) or next milestone phase

## Self-Check: PASSED

All files found, all commits verified.

---
*Phase: 17-missing-project-form*
*Completed: 2026-03-09*
