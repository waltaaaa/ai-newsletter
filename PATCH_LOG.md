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

### Agriculture (NAICS 11) approved 2026-04-09 as replication template
Full template spec locked in [APPROVED_TEMPLATE_INDUSTRIES.md](./APPROVED_TEMPLATE_INDUSTRIES.md). Replication to the other 19 NAICS industries pending in a new session.

- [x] **IND-01**: Every industry showed the same cross-sector diverging GDP bar chart (same 20 NAICS bars, only the highlighted sector differed). User feedback: each industry needs a chart relevant to its own story, dynamic per week, sourced primarily from StatCan. Fix approach:
  1. Extended `.claude/skills/tldr-charts/SKILL.md` — added Industries output section, promoted `indicators.json` history to primary data source, added `multi_line` chart type (normalized to 100 at window start), added `callout` field (user-facing, distinct from `reasoning`), added industry-NAICS→dataKey mapping table, extended execution procedure to iterate the 20 industries. Preserved pre-existing `context: fork` frontmatter addition.
  2. Invoked the extended skill to regenerate industry `insightCharts[0]` specs in `docs/data/briefing_latest.json`.
  3. Rewrote `_renderIndContent()` chart block in `docs/js/app.js` — consumes `industry.insightCharts[0]` instead of synthesizing the cross-sector bar client-side. New `_buildIndChart(spec)` function dispatches on `chartType` (`line`, `multi_line`, `bar`, `diverging_bar`). For `multi_line` each series is normalized to 100 at the window start so trajectories can be compared. Callout text pulled from `insightCharts[0].callout`.
  4. Resolved data at render time from `indicators.json` history (when `dataSource: "indicators"`) or `timeseries.json` (when `dataSource: "timeseries"`), capped at the `window` field (max 24 months).
  5. Follow-up (not in this session): next pipeline run will regenerate industry charts automatically via the extended skill.
- [x] **IND-02**: Key Indicators table was generic across every industry (same 5 rows: Real GDP M/M, Y/Y, Subsectors Tracked, Active Projects, Pipeline Value). User feedback: table should be industry-specific, and subsectors should be attached to the banner at the top (the hero card with industry growth stats) rather than living in a separate section. Fix:
  1. Added `IND_KEY_INDICATORS` NAICS→rows mapping in `docs/js/app.js` with industry-specific indicator specs. Each spec has `{label, key, source, unit, srcLabel, srcUrl}` — primarily StatCan (`source: "indicators"`) with some commodity / FX / TSX / credit spread rows from `source: "timeseries"`.
  2. Added `_indResolveKeyRow(spec, tsData)` helper that resolves each spec into a table row. Drops rows where the latest period is older than 18 months (staleness cutoff). For indicators-source rows, reads current value from `indicators[]` and M/M change from `computeChange()`. For timeseries-source rows, reads latest point and computes 30-day percent change.
  3. Added `_indFmtKeyValue(val, unit)` formatter handling `$M` (→ B/T), `thousands` (→ K), `%`, `pp`, `bps` (value × 100 for percentage-point storage), `rate`, `points`, `index`, commodity USD units.
  4. Rewrote Key Indicators table rendering in `_renderIndContent()` to: (a) always show Real GDP M/M + Y/Y at top, (b) insert industry-specific rows resolved from `IND_KEY_INDICATORS[code]`, (c) always show Active Projects + Pipeline Value at bottom.
  5. Rewrote hero card layout: new `industry-header-top` row wraps title + 4 stat columns (existing layout), followed by new `industry-subsector-strip` row containing per-subsector chips (name, NAICS code, M/M badge colored green/red/grey for up/down/NA).
  6. Removed the standalone "Subsector Detail" table section (subsectors moved up to the hero card).
  7. Added CSS in `docs/index.html` for `.industry-header-top`, `.industry-subsector-strip`, `.ind-strip-label`, `.ind-strip-chips`, `.ind-subsector-chip` with up/down/flat color variants.
  8. Edge cases: "±0.0%" / "±0.0pp" display for near-zero M/M changes (was "+0.0%"/"-0.0%"). Credit spread bps conversion (values stored as percent — 3.42 → 342 bps). Staleness cutoff tightened from 36mo to 18mo so Oct 2023 quarterly building investment data and May 2023 lumber data are hidden.
  9. Known follow-up: `computeChange()` returns empty for `cpi_national` — flagged for later industries (Retail, Accommodation) when we replicate.
- [x] **IND-03**: Agriculture Key Indicators table was still too generic for data-rich industries. User requested hyper-specific indicators per industry (example: "fertilizer costs or growing days for agriculture"). Fix:
  1. Spawned a subagent to fetch 10 new Agriculture-specific data series from free public APIs: StatCan WDS (`farm_cash_receipts` 32-10-0046, `ag_exports_current` 12-10-0176, `ag_employment` 14-10-0022, `ag_hourly_wage` 14-10-0063, `farm_input_price_index` + `fertilizer_price_index` 18-10-0258), Yahoo Finance (`live_cattle` LE=F, `lean_hogs` HE=F), StatCan 32-10-0077 (`canola` — Yahoo RS=F was delisted so monthly Saskatchewan prices used as fallback), and ECCC historical weather (`ag_gdd_prairie_2025` — 2025 full growing season GDD total averaged across Saskatoon/Winnipeg/Lethbridge, base 5°C, compared to 2024).
  2. Injected 8 new indicator rows + 134 history rows + 3 new timeseries keys into `docs/data/indicators.json` and `docs/data/timeseries.json`. Next available id: 68590. Pre-existing 674 indicators, 44,718 history rows, and 117 timeseries keys all preserved byte-for-byte (verified).
  3. Expanded `IND_KEY_INDICATORS['11']` in `docs/js/app.js` from 3 rows to 13 industry-specific rows. Total rendered Agriculture table: **16 rows** (2 universal GDP anchors + 13 ag-specific + GDD retrospective). Active Projects and Pipeline Value dropped from the table per user feedback — they live in the hero banner only.
  4. Applied a structural change to the Key Indicators table builder (in `_renderIndContent`): universal Active Projects + Pipeline Value rows are no longer appended to ANY industry's Key Indicators table. This applies across all 20 industries going forward.
  5. Extended `_indFmtKeyValue()` formatter with unit handlers for `$/hr` (→ `$X.XX/hr`), `CAD/tonne` (→ `C$X/t`), `gdd` (→ `X,XXX GDD`), `USD` (→ `$X.XX`). Also added `/lb`, `/bbl`, `/oz`, `/MMBtu`, `/MBF`, `/bu`, `/t` suffixes to the USD-per-unit handlers (was just showing `$X.XX`).
  6. Fixed wage change format bug: `computeChange()` misdetects wage values ($27.27/hr) as rates because they're <100 and returned a `+0.7pp` display instead of the actual `+2.6%` M/M. Added a wage-unit override in `_indResolveKeyRow()` that recomputes the percent change manually from history when `spec.unit === '$/hr'`.
  7. Added optional `chgLabel` field to the spec schema so annual/retrospective comparisons can show context (e.g., GDD shows `+2.6% vs 2024`). Applied to the Agriculture GDD row.
  8. Added optional `freq` field to the spec schema so specs can override the frequency heuristic (used for Canola which is monthly despite being a timeseries key).
  9. Relabeled "Potash (Nutrien)" → "Potash (Nutrien stock)" to honestly represent that it's the Nutrien equity price (NTR), not a physical potash commodity index.
- [x] **IND-04**: Agriculture analysis narrative was 72 words across 2 paragraphs, too thin to convey the full sector story given the rich new data we fetched. User asked for +50, then bumped cap to 200. Fix:
  1. Added a third paragraph (~59 words) to `goodsIndustries[11].analysis` covering farm cash receipts, agriculture employment, average hourly wage, farm input price index and fertilizer sub-index, and the 2025 Prairie growing season GDD vs 2024.
  2. Added a fourth paragraph (~55 words) covering crop commodity price moves (wheat +5.7%, corn +7.7%, soybeans +2.1% over 30 days), livestock prices (live cattle $2.48/lb +6.5%, lean hogs $1.04/lb +8.4%), canola (C$619/t Jan 2026), and agricultural merchandise exports ($3.29B Feb 2026, +5.4% M/M).
  3. Final word count: **193 words across 4 paragraphs**. Each paragraph has a bold lead sentence wrapped in `<span class="lead-sentence">` + em-dash separator matching the Provinces pattern.
  4. All new content is factual per editorial policy — no editorializing, no recommendations, all numbers sourced from the newly injected indicators/timeseries data.

### Files changed (IND-01 through IND-04)
- `docs/js/app.js` — `_renderIndContent`, `renderIndustries`, new `IND_KEY_INDICATORS` mapping, `_indResolveKeyRow`, `_indFmtKeyValue`, `_indResolveIndicatorsSeries`, `_indWindowMonths`, `_indNormalize`, `_indFmtMonthLabel`, `buildIndInsightStrip`, `renderIndInsightChart`
- `docs/index.html` — CSS for `.industry-header-card` (flex column), `.industry-header-top`, `.industry-subsector-strip`, `.ind-subsector-chip` color variants
- `docs/data/briefing_latest.json` — 20 industry `insightCharts[0]` specs injected by extended `tldr-charts` skill; Agriculture `analysis` narrative expanded from 72 → 193 words
- `docs/data/indicators.json` — 8 new Agriculture indicator rows + 134 new history rows (IDs 68582–68589). All pre-existing data preserved.
- `docs/data/timeseries.json` — 3 new keys: `canola` (300 points), `live_cattle` (503 points), `lean_hogs` (503 points). All pre-existing keys preserved.
- `.claude/skills/tldr-charts/SKILL.md` — extended with Industries output section, `multi_line` chart type, `indicators.json` as primary data source, `callout` field in schema, Industry → Primary Data Key Map, Industry Chart Selection Procedure (preserved existing `context: fork` pending change)
- `APPROVED_TEMPLATE_INDUSTRIES.md` — NEW standalone template file documenting the approved Industries layout (used by future sessions to replicate to the other 19 NAICS industries)
- `APPROVED_TEMPLATES.md` — Industries Tab stub updated to point at the standalone template file

- [x] **IND-05**: Replicated the approved Agriculture template to the other 19 NAICS industries in a single session. Every industry's Key Indicators table was expanded from ~1–7 thin rows to 10–17 industry-specific rows, and every industry's `analysis` narrative was expanded from 30–90 words to 120–160 words across three paragraphs. Data availability:
  - Background subagent fetched 31 new data series from StatCan WDS API (free, no key, zero cost): 16 sector employment series (14-10-0022), national avg hourly wage (14-10-0063), retail/wholesale/manufacturing sales (20-10-0056, 20-10-0074, 16-10-0047), quarterly building investment refresh for 5 categories (34-10-0293), residential + non-residential building permits national (34-10-0292), household disposable income/savings rate (36-10-0112), household debt-service ratio (11-10-0065), and total job vacancies (14-10-0372, monthly successor to the inactive 14-10-0326). Starting next_id was 68590; 31 new indicator rows + 636 history rows appended (IDs 68590–68620). All pre-existing data preserved byte-identically; baseline keys (`gdp_agriculture`, `farm_cash_receipts`, etc.) unchanged; stale 2003 export rows and 2023 building investment rows left in place alongside fresh entries so the renderer's max-period resolver picks the new values automatically.
  - Four StatCan table substitutions handled automatically: 20-10-0008 → 20-10-0056 (retail sales), 34-10-0175 → 34-10-0293 (building investment), 34-10-0066 → 34-10-0292 (building permits), 14-10-0326 → 14-10-0372 (job vacancies). Vector IDs and coordinates documented in `tmp_inds_fetch/FETCH_REPORT.md`.
  - NAICS-51/71 and NAICS-55/56 employment are only published at aggregate (Info-Culture-Recreation and Business-Building-Support Services respectively) in table 14-10-0022. To avoid showing identical employment numbers on two different industry pages, the row is kept on 51 and 56 (the natural home of each aggregate) and omitted from 71 and 55. Comments in `IND_KEY_INDICATORS` document the omission and reference table 36-10-0489 as the more granular alternative if needed later.
- Per-industry key indicator row counts (including the 2 universal GDP rows): 11=16, 21=15, 22=12, 23=17, 31-33=15, 41=12, 44-45=14, 48-49=12, 51=11, 52=14, 53=14, 54=12, 55=10, 56=11, 61=11, 62=11, 71=10, 72=11, 81=11, 91=13. Screenshots at `C:/Users/walte/AppData/Local/Temp/ind_<code>_hero.png` and `ind_<code>_keyind.png` for user review; row-dump JSON at `C:/Users/walte/AppData/Local/Temp/ind_rows_all.json`.

### Files changed (IND-05)
- `docs/js/app.js` — `IND_KEY_INDICATORS` expanded from Agriculture + 19 thin entries to the full 20-industry template
- `docs/data/indicators.json` — 31 new indicator rows + 636 new history rows (IDs 68590–68620)
- `docs/data/briefing_latest.json` — 19 industry `analysis` + `industrySources` blocks rewritten (Agriculture code 11 untouched)
- `tmp_inds_fetch/` — fetch scripts, metadata dumps, and `FETCH_REPORT.md` (new working directory, parallel to `tmp_agri_fetch/`)

