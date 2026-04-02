# Provinces Tab — Implementation Guide

Reference mockup: `PROVINCES_MOCKUP.html`
Design spec: `DASHBOARD_DESIGN_SPEC.md` (Tab 2 section)

This guide covers everything needed to implement the Provinces tab in production: HTML structure, CSS classes, JavaScript rendering, data contracts, pipeline wiring, and deploy integration.

---

## 1. Page Layout

The Provinces tab uses a two-column flex layout — a sticky sidebar on the left and a scrolling content area on the right. This is the only tab that uses a sidebar; all other tabs render content in a single centered column.

### HTML Shell

```html
<div class="page" id="provinces-page">

  <nav class="prov-sidebar">
    <!-- 10 provinces + 3 territories, grouped -->
  </nav>

  <div class="page-main">
    <!-- Province header card -->
    <!-- 6 content sections -->
  </div>

</div>
```

### CSS

```css
.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 40px;
  display: flex;
  gap: 32px;
}

.page-main {
  flex: 1;
  min-width: 0;  /* prevents flex child from overflowing */
}
```

The `min-width: 0` on `.page-main` is critical — without it, wide tables and charts will push the flex child beyond its container width.

---

## 2. Province Sidebar

A sticky `<nav>` element with hidden radio inputs and styled labels. Pure CSS handles the active state — no JavaScript needed for selection highlighting.

### HTML

```html
<nav class="prov-sidebar">
  <div class="prov-sidebar-title">Provinces</div>

  <input type="radio" name="province" id="prov-ON" value="ON" class="prov-radio" checked>
  <label for="prov-ON" class="prov-label">Ontario</label>

  <input type="radio" name="province" id="prov-QC" value="QC" class="prov-radio">
  <label for="prov-QC" class="prov-label">Quebec</label>

  <input type="radio" name="province" id="prov-AB" value="AB" class="prov-radio">
  <label for="prov-AB" class="prov-label">Alberta</label>

  <input type="radio" name="province" id="prov-BC" value="BC" class="prov-radio">
  <label for="prov-BC" class="prov-label">British Columbia</label>

  <input type="radio" name="province" id="prov-SK" value="SK" class="prov-radio">
  <label for="prov-SK" class="prov-label">Saskatchewan</label>

  <input type="radio" name="province" id="prov-MB" value="MB" class="prov-radio">
  <label for="prov-MB" class="prov-label">Manitoba</label>

  <input type="radio" name="province" id="prov-NS" value="NS" class="prov-radio">
  <label for="prov-NS" class="prov-label">Nova Scotia</label>

  <input type="radio" name="province" id="prov-NB" value="NB" class="prov-radio">
  <label for="prov-NB" class="prov-label">New Brunswick</label>

  <input type="radio" name="province" id="prov-NL" value="NL" class="prov-radio">
  <label for="prov-NL" class="prov-label">Newfoundland &amp; Labrador</label>

  <input type="radio" name="province" id="prov-PE" value="PE" class="prov-radio">
  <label for="prov-PE" class="prov-label">Prince Edward Island</label>

  <div class="prov-sidebar-title" style="margin-top: 12px;">Territories</div>

  <input type="radio" name="province" id="prov-YT" value="YT" class="prov-radio">
  <label for="prov-YT" class="prov-label">Yukon</label>

  <input type="radio" name="province" id="prov-NT" value="NT" class="prov-radio">
  <label for="prov-NT" class="prov-label">Northwest Territories</label>

  <input type="radio" name="province" id="prov-NU" value="NU" class="prov-radio">
  <label for="prov-NU" class="prov-label">Nunavut</label>
</nav>
```

### CSS

```css
.prov-sidebar {
  width: 200px;
  flex-shrink: 0;
  position: sticky;
  top: 56px;                          /* clears the tab bar */
  align-self: flex-start;
  max-height: calc(100vh - 80px);
  overflow-y: auto;
}

.prov-sidebar-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-muted);
  padding: 0 12px 10px;
  border-bottom: 1px solid var(--border-light);
  margin-bottom: 6px;
}

.prov-radio { display: none; }

.prov-label {
  display: block;
  padding: 8px 12px;
  cursor: pointer;
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 6px;
  transition: background 0.1s, color 0.1s;
  border-left: 3px solid transparent;
  margin-bottom: 1px;
}

.prov-label:hover {
  background: var(--accent-light);
  color: var(--text);
}

.prov-radio:checked + .prov-label {
  color: var(--accent);
  font-weight: 600;
  background: var(--accent-light);
  border-left-color: var(--accent);
}
```

### Key Details

- **`top: 56px`** — matches the sticky tab bar height so the sidebar tucks below it
- **Province ordering** — west to east (BC, AB, SK, MB, ON, QC, NB, NS, NL, PE), then territories (YT, NT, NU). The mockup uses alphabetical for provinces; production should match the existing `PROVS` array in `app.js`
- **Full names only** — "Prince Edward Island" not "PEI", "Northwest Territories" not "NWT". No abbreviations in labels.
- **Radio `value` attributes** — use two-letter province codes (ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU). These must match the codes in `PROVS` and the pipeline's province metadata.

