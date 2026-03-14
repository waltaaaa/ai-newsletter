# CAN-MACRO Strategic Dashboard — System Architecture

> Signal Dispatch: Weekly Canadian economic intelligence platform. Python pipeline → SQLite → static JSON → GitHub Pages.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GITHUB ACTIONS                               │
│  weekly-pipeline.yml (Mon 10:30 UTC / 5:30 AM ET) — full pipeline  │
│  daily-indicators.yml (Daily 05:00 UTC / midnight ET) — data only  │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  update_dashboard.py (~4150 lines)                   │
│                                                                     │
│  Step 1:  Hard data (6 APIs, no AI)                                 │
│  Step 1b: Primary source indicators (StatCan, CMHC, FRED, ECB, BoE)│
│  Tier 1-14: Discovery pipeline (14 tiers)                           │
│  Step 3:  Claude analysis (4 API calls)                             │
│  Step 4:  Hard-data injection (API values override AI)              │
│  Step 2J: User submissions (GitHub Issues)                          │
│  Step 2K: Claude reasoning (gap analysis, dedup QA, meta-analysis)  │
│  Step 2M: Trend analysis (sector, indicator, cross-reference)       │
│  Step 2N: Narrative pipeline (markets, events, microscope, briefing)│
│  Step 2G: Structured signals (permits, lobbyists)                   │
│  Step 5:  Source verification + Wayback archival                    │
│  Step 6:  Timeseries append                                        │
│  Step 7:  Final assembly → dashboard_state                          │
│  Step 8:  Quality report → pipeline_runs                            │
│  Step 9:  Static JSON export → docs/data/                           │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
          ┌────────────┼────────────────┐
          ▼            ▼                ▼
   ┌─────────────┐  ┌───────────┐  ┌──────────────┐
   │  14 Discovery│  │ AI Engine │  │  Hard Data   │
   │  Tiers       │  │ (3 models)│  │  (6+ APIs)   │
   └──────┬──────┘  └─────┬─────┘  └──────┬───────┘
          │                │               │
          └────────────────┼───────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SQLite (dashboard.db) — WAL mode                  │
