# TL;DR Tab — Complete JSON Specification

> Reference document for building a Claude cowork agent that can replace the TL;DR tab generation pipeline.

---

## Overview

The TL;DR tab is the first tab of "The Lagging Indicator" dashboard. It displays a weekly intelligence briefing covering Canadian national economic conditions, provincial policy, capital projects, markets, and events. The tab is fed primarily by a single JSON file (`briefing_latest.json`) with supplementary data from `indicators.json` and other supporting files.

---

## 1. Primary Data File: `briefing_latest.json`

**Location:** `docs/data/briefing_latest.json` (GitHub Pages served) and `public/data/briefing_latest.json` (build output)

**Loaded by:** `loadNewsletter()` in `docs/js/app.js` — populates the global `D` object:
```javascript
async function loadNewsletter(editionId){
  try { D = await fetchJSON('briefing_latest.json') }
  catch(e) { console.error('Newsletter load:', e) }
}
```

### Complete Field Schema

```jsonc
{
  // ─── HEADER & IDENTITY ───
  "headline": "string",
  // Single most significant factual development of the week.
  // If missing or starts with a date/code pattern, the frontend falls back
  // to the first sentence of executive_summary.
  // Example: "BoC holds at 2.75% as Q1 GDP contracts 0.6%"

  "edition": "string",
  // Format: "EDITION: Mon DD – Mon DD // STATUS: AI-SYNTHESIZED"
  // Example: "EDITION: Mar 19 – Mar 26 // STATUS: AI-SYNTHESIZED"

  "week_of": "string (ISO date)",
  // The Monday of the briefing week. Example: "2026-03-25"

  "generated_at": "string (ISO datetime)",
  // When the pipeline produced this payload. Example: "2026-03-25T13:18:39Z"

  "updated_at": "string (ISO date)",
  // Last update date. Example: "2026-03-25"


  // ─── LEAD IMAGE ───
  "unsplash_image_url": "string (URL)",
  // Curated Unsplash image selected by keyword match on the headline.
  // Used as a float image in the executive summary section.
  // Example: "https://images.unsplash.com/photo-..."


  // ─── EXECUTIVE SUMMARY ───
  "executive_summary": "string (HTML)",
  // The main narrative for the TL;DR tab. Multiple <p> tags with
  // <sup>N</sup> footnote references that link to the sources[] array.
  // Typically 3-5 paragraphs. Written by Claude Opus.
  // Example: "<p>The Bank of Canada held its policy rate at 2.75%<sup>1</sup>...</p>"


  // ─── KEY INDICATORS PANEL ───
  "key_indicators": [
    {
      "label": "string",
      // Display name. Examples: "BOC RATE", "REAL GDP", "CPI", "UNEMPLOYMENT",
      // "HOUSING STARTS", "WTI CRUDE", "CAD/USD", "TSX"
      "value": "string",
      // Current value with formatting. Examples: "2.75%", "-0.6% QoQ ann.", "+1.8% YoY"
      "change": "string"
      // Period-over-period change. Can be empty string. Examples: "", "+7.3% YoY", "-25bps"
    }
    // Typically 7-10 items
  ],


  // ─── NATIONAL METRICS (HARD DATA — NEVER AI-GENERATED) ───
  "metrics": {
    "realGdp": "string",       // Example: "-0.6%"
    "nomGdp": "string",        // Nominal GDP. Often ""
    "outputGap": "string",     // Often ""
    "cpi": "string",           // Example: "+1.8%"
    "shelterCpi": "string",    // Shelter component. Often ""
    "bocRate": "string",       // Example: "2.75%"
    "unemployment": "string",  // Example: "6.7%"
    "participation": "string", // Labour force participation. Often ""
    "wageGrowth": "string",    // Often ""
    "currentAccount": "string",// Often ""
    "agCrop": "string",        // Agricultural crop indicator. Often ""
    "farmCash": "string",      // Farm cash receipts. Often ""
    "housingStarts": "number or string" // Example: 229300 or "229.3K"
  },

  // ─── INDICATOR METADATA ───
  "indicatorMeta": {
    // One entry per metric key (bocRate, cpi, unemployment, etc.)
    "bocRate": {
      "change": "string",   // Example: "-25bps" or ""
      "prev": "string",     // Previous value. Example: "3.00%"
      "period": "string",   // Reference period. Example: "2026-03-12"
      "frequency": "string" // Example: "8 times/year"
    },
    "cpi": {
      "change": "string",
      "prev": "string",
      "period": "string",
      "frequency": "string"  // Example: "monthly"
    }
    // ... one per metric
  },

  // ─── INDICATOR SOURCES ───
  "indicatorSources": {
    // Which API/institution provided each metric value
    "bocRate": "Bank of Canada",
    "cpi": "Statistics Canada",
    "unemployment": "Statistics Canada",
    "housingStarts": "CMHC",
    "realGdp": "Statistics Canada"
    // ... one per metric
  },

  // ─── INDICATOR CONTEXT LINES ───
  "indicatorContextLines": {
    // Plain-English one-liner explaining each metric in context
    "bocRate": "Policy rate at 2.25% as two Governing Council deputies announced departures.",
    "cpi": "Inflation at +1.8% YoY sits comfortably inside the BoC's 1-3% band.",
    "unemployment": "Unemployment at 6.7% while EI beneficiaries fell 1.9% in January."
    // ... one per metric
  },


  // ─── NATIONAL ANALYSIS ───
  "national": {
    "analysis": "string (HTML)",
    // Detailed national macroeconomic analysis with <sup>N</sup> citations.
    // Written by Claude Opus Call 1.
    "sources": [
      {
        "id": 1,           // Integer, matches <sup> references
        "title": "string", // Source description
        "url": "string"    // Source URL
      }
    ]
  },


  // ─── GLOBAL ECONOMIC CONTEXT ───
  "global": [
    {
      "region": "string",  // "United States", "China", "European Union", "United Kingdom"
      "emoji": "string",   // Flag emoji
      "indicators": {
        "gdp": "string",            // Example: "+0.7%"
        "cpi": "string",            // Example: "+2.7%"
        "rate": "string",           // Central bank rate. Example: "3.64%"
        "unemployment": "string",   // Example: "4.4%"
        "tradeBalance": "string",   // Often ""
        "productivityGrowth": "string" // Often ""
      },
      "indicatorMeta": {
        "gdp": { "change": "string", "prev": "string" },
        "cpi": { "change": "string", "prev": "string" }
        // ... per indicator
      },
      "indicatorSources": {
        "gdp": "FRED/BEA",
        "cpi": "FRED/BLS"
        // ... per indicator
      },
      "analysis": "string (HTML)",
      // Regional analysis with <sup> citations
      "sources": [
        { "id": 1, "title": "string", "url": "string" }
      ]
    }
    // 4 regions: US, China, EU, UK
  ],

  // ─── GLOBAL ECONOMIC VECTORS ───
  "globalVectors": {
    "us": "string",    // 1-2 sentence summary of US impact on Canada
    "china": "string", // 1-2 sentence summary of China impact
    "eu": "string"     // 1-2 sentence summary of EU impact
  },


  // ─── INDUSTRY ANALYSIS ───
  "industry_executive_summary": "string (HTML)",
  // High-level industry overview paragraph(s). Written by Claude Opus Call 2.

  "goodsIndustries": [
    {
      "code": "string",    // NAICS 2-digit code. Example: "11"
      "name": "string",    // Example: "Agriculture"
      "mm": "string",      // Month-over-month change. Example: "-0.8%"
      "yy": "string",      // Year-over-year change. Example: "+7.6%"
      "analysis": "string (HTML)", // Sector-specific analysis with bullet points
      "industrySources": [
        { "id": 1, "title": "string", "url": "string" }
      ],
      "isNegative": true,  // Boolean flag for styling
      "subsectors": [
        {
          "code": "string", // NAICS 3-digit. Example: "111"
          "name": "string", // Example: "Crop Production"
          "mm": "string"    // Example: "N/A" or "-1.2%"
        }
      ],
      "indicatorSrc": "string" // Example: "StatCan"
    }
    // Goods: NAICS 11 (Agriculture), 21 (Mining/Oil/Gas), 22 (Utilities), 23 (Construction), 31-33 (Manufacturing)
  ],

  "servicesIndustries": [
    // Same structure as goodsIndustries
    // Services: NAICS 41 (Wholesale), 44-45 (Retail), 48-49 (Transport), 51 (Information),
    // 52 (Finance/Insurance), 53 (Real Estate), 54 (Professional Services),
    // 55 (Management), 56 (Admin), 61 (Education), 62 (Healthcare),
    // 71 (Arts/Entertainment), 72 (Accommodation/Food), 81 (Other Services), 91 (Public Admin)
  ],


  // ─── FINANCIAL MARKETS ───
  "financialMarkets": {
    "indices": [
      {
        "name": "string",    // Example: "S&P/TSX"
        "value": "string",   // Example: "24,521.73"
        "region": "string",  // Example: "Canada"
        "change": "string",  // Weekly change. Example: "-2.3%"
        "day": "string",     // Daily change. Example: "+0.4%"
        "yy": "string"       // Year-over-year. Example: "+8.1%"
      }
      // TSX, S&P 500, Dow, NASDAQ, FTSE, DAX, Nikkei, etc.
    ],
    "fx": [
      {
        "name": "string",  // Example: "CAD/USD"
        "value": "string", // Example: "0.73"
        "day": "string",   // Daily change
        "yy": "string"     // Year-over-year change
      }
      // CAD/USD, EUR/USD, GBP/USD, USD/CNY, USD/JPY
    ]
  },

  "commodities": [
    {
      "category": "string", // "Energy", "Metals", "Agriculture"
      "items": [
        {
          "name": "string",  // Example: "Crude Oil (WTI)"
          "val": "string",   // Current price. Example: "87.84"
          "unit": "string",  // Example: "bbl", "oz", "lb", "bu"
          "yy": "string",    // Year-over-year change
          "day": "string"    // Daily change
        }
      ]
    }
  ],

  "yieldCurve": [
    {
      "term": "string",   // "2Y", "5Y", "10Y"
      "yield": "string"   // Example: "3.42%"
    }
  ],


  // ─── CONSUMER PULSE ───
  "consumer_pulse": "string (HTML)",
  // Consumer sentiment analysis drawn from Reddit (r/PersonalFinanceCanada),
  // Google Trends, and news sentiment. Written by Claude Opus.


  // ─── WORD CLOUD ───
  "word_cloud_topics": [
    {
      "topic": "string",           // Example: "GDP contraction"
      "sentiment_score": -0.8,     // Float from -1.0 (negative) to +1.0 (positive)
      "frequency": 10              // Integer, occurrence count
    }
    // Typically 40+ topics. Used to render a D3 word cloud in the Consumer Pulse section.
    // Sentiment determines color (blue shades), frequency determines font size.
  ],


  // ─── UPCOMING EVENTS WATCHLIST ───
  "watchlist": [
    {
      "date": "string",         // Example: "Mar 27"
      "week_label": "string",   // "This Week", "Next Week", "Week 3", "Week 4"
      "institution": "string",  // Example: "Statistics Canada", "Bank of Canada"
      "event_name": "string",   // Example: "Monthly GDP by Industry, January 2026"
      "description": "string",  // 1-2 sentence factual description of event significance
      "impact": "string",       // "high", "medium", "low"
      "source_url": "string"    // URL to official source
    }
    // Typically 18-20 events over a 30-day forward window
  ],


  // ─── DISCOVERY STATS (PROJECT DATABASE SUMMARY) ───
  "discovery_stats": {
    "total_projects": "number or string",       // Example: 847
    "new_this_week": "number or string",         // Example: 23
    "total_value_billions": "number or string"   // Example: "412.3"
  },
  // Fallback fields if discovery_stats is absent:
  "project_count": "number or string",
  "new_projects": "number or string",
  "pipeline_value": "number or string",


  // ─── SOURCES (FOOTNOTE CITATIONS) ───
  "sources": [
    {
      "id": 1,               // Integer matching <sup>1</sup> in HTML
      "title": "string",     // Source description
      "url": "string",       // Primary URL
      "archive_url": "string" // Wayback Machine archive URL (optional)
    }
    // All sources cited in executive_summary, national.analysis, industry analyses, etc.
    // Footnotes in HTML use <sup>N</sup> which link to these by id.
  ]
}
```