---

## 3. Province Header Card

A full-width Prussian blue card showing the province name, GDP threshold, and three summary stats.

### HTML

```html
<div class="province-header-card">
  <div>
    <h2>Ontario</h2>
    <div class="province-sub">Weekly provincial economic analysis · GDP threshold: $500M</div>
  </div>
  <div class="province-header-stats">
    <div class="stat-item">
      <div class="stat-value">287</div>
      <div class="stat-label">Active Projects</div>
    </div>
    <div class="stat-item">
      <div class="stat-value">$142.3B</div>
      <div class="stat-label">Pipeline Value</div>
    </div>
    <div class="stat-item">
      <div class="stat-value">12</div>
      <div class="stat-label">New This Week</div>
    </div>
  </div>
</div>
```

### CSS

```css
.province-header-card {
  background: var(--accent);
  border-radius: 8px;
  padding: 28px 32px;
  color: #fff;
  margin-bottom: 28px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.province-header-card h2 {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.province-header-card .province-sub {
  font-size: 13px;
  color: rgba(255,255,255,0.65);
}

.province-header-stats {
  display: flex;
  gap: 32px;
  text-align: right;
}

.province-header-stats .stat-value {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.province-header-stats .stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: rgba(255,255,255,0.6);
}
```

### Data Binding

| Field | Source |
|-------|--------|
| Province name | `PROVS` lookup by selected code |
| GDP threshold | `PROV_THRESHOLDS[code]`, formatted as currency |
| Active Projects | Count of projects where `province === code` and `status !== 'Cancelled'` and `status !== 'Complete'` |
| Pipeline Value | Sum of `value` for active projects in that province |
| New This Week | Count of projects with `discovered_date` in the current briefing week |

---

## 4. Section Flow

Six sections render top-to-bottom inside `.page-main`. Each section follows the shared section block pattern.

### Section Block Pattern

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Section Title — Ontario</h3>
    <span class="section-meta">Metadata text</span>
  </div>

  <!-- Section content here -->
</div>
```

```css
.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-light);
  margin-bottom: 20px;
}

.section-header .accent-bar {
  width: 4px;
  height: 22px;
  background: var(--accent);
  border-radius: 2px;
  flex-shrink: 0;
}

.section-header h3 {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
}

.section-header .section-meta {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.section-block {
  padding: 0 0 28px;
  margin-bottom: 28px;
}
```

---

## 5. Section 1: Provincial Analysis

Narrative text with em dash lead sentences, callout boxes, an insight chart, and collapsible sources.

### Narrative Pattern

```html
<div class="narrative">
  <p><span class="lead-sentence">Ontario's labour market added 5,200 jobs in March,
  a deceleration from the 18,400 recorded in February</span> — the provincial
  unemployment rate rose to 6.4%, above the national average of 6.2%.</p>

  <div class="callout">
    <strong>Cross-reference:</strong> 23 proposed residential projects ($4.2B)
    are in rate-sensitive sectors. A 25bps cut would move 8 of these below
    their financing thresholds.
  </div>

  <p><span class="lead-sentence">Building permits in the Toronto CMA declined
  4.8% in February</span> — the third consecutive monthly decline, reducing the
  12-month rolling total to $8.7B from $9.2B in the prior period.</p>
</div>
```

### CSS

```css
.narrative {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 16px;
  line-height: 1.75;
  color: var(--text);
}

.narrative p { margin-bottom: 16px; }

.narrative .lead-sentence { font-weight: 600; }

.narrative sup {
  font-family: 'Inter', sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
}

.callout {
  background: var(--accent-light);
  border-left: 3px solid var(--accent);
  border-radius: 0 8px 8px 0;
  padding: 14px 18px;
  margin: 12px 0 20px;
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.callout strong { color: var(--text); font-weight: 600; }
```

### Insight Chart

```html
<div class="insight-chart-wrapper">
  <div class="insight-chart-title">Ontario Unemployment Rate</div>
  <div class="insight-chart-subtitle">12-Month Trend · Source: StatCan 14-10-0287</div>
  <div class="chart-wrap">
    <canvas id="chart-prov-unemployment"></canvas>
  </div>
  <div class="chart-source">Source: Statistics Canada, Table 14-10-0287-01</div>
</div>
```

```css
.insight-chart-wrapper {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: 3px solid var(--accent);
  border-radius: 0 0 8px 8px;
  padding: 24px;
  margin: 24px 0;
}

.insight-chart-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 4px;
}

.insight-chart-subtitle {
  font-size: 12px;
  color: var(--text);
  margin-bottom: 16px;
}

.chart-wrap {
  position: relative;
  height: 220px;
  width: 100%;
}

.chart-source {
  margin-top: 10px;
  font-size: 10px;
  color: var(--text-secondary);
  border-top: 1px solid rgba(0,49,83,0.08);
  padding-top: 8px;
}
```

### Chart.js Configuration

Each province gets up to 2 insight charts driven by the `insightCharts` array from the pipeline. See the Chart.js rules in `DASHBOARD_DESIGN_SPEC.md` — no spread operators, no annotation plugin, no arrow functions, reference lines as secondary datasets.

```javascript
var chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: months,
    datasets: [
      {
        label: 'Ontario Unemployment Rate',
        data: data,
        borderColor: '#003153',
        backgroundColor: 'rgba(0,49,83,0.10)',
        fill: true,
        tension: 0.35,
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: '#003153',
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2
      },
      {
        label: 'Current',
        data: Array(12).fill(currentValue),
        borderColor: '#c4320a',
        borderWidth: 1,
        borderDash: [4, 3],
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#00253f',
        titleFont: { family: 'Inter', size: 11, weight: '600' },
        bodyFont: { family: 'Inter', size: 12 },
        padding: 10,
        cornerRadius: 6,
        displayColors: false,
        filter: function(item) { return item.datasetIndex === 0; },
        callbacks: {
          label: function(c) {
            return 'Unemployment: ' + c.parsed.y.toFixed(1) + '%';
          }
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          font: { family: 'Inter', size: 11, weight: '500' },
          color: '#4a5568'
        },
        border: { color: '#9aa5b4' }
      },
      y: {
        grid: { display: false },
        ticks: {
          font: { family: 'Inter', size: 11, weight: '500' },
          color: '#4a5568',
          callback: function(v) { return v.toFixed(1) + '%'; }
        },
        border: { display: false }
      }
    }
  }
});
```

### Collapsible Sources

```html
<details class="sources-section">
  <summary>Sources (4)</summary>
  <ol>
    <li><a href="...">Statistics Canada — Labour Force Survey, March 2026</a></li>
    <li><a href="...">Statistics Canada — Building Permits, February 2026</a></li>
  </ol>
