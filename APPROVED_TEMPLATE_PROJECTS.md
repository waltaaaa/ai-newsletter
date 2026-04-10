# Approved Template — Projects Tab

**Approved:** 2026-04-10 (after PROJ-01 through PROJ-23)
**Status:** Locked. Design-theme pass, lazy loading, CMA filter, and table refinements complete.
**Purpose:** Source of truth for the Projects tab layout, data flow, and editorial rules. Use this file (instead of the full `APPROVED_TEMPLATES.md`) when resuming Projects work to keep context lean.

---

## Lock state (2026-04-10)

- **Data sources:**
  - `docs/data/projects_all.json` (6.0 MB, ~7,344 projects) — loaded only when user picks "All Provinces"
  - `docs/data/projects_{province}.json` — per-province chunks already exported by `tools/export_dashboard.py`. Used for specific-province lazy loads.
  - `config/cmas_full.json` — reference list of 40+ canonical Canadian CMAs (not loaded directly by frontend; CMA dropdown populates from whatever province is loaded)
- **Initial load on page render:** `projects_ontario.json` (~1.7 MB) — the largest province by project count. Dropdown UI syncs to "Ontario" so there's no phantom double-load.
- **Page sections:** 1 — a single Prussian blue hero card containing title, stats, and filter bar, followed by the collapsible missing-project form and the project table.
- **Renderer entry points:** `renderProjectsTab()` (~line 4852), `filterProjects()` (~line 4897), `populateCmaFilter()` (new), `renderProjectSummary()` (~line 4934), `renderProjectTable()` (~line 4953). All in `docs/js/app.js`.
- **Lazy loading:** per-province. Changing the province filter dispatches `loadProjects(prov)` which replaces `allProjects` with the smaller per-province file. CMA dropdown is repopulated from the new `allProjects` on every province change.
- **Removed on lock:** the standalone "Methodology" tab (removed from main nav before the Projects work started).

---

## Page structure (top → bottom)

1. **Prussian blue hero card** (`#projSummaryStats.proj-hero-stats`) — a single rounded container containing:
   - **Top row** (`.proj-hero-top`) — title on the left, 5 stat columns on the right
   - **Nested filter bar** (`.filter-bar#projectFilterBar`) — search + 4 selects + toggle pill + 2 buttons, on a subtle `rgba(255,255,255,0.15)` top border
2. **Missing Project Submission Form** (`#missedProjectSection`) — collapsible light panel that appears below the hero only when the "+ Report Missing" button in the filter bar is clicked
3. **Project table** (`.section-block > .project-table-wrap > .project-table`) — 9-column table with Prussian blue column-header row filling the rounded top corners

There is **no separate `.section-header` for "Project Pipeline"** — the column-header row itself serves as the visual top of the pipeline section.

---

## 1. Hero card

**Container:** `.proj-hero-stats` — Prussian blue `#003153`, 8px full border-radius, `overflow: hidden`, flex column, `margin: 0 0 24px`.

**CSS entry points:** `#tab-projects .proj-hero-stats` + descendant selectors in `docs/index.html` (inserted immediately after the `#tab-markets` CSS block).

### Top row (`.proj-hero-top`)
- `display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 24px; padding: 28px 32px 22px`
- **Left** — `.proj-hero-title` (flex-shrink: 0):
  - `<h2>Capital Projects Tracker</h2>` — 28px/700 DM Sans, `#ffffff`
  - `.proj-hero-sub` — 14px, `rgba(255,255,255,0.7)`, "Major capital projects across Canada"
- **Right** — `.proj-hero-stats-right#projHeroStats` (flex: 1, display: flex, justify-content: space-around, align-items: flex-end, gap: 16px, padding-left: 48px, flex-wrap: wrap):
  - 5 `.stat-item` columns — each with `.stat-value` (22px/700 DM Sans, tabular-nums, `#ffffff`) and `.stat-label` (10px uppercase, `rgba(255,255,255,0.6)`, letter-spacing 0.4px)
  - Stats are the only DOM rendered by JS; the rest of the hero is static HTML

