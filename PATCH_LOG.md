# Patch Log — Dashboard Review

Tracks issues found during page-by-page review. Each entry includes the page, issue description, and status.

## Status Key
- [ ] Open
- [x] Fixed

---

## TL;DR Tab

### Numbers at a Glance — Markets view
- [x] **TLDR-01**: Markets tab — all commodity/equity/FX rows showed empty values. Root cause: data uses `val` and `mm` fields, code looked for `price`/`value` and `change`. Fixed field mapping in `_tldrBuildMarketsTable()`.
- [x] **TLDR-02**: Markets tab — removed "Next Release" and "Reference Period" columns (not meaningful for daily snapshots).

### Numbers at a Glance — Key Indicators view
- [x] **TLDR-03**: Key Indicators tab — removed "Next Release" column (entirely empty).
- [x] **TLDR-04**: Key Indicators tab — added fallback source map so all rows show sources (Bank of Canada, Statistics Canada, CMHC, Conference Board).

### This Week's Key Data section
- [x] **TLDR-05**: All rows showed empty values. Same root cause as TLDR-01 — fixed field mapping in `_tldrBuildWeeklyDataTable()`. Rows without values are now skipped.
- [x] **TLDR-06**: Removed "Next Release" and "Reference Period" columns.

### Projects section
- [x] **TLDR-07**: Projects without assigned values showed "N/D". Added `hasValue` filter so only projects with dollar values appear in the table.

### Markets table formatting
- [x] **TLDR-08**: Separated value and unit into distinct columns. Added `_parseMarketVal()` parser.
- [x] **TLDR-09**: Normalized all change values to consistent `+X.X%` / `-X.X%` format via `_normalizeChg()`. Removed "M/M", "day", "W/W" suffixes and text descriptions.
- [x] **TLDR-10**: Commodities, Currencies, and Indices separated into distinct labeled sections with `tldr-mkt-group-label` dividers.

### Data gaps filled
- [x] **TLDR-11**: Filled W/W % changes for all commodities, FX, and indices using timeseries data and prior-week calculations. Only Lumber required web search (prior ~$533, current ~$510 = -4.3%).
- [x] **TLDR-12**: Fixed Wheat unit — parser now handles `607.5c/bu` cent notation correctly as `USc/bu`.
- [x] **TLDR-13**: Added FX units ("rate") and index units ("pts") via `forceUnit` mapping.

### Table structure & alignment
- [x] **TLDR-14**: Unified all tables to 5-column structure: Indicator, Unit/Frequency, Value, Change, Source. `table-layout:fixed` with explicit `th` widths ensures columns align across all tables.
- [x] **TLDR-15**: Key Indicators table — change column split into short value + context subtitle under indicator name (`ind-t-name-ctx`). Context includes period (e.g., "2nd consecutive monthly gain - Jan 2026"). Data stored as separate `change` and `changeContext` fields in JSON.
- [x] **TLDR-16**: This Week's Key Data moved to top of Key Indicators view (removed from Markets tab to avoid duplication).
- [x] **TLDR-17**: "KEY ECONOMIC INDICATORS" subtitle label added above the indicator table.
- [x] **TLDR-18**: Em dash (`--`) used as directional arrow for "Held" indicators.

### Column alignment & spacing
- [x] **TLDR-19**: All column headers left-justified except Value (right-justified to match data).
- [x] **TLDR-20**: Change column left-justified with generous left padding (16px) for visual separation from Value.
- [x] **TLDR-21**: Unit/Frequency column right-aligned and tight to Value column, with more space separating it from Indicator.
- [x] **TLDR-22**: Source column left-aligned, tight to Unit/Frequency — closes the white space gap.
- [x] **TLDR-23**: Uniform 13px font size across all table cells (td, ind-t-name, ind-t-val, ind-t-unit, ind-t-chg, ind-t-src).
- [x] **TLDR-24**: Column widths: Indicator 24%, Unit/Freq 14%, Value 16%, Change 20%, Source 22%.