</details>
```

### Data Binding

| Field | JSON Path |
|-------|-----------|
| Narrative text | `provinces[i].analysis` |
| Callout data | Generated from cross-reference engine output embedded in `analysis` |
| Chart data | `timeseries.json` keyed by `{PROV}_unemployment` (or `insightCharts[0].dataKeys`) |
| Sources | `provinces[i].sources[]` (title + url + archive_url) |

---

## 6. Section 2: Policy Developments

An intro paragraph followed by an accordion of policy items.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Policy Developments — Ontario</h3>
    <span class="section-meta">3 items this week</span>
  </div>

  <div class="narrative">
    <p><span class="lead-sentence">Three provincial policy developments this week
    affect tracked projects in Ontario</span> — two relate to housing and permitting,
    one to the energy transition framework.</p>
  </div>

  <div class="inner-card">
    <details class="policy-item" open>
      <summary>Ontario Housing Supply Action Plan — Phase 3 Regulations</summary>
      <div class="policy-body">
        The Ministry of Municipal Affairs published draft regulations...
        <a href="..." class="policy-link">Ontario Gazette, March 28 →</a>
      </div>
    </details>
    <details class="policy-item">
      <summary>IESO Long-Term Energy Plan — Storage Procurement</summary>
      <div class="policy-body">
        The Independent Electricity System Operator announced...
        <a href="..." class="policy-link">IESO, March 27 →</a>
      </div>
    </details>
  </div>
</div>
```

### CSS

```css
.inner-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
}

.policy-item { border-bottom: 1px solid var(--border-light); }
.policy-item:last-child { border-bottom: none; }

.policy-item summary {
  padding: 12px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.policy-item summary::-webkit-details-marker { display: none; }
.policy-item summary::before { content: '▸'; font-size: 11px; color: var(--text-muted); }
.policy-item[open] summary::before { content: '▾'; }

.policy-item .policy-body {
  padding: 0 0 14px 22px;
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.65;
}

.policy-link {
  display: inline-block;
  margin-top: 6px;
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  color: var(--accent);
  text-decoration: none;
}

.policy-link:hover { text-decoration: underline; }
```

### Data Binding

Policy items come from the `policy_snapshots` table, filtered by province. The pipeline's `policy_tracker.py` classifies each item into one of 8 categories (housing, energy_transition, infrastructure_funding, trade_policy, defence, resource_development, healthcare_infrastructure, fiscal_policy) and links them to affected sectors/provinces.

| Field | Source |
|-------|--------|
| Intro narrative | Generated by province agent in `analysis` or from policy_summary context |
| Policy items | `policy_snapshots` WHERE `province = '{code}'` AND `snapshot_date` in current week |
| Item title | `policy_snapshots.title` |
| Item body | `policy_snapshots.summary` |
| Source link | `policy_snapshots.source_url` |

---

## 7. Section 3: Key Indicators

