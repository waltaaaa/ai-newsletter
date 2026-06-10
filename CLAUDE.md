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
- **Dependencies:** aiohttp, feedparser, beautifulsoup4, yfinance, reportlab, python-docx, trafilatura

## Model Stack (DO NOT CHANGE)
- **Claude Code Agents (subscription, $0 API cost):** ALL writing and reasoning runs via `claude -p` subprocess on user's Claude subscription. Covers: macro/industry writing agents (~30 agents), province writing agents (13 agents), weekly briefing, executive summary, market commentary, policy assessment, pre-event analysis, Under the Microscope, project extraction, gap analysis, extraction recovery, dedup QA, signal investigation, meta-analysis, selective extraction, citation audit, context lines, JSON repair fallback.
- **Groq LLaMA 3.3 70B:** Fallback classifier — Layer 6 RSS classification, JSON repair, sentiment. FREE TIER (6K TPM / 500K TPD).
- **NVIDIA NIM (free tier, 40 RPM shared):**
  - Nemotron 3 Super 120B — L6 article classification (primary) + deep extraction + JSON repair + rehash detection
  - DeepSeek V3.2 — second-opinion on hardest extraction cases
  - Llama Nemotron Rerank 1B v2 — L7 article relevance scoring + search result scoring
  - Llama Nemotron Embed 1B v2 — semantic article dedup + semantic project dedup (26-language support)
  - Nemotron OCR v1 — provincial PDF text extraction
- **NO Ollama/Qwen.** Removed. All classification runs through NIM Nemotron (Groq fallback).
- **Tavily:** Targeted enrichment searches only (cost-finding, verification, named tracking). Free tier 1,000 credits/month.
- **Anthropic API:** OPTIONAL fallback only. Set `REASONING_AGENT_MODE=api` / `WRITING_AGENT_MODE=api` / `PROVINCE_AGENT_MODE=api` to use API instead of Claude Code agents. Required for GitHub Actions where `claude` CLI is unavailable.
- **NO Gemini in active pipeline.** Removed from classification chain. Legacy fallback only. Code must NEVER pass `google_search` tool or `groundingConfig` to the API.
- **NO Gemini Pro.** Removed. All reasoning goes through Claude agents.
- **NO Gemini grounded search.** Caused $136/day in charges. Replaced by Google News RSS.
- **NO Perplexity.** Removed. Do not add.
- **NO GDELT.** Removed. Do not add.

## Annual Budget: ~$20/year (Tavily only)
Claude API costs eliminated by Claude Code agents running on subscription. Do not introduce paid services without explicit approval. Every new API must be free or use existing budgets.

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
2. Google News RSS search (2,574 compound queries + ~100 three-digit NAICS × 41 CMA expansion queries, deduped to unique RSS URLs)
3. RSS feeds (324+ feeds, 6-layer remediated filter)
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
Plus: Procurement monitor — federal/provincial contract awards and tenders (Open Canada, BuyAndSell, Ontario BPS, BC Bid). Filters for construction/infrastructure >=5M. Links awards to existing projects. Zero cost.
Plus: Corporate newswires — 12 RSS feeds from GlobeNewswire, Canada Newswire, and Cision covering mining, energy, real estate, construction, manufacturing, transport, and government press releases. Pre-filtered for Canadian relevance before entering the 6-layer RSS filter. Zero cost.
Plus: IAAC status tracker — monitors federal Impact Assessment Registry for status transitions (planning, public comment, panel review, decision). Updates project statuses and detects new IAAC projects. Zero cost.
Plus: Regulatory feeds — 10 CanLII RSS feeds covering Federal Court, CER, Ontario LPAT, Ontario/BC/Alberta environmental tribunals, BC/Alberta utilities commissions, Quebec TAQ, and Saskatchewan Municipal Board. Pre-filtered for project relevance (>=2 keyword matches). Regulatory decisions carry status signals: approvals, denials, compliance orders, and stop-work orders map to project status updates. Tagged as government sources — bypass RSS keyword filter (L1). Zero cost.

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
6. LLM classification: NIM Nemotron Super 120B → Groq LLaMA 3.3 70B → fail-open (uncertain = RELEVANT)
7. NIM Rerank: relevance scoring of classified articles, top-N pass to extraction

