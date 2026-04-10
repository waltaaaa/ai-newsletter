# Approved Template — Data Explorer Tab

**Approved:** 2026-04-10 (after EXP-01 through EXP-13)
**Status:** Locked. Design-theme pass, Prussian blue hero with 4 stats, scoped section rhythm across 6 sub-sections, reskinned charts/callouts/stat-card grids, paginated 5-column V-code table, full inline-style cleanup, and new `export_statcan_tables()` pipeline function complete.
**Purpose:** Source of truth for the Data Explorer tab layout, data flow, and editorial rules. Use this file (instead of the full `APPROVED_TEMPLATES.md`) when resuming Data Explorer work to keep context lean.

---

## Lock state (2026-04-10)

- **Data sources** (loaded independently by renderer helpers):
  1. **`docs/data/indicators.json`** — full indicator corpus. 713 `indicators[]` rows, 45,488 `history[]` rows (5-year window), `statcan_latest{updatedAt, indicators[]}` (71 StatCan feed indicators), `validation{failed_count, failed_indicators[]}`. Populated on app bootstrap via `loadIndicators()` and cached at module level as `_indJsonCache`. Written by `export_indicators()` in `tools/export_dashboard.py:617` on each pipeline run.
  2. **`docs/data/statcan_tables.json`** — **NEW this session.** 4,908-row StatCan table directory that powers the V-code search fallback beyond the hand-curated `VCODE_INDEX`. Bare top-level array of `{t, n, k, c, f, g}` objects (table ID / name / keyword blob / category / frequency / geography). Loaded lazily by the async IIFE at `docs/js/app.js:5625`. Written by the new `export_statcan_tables()` function in `tools/export_dashboard.py:1275`, canonical source `config/statcan_table_registry.csv`.
  3. **`VCODE_INDEX`** — 125-entry hand-curated V-code list at `docs/js/app.js:5465`. Compiled into the JS bundle, not a data file.
- **Merge rule:** the async loader builds `_fullTableDir` by filtering `statcan_tables.json` rows whose `t` is already present in `VCODE_INDEX` (prevents double-counting). Curated entries and directory entries are concatenated at search time with curated entries receiving a +5 score boost so they rank above directory matches.
- **Renderer entry points:** `renderExplorer()` (`docs/js/app.js:5778`), `_expRenderHeroStats()` (`~5738`), `renderIndicatorExplorer()` (`~2645`), `_renderProvExplorer()` (`~5861`), `_renderOeaSection()` (`~5940`), `_renderOeaLatestTable()` (`~5983`), `_renderIsqSection()` (`~6035`), `_renderIsqLatestTable()` (`~6087`), `window._doVcodeSearch()` (`~6141`), `_expRenderVcodeResults()` (`~6155`), `window._expGoPage()` (`~6197`). Module state: `_fullTableDir`, `_fullDirLoaded`, `_expSearchPage`, `_expLastQuery`, `_provExpSel/_provExpProv/_provExpRange/_provExpData`, `_oeaSel/_oeaRange/_oeaData`, `_isqSel/_isqRange/_isqData`, `_indExpSel/_indExpProv/_indExpRange/_indExpData`. Constant: `EXP_PAGE_SIZE = 10`.
- **Window globals:** `window._doVcodeSearch(cat)`, `window._expGoPage(n)`, `window.onIndExpChange()` — wired as `onclick`/`onchange` handlers in the rendered markup.

---

## Page structure (top → bottom)

1. **Prussian blue hero card** (`.exp-hero-stats#expHeroStats`) — title + subtitle on the left, 4 stat columns right-justified. No nested filter bar, no banner image.
2. **Section 1 — StatCan Key Economic Indicators** (`.section-block`) — section-header (`.accent-bar` + `<h3>StatCan Key Economic Indicators</h3>`) + `#canadaIndicatorSection` containing an `.exp-card` with a StatCan indicator dropdown (`#canadaIndicatorDropdown`) and the interactive `#indicatorExplorer` (chart + selectors).
3. **Section 2 — Provincial Indicator Explorer** (`.section-block`) — section-header + `#provExpSection` rendered by `_renderProvExplorer()` into an `.exp-card` with province + indicator `<select>`s, 3M/1Y/3Y/5Y range buttons, KPI callout, and line chart.
4. **Section 3 — Ontario Economic Accounts** (`.section-block`) — section-header + `#oeaSection` rendered by `_renderOeaSection()` with 14 OEA indicators in an `.exp-card`: dropdown, range buttons, `.exp-stat-grid` latest-values card strip, callout, chart.
5. **Section 4 — Quebec Economic Accounts (ISQ)** (`.section-block`) — identical shape to Section 3 with 24 ISQ indicators.
6. **Section 5 — Provincial Raw Indicators** (`.section-block`) — section-header + `#provIndicatorSection` rendered as an `.exp-card` wrapping the legacy `renderIndicatorDropdown()` list for the currently-selected province.
7. **Section 6 — StatCan Table Search** (`.section-block`) — section-header (`.accent-bar` + `<h3>StatCan Table Search</h3>` + `.section-meta#expSearchMeta`) + `#explorerSearch` (search row) + `#explorerCategories` (14 category chips) + `#explorerResults` (paginated 5-column V-code table).