---

## 2. Secondary Data File: `indicators.json`

**Location:** `docs/data/indicators.json`
**Loaded by:** `loadIndicators()` in app.js

Used by the TL;DR tab for:
- **Interactive Canada Map** (D3 choropleth colored by provincial GDP growth)
- **Province hover tooltips** (GDP, unemployment, CPI, housing starts, participation, employment rate, wage growth)
- **National stats panel** (toggleable table view)

### Schema

```jsonc
{
  "indicators": [
    {
      "id": "number",
      "indicator_name": "string",  // e.g. "unemployment", "cpi", "gdp_growth", "housing_starts"
      "category": "string",        // e.g. "Labour", "Prices", "Output", "Housing", "Trade"
      "province": "string",        // "National", "ON", "QC", "AB", "BC", etc.
      "value": "number",           // e.g. 6.7
      "period": "string",          // ISO date. e.g. "2026-02-01"
      "previous_value": "number or null",
      "change": "number or null",
      "source": "string",          // e.g. "Statistics Canada WDS", "Bank of Canada"
      "fetched_at": "string",      // ISO datetime
      "unit": "string",            // "%", "$M", "K units", etc.
      "frequency": "string",       // "monthly", "quarterly", "8 times/year"
      "description": "string",
      "backfilled": 0,             // 0 or 1
      "metadata": {}               // Additional context (optional)
    }
    // 100+ records per indicator type across provinces
  ],

  "history": [
    {
      "indicator_name": "string",
      "province": "string",
      "period": "string",
      "value": "number",
      "unit": "string",
      "source": "string"
    }
    // 5 years of historical data for time series charts
  ],

  "statcan_latest": {
    // Snapshot of latest StatCan data fetch metadata
  }
}
```

