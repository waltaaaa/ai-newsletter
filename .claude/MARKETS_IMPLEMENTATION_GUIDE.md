# Markets Tab — Implementation Guide

Reference mockup: `MARKETS_MOCKUP.html`
Design spec: `DASHBOARD_DESIGN_SPEC.md` (Tab 5 section)

This guide covers everything needed to implement the Markets tab in production: HTML structure, CSS classes, JavaScript rendering, data contracts, pipeline wiring, and deploy integration.

---

## 1. Page Layout

The Markets tab uses a single centered column. Five sections stack vertically: Market Commentary, Equity Indices, Foreign Exchange, Government of Canada Yields, and Commodities.

### HTML Shell

```html
<div class="page" id="markets-page">

  <!-- Section 1: Market Commentary -->
  <div class="section-block"> ... </div>

  <!-- Section 2: Equity Indices -->
  <div class="section-block"> ... </div>

  <!-- Section 3: Foreign Exchange -->
  <div class="section-block"> ... </div>

  <!-- Section 4: Government of Canada Yields -->
  <div class="section-block"> ... </div>

  <!-- Section 5: Commodities (accordion table) -->
  <div class="section-block"> ... </div>

</div>
```

All sections are full-width within the `.page` container (max-width: 1200px). No side-by-side columns — everything stacks vertically.

---

## 2. Section 1: Market Commentary

A narrative overview of the week's market activity using the em dash lead sentence pattern. Includes a callout box cross-referencing the project database.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Market Commentary</h3>
    <span class="section-meta">Week ending {date}</span>
  </div>

  <div class="narrative">
    <p><span class="lead-sentence">{equity lead}</span> — {supporting detail}</p>
    <p><span class="lead-sentence">{yields lead}</span> — {supporting detail}</p>

    <div class="callout">
      <strong>Project cross-reference:</strong> {database cross-reference text}
    </div>

    <div class="sources"><span>Sources:</span> {source1} · {source2} · ...</div>
  </div>
</div>
```

### Data Source

Rendered from `briefing.market_commentary` — the market writing agent output. The commentary must follow editorial policy: factual reporting only, no editorializing.

---

## 3. Section 2: Equity Indices

A market card with selectable index pills, stat row, line chart with gradient fill, and commentary below.

### Component Order (top to bottom)

1. **Series pills** — horizontal scrollable row of 7 index pills
2. **Stat row** — 52-week high/low, YTD, YoY
3. **Chart controls** — range selector buttons (1M, 3M, 6M, 1Y, 3Y)
4. **Line chart** — SVG with gradient fill area, grid lines, axis labels, current-value dot
5. **Commentary** — em dash narrative with sources

### Series Pill HTML

```html
<div class="series-row">
  <div class="series-pill active">
    <div class="pill-name">S&P/TSX Composite</div>
    <div class="pill-value">25,427</div>
    <div class="pill-change up">▲ +1.54%</div>
  </div>
  <!-- ... more pills -->