There is no `.section-banner` Unsplash image anywhere in the Data Explorer panel.

---

## 1. Hero card

**Container:** `.exp-hero-stats` — Prussian blue `#003153`, `border-radius: 8px`, `overflow: hidden`, flex column, `margin: 0 0 24px`.

**CSS entry points:** `#tab-explorer .exp-hero-stats` + descendant selectors in `docs/index.html` (inserted immediately after the `#tab-calendar` CSS block).

### Top row (`.exp-hero-top`)
- `display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 24px; padding: 28px 32px 22px`
- **Left** — `.exp-hero-title` (flex-shrink: 0):
  - `<h2>Data Explorer</h2>` — 28px/700 DM Sans, `#ffffff`
  - `.exp-hero-sub` — 14px, `rgba(255,255,255,0.7)`, "Indicators, provincial accounts, StatCan table directory"
- **Right** — `.exp-hero-stats-right#expHeroStatsRight` (flex: 1, display: flex, **justify-content: flex-end**, align-items: flex-end, gap: 24px, padding-left: 48px, flex-wrap: wrap):
  - 4 `.stat-item` columns clustered at the right edge
  - Each with `.stat-value` (22px/700 DM Sans, tabular-nums, `#ffffff`) and `.stat-label` (10px uppercase, `rgba(255,255,255,0.6)`, letter-spacing 0.4px)
  - Stats are populated by `_expRenderHeroStats()` on every `renderExplorer()` call and again when the async `statcan_tables.json` load completes (so the "StatCan Tables" count updates from `…` to the real value)

### Stats list (4 — locked)
| # | Label | Source | Sample |
|---|---|---|---|
| 1 | Indicators | `_indJsonCache.indicators.length` | `713` |
| 2 | V-Codes | `VCODE_INDEX.length` (JS constant) | `125` |
| 3 | StatCan Tables | `_fullTableDir.length + VCODE_INDEX.length` once `_fullDirLoaded === true`; `…` placeholder during the ~200 ms async load | `4,908` |
| 4 | Updated | `_indJsonCache.statcan_latest.updatedAt` parsed as Date and formatted `{month:'short',day:'numeric'}` | `Mar 31` |

All four values are real, derived from pipeline output or the bundled V-code index. Zero fabrication.

**Rejected stats (from the Phase 2 proposal):**
- "History Points: 45,488" — dropped because raw history record count is an internal metric, not a user-facing one. Swapped to "StatCan Tables" once the `export_statcan_tables()` pipeline function unlocked the real count.
- "Provinces: 13" — dropped because it is a constant and not useful.
- "Full Directory: N" / "Curated: N" / "Total Tables: N" — the old `_renderExplorerStats()` three-pill row removed entirely; the hero now carries this story.

### No nested filter bar
Unlike the Projects hero, the Explorer hero has no nested filter bar. Each of the 6 sub-sections already owns its own selectors (province/indicator/range for the indicator explorers, search + category chips for the V-code table). A shared top-level filter would not have clean targets across the mixed section content.

---

## 2. Section 1 — StatCan Key Economic Indicators

**Wrapper:** `.section-block` — `padding: 0 0 28px; margin-bottom: 28px`.

**Header:** `.section-header` with `.accent-bar` (4px × 22px Prussian blue) + `<h3>StatCan Key Economic Indicators</h3>`.

**Body:** `#canadaIndicatorSection` is populated by `renderExplorer()` with an `.exp-card` containing:
- `.exp-card-title`: "Statistics Canada — Key Economic Indicators"
- `.exp-card-sub`: one-line description with a link to the StatCan daily indicators page
- `#canadaIndicatorDropdown` — rendered via `renderIndicatorDropdown()` using the 71 StatCan feed indicators in `_indJsonCache.statcan_latest.indicators` (falls back to raw national indicators if the StatCan feed is absent), categorized by name regex
- `<section id="indicatorExplorer"></section>` — populated by `renderIndicatorExplorer()` with an inner `.exp-card` containing the main indicator catalog dropdown, optional province selector (only for indicators with `prov:true` in `INDICATOR_CATALOG`), 3M/1Y/3Y/5Y `.exp-range-btn` group, callout, 240px chart via `loadIndExpData()`, and an `.exp-card-footlink` to the StatCan source

