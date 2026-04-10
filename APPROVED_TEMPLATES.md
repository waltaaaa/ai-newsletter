# Approved Templates — Dashboard Design Reference

This file documents the approved layout, formatting, and behavior for each page. Use this as the source of truth when generating new briefings or modifying the frontend. Pages are locked once approved.

---

## TL;DR Tab (Approved 2026-04-07)

### Numbers at a Glance — Key Indicators View

**Layout:** Two sections stacked vertically inside a collapsible `<details>` element with toggle between Key Indicators and Markets.

#### This Week's Key Data (top section)
- **Purpose:** Snapshot of top 4 energy commodities for the reporting week
- **Columns (5):** Indicator | Unit | Value | Change (W/W) | Source
- **Column order matters:** Unit before Value
- **Column widths:** 24% | 14% | 16% | 20% | 22% (table-layout: fixed)
- **Alignment:**
  - Indicator: left
  - Unit: right (tight to Value)
  - Value: right, bold, 13px
  - Change (W/W): left, with 16px left padding for separation from Value
  - Source: left, hyperlinked in Prussian blue (#003153)
- **Change format:** `▲ +X.X%` or `▼ -X.X%` only — no text, no suffixes (M/M, day, W/W)
- **Data source:** `commodities[0:4]` from briefing JSON, fields `val` and `mm`
- **Section label:** "THIS WEEK'S KEY DATA" (tldr-mkt-group-label style)

#### Key Economic Indicators (bottom section)
- **Purpose:** Core macro indicators (BoC Rate, GDP, CPI, Unemployment, Housing Starts, WTI, CAD/USD, TSX)
- **Columns (5):** Indicator | Frequency | Value | Change | Source
- **Column order matters:** Frequency before Value
- **Same column widths and alignment as This Week's Key Data
- **Indicator column includes:**
  - Bold indicator name (13px, #1a1a1a)
  - Grey context subtitle below (11px, #7a8599, `ind-t-name-ctx` class)
  - Context = changeContext + period joined by ` · `
- **Change format:** Arrow + short value only (e.g., `▲ +0.1% M/M`, `▼ -0.5pp`, `— Held`)
- **Held indicators:** Use em dash `—` as directional arrow
- **Data fields:** `change` (short) and `changeContext` (context) are separate fields in JSON
- **Source fallback map:** bocRate->Bank of Canada, realGdp/cpi/unemployment->Statistics Canada, housingStarts->CMHC, consumerConfidence->Conference Board, wtiCrude/cadUsd/tsx->yfinance
- **Section label:** "KEY ECONOMIC INDICATORS"

### Numbers at a Glance — Markets View

**Layout:** Three sections with group labels: Commodities, Currencies, Indices.

#### All three sections share:
- **Columns (5):** Indicator | Unit | Value | Change (W/W) | Source
- **Same column widths, alignment, and styling as Key Indicators tables
- **Group labels:** Uppercase, 11px, #7a8599, bottom border, `tldr-mkt-group-label` class
- **Unit values:**
  - Commodities: parsed from value string (e.g., "US$102.88/bbl" -> num="102.88", unit="USD/bbl")
  - Wheat: special cent handling ("607.5¢/bu" -> num="607.5", unit="USc/bu")
  - FX: forced unit "rate"
  - Indices: forced unit "pts"
- **Change format:** Normalized via `_normalizeChg()` — extracts `±X.X%` only
- **Data source:** `commodities` (fields `val`, `mm`), `financialMarkets.fx` (fields `value`, `mm`/`day`), `financialMarkets.indices` (fields `value`, `mm`/`day`)

### Source Hyperlinks
- All source names are hyperlinked via `_srcLink()` helper
- Link color: Prussian blue (#003153), no underline, underline on hover
- URL mapping:
  - Bank of Canada -> https://www.bankofcanada.ca/rates/
  - Statistics Canada -> https://www150.statcan.gc.ca/n1/en/type/data
  - CMHC -> https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research
  - Conference Board -> https://www.conferenceboard.ca/
  - yfinance -> https://finance.yahoo.com/

### Table Styling (shared across all tables)
- **Font:** 13px uniform across all cells
- **Headers:** 12px uppercase, DM Sans, white text on Prussian blue (#003153) background
- **Header alignment:** All left except Value (right)
- **Cell padding:** 10px 8px default
- **Row borders:** 1px solid #e8ecf0, no border on last row
- **Table layout:** fixed with explicit th widths
- **Change colors:** up=#0d7a3f, down=#c4320a, unch=#7a8599

### Projects Section
- Only show projects with assigned dollar values (filter out N/D, N/A, Not disclosed, empty)
- Sort by value descending
- New projects first (up to 6), then status changes (fill to 12 total)
- Status badges with color-coded slugs

### Weekly Briefing Narrative
- Lead sentences in `<span class="lead-sentence">` — bold
- Body text: no `<strong>` tags (stripped during body trimming)
- Em dashes (—) used as separator after lead sentences
- Superscript footnote citations link to sources
- No mojibake — all UTF-8 characters properly encoded

### Encoding Requirements
- All text in briefing JSON must be valid UTF-8
- No double-encoded sequences (â€", â€™, etc.)
- Em dash: U+2014, En dash: U+2013, Right single quote: U+2019

---

## National Tab (Approved 2026-04-07)

### Layout
Five subtabs: Canada, United States, China, European Union, United Kingdom. Canada renders on load; others render lazily on click.

### Canada Subtab

#### National Analysis
- **Font:** 15px DM Sans, line-height 1.7, #1a1a1a (matches Policy Developments)
- **Lead sentences:** Bold, followed by em dash separator
- **Footnote citations:** Superscript, Prussian blue (#003153), clickable

#### Unemployment Chart
- **Data source:** `timeseries.json` key `unemployment_rate` (built from `nat_unemployment` indicator history)
- **Type:** Line chart with current-value reference line (red dashed)
- **Window:** 12 months from current date

#### Key Indicators & Sector Signals Table
- **Uses:** `_natIndTable()` with `tldr-ind-table` class (shared TL;DR styling)
- **Columns (5):** Indicator | Frequency | Value | Change | Source
- **Data source:** `metaRow()` helper reads from `D.indicatorMeta` (primary) + `D.metrics` (fallback) + `computeChange()` (last resort). Fully dynamic — pipeline updates each week.
- **Value rendering:** `san()` not `fmtNum()` — prevents rounding (e.g., 2.25% → 2.3%)
- **Indicators (8):** BoC Rate (8x/yr), Real GDP (Monthly), CPI Inflation, Unemployment Rate, Employment Change, Participation Rate, Housing Starts, Building Permits
- **No emojis** in panel title — just "Canada — National"

#### Enrichment Tables (4 sections)
All use `_natIndTable()` via `enrichTable()` helper. Same 5-column layout as Key Indicators.
- **Labour Market** — Change (M/M): Employment Change, Full-time, Part-time, Private Sector, Public Sector
- **Consumer Pulse** — Change (M/M): CPI, Core CPI (Median), Shelter, Food, Energy
- **Housing & Construction** — Change (M/M): Housing Starts, Building Permits, Residential Permits, Non-Residential Permits
- **Trade & Commodities** — Change (M/M): Merchandise Exports, Imports, Trade Balance, WTI Crude, CAD/USD
- **Change values:** Stored in `metrics` as `{key}_chg` fields (e.g., `fulltime_change_chg`)
- **Change labels:** "Change (M/M)" header passed via `chgLabel` parameter
- **No "Active Residential Projects" row**

#### Project Pipeline
- **Threshold filter:** Province GDP thresholds via `meetsThreshold()` — ON $500M, QC $250M, AB $200M, BC $175M, SK $45M, MB $40M, NS $25M, NB $20M, NL $17M, PE $5M, YT/NT/NU $3M
- **New projects first:** Sorted by value descending within new/existing groups
- **NEW badge:** Prussian blue (#003153) background, white text, `tldr-freq-tag` class
- **Max rows:** 10 (up to 5 new + fill to 10 with existing)

### Global Subtabs (US, China, EU, UK)
- **No flag emojis** — plain text labels
- **Analysis narrative:** Same 15px font as Canada
- **Charts:** Each subtab has a chart. Config in `GLOBAL_CHART_CFG` with `tsKeys` array (fallback). Chart init picks source with most data points. Falls back to last 24 entries if insufficient recent data.
  - US: S&P 500 (keys: `idx_sp500`, `sp500`)
  - China: Manufacturing PMI (key: `china_pmi`) with 50.0 expansion threshold reference line
  - EU: EUR/USD (key: `eurusd`)
  - UK: FTSE 100 (keys: `idx_ftse`, `ftse100`)
- **Indicator table:** 5 rows — GDP Growth, CPI Inflation, Policy Rate, Unemployment Rate, Trade Balance. No Productivity Growth row.
- **Data source:** `D.global[].indicators` + `D.global[].indicatorMeta`
- **Region mapping:** `REGION_MAP` includes `'China / Asia':'china'`
- **Change column:** Uses `indicatorMeta.change` only — no value-as-change fallback
- **Trade balance changes:** Numeric values (e.g., `▼ -$33.0B`) not text ("Widened")
- **Source hyperlinks:** BEA, BLS, Federal Reserve, Census Bureau, NBS, PBOC, GAC, Eurostat, ECB, ONS, BoE — all in `_srcUrls` map

## Provinces Tab (Approved 2026-04-09)

### Layout
Horizontal province sub-nav bar (charcoal) flush-connected to main nav, followed by hero card, provincial analysis narrative, chart callout, policy developments accordion, key indicators table, 4 enrichment dropdowns, sector signals narrative, project pipeline table, and upcoming events.

### Province Sub-Navigation
- **Position:** Static (scrolls with content, does not follow user down the page)
- **Background:** Charcoal (`#2d3748`) with darker accent border at bottom (`#1a202c`)
- **Layout:** Single centered row, flex-wrap, 6px gap, flush against the main nav (zero gap)
- **Pills:**
  - Short codes: ON, QC, AB, BC, SK, MB, NS, NB, NL, PEI, YT, NWT, NU
  - Font: 13px/600 DM Sans, letter-spacing 0.3px
  - Unselected: `rgba(255,255,255,0.65)` text
  - Hover: `rgba(255,255,255,0.95)` text
  - Selected: white text with white 2px underline
  - Territories: slightly muted (`rgba(255,255,255,0.45)`)
  - Vertical separator between provinces and territories
- **Full name on hover** via `title` attribute; hero card displays full province name
- **Mobile padding fix:** `@media(max-width:899px)` sets `.prov-page { padding: 0 16px 20px }` (no top padding) to preserve flush connection

### Hero Card
- Prussian blue (`#003153`) rounded panel
- Full province name (h2), subtitle "Weekly provincial economic analysis · GDP threshold: $XM"
- 3 stat items: Active Projects, Pipeline Value, New This Week

### Provincial Analysis
- **Content source:** `provData.analysis` + `provData.consumerPulse` (sectorHighlights moved to Sector Signals section)
- **Font:** 15px DM Sans, line-height 1.7, #1a1a1a
- **Lead sentences:** Bold, followed by em dash separator (auto-wrapped via `addLeads()`)
- **Footnote citations:** Superscript, Prussian blue (#003153), clickable
- **Helpers hoisted:** `addLeads()` function and `allSrc` array defined at function scope for reuse by Sector Signals section

### Insight Chart Callout
- **Structure:** TL;DR callout pattern — text component on top, chart below, Prussian blue left border, light blue (`#e8eef4`) background
- **Classes:** `.tldr-callout` wrapper, `.tldr-callout-chart` inner, `.tldr-callout-chart-title`, `.tldr-callout-source`
- **Text component:** News-driven narrative pulled from:
  1. Primary: `provData.insightCharts[0].reasoning` (agent-written, database refs stripped)
  2. Secondary: One supporting sentence extracted via `_buildProvCalloutText()` from province narrative fields (analysis, labourDeepDive, consumerPulse, sectorHighlights, tradeExposure, marketContext) that shares topic keywords AND contains distinct data points
- **Sentence splitter:** `_splitSentences()` protects decimals (7.6), acronyms (U.S.), and dollar amounts from false period splits
- **Chart title:** Data-driven narrative (e.g., "Unemployment Rate declined 3.8% over the past year") — simple format, no garbled clause extraction
- **Subtitle:** Updates dynamically to reflect only datasets that actually rendered
- **Minimum 2 points** required for a series to render (prevents single-point "wonky" lines)
- **Data source priority:** `provData.insightCharts[0]` array first, falls back to legacy `provData.insightChart` singular
- **Editorial rule:** Stripped phrases — "The province tracks N projects", "The database tracks N...", "key secondary indicator"

### Policy Developments
- **Collapsible accordion** (`<details class="policy-item">`)
- **Dedup by title** to prevent duplicates (e.g., BC showed "Opening more homes in West Vancouver" twice)
- **Empty state:** "No policy developments tracked for [province] this week."
- **Meta label:** "N provincial + M federal developments"

### Key Indicators Table (Full-Width)
- **Uses:** `_natIndTable()` with `tldr-ind-table` class (shared TL;DR styling)
- **Columns (5):** Indicator | Frequency | Value | Change | Source
- **Row grouping:**
  1. **GDP Group** — Real GDP Growth (QoQ), Provincial GDP, GDP Goods-Producing, GDP Services-Producing
  2. **Labour Group** — Unemployment Rate, Employment Rate, Participation Rate, Average Hourly Wage
  3. **Prices Group** — CPI Index
  4. **Housing & Investment Group** — Housing Starts, Building Permits, Capital Investment
  5. **Trade Group** — Trade Balance
- **Indicators (up to 13):**
  - **Real GDP Growth (QoQ)** — Uses `real_gdp_qoq` indicator when available, falls back to annual YoY. Displays `+X.X%` with `— QoQ` tag. Source: Ontario Economic Accounts / StatCan 36-10-0402
  - **Provincial GDP** — Annual, `_fmtMillions()` → `$XXX.XB`. Change from briefing `gdp` field. Source: StatCan 36-10-0402
  - **GDP Goods-Producing** — Quarterly, from `provPrefix + '_gdp_goods'` in indicator_history. Source: StatCan 36-10-0402
  - **GDP Services-Producing** — Quarterly, derived as `total GDP - goods GDP`. Change computed from total/goods pct shares. Source: StatCan 36-10-0402
  - **Unemployment Rate** — Monthly, from briefing or indicator_history
  - **Employment Rate** — Monthly, from indicator_history (real StatCan LFS Feb 2026 data)
  - **Participation Rate** — Monthly, from indicator_history
  - **Average Hourly Wage** — Monthly, `$X.XX/hr`, pulled from `avg_hourly_wage` indicator with `previous_value` for MoM change. Source: StatCan 14-10-0063
  - **CPI Index** — Monthly, from briefing with computed MoM change from `indicatorMeta.cpi.prev`. Source: StatCan 18-10-0004
  - **Housing Starts** — Monthly, real numeric value from `housingStarts` indicator (filters out descriptive-text values). Source: CMHC
  - **Building Permits** — Monthly, sum of residential + non-residential from `bldg_permits_res` + `bldg_permits_nonres` indicators (StatCan 34-10-0292). $K raw → `_fmtMillions()` → `$X.XB`
  - **Capital Investment** — Quarterly, from `provPrefix + '_real_capital_investment'`. Source: StatCan 36-10-0104
  - **Trade Balance** — Quarterly, computed as exports - imports. Change computed as QoQ delta using export/import pct values. Source: StatCan 12-10-0121
- **Format helpers:**
  - `_fmtMillions()` — converts `$M`-denominated raw values to `$B`/`$M`/`$T`
  - `_fmtPersons()` — formats employment levels to K/M with "persons" suffix
  - `_fmtBig()` — legacy dollar formatter
- **Change behavior:**
  - Zero changes display as `— Held` (em dash + "Held")
  - GDP Growth value-is-change labeled as `— YoY` tag
- **N/A rows filtered out** — indicator count header shows actual filtered count

### pchg() / computeChange() — data accuracy (critical)
- **Priority order in `pchg()`:**
  1. Compute from `indicatorMeta.prev` (briefing-level current vs prev) — highest trust
  2. Compute from `computeChange()` using indicator_history consecutive months
  3. Briefing `meta.change` — only if non-zero (agent writes "0.0pp" placeholder for everything)
  4. Value fallback
- **`computeChange()` dedup:** Groups history records by YYYY-MM (calendar month), compares most recent 2 consecutive months. Prevents "last two distinct values" bug that skipped months of genuine "Held" periods
- **Briefing snapshot artifact filter:** `computeChange()` only uses periods matching `YYYY-MM-01`, `YYYY-MM`, or `YYYY` — excludes pipeline run-date artifacts like `2026-03-31`

### Enrichment Dropdowns (4 collapsible sections)
Stacked full-width `<details class="prov-enrich-detail">` elements below Key Indicators.

- **Wrapper:** `_enrichDropdown(title, rows, chgLabel)` — returns details/summary with count badge
- **Summary style:** 14px/600 DM Sans, caret indicator (`▸` → `▾`), count badge on right
- **Inner table:** `_natIndTable()` with `tldr-ind-table` class, 5-column full-width layout
- **Panel header hidden** inside details to avoid duplication

**1. Labour Market** — Change (M/M)
- Unemployment Rate, Employment Rate, Participation Rate, Average Hourly Wage
- All from StatCan 14-10-0287 / 14-10-0063

**2. Consumer Pulse** — Change
- CPI Index (StatCan 18-10-0004)
- Real Household Final Consumption (StatCan 36-10-0222)
- Total Consumption Expenditure (StatCan 36-10-0222)
- Household Disposable Income (StatCan 36-10-0226, annual)
- Debt-Service Ratio (StatCan 36-10-0226, annual, `XX.XX%`)
- Savings Rate (StatCan 36-10-0226, annual, computed from income-outlays)

**3. Housing & Construction** — Change
- Housing Starts (CMHC)
- Building Permits (Residential) (StatCan 34-10-0292, $K → `_fmtMillions()`)
- Building Permits (Non-Residential) (StatCan 34-10-0292)
- Capital Investment (StatCan 36-10-0104)

**4. Trade & Economy** — Change (Q/Q)
- Merchandise Exports, Merchandise Imports (StatCan 12-10-0121)
- Government Expenditure (StatCan 36-10-0222)

### Sector Signals Section
- **Content source:** `provData.sectorHighlights` (news-driven, written by briefing agent) — NOT pipeline/database data
- **Rendered as:** `.narrative` div with `addLeads()` to wrap lead sentences
- **Section meta:** Shows paragraph count (e.g., "3 sector updates")
- **Empty state:** Section hidden if no sectorHighlights content (≥20 chars)

### Project Pipeline Table
- **Columns (4):** Project | Sector | Value | Status
- No empty CITY column
- **Threshold filter:** `meetsThreshold()` — filters by province GDP threshold
- **New projects first:** Sorted by value descending within new/existing groups
- **NEW badge:** Prussian blue (#003153) background, white text, `tldr-freq-tag` class
- **Max rows:** 10 (up to 5 new + fill to 10 with existing)

### Real Data Sources (validated via StatCan WDS API)
All provincial data pulled from real StatCan tables, injected into `docs/data/indicators.json`:
- **Table 14-10-0063** — Employee wages by industry (provincial avg hourly wage)
- **Table 14-10-0287** — Labour force characteristics (unemployment, employment rate, participation rate)
- **Table 18-10-0004** — CPI (provincial)
- **Table 34-10-0292** — Building permits by type of structure
- **Table 36-10-0104** — Capital investment (national quarterly)
- **Table 36-10-0222** — Household sector selected indicators
- **Table 36-10-0226** — Household sector provincial (disposable income, DSR, savings rate)
- **Table 36-10-0402** — GDP by industry (provincial)
- **Table 12-10-0121** — International merchandise trade
- **Ontario Economic Accounts Table 3** — Quarterly real GDP (rows 42/43 for total level and QoQ growth)

### Pipeline additions (`tools/backfill_indicators.py`)
- Added vector IDs for `avg_hourly_wage_XX` × 10 provinces (14-10-0063)
- Added vector IDs for `bldg_permits_res_XX` + `bldg_permits_nonres_XX` × 10 provinces (34-10-0292)
- Added vector IDs for `household_disposable_income_XX`, `household_debt_service_ratio_XX`, `household_savings_rate_XX` × 10 provinces (36-10-0226)
- Added OEA Table 3 rows 42/43 extraction for `on_real_gdp` and `on_real_gdp_pct`

### Editorial Rules
- **No database/pipeline references** in callout text, sector signals, or chart narratives — news & public data driven only
- **Real StatCan data** in all tables — no synthetic or estimated values
- **Provincial-level data** preferred over national fallbacks
- **Period subtitles** on every row (e.g., "Feb 2026", "Q3 2025", "2024") — no blank cells
- **Source hyperlinks** in Prussian blue via `_srcLink()` — all StatCan tables auto-link to their WDS portal URLs

## Industries Tab (All 20 NAICS industries approved 2026-04-09)

The full Industries template lives in its own file to keep context lean when resuming Industries work: **[APPROVED_TEMPLATE_INDUSTRIES.md](./APPROVED_TEMPLATE_INDUSTRIES.md)**.

- **Reference industry:** Agriculture (NAICS 11) — 16-row Key Indicators table, 193-word 4-paragraph analysis, GDP trajectory chart, subsector chips attached to hero banner
- **Coverage:** All 20 NAICS industries locked — Goods (5): 11, 21, 22, 23, 31-33 · Services (15): 41, 44-45, 48-49, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 91
- **Per-industry Key Indicators row counts** (including the 2 universal GDP rows): 11=16, 21=15, 22=12, 23=17, 31-33=15, 41=12, 44-45=14, 48-49=12, 51=11, 52=14, 53=14, 54=12, 55=10, 56=11, 61=11, 62=11, 71=10, 72=11, 81=11, 91=13
- **Subsector chips:** All 20 industries display real M/M and Y/Y computed from StatCan 36-10-0434 (with documented proxy fallbacks for 16 of 60 subsector codes that aren't published at the exact NAICS level)
- **Status:** Locked. IND-04 (Agriculture baseline) + IND-05 (31-series all-industries backfill, indicator IDs 68590–68620) + IND-06 (subsector GDP populate) all complete. Next available indicator ID: 68621.
- **Do not duplicate the spec here** — single source of truth is `APPROVED_TEMPLATE_INDUSTRIES.md`.

## Markets Tab (Approved 2026-04-09)

The full Markets template lives in its own file to keep context lean when resuming Markets work: **[APPROVED_TEMPLATE_MARKETS.md](./APPROVED_TEMPLATE_MARKETS.md)**.

- **Sections (5):** Market Commentary, Equity Indices, Foreign Exchange, Government of Canada Yields, Commodities
- **Pill counts:** 9 equity indices, 7 FX pairs — each pill shows three labelled changes (1W / 1M / 1Y) inline (locked in MKT-20)
- **Yield curve:** 6 tenors (untouched, on existing pipeline cadence)
- **Commodities table:** 43 rows across 9 categories — Energy (7), Precious Metals (4), Diamonds (1), Base Metals (6), Agriculture (14), Livestock (4), Forest Products (2), Fisheries (1), Canadian Equity Proxies (4)
- **Data sources:** Yahoo Finance public chart endpoint (39 series), Bank of Canada Valet API (4 weekly indices), Statistics Canada WDS (canola monthly + diamonds Table 16-10-0020). All free, no API keys.
- **Status:** Locked. All 20 patches MKT-01 through MKT-20 documented in `PATCH_LOG.md`.
- **Do not duplicate the spec here** — single source of truth is `APPROVED_TEMPLATE_MARKETS.md`.

## Projects Tab (Approved 2026-04-10)

The full Projects template lives in its own file to keep context lean when resuming Projects work: **[APPROVED_TEMPLATE_PROJECTS.md](./APPROVED_TEMPLATE_PROJECTS.md)**.

- **Structure:** Single Prussian blue hero card (title + 5 stats + nested filter bar) → collapsible missing-project form → rounded-corner 9-column project table with Prussian blue column-header row
- **Hero stats (5):** Total Projects · Total Value · Under Construction · Approved · New This Week (all comma-formatted, billions include commas via `toLocaleString('en-CA')`)
- **Filter bar (nested in hero):** Search · Province · CMA · Sector · Status · Sort · "Above Threshold" toggle pill · Export CSV · "+ Report Missing"
- **Lazy loading:** default initial load is `projects_ontario.json` (~1.7 MB, largest province). Per-province files loaded on province filter change. `projects_all.json` (6 MB) only loaded when user explicitly picks "All Provinces". Double-load bug fixed (dropdown UI synced before filter logic runs). Removed a 6 MB hidden background fetch that was used only for dropdown count labels.
- **CMA filter:** dynamically populated from unique CMAs in the loaded province, refreshed on every province change. Selection preserved if still valid after repopulation.
- **Table:** 9 columns (Value / Project / Type / Province / Proponent / Status / Sector / Updated / Source). Prussian blue header row fills the rounded top corners via `overflow: hidden` on the wrap. Vertical column separators, 18px left padding, zebra row striping. Source column reads from `p.evidence[0].url` (NOT the empty `p.sources[]`).
- **Removed on lock:** Unsplash stock photo banner, verify-banner ("X% have source links"), Provinces stat, "Project Pipeline" separate section-header, sticky thead positioning
- **Status:** Locked. All 23 patches PROJ-01 through PROJ-23 documented in `PATCH_LOG.md`.
- **Do not duplicate the spec here** — single source of truth is `APPROVED_TEMPLATE_PROJECTS.md`.

## Calendar Tab (Approved 2026-04-10)

The full Calendar template lives in its own file to keep context lean when resuming Calendar work: **[APPROVED_TEMPLATE_CALENDAR.md](./APPROVED_TEMPLATE_CALENDAR.md)**.

- **Structure:** Prussian blue hero card (title + 2 stats, right-justified: **This Week** + **Next Week**) → "Month View" `.section-block` with reskinned 7-column grid (Prussian blue day-of-week header, Prussian blue inset ring on today, dark tooltip opening upward with no clipping) → "Scheduled Events" `.section-block` with filter bar (Search · Impact · Source · Scope) above a rounded 8px table with 5 columns (Date / Event / Source / Impact / Link) paginated at **10 rows per page**
- **Data sources:** Canadian `D.watchlist` from `briefing_latest.json` (~21 events) **merged with** `events_global.json` (90 events across 15 institutions — Fed FOMC, BLS, BEA, Census, Federal Reserve Board, ECB, BoE, and 8 Canadian provincial budgets). Merge dedup by `(date + event_name)`. Source of truth is `config/events_global_schedule.json`; the pipeline rewrites `docs/data/events_global.json` on every run via `export_events_global()` in `tools/export_dashboard.py`.
- **Filter bar:** lives above the events table (not inside the hero). Filter changes reset pagination to page 1. Source dropdown auto-populates from unique `institution` values so new pipeline data flows through without frontend edits.
- **Pipeline bug fixed in the same session:** `tools/export_dashboard.py` had been accidentally truncated on 2026-04-02 (commit `def2ea2`), removing `export_signals` body + `export_all` + `_validate_output` + `__main__`. Restored from `b26dc7a` and extended with `export_events_global()`. Pipeline imports now unblocked. See CAL-19 through CAL-23 in PATCH_LOG.
- **Removed on lock:** Unsplash stock photo banner, 5-stat hero (Upcoming, High Impact, Next BoC, Next StatCan dropped; This Week + Next Week kept), filter bar nested in hero (moved to events section), light-theme tooltip (reverted to dark global rules), `overflow: hidden` on calendar grid (let tooltips escape), `.section-meta` "April 2026" next to Month View heading (month name is still shown inside the calendar nav bar)
- **Status:** Locked. All 31 patches CAL-01 through CAL-31 documented in `PATCH_LOG.md`.
- **Do not duplicate the spec here** — single source of truth is `APPROVED_TEMPLATE_CALENDAR.md`.

## Data Explorer Tab (Approved 2026-04-10)

The full Data Explorer template lives in its own file to keep context lean when resuming Data Explorer work: **[APPROVED_TEMPLATE_EXPLORER.md](./APPROVED_TEMPLATE_EXPLORER.md)**.

- **Structure:** Single Prussian blue hero card (title + 4 stats) → six `.section-block`s covering StatCan Key Economic Indicators · Provincial Indicator Explorer · Ontario Economic Accounts · Quebec Economic Accounts (ISQ) · Provincial Raw Indicators · StatCan Table Search (paginated 5-column V-code table)
- **Hero stats (4):** Indicators (713, from `_indJsonCache.indicators.length`) · V-Codes (125, from `VCODE_INDEX.length`) · StatCan Tables (4,908, from `_fullTableDir.length + VCODE_INDEX.length`) · Updated (Mar 31, from `_indJsonCache.statcan_latest.updatedAt`). All real, no fabrication.
- **Pipeline work:** New `export_statcan_tables(conn, output_dir)` function in `tools/export_dashboard.py` reads `config/statcan_table_registry.csv` (4,908 rows), filters `Status=='Current'`, maps to `{t,n,k,c,f,g}` compact shape, writes `docs/data/statcan_tables.json` as a bare top-level array (1,493 KB). Wired into `export_all()` with try/except. This is the first time `statcan_tables.json` has existed on disk — the frontend loader had been fetching it silently with a 404 since launch, leaving the "Full Directory" search always empty.
- **V-code search table:** 5 columns (V-Code · Table · Title · Category · Link) in a rounded 8px wrap with Prussian blue thead, `#e8eef4` hover, `#f9fafb` zebra. Paginated at `EXP_PAGE_SIZE=10` with `‹ Prev` / `Page X of Y` / `Next ›`. Drops the old 25-result hard cap — `_expSearchAll()` returns the full sorted match set. Enter keypress and category chip clicks both reset to page 1.
- **Inline-style cleanup:** Full pass — every `style="..."` blob in the Explorer-related JS renderers (`renderIndicatorExplorer`, `loadIndExpData`, `renderExplorer`, `_renderProvExplorer`, `_loadProvExpData`, `_renderOeaSection`, `_renderOeaLatestTable`, `_loadOeaData`, `_renderIsqSection`, `_renderIsqLatestTable`, `_loadIsqData`, `window._doVcodeSearch`, `provIndicatorSection` innerHTML) replaced with scoped `#tab-explorer` classes. Zero inline styles remain in Explorer renderers.
- **Removed on lock:** Unsplash stock photo banner, dead `_renderExplorerStats()` helper, dead `#explorerStats` div, the three broken "Total Tables / Curated / Full Directory" pills, the 25-result cap on V-code search, hand-crafted `#2563EB` accent blue (all usages now `#003153`), hand-crafted `#c0c0c0`/`#f0f0f0` select styling (all usages now white/`#d5dbe3`), `.mkt-section` card wrappers (replaced with `.exp-card`), hard-coded 15px h3 card titles (replaced with `.exp-card-title`).
- **Status:** Locked. All 13 patches EXP-01 through EXP-13 documented in `PATCH_LOG.md`. All 8 main-nav tabs now locked.
- **Do not duplicate the spec here** — single source of truth is `APPROVED_TEMPLATE_EXPLORER.md`.
