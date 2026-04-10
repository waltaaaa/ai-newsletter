# Approved Template — Industries Tab

**Reference industry:** Agriculture (NAICS 11) — approved 2026-04-09
**Status:** Template locked for ALL 20 NAICS industries — approved 2026-04-09 (IND-05 + IND-06).
**Purpose:** Source of truth for the Industries tab layout, data, and editorial rules. Use this file (instead of the full `APPROVED_TEMPLATES.md`) when resuming Industries work to keep context lean.

## Lock state (2026-04-09)

All 20 industries use the same page structure, hero card, subsector chip strip, insight chart, Key Indicators row spec, and Project Pipeline table documented below. The approved set covers:

- Goods (5): 11, 21, 22, 23, 31-33
- Services (15): 41, 44-45, 48-49, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 91

Per-industry Key Indicators row counts (including the 2 universal GDP rows prepended by the renderer): 11=16, 21=15, 22=12, 23=17, 31-33=15, 41=12, 44-45=14, 48-49=12, 51=11, 52=14, 53=14, 54=12, 55=10, 56=11, 61=11, 62=11, 71=10, 72=11, 81=11, 91=13.

Subsector chips for all 20 industries display real M/M and Y/Y computed from StatCan 36-10-0434 (latest period 2026-01-01 as of the lock).

Next available indicator ID after the lock: **68621**.

---

## Page structure (top → bottom)

1. **Sub-nav bar** — horizontal charcoal pill bar with 20 NAICS short-code pills (5 goods + separator + 15 services). Same charcoal style as the provinces sub-nav. Click toggles `selectedIndustry` and calls `_renderIndContent()`.
2. **Hero card** (Prussian blue) — title + subtitle + 4 stat columns + subsector chip strip
3. **Industry Analysis section** — narrative prose + insight chart callout + collapsible sources footer
4. **Key Indicators table** — industry-specific rows from `IND_KEY_INDICATORS[code]`
5. **Project Pipeline table** — projects filtered by NAICS prefix, top 10 by value

The standalone "Subsector Detail" table section that used to sit between Key Indicators and Project Pipeline has been **removed** — subsectors now live as chips in the hero card.

---

## 1. Sub-nav bar

Untouched from pre-approval. Horizontal pill list using the existing `.ind-bar` / `.ind-pill` CSS in `docs/index.html`. Short codes defined in `IND_SHORT` const in `docs/js/app.js`. 20 industries across 2 rows (5 goods + 15 services) with a vertical separator.

Selected pill is white text with white underline. Hover brightens. Territories-equivalent (services group) is slightly dimmed for visual hierarchy.

---

## 2. Hero card

**Container:** `.industry-header-card` — Prussian blue `#003153`, 28px × 32px padding, 8px radius, `display: flex; flex-direction: column; gap: 20px`.

**Top row** (`.industry-header-top`) — flex row, space-between, flex-wrap:
- **Left:** `<h2>` industry name + `<div class="industry-sub">Weekly industry analysis · NAICS {code}</div>`
- **Right:** `.industry-header-stats` — flex row of 4 stat columns, text-align right, gap 32px. Each column has `.stat-value` (22px/700) + `.stat-label` (10px uppercase).
  1. **GDP M/M** — `mmArr san(mm)` with `chg-up` / `chg-down` / `chg-flat` class
  2. **GDP Y/Y** — same treatment
  3. **Active Projects** — count (pre-filtered by NAICS prefix)
  4. **Pipeline Value** — sum of tracked project values, formatted `$X.XB` or `$X.XM` or `—`

