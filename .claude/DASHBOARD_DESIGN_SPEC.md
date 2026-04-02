# Dashboard Redesign — Complete Design Specification

Reference mockups: `NATIONAL_MOCKUP.html`, `PROVINCES_MOCKUP.html`, `INDUSTRIES_MOCKUP.html`, `MARKETS_MOCKUP.html`, `PROJECTS_MOCKUP.html`, `CALENDAR_MOCKUP.html`, `EXPLORER_MOCKUP.html`

This document extends `TLDR_DESIGN_SPEC.md` to cover all remaining tabs. The TL;DR spec remains the source of truth for shared design tokens (colors, typography, spacing). This spec describes tab-specific layouts and components.

---

## Shared Design System (from TLDR_DESIGN_SPEC.md)

### Colors
```
--bg: #f4f6f8           --accent: #003153        --green: #0d7a3f
--surface: #ffffff       --accent-light: #e8eef4  --green-bg: #ecfdf5
--border: #d5dbe3        --text: #1a1a1a          --red: #c4320a
--border-light: #e8ecf0  --text-secondary: #4a5568 --red-bg: #fef2f2
                         --text-muted: #7a8599     --grey: #7a8599
```

### Typography
- **Inter** (400, 500, 600, 700) — UI: headers, tables, labels, navigation, controls
- **Source Serif 4** (400, 600, 700; italic 400) — Narrative: analysis, policy text, methodology

### Page Layout & Widths

**CRITICAL:** These widths apply to ALL tabs including TL;DR. The production `.tldr-page` class currently uses `padding: 32px 0` (missing horizontal padding) — this must be corrected to match the spec below.

```
Full-width elements (edge to edge, no max-width):
  .site-header    { padding: 20px 40px; }     /* Prussian blue header bar */
  .tabs / nav     { padding: 0 40px; }         /* dark nav bar, sticky */

Centered content area (all tab panels):
  .page / .tldr-page / .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 40px;          /* 40px horizontal padding on both sides */
  }
```

This means the content area is **1120px wide** at max (1200 − 40 − 40). On screens wider than 1200px, the content is centered with the `#f4f6f8` background visible on either side.

| Element | Width | Notes |
|---------|-------|-------|
| Header bar | 100vw | Full viewport, Prussian blue bg |
| Tab bar | 100vw | Full viewport, #00253f bg |
| Content area max | 1200px | Centered with `margin: 0 auto` |
| Content area usable | 1120px | After 40px padding each side |
| 2-column grid | 1120px total | Two equal columns, 20px gap → each column ~550px |
| 4-column grid (metrics) | 1120px total | Four columns, 12px gap → each column ~271px |
| Indicator table | 100% of content | Full width of the content area, no horizontal scroll |
| Inner card | 100% of content | Full width minus section padding |
| Enrichment cards | ~550px each | 2-column grid children |
| Sector cards | ~550px each | 2-column grid children |
| Market section cards | 100% of content | Full width, internal padding 20px |
| Chart canvas wrapper | 100% of parent | Inside `.insight-chart-wrapper`, 24px padding |
| Chart canvas | 100% of wrapper | Responsive within `.chart-wrap` (height: 220px) |

#### Responsive Breakpoints
```
≤ 1199px:
  .page padding → 24px horizontal (content area = 1152px usable)
  grid gaps reduced
  market grid → 3 columns

≤ 899px:
  .page padding → 20px 16px
  2-column grids → single column
  enrichment/sector cards → full width stacked

≤ 599px:
  .page padding → 16px 12px
  font sizes reduced by 1–2px
  tables may horizontally scroll if needed
```

### Shared Components
All tabs reuse these patterns from the TL;DR spec:
- **Header:** Prussian blue, 18px Inter bold title, date badge, freshness. Full viewport width, `padding: 20px 40px`.
- **Tab Bar:** #00253f background, white active text + 2px bottom border. Full viewport width, `padding: 0 40px`.
- **Section Header:** 4px × 22px accent bar + Source Serif 4 h3 (20px, 700) + section-meta
- **Section Block:** `padding: 0 0 28px; margin-bottom: 28px`
- **Callout Box:** accent-light bg, 3px left border, Inter 13px
- **Inner Card:** white bg, 1px border, 8px radius, `padding: 16px 20px`
- **Sources (collapsible):** `<details>`, 13px summary, 12px list, accent links
- **Status Badges:** pill-style, 4 colors (proposed/pre/construction/review)
- **Projects Table:** accent header row, 10px uppercase, 13px body, hover accent-light. Full width of parent container.
- **Footer Link:** right-aligned, 12px accent color, border-top

