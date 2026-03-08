# CANADIAN MACRO STRATEGIC DASHBOARD — COMPLETE SYSTEM SPECIFICATION

**Purpose:** This document describes every feature and component the system should have after implementing STEP_2A through STEP_2P. Use this as an audit checklist — verify each item exists and functions correctly. Fix anything missing or broken.

**Annual operating cost:** ~$60/year (Claude Sonnet ~$55, Firebase ~$5, all search free)

---

## 1. DATA COLLECTION INFRASTRUCTURE

### 1.1 Scheduled Execution
- **Weekly pipeline trigger:** Cloud Function running every Monday at 6:00 AM Eastern via `functions/index.js` → `weeklyPipeline`
- **Daily query trigger:** Cloud Function running every day at midnight Eastern via `functions/index.js` → `dailyIndicators`
- **Firebase configuration:** `firebase.json` includes functions section, `functions/` directory contains `index.js` and `package.json`
- Both triggers call `update_dashboard.py` with appropriate flags

### 1.2 Environment Variables
- `GEMINI_API_KEY` — Gemini 2.5 Flash and Pro
- `ANTHROPIC_API_KEY` — Claude Sonnet 4.5
- No Perplexity API key (removed)
- Firebase credentials via service account or default application credentials

---

## 2. PROJECT DISCOVERY PIPELINE

### 2.1 Tier 1: Federal IAAC Registry (Existing)
- Scrapes the Impact Assessment Agency of Canada registry
- Returns structured project records (name, proponent, status, location)
- Projects enter dedup pipeline with `_discovery_tier: "iaac_registry"`

### 2.2 Tier 2: Google News RSS Search (replaces Gemini grounded search)
- **759 compound queries** from `compound_queries_final.json` converted to Google News RSS URLs
- Each query shortened to concise keywords for RSS: "mining project Saskatchewan 2026"
- URL format: `https://news.google.com/rss/search?q=QUERY&hl=en-CA&gl=CA&ceid=CA:en`
- French queries use `hl=fr-CA&gl=CA&ceid=CA:fr`
- Polled via feedparser with 30x parallelism
- Returns ~10-15 articles per feed, deduplicated by URL before processing
- Articles flow through existing 6-layer RSS filter and Gemini Flash classification (no grounding)
- Cost: $0 (Google News RSS is free and unlimited)

### 2.3 Tier 3: RSS Feeds with Remediated Filter
- **201+ RSS feeds** across categories: national news, regional news, government newsrooms, industry trade publications, French media, Google Alerts
- **Industry feeds (15+):** Daily Commercial News, Journal of Commerce, On-Site Magazine, Canadian Architect, ReNew Canada, Canadian Consulting Engineer, Canadian Mining Journal, Northern Miner, Mining.com, JWN Energy, Electric Energy Online, RENX, Storeys, Journal Constructo, Infra Quebec
- **Government feeds (25+):** 13 provincial newsrooms, federal departments (Infrastructure Canada, Transport Canada, CMHC, NRCan, ISED), 6 federal regional development agencies (PrairiesCan, PacifiCan, ACOA, FedNor, CanNor, FedDev Ontario, CED Quebec), 12+ major municipal newsrooms

#### Six-layer filter pipeline:
1. **Government source bypass:** Articles from 50+ government domains skip keyword filtering entirely and go straight to Gemini Flash classification
2. **Dollar-value bypass:** Articles with dollar values ≥ province GDP threshold skip Layers 1-2 and go to Gemini Flash classification
3. **Below-threshold dampener:** Articles with detected dollar values below threshold require strong project signals to proceed
4. **Layer 1 — Expanded keyword co-occurrence:** ~80 project signal keywords (including full brownfield vocabulary: redevelopment, revitalization, conversion, adaptive reuse, retrofit, renovation, modernization, expansion, etc.) + ~30 economic signal keywords. Must have co-occurrence of at least one from each list
5. **Layer 2 — Cleaned negative keywords:** Only true noise (crime, sports, weather, entertainment, obituaries). Does NOT include: mall, shopping, store, housing, residential, apartment, condo, office, heritage, downtown, Indigenous, First Nations, reconciliation
6. **Layer 3 — Gemini Flash classification:** LLM classification with brownfield-aware prompt. Uncertain = RELEVANT (false negatives worse than false positives)

#### GDP-proportional thresholds:
ON $500M, QC $250M, AB $200M, BC $175M, SK $45M, MB $40M, NS $25M, NB $20M, NL $17M, PE $5M, YT/NT/NU $3M

### 2.4 Tier 4: Project Status Monitoring
- Existing project monitoring for tracked projects
- Benefits from expanded brownfield vocabulary

### 2.5 Tier 5: Provincial EA Registries (13)
- Scrapers for all 13 provincial/territorial environmental assessment registries
- BC EAO uses JSON API (best structured source)
- Ontario ERO, Quebec BAPE, Alberta EPEA, and others use HTML scraping
- Projects from EA registries get high confidence (0.8) — government verified
- Evidence URL = the registry page URL (always valid, permanent)

