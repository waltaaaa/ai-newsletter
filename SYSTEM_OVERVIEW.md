# Signal Dispatch — System Overview

**Canadian Macro Strategic Dashboard**

Signal Dispatch is an autonomous weekly intelligence briefing platform that tracks Canadian national economic conditions, provincial policy, capital projects, commodity markets, and scheduled economic events. A Python pipeline discovers and processes information from 14 source tiers, stores structured data in SQLite, and publishes a static single-page application via GitHub Pages — with no backend server required in production.

The system runs on a ~$60/year budget. Every Monday at 5:30 AM ET, GitHub Actions triggers a full pipeline run. A lighter daily run at midnight ET refreshes economic indicators and market data only.

---

## What It Does

### For the Reader

Each week, Signal Dispatch produces:

1. **A 1,000–1,500 word intelligence briefing** covering the most significant Canadian economic developments, written in neutral Reuters wire-service style with no editorializing
2. **A live project database** tracking hundreds of capital projects across Canada — from $3M territorial builds to multi-billion dollar megaprojects — with status, value, location, proponent, and source evidence
3. **National and provincial economic indicators** pulled directly from primary government APIs (Bank of Canada, Statistics Canada, CMHC) with period-over-period changes
4. **Commodity and market tracking** for 21 commodities, 7 equity indices, and 4 FX pairs, with commentary connecting price movements to specific Canadian projects
5. **A Data Explorer** for searching Statistics Canada's catalogue by natural language (backed by 120+ curated V-code entries)
6. **PDF and DOCX exports** of the weekly briefing for offline distribution

### For the Operator

The pipeline is designed to run unattended. It handles API failures gracefully (retries, bail-outs, fallbacks), tracks its own cost per run, logs structured pipeline metrics, and self-improves through an adaptive learning system that adds new search queries and RSS feeds when users report missed projects.

---

## How It Works — End to End

### Phase 1: Hard Data Collection (No AI)

Before any AI model is invoked, the pipeline collects factual data from government and market APIs. These values are treated as ground truth and will override any AI-generated estimates later in the pipeline.

| Source | Data | Method |
|--------|------|--------|
| Bank of Canada Valet API | Overnight rate, 6 GoC yield terms | REST JSON |
| Statistics Canada WDS | CPI, unemployment, GDP, 20 industry GDP, 10 provincial unemployment/CPI/GDP | Batch POST (vector IDs) |
| CMHC | Housing starts (national + provincial) | HTML scrape of news releases |
| FRED | US rate, unemployment, CPI, GDP; UK/EU GDP | CSV download (no key) |
| ECB SDW | Deposit rate, HICP, unemployment | REST JSON |
| Bank of England IADB | Bank rate | CSV download |
| World Bank | China GDP, CPI | REST JSON |
| Yahoo Finance | 21 commodities, 7 equity indices, 4 FX pairs | yfinance library (12hr cache) |
| StatCan JSON | 71 key economic indicators | JSON feed |

All values are archived to the `indicator_history` table for trend analysis and sparkline rendering.

### Phase 2: 14-Tier Discovery Pipeline

The discovery pipeline searches for capital project announcements, status changes, and new developments across Canada. Each tier targets a different source type, from federal registries to municipal development applications.

**Tier 1 — Federal Registries**
IAAC (Impact Assessment Agency of Canada), BC EAO (JSON API), NRCan major projects inventory, Infrastructure Canada (JSON export), CanadaBuys (CSV stream), Canada Energy Regulator, Ontario Environmental Registry. Government-verified projects enter with high confidence (0.8).

**Tier 2 — Google News RSS (759 queries)**
759 compound search queries (e.g., "mining project Saskatchewan 2026") are converted to Google News RSS feed URLs. Each is polled via feedparser with 30x parallelism. This tier replaced Gemini grounded search, which was costing $136/day. Google News RSS is free and unlimited.