**Chart data:** `loadIndExpData()` reads from `indicators.json` `history[]`, filters by `indicator_name + province`, supports a 25/75 percentile range band, optional high-impact watchlist event annotations, and an endpoint label via a one-off Chart.js plugin.

---

## 3. Section 2 — Provincial Indicator Explorer

**Header:** `.section-header` + `<h3>Provincial Indicator Explorer</h3>`.

**Body:** `#provExpSection` populated by `_renderProvExplorer()` into an `.exp-card` with:
- `.exp-card-title` "Provincial Indicator Explorer"
- `.exp-card-sub` "Compare provincial indicators with interactive charts"
- `.exp-control-row` containing:
  - `<select id="provExpProvSel" class="exp-select">` — 13 provinces/territories
  - `<select id="provExpIndSel" class="exp-select">` — 6 provincial indicators (CPI, Unemployment, Employment Rate, Participation Rate, Wage Growth, Housing Starts)
  - `.exp-range-group` with 3M/1Y/3Y/5Y `.exp-range-btn` buttons (active state `#003153` bg / white text)
- `#provExpCallout` — `_loadProvExpData()` writes an `.exp-callout` with latest value, diff vs prev period, and period label
- `.exp-chart-wrap` (240px fixed height) wrapping `<canvas id="provExpCanvas">`

**Chart data:** `_loadProvExpData()` reads from `indicators.json` `history[]`, filters by `indicator_name + province`, caches per `(indicator, province)` key, applies range cutoff.

---

## 4. Sections 3 & 4 — Ontario Economic Accounts / Quebec Economic Accounts (ISQ)

Both sections share a common structure rendered by `_renderOeaSection()` / `_renderIsqSection()`:

**Header:** `.section-header` + `<h3>Ontario Economic Accounts</h3>` or `<h3>Quebec Economic Accounts (ISQ)</h3>`.

**Body:** `#oeaSection` / `#isqSection` populated with an `.exp-card` containing:
- `.exp-card-title` with the account name
- `.exp-card-sub` with a source link (Ontario Data Catalogue / Institut de la statistique du Québec)
- `.exp-control-row` with a single indicator `<select>` (14 OEA indicators / 24 ISQ indicators) and a 1Y/3Y/5Y `.exp-range-group`
- `#oeaLatestTable` / `#isqLatestTable` — `.exp-stat-grid` of `.exp-stat-card`s, one per indicator with a value (latest), small unit label, and period subcaption
- `#oeaCallout` / `#isqCallout` — `.exp-callout` with diff vs prev quarter
- `.exp-chart-wrap` wrapping `<canvas id="oeaCanvas">` / `<canvas id="isqCanvas">`

### Latest-value card grid (`.exp-stat-grid`)
- `display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px`
- Each `.exp-stat-card`: white bg, `1px solid #e8ecf0`, 6px radius, 10px 14px padding
  - `.exp-stat-card-label` — 10px uppercase `#475569`, letter-spacing 0.4px
  - `.exp-stat-card-value` — 17px/700 Prussian blue tabular-nums, with optional `<small>` unit suffix (11px `#7a8599`)
  - `.exp-stat-card-period` — 10px `#94a3b8`

### Indicator lists (locked)
- **OEA (14):** Real Consumption, Household Spending, Gov Expenditure, Capital Investment, Exports, Imports, GDP Goods-Producing, Consumption Q/Q %, Household Q/Q %, Gov Spend Q/Q %, Capital Inv Q/Q %, Exports Q/Q %, Imports Q/Q %, GDP Goods Q/Q %
- **ISQ (24):** Real GDP, Nominal GDP, Monthly GDP, Household Spending, Gov Spending, Business Investment, Exports, Imports, Int'l Exports, Int'l Imports, Employee Compensation, Household Income, Real GDP Q/Q %, Housing Starts, Retail Sales, Manufacturing Sales, Wholesale Sales, Avg Weekly Earnings, Employment, Unemployment Rate, Participation Rate, CPI Index, Building Permits (Res), Building Permits (Non-Res)

---

## 5. Section 5 — Provincial Raw Indicators

**Header:** `.section-header` + `<h3>Provincial Raw Indicators</h3>`.

**Body:** `#provIndicatorSection` populated by `renderExplorer()` with an `.exp-card` wrapping the legacy `renderIndicatorDropdown()` output for the currently-selected province (`selectedProvince` module state, defaults to ON). Shows all indicator records for that province grouped by category.