### Stats list (5 — locked)
| # | Label | Source | Notes |
|---|---|---|---|
| 1 | Total Projects | `filteredProjects.length` | comma-formatted via `.toLocaleString()` |
| 2 | Total Value | `sum(parseNumericValue(p.value))` → `fv()` helper | `fv()` uses `toLocaleString('en-CA',{minimumFractionDigits:1,maximumFractionDigits:1})` for billions so `$1,234.5B` renders with comma |
| 3 | Under Construction | status includes "construction" | comma-formatted |
| 4 | Approved | status includes "approved" but not "construction" | comma-formatted |
| 5 | New This Week | `p.firstTracked >= (today - 7d)` | comma-formatted |

**Not included (removed during lock-in):** Provinces count, verify-banner ("X% have source links").

### Nested filter bar (`.filter-bar`)
- `padding: 14px 32px; margin: 0; border-top: 1px solid rgba(255,255,255,0.15); align-items: center`
- Inputs/selects override: white background (`#ffffff`), Prussian blue text, `rgba(255,255,255,0.25)` border
- All `select` elements capped at `max-width: 180px` with `text-overflow: ellipsis; overflow: hidden` — prevents long CMA names from bloating dropdown width

### Filter controls (in order)
1. **Search input** (`#projectSearch`) — text, searches name / cma / proponent
2. **Province dropdown** (`#filterProvince`) — default "Ontario"; "All Provinces" option triggers the 6 MB load; other provinces trigger per-province lazy load
3. **CMA dropdown** (`#filterCma`) — dynamically populated from unique CMAs in `allProjects` after every `loadProjects()`; preserves selection if still valid
4. **Sector dropdown** (`#filterSector`) — populated from `NAICS_CODES` + `NAICS_NAMES`
5. **Status dropdown** (`#filterStatus`) — populated from `STATUSES` array
6. **Sort dropdown** (`#sortProjects`) — Value desc, Recently Updated, Name A-Z, Confidence
7. **"Above Threshold" toggle pill** (`.toggle-label`) — bordered translucent white pill, 7px 12px padding, 6px radius, white text + border. Toggle track switches track white / thumb Prussian blue when checked (default ON).
8. **Export CSV button** — white bg, Prussian blue text, 8px 12px padding, `var(--text-sm)` font (matches inputs)
9. **"+ Report Missing" button** (`#toggleMissedForm`) — same style as Export CSV, toggles the collapsible form below the hero

---

## 2. Missing Project Submission Form

- Collapsible light panel (`#missedProjectForm`) that renders below the hero
- Hidden by default (`display: none`)
- Toggled by the "+ Report Missing" button in the filter bar
- Contains 9 fields in a 2-column grid: Project Name, Province, City, Sector, Estimated Value, Proponent, Type, Status, Source URL, Description, Notes
- **Inline styles preserved on the form fields** — deliberately not cleaned up during the design-theme pass. Future refactor can extract them to a `#tab-projects .mp-form` CSS block.
- `submitMissedProject()` handler currently shows a "being migrated" feedback message; full submission pipeline deferred.

---

## 3. Project table

**Wrapper:** `.project-table-wrap` — `width: 100%; overflow: hidden; border-radius: 8px; background: #ffffff; border: 1px solid #d5dbe3; box-shadow: var(--shadow-sm)`. The `overflow: hidden` clips the Prussian blue `<thead>` background to the rounded top corners.

**Table:** `.project-table` — `border-collapse: collapse; table-layout: fixed; font-size: var(--text-sm)`.