Pre-filter step 1: Metadata tagging — articles tagged with sector (NAICS keys) and geography (province codes) using 6 signal layers: source domain, feed label, RSS categories, URL path, headline geography, headline keywords. Zero API cost. Tags flow through to L1 (metadata boost bypasses keyword check), Claude extraction (sector/province hints), and cross-reference engine (article-indicator alignment).

Pre-filter step 2: Articles with snippets shorter than 80 chars are enhanced via trafilatura (primary, purpose-built news article extractor) + sumy (LexRank extractive summarization) before entering the 6-layer filter. trafilatura handles boilerplate removal, varied HTML layouts, and paywall stubs better than basic BeautifulSoup parsing. Falls back to BeautifulSoup if trafilatura is unavailable or returns nothing. This improves L4 keyword co-occurrence and L6 LLM classification accuracy. Zero API cost. Fails gracefully — original snippet preserved on any error. Government sources are skipped (they already bypass L1+L2).

## Province GDP Thresholds
ON $500M, QC $250M, AB $200M, BC $175M, SK $45M, MB $40M, NS $25M, NB $20M, NL $17M, PE $5M, YT/NT/NU $3M

## Pipeline Invariants (non-negotiable)
- **ADDITIVE ONLY for adaptive learning.** The system can add queries, keywords, feeds. It can NEVER remove existing ones.
- **URL hard gate.** Every project MUST have at least one verifiable source URL. No URL = no database write.
- **Evidence merge NEVER loses URLs.** During dedup, evidence arrays combine, never overwrite.
- **Government source bypass.** Articles from government domains skip RSS keyword filtering entirely.
- **Dollar-value bypass.** Articles with dollar values ≥ province threshold skip keyword filtering.
- **4-week lookback** on compound queries. Historical projects are found by the one-time sweep, not weekly queries.
- **Status never regresses.** Merge logic always advances to highest status. Cancelled is terminal and always applies. Hold states (On Hold/Suspended/Paused) apply only with an explicit or government-backed signal (patch-1.3 C5) — a media "delayed" mention is logged but does not change status.
- **Confidence range 0.0-1.0.** Decay applied after 30 days without re-discovery.
- **Callout quality contract.** Every insight chart spec MUST carry a non-empty `callout` string. `national.chart_callout` and each non-empty `global[i].chart_callout` MUST also be present. Callouts are 60–240 chars, cite ≥1 chart data point, reference ≥1 pipeline-tracked artifact, and contain zero banned editorial words. Every insight chart spec MUST also carry a non-empty `chartType` (enum: line / multi_line / bar / diverging_bar), `title`, and `dataKeys[]` — the frontend silently drops charts missing `dataKeys` and degrades on missing `chartType`/`title`; `subtitle` is validator-warned when absent. `tools/validate_briefing_schema.py` enforces. Skills MUST raise a loud error rather than emit empty or placeholder callouts or chart specs.
- **External data files are validator-gated.** The frontend reads `docs/data/policy.json`, `projects_all.json`, `timeseries.json`, `indicators.json`, `events.json`, and `events_global.json` directly (not through the briefing). `tools/validate_briefing_schema.py` Phase 2 (`_validate_data_dir`) checks shape, freshness, and cross-references every `insightCharts[].dataKeys[]` against the underlying series in timeseries.json / indicators.history. A missing dataKey means a silent blank chart in production — the cross-reference check surfaces these gaps at deploy time.
- **Validator is a deploy gate.** `tools/validate_briefing_schema.py` MUST pass with 0 FAIL before any export, commit, or deploy. Enforced at four chokepoints: GATE 3.5 (post-assembly) and GATE 4 (post-charts) in `tldr-conductor`, the new GATE PRE-DEPLOY (final re-validation in `tldr-conductor` before the Deploy step), and a post-export call in `update_dashboard.py` that fails the process on exit code 1. `.github/workflows/weekly-pipeline.yml` and `daily-indicators.yml` also run the validator as a step that fails the job on FAIL. WARN (exit 2) does not block; FAIL (exit 1) always blocks. No override flag, no bypass. The daily run cannot clobber required fields — if it does, the workflow fails before deploy.

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

