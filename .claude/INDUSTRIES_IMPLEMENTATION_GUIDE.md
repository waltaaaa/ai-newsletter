# Industries Tab — Implementation Guide

Reference mockup: `INDUSTRIES_MOCKUP.html`
Design spec: `DASHBOARD_DESIGN_SPEC.md` (Tab 3 section)

This guide covers everything needed to implement the Industries tab in production: HTML structure, CSS classes, JavaScript rendering, data contracts, pipeline wiring, and deploy integration.

---

## 1. Page Layout

The Industries tab uses a single centered column — no sidebar. Three sections stack vertically: Industry Overview, Biggest Movers, and All Sectors (expandable table).

### HTML Shell

```html
<div class="page" id="industries-page">

  <!-- Section 1: Industry Overview -->
  <div class="section-block"> ... </div>

  <!-- Section 2: Biggest Movers (4 cards) -->
  <div class="section-block"> ... </div>

  <!-- Section 3: All Sectors (expandable table) -->
  <div class="section-block"> ... </div>

</div>
```

### CSS

```css
.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 40px;
}
```

No flex layout needed — this tab is a simple single-column flow within the shared `.page` container.

---

## 2. Section 1: Industry Overview

A narrative summary of all 20 sectors with an em dash lead sentence and a callout box cross-referencing the project database.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Industry Overview</h3>
    <span class="section-meta">20 NAICS sectors · GDP by industry, {month} {year}</span>
  </div>

  <div class="narrative">
    <p><span class="lead-sentence">{executive summary lead}</span> — {supporting detail}</p>

    <div class="callout">
      <strong>Pipeline cross-reference:</strong> {total projects} ({total value}) across all sectors.
      Goods-producing: {goods count} ({goods value}), services-producing: {services count} ({services value}).
      {status changes} projects changed status this week.
    </div>
  </div>
</div>
```

### CSS

All classes are shared from the design system — `.narrative`, `.lead-sentence`, `.callout`. No new CSS needed.

### Data Binding

| Field | Source |
|-------|--------|
| Executive summary | `industry_executive_summary` from briefing JSON (strip HTML `<p>` tags, convert to em dash narrative) |
| Month/year | Derived from `today_str` in briefing metadata |
| Total projects | `COUNT(*)` from `projects` where status not in ('Cancelled', 'Complete') |
| Total value | `SUM(value)` from same query |
| Goods/services split | Filter by NAICS code: goods = 11, 21, 22, 23, 31-33; services = all others |
| Status changes | Count of projects with `status_changed_date` in current briefing week |

---

## 3. Section 2: Biggest Movers

Four full-width cards highlighting the sectors with the largest month-over-month GDP changes — 2 gainers and 2 decliners.

### HTML

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>Biggest Movers</h3>
    <span class="section-meta">Largest month-over-month changes</span>
  </div>

  <!-- Repeat for each of the 4 movers -->
  <div class="mover-card">
    <div class="mover-card-header">
      <div class="mover-title">{sector name}</div>
      <span class="mover-direction up">▲ +{mm}% month-over-month</span>
    </div>
    <div class="mover-metrics">
      <div class="mover-metric">
        <span class="mover-metric-label">GDP (Monthly)</span>
        <span class="mover-metric-value">{gdp}</span>
      </div>
      <div class="mover-metric">
        <span class="mover-metric-label">Year-over-Year</span>
        <span class="mover-metric-value chg-up">{yy}</span>
      </div>
      <div class="mover-metric">
        <span class="mover-metric-label">Active Projects</span>
        <span class="mover-metric-value">{count}</span>
      </div>
      <div class="mover-metric">
        <span class="mover-metric-label">Pipeline Value</span>
        <span class="mover-metric-value">{value}</span>
      </div>
    </div>
    <div class="mover-analysis">
      <span class="lead-sentence">{analysis lead}</span> — {analysis body}
      <div class="sources"><span>Sources:</span> {source1} · {source2} · ...</div>
    </div>
  </div>
</div>
```