### 2.6 Tier 6: SEDAR+ Securities Filings
- Searches SEDAR+ for recent filings containing capital project disclosures
- NI 43-101 technical reports (mining), material change reports, MD&A sections
- Filing titles often contain project name and location directly
- Evidence URL = SEDAR+ filing page (government-mandated, permanent)

### 2.7 Tier 7: Crown Corporation Capital Plans (25+)
- Monitors published capital plans from:
  - Power utilities: Hydro-Québec, BC Hydro, OPG, SaskPower, Manitoba Hydro, NB Power, NL Hydro
  - Transit agencies: Metrolinx, TransLink, STM/ARTM
  - Port authorities: Vancouver Fraser Port, Montreal Port, Halifax Port
  - Airport authorities: GTAA (Pearson), ADM (Montreal), YVR (Vancouver)
  - Other: Canada Post, VIA Rail/VIA HFR, Canada Infrastructure Bank
- Quarterly scraping + news release monitoring

### 2.8 Tier 8: Canada Energy Regulator
- Scrapes CER project database for active and recent energy project filings
- Covers pipelines, power lines, LNG, offshore energy
- Separate from IAAC — different regulatory body

### 2.9 Tier 9: StatsCan Building Permits (Signal)
- Pulls Table 34-10-0066-01 monthly
- Detects anomalies: municipalities with permit values > 3x their 12-month moving average
- Anomalies generate investigation queries fed to enrichment pipeline
- Signal tier — produces investigation targets, not project records directly

### 2.10 Tier 10: Lobbyist Registries (Signal)
- Federal Office of the Commissioner of Lobbying + Ontario, Quebec, Alberta, BC registries
- Searches for registrations mentioning construction, infrastructure, permits, environmental assessment
- Signal tier — generates investigation queries for enrichment

### 2.11 Tier 11: Municipal Development Applications (15 CMAs)
- Open Data APIs: Vancouver, Calgary, Edmonton, Winnipeg (Socrata/CKAN)
- HTML portals: Toronto AIC, Ottawa DevApps, Halifax, Hamilton, Quebec City, Saskatoon, Regina, St. John's, Charlottetown, Fredericton
- Filtered by GDP-proportional thresholds
- Earliest possible project signal — months/years before media coverage

### 2.12 Tier 12: Google Alerts (~25)
- RSS-delivered Google Alerts for key project terms
- Terms cover: dollar-value catches ("billion dollar project Canada"), brownfield-specific ("redevelopment million Canada"), sector-specific ("mine approved Canada"), French ("projet majeur construction Canada"), status changes ("project delayed Canada")
- Feed directly into RSS filter pipeline

### 2.13 Tier 13: Industry Trade RSS (~15 feeds)
- Construction industry publications processed through RSS filter pipeline
- Tagged as `source_type: industry` — high signal, almost everything passes
- Included in the 201+ feed count

### 2.14 Tier 14: University/Institutional Capital Plans
- U15 research universities capital project pages
- Major colleges/polytechnics (BCIT, SAIT, George Brown)
- Healthcare institutions (SickKids Project Horizon, MUHC)
- Annual scrape + quarterly news monitoring

---

## 3. SEARCH & ENRICHMENT BUDGET

### 3.1 Google News RSS (Unlimited, $0)
All 759 compound queries converted to RSS feed URLs. Polled weekly. No daily limit.

### 3.2 Tavily (1,000 credits/month, $0)

| Task | Credits/month |
|---|---|
| Cost-finding for valueless projects | 300 |
| Named project tracking (top 50 by value) | 200 |
| Deep verification (single-source projects) | 200 |
| Enrichment (missing fields) | 150 |
| Signal investigation (permit/lobbyist follow-up) | 100 |
| Buffer | 50 |
| **Total** | **1,000** |

### 3.3 Gemini Flash WITHOUT Grounding (Unlimited, $0)
- RSS article classification (Layer 6 of filter)
- Project field extraction from article text
- V-code search fallback
- **CRITICAL:** Code must NEVER pass `google_search` tool or `groundingConfig` to the API. This enables grounding fees ($35/1,000 queries).

---

## 4. COST-FINDING FOR VALUELESS PROJECTS

- Runs as FIRST priority within enrichment budget (60/day)
- Selects projects with no `value_millions` field
- Priority: new projects > government-sourced > multi-evidence > older
- Query specifically crafted for dollar figures (budget approvals, procurement awards, news, filings)
- QC and NB projects get both French and English cost queries
- Regex-based cost extraction from response (handles $X million, $X billion, ranges, revised estimates)
- After 3 failed attempts across 6 weeks: marked `cost_unfindable`
- Found values written to Firestore with source URLs, confidence recalculated
- Firestore fields: `value_millions`, `value_low_millions`, `value_high_millions`, `value_notes`, `last_cost_search`, `cost_search_attempts`, `cost_unfindable`

---

## 5. PROJECT DATA MODEL

### 5.1 Project Type Taxonomy (11 types)
- `greenfield` — New build on unused/cleared land
- `redevelopment` — Demolish and rebuild on same site
- `adaptive_reuse` — Convert to fundamentally different use
- `major_renovation` — Significant upgrade retaining structure
- `expansion` — Addition to existing facility
- `retrofit` — Structural/systems upgrade
- `restoration` — Heritage rehabilitation
- `remediation` — Environmental cleanup ± redevelopment
- `conversion` — Use-type change (e.g., office to residential)
- `modernization` — Technology/systems upgrade
- `decommission_replace` — Shut down old, build replacement