---

## Tab 1: National

**Mockup:** `NATIONAL_MOCKUP.html`

### Country Subtabs
- Horizontal tab row below main nav: Canada, United States, China, EU, UK
- Active: accent color text + 2px bottom accent border
- Inactive: muted text, no border
- Font: Inter 13px, 500 weight; active 600

### Indicator Panel
- White card with header (flag emoji + title) and border-light bottom separator
- Contains full indicator table (from TLDR_DESIGN_SPEC — 6-column layout)
- Frequency tags are inline within the name column (not a separate column)

### Section Flow (top to bottom)
1. **National Analysis** — editorial narrative with callouts and insight charts
2. **Policy Developments** — policy accordion (elevated from lower position for prominence)
3. **Key Indicators & Sector Signals** — combined section: indicator table then enrichment cards
4. **Projects Preview** — new/notable projects table

### International Subtab Layout (US, China, EU, UK)
Each international subtab follows a simplified 2-section pattern:

**Section 1: [Country] Analysis**
- Standard narrative section (Source Serif 4, 16px, 1.75 line-height)
- **Canadian Impact callout:** accent-light callout boxes that connect the country's data back to the Canadian project pipeline. Every international subtab must include at least one Canadian Impact callout linking foreign indicators to tracked Canadian projects (counts, values, sectors). This is the dashboard's core differentiator.
- **Insight chart** — every international subtab has one chart:
  - US: S&P 500 (12-month performance)
  - China: Manufacturing PMI (12-month trend, with 50-line expansion threshold as dashed reference line)
  - EU: EUR/USD exchange rate (12-month trend)
  - UK: FTSE 100 (12-month performance)
- Collapsible sources section

**Section 2: Key Indicators**
- Same indicator table pattern as Canada (6-column layout)
- Panel header: flag emoji + country name + source attribution (right-aligned, 11px muted)
- Source agencies vary by country:
  - US: BEA, BLS, Federal Reserve, Census Bureau
  - China: NBS, PBOC, GAC
  - EU: Eurostat, ECB, S&P Global
  - UK: ONS, BoE, LSE
- 6 indicators per country, standardized across: GDP, CPI/HICP, policy rate, unemployment, plus 2 country-specific (e.g., Nonfarm Payrolls for US, PMI for China, EUR/USD for EU, FTSE 100 for UK)

**No Policy, Sector Signals, or Projects Preview for international subtabs** — these sections are Canada-only since the project pipeline database tracks Canadian projects exclusively.

### National Analysis (Canada subtab)
- Standard narrative section (Source Serif 4, 16px, 1.75 line-height)
- Callout boxes with cross-reference data inline
- Insight charts: white bg with 1px border, 3px accent top border, chart canvas, source line

### Policy Developments
- Positioned immediately after the narrative analysis for high visibility
- Identical to TLDR spec: inner-card with `<details>` accordion, expanded by default
- Policy body: Source Serif 4, 13px, secondary color, 22px left-pad
- Inline source links: 11px accent

### Key Indicators & Sector Signals (merged section)
- Single section block with combined header: "Key Indicators & Sector Signals"
- **Indicator table** comes first: full 6-column indicator panel with frequency tags inline, 20px bottom margin
- **Enrichment cards** follow directly below within the same section block
- 2-column grid of white cards (border, 8px radius)
- Card title: accent uppercase 12px + 6px dot
- Content: either metric rows (label/value pairs) or narrative paragraph
- Metric rows: flex justify-between, 6px padding, border-light separators

### Projects Preview
- Same as TLDR spec: inner-card with padding:0, overflow:hidden
- 5-column table + footer link

---

## Tab 2: Provinces

**Mockup:** `PROVINCES_MOCKUP.html`