</div>
```

### Series Pill CSS

```css
.series-row {
  display: flex; gap: 8px; padding: 16px 20px;
  overflow-x: auto; border-bottom: 1px solid var(--border-light);
}
.series-pill {
  flex-shrink: 0; min-width: 130px; padding: 10px 14px;
  border: 1px solid var(--border); border-radius: 8px;
  cursor: pointer; transition: all 0.15s; background: var(--surface);
}
.series-pill.active { border-color: var(--accent); background: var(--accent-light); }
.pill-name { font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px; }
.series-pill.active .pill-name { color: var(--accent); }
.pill-value { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }
.pill-change { font-size: 12px; font-weight: 600; }
.pill-change.up { color: var(--green); }
.pill-change.down { color: var(--red); }
.pill-change.flat { color: var(--grey); }
```

### Chart Rendering

Charts are rendered as inline SVG inside `.chart-area`. The production implementation should use JavaScript to generate SVG paths from `timeseries.json` data.

```javascript
function renderEquityChart(seriesKey, container, range) {
  // 1. Read timeseries.json for the selected index
  // 2. Filter to selected range (1M, 3M, 6M, 1Y, 3Y)
  // 3. Calculate SVG viewBox coordinates from price data
  // 4. Generate: gradient def, grid lines, y-axis labels, area fill path, line polyline, current-value dot, x-axis labels
  // 5. Insert SVG into container
}
```

SVG chart pattern:
- `viewBox="0 0 800 220"` with `preserveAspectRatio="none"`
- Gradient fill: `linearGradient` from `--accent` 0.12 opacity to 0.01 opacity
- Line: `polyline` with `stroke: var(--accent)`, `stroke-width: 2.5`, `stroke-linejoin: round`
- Current value dot: `circle` with `r="4"`, white stroke
- Grid lines: horizontal `line` elements with `stroke: var(--border-light)`

### Stat Row CSS

```css
.stat-row {
  display: flex; gap: 24px; padding: 14px 20px;
  border-top: 1px solid var(--border-light); flex-wrap: wrap;
}
.stat-item { display: flex; flex-direction: column; gap: 2px; }
.stat-label { font-size: 9px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }
.stat-val { font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }
```

### Commentary CSS

```css
.market-narrative {
  padding: 16px 20px; border-top: 1px solid var(--border-light);
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 14px; line-height: 1.65; color: var(--text-secondary);
}
.market-narrative .lead-sentence { font-weight: 600; color: var(--text); }
```

### 7 Equity Indices

| Pill Label | Data Key (timeseries.json) | Source |
|---|---|---|
| S&P/TSX Composite | `tsx_composite` | yfinance `^GSPTSE` |
| S&P 500 | `sp500` | yfinance `^GSPC` |
| Dow Jones | `djia` | yfinance `^DJI` |
| NASDAQ | `nasdaq` | yfinance `^IXIC` |
| FTSE 100 | `ftse100` | yfinance `^FTSE` |
| DAX | `dax` | yfinance `^GDAXI` |
| Nikkei 225 | `nikkei225` | yfinance `^N225` |

### Pill Selection JavaScript

```javascript
function selectEquityIndex(pill) {
  document.querySelectorAll('.series-pill').forEach(p => p.classList.remove('active'));
  pill.classList.add('active');
  const seriesKey = pill.dataset.series;
  renderEquityChart(seriesKey, document.querySelector('#equity-chart-area'), currentRange);
  updateStatRow(seriesKey);
}
```

---

## 4. Section 3: Foreign Exchange

Same market card pattern as equities but with compact pills sized for 4 currency pairs.

### FX Pill CSS (Compact)

```css
.fx-series-row {
  display: flex; gap: 4px; padding: 10px 20px;
  overflow-x: auto; border-bottom: 1px solid var(--border-light);
}
.fx-pill {
  flex: 1; min-width: 0; padding: 6px 8px;
  border: 1px solid var(--border); border-radius: 5px;
  cursor: pointer; transition: all 0.15s; background: var(--surface);
  text-align: center;
}
.fx-pill.active { border-color: var(--accent); background: var(--accent-light); }
.fx-pill .pill-name { font-size: 9px; margin-bottom: 1px; }
.fx-pill .pill-value { font-size: 13px; margin-bottom: 0; }
.fx-pill .pill-change { font-size: 10px; }
```

### Component Order (top to bottom)

1. **Compact FX pills** — 4 pairs, equal-width flex, center-aligned
2. **Stat row** — MoM, YoY, BoC rate
3. **Line chart** — SVG with gradient fill (same pattern as equities)
4. **Commentary** — em dash narrative with sources

### 4 FX Pairs

| Pill Label | Data Key | Source |
|---|---|---|
| CAD/USD | `cad_usd` | yfinance `CADUSD=X` |
| EUR/USD | `eur_usd` | yfinance `EURUSD=X` |
| USD/CNY | `usd_cny` | yfinance `USDCNY=X` |
| USD/JPY | `usd_jpy` | yfinance `USDJPY=X` |

---

## 5. Section 4: Government of Canada Yields

A table-first layout showing current yields, 1-year-ago comparison, and basis point changes across 7 tenors, followed by a yield curve chart overlay.

### Component Order (top to bottom)

1. **Yield table** — Prussian blue header, 3 data rows (Current, 1 Year Ago, Change), 7 tenor columns
2. **Spread badge row** — 2s10s spread with normal/inverted badge + BoC overnight rate
3. **Yield curve chart** — SVG with current (solid Prussian blue) vs 1-year-ago (dashed red) overlay, dot markers on current, legend
4. **Commentary** — em dash narrative with sources

### Yield Table CSS

```css
.yield-table-wrap { padding: 16px 20px 12px; }
.yield-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.yield-table th {
  padding: 10px 12px; font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.3px; color: #fff; background: var(--accent); text-align: center;
}
.yield-table th:first-child { text-align: left; border-radius: 6px 0 0 0; }
.yield-table th:last-child { border-radius: 0 6px 0 0; }
.yield-table td {
  padding: 10px 12px; text-align: center; font-weight: 600;
  font-variant-numeric: tabular-nums; border-bottom: 1px solid var(--border-light);
}
.yield-table td:first-child {
  text-align: left; font-size: 11px; font-weight: 600;
  color: var(--text-muted); text-transform: uppercase;
}
.yield-table .yield-current { font-size: 16px; font-weight: 700; color: var(--text); }
.yield-table .yield-prev { font-size: 12px; color: var(--text-muted); }
.yield-table .yield-chg { font-size: 12px; font-weight: 600; }
```

### Spread Badge

```css
.spread-badge {
  display: inline-flex; align-items: center; padding: 4px 12px;
  border-radius: 6px; font-size: 12px; font-weight: 600;
}
.spread-badge.normal { background: var(--green-bg); color: var(--green); }
.spread-badge.inverted { background: var(--red-bg); color: var(--red); }
```

### Yield Curve Chart

The yield curve SVG plots yield (y-axis) against tenor (x-axis) for two series:

- **Current** — solid Prussian blue line, `stroke-width: 2.5`, circle dots at each tenor (`r="4"`)
- **1 Year Ago** — dashed red line, `stroke: #c4320a`, `stroke-dasharray: 5,3`
- **Legend** — top-right, solid blue = "Current", dashed red = "1 Year Ago"