- [x] **IND-06**: Subsector chips across all 20 industries were mostly showing "N/A" for their month-over-month change (only 5 of 60 had populated values: 111, 113, 211, 445, 531, 541, 415). Root cause: the original briefing generator didn't have 3-digit/4-digit NAICS GDP data. Fix: background subagent pulled `StatCan 36-10-0434` Real GDP by Industry (monthly, chained 2017 $, SAAR) and resolved vectors for all 60 target subsector codes, fetched 14 months per vector, computed M/M and Y/Y, and injected into each industry's `subsectors[]` array in `briefing_latest.json`. Coordinate template was `1.1.1.<dim4>.0.0.0.0.0.0` — dim1=Canada, dim2=SAAR, dim3=Chained 2017 $, dim4=NAICS (249 members). 60/60 PASS with latest period 2026-01-01.
  - **Proxy fallbacks (16 of 60) documented in `tmp_subs_fetch/FETCH_REPORT.md`:** cube publishes several subsectors only at an aggregate level. Proxies used where the exact NAICS cell isn't available:
    - 236/237/238 → 23A/23X/23D (construction subtype aggregates, not NAICS-3)
    - 452 → 455 (NAICS 2022 renumber)
    - 511 → 513 (NAICS 2022 renumber)
    - 522/523/524 → 52BX/52C/5241 aggregates
    - 541 → 54 parent (legal and scientific detail not published)
    - 551/5511/55111 → 55 parent (all three share the same 2-digit series)
    - 5621 → 562 parent
    - 711/712 → 71A (performing arts + heritage combined)
    - 7211 → 721 parent
- Agriculture `analysis` locked template reference "Farm cash receipts totaled" verified untouched post-write. `goodsIndustries` count = 5, `servicesIndustries` count = 15, all other top-level briefing fields preserved.

### Files changed (IND-06)
- `docs/data/briefing_latest.json` — 60 subsector `mm` / `yy` values populated (existing "declined"/numeric values overwritten with consistent computed values)
- `tmp_subs_fetch/` — fetch scripts, metadata dump, NAICS-to-dim4 map, and `FETCH_REPORT.md`

## Markets Tab

### Diagnosed gaps (pre-fix state, 2026-04-09)
Initial CDP diagnostic captured 13 rows across 4 issue classes:

1. **Stale timeseries data across all market series.** Legacy keys (`wti`, `brent`, `gold`, `silver`, `copper`, `cadusd`, `tsx_composite`, etc.) last updated between 2015 (iron ore, nickel, lead, tin, zinc), 2023, and 2025. Fresh `comm_*` and `idx_*` keys had only 2–5 points each — too sparse for charts. Result: short-window chart filters (1M, 3M, 6M) rendered empty or near-empty SVGs.
2. **Sparse briefing markets block.** `financialMarkets.indices` had 4 items, `financialMarkets.fx` had 3 items, top-level `commodities` had 13 items. Missing: Shanghai Composite, Hang Seng, FTSE, DAX, Nikkei, DJIA, GBP/USD, USD/JPY, USD/CNY, AUD/USD, Aluminum, Iron Ore, Platinum, Palladium, Corn, Soybeans, Sugar, Coffee, Cocoa, Rice, Cotton, Live Cattle, Lean Hogs.
3. **Data-level field quality issues.** (a) Commodity `day` (weekly) column empty on 11 of 13 rows. (b) Y/Y column empty on 11 of 13 commodity rows AND all indices/FX rows. (c) FX `day` field stored text narrative ("Loonie weakened past 1.38 to two-month low", "Euro strengthened amid geopolitical uncertainty") instead of numeric. (d) Equity `day` field contained literal suffix " day" (e.g., "+1.54% day"). (e) Wheat unit mojibake `Â¢/bu`. (f) Nonsensical commodity M/M values ("+50%+" for WTI).
4. **Stale, partially hallucinated narrative text.** `marketCommentary` opened with "WTI crude settled at US$102.88/bbl on March 31 — its first weekly close above $100 since July 2022" — inconsistent with the rest of the data and hard-coded to a prior session's synthesized state.

Chart filter logic in `_mktRenderSvg()` (app.js:4558) was inspected and found to be correct. Root cause of broken charts was stale underlying data, not renderer bugs.

### Fixes applied

- [x] **MKT-01**: Fetched fresh 5-year daily timeseries for 39 market symbols from Yahoo Finance chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5y`). Covered 9 equity indices, 7 FX pairs, 4 energy, 4 precious metals, 3 base metals (copper + aluminum + iron ore via ALI=F, TIO=F), 2 uranium proxies (CCJ, URA), 9 ag, 2 livestock, 1 lumber (LBR=F), 1 potash proxy (NTR), and the 3 remaining direct commodities (soybeans, rice, cotton). All 39 tickers returned valid data with ~1,200–1,300 daily points each. Raw responses and cleaned series saved to `tmp_mkt_fetch/raw/` and `tmp_mkt_fetch/series/`. Zero API cost; zero API key required. See `tmp_mkt_fetch/summary.json` for latest values + computed wk/mm/yy percentages.
- [x] **MKT-02**: Added single-point outlier cleaning in the series extraction pipeline (`tmp_mkt_fetch/fetch_all.py`). Rationale: Yahoo's rough rice (ZR=F) feed has occasional decimal-point glitches where one trading day is reported as ~1/100 of the correct value (e.g., 10.905 between 1123.0 and 1105.5 on 2026-04-09, and 17.685 at 2024-06-17). The cleaner drops a point if it differs from both neighbors by >50% AND the neighbors are consistent with each other (<20% apart). Also drops the trailing point if it's >50% off the penultimate cleaned point. Applied globally to all 39 series. Post-clean rice reports $1,105.50/cwt (-2.0% wk) correctly.
- [x] **MKT-03**: Injected 39 fresh timeseries keys into `docs/data/timeseries.json` via `tmp_mkt_fetch/inject.py`. Byte-identical preservation verified on all 120 pre-existing keys (0 modifications, 0 losses). Added 4 new keys: `fx_gbpusd`, `fx_audusd`, `idx_shanghai`, `idx_hangseng`. File grew from 1.85MB to 2.36MB due to the denser 5-year daily coverage. Backup at `docs/data/timeseries.bak_mkt_20260409_194623_pre.json`.
- [x] **MKT-04**: Rebuilt `financialMarkets.indices` from 4 → 9 rows. Each row now has populated `value`, `day` (weekly %), `mm` (monthly %), and `yy` (yearly %) computed from the fresh timeseries data. Added FTSE 100, DAX, Nikkei 225, Shanghai Composite, Hang Seng to the original TSX / S&P 500 / DJIA / NASDAQ set.
- [x] **MKT-05**: Rebuilt `financialMarkets.fx` from 3 → 7 pairs. CAD/USD, USD/CAD, EUR/USD, GBP/USD, USD/JPY, USD/CNY, AUD/USD. USD/CAD is derived as the inverse of CAD/USD (Yahoo's CADUSD=X returns CAD→USD, and the sign of the percent change is inverted for USD/CAD). Replaced the text narratives in the `day` field ("Loonie weakened past 1.38 to two-month low" etc.) with numeric `+X.X%` / `-X.X%` values computed from the timeseries.
- [x] **MKT-06**: Rebuilt top-level `commodities` array from 13 → 26 rows across 6 categories (was 5). Added Livestock as a new category. Full list: **Energy** — WTI, Brent, WCS (est.), Natural Gas. **Precious Metals** — Gold, Silver, Platinum, Palladium. **Base Metals** — Copper, Aluminum, Iron Ore (TSI 62% Fe), Uranium (Cameco CCJ), Uranium (Sprott URA). **Agriculture** — Wheat, Corn, Soybeans, Canola, Sugar, Coffee, Cocoa, Rough Rice, Cotton, Potash (Nutrien NTR). **Livestock** — Live Cattle, Lean Hogs. **Forest Products** — Lumber. Every row has `val`, `day` (weekly %), `mm`, `yy`, `unit`, `context`, and `category` populated. Not included: physical LME nickel / zinc / lead / tin (Yahoo doesn't expose direct futures for these), coal, LNG Asia (no free daily source). These are flagged as known gaps for a future fetch tier using the pipeline's existing StatCan / BoC / ECCC scrapers.
- [x] **MKT-07**: Wheat unit mojibake (`Â¢/bu`) eliminated. Fresh wheat row stores value as `573.5 USc/bu` using an explicit `USc` prefix — no UTF-8 cent-sign characters in the JSON. Same pattern applied to corn, soybeans, sugar, coffee, cotton, live cattle, lean hogs (all CME/ICE tickers that Yahoo returns in US cents: currency code `USX`).
- [x] **MKT-08**: Equity / FX pill change display no longer shows the literal word " day". Fresh data writes `+X.X%` strings directly without suffix tokens, so the renderer's `it.change||it.day` path produces clean pct values.
- [x] **MKT-09**: WCS (Western Canadian Select) is tracked as an estimate derived from the fresh WTI futures price minus a US$13/bbl constant differential. The context tooltip explicitly flags this as an estimate and notes that the pipeline should pull the official weekly Alberta Ministry of Energy / CER WCS-WTI differential for true daily values. Weekly/monthly/yearly percent changes are taken from WTI (same directional move).
- [x] **MKT-10**: Canola is tracked from the existing StatCan 32-10-0077 Saskatchewan producer price series (already injected during the Agriculture template work — see IND-03). Yahoo's RS=F canola futures symbol returned empty. Canola's weekly percent shows `—` because the series is monthly; month-over-month and year-over-year are computed from adjacent StatCan entries.
- [x] **MKT-11**: Rebuilt narrative blocks with fresh numbers — `marketCommentary`, `commodityCommentary`, `financialMarkets.equityNarrative`, `financialMarkets.fxNarrative`, `financialMarkets.commodityNarrative`. Each narrative is factual and wire-service-style per editorial policy: states what happened, cites specific numbers and dates, links to the data source (Yahoo Finance public chart endpoint for 38 series; StatCan WDS for canola). No banned words, no editorializing. The original stale WTI $102.88 / gold $4,578 commentary is retained in the backup file only.
- [x] **MKT-12**: Yield curve block (`yieldCurve`, `financialMarkets.yieldCurve`) and BoC rate (`2.25%`) untouched — verified byte-identical post-inject. The yield table, 2s10s spread row, and yield curve SVG continue to render from the pre-existing pipeline data.
- [x] **MKT-13**: Verified chart filter buttons work across all five range toggles (1M, 3M, 6M, 1Y, 3Y) on both the Equity Indices and FX charts. Point counts scale correctly: equities 1M=22, 3M=62, 6M=124, 1Y=250, 3Y=754; FX 1M=24, 3M=65, 6M=128, 1Y=257, 3Y=779. Pill-click switching between series (TSX → S&P 500 → Nikkei 225 → Hang Seng) re-renders with ~750 points each for the default 3-year range. The chart filter code in `_mktRenderSvg()` was already correct — the root cause of the earlier broken behavior was empty timeseries data, not renderer bugs.
- [x] **MKT-14**: Verified commodity category tab filter works. "All" shows 26 rows; Energy 4; Precious Metals 4; Base Metals 5; Agriculture 10; Livestock 2; Forest Products 1. Sum matches total.
- [x] **MKT-15**: Section metadata updates reflect the new counts: "9 indices", "7 pairs", "Yield curve · 6 tenors", "Click any row for details · 26 commodities".

### Files changed (Markets Tab)
- `docs/data/timeseries.json` — 39 keys refreshed with 5y daily data (1,200–1,300 points each); 4 new keys added (`fx_audusd`, `fx_gbpusd`, `idx_shanghai`, `idx_hangseng`); 120 pre-existing keys preserved byte-identically. Backup at `docs/data/timeseries.bak_mkt_20260409_194623_pre.json`.
- `docs/data/briefing_latest.json` — `financialMarkets.indices`, `financialMarkets.fx`, top-level `commodities`, `financialMarkets.summary` / `commentary`, `marketCommentary`, `commodityCommentary`, `financialMarkets.equityNarrative`, `financialMarkets.fxNarrative`, `financialMarkets.commodityNarrative`, `bocRate` (top-level mirror). All other keys verified byte-identical. Backup at `docs/data/briefing_latest.bak_mkt_20260409_194623_pre.json`.
- `docs/js/app.js` — no changes. Renderer was already correct. All fixes are data-layer only.
- `tmp_mkt_fetch/` — new working directory: `fetch_all.py` (Yahoo fetch + outlier cleaning), `test_tickers.py` (ticker availability probe), `inject.py` (timeseries + briefing inject with byte-identical verification), `raw/` (39 raw Yahoo chart responses), `series/` (39 cleaned date/value series), `summary.json`, `inject_report.json`, `failures.json` (empty — all 39 fetches succeeded).

### Known gaps for future sessions
- **LME base metals (Nickel, Zinc, Lead, Tin).** Yahoo has no free futures feed. **Partially closed in MKT-16 below** — the BoC Metals & Minerals Index (W.MTLS) now provides a weighted basket covering these. Individual daily prices still unavailable.
- **Coal (Newcastle), LNG Asia.** No free daily source. **Partially closed in MKT-16 below** — the BoC Energy Index (W.ENER) includes coal and natural gas as index components.
- **WCS differential.** Currently an estimated US$13/bbl constant. Could be refreshed from Alberta Ministry of Energy weekly reports or the CER commodity tracker. Deferred.
- **Lumber unit.** LBR=F returns the new 27,500 board feet contract in US$/1,000 board feet; the prior LB=F contract is delisted. Currently labelled `/mbf`. Confirm this is the user's preferred unit display.

### Expansion round 2 — 16 additional commodities (MKT-16 through MKT-18)

- [x] **MKT-16**: Fetched 16 additional series from free public sources. 12 from Yahoo Finance (10 new commodity futures + refresh of the two stale soybean meal / soybean oil keys + 4 Canadian commodity-proxy equities) and 4 from the Bank of Canada Valet API (`https://www.bankofcanada.ca/valet/observations/W.ENER,W.MTLS,W.FOPR,W.FISH/json`). Yahoo additions: Heating Oil (HO=F), RBOB Gasoline (RB=F), HRW Wheat (KE=F), Oats (ZO=F), Soybean Meal (ZM=F — refresh), Soybean Oil (ZL=F — refresh), Feeder Cattle (GF=F), Milk Class III (DC=F), Suncor Energy (SU), Teck Resources (TECK), Barrick Mining (ABX.TO), West Fraser Timber (WFG). BoC Valet additions: BoC Energy Index (W.ENER, 1,743.00), BoC Metals & Minerals Index (W.MTLS, 1,191.38), BoC Forestry Index (W.FOPR, 449.29), BoC Fisheries Index (W.FISH, 2,148.06) — all weekly, last observation 2026-04-08. Zero cost; zero API key required for either source. Fetch script at `tmp_mkt_fetch/fetch_more.py`; raw responses and cleaned series saved to `tmp_mkt_fetch/raw/` and `tmp_mkt_fetch/series/`; computed summary at `tmp_mkt_fetch/summary_more.json`. 16 of 16 fetches succeeded.
- [x] **MKT-17**: Injected 14 new timeseries keys (`heating_oil`, `gasoline_rbob`, `wheat_hrw`, `oats`, `feeder_cattle`, `milk_class3`, `suncor_energy`, `teck_resources`, `barrick_mining`, `west_fraser`, `boc_energy_index`, `boc_metals_index`, `boc_forestry_index`, `boc_fisheries_index`) and refreshed 2 existing stale keys (`soybean_meal`, `soybean_oil` — last 2023-09-26 → last 2026-04-09). Byte-identical preservation verified on all 122 pre-existing non-touched timeseries keys (124 − 2 refreshed = 122). Added 14 new keys → total 138 timeseries keys. File grew from 2.36 MB → 2.94 MB. Backup at `docs/data/timeseries.bak_mkt2_20260409_202239_pre.json`.
- [x] **MKT-18**: Appended 16 new rows to top-level `commodities` in `briefing_latest.json` (26 → 42 rows) across 8 categories (was 6). New categories: **Fisheries** (1 row — BoC Fisheries Index) and **Canadian Equity Proxies** (4 rows — Suncor, Teck, Barrick, West Fraser). Per-category counts: Energy 7 (was 4, added Heating Oil, RBOB Gasoline, BoC Energy Index), Precious Metals 4 (unchanged), Base Metals 6 (was 5, added BoC Metals & Minerals Index), Agriculture 14 (was 10, added HRW Wheat, Oats, Soybean Meal, Soybean Oil), Livestock 4 (was 2, added Feeder Cattle, Milk Class III), Forest Products 2 (was 1, added BoC Forestry Index), Fisheries 1 (new), Canadian Equity Proxies 4 (new). Combined array sorted by category using a stable sort on `CAT_ORDER`, preserving within-category insertion order so the MKT-06 layout is unchanged except where new rows are appended to their respective category. Every new row has `val`, `day`, `mm`, `yy`, `unit`, `category`, and a factual `context` narrative populated. BoC index rows display as `"1,743 pts"` with unit `index`; equity proxy rows display as `"US$63.39"` / `"C$58.73"` with unit `share`; BoC Valet indices use dimensionless weekly weights so unit is `index`. Section meta updated automatically by renderer: "Click any row for details · 42 commodities". Category tabs verified working for all 8 categories via CDP test: All=42, Energy=7, Precious Metals=4, Base Metals=6, Agriculture=14, Livestock=4, Forest Products=2, Fisheries=1, Canadian Equity Proxies=4. Chart filters still work (verified 1M/3M/6M/1Y/3Y re-renders on both Equities and FX charts, point counts unchanged from MKT-13). Byte-identical preservation verified on all non-touched briefing keys. Backup at `docs/data/briefing_latest.bak_mkt2_20260409_202239_pre.json`.