### CSS

```css
.mover-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 22px 24px;
  margin-bottom: 16px;
}

.mover-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.mover-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
}

.mover-direction {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 6px;
}

.mover-direction.up {
  background: var(--green-bg);
  color: var(--green);
}

.mover-direction.down {
  background: var(--red-bg);
  color: var(--red);
}

.mover-metrics {
  display: flex;
  gap: 24px;
  padding: 12px 0;
  margin-bottom: 12px;
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
}

.mover-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mover-metric-label {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.mover-metric-value {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.mover-analysis {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.mover-analysis .lead-sentence {
  font-weight: 600;
  color: var(--text);
}
```

### Mover Selection Logic

```javascript
function selectMovers(goodsArr, servicesArr) {
  var all = goodsArr.concat(servicesArr);

  // Parse mm string to number, skip empty/missing
  var withChange = [];
  for (var i = 0; i < all.length; i++) {
    var mmStr = (all[i].mm || '').replace('%', '').replace('+', '');
    var mmNum = parseFloat(mmStr);
    if (!isNaN(mmNum)) {
      all[i]._mmNum = mmNum;
      withChange.push(all[i]);
    }
  }

  // Sort descending by absolute change
  withChange.sort(function(a, b) {
    return Math.abs(b._mmNum) - Math.abs(a._mmNum);
  });

  // Pick top 2 gainers and top 2 decliners
  var gainers = [];
  var decliners = [];
  for (var j = 0; j < withChange.length; j++) {
    if (withChange[j]._mmNum > 0 && gainers.length < 2) {
      gainers.push(withChange[j]);
    } else if (withChange[j]._mmNum < 0 && decliners.length < 2) {
      decliners.push(withChange[j]);
    }
    if (gainers.length === 2 && decliners.length === 2) break;
  }

  return gainers.concat(decliners);
}
```

### Data Binding

| Field | Source |
|-------|--------|
| Sector name | `sector.name` from `goodsIndustries` / `servicesIndustries` |
| Direction class | `sector.isNegative ? 'down' : 'up'` |
| Direction symbol | `sector.isNegative ? '▼' : '▲'` |
| Month-over-month | `sector.mm` (string, e.g. "+1.1%") |
| GDP monthly | From `timeseries.json` GDP by industry key, or from StatCan hard data in briefing |
| Year-over-year | `sector.yy` (string) |
| Active projects | `COUNT(*)` from `projects` where sector matches NAICS code group |
| Pipeline value | `SUM(value)` from same query |
| Analysis text | `sector.analysis` (convert from `<ul><li>` HTML to em dash narrative prose) |
| Sources | `sector.industrySources[]` — render as `title` strings separated by ` · ` |

### Analysis Text Conversion

The pipeline outputs analysis as `<ul class="list-disc..."><li>bullet<sup>N</sup></li>...</ul>`. The frontend must convert this to em dash narrative format:

```javascript
function convertAnalysisToNarrative(html) {
  // Strip outer <ul> tags
  var text = html.replace(/<\/?ul[^>]*>/g, '');
  // Extract <li> content
  var items = [];
  var liRegex = /<li[^>]*>(.*?)<\/li>/g;
  var match;
  while ((match = liRegex.exec(text)) !== null) {
    items.push(match[1].replace(/<sup>\d+<\/sup>/g, '').trim());
  }
  if (items.length === 0) return html;

  // First item becomes lead sentence, rest joined with em dashes
  var lead = '<span class="lead-sentence">' + items[0] + '</span>';
  if (items.length === 1) return lead;
  return lead + ' — ' + items.slice(1).join('. ') + '.';
}
```

---

## 4. Section 3: All Sectors (Expandable Table)

A compact ranked table of all 20 NAICS sectors with expandable rows. Clicking any row reveals a narrative write-up, supplementary metrics, and source citations.

### HTML Structure