Two indicator tables within a single section: 8 universal indicators, then 4 province-specific indicators under a subheader.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Key Indicators — Ontario</h3>
    <span class="section-meta">12 indicators · Updated Mar 28</span>
  </div>

  <!-- Universal indicators -->
  <div class="indicator-panel">
    <table class="ind-table">
      <thead>
        <tr>
          <th>Indicator</th>
          <th>Frequency</th>
          <th>Value</th>
          <th>Change</th>
          <th>Reference Period</th>
          <th>Next Release</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="ind-name">GDP Growth (Real)</td>
          <td class="ind-freq">Quarterly</td>
          <td class="ind-val">1.2%</td>
          <td class="chg-down">▼ −0.3pp from Q3 (1.5%)</td>
          <td class="ind-period">Q4 2025</td>
          <td class="ind-period">May 30</td>
          <td class="ind-source">StatCan 36-10-0402</td>
        </tr>
        <!-- ... 7 more universal rows ... -->
      </tbody>
    </table>
  </div>

  <!-- Province-specific indicators -->
  <h4 class="ind-section-label">Ontario-Specific Indicators</h4>
  <div class="indicator-panel">
    <table class="ind-table">
      <thead>
        <tr>
          <th>Indicator</th>
          <th>Frequency</th>
          <th>Value</th>
          <th>Change</th>
          <th>Reference Period</th>
          <th>Next Release</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="ind-name">Auto Production</td>
          <td class="ind-freq">Monthly</td>
          <td class="ind-val">124,200 units</td>
          <td class="chg-up">▲ +3.4% from Feb (120,100)</td>
          <td class="ind-period">March 2026</td>
          <td class="ind-period">Apr 18</td>
          <td class="ind-source">DesRosiers</td>
        </tr>
        <!-- ... 3 more province-specific rows ... -->
      </tbody>
    </table>
  </div>
</div>
```

### CSS (indicator-specific)

```css
.indicator-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 24px;
}

.ind-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.ind-table thead th {
  background: var(--accent);
  color: #ffffff;
  padding: 8px 12px;
  text-align: left;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.ind-table thead th:nth-child(n+2) { text-align: right; }

.ind-table tbody td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}

.ind-table tbody tr:last-child td { border-bottom: none; }
.ind-table tbody tr:hover { background: var(--accent-light); }
.ind-table tbody td:nth-child(n+2) { text-align: right; }

.ind-table .ind-name {
  font-weight: 500;
  color: var(--text);
  white-space: normal;
}

.ind-table .ind-val {
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.ind-freq {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted);
  text-align: center;
}

.chg-up { color: var(--green); }
.chg-down { color: var(--red); }
.chg-flat { color: var(--grey); }

.ind-period { font-size: 10px; color: var(--text-muted); }
.ind-source { font-size: 10px; color: var(--text-muted); }