### Pill labelling + narrative cleanup (MKT-20)

- [x] **MKT-20**: Reworked the Equity Indices and Foreign Exchange section pills to show three labelled change percentages (1W / 1M / 1Y) inline inside each pill, and removed the narrative paragraphs that previously rendered below the equity and FX charts. The change column previously showed only one unlabeled percentage and a separate "Year-over-Year" stat row appeared below the pill grid for the first item only — readers had to guess what timeframe the pill percentage represented. Now each pill displays all three timeframes side-by-side with small "1W" / "1M" / "1Y" tag-style labels, color-coded green for positive and red for negative. The redundant standalone "Year-over-Year" stat row was removed from both Equity Indices and Foreign Exchange sections. The Bank of Canada overnight rate stat is preserved in the Foreign Exchange section (rendered only when a BoC rate value is present in the data). Section meta line in both headers now reads `"N indices · changes shown 1W / 1M / 1Y"` / `"N pairs · changes shown 1W / 1M / 1Y"` so the column meaning is also stated at the section level. Renderer changes in `_buildMktEquities()` and `_buildMktFx()`: items mapping now pulls `it.mm` in addition to `it.change` and `it.yy`; pill markup wraps the three change items in a new `pill-changes-row` flex container; the `eqNarr` / `fxNarr` rendering blocks were deleted (the underlying `equityNarrative` / `fxNarrative` data is left in `briefing_latest.json` for non-frontend consumers like PDF/DOCX exports). New CSS classes added in `docs/index.html`: `.pill-changes-row`, `.pill-chg-item`, `.pill-chg-label`, `.pill-chg-val` (with `.up` / `.down` / `.flat` color modifiers), plus a more compact `.fx-pill .pill-chg-*` override so the labels fit inside the smaller FX pill cells. The existing single-percent `.pill-change` class is left in place for backwards compat in case any other view still references it. Verified via CDP that all 9 equity pills and all 7 FX pills render the new 1W / 1M / 1Y triplets and that no narrative paragraph appears at the bottom of either chart.

### Files changed (MKT-20)
- `docs/js/app.js` — `_buildMktEquities()` and `_buildMktFx()` rewritten: items mapping adds `mm`, pill markup uses three `pill-chg-item` children, narrative blocks removed, redundant stat row removed (BoC rate preserved on FX side).
- `docs/index.html` — added `.pill-changes-row`, `.pill-chg-item`, `.pill-chg-label`, `.pill-chg-val` (with `.up` / `.down` / `.flat` modifiers) and a compact override for `.fx-pill .pill-chg-*`.
- `docs/data/briefing_latest.json` — no changes (the `financialMarkets.equityNarrative`, `financialMarkets.fxNarrative`, `financialMarkets.commodityNarrative` strings remain in the JSON for non-frontend consumers; the renderer just stops rendering equity and FX narratives).

### Expansion round 3 — Diamonds (MKT-19)

- [x] **MKT-19**: Added a Canadian diamond price row using StatCan Table 16-10-0020 (Production of non-metallic minerals in quantities, monthly). Investigation: free daily diamond spot price feeds (Rapaport, IDEX Online, WWW Diamond International) are all subscription-only; the Bank of Canada commodity index does not break out diamonds; equity proxies (Mountain Province Diamonds MPVD.TO at C$0.05/share, Burgundy Diamond Mines BDM.AX at A$0.017/share) are distressed micro-caps whose share prices reflect company-specific financial condition more than the underlying diamond market. The most accurate free measure available is StatCan's monthly mine-gate realized price computed as **value of shipments / quantity shipped, Canada total** — covering Diavik (NWT), Ekati (NWT), Gahcho Kué (NWT) and historical Renard (Quebec). Pulled both vectors via WDS API: vector **1145997613** (Diamonds (carats), Quantity shipped, Canada — coordinate `1.1.2.0.0.0.0.0.0.0`) and vector **1145997965** (Diamonds (dollars), Value of shipments, Canada — coordinate `1.2.3.0.0.0.0.0.0.0`). 72-period pull returned 66 valid monthly observations from Feb 2020 to Dec 2025 (gaps in 2020-05, 2020-07/08, 2021-01 are StatCan confidentiality suppressions during early COVID reporting; series is complete monthly from Feb 2021 onwards). Latest complete period: **Dec 2025 = C$66.09/ct** ($80.5M shipment value over 1.22M carats shipped). M/M vs Nov 2025 (C$62.24): **+6.2%**. Y/Y vs Dec 2024 (C$117.87): **-43.9%**. Jan 2026 not yet published. Publication lag is roughly 2 months — the freshest period available will always be ~3 months behind today's date. Three new timeseries keys injected: `diamonds_canada_price` (66 monthly $/ct points), `diamonds_canada_carats` (carats shipped), `diamonds_canada_value` (CAD value shipped). All 138 pre-existing timeseries keys preserved byte-identical (verified). Created new commodity category **Diamonds** placed immediately after Precious Metals in the category order — parallel to how Fisheries was added with a single row in MKT-18. Briefing commodities: 42 → 43 rows across 9 categories (was 8). All non-commodities briefing keys preserved byte-identical. Backups: `docs/data/timeseries.bak_diam_20260409_204626_pre.json`, `docs/data/briefing_latest.bak_diam_20260409_204626_pre.json`. Verified via CDP that the new "Diamonds" category tab renders and shows the single row with `val=C$66.09/ct mm=+6.2% yy=-43.9%`.

### Files changed (MKT-19)
- `docs/data/timeseries.json` — 3 new keys added (`diamonds_canada_price`, `diamonds_canada_carats`, `diamonds_canada_value`); 138 pre-existing keys preserved byte-identical.
- `docs/data/briefing_latest.json` — `commodities` array extended from 42 → 43 rows; new "Diamonds" category inserted between "Precious Metals" and "Base Metals" in CAT_ORDER.
- `tmp_mkt_fetch/fetch_diamonds.py` — StatCan WDS fetcher for vectors 1145997613 and 1145997965; computes monthly realized C$/ct.
- `tmp_mkt_fetch/inject_diamonds.py` — inject script with byte-identical verification.
- `tmp_mkt_fetch/diamonds_summary.json` — audit trail of computed metrics.
- `tmp_mkt_fetch/raw/diamonds_carats_raw.json`, `tmp_mkt_fetch/raw/diamonds_value_raw.json` — raw WDS responses.
- `tmp_mkt_fetch/series/diamonds_canada_price.json`, `tmp_mkt_fetch/series/diamonds_canada_carats.json`, `tmp_mkt_fetch/series/diamonds_canada_value.json` — cleaned series files.