### Province Selector (Sidebar Navigation)
- **Page layout** (`.page`): `display: flex; gap: 32px` — sidebar sits left, content right
- **Sidebar** (`.prov-sidebar`): `<nav>`, 200px wide, sticky (`top: 56px`), `align-self: flex-start`, scrollable if viewport is short
- **Section titles** (`.prov-sidebar-title`): 10px, 700 weight, uppercase, 0.8px letter-spacing, muted text, bottom border separator. Two groups: "Provinces" (10 items) and "Territories" (3 items)
- **Radio inputs** (`.prov-radio`): hidden (`display: none`), native `<input type="radio">` with `name="province"`, ids `prov-{CODE}`
- **Labels** (`.prov-label`): block display, 8px 12px padding, 13px Inter 500, secondary text, 6px radius, 3px transparent left border
  - Hover: accent-light bg, text darkens
  - Checked (via `:checked + .prov-label`): accent color, 600 weight, accent-light bg, accent left border
- **Content area** (`.page-main`): `flex: 1; min-width: 0` — contains all section content
- Pure CSS — no JavaScript needed for selection state
- Full names: "Prince Edward Island", "Northwest Territories" (no abbreviations)
- Province codes as radio values (ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU)

### Province Header Card
- Full-width card, accent bg, white text, 8px radius
- Left: h2 (Source Serif 4, 28px, 700) + subtitle
- Right: 3 stat items (22px value, 10px uppercase label, 60% opacity label)
- Stats: Active Projects, Pipeline Value, New This Week

### Section Flow (6 sections)
1. **Provincial Analysis** — narrative + callouts + insight chart + section sources
2. **Policy Developments** — narrative intro + accordion items + section sources
3. **Key Indicators — {Province}** — 8 universal indicators + secondary table with 4 province-specific indicators
4. **Sector Signals** — enrichment cards (sector highlights, labour market, trade, hiring)
5. **Projects Preview** — narrative intro + project table
6. **Upcoming Events** — province-specific watchlist items

### Section 1: Provincial Analysis
- Same narrative pattern as National (Source Serif 4, callout boxes)
- Insight chart: same wrapper pattern (white bg, border, 3px accent top)
- Sources listed at bottom of section

### Section 2: Policy Developments
- Narrative intro paragraph before accordion
- Same inner-card accordion as National/TLDR
- Sources listed at bottom of section

### Section 3: Key Indicators — {Province}
- Own `section-block` with section header: "Key Indicators — {Province}"
- Section meta: "8 indicators · Updated {date}"
- Single `indicator-panel` with `ind-table` (7 columns: Indicator, Frequency, Value, Change, Reference Period, Next Release, Source)
- 8 universal indicators (same for all provinces):
  1. GDP Growth (Real) — Quarterly — StatCan 36-10-0402
  2. Unemployment Rate — Monthly — StatCan 14-10-0287
  3. CPI Inflation — Monthly — StatCan 18-10-0004
  4. Employment Rate — Monthly — StatCan 14-10-0287
  5. Participation Rate — Monthly — StatCan 14-10-0287
  6. Wage Growth — Monthly — StatCan 14-10-0287
  7. Housing Starts — Monthly — CMHC
  8. Building Permits — Monthly — StatCan 34-10-0066

#### {Province}-Specific Indicators (secondary table within Section 3)
- `h4.ind-section-label` subheader: "{Province}-Specific Indicators" (13px, 600 weight, accent color)
- Second `indicator-panel` with own `ind-table` and `thead` (same 7 columns)
- 4 province-specific indicator rows (vary by province — see table below)

```css
.ind-section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  margin: 20px 0 8px;
  padding: 0;
}
```

#### Province-Specific Indicator Table