.ind-section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  margin: 20px 0 8px;
  padding: 0;
}
```

### 8 Universal Indicators (all provinces)

| # | Indicator | Frequency | StatCan Table |
|---|-----------|-----------|---------------|
| 1 | GDP Growth (Real) | Quarterly | 36-10-0402 |
| 2 | Unemployment Rate | Monthly | 14-10-0287 |
| 3 | CPI Inflation | Monthly | 18-10-0004 |
| 4 | Employment Rate | Monthly | 14-10-0287 |
| 5 | Participation Rate | Monthly | 14-10-0287 |
| 6 | Wage Growth | Monthly | 14-10-0287 |
| 7 | Housing Starts | Monthly | CMHC |
| 8 | Building Permits | Monthly | 34-10-0066 |

### Province-Specific Indicators (4 per province)

| Code | Indicator 1 | Indicator 2 | Indicator 3 | Indicator 4 |
|------|-------------|-------------|-------------|-------------|
| ON | Auto Production (DesRosiers) | Toronto Home Price Index (TRREB) | Financial Services Employment (StatCan 14-10-0022) | Ring of Fire Mining Permits (Ontario MNDM) |
| QC | Aerospace Exports (StatCan 12-10-0129) | Montreal Home Price Index (QPAREB Centris) | Hydro-Quebec Generation Capacity (HQ) | AI/Tech Venture Capital (CVCA) |
| AB | Oil Sands Production (AER ST-39) | WCS-WTI Differential (market) | Drilling Rig Count (CAODC) | Calgary Office Vacancy Rate (CBRE) |
| BC | Port of Vancouver TEU Volume (VFPA) | Vancouver Home Price Index (REBGV) | Lumber Export Value (StatCan 12-10-0129) | Film/TV Production Spending (CMPA) |
| SK | Potash Production Volume (StatCan 16-10-0048) | Crop Receipts (StatCan 21-10-0019) | Uranium Mine Output (CNSC) | Oil Production (SK Government) |
| MB | Agriculture Receipts (StatCan 21-10-0019) | Winnipeg CMA Employment (StatCan 14-10-0384) | Hydro Generation (Manitoba Hydro) | Manufacturing Sales (StatCan 16-10-0048) |
| NS | Shipbuilding Contracts Value (Irving/PSC) | Halifax Home Price Index (NSAR MLS) | Seafood Export Value (StatCan 12-10-0129) | Tourism Visitors (NS Tourism) |
| NB | Forestry Output Value (StatCan 16-10-0048) | Saint John Refinery Throughput (Irving Oil) | Aquaculture Production (DFO) | NB Power Generation (NB Power) |
| NL | Offshore Oil Production (C-NLOPB) | Muskrat Falls Generation (NL Hydro) | Mineral Shipments Value (NL Government) | Marine/Fishery Landings (DFO) |
| PE | Potato Crop Value (StatCan 21-10-0019) | Tourism Revenue (PEI Tourism) | Shellfish Aquaculture Volume (DFO) | Population Growth Rate (StatCan 17-10-0009) |
| YT | Mining Exploration Spending (NRCan) | Placer Gold Production (YT Mining) | Tourism Visitors (YT Tourism) | Federal Transfer Revenue (YT Finance) |
| NT | Diamond Production Value (GNWT) | Mining Exploration Spending (NRCan) | Resource Royalties (GNWT Finance) | Remediation Site Progress (CIRNAC) |
| NU | Mining Exploration Spending (NRCan) | Inuit Employment Rate (StatCan 14-10-0364) | Construction Investment (StatCan 34-10-0175) | Federal Transfer Revenue (NU Finance) |

### Data Binding

Universal indicators come from `indicator_history` table filtered by province. The pipeline fetches these via StatCan WDS API in `phases/data_collection.py` and stores them with `province` field set to the province name or code.

Province-specific indicators require additional data sources beyond StatCan. Many come from provincial agencies (DesRosiers, TRREB, AER, VFPA, etc.). These are fetched during the data collection phase and stored in `indicator_history` with appropriate source attribution.

| Field | Source |
|-------|--------|
| Indicator name | Hardcoded per province (see table above) |
| Value | `indicator_history.value` WHERE `indicator_name` and `province` match |
| Change | Computed: `value - previous_value` with direction arrow |
| Reference period | `indicator_history.period` |
| Next release | Derived from frequency + reference period, or from `events.json` |
| Source | `indicator_history.source` |

---

## 8. Section 4: Sector Signals

A 2-column grid of enrichment cards showing sector highlights, labour market, trade, and hiring signals.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Sector Signals — Ontario</h3>
    <span class="section-meta">Week of Mar 30</span>
  </div>

  <div class="two-col">
    <div class="enrichment-card">
      <div class="enrichment-card-title"><span class="dot"></span> Sector Highlights</div>
      <p><span class="lead-sentence">Manufacturing PMI in Ontario rose to 52.1
      in March</span> — the first expansion reading in four months, driven by
      auto parts and food processing subsectors.</p>
    </div>

    <div class="enrichment-card">
      <div class="enrichment-card-title"><span class="dot"></span> Labour Market</div>
      <div class="enrichment-metric">
        <span class="label">Employment</span>
        <span class="value">7,582,400</span>
      </div>
      <div class="enrichment-metric">
        <span class="label">Unemployment Rate</span>
        <span class="value chg-up">6.4%</span>
      </div>
      <div class="enrichment-metric">
        <span class="label">Participation Rate</span>
        <span class="value">64.8%</span>
      </div>
    </div>

    <div class="enrichment-card">
      <div class="enrichment-card-title"><span class="dot"></span> Trade &amp; Commodities</div>
      <div class="enrichment-metric">
        <span class="label">Exports</span>
        <span class="value">$22.1B</span>
      </div>
      <div class="enrichment-metric">
        <span class="label">Imports</span>
        <span class="value">$26.8B</span>
      </div>
      <div class="enrichment-metric">
        <span class="label">Trade Balance</span>
        <span class="value chg-down">−$4.7B</span>
      </div>
    </div>

    <div class="enrichment-card">
      <div class="enrichment-card-title"><span class="dot"></span> Hiring Signals</div>
      <p><strong>Construction (+12%)</strong> in the Greater Toronto Area and
      <strong>healthcare (+8%)</strong> in Ottawa-Gatineau showed elevated posting
      activity this week.</p>
    </div>
  </div>
</div>
```

### CSS

```css
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.enrichment-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px 20px;
}

.enrichment-card-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.enrichment-card-title .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}

.enrichment-card p {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.enrichment-metric {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 13px;
}

.enrichment-metric:last-child { border-bottom: none; }
.enrichment-metric .label { color: var(--text-secondary); }
.enrichment-metric .value {
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
```

### Data Binding

| Card | JSON Path |
|------|-----------|
| Sector Highlights | `provinces[i].sectorHighlights` |
| Labour Market | `provinces[i].labourDeepDive` or `provinces[i].indicators` (unemployment, employment, participation) |
| Trade & Commodities | `provinces[i].tradeExposure` or `provinces[i].indicators` (exports, imports) |
| Hiring Signals | `job_snapshots` WHERE `province = '{code}'` AND `snapshot_date` in current week |