```html
<div class="section-block">
  <div class="section-header">
    <div class="accent-bar"></div>
    <h3>All Sectors</h3>
    <span class="section-meta">Click any row to read the analysis · 20 NAICS industries</span>
  </div>

  <!-- View Toggle -->
  <div class="controls-row">
    <div class="view-toggle">
      <button class="toggle-btn active" data-filter="all">All</button>
      <button class="toggle-btn" data-filter="goods">Goods-Producing</button>
      <button class="toggle-btn" data-filter="services">Services-Producing</button>
    </div>
  </div>

  <!-- Goods-Producing -->
  <div class="subsection-divider" data-group="goods">Goods-Producing Industries</div>
  <div class="sector-table-wrap" data-group="goods">
    <table class="sector-table">
      <thead>
        <tr>
          <th>Sector</th>
          <th>GDP</th>
          <th>Month-over-Month</th>
          <th>Year-over-Year</th>
          <th>Projects</th>
          <th>Pipeline Value</th>
        </tr>
      </thead>
      <tbody>
        <!-- Repeated for each goods sector -->
        <tr class="sector-row" onclick="toggleRow(this)">
          <td class="tbl-name"><span class="row-chevron">&#9654;</span>{name}</td>
          <td class="tbl-gdp">{gdp}</td>
          <td class="{chg-class}">▲ {mm}</td>
          <td class="{chg-class}">{yy}</td>
          <td class="tbl-projects">{count}</td>
          <td class="tbl-value">{value}</td>
        </tr>
        <tr class="expand-row">
          <td colspan="6">
            <div class="expand-content">
              <div class="expand-metrics">
                <!-- 2-3 supplementary metrics -->
              </div>
              <span class="lead-sentence">{lead}</span> — {body}
              <div class="sources"><span>Sources:</span> {citations}</div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Services-Producing: same structure, data-group="services" -->
</div>
```

### CSS — View Toggle

```css
.controls-row {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 24px;
}

.view-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.toggle-btn {
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
  background: var(--surface);
  color: var(--text-muted);
  border-right: 1px solid var(--border);
}

.toggle-btn:last-child { border-right: none; }
.toggle-btn:hover { background: var(--accent-light); color: var(--accent); }
.toggle-btn.active { background: var(--accent); color: #fff; }
```

### CSS — Subsection Divider

```css
.subsection-divider {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 20px 0 12px;
  border-bottom: 1px solid var(--border-light);
  margin-bottom: 0;
}
```

### CSS — Sector Table

```css
.sector-table-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 24px;
}

.sector-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.sector-table thead th {
  background: var(--accent);
  color: #fff;
  padding: 11px 16px;
  text-align: left;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

/* Right-align numeric columns (all except first) */
.sector-table thead th:nth-child(n+2) { text-align: right; }
```

### CSS — Data Row

```css
.sector-row {
  cursor: pointer;
  transition: background 0.1s;
}

.sector-row:hover { background: var(--accent-light); }

.sector-row td {
  padding: 13px 16px;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}

.sector-row td:nth-child(n+2) { text-align: right; }

.tbl-name { font-weight: 600; color: var(--text); }
.tbl-gdp { font-weight: 700; font-variant-numeric: tabular-nums; }
.tbl-projects { font-variant-numeric: tabular-nums; font-weight: 600; }
.tbl-value { font-variant-numeric: tabular-nums; color: var(--text-muted); font-size: 13px; }

.chg-up { color: var(--green); font-weight: 600; }
.chg-down { color: var(--red); font-weight: 600; }
.chg-flat { color: var(--grey); }
```

### CSS — Chevron

```css
.row-chevron {
  display: inline-block;
  width: 16px;
  height: 16px;
  text-align: center;
  font-size: 10px;
  color: var(--text-muted);
  transition: transform 0.2s;
  margin-right: 6px;
  vertical-align: middle;
}

.sector-row.expanded .row-chevron {
  transform: rotate(90deg);
}
```

### CSS — Expandable Content