---

## 6. Section 6 — StatCan Table Search

**Header:** `.section-header` with `.accent-bar` + `<h3>StatCan Table Search</h3>` + `.section-meta#expSearchMeta`. The meta span is written by `_expRenderVcodeResults()` and shows one of four forms:
- `""` — initial state, no search run
- `"0 results"` — no matches
- `"N result"` / `"N results"` — single page fits all matches
- `"N results · page X of Y"` — multi-page result

### Search row (`#explorerSearch` → `.exp-search-row`)
- `<input type="text" id="vcodeSearch" class="exp-search-input">` — 14px placeholder, Enter keypress runs the search and resets pagination to page 1
- `<button class="exp-search-btn">` Search — Prussian blue background, white text, 11px 24px padding, 8px radius

### Category chips (`#explorerCategories` → `.exp-cat-row`)
- 14 `.exp-cat-btn` pills: Labour Market · GDP · Construction · Housing · Prices · Trade · Energy · Manufacturing · Agriculture · Infrastructure · Transportation · Health · Demographics · Tourism
- Click any chip to trigger `window._doVcodeSearch(category)` with the chip label as the query and reset `_expSearchPage = 1`

### Results table (`#explorerResults` → `_expRenderVcodeResults()`)

**Wrapper:** `.exp-vcode-table-wrap` — `width: 100%; overflow: hidden; border-radius: 8px; background: #ffffff; border: 1px solid #d5dbe3; box-shadow: var(--shadow-sm)`. The `overflow: hidden` clips the Prussian blue `<thead>` background to the rounded top corners — matches the Calendar and Projects table patterns.

**Table:** `.exp-vcode-table` — `border-collapse: collapse; table-layout: fixed; font-size: 13px`.

### Column layout (5 columns — locked)
| # | Header | Class | Width | Content |
|---|---|---|---|---|
| 1 | V-Code | `.exp-col-vcode` | 110px | `.exp-vcode-code` pill — monospace, `#f1f5f9` bg, Prussian blue text, 3px 7px padding, 3px radius |
| 2 | Table | `.exp-col-table` | 130px | `.exp-vcode-tbl` monospace 11px `#475569` text (e.g., `"34-10-0066-01"`) |
| 3 | Title | (auto) | remainder | `.exp-vcode-title` (13px/600 DM Sans, `white-space: normal` for wrap) + optional `.exp-vcode-meta` subcaption in `#7a8599` 11px (`freq · geo` joined) |
| 4 | Category | `.exp-col-category` | 180px | `.exp-vcode-cat` pill — `#e8eef4` bg, Prussian blue text, 10px uppercase DM Sans |
| 5 | Link | `.exp-col-link` | 70px | `↗` anchor centered via `td.exp-col-link{text-align:center}`; URL is `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={tableId_no_dashes}` (BoC entries rewrite to `https://www.bankofcanada.ca/rates/`) |

### Header styling (`.exp-vcode-table thead th`)
- Background: `#003153` Prussian blue — fills the wrap's rounded top corners via `overflow: hidden` on the wrap
- Font: 11px DM Sans 600 uppercase, `letter-spacing: 0.3px`, color `#ffffff`
- Padding: `12px 10px 12px 18px` (18px left matches Calendar and Projects)
- Right border: `1px solid rgba(255,255,255,0.15)` on each `th`, `:last-child` drops it

### Body row styling (`.exp-vcode-table tbody tr` / `td`)
- Row background: `#ffffff` alternating with `#f9fafb` (zebra via `:nth-child(even)`)
- Hover: `#e8eef4` (light Prussian blue tint)
- `border-bottom: 1px solid #e8ecf0` on td, `:last-row` drops the bottom border
- `border-right: 1px solid #e8ecf0` on td, `:last-column` drops it
- `vertical-align: top` (since title can wrap to multiple lines for long table names)
- Cell padding: `13px 10px 13px 18px`

### Empty state (`.exp-empty`)
- `padding: 40px 24px; text-align: center; color: #7a8599; font-size: 13px; background: #ffffff; border: 1px solid #d5dbe3; border-radius: 8px`
- Used for both the initial "Enter a search term..." prompt and the "No tables found for ..." no-match state

### Pagination (`.exp-pagination`)

Rendered below the table wrap **only when `totalPages > 1`**. Centered flex row with:
- `‹ Prev` button — disabled when `_expSearchPage === 1`
- `.exp-page-info` — "Page X of Y", 13px DM Sans, `#1a1a1a`, min-width 120px centered
- `Next ›` button — disabled when `_expSearchPage === totalPages`

