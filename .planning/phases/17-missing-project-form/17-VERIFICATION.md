---
phase: 17-missing-project-form
verified: 2026-03-09T23:45:14Z
status: gaps_found
score: 6/9 must-haves verified
re_verification: false
gaps:
  - truth: "ROADMAP.md and REQUIREMENTS.md updated to reflect GitHub Issues pivot"
    status: failed
    reason: "ROADMAP.md phase 17 goal, success criteria, and plan names still reference Google Forms/Sheets. REQUIREMENTS.md SUB-01/02/03 still read 'Google Form' and 'Google Sheet'. Neither document was updated after the implementation pivot documented in CONTEXT.md."
    artifacts:
      - path: ".planning/ROADMAP.md"
        issue: "Phase 17 goal reads 'Users can submit missing projects and corrections via Google Forms', success criteria 1-3 all reference Google Form/Google Sheet. Plan names read 'Google Sheets reader module' and 'Replace in-page forms with Google Form links'."
      - path: ".planning/REQUIREMENTS.md"
        issue: "SUB-01 reads 'Missing project form submits via Google Form instead of Firestore', SUB-02 reads 'Pipeline reads Google Form submissions from connected Google Sheet', SUB-03 reads 'Project correction form submits via Google Form'. All three still describe the abandoned Google Forms approach."
    missing:
      - "Update ROADMAP.md phase 17 goal to: 'Users can submit missing projects and corrections via GitHub Issues — no Firestore dependency for user submissions, and the pipeline reads those submissions automatically'"
      - "Update ROADMAP.md success criteria 1-3 to describe GitHub Issues templates and the github_issues_reader.py pipeline integration"
      - "Update ROADMAP.md plan names from 'Google Sheets reader module' to 'GitHub Issues reader module'"
      - "Update REQUIREMENTS.md SUB-01 to: 'Missing project form submits via GitHub Issues template instead of Firestore'"
      - "Update REQUIREMENTS.md SUB-02 to: 'Pipeline reads GitHub Issues API submissions via github_issues_reader.py'"
      - "Update REQUIREMENTS.md SUB-03 to: 'Project correction form submits via GitHub Issues template'"
      - "Update the requirements tracking table at the bottom of REQUIREMENTS.md to reflect the GitHub Issues implementation"
human_verification:
  - test: "Open dashboard in browser, navigate to Projects tab, click 'Report a Missing Project' button"
    expected: "New browser tab opens to https://github.com/waltaaaa/ai-newsletter/issues/new?template=missing-project.yml with the structured missing-project form"
    why_human: "Cannot verify browser tab opening or GitHub template rendering programmatically"
  - test: "Expand any project row in the Projects tab, click 'Report correction' link"
    expected: "New browser tab opens to GitHub Issues new issue page with missing-project.yml correction template and the project name prefilled in the title"
    why_human: "Cannot verify window.open behavior or title prefill in a browser context programmatically"
---

# Phase 17: Missing Project Form — Verification Report

**Phase Goal (from prompt):** Users can submit missing projects and corrections via GitHub Issues — no Firestore dependency for user submissions, and the pipeline reads those submissions automatically

**Phase Goal (from ROADMAP.md — NOT updated):** Users can submit missing projects and corrections via Google Forms — no Firestore dependency for user submissions, and the pipeline reads those submissions automatically

**Verified:** 2026-03-09T23:45:14Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Implementation Pivot Notice

The planning CONTEXT.md (17-CONTEXT.md) explicitly documents a decision to replace Google Forms/Sheets with GitHub Issues:

> "Submission method (CHANGED: GitHub Issues replaces Google Forms)"

The implementation correctly uses GitHub Issues. However, ROADMAP.md and REQUIREMENTS.md were never updated to reflect this pivot. The gaps identified are documentation gaps, not implementation gaps — the working code is correct and complete.

---

## Goal Achievement

### Observable Truths