### Sources & encoding
- [x] **TLDR-25**: Sources hyperlinked in Prussian blue (#003153) — Bank of Canada, Statistics Canada, CMHC, Conference Board, yfinance all link to their respective data portals. Added `_srcLink()` helper and `ind-src-link` CSS.
- [x] **TLDR-26**: Fixed 694 mojibake instances in briefing JSON — em dashes (U+00E2 U+20AC U+201D -> U+2014), en dashes (U+00E2 U+20AC U+201C -> U+2013), and apostrophes (26 instances).

### Files changed
- `docs/js/app.js` — rendering logic (all table builders, parsers, normalizers, source link helper)
- `docs/index.html` — CSS (table layout, column widths, alignment, spacing, font sizes, link styles)
- `docs/data/briefing_latest.json` — data fixes (W/W changes, change/changeContext split, encoding)

---

## National Tab

### Canada subtab
- [x] **NAT-01**: Removed CA flag emoji from "Canada — National" indicator panel title.
- [x] **NAT-02**: Indicator table rewritten to use `tldr-ind-table` class (matching TL;DR styling). Uses `metaRow()` helper pulling from `indicatorMeta` + `metrics` dynamically.
- [x] **NAT-03**: BoC Rate displayed as 2.3% due to `fmtNum` rounding 2.25 → 2.3. Fixed by using `san()` instead of `fmtNum()` for pre-formatted values in `_natIndTable`.
- [x] **NAT-04**: Participation Rate change showed +58.0pp (was computing from wrong province SK vs national). Fixed via `indicatorMeta` as primary data source.
- [x] **NAT-05**: Employment Change missing change value. Added `indicatorMeta.employmentChange` with `-160,000` (swing from prior +76,000).
- [x] **NAT-06**: Building Permits showed stale data from Apr 2007. Fixed by adding `indicatorMeta.buildingPermits` with value `$13.3B`, change `+4.8%`, period `Jan 2026`.
- [x] **NAT-07**: Unemployment chart not rendering — `timeseries.json` had no `unemployment_rate` key. Built national series from `nat_unemployment` indicator history (26 data points Jan 2024–Feb 2026).
- [x] **NAT-08**: Indicator panel padding increased (`padding: 8px 16px 16px`) — text was too close to edges.
- [x] **NAT-09**: Enrichment cards (Labour Market, Consumer Pulse, Housing, Trade) converted from simple metric cards to structured `tldr-ind-table` tables with Indicator, Frequency, Value, Change (M/M), Source columns.
- [x] **NAT-10**: All enrichment card data gaps filled — 18 metric values + 18 change values populated from briefing data, indicator history, and web search.
- [x] **NAT-11**: "Active Residential Projects" row removed from Housing table.
- [x] **NAT-12**: Trade Balance change fixed from "Widened" to numeric `-$2.3B`.
- [x] **NAT-13**: National Analysis font size matched to Policy Developments (both 15px). CSS rule `#tab-national .dash-narrative p{font-size:15px}`.
- [x] **NAT-14**: Project pipeline filtered by province GDP thresholds via `meetsThreshold()`. New projects listed first with "NEW" tag (Prussian blue badge).
- [x] **NAT-15**: Fixed duplicate `const PROV_THRESHOLDS` declaration that crashed entire JS file. Used existing `meetsThreshold` at line 101 via alias.

### Global subtabs (US, China, EU, UK)
- [x] **NAT-16**: Removed all flag emojis from `COUNTRY_SUBTABS` and `global[].emoji` data.
- [x] **NAT-17**: Added `'China / Asia':'china'` to `REGION_MAP` — China subtab was failing to match data.
- [x] **NAT-18**: Filled all indicator data gaps: GDP, CPI, unemployment changes for all 4 regions. Trade balance values added (US -$131.4B, China +$170.5B, EU +€15.5B, UK -£7.5B).
- [x] **NAT-19**: Trade balance changes fixed to numeric values: US `▼ -$33.0B`, EU `▲ +€5.3B`, UK `▼ -£1.7B`.
- [x] **NAT-20**: Removed value-as-change fallback (line 2321) that showed unemployment value as its own change.
- [x] **NAT-21**: Removed Productivity Growth row (no data source available).
- [x] **NAT-22**: All sources hyperlinked — added BEA, BLS, Federal Reserve, Census Bureau, NBS, PBOC, GAC, Eurostat, ECB, ONS, BoE to `_srcUrls` map.
- [x] **NAT-23**: Global charts fixed — `GLOBAL_CHART_CFG` updated with `tsKeys` array for fallback keys. Chart init tries multiple keys, picks source with most data. Added `china_pmi` timeseries (12 months). Graceful fallback to last 24 entries when recent data insufficient.

### Files changed
- `docs/js/app.js` — `_natIndTable`, `_renderCanadaSubtab`, `_renderNatEnrichmentCards`, `_renderGlobalSubtab`, `COUNTRY_SUBTABS`, `GLOBAL_CHART_CFG`, `_initGlobalInsightChart`, `meetsThreshold` alias, `_srcUrls` map
- `docs/index.html` — CSS (indicator panel padding, narrative font size, responsive breakpoint)
- `docs/data/briefing_latest.json` — `indicatorMeta` entries, `metrics` enrichment values/changes, global indicator data, trade balance changes, emoji removal
- `docs/data/timeseries.json` — `unemployment_rate` series, `china_pmi` series

## Provinces Tab

### Navigation
- [x] **PROV-01**: Replaced vertical sidebar with horizontal sub-nav bar (pill tabs for 13 provinces + 3 territories as short codes: ON, QC, AB, BC, SK, MB, NS, NB, NL, PEI, YT, NWT, NU).
- [x] **PROV-02**: Sub-nav bar connects flush to main nav (zero gap), charcoal background (#2d3748) with darker accent border (#1a202c), white pill text, selected pill underlined in white.
- [x] **PROV-03**: Static positioning — scrolls with page content (does not follow user down the page).
- [x] **PROV-04**: Territories rendered same size/font as provinces, slightly lighter opacity for hierarchy. Vertical separator between provinces and territories.
- [x] **PROV-05**: Full names shown on hover via `title` attribute; hero card displays full province name.

### Provincial Analysis narrative
- [x] **PROV-06**: Removed `sectorHighlights` from analysis narrative (moved to dedicated Sector Signals section to avoid duplication).
- [x] **PROV-07**: Hoisted `addLeads()` and `allSrc` outside the conditional so they're reusable by Sector Signals section.
- [x] **PROV-08**: Bold lead sentences with em dash separators, superscript citation footnotes.

### Chart Callout
- [x] **PROV-09**: Restructured chart area to match TL;DR callout pattern — text component on top, chart below, Prussian blue left border, light blue background.
- [x] **PROV-10**: Chart callout text pulls from `insightCharts[0].reasoning` with database/pipeline references stripped.
- [x] **PROV-11**: `_buildProvCalloutText()` extracts 1 supporting sentence from province narrative fields (analysis, labourDeepDive, consumerPulse, sectorHighlights, tradeExposure, marketContext) sharing topic keywords with the chart and containing distinct data points.
- [x] **PROV-12**: `_splitSentences()` protects decimals ("7.6"), acronyms ("U.S."), and dollar amounts from false period splits.
- [x] **PROV-13**: Chart subtitle updates dynamically to reflect only datasets that actually render; minimum 2 points required for a series to render.
- [x] **PROV-14**: Uses `provData.insightCharts[0]` as primary source with legacy `insightChart` fallback.

### Key Indicators Table
- [x] **PROV-15**: Reordered rows into logical groups — GDP (4 rows), Labour (4 rows), Prices (1 row), Housing & Investment (3 rows), Trade (1 row).
- [x] **PROV-16**: GDP Growth row uses quarterly QoQ growth (`real_gdp_qoq`) when available, falls back to annual YoY (Ontario: Q3 2025 +0.5% from Ontario Economic Accounts).
- [x] **PROV-17**: Added 5 structural indicators — Provincial GDP, GDP Goods-Producing, GDP Services-Producing (derived), Capital Investment, Trade Balance. All formatted via `_fmtMillions()` to `$B`/`$T`.
- [x] **PROV-18**: Added Average Hourly Wage row from StatCan 14-10-0063 (`$X.XX/hr` format, MoM change).
- [x] **PROV-19**: CPI row shows index level with computed MoM change from `indicatorMeta.prev`.
- [x] **PROV-20**: Housing Starts uses real numeric value from indicator_history; filters descriptive-text ("Down 28% YoY").
- [x] **PROV-21**: Building Permits row derives from StatCan 34-10-0292 (sum of residential + non-residential).
- [x] **PROV-22**: Zero-change values display as `— Held` instead of "— 0.0pp".
- [x] **PROV-23**: GDP Growth value-is-change relabeled as `— YoY` tag.
- [x] **PROV-24**: N/A rows filtered out; indicator count in header shows actual filtered count.

### pchg() / computeChange() fixes
- [x] **PROV-25**: `pchg()` rewritten with priority order — (1) compute from `indicatorMeta.prev`, (2) compute from indicator_history consecutive months, (3) use briefing meta.change only if non-zero, (4) value fallback. Previously trusted agent-written "0.0pp" placeholder.
- [x] **PROV-26**: `computeChange()` dedupes history by YYYY-MM (calendar month) not by value — ensures comparing consecutive months.
- [x] **PROV-27**: `computeChange()` filters out briefing snapshot artifacts (only uses `YYYY-MM-01` / `YYYY-MM` / `YYYY` periods; excludes pipeline run-dates).

### Enrichment Dropdowns
- [x] **PROV-28**: Replaced two-col grid with stacked full-width collapsible `<details>` dropdowns with count badges.
- [x] **PROV-29**: **Labour Market** — Unemployment, Employment Rate, Participation Rate, Average Hourly Wage.
- [x] **PROV-30**: **Consumer Pulse** — CPI Index, Real Household Final Consumption, Total Consumption Expenditure, Household Disposable Income, Debt-Service Ratio, Savings Rate.
- [x] **PROV-31**: **Housing & Construction** — Housing Starts, Building Permits (Residential), Building Permits (Non-Residential), Capital Investment.
- [x] **PROV-32**: **Trade & Economy** — Merchandise Exports, Merchandise Imports, Government Expenditure.
- [x] **PROV-33**: Removed Industry Pipeline dropdown (was pipeline-data based).

### Sector Signals Section
- [x] **PROV-34**: Replaced pipeline-based sector counts with news-driven narrative from `provData.sectorHighlights`.
- [x] **PROV-35**: Shows sector-labeled paragraphs with bold lead sentences and em dashes.

### Project Pipeline & Policy
- [x] **PROV-36**: Removed empty CITY column — 4 columns (Project, Sector, Value, Status).
- [x] **PROV-37**: Projects filtered by province GDP threshold via `meetsThreshold()`.
- [x] **PROV-38**: New projects listed first with Prussian blue "NEW" badge.
- [x] **PROV-39**: Added dedup by title on Policy Developments accordion.

### Real StatCan Data Injection (all 10 provinces)
- [x] **PROV-40**: Fetched real current-period data from StatCan WDS API and injected into `indicators.json`:
  - **Avg Hourly Wage** × 10 (Table 14-10-0063, Feb 2026)
  - **Building Permits Residential** × 10 (Table 34-10-0292, Jan 2026 SAAR)
  - **Building Permits Non-Residential** × 10 (Table 34-10-0292, Jan 2026 SAAR)
  - **Household Disposable Income** × 10 (Table 36-10-0226, 2024 annual)
  - **Debt-Service Ratio** × 10 (Table 36-10-0226, 2024 annual)
  - **Savings Rate** × 10 (Table 36-10-0226, 2024 annual, computed)
  - 60 new indicator rows total
- [x] **PROV-41**: Computed YoY changes for 2024 annual indicators using 2023 prior values.
- [x] **PROV-42**: Injected `real_gdp_qoq` row for Ontario from Ontario Economic Accounts Table 3 row 42/43 (Q3 2025 +0.5%).
- [x] **PROV-43**: Updated 30 LFS rows (Employment/Participation/Unemployment × 10 provinces) with real Feb 2026 values and `previous_value`. Cleaned 138 stale history rows with run-date periods.

### Pipeline (tools/backfill_indicators.py)
- [x] **PROV-44**: Added StatCan WDS vector IDs for provincial Avg Hourly Wage (14-10-0063, validated).
- [x] **PROV-45**: Added StatCan WDS vector IDs for provincial Building Permits (34-10-0292).
- [x] **PROV-46**: Added StatCan WDS vector IDs for provincial Household Sector (36-10-0226).
- [x] **PROV-47**: Added OEA Table 3 rows 42/43 extraction for `on_real_gdp` and `on_real_gdp_pct` (total Ontario real GDP and official QoQ growth rate).

### Encoding
- [x] **PROV-48**: Fixed 26 mojibake instances (`Â·` → `·`) in briefing_latest.json.

### Files changed
- `docs/js/app.js` — `_renderProvContent`, `renderProvinces`, `pchg()`, `computeChange()`, `_fmtMillions`, `_fmtPersons`, `_provHist`, `_provHistVal`, `_provHistChg`, `_buildProvCalloutText`, `_splitSentences`, `buildInsightStrip`, `buildAgentInsightStrip`, `_enrichDropdown`, wage/permits/household/GDP lookups, sector signals narrative
- `docs/index.html` — CSS for `.prov-bar` (charcoal static sub-nav), `.prov-pill`, `.prov-enrich-detail`, flush-connect fix for mobile breakpoint
- `docs/data/indicators.json` — 60 new indicator rows, 30 updated LFS rows, 1 `real_gdp_qoq` row, 138 stale history rows cleaned
- `docs/data/briefing_latest.json` — 26 mojibake fixes
- `tools/backfill_indicators.py` — 60+ new StatCan WDS vector IDs, OEA Table 3 total GDP extraction

## Industries Tab
_(pending)_

## Markets Tab
_(pending)_

## Projects Tab
_(pending)_

## Events Tab
_(pending)_