**Tier 3 — GDELT**
~200 queries against the GDELT DOC 2.0 API for global news coverage of Canadian projects. Operates over HTTP only (HTTPS is ISP-blocked). Bails out after 3 consecutive failures to avoid hanging the pipeline.

**Tier 4 — RSS Feeds (201+ feeds)**
Government newsrooms (13 provincial + federal departments), national/regional media (CBC, CTV, Globe, Postmedia), industry trade publications (Daily Commercial News, Mining.com, JWN Energy, RENX, On-Site, Canadian Architect — 15+ feeds), and French media. All articles pass through the 6-layer filter (described below).

**Tier 5 — Provincial EA Registries (13)**
Scrapers for all 13 provincial/territorial environmental assessment registries. BC EAO uses a structured JSON API; others use HTML scraping.

**Tier 6 — SEDAR+ Securities Filings**
Searches SEDAR+ for capital project disclosures in NI 43-101 technical reports, material change reports, and MD&A sections.

**Tier 7 — Crown Corporation Capital Plans (25+)**
Monitors published capital plans from power utilities (Hydro-Québec, BC Hydro, OPG, SaskPower, Manitoba Hydro), transit agencies (Metrolinx, TransLink), port and airport authorities, Canada Post, VIA Rail, and the Canada Infrastructure Bank.

**Tier 8 — Canada Energy Regulator**
CER project database for pipeline, power line, LNG, and offshore energy filings. Separate regulatory body from IAAC.

**Tier 9 — StatsCan Building Permits (Signal)**
Pulls monthly building permit data for 20 CMAs. Flags municipalities where permit values exceed 3x their 12-month moving average. These anomalies generate investigation queries — they don't create project records directly.

**Tier 10 — Lobbyist Registries (Signal)**
Federal Office of the Commissioner of Lobbying + provincial registries. Searches for registrations mentioning construction, infrastructure, permits, or environmental assessment. Another signal tier that produces investigation targets.

**Tier 11 — Municipal Development Applications (15 CMAs)**
Open Data APIs (Socrata/CKAN) for Vancouver, Calgary, Edmonton, Winnipeg. HTML portal scraping for Toronto, Ottawa, Halifax, Hamilton, Quebec City, Saskatoon, Regina, St. John's, Charlottetown, Fredericton, and others. These catch projects months or years before media coverage.

**Tier 12 — Google Alerts (~25 queries)**
RSS-delivered Google Alerts for terms like "billion dollar project Canada," "mine approved Canada," "projet majeur construction Canada." Feed directly into the RSS filter pipeline.

**Tier 13 — Industry Trade RSS (~15 feeds)**
Construction and resource industry publications. Tagged as high-signal — almost everything passes the filter.

**Tier 14 — University/Institutional Capital Plans**
U15 research universities, major colleges/polytechnics (BCIT, SAIT, George Brown), and healthcare institutions (SickKids, MUHC). Annual scrape plus quarterly news monitoring.

**Plus: Key People RSS**
15 RSS feeds tracking PM office, premiers, and crown corporation executives. Processed through the government bypass path.

### The 6-Layer RSS Filter

Every article from Tiers 2, 4, 12, and 13 passes through this filter. Order matters — earlier layers can bypass later ones.

```
Article arrives
    │
    ├─ Layer 1: Government source? ──yes──► Skip to Layer 6
    │
    ├─ Layer 2: Dollar value ≥ province GDP threshold? ──yes──► Skip to Layer 6
    │
    ├─ Layer 3: Below-threshold dampener (detected value below threshold → needs strong signals)
    │
    ├─ Layer 4: Keyword co-occurrence (~80 project keywords × ~30 economic keywords)
    │           No match → REJECT
    │
    ├─ Layer 5: Negative keywords (crime/sports/weather ONLY — not mall, housing, office, heritage)
    │           Match → REJECT
    │
    └─ Layer 6: Gemini Flash classification (uncertain = RELEVANT → extraction pipeline)
```