### Column layout (9 columns)
| # | Header | Class | Width | Notes |
|---|---|---|---|---|
| 1 | Value | `col-value` | 90px | `fmtCurrency(p.value,p)` + optional `unconfirmed` badge |
| 2 | Project | `col-name` | 22% | Name truncated to 50 chars |
| 3 | Type | — | auto | `typeBadge(p.project_type\|\|'greenfield')` |
| 4 | Province | `col-province` | 50px | `normProvince(p.province)` + extra-provinces count |
| 5 | Proponent | `col-proponent` | 12% | Raw `p.proponent` |
| 6 | Status | — | auto | `statusBadge(p.status\|\|'Proposed')` |
| 7 | Sector | — | auto | `NAICS_NAMES[p.naics_code]` or normalized sector |
| 8 | Updated | `col-updated` | 70px | `relDate(p.lastSeen\|\|p.updated_at)` |
| 9 | Source | `col-source` | 75px | `srcLink(firstEv.url, firstEv.name)` — pulls from `p.evidence[0]` (NOT `p.sources`, which is empty on most rows) |

### Header styling (`.project-table thead th`)
- Background: `#003153` (Prussian blue) — fills the wrap's rounded top corners via `overflow: hidden`
- Font: 11px DM Sans, 600, uppercase, `letter-spacing: 0.3px`, color `#ffffff`
- Padding: `12px 10px 12px 18px` (18px left)
- Right border: `1px solid rgba(255,255,255,0.15)` — visible column dividers on the dark bg
- `:last-child` override removes the right border (no double-edge at the rounded corner)
- **No `position: sticky`** — removed because `overflow: hidden` on the wrap would break sticky clipping. Headers scroll with the table.

### Body row styling (`.project-table tbody tr` / `td`)
- Row background: `#ffffff` alternating with `#f9fafb` (zebra)
- Hover: `#e8eef4` (light Prussian blue tint)
- Row border-bottom: `1px solid #e8ecf0`
- Cell padding: `12px 10px 12px 18px` (18px left matches header)
- Column right border: `1px solid #e8ecf0` with `:last-child` override
- Vertical align: middle; overflow: hidden; text-overflow: ellipsis; white-space: nowrap

### Source column — data derivation (critical)
```js
const firstEv = (p.evidence || [])[0] || {};
const srcDead = firstEv.url_dead || false;
const srcUrl = srcDead ? '' : (firstEv.url || '');
const srcTitle = firstEv.name || firstEv.source_type || 'Source';
```
- **Do NOT read from `p.sources[0]`** — that array is empty on most projects (confirmed by inspecting `projects_ontario.json`). Evidence URLs live in `p.evidence[]`.
- Rendered via `srcLink(url, title)` which returns `<a href="..." target="_blank">↗</a>` or empty string if no URL.

### Expansion row
- Click any row to expand via `toggleProjectRow(rowId)` — reveals a detail panel with the full description, timeline, evidence list
- **Untouched during lock-in** — retains existing `.project-expand` styling

---

## 4. Data flow & lazy loading

### Initial load sequence (`renderProjectsTab()`)
1. Populate province / sector / status dropdowns **first** (before data load)
2. Read current `provSel.value` → if empty, default to `'ON'` (Ontario)
3. **`provSel.value = initProv`** — sync the UI to the chosen province BEFORE calling `loadProjects`, so `filterProjects()` doesn't detect a mismatch and trigger a phantom reload
4. `await loadProjects(initProv)` — loads `projects_ontario.json` (~1.7 MB)
5. `populateCmaFilter()` — build the CMA dropdown from the loaded province's unique CMAs
6. Wire up filter change listeners
7. Call `filterProjects()` for the first render

### On province change (`filterProjects()`)
1. Read current `prov` from dropdown
2. If `prov !== _lastLoadedProvince`:
   - `await loadProjects(prov)` — replace `allProjects` with new province's data
   - `populateCmaFilter()` — refresh CMA dropdown with new province's CMAs
   - Recurse into `filterProjects()`
3. Otherwise, filter in-memory and re-render

### `populateCmaFilter()` behavior
- Clears all options except `<option value="">All CMAs</option>`
- Computes unique CMAs from `allProjects.map(p => p.cma)`, filters blanks, sorts alphabetically
- Preserves current selection if still valid after repopulation

### Removed background fetches (PROJ-16)
- **Removed:** the async `fetch('./data/projects_all.json')` that was running after dropdown population just to compute per-province project counts for dropdown labels. Eliminated the hidden 6 MB load on every render. Province counts in dropdown labels are gone.

