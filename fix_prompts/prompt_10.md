I need you to fix frontend and deployment issues, and update the architecture documentation to reflect all changes made in Prompts 1-9.

## Fix 1: Missing JSON exports

Files: `export_dashboard.py`, `public/js/app.js`

The frontend references `policy.json` (line ~1491) and `commodities.json` (line ~1512) but `export_dashboard.py` never creates these files.

Fix: Either:
a) Add export functions for these files in `export_dashboard.py` — pull policy data from `provincial_policy_monitor.py` output and commodity data from the market/timeseries tables
OR
b) If the data isn't available, remove the frontend references and any UI elements that depend on these files. Add a comment noting these are planned future features.

Choose option (a) if the data exists in the DB. Choose option (b) if it doesn't.

## Fix 2: Deploy script too narrow

File: `deploy_to_github.py`

Currently only copies `index.html`, `404.html`, and `js/` from `public/` to `docs/`. Any future `css/`, `img/`, or `assets/` directories would be silently skipped.

Fix: Change the copy logic to sync the entire `public/` directory to `docs/`, excluding any hidden files or `node_modules`. Use `shutil.copytree` with an ignore pattern, or a simple recursive copy.

## Fix 3: Briefing export not in CI

File: `.github/workflows/weekly-pipeline.yml`

`briefing_export.py` generates PDF and DOCX files but is never called by the CI workflow. The frontend's download buttons have no files to point to.

Fix: Add a step in the weekly workflow after the pipeline completes:
```yaml
- name: Generate briefing exports
  run: python briefing_export.py
  continue-on-error: true
```

Make sure the output PDF/DOCX files are saved to `docs/data/` (or wherever the frontend expects them) and included in the git commit.

## Fix 4: No meta tags for SEO/sharing

File: `public/index.html`

Add basic meta tags:
```html
<meta name="description" content="Signal Dispatch — Weekly Canadian economic intelligence dashboard">
<meta property="og:title" content="Signal Dispatch">
<meta property="og:description" content="Weekly Canadian economic intelligence">
<meta property="og:type" content="website">
```

## Fix 5: Weekly briefing prompt editorializing

File: `weekly_briefing.py`

The system prompt says "Forward-looking (what does this week's data mean for next quarter?)" and "actionable insight" — both conflict with your editorial policy of no predictions/recommendations.

Fix: Replace with: "Analytical (what does this week's data tell us about current conditions?)" and "contextual insight" — factual framing instead of predictive.

## Fix 6: Update ARCHITECTURE.md

This is the final step. Update `ARCHITECTURE.md` to reflect all changes made across Prompts 1-9:

1. Update the high-level diagram to show the phase-based architecture
2. Replace the step numbering with the new phase structure:
   - Phase 1: Data Collection
   - Phase 2: Discovery
   - Phase 3: Filtering & Dedup
   - Phase 4: Signals (permits, lobbyists)
   - Phase 5: AI Analysis (Claude calls + hard data override)
   - Phase 6: Reasoning (gap analysis, dedup QA, meta-analysis)
   - Phase 7: Narrative (trends, commentary, briefing)
   - Phase 8: Verification & Quality
   - Phase 9: Finalize, Export & Deploy
3. Update the AI Model Stack table — add local LLM (Qwen 2.5 3B) row, note that Gemini is now fallback-only
4. Update the discovery tier list with status annotations for disabled tiers
5. Update the Repository Layout to show the new `phases/` directory and `archive/` directory
6. Remove archived files from the file index
7. Update the file count to reflect consolidations
8. Update the Database Schema section to include the new `claude_checkpoints` table
9. Add a new "Circuit Breaker" section under Error Handling Patterns explaining ServiceHealth
10. Update the Dependencies section to include `llama-cpp-python`

Keep the document accurate to what the code now actually does — not aspirational.
