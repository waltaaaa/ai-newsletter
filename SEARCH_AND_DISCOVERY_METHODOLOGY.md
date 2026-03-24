# Search & Discovery Methodology

## How Signal Dispatch Finds Every Capital Project in Canada

Signal Dispatch tracks capital projects across all 13 provinces and territories, 18 NAICS-aligned sectors, and 11 project types. The discovery system runs autonomously every Monday at 5:30 AM Eastern, executing a 14-tier pipeline that combines government registries, news intelligence, regulatory filings, municipal data, and adaptive machine learning into a single unified project database.

The annual operating cost for the entire search and discovery layer is under $150.

---

## The 14-Tier Discovery Pipeline

Every weekly run fires all 14 tiers concurrently. Each tier operates independently, producing raw project mentions that converge into a shared deduplication and merge layer before writing to SQLite. No single tier is authoritative on its own. The system's strength is in overlap: the same project discovered across multiple tiers earns higher confidence and richer metadata.

### Tier 1: Federal Impact Assessment Registry (IAAC)

The Impact Assessment Agency of Canada maintains a public registry of every project undergoing federal environmental review. The pipeline scrapes this registry directly, returning structured records with project name, proponent, status, location, and assessment phase.

IAAC projects enter the database with high base confidence (0.8) because they are government-verified. The evidence URL is the registry page itself, which is permanent and publicly accessible.

A companion IAAC status tracker monitors the same registry for *transitions*: when a project moves from Planning Phase to Public Comment, from Panel Review to Decision Statement. These status changes update existing project records and also detect new IAAC projects not yet in the database.

### Tier 2: Google News RSS Search

This is the primary discovery layer. 2,574 compound queries cover every combination of province, sector, and project type. Each query is shortened to concise keywords and converted into a Google News RSS URL:

```
https://news.google.com/rss/search?q=mining+project+Saskatchewan+2026&hl=en-CA&gl=CA&ceid=CA:en
```

French-language queries use `hl=fr-CA` for Quebec and New Brunswick coverage:

```
https://news.google.com/rss/search?q=projet+infrastructure+Québec+2026&hl=fr-CA&gl=CA&ceid=CA:fr
```

After deduplication of overlapping queries, the unique RSS URLs are polled with 30-way parallelism using async HTTP. Each feed returns 10-15 articles. The entire tier runs in under 60 seconds and costs nothing. Google News RSS is free and unlimited.

All articles from this tier flow through the 6-layer filter (described below) before any project extraction occurs.

### Tier 3: Curated RSS Feeds (324+ feeds)

A maintained list of 324+ RSS feeds organized into categories:

- **National news:** Globe and Mail, CBC, Financial Post, BNN Bloomberg, National Post
- **Regional news:** Vancouver Sun, Calgary Herald, Edmonton Journal, Toronto Star, Montreal Gazette, Winnipeg Free Press, Halifax Chronicle Herald, and dozens more
- **Government newsrooms:** 13 provincial newsrooms, Infrastructure Canada, Transport Canada, CMHC, NRCan, ISED, and 6 federal regional development agencies (PrairiesCan, PacifiCan, ACOA, FedNor, CanNor, FedDev Ontario, CED Quebec), plus 12+ major municipal newsrooms
- **Industry trade publications:** Daily Commercial News, Journal of Commerce, On-Site Magazine, Canadian Architect, ReNew Canada, Canadian Consulting Engineer, Canadian Mining Journal, Northern Miner, Mining.com, JWN Energy, Electric Energy Online, RENX, Storeys, Journal Constructo, Infra Quebec
- **French media:** Le Devoir, Radio-Canada, La Presse, Journal Constructo, Infra Quebec
- **Corporate newswires:** 12 feeds from GlobeNewswire, Canada Newswire, and Cision covering mining, energy, real estate, construction, manufacturing, transport, and government press releases
- **Google Alerts:** ~25 RSS-delivered alerts for high-value catch terms
- **Regulatory feeds:** 10 CanLII RSS feeds covering Federal Court, CER, Ontario LPAT, environmental tribunals, utilities commissions, and municipal boards