| Province | Indicator 1 | Indicator 2 | Indicator 3 | Indicator 4 |
|----------|-------------|-------------|-------------|-------------|
| **ON** | Auto Production (DesRosiers) | Toronto Home Price Index (TRREB MLS HPI) | Financial Services Employment (StatCan 14-10-0022) | Ring of Fire Mining Permits (Ontario MNDM) |
| **QC** | Aerospace Exports (StatCan 12-10-0129) | Montreal Home Price Index (QPAREB Centris) | Hydro-Quebec Generation Capacity (HQ) | AI/Tech Venture Capital (CVCA) |
| **AB** | Oil Sands Production (AER ST-39) | WCS-WTI Differential (market) | Drilling Rig Count (CAODC) | Calgary Office Vacancy Rate (CBRE) |
| **BC** | Port of Vancouver TEU Volume (VFPA) | Vancouver Home Price Index (REBGV MLS HPI) | Lumber Export Value (StatCan 12-10-0129) | Film/TV Production Spending (CMPA) |
| **SK** | Potash Production Volume (StatCan 16-10-0048) | Crop Receipts (StatCan 21-10-0019) | Uranium Mine Output (CNSC) | Oil Production (SK Gov) |
| **MB** | Agriculture Receipts (StatCan 21-10-0019) | Winnipeg CMA Employment (StatCan 14-10-0384) | Hydro Generation (Manitoba Hydro) | Manufacturing Sales (StatCan 16-10-0048) |
| **NS** | Shipbuilding Contracts Value (Irving/PSC) | Halifax Home Price Index (NSAR MLS) | Seafood Export Value (StatCan 12-10-0129) | Tourism Visitors (NS Tourism) |
| **NB** | Forestry Output Value (StatCan 16-10-0048) | Saint John Refinery Throughput (Irving Oil) | Aquaculture Production (DFO) | NB Power Generation (NB Power) |
| **NL** | Offshore Oil Production (C-NLOPB) | Muskrat Falls Generation (NL Hydro) | Mineral Shipments Value (NL Gov) | Marine/Fishery Landings (DFO) |
| **PE** | Potato Crop Value (StatCan 21-10-0019) | Tourism Revenue (PEI Tourism) | Shellfish Aquaculture Volume (DFO) | Population Growth Rate (StatCan 17-10-0009) |
| **YT** | Mining Exploration Spending (NRCan) | Placer Gold Production (YT Mining) | Tourism Visitors (YT Tourism) | Federal Transfer Revenue (YT Finance) |
| **NT** | Diamond Production Value (GNWT) | Mining Exploration Spending (NRCan) | Resource Royalties (GNWT Finance) | Remediation Site Progress (CIRNAC) |
| **NU** | Mining Exploration Spending (NRCan) | Inuit Employment Rate (StatCan 14-10-0364) | Construction Investment (StatCan 34-10-0175) | Federal Transfer Revenue (NU Finance) |

### Section 4: Sector Signals
- Own `section-block` with section header
- 2-column grid of enrichment cards
- 4 cards: Sector Highlights, Labour Market, Trade & Commodities, Hiring Signals
- Same enrichment-card pattern as National

### Section 5: Projects Preview
- Narrative intro paragraph before table
- Header shows: "{count} tracked · ${value} total value"
- Same table pattern as National: 5 columns (Project, City, Sector, Value, Status)

### Section 6: Upcoming Events
- Province-specific watchlist items
- Inner-card with watchlist-item rows
- Each row: impact dot (8px, colored) + date (12px accent bold) + event name + institution
- Impact colors: high=red, medium=#d97706, low=grey

---

## Tab 3: Industries

**Mockup:** `INDUSTRIES_MOCKUP.html`
**Implementation guide:** `INDUSTRIES_IMPLEMENTATION_GUIDE.md`

Three-section single-column layout: overview narrative, biggest movers cards, expandable all-sectors table.

### Section 1: Industry Overview
- Narrative block with em dash lead sentence pattern
- Callout box: pipeline cross-reference with total projects, goods/services split, weekly status changes

### Section 2: Biggest Movers (4 cards)
- 4 full-width `.mover-card` elements: 2 gainers + 2 decliners, selected by largest absolute M/M change
- Card header: sector name (16px 700) + direction badge (colored pill: green-bg/green for up, red-bg/red for down)
- Metrics row: flex, 4 items (GDP, Year-over-Year, Active Projects, Pipeline Value), bordered top/bottom
  - Label: 10px uppercase muted, Value: 16px 700 tabular-nums
- Analysis: Source Serif 4, 14px, em dash lead sentence pattern
- Sources: 11px muted, separated by ` · `, border-top divider