**Bottom row** (`.industry-subsector-strip`) — appears directly below the top row, separated by a subtle 1px `rgba(255,255,255,0.12)` top border, 16px top padding:
- Label: `SUBSECTORS (N)` in 10px uppercase `rgba(255,255,255,0.6)`
- Chips row (`.ind-strip-chips`) — flex wrap, 10px gap
- Each chip (`.ind-subsector-chip`) — pill-shaped, contains: `.ind-chip-name` (bold) + `.ind-chip-code` (10px muted NAICS code) + `.ind-chip-chg` (M/M badge, separated by a vertical divider)
- Chip color states:
  - `.chip-up` — green tinted bg + border + `#6ee7b7` change text (numeric positive M/M)
  - `.chip-down` — red tinted bg + border + `#fca5a5` change text (numeric negative)
  - `.chip-flat` — neutral bg + `rgba(255,255,255,0.42)` change text (N/A or missing)
- Soft-status words like "declined" / "rose" get directional coloring via keyword matching in the renderer

**Subsector chip data population (locked as of IND-06):** Each subsector's `mm` and `yy` fields in `briefing_latest.json` → `goodsIndustries[i].subsectors[j]` / `servicesIndustries[i].subsectors[j]` are populated from StatCan Table 36-10-0434 "Real GDP by Industry, monthly". Coordinate template: `1.1.1.<dim4>.0.0.0.0.0.0` — dim1=Canada, dim2=Seasonally adjusted at annual rates, dim3=Chained 2017 dollars, dim4=NAICS member index (249 members). latestN=14 per vector; M/M computed from latest two points, Y/Y from latest vs 12-months-prior.

**Proxy fallbacks (documented in `tmp_subs_fetch/FETCH_REPORT.md`)** — 16 of 60 subsector codes aren't published at the exact NAICS level in 36-10-0434 and fall back to parent or cube-specific aggregates:
- 236/237/238 → 23A/23X/23D (cube uses construction subtype aggregates, not NAICS-3 splits)
- 452 → 455 (NAICS 2022 renumber)
- 511 → 513 (NAICS 2022 renumber)
- 522/523/524 → 52BX/52C/5241 aggregates
- 541 → 54 parent (legal/scientific detail not published at 3-digit level)
- 551/5511/55111 → 55 parent (all three entries share the same 2-digit series)
- 5621 → 562 parent
- 711/712 → 71A (performing-arts + heritage combined)
- 7211 → 721 parent

This is honest data limitation, not fabrication — numbers are real StatCan values at whatever aggregation the cube actually publishes.

**Active Projects and Pipeline Value are exclusively in the hero card banner.** They are NOT duplicated in the Key Indicators table.

---

## 3. Industry Analysis section

**Heading:** `<h3>Industry Analysis</h3>` inside a `.section-block` with the standard accent-bar + section-header pattern.