Button styling matches `.exp-range-btn`: white background, `#d5dbe3` border, 6px radius, Prussian blue text. Disabled state: `opacity: 0.4; cursor: not-allowed`. On click, `window._expGoPage(n)` updates `_expSearchPage` and re-renders, then scrolls `#explorerResults` into view via `scrollIntoView({ behavior: 'smooth', block: 'start' })`.

**Page size:** `EXP_PAGE_SIZE = 10` (locked — matches `CAL_PAGE_SIZE`).

### Search logic (`_expSearchAll()`)

Full (unsliced) search that bypasses the 25-result hard cap in the legacy `searchVCodes()` helper so pagination can walk the complete match set:
1. Lowercase + split query on whitespace, drop tokens shorter than 2 chars
2. Expand via `_SYN` synonym map (`jobs` → `employment, labour, workforce, ...`, etc. — 56 synonym groups at `app.js:5642`)
3. Score every entry in `VCODE_INDEX` (curated, +5 score boost) and every entry in `_fullTableDir` (directory, 0 boost)
4. Score formula: +1 per expanded token found in `(title + keywords + category + geo)`, +2 per token found in title alone, +1 per token found in keywords
5. Filter to non-zero scores, concatenate curated + directory, sort by score desc
6. Return the full set — pagination slicing happens inside `_expRenderVcodeResults()`

### HTML escaping

`_expEscapeHtml()` helper escapes `& < > "` in all user-facing strings written into the table — protects against malformed StatCan titles breaking the DOM.

---

## 7. Data flow & rendering pipeline

### Initial load sequence
1. `init()` calls `loadIndicators()` which fetches `indicators.json` and caches it as `_indJsonCache`
2. Async IIFE at `app.js:5625` fetches `data/statcan_tables.json`, filters out entries already in `VCODE_INDEX`, maps to `_fullTableDir`, sets `_fullDirLoaded = true`, and calls `_expRenderHeroStats()` so the "StatCan Tables" stat updates
3. User clicks the Explorer tab — `renderExplorer()` runs:
   1. `_expRenderHeroStats()` — writes the 4 hero stats
   2. Renders `#explorerSearch` with `.exp-search-row`
   3. Renders `#explorerCategories` with `.exp-cat-row` and 14 `.exp-cat-btn` chips
   4. Writes the initial `.exp-empty` prompt into `#explorerResults`
   5. Clears `#expSearchMeta`
   6. Populates `#canadaIndicatorSection` with its `.exp-card` wrapper
   7. Calls `renderIndicatorDropdown()` into `#canadaIndicatorDropdown`
   8. Calls `renderIndicatorExplorer()` to render the chart into `#indicatorExplorer`
   9. Calls `_renderProvExplorer()` to render `#provExpSection`
   10. Calls `_renderOeaSection()` to render `#oeaSection` + `_loadOeaData()`
   11. Calls `_renderIsqSection()` to render `#isqSection` + `_loadIsqData()`
   12. Populates `#provIndicatorSection` with an `.exp-card` + `renderIndicatorDropdown()`

### On search (`window._doVcodeSearch()`)
1. Reads the query from `#vcodeSearch` or uses the category chip value
2. Sets `_expLastQuery = query`
3. Calls `_expRenderVcodeResults()` which runs `_expSearchAll()`, slices to current page, writes the rendered table into `#explorerResults`, updates `#expSearchMeta`

### On pagination (`window._expGoPage(n)`)
1. `_expSearchPage = n`
2. Calls `_expRenderVcodeResults()` — the render clamps page to `[1, totalPages]` on every render so stale values self-correct
3. `scrollIntoView` on `#explorerResults`

### On Enter keypress or category chip click
Both reset `_expSearchPage = 1` before running the search so narrowing a query doesn't strand the user on a trailing page.

---

## 8. Data: `statcan_tables.json`

### Location
- **Canonical source:** `config/statcan_table_registry.csv` — 4,908-row registry with columns `Table Name | Table ID | Product ID (raw) | CANSIM ID | Link | Frequency | Coverage | Focus | Subject Codes | Survey Codes | Start Date | End Date | Last Release | Status`. Hand-curated, edited to add new tables.
- **Frontend-consumed copy:** `docs/data/statcan_tables.json` and `public/data/statcan_tables.json` — regenerated by `export_statcan_tables()` on each pipeline run.

### Schema (frontend-expected shape)
```json
[
  {
    "t": "34-10-0066-01",
    "n": "Building permits, by type of structure",
    "k": "building permits, by type of structure construction 34",
    "c": "Construction",
    "f": "Monthly",
    "g": "Canada"
  },
  ...
]
```