All RSS articles pass through the same 6-layer filter as Google News results.

### Tier 4: Project Status Monitoring

Existing projects in the database are monitored for status changes. When a project previously marked "proposed" appears in a news article describing construction activity, its status advances. Status never regresses: once a project reaches "under construction," a new article referencing the proposal phase does not demote it.

### Tier 5: Provincial Environmental Assessment Registries (13)

Separate scrapers for all 13 provincial and territorial environmental assessment registries:

- **BC EAO** uses a JSON API (the best-structured source in the pipeline)
- **Ontario ERO, Quebec BAPE, Alberta EPEA**, and others use HTML scraping
- Projects from EA registries receive high confidence (0.8) as government-verified sources
- Evidence URLs are the registry page URLs, which are permanent

### Tier 6: SEDAR+ Securities Filings

The Canadian securities regulator requires public companies to file disclosure documents. The pipeline searches SEDAR+ for recent filings containing capital project information:

- NI 43-101 technical reports (mining)
- Material change reports
- MD&A (Management Discussion & Analysis) sections

Filing titles frequently contain the project name and location directly. Evidence URLs point to the SEDAR+ filing page, which is government-mandated and permanent.

### Tier 7: Crown Corporation Capital Plans (25+)

Monitors published capital plans and news releases from 25+ Crown corporations and major public agencies:

- **Power utilities:** Hydro-Quebec, BC Hydro, OPG, SaskPower, Manitoba Hydro, NB Power, NL Hydro
- **Transit agencies:** Metrolinx, TransLink, STM/ARTM
- **Port authorities:** Vancouver Fraser Port, Montreal Port, Halifax Port
- **Airport authorities:** GTAA (Pearson), ADM (Montreal), YVR (Vancouver)
- **Other:** Canada Post, VIA Rail/VIA HFR, Canada Infrastructure Bank

Quarterly scraping plus continuous news release monitoring.

### Tier 8: Canada Energy Regulator (CER)

Scrapes the CER project database for active and recent energy project filings covering pipelines, power lines, LNG terminals, and offshore energy. The CER is a separate regulatory body from IAAC, so this tier captures a different set of projects.

### Tier 9: StatsCan Building Permits (Signal Tier)

Pulls Statistics Canada Table 34-10-0066-01 monthly. Instead of generating project records directly, this tier detects anomalies: municipalities where permit values exceed 3x their 12-month moving average.

An anomaly in building permit values in a small municipality often signals a large project that hasn't appeared in media yet. These anomalies generate investigation queries that are routed to the enrichment pipeline for follow-up.

### Tier 10: Lobbyist Registries (Signal Tier)

Searches the federal Office of the Commissioner of Lobbying plus provincial registries (Ontario, Quebec, Alberta, BC) for registrations mentioning construction, infrastructure, permits, or environmental assessment.

Like building permits, this is a signal tier. A lobbying registration for a large infrastructure project can surface months before any public announcement. Signals generate investigation queries for follow-up.

### Tier 11: Municipal Development Applications (15 CMAs)

Direct access to municipal planning data across 15 Census Metropolitan Areas:

- **Open Data APIs:** Vancouver, Calgary, Edmonton, Winnipeg (Socrata/CKAN)
- **HTML portals:** Toronto AIC, Ottawa DevApps, Halifax, Hamilton, Quebec City, Saskatoon, Regina, St. John's, Charlottetown, Fredericton

Development applications are filtered by GDP-proportional thresholds (see below). This tier captures the earliest possible project signal, sometimes months or years before media coverage.

### Tier 12: Google Alerts (~25 RSS alerts)

RSS-delivered Google Alerts covering high-value catch terms:

- Dollar-value catches: "billion dollar project Canada"
- Brownfield-specific: "redevelopment million Canada"
- Sector-specific: "mine approved Canada"
- French: "projet majeur construction Canada"
- Status changes: "project delayed Canada"

These feed directly into the RSS filter pipeline.

### Tier 13: Industry Trade RSS (~15 feeds)

Construction industry publications processed through the RSS filter pipeline. Tagged as `source_type: industry`, meaning almost everything from these feeds passes through. These are high-signal, low-noise sources already focused on capital projects.

### Tier 14: University & Institutional Capital Plans

Monitors capital project pages for:

- U15 research universities
- Major colleges and polytechnics (BCIT, SAIT, George Brown)
- Healthcare institutions (SickKids Project Horizon, MUHC)

Annual scrape plus quarterly news monitoring.

### Supplementary Tiers

**Procurement Monitor:** Scrapes federal and provincial contract award databases (Open Canada, BuyAndSell, Ontario BPS, BC Bid). Filters for construction and infrastructure contracts at or above $5M. Links awards to existing projects. Zero cost.

**Key People RSS Feeds:** Monitors official feeds for 60+ tracked decision-makers: the PM, Finance Minister, 13 Premiers, 13 provincial Finance Ministers, mayors of the top 15 CMAs, and CEOs of major Crown corporations. These feeds are processed through the government source bypass, skipping keyword filtering entirely.

---

## The 6-Layer Filter

Every article from Tiers 2, 3, 12, and 13 passes through a 6-layer filter before project extraction. The filter's job is to eliminate noise (crime, sports, weather, entertainment) while preserving every article that could describe a capital project.

The filter is deliberately biased toward false positives over false negatives. A sports article that slips through wastes one Gemini Flash classification call (free). A legitimate project article that gets filtered out is a missed project.

### Pre-Filter Step 1: Metadata Tagging

Before entering the filter, every article is tagged with sector and geography using six zero-cost signal layers:

1. **Source domain mapping:** An article from `mining.com` is tagged `mining`. An article from `renx.ca` is tagged `commercial_mixed, residential`.
2. **RSS feed label:** The feed's declared category in `rss_feeds.json`.
3. **RSS category/tag fields:** Category metadata embedded in the RSS entry.
4. **URL path segments:** Geographic and sector signals from the URL structure.
5. **Headline geographic mentions:** Province names, city names, CMA names extracted from the headline.
6. **Headline sector keywords:** NAICS-aligned keyword scan.

These metadata tags flow through to keyword matching (where they can trigger bypasses), Claude extraction (as sector/province hints), and the cross-reference engine.

### Pre-Filter Step 2: Snippet Enhancement

Articles with snippets shorter than 80 characters are enhanced before entering the filter. Many RSS feeds only provide a truncated description.

The primary extractor is **trafilatura**, a purpose-built news article extraction library that handles varied HTML layouts, boilerplate removal, paywall stubs, and navigation stripping. Extracted text is then summarized to 3 sentences using **sumy** (LexRank extractive summarization). Falls back to BeautifulSoup if trafilatura is unavailable.

This improves accuracy at Layer 4 (keyword co-occurrence) and Layer 6 (LLM classification) by giving them more text to work with. Zero API cost. Government sources are skipped since they already bypass Layers 1-2.

### Layer 1: Government Source Bypass

Articles from 50+ government domains skip keyword filtering entirely and jump straight to Layer 6 (Gemini Flash classification). Government sources include federal and provincial newsrooms, regulatory agencies, municipal governments, and Crown corporation news feeds.

The logic: a government announcement about spending money is almost always relevant to a capital project tracker. Filtering it by keywords risks losing legitimate announcements that use unexpected vocabulary.

### Layer 2: Dollar-Value Bypass

Articles containing dollar values at or above the province's GDP-proportional threshold skip Layers 3-5 and proceed directly to Layer 6.

**GDP-proportional thresholds:**