### 5.2 NAICS-Aligned Sectors (18)
oil_gas, mining, infrastructure, power_energy, manufacturing, transport_logistics, healthcare, education, residential, commercial_mixed, agriculture, forestry, defence, telecom, indigenous, environment, tourism_culture, government

### 5.3 Status Progression
rumoured (0) → proposed (1) → approved (2) → under_construction (3) → completed (4)
Branches: delayed/on_hold (2.5), cancelled (-1)
Merge logic: always advance to highest status, never regress

### 5.4 Firestore Project Document Schema
```
{
  name, proponent,
  location: { city, province, cma },
  value_millions, value_low_millions, value_high_millions, value_notes,
  currency: "CAD",
  status, project_type, is_brownfield, sector,
  description,
  evidence: [{ url, url_normalized, name, date, source_type, authority, url_valid, url_verified, is_known_source }],
  evidence_count, has_government_source, has_known_source,
  confidence, display_confidence (with decay),
  discovery_sources: [tier names],
  anomalies: [{ type, detail, old_value, new_value }],
  has_anomalies,
  is_stale, needs_review, days_since_update,
  cost_search_attempts, cost_unfindable, last_cost_search,
  needs_enrichment, needs_cost_search,
  year_first_tracked, backfill_source,
  first_seen, last_updated
}
```

### 5.5 URL Hard Gate
- Every project MUST have at least one verifiable source URL
- `build_project_document()` returns None if no evidence URL exists
- Projects without URLs are rejected from Firestore
- Evidence merge NEVER loses URLs during dedup

---

## 6. DEDUPLICATION & CONFIDENCE

### 6.1 Deduplication
- Dedup key: province + city + normalized name (lowercase, remove punctuation/filler)
- Same project from multiple sources MERGES (evidence arrays combine)
- Keep highest value, most advanced status, fill missing fields
- Track all discovery_sources

### 6.2 Confidence Scoring
- Base: 0.1
- Evidence count bonus: +0.1 per source (max 0.3)
- Government source bonus: +0.15 per gov source (max 0.3)
- Verified value bonus: +0.1
- Multi-tier bonus: +0.05-0.1
- Range: 0.0 to 1.0

### 6.3 Confidence Decay
- 0-30 days: no decay
- 31-60 days: -0.05
- 61-90 days: -0.10
- 91-120 days: -0.15
- 121-180 days: -0.20, flagged `is_stale`
- 180+ days: flagged `needs_review`
- Decay reversed immediately when project is re-discovered
- Frontend uses `display_confidence` (includes decay)

### 6.4 Anomaly Detection
- Value change > 30%: flagged as `value_spike` or `value_drop`
- Status regression (e.g., under_construction → proposed): flagged
- Proponent change: flagged
- Province/location change: flagged
- Cross-project duplicate detection: similar names across provinces
- Anomalies stored in project document, displayed on frontend

---

## 7. REASONING LAYERS

### 7.1 Claude Sonnet — All Reasoning (~$55/year)
- `claude_reasoning.py` — calls Claude Sonnet 4.5 via Anthropic API
- Token usage tracking per call with cost calculation
- **Narrative intelligence (from STEP_2N):**
  - Policy impact assessment
  - Market commentary (200-300 words)
  - Pre-event analysis (150-250 words per event)
  - Weekly briefing synthesis (1000-1500 words, 8 sections)
  - Under the Microscope deep-dive (200-300 words)
- **Structured analysis (formerly Gemini Pro, from STEP_2K):**
  - Gap analysis on discovery results
  - Failed extraction recovery
  - Signal investigation (permits, lobbyists)
  - Cross-reference dedup quality check
  - Monthly meta-analysis
- **NO Gemini Pro.** Removed entirely. All reasoning consolidated into one model, one billing relationship.

---

## 8. ADAPTIVE LEARNING SYSTEM

### 8.1 Missing Project Input
- Frontend form: name (required), province (required), city, sector, value, proponent, description, source_url, project_type, status, user_notes
- Submitted projects immediately enter main projects collection (low confidence 0.2-0.3)
- Dedup check prevents duplicating existing projects
- Queued for enrichment and cost-finding

### 8.2 Diagnostic Engine
- Runs backward through every discovery tier to identify WHY a project was missed
- 8 failure categories:
  1. VOCABULARY_GAP — terminology not in queries/keywords
  2. FILTER_KILL — RSS filter blocked valid article (which layer, which keyword)
  3. GEOGRAPHIC_GAP — city not in any CMA or regional cluster query
  4. SECTOR_GAP — sector not in province's affinity matrix
  5. SOURCE_GAP — publication not in RSS feed list
  6. LANGUAGE_GAP — French coverage missing for province-sector pair
  7. VALUE_BELOW_THRESHOLD — project value below province threshold
  8. NOVEL_PROJECT_TYPE — project type not in taxonomy
- Uses Gemini to find similar at-risk projects (1 query per submission)