```css
.expand-row { display: none; }
.expand-row.visible { display: table-row; }

.expand-row td {
  padding: 0;
  border-bottom: 1px solid var(--border-light);
}

.expand-content {
  padding: 18px 24px 20px 24px;
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
  background: #fafbfc;
  border-top: 1px dashed var(--border-light);
}

.expand-content .lead-sentence {
  font-weight: 600;
  color: var(--text);
}

.expand-metrics {
  display: flex;
  gap: 20px;
  margin-bottom: 10px;
  font-family: 'Inter', sans-serif;
  font-size: 12px;
}

.expand-metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.expand-metric-label {
  font-size: 9px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.expand-metric-value {
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text);
}
```

### CSS — Source Citations

```css
.sources {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.6;
}

.sources span {
  font-weight: 600;
  color: var(--text-secondary);
}

.sources a {
  color: var(--accent);
  text-decoration: none;
}

.sources a:hover { text-decoration: underline; }
```

---

## 5. Expand/Collapse JavaScript

```javascript
function toggleRow(row) {
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

### View Toggle JavaScript

```javascript
function initViewToggle() {
  var buttons = document.querySelectorAll('.view-toggle .toggle-btn');
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener('click', function() {
      // Update active button
      for (var j = 0; j < buttons.length; j++) {
        buttons[j].classList.remove('active');
      }
      this.classList.add('active');

      var filter = this.getAttribute('data-filter');
      var goodsEls = document.querySelectorAll('[data-group="goods"]');
      var servicesEls = document.querySelectorAll('[data-group="services"]');

      for (var g = 0; g < goodsEls.length; g++) {
        goodsEls[g].style.display = (filter === 'services') ? 'none' : '';
      }
      for (var s = 0; s < servicesEls.length; s++) {
        servicesEls[s].style.display = (filter === 'goods') ? 'none' : '';
      }
    });
  }
}
```

---

## 6. Rendering Architecture

The Industries tab rendering function replaces the current `renderIndustries()` / `renderIndustrySectors()` in `app.js`.

### Main Render Function

```javascript
function renderIndustries(briefing) {
  var container = document.getElementById('industries-page');
  if (!container) return;

  var goodsArr = (briefing && briefing.goodsIndustries) || [];
  var servicesArr = (briefing && briefing.servicesIndustries) || [];
  var allSectors = goodsArr.concat(servicesArr);

  // Section 1: Overview
  var overviewHtml = buildOverviewSection(briefing, allSectors);

  // Section 2: Biggest Movers
  var movers = selectMovers(goodsArr, servicesArr);
  var moversHtml = buildMoversSection(movers);

  // Section 3: All Sectors table
  var tableHtml = buildAllSectorsSection(goodsArr, servicesArr);

  container.innerHTML = overviewHtml + moversHtml + tableHtml;

  // Initialize toggle after DOM is built
  initViewToggle();
}
```

### Project Count Helpers

Project counts and pipeline values come from the project database, not the briefing JSON. These must be precomputed during export or fetched from a summary endpoint.

```javascript
// Precomputed in export_dashboard.py and included in briefing JSON
// as sectorProjectCounts: { "21": { count: 94, value: 62000000000 }, ... }
function getProjectCount(sectorCode, projectCounts) {
  var entry = projectCounts[sectorCode];
  return entry ? entry.count : 0;
}