| Province | Threshold |
|----------|-----------|
| Ontario | $500M |
| Quebec | $250M |
| Alberta | $200M |
| British Columbia | $175M |
| Saskatchewan | $45M |
| Manitoba | $40M |
| Nova Scotia | $25M |
| New Brunswick | $20M |
| Newfoundland & Labrador | $17M |
| Prince Edward Island | $5M |
| Yukon / NWT / Nunavut | $3M |

A secondary bypass triggers for any article mentioning a dollar figure (any amount) alongside a Canadian location name. This catches articles like "$12 million Fredericton water treatment plant" that fall below the province threshold but are clearly project-relevant.

### Layer 3: Below-Threshold Dampener

Articles with detected dollar values below their province's threshold require additional strong project signals (multiple keyword matches from Categories A and C) to proceed. This reduces noise from small-dollar stories while still allowing through articles with clear construction or infrastructure language.

### Layer 4: Keyword Co-Occurrence

The core keyword filter. An article passes if it contains:

**(At least 1 from Category A) AND (at least 1 from Category B OR at least 1 from Category C)**

**Category A (~120 project signal keywords)** covers both greenfield and brownfield vocabulary:
- Greenfield: project, construction, facility, plant, tower, terminal, pipeline, mine, dam, reactor, data centre...
- Brownfield: redevelopment, expansion, renovation, conversion, remediation, retrofit, restoration, adaptive reuse, modernization, demolition and rebuild...
- Building types: mixed-use, condo, apartment, long-term care, seniors residence...
- Infrastructure: interchange, tunnel, light rail, wastewater, solar farm, wind farm, carbon capture...
- Milestone terms: sod turning, financial close, groundbreaking, ribbon cutting, substantial completion...
- French: projet, investissement, agrandissement, usine, aménagement...

**Category B (~30 economic signal keywords):**
million, billion, investment, funding, contract, awarded, procurement, budget, financing, capital, infrastructure bank, P3, public-private...

**Category C (~45 status signal keywords):**
proposed, approved, under construction, breaking ground, announced, tender, RFP, permit, environmental assessment, shovel-ready, rezoning approved, contract awarded to...

### Layer 5: Negative Keyword Exclusion

Title-only check against a carefully curated list of reject keywords organized into six categories:

- **Crime:** homicide, murder, assault, robbery, arrest, sentenced, trafficking...
- **Sports:** NHL, CFL, NBA, playoff, roster, championship, Stanley Cup...
- **Entertainment:** concert, album, box office, Grammy, celebrity, recipe...
- **Health (non-facility):** patient, diagnosis, outbreak, vaccination, overdose...
- **Weather:** flood warning, wildfire evacuation, tornado watch, blizzard...
- **Politics (non-spending):** polling, approval rating, leadership race, scandal...

Critically, the negative list does **not** include terms that frequently appear in legitimate project articles: mall, shopping, housing, residential, apartment, condo, office, heritage, downtown, Indigenous, First Nations, film. Previous versions filtered these and lost real projects.

### Layer 6: Gemini Flash Classification

Articles that pass through (or bypass) Layers 1-5 are batch-classified by Gemini 2.5 Flash in groups of 20. The LLM prompt is deliberately inclusive, covering 15 project categories from new builds to data centres to defence procurement.

The classification returns structured JSON for each article:
- `is_relevant`, `is_canadian`, `is_project_related`
- `likely_province`, `likely_sector`, `likely_event_type`
- `confidence`, `has_dollar_value`, `estimated_value_range`
- `likely_source_type`

The key design decision: **uncertain = RELEVANT**. If the model isn't sure whether an article describes a capital project, it passes through. False negatives are more expensive than false positives because a missed project may never resurface.

Gemini Flash runs on the free tier with no grounding enabled. The system never passes `google_search` tool or `groundingConfig` to the API.

---

## Project Extraction

Articles that survive the 6-layer filter are sent to Claude Sonnet for structured project extraction. Claude extracts:

