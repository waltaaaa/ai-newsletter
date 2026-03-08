# CONCERNS.md — Technical Debt & Issues

## Critical Safety Constraints
These are by-design constraints, not bugs. Violating them causes real cost/data issues:
- **Gemini grounding DISABLED** — `GEMINI_SEARCH_ENABLED=false`. Enabling costs $35/1000 queries ($136/day incident occurred)
- **Tavily budget cap** — 1,000 credits/month free tier. No enforcement mechanism in code
- **URL hard gate** — No URL = no Firestore write. Must not be bypassed
- **Evidence merge** — Arrays combine, never overwrite. Status never regresses
- **Additive-only** — System can add queries/keywords/feeds, never remove existing ones

## Technical Debt

### Archived but not removed
- `compound_discovery.py.bak` — Gemini grounded search (removed)
- `gemini_pro_reasoning.py.bak` — Gemini Pro (removed)
- `pro_dedup_analysis.py.bak`, `pro_extraction_recovery.py.bak`, `pro_gap_analysis.py.bak`, `pro_meta_analysis.py.bak`, `pro_signal_analysis.py.bak` — All removed Pro modules
- `perplexity_search.py` — Still exists as file, disabled in weekly pipeline
- These `.bak` files add confusion about what's active

### Inconsistent module boundaries
- `update_dashboard.py` is the monolith entry point importing from many modules
- `gemini_search.py` still exists (legacy logging helper `log_gemini_unique`) despite search being removed
- `gemini_engine.py` vs `gemini_search.py` — unclear separation

### Configuration scattered
- Constants split between `.env`, `pipeline_config.py`, `rss_feeds.json`, and hardcoded in individual modules
- Model routing defined in `pipeline_config.py` but also referenced in `.env`
- Province thresholds in `pipeline_config.py` but also mentioned in CLAUDE.md

### No dependency pinning
`requirements.txt` has no version pins (e.g., `firebase-admin` not `firebase-admin==6.x`). Builds are not reproducible.

## Known Issues

### GDELT network
- Port 443 (HTTPS) TCP-blocked by ISP — forced to use HTTP
- Default gdeltdoc User-Agent blocked — requires spoofed UA via `_GdeltDocPatched`
- Bail-out after 3 consecutive failures (may miss valid data)

### Yahoo Finance
- `PN=F` ticker delisted — non-blocking warning but data gap
- yfinance subject to rate limiting and API changes

### Anthropic credits
- Need manual top-up at console.anthropic.com
- Pipeline completes without AI analysis but loses reasoning quality

### Firebase deploy
- Standard `firebase` CLI OOMs when `index.html` >1700 lines
- Requires `node --max-old-space-size=4096` workaround

## Security Concerns

### Service account key
- `serviceAccountKey.json` in project root — must never be committed
- No `.gitignore` observed (project is not a git repo)

### API keys in environment
- All keys in `.env` file — standard practice but no encryption at rest
- No secret rotation policy

### External response validation
- RSS feeds, GDELT, government APIs return unvalidated data that flows into Firestore
- Gemini Flash classification is the gatekeeper but "uncertain = RELEVANT" policy is permissive
- No input sanitization documented for project names/descriptions before Firestore write

## Performance Concerns

### Sequential RSS processing
- 201+ RSS feeds processed sequentially in `rss_monitor.py`
- Could benefit from async/concurrent fetching (aiohttp already a dependency)

### Firestore write patterns
- `upsert_flat_projects()` does individual document reads for dedup before writes
- High-volume discovery weeks could hit Firestore read quotas

### Single-file frontend
- `public/index.html` is the entire SPA — growing complexity
- No code splitting, lazy loading, or component separation
- Firebase deploy OOM already occurring at >1700 lines

### No caching layer
- Every frontend load reads directly from Firestore
- No CDN caching for static data (indicators, historical trends)

## Scaling Limits

### Project database growth
- No archival strategy for completed/cancelled projects
- Evidence arrays grow unbounded per project
- Confidence decay flags stale projects but doesn't remove them

### Query volume
- 759 Google News RSS queries — additive-only means this grows monotonically
- 201+ RSS feeds — same growth pattern
- No pruning mechanism for underperforming queries/feeds

### Briefing generation
- Claude API calls for 8-section briefing could timeout on slow weeks
- No retry/resume for partial briefing generation

## Test Coverage Gaps
- No E2E pipeline tests
- No integration tests for AI API calls
- No Firestore read/write tests
- No frontend tests
- Only 4 test files covering dedup, RSS filter, queries, and brownfield detection
- No CI/CD pipeline — all tests manual
- See `TESTING.md` for full gap analysis

## Missing Operational Features
- No cost monitoring or alerting (Tavily budget, Anthropic spend)
- No health checks or uptime monitoring
- No audit trail for pipeline runs (partial: seed audit logs exist)
- No rollback mechanism for bad Firestore writes
- No data backup automation (manual backups in `backup_*` directories)

## Editorial Policy Risk
- AI-generated content must follow strict no-editorializing rules
- No automated check for subjective language in generated briefings
- Relies on prompt engineering — could drift with model updates
