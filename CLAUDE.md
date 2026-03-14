# CLAUDE.md — Canadian Macro Strategic Dashboard

## What This Project Is
A weekly intelligence briefing platform covering Canadian national economic conditions, provincial policy, capital projects, markets, and events. Python discovery pipeline feeds a static HTML frontend via SQLite + GitHub Pages. Runs autonomously every Monday.

## Reference Document
For full system specification (25 sections, every feature detailed), see `COMPLETE_SYSTEM_SPECIFICATION.md` in the project root. Consult it before making architectural changes.

## Second Brain (Obsidian Vault)
- **Location:** `C:/Users/walte/OneDrive/SecondBrain/`
- **Project context:** `01-projects/can-macro-dashboard/context.md`
- **Access:** `claude --add-dir "C:/Users/walte/OneDrive/SecondBrain"`
- **Purpose:** Persistent context, decisions, debug journals, cross-session knowledge

## Architecture
- **Pipeline:** Python, async, multi-step. Entry point: `update_dashboard.py`
- **Frontend:** Static HTML + JS served via GitHub Pages from `docs/`
- **Database:** SQLite (`dashboard.db`) via `db.py` single interface module
- **Scheduling:** GitHub Actions — weekly Monday 5:30 AM ET + daily midnight ET
- **User submissions:** GitHub Issues templates — pipeline reads via API
- **Dependencies:** aiohttp, feedparser, beautifulsoup4, yfinance, reportlab, python-docx

## Model Stack (DO NOT CHANGE)
- **Gemini 2.5 Flash (NO GROUNDING):** Classification, extraction, RSS processing, rehash detection. FREE TIER. Code must NEVER pass `google_search` tool or `groundingConfig` to the API.
- **Claude Sonnet 4.6:** ALL reasoning and writing — briefing, executive summary, market commentary, policy assessment, pre-event analysis, Under the Microscope, gap analysis, extraction recovery, dedup QA, signal investigation, meta-analysis, selective extraction. ~$55/year.
- **Tavily:** Targeted enrichment searches only (cost-finding, verification, named tracking). Free tier 1,000 credits/month.
- **NO Claude Opus.** Removed (Phase 6). All writing goes through Claude Sonnet.
- **NO Gemini Pro.** Removed. All reasoning goes through Claude Sonnet.
- **NO Gemini grounded search.** Caused $136/day in charges. Replaced by Google News RSS.
- **NO Perplexity.** Removed. Do not add.
- **NO GDELT.** Removed. Do not add.
- **NO Claude Haiku in weekly pipeline.** Exception: seed_projects.py may use Haiku for one-time bulk seeding.

## Annual Budget: ~$60/year
Do not introduce paid services without explicit approval. Every new API must be free or use existing budgets.

## Editorial Policy: REPORTING ONLY — NO EDITORIALIZING
All output — briefings, market commentary, policy assessments, Under the Microscope, pre-event analysis — must be factual reporting. Present data, context, and connections. Never take positions, make recommendations, express opinions, or use language that implies something is good, bad, welcome, worrying, concerning, promising, or encouraging.

**Wrong:** "Alberta's energy sector faces a worrying decline as WTI drops below $70."
**Right:** "WTI fell below $70 this week. The database tracks 14 proposed Alberta oil sands projects with breakeven costs above $65, totaling $8.2B."

**Wrong:** "Ontario's housing policy is a welcome step that should accelerate development."
**Right:** "Ontario announced a housing accelerator policy. 23 proposed residential projects ($4.1B) would be eligible for expedited permitting under the new framework."

Rules:
- State what happened, what the data shows, and what is connected to what
- Let the reader draw their own conclusions
- Use specific numbers, project names, and source references
- Never say "should," "must," "hopefully," "unfortunately," "worrying," "promising," "encouraging," "welcome"
- Never recommend policy, investment, or business decisions
- Attribution over assertion: "The cross-reference engine links X to Y" not "X will cause Y"
- Conditional language for projections: "If rates hold, 23 projects would see..." not "23 projects will benefit"