Y-axis: 2.0% to 5.0%. X-axis: 3M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y.

### 7 Yield Tenors

| Tenor | Data Key | Source |
|---|---|---|
| 3 Month | `ca_yield_3m` | Bank of Canada |
| 1 Year | `ca_yield_1y` | Bank of Canada |
| 2 Year | `ca_yield_2y` | Bank of Canada |
| 5 Year | `ca_yield_5y` | Bank of Canada |
| 10 Year | `ca_yield_10y` | Bank of Canada |
| 20 Year | `ca_yield_20y` | Bank of Canada |
| 30 Year | `ca_yield_30y` | Bank of Canada |

### Rendering Logic

```javascript
function renderYieldSection(briefing) {
  const yields = briefing.yields; // { current: {...}, yearAgo: {...} }
  // 1. Populate table cells with current/yearAgo/change values
  // 2. Calculate 2s10s spread = yields.current['10y'] - yields.current['2y']
  // 3. Set spread badge class: 'normal' if positive, 'inverted' if negative
  // 4. Generate SVG curve from yield values (map tenor positions to x, yield values to y)
  // 5. Render commentary from briefing.yield_commentary
}
```

---

## 6. Section 5: Commodities (Accordion Table)

A full-width accordion table with category tabs, group dividers, and expandable rows containing sparkline charts, metrics, narratives, and sources.

### Component Order (top to bottom)