### How the Map Uses Indicator Data

The function `getProvIndicators()` builds a per-province data object:

```javascript
// For each province (ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU):
{
  "gdp": "+2.1%",
  "gdp_period": "2025-Q4",
  "unemployment": "5.8%",
  "unemployment_period": "2026-02",
  "cpi": "+2.3%",
  "cpi_period": "2026-02",
  "housingStarts": "45,200",
  "housingStarts_period": "2026-02",
  "participationRate": "65.2%",
  "employmentRate": "61.4%",
  "wageGrowth": "+3.1%"
}
```

---

## 3. Other Supporting JSON Files

| File | Purpose in TL;DR | Key Fields |
|------|-------------------|------------|
| `commodities.json` | Commodity prices for Financial Markets section | `indicators.Energy[]`, `indicators.Metals[]`, `indicators.Agriculture[]` |
| `projects_all.json` | Project count, pipeline value for header stats | Array of project objects with `value`, `status`, `province`, `sector` |
| `policy.json` | Policy developments referenced in briefing | Array of policy items with `title`, `province`, `sector`, `date` |
| `events.json` | Upcoming economic events for watchlist | Array of events with `date`, `title`, `institution`, `impact` |
| `microscope.json` | "Under the Microscope" history sidebar | Array of past deep-dive topics with `title`, `date`, `summary` |
| `canada-provinces.topo.json` | TopoJSON geometry for interactive map | Standard TopoJSON with province boundaries |
| `timeseries.json` | Historical time series for sparklines | Per-indicator arrays of `{period, value}` |