## Discovery Pipeline (14 tiers)
1. Federal IAAC registry
2. Google News RSS search (759 queries converted to RSS URLs — replaces Gemini grounded search)
3. RSS feeds (201+ feeds, 6-layer remediated filter)
4. Project status monitoring
5. Provincial EA registries (13 provinces)
6. SEDAR+ securities filings
7. Crown corporation capital plans (25+)
8. Canada Energy Regulator
9. StatsCan building permits (anomaly signal)
10. Lobbyist registries (signal)
11. Municipal development applications (15 CMAs)
12. Google Alerts (~25 RSS alerts)
13. Industry trade RSS (~15 feeds)
14. University/institutional capital plans
Plus: Key people RSS feeds (processed through government bypass)

## Search Budget
- **Google News RSS:** Unlimited, free. Primary discovery layer.
- **Tavily:** 1,000 credits/month free. Cost-finding 300, named tracking 200, verification 200, enrichment 150, signals 100, buffer 50.
- **Gemini Flash (no grounding):** Unlimited free. Classification and extraction only.
- **NEVER use Gemini grounded search.** It costs $35 per 1,000 queries.

## RSS Filter (6 layers — order matters)
1. Government source bypass (skip to layer 6)
2. Dollar-value bypass ≥ province threshold (skip to layer 6)
3. Below-threshold dampener
4. Keyword co-occurrence (~80 project + ~30 economic signals)
5. Negative keywords (crime/sports/weather ONLY — NOT mall, housing, office, heritage)
6. Gemini Flash classification (uncertain = RELEVANT)

## Province GDP Thresholds
ON $500M, QC $250M, AB $200M, BC $175M, SK $45M, MB $40M, NS $25M, NB $20M, NL $17M, PE $5M, YT/NT/NU $3M

## Editorial Policy: REPORT, DO NOT EDITORIALIZE
All generated content must be factual reporting, not opinion or analysis.
- **DO:** "The BoC cut rates 25bps. The database contains 23 proposed residential projects ($4.2B) in rate-sensitive sectors."
- **DO NOT:** "This rate cut is good news for housing and should accelerate approvals."
- **DO:** "WTI fell 12% to $65. The database tracks 14 Alberta oil projects ($18B) with breakeven above $70."
- **DO NOT:** "This oil price decline threatens Alberta's energy sector outlook."
- State facts, present data, show connections between indicators and projects. Let readers draw their own conclusions.
- No predictions, no recommendations, no characterizing events as good/bad/bullish/bearish.
- Every claim must cite a source or reference specific data from the database.
- This applies to: weekly briefing, Under the Microscope, market commentary, policy sections, pre-event sections.

- **ADDITIVE ONLY for adaptive learning.** The system can add queries, keywords, feeds. It can NEVER remove existing ones.
- **URL hard gate.** Every project MUST have at least one verifiable source URL. No URL = no database write.
- **Evidence merge NEVER loses URLs.** During dedup, evidence arrays combine, never overwrite.
- **Government source bypass.** Articles from government domains skip RSS keyword filtering entirely.
- **Dollar-value bypass.** Articles with dollar values ≥ province threshold skip keyword filtering.
- **4-week lookback** on compound queries. Historical projects are found by the one-time sweep, not weekly queries.
- **Status never regresses.** Merge logic always advances to highest status.
- **Confidence range 0.0-1.0.** Decay applied after 30 days without re-discovery.

## Project Type Taxonomy (11 types — do not modify without approval)
greenfield, redevelopment, adaptive_reuse, major_renovation, expansion, retrofit, restoration, remediation, conversion, modernization, decommission_replace

## Sectors (18 NAICS-aligned — do not modify without approval)
oil_gas, mining, infrastructure, power_energy, manufacturing, transport_logistics, healthcare, education, residential, commercial_mixed, agriculture, forestry, defence, telecom, indigenous, environment, tourism_culture, government