### 8.3 Improvement Application
- Each diagnosis generates concrete improvements (new terms, new feeds, expanded coverage)
- Stored in Firestore `pipeline_improvements` collection
- Auto-approved types (additive only): vocabulary_addition, keyword_addition, feed_addition, french_sector_expansion
- Manual review types: negative_keyword_review, affinity_expansion, geographic_addition, taxonomy_expansion
- **CRITICAL CONSTRAINT:** Improvements are ADDITIVE ONLY — system can never remove existing queries, keywords, or feeds

### 8.4 Effectiveness Tracking
- Monthly check: did applied improvements catch new projects?
- After 60 days with no matching discoveries: marked "unproven"
- Monthly learning report: submission count, failure category distribution, improvements applied vs pending, effectiveness rates

---

## 9. HISTORICAL BACKFILL

### 9.1 Project Backfill
- `historical_backfill.py` — seeds database from ReNew Canada Top 100 (2021-2025 editions)
- ~250-350 unique projects including both greenfield and brownfield
- Seeded with `needs_enrichment: true`, low confidence (0.3)
- Weekly enrichment pipeline fills in current status and source URLs
- Run ONCE

### 9.2 Economic Indicator Backfill
- Bank of Canada Valet API: 5 years of policy rate, CAD/USD, CPI, prime rate, 10Y bond yield, 5Y mortgage rate
- Statistics Canada: 5 years of GDP, employment, building permits, housing starts, unemployment by province, non-residential capital expenditure
- Yahoo Finance: 5 years of WTI, natural gas, gold, copper, lumber, TSX composite, TSX mining/energy/REIT sub-indices, CAD/USD
- All written to `indicator_history` Firestore collection with schema: {indicator, series, province, date, value, unit, source, frequency, description, backfilled}
- Live weekly data also writes to `indicator_history` (same schema)
- Run ONCE for backfill, then ongoing via weekly pipeline

---

## 10. SECTOR TREND ANALYSIS

### 10.1 Project Trends
- `sector_trends.py` — computes period-over-period changes
- **Period comparisons:** week-over-week, month-over-month, quarter-over-quarter
- **Sector momentum:** current 30-day activity vs prior 30 days per sector (accelerating/decelerating/stable)
- **Geographic shifts:** provincial share of new project value, 90-day comparison
- **Pipeline health metrics:** % with value, % with evidence, % with government source, % high confidence, % stale

### 10.2 Indicator Trends
- Current value vs 1 week, 1 month, 3 months, 6 months, 1 year, 2 years, 5-year average
- Rate of change calculation (accelerating/decelerating)
- Historical comparison requires backfilled data in `indicator_history`

### 10.3 Cross-Reference Engine
- `cross_reference.py` — connects macro indicators to project database
- 8+ indicator-to-project mappings:
  - policy_rate → residential, commercial (inverse)
  - wti_crude → oil_gas in AB, SK, NL (direct, threshold $65)
  - natural_gas → oil_gas, power_energy in AB, BC (direct)
  - copper → mining (direct)
  - lumber → forestry, residential (direct)
  - unemployment_rate → infrastructure, government (inverse)
  - building_permits → residential, commercial (leading indicator)
  - mortgage_5y_fixed → residential (inverse)
- Each mapping has threshold_change and affected sectors/provinces
- When indicator crosses threshold, generates insight with affected project count and value

### 10.4 Trend Snapshots
- Weekly trend data stored in Firestore `trend_snapshots` collection
- Enables historical comparison of trends themselves

---

## 11. PROVINCIAL POLICY MONITOR

### 11.1 Policy RSS Feeds
- Federal: Department of Finance, Parliament news, Budget RSS
- Provincial: Finance ministry newsrooms for all provinces
- Energy regulators: CER, AER, BCUC
- Classified by 12 policy categories: budget_capital_spending, tax_incentive, regulatory_change, housing_policy, energy_policy, mining_royalty, infrastructure_funding, trade_policy, indigenous_policy, environmental_regulation, immigration_workforce, procurement_policy

### 11.2 Policy Classification
- Gemini Flash classifies policy articles as POLICY_RELEVANT or NOT_RELEVANT
- Assigns policy category

### 11.3 Policy Impact Assessment
- Claude Sonnet assesses economic implications
- Links policy changes to affected sectors, provinces, and specific projects in database
- Estimates magnitude (high/medium/low) and timeline (immediate, 3-6 months, 1-2 years)

---

## 12. ENHANCED MARKETS & COMMODITIES

### 12.1 Canadian-Specific Indicators
Beyond standard Yahoo Finance tickers:
- Western Canadian Select discount to WTI (oil sands profitability)
- AECO natural gas hub price (BC LNG economics)
- Lithium carbonate spot (EV battery plant viability)
- Uranium spot (Saskatchewan mining + SMR economics)
- Nickel spot (Ontario/Quebec mining)
- Potash price (Saskatchewan potash projects)
- Steel rebar price (construction input cost)
- Cement/concrete price (construction input cost)
- CMHC housing starts SAAR
- TSX infrastructure basket (BIP, AQN, BEPC, TRP, ENB)
- Corporate credit spread (project financing conditions)

### 12.2 Market Commentary
- Claude Sonnet generates weekly 200-300 word commentary
- Connects price movements to specific Canadian project impacts
- References database projects by name