---

## 4. Backend Generation Pipeline

### Data Flow

```
API Sources (StatCan, BoC, Yahoo Finance, FRED, ECB, BoE, BLS)
    |
    v
Phase 1: Data Collection (phases/data_collection.py)
    |  Fetches hard data: metrics, indicators, market prices
    |  Stores in context['hard_data'], context['statcan_inds'], etc.
    v
Phase 2-4: Discovery & Enrichment
    |  Google News RSS, RSS feeds, IAAC, provincial registries, etc.
    |  Builds project database, policy tracker, event calendar
    v
Phase 5: Analysis (phases/analysis.py)
    |  Claude Opus Call 1: Macro pulse (national + policy + hiring + procurement + IAAC)
    |  Claude Opus Call 2: Industry analysis (per-sector signals)
    |  Claude Opus Call 3: Provincial spotlight (per-province signals)
    |  Claude Opus Call 4: Global economy (US, China, EU, UK)
    |  Hard data override: replaces AI estimates with API values
    |  Output: final_payload dict
    v
Phase 7: Narrative (phases/narrative.py)
    |  Claude Sonnet: Weekly briefing synthesis (8 sections, 1100-1600 words)
    |  Input: sector_data, indicator_trends, cross_reference, signal_context
    |  Stores to SQLite weekly_briefings table
    v
Phase 9: Finalize (phases/finalize.py)
    |  Merges final_payload with briefing data
    |  Adds unsplash_image_url
    |  Citation audit (removes broken URLs)
    |  Saves to SQLite dashboard_state table
    v
Export (tools/export_dashboard.py)
    |  Reads dashboard_state['newsletter_latest'] from SQLite
    |  Merges market data from indicator_history if needed
    |  Writes briefing_latest.json to docs/data/
    v
Frontend (docs/js/app.js)
    |  loadNewsletter() -> D = fetchJSON('briefing_latest.json')
    |  renderTLDR() -> renderEditorialFlow()
    v
TL;DR Tab Display
```