---

## 5. Editorial / data integrity rules

- **URL hard gate** (from CLAUDE.md) — every project must have at least one verifiable source URL. Rendered from `p.evidence[0].url`.
- **Above Threshold toggle** — ON by default. Filters to projects with `p.value >= PROV_THRESHOLDS[p.province]` (Ontario $500M, Quebec $250M, etc.). Users can toggle off to see all projects.
- **No editorializing in the rendered UI** — stat labels and button text are factual. Callouts, narrative, and status badges are data-driven (no hand-written editorial).
- **Status colors** — existing `.status-badge` / `.st-*` classes preserved; not touched during this lock-in.
- **CMA values** — pulled as-is from `p.cma` field. Canonical list in `config/cmas_full.json` but frontend does not validate against it; trusts whatever the pipeline writes.

---

## 6. Approved design vocabulary reused from other tabs

- `#003153` Prussian blue — hero background, table header background, accent color
- `#e8ecf0` light gray — row borders, column separators, divider lines
- `#d5dbe3` medium gray — table wrap border
- DM Sans typography — all headings and labels
- `var(--text-sm)` / `var(--text-xs)` — consistent sizing with other filter bars
- `.stat-value` / `.stat-label` — hero stat formatting modeled on `.province-header-stats` (Provinces tab lines 732–734)
- Rounded corners — 8px radius on both hero card and table wrap, matching the approved-tab pattern

**Not promoted to global classes** — all new rules scoped to `#tab-projects` to match the existing tab-scoped CSS pattern (Provinces, National, Industries, Markets all have their own scoped copies of identical base rules).

---

## 7. Files of record

- `docs/index.html` — all CSS additions (`#tab-projects` block) and HTML structure (hero + filter bar + missing form + table wrapper)
- `public/index.html` — byte-identical mirror of docs/index.html for the Projects region (source of truth synced by `tools/deploy_to_github.py`)
- `docs/js/app.js` — `renderProjectsTab()`, `filterProjects()`, `populateCmaFilter()`, `renderProjectSummary()`, `renderProjectTable()`, `loadProjects()` (unchanged signature, just called with different province values)
- `docs/data/projects_all.json` — 6 MB full dataset; loaded only when user picks "All Provinces"
- `docs/data/projects_{province}.json` — 13 per-province chunks (Ontario 1.7 MB down to Nunavut 40 KB); loaded on province filter change
- `tools/export_dashboard.py` — unchanged; already exports per-province chunks

---

## 8. Known gaps / deferred

- **Inline-style cleanup on the missing-project form** — still uses `style="..."` attrs on 9 input fields. Deferred as explicit scope decision during the design-theme pass (user chose "visual alignment only").
- **Sticky thead** — removed during PROJ-20 because `overflow: hidden` on the wrapper breaks sticky clipping. If sticky headers are wanted, the wrap needs a nested scroll container.
- **Province counts in dropdown labels** — removed with the 6 MB fetch. Future: export a tiny `projects_counts.json` (province → count) and load it on dropdown populate to restore the "(N)" labels without the 6 MB cost.
- **`p.sources[]` array** — empty on all inspected projects. The pipeline writes evidence to `p.evidence[]` instead. Consider removing the unused `sources` field from the project schema in a future backend cleanup.
- **CMA dropdown scope** — currently only shows CMAs for the loaded province. When "All Provinces" is selected, it shows CMAs from the full 6 MB dataset. No cross-province CMA browsing without loading the full file.
- **Pagination UI** — still uses `PAGE_SIZE` and `projectPage` with a "Load more projects" button. No virtual scrolling. Table can grow large on dense provinces.
- **"Results summary" text** — `#projectResultsSummary` element still in the DOM and still written to by `renderProjectTable()`, now visible as loose text above the table wrap. Low priority cleanup.

---

## 9. Locked patch set

All 23 patches — **PROJ-01 through PROJ-23** — documented in `PATCH_LOG.md` under the "Projects Tab" section. See that file for the full change log including root causes, file diffs, and byte-identical preservation notes.