1. **Category tabs** — All, Energy, Precious Metals, Base Metals, Agriculture, Forest Products
2. **Accordion table** — Prussian blue header row, category group dividers, clickable commodity rows
3. **Expanded row content** — narrative, metrics strip, SVG sparkline, sources
4. **Summary commentary** — overall commodity narrative with sources

### Table CSS

```css
.commodity-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.commodity-table thead th {
  background: var(--accent); color: #fff; padding: 11px 16px;
  text-align: left; font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.4px;
}
.commodity-table thead th:nth-child(n+3) { text-align: right; }
```

### 6 Table Columns

| Column | Alignment | Content |
|---|---|---|
| Commodity | Left | Name + unit badge + chevron |
| Price | Left | Current price, tabular-nums |
| Weekly | Right | % change with ▲/▼ arrow |
| Month-over-Month | Right | % change |
| Year-over-Year | Right | % change |
| 52-Week Range | Right | Low – High |

### Commodity Row HTML

```html
<tr class="commodity-row" onclick="toggleCmdRow(this)">
  <td class="cmd-name"><span class="row-chevron">&#9654;</span>{name} <span class="cmd-unit">{unit}</span></td>
  <td class="cmd-price">{price}</td>
  <td class="pill-change {direction}">▼ {weekly}%</td>
  <td class="pill-change {direction}">{mom}%</td>
  <td class="pill-change {direction}">{yoy}%</td>
  <td style="font-size:12px; color: var(--text-muted);">{low} – {high}</td>
</tr>
```

### Expanded Row Content Order

1. **Narrative** — em dash lead sentence pattern (`.cmd-narrative`)
2. **Metrics strip** — flex row of stat items (`.cmd-ts-stats`)
3. **SVG sparkline** — 1-year timeseries chart with optional reference lines
4. **Sources** — citation list

### Expand/Collapse JavaScript

```javascript
function toggleCmdRow(row) {
  var expandRow = row.nextElementSibling;
  if (row.classList.contains('expanded')) {
    row.classList.remove('expanded');
    expandRow.classList.remove('visible');
  } else {
    row.classList.add('expanded');
    expandRow.classList.add('visible');
  }
}
```

### Chevron Rotation CSS

```css
.row-chevron {
  display: inline-block; width: 16px; height: 16px; text-align: center;
  font-size: 10px; color: var(--text-muted); transition: transform 0.2s;
  margin-right: 6px;
}
.commodity-row.expanded .row-chevron { transform: rotate(90deg); }
.cmd-expand-row { display: none; }
.cmd-expand-row.visible { display: table-row; }
```

### Category Group Dividers

```css
.cmd-group-divider {
  padding: 6px 16px; font-size: 10px; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.5px; background: var(--bg);
  border-bottom: 1px solid var(--border-light);
}
```

### Category Tabs CSS

```css
.cat-tabs {
  display: flex; gap: 0; padding: 0 20px;
  border-bottom: 1px solid var(--border-light);
}
.cat-tab {
  padding: 10px 16px; font-size: 12px; font-weight: 500; color: var(--text-muted);
  cursor: pointer; border-bottom: 2px solid transparent;
}
.cat-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
```

### Category Tab Filtering

```javascript
function filterCommodityCategory(tab) {
  document.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  const category = tab.dataset.category; // 'all', 'energy', 'precious', 'base', 'agriculture', 'forest'
  document.querySelectorAll('.commodity-row, .cmd-expand-row, .cmd-group-divider-row').forEach(row => {
    if (category === 'all' || row.dataset.category === category) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}
```

### 13 Commodities (5 categories)