Truths are derived from the PLAN frontmatter `must_haves` sections across both plans (17-01-PLAN.md and 17-02-PLAN.md), which reflect the actual GitHub Issues implementation.

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Pipeline reads new issue submissions from GitHub Issues API on each run | VERIFIED | `github_issues_reader.py` line 224: `fetch_issue_submissions(conn)` fetches from `api.github.com/repos/waltaaaa/ai-newsletter/issues?labels=missing-project` and `?labels=project-correction`. Integrated as Step 2J in `update_dashboard.py` line 3473. |
| 2 | Submitted projects are created in SQLite via existing missed_project_enrichment flow | VERIFIED | `github_issues_reader.py` line 187: `save_missed_project(conn, project_dict)` called for each new issue. Step 2K (line 3488 in `update_dashboard.py`) follows immediately after Step 2J. |
| 3 | Corrections are logged as type='correction' in missed_projects table | VERIFIED | `github_issues_reader.py` line 209: `"type": "correction"` included in `data` JSON dict. Saved via `save_missed_project()`. |
| 4 | Pipeline continues gracefully if GitHub API is unreachable | VERIFIED | `github_issues_reader.py` lines 251-253 and 260-262: both fetch calls wrapped in try/except returning `{"skipped": True, "reason": ...}`. Step 2J in pipeline also wrapped in outer try/except (line 3474). |
| 5 | Processed issues are tracked in dashboard_state to avoid re-processing | VERIFIED | `github_issues_reader.py` line 237: `get_dashboard_state(conn, _STATE_KEY)` reads last processed issue number. Line 294: `save_dashboard_state(conn, _STATE_KEY, max_seen)` updates after processing. |
| 6 | Clicking 'Report a Missing Project' opens GitHub issue template in new tab | HUMAN NEEDED | `public/index.html` line 457: direct `<a href="https://github.com/waltaaaa/ai-newsletter/issues/new?template=missing-project.yml" target="_blank"` confirmed present. Browser behavior requires human verification. |
| 7 | Clicking 'Report correction' on a project card opens GitHub correction template with project name prefilled | HUMAN NEEDED | `public/js/app.js` line 1127-1128: `href="https://github.com/waltaaaa/ai-newsletter/issues/new?template=project-correction.yml&title=Correction:+'+encodeURIComponent(p.name||'')` confirmed present. Browser tab opening requires human verification. |
| 8 | No in-page form HTML remains — old dropdowns, inputs, and submit buttons are removed | VERIFIED | `grep` of `index.html` for `mpSubmitBtn`, `mpProvince`, `mpSector`, `being migrated` returns zero results. `missedProjectSection` now contains only an `<a>` anchor element (lines 456-458). |
| 9 | ROADMAP.md and REQUIREMENTS.md updated to reflect GitHub Issues pivot | FAILED | ROADMAP.md phase 17 goal, success criteria, and plan names still reference Google Forms/Sheets. REQUIREMENTS.md SUB-01/02/03 still describe the abandoned Google Forms approach. |

**Score:** 6/9 truths verified (2 pending human verification, 1 failed — documentation not updated)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `github_issues_reader.py` | GitHub Issues API reader for user submissions | VERIFIED | 297 lines. Exports `fetch_issue_submissions`. Imports `get_dashboard_state`, `save_dashboard_state`, `save_missed_project` from `db.py`. Full implementation: parses issue bodies, maps province/sector display names to codes, enforces URL hard gate, tracks processed IDs in dashboard_state, optionally closes issues. |
| `.github/ISSUE_TEMPLATE/missing-project.yml` | Structured issue template for missing project submissions | VERIFIED | 87 lines. 7 fields: Project Name (required), Province/Territory dropdown (13 options, required), Sector dropdown (18 options, required), Estimated Value (optional), Proponent/Developer (optional), Description (required), Source URL (required). Labels: `missing-project`. |
| `.github/ISSUE_TEMPLATE/project-correction.yml` | Structured issue template for project corrections | VERIFIED | 49 lines. 5 fields: Project Name (required), Field to Correct dropdown (7 options, required), Correct Value (required), Source URL (required), Additional Notes (optional). Labels: `project-correction`. |
| `update_dashboard.py` | Pipeline integration of Issues reader before Step 2K | VERIFIED | Step 2J block at line 3473. Imports `fetch_issue_submissions` from `github_issues_reader`. Calls it with `conn`. Logs result or warning. Step 2K (enrichment) immediately follows at line 3488. |
| `public/index.html` | Clean external link button replacing old in-page form HTML | VERIFIED | Line 456-458: `missedProjectSection` div contains only an `<a>` anchor with correct GitHub Issues URL. No `mpSubmitBtn`, `mpProvince`, `mpSector`, or form inputs found. |
| `public/js/app.js` | GitHub Issues link functions replacing old submission banners | VERIFIED | Line 1127-1128: project card row builder outputs direct `<a>` anchor with correction template URL and encodeURIComponent project name. No `being migrated` text or `submitMissedProject`/`submitProjectCorrection` function definitions found. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `github_issues_reader.py` | `db.py:save_missed_project` | `save_missed_project()` call for each new issue | WIRED | Line 187: `save_missed_project(conn, project_dict)` in `_process_missing_project()`. Line 220: `save_missed_project(conn, project_dict)` in `_process_correction()`. |
| `update_dashboard.py` | `github_issues_reader.py` | import and call before missed_project_enrichment step | WIRED | Line 3475: `from github_issues_reader import fetch_issue_submissions`. Line 3476: `issues_result = fetch_issue_submissions(conn)`. Step 2K at line 3488 follows. |
| `public/index.html` | GitHub Issues new issue URL | anchor href in new tab | WIRED | Line 457: `href="https://github.com/waltaaaa/ai-newsletter/issues/new?template=missing-project.yml" target="_blank" rel="noopener"`. |
| `public/js/app.js` | GitHub Issues new issue URL | direct anchor with prefilled project name via query param | WIRED | Line 1128: `href="https://github.com/waltaaaa/ai-newsletter/issues/new?template=project-correction.yml&title=Correction:+'+encodeURIComponent(p.name||'')+'"`. |