### Files changed (MKT-16 through MKT-18)
- `docs/data/timeseries.json` — 14 new keys, 2 refreshed keys, 122 preserved byte-identical. Total 138 keys.
- `docs/data/briefing_latest.json` — `commodities` array extended from 26 → 42 rows across 8 categories. All other keys preserved byte-identical.
- `tmp_mkt_fetch/fetch_more.py` — Yahoo + BoC Valet fetcher for the 16 approved additions. Reuses the MKT-02 outlier cleaner.
- `tmp_mkt_fetch/probe_more.py` — availability probe that confirmed 47 of 49 candidate tickers are reachable via free Yahoo Finance (only BRN=F and AAA=F 404'd — not in the final selection).
- `tmp_mkt_fetch/probe_fred.py` — confirmed that FRED CSV endpoint times out / resets connection from this environment and that FRED's JSON API requires a free API key (which would be a new service — not adopted). Confirmed BoC Valet requires series IDs prefixed `W.` (weekly) or `M.` (monthly), not raw names like `BCPI_TOTAL`.
- `tmp_mkt_fetch/inject_more.py` — inject script with byte-identical verification, stable-sorted merge into the existing commodities array.
- `tmp_mkt_fetch/inject_more_report.json` — audit trail of which keys were updated, which were added, and final category counts.

## Projects Tab

Design-theme pass, hero/filter merge, lazy loading refinements, CMA filter, and table polish. Locked 2026-04-10. See `APPROVED_TEMPLATE_PROJECTS.md` for the full lock spec.

### Design-theme pass (PROJ-01 through PROJ-05)

- [x] **PROJ-01**: Added `#tab-projects` section-header / accent-bar / section-meta / section-block CSS rules — copied verbatim from `#tab-provinces` (lines 735–739 in `docs/index.html`). Inserted after the `#tab-markets` block so the Projects tab now has the same scoped vocabulary as the other approved tabs. Five new rules total; no changes to any existing selectors.
- [x] **PROJ-02**: Added Prussian blue hero card CSS block `#tab-projects .proj-hero-stats` + descendants. Modeled on `.province-header-card` / `.province-header-stats` (lines 729–734). Hero card: `background: #003153; border-radius: 8px; color: #fff; padding: 28px 32px 22px`. Title h2 28px/700, subtitle 14px, stat-value 22px/700 tabular-nums, stat-label 10px uppercase 0.4 letter-spacing. Full border-radius + `overflow: hidden` so nested children clip to the rounded corners cleanly.
- [x] **PROJ-03**: Reskinned `.project-table thead th` from `rgba(245,247,250,0.98)` gray-blue with `#475569` dark text to `#003153` Prussian blue background with `#ffffff` 11px uppercase DM Sans (600 weight, 0.3 letter-spacing) to match the `.tldr-ind-table th` pattern used in other approved tabs. `.project-table tbody tr` border-bottom updated from `rgba(0,0,0,0.05)` to `#e8ecf0` for row separators matching the approved vocabulary.
- [x] **PROJ-04**: Wrapped Projects HTML content in `.section-block` + `.section-header` divs to establish the same visual rhythm as Provinces/Industries. Initial pass added two sections: "Filters & Summary" and "Project Pipeline" (since deprecated in PROJ-19). Section-header contains accent-bar + h3 + section-meta per the approved pattern.
- [x] **PROJ-05**: Removed the Unsplash stock photo `<div class="section-banner">` from the Projects tab — the `1541888946425-d81bb19240f5` construction-site hero image was inconsistent with the approved vocabulary (none of TL;DR / National / Provinces / Industries / Markets use section-banner images). CLAUDE.md editorial policy also calls for factual reporting only; a decorative stock photo has no data attribution. The Prussian blue hero card (PROJ-02) now serves as the page's top visual anchor.

### Hero card evolution (PROJ-06 through PROJ-09)

- [x] **PROJ-06**: Promoted the Prussian blue summary strip to a full hero card matching the Provinces/Industries pattern. Structure: `.proj-hero-stats` as a flex container with `.proj-hero-title` (h2 + subtitle) on the left and `.proj-hero-stats-right` with 3 stat columns on the right. `justify-content: space-between; align-items: flex-end`. Title text "Capital Projects Tracker" + subtitle "Major capital projects across Canada" added as static HTML (replacing the identical text that was in the removed section-banner). Rename of `#projSummaryStats` class from `.proj-stats` to the hero card role. Rename of Section 1 header from "Filters & Summary" to "Filters" since the summary stats moved into the hero.
- [x] **PROJ-07**: Removed the `verify-banner` "X% of projects have source links for independent verification. N backed by government sources." element from `renderProjectSummary()`. Eliminated the `withUrls` / `withGov` / `pctVerified` calculations. The hero card now opens directly with the Prussian blue stats strip — no lead banner above it. Factual per editorial policy but redundant with the existing source links in the table Source column.
- [x] **PROJ-08**: Expanded hero stats from 3 to 6 to fill the wide empty middle of the hero card on 1520px desktop viewports. Added: `approved` (status includes "approved" but not "construction"), `newCount` (`p.firstTracked >= today - 7d`), `provCount` (unique provinces in filtered set). Layout changed from `justify-content: space-between` (clustered on right) to `.proj-hero-stats-right { flex: 1; justify-content: space-around; padding-left: 48px }` so the stats spread evenly across the remaining width after the title block. Also added `.proj-hero-title { flex-shrink: 0 }` to keep the title at its natural width.
- [x] **PROJ-09**: Restructured hero card so the filter bar lives **inside** the hero DOM as a nested child, not as a sibling with matching styles. Flex column with `.proj-hero-top` wrapping the title+stats row, and `.filter-bar#projectFilterBar` as the second row separated by a `1px solid rgba(255,255,255,0.15)` top border. Full border-radius 8px + `overflow: hidden` on the hero so the nested filter bar clips to the rounded corners. `#projSummaryStats` renamed to serve as the hero wrapper directly (class `proj-hero-stats` applied to the outer div). JS `renderProjectSummary()` now only updates the stat items inside `#projHeroStats` (sub-element), not the whole hero — so the filter bar DOM stays intact across filter changes without event-listener churn.

### Filter bar polish (PROJ-10 through PROJ-13)

- [x] **PROJ-10**: Styled the "Above Threshold" toggle as a distinct pill control on the Prussian blue background. Container: `background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.28); padding: 7px 12px; border-radius: 6px; gap: 8px; color: #ffffff; font-weight: 500`. Toggle slider track off-state: `rgba(255,255,255,0.35)`. Toggle slider track on-state: `#ffffff`. Thumb on-state: `#003153` (Prussian blue, for contrast against the white track). Off-state thumb stays white per the base `.toggle-slider::after` rule.
- [x] **PROJ-11**: Added comma formatting to all stat values via `.toLocaleString()`. Applied to `total`, `uc`, `approved`, `newCount`, `provCount` (before PROJ-18 dropped it). The `fv()` currency helper was also rewritten from `(v/1e9).toFixed(1)` + `(v/1e6).toFixed(0)` to `.toLocaleString('en-CA', {minimumFractionDigits:1, maximumFractionDigits:1})` for the billions branch and `Math.round(v/1e6).toLocaleString('en-CA')` for the millions branch. Result: `$1,234.5B` renders correctly when Canadian total project value crosses into trillions.
- [x] **PROJ-12**: Moved the "+ Report a Missing Project" button from its standalone wide-button location below the hero into the filter bar alongside the Export CSV button. Text shortened to "+ Report Missing" to fit the filter bar flow. Button style inlined to match Export CSV (`background: #ffffff; border: 1px solid rgba(0,0,0,0.12); border-radius: 6px; color: #003153; white-space: nowrap`). The `#missedProjectForm` collapsible panel remains in its current DOM location below the hero; the onclick handler targets `#missedProjectForm` by ID so it still works from the new button location. `#missedProjectSection` wrapper's margin-top dropped from `0.5rem` to `0`. Form panel's `border-radius` corrected from `0 0 8px 8px` (connected to the old button above) to `8px` full rounding since it's now standalone.
- [x] **PROJ-13**: Normalized all filter-bar buttons (Export CSV, "+ Report Missing") to match the input/select size. Changed padding from `0.4rem 0.8rem` (6.4×12.8px) to `8px 12px` and font-size from `var(--text-xs)` to `var(--text-sm)`. All filter-bar elements now line up at the same height visually.

### Lazy loading + CMA filter (PROJ-14 through PROJ-17)

- [x] **PROJ-14**: Added CMA filter dropdown (`#filterCma`) to the filter bar between the Province and Sector selects. New `populateCmaFilter()` function computes `new Set(allProjects.map(p => (p.cma||'').trim()).filter(Boolean))`, sorts alphabetically, and populates the dropdown. Preserves the current selection after repopulation if the CMA still exists in the new set. Called after every `loadProjects()` so the CMA list refreshes when the user changes provinces. `filterProjects()` reads `$('filterCma').value` and adds `if (cma && (p.cma||'').trim() !== cma) return false` to the filter chain. `$('filterCma').onchange = filterProjects` wired in `renderProjectsTab()`. `p.cma` field was already populated in project data (confirmed via inspection of `projects_ontario.json` entries like `{"cma":"Sturgeon County"}` / `{"cma":"Airdrie"}`), and the base `.filter-bar` search box was already matching `p.cma` (line 4910) — we just surfaced it as a dedicated dropdown.
- [x] **PROJ-15**: Fixed a double-load bug in `renderProjectsTab()`. Before: line 4855 defaulted to `'BC'` if the dropdown was empty, loaded `projects_british_columbia.json` (~794 KB), then `filterProjects()` ran on line 4880, read the dropdown value (still `""` since `provSel.value` was never set), computed `prov = null`, detected mismatch against `_lastLoadedProvince='BC'`, and triggered a phantom `loadProjects(null)` which fetched `projects_all.json` (6 MB). Two loads on every initial render. Fix: changed default to `'ON'` (Ontario, ~1.7 MB — the largest province, most relevant for typical use), and added `provSel.value = initProv` BEFORE `loadProjects` runs so the dropdown UI matches the loaded data and no phantom reload fires.
- [x] **PROJ-16**: Removed the async background fetch of `projects_all.json` that was running inside `renderProjectsTab()` solely to compute per-province project counts for the province dropdown labels (the `(${cnt[o.value]})` suffix). This was a hidden 6 MB load on every initial render even when the user never selected "All Provinces". With PROJ-15 loading Ontario by default and PROJ-14 not needing the full dataset, the count-fetch was the last holdout forcing the full dataset into memory on init. Dropped entirely — province dropdown now shows just the province names without counts.
- [x] **PROJ-17**: Capped `#tab-projects .proj-hero-stats .filter-bar select` at `max-width: 180px` with `text-overflow: ellipsis; overflow: hidden`. Applied to all filter-bar selects (Province, CMA, Sector, Status, Sort) for visual consistency. Root cause: long CMA names like "Regional Municipality of Wood Buffalo" and "Greater Sudbury / Grand Sudbury" were auto-sizing the closed dropdown to fit the longest option, causing the CMA select to bloat far wider than the other filters. 180px cap lets the closed state truncate with an ellipsis while the full name remains visible in the open dropdown list.

### Hero stat reduction (PROJ-18)

- [x] **PROJ-18**: Removed the "Provinces" stat (6th) from the hero card and deleted the unused `provCount` calculation from `renderProjectSummary()`. Hero now shows 5 stats instead of 6: Total Projects, Total Value, Under Construction, Approved, New This Week. User feedback: the Provinces count "feels out of place" next to New This Week.

### Table header integration (PROJ-19 through PROJ-20)

- [x] **PROJ-19**: Removed the separate `.section-header` for "Project Pipeline" (accent-bar + h3 + section-meta). The Prussian blue `<thead>` row with uppercase column labels is visually prominent enough to serve as both the section divider and the column headers. Net vertical savings ~60px. `.section-block` wrapper retained around the table + load-more button.
- [x] **PROJ-20**: Rebuilt `.project-table-wrap` CSS. Before: `overflow-x: auto; border-radius: var(--radius-lg); background: var(--glass-bg); border: 1px solid var(--glass-border); box-shadow: var(--shadow-sm); backdrop-filter: blur(var(--glass-blur))` (glass effect). After: `overflow: hidden; border-radius: 8px; background: #ffffff; border: 1px solid #d5dbe3; box-shadow: var(--shadow-sm)` (solid). The key change is `overflow: hidden` which clips the `<thead>`'s Prussian blue background to the wrap's rounded top corners — visually the column-header row now fills the rounded corners instead of sitting inside a white-bg wrap with empty corners. Side effect: `.project-table thead th` lost its `position: sticky; top: var(--nav-height, 44px); z-index: 10; border-bottom: 2px solid #d5dbe3` because sticky positioning doesn't clip properly inside `overflow: hidden`. Headers no longer pin on scroll — accepted trade-off for the rounded-corner visual.

### Source column fix (PROJ-21)

- [x] **PROJ-21**: Source column was rendering empty on every row, and the header was abbreviated "Src". Three fixes in one patch:
  1. **Header text**: "Src" → "Source" in `renderProjectTable()` thead string.
  2. **Data source**: Changed from `(p.sources && p.sources[0]) ? p.sources[0].url : ''` to `firstEv.url || ''` where `firstEv = (p.evidence || [])[0] || {}`. Root cause confirmed by inspecting `projects_ontario.json`: `p.sources` is an **empty array** on most/all projects; evidence URLs live in `p.evidence[]` (with fields `url`, `source_type`, `name`, `date`, `authority`). Pipeline writes to `evidence[]`, frontend was reading from the vestigial `sources[]` field. Updated `srcTitle` fallback chain to `firstEv.name || firstEv.source_type || 'Source'`.
  3. **Column width**: `.project-table .col-source` widened from `50px` to `75px` so the spelled-out "Source" header fits comfortably without clipping.

### Table polish (PROJ-22 through PROJ-23)

- [x] **PROJ-22**: Added vertical column separators to the project table. `.project-table thead th { border-right: 1px solid rgba(255,255,255,0.15) }` — translucent white, subtle on the Prussian blue header. `.project-table td { border-right: 1px solid #e8ecf0 }` — light gray on the body cells matching the existing row separators. `:last-child` override on both th and td removes the right border on the final column so the rounded-corner wrap doesn't show a double edge on the right side.
- [x] **PROJ-23**: Increased left padding on all table cells from 10px to 18px. `.project-table thead th` padding changed from `12px 10px` to `12px 10px 12px 18px` (top/right/bottom/left). Same change applied to `.project-table td`. Right padding, top/bottom padding, and font sizes unchanged. Content in each column now sits further from its left divider, improving readability.

### Files changed (Projects Tab)

- `docs/index.html`:
  - Removed the "Methodology" nav pill + full methodology tab panel (pre-Projects cleanup, part of the same session; not counted as a PROJ patch)
  - Added `#tab-projects` CSS block (~lines 1136–1156 in the final state) containing section-header, section-block, proj-hero-stats, proj-hero-top, proj-hero-title, proj-hero-sub, proj-hero-stats-right, stat-item, stat-value, stat-label, filter-bar overrides, and toggle-label pill styling
  - Replaced the Unsplash `section-banner` with the new Prussian blue hero wrapper `#projSummaryStats.proj-hero-stats`
  - Moved the filter bar inside the hero DOM as a direct child
  - Added the CMA dropdown `<select id="filterCma">` between filterProvince and filterSector
  - Added the "+ Report Missing" button inside the filter bar after Export CSV
  - Removed the standalone wide "+ Report a Missing Project" button (its wrapper `#missedProjectSection` now only contains the collapsible form)
  - Removed the `<div class="section-header">` for "Project Pipeline"
  - `.project-table-wrap`, `.project-table thead th`, `.project-table tbody tr`, `.project-table td` styling updates (see PROJ-03, PROJ-20, PROJ-22, PROJ-23)
  - `.project-table .col-source` width 50px → 75px

- `public/index.html`:
  - Mirror of every `docs/index.html` change above

- `docs/js/app.js`:
  - `renderProjectsTab()` — rewritten per PROJ-14, PROJ-15, PROJ-16 (reordered dropdown population, default province 'ON', removed 6 MB count fetch, added CMA init + listener)
  - `filterProjects()` — added CMA filter check, calls `populateCmaFilter()` after `loadProjects()`
  - New `populateCmaFilter()` function added directly above `filterProjects()`
  - `renderProjectSummary()` — rewritten per PROJ-06, PROJ-07, PROJ-08, PROJ-09, PROJ-11, PROJ-18 (removed verify-banner, now only innerHTMLs the `#projHeroStats` sub-element with 5 stat-item cards, formats all counts via `.toLocaleString()`, `fv()` helper updated to use `toLocaleString('en-CA')` for billions and millions)
  - `renderProjectTable()` — header text "Src" → "Source" (PROJ-21), source data derivation switched from `p.sources[0]` to `(p.evidence || [])[0]` (PROJ-21)

### Known gaps for future sessions

- **Inline styles on the missing-project form** — 9 input fields still use inline `style="..."` attrs. Explicitly deferred during the design-theme pass (user picked "visual alignment only"). Future cleanup: extract to `#tab-projects .mp-form` CSS block.
- **Sticky table headers** — dropped in PROJ-20 because `overflow: hidden` on the wrap breaks sticky clipping. If wanted, requires a nested scroll container or a different architecture (e.g., separate header table + body table with synced scroll).
- **Province counts in dropdown labels** — removed with the 6 MB fetch in PROJ-16. Restoring requires exporting a tiny `projects_counts.json` from `tools/export_dashboard.py` and fetching it on dropdown populate.
- **`p.sources[]` field** — empty on all inspected projects. Pipeline writes to `p.evidence[]`. Consider removing the unused `sources` field from the project schema in a future backend cleanup so it's clear which field is authoritative.
- **Results summary line** — `#projectResultsSummary` element still in the DOM and still written by `renderProjectTable()`, now rendering as loose text above the table wrap with no visual container. Low priority cleanup.
- **Pagination UI** — still `PAGE_SIZE` + `projectPage` + "Load more projects" button. No virtual scrolling. Can grow tall on dense provinces like Ontario.

## Calendar Tab

Design-theme pass, hero card with This Week + Next Week stats, reskinned month grid, paginated scheduled-events table, merged global + Canadian watchlist data, restored broken pipeline exporter, and new `export_events_global()` bridge. **Locked 2026-04-10.** See `APPROVED_TEMPLATE_CALENDAR.md` for the full lock spec. 31 patches (CAL-01 through CAL-31) — the second half (CAL-24 onwards) was iterative refinement based on user feedback on the initial design-theme pass.

### Design-theme pass (CAL-01 through CAL-03)

- [x] **CAL-01**: Removed the Unsplash stock photo `<div class="section-banner">` from the Calendar panel in `docs/index.html` and `public/index.html`. The `photo-1519832979-6fa011b87667` clock image was inconsistent with the approved tabs (none of TL;DR / National / Provinces / Industries / Markets / Projects use section-banner images). Matches the PROJ-05 precedent.
- [x] **CAL-02**: Added `#tab-calendar` scoped CSS block in both `docs/index.html` and `public/index.html`, inserted immediately after the `#tab-projects` block. Copied verbatim from the approved vocabulary: `.cal-hero-stats` (Prussian blue rounded hero matching `.proj-hero-stats`), nested `.filter-bar` input/select overrides, `.section-header` / `.accent-bar` / `.section-block` rhythm, reskinned `.calendar-wrap` (drops glass-bg for solid white + `#d5dbe3` border), reskinned `.calendar-grid` / `.calendar-header-cell` (Prussian blue `#003153` day-of-week header with 11px white DM Sans uppercase), `.calendar-cell` with `#e8ecf0` separators and `#003153`-tinted `today` highlight, lightened `.cal-tooltip` (from dark `rgba(15,23,42,0.97)` to white + `#d5dbe3` border), and a new `.cal-events-table-wrap` + `.cal-events-table` block (rounded 8px wrap, Prussian blue thead, `#e8ecf0` row borders, `#f9fafb` zebra, `#e8eef4` hover, `.impact-pill` badges scoped to `#tab-calendar`).
- [x] **CAL-03**: Replaced the Calendar panel HTML shell in `docs/index.html` and `public/index.html`. New structure: (1) `.cal-hero-stats#calHeroStats` Prussian blue hero with `<h2>Economic Calendar</h2>` + "Scheduled economic releases, policy decisions, and events" subtitle on the left, 5 stat columns on the right (Upcoming, High Impact, This Week, Next BoC, Next StatCan) — `#calStatUpcoming`, `#calStatHigh`, `#calStatThisWeek`, `#calStatNextBoc`, `#calStatNextStatcan`. (2) Nested `.filter-bar#calendarFilterBar` with `#calSearch` input, `#calFilterImpact` select (All/High/Medium/Low), `#calFilterInstitution` select (populated dynamically), `#calFilterScope` select (All Upcoming / This Week / This Month / Next 3 Months). (3) `.section-block` containing `.section-header` + `#calendarGrid`. (4) `.section-block` containing `.section-header` + `#calendarEvents`. Deleted: `#thisWeekEvents` and `#allEventsTable` containers (consolidated into the single filter-driven `#calendarEvents` table).

### JS renderers rewritten (CAL-04 through CAL-06)

- [x] **CAL-04**: Rewrote `renderCalendar()` entry point in `docs/js/app.js` and `public/js/app.js`. New state: `_calFilter={impact:'',institution:'',scope:'upcoming',search:''}` and `_calWired=false`. New helper functions: `_calPopulateInstitutionFilter()` rebuilds the institution dropdown from unique `e.institution || e.source` values (preserves current selection), `_calRenderHeroStats()` computes Upcoming / High Impact / This Week counts plus Next BoC and Next StatCan dates via case-insensitive substring match on institution names, `_calWireFilters()` idempotently attaches `input`/`change` listeners to the 4 filter controls. Hero stat values use `.toLocaleString('en-CA')` for comma formatting (matches Projects convention). `_nextBy()` helper returns the soonest upcoming event matching an institution substring, formatted as `"Mon D"` (e.g., `"Apr 15"`) or `"—"` if none.
- [x] **CAL-05**: `renderCalendarGrid()` is largely unchanged in logic (same date-parse, same tooltip DOM) — the visual refresh comes from CAL-02's CSS. Only addition: writes the visible month name to `#calMonthMeta` (the section-header meta span) so the header shows "April 2026" next to the "Month View" title.
- [x] **CAL-06**: Rewrote `renderCalendarEvents()` as a single filterable `<table class="cal-events-table">`. Columns: Date (96px) | Event (auto-wrap) | Source/Institution (180px) | Impact (110px) | Link (78px). Date cell shows `Mon D` large + `Weekday · Year` small subcaption. Event cell shows bold 13px title + 11px factual description. Impact cell shows `.impact-pill` badge (light tint — `#fbeae0` bg / `#c4320a` text for high, `#fef3c7` / `#b45309` for medium, `#e8eef4` / `#003153` for low). Link cell uses shared `srcLink()` helper with the event's `source_url || url` and institution as title. Removed: the red `event-high-accent` left border, the 25-event hard cap on the "All Events" section, the glass-bg wrappers, and the two collapsible toggles. New `_calFilterEvents()` helper applies the 4 filters in order (scope date range → impact → institution → search substring) and sorts by ascending date. `#calEventsMeta` shows the filtered count (e.g., "21 events").

### Global events bridge file (CAL-08 through CAL-14)

The briefing pipeline's `D.watchlist` only tracks Canadian institutions (BoC, StatCan, Parliament). Added a static bridge file for US + European releases until the pipeline ingests them natively. All dates verified against official calendars via WebFetch.

- [x] **CAL-08**: Fetched 2026 FOMC meeting dates from `federalreserve.gov/monetarypolicy/fomccalendars.htm`. Six upcoming meetings extracted: Apr 29, Jun 17 (+SEP), Jul 29, Sep 16 (+SEP), Oct 28, Dec 9 (+SEP). SEP meetings are flagged with asterisks on the Fed's calendar.
- [x] **CAL-09**: Fetched 2026 BLS release dates for Employment Situation and Consumer Price Index via the OMB Principal Federal Economic Indicators schedule PDF (`statspolicy.gov/assets/fcsm/files/docs/OMB_pfei_schedule_release_dates_cy2026.pdf`). Direct bls.gov URLs returned 403; the OMB PDF is the authoritative cross-agency source. 8 Employment Situation dates + 9 CPI dates extracted for upcoming 2026.
- [x] **CAL-10**: Fetched 2026 BEA release dates for GDP advance estimates, Personal Income and Outlays (PCE), International Trade in Goods and Services, and International Transactions from `bea.gov/news/schedule`. 3 GDP advance estimates + 9 PCE releases + 8 International Trade releases extracted.
- [x] **CAL-11**: Fetched 2026 ECB Governing Council monetary policy meeting dates from `ecb.europa.eu/press/calendars/mgcgc/html/index.en.html`. 6 upcoming meetings: Apr 30, Jun 11 (+projections), Jul 23, Sep 10 (+projections), Oct 29, Dec 17 (+projections). Dates captured from the rate-announcement day (day 2 of each two-day meeting).
- [x] **CAL-12**: Fetched 2026 BoE MPC dates. Direct bankofengland.co.uk URLs returned 403; extracted from a secondary source (`mpc-mortgages.com`) that listed all 8 dates with MPR flagging. 6 upcoming dates: Apr 30 (+MPR), Jun 18, Jul 30 (+MPR), Sep 17, Nov 5 (+MPR), Dec 17. MPR (Monetary Policy Report) meetings are Feb/Apr/Jul/Nov per the page annotation.
- [x] **CAL-13**: Composed `docs/data/events_global.json` with 82 total events across 7 institutions: Federal Reserve (6 FOMC), Bureau of Labor Statistics (8 Employment Situation + 9 CPI = 17), Bureau of Economic Analysis (3 GDP advance + 9 PCE + 8 International Trade = 20), U.S. Census Bureau (9 Housing Starts + 9 Advance Retail Sales = 18), Federal Reserve Board (9 Industrial Production), European Central Bank (6 Governing Council), Bank of England (6 MPC). Each event has `date` (ISO YYYY-MM-DD), `institution`, `event_name`, factual `description` (no editorializing), `impact` (high/medium/low), and a real `source_url`. FOMC + Employment Situation + CPI + GDP advance + PCE = high impact. International Trade + Housing Starts + Retail Sales + Industrial Production + non-projection ECB/BoE = medium impact. Projection-release ECB/BoE meetings promoted to high. `_meta` block documents the four source URLs and the fetch date. Mirrored byte-identically to `public/data/events_global.json`.
- [x] **CAL-14**: Wired `events_global.json` into `renderCalendar()` in both `docs/js/app.js` and `public/js/app.js`. After loading `D.watchlist`, the function calls `fetchJSON('events_global.json')`, extracts the `events` array, and merges it into `_calEvents` with dedup by `(date + '|' + event_name)` key (protects against future overlap if the pipeline starts tracking the same events). The institution filter dropdown auto-populates with the new sources via `_calPopulateInstitutionFilter()` — no additional wiring needed.
- [x] **CAL-15**: PATCH_LOG note (this entry). The `events_global.json` file is a static bridge — it will not auto-refresh. Pipeline follow-up is required to:
  1. Add a Python component that fetches the same 4 calendars (Fed FOMC, OMB PFEI schedule, ECB, BoE) on the weekly pipeline run and rewrites `docs/data/events_global.json` with fresh dates.
  2. Alternatively, extend the briefing writer agent's watchlist generation to include US/European events so they flow through `D.watchlist` directly and `events_global.json` can be retired.
  3. Consider adding Whitehouse/Treasury events (quarterly refunding announcements, SOTU, Economic Report of the President) — these don't follow a fixed calendar and were skipped in this pass.
  4. Consider adding BLS PPI, BEA GDP 2nd/3rd estimates, BoJ, PBoC, and IMF/World Bank WEO releases in a future expansion.

### Files changed (Calendar Tab)

- `docs/index.html`:
  - Removed the Unsplash `.section-banner` from the `#tab-calendar` panel (CAL-01)
  - Added the `#tab-calendar` scoped CSS block (~lines 1160–1252 in the final state) covering hero card, filter bar overrides, section-header rhythm, reskinned calendar grid + light tooltip, and the new events table vocabulary (CAL-02)
  - Replaced the Calendar panel HTML with `.cal-hero-stats` (title + 5 stat slots + nested `.filter-bar`), plus two `.section-block` containers for `#calendarGrid` and `#calendarEvents` (CAL-03)

- `public/index.html`:
  - Byte-identical mirror of every `docs/index.html` change above

- `docs/js/app.js`:
  - `renderCalendar()` rewritten — loads `events_global.json`, merges with `D.watchlist`, populates institution filter, renders hero stats, wires filter listeners, then calls grid + events renderers (CAL-04, CAL-14)
  - New helpers `_calPopulateInstitutionFilter()`, `_calWireFilters()`, `_calRenderHeroStats()`, `_calFilterEvents()` added between `renderCalendar` and `renderCalendarGrid` (CAL-04, CAL-06)
  - `renderCalendarGrid()` now also writes visible month name to `#calMonthMeta` (CAL-05)
  - `renderCalendarEvents()` rewritten as a single filterable `<table class="cal-events-table">` (CAL-06)
  - Module state expanded: `_calFilter` filter state object, `_calWired` idempotency flag

- `public/js/app.js`:
  - Byte-identical mirror of every `docs/js/app.js` change above

- `docs/data/events_global.json`:
  - New file — 82 scheduled 2026 events from Fed, BLS, BEA, Census, Fed Board, ECB, BoE (CAL-13)

- `public/data/events_global.json`:
  - Byte-identical mirror of `docs/data/events_global.json`

### Tooltip flip (post-CAL-15)

- [x] **CAL-TOOLTIP-FLIP**: Changed `#tab-calendar .cal-tooltip` from `bottom:calc(100% + 6px)` to `top:calc(100% + 6px)` in both `docs/index.html` and `public/index.html`. User feedback: the upward-opening tooltip was getting clipped above the first row of the calendar grid. Side effect: tooltips on the last row of the month may now clip at the bottom instead — deferred as future-session follow-up with per-row open-up/open-down class toggling in JS if it becomes a problem.

### Provincial + federal fiscal expansion (CAL-16 through CAL-18)

Expanded the static bridge file with Canadian provincial 2026-27 budget tabling dates. All verified against news coverage that cites the finance ministry / legislative record. NL and PEI 2026-27 operating budgets did not have confirmed public dates at the time of this fetch and were skipped.

- [x] **CAL-16**: Fetched 2026-27 provincial budget tabling dates via WebSearch. Confirmed 8 provinces: BC (Feb 17, Bailey), NS (Feb 23, Lohr), AB (Feb 26, Horner), NB (Mar 17, Legacy), QC (Mar 18, Girard), SK (Mar 18, Reiter), MB (Mar 24, Sala), ON (Mar 26, Bethlenfalvy). All already-tabled at the time of this session (today = 2026-04-10) — included for calendar grid backward-navigation context and for pipeline seed data. NL expected "spring 2026" with no firm date; PEI 2026-27 operating budget not publicly confirmed (2026-27 capital budget was tabled in Nov 2025).
- [x] **CAL-17**: Searched for 2026 federal Fall Economic Statement (FES) date. Not yet announced as of 2026-04-10. The 2025 budget was tabled on 2025-11-04 by Finance Minister François-Philippe Champagne; the 2026 FES will be added to the schedule once the Department of Finance publishes a date.
- [x] **CAL-18**: Added the 8 verified provincial budgets to `events_global.json` (bringing total to 90 events across 15 institutions). Source URLs point to official finance ministry / news release pages (e.g., `news.gov.bc.ca/releases/2026FIN0003-000158`, `budget.ontario.ca/2026/`, etc.). Mirrored byte-identically to `public/data/events_global.json`.

### Pipeline integration (CAL-19 through CAL-21)

User directive: **"make sure our changes are also reflected in the pipeline"**. Investigation uncovered a pre-existing bug in `tools/export_dashboard.py` that was blocking all pipeline-side work. Fixed as part of this session.

- [x] **CAL-19 (BLOCKING BUG DISCOVERED)**: `tools/export_dashboard.py` was accidentally truncated on 2026-04-02 in commit `def2ea2` ("Replace Ollama/Qwen with NIM Nemotron for classification and discovery"). The truncation cut the file off mid-docstring at line 1160 (`"""Export combined sign`), removing three complete function definitions: `export_signals` body, `export_all`, `_validate_output`, and the `__main__` CLI block. Confirmed via `python ast.parse` → `SyntaxError: unterminated triple-quoted string literal (detected at line 1160)`. This made `from tools.export_dashboard import export_all` in both `update_dashboard.py:38` and `phases/finalize.py:332` crash at import time — the weekly pipeline could not run. Source: the previous commit `b26dc7a` had the file at 1233 lines; `def2ea2` shortened it to 1159 lines and cut the tail.
- [x] **CAL-20**: Restored `tools/export_dashboard.py` by diffing against the `b26dc7a` commit and the `.claude/worktrees/nostalgic-nightingale/tools/export_dashboard.py` checkpoint. Added the full original bodies of:
  1. `export_signals(conn, output_dir)` — writes `signals.json` with job_spikes / procurement / iaac summary, each section wrapped in try/except, reads from `job_snapshots` / `procurement_snapshots` / `projects` tables
  2. `export_all(conn=None, output_dir="docs/data") -> dict` — master orchestrator. Imports `PROVINCES`, loops over provinces calling `export_province_projects`, then calls `export_briefings` (tuple return), then each of `export_indicators`, `export_trends`, `export_events`, `export_timeseries`, `export_all_projects`, `export_pipeline_status`, `export_policy`, `export_commodities`, and iterates `(export_jobs, export_procurement, export_iaac, export_signals)` each wrapped in try/except with `logger.warning('Export %s failed: %s', export_fn.__name__, e)`. Writes `manifest.json` at the end. Returns `{file_count, output_dir, files_written}`.
  3. `_validate_output(output_dir)` — loads each JSON in the output directory and prints a summary table with file size and entry count, used in the `__main__` block
  4. `if __name__ == "__main__":` CLI block — argparse with `--out` (default `docs/data`) and `--db` options, calls `export_all` then `_validate_output`
  
  Note: the `_calc_changes(conn, indicator_name, alt_names)` function that was also removed in `def2ea2` was NOT restored, because that removal appears intentional (the surrounding `_build_market_data_from_indicators` function was simultaneously refactored to remove all `_calc_changes` call sites and inline plain dicts). Scope-respecting restoration — only undid the truncation, not the intentional refactor.
- [x] **CAL-21 (new function)**: Added `export_events_global(conn, output_dir)` to `tools/export_dashboard.py`. The function:
  - Reads from `config/events_global_schedule.json` (new file — the editable source of truth for the global-institutions schedule, relocated from `docs/data/` on this session)
  - Validates the structure has an `events` array
  - Refreshes the `_meta.exported_at` timestamp and `_meta.event_count` on every run so downstream consumers see the latest export time
  - Writes to `{output_dir}/events_global.json`
  - Has a clear docstring flagging future extension points: live fetches from Fed/BLS/BEA/ECB/BoE calendars, Whitehouse/Treasury events, IMF WEO/GEP, BoJ/PBoC/RBA/RBNZ, and provincial fall fiscal updates
  - `conn` parameter is accepted for signature compatibility with the other exporters but is unused today (everything comes from the config file)
- [x] **CAL-22**: Wired `export_events_global` into the restored `export_all` orchestrator. Placed immediately after `export_events` in the call chain, wrapped in try/except so a missing `config/events_global_schedule.json` degrades gracefully (logs a warning and skips). On success it appends the output filename to `files_written` so it shows up in the `manifest.json` file list.
- [x] **CAL-23**: Created `config/events_global_schedule.json` — the editable source of truth. Byte-identical copy of the hand-curated `docs/data/events_global.json` from CAL-13 + CAL-18. Going forward, this is the file to edit when adding new events; the weekly pipeline will copy it to `public/data/events_global.json` and `docs/data/events_global.json` on each run.

### Pipeline verification

- Verified `python ast.parse` on `tools/export_dashboard.py` → `syntax OK` (was `SyntaxError` before CAL-20)
- Verified `from tools.export_dashboard import export_all, export_events_global, export_signals, _validate_output` imports cleanly
- Verified `update_dashboard.py` parses (no longer blocks at line 38 import)
- Verified `export_events_global(None, tmpdir)` writes a valid 90-event JSON with refreshed `_meta.exported_at` and `_meta.event_count` fields
- Regenerated `public/data/events_global.json` and `docs/data/events_global.json` via `export_events_global` to confirm round-trip fidelity (same 90 events, new timestamp)

### Files changed (pipeline integration)

- `tools/export_dashboard.py` — Restored 274 lines at the tail (export_signals body, export_all, _validate_output, __main__ block). Added `export_events_global` function. Added `export_events_global` call to `export_all`. File now parses and imports cleanly. Went from 1159 lines (broken) to 1463 lines (working).
- `config/events_global_schedule.json` — New file. Canonical source for the global-institutions calendar. 90 events across 15 institutions (Fed FOMC, BLS, BEA, Census, Fed Board, ECB, BoE, plus 8 Canadian provincial finance ministries). Each event has `date` / `institution` / `event_name` / `description` / `impact` / `source_url`.
- `public/data/events_global.json`, `docs/data/events_global.json` — Regenerated via the pipeline export function; content is the same 90 events that were hand-written earlier in the session, now with an `_meta.exported_at` timestamp from the export run.

### Post-pipeline iteration (CAL-24 through CAL-31)

After the pipeline fixes landed, the user iterated on the Calendar tab visuals and interaction. Each of these patches was a targeted single-concern edit mirrored byte-identically to `public/`:

- [x] **CAL-24**: Dropped `Next BoC` and `Next StatCan` stat items from the hero card. Removed the two `<div class="stat-item">` nodes from both `index.html` files and deleted the corresponding `setText('calStatNextBoc', ...)` + `setText('calStatNextStatcan', ...)` + `_nextBy()` helper from `_calRenderHeroStats()` in both `app.js` files. Hero temporarily shrank from 5 stats to 3 (Upcoming, High Impact, This Week).
- [x] **CAL-25**: Moved the `.filter-bar#calendarFilterBar` out of the hero (where it was nested inside `.cal-hero-stats`) and into the "Scheduled Events" `.section-block`, placed directly above `#calendarEvents`. Removed the 4 dead `#tab-calendar .cal-hero-stats .filter-bar*` CSS rules from both `index.html` files. Added a new rule `#tab-calendar .section-block .filter-bar { margin: 0 0 16px; align-items: center }` + `select { max-width: 200px; text-overflow: ellipsis; overflow: hidden }` so the bar sits cleanly above the table on the white section background. No JS changes needed — the filter-bar element IDs (`#calSearch`, `#calFilterImpact`, `#calFilterInstitution`, `#calFilterScope`) are untouched so `_calWireFilters()` and `_calPopulateInstitutionFilter()` still bind correctly in the new DOM location.
- [x] **CAL-26**: Reverted the Calendar tab tooltip to the original dark theme + fixed the clipping at the source. Deleted 13 `#tab-calendar .cal-tooltip*` override rules from both `index.html` files (this was the light-theme block I added in CAL-02). With the overrides gone, the global `.cal-tooltip*` rules from `docs/index.html:374–392` take over: `rgba(15,23,42,0.97)` background, white text, pink/amber/blue impact badges, `bottom: calc(100% + 6px)` opening upward. Also removed `overflow: hidden` and `border-radius: 8px` from `#tab-calendar .calendar-grid` so the upward-opening tooltip can extend past the top and side edges of the calendar grid without being clipped. Supersedes the earlier CAL-TOOLTIP-FLIP patch (which changed direction instead of fixing the clipping source).
- [x] **CAL-27**: Paginated the Scheduled Events table. Added module state `let _calPage = 1` and `const CAL_PAGE_SIZE = 15` (later reduced to 10 in CAL-31). Rewrote `renderCalendarEvents()` to compute `totalPages = Math.ceil(events.length / CAL_PAGE_SIZE)`, clamp `_calPage` to `[1, totalPages]`, slice the filtered events to the current page, and render the rows. Added a `.cal-pagination` row below the table (only shown when `totalPages > 1`) with `‹ Prev` / `.cal-page-info` / `Next ›` buttons; Prev/Next are disabled at the edges via the `disabled` attribute + `opacity: 0.4; cursor: not-allowed` CSS. Added `window._calGoPage(n)` handler that updates `_calPage`, re-renders, and `scrollIntoView`s `#calendarEvents` so the user doesn't lose their place when clicking Next. `_calWireFilters()` listener now resets `_calPage = 1` on every filter change so you don't get stranded on page 5 after narrowing a search. Section-header meta expanded from `"N events"` to `"N events · page X of Y"` when pagination is active. New `.cal-pagination` CSS block scoped to `#tab-calendar` — buttons match `.calendar-nav-btn` styling (white background, `#d5dbe3` border, 6px radius, Prussian blue text).
- [x] **CAL-28**: Further reduced the hero from 3 stats to 2. Dropped `Upcoming` and `High Impact` stat items (removed HTML nodes + setText calls in both files). Added a new `Next Week` stat. `_calRenderHeroStats()` simplified to two focused day-window filters: `d >= now && d < now+7d` for This Week (days 0-6) and `d >= now+7d && d < now+14d` for Next Week (days 7-13). New element id `#calStatNextWeek`; `#calStatUpcoming` and `#calStatHigh` removed from markup and JS.
- [x] **CAL-29**: Tightened hero stat spacing and right-justified the stats. Changed `#tab-calendar .cal-hero-stats .cal-hero-stats-right` from `justify-content: space-around; gap: 16px` to `justify-content: flex-end; gap: 24px` so the 2 stats cluster at the right edge of the hero card instead of spreading across the whole right side with whitespace between them.
- [x] **CAL-30**: Removed the "April 2026" text that was appearing above the calendar in light grey. Deleted the `<span class="section-meta" id="calMonthMeta"></span>` from the Month View `.section-header` in both `index.html` files. Deleted the corresponding `const meta=$('calMonthMeta');if(meta)meta.textContent=monthName;` line at the end of `renderCalendarGrid()` in both `app.js` files. The month name is still shown inside the calendar wrap's `.calendar-nav-title` so there's no loss of information.
- [x] **CAL-31**: Dropped `CAL_PAGE_SIZE` from 15 to 10. Single-character change in both `app.js` files. With 94 total events (21 Canadian + 90 global, minus dedup overlaps), the paginated table now shows ~10 pages instead of 7.

### Known gaps for future sessions

- **Static bridge file is still static** — `config/events_global_schedule.json` is hand-curated. The pipeline copies it verbatim on each run but does not yet fetch live dates from source calendars. Future work: add `tools/events_global_fetcher.py` with functions to pull from federalreserve.gov, statspolicy.gov OMB PFEI, ecb.europa.eu, bankofengland.co.uk, and the provincial finance ministry pages, then merge into the config file with dedup by `(date, event_name)`.
- **Whitehouse/Treasury events** — no fixed release calendar; skipped in this pass. Manual entry for SOTU, Budget Request, quarterly refunding announcements, CEA Economic Report of the President.
- **Federal Fall Economic Statement 2026** — not yet announced as of 2026-04-10. Add to config when the Department of Finance publishes a date.
- **NL + PEI 2026-27 operating budgets** — not publicly confirmed at the time of this fetch. Add when available.
- **PPI + GDP 2nd/3rd estimates** — omitted for signal-to-noise; can be added later if users want fuller coverage.
- **BoJ / PBoC / RBA / RBNZ** — Asian/Pacific central banks not yet tracked.
- **IMF WEO + World Bank GEP** — semi-annual publications with known release windows (April/October for WEO, January/June for GEP); not yet added.
- **Provincial fall fiscal updates / mid-year reports** — typically Oct-Dec; add when individual provinces publish dates.
- **Event descriptions cross-ref** — existing `D.watchlist` descriptions reference Canadian pipeline counts ("The database tracks N projects"); `events_global.json` descriptions don't, since the bridge file doesn't have access to pipeline state. Cross-referencing is a pipeline-side concern — future work in `export_events_global` could augment descriptions with DB-derived counts.
- **`_calc_changes` refactor** — the Apr 2 commit removed `_calc_changes(conn, indicator_name, alt_names)` and simplified `_build_market_data_from_indicators` to emit plain dicts without wow/mom/yoy/52w fields. If the frontend markets renderer expects those fields, there may be a separate bug to investigate. This session did not touch that area — scope was explicitly limited to restoring the truncation.
- **Tooltip overflow on first-row or viewport-top cells** — the upward-opening dark tooltip can still clip above the browser viewport if the hovered cell is near the top of the visible area (the grid's `overflow: visible` fix only solves clipping inside the grid, not the viewport). Deferred as future work: detect cell row position in JS and toggle an `.opens-down` class on first-row cells, or pin the tooltip via `position: fixed` with JS-computed coordinates.
- **Lock status** — Calendar tab **LOCKED 2026-04-10**. `APPROVED_TEMPLATE_CALENDAR.md` created. `APPROVED_TEMPLATES.md` updated to mark Calendar as approved. The "Data Explorer" tab is now the only un-reviewed tab in the main nav.

## Data Explorer Tab

Design-theme pass, hero card with 4 stats (Indicators · V-Codes · StatCan Tables · Updated), scoped section rhythm across 6 sub-sections, reskinned charts/callouts/stat-card grids, paginated 5-column V-code table powered by a newly-unlocked 4,908-row StatCan table directory, and full inline-style cleanup. Also added a new pipeline exporter `export_statcan_tables()` that reads `config/statcan_table_registry.csv` and writes `docs/data/statcan_tables.json` — this file had been fetched by the frontend loader since launch but was never exported, so the "Full Directory" search had always silently returned 0 results. **Locked 2026-04-10.** See `APPROVED_TEMPLATE_EXPLORER.md` for the full lock spec. 13 patches (EXP-01 through EXP-13) — ordered pipeline-first so `statcan_tables.json` would exist before the frontend hero stats tried to read it.

### Pipeline work (EXP-10 through EXP-13)

Executed first because the hero stat "StatCan Tables: 4,908" depends on `statcan_tables.json` being present on disk. Investigation uncovered a latent bug: the async loader at `docs/js/app.js:5625` has always fetched `data/statcan_tables.json`, but no exporter had ever written it — the loader was silently catching the 404 in an empty `catch(e){}` block, leaving `_fullTableDir = []` and `_fullDirLoaded = false`. The old "Full Directory" stat pill in `_renderExplorerStats()` had therefore always shown `0` in grey with a "Loading directory…" suffix. Fixed as part of this session.

- [x] **EXP-10**: Added `export_statcan_tables(conn, output_dir)` to `tools/export_dashboard.py` at line 1275 (immediately after `export_events_global()`). The function:
  - Reads `config/statcan_table_registry.csv` (pre-existing 4,908-row file with columns `Table Name | Table ID | Product ID (raw) | CANSIM ID | Link | Frequency | Coverage | Focus | Subject Codes | Survey Codes | Start Date | End Date | Last Release | Status`)
  - Filters `Status == 'Current'` (no-op today since all 4,908 rows are `Current`, but forward-compatible against future archived entries)
  - Maps each row to the compact frontend-expected shape `{t, n, k, c, f, g}`:
    - `t` ← `Table ID` (e.g., `"34-10-0066-01"`)
    - `n` ← `Table Name`
    - `k` ← lowercase concatenation of `Table Name + Focus + Subject Codes` (keyword blob for the search scorer)
    - `c` ← `Focus` (category label — 34 distinct values observed, e.g., "Construction", "Health", "National accounts and GDP")
    - `f` ← `Frequency` as-is (13 distinct values — `Occasional`, `Monthly`, `Annual`, `Every 5 years`, etc. — passed through since the frontend `FREQ_MAP` falls back to raw strings for non-letter codes)
    - `g` ← `Coverage` normalized — `"National (default)"` and `"National"` both rewrite to `"Canada"`, other values preserved
  - Writes `{output_dir}/statcan_tables.json` as a **bare top-level array** (not wrapped in `{_meta, tables}`) via `json.dump(rows_out, f, ensure_ascii=False, separators=(",", ":"))`. Bare array matches what the frontend loader at `app.js:5632` expects (`raw.filter(r=>!curated.has(r.t))`), keeping the frontend change surface zero. Compact separators keep the output ~1.5 MB instead of ~3 MB.
  - `conn` parameter accepted for signature compatibility with the other exporters (unused today — everything comes from the CSV)
  - `import csv as _csv` scoped inside the function to keep the top-of-file import block stable (same pattern as `import sqlite3 as _sql` inside `export_indicators()`)
  - Logs `Exported N StatCan tables to {path}` on success via `logger.info`
- [x] **EXP-11**: Wired `export_statcan_tables()` into the `export_all()` orchestrator at line 1339, immediately after the `export_events_global()` call. Wrapped in `try/except` with `logger.warning("Export %s failed: %s", "export_statcan_tables", e)` so a missing CSV config degrades gracefully. On success appends `statcan_tables.json` to `files_written` which shows up in the `manifest.json` file list.
- [x] **EXP-12**: Ran `export_statcan_tables(None, 'docs/data')` and `export_statcan_tables(None, 'public/data')` to generate the initial file copies. Both write 4,908 rows (1,493 KB each) and SHA256-compare byte-identical. This is the first time `statcan_tables.json` has existed on disk — prior to this session the frontend loader's silent 404 had always left `_fullTableDir = []`.
- [x] **EXP-13**: Pipeline verification (CAL-23 pattern):
  - `python -c "import ast; ast.parse(open('tools/export_dashboard.py').read())"` → syntax OK
  - `python -c "import ast; ast.parse(open('update_dashboard.py').read())"` → syntax OK
  - `python -c "from tools.export_dashboard import export_all, export_statcan_tables, export_events_global, export_indicators, export_signals, _validate_output"` → imports cleanly
  - Dry-run via `export_statcan_tables(None, 'docs/data')` → valid 4,908-row JSON with correct shape
  - Spot-check of distinct values: 13 frequencies, 34 categories, 13 geographies — all as expected from the source CSV
  - `node -e "new Function(require('fs').readFileSync('docs/js/app.js','utf-8'))"` → JS syntax OK (6,281 lines)
  - `node -e "new Function(require('fs').readFileSync('public/js/app.js','utf-8'))"` → JS syntax OK (4,994 lines)

### Design-theme pass (EXP-01 through EXP-03)

- [x] **EXP-01**: Removed the Unsplash stock photo `<div class="section-banner">` from the Explorer panel in `docs/index.html` and `public/index.html`. The `photo-1460925895917-afdab827c52f` image was the last remaining Unsplash banner in the main nav and was inconsistent with the approved tabs (none of TL;DR / National / Provinces / Industries / Markets / Projects / Calendar use section-banner images). Matches the PROJ-05 and CAL-01 precedent.
- [x] **EXP-02**: Added an 80-line `#tab-explorer` scoped CSS block to both `docs/index.html` and `public/index.html`, inserted immediately after the `#tab-calendar` block. Copied verbatim from the approved vocabulary: `.exp-hero-stats` (Prussian blue rounded hero matching `.cal-hero-stats` / `.proj-hero-stats`), `.section-header` / `.accent-bar` / `.section-block` rhythm, `.exp-card` (white rounded 8px card with `#d5dbe3` border and `var(--shadow-sm)`), `.exp-card-title` / `.exp-card-sub` / `.exp-card-footlink`, `.exp-control-row`, `.exp-select` (reskinned from `#c0c0c0`/`#f0f0f0` to `#ffffff`/`#d5dbe3`), `.exp-range-group` + `.exp-range-btn` / `.exp-range-btn.active` (reskinned from `#2563EB` to `#003153`), `.exp-callout` + `.exp-callout-value` / `.exp-callout-chg.{up,down,flat}` / `.exp-callout-meta` / `.exp-callout-empty`, `.exp-chart-wrap` (240px fixed height), `.exp-stat-grid` + `.exp-stat-card` / `-label` / `-value` / `-period` (reskinned from `#f8fafc` / `#e2e8f0` to white / `#e8ecf0`), `.exp-search-row` + `.exp-search-input` / `.exp-search-btn` (Prussian blue button), `.exp-cat-row` + `.exp-cat-btn`, `.exp-empty` (white rounded 8px empty state card), `.exp-vcode-table-wrap` + `.exp-vcode-table` (rounded 8px wrap, Prussian blue thead, 5 explicit column widths, `.exp-vcode-code` / `.exp-vcode-title` / `.exp-vcode-meta` / `.exp-vcode-tbl` / `.exp-vcode-cat` classes, zebra rows, `#e8eef4` hover, `#e8ecf0` row and column borders), `.exp-pagination` + `.exp-page-info` (copy of `.cal-pagination`).
- [x] **EXP-03**: Replaced the Explorer panel HTML shell in `docs/index.html` and `public/index.html`. New structure: (1) `.exp-hero-stats#expHeroStats` Prussian blue hero with `<h2>Data Explorer</h2>` + "Indicators, provincial accounts, StatCan table directory" subtitle on the left, 4 stat columns right-justified (Indicators, V-Codes, StatCan Tables, Updated) — `#expStatIndicators`, `#expStatVcodes`, `#expStatTables`, `#expStatUpdated` — all initialized to `—` in the static HTML and populated by `_expRenderHeroStats()` at render time. (2) Six `.section-block` containers, each with a `.section-header` + `.accent-bar` + `<h3>` titled "StatCan Key Economic Indicators" / "Provincial Indicator Explorer" / "Ontario Economic Accounts" / "Quebec Economic Accounts (ISQ)" / "Provincial Raw Indicators" / "StatCan Table Search". The Table Search header also has a `.section-meta#expSearchMeta` span for the "N results · page X of Y" pagination indicator. All inner div IDs preserved (`#canadaIndicatorSection`, `#canadaIndicatorDropdown`, `#indicatorExplorer`, `#provExpSection`, `#oeaSection`, `#isqSection`, `#provIndicatorSection`, `#explorerSearch`, `#explorerCategories`, `#explorerResults`) so the existing renderer functions still find their targets. Deleted: the 11-line skeleton of empty divs with inline margin styles, and the dead `#explorerStats` div that was written to by the now-removed `_renderExplorerStats()` helper.

### JS renderers + hero stats (EXP-04 through EXP-05)

- [x] **EXP-04**: New `_expRenderHeroStats()` function in `docs/js/app.js` and `public/js/app.js`. Computes the 4 hero stats from real data:
  1. **Indicators** — `_indJsonCache.indicators.length` (713 at current pipeline state), falls back to `indicators.length` if the JSON cache is empty
  2. **V-Codes** — `VCODE_INDEX.length` (125, bundled constant)
  3. **StatCan Tables** — `_fullTableDir.length + VCODE_INDEX.length` once `_fullDirLoaded === true` (4,908 after the async load resolves); shows `…` placeholder during the load
  4. **Updated** — parses `_indJsonCache.statcan_latest.updatedAt` as a Date and formats via `toLocaleDateString('en-CA', {month:'short', day:'numeric'})` (e.g., `"Mar 31"`); falls back to the raw string if Date parse fails, or `—` if missing
  All writes via a locally-scoped `setText(id, val)` closure that safely no-ops if the target element doesn't exist. Function called from (a) `renderExplorer()` on every tab render and (b) the async `statcan_tables.json` loader at `app.js:5625` once the fetch resolves — the loader's old call to `_renderExplorerStats()` was replaced with `if(typeof _expRenderHeroStats==='function')_expRenderHeroStats()` to update the "StatCan Tables" stat after the ~200 ms async load. Dead `_renderExplorerStats()` helper removed entirely (this is what used to render the broken "Total Tables / Curated / Full Directory" three-pill row).
- [x] **EXP-05**: V-Code search rewritten as a paginated 5-column `.exp-vcode-table`. Dropped the existing 25-result hard cap and the `.card`-stack result layout. New module state: `let _expSearchPage = 1`, `const EXP_PAGE_SIZE = 10`, `let _expLastQuery = ''`. New helpers:
  - `_expSearchAll(query)` — full unsliced scorer that duplicates the logic of `searchVCodes()` but does not `.slice(0, 25)` at the end. Returns the complete sorted match set so pagination can walk it.
  - `_expEscapeHtml(s)` — escapes `& < > "` in all user-facing strings written into the table, protecting against malformed StatCan titles breaking the DOM.
  - `_expRenderVcodeResults()` — the actual renderer. Reads `_expLastQuery`, calls `_expSearchAll()`, computes `totalPages = Math.max(1, Math.ceil(results.length / EXP_PAGE_SIZE))`, clamps `_expSearchPage` to `[1, totalPages]`, slices to the current page, and writes the rendered table + optional `.exp-pagination` row to `#explorerResults`. Columns: V-Code (110px) | Table (130px) | Title (auto-wrap with optional `freq · geo` subcaption) | Category (180px) | Link (70px, centered `↗` anchor). Updates `#expSearchMeta` to `"N result"` / `"N results"` / `"N results · page X of Y"`.
  - `window._expGoPage(n)` — updates `_expSearchPage`, re-renders, and `scrollIntoView`s `#explorerResults` so the user doesn't lose their place when clicking Next.
  - `window._doVcodeSearch(cat)` is now a thin wrapper: sets `_expLastQuery` from the search input or category chip, then calls `_expRenderVcodeResults()`. Both the input's Enter keypress and the category chip clicks reset `_expSearchPage = 1` before running the search.

### Inline-style cleanup (EXP-06 through EXP-09)

User explicit approval: "you can clean the inline styles." Every `style="..."` blob inside Explorer-rendered HTML was removed and replaced with scoped `#tab-explorer` classes.

- [x] **EXP-06**: Cleaned up the 4 "sub-explorer" card sections — `renderIndicatorExplorer()`, `_renderProvExplorer()`, `_renderOeaSection()`, `_renderIsqSection()`, plus the `canadaIndicatorSection` inner HTML written inside `renderExplorer()`. All removed the `<div class="mkt-section" style="background:rgba(255,255,255,0.95);border-radius:var(--radius-md);padding:20px">` wrapper in favor of `<div class="exp-card">`. All removed the inline `<h3 style="font-family:...;font-size:15px;font-weight:700;color:#003153;margin:0 0 4px">` titles in favor of `<div class="exp-card-title">`. All removed the `<p style="font-size:var(--text-sm);color:#475569;margin:0 0 14px">` sub-descriptions in favor of `<div class="exp-card-sub">`. All converted the `<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px">` control rows to `<div class="exp-control-row">`. All converted `<select style="padding:6px 10px;border-radius:6px;border:1px solid #c0c0c0;background:#f0f0f0;color:#1a2744;font-size:var(--text-sm)">` to `<select class="exp-select">`. All converted the 3M/1Y/3Y/5Y button row from `<div style="display:flex;gap:4px"><button onclick="..." style="padding:4px 10px;border-radius:4px;border:none;cursor:pointer;font-size:var(--text-xs);background:#2563EB;color:#FFFFFF">...</button>` to `<div class="exp-range-group"><button class="exp-range-btn active" onclick="...">...</button>`. All converted `<div style="height:220px;position:relative"><canvas ...></canvas></div>` chart wrappers to `<div class="exp-chart-wrap"><canvas ...></canvas></div>` (wrap height bumped from 220px to 240px for visual parity with the Calendar section). `renderIndicatorExplorer()` source link at the bottom replaced `<div style="margin-top:8px;text-align:right"><a href="..." style="font-size:var(--text-xs);color:var(--accent-blue)">...</a></div>` with `<div class="exp-card-footlink"><a href="...">...</a></div>`.
- [x] **EXP-07**: Cleaned up the 4 callout-rendering functions — `loadIndExpData()`, `_loadProvExpData()`, `_loadOeaData()`, `_loadIsqData()`. All converted from `callout.innerHTML='<div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap"><span style="font-size:1.5rem;font-weight:700;font-family:DM Sans,sans-serif">...</span><span class="change-up" style="font-family:var(--font-mono);font-size:var(--text-sm)">...</span>...</div>'` to `callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">...</span><span class="exp-callout-chg up">...</span><span class="exp-callout-meta">...</span></div>'`. Class names `change-up` / `change-down` / `change-flat` changed to the shorter `up` / `down` / `flat` scoped as children of `.exp-callout-chg` (so the global `.change-up` styling in a frozen tab isn't accidentally inherited). Empty states converted from `<span style="color:#64748B;font-size:var(--text-sm)">No data for this period.</span>` to `<div class="exp-callout"><span class="exp-callout-empty">No data for this period.</span></div>`. Also cleaned up the two "latest value" card grids in `_renderOeaLatestTable()` and `_renderIsqLatestTable()` from `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px"><div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px"><div style="font-size:10px;color:#64748B;text-transform:uppercase;letter-spacing:0.5px">...</div>...</div></div>` to `<div class="exp-stat-grid"><div class="exp-stat-card"><div class="exp-stat-card-label">...</div><div class="exp-stat-card-value">...</div><div class="exp-stat-card-period">...</div></div></div>`.
- [x] **EXP-08**: Cleaned up `renderExplorer()` itself. Search row converted from `<div style="display:flex;gap:8px"><input ... style="flex:1;padding:10px 14px;border-radius:var(--radius-md);border:1px solid var(--border-light);background:var(--bg-white);..."><button style="padding:10px 20px;border-radius:var(--radius-md);border:none;background:var(--accent-blue);color:#fff;...">Search</button></div>` to `<div class="exp-search-row"><input type="text" id="vcodeSearch" class="exp-search-input" ...><button class="exp-search-btn" ...>Search</button></div>`. Category chips converted from `<div style="display:flex;gap:6px;flex-wrap:wrap"><button onclick="..." style="padding:6px 14px;border-radius:20px;border:1px solid var(--border-light);background:var(--bg-white);color:#2d3a52;..."></button></div>` to `<div class="exp-cat-row"><button class="exp-cat-btn" onclick="...">...</button></div>`. Initial empty state converted from `<div style="color:#556B7A;font-size:var(--text-sm);padding:20px 0">Enter a search term...</div>` to `<div class="exp-empty">Enter a search term...</div>`. Provincial raw indicators section (`#provIndicatorSection`) converted from an inline `<h3 style="...">` + `<p style="...">` header to an `<div class="exp-card"><div class="exp-card-title">...</div><div class="exp-card-sub">...</div>...</div>` wrapper. The entire `_renderExplorerStats()` helper was removed (dead code after EXP-04), along with the `#explorerStats` div it used to write to.
- [x] **EXP-09**: Cleaned up the V-code table rendering in `_expRenderVcodeResults()`. One remaining inline `style="text-align:center"` on the link `<td>` was replaced with `class="exp-col-link"` + a new `#tab-explorer .exp-vcode-table tbody td.exp-col-link{text-align:center}` rule in the scoped CSS block. Zero inline styles remain in any Explorer-related renderer after this patch.

### Files changed (Data Explorer Tab)

- `docs/index.html`:
  - Removed the Unsplash `.section-banner` from the `#tab-explorer` panel (EXP-01)
  - Added the `#tab-explorer` scoped CSS block (~80 lines, inserted after the `#tab-calendar` block) covering hero card, section-header rhythm, exp-card, reskinned form controls, callout, chart-wrap, stat-card grid, search row, category chips, empty state, 5-column paginated V-code table with Prussian blue thead and zebra rows, and pagination (EXP-02, EXP-09)
  - Replaced the Explorer panel HTML with `.exp-hero-stats` (title + 4 stat slots) and six `.section-block`s with `.section-header` + inner containers (EXP-03)

- `public/index.html`:
  - Byte-identical mirror of every `docs/index.html` change above (verified via SHA256 on the Explorer CSS and HTML panel regions)

- `docs/js/app.js`:
  - `renderIndicatorExplorer()` rewritten with `.exp-card` / `.exp-control-row` / `.exp-select` / `.exp-range-btn` / `.exp-chart-wrap` / `.exp-card-footlink` classes (EXP-06)
  - `loadIndExpData()` callout rewritten with `.exp-callout` / `.exp-callout-value` / `.exp-callout-chg.{up,down,flat}` / `.exp-callout-meta` / `.exp-callout-empty` classes (EXP-07)
  - Async table directory loader at `~5625` — added `_expSearchPage = 1` + `EXP_PAGE_SIZE = 10` module state, changed the post-load hook from `_renderExplorerStats()` to `if(typeof _expRenderHeroStats==='function')_expRenderHeroStats()` (EXP-04)
  - New `_expRenderHeroStats()` function (~5738) — replaces the dead `_renderExplorerStats()` with the 4-stat hero renderer (EXP-04)
  - `renderExplorer()` rewritten with `.exp-search-row` / `.exp-cat-row` / `.exp-empty` / `.exp-card` wrappers, calls `_expRenderHeroStats()` on every render (EXP-04, EXP-08)
  - `_renderProvExplorer()` + `_loadProvExpData()` callout reskinned to `.exp-card` + `.exp-callout` vocabulary (EXP-06, EXP-07)
  - `_renderOeaSection()` + `_renderOeaLatestTable()` + `_loadOeaData()` callout reskinned to `.exp-card` + `.exp-stat-grid` + `.exp-callout` (EXP-06, EXP-07)
  - `_renderIsqSection()` + `_renderIsqLatestTable()` + `_loadIsqData()` callout reskinned identically (EXP-06, EXP-07)
  - New `_expSearchAll()` helper (~6113) — full-unsliced scorer bypassing `searchVCodes()`'s 25-result cap (EXP-05)
  - New `_expEscapeHtml()` helper (~6134) — HTML escape for the paginated table (EXP-05)
  - `window._doVcodeSearch()` rewritten as a thin wrapper that sets `_expLastQuery` and calls `_expRenderVcodeResults()` (EXP-05)
  - New `_expRenderVcodeResults()` function (~6155) — paginated 5-column table renderer (EXP-05, EXP-09)
  - New `window._expGoPage()` handler (~6197) — pagination click handler with scroll-into-view (EXP-05)
  - Dead `_renderExplorerStats()` helper removed (EXP-04, EXP-08)

- `public/js/app.js`:
  - Byte-identical mirror of every `docs/js/app.js` change above. Verified via SHA256 on two regions:
    - `renderIndicatorExplorer()` through end of `loadIndExpData()` = 8,148 bytes, matching hash
    - `/* ====== PHASE 4: DATA EXPLORER */` through end of the V-code search block = 56,439 bytes, matching hash

- `docs/data/statcan_tables.json`:
  - **New file** — 4,908 rows (1,493 KB) generated by `export_statcan_tables()` from `config/statcan_table_registry.csv`. This file had been fetched by the frontend loader since launch but never written — EXP-10 through EXP-13 are the first time it has existed on disk (EXP-12)

- `public/data/statcan_tables.json`:
  - New file — byte-identical mirror of `docs/data/statcan_tables.json` (same SHA256) (EXP-12)

- `tools/export_dashboard.py`:
  - New `export_statcan_tables(conn, output_dir)` function at line 1275 — reads the CSV, filters `Status=='Current'`, maps to `{t,n,k,c,f,g}` shape, writes a bare top-level array as compact JSON (EXP-10)
  - `export_all()` extended with the `export_statcan_tables` call at line 1339, wrapped in try/except matching the `export_events_global` pattern (EXP-11)
  - File now 1,530 lines (was 1,463 after the CAL-20 restoration)

- `APPROVED_TEMPLATE_EXPLORER.md`:
  - New file — full lock spec with all 14 sections (lock state, page structure, hero card, 6 sections, data flow, `statcan_tables.json` format, pipeline integration, editorial rules, design vocabulary, files of record, known gaps, and locked patch set)

- `APPROVED_TEMPLATES.md`:
  - Updated "Data Explorer Tab" section from `_(not yet reviewed)_` placeholder to an "Approved 2026-04-10" block pointing at `APPROVED_TEMPLATE_EXPLORER.md`

### Known gaps for future sessions

- **Registry is still hand-curated** — `config/statcan_table_registry.csv` is 4,908 rows of manual data. The pipeline now copies it to `statcan_tables.json` verbatim on each run but does not fetch fresh metadata from StatCan's product API. Future work: build `tools/statcan_registry_fetcher.py` that pulls the latest table list from StatCan's discovery endpoint and merges into the CSV with dedup by `Table ID` before the export runs.
- **`Code 19` / `Code 20` frequency values** — 99 rows in the registry have these uninterpreted StatCan internal codes. They pass through to the frontend search results unchanged and show up in search results as the literal strings. Future work: map them to real frequency meanings once documented, or filter them out at export time if known to be deprecated.
- **"Unclassified" Focus category** — 525 rows in the registry have `Focus == 'Unclassified'`. They are preserved in the export (so keyword search still finds them) but cluster into a single large generic category. Future work: add a name-substring-based secondary classifier inside `export_statcan_tables()` that assigns a better category.
- **V-code search has no frequency/geography filters** — only the 14 preset category chips. Users can't narrow by frequency ("only Monthly") or geography ("only CMAs"). Future work: add a filter bar above the results table with `<select>`s bound to the 13 frequency and 13 geography values observed.
- **No autocomplete on the search input** — users can't see matching tables as they type. Future work: debounced on-input preview dropdown.
- **`_fullDirLoaded` flicker** — on the very first Explorer tab click, the hero briefly shows "StatCan Tables: `…`" until the async load resolves (~200 ms on localhost). Acceptable as-is; could be eliminated by awaiting the load before the first `_expRenderHeroStats()` call.
- **Global `public/` drift** — `public/index.html` and `public/js/app.js` are NOT byte-identical to `docs/` at a whole-file level. They diverged long before this session (public is ~263 lines shorter in HTML and ~1,384 lines shorter in JS). The Explorer region (CSS + HTML + JS) IS byte-identical across both, verified via SHA256. The session rule is "byte-identical in the touched region", which holds. Future work (out of scope) would be to reconcile the global drift via `tools/deploy_to_github.py`.
- **`renderIndicatorExplorer()` scope** — this renderer is called only from `renderExplorer()` at `docs/js/app.js:5810` and recursively from its own `onIndExpChange()` handler at ~2696. Verified via grep. If a future session wants to show the indicator explorer chart on a frozen tab, the `.exp-card` classes will need to be mirrored or promoted to a shared scope.
- **No unit tests** — following the CAL/PROJ/MKT session convention. Future work: `tests/test_explorer.py` covering `export_statcan_tables()` row shape, `_expSearchAll()` result count + score ordering via a headless browser or jsdom harness.
- **Lock status** — Data Explorer tab **LOCKED 2026-04-10**. `APPROVED_TEMPLATE_EXPLORER.md` created. `APPROVED_TEMPLATES.md` updated to mark Data Explorer as approved. **All 8 tabs in the main nav are now locked:** TL;DR (2026-04-07), National (2026-04-07), Provinces (2026-04-09), Industries (2026-04-09), Markets (2026-04-09), Projects (2026-04-10), Calendar (2026-04-10), Data Explorer (2026-04-10).