---

## 13. ECONOMIC EVENT CALENDAR

### 13.1 Event Sources
- Bank of Canada rate decision dates (published annually, hardcoded for current year)
- Statistics Canada release calendar (recurring monthly: LFS, CPI, GDP, permits, housing starts)
- Federal/provincial budget dates (updated as announced)
- IAAC hearing and decision dates for tracked projects

### 13.2 Pre-Event Analysis
- Claude Sonnet generates forward-looking analysis for high-significance events
- References market expectations, historical precedent, and affected projects
- 150-250 words per event

---

## 14. WEEKLY BRIEFING SYNTHESIS

### 14.1 Structure (1000-1500 words)
1. **HEADLINE** — single most significant factual development (1-2 sentences, no characterization)
2. **MACRO PULSE** — national indicators with period-over-period changes, all sourced (150-200 words)
3. **UNDER THE MICROSCOPE** — factual deep-dive: what happened, what changed, which Canadian sectors/projects are in scope (200-300 words, see Section 15)
4. **PROVINCIAL SPOTLIGHT** — one province's data: new projects, value totals, status changes (100-150 words)
5. **SECTOR WATCH** — sectors with largest volume/value changes, stated with numbers (150-200 words)
6. **PROJECT TRACKER** — new projects discovered, status changes recorded, completions confirmed (150-200 words)
7. **MARKETS & COMMODITIES** — price movements stated factually, affected project counts from database (100-150 words)
8. **LOOKING AHEAD** — upcoming scheduled events (BoC dates, StatsCan releases, budget dates) with affected project counts (100-150 words)

### 14.2 Generation
- Claude Sonnet system prompt defines a factual reporter persona — NOT an analyst, editor, or advisor
- Input: project trends, indicator trends, cross-reference data, policy developments, market data, upcoming events, microscope context
- Every claim must trace to specific data in the provided context
- No fabrication, no filler phrases, no predictions, no recommendations
- No characterizing events as good/bad/bullish/bearish/positive/negative
- State facts, present data, show connections. Let readers draw conclusions.
- Tone: Reuters wire service, not opinion column

### 14.3 Storage & Distribution
- Stored in Firestore `weekly_briefings` collection (date, week_number, content, metadata)
- Latest briefing in `dashboard_state/latest_briefing` for frontend display
- Token usage and cost tracked per briefing

---

## 16. FRONTEND

### 16.1 Projects Tab
- **Project cards** with: name, type badge, status badge, proponent, location, value (formatted $XB or $XM), description, sector label, confidence score with evidence count
- **Type badges:** Color-coded (greenfield green, brownfield amber/blue/purple/orange/red by subtype) with emoji icons
- **Status badges:** proposed (gray), approved (blue), under_construction (yellow), completed (green), delayed/on_hold (orange), cancelled (red)
- **Confidence badges:** Percentage + evidence count, color-coded (≥70% green, ≥40% yellow, <40% gray)
- **Filter controls:** Project category (All/Greenfield/Brownfield), project type (11 types), status (7 statuses), sector (18 sectors), province (13)
- **Summary statistics:** Total projects, total value, greenfield count, brownfield count, under construction count
- **Evidence sources:** Expandable section with clickable verification links, source authority badges (GOV blue, NEWS gray, IND amber, REG gray), sorted government first
- **Stale indicators:** ⏰ badge with days since update for stale projects
- **Anomaly indicators:** ⚠️ expandable section showing anomaly details
- **Needs review badge:** Red badge for projects not updated in 180+ days
- **Value display:** Shows range if available, asterisk for value notes, "searching" / "not available" states for valueless projects

### 16.2 Missing Project Submission Form
- Modal form with fields: name (required), province (required), city, sector (dropdown 18 options), value, proponent, project type (dropdown 11 options), status (dropdown), source URL, description, user notes
- Confirmation message after submission showing whether project was new or merged
- States system is diagnosing why it was missed

### 16.3 Pipeline Improvements Panel (Admin)
- Pending review: list of structural improvements awaiting approval (approve/dismiss buttons)
- Applied: list of improvements with effectiveness status (effective/unproven)

### 16.4 Weekly Briefing Display
- Displays latest briefing from `dashboard_state/latest_briefing`
- Formatted 1000-1500 word intelligence report with 8 sections including Under the Microscope
- Date and week number
- **Download buttons:** "📄 Download PDF" and "📝 Download Word" — trigger direct browser download via `/api/briefing-download?format=pdf` and `?format=docx`
- Optional `week_date` parameter for downloading historical briefings

### 16.5 Data Explorer Tab (STEP_2O)
- **Search bar:** Natural language input with Enter key support
- **Quick category buttons:** Labour Market, GDP, Construction, Housing, Inflation, Trade, Energy, Mining
- **Results list:** Each result shows V-code (mono badge), table number, frequency, geography, title, description, unit, subject category
- **"View on StatsCan" button:** Opens `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}` in new tab
- **"Preview Data" button:** Shows last 12 periods of data inline
- **Gemini fallback:** When local search returns no good matches (score < 3), automatically searches via Gemini Flash and adds discovered V-codes to local index