### Section 3: All Sectors (Expandable Table)
- View toggle above table: All / Goods-Producing / Services-Producing
  - Inline-flex toggle group: 8px/20px padding, 13px 600, 8px border-radius
  - Inactive: surface bg, muted text. Active: accent bg, white text. Hover: accent-light bg, accent text
- Subsection dividers: 12px uppercase, 600, muted, 0.5px letter-spacing, border-bottom
- Two table groups: Goods-Producing (5 rows) + Services-Producing (15 rows)
- Table: Prussian blue header, 6 columns (Sector, GDP, M/M, Y/Y, Projects, Pipeline Value)
  - Header: 10px uppercase white on accent bg
  - Data rows: 14px, 13px/16px padding, hover accent-light
  - Sector column: 600 weight with chevron (▶) before name
  - Numeric columns right-aligned, change columns colored (green/red/grey)
  - Sorted by GDP descending within each group
- Expandable rows: click any row to reveal narrative write-up
  - Chevron rotates 90deg on expand
  - Expand content: #fafbfc bg, dashed top border, 24px padding
  - Supplementary metrics strip: 2-3 context metrics (9px label, 14px 700 value)
  - Narrative: Source Serif 4, 14px, em dash lead sentence, secondary color
  - Sources: 11px, border-top, label + citation list separated by ` · `

### No Pipeline Bars
Pipeline bars (stacked horizontal status bars) are removed from the Industries tab. Project counts and total values are shown as plain text columns.

### No NAICS ID Badges
NAICS code badges are not displayed. Sectors identified by full official name only.

---

## Tab 4: Markets

**Mockup:** `MARKETS_MOCKUP.html`
**Implementation guide:** `MARKETS_IMPLEMENTATION_GUIDE.md`

### 5 Sections (stacked vertically, full width)

1. **Market Commentary** — narrative overview with callout box and sources
2. **Equity Indices** — series pills (7 indices) → stat row → chart controls → SVG line chart → commentary
3. **Foreign Exchange** — compact FX pills (4 pairs) → stat row → SVG line chart → commentary
4. **Government of Canada Yields** — Prussian blue header table (7 tenors) → spread badge → yield curve SVG (current vs 1Y ago overlay) → commentary
5. **Commodities** — category tabs → accordion table (13 commodities, 5 categories) with expandable rows containing narrative, metrics, sparkline charts, and sources → summary commentary

### Market Card Container
- White bg, 1px border, 8px radius, overflow hidden
- No padding on container (internal elements handle their own)

### Series Pills (Equity Indices)
- Flex row, 8px gap, 16px/20px padding, horizontal scroll
- Each pill: 130px min-width, 10px/14px padding, 8px radius, border
- Content: pill-name (11px 600 muted), pill-value (18px 700), pill-change (12px colored)
- Active: accent border, accent-light bg, accent pill-name
- Change colors: green (up), red (down), grey (flat)

### FX Pills (Compact)
- Flex row, 4px gap, 10px/20px padding
- Each pill: flex: 1 (equal width), 6px/8px padding, 5px radius, center-aligned
- Content: pill-name (9px), pill-value (13px), pill-change (10px)
- Same active state as series pills

### Chart Controls (Equities only)
- Range selector: inline-flex group — 1M, 3M, 6M, 1Y, 3Y
- Button: 4px/12px padding, 11px 500, border-right 1px
- Active: accent bg, white text

### SVG Line Charts (Equities + FX)
- viewBox="0 0 800 220" (equities) / "0 0 800 180" (FX)
- Gradient fill: linearGradient from accent 0.12 to 0.01 opacity
- Line: polyline, accent stroke, 2.5px width, round joins
- Current value dot: circle r=4, white stroke
- Grid: horizontal lines at 3 intervals, border-light color
- Axis labels: 10px Inter, text-muted color

### Yield Table
- Prussian blue header row (accent bg, white text, uppercase 11px)
- 3 data rows: Current (16px 700), 1 Year Ago (12px muted), Change (12px colored)
- 7 tenor columns: 3M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y
- 16px top padding to separate from card edge
- First column header has left border-radius 6px, last has right