---

## 9. Section 5: Projects Preview

A narrative intro, then a 5-column projects table with status badges.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Projects Preview — Ontario</h3>
    <span class="section-meta">287 tracked · $142.3B total value</span>
  </div>

  <div class="narrative">
    <p><span class="lead-sentence">Twelve new projects entered the Ontario pipeline
    this week</span> — led by a $2.1B transit expansion in Mississauga and a $680M
    data centre campus in Markham.</p>
  </div>

  <div class="inner-card" style="padding: 0; overflow: hidden;">
    <table class="projects-table">
      <thead>
        <tr>
          <th>Project</th>
          <th>City</th>
          <th>Sector</th>
          <th>Value</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Hurontario LRT Extension</strong></td>
          <td>Mississauga</td>
          <td>Infrastructure</td>
          <td>$2.1B</td>
          <td><span class="status-badge status-pre">Pre-construction</span></td>
        </tr>
        <!-- ... more rows ... -->
      </tbody>
    </table>
    <a href="#" class="footer-link">View all Ontario projects →</a>
  </div>
</div>
```

### CSS

```css
.projects-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.projects-table thead th {
  background: var(--accent);
  color: #fff;
  padding: 10px 12px;
  text-align: left;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.projects-table tbody td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}

.projects-table tbody tr:hover { background: var(--accent-light); }

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.status-proposed { background: #fef3c7; color: #92400e; }
.status-pre { background: #dbeafe; color: #1e40af; }
.status-construction { background: #d1fae5; color: #065f46; }
.status-review { background: #ede9fe; color: #5b21b6; }

.footer-link {
  display: block;
  text-align: right;
  padding: 12px 16px;
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
  border-top: 1px solid var(--border-light);
}

.footer-link:hover { text-decoration: underline; }
```

### Data Binding

Projects come from `projects_{slug}.json` (per-province export) or filtered from `projects_all.json`. The table shows the 5-8 most notable projects for the week (new discoveries, status changes, highest value).

| Field | Source |
|-------|--------|
| Project name | `projects[].name` |
| City | `projects[].cma` or extracted from location |
| Sector | `projects[].sector` (mapped to display name) |
| Value | `projects[].value` (formatted as currency) |
| Status | `projects[].status` (mapped to badge class) |
| Total count + value | Computed from full province project set |

---

## 10. Section 6: Upcoming Events

Province-specific watchlist items for the next two weeks.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Upcoming Events — Ontario</h3>
    <span class="section-meta">Next 2 weeks</span>
  </div>

  <div class="inner-card">
    <div class="watchlist-item">
      <span class="impact-dot impact-high"></span>
      <span class="watchlist-date">Apr 3</span>
      <span class="watchlist-event">Statistics Canada — Employment, March (Ontario breakdown)</span>
      <span class="watchlist-institution">StatCan</span>
    </div>
    <div class="watchlist-item">
      <span class="impact-dot impact-medium"></span>
      <span class="watchlist-date">Apr 8</span>
      <span class="watchlist-event">Statistics Canada — Building Permits, February (provincial)</span>
      <span class="watchlist-institution">StatCan</span>
    </div>
    <!-- ... more items ... -->
  </div>
</div>
```

### CSS

```css
.watchlist-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 13px;
}

.watchlist-item:last-child { border-bottom: none; }

.watchlist-date {
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
  min-width: 70px;
  font-size: 12px;
}

.watchlist-event { color: var(--text); flex: 1; }

.watchlist-institution {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.impact-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.impact-high { background: var(--red); }
.impact-medium { background: #d97706; }
.impact-low { background: var(--grey); }
```

### Data Binding

| Field | Source |
|-------|--------|
| Events | `provinces[i].watchlistItems[]` from briefing, or `events.json` filtered by province relevance |
| Date | `watchlistItems[].date` (formatted as "Mon DD") |
| Event name | `watchlistItems[].event_name` |
| Institution | `watchlistItems[].institution` |
| Impact level | `watchlistItems[].impact` → mapped to dot color class |

---

## 11. JavaScript Rendering Architecture

### Province Selection Handler

When a user clicks a sidebar label, the radio input changes via native browser behavior (no JS needed for the visual state). JavaScript listens for the `change` event to re-render the content area.

```javascript
function initProvinceSelector() {
  var radios = document.querySelectorAll('.prov-radio');
  for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener('change', function() {
      renderProvinceContent(this.value);
    });
  }
}
```

### Main Render Function

```javascript
function renderProvinceContent(code) {
  var prov = findProvince(code);          // lookup in D.provinces[]
  var projects = loadProvinceProjects(code); // from projects_{slug}.json
  var indicators = getProvinceIndicators(code);
  var policies = getProvincePolicies(code);
  var events = getProvinceEvents(code);

  var main = document.querySelector('.page-main');
  main.innerHTML = '';

  // 1. Header card
  main.appendChild(buildHeaderCard(prov, projects));

  // 2. Section 1: Provincial Analysis
  main.appendChild(buildAnalysisSection(prov));

  // 3. Section 2: Policy Developments
  main.appendChild(buildPolicySection(prov, policies));

  // 4. Section 3: Key Indicators
  main.appendChild(buildIndicatorsSection(prov, indicators, code));

  // 5. Section 4: Sector Signals
  main.appendChild(buildSectorSignalsSection(prov));

  // 6. Section 5: Projects Preview
  main.appendChild(buildProjectsSection(prov, projects));

  // 7. Section 6: Upcoming Events
  main.appendChild(buildEventsSection(prov, events));

  // 8. Initialize charts after DOM is ready
  initProvinceCharts(prov, code);
}
```

### Province Name Matching

The pipeline stores province names in various formats. The frontend needs fuzzy matching.

```javascript
var PROV_NAME_MAP = {
  'ON': 'Ontario', 'QC': 'Quebec', 'AB': 'Alberta',
  'BC': 'British Columbia', 'SK': 'Saskatchewan', 'MB': 'Manitoba',
  'NS': 'Nova Scotia', 'NB': 'New Brunswick',
  'NL': 'Newfoundland and Labrador', 'PE': 'Prince Edward Island',
  'YT': 'Yukon', 'NT': 'Northwest Territories', 'NU': 'Nunavut'
};

function findProvince(code) {
  var name = PROV_NAME_MAP[code];
  for (var i = 0; i < D.provinces.length; i++) {
    var p = D.provinces[i];
    if (p.name === name || p.name === code) return p;
    // Handle variants: "Newfoundland & Labrador" vs "Newfoundland and Labrador"
    if (p.name.replace('&', 'and') === name) return p;
  }
  return null;
}
```

### GDP Threshold Lookup

```javascript
var PROV_THRESHOLDS = {
  'ON': 500e6, 'QC': 250e6, 'AB': 200e6, 'BC': 175e6,
  'SK': 45e6,  'MB': 40e6,  'NS': 25e6,  'NB': 20e6,
  'NL': 17e6,  'PE': 5e6,   'YT': 3e6,   'NT': 3e6, 'NU': 3e6
};
```

---

## 12. Data Pipeline Integration

### Pipeline Phases That Feed Province Data

```
Phase 1: Data Collection
  └─ statcan_extended.py      → indicator_history (unemployment, CPI, GDP, etc.)
  └─ data_collection.py       → indicator_history (BoC rate, commodities)

Phase 2: Discovery
  └─ google_news_rss_search.py → articles (tagged with province by metadata_tagger.py)
  └─ rss_filter.py             → filtered articles
  └─ gov_sources.py            → IAAC projects, provincial EA registries
  └─ procurement_monitor.py    → procurement_snapshots (federal/provincial contracts)

Phase 3: Analysis
  └─ province_agents.py        → 13 province analyses in briefing JSON
  └─ policy_tracker.py         → policy_snapshots
  └─ job_monitor.py            → job_snapshots (hiring spikes by CMA)

Phase 4: Export
  └─ export_dashboard.py       → briefing_latest.json (provinces array)
                               → projects_{slug}.json (per-province)
                               → indicators.json
                               → timeseries.json (provincial series)
                               → events.json
```

### Province Agent Output Contract

Each province agent (`phases/province_agents.py`) receives enriched context and returns a JSON object with these fields:

```json
{
  "analysis": "250-400 word narrative (Source Serif 4 style, em dash leads)",
  "sectorHighlights": "Top 2-3 sector developments with NAICS GDP context",
  "labourDeepDive": "Employment/wage/participation narrative",
  "consumerPulse": "Cost-of-living, housing, energy themes",
  "tradeExposure": "Trade & commodities exposure narrative",
  "marketContext": "Provincial market impact narrative",
  "watchlistItems": [
    {
      "date": "YYYY-MM-DD",
      "event_name": "Event description",
      "institution": "Source institution",
      "impact": "high|medium|low"
    }
  ],
  "insightCharts": [
    {
      "dataKeys": ["ON_unemployment"],
      "title": "Ontario Unemployment Rate",
      "chartType": "line"
    }
  ],
  "sources": [
    {
      "url": "https://...",
      "title": "Source Title",
      "archive_url": "https://web.archive.org/..."
    }
  ]
}
```

### JSON Files Consumed by Frontend

| File | Contents | Used By |
|------|----------|---------|
| `briefing_latest.json` | `provinces[]` array with analysis text, indicators, sources, watchlist | Sections 1, 2, 4, 6 |
| `projects_{slug}.json` | Province-filtered projects above GDP threshold | Section 5, header card stats |
| `indicators.json` | Full indicator history with validation status | Section 3 |
| `timeseries.json` | Time series keyed by `{PROV}_{indicator}` | Insight charts |
| `events.json` | 30-day event window | Section 6 |

### Indicator History Schema

```sql
indicator_history (
  indicator_name TEXT NOT NULL,
  province TEXT DEFAULT 'National',
  period TEXT DEFAULT '',
  value REAL,
  previous_value REAL,
  change REAL,
  source TEXT DEFAULT '',
  fetched_at TEXT,
  validated INTEGER DEFAULT 0
);
```

### Province Indicators in Timeseries

The `timeseries.json` export includes provincial series keyed as `{PROV_CODE}_{indicator}`:

- `ON_unemployment`, `QC_unemployment`, `AB_unemployment`, etc.
- `ON_cpi`, `QC_cpi`, `AB_cpi`, etc.
- Extended series for major provinces (ON, QC): exports, imports, capital investment, GDP by goods/services, manufacturing sales, housing starts

---

## 13. Deploy Integration

### Export to GitHub Pages

`tools/export_dashboard.py` writes all JSON files to `docs/data/`. The deploy script `tools/deploy_to_github.py` syncs `public/` to `docs/` and pushes to the GitHub Pages branch.

```
export_dashboard.export_all()
  └─ writes to docs/data/briefing_latest.json
  └─ writes to docs/data/projects_ontario.json (etc.)
  └─ writes to docs/data/indicators.json
  └─ writes to docs/data/timeseries.json
  └─ writes to docs/data/events.json

deploy_to_github.py
  └─ copies public/ → docs/
  └─ git add, commit, push to GitHub Pages
```

### Frontend File Structure

```
public/
  index.html            ← single-page app, all tabs
  js/
    app.js              ← main rendering logic (renderProvinces, renderProvinceContent)
  css/
    style.css           ← shared styles (all the CSS patterns from this guide)
```

### Data Loading in app.js

The frontend loads JSON files on page init and caches them in the global `D` object:

```javascript
var D = {};  // global data store

function loadData() {
  return Promise.all([
    fetch('data/briefing_latest.json').then(function(r) { return r.json(); }),
    fetch('data/indicators.json').then(function(r) { return r.json(); }),
    fetch('data/timeseries.json').then(function(r) { return r.json(); }),
    fetch('data/events.json').then(function(r) { return r.json(); })
  ]).then(function(results) {
    D.briefing = results[0];
    D.provinces = results[0].provinces || [];
    D.indicators = results[1];
    D.timeseries = results[2];
    D.events = results[3];
  });
}
```

Province project files are loaded on demand when a province is selected:

```javascript
function loadProvinceProjects(code) {
  var slug = PROV_NAME_MAP[code].toLowerCase().replace(/ /g, '_');
  return fetch('data/projects_' + slug + '.json')
    .then(function(r) { return r.json(); });
}
```

---

## 14. Responsive Behavior

At narrower viewports, the sidebar should collapse and the layout should stack.

```css
@media (max-width: 899px) {
  .page {
    flex-direction: column;
    padding: 24px 16px;
    gap: 0;
  }

  .prov-sidebar {
    position: static;
    width: 100%;
    max-height: none;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 8px;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-light);
  }

  .prov-sidebar-title {
    width: 100%;
    border-bottom: none;
    padding-bottom: 6px;
    margin-bottom: 2px;
  }

  .prov-label {
    padding: 6px 10px;
    border-left: none;
    border-radius: 6px;
    font-size: 12px;
  }

  .prov-radio:checked + .prov-label {
    border-left-color: transparent;
  }

  .two-col {
    grid-template-columns: 1fr;
  }
}
```

At the narrowest breakpoint (below 600px), indicator tables may need horizontal scroll:

```css
@media (max-width: 599px) {
  .indicator-panel {
    overflow-x: auto;
  }

  .ind-table {
    min-width: 600px;
  }
}
```

---

## 15. Implementation Checklist

### Frontend (app.js)

1. Add sidebar HTML generation in `renderProvinces()`
2. Replace pill selector with sidebar radio inputs
3. Add `renderProvinceContent(code)` function with 6 section builders
4. Add province-specific indicator lookup (4 indicators per province)
5. Add Chart.js initialization for province insight charts
6. Add `loadProvinceProjects(code)` lazy-loader for per-province project files
7. Add responsive breakpoint CSS for sidebar collapse
8. Wire radio `change` event to content re-render

### Backend (pipeline)

1. Ensure `province_agents.py` output matches the JSON contract in Section 12
2. Ensure `export_dashboard.py` exports `projects_{slug}.json` for all 13 provinces
3. Ensure `timeseries.json` includes provincial series (`{CODE}_unemployment`, `{CODE}_cpi`)
4. Ensure `indicator_history` stores province-level values for all 8 universal indicators
5. Add province-specific indicator fetching for the 4 custom indicators per province (new data sources)
6. Ensure `policy_snapshots` includes province field for filtering
7. Ensure `job_snapshots` includes province/CMA field for hiring signals

### Deploy

1. Verify `export_all()` writes all province JSON files to `docs/data/`
2. Verify `deploy_to_github.py` includes new CSS in `style.css`
3. Test with GitHub Pages — confirm all JSON files load via relative paths
