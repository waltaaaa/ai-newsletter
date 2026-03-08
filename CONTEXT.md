# CONTEXT.md — Canadian Macro Strategic Dashboard

## What This Project Is
A weekly Canadian economic intelligence briefing platform. A Python pipeline discovers capital projects (infrastructure, mining, energy, housing, etc.) across all 13 provinces, tracks economic indicators, monitors policy changes, and generates an automated weekly briefing. The output is a public-facing interactive dashboard hosted as a static website.

## Current State (March 7, 2026)

### What Works
- 759 compound discovery queries defined in `compound_queries_final.json`
- 201+ RSS feeds with a 6-layer remediated filter (government bypass, dollar bypass, keyword co-occurrence, negative keywords, Gemini Flash classification)
- 14 discovery tiers defined (IAAC registry, Gemini search, RSS, EA registries, SEDAR+, CER, municipal APIs, Google Alerts, etc.)
- Project deduplication with confidence scoring and evidence merging
- Brownfield project taxonomy (11 types) and 18 NAICS-aligned sectors
- Historical backfill functions for projects, BoC, StatsCan, Yahoo Finance
- Claude Sonnet reasoning module (`claude_reasoning.py`) for briefing, commentary, policy assessment
- Weekly briefing generator with 8-section structure
- Frontend in `public/index.html` — single-file HTML with project cards, filters, badges
- 32,201 projects in Firestore database
- Anthropic API key active with spending cap
- Tavily API key available

### What's Broken / Needs Fixing
- **Gemini grounded search disabled** — was costing $136/day ($35 per 1,000 queries via Google Search grounding fees). API key deleted. All grounding code commented out. Pipeline cannot run discovery until search layer is replaced.
- **No scheduled automation** — Cloud Functions require Firebase Blaze plan. Currently on Spark (free). Pipeline runs manually only.
- **Frontend can't display projects properly** — `loadProjects()` fetches only 500 of 32,201 projects. `PROV_THRESHOLDS` uses full province names but Firestore stores codes. Projects below threshold still showing.
- **Gemini Pro still referenced** — `update_dashboard.py:3435` and `weekly_trend_report.py` still call Gemini Pro. Module exists but should be removed.
- **Duplicates likely** — 32,201 projects almost certainly contains duplicates from multiple discovery sources
- **Perplexity and GDELT removed from imports** — but some variable names and comments still reference them

### What's Being Changed (This Milestone)
1. **Firestore → SQLite** — Replace all Firestore with local `dashboard.db`
2. **Firebase Hosting → GitHub Pages** — Static JSON export, free unlimited hosting
3. **Gemini grounded search → Google News RSS** — Convert 759 queries to free RSS feeds
4. **Add Tavily** — 1,000 free credits/month for targeted enrichment
5. **Remove Gemini Pro** — All reasoning through Claude Sonnet only
6. **Fix frontend** — Province normalization, threshold logic, province-scoped loading
7. **Interactive indicator chart** — Replace static cards with Chart.js
8. **Dedup audit** — Find and merge duplicates

## Architecture After This Milestone

```
Pipeline (Python, runs weekly):
  Google News RSS (759 feeds) ──→ 6-layer filter ──→ Gemini Flash (classify/extract) ──→ SQLite
  RSS feeds (201+) ────────────→ 6-layer filter ──→ Gemini Flash (classify/extract) ──→ SQLite
  Government registries ───────→ Direct scrape ───→ SQLite
  Tavily (targeted search) ────→ Gemini Flash (extract) ──→ SQLite
  Enrichment/Intelligence ─────→ Claude Sonnet (reasoning) ──→ SQLite
  Briefing generation ─────────→ Claude Sonnet ──→ SQLite
  Export ───────────────────────→ Static JSON files ──→ GitHub Pages

Frontend (static HTML + JSON):
  GitHub Pages serves index.html + data/*.json
  Browser loads JSON, all interactivity is client-side JavaScript
  Zero database queries from visitors
```

## Model Stack

| Model | Role | Cost |
|---|---|---|
| Gemini 2.5 Flash (NO grounding) | Classification, extraction, RSS processing | $0 |
| Claude Sonnet 4.5 | ALL reasoning — briefing, commentary, policy, microscope, gap analysis, dedup QA, extraction recovery, signal investigation, meta-analysis | ~$55/yr |
| Tavily | Targeted enrichment: cost-finding, verification, named tracking | $0 (1,000/month free) |
| Google News RSS | Primary web search replacement | $0 (unlimited) |