| Category | Commodity | Unit | Data Key | Source |
|---|---|---|---|---|
| Energy | WTI Crude | USD/bbl | `wti_crude` | yfinance `CL=F` |
| Energy | Brent Crude | USD/bbl | `brent_crude` | yfinance `BZ=F` |
| Energy | Natural Gas | USD/MMBtu | `natural_gas` | yfinance `NG=F` |
| Energy | WCS Discount | USD/bbl spread | `wcs_discount` | calculated |
| Precious Metals | Gold | USD/troy oz | `gold` | yfinance `GC=F` |
| Precious Metals | Silver | USD/troy oz | `silver` | yfinance `SI=F` |
| Base Metals | Copper | USD/lb | `copper` | yfinance `HG=F` |
| Base Metals | Uranium | USD/lb | `uranium` | UxC / Cameco |
| Base Metals | Nickel | USD/t | `nickel` | LME |
| Agriculture | Canola | CAD/t | `canola` | ICE `RS=F` |
| Agriculture | Wheat | USD/bu | `wheat` | yfinance `ZW=F` |
| Agriculture | Potash (Nutrien) | CAD/share | `potash_nutrien` | yfinance `NTR.TO` |
| Forest Products | Lumber | USD/MBF | `lumber` | yfinance `LBS=F` |

### Special: WTI Breakeven Reference Line

The WTI expanded view includes a $70 breakeven reference line on the sparkline chart. This is a dashed horizontal line at the $70 price level with a text label. The breakeven threshold is used to count how many Alberta oil sands projects are above breakeven.

```javascript
// In WTI sparkline rendering:
if (commodity.key === 'wti_crude') {
  const breakevenY = priceToY(70); // $70 breakeven
  svg += `<line x1="40" y1="${breakevenY}" x2="755" y2="${breakevenY}" stroke="#7a8599" stroke-width="1" stroke-dasharray="4,3"/>`;
  svg += `<text x="760" y="${breakevenY - 2}" fill="#7a8599" font-size="8" font-family="Inter">$70 breakeven</text>`;
}
```

---

## 7. Data Pipeline Integration

### Pipeline Output Schema (briefing_latest.json)

```json
{
  "market_commentary": "The S&P/TSX Composite gained...",
  "equity_indices": [
    {
      "key": "tsx_composite",
      "name": "S&P/TSX Composite",
      "value": 25427,
      "weekly_pct": 1.54,
      "ytd_pct": 4.8,
      "yoy_pct": 11.2,
      "high_52w": 26148,
      "low_52w": 22835,
      "commentary": "The TSX gained 1.5% this week..."
    }
  ],
  "fx_pairs": [
    {
      "key": "cad_usd",
      "name": "CAD/USD",
      "value": 0.7198,
      "weekly_pct": -0.42,
      "mom_pct": -1.85,
      "yoy_pct": -3.2
    }
  ],
  "fx_commentary": "The Canadian dollar weakened...",
  "yields": {
    "current": { "3m": 3.12, "1y": 3.08, "2y": 2.95, "5y": 3.18, "10y": 3.58, "20y": 3.65, "30y": 3.72 },
    "year_ago": { "3m": 4.68, "1y": 4.22, "2y": 3.85, "5y": 3.62, "10y": 3.48, "20y": 3.52, "30y": 3.55 },
    "boc_rate": 3.25,
    "spread_2s10s": 63,
    "curve_shape": "normal"
  },
  "yield_commentary": "The yield curve remained positively sloped...",
  "commodities": [
    {
      "key": "wti_crude",
      "name": "WTI Crude",
      "unit": "USD/bbl",
      "category": "energy",
      "price": 69.40,
      "weekly_pct": -2.1,
      "mom_pct": -6.8,
      "yoy_pct": -12.4,
      "high_52w": 84.20,
      "low_52w": 62.10,
      "avg_1y": 74.20,
      "projects_affected": 52,
      "commentary": "WTI crude declined 2.1% to $69.40...",
      "sources": ["NYMEX", "Alberta Energy Regulator", "Project Database"]
    }
  ],
  "commodity_commentary": "Precious metals led commodity gains..."
}
```

### timeseries.json

