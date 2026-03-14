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
│               update_dashboard.py (orchestrator)                     │
│                                                                     │
│  Phase 1: Data Collection ─── phases/data_collection.py             │
│  Phase 2: Discovery ───────── phases/discovery.py                   │
│  Phase 3: Filtering & Dedup ─ phases/filtering.py                   │
│  Phase 4: Signals ──────────── phases/signals.py                    │
│  Phase 5: AI Analysis ──────── phases/analysis.py                   │
│  Phase 6: Reasoning ────────── phases/reasoning.py                  │
│  Phase 7: Narrative ────────── phases/narrative.py                  │
│  Phase 8: Verification ─────── phases/verification.py               │
│  Phase 9: Finalize & Export ── phases/finalize.py                   │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
          ┌────────────┼────────────────┐
          ▼            ▼                ▼
   ┌─────────────┐  ┌───────────┐  ┌──────────────┐
   │  14 Discovery│  │ AI Engine │  │  Hard Data   │
   │  Tiers       │  │ (4 models)│  │  (6+ APIs)   │
   └──────┬──────┘  └─────┬─────┘  └──────┬───────┘
          │                │               │
          └────────────────┼───────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SQLite (dashboard.db) — WAL mode                  │
│                    db.py — single interface module                   │
│                    15+ tables + FTS5 triggers                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              export_dashboard.py → docs/data/*.json (30+ files)     │
│              briefing_export.py → docs/data/*.pdf, *.docx           │
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
├── update_dashboard.py         # Master pipeline orchestrator
├── deploy_to_github.py         # public/ → docs/ sync
├── export_dashboard.py         # SQLite → docs/data/*.json
├── briefing_export.py          # PDF + DOCX briefing generation
├── db.py                       # Single SQLite interface module (~1744 lines)
├── pipeline_config.py          # Model routing, thresholds, dedup config
├── pipeline_logging.py         # Structured run logger → pipeline_runs table
├── service_health.py           # Circuit breaker for external APIs
│
├── ── PHASES (pipeline architecture) ──
├── phases/
│   ├── __init__.py
│   ├── data_collection.py      # Phase 1: Hard data (6+ APIs, no AI)
│   ├── discovery.py            # Phase 2: 14-tier project discovery
│   ├── filtering.py            # Phase 3: RSS filter, extraction, dedup
│   ├── signals.py              # Phase 4: Permits + lobbyist signals
│   ├── analysis.py             # Phase 5: Claude 4-call analysis + hard data override
│   ├── reasoning.py            # Phase 6: Gap analysis, dedup QA, meta-analysis
│   ├── narrative.py            # Phase 7: Trends, commentary, briefing
│   ├── verification.py         # Phase 8: URL verification, Wayback, enrichment
│   └── finalize.py             # Phase 9: Timeseries, assembly, export, deploy
│
├── ── DISCOVERY (14 tiers) ──
├── google_news_rss_search.py   # Tier 2: 2,574 queries → Google News RSS
├── rss_monitor.py              # Tier 4: ~201 RSS feeds, 6-layer filter
├── gov_sources.py              # Tier 1,5,8: IAAC, BC EAO, NRCan, CER, provincial EAs
├── municipal_dev_apps.py       # Tier 11: 15 CMAs (Socrata/CKAN/HTML)
├── institutional_capital.py    # Tier 14: U15 universities, polytechnics, hospitals
├── statcan_permits.py          # Tier 9: Building permit anomaly detection
├── lobbyist_registries.py      # Tier 10: Federal lobbyist registry
├── key_people_tracker.py       # Key people RSS (PM, premiers, ministers)
├── google_alerts.py            # Tier 12: 25 Google Alert RSS feeds
│
├── ── FILTERING / DEDUP ──
├── article_filter.py           # 6-layer article filter (local LLM + Gemini)
├── project_dedup.py            # Cross-tier deduplication
├── project_schema.py           # normalize_project_type, is_brownfield
├── project_sync.py             # upsert_projects, upsert_flat_projects
├── confidence_decay.py         # 30/60/90/120-day decay
├── lifecycle_monitor.py        # Gemini status checks for tracked projects
│
├── ── AI / REASONING ──
├── claude_reasoning.py         # Claude Sonnet: all reasoning tasks
├── gemini_engine.py            # Gemini Flash classification (local LLM fallback)
├── local_llm.py                # Qwen 2.5 3B via llama-cpp-python (no API needed)
├── enrichment_queries.py       # Gemini Flash: fill missing value/status
├── under_the_microscope.py     # Topic selection + deep-dive analysis
├── weekly_briefing.py          # 8-section weekly briefing generation
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
│
├── ── DATA QUALITY ──
├── url_utils.py                # URL normalization for dedup
├── url_verify.py               # Sync URL verification, quick_reject()
├── wayback.py                  # Wayback Machine save + backfill snapshots
├── quality_report.py           # Pipeline quality metrics report
├── learning_store.py           # Adaptive learning (additive only)
├── github_issues_reader.py     # Read user submissions via GitHub Issues API
├── dedup_audit.py              # Deduplication quality audit
├── coverage_audit.py           # Geographic + sector coverage gap audit
│
├── ── SEEDING / ONE-TIME ──
├── seed_projects_v2.py         # Full rebuild (registries → GDELT+Claude → Perplexity)
├── known_project_sweep.py      # ~208 Gemini queries + 47 hardcoded seeds
├── generate_compound_queries.py# Generates compound_queries_final.json
├── compound_queries.py         # Compound query builder logic
│
├── ── MISC UTILITIES ──
├── named_tracker.py            # Named entity tracking across runs
├── sentiment.py                # Consumer sentiment (Reddit, Google Trends)
├── statcan_table_registry.py   # Generates statcan_tables.json for Data Explorer
├── convert_watchlist.py        # Converts watchlist CSV → watchlist.json
├── capacity_scheduler.py       # AI capacity management
├── capacity_queries.py         # Query sets for capacity scheduler
│
├── ── TESTS ──
├── test_compound_queries.py
├── test_rss_filter.py
├── test_dedup.py
├── test_brownfield_discovery.py
├── test_db.py
├── tests/test_export_dashboard.py
│
├── ── ARCHIVE (disabled / one-time scripts) ──
├── archive/
│   ├── gdelt_monitor.py        # GDELT DOC 2.0 (disabled — replaced by Google News RSS)
│   ├── gemini_search.py        # Gemini grounded search (removed — $136/day cost)
│   ├── seed_projects.py        # Legacy seeder
│   ├── pipeline_cache.py       # Legacy cache
│   ├── pipeline_state.py       # Legacy state store
│   ├── url_verifier.py         # Legacy URL checker
│   ├── deep_verification.py    # Legacy deep verification
│   ├── missed_project_enrichment.py
│   ├── missed_project_diagnostics.py
│   ├── historical_backfill.py
│   └── backfill_*.py (7 files) # One-time data migrations
│
├── ── DATA / CONFIG ──
├── dashboard.db                # SQLite database (WAL mode, 15+ tables)
├── .env                        # API keys, model IDs, feature flags (not committed)
├── compound_queries_final.json # 2,574 compound queries
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
        ├── policy.json               # Provincial policy monitor articles
        ├── commodities.json          # Canadian commodity indicators
        ├── pipeline_status.json      # Last pipeline run status
        ├── statcan_tables.json       # Data Explorer table registry
        ├── CAN_Macro_Briefing_*.pdf  # Downloadable briefing PDF
        ├── CAN_Macro_Briefing_*.docx # Downloadable briefing DOCX
        └── manifest.json             # Build metadata
```

---

## GitHub Actions Scheduling

### `weekly-pipeline.yml` — Full Run
- **Schedule:** Monday 10:30 UTC (5:30 AM ET)
- **Trigger:** Also `workflow_dispatch` (manual)
- **Steps:** Checkout → Python 3.12 → `pip install` → cache/download local LLM model → `python update_dashboard.py` → `python briefing_export.py` → `python deploy_to_github.py` → git commit/push docs/
- **Env:** `GEMINI_SEARCH_ENABLED=false`, `GEMINI_MODEL=gemini-2.5-flash`, `SONNET_MODEL=claude-sonnet-4-6`, `LOCAL_MODEL_PATH=models/qwen2.5-3b-instruct-q4_k_m.gguf`

### `daily-indicators.yml` — Indicator Refresh
- **Schedule:** Daily 05:00 UTC (midnight ET)
- **Runs:** `python update_dashboard.py --indicators-only`
- **Purpose:** Fresh BoC rate, StatCan indicators, commodity prices without full discovery

---

## Pipeline Execution Order (9 Phases)

### Phase 1 — Data Collection (No AI)

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

### Phase 2 — Discovery Pipeline (14 tiers)

```
Tier 1:  Federal Registries ──── IAAC, BC EAO, NRCan, Infra CAN, CanadaBuys, CER, ERO, CIB, Metrolinx
Tier 2:  Google News RSS ─────── 2,574 compound queries → free RSS feeds
Tier 3:  GDELT ────────────────── (disabled — moved to archive/; replaced by Google News RSS)
Tier 4:  RSS Feeds ────────────── ~201 feeds through 6-layer filter
Tier 5:  Provincial EA ────────── 10 registries (QC BAPE, AB, SK, MB, NS, NB, NL, YT, NWT)
Tier 6:  SEDAR+ ───────────────── (disabled — endpoint audit needed; scraper targets login portal)
Tier 7:  Crown Corps ──────────── CIB, Metrolinx (via Tier 1)
Tier 8:  Canada Energy Regulator── CER applications (via Tier 1)
Tier 9:  StatCan Permits ──────── 20 CMAs, anomaly threshold 3.0x 12-month MA
Tier 10: Lobbyist Registry ────── Federal bulk CSV, infrastructure keyword filter
Tier 11: Municipal Dev Apps ───── (degraded — most HTML endpoints broken; 4 API cities may work)
Tier 12: Google Alerts ────────── (disabled — not configured; placeholder URLs only)
Tier 13: Industry Trade RSS ───── 22 feeds (included in Tier 4)
Tier 14: Institutional Capital ── U15 universities, polytechnics, hospitals
```

### Phase 3 — Filtering & Dedup

#### RSS Filter (6 layers — order matters)

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
         L6: Local LLM classification (Gemini Flash fallback)
         │
         ▼
     PASS → extraction pipeline
```

**Note:** Layer 6 now uses the local Qwen 2.5 3B model as the primary classifier, with Gemini Flash as fallback when the local model is unavailable.

#### Post-Extraction — Project Pipeline

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
```

### Phase 4 — Signals

| Signal | Source |
|--------|--------|
| Building permit anomalies | StatCan permits (20 CMAs, 3.0x threshold) |
| Lobbyist registrations | Federal CSV, infrastructure keyword filter |

### Phase 5 — AI Analysis (Claude 4-call pipeline)

| Call | Model | Output |
|------|-------|--------|
| 1 | Claude Sonnet | Executive summary, national analysis, global vectors, watchlist, consumer pulse, word cloud |
| 2 | Claude Sonnet | Industry analysis (5 goods + 15 services sectors), yield curve, charts |
| 3 | Claude Sonnet | All 13 provinces (analysis bullets, indicators, projects) |
| 4 | Claude Sonnet | Structured project extraction from discovered articles |

- 4 retry attempts with exponential backoff per call
- JSON parse failure → Gemini Flash repair
- Claude checkpoint support (resume after crash via `claude_checkpoints` table)
- Post-call citation audit removes unsourced claims

#### Hard Data Override (Steps 4a-4g)

After Claude writes the payload, authoritative API values overwrite all indicators:
- Commodities, markets, yields (Yahoo Finance / BoC Valet)
- National metrics: bocRate, CPI, unemployment, housingStarts, GDP
- Global indicators: US/EU/UK/China (FRED/ECB/BoE/World Bank)
- Provincial indicators (StatCan WDS)
- Industry M/M and Y/Y (StatCan Table 36-10-0434-01)
- `validate_indicators()` cross-checks and logs any mismatches

### Phase 6 — Reasoning

| Task | Purpose |
|------|---------|
| Gap analysis | Identify provincial discovery gaps → follow-up queries |
| Extraction recovery | Retry failed RSS articles with Claude |
| Dedup QA | Flag probable duplicates in new projects |
| Meta-analysis | Monthly full database review (first 7 days of month) |

### Phase 7 — Narrative

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

### Phase 8 — Verification & Quality

| Task | Method |
|------|--------|
| Source verification | Concurrent HEAD requests, dead URLs flagged |
| Wayback archival | Up to 20 URLs per run |
| Cost-finding | Tavily search for projects missing dollar values |
| Gemini enrichment | Fill missing fields (≤100 queries/day) |
| Stale project check | 28+ days unseen detection |
| Confidence decay | 31-120+ day score reduction |
| Lifecycle monitoring | Gemini status transition checks |
| Cross-project anomaly detection | Duplicate/outlier detection |

### Phase 9 — Finalize, Export & Deploy

1. **Timeseries append** — One data point per tracked variable for sparklines
2. **Final assembly** — Full JSON payload saved to `dashboard_state`
3. **Quality report** — Pipeline metrics logged to `pipeline_runs`
4. **Briefing export** — PDF (reportlab) + DOCX (python-docx) to `docs/data/`
5. **Static JSON export** — `export_all(conn)` writes 30+ files to `docs/data/`
6. **Deploy** — `deploy_to_github.py` syncs `public/` → `docs/`, git commit/push

---

## Database Schema — `db.py`

All SQLite access through `db.py`. WAL mode, foreign keys ON, `busy_timeout=5000`.

### 15+ Tables

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
| `claude_checkpoints` | Resume-after-crash for expensive Claude API calls |
| `miss_audit_results` | Typed miss classifications from coverage audit |

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

### Claude Checkpoints Table

```sql
CREATE TABLE claude_checkpoints (
    run_id    TEXT NOT NULL,
    call_name TEXT NOT NULL,
    response  TEXT,
    cost_usd  REAL DEFAULT 0,
    created   TEXT,
    PRIMARY KEY (run_id, call_name)
);
```

Allows the pipeline to resume from the last successful Claude call after a crash, avoiding re-spending on expensive API calls.

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
5. **Primary API always wins** — Hard data override in Phase 5
6. **No fabrication** — Citation audit removes unsourced claims

---

## Frontend Architecture

### Stack
- **HTML:** `public/index.html` (~500 lines, shell only)
- **JS:** `public/js/app.js` (~1400+ lines, all rendering)
- **CSS:** Tailwind CDN + custom properties
- **Charts:** Chart.js 4.4.1 + chartjs-plugin-annotation
- **Viz:** D3 7.8.5 + d3-cloud (word cloud)
- **Fonts:** Neue Haas Grotesk Display Pro + JetBrains Mono
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
| Markets | `briefing_latest.json`, `timeseries.json`, `commodities.json` | Commodity cards, equities, yield curve |

### No Backend
- No server, no runtime API calls
- All data is static JSON served by GitHub Pages CDN
- Province project threshold filtering done client-side

---

## AI Model Stack

| Model | Role | Cost | Constraint |
|-------|------|------|------------|
| Claude Sonnet (claude-sonnet-4-6) | All reasoning, writing, briefing, analysis | ~$55/year | $3/M input, $15/M output |
| Gemini 2.5 Flash | Classification, extraction, JSON repair (fallback) | Free tier | **NEVER pass google_search tool or groundingConfig** |
| Qwen 2.5 3B (local) | Primary classifier for RSS filter L6, article filter | Free (local) | llama-cpp-python; ~2GB model file |
| Tavily | Targeted enrichment search | Free tier (1,000/mo) | Budget tracked in dashboard_state |

### Cost Constraint: ~$60/year total

No Gemini Pro, no Gemini grounded search ($35/1K queries), no Claude Opus, no Perplexity, no GDELT paid tier, no Haiku in weekly pipeline.

### Local LLM Details

- **Model:** Qwen 2.5 3B Instruct (Q4_K_M quantization, ~2GB)
- **Runtime:** llama-cpp-python with 4096 context, 2 threads
- **Path:** `LOCAL_MODEL_PATH` env var or `models/qwen2.5-3b-instruct-q4_k_m.gguf`
- **Usage:** Primary classifier in `article_filter.py` L6 and `gemini_engine.py` fallback
- **Behavior:** Lazy-loaded on first call, stays in memory for run duration. Returns "RELEVANT" (safe default) if model unavailable.
- **CI caching:** `actions/cache@v4` caches `models/` directory; downloaded from HuggingFace on miss

---

## Circuit Breaker — `service_health.py`

The `ServiceHealth` singleton tracks consecutive failures per external service. After reaching a configurable threshold, the service is marked "dead" for the remainder of the pipeline run to avoid wasting time on unreachable endpoints.

| Service | Failure Threshold | Effect when dead |
|---------|-------------------|------------------|
| `gemini` | 3 | Skip Gemini classification → use local LLM only |
| `reddit` | 2 | Skip sentiment collection |
| `wayback` | 2 | Skip Wayback archival |
| `statcan` | 3 | Skip StatCan WDS calls |
| `tavily` | 3 | Skip Tavily enrichment searches |

**API:**
- `service_health.init()` — create/reset at pipeline start
- `service_health.get()` — get singleton
- `health.record_failure(service, reason)` — increment counter; auto-marks dead at threshold
- `health.record_success(service)` — reset counter
- `health.is_available(service)` — check before making calls

---

## Data Flow Summary

```
DISCOVERY                    PROCESSING                  STORAGE            DELIVERY
─────────────────────────── ─────────────────────────── ──────────────────── ──────────────
Google News RSS (2574) ───┐
Gov Registries (9)     ───┤  6-layer RSS filter
RSS Feeds (~201)       ───┤  (local LLM + Gemini)
Municipal Apps (4*)    ───┤  ───────────────────►
Institutional (20)     ───┤  Claude extraction (4 calls)
StatCan Permits (20)   ───┤  ───────────────────►          dashboard.db
Lobbyist Registry      ───┘  Cross-tier dedup              (SQLite WAL)
                             URL hard gate                 ──────────────►
                             Evidence merge                                  docs/data/
                             Status non-regression                           *.json
                        * Municipal: 4 API cities active; HTML scrapers degraded
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
| `--known-sweep` | One-time historical sweep (~208 queries + 47 seeds) |
| `--audit-archetypes` | Archetype pattern scan for missed project types |
| `--test-sentiment` | Sentiment collection only |

---

## Error Handling Patterns

- All discovery tiers: `try/except` → `[WARN]` + continue (non-critical)
- Claude API: 4 retries, exponential backoff (1s→8s), JSON failure → Gemini repair
- Claude checkpoints: expensive calls saved to `claude_checkpoints` table for crash recovery
- StatCan WDS: 1 retry after 5s
- BoC Valet: 1 retry after 5s
- CMHC: tries last 4 months for publication lag
- GDELT: disabled (moved to archive/)
- Yahoo Finance: 12hr cache shields instability
- URL verification: HEAD with 5s timeout, 12 concurrent workers
- Pipeline logging: `PipelineRunLogger` → `pipeline_runs` table (step logs, error counts, API usage)
- Full traceback on unhandled exceptions; run finalized with `"error"` status
- **Circuit breaker:** `ServiceHealth` marks services dead after N consecutive failures (see section above)

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
anthropic         # Claude SDK
google-genai      # Gemini SDK (classification)
tavily-python     # Tavily search client
llama-cpp-python  # Local LLM inference (Qwen 2.5 3B)
lxml              # HTML/XML parsing
nest_asyncio      # Allow nested event loops
python-dotenv     # .env file loading
requests          # Sync HTTP (RSS SSL fix)
gdeltdoc          # GDELT DOC 2.0 client (legacy, archive/)
pytz              # Timezone handling
```