- Project name, proponent, location (city, province, CMA)
- Estimated value (with range handling)
- Status (proposed, approved, under construction, completed, delayed, cancelled)
- Project type (from the 11-type taxonomy)
- Sector (from the 18 NAICS-aligned sectors)
- Description
- Evidence URLs

A separate extraction call processes articles in batch, with sector and province hints from the metadata tagger providing context.

---

## Deduplication & Merge

All raw project mentions from all 14 tiers converge into a single deduplication layer.

**Dedup key:** province + city + normalized name (lowercase, stripped of punctuation and filler words).

When the same project appears from multiple sources, records are **merged**, not overwritten:

- Evidence arrays are combined (URLs are never lost)
- Discovery source lists are combined
- The highest value is kept
- Status advances to the most progressed stage (non-regression rule)
- Missing fields are filled from whichever source has them
- All discovery tiers that found the project are tracked

---

## Confidence Scoring

Every project receives a confidence score on a 0.0-1.0 scale, calculated from multiple factors:

| Factor | Score |
|--------|-------|
| Base score | 0.1 |
| Per evidence source (max 3) | +0.1 each |
| Per government source (max 2) | +0.15 each |
| Verified dollar value | +0.1 |
| Multi-tier discovery | +0.05-0.1 |

Source types are weighted by reliability:

| Source Type | Weight |
|------------|--------|
| Government API | 1.0 |
| Government press release | 0.95 |
| Regulatory filing | 0.90 |
| Securities filing | 0.90 |
| Wire service | 0.75 |
| National media | 0.70 |
| Industry publication | 0.70 |
| Local media | 0.50 |
| Blog/other | 0.30 |

**Confidence decay** applies to projects that aren't re-discovered:

| Days Since Update | Decay |
|-------------------|-------|
| 0-30 | None |
| 31-60 | -0.05 |
| 61-90 | -0.10 |
| 91-120 | -0.15 |
| 121-180 | -0.20, flagged stale |
| 180+ | flagged needs review |

Decay reverses immediately when a project is re-discovered by any tier.

**Editorial thresholds:**
- 0.80+: Confirmed. Included in the main briefing.
- 0.50+: Probable. Included with caveat.
- 0.30+: Watch list. Mentioned in supplementary section.
- Below 0.30: Unverified. Held for next week's corroboration.

---

## Enrichment Pipeline

After discovery and dedup, a budget-constrained enrichment pipeline fills gaps:

1. **Cost-finding** (first priority, 300 Tavily credits/month): Searches for dollar values on projects with no `value_millions`. Crafts queries specifically for budget approvals, procurement awards, and news articles mentioning dollar figures. Quebec and New Brunswick projects get both French and English queries. After 3 failed attempts across 6 weeks, projects are marked `cost_unfindable`.

2. **Named project tracking** (200 credits/month): Re-confirms details on the top 50 projects by value.

3. **Deep verification** (200 credits/month): Verifies single-source projects, looking for corroborating evidence.

4. **General enrichment** (150 credits/month): Fills missing fields (proponent, city, sector).

5. **Signal investigation** (100 credits/month): Follows up on anomalies from building permits and lobbyist registries.

Total Tavily budget: 1,000 credits/month (free tier).

---

## Adaptive Learning

The system learns from its own gaps.

### User-Submitted Missed Projects

Users can submit projects the system missed via a frontend form. Submitted projects immediately enter the database at low confidence (0.2-0.3) and are queued for enrichment and cost-finding.

### Diagnostic Engine

For every missed project submission, a diagnostic engine runs backward through every discovery tier to identify *why* the project was missed. It classifies failures into 8 categories:

1. **VOCABULARY_GAP** - Terminology not in queries or keywords
2. **FILTER_KILL** - RSS filter blocked a valid article (which layer, which keyword)
3. **GEOGRAPHIC_GAP** - City not in any CMA or regional cluster query
4. **SECTOR_GAP** - Sector not in province's affinity matrix
5. **SOURCE_GAP** - Publication not in RSS feed list
6. **LANGUAGE_GAP** - French coverage missing for province-sector pair
7. **VALUE_BELOW_THRESHOLD** - Project value below province threshold
8. **NOVEL_PROJECT_TYPE** - Project type not in taxonomy

