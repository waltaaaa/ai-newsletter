# Phase 17: Missing Project Form - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can submit missing projects and corrections via GitHub Issues (structured issue templates). The pipeline reads those submissions automatically from the GitHub Issues API and creates/updates projects in SQLite. No Firestore dependency, no new services — uses existing GitHub infrastructure.

Replaces the amber "being migrated" banners added in Phase 15 with working GitHub Issues links.

</domain>

<decisions>
## Implementation Decisions

### Submission method (CHANGED: GitHub Issues replaces Google Forms)
- GitHub Issues with structured YAML form templates — no new services, no API keys for reads (public repo)
- Missing Project template: Name, Province (dropdown), Sector (dropdown matching 18 NAICS codes), Estimated value (optional), Proponent (optional), Description, Source URL (required)
- Source URL is required on the form — matches the project URL hard gate (no URL = no project)
- Project Correction template: project name, field to correct, new value, source URL, notes
- Two separate issue templates, labeled `missing-project` and `project-correction`
- Pipeline auto-closes processed issues with a thank-you comment (when GITHUB_TOKEN available)

### Pipeline ingestion behavior
- Auto-create projects from submissions — pipeline reads GitHub Issues API, runs enrichment via existing missed_project_enrichment.py, creates project in SQLite if URL hard gate passes
- Duplicate handling: merge evidence — if submitted project matches existing one (name + province fuzzy match), add submission URL to evidence array; status never regresses; follows existing dedup rules
- Issue tracking: track processed issue numbers in SQLite dashboard_state (monotonically increasing); no write access to issues needed for tracking
- Corrections: log as pending correction in missed_projects table with type='correction'; enrichment step reviews and applies if source URL confirms the change
- Failure mode: log warning and continue pipeline if GitHub API is unreachable; submissions picked up on next successful run

### Frontend submission UX
- "Missing Project" button: direct link opening GitHub issue template in new tab; replaces current amber migration banner
- Project Correction link: on each project card as a small "Report correction" link; GitHub issue URL includes project name in title
- No submission tracking on dashboard — dashboard is read-only; users see their project appear in Projects tab when pipeline processes it
- Remove existing in-page form HTML entirely — delete the old form fields, dropdowns, and submitMissedProject()/submitProjectCorrection() JS functions; replace with clean external links

### Authentication
- No auth needed for reading issues from public repo (GitHub REST API allows unauthenticated reads)
- GITHUB_TOKEN (already available in GitHub Actions) used for closing issues after processing
- No new env vars or secrets needed — zero configuration

### Claude's Discretion
- Exact GitHub Issues API query implementation
- How to structure the Issues reader module (new file vs extension of existing)
- Fuzzy matching algorithm for duplicate detection against existing projects
- Issue body parsing approach for structured template responses

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