The briefing integrates data from: indicator history, project database, discovery articles, policy tracker (legislative/regulatory developments), job monitor (hiring spikes), procurement monitor (contract awards), IAAC status changes, and regulatory tribunal decisions. All sources cited factually per editorial policy.

## Claude Analysis Calls — Additional Context (from Prompts 11-19)
| Call | Additional Context |
|------|-------------------|
| 1 (Macro) | Policy summary, top hiring spikes, procurement ≥$10M, IAAC changes, extended StatCan summary |
| 2 (Industries) | Per-sector signals: policy items, hiring spikes, procurement awards |
| 3 (Provinces) | Per-province signals: policy items, hiring spikes, procurement awards, IAAC changes |

## Insight Charts (Agent 4 — tldr-charts)
- **Skill:** `.claude/skills/tldr-charts/SKILL.md`
- **Purpose:** Generates 2 data visualizations per province + 2 for National (28 total per briefing)
- **Runs after:** Writer agent (Agent 3) completes the briefing narrative
- **Output:** Adds `insightCharts` array (2 chart specs) to top-level JSON and to each province object
- **Data source:** `timeseries.json` (102 keys — commodities, provincial indicators, indices, currencies)
- **Chart types:** `line` (trends), `bar` (comparisons), `diverging_bar` (changes)
- **Design reference:** `.claude/skills/lagging_indicator_charts.md` (10-chart design library)
- **Frontend rendering:** `buildAgentInsightStripMulti()` and `renderAgentInsightChartMulti()` in `app.js`
- **Backward compatible:** Falls back to single `insightChart` or keyword-based charts if `insightCharts` array is absent

## Briefing Export
- PDF via reportlab, DOCX via python-docx
- Download buttons on frontend: `/api/briefing-download?format=pdf` and `?format=docx`

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
- `job_snapshots` — weekly job posting aggregates and hiring spike alerts
- `procurement_snapshots` — weekly government procurement contract snapshots
- `policy_snapshots` — weekly policy/legislative developments with sector/project linkages
- `project_alerts` — Google News RSS tracking per project (auto-registered on discovery, monthly check, deactivated on Cancelled/Complete)

## Directory Structure
- `phases/` — Pipeline phase modules (data_collection, discovery, filtering, analysis, etc.)
- `tools/` — Utilities, seeders, audits, deploy, export (`deploy_to_github.py`, `export_dashboard.py`, `url_verify.py`, `wayback.py`, `quality_report.py`, `seed_projects_v2.py`, etc.)
- `tests/` — Test files (`conftest.py` adds project root to sys.path)
- `config/` — Static data files (`watchlist.json`, `compound_queries_final.json`, `statcan_table_registry.*`, etc.)
- `archive/` — Archived code, old backups, legacy frontend
- `docs/` — GitHub Pages static frontend
- `public/` — Source frontend assets (synced to docs/ by `tools/deploy_to_github.py`)