Fields:
- `t` — StatCan Table ID (e.g., `"34-10-0066-01"`). Used by the frontend to build the StatCan portal URL.
- `n` — Table name (full, human-readable).
- `k` — Keyword blob — lowercase concatenation of `Table Name + Focus + Subject Codes`. Powers the substring scorer in `_expSearchAll()`.
- `c` — Category (`Focus` column from the CSV). 34 distinct values observed in the current registry, e.g., "Construction", "Health", "Travel and tourism", "National accounts and GDP", "Unclassified".
- `f` — Frequency (full string). Registry contains 13 distinct values: `Occasional` (2,438), `Annual` (1,386), `Monthly` (321), `Every 5 years` (216), `3 times/year` (185), `Every 2 years` (133), `3 times in 2 years` (68), `Code 20` (52), `Code 19` (47), `Every 3 years` (39), `Weekly` (17), `Daily` (5), `Every 10 years` (1). The frontend's `FREQ_MAP` normalizes single-letter codes (`M`/`Q`/`A`/`D`/`W`/`E`/`S`/`O`) but falls back to the raw string for everything else, so these full-string frequencies pass through unchanged.
- `g` — Geography / Coverage. `National (default)` and `National` both normalize to `"Canada"` at export time. Other values preserved as-is: `CMA`, `Provincial/territorial`, `Census division`, `International`, `Municipal`, `Economic region`, `Census subdivision`, `Health region`, `Census agglomeration`, `Federal electoral district`, `Forward sortation area`, `Census tract`.

### Write format
- Written with `json.dump(rows_out, f, ensure_ascii=False, separators=(",", ":"))` — **compact JSON, no pretty-printing.** Keeps the file ~1.5 MB instead of ~3 MB. The frontend doesn't care about whitespace.
- Filters to `Status == 'Current'` at export time (drops archived/discontinued tables). In the current registry all 4,908 rows are `Current`, so the filter is a no-op today but remains in place as a forward-compatibility guard.
- Writes to `{output_dir}/statcan_tables.json` where `output_dir` is the caller's choice (`docs/data` or `public/data`).

---

## 9. Pipeline integration

### `export_statcan_tables()` in `tools/export_dashboard.py`
- Inserted immediately after `export_events_global()` at line 1275 and before the `MAIN ENTRY POINT` banner
- Reads `config/statcan_table_registry.csv` via `csv.DictReader`
- Filters `Status == 'Current'`
- Maps each row to the compact `{t, n, k, c, f, g}` shape
- Writes a bare top-level array (matching what the frontend loader at `app.js:5625` expects)
- Accepts `conn` parameter for signature compatibility with the other exporters (unused today)
- Called from `export_all()` right after `export_events_global()`, wrapped in try/except so a missing config CSV degrades gracefully (logs a warning, skips)
- On success, appends `statcan_tables.json` to `files_written` which shows up in `manifest.json`
- Raises `SyntaxWarning`-free on import; `ast.parse` and `from tools.export_dashboard import export_statcan_tables` both verified clean

### Verification (EXP-13)
- `python -c "import ast; ast.parse(open('tools/export_dashboard.py').read())"` → syntax OK
- `python -c "import ast; ast.parse(open('update_dashboard.py').read())"` → syntax OK
- `from tools.export_dashboard import export_all, export_statcan_tables, export_events_global, export_indicators, export_signals, _validate_output` → imports cleanly
- `export_statcan_tables(None, 'docs/data')` → writes `docs/data/statcan_tables.json` with 4,908 rows (1,493 KB)
- `export_statcan_tables(None, 'public/data')` → writes byte-identical copy to `public/data/statcan_tables.json` (same SHA256)
- `node -e "new Function(require('fs').readFileSync('docs/js/app.js','utf-8'))"` → JS syntax OK (6,281 lines)
- `node -e "new Function(require('fs').readFileSync('public/js/app.js','utf-8'))"` → JS syntax OK (4,994 lines)
- Byte-identical comparison of the Explorer CSS (80 lines, SHA256 match) and the Explorer HTML panel (SHA256 match) across `docs/index.html` and `public/index.html`
- Byte-identical comparison of the Explorer JS regions (`renderIndicatorExplorer` + `loadIndExpData` = 8,148 bytes, and the main Explorer + V-code block = 56,439 bytes) across `docs/js/app.js` and `public/js/app.js` — all SHA256-matched

---

## 10. Editorial / data integrity rules