### 16.6 Interactive Indicator Chart
- **Single large chart** displaying historical data for a selected indicator
- **Indicator selector dropdown** with all tracked indicators grouped by category:
  - Rates: BoC policy rate, prime rate, 5Y mortgage rate, 10Y bond yield
  - Prices: CPI (all-items, shelter, energy), WTI crude, natural gas, gold, copper, lumber
  - Labour: unemployment rate (national + by province), employment, construction employment
  - Activity: GDP (total, construction, mining, manufacturing), building permits, housing starts
  - Markets: TSX composite, TSX mining, TSX energy, TSX REIT, CAD/USD
- **Province toggle** (where applicable): national view or select a province for provincial series
- **Chart features:**
  - Line chart (Chart.js or Recharts) showing full historical data from `indicator_history` collection (up to 5 years)
  - Most recent data point highlighted with a larger dot and label showing the value and date
  - Most recent change annotated: arrow up/down + absolute and percentage change from prior period
  - Shaded band showing the 5-year range (min/max) for context
  - Hover tooltip showing date, value, and period-over-period change
  - Time range selector: 3 months, 1 year, 3 years, 5 years
- **Data source:** Reads from `indicator_history` Firestore collection (already populated by backfill + weekly pipeline)
- **StatsCan link:** "View on StatsCan" button that opens the source table using the V-code URL

### 16.7 Firestore Indexes
- Composite indexes for filter combinations: province + status, is_brownfield + province, sector + province, project_type + status, province + value DESC

---

## 15. UNDER THE MICROSCOPE

### 15.1 Purpose
A dedicated deep-dive section in the weekly briefing that provides extended analysis of one dominant story, explaining what happened, what changed, new developments, and how it specifically affects Canada's economy and capital investment pipeline. Examples: a war with Iran (defence contracts, energy prices, supply chains), a US trade war (manufacturing projects at risk), a major bank failure (project financing), a natural disaster (reconstruction pipeline), a federal election (policy shift implications).

### 15.2 Topic Selection (Automated)
- Claude Sonnet selects the topic during briefing generation based on:
  - Highest-volume news story in the past 7 days from RSS feeds and Gemini results
  - Story with the largest measurable impact on tracked indicators (biggest commodity/rate move)
  - Story with the most affected projects in the database (via cross-reference engine)
  - User override: optional Firestore field `dashboard_state/microscope_override` to force a specific topic
- Only ONE topic per week — depth over breadth

### 15.3 Analysis Structure (200-300 words within briefing)
1. **What happened / what changed** — factual summary of the development, sourced
2. **New developments this week** — what is factually different since last week
3. **Canadian exposure** — which sectors, provinces, and indicators are directly connected, stated with data:
   - Affected sectors (with project counts and values from database)
   - Affected provinces (with specific exposure data)
   - Commodity/indicator movements (with current numbers)
4. **Projects in scope** — named projects from the database that fall within affected sectors/provinces (e.g., "The database tracks 14 Alberta oil projects ($18B) with production costs above current WTI")
5. **Upcoming scheduled events** — dates of decisions, releases, or hearings related to this story

**Tone:** Factual reporting only. State what happened, state what the data shows, state which projects are in scope. Do not predict outcomes, recommend actions, or characterize events as positive/negative.

### 15.4 Generation
- Uses one additional Claude Sonnet call per week (~$0.20)
- System prompt defines factual reporter persona — present data and connections, no opinions or recommendations
- Input: news context from RSS/Gemini, affected projects from cross-reference engine, relevant indicator data
- Gemini Flash runs 2-3 web searches to get latest context on the selected topic before Claude Sonnet analyzes

### 15.5 Continuity Tracking
- If the same story dominates multiple consecutive weeks, briefings reference prior coverage: "In its third week under the microscope, the Iran conflict has now..."
- Firestore `dashboard_state/microscope_history` stores past topics with dates
- Prevents repetitive analysis — each week must have genuinely new developments to justify continuation

---

## 17. KNOWN-PROJECT SWEEP

### 17.1 Problem
The weekly pipeline's 4-week lookback window only catches projects with recent media activity. Projects announced months or years ago that are still active (proposed, approved, under construction) are invisible to the pipeline unless they generate fresh news.

### 17.2 One-Time Comprehensive Sweep
- `known_project_sweep.py` — ~200 Gemini queries with NO time constraint
- Province × sector queries: "List ALL major [sector] projects in [province] that are currently proposed, approved, under construction, or recently completed"
- CMA sweeps for top 20 cities: all sectors, all stages, $10M+ threshold
- French sweeps for QC and NB
- Specific queries for known-missing projects (Portage Place, The Forks, etc.)
- Results process through standard dedup pipeline
- Cost: $0 (uses 75/day buffer over 2-3 days)
- Run ONCE after deployment

### 17.3 Extended Seed List
- 50+ hardcoded known major projects across all provinces
- Includes: Portage Place ($650M), The Forks, Wehwehneh Bahgahkinahgohn ($140M), Ontario Line ($19B), REM ($7.95B), LNG Canada ($40B), Site C ($16B), BHP Jansen ($12B), Irving CSC ($77B), Parliament Hill ($5B), SickKids Project Horizon ($1.3B), VIA HFR ($12B), Calgary Event Centre ($800M), Halifax Cogswell ($2B), Northvolt ($7B), etc.
- Each seeded with `needs_enrichment: true`, low confidence (0.3)
- Enrichment pipeline fills in current status and source URLs

