# STRUCTURE.md — Directory Layout & Organization

## Root Directory

```
AI newsletter/
├── .planning/                    # GSD planning documents
│   └── codebase/                 # This codebase map
├── public/                       # Firebase Hosting
│   ├── index.html                # Single-file SPA (entire frontend)
│   └── 404.html                  # Error page
├── functions/                    # Cloud Functions
│   ├── index.js                  # Scheduled triggers (weekly + daily)
│   └── package.json              # Node 20, firebase-admin/functions
├── backup_2026-03-02/            # Pre-restructure backup
├── backup_2026-03-03_pipeline_restructure/  # Pipeline restructure backup
│
├── ── Pipeline Entry ──
├── update_dashboard.py           # Main pipeline (7-step, all flags)
├── run_weekly_briefing.py        # Standalone briefing generation
├── seed_projects.py              # Legacy project seeding
├── seed_projects_v2.py           # Full project rebuild (Tier 1→2→3)
├── known_project_sweep.py        # One-time ~208 queries + 47 hardcoded
│
├── ── Configuration ──
├── pipeline_config.py            # Central config (models, schema, thresholds, NAICS)
├── rss_feeds.json                # 201+ RSS feeds (7 categories)
├── compound_queries_final.json   # 759 Google News RSS queries
├── watchlist.json                # Named project tracking list
├── .env                          # API keys, model routing, feature flags
├── firebase.json                 # Firebase Hosting + Functions config
├── firestore.rules               # Firestore security rules
├── serviceAccountKey.json        # Firebase service account (secret)
├── requirements.txt              # Python dependencies (16 packages)
│
├── ── Discovery (14 Tiers) ──
├── gov_sources.py                # Tier 1: StatCan + government registries
├── google_news_rss_search.py     # Tier 2: 759 compound queries as RSS
├── gdelt_monitor.py              # Tier 3: GDELT DOC 2.0 (reduced role)
├── rss_monitor.py                # Tier 4: 201+ RSS feeds
├── statcan_permits.py            # Tier 9: StatCan building permits
├── lobbyist_registries.py        # Tier 10: Lobbyist signals
├── municipal_dev_apps.py         # Tier 13: 15 CMAs (Socrata/CKAN + HTML)
├── institutional_capital.py      # Tier 14: Universities, hospitals
├── google_alerts.py              # Tier 12: Google Alerts RSS integration
├── key_people_tracker.py         # Key people RSS (gov bypass)
│
├── ── Search & Enrichment ──
├── tavily_search.py              # Tavily targeted searches (1000/mo)
├── gemini_search.py              # Legacy Gemini search logging
├── gemini_engine.py              # Gemini Flash extraction engine
├── cost_finder.py                # Project cost lookup
├── enrichment_queries.py         # Post-dedup enrichment (Gemini Flash)
├── compound_queries.py           # Query generation helpers
├── generate_compound_queries.py  # Query builder tool
├── capacity_queries.py           # Capacity-related queries
├── capacity_scheduler.py         # Query scheduling
│
├── ── AI Reasoning ──
├── claude_reasoning.py           # Claude Sonnet reasoning (all tasks)
│
├── ── Analysis ──
├── sector_trends.py              # Sector analysis
├── cross_reference.py            # Indicator ↔ project cross-reference
├── indicator_trends.py           # Indicator trend analysis
├── anomaly_detection.py          # Statistical anomaly detection
├── provincial_policy_monitor.py  # Province policy tracking
├── canadian_markets.py           # Market data collection
├── event_calendar.py             # Upcoming events (BoC, StatCan, budgets)
├── sentiment.py                  # Consumer sentiment (Reddit, Google Trends)
│
├── ── Project Management ──
├── project_sync.py               # Firestore upsert (dedup + merge)
├── project_dedup.py              # Deduplication logic
├── project_schema.py             # Project type taxonomy, brownfield detection
├── confidence_decay.py           # Confidence scoring + decay
├── lifecycle_monitor.py          # Project lifecycle tracking
│
├── ── Content Generation ──
├── weekly_briefing.py            # 8-section briefing structure
├── under_the_microscope.py       # Deep-dive topic selection + analysis
├── briefing_export.py            # PDF (reportlab) + DOCX (python-docx)
├── weekly_trend_report.py        # Trend report generation
│
├── ── Quality & Audit ──
├── article_filter.py             # 6-layer RSS filter
├── citation_audit.py             # Citation verification + link rot
├── quality_report.py             # Pipeline quality metrics
├── coverage_audit.py             # Discovery coverage analysis
├── dedup_audit.py                # Dedup verification
├── url_utils.py                  # URL normalization helpers
├── url_verifier.py               # URL verification
├── url_verify.py                 # Legacy URL checker
├── deep_verification.py          # Deep source verification
│
├── ── Data & State ──
├── pipeline_state.py             # Firestore pipeline state helpers
├── learning_store.py             # Adaptive learning storage
├── named_tracker.py              # Named project tracking
├── wayback.py                    # Wayback Machine archival
│
├── ── Backfill Scripts ──
├── backfill_timeseries.py
├── backfill_descriptions.py
├── backfill_global_indicators.py
├── backfill_indicator_history.py
├── backfill_project_fields.py
├── backfill_project_values.py
├── backfill_commodity_timeseries.py
│
├── ── Tests ──
├── test_dedup.py                 # Dedup logic tests
├── test_rss_filter.py            # RSS filter tests
├── test_compound_queries.py      # Query validation tests
├── test_brownfield_discovery.py  # Brownfield detection tests
│
├── ── Archived / Removed ──
├── compound_discovery.py.bak     # Gemini grounded search (REMOVED)
├── gemini_pro_reasoning.py.bak   # Gemini Pro reasoning (REMOVED)
├── pro_dedup_analysis.py.bak     # Pro dedup (REMOVED)
├── pro_extraction_recovery.py.bak
├── pro_gap_analysis.py.bak
├── pro_meta_analysis.py.bak
├── pro_signal_analysis.py.bak
├── perplexity_search.py          # Still exists but weekly pipeline disabled
│
├── ── Spec & Docs ──
├── CLAUDE.md                     # Project instructions for Claude Code
├── COMPLETE_SYSTEM_SPECIFICATION.md  # Full 25-section system spec
├── STEP_2N_POLICY_MARKETS_EVENTS_NARRATIVE.md
├── STEP_2O_VCODE_SEARCH_ENGINE.md
├── STEP_2P_PEOPLE_EXPORT_SWEEP.md
├── STEP_2Q_SEARCH_REPLACEMENT_FRONTEND_FIX.md
│
└── ── Data Files ──
    ├── canada_tracker_master_watchlist.csv
    ├── *.json (backup files)
    ├── *.log (seed run logs)
    └── *.txt (audit/filter logs)
```