- **No fabrication in hero stats** — every one of the 4 stats is derived from real pipeline output or the bundled JS constant. "StatCan Tables" shows `…` during the async load rather than lying with a `0`.
- **URL hard gate** (from CLAUDE.md) — every V-code search result has a real StatCan portal URL derived from its Table ID, or the Bank of Canada rates page for BoC entries. No result without a valid link.
- **No editorializing in UI text** — section headers, card titles, stat labels, empty-state messages are all factual. No "powerful", "insightful", "comprehensive" language.
- **HTML-escape all user-facing strings** in the V-code table via `_expEscapeHtml()` — protects against malformed StatCan titles containing `& < > "` from breaking the DOM.
- **Use indicators.json as the single source for the "Updated" stat** — `statcan_latest.updatedAt` is the authoritative freshness marker for the StatCan indicator feed. If it is missing, the stat falls back to `—` rather than inventing a date.
- **Preserve the `Status` filter on the CSV export** even though all rows are currently `Current` — it is a forward-compatibility guard against registry edits that add discontinued tables.
- **Zero modifications to `docs/data/*.json`** during this session's frontend work. The only JSON change is the new `statcan_tables.json` file generated by the new exporter, which matches what the pipeline will produce on its next weekly run.

---

## 11. Approved design vocabulary reused from other tabs

- `#003153` Prussian blue — hero background, accent-bar, card titles, section headers, range-button active state, V-code table thead, pagination button text
- `#e8ecf0` light gray — row borders, column separators, section-header bottom border, stat-card border
- `#d5dbe3` medium gray — exp-card border, select borders, button borders, pagination button borders, wrap borders
- `#f9fafb` — table zebra row
- `#e8eef4` — hover tint (light Prussian blue), V-code category pill background, range-button hover
- `#f1f5f9` — V-code code pill background
- `#f5f8fc` — (unused in Explorer; reserved for calendar cell hover)
- `#475569` / `#7a8599` / `#94a3b8` — gray text scale for labels, meta, and subcaptions
- DM Sans typography — all headings, labels, and tabular stat values
- JetBrains Mono / Consolas — V-code identifier and Table ID cells
- `var(--text-sm)` — chart axis font, callout meta
- 8px border-radius on the hero card, exp-cards, V-code table wrap, pagination buttons, search input, search button
- 6px border-radius on selects, range buttons, stat cards
- 20px border-radius on category chip pills
- 11px uppercase 0.3px-letter-spacing DM Sans pattern for all column headers and stat labels

**Not promoted to global classes** — all new rules scoped to `#tab-explorer` to match the existing tab-scoped CSS pattern (National, Provinces, Industries, Markets, Projects, Calendar all have their own scoped copies).

---

## 12. Files of record

- `docs/index.html`:
  - `#tab-explorer` CSS block (~80 lines, inserted after the `#tab-calendar` block) — hero card, section-header rhythm, `.exp-card`, select/button/range reskin, `.exp-callout`, `.exp-chart-wrap`, `.exp-stat-grid`/`.exp-stat-card`, `.exp-search-row`, `.exp-cat-row`, `.exp-empty`, `.exp-vcode-table-wrap`/`.exp-vcode-table` (5 columns + header + body styles), `.exp-pagination`
  - `<div class="tab-panel" id="tab-explorer">` HTML structure — Prussian blue hero with 4 stats, six `.section-block`s with `.section-header` + inner containers
- `public/index.html` — byte-identical mirror of the Explorer HTML + CSS regions
- `docs/js/app.js`:
  - `renderIndicatorExplorer()` (~2645) — reskinned to use `.exp-card` / `.exp-control-row` / `.exp-select` / `.exp-range-btn` / `.exp-chart-wrap` / `.exp-card-footlink`
  - `loadIndExpData()` callout (~2720) — reskinned to use `.exp-callout` / `.exp-callout-value` / `.exp-callout-chg.{up,down,flat}` / `.exp-callout-meta` / `.exp-callout-empty`
  - Async table directory loader (~5625) — added `_expSearchPage = 1` + `EXP_PAGE_SIZE = 10` module state, changed the post-load hook from `_renderExplorerStats()` to `_expRenderHeroStats()`
  - `_expRenderHeroStats()` (new, ~5738) — replaces the dead `_renderExplorerStats()`
  - `renderExplorer()` (~5778) — rewritten with `.exp-search-row` / `.exp-cat-row` / `.exp-empty` / `.exp-card` wrappers
  - `_renderProvExplorer()` + `_loadProvExpData()` callout (~5861) — reskinned to `.exp-card`, `.exp-control-row`, `.exp-callout` vocabulary
  - `_renderOeaSection()` + `_renderOeaLatestTable()` + `_loadOeaData()` callout (~5940) — reskinned to `.exp-card` + `.exp-stat-grid` + `.exp-callout`
  - `_renderIsqSection()` + `_renderIsqLatestTable()` + `_loadIsqData()` callout (~6035) — reskinned to `.exp-card` + `.exp-stat-grid` + `.exp-callout`
  - `_expSearchAll()` (new, ~6113) — full-unsliced scorer bypassing `searchVCodes()`'s 25-result cap
  - `_expEscapeHtml()` (new, ~6134) — HTML escape helper for the paginated table
  - `window._doVcodeSearch()` (~6141) — now just sets `_expLastQuery` and calls `_expRenderVcodeResults()`
  - `_expRenderVcodeResults()` (new, ~6155) — the paginated 5-column table renderer
  - `window._expGoPage()` (new, ~6197) — pagination handler with scroll-into-view