**Banned models/services:**
- Gemini grounded search (costs $35/1,000 queries — caused $136/day charge)
- Gemini Pro (removed, tasks moved to Claude Sonnet)
- Perplexity (removed)
- GDELT (removed)
- Claude Haiku in weekly pipeline (exception: one-time bulk seeding only)

## Project Structure

```
AI newsletter/
├── .claude/
│   ├── skills/
│   │   └── statcan/
│   │       └── SKILL.md          # StatsCan/BoC data parsing skill
├── .env                           # API keys (Anthropic, Tavily, Gemini disabled)
├── CLAUDE.md                      # Claude Code guardrails (read every session)
├── COMPLETE_SYSTEM_SPECIFICATION.md  # 25-section full system spec
├── CONTEXT.md                     # This file
├── compound_queries_final.json    # 759 discovery queries
├── update_dashboard.py            # Main pipeline orchestrator (~3700 lines)
├── public/
│   └── index.html                 # Single-file frontend
├── data/                          # Static JSON exports (new)
├── docs/                          # GitHub Pages root (new)
│
├── # Discovery modules
├── google_news_rss_search.py      # New — replaces Gemini grounded search
├── compound_discovery.py          # Gemini caller (grounding disabled)
├── rss_filter.py                  # 6-layer RSS filter
├── rss_monitor.py                 # RSS feed poller
├── gov_sources.py                 # EA registries, SEDAR+, CER scrapers
├── municipal_dev_apps.py          # Municipal development application scrapers
├── gdelt_monitor.py               # DEPRECATED — do not use
│
├── # Enrichment modules
├── tavily_search.py               # New — targeted search
├── cost_finder.py                 # Find dollar values for projects
├── deep_verification.py           # Second-source confirmation
├── lifecycle_monitor.py           # Status monitoring for tracked projects
├── enrichment_queries.py          # Fill missing project fields
├── missed_project_enrichment.py   # Enrich user-submitted projects
├── missed_project_diagnostics.py  # Diagnose why projects were missed
│
├── # Intelligence modules
├── confidence_decay.py            # Time-based confidence reduction
├── anomaly_detection.py           # Value/status/proponent change detection
├── named_tracker.py               # Top 200 project tracking
│
├── # Analysis modules
├── sector_trends.py               # Period-over-period trend analysis
├── cross_reference.py             # Indicator → project linkage
├── indicator_trends.py            # Indicator historical comparison
│
├── # Reasoning modules
├── claude_reasoning.py            # ALL reasoning (Sonnet)
├── gemini_pro_reasoning.py        # DEPRECATED — remove, move tasks to claude_reasoning.py
├── weekly_trend_report.py         # DEPRECATED — uses Gemini Pro, rewrite for Sonnet
│
├── # Output modules
├── weekly_briefing.py             # Generate weekly briefing via Claude Sonnet
├── under_the_microscope.py        # Deep-dive topic selection and analysis
├── briefing_export.py             # PDF/DOCX generation
├── export_dashboard.py            # New — SQLite to static JSON export
├── deploy_to_github.py            # New — push to GitHub Pages
│
├── # Data modules
├── db.py                          # New — SQLite interface (replaces all Firestore calls)
├── project_sync.py                # Project write/merge to database
├── project_dedup.py               # Deduplication logic
├── vcode_index.py                 # CANSIM V-code curated index
├── vcode_search.py                # Fuzzy V-code search
├── indicator_registry.py          # Tracked indicator metadata
├── backfill_timeseries.py         # BoC indicator backfill
├── backfill_commodity_timeseries.py # Yahoo Finance backfill
├── historical_backfill.py         # Project seed backfill
│
├── # Policy & Markets
├── provincial_policy_monitor.py   # Policy RSS monitoring
├── canadian_markets.py            # Canadian-specific commodity tracking
├── event_calendar.py              # Economic event calendar
├── key_people_tracker.py          # Key decision-maker monitoring
│
├── # Utility
├── quality_report.py              # Pipeline quality metrics
├── learning_store.py              # Adaptive learning improvements
├── pipeline_state.py              # Pipeline state management
├── sentiment.py                   # Sentiment analysis
├── wayback.py                     # Wayback Machine scraping
│
├── # One-time scripts
├── migrate_firestore_to_sqlite.py # New — one-time migration
├── known_project_sweep.py         # One-time comprehensive project discovery
├── seed_projects.py               # Initial project seeding (uses Haiku)
├── backfill_descriptions.py       # One-time description backfill
├── backfill_project_values.py     # One-time value backfill
│
├── # Config
├── rss_feeds.json                 # RSS feed URLs
├── firebase.json                  # Firebase config (being removed)
├── functions/                     # Cloud Functions (being removed)
│   └── index.js
└── dashboard.db                   # New — SQLite database
```