### Yield Curve SVG
- Two polylines: current (solid Prussian blue, 2.5px) vs 1Y ago (dashed red, 1.5px)
- Circle dots on current curve at each tenor (r=4)
- Y-axis: 2.0% to 5.0%. X-axis: 7 tenor labels
- Legend: top-right, solid blue "Current" + dashed red "1 Year Ago"

### Spread Badge
- Inline-flex, 4px/12px padding, 6px radius, 12px 600
- Normal: green-bg/green · Inverted: red-bg/red
- Row includes BoC overnight rate right-aligned

### Commodity Accordion Table
- Prussian blue header: 6 columns (Commodity, Price, Weekly, MoM, YoY, 52-Week Range)
- Category group dividers: 10px uppercase, bg background, between commodity groups
- 5 categories: Energy (4), Precious Metals (2), Base Metals (3), Agriculture (3), Forest Products (1)
- 13 commodity rows total, each clickable to expand
- Chevron: 10px triangle, rotates 90deg on expand
- Expanded content order: narrative → metrics strip → SVG sparkline → sources
- WTI pre-expanded by default with $70 breakeven reference line

### Category Tabs
- Flex row inside market card, above table
- 6 tabs: All, Energy, Precious Metals, Base Metals, Agriculture, Forest Products
- 12px 500, bottom 2px accent border on active

### Commentary Pattern (all sections)
- Below charts/data, border-top separator
- Source Serif 4, 14px, 1.65 line-height, text-secondary
- Lead sentence bold (text color), supporting in text-secondary
- Sources div: 11px Inter, dot-separated citations

### Frontend Reference
- `renderMarkets(briefing)` → market commentary + equity indices + FX + yields + commodities
- `renderEquityChart(seriesKey, container, range)` → SVG line chart from timeseries.json
- `renderYieldCurve(current, yearAgo)` → SVG yield curve overlay
- `toggleCmdRow(row)` → commodity accordion expand/collapse
- `filterCommodityCategory(tab)` → show/hide rows by category

---

## Tab 5: Projects

**Mockup:** `PROJECTS_MOCKUP.html`

### Summary Stats
- 4-column grid, 12px gap
- Each card: surface bg, border, 8px radius, center aligned
- Value: 24px 700 accent color · Label: 11px uppercase muted

### Submit Missing Project
- Full-width button: surface bg, border, 8px radius, left-aligned text
- Hover: accent-light bg
- Expandable form below: 2-column form grid, standard input styling

### Filter Bar
- Flex wrap row: search input + 4 selects + toggle checkbox + export button
- Contained in surface card with 14px/18px padding, border, 8px radius
- Search: flex-1, min-width 200px, 8px/14px padding, 13px
- Selects: 8px/12px padding, 12px, bg color matches page bg
- Export button: border, 6px radius, accent text
- Toggle: 12px label + 16px checkbox (accent-color)

### Projects Table
- Wrapped in surface card (border, 8px radius, overflow hidden)
- 9 columns: Value, Project (name + proponent), Type, Province, Proponent, Status, Sector, Updated, Source
- Sortable headers: cursor pointer, hover #004a7a
- Project name: 500 weight · Proponent sub-line: 11px muted
- Value: 700 weight, tabular-nums
- Type badge: 10px, accent-light bg, accent text
- Source badge: 9px pill (gov=blue, news=amber)

### Expanded Row
- bg: #fafbfc, border-bottom
- 2-column grid: description + evidence (left) + meta (right)
- Description: Source Serif 4, 14px, secondary
- Evidence list: list items with source badges + links
- Meta: 12px label/value pairs, includes confidence bar (40px inline bar)

### Confidence Bar
- 40px × 5px, border-light bg, 3px radius
- Fill: accent color, width = confidence × 100%

### Pagination
- Flex row, space-between, 14px/20px padding
- Left: "Showing X-Y of Z"
- Right: page buttons (6px/12px, border, 6px radius)
- Active: accent bg, white

---

## Tab 6: Calendar

**Mockup:** `CALENDAR_MOCKUP.html`

### Impact Legend
- Flex row of items: 6px colored dot + 11px label
- Colors: high=red, medium=#d97706, low=grey