### Narrative
- **Source:** `industry.analysis` field in the briefing JSON (HTML string with `<p>` and `<sup>` tags)
- **Word count:** **150–200 words** across 3–4 paragraphs ideal; the locked IND-05 pass sets most non-Agriculture industries at 120–160 words across 3 paragraphs as an acceptable floor. Agriculture reference: 193 words across 4 paragraphs.
- **Paragraph structure** (Agriculture example):
  1. **Sector performance** — GDP print + top story of the week (the sector's main driver, e.g., commodity price, major project, policy event) + 1 contextual data point
  2. **Project pipeline / policy angle** — project count + value + anchor project + policy/trade context
  3. **Labour + input costs + conditions** — employment, wages, input price indexes, growing conditions (or equivalent sector conditions)
  4. **Commodity / price action** — spot prices and recent moves across the sector's key markets
- **Lead sentences:** Each paragraph opens with a `<span class="lead-sentence">...</span>` followed by ` — ` em-dash. `addLeads()` auto-wraps if the span is absent.
- **Factual only** — no editorializing (see Editorial Rules section below)
- **Footnote citations** in `<sup>N</sup>` tags, mapped to `industry.industrySources[N-1]`. Existing citations with high numbers (40, 75, 153...) are legacy from a larger global index and render as decorative superscripts — new citations should use 1-based indices matching `industrySources[]`.
- **Sources footer** — `<details class="sources-section"><summary>Sources (N)</summary><ol>...</ol></details>`, linked list of `{url, title}` from `industrySources[]`

### Insight chart callout
- **Container:** Empty `<div id="indInsightChartArea">` injected at render time by `buildIndInsightStrip(spec)`
- **Spec source:** `industry.insightCharts[0]` — produced by the extended `tldr-charts` skill during the weekly pipeline run
- **Chart types supported:** `line`, `multi_line` (with first-point normalization to 100), `bar`, `diverging_bar`
- **Data source:** `dataSource: "indicators"` (→ reads `_getHistory()` from indicators.json) or `dataSource: "timeseries"` (→ `fetchJSON('timeseries.json')`)
- **Window:** capped at 24 months via `_indWindowMonths()`. Spec values: `"6m"`, `"12m"`, `"18m"`, `"24m"`
- **Callout text:** `spec.callout` (user-facing, references the visible chart, distinct from analysis narrative) with fallback to `spec.reasoning`
- **Styling:** Prussian blue left border, light blue background, matches TL;DR callout pattern — `.tldr-callout` wrapper, `.tldr-callout-chart` inner, `.tldr-callout-chart-title`, `.tldr-callout-source`
- **Canvas:** `<canvas id="indInsightChart">` inside a 320px-tall white box
- **Y-axis:** `beginAtZero: false` + `grace: '8%'` so line charts show variation rather than compressing near the top
- **Endpoint marker:** last data point gets a 5px filled circle; intermediate points hidden
- **Source attribution:** StatCan link for `indicators` source, generic "Market data" for `timeseries`

### Chart-spec contract (stored in `briefing_latest.json`)
```json
{
  "chartType": "line" | "multi_line" | "bar" | "diverging_bar",
  "dataKeys": ["gdp_agriculture"],
  "dataSource": "indicators",
  "window": "24m",
  "title": "Agriculture Real GDP — 24 Month Trajectory",
  "subtitle": "StatCan 36-10-0434 · Chained 2017 dollars",
  "yAxisLabel": "Index (2017=100)",
  "reasoning": "Internal rationale (not rendered)",
  "callout": "2-3 sentences referencing what's visible in the chart. Must be distinct from the analysis narrative."
}
```

See `.claude/skills/tldr-charts/SKILL.md` for the full skill definition, the Industry → Primary Data Key Map, and the chart selection procedure.

---

## 4. Key Indicators table

**Purpose:** Industry-specific data — NOT a generic meta-table. Every industry has its own set of relevant indicators.

**Structure:**
- `.section-block` > `.section-header` "Key Indicators" with meta `{industryName} · NAICS {code}`
- `.indicator-panel` > `<table class="ind-table">`
- **5 columns:** Indicator | Frequency | Value | Change | Source
- Every row has a period subtitle under the indicator name (e.g., "Jan 2026", "Q3 2025") in `.ind-t-name-ctx` grey 11px text

**Row composition** (assembled in this order):
1. **Real GDP (M/M)** — universal, from `industry.mm` (briefing)
2. **Real GDP (Y/Y)** — universal, from `industry.yy` (briefing)
3. **Industry-specific rows** — resolved from `IND_KEY_INDICATORS[code]` via `_indResolveKeyRow(spec, tsData)`
4. **(No footer rows)** — Active Projects and Pipeline Value stay in the hero banner

### Mapping contract: `IND_KEY_INDICATORS[naicsCode]`
Defined in `docs/js/app.js` at the top of the Industry insight chart infrastructure block. Each entry is a list of row specs:

```js
{
  label: 'Farm Cash Receipts',          // display name
  key: 'farm_cash_receipts',            // key in indicators.json or timeseries.json
  source: 'indicators' | 'timeseries',  // which file to resolve against
  unit: '$M',                            // unit hint for formatter
  freq: 'Quarterly',                    // optional — overrides frequency heuristic
  chgLabel: 'vs 2024',                  // optional — suffix appended to change (e.g., annual Y/Y)
  srcLabel: 'StatCan 32-10-0046',       // displayed in Source column
  srcUrl: 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210004601'
}
```

### `_indResolveKeyRow(spec, tsData)` behavior
- **indicators source:** picks the latest national-level row for `spec.key` from `indicators[]`, computes M/M change via `computeChange(key, 'national')`
- **timeseries source:** sorts the key's array ascending by date, takes the latest point, computes 30-day percent change against the closest point ~30 days prior, appends `" (30d)"` to the change string
- **Stale filter:** drops rows where the latest period is older than **18 months** (tightened from 36 months 2026-04-09)
- **Wage override:** for `unit === "$/hr"` rows, `computeChange()` is bypassed and the percent change is computed manually (prevents misdetection as "rate" → "pp")
- **±0.0% handling:** near-zero changes display as `± 0.0%` / `± 0.0pp` with `chg-flat` class
- **chgLabel suffix:** if the spec has `chgLabel`, it's appended to the change string (used for non-standard comparison windows like annual retrospective)
- **Missing data:** if the key resolves to nothing, the row is dropped silently (no empty row placeholder)

### `_indFmtKeyValue(val, unit)` — unit-aware formatter
Handles: `$M` (→ `$X.XB` / `$X.XXT`), `thousands` (→ `X,XXXK`), `units` (→ `X,XXX`), `index`, `%`, `pp`, `bps` (value × 100 — credit spreads stored as percent), `rate` (4 decimals), `points`, `USD` (→ `$X.XX`), `USD/bbl`, `USD/oz`, `USD/lb`, `USD/MMBtu`, `USD/MBF`, `USD/bu`, `USD/t`, `$/hr`, `CAD/tonne` (→ `C$X/t`), `gdd`.

### Agriculture (NAICS 11) reference — 14 spec rows (16 rendered with the 2 auto-prepended GDP rows)
The gold-standard implementation. Each row is hyper-industry-specific and was hand-picked to cover performance, trade, labour, crop prices, livestock, input costs, and growing conditions.

| # | Row | Freq | Source | Notes |
|---|---|---|---|---|
| 1 | Real GDP (M/M) | Monthly | StatCan 36-10-0434 | universal |
| 2 | Real GDP (Y/Y) | Monthly | StatCan 36-10-0434 | universal |
| 3 | Farm Cash Receipts | Quarterly | StatCan 32-10-0046 | sector top-line revenue |
| 4 | Agriculture Exports | Monthly | StatCan 12-10-0176 | trade (refreshed — old `agri_exports` 2003 row was stale) |
| 5 | Agriculture Employment | Monthly | StatCan 14-10-0022 | labour |
| 6 | Avg Hourly Wage, Agriculture | Monthly | StatCan 14-10-0063 | labour (uses $/hr wage override) |
| 7 | Wheat | Daily | Yahoo `ZW=F` → CME Group | crop commodity |
| 8 | Corn | Daily | Yahoo `ZC=F` → CME Group | crop commodity |
| 9 | Soybeans | Daily | Yahoo `ZS=F` → CME Group | crop commodity |
| 10 | Canola (Saskatchewan) | Monthly | StatCan 32-10-0077 | crop commodity (Yahoo RS=F delisted — fallback) |
| 11 | Live Cattle | Daily | Yahoo `LE=F` | livestock |
| 12 | Lean Hogs | Daily | Yahoo `HE=F` | livestock |
| 13 | Fertilizer Price Index | Quarterly | StatCan 18-10-0258 sub-component | input cost |
| 14 | Farm Input Price Index | Quarterly | StatCan 18-10-0258 | input cost |
| 15 | Potash (Nutrien stock) | Daily | Yahoo NTR | input proxy (equity, not commodity) |
| 16 | 2025 Growing Season GDD (Prairie Avg) | Annual | ECCC historical weather | conditions (base 5°C, retrospective vs 2024) |

### Row count target per industry
- **Minimum:** 8 rows (2 universal + 6 industry-specific)
- **Recommended:** 12–16 rows
- **Maximum:** 18 rows (Construction is at 17, Agriculture at 16; target tops out around this)
- **Locked range across all 20 industries:** 10–17 rows (see counts in Lock State section at the top)

### Locked data sources per industry (post IND-05)

The approved Key Indicators table uses these canonical data spines per sector. Keys are resolved against `indicators.json` (national rows) or `timeseries.json`.

**Goods (5)**
- **11 Agriculture:** Farm Cash Receipts, Agriculture Exports, Agriculture Employment, Hourly Wage Agriculture, Wheat, Corn, Soybeans, Canola, Live Cattle, Lean Hogs, Fertilizer Price Index, Farm Input Price Index, Potash (Nutrien), Prairie GDD
- **21 Mining & Energy:** WTI, Brent, Natural Gas, LNG Asia, Gold, Silver, Copper, Nickel, Iron Ore, Uranium (Cameco), Potash (Nutrien), Coal, Mining & Energy Employment
- **22 Utilities:** Natural Gas, WTI (Fuel), Coal, LNG Asia, Uranium (Cameco), Utilities Employment, GoC 10Y Yield, BoC Rate, National CPI, CAD/USD
- **23 Construction:** Housing Starts (total/single/multi), 5 building investment cuts (residential/non-residential/commercial/industrial/institutional), NHPI, Residential + Non-Residential Permits, Construction Employment, BoC Rate, Prime Rate, Copper
- **31-33 Manufacturing:** Manufacturing Sales, Manufacturing Employment, Machinery & Equipment Capex, CAD/USD, Copper, Aluminum, Iron Ore, Nickel, Zinc, Natural Gas, WTI, Dry Bulk Shipping, S&P 500

**Services (15)**
- **41 Wholesale Trade:** Wholesale Sales, Wholesale Trade Employment, Manufacturing Sales, Retail Sales, CAD/USD, Dry Bulk Shipping, National CPI, BoC Rate, National Avg Hourly Wage, TSX Composite
- **44-45 Retail Trade:** Retail Sales, Retail Trade Employment, National CPI, Household Disposable Income, Household Savings Rate, Household Debt-Service Ratio, BoC Rate, Prime Rate, National Unemployment, National Employment Rate, National Avg Hourly Wage, CAD/USD
- **48-49 Transportation:** Transportation Employment, WTI, Brent, Natural Gas, Dry Bulk Shipping, Manufacturing Sales, Retail Sales, GoC 10Y Yield, CAD/USD, National Avg Hourly Wage
- **51 Information & Cultural:** Information Sector Employment, Nasdaq, S&P 500, TSX Composite, GoC 10Y Yield, BoC Rate, CAD/USD, National CPI, National Avg Hourly Wage
- **52 Finance & Insurance:** BoC Rate, Prime Rate, GoC 2Y/5Y/10Y, Yield Curve 10y–2y, HY Spread, IG Spread, TSX Composite, S&P 500, Finance & Insurance Employment, CAD/USD
- **53 Real Estate:** Housing Starts (total/single/multi), NHPI, BoC Rate, Prime Rate, GoC 5Y, Residential Permits, Residential Building Investment, Household Debt-Service Ratio, Real Estate Employment, National CPI
- **54 Professional Services:** Professional Services Employment, National Employment Rate, National Unemployment, National Avg Hourly Wage, Job Vacancies, TSX Composite, S&P 500, BoC Rate, GoC 10Y Yield, CAD/USD
- **55 Management of Companies:** TSX Composite, S&P 500, BoC Rate, Prime Rate, GoC 10Y Yield, HY Spread, IG Spread, CAD/USD _(employment intentionally omitted — 14-10-0022 aggregates NAICS 55 with 56 so no standalone sector series)_
- **56 Administrative & Support:** Admin & Support Employment, National Unemployment, National Employment Rate, National Participation Rate, National Avg Hourly Wage, Job Vacancies, National CPI, BoC Rate, TSX Composite
- **61 Educational Services:** Education Sector Employment, National Avg Hourly Wage, Job Vacancies, Institutional Building Investment, National CPI, BoC Rate, GoC 10Y Yield, National Unemployment, National Employment Rate
- **62 Health Care:** Health Care Employment, National Avg Hourly Wage, Job Vacancies, Institutional Building Investment, National CPI, BoC Rate, GoC 10Y Yield, National Employment Rate, National Unemployment
- **71 Arts & Recreation:** National Avg Hourly Wage, Household Disposable Income, Household Savings Rate, CAD/USD (Tourism FX), National CPI, BoC Rate, National Employment Rate, TSX Composite _(employment intentionally omitted — 14-10-0022 aggregates NAICS 71 with 51)_
- **72 Accommodation & Food:** Accommodation & Food Employment, National Avg Hourly Wage, Household Disposable Income, Household Savings Rate, CAD/USD (Tourism FX), National CPI, WTI (Gas Prices), National Unemployment, National Employment Rate
- **81 Other Services:** Other Services Employment, National Avg Hourly Wage, Household Disposable Income, Household Savings Rate, National CPI, BoC Rate, National Employment Rate, National Unemployment, National Participation Rate
- **91 Public Administration:** Public Admin Employment, National Avg Hourly Wage, BoC Rate, Prime Rate, GoC 2Y/5Y/10Y, Yield Curve 10y–2y, National CPI, Institutional Building Investment, National Unemployment

### NAICS 14-10-0022 aggregation caveat (locked)

StatCan table 14-10-0022 publishes sector employment at aggregate buckets where NAICS 51+71 collapse into "Information, Culture & Recreation" and NAICS 55+56 collapse into "Business, Building & Other Support Services." The template keeps the aggregate row on 51 (information_employment) and 56 (admin_waste_employment) — their natural homes — and omits it from 71 and 55 to prevent showing identical numbers on two different industry pages. Comments in `IND_KEY_INDICATORS` at 55 and 71 document this. To split the aggregates in a future phase, use StatCan Table 36-10-0489 GDP by Industry (NAICS-3 detail).

---

## 5. Project Pipeline table

**Container:** `.section-block` > "Project Pipeline" header with meta `{count} projects · {totalValue}`
**Table:** 4 columns — Project | Province | Value | Status
**Source:** `allProjects` filtered by NAICS prefix (see `prefixList` logic — handles compound codes 31-33, 44-45, 48-49 by expanding to the range)
**Sort:** by value descending
**Limit:** top 10
**Empty state:** "No tracked projects for {name}."

---

## Data injection conventions

### `indicators.json`
```json
{
  "indicators": [
    {
      "id": 68590,
      "indicator_name": "farm_cash_receipts",
      "category": "Agriculture",
      "province": "national",
      "value": 27489.13,
      "period": "2025-10-01",
      "previous_value": 24397.5,
      "change": null,
      "source": "Statistics Canada 32-10-0046",
      "fetched_at": "2026-04-09T...",
      "unit": "$M",
      "frequency": "Quarterly",
      "description": "",
      "backfilled": 1,
      "metadata": {},
      "validation_status": "backfilled"
    }
  ],
  "history": [
    {"indicator_name": "farm_cash_receipts", "province": "national", "period": "2022-10-01", "value": 25128.0, "unit": "$M", "source": "Statistics Canada 32-10-0046"}
  ]
}
```

- **ID allocation:** next available ID was `68590` as of the Agriculture fetch (2026-04-09). Always scan the max and increment.
- **Province field:** `"national"` for Canada-level series; `"Ontario"` etc. for provincial series
- **Period format:** `YYYY-MM-01` (monthly), `YYYY-MM-01` with month = 1/4/7/10 for quarterly, `YYYY-01-01` for annual
- **Source label:** `"Statistics Canada {TABLE-ID}"` format preferred
- **Never overwrite existing rows** — always add. If refreshing a stale key (like `agri_exports`), add new rows with current periods alongside the stale ones; the latest-period resolver picks the fresh one.

### `timeseries.json`
Each key is an array of `{date, value, unit, source}` sorted **DESCENDING** by date (newest first). Never modify existing keys — only add new ones.

---

## Editorial rules (per project policy)

- **Factual reporting only** — no editorializing, no "worrying", "encouraging", "positive", "concerning", "welcome", "should", "must"
- **State what happened, let the reader draw conclusions**
- **Source every claim** — citations in narrative prose, hyperlinked sources in tables
- **No fabrication** — if data isn't available, omit the row. Never estimate or synthesize values.
- **Match the existing tone** of the Agriculture analysis when writing new industry narratives

---

## Data fetched during approval (2026-04-09)

### Agriculture baseline (IND-04) — next_id started at 68582
**StatCan WDS:**
- `farm_cash_receipts` (Table 32-10-0046, vec 170328) — quarterly
- `ag_exports_current` (Table 12-10-0176, vec 1592742954) — monthly (also refreshed `agri_exports` key in-place)
- `ag_employment` (Table 14-10-0022, vec 2710135) — monthly
- `ag_hourly_wage` (Table 14-10-0063, vec 2132659) — monthly
- `farm_input_price_index` (Table 18-10-0258, vec 113440252) — quarterly
- `fertilizer_price_index` (Table 18-10-0258, vec 113440263) — quarterly

**Yahoo Finance (timeseries.json):**
- `canola` — via StatCan 32-10-0077 (Yahoo RS=F delisted; monthly Saskatchewan prices as fallback)
- `live_cattle` — LE=F (stored as USD/lb, converted from Yahoo's cents/lb)
- `lean_hogs` — HE=F (stored as USD/lb)

**ECCC Historical Weather (indicators.json):**
- `ag_gdd_prairie_2025` — Saskatoon/Winnipeg/Lethbridge avg, Apr 1–Oct 31 2025 total (base 5°C). 2025 = 1918.6 GDD, 2024 = 1870.1 GDD, +2.6% Y/Y.

### All-industries backfill (IND-05) — 31 series, IDs 68590–68620

Background fetch agent pulled the following, all from StatCan WDS free public API. Scripts saved in `tmp_inds_fetch/`.

**Group A — 16 sector employment series (14-10-0022, monthly, thousands of persons):**
`utilities_employment` (22, vec 2710140), `wholesale_employment` (41, vec 2710147), `retail_employment` (44-45, vec 2710148), `transportation_employment` (48-49, vec 2710149), `information_employment` (51, vec 2710157), `finance_employment` (52, vec 2710151), `real_estate_employment` (53, vec 2710152), `professional_employment` (54, vec 2710153), `management_employment` (55, vec 2710154 — aggregate bucket, see caveat), `admin_waste_employment` (56, vec 2710154 — aggregate bucket, see caveat), `education_employment` (61, vec 2710155), `healthcare_employment` (62, vec 2710156), `entertainment_employment` (71, vec 2710157 — aggregate bucket, see caveat), `accommodation_food_employment` (72, vec 2710158), `other_services_employment` (81, vec 2710159), `public_admin_employment` (91, vec 2710160).

**Group B — National average hourly wage (14-10-0063):**
`nat_avg_hourly_wage` (vec 2132579) — Canada, all industries, both full- and part-time, both genders, 15+.

**Group C — Sector sales ($M, scalar=3 converted to $M):**
- `retail_sales_national` — Table **20-10-0056** (successor to archived 20-10-0008), vec 1446859483
- `wholesale_sales_national` — Table 20-10-0074, vec 52367637
- `manufacturing_sales_national` — Table 16-10-0047, vec 800450

**Group D — Building investment refresh (34-10-0293, quarterly, $M):**
Table **34-10-0293** is the successor to archived 34-10-0175. Fresh 2026-Q1 rows added under existing indicator names (2023-Q4 rows preserved; renderer picks max period):
- `residential_building_investment` (vec 1705315946)
- `non_residential_building_investment` (vec 1705316166)
- `commercial_building_investment` (vec 1705316286)
- `industrial_building_investment` (vec 1705316186)
- `institutional_building_investment` (vec 1705316466)

**Group E — National building permits (34-10-0292, monthly, $M):**
Table **34-10-0292** is the successor to archived 34-10-0066.
- `bldg_permits_res_national` (vec 1675119646)
- `bldg_permits_nonres_national` (vec 1675119649)

**Group F — Household stats national:**
- `household_disposable_income_national` — Table 36-10-0112, vec 62305981 (scalar=6, already in $M)
- `household_savings_rate_national` — Table 36-10-0112, vec 62305984
- `household_debt_service_ratio_national` — Table **11-10-0065**, vec 1001696813 (38-10-0238 does not publish DSR)

**Group G — Job vacancies (14-10-0372, monthly):**
`job_vacancies_total` (vec 1212389466). Table **14-10-0372** is the active monthly successor to inactive 14-10-0326.

### Subsector GDP populate (IND-06)

Pulled 60 3-digit/4-digit/5-digit NAICS subsector GDP series from **StatCan Table 36-10-0434** for populating `briefing_latest.json` subsector chips. No entries written to `indicators.json` for these — they only live in the briefing JSON because they're per-industry metadata, not standalone dashboard indicators. Scripts saved in `tmp_subs_fetch/`.

### StatCan table substitutions (locked)

The following table swaps are canonical for this dashboard. Any future fetch agent replicating this pattern should use the successor tables, not the archived/inactive ones:

| Archived / inactive | Successor | Use case |
|---|---|---|
| 20-10-0008 | **20-10-0056** | Retail trade sales |
| 34-10-0175 | **34-10-0293** | Investment in building construction |
| 34-10-0066 | **34-10-0292** | Building permits by type |
| 14-10-0326 | **14-10-0372** | Job vacancies (now monthly, was quarterly) |
| 38-10-0238 | **11-10-0065** | Household debt-service ratio |

Next available indicator ID: **68621** (as of 2026-04-09, post IND-05).

---

## Files of record

- **Renderer:** `docs/js/app.js` — `_renderIndContent()`, `IND_KEY_INDICATORS` (all 20 industries, locked IND-05), `_indResolveKeyRow()`, `_indFmtKeyValue()`, `buildIndInsightStrip()`, `renderIndInsightChart()`, `_indResolveIndicatorsSeries()`, `_indWindowMonths()`, `_indNormalize()`, `_indFmtMonthLabel()`
- **Styling:** `docs/index.html` — `#tab-industries .industry-header-card` (flex column), `.industry-header-top`, `.industry-subsector-strip`, `.ind-subsector-chip` + color variants
- **Data:** `docs/data/indicators.json` (713 indicator rows, 45,488 history rows post IND-05), `docs/data/timeseries.json`, `docs/data/briefing_latest.json` (industry `insightCharts` array + `analysis` narrative + populated `subsectors[].mm/.yy` post IND-06)
- **Chart skill:** `.claude/skills/tldr-charts/SKILL.md` — extended 2026-04-09 to support industries, `multi_line` chart type, `indicators.json` data source, and the `callout` field
- **Fetch working dirs (reference only, do not modify):** `tmp_agri_fetch/` (IND-04), `tmp_inds_fetch/` (IND-05), `tmp_subs_fetch/` (IND-06). Each contains its own `FETCH_REPORT.md` with vector IDs, coordinates, PASS/FAIL audit, and byte-identical verification notes.