## Database Schema (SQLite — new)

### projects
All capital projects tracked by the pipeline.
- id (TEXT PK), name, province (2-letter code), city, cma, sector (18 options), project_type (11 options), status (proposed/approved/under_construction/completed/delayed/on_hold/cancelled), value_millions (REAL, nullable), proponent, description
- confidence (0.0-1.0), display_confidence (with decay), evidence_count, is_brownfield, is_stale, needs_review, has_anomalies, days_since_update
- cost_search_attempts, cost_unfindable, last_cost_search, needs_enrichment, needs_cost_search
- discovery_sources (JSON text), anomalies (JSON text)
- year_first_tracked, backfill_source, first_seen, last_updated

### evidence
Source URLs for each project. Never deleted during merge — only appended.
- id (INTEGER PK), project_id (FK), url, url_normalized, source_type, authority, date, name, url_valid, is_known_source

### indicator_history
All economic indicator time series (5 years backfill + weekly live).
- indicator + province + date (composite PK), value, unit, source, frequency, description, backfilled

### weekly_briefings
Generated weekly intelligence briefings.
- date (PK), week_number, year, content, microscope_topic, metadata (JSON)

### missed_projects, pipeline_improvements, dashboard_state
Supporting tables for adaptive learning and frontend state.

## Province GDP Thresholds (minimum project value to display)
ON $500M, QC $250M, AB $200M, BC $175M, SK $45M, MB $40M, NS $25M, NB $20M, NL $17M, PE $5M, YT/NT/NU $3M
Projects with no value are shown as "unconfirmed" — NOT excluded.

## Confidence Scoring
Base 0.1. +0.1 per evidence source (max 0.3). +0.15 per government source (max 0.3). +0.1 for verified value. +0.05-0.1 multi-tier discovery. Decay: 31-60d -0.05, 61-90d -0.10, 91-120d -0.15, 121+ -0.20 (flagged stale).

## Weekly Briefing Structure (8 sections, 1000-1500 words)
1. Headline
2. Macro Pulse
3. Under the Microscope (deep-dive on dominant story)
4. Provincial Spotlight
5. Sector Watch
6. Project Tracker
7. Markets & Commodities
8. Looking Ahead

## Editorial Policy
REPORTING ONLY. No editorializing. State facts, data, connections. Never use "worrying," "promising," "welcome," "unfortunately," "should," "must." Use conditional language for projections: "If X holds, Y projects would..." not "Y projects will benefit." Tone: Reuters wire service.

## Key Constraints
- ADDITIVE ONLY for adaptive learning — never remove queries, keywords, or feeds
- URL hard gate — every project must have at least one source URL
- Evidence merge never loses URLs — always append during dedup
- Status never regresses during merge — always advance to highest
- Government source bypass — gov articles skip RSS keyword filtering
- Dollar-value bypass — articles with values ≥ province threshold skip filtering
- NEVER pass grounding config to Gemini — costs $35/1,000 queries
- Anthropic spending cap is set — do not remove or increase without approval
- Tavily: do not exceed 1,000 credits/month

## Files to Read
- `CLAUDE.md` — guardrails, read first every session
- `COMPLETE_SYSTEM_SPECIFICATION.md` — 25-section full spec
- `STEP_2Q_SEARCH_REPLACEMENT_FRONTEND_FIX.md` — implementation details for search/frontend
- `STEP_2P_PEOPLE_EXPORT_SWEEP.md` — key people tracking, briefing export, known-project sweep, Under the Microscope
- `STEP_2N_POLICY_MARKETS_EVENTS_NARRATIVE.md` — policy monitor, markets, events, briefing prompts
- `STEP_2O_VCODE_SEARCH_ENGINE.md` — CANSIM V-code search