## File Naming
- Discovery: `google_news_rss_search.py`, `rss_filter.py`, `gov_sources.py`, `municipal_dev_apps.py`, `snippet_enhancer.py`, `metadata_tagger.py`, `iaac_status.py`
- Procurement: `procurement_monitor.py` (federal + provincial contract awards — Open Canada, BuyAndSell, Ontario BPS, BC Bid)
- Policy: `policy_tracker.py` (LEGISinfo, Canada Gazette, ministry feeds — legislative/regulatory tracking)
- Signals: `job_monitor.py` (hiring spike detection — 15 CMAs, 9 sectors, Indeed/Job Bank RSS)
- StatCan Extended: `statcan_extended.py` (8 additional WDS tables — investment, employment, trade, housing)
- Regulatory: `article_filter.py` contains `is_regulatory_relevant()` pre-filter and `extract_regulatory_signal()` for CanLII feeds (10 feeds in `rss_feeds.json` `regulatory` category)
- Alert Tracking: `project_alert_tracker.py` (per-project Google News RSS alerts, monthly check, auto-deactivate on Cancelled/Complete)
- Search: `tavily_search.py` (targeted enrichment only)
- Reasoning: `claude_reasoning.py` (all reasoning — no gemini_pro_reasoning.py)
- Analysis: `sector_trends.py`, `cross_reference.py`, `indicator_trends.py`
- Frontend: `docs/index.html` (GitHub Pages root)

## StatCan Extended Indicators
8 additional StatCan WDS tables fetched in Phase 1 (data collection) covering capital expenditure intentions (34-10-0035, annual), building investment (34-10-0175, quarterly), construction price index (18-10-0135, quarterly), employment by industry (14-10-0022, monthly), job vacancies (14-10-0326, quarterly), merchandise exports (12-10-0129, monthly), housing starts (34-10-0143, monthly), and new housing price index (18-10-0205, monthly). All fetched via WDS API. Zero cost, no API key. Mode-aware: daily/indicators-only runs skip annual and quarterly tables, only fetch monthly ones. Indicators feed into `indicator_history` and the cross-reference engine.

## Policy Tracking
Monitors ~17 federal and provincial RSS feeds for legislative and regulatory developments affecting capital investment. Sources include LEGISinfo (federal bills), Canada Gazette (regulations), and ministry news feeds for Finance, ISED, NRCan, ECCC, Transport, Infrastructure, CMHC, Global Affairs, and DND. Provincial feeds cover ON, BC, AB, QC, SK.

Policy items are classified into 8 categories (housing, energy_transition, infrastructure_funding, trade_policy, defence, resource_development, healthcare_infrastructure, fiscal_policy) and linked to affected projects by sector and province. The policy_summary output feeds into the narrative phase for the weekly briefing.

Zero cost — all government RSS feeds are free public data.

## IAAC Status Tracker
Monitors the federal Impact Assessment Registry for status transitions on projects under assessment. Maps IAAC phases (Planning Phase, Public Comment, Panel Review, Decision Statement, etc.) to project statuses and updates the database when projects advance through the assessment process. Also detects IAAC projects not yet in the database as new discoveries. Reuses the existing Tier 1 IAAC scraper from `gov_sources.py` — does not duplicate the HTTP/parsing logic. Status updates respect the non-regression rule (terminal states like Cancelled always apply). Zero cost.

## Common Mistakes to Avoid
- Do not use Gemini for classification — replaced by Groq LLaMA 3.3 70B. Gemini is legacy fallback only.
- Do not use Gemini grounded search — it costs $35/1,000 queries. Use Google News RSS instead.
- Do not pass `google_search` tool or `groundingConfig` to Gemini API — this enables grounding fees
- Do not use Gemini Pro — removed. All reasoning goes through Claude Sonnet.
- Do not use Perplexity or GDELT in the weekly pipeline
- Haiku 4.5 is permitted ONLY for strictly mechanical agents with no editorial judgment, writing, or reasoning component (currently: `tldr-assembler` — pure JSON merge, source de-duplication, citation re-numbering, schema validation). Do not extend Haiku to writers, researchers, analysts, auditor, fixer, or any agent that produces prose or makes editorial/quality decisions. Those remain on Opus (writing) or Sonnet (extraction/reasoning) per the Model Stack section.
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
- Do not route Opus to extraction tasks (Call 4, gap analysis, dedup QA) — use Sonnet for those.
- Do not route Sonnet to writing tasks (Calls 1-3, briefing, market, microscope) — use Opus for those.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