Timeseries data for all indices, FX pairs, yields, and commodities is stored in `timeseries.json` with 102 keys. Each key maps to an array of `[timestamp, value]` pairs. Charts are rendered from this data.

### Required Pipeline Additions

1. **Yield data** — fetch Government of Canada bond yields (Bank of Canada API or yfinance) for 7 tenors, store current + 1-year-ago
2. **Commodity metrics** — for each commodity, calculate `avg_1y`, `projects_affected` (count from project database by sector), and generate `commentary` via writing agent
3. **FX stats** — calculate MoM and YoY for each currency pair
4. **Equity stats** — fetch 52-week high/low from yfinance for each index

---

## 8. Rendering Architecture

### Main Render Function

```javascript
function renderMarkets(briefing) {
  renderMarketCommentary(briefing.market_commentary);
  renderEquityIndices(briefing.equity_indices);
  renderForeignExchange(briefing.fx_pairs, briefing.fx_commentary);
  renderYields(briefing.yields, briefing.yield_commentary);
  renderCommodities(briefing.commodities, briefing.commodity_commentary);
}
```

### Chart Library

No external chart library. All charts are inline SVG generated by JavaScript helper functions:

```javascript
function generateLineChart(data, options) {
  // options: { viewBox, gradientId, strokeColor, fillGradient, gridLines, xLabels, yLabels, showDot }
  // Returns SVG string
}

function generateYieldCurve(current, yearAgo, options) {
  // Two polylines: solid for current, dashed for year ago
  // Returns SVG string
}

function generateSparkline(data, options) {
  // Compact chart for commodity expanded rows
  // options: { referenceLine, referenceLabel }
  // Returns SVG string
}
```

---

## 9. Export Integration

The Markets tab data must be included in `export_dashboard.py` output:

```python
# In export_dashboard.py
market_data = {
    "market_commentary": briefing_row["market_commentary"],
    "equity_indices": json.loads(briefing_row["equity_indices"]),
    "fx_pairs": json.loads(briefing_row["fx_pairs"]),
    "fx_commentary": briefing_row["fx_commentary"],
    "yields": json.loads(briefing_row["yields"]),
    "yield_commentary": briefing_row["yield_commentary"],
    "commodities": json.loads(briefing_row["commodities"]),
    "commodity_commentary": briefing_row["commodity_commentary"],
}
```

---

## 10. Responsive Breakpoints

```css
@media (max-width: 768px) {
  .series-row { gap: 6px; padding: 12px 16px; }
  .series-pill { min-width: 110px; padding: 8px 10px; }
  .pill-value { font-size: 15px; }
  .fx-series-row { flex-wrap: wrap; }
  .fx-pill { flex: 1 1 45%; }
  .yield-table { font-size: 11px; }
  .yield-table th, .yield-table td { padding: 6px 8px; }
  .commodity-table { font-size: 12px; }
  .commodity-row td { padding: 10px 12px; }
  .cmd-expand-content { padding: 12px 16px; }
}
```

---

## 11. Implementation Checklist

- [ ] Add yield data fetching to Phase 1 (data collection) — Bank of Canada API for 7 tenors
- [ ] Add commodity metrics to export — `avg_1y`, `projects_affected`, per-commodity commentary
- [ ] Add FX MoM/YoY calculations to market data processing
- [ ] Implement `renderMarkets(briefing)` in `app.js`
- [ ] Implement SVG chart generation helpers (`generateLineChart`, `generateYieldCurve`, `generateSparkline`)
- [ ] Implement series pill selection (equities + FX) with chart re-render
- [ ] Implement commodity accordion with `toggleCmdRow()` and category tab filtering
- [ ] Implement yield table rendering with spread badge logic (normal/inverted)
- [ ] Implement WTI breakeven reference line in sparkline
- [ ] Add market data to `export_dashboard.py` output
- [ ] Wire up timeseries.json for all chart data sources
- [ ] Test responsive breakpoints at 768px
- [ ] Verify editorial policy compliance — no editorializing in any commentary