### Key Backend Files

| File | Role |
|------|------|
| `update_dashboard.py` | Entry point orchestrator (9 phases) |
| `phases/data_collection.py` | Phase 1: API data fetching |
| `phases/analysis.py` | Phase 5: Claude Opus analysis (Calls 1-4) + hard data override |
| `phases/narrative.py` | Phase 7: Claude Sonnet briefing synthesis |
| `phases/finalize.py` | Phase 9: Merge, image, citations, save to SQLite |
| `tools/export_dashboard.py` | Export SQLite -> JSON files for GitHub Pages |
| `weekly_briefing.py` | Briefing generation logic |
| `claude_reasoning.py` | Claude API wrapper (Opus + Sonnet) |
| `canadian_markets.py` | Yahoo Finance market data |
| `indicator_trends.py` | Indicator trend analysis |
| `cross_reference.py` | Cross-reference engine (links indicators to projects) |
| `tools/unsplash_image.py` | Lead image selection |
| `db.py` | SQLite interface |

---

## 5. Frontend Rendering: What the TL;DR Tab Displays

### Section Layout (top to bottom)

1. **Header**
   - Eyebrow: "Weekly Intelligence Briefing"
   - Headline: from `D.headline` (fallback: first sentence of `D.executive_summary`)
   - Accent rule
   - Meta stats: Projects Tracked / New This Week / Pipeline Value (from `D.discovery_stats`)

2. **Interactive Canada Map** (floated)
   - D3 choropleth colored by provincial GDP growth
   - Hover tooltips: GDP, unemployment, CPI, participation, employment rate, housing starts
   - Toggle: "Key Indicators" table vs "This Week" stat boxes
   - Data from: `indicators.json` via `getProvIndicators()` + `D.metrics` + `D.key_indicators`

3. **Executive Summary**
   - Lead image: `D.unsplash_image_url` (floated right)
   - HTML content: `D.executive_summary` with `<sup>` footnotes
   - Footnotes resolve to `D.sources[]` by id

4. **Industry Overview**
   - Section title + subtitle (extracted from `D.industry_executive_summary`)
   - HTML body from `D.industry_executive_summary`
   - Embedded "Capital by Sector" bar chart (from project database aggregation)

5. **Financial Markets**
   - Indices grid: `D.financialMarkets.indices[]` (name, value, change)
   - FX grid: `D.financialMarkets.fx[]` (name, value, change)
   - Commodity Movers bar chart (biggest weekly price changes)
   - Data from `D.financialMarkets` + `D.commodities`

6. **Consumer Pulse**
   - Word cloud (floated right): `D.word_cloud_topics[]` rendered as D3 word cloud
     - Size = frequency, color = blues palette
   - HTML body: `D.consumer_pulse`

7. **Sources Footer**
   - Numbered list from `D.sources[]` with clickable links
   - Archive URLs shown as fallback links

8. **Microscope History Sidebar** (right rail)
   - Past "Under the Microscope" deep-dives from `microscope.json`