## Confidence Scoring
- Base: 0.1
- +0.1 per evidence source (max 0.3)
- +0.15 per government source (max 0.3)
- +0.1 for verified value
- +0.05-0.1 for multi-tier discovery
- Decay: 31-60 days -0.05, 61-90 -0.10, 91-120 -0.15, 121+ -0.20 (flagged stale)

## Weekly Briefing Structure (8 sections, 1000-1500 words)
1. Headline — single most significant factual development
2. Macro Pulse — national indicators with period-over-period changes, sourced
3. Under the Microscope — factual deep-dive: what happened, what changed, which Canadian sectors/projects are in scope
4. Provincial Spotlight — one province's data: new projects, value, status changes
5. Sector Watch — sectors with largest volume/value changes, with numbers
6. Project Tracker — new projects discovered, status changes recorded, completions confirmed
7. Markets & Commodities — price movements stated factually, affected project counts from database
8. Looking Ahead — upcoming scheduled events (BoC dates, StatsCan releases, budget dates) with affected project counts

## Briefing Export
- PDF via reportlab, DOCX via python-docx
- Download buttons on frontend: `/api/briefing-download?format=pdf` and `?format=docx`

## Data Explorer (V-Code Search)
- Local fuzzy search over curated index (~40+ V-codes, growing)
- Gemini Flash fallback for queries the index can't match
- StatsCan table URL: `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}`
- Every result includes a "View on StatsCan" link

## Data Explorer (V-Code Search)
- Local fuzzy search over curated index (120+ entries across 9 categories)
- Categories: Labour Market, GDP, Construction, Housing, Prices, Trade, Rates, Energy, Demographics
- Includes: all 20 NAICS industry GDP, 10 provincial unemployment/employment/participation/CPI/GDP, 10 CMA permits, CPI components, 20 table-only references
- StatCan table URL: `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}`
- Pipeline fetches national + provincial: unemployment, employment rate, participation rate, CPI, GDP

## SQLite Tables (dashboard.db)
- `projects` — main project database
- `missed_projects` — user-submitted missed projects (via GitHub Issues)
- `pipeline_improvements` — adaptive learning improvements
- `indicator_history` — time series for all economic indicators
- `trend_snapshots` — weekly trend analysis snapshots
- `weekly_briefings` — generated briefings
- `dashboard_state` — frontend state, latest briefing, microscope history/override
- `miss_audit_results` — typed miss classifications from coverage audit (Phase 6)

## File Naming
- Step files: `STEP_2X_DESCRIPTION.md`
- Discovery: `google_news_rss_search.py`, `rss_filter.py`, `gov_sources.py`, `municipal_dev_apps.py`
- Search: `tavily_search.py` (targeted enrichment only)
- Reasoning: `claude_reasoning.py` (all reasoning — no gemini_pro_reasoning.py)
- Analysis: `sector_trends.py`, `cross_reference.py`, `indicator_trends.py`
- Frontend: `docs/index.html` (GitHub Pages root)

## Common Mistakes to Avoid
- Do not use Gemini grounded search — it costs $35/1,000 queries. Use Google News RSS instead.
- Do not pass `google_search` tool or `groundingConfig` to Gemini API — this enables grounding fees
- Do not use Gemini Pro — removed. All reasoning goes through Claude Sonnet.
- Do not use Perplexity, GDELT, or Haiku in the weekly pipeline
- Do not remove keywords from RSS filter (additive only)
- Do not skip dedup when writing to SQLite
- Do not create projects without source URLs
- Do not exceed 1,000 Tavily credits/month (free tier limit)
- Do not generate briefing content without real data — no fabrication
- Do not regress project status during merge
- Do not overwrite evidence arrays during dedup — always append/merge
- Do not add negative keywords that match legitimate project terms (mall, housing, office, heritage, downtown, Indigenous)
- Do not create new SQLite tables without documenting them here
- Do not editorialize — no predictions, no recommendations, no "good news/bad news" framing, no "bullish/bearish"
- Do not enable billing on any Google Cloud project without explicit approval
- Do not use Claude Opus — removed in Phase 6. All writing uses Sonnet.