function getProjectValue(sectorCode, projectCounts) {
  var entry = projectCounts[sectorCode];
  return entry ? formatCurrency(entry.value) : '$0';
}
```

### NAICS Code to Sector Mapping

The frontend needs a mapping from NAICS codes to the project database's sector taxonomy (18 sectors in CLAUDE.md). Not all NAICS codes map 1:1 to project sectors.

```javascript
var NAICS_TO_PROJECT_SECTOR = {
  '11': ['agriculture', 'forestry'],
  '21': ['oil_gas', 'mining'],
  '22': ['power_energy'],
  '23': ['infrastructure'],
  '31-33': ['manufacturing'],
  '41': ['commercial_mixed'],
  '44-45': ['commercial_mixed'],
  '48-49': ['transport_logistics'],
  '51': ['telecom', 'tourism_culture'],
  '52': ['commercial_mixed'],
  '53': ['residential', 'commercial_mixed'],
  '54': ['commercial_mixed'],
  '55': ['commercial_mixed'],
  '56': ['commercial_mixed'],
  '61': ['education'],
  '62': ['healthcare'],
  '71': ['tourism_culture'],
  '72': ['tourism_culture', 'commercial_mixed'],
  '81': ['commercial_mixed'],
  '91': ['government', 'defence']
};
```

---

## 7. Data Pipeline Integration

### Pipeline Output (writing_agents.py)

The writing agents produce three industry-related fields in the briefing JSON:

| Field | Type | Content |
|-------|------|---------|
| `industry_executive_summary` | string (HTML) | 2-3 paragraphs, 120-200 words. Biggest sectoral story + 2-3 notable movements. Citations as `<sup>N</sup>`. |
| `goodsIndustries` | array (5 objects) | One object per goods-producing NAICS sector |
| `servicesIndustries` | array (15 objects) | One object per services-producing NAICS sector |

### Sector Object Schema

```json
{
  "code": "21",
  "name": "Mining & Energy",
  "mm": "-1.2%",
  "yy": "-3.4%",
  "analysis": "<ul class=\"list-disc...\"><li>GDP declined 1.2%...<sup>1</sup></li></ul>",
  "industrySources": [
    {
      "id": 1,
      "title": "Statistics Canada — GDP by Industry, January 2026",
      "url": "https://www150.statcan.gc.ca/..."
    }
  ],
  "isNegative": true,
  "subsectors": [
    { "code": "211", "name": "Oil & Gas Extraction", "mm": "-1.8%" },
    { "code": "212", "name": "Mining", "mm": "-0.4%" }
  ],
  "indicatorSrc": "StatCan"
}
```

### Required Pipeline Changes

**1. Add `sectorProjectCounts` to briefing export**

In `export_dashboard.py`, after assembling the briefing payload, add a sector project summary:

```python
def compute_sector_project_counts(db):
    """Count active projects and sum values by NAICS-aligned sector."""
    query = """
        SELECT sector, COUNT(*) as count, COALESCE(SUM(value), 0) as total_value
        FROM projects
        WHERE status NOT IN ('Cancelled', 'Complete')
        GROUP BY sector
    """
    rows = db.execute(query).fetchall()
    return {row['sector']: {'count': row['count'], 'value': row['total_value']} for row in rows}