Province GDP thresholds scale with provincial economy size: Ontario $500M, Quebec $250M, Alberta $200M, BC $175M, down to PEI $5M and territories $3M.

### Phase 3: AI Analysis

After discovery, three AI models process the results. Their roles are strictly separated.

**Gemini 2.5 Flash (free tier, no grounding)**
- Article classification (Layer 6 of the RSS filter)
- Structured field extraction from article text
- JSON repair when Claude responses fail to parse
- Enrichment queries to fill missing project fields (≤100/day)
- Under the Microscope topic selection
- V-code search fallback for the Data Explorer

Gemini is **never** called with `google_search` tool or `groundingConfig` — that would enable grounding fees at $35 per 1,000 queries.

**Claude Sonnet 4.6 (~$55/year)**
All reasoning and writing tasks:
- Executive summary and national analysis
- Industry analysis (20 NAICS sectors)
- Provincial analysis (13 provinces)
- Structured project extraction from discovered articles
- Gap analysis (identifies discovery blind spots)
- Extraction recovery (retries failed articles)
- Dedup QA (flags probable duplicates)
- Monthly meta-analysis (full database review)
- Market commentary (200–300 words)
- Pre-event analysis (150–250 words per event)
- Under the Microscope deep-dive (200–300 words)
- Weekly briefing synthesis (1,000–1,500 words, 8 sections)
- Policy impact assessment

**Tavily (1,000 credits/month free tier)**
Targeted enrichment only — not broad search:
- Cost-finding for projects with no dollar value (300 credits)
- Named project tracking for top 50 by value (200 credits)
- Deep verification for single-source projects (200 credits)
- Enrichment for missing fields (150 credits)
- Signal investigation follow-ups (100 credits)

### Phase 4: Hard Data Override

After Claude writes the analysis payload, authoritative API values overwrite all indicators. This ensures no AI-generated estimate ever replaces a real data point. The pipeline logs any mismatches between AI output and API values.

### Phase 5: Project Processing Pipeline

All discovered projects — from every tier — flow through a standardized pipeline:

1. **Cross-tier deduplication** — Normalized key (province + city + name) plus fuzzy matching (SequenceMatcher ≥ 0.85). Same project from multiple tiers merges: evidence arrays combine, highest value kept, most advanced status preserved, missing fields filled.

2. **URL hard gate** — Every project must have at least one verifiable source URL. No URL = no database write. This is non-negotiable.

3. **SQLite upsert** — Status never regresses (proposed can become approved, but not the reverse). Evidence merge never loses URLs. All discovery sources tracked.

4. **Post-upsert enrichment:**
   - Tavily cost-finding for projects missing dollar values
   - Gemini enrichment for missing proponent/status fields
   - Wayback Machine archival of source URLs (up to 20/run)
   - Stale project check (28+ days unseen)
   - Evidence URL verification (HEAD requests)
   - Confidence decay (31–120+ day schedule)
   - Lifecycle monitoring (Gemini checks for status transitions)
   - Cross-project anomaly detection

### Phase 6: Narrative Generation

The pipeline generates the weekly briefing and supporting analysis:

| Component | AI Model | Output |
|-----------|----------|--------|
| Sector trends | SQL only | Project counts/values by sector |
| Indicator trends | SQL only | Trends from indicator_history |
| Cross-reference | Code only | Links indicator moves to project counts |
| Trend report | Claude Sonnet | Narrative combining all three |
| Policy monitor | RSS only | Provincial policy developments |
| Market commentary | Claude Sonnet | Factual commodity analysis |
| Event calendar | Code only | BoC dates, StatsCan releases |
| Pre-event analysis | Claude Sonnet | High-significance event previews |
| Under the Microscope | Gemini (topic) + Claude (analysis) | 200–300 word deep-dive |
| Weekly briefing | Claude Sonnet | 8 sections, 1,000–1,500 words |
| Briefing export | reportlab + python-docx | PDF + DOCX files |