### 17.4 Ongoing Gap Prevention
- After the one-time sweep, the adaptive learning system (STEP_2L) catches future gaps
- Historical backfill from STEP_2M covers ReNew Canada Top 100 annual editions
- Deep verification from STEP_2J re-confirms projects quarterly

---

## 18. KEY PEOPLE TRACKING

### 18.1 Tracked Decision-Makers
- **Federal (5+):** PM, Finance Minister, Infrastructure/Housing Minister, NRCan Minister, Transport Minister
- **Provincial (26+):** 13 Premiers, 13 Finance Ministers
- **Municipal (15+):** Mayors of top 15 CMAs
- **Crown Corporation (6+):** CEOs of Canada Infrastructure Bank, CMHC, Metrolinx, Hydro-Québec, BC Hydro, VIA Rail

### 18.2 Monitoring Methods
- **Official RSS feeds:** Provincial/federal newsrooms, Premier's office feeds — processed through government source bypass (skip keyword filtering)
- **Google Alerts:** Generated for each key person + project/investment announcement keywords — feeds into existing Google Alerts RSS pipeline
- **X/Twitter (optional):** If X API access is available, monitor handles for announcement keywords; otherwise covered by Google Alerts proxy

### 18.3 Announcement Keywords
- English: announce, invest, fund, approve, construction, build, project, million, billion, infrastructure, development, expansion, breaking ground, budget, capital plan
- French: annoncer, investir, financer, approuver, construction, projet, millions, milliards, infrastructure

### 18.4 Integration
- Key people RSS feeds are added to the government source bypass list — they skip keyword filtering entirely
- Any article matching announcement keywords goes directly to Gemini Flash classification
- Government source confidence weight: 0.35-0.40

---

## 19. BRIEFING EXPORT

### 19.1 Export Formats
- **PDF:** Generated via reportlab with dashboard branding (title, date, week number, section headers, footer with generation timestamp and data source attribution)
- **Word (DOCX):** Generated via python-docx with same branding and formatting

### 19.2 API Endpoint
- `/api/briefing-download?format=pdf` — returns PDF file
- `/api/briefing-download?format=docx` — returns DOCX file
- Optional `week_date` parameter for historical briefings
- Content-Disposition header triggers browser download dialog

### 19.3 Frontend
- Two download buttons on the weekly briefing display section: "📄 Download PDF" and "📝 Download Word"
- Both trigger direct download

### 19.4 Dependencies
- `reportlab` (PDF generation)
- `python-docx` (Word generation)
- Install: `pip install reportlab python-docx --break-system-packages`

---

## 20. CANSIM V-CODE SEARCH ENGINE

### 20.1 Curated Index
- `vcode_index.py` — ~40+ curated V-codes across 12 subject areas as initial seed
- Subject areas: labour_market, gdp, construction, housing, prices, trade, manufacturing, investment, retail, demographics, energy, mining
- Each entry: vcode, table, title, description, geography, frequency, unit, subject, keywords, statcan_table_url, statcan_vector_url

### 20.2 Fuzzy Search
- `vcode_search.py` — scores results by exact and word-level matching against title, description, keywords, geography, subject
- Province detection from query text
- Stop word removal
- Returns top 10 results sorted by score

### 20.3 Gemini Flash Fallback
- `vcode_gemini_fallback.py` — uses 1 Gemini free tier query when local search fails
- Discovered V-codes saved to `vcode_index.json` for future local matches
- Index grows over time, reducing Gemini fallback frequency

### 20.4 Live Data Preview
- `vcode_data_fetch.py` — fetches recent data from StatsCan Web Data Service API
- Returns last 12 periods with latest value and date
- Free API, no authentication required

### 20.5 StatsCan URLs
- Table URL: `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}`
- Vector URL: `https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en?vectorIds={vcode_number}`
- Both generated automatically from table number and V-code

---

## 21. DEPRECATED COMPONENTS (must NOT exist in active code)

- **Gemini grounded search:** No `google_search` tool, no `groundingConfig`, no `grounding` parameters in ANY Gemini API call. This was costing $35/1,000 queries. Replaced by Google News RSS.
- **Gemini Pro:** No imports of `gemini_pro_reasoning`. All reasoning tasks moved to `claude_reasoning.py` (Claude Sonnet). Removing eliminates Google billing risk entirely.
- **Perplexity Sonar Pro:** No imports, no API calls, no API key. Superseded by compound queries + enrichment.
- **GDELT:** No imports, no API calls. Superseded by compound queries + RSS feeds.
- **Claude Haiku:** No imports in weekly pipeline code. Exception: seed_projects.py may use Haiku for one-time bulk seeding with a comment explaining the cost rationale.

---

## 22. COLLECTIONS SUMMARY (Firestore)