```

**2. Convert analysis HTML to narrative prose**

The pipeline currently outputs `<ul><li>` bullet HTML. The new design requires em dash narrative prose. This conversion can happen either in the writing agent prompt (preferred — instruct agent to output narrative) or in the frontend (see Section 3 conversion function above).

Recommended approach: update the writing agent prompt in `writing_agents.py` `_build_sector_prompt()` to request narrative prose instead of bullet HTML:

```
Output format for analysis: Write 2-3 sentences in narrative prose.
The first sentence should be a bold factual lead (wrapped in no HTML).
Subsequent sentences provide supporting data points, each carrying a specific number.
Do NOT use bullet points or <ul>/<li> tags.
```

**3. Add supplementary metrics for expand rows**

Each expanded row shows 2-3 contextual metrics (status changes, new this week, sector-specific indicators). These should be included in the sector object:

```json
{
  "expandMetrics": [
    { "label": "Status Changes", "value": "3" },
    { "label": "New This Week", "value": "1" },
    { "label": "WTI Average", "value": "$68" }
  ]
}
```

Add these in the writing agent prompt or compute them from the project database during export.

### Signal Context Integration

The writing agent receives sector-level signals (from `analysis.py` `_build_signal_context_blocks()`):

| Signal Type | Data Source | How It Feeds Analysis |
|-------------|------------|----------------------|
| Policy items | `policy_snapshots` table, filtered by sector | Mentioned in narrative when a policy affects the sector |
| Hiring spikes | `job_snapshots` table, filtered by sector | Percentage change in postings for relevant CMAs |
| Procurement awards | `procurement_snapshots` table, filtered by sector | Government contract awards linked to sector |
| IAAC status changes | IAAC tracker, filtered by sector | Environmental assessment milestones for sector projects |

These signals are formatted as text blocks in the writing agent prompt. The agent weaves them into the analysis narrative.

---

## 8. Source Citations

Every narrative — both mover cards and expanded table rows — must include a sources line.

### Source Rendering

```javascript
function renderSources(industrySources) {
  if (!industrySources || industrySources.length === 0) return '';

  var labels = [];
  for (var i = 0; i < industrySources.length; i++) {
    var src = industrySources[i];
    if (src.url) {
      labels.push('<a href="' + src.url + '" target="_blank">' + src.title + '</a>');
    } else {
      labels.push(src.title);
    }
  }

  return '<div class="sources"><span>Sources:</span> ' + labels.join(' · ') + '</div>';
}
```

### Standard Source Labels

Sources should use short recognizable labels:

| Data | Label |
|------|-------|
| GDP by industry | StatCan Table 36-10-0434 |
| Building permits | StatCan Table 34-10-0066 |
| Labour force | StatCan Table 14-10-0287 |
| Merchandise exports | StatCan Table 12-10-0129 |
| Retail trade | StatCan Table 20-10-0008 |
| Oil prices | NYMEX WTI |
| Natural gas | AECO NGX |
| Gold | LBMA Gold |
| Lumber | Random Lengths |
| Canola | ICE Canola Futures |
| Project data | Project Database |
| Job postings | Job Monitor (Indeed/Job Bank) |
| Procurement | Open Canada Procurement |
| Policy items | Policy Tracker |
| Telecom data | CRTC Telecom Monitoring |

---

## 9. Export Integration

### Files Written by export_dashboard.py

The briefing export writes to `docs/data/briefing_latest.json`. The Industries tab reads from this file. The following fields must be present:

```json
{
  "industry_executive_summary": "...",
  "goodsIndustries": [ ... ],
  "servicesIndustries": [ ... ],
  "sectorProjectCounts": {
    "oil_gas": { "count": 52, "value": 48000000000 },
    "mining": { "count": 42, "value": 14000000000 },
    ...
  }
}
```

### Validation Checklist

The export should validate:
- `goodsIndustries` has exactly 5 entries
- `servicesIndustries` has exactly 15 entries
- Each entry has `code`, `name`, `analysis`, `industrySources`
- `industrySources` array is non-empty for each sector
- `mm` and `yy` fields are present (can be empty strings for services if StatCan data unavailable)
- `sectorProjectCounts` has entries for all 18 project sectors

---

## 10. Responsive Behavior

### Breakpoints

```
>= 1200px: Full layout, all columns visible

<= 1199px:
  .page padding → 24px horizontal
  Table font size → 13px
  Mover metrics gap → 16px

<= 899px:
  .page padding → 20px 16px
  Hide GDP column in table (keep M/M, Y/Y, Projects, Value)
  Mover metrics → wrap to 2 rows

<= 599px:
  .page padding → 16px 12px
  Table → horizontal scroll
  Mover cards → reduce padding to 16px
  View toggle → full width, smaller buttons
