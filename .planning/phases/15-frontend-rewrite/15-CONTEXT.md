# Phase 15: Frontend Rewrite - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace all Firebase SDK usage in the frontend with fetch() calls to static JSON files produced by Phase 14's export_dashboard.py. Remove Firebase API key, Firebase Auth, and all Firestore imports. All existing UI features must continue to work identically. This phase does NOT add new UI features or change the visual design.

</domain>

<decisions>
## Implementation Decisions

### Data path & base URL
- Hardcoded relative path prefix `data/` for all fetch calls
- Works on GitHub Pages (docs/data/) and local dev (serve from docs/)
- No configuration object or auto-detect needed

### Province filter & file mapping
- Province dropdown values map to JSON filenames via slug lookup
- Display name to slug mapping table (e.g., 'British Columbia' -> 'british_columbia')
- Fetch pattern: `fetch('data/projects_${slug}.json')`

### All-provinces view
- Add `projects_all.json` to Phase 14 export (one fetch vs 13 parallel fetches)
- Single file for "All provinces" view, per-province files for filtered views

### Indicator history
- Load `indicators.json` once, filter client-side by indicator name
- Dataset is small enough (~2000 rows max) for in-memory filtering
- No need to split into per-indicator files

### User submission forms
- Keep "Missing Project" and "Project Correction" buttons visible
- Replace addDoc calls with a message: "Project submissions are being migrated. Check back soon!"
- Phase 17 will replace these with Google Form links

### Firebase Auth removal
- Remove all Firebase Auth imports and anonymous sign-in logic entirely
- Auth was only used for Firestore read permissions — static JSON needs no auth

### Caching strategy
- In-memory JS cache object for fetched JSON data
- Province data cached after first load, briefing cached, etc.
- Cleared on page refresh — no localStorage or sessionStorage needed

### Loading UX
- Per-section shimmer/skeleton animation while data loads
- Reuse existing `@keyframes shimmer` already in index.html CSS
- Sections load independently — one failing section doesn't block others

### Error handling
- Inline error message per section on fetch failure
- "Could not load data" with retry button in the section that failed
- Other sections continue working independently

### Pipeline status widgets
- Add `pipeline_status.json` to Phase 14 export (last run info, Tavily credits, recent runs)
- Data exists in SQLite pipeline_runs and tavily_credits — just needs export function

### Canadian commodities & policy developments
- Claude to investigate whether these collections have data in SQLite
- If populated: add commodities.json and policy.json to export
- If empty/unused: remove those frontend sections (dead code cleanup)

### Claude's Discretion
- Exact shimmer/skeleton CSS implementation
- fetchJSON wrapper function design
- Error retry logic details
- Order of migration (which Firestore queries to replace first)
- Whether to split app.js into multiple files during rewrite or keep single file

</decisions>

<specifics>
## Specific Ideas

- shimmer keyframe already exists in index.html CSS — reuse it for loading skeletons
- tsCache object pattern already used in app.js for timeseries — extend that pattern to all data
- Province slug generation must match Phase 14 export filenames exactly (lowercase, underscores)
- manifest.json from Phase 14 lists all available files — could validate against it on load

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `public/js/app.js` (1,602 lines): All frontend logic, 33 Firebase references to replace
- `public/index.html` (514 lines): HTML + CSS only, shimmer keyframe animation ready
- `docs/data/manifest.json`: Lists all 20 exported files with timestamp
- `tsCache` object (app.js): Existing in-memory cache pattern for timeseries data

### Established Patterns
- CSS variables system in index.html `:root` — consistent theming
- Tab-based navigation with `.tab-panel.active` pattern
- Card component pattern (`.card`, `.card-header`, `.card-body`)
- Indicator pill components for macro data display
- Chart.js for all indicator charts (imported via CDN)

### Integration Points
- `docs/data/` directory: 20 JSON files produced by Phase 14 export
- Province JSON filenames: `projects_{slug}.json` where slug = lowercase name with spaces as underscores
- Firebase imports on lines 1-5 of app.js: entry point for removal
- `addDoc` calls on lines 1026 and 1228: submission forms to disable
- Pipeline status queries on lines 1385-1457: need new export or removal

</code_context>

<deferred>
## Deferred Ideas

- Google Form integration for project submissions — Phase 17
- GitHub Pages deployment configuration — Phase 16
- Splitting app.js into multiple module files — evaluate during planning, but not a Phase 15 requirement

</deferred>

---

*Phase: 15-frontend-rewrite*
*Context gathered: 2026-03-08*
