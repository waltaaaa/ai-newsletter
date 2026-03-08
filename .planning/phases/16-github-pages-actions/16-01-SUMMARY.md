---
phase: 16-github-pages-actions
plan: "01"
subsystem: deployment
tags: [github-pages, github-actions, deploy, firebase-archive, ci-cd]
dependency_graph:
  requires: []
  provides: [deploy_to_github.py, weekly-pipeline.yml, daily-indicators.yml, archive/firebase/]
  affects: [docs/, .github/workflows/]
tech_stack:
  added: [GitHub Actions, GitHub Pages]
  patterns: [cron-workflow, static-deploy, firebase-archive]
key_files:
  created:
    - deploy_to_github.py
    - .github/workflows/weekly-pipeline.yml
    - .github/workflows/daily-indicators.yml
    - archive/firebase/firebase.json
    - archive/firebase/firestore.rules
    - archive/firebase/firestore.indexes.json
    - archive/firebase/.firebaserc
    - archive/firebase/functions/index.js
    - archive/firebase/functions/package.json
    - archive/firebase/README.md
    - docs/index.html
    - docs/404.html
    - docs/js/app.js
  modified:
    - .gitignore
decisions:
  - "deploy_to_github.py uses shutil.copytree(dirs_exist_ok=True) for js/ and shutil.copy2 for individual HTML files — idempotent, never touches docs/data/"
  - "Weekly cron set to 10:30 UTC (not 10:30 EST) so it covers both EST/EDT year-round at approximately 5:30 AM ET winter"
  - "Both workflows set GEMINI_SEARCH_ENABLED=false to prevent accidental grounded search cost"
  - "Firebase configs moved (not copied) to archive/firebase/ — original locations are empty, functions/ directory removed"
metrics:
  duration_minutes: 6
  completed_date: "2026-03-08"
  tasks_completed: 3
  files_created: 13
  files_modified: 1
---

# Phase 16 Plan 01: Deployment Infrastructure Summary

**One-liner:** GitHub Actions weekly/daily cron workflows and deploy_to_github.py script that copies public/ assets to docs/ for GitHub Pages, with all Firebase configs archived to archive/firebase/.

## What Was Built

### deploy_to_github.py
A Python deployment script that:
- Copies `public/index.html` to `docs/index.html`
- Copies `public/404.html` to `docs/404.html`
- Copies `public/js/` to `docs/js/` using `shutil.copytree(dirs_exist_ok=True)`
- Does NOT touch `docs/data/` (that directory is managed by `export_dashboard.py`)
- Is fully idempotent — safe to run repeatedly
- Has a `__main__` guard for standalone or imported use

### .github/workflows/weekly-pipeline.yml
- Cron: `30 10 * * 1` (Monday 10:30 UTC = approximately 5:30 AM ET)
- Manual trigger: `workflow_dispatch`
- Runs `python update_dashboard.py` with API secrets
- Then runs `python deploy_to_github.py`
- Commits and pushes docs/ with github-actions bot identity
- Handles "nothing to commit" gracefully via `git diff --staged --quiet || ...`

### .github/workflows/daily-indicators.yml
- Cron: `0 5 * * *` (5:00 UTC = midnight ET)
- Manual trigger: `workflow_dispatch`
- Runs `python update_dashboard.py --indicators-only`
- Same deploy and commit pattern as weekly

### Firebase Archive
All Firebase configuration moved to `archive/firebase/`:
- `firebase.json`, `firestore.rules`, `firestore.indexes.json`, `.firebaserc`
- `functions/index.js`, `functions/package.json`
- `README.md` explaining the Phase 16 migration
- Original `functions/` directory removed

### .gitignore Updates
Added entries:
- `__pycache__/`, `*.pyc` — Python cache
- `*.db` — SQLite databases (dashboard.db, pipeline cache)
- `serviceAccountKey.json` — Google service account credentials
- `.cache/` — local pipeline cache directory

## Verification Results

All success criteria met:
- `deploy_to_github.py` runs without errors, populates `docs/` correctly
- `deploy_to_github.py` is idempotent (confirmed by running twice)
- Weekly workflow cron: `"30 10 * * 1"` (Monday 5:30 AM ET / 10:30 UTC)
- Daily workflow cron: `"0 5 * * *"` (midnight ET / 5:00 UTC)
- Both workflows reference secrets: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`
- `GEMINI_SEARCH_ENABLED=false` set in both workflows (cost protection)
- All Firebase configs archived to `archive/firebase/`
- `firebase.json`, `firestore.rules`, `firestore.indexes.json`, `.firebaserc`, `functions/` all removed from project root
- `docs/` contains: `index.html`, `404.html`, `js/app.js`, `data/` (pre-existing)

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 9a4783b | feat(16-01): create deploy_to_github.py and GitHub Actions workflows |
| 2 | 663a74a | chore(16-01): archive Firebase configuration files to archive/firebase/ |
| 3 | — | Verification only, no new files |

## Self-Check: PASSED

All files found on disk. All commits verified in git log.
