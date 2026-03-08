# INTEGRATIONS.md — External Services & APIs

## AI Services

### Anthropic Claude API
- **Models:** Claude Opus 4.6, Claude Sonnet 4.6
- **Config:** `pipeline_config.py` → `OPUS_MODEL`, `SONNET_MODEL`
- **Client:** `anthropic` Python SDK in `claude_reasoning.py`
- **Usage:** ALL reasoning — briefing, market commentary, policy assessment, Under the Microscope, gap analysis, extraction recovery, dedup QA, signal investigation, meta-analysis
- **Cost:** ~$55/year combined

### Google Gemini API
- **Model:** Gemini 2.5 Flash only (NO Pro, NO grounding)
- **Config:** `pipeline_config.py` → `GEMINI_MODEL`
- **Client:** `google.genai` SDK in `gemini_engine.py`
- **Usage:** Classification, JSON extraction, Wayback parsing, RSS article classification, enrichment queries
- **CRITICAL:** Never pass `google_search` tool or `groundingConfig` — causes $35/1000 query charges
- **Cost:** Free tier

### Tavily Search API
- **Client:** `tavily-python` SDK in `tavily_search.py` (optional import)
- **Usage:** Cost-finding (300/mo), named tracking (200/mo), verification (200/mo), enrichment (150/mo), signals (100/mo), buffer (50/mo)
- **Budget:** 1,000 credits/month free tier — hard cap
- **Cost:** Free

## Government Data APIs

### Bank of Canada Valet API
- **Endpoint:** `https://www.bankofcanada.ca/valet/`
- **Series:** V39079 (overnight rate) + others
- **Used in:** `update_dashboard.py` → `fetch_primary_indicators()`

### StatCan Web Data Service (WDS)
- **Endpoint:** `https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadCompleteTable~...`
- **Tables:** 36-10-0434-01 (industry GDP), 18-10-0004-01 (CPI), 14-10-0287 (unemployment)
- **Used in:** `gov_sources.py` → `_statcan_wds()`, `fetch_statcan_indicators()`

### CMHC Housing Data
- **Used in:** `update_dashboard.py` (housing starts, completions)

### FRED (Federal Reserve Economic Data)
- **Format:** CSV download
- **Used in:** `update_dashboard.py` (US indicators for cross-reference)

### ECB Statistical Data Warehouse
- **Format:** SDW API
- **Used in:** `update_dashboard.py` (European rates for context)

### Bank of England IADB
- **Used in:** `update_dashboard.py` (UK rates for context)

## Discovery & News APIs

### Google News RSS
- **Format:** RSS feeds generated from 759 compound queries
- **Module:** `google_news_rss_search.py`
- **Config:** `compound_queries_final.json`
- **Cost:** Free, unlimited
- **Replaces:** Gemini grounded search ($136/day)

### GDELT DOC 2.0 API
- **Endpoint:** `http://api.gdeltproject.org/api/v2/doc/doc` (HTTP only — port 443 blocked)
- **Module:** `gdelt_monitor.py`
- **Workaround:** Custom `_GdeltDocPatched` subclass with spoofed User-Agent
- **Bail-out:** Skips after 3 consecutive failures

### RSS Feeds (201+)
- **Config:** `rss_feeds.json` — 7 categories: federal (20), provincial (14), municipal (1), CBC, CTV, Postmedia, independent, industry (11), key_people (15)
- **Module:** `rss_monitor.py`
- **Filter:** 6-layer pipeline in `article_filter.py` / `rss_monitor.py`

### Yahoo Finance
- **Client:** `yfinance` library
- **Usage:** Commodities (WTI, Brent, gold, copper), indices (TSX, S&P), yields, FX
- **Known issue:** PN=F ticker delisted (non-blocking warning)

## Government Registries (Tier 1)

### IAAC (Impact Assessment Agency of Canada)
- **Module:** `gov_sources.py` → `fetch_registry_projects()`
- **Format:** Web scraping

### BC Environmental Assessment Office
- **Endpoint:** `https://www.projects.eao.gov.bc.ca/api/v2/projects`
- **Format:** JSON API

### Infrastructure Canada
- **Endpoint:** `https://infrastructure.gc.ca/alt-format/opendata/project-list-liste-de-projets-bil.json`
- **Format:** JSON export

### CanadaBuys (BuyAndSell)
- **Endpoint:** `https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv`
- **Format:** CSV stream

### NRCan Major Projects Inventory
- **Endpoint:** `https://natural-resources.canada.ca/science-and-data/data-and-analysis/major-projects-inventory/22218`
- **Format:** HTML scraping + Tavily fallback

## Database

### Google Cloud Firestore
- **Project:** `can-macro-dashboard`
- **Collections:**
  - `projects` — Main project database
  - `missed_projects` — User-submitted missed projects
  - `pipeline_improvements` — Adaptive learning
  - `indicator_history` — Economic indicator time series
  - `trend_snapshots` — Weekly trend analysis
  - `weekly_briefings` — Generated briefings
  - `dashboard_state` — Frontend state, latest briefing, microscope history/override
- **Auth:** Service account key (`serviceAccountKey.json`)
- **Client:** `firebase-admin` SDK

### Firebase Storage
- **Usage:** Briefing PDF/DOCX export uploads
- **Module:** `briefing_export.py`

## Hosting & Deployment

### Firebase Hosting
- **Content:** `public/index.html` (single-file SPA)
- **Deploy:** `node --max-old-space-size=4096 firebase.js deploy --only hosting,firestore:rules`
- **Note:** Standard `firebase` CLI OOMs when index.html >1700 lines

### Cloud Functions
- **Runtime:** Node 20
- **Schedule:** Weekly Monday 6AM ET + daily midnight ET
- **Module:** `functions/index.js`

## Archival

### Wayback Machine
- **Usage:** Archive project source URLs, retrieve historical snapshots
- **Module:** `wayback.py`
- **Config:** `WAYBACK_ENABLED`, `WAYBACK_SAVE_ENABLED`, `WAYBACK_BACKFILL_ENABLED`
- **Rate limit:** 4 seconds between requests