│                    db.py — single interface module                   │
│                    14 tables + FTS5 triggers                         │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              export_dashboard.py → docs/data/*.json (28+ files)     │
│              deploy_to_github.py → public/ → docs/                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                    git add + commit + push
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GitHub Pages (docs/)                                    │
│              Static SPA: index.html + js/app.js                     │
│              Tailwind CSS + Chart.js + D3                           │
│              No server — all data is static JSON                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Repository Layout

```
AI newsletter/
├── update_dashboard.py         # Master pipeline entry point
├── deploy_to_github.py         # public/ → docs/ copy
├── export_dashboard.py         # SQLite → docs/data/*.json
├── db.py                       # Single SQLite interface module
├── pipeline_config.py          # Model routing, thresholds, dedup config
├── pipeline_logging.py         # Structured run logger → pipeline_runs table
├── pipeline_cache.py           # In-memory + SQLite TTL cache
├── pipeline_state.py           # Follow-up query storage
│
├── ── DISCOVERY (14 tiers) ──
├── google_news_rss_search.py   # Tier 2: 759 queries → Google News RSS
├── rss_monitor.py              # Tier 4: ~201 RSS feeds, 6-layer filter
├── gov_sources.py              # Tier 1: IAAC, BC EAO, NRCan, Infra CAN, CanadaBuys, CER, ERO
├── municipal_dev_apps.py       # Tier 11: 15 CMAs (Socrata/CKAN/HTML)
├── institutional_capital.py    # Tier 14: U15 universities, polytechnics, hospitals
├── statcan_permits.py          # Tier 9: Building permit anomaly detection
├── lobbyist_registries.py      # Tier 10: Federal lobbyist registry
├── key_people_tracker.py       # Key people RSS (PM, premiers, ministers)
├── google_alerts.py            # Tier 12: 25 Google Alert RSS feeds
├── gdelt_monitor.py            # Tier 3: GDELT DOC 2.0 (~200 queries)
├── known_project_sweep.py      # One-time: ~208 queries + 47 hardcoded seeds
│
├── ── FILTERING / DEDUP ──
├── article_filter.py           # 6-layer article filter
├── project_dedup.py            # Cross-tier deduplication
├── project_schema.py           # normalize_project_type, is_brownfield
├── project_sync.py             # upsert_projects, upsert_flat_projects
├── confidence_decay.py         # 30/60/90/120-day decay
├── lifecycle_monitor.py        # Gemini status checks for tracked projects
│
├── ── AI / REASONING ──
├── claude_reasoning.py         # Claude Sonnet: all reasoning tasks
├── gemini_engine.py            # Gemini Flash classification helpers
├── enrichment_queries.py       # Gemini Flash: fill missing value/status
├── under_the_microscope.py     # Topic selection + deep-dive analysis
├── weekly_briefing.py          # 8-section weekly briefing generation
├── briefing_export.py          # PDF (reportlab) + DOCX (python-docx)
│
├── ── ANALYSIS ──
├── sector_trends.py            # Sector project counts/values
├── indicator_trends.py         # Economic indicator trends
├── cross_reference.py          # Links indicator moves to projects
├── weekly_trend_report.py      # Narrative trend report
├── anomaly_detection.py        # Cross-province duplicate detection
├── canadian_markets.py         # Commodity data + market commentary
├── provincial_policy_monitor.py# Policy RSS monitoring
├── event_calendar.py           # BoC dates, StatsCan releases
├── citation_audit.py           # Footnote verification
│
├── ── SEARCH ──
├── tavily_search.py            # Targeted Tavily (1000 credits/mo free)
├── cost_finder.py              # Tavily-powered cost search for valueless projects
├── perplexity_search.py        # Legacy (removed from pipeline; reference only)
│
├── ── DATA QUALITY ──
├── url_utils.py                # URL normalization for dedup
├── url_verifier.py             # Async URL verification with retry
├── url_verify.py               # Sync URL verification, quick_reject()
├── wayback.py                  # Wayback Machine save + backfill snapshots
├── deep_verification.py        # Deep project URL verification with Wayback fallback
├── quality_report.py           # Pipeline quality metrics report
├── learning_store.py           # Adaptive learning (additive only)
├── github_issues_reader.py     # Read user submissions via GitHub Issues API
├── missed_project_enrichment.py# Process pending user submissions via Tavily
├── missed_project_diagnostics.py# Diagnostic tools for missed project analysis
├── dedup_audit.py              # Deduplication quality audit
├── coverage_audit.py           # Geographic + sector coverage gap audit
│
├── ── SEEDING / ONE-TIME ──
├── seed_projects.py            # Legacy one-time project seeder
├── seed_projects_v2.py         # Full rebuild (Tier 1 → GDELT+Claude → Perplexity)
├── known_project_sweep.py      # ~208 Gemini queries + 47 hardcoded seeds
├── generate_compound_queries.py# Generates compound_queries_final.json
├── compound_queries.py         # Compound query builder logic
├── historical_backfill.py      # Historical indicator backfill
├── backfill_indicator_history.py
├── backfill_commodity_timeseries.py
├── backfill_descriptions.py
├── backfill_frontend_data.py
├── backfill_global_indicators.py
├── backfill_project_fields.py
├── backfill_project_values.py
├── backfill_timeseries.py
│
├── ── MISC UTILITIES ──
├── named_tracker.py            # Named entity tracking across runs
├── sentiment.py                # Consumer sentiment (Reddit, Google Trends)
├── statcan_table_registry.py   # Generates statcan_tables.json for Data Explorer
├── convert_watchlist.py        # Converts watchlist CSV → watchlist.json
│
├── ── TESTS ──
├── test_compound_queries.py
├── test_rss_filter.py
├── test_dedup.py
├── test_brownfield_discovery.py
├── test_db.py
│
├── ── DATA / CONFIG ──
├── dashboard.db                # SQLite database (WAL mode, 14 tables)
├── .env                        # API keys, model IDs, feature flags (not committed)
├── compound_queries_final.json # 759 compound queries
├── rss_feeds.json              # Feed inventory (~201 feeds, 6 categories)
├── watchlist.json              # Verified officials list (PM, ministers, premiers)
├── requirements.txt            # Python dependencies
│
├── ── FRONTEND ──
├── public/
│   ├── index.html              # Shell HTML (Tailwind, Chart.js, D3)
│   └── js/app.js               # SPA logic (~1400+ lines)
└── docs/                       # GitHub Pages root
    ├── index.html              # Deployed from public/
    ├── 404.html                # GitHub Pages 404
    ├── js/app.js               # Deployed from public/
    └── data/                   # Static JSON (written by export_dashboard.py)
        ├── indicators.json           # National/provincial/global/industry
        ├── projects_all.json         # All projects combined
        ├── projects_{province}.json  # ×13 province-specific files
        ├── briefing_latest.json      # Current week briefing
        ├── briefing_archive.json     # Historical briefings
        ├── timeseries.json           # Market/commodity time series
        ├── trends.json               # Sector trend snapshots
        ├── events.json               # Upcoming economic events
        ├── microscope.json           # Under the Microscope analysis
        ├── pipeline_status.json      # Last pipeline run status
        ├── statcan_tables.json       # Data Explorer table registry
        └── manifest.json             # Build metadata
```

---

## GitHub Actions Scheduling

### `weekly-pipeline.yml` — Full Run
- **Schedule:** Monday 10:30 UTC (5:30 AM ET)
- **Trigger:** Also `workflow_dispatch` (manual)
- **Steps:** Checkout → Python 3.12 → `pip install` → `python update_dashboard.py` → `python deploy_to_github.py` → git commit/push docs/
- **Env:** `GEMINI_SEARCH_ENABLED=false`, `GEMINI_MODEL=gemini-2.5-flash`, `SONNET_MODEL=claude-sonnet-4-6`

### `daily-indicators.yml` — Indicator Refresh
- **Schedule:** Daily 05:00 UTC (midnight ET)
- **Runs:** `python update_dashboard.py --indicators-only`
- **Purpose:** Fresh BoC rate, StatCan indicators, commodity prices without full discovery

---

## Pipeline Execution Order

### Step 1 — Hard Data (No AI)

| Source | What | API |
|--------|------|-----|
| Yahoo Finance | 21 commodities, 7 equity indices, 4 FX pairs | yfinance (12hr cache) |
| BoC Valet | Overnight rate (V39079), 6 GoC yield terms | REST JSON |
| StatCan WDS | CPI, unemployment, GDP, 10 provincial unemployment, 10 provincial CPI, 10 provincial GDP, 20 industry GDP | POST JSON (batch vectors) |
| CMHC | Housing starts (national + provincial) | HTML scrape of news releases |
| FRED | US rate, unemployment, CPI, GDP; UK/EU GDP | CSV download (no key) |
| ECB SDW | Deposit rate, HICP, unemployment | REST JSON |
| BoE IADB | Bank rate | CSV download |
| World Bank | China GDP, CPI | REST JSON |
| StatCan JSON | 71 key economic indicators | JSON feed |
| RSS feeds | ~201 feeds fetched concurrently | feedparser |

All values archived to `indicator_history` table for trend analysis.

### Step 2 — 14-Tier Discovery Pipeline

```
Tier 1:  Federal Registries ──── IAAC, BC EAO, NRCan, Infra CAN, CanadaBuys, CER, ERO, CIB, Metrolinx
Tier 2:  Google News RSS ─────── 759 compound queries → free RSS feeds
Tier 3:  GDELT ────────────────── ~200 queries (HTTP only, bail-out after 3 failures)
Tier 4:  RSS Feeds ────────────── ~201 feeds through 6-layer filter
Tier 5:  Provincial EA ────────── 10 registries (QC BAPE, AB, SK, MB, NS, NB, NL, YT, NWT)
Tier 6:  SEDAR+ ───────────────── Securities filings (via Tavily extract)
Tier 7:  Crown Corps ──────────── CIB, Metrolinx (via Tier 1)
Tier 8:  Canada Energy Regulator── CER applications (via Tier 1)
Tier 9:  StatCan Permits ──────── 20 CMAs, anomaly threshold 3.0x 12-month MA
Tier 10: Lobbyist Registry ────── Federal bulk CSV, infrastructure keyword filter
Tier 11: Municipal Dev Apps ───── 15 CMAs (Socrata/CKAN APIs + HTML portals)
Tier 12: Google Alerts ────────── 25 alert queries (RSS delivery)
Tier 13: Industry Trade RSS ───── 22 feeds (included in Tier 4)
Tier 14: Institutional Capital ── U15 universities, polytechnics, hospitals
```

### RSS Filter (6 layers — order matters)

```
Article → L1: Government source? ──yes──► skip to L6
         │ no
         L2: Dollar value ≥ province threshold? ──yes──► skip to L6
         │ no
         L3: Below-threshold dampener
         │
         L4: Keyword co-occurrence (~80 project + ~30 economic keywords)
         │ no match → REJECT
         L5: Negative keywords (crime/sports/weather ONLY)
         │ match → REJECT
         L6: Gemini Flash classification (uncertain = RELEVANT)
         │
         ▼
     PASS → extraction pipeline
```

### Step 3 — Claude Analysis (4 API calls)

| Call | Model | Output |
|------|-------|--------|
| 1 | Claude Opus | Executive summary, national analysis, global vectors, watchlist, consumer pulse, word cloud |
| 2 | Claude Sonnet | Industry analysis (5 goods + 15 services sectors), yield curve, charts |
| 3 | Claude Sonnet | All 13 provinces (analysis bullets, indicators, projects) |
| 4 | Claude Sonnet | Structured project extraction from discovered articles |

- 4 retry attempts with exponential backoff per call
- JSON parse failure → Gemini Flash repair
- Opus 404 → automatic Sonnet fallback
- Post-call citation audit removes unsourced claims

### Step 2K — Claude Reasoning Layer

| Task | Purpose |
|------|---------|
| Gap analysis | Identify provincial discovery gaps → follow-up queries |
| Extraction recovery | Retry failed RSS articles with Claude |
| Dedup QA | Flag probable duplicates in new projects |
| Meta-analysis | Monthly full database review (first 7 days of month) |

### Post-Extraction — Project Pipeline

```
All discovered projects
        │
        ▼
Cross-tier dedup (norm_key + fuzzy 0.85)
        │
        ▼
URL hard gate (must have evidence URL)
        │
        ▼
upsert to SQLite (status non-regression, evidence merge)
        │
        ├── Tavily cost-finding (projects with no dollar value)
        ├── Gemini enrichment (fill missing fields, ≤100 queries/day)
        ├── Wayback Machine backfill (up to 20/run)
        ├── Stale project check (28+ days unseen)
        ├── Evidence URL verification (HEAD requests)
        ├── Confidence decay (31-120+ days)
        ├── Lifecycle monitoring (Gemini status checks)
        └── Cross-project anomaly detection
```

### Steps 4a-4g — Hard Data Override

After Claude writes the payload, authoritative API values overwrite all indicators:
- Commodities, markets, yields (Yahoo Finance / BoC Valet)
- National metrics: bocRate, CPI, unemployment, housingStarts, GDP
- Global indicators: US/EU/UK/China (FRED/ECB/BoE/World Bank)
- Provincial indicators (StatCan WDS)
- Industry M/M and Y/Y (StatCan Table 36-10-0434-01)
- `validate_indicators()` cross-checks and logs any mismatches

### Steps 2M-2P — Analysis & Briefing

| Component | AI Model | Output |
|-----------|----------|--------|
| Sector trends | None (SQL) | Project counts/values by sector |
| Indicator trends | None (SQL) | Trends from indicator_history |
| Cross-reference | None (code) | Links indicator moves to project counts |
| Trend report | Claude Sonnet | Narrative combining all three |
| Policy monitor | None (RSS) | Provincial policy developments |
| Market commentary | Claude Sonnet | Factual commodity analysis |
| Event calendar | None (code) | BoC dates, StatsCan releases |
| Pre-event analysis | Claude Sonnet | High-significance event previews |
| Under the Microscope | Gemini (topic) + Claude (analysis) | 200-300 word deep-dive |
| Weekly briefing | Claude Sonnet | 8 sections, 1000-1500 words |
| Briefing export | reportlab + python-docx | PDF + DOCX files |

### Steps 5-9 — Finalize & Export

1. **Source verification** — Concurrent HEAD requests, dead URLs cleared, Wayback archived
2. **Timeseries append** — One data point per tracked variable for sparklines
3. **Final assembly** — Full JSON payload saved to `dashboard_state`
4. **Quality report** — Pipeline metrics logged to `pipeline_runs`
5. **Static JSON export** — `export_all(conn)` writes 13+ files to `docs/data/`
6. **Deploy** — `deploy_to_github.py` copies `public/` → `docs/`, git commit/push

---

## Database Schema — `db.py`

All SQLite access through `db.py`. WAL mode, foreign keys ON, `busy_timeout=5000`.

### 14 Tables

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

### Projects Table (key fields)

```sql
CREATE TABLE projects (
    rowid             INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_key          TEXT UNIQUE NOT NULL,       -- dedup key
    name              TEXT NOT NULL,
    province          TEXT NOT NULL,
    cma               TEXT,
    sector            TEXT,                       -- NAICS sector
    naics_code        TEXT,
    value             TEXT DEFAULT 'Not disclosed',
    status            TEXT DEFAULT 'Proposed',
    confidence        REAL DEFAULT 0.3,
    project_type      TEXT,                       -- 11-type taxonomy
    is_brownfield     INTEGER DEFAULT 0,
    proponent         TEXT,
    description       TEXT,
    evidence          TEXT DEFAULT '[]',          -- JSON [{url, source, date}]
    discovery_sources TEXT DEFAULT '[]',
    statusHistory     TEXT DEFAULT '[]',
    discovery_source  TEXT,                       -- tier that found it
    has_government_source INTEGER DEFAULT 0,
    evidence_count    INTEGER DEFAULT 0,
    firstTracked      TEXT,
    lastUpdated       TEXT,
    lastSeen          TEXT
);
```

### Status Ordering (non-regression)

```
Rumoured(0) → Proposed(1) → Under Review(2) → Approved(3) →
Under Construction(4) → Partially Complete(5) → Complete(6)

Terminal states (always override): Cancelled, On Hold, Suspended, Paused
```

### Key Integrity Rules

1. **URL hard gate** — No evidence URL = no DB write
2. **Evidence merge never loses URLs** — Dedup by normalized URL, always append
3. **Status never regresses** — Only advances in ordering
4. **Additive only** — Keywords, queries, feeds can be added, never removed
5. **Primary API always wins** — Hard data override in Steps 4a-4f
6. **No fabrication** — Citation audit removes unsourced claims

---

## Frontend Architecture

### Stack
- **HTML:** `public/index.html` (496 lines, shell only)
- **JS:** `public/js/app.js` (~1400+ lines, all rendering)
- **CSS:** Tailwind CDN + custom properties
- **Charts:** Chart.js 4.4.1 + chartjs-plugin-annotation
- **Viz:** D3 7.8.5 + d3-cloud (word cloud)
- **Fonts:** Plus Jakarta Sans + JetBrains Mono
- **Sanitization:** DOMPurify 3.0.6

### Data Loading
- Base path: `data/` (relative)
- `fetchJSON(path)` with in-memory cache
- `loadAll()` on page load → fetches core JSON files
- Lazy tab rendering: each tab rendered on first activation

### Tabs

| Tab | Data Source | Content |
|-----|------------|---------|
| Overview | `briefing_latest.json` | Executive summary, word cloud, key metrics |
| Macro | `briefing_latest.json`, `indicators.json` | National indicators, indicator explorer |
| Industries | `briefing_latest.json` | Goods/services sectors, yield curve |
| Provinces | `briefing_latest.json`, `projects_{prov}.json` | Per-province analysis + projects |
| Projects | `projects_all.json`, `projects_{prov}.json` | Searchable/filterable project database |
| Briefing | `briefing_latest.json`, `briefing_archive.json` | 8-section briefing, PDF/DOCX downloads |
| Markets | `briefing_latest.json`, `timeseries.json` | Commodity cards, equities, yield curve |

### No Backend
- No server, no runtime API calls
- All data is static JSON served by GitHub Pages CDN
- Province project threshold filtering done client-side

---

## AI Model Stack

| Model | Role | Cost | Constraint |
|-------|------|------|------------|
| Claude Opus (claude-opus-4-6) | Call 1: macro writing | ~$7/year | Opus 404 → Sonnet fallback |
| Claude Sonnet (claude-sonnet-4-6) | All reasoning, briefing, analysis | ~$25/year | $3/M input, $15/M output |
| Gemini 2.5 Flash | Classification, extraction, JSON repair | Free tier | **NEVER pass google_search tool or groundingConfig** |
| Tavily | Targeted enrichment search | Free tier (1,000/mo) | Budget tracked in dashboard_state |

### Cost Constraint: ~$60/year total

No Gemini Pro, no Gemini grounded search ($35/1K queries), no Perplexity, no GDELT paid tier, no Haiku in weekly pipeline.

---

## Data Flow Summary

```
DISCOVERY                    PROCESSING                  STORAGE            DELIVERY
─────────────────────────── ─────────────────────────── ──────────────────── ──────────────
Google News RSS (759)  ───┐
Gov Registries (9)     ───┤  6-layer RSS filter
GDELT (~200)           ───┤  ───────────────────►
RSS Feeds (~201)       ───┤  Claude extraction (4 calls)
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

---

## CLI Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Weekly: 7-day lookback, all tiers, full analysis |
| `--indicators-only` | Daily: hard data + export only, skip discovery |
| `--deep-sweep` | Monthly: 30-day lookback, full Wayback backfill |
| `--seed-projects` | One-time project seed (registries + Google News RSS + municipal + institutional) |
| `--test-feeds` | Test all RSS feed URLs for connectivity |
| `--audit-citations` | Verify all source URLs, archive dead ones via Wayback |
| `--test-sentiment` | Sentiment collection only |
| `--test-queries` | GDELT dry run |

---

## Error Handling Patterns

- All discovery tiers: `try/except` → `[WARN]` + continue (non-critical)
- Claude API: 4 retries, exponential backoff (1s→8s), JSON failure → Gemini repair
- StatCan WDS: 1 retry after 5s
- BoC Valet: 1 retry after 5s
- CMHC: tries last 4 months for publication lag
- GDELT: bail-out after 3 consecutive failures
- Yahoo Finance: 12hr cache shields instability
- URL verification: HEAD with 5s timeout, 12 concurrent workers
- Pipeline logging: `PipelineRunLogger` → `pipeline_runs` table (step logs, error counts, API usage)
- Full traceback on unhandled exceptions; run finalized with `"error"` status

---

## Province GDP Thresholds

| Province | Threshold |
|----------|-----------|
| ON | $500M |
| QC | $250M |
| AB | $200M |
| BC | $175M |
| SK | $45M |
| MB | $40M |
| NS | $25M |
| NB | $20M |
| NL | $17M |
| PE | $5M |
| YT/NT/NU | $3M |

---

## Confidence Scoring

| Factor | Points |
|--------|--------|
| Base | 0.1 |
| Per evidence source (max 0.3) | +0.1 |
| Per government source (max 0.3) | +0.15 |
| Verified dollar value | +0.1 |
| Multi-tier discovery | +0.05-0.1 |

### Decay Schedule

| Days since last seen | Penalty |
|----------------------|---------|
| 31-60 | -0.05 |
| 61-90 | -0.10 |
| 91-120 | -0.15 |
| 121+ | -0.20 (flagged stale) |

---

## Dependencies

```
aiohttp           # Async HTTP (Claude API, discovery)
feedparser        # RSS feed parsing
beautifulsoup4    # HTML scraping (registries)
yfinance          # Yahoo Finance market data
reportlab         # PDF briefing export
python-docx       # DOCX briefing export
anthropic         # Claude SDK (Call 1-3)
google-genai      # Gemini SDK (classification)
tavily-python     # Tavily search client
openpyxl          # NRCan XLSX parsing
lxml              # HTML/XML parsing
nest_asyncio      # Allow nested event loops
python-dotenv     # .env file loading
requests          # Sync HTTP (RSS SSL fix)
gdeltdoc          # GDELT DOC 2.0 client (patched UA)
pytz              # Timezone handling
```

---

## Complete Python File Index (60+ files)

### Pipeline Core
| File | Lines | Purpose |
|------|-------|---------|
| `update_dashboard.py` | ~4150 | Main orchestrator — all 9 steps |
| `db.py` | — | SQLite interface, 14 table schemas, upsert logic, FTS5 |
| `pipeline_config.py` | — | Model routing, GDP thresholds, NAICS map, dedup helpers |
| `pipeline_cache.py` | — | In-memory TTL cache (yfinance 12hr, indicators 24hr) |
| `pipeline_logging.py` | — | Structured `PipelineRunLogger` → pipeline_runs table |
| `pipeline_state.py` | — | Follow-up query store/retrieve |
| `export_dashboard.py` | — | SQLite → docs/data/*.json (28+ static files) |
| `deploy_to_github.py` | — | Copy public/ → docs/ for GitHub Pages |

### Discovery (14 Tiers)
| File | Tier | Purpose |
|------|------|---------|
| `gov_sources.py` | 1,5,8 | IAAC, BC EAO, NRCan, InfraCA, BuyAndSell, CER, 13 provincial EAs |
| `google_news_rss_search.py` | 2 | 759 compound queries → Google News RSS (free, unlimited) |
| `gdelt_monitor.py` | 3 | GDELT DOC 2.0 (~200 queries, HTTP only, bail-out after 3 fails) |
| `rss_monitor.py` | 4,12,13 | 201+ RSS/Atom feeds (gov, media, industry, Google Alerts) |
| `article_filter.py` | — | 6-layer RSS filter (gov bypass → dollar bypass → keywords → Gemini) |
| `statcan_permits.py` | 9 | Building permit anomaly detection (20 CMAs, 3.0x threshold) |
| `lobbyist_registries.py` | 10 | Federal/provincial lobbyist signal detection |
| `municipal_dev_apps.py` | 11 | 15 CMAs (Socrata/CKAN APIs + HTML portals) |
| `google_alerts.py` | 12 | 25 Google Alerts RSS feeds |
| `institutional_capital.py` | 14 | U15 universities, polytechnics, hospitals |
| `key_people_tracker.py` | — | 15 RSS feeds (PM, premiers, crown corps) — gov bypass |
| `capacity_scheduler.py` | — | T1-T6 remaining Gemini budget allocation |
| `capacity_queries.py` | — | Query sets for capacity scheduler |

### AI / Reasoning
| File | Model | Purpose |
|------|-------|---------|
| `claude_reasoning.py` | Claude Sonnet | Gap analysis, extraction recovery, dedup QA, meta-analysis |
| `gemini_engine.py` | Gemini Flash | Classification, extraction, JSON repair |
| `enrichment_queries.py` | Gemini Flash | Fill missing value/proponent/status (≤100/day) |
| `under_the_microscope.py` | Gemini + Claude | Topic selection + 200-300 word deep-dive |
| `weekly_briefing.py` | Claude Sonnet | 8-section briefing (1000-1500 words) |
| `briefing_export.py` | — | PDF (reportlab) + DOCX (python-docx) generation |

### Project Processing
| File | Purpose |
|------|---------|
| `project_dedup.py` | Cross-tier fuzzy dedup (norm_key + SequenceMatcher ≥0.85) |
| `project_sync.py` | SQLite upsert with status non-regression, evidence merge |
| `project_schema.py` | Type normalization, brownfield detection |
| `confidence_decay.py` | Score decay after 30/60/90/120 days |
| `lifecycle_monitor.py` | Gemini status transition checks on active projects |
| `anomaly_detection.py` | Cross-project/cross-province duplicate detection |

### Analysis + Narrative
| File | Purpose |
|------|---------|
| `sector_trends.py` | Project count/value trends by sector |
| `indicator_trends.py` | M/M and Y/Y computations from indicator_history |
| `cross_reference.py` | Link indicator movements to project counts |
| `weekly_trend_report.py` | Textual trend narrative |
| `canadian_markets.py` | Commodity data + Claude market commentary |
| `event_calendar.py` | BoC dates, StatsCan releases + Claude pre-event analysis |
| `provincial_policy_monitor.py` | Policy RSS processing |
| `citation_audit.py` | Removes unverifiable claims after each Claude call |

### Search
| File | Purpose |
|------|---------|
| `tavily_search.py` | Targeted enrichment (cost-finding, verification, follow-ups) |
| `cost_finder.py` | Tavily cost search for projects missing dollar values |
| `gemini_search.py` | Legacy search logging helper (search disabled) |

### Data Quality
| File | Purpose |
|------|---------|
| `url_utils.py` | URL normalization for dedup |
| `url_verifier.py` | Async URL verification with retry |
| `url_verify.py` | Sync URL verification, quick_reject() |
| `wayback.py` | Wayback Machine save + backfill snapshots |
| `deep_verification.py` | Deep URL verification with Wayback fallback |
| `quality_report.py` | Pipeline quality metrics |
| `learning_store.py` | Adaptive learning (additive only) |
| `github_issues_reader.py` | Read user submissions via GitHub Issues API |
| `missed_project_enrichment.py` | Process submissions via Tavily |
| `missed_project_diagnostics.py` | Missed project diagnostic tools |
| `dedup_audit.py` | Dedup quality audit |
| `coverage_audit.py` | Geographic + sector coverage gaps |

### Seeding / One-Time
| File | Purpose |
|------|---------|
| `seed_projects.py` | Legacy one-time seeder |
| `seed_projects_v2.py` | Full rebuild (registries → GDELT+Claude → Perplexity) |
| `known_project_sweep.py` | ~208 Gemini queries + 47 hardcoded seeds |
| `generate_compound_queries.py` | Generates compound_queries_final.json |
| `compound_queries.py` | Compound query builder logic |
| `historical_backfill.py` | Historical indicator backfill |
| `backfill_*.py` (7 files) | Various one-time data backfill scripts |

### Misc
| File | Purpose |
|------|---------|
| `named_tracker.py` | Named entity tracking across runs |
| `sentiment.py` | Consumer sentiment (Reddit, Google Trends) |
| `statcan_table_registry.py` | Generates statcan_tables.json for Data Explorer |
| `convert_watchlist.py` | Converts watchlist CSV → JSON |
| `test_*.py` (5 files) | Unit/integration tests |