```

### Mobile Table Adjustment

On narrow screens, the table should scroll horizontally rather than wrapping:

```css
@media (max-width: 599px) {
  .sector-table-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .sector-table {
    min-width: 600px;
  }
}
```

---

## 11. Sector Display Names

Use full official NAICS names in the table. No abbreviations.

| Code | Display Name |
|------|-------------|
| 11 | Agriculture, Forestry, Fishing and Hunting |
| 21 | Mining, Quarrying, and Oil and Gas |
| 22 | Utilities |
| 23 | Construction |
| 31-33 | Manufacturing |
| 41 | Wholesale Trade |
| 44-45 | Retail Trade |
| 48-49 | Transportation and Warehousing |
| 51 | Information and Cultural Industries |
| 52 | Finance and Insurance |
| 53 | Real Estate and Rental and Leasing |
| 54 | Professional, Scientific and Technical Services |
| 55 | Management of Companies and Enterprises |
| 56 | Administrative and Support Services |
| 61 | Educational Services |
| 62 | Health Care and Social Assistance |
| 71 | Arts, Entertainment and Recreation |
| 72 | Accommodation and Food Services |
| 81 | Other Services |
| 91 | Public Administration |

### Sort Order

Within each group (goods/services), sectors are sorted by GDP descending. The pipeline's `mm` values from StatCan determine ordering when GDP values are equal.

---

## 12. Implementation Checklist

### CSS (add to app.css or inline in index.html)
- [ ] `.mover-card`, `.mover-card-header`, `.mover-title`, `.mover-direction` (`.up`, `.down`)
- [ ] `.mover-metrics`, `.mover-metric`, `.mover-metric-label`, `.mover-metric-value`
- [ ] `.mover-analysis`, `.mover-analysis .lead-sentence`
- [ ] `.controls-row`, `.view-toggle`, `.toggle-btn` (`.active`, `:hover`)
- [ ] `.subsection-divider`
- [ ] `.sector-table-wrap`, `.sector-table`, `thead th`, `tbody td`
- [ ] `.sector-row`, `.sector-row:hover`, `.sector-row.expanded`
- [ ] `.row-chevron`, `.sector-row.expanded .row-chevron`
- [ ] `.expand-row`, `.expand-row.visible`, `.expand-content`
- [ ] `.expand-metrics`, `.expand-metric`, `.expand-metric-label`, `.expand-metric-value`
- [ ] `.tbl-name`, `.tbl-gdp`, `.tbl-projects`, `.tbl-value`
- [ ] `.chg-up`, `.chg-down`, `.chg-flat`
- [ ] `.sources`, `.sources span`, `.sources a`
- [ ] Responsive breakpoints (1199, 899, 599)

### JavaScript (add to app.js)
- [ ] `renderIndustries(briefing)` — main render function replacing current implementation
- [ ] `selectMovers(goodsArr, servicesArr)` — pick top 2 gainers + 2 decliners
- [ ] `buildOverviewSection(briefing, allSectors)` — overview narrative with callout
- [ ] `buildMoversSection(movers)` — render 4 mover cards
- [ ] `buildAllSectorsSection(goodsArr, servicesArr)` — build expandable table
- [ ] `toggleRow(row)` — expand/collapse handler
- [ ] `initViewToggle()` — filter toggle handler
- [ ] `convertAnalysisToNarrative(html)` — convert `<ul><li>` to em dash prose
- [ ] `renderSources(industrySources)` — build source citation line

### Pipeline (phases/ and tools/)
- [ ] Update `_build_sector_prompt()` in `writing_agents.py` to request narrative prose output
- [ ] Add `expandMetrics` to sector object in writing agent prompt
- [ ] Add `compute_sector_project_counts()` to `export_dashboard.py`
- [ ] Include `sectorProjectCounts` in `briefing_latest.json` export
- [ ] Validate all 20 sectors present with sources in export validation

### Testing
- [ ] Verify all 20 sectors render with write-ups
- [ ] Verify expand/collapse works for each row
- [ ] Verify view toggle filters goods/services correctly
- [ ] Verify mover selection picks correct 4 sectors
- [ ] Verify source citations render for all cards and expanded rows
- [ ] Test with missing `mm`/`yy` data (services sectors often have empty strings)
- [ ] Test responsive breakpoints at 1199, 899, 599px
- [ ] Verify GDP sort order within each group