## Naming Conventions

### Files
- **Pipeline modules:** `snake_case.py` — descriptive names matching function
- **Step specs:** `STEP_2X_DESCRIPTION.md` — numbered implementation specs
- **Config:** `snake_case.json` or `snake_case.py`
- **Archived:** `*.bak` suffix for removed modules
- **Tests:** `test_*.py` prefix

### Functions
- `fetch_*` — Data retrieval from external APIs
- `run_*` — Pipeline execution entry points
- `upsert_*` — Firestore write with dedup
- `norm_*` / `normalize_*` — Data normalization
- `infer_*` — Heuristic inference (e.g., NAICS from name)
- `make_*` — Factory functions (e.g., `make_project()`)
- `_private_*` — Internal helpers (underscore prefix)

### Constants
- `UPPER_CASE` for all constants
- Model names: `OPUS_MODEL`, `SONNET_MODEL`, `GEMINI_MODEL`
- Feature flags: `*_ENABLED` suffix
- Budget caps: `*_MAX_*` pattern

## Key Locations
- **Entry point:** `update_dashboard.py` — start here to understand the pipeline
- **Config hub:** `pipeline_config.py` — all constants, thresholds, schema
- **Feed config:** `rss_feeds.json` — all 201+ RSS feeds
- **Frontend:** `public/index.html` — entire dashboard UI
- **Scheduling:** `functions/index.js` — Cloud Functions triggers
- **AI reasoning:** `claude_reasoning.py` — all Claude API calls