### Calendar Grid
- Surface card with 8px radius, overflow hidden
- Nav bar: flex row, 14px/20px padding, title (16px 700) right-aligned
- Nav buttons: 6px/14px padding, border, 6px radius, 12px 500
- "Today" button: accent bg, white text

### Day Grid
- 7-column CSS grid
- Day headers: accent-light bg, 10px uppercase, border-bottom
- Day cells: min-height 90px, 8px/10px padding, border-right + border-bottom
- Day number: 13px 600
- Today: accent bg circle (24px) around number
- Other-month days: fafbfc bg, faded number
- Event dots: 9px labels with 6px impact-colored dots

### Event Lists
- Surface card, 8px radius, overflow hidden
- Header: 14px 600, border-bottom
- Event rows: 5-column grid (date, name+desc, institution, impact badge, link)
  - Date: 12px accent 600, 70px width
  - Name: 500 weight, sub-desc 11px muted
  - Institution: 11px muted, 140px
  - Impact badge: pill (high=red-bg, medium=amber-bg, low=slate-bg)
  - Link: 11px accent

### Key Event Highlighting
- BoC decision row gets subtle background: rgba(0,49,83,0.03)

---

## Tab 7: Data Explorer

**Mockup:** `EXPLORER_MOCKUP.html`

### Search Bar
- Flex row: text input (flex-1, 12px/18px padding, 14px, 8px radius) + search button
- Button: accent bg, white, 14px 600, 8px radius

### Category Pills
- Flex wrap row, 6px gap
- Same pill styling as province pills but surface bg + border default
- Active: accent bg, white, accent border

### Stats Pills
- Flex row: 3 stat cards
- Each: 12px/18px padding, surface bg, border, 8px radius
- Value: 18px 700 accent · Label: 10px uppercase muted

### Search Results
- Surface card, 8px radius, overflow hidden
- Header: accent-light bg, 13px 600, with result count
- Result rows: 4-column grid (name, table number, category badge, StatCan link)
- Table number: 11px monospace, muted
- Category badge: 10px accent-light/accent pill

### Provincial Indicator Explorer
- Controls row: province select + indicator select + range selector
- Value callout: accent-light bg card, 4 stat items (value, change, YoY, range)
  - Values: 20px 700 accent · Labels: 10px uppercase · Meta: 11px muted
- Chart: 220px placeholder

### National Indicators
- Grouped table within surface card
- Group headers: fafbfc bg, 11px uppercase, border-bottom
- Indicator rows: 5-column grid (name, value, change, period, source link)
- Same styling as TLDR indicator table rows

### Methodology Section
- Surface card, 24px/28px padding
- h4: Source Serif 4, 16px, 700
- Body: Source Serif 4, 14px, secondary, 1.7 line-height
- Tier list: numbered circles (24px, accent bg, white text) + name + detail
- Tier items: flex row, 8px padding, border-light separators

---

## Responsive Breakpoints

All tabs follow the same breakpoint pattern:
- **≤ 1199px:** Reduce page padding to 24px, reduce gap sizes
- **≤ 767px:** Stack 2-column grids to single column, reduce font sizes by 1px, collapse enrichment cards

Province selector and series pills remain horizontally scrollable at all widths.

---

## Migration Notes