| Collection | Purpose | Written By |
|---|---|---|
| projects | Main project database | All discovery tiers, enrichment, cost-finding, known-project sweep |
| missed_projects | User-submitted missed projects | Frontend form, diagnostic engine |
| pipeline_improvements | Adaptive learning improvements | Learning store |
| indicator_history | Time series for all economic indicators | Backfill + weekly pipeline |
| trend_snapshots | Weekly trend analysis snapshots | Trend analysis engine |
| weekly_briefings | Generated weekly intelligence briefings | Briefing generator |
| dashboard_state | Frontend state (latest briefing, market data, events, microscope override/history) | Various modules |

---

## 23. ANNUAL COST BREAKDOWN

| Component | Annual Cost |
|---|---|
| Google News RSS (759 query feeds, unlimited) | $0 |
| Gemini 2.5 Flash WITHOUT grounding (classification, extraction) | $0 |
| RSS feeds (~200), Google Alerts (~25) | $0 |
| Government registries, SEDAR+, CER, municipal APIs | $0 |
| StatsCan API, Bank of Canada Valet API | $0 |
| Yahoo Finance (yfinance) | $0 |
| StatsCan Web Data Service (V-code search) | $0 |
| Tavily (1,000 credits/month free tier) | $0 |
| Key people RSS monitoring | $0 |
| Briefing PDF/DOCX export (reportlab, python-docx) | $0 |
| Known-project sweep (one-time) | $0 |
| Claude Sonnet 4.5 (ALL reasoning — briefing, microscope, commentary, gap analysis, dedup QA, ~10 calls/week) | ~$55 |
| Firebase/Firestore (storage + functions) | ~$5 |
| **Total** | **~$60/year** |

---

## 24. WEEKLY PIPELINE EXECUTION ORDER

```
1. Discovery Phase (all tiers concurrent):
   - Tier 1: IAAC registry
   - Tier 2: Google News RSS search (759 queries as RSS feeds)
   - Tier 3: RSS feeds (201+ feeds, remediated filter)
   - Tier 4: Project status monitoring
   - Tier 5: Provincial EA registries (13)
   - Tier 6: SEDAR+ securities filings
   - Tier 7: Crown corporation capital plans
   - Tier 8: Canada Energy Regulator
   - Tier 9: StatsCan building permits (signal)
   - Tier 10: Lobbyist registries (signal)
   - Tier 11: Municipal development applications (15 CMAs)
   - Tier 12: Google Alerts (RSS)
   - Tier 13: Industry trade RSS
   - Tier 14: University/institutional capital plans
   - Key people RSS feeds (processed through government bypass)

2. Deduplication (all raw mentions merged)

3. Firestore Write (new projects created, existing updated)

4. Enrichment Phase (ordered):
   a. Cost-finding for valueless projects (first priority, 60/day)
   b. General enrichment (missing fields, 22/day)
   c. Lifecycle monitoring (stale high-value projects, 20/day)
   d. Investigation of signals from permits + lobbyists

5. Intelligence Phase:
   a. Confidence decay applied
   b. Anomaly detection (value changes, status regressions, duplicates)
   c. Cross-project anomaly check

6. Claude Sonnet Reasoning (replaces Gemini Pro):
   a. Gap analysis on discovery results
   b. Failed extraction recovery
   c. Signal investigation
   d. Cross-reference dedup quality check

7. Trend Analysis:
   a. Project trends (sector momentum, geographic shifts, pipeline health)
   b. Indicator trends (current vs historical)
   c. Cross-reference insights (indicators → affected projects)

8. Adaptive Learning:
   a. Process pending missed project submissions
   b. Run diagnostics
   c. Apply auto-approved improvements
   d. Monthly effectiveness tracking

9. Policy Monitor:
   a. Process policy RSS feeds
   b. Classify policy articles
   c. Claude Sonnet impact assessments for significant policies

10. Market Commentary:
    a. Claude Sonnet market commentary generation

11. Event Calendar:
    a. Build upcoming events list (14 days)
    b. Claude Sonnet pre-event analyses for high-significance events

12. Under the Microscope:
    a. Select dominant story (highest news volume + indicator impact + project crossover)
    b. Check microscope_override in dashboard_state
    c. Check microscope_history for continuity (same story = reference prior weeks)
    d. Gemini Flash: 2-3 web searches for latest context on selected topic
    e. Claude Sonnet: generate 200-300 word deep-dive with Canadian impact analysis
    f. Store topic in microscope_history

13. Weekly Briefing:
    a. Claude Sonnet narrative synthesis (1000-1500 words, 8 sections including Under the Microscope)
    b. Store in weekly_briefings collection
    c. Update dashboard_state/latest_briefing

14. Briefing Export:
    a. Generate PDF version via reportlab
    b. Generate DOCX version via python-docx
    c. Store both in Firestore or Cloud Storage for download

15. Archive Indicators:
    a. Write current week's indicator values to indicator_history
```

---

## 25. DAILY EXECUTION ORDER (midnight Eastern)

```
1. Tavily deep verification (~7 queries, from 200/month budget)
2. Tavily named project tracking (~7 queries, from 200/month budget)
3. Tavily cost-finding for valueless projects (~10 queries, from 300/month budget)
4. Tavily enrichment for missing fields (~5 queries, from 150/month budget)
5. Process any results through dedup and Firestore write
```
