I need you to fix 4 critical data integrity bugs. Read the relevant files before making changes.

## Fix 1: dashboard.db not committed by CI

Files: `.github/workflows/weekly-pipeline.yml`, `.github/workflows/daily-indicators.yml`

Both workflows only run `git add docs/`. The updated dashboard.db (with new projects, indicator history, timeseries, briefings) is never committed. On the next CI run, the pipeline starts from the stale committed database — all accumulated data is lost.

Fix: In both workflow files, after the `git add docs/` line, add:
- `git add dashboard.db` (or use Git LFS if the file exceeds 100MB)
- Before the git add, run `python -c "import sqlite3; c=sqlite3.connect('dashboard.db'); c.execute('VACUUM'); c.close()"` to compact the DB

Also add `dashboard.db` to the git commit command if it's not already included.

## Fix 2: RSS filter never applied (inverted conditional)

File: `update_dashboard.py` around line 3253-3257

The conditional `rss_filtered = rss_monitor.fetch_and_filter(...) if not rss_items else rss_items` is inverted. Since `rss_items` is always populated at line ~3138, the `fetch_and_filter()` path (which applies the 6-layer relevance filter) is NEVER executed. Raw unfiltered RSS articles go straight to Claude analysis.

Fix: Invert the condition so the filter is always applied when rss_items exist. The correct logic should be: if we have rss_items, run them through the filter; if we don't, fetch and filter fresh.

## Fix 3: BoC rate hardcoded fallback

File: `update_dashboard.py` around line 332

If the BoC Valet API fails, the function silently returns a hardcoded rate of `2.75%` instead of `None`. Every other indicator returns `None` on failure. This means the dashboard displays stale fake data with no indication of failure.

Fix: Change the fallback to return `None` instead of the hardcoded value. Let the frontend display "N/A" like all other indicators.

## Fix 4: Empty Claude payload publishes without error

File: `update_dashboard.py` around line 2086 and 3262

If all 4 Claude API calls fail, `generate_claude_analysis()` returns `{}`. This empty dict propagates through the pipeline and the dashboard is published with no executive summary, no provincial analysis, no industry analysis — and the pipeline reports success.

Fix: After `generate_claude_analysis()` returns, check if the result is empty or missing critical keys (like 'overview', 'provinces', 'industries'). If so, log a CRITICAL error and either:
- Abort the run and set status to "failed"
- Or set a flag like `ANALYSIS_INCOMPLETE = True` that gets written to `pipeline_status.json` so the frontend can display a warning

Do NOT silently publish an empty dashboard.
