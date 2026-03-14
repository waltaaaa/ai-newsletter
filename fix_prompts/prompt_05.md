I need you to clean up non-functional discovery tiers. Read each file before making changes.

## 1. GDELT (Tier 3) — dead code

File: `gdelt_monitor.py` exists but is never imported or called in `update_dashboard.py`.

Action: 
- Move `gdelt_monitor.py` to a new directory `archive/` (create it if needed)
- Search all .py files for any import of `gdelt_monitor` and remove them
- In `pipeline_config.py`, if there are any GDELT-related config entries, comment them out with a note: "# GDELT disabled — module never integrated into pipeline"

## 2. SEDAR+ (Tier 6) — stub that scrapes a login page

The SEDAR+ scraper attempts Tavily extraction of a generic login portal URL and always returns 0 results.

Action:
- Find the SEDAR+ code (likely in `update_dashboard.py` or a dedicated file) 
- Comment out the tier with a clear note: "# SEDAR+ disabled — scraper targets login portal, returns 0 results. Needs endpoint audit."
- Do NOT delete the code — just disable it so it can be fixed later

## 3. Google Alerts (Tier 12) — never configured

File: `rss_feeds.json`

All 31 Google Alert feeds have `"url": "PASTE_FEED_URL_HERE"` and `"enabled": false`.

Action:
- In the RSS monitor code, add an early check: if a feed URL contains "PASTE_FEED_URL_HERE" or is obviously a placeholder, skip it and log a warning
- In the tier execution code, if all feeds for the tier are placeholders, log: "[Tier 12] Skipped — no Google Alert feeds configured"

## 4. Municipal Dev Apps (Tier 11) — 17/17 failing

All 17 municipal HTML scrapers fail (HTTP 400, 403, 404). Only the 4 Socrata API cities have any chance of working.

Action:
- In `municipal_dev_apps.py`, add a per-city health check: attempt a HEAD request with 5-second timeout before running the full scraper
- If the health check fails, skip that city and log: "[Municipal] {city} skipped — endpoint unreachable"
- Add a tier-level check: if all cities fail the health check, skip the tier entirely

## 5. Update documentation

After making the above changes, update `ARCHITECTURE.md`:
- Change the tier count from 14 to reflect reality. Note which tiers are disabled and why
- In the "14-Tier Discovery Pipeline" section, add status annotations:
  - Tier 3: `(disabled — not integrated)`
  - Tier 6: `(disabled — endpoint audit needed)`
  - Tier 12: `(disabled — not configured)`
  - Tier 11: `(degraded — most endpoints broken)`

Do NOT renumber the tiers — keep the numbering stable for reference.