- `public/js/app.js` — byte-identical mirror of the Explorer JS regions
- `docs/data/statcan_tables.json` — new file, 4,908 rows, 1,493 KB
- `public/data/statcan_tables.json` — byte-identical mirror
- `config/statcan_table_registry.csv` — pre-existing canonical 4,908-row registry (not modified this session)
- `tools/export_dashboard.py`:
  - `export_statcan_tables(conn, output_dir)` (new, ~line 1275) — reads CSV, filters `Status=='Current'`, maps to compact shape, writes bare array
  - `export_all()` — extended with the `export_statcan_tables` call wrapped in try/except (line 1339)

---

## 13. Known gaps / deferred

- **`statcan_table_registry.csv` is still hand-curated.** The pipeline now copies it to `statcan_tables.json` via `export_statcan_tables()` on every run, but there is no live-fetch from StatCan's registry endpoint. Future work: build `tools/statcan_registry_fetcher.py` that pulls the latest full table list from StatCan's product metadata API and merges into `config/statcan_table_registry.csv` with dedup by Table ID before the export runs. This would let the registry stay current without manual edits.
- **`Code 19` / `Code 20` frequency values** — the current registry contains 99 rows with these uninterpreted StatCan internal codes in the `Frequency` column. They pass through to the frontend search results unchanged. Future work: map them to their real meanings once StatCan documents them, or filter them out at export time if they are known to be deprecated markers.
- **"Unclassified" category rows** — 525 rows in the registry have `Focus == 'Unclassified'`. They are preserved in the export so search still finds them, but they cluster into a large generic category. Future work: add a second-pass keyword classifier inside `export_statcan_tables()` that assigns a better category based on Table Name substrings.
- **V-code search has no filters beyond the category chips** — you can't narrow by frequency, geography, or time range. Future work: add a filter bar above the results table with `<select>`s bound to the 13 frequency values and 13 geography values observed in the registry.
- **No autocomplete on the search input** — users can't preview matching tables as they type. Future work: debounced on-input search with a dropdown of top-5 matches.
- **`_fullDirLoaded` gating lags the hero render** — on the very first Explorer tab click, the hero briefly shows "StatCan Tables: `…`" until the async load resolves (typically <200 ms on localhost). Acceptable as-is; future work could await the load before the first `_expRenderHeroStats()` call to eliminate the flicker.
- **`renderIndicatorExplorer()` rendering is shared logic** — it is called only from `renderExplorer()` at `docs/js/app.js:5810` and recursively from its own `onIndExpChange()` handler at ~2696. Grep confirmed no frozen-tab calls. If a future session needs to show this chart elsewhere, the `.exp-card`-scoped classes will need to be mirrored or promoted.
- **`public/index.html` and `public/js/app.js` are not byte-identical to `docs/` globally.** The Explorer region (CSS + HTML + JS) is byte-identical and verified via SHA256. Other tab regions have pre-existing drift from before the design-theme pass began. The session rule is "byte-identical in the Explorer region", not globally, and that holds.
- **No test coverage** — no unit tests for `_expSearchAll()`, `_expRenderVcodeResults()`, or `export_statcan_tables()`. The CAL/PROJ/MKT sessions also shipped without tests per the session convention; Explorer follows the same pattern. Future work: a tests/ module that loads `statcan_tables.json`, runs `_expSearchAll()` against sample queries, and asserts result counts + score ordering.
- **Responsive / mobile layout** — Signal Dispatch is desktop-only per project rules, so no mobile media queries were added. If mobile is ever scoped in, the hero's 4-stat row will need to wrap sensibly and the V-code table will need horizontal scroll or column hiding.

---

## 14. Locked patch set

All 13 patches — **EXP-01 through EXP-13** — documented in `PATCH_LOG.md` under the "Data Explorer Tab" section. See that file for the full change log including root causes, file diffs, byte-identical preservation notes, and the `export_statcan_tables()` pipeline function writeup.