### Phase 7: Export and Deployment

1. Source verification — concurrent HEAD requests, dead URLs cleared, Wayback archived
2. Timeseries append — one data point per tracked variable for sparklines
3. Final assembly — full JSON payload saved to `dashboard_state`
4. Quality report — pipeline metrics logged to `pipeline_runs`
5. Static JSON export — `export_dashboard.py` writes 28+ files to `docs/data/`
6. Deploy — `deploy_to_github.py` copies `public/` → `docs/`, git commit + push

---

## Architecture

### Data Flow

```
DISCOVERY                    PROCESSING                  STORAGE            DELIVERY
─────────────────────────── ─────────────────────────── ──────────────────── ────────────
Google News RSS (759)  ───┐
Gov Registries (9)     ───┤  6-layer RSS filter
GDELT (~200)           ───┤  ───────────────────►
RSS Feeds (~201)       ───┤  Claude extraction
Municipal Apps (15)    ───┤  ───────────────────►          dashboard.db
Institutional (20)     ───┤  Cross-tier dedup              (SQLite WAL)
StatCan Permits (20)   ───┤  URL hard gate                 ──────────────►
Lobbyist Registry      ───┤  Evidence merge                                  docs/data/
Google Alerts (25)     ───┘  Status non-regression                           *.json
                             Confidence scoring                              ──────────►
                             ───────────────────►
BoC Valet API      ────────► Hard data override                              GitHub Pages
StatCan WDS        ────────► (API values always win)                         (CDN)
FRED / ECB / BoE   ────────►                                                 ──────────►
Yahoo Finance      ────────►
CMHC               ────────►                                                 Browser
World Bank         ────────►                                                 (app.js SPA)
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| Pipeline | Python 3.12, async (aiohttp), concurrent.futures |
| Database | SQLite in WAL mode, FTS5 for full-text search |
| Frontend | Static HTML + JS SPA (no framework) |
| Styling | Tailwind CSS (CDN) + custom CSS properties |
| Charts | Chart.js 4.4.1 + chartjs-plugin-annotation |
| Visualization | D3 7.8.5 + d3-cloud (word cloud) |
| Sanitization | DOMPurify 3.0.6 |
| Fonts | Neue Haas Grotesk Display Pro + JetBrains Mono |
| Hosting | GitHub Pages (static CDN, free) |
| CI/CD | GitHub Actions (2 workflows) |
| PDF export | reportlab |
| DOCX export | python-docx |

### Database Schema

SQLite database (`dashboard.db`) in WAL mode with 14 tables. All access goes through `db.py`.

| Table | Purpose |
|-------|---------|
| `projects` | Main project database with FTS5 triggers |
| `projects_fts` | FTS5 virtual table for full-text search |
| `projects_archive` | Soft-deleted / superseded projects |
| `indicator_history` | Time series for all economic indicators |
| `trend_snapshots` | Weekly trend analysis snapshots (JSON) |
| `weekly_briefings` | Generated briefings (sections JSON, pdf/docx URLs) |
| `dashboard_state` | Key-value store (latest briefing, microscope, credits) |
| `pipeline_runs` | Structured run logs (steps, errors, API usage) |
| `missed_projects` | User-submitted missing projects (GitHub Issues) |
| `pipeline_improvements` | Adaptive learning improvements (additive only) |
| `statcan_indicators` | StatCan 71-indicator snapshot |
| `timeseries` | Commodity/market time series (sparklines) |
| `newsletters` | Legacy newsletter collection |
| `pipeline_state` | Follow-up queries, misc state |

### Project Data Model

**11 project types:** greenfield, redevelopment, adaptive_reuse, major_renovation, expansion, retrofit, restoration, remediation, conversion, modernization, decommission_replace

**18 NAICS-aligned sectors:** oil_gas, mining, infrastructure, power_energy, manufacturing, transport_logistics, healthcare, education, residential, commercial_mixed, agriculture, forestry, defence, telecom, indigenous, environment, tourism_culture, government

**Status progression:** Rumoured → Proposed → Under Review → Approved → Under Construction → Partially Complete → Complete. Terminal states: Cancelled, On Hold, Suspended, Paused. Status never regresses during merge.

**Confidence scoring:**
- Base: 0.1
- +0.1 per evidence source (max 0.3)
- +0.15 per government source (max 0.3)
- +0.1 for verified dollar value
- +0.05–0.1 for multi-tier discovery
- Decay: -0.05 at 31 days, -0.10 at 61, -0.15 at 91, -0.20 at 121+ (flagged stale)

### Frontend

The frontend is a static single-page application with no backend. All data is pre-rendered as JSON files in `docs/data/` and served by GitHub Pages CDN.

**Tabs:**

| Tab | Content |
|-----|---------|
| Overview | Executive summary, word cloud, key metrics |
| Macro | National indicators, indicator explorer with historical charts |
| Industries | 20 NAICS sector analysis, yield curve with toggle |
| Provinces | Per-province analysis, projects, indicators |
| Projects | Searchable/filterable database with cards showing type/status/confidence badges, evidence sources, anomalies |
| Briefing | 8-section weekly briefing, archive, PDF/DOCX download |
| Markets | Commodity cards, equities, yield curve |
| Data Explorer | Natural language StatCan search (120+ V-codes, Gemini fallback) |

### Scheduling

| Workflow | Schedule | Scope |
|----------|----------|-------|
| `weekly-pipeline.yml` | Monday 5:30 AM ET | Full pipeline: discovery + analysis + briefing + export |
| `daily-indicators.yml` | Daily midnight ET | Hard data only: BoC, StatCan, markets, export |

### CLI Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Weekly: 7-day lookback, all tiers, full analysis |
| `--indicators-only` | Daily: hard data + export only, skip discovery |
| `--deep-sweep` | Monthly: 30-day lookback, full Wayback backfill |
| `--seed-projects` | One-time project seed |
| `--test-feeds` | Test all RSS feed URLs |
| `--audit-citations` | Verify all source URLs |

---

## Key Design Principles

### Primary API Always Wins
No AI model is trusted to produce economic indicator values. The pipeline fetches from government APIs first, then overwrites any AI-generated figures. If an API is unavailable, the frontend shows "N/A" with a tooltip — never a fabricated number.

### URL Hard Gate
Every project in the database must have at least one verifiable source URL. Projects without evidence are rejected at write time. During deduplication, evidence arrays are always merged — never overwritten.

### Status Non-Regression
When the same project is discovered from multiple tiers, the merge logic always advances to the highest status. A project that was "under construction" from one source won't be downgraded to "proposed" because another source is outdated.

### Additive Only
The adaptive learning system can add queries, keywords, and RSS feeds. It can never remove them. This prevents the system from accidentally narrowing its own discovery aperture.

### No Editorializing
All generated content — briefings, market commentary, policy assessments — must be factual reporting. The system presents data, context, and connections. It never takes positions, makes recommendations, or uses evaluative language (good, bad, promising, concerning, bullish, bearish).

### Budget Discipline
The entire system runs on ~$60/year. Claude Sonnet handles all reasoning (~$55/year). Google News RSS and Gemini Flash are free. Tavily's free tier provides 1,000 credits/month. No paid search services. No grounded search. No premium model tiers.

---

## Error Handling

- All discovery tiers: `try/except` → `[WARN]` + continue (no tier failure crashes the pipeline)
- Claude API: 4 retries with exponential backoff (1s → 8s), JSON parse failure → Gemini Flash repair
- StatCan WDS: 1 retry after 5s
- BoC Valet: 1 retry after 5s
- CMHC: tries last 4 months to handle publication lag
- GDELT: bail-out after 3 consecutive failures
- Yahoo Finance: 12hr cache shields API instability
- URL verification: HEAD with 5s timeout, 12 concurrent workers
- Claude Opus 404: automatic Sonnet fallback
- Pipeline logger: every step logged to `pipeline_runs` table with error counts and API usage

---

## Repository Structure

```
AI newsletter/
├── update_dashboard.py           # Master pipeline (~4150 lines)
├── db.py                         # SQLite interface (14 tables, FTS5)
├── pipeline_config.py            # Model routing, thresholds
├── export_dashboard.py           # SQLite → docs/data/*.json
├── deploy_to_github.py           # public/ → docs/ for GitHub Pages
│
├── ── Discovery (14 tiers) ──
├── gov_sources.py                # Tier 1,5,8: government registries
├── google_news_rss_search.py     # Tier 2: 759 queries → RSS
├── gdelt_monitor.py              # Tier 3: GDELT DOC 2.0
├── rss_monitor.py                # Tier 4,12,13: 201+ feeds
├── municipal_dev_apps.py         # Tier 11: 15 CMAs
├── institutional_capital.py      # Tier 14: universities, hospitals
├── statcan_permits.py            # Tier 9: permit anomaly detection
├── lobbyist_registries.py        # Tier 10: lobbyist signals
├── key_people_tracker.py         # Key people RSS feeds
│
├── ── AI / Reasoning ──
├── claude_reasoning.py           # Claude Sonnet: all reasoning
├── gemini_engine.py              # Gemini Flash: classification
├── weekly_briefing.py            # 8-section briefing generation
├── under_the_microscope.py       # Weekly deep-dive
├── briefing_export.py            # PDF + DOCX export
│
├── ── Project Processing ──
├── article_filter.py             # 6-layer RSS filter
├── project_dedup.py              # Cross-tier deduplication
├── project_sync.py               # SQLite upsert with merge logic
├── confidence_decay.py           # Score decay schedule
├── tavily_search.py              # Targeted enrichment (1000/mo)
├── cost_finder.py                # Cost search for valueless projects
│
├── ── Analysis ──
├── sector_trends.py              # Sector project counts/values
├── indicator_trends.py           # M/M and Y/Y computations
├── cross_reference.py            # Indicator → project linkage
├── canadian_markets.py           # Market data + commentary
├── event_calendar.py             # Economic event calendar
│
├── ── Frontend ──
├── public/
│   ├── index.html                # Shell HTML
│   └── js/app.js                 # SPA logic (~1400+ lines)
├── docs/                         # GitHub Pages root
│   ├── index.html
│   ├── js/app.js
│   └── data/                     # 28+ static JSON files
│       ├── indicators.json
│       ├── projects_all.json
│       ├── projects_{province}.json  (×13)
│       ├── briefing_latest.json
│       ├── timeseries.json
│       ├── events.json
│       ├── pipeline_status.json
│       └── manifest.json
│
├── ── Config / Data ──
├── dashboard.db                  # SQLite database (WAL mode)
├── .env                          # API keys (not committed)
├── compound_queries_final.json   # 759 compound queries
├── rss_feeds.json                # 201+ feed inventory
├── watchlist.json                # Verified officials list
└── requirements.txt              # Python dependencies
```

---

## Cost Breakdown

| Service | Annual Cost | Usage |
|---------|-------------|-------|
| Claude Sonnet 4.6 | ~$55 | All reasoning, briefing, analysis |
| Gemini 2.5 Flash | $0 | Classification, extraction (free tier, no grounding) |
| Google News RSS | $0 | 759 queries, unlimited polling |
| Tavily | $0 | 1,000 credits/month free tier |
| GitHub Pages | $0 | Static hosting |
| GitHub Actions | $0 | CI/CD (free for public repos) |
| Yahoo Finance | $0 | yfinance library |
| FRED / ECB / BoE / World Bank | $0 | Open data APIs |
| **Total** | **~$60/year** | |