---

## 6. Claude Analysis Prompts (What the AI Generates)

### Call 1: Macro Pulse (Claude Opus)
**Input context:** Hard data (metrics), policy summary, top hiring spikes, procurement >= $10M, IAAC changes, extended StatCan summary
**Output fields:** `executive_summary`, `headline`, `key_indicators`, `metrics` (overridden by hard data), `indicatorMeta`, `indicatorContextLines`

### Call 2: Industry Analysis (Claude Opus)
**Input context:** Per-sector signals (policy items, hiring spikes, procurement awards), StatCan industry GDP data
**Output fields:** `industry_executive_summary`, `goodsIndustries[]`, `servicesIndustries[]`

### Call 3: Provincial Spotlight (Claude Opus)
**Input context:** Per-province signals (policy items, hiring spikes, procurement awards, IAAC changes)
**Output fields:** Provincial analysis (used in National tab, not directly in TL;DR)

### Call 4: Global Economy (Claude Opus)
**Input context:** FRED, ECB, BoE, BLS data + Yahoo Finance FX/equity
**Output fields:** `global[]` (4 regions), `globalVectors`

### Narrative Synthesis (Claude Sonnet)
**Input context:** sector_data, indicator_trends, cross_reference data, signal_context (policy, hiring, procurement, IAAC)
**Output:** 8-section briefing merged into final_payload

---

## 7. Editorial Rules (MUST be encoded in any replacement agent)

1. **REPORTING ONLY** — No editorializing, no opinions, no recommendations
2. **Every claim must cite a source** — `<sup>N</sup>` references linking to `sources[]`
3. **Hard data overrides AI** — API values always replace Claude's estimates for metrics
4. **No fabrication** — All data must come from real API responses or verified sources
5. **Conditional language for projections** — "If rates hold, 23 projects would see..." not "23 projects will benefit"
6. **Attribution over assertion** — "The cross-reference engine links X to Y" not "X will cause Y"
7. **Banned words:** should, must, hopefully, unfortunately, worrying, promising, encouraging, welcome, bullish, bearish

---

## 8. Model Stack

| Model | Role in TL;DR Pipeline | Cost |
|-------|----------------------|------|
| **Claude Opus 4.6** | All writing: executive_summary, headline, industry analysis, consumer pulse, global analysis | $15/$75 per MTok |
| **Claude Sonnet 4.6** | Extraction, reasoning, briefing synthesis, gap analysis | $3/$15 per MTok |
| **Gemini 2.5 Flash** | Classification, extraction (NO grounding, NO google_search tool) | FREE |
| **Tavily** | Targeted enrichment searches only | FREE (1,000/month) |

**Cost cap:** $8/run. Annual budget: ~$150/year.

---

## 9. SQLite Storage

The final payload is stored in `dashboard.db` table `dashboard_state`:
- Key: `newsletter_latest` — always the most recent briefing
- Key: `newsletter_YYYY-MM-DD` — dated archive entry
- Value: JSON string of the complete briefing payload

The export step (`tools/export_dashboard.py`) reads from SQLite and writes to `docs/data/briefing_latest.json`.

---

## 10. Cowork Agent Requirements Summary

A replacement agent must:

1. **Fetch hard data** from StatCan WDS, Bank of Canada, Yahoo Finance, FRED, ECB, BoE, BLS APIs
2. **Generate editorial content** via Claude Opus following strict editorial policy (no editorializing)
3. **Override AI metrics** with authoritative API values (metrics, indicatorMeta, indicatorSources)
4. **Produce a complete `briefing_latest.json`** matching the schema in Section 1
5. **Produce supporting `indicators.json`** matching the schema in Section 2
6. **Include properly numbered `sources[]`** with real URLs and archive URLs
7. **Generate word cloud topics** with sentiment scores and frequencies
8. **Build a 30-day event watchlist** from known economic calendar
9. **Select a lead image** via Unsplash API
10. **Write output to `docs/data/`** for GitHub Pages serving
11. **Respect cost caps** — $8/run, ~$150/year total
12. **Never use** Gemini grounded search, Perplexity, GDELT, or Haiku in the weekly pipeline