### Components Removed
- Section banners (Unsplash background images) — replaced by section headers with accent bars
- Glass morphism cards — replaced by clean surface cards
- Outfit/Work Sans fonts — replaced by Inter/Source Serif 4
- Dark blue (#3B5998) primary — replaced by Prussian blue (#003153)
- Indicator pill strips — replaced by full-width indicator tables

### Components Added
- Province header card (accent bg with stat summary)
- Sector pipeline bars (stacked horizontal)
- Market section cards with inline series pills
- Calendar grid with impact dots
- Expanded project rows with evidence and metadata
- Value callout cards in Data Explorer

### JS Function Mapping
Each `render*()` function needs updating to emit the new HTML patterns:
- `renderCanadaSub()` → Canada subtab: narrative + policy + merged indicators & sectors + projects
- `renderAllGlobalPlayers()` → International subtabs (US/China/EU/UK): narrative with Canadian Impact callouts + insight chart + indicator table
- `renderProvinces()` → province pill selector + header card + metrics grid + narrative + enrichments
- `renderIndustries()` → overview narrative + 4 mover cards + expandable all-sectors table (no pipeline bars, no NAICS badges)
- `renderMarkets()` → 5 sections: commentary + equity indices + FX + yields (table + curve) + commodities (accordion)
- `renderProjectsTab()` → summary stats + filter bar + table with expanded rows + pagination
- `renderCalendar()` → calendar grid + event lists
- `renderExplorer()` → search + categories + provincial explorer + national indicators + methodology

---

## Insight Chart Implementation (All Tabs)

### Chart.js Configuration Rules
All charts use Chart.js 4.x (`chart.umd.min.js` from cdnjs). Follow these rules when implementing charts in `app.js`:

**Container:** Every `<canvas>` must be wrapped in a `<div class="chart-wrap">` (`position: relative; height: 220px; width: 100%`). Without a fixed-height parent, `maintainAspectRatio: false` has no constraint and the chart collapses or stretches.

**Options — always explicit, never spread:** Do NOT use `...sharedOptions` or spread operators to compose chart configs. Chart.js nested objects (scales, plugins, tooltip) do not deep-merge via spread — properties silently drop. Write every chart config in full.

**No annotation plugin:** Do not use `chartjs-plugin-annotation`. Reference lines (e.g., Canada 6.7% unemployment, China PMI 50-line) are rendered as a second dataset: `data: Array(N).fill(value)`, `borderDash: [4, 3]`, `pointRadius: 0`, `fill: false`. Filter the reference dataset out of tooltips with `filter: function(item) { return item.datasetIndex === 0; }`.

**No arrow functions in callbacks:** Use `function(v) { return ...; }` instead of `v => ...` for broader compatibility.

### Chart Wrapper Styling
```css
.insight-chart-wrapper {
  border-top: 3px solid var(--accent);
  background: var(--surface);          /* white, not accent-light */
  border: 1px solid var(--border);
  border-top: 3px solid var(--accent); /* override top border */
  border-radius: 0 0 8px 8px;
  padding: 24px;
  margin: 24px 0;
}
```
Background is white (`--surface`), not the blue-grey `--accent-light`. The accent-light fill under the data line was too hard to distinguish from the container background.

### Axis Styling
```
x-axis:
  grid: { display: false }
  ticks: { font: Inter 11px weight 500, color: #4a5568 }
  border: { color: #9aa5b4 }

y-axis:
  grid: { display: false }              /* no horizontal gridlines */
  ticks: { font: Inter 11px weight 500, color: #4a5568 }
  border: { display: false }
```
Axis tick labels use `--text-secondary` (`#4a5568`) at medium weight. No horizontal gridlines — the chart area is clean with just the data line and fill.

### Fill Colors (under the line)
Use 10–12% alpha of the line color. Enough to read clearly against white without overwhelming:
- Prussian blue line → `rgba(0,49,83,0.10)`
- Blue line (#1e40af) → `rgba(30,64,175,0.12)`
- Green line (#065f46) → `rgba(6,95,70,0.12)`
- Red line (#b91c1c) → `rgba(185,28,28,0.10)`

### Tooltip Styling
```
backgroundColor: #00253f
titleFont: Inter 11px weight 600
bodyFont: Inter 12px
padding: 10, cornerRadius: 6
displayColors: false
```

### Lazy Initialization
International subtab charts (US, China, EU, UK) are lazy-initialized on first subtab click via `showSubtab()`. The Canada chart initializes immediately on page load since it's the default visible subtab.

### Charts per Subtab
| Subtab | Chart | Timeseries Key | Line Color | Reference Line |
|--------|-------|---------------|------------|----------------|
| Canada | Unemployment Rate | `unemployment_rate` | #003153 (Prussian) | 6.7% dashed red |
| US | S&P 500 | `idx_sp500` | #1e40af (blue) | — |
| China | Manufacturing PMI | `china_pmi` | #b91c1c (red) | 50.0 dashed grey |
| EU | EUR/USD | `fx_eurusd` | #1e40af (blue) | — |
| UK | FTSE 100 | `idx_ftse100` | #065f46 (green) | — |