### Improvement Application

Each diagnosis generates concrete improvements: new search terms, new RSS feeds, expanded geographic coverage. Improvements are stored in SQLite and categorized:

- **Auto-approved (additive only):** Vocabulary additions, keyword additions, feed additions, French sector expansion
- **Manual review required:** Negative keyword changes, affinity expansion, geographic additions, taxonomy expansion

The system can add queries, keywords, and feeds. It can **never remove** existing ones. This is a hard constraint.

### Autonomous Learning Engine

After each weekly sweep, the learning engine analyzes feedback signals and adjusts pipeline configuration within bounded safety limits:

- **Query effectiveness:** Low-hit queries get demoted to monthly/quarterly frequency (max 30% of queries)
- **Dedup thresholds:** Nudged based on Claude feedback (bounded 0.70-0.95, max 0.02 change per sweep)
- **Source weights:** Adjusted by empirical accuracy (government sources never drop below 0.80)
- **Extraction prompts:** Auto-refined from error patterns every N sweeps
- **Snowball patterns:** Learns from successful follow-up queries

Cold start protection: the first 4 sweeps collect signals only, no optimization. Regression detection: if metrics degrade more than 20%, the last change is automatically rolled back.

### Snowball Discovery

When the pipeline discovers a project, it generates targeted follow-up queries to find related projects. Example chain:

- **Pass 1:** "Alberta energy infrastructure projects 2026" discovers Pembina Pipeline Expansion ($1.2B)
- **Pass 2:** "Pembina Pipeline Expansion regulatory approval IAAC" discovers EA details, timeline, connected compressor stations
- **Pass 3:** "Alberta natural gas compressor station construction 2025 2026" discovers 3 related compressor station projects not in original query list

Stop conditions: max passes reached (default 3), follow-up queries return fewer than 5 new projects, or circuit breaker trips.

---

## URL Hard Gate

Every project in the database must have at least one verifiable source URL. This is enforced at the data model level: the `build_project_document()` function returns `None` if no evidence URL exists. Projects without URLs are rejected from SQLite.

During dedup merges, evidence arrays are always combined, never overwritten. A merge operation can only add URLs to a project, never remove them.

---

## Anomaly Detection

The pipeline flags unusual changes for review:

- **Value spike/drop:** Project value changes more than 30%
- **Status regression:** A project moving backward (e.g., under_construction to proposed)
- **Proponent change:** Different company associated with the same project
- **Location change:** Project appearing in a different province
- **Cross-project duplicates:** Similar names detected across provinces

Anomalies are stored in the project record and displayed on the frontend.

---

## Cost Structure

| Component | Annual Cost |
|-----------|-------------|
| Google News RSS (2,574 queries, unlimited) | $0 |
| Curated RSS feeds (324+) | $0 |
| Google Alerts (~25) | $0 |
| Gemini 2.5 Flash (classification, extraction) | $0 |
| Government registries, SEDAR+, CER | $0 |
| Municipal open data APIs | $0 |
| StatsCan API, Bank of Canada API | $0 |
| Yahoo Finance (market data) | $0 |
| Tavily enrichment (1,000 credits/month free tier) | $0 |
| Key people RSS monitoring | $0 |
| Claude Opus 4.6 (all narrative writing) | ~$120 |
| Claude Sonnet 4.6 (extraction, reasoning) | ~$30 |
| GitHub Pages + Actions (hosting, scheduling) | $0 |
| **Total** | **~$150/year** |

The entire search and discovery layer runs at zero marginal cost. The $150 budget goes entirely to Claude for narrative intelligence: writing the weekly briefing, generating market commentary, producing the Under the Microscope deep-dive, and running extraction and reasoning tasks. Everything else is free.