---

## Requirements Coverage

| Requirement | Source Plan | REQUIREMENTS.md Wording | Implementation | Status |
|-------------|-------------|--------------------------|----------------|--------|
| SUB-01 | 17-02-PLAN.md | "Missing project form submits via Google Form instead of Firestore" | Form submits via GitHub Issues template (`missing-project.yml`). `index.html` has direct anchor link to GitHub Issues. | SATISFIED (implementation fulfills intent; REQUIREMENTS.md text is stale — references Google Form instead of GitHub Issues) |
| SUB-02 | 17-01-PLAN.md | "Pipeline reads Google Form submissions from connected Google Sheet" | Pipeline reads GitHub Issues API via `github_issues_reader.py` Step 2J. No Google Sheet involved. | SATISFIED (implementation fulfills intent; REQUIREMENTS.md text is stale — references Google Sheet) |
| SUB-03 | 17-02-PLAN.md | "Project correction form submits via Google Form" | Corrections submit via GitHub Issues template (`project-correction.yml`). `app.js` generates direct anchor links with project name prefilled. | SATISFIED (implementation fulfills intent; REQUIREMENTS.md text is stale — references Google Form) |

**Note on requirement wording:** All three requirements are satisfied by the GitHub Issues implementation, which achieves the same functional intent (no-Firestore user submission path that feeds the pipeline automatically). However, REQUIREMENTS.md still describes the abandoned Google Forms approach. This creates a documentation mismatch that should be corrected.

**Orphaned requirements:** None. All three SUB requirements assigned to Phase 17 are accounted for by the two plans.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `github_issues_reader.py` | 84, 100 | `return {}` | Info | Legitimate no-token early returns in `_github_post` and `_github_patch`. These are correct guards, not stubs — both functions are only called for issue closing, which is optional. |
| `github_issues_reader.py` | 125 | `return {}` | Info | Legitimate early return in `_parse_issue_body` when body is empty or None. Not a stub. |

No blockers or warnings found. All `return {}` instances are guarded no-token paths in optional-close helper functions.

---

## Human Verification Required

### 1. Missing Project Button Opens GitHub Issues Template

**Test:** Open the deployed dashboard (or `public/index.html` via local server). Navigate to the Projects tab. Locate the "Report a Missing Project" button and click it.
**Expected:** A new browser tab opens to `https://github.com/waltaaaa/ai-newsletter/issues/new?template=missing-project.yml` showing the structured GitHub Issues form with the fields: Project Name, Province/Territory, Sector, Estimated Value, Proponent/Developer, Description, Source URL.
**Why human:** Browser tab opening and GitHub template rendering cannot be verified by grep or static analysis.

### 2. Project Correction Link Opens with Prefilled Project Name

**Test:** On the Projects tab, expand any project row. Click the "Report correction" link.
**Expected:** A new browser tab opens to `https://github.com/waltaaaa/ai-newsletter/issues/new?template=project-correction.yml&title=Correction:+[PROJECT_NAME]` where `[PROJECT_NAME]` is the actual project name from the row. The GitHub Issues form shows the project-correction template fields.
**Why human:** `window.open` behavior and title prefill cannot be verified programmatically without running a browser.

---

## Gaps Summary

The implementation is functionally complete. `github_issues_reader.py`, the two issue templates, the pipeline Step 2J integration, and the frontend links are all present, substantive, and wired correctly. The URL hard gate is enforced. Error handling is in place. Processed issue tracking via `dashboard_state` prevents re-processing.

The single gap is a documentation mismatch: ROADMAP.md and REQUIREMENTS.md still describe the abandoned Google Forms/Sheets approach. The decision to pivot to GitHub Issues was documented in CONTEXT.md but was never backpropagated to ROADMAP.md (phase 17 goal, success criteria, plan names) or REQUIREMENTS.md (SUB-01/02/03 descriptions). This is a stale documentation gap, not a broken implementation.

The two human-verification items (browser-level link behavior) are standard frontend items that cannot be verified by static analysis.

---

_Verified: 2026-03-09T23:45:14Z_
_Verifier: Claude (gsd-verifier)_
