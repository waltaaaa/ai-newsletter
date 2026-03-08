# STACK.md — Technology Stack

## Languages & Runtime

| Language | Version | Usage |
|----------|---------|-------|
| Python | 3.12+ | Pipeline, scrapers, AI orchestration, analysis |
| JavaScript | Node 20 | Cloud Functions (scheduling only) |
| HTML/CSS/JS | ES6+ | Single-file frontend SPA |

## Frameworks & Libraries

### Python Pipeline (requirements.txt)
- `firebase-admin` — Firestore read/write, Firebase Storage uploads
- `yfinance` — Yahoo Finance market data (commodities, equities, yields)
- `requests` — HTTP client for government APIs, RSS fallback
- `pytz` — Timezone handling (ET for scheduling)
- `feedparser` — RSS/Atom feed parsing (201+ feeds)
- `google-generativeai` — Gemini 2.5 Flash (classification/extraction only, NO grounding)
- `python-dotenv` — Environment variable loading from `.env`
- `anthropic` — Claude Sonnet API (all reasoning tasks)
- `beautifulsoup4` + `lxml` — HTML scraping (government registries, institutional capital)
- `gdeltdoc` — GDELT DOC 2.0 API client (patched for User-Agent)
- `tavily-python` — Tavily search API (optional import, 1000 credits/month free)
- `aiohttp` + `nest_asyncio` — Async HTTP for concurrent API calls
- `reportlab` — PDF generation for briefing export
- `python-docx` — DOCX generation for briefing export

### Frontend (public/index.html)
- Tailwind CSS (CDN) — Utility-first styling
- Chart.js (CDN) — Indicator charts, yield curve, commodity charts
- D3.js (CDN) — Data visualization
- Firebase JS SDK (CDN) — Firestore client, Auth

### Cloud Functions (functions/package.json)
- `firebase-admin` ^12.0.0
- `firebase-functions` ^5.0.0
- Node 20 runtime

## AI Model Stack

| Model | Role | Cost |
|-------|------|------|
| Claude Opus 4.6 | Executive summary, national analysis, global vectors, narrative prose | ~$7/yr |
| Claude Sonnet 4.6 | Extraction, provincial/industry writing, citation checks, all reasoning | ~$25/yr |
| Gemini 2.5 Flash | Classification, JSON extraction, Wayback parsing (NO grounding) | Free |
| Tavily | Targeted enrichment searches (cost-finding, verification, tracking) | Free tier (1000/mo) |

**Removed:** Gemini Pro, Gemini grounded search, Perplexity (in weekly pipeline), GDELT as primary, Claude Haiku

## Configuration

### Environment Variables (.env)
- `FIREBASE_PROJECT_ID` — `can-macro-dashboard`
- `OPUS_MODEL` / `SONNET_MODEL` / `GEMINI_MODEL` — Model routing
- `YAHOO_FINANCE_ENABLED` — Feature flag for market data
- `WAYBACK_ENABLED` / `WAYBACK_SAVE_ENABLED` / `WAYBACK_BACKFILL_ENABLED` — Wayback Machine controls
- `GEMINI_SEARCH_ENABLED` — Must be `false` (grounded search disabled)
- `PERPLEXITY_ENABLED` — Monthly deep-sweep only
- API keys for Anthropic, Google AI, Tavily (secrets — not committed)

### Config Files
- `pipeline_config.py` — Model routing, project schema, GDP thresholds, NAICS map, status normalization, dedup logic
- `rss_feeds.json` — 201+ RSS feeds across 7 categories (federal, provincial, municipal, CBC, CTV, Postmedia, independent, industry, key_people)
- `compound_queries_final.json` — 759 Google News RSS query definitions
- `watchlist.json` — Project watchlist for named tracking
- `firebase.json` — Firebase Hosting + Functions config
- `firestore.rules` — Firestore security rules
- `serviceAccountKey.json` — Firebase service account (secret)

## Infrastructure

- **Database:** Google Cloud Firestore (7 collections)
- **Hosting:** Firebase Hosting (single-file SPA)
- **Storage:** Firebase Storage (briefing PDF/DOCX exports)
- **Scheduling:** Cloud Functions — weekly Monday 6AM ET + daily midnight ET
- **Budget:** ~$60/year total across all services
