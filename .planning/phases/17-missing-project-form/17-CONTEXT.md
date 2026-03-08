# Phase 17: Missing Project Form - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can submit missing projects and corrections via Google Forms. The pipeline reads those submissions automatically from a connected Google Sheet and creates/updates projects in SQLite. No Firestore dependency for user submissions.

Replaces the amber "being migrated" banners added in Phase 15 with working Google Form links.

</domain>

<decisions>
## Implementation Decisions

### Form field design
- Missing Project form: moderate fields — Name, Province (dropdown), Sector (dropdown matching 18 NAICS codes), Estimated value (optional), Proponent (optional), Description, Source URL (required)
- Source URL is required on the form — matches the project URL hard gate (no URL = no project)
- Project Correction form: separate Google Form with project name, field to correct, new value, source URL, notes
- Two separate forms, feeding into one Google Sheet with separate tabs (or two sheets)
- Optional email field — not required, for submitters who want follow-up
- Forms created manually by user; phase delivers setup documentation with exact field names and Sheet column mappings

### Pipeline ingestion behavior
- Auto-create projects from submissions — pipeline reads Sheet, runs enrichment via existing missed_project_enrichment.py, creates project in SQLite if URL hard gate passes
- Duplicate handling: merge evidence — if submitted project matches existing one (name + province fuzzy match), add submission URL to evidence array; status never regresses; follows existing dedup rules
- Row tracking: track processed rows in SQLite only — store processed row numbers/timestamps in dashboard_state; Sheet stays read-only (simpler auth)
- Corrections: log as pending correction in missed_projects table with type='correction'; enrichment step reviews and applies if source URL confirms the change
- Failure mode: log warning and continue pipeline if Google Sheet is unreachable; submissions picked up on next successful run

### Frontend submission UX
- "Missing Project" button: direct link opening Google Form in new tab; replaces current amber migration banner
- Project Correction link: on each project card as a small "Report correction" link; Google Form URL includes project name as prefilled parameter
- No submission tracking on dashboard — dashboard is read-only; users see their project appear in Projects tab when pipeline processes it
- Remove existing in-page form HTML entirely — delete the old form fields, dropdowns, and submitMissedProject()/submitProjectCorrection() JS functions; replace with clean external links

### Google API authentication
- API key (read-only) for Google Sheets API v4 — publish Sheet as "Anyone with link can view"
- Credentials stored in .env + GitHub Actions secrets: GOOGLE_SHEET_ID and GOOGLE_SHEETS_API_KEY; matches existing pattern for other API keys
- Sheet ID could be hardcoded since it's not sensitive (public-readable sheet), but .env is cleaner for consistency
- No service account needed — read-only access sufficient since row tracking is in SQLite

### Claude's Discretion
- Exact Google Sheets API v4 query implementation
- How to structure the Sheet reader module (new file vs extension of existing)
- Fuzzy matching algorithm for duplicate detection against existing projects
- How to prefill Google Form fields from project card links (URL parameters)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `db.py:save_missed_project()` — existing function to insert into missed_projects table; accepts project_dict with name, province, description, source_url, submitted_at, data fields
- `missed_project_enrichment.py:process_missed_projects()` — existing pipeline step that reads pending submissions from missed_projects table and processes them through enrichment
- `db.py:upsert_project()` — handles evidence merge, status non-regression, confidence scoring; already implements all dedup business rules
- `learning_store.py:diagnose_missed_project()` — existing diagnostic for missed projects

### Established Patterns
- `.env` file for API keys — ANTHROPIC_API_KEY, TAVILY_API_KEY, GEMINI_API_KEY already stored there
- GitHub Actions workflows reference secrets for API keys (GEMINI_SEARCH_ENABLED=false pattern)
- Pipeline steps log warnings and continue on non-critical failures (GDELT bail-out pattern)
- JSON string serialization for SQLite array fields — json.loads()/json.dumps() pattern from Phase 13

### Integration Points
- `update_dashboard.py` — main pipeline entry point; Google Sheet reading step should be added as a new step before missed_project_enrichment
- `public/js/app.js` lines 997-1005 — submitMissedProject() amber banner to replace
- `public/js/app.js` line 1179 — submitProjectCorrection() amber banner to replace
- `public/index.html` — contains the Missing Project form HTML elements to remove
- GitHub Actions workflows — need GOOGLE_SHEETS_API_KEY and GOOGLE_SHEET_ID as repository secrets
- `export_dashboard.py` — no changes needed; processed submissions become regular projects

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key principle is simplicity: Google Forms handles the UI, Google Sheets provides the data store, and the pipeline just reads a spreadsheet.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-missing-project-form*
*Context gathered: 2026-03-08*
