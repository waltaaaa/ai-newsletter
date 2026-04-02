# Conductor Architecture — The Lagging Indicator

## Overview

The conductor replaces the single-session `tldr-pipeline` orchestrator with a subagent-based system. Each agent runs in its own isolated context window, communicates via files on disk, and is validated by the conductor before the next stage proceeds.

The pipeline has two tracks:
- **Briefing Track** — produces the weekly newsletter (Phases 0–6, Deploy)
- **Project Track** — maintains the project database (Phases P0–P2, runs in parallel or independently)

Total subagents: **up to 55** (full run with all project monitors)
Critical path (briefing): **8 sequential steps** with parallelism
Estimated runtime (briefing): **88–105 minutes**
Estimated runtime (project track): **45–60 minutes** (parallel)

---

## Briefing Track — Subagent Map

```
PHASE 0 — DATA REFRESH                          ┌─────────────┐
Sequential, runs first                           │  Agent 0     │
                                                 │  Data Refresh│
                                                 └──────┬───────┘
                                                        │
PHASE 0.5 — DATA GAP AUDIT                      ┌──────┴──────┐
Sequential, validates data                       │  Agent 0.5   │
completeness before research                     │  Data Gap    │
                                                 └──────┬───────┘
                                                        │
PHASE 1 — RESEARCH                          ┌───────────┼───────────┐
3 subagents, all parallel                   │           │           │
                                      ┌─────┴─────┐ ┌──┴────────┐ ┌┴───────────┐
                                      │ Agent 1A   │ │ Agent 1B  │ │ Agent 1C   │
                                      │ Macro &    │ │ Provincial│ │ Sector &   │
                                      │ Markets    │ │ Research  │ │ Industry   │
                                      └─────┬──────┘ └──┬────────┘ └┬───────────┘
                                            │           │           │
PHASE 2 — ANALYSIS                          │     ┌─────┼───────────┘
3 subagents, all parallel                   │     │     │
                                      ┌─────┴─────┐ ┌──┴────────┐ ┌────────────┐
                                      │ Agent 2A   │ │ Agent 2B  │ │ Agent 2C   │
                                      │ Macro      │ │ Province  │ │ Industry   │
                                      │ Analyst    │ │ Analyst   │ │ Analyst    │
                                      └─────┬──────┘ └──┬────────┘ └┬───────────┘
                                            │           │           │
PHASE 3 — WRITING               ┌───────┬────────┬────────────┬────────────┬──────────┬──────────┬──────────┐
8 subagents, all parallel        │       │        │            │            │          │          │          │
  Group 1: Core            ┌─────┴───┐   │        │            │            │          │          │          │
                           │Agent 3A  │   │        │            │            │          │          │          │
                           │Macro     │   │        │            │            │          │          │          │
                           └─────┬────┘   │        │            │            │          │          │          │
  Group 2: Sectors               │  ┌──┴─────┐ ┌┴─────────┐ ┌┴──────────┐ │          │          │          │
                                 │  │Agent 3B│ │ Agent 3C │ │ Agent 3D  │ │          │          │          │
                                 │  │Province│ │ Goods    │ │ Services  │ │          │          │          │
                                 │  └──┬─────┘ └┬─────────┘ └┬──────────┘ │          │          │          │
  Group 3: Markets               │     │        │            │      ┌─────┴────┐ ┌───┴────┐ ┌──┴─────┐ ┌─┴────────┐
                                 │     │        │            │      │Agent 3F  │ │Agent 3G│ │Agent 3H│ │Agent 3I  │
                                 │     │        │            │      │Market    │ │Equities│ │FX &    │ │Commodi-  │
                                 │     │        │            │      │Commen-   │ │Writer  │ │Yields  │ │ties      │
                                 │     │        │            │      │tary      │ │        │ │Writer  │ │Writer    │
                                 │     │        │            │      └─────┬────┘ └───┬────┘ └──┬─────┘ └─┬────────┘
                                 │     │        │            │            │          │         │          │
PHASE 3.25 — VISUALIZER          └─────┼────────┼────────────┼────────────┼──────────┼─────────┼──────────┘
1 subagent, sequential                 │   ┌────┴────┐
after all 8 writers                    │   │Visualizr│
                                       │   │Phase3.25│
                                       │   └────┬────┘
                                       │        │
PHASE 3.5 — ASSEMBLY                   └────────┼────────────────────────────────────────────────
1 subagent, sequential                     ┌────┴────┐
                                           │Agent 3E │
                                           │Assemble │
                                           └────┬────┘
                                                        │
PHASE 4 — CHARTS                                 ┌──────┴──────┐
1 subagent, sequential                           │  Agent 4     │
                                                 │  Charts      │
                                                 └──────┬───────┘
                                                        │
PHASE 5 — QUALITY                           ┌───────────┼───────────┐
2 subagents, parallel                       │                       │
                                      ┌─────┴──────┐        ┌──────┴──────┐
                                      │  Agent 5    │        │  Agent 7    │
                                      │  Auditor    │        │  Discovery  │
                                      └─────┬───────┘        └─────────────┘
                                            │
PHASE 6 — FIX (conditional)          ┌──────┴──────┐
Only if audit ≠ PASS                 │  Agent 6     │
                                     │  Fixer       │
                                     └──────┬───────┘
                                            │
DEPLOY                                      ▼
Bash commands, user approval         Publish + Push
```

---

## Project Track — Subagent Map

The project track maintains the project database independently. It can run in parallel with the briefing track or on a separate schedule.

```
PHASE P0 — PROJECT MONITORING               ┌──────────────────────────────────────────┐
29 subagents, all parallel                   │  1 National + 13 Provincial + 15 CMA     │
                                             │  Project Monitor agents                   │
                                             └────────────────────┬─────────────────────┘
                                                                  │
PHASE P1 — PROJECT SUMMARIZER                ┌────────────────────┴─────────────────────┐
1-3 subagents depending on backlog           │  Writes summaries + update logs           │
                                             │  for new, updated, and backfill projects  │
                                             └────────────────────┬─────────────────────┘
                                                                  │
PHASE P2 — DATABASE UPDATE                                        ▼
Bash/Python script                           Write to dashboard.db + export projects_all.json
```

---

## Phase 0 — Data Refresh (1 subagent)

| Agent | Reads | Writes |
|-------|-------|--------|
| **0: Data Refresh** | `docs/data/briefing_latest.json`, `docs/data/indicators.json` | Updated `briefing_latest.json` (metrics, markets, commodities, yields), updated `indicators.json`, new entry in `docs/data/data_snapshots.json` |

Uses WebSearch to find latest values for all indicators, market prices, commodities, bond yields, and provincial data. Updates JSON files in place.

**Validation:** `indicators.json` modified within last 30 min. `briefing_latest.json` has fresh `metrics.bocRate`, `financialMarkets`, `commodities`.

---

## Phase 0.5 — Data Gap Audit (1 subagent)

| Agent | Reads | Writes |
|-------|-------|--------|
| **0.5: Data Gap** | `docs/data/indicators.json`, `docs/data/briefing_latest.json`, `docs/data/projects_all.json`, `docs/data/timeseries.json`, `docs/data/commodities.json`, `docs/data/policy.json` | `docs/data/data_gap_report.md`, updated data files where gaps can be filled |

**Purpose:** Sits between data refresh and research. Performs a systematic audit of data completeness and freshness across all data sources. Identifies what's missing or stale so researchers know where to focus.

**What it checks:**

1. **Indicator coverage** — For each of the 13 provinces: is CPI, unemployment, GDP, housing starts, employment rate, participation rate current? Flag any indicator older than the expected release cycle.
2. **Commodity gaps** — Are all 30+ commodity prices in `timeseries.json` up to date? Flag any with no data point in the last 7 days.
3. **Project status staleness** — How many projects haven't been seen (`lastSeen`) in 30+ days? 60+? 90+? Flag the highest-value stale projects by name.
4. **Policy freshness** — Does `policy.json` have entries from the current week? Flag if the newest policy item is >14 days old.
5. **Timeseries completeness** — For each of the 102 timeseries keys, check if the most recent data point is within the expected frequency (daily for commodities, monthly for indicators, quarterly for GDP).
6. **Missing province data** — Identify provinces with <3 indicators populated (common for territories).
7. **Market data gaps** — Check indices, FX, and yield curve data for completeness.

**What it does about gaps:**
- Gaps it CAN fill: uses WebSearch to find missing values and updates the data files directly (same approach as Agent 0, but targeted at specific gaps).
- Gaps it CANNOT fill: documents them in `data_gap_report.md` with severity (critical/warning/info) and recommended action.

**Output format of `data_gap_report.md`:**
```markdown
# Data Gap Report — YYYY-MM-DD

## Critical Gaps (will affect briefing quality)
- [province] [indicator]: last value from [date], expected [frequency]
- ...

## Warnings (may affect depth)
- ...

## Filled This Run
- [indicator]: found [value] for [period] via WebSearch
- ...

## Coverage Summary
- Provinces with full indicator sets: X/13
- Commodity prices current (7d): X/30
- Projects seen in last 30 days: X/total
- Timeseries keys current: X/102
```

**Validation:** `data_gap_report.md` exists. Critical gaps count is reported to the conductor. If >5 critical gaps, conductor asks user whether to proceed or address gaps first.

---

## Phase 1 — Research (3 parallel subagents)

| Agent | Reads | Writes |
|-------|-------|--------|
| **1A: Macro & Markets** | `docs/data/briefing_latest.json`, `docs/data/indicators.json`, `docs/data/commodities.json`, `docs/data/timeseries.json`, `docs/data/events.json`, `docs/data/data_gap_report.md` | `docs/data/research_macro.md` |
| **1B: Provincial** | `docs/data/indicators.json`, `docs/data/policy.json`, `docs/data/projects_all.json`, `docs/data/data_gap_report.md` | `docs/data/research_provinces.md` |
| **1C: Sector & Industry** | `docs/data/projects_all.json`, `docs/data/commodities.json`, `docs/data/indicators.json`, `docs/data/data_gap_report.md` | `docs/data/research_sectors.md` |

All three researchers receive the data gap report so they can prioritize searching for missing data.

**Scope per agent:**

- **1A** covers: BoC rate, GDP, CPI, unemployment, housing, trade, financial markets (indices, FX, commodities), global context (US, China, EU, UK), consumer pulse themes, upcoming events.
- **1B** covers: all 13 provinces — provincial indicators, policy developments, capital projects by province, labour market, IAAC status changes, procurement awards.
- **1C** covers: 20 NAICS industries (5 goods + 15 services) — sector trends, project pipeline by sector, emerging stories, new project announcements.

**Validation per agent:**
- 1A: `research_macro.md` exists, >800 words, contains sections for macro, markets, global, consumer.
- 1B: `research_provinces.md` exists, >1500 words, mentions all 13 provinces.
- 1C: `research_sectors.md` exists, >1000 words, covers goods and services industries.

---

## Phase 2 — Analysis (3 parallel subagents)

| Agent | Reads | Writes |
|-------|-------|--------|
| **2A: Macro Analyst** | `docs/data/research_macro.md`, `docs/data/briefing_latest.json`, `docs/data/indicators.json`, `docs/data/projects_all.json`, `docs/data/events.json`, `docs/data/policy.json`, `docs/data/commodities.json`, `docs/data/timeseries.json` | `docs/data/dossier_macro.json` |
| **2B: Province Analyst** | `docs/data/research_provinces.md`, `docs/data/indicators.json`, `docs/data/projects_all.json`, `docs/data/policy.json` | `docs/data/dossier_provinces.json` |
| **2C: Industry Analyst** | `docs/data/research_sectors.md`, `docs/data/projects_all.json`, `docs/data/commodities.json`, `docs/data/indicators.json` | `docs/data/dossier_industries.json` |

**Scope per agent:**

- **2A** produces: `headline`, `key_indicators`, `executive_summary_package`, `national_analysis_package`, `global[]` (4 regions), `consumer_pulse_package`, `financial_markets_package`, `watchlist`, `sources_registry`, `charts` (yield curve data).
- **2B** produces: `provinces[]` — 13 objects, each with indicators, indicatorMeta, story_threads, cross_references (projects linked to indicators), policy_items, watchlistItems.
- **2C** produces: `goodsIndustries[]` (5) and `servicesIndustries[]` (15), each with sector data, project counts, cross_references, trend analysis.

**Validation per agent:**
- 2A: Valid JSON, contains `headline`, `key_indicators` (≥5 items), `sources_registry` (≥20 entries), `global` (4 regions).
- 2B: Valid JSON, contains `provinces` array with exactly 13 items, each with `name`, `indicators`, `story_threads`.
- 2C: Valid JSON, contains `goodsIndustries` (5 items) and `servicesIndustries` (15 items).

---

## Phase 3 — Writing (8 parallel subagents in 3 groups)

| Agent | Group | Reads | Writes |
|-------|-------|-------|--------|
| **3A: Macro Writer** | 1 — Core | `docs/data/dossier_macro.json`, `docs/data/briefing_latest.json` (template) | `docs/data/briefing_macro.json` |
| **3B: Province Writer** | 2 — Sectors | `docs/data/dossier_provinces.json`, `docs/data/briefing_latest.json` (template) | `docs/data/briefing_provinces.json` |
| **3C: Goods Industry Writer** | 2 — Sectors | `docs/data/dossier_industries.json` (goods subset), `docs/data/briefing_latest.json` (template) | `docs/data/briefing_goods.json` |
| **3D: Services Industry Writer** | 2 — Sectors | `docs/data/dossier_industries.json` (services subset), `docs/data/briefing_latest.json` (template) | `docs/data/briefing_services.json` |
| **3F: Market Commentary** | 3 — Markets | `docs/data/dossier_macro.json`, `docs/data/briefing_latest.json` | `docs/data/briefing_market_commentary.json` |
| **3G: Market Equities** | 3 — Markets | `docs/data/dossier_macro.json`, `docs/data/timeseries.json`, `docs/data/briefing_latest.json` | `docs/data/briefing_market_equities.json` |
| **3H: FX & Yields** | 3 — Markets | `docs/data/dossier_macro.json`, `docs/data/timeseries.json`, `docs/data/briefing_latest.json` | `docs/data/briefing_market_fx_yields.json` |
| **3I: Market Commodities** | 3 — Markets | `docs/data/dossier_macro.json`, `docs/data/timeseries.json`, `docs/data/briefing_latest.json` | `docs/data/briefing_market_commodities.json` |

**Scope per agent:**

- **3A** writes: `headline`, `edition`, `week_of`, `executive_summary`, `national.analysis`, `national.sources`, `consumer_pulse`, `watchlist`, `globalVectors`, `global[]` (4 region analyses), `indicatorContextLines`, `key_indicators`, `metrics`, `indicatorMeta`, `indicatorSources`. **Note:** `financialMarkets`, `commodities`, and `yieldCurve` are no longer produced by 3A — they are handled by agents 3F–3I.
- **3B** writes: `provinces[]` — 13 complete province objects with `name`, `indicators`, `indicatorMeta`, `analysis` (HTML with citations), `sources[]`, `sectorHighlights`, `labourDeepDive`, `consumerPulse`, `tradeExposure`, `marketContext`, `watchlistItems`.
- **3C** writes: `goodsIndustries[]` — 5 goods industries (NAICS 11, 21, 22, 23, 31-33), each with `code`, `name`, `analysis` (HTML), `sources[]`, `trend`, `projectCount`, `signalStrength`. These are the data-heavy sectors (agriculture, mining, utilities, construction, manufacturing) that require cross-referencing with commodity prices, trade data, and project pipelines.
- **3D** writes: `servicesIndustries[]` — 15 services industries (NAICS 41 through 91), each with `code`, `name`, `analysis` (HTML), `sources[]`, `trend`, `projectCount`, `signalStrength`. These cover wholesale trade through public administration, requiring different analytical lenses (labour market, government policy, consumer demand).
- **3F** writes: `market_commentary` (150–200 word cross-referenced narrative), `market_commentary_callout` (pipeline cross-reference data points).
- **3G** writes: `equities[]` — 4 index objects (TSX Composite, S&P 500, DJIA, Nasdaq Composite), each with data fields and `commentary` (100–150 total words).
- **3H** writes: `fx.pairs[]` (≥3 currency pairs + `fx_commentary`), `yieldCurve` (7 tenors with year-ago data + `yield_commentary`, `spread_2_10`, `curve_shape`). 100–150 total words.
- **3I** writes: `commodities[]` — 13 commodity objects each with data fields and `commentary`, plus `commodity_commentary` (summary paragraph), `wcs_analysis` (WCS-WTI discount and breakeven analysis). 300–400 total words.

**Why split goods and services:** Goods industries (mining, energy, manufacturing, construction, agriculture) draw heavily on commodity prices, trade flows, and physical project data. Services industries (retail, finance, healthcare, education, government) draw on labour market data, consumer sentiment, and policy. Splitting them gives each writer a focused analytical context and produces deeper, institutional-grade output per industry rather than spreading one agent across 20 diverse sectors.

**Why split markets from macro:** The macro agent (3A) previously handled financial markets, commodities, and yield curve alongside the executive summary, national analysis, global context, and consumer pulse. This created a ~2000-word scope that competed for context window space with the analytical depth needed for each section. Dedicated market agents (3F–3I) now handle: market overview commentary (3F, 150–200 words), per-index equities (3G, 100–150 words), FX and yield curve (3H, 100–150 words), and per-commodity narratives with breakeven analysis (3I, 300–400 words). This split gives each market section institutional-grade depth — particularly the commodities agent, which now covers 13 commodities with WCS discount calculations and project breakeven thresholds that were previously compressed into a bullet list.

**Editorial rules apply to all four writers:**
- No editorializing — facts only, no "worrying", "encouraging", "promising"
- Every claim cites a source using `<sup>N</sup>` format with a specific, verifiable URL (see Citation Chain Protocol)
- Specific numbers, not vague language
- Attribution over assertion

**Validation per agent:**
- 3A: Valid JSON, contains `headline`, `executive_summary` (>200 words), `national.analysis` (>300 words), `global` (4 regions each with `analysis`). Does NOT contain `financialMarkets`, `commodities`, or `yieldCurve`. All sources have specific URLs.
- 3B: Valid JSON, `provinces` array with 13 items, each `analysis` field is non-empty HTML. All sources have specific URLs.
- 3C: Valid JSON, `goodsIndustries` with exactly 5 items, each `analysis` >100 words. All sources have specific URLs.
- 3D: Valid JSON, `servicesIndustries` with exactly 15 items, each `analysis` >80 words. All sources have specific URLs.
- 3F: Valid JSON, `market_commentary` (150–200 words), `sources[]`. Both paragraphs have em dash leads.
- 3G: Valid JSON, `equities[]` with 4 items (TSX, S&P 500, DJIA, Nasdaq), total commentary 100–150 words.
- 3H: Valid JSON, `fx.pairs[]` (≥3), `yieldCurve.tenors` (7), total commentary 100–150 words.
- 3I: Valid JSON, `commodities[]` with 13 items, `wcs_analysis` present, total 300–400 words.

---

## Phase 3.25 — Visualizer (1 subagent)

| Agent | Reads | Writes |
|-------|-------|--------|
| **3.25: Visualizer** | `docs/data/briefing_macro.json`, `docs/data/briefing_provinces.json`, `docs/data/briefing_goods.json`, `docs/data/briefing_services.json`, `docs/data/briefing_market_commentary.json`, `docs/data/briefing_market_equities.json`, `docs/data/briefing_market_fx_yields.json`, `docs/data/briefing_market_commodities.json`, `docs/data/timeseries.json`, `docs/data/briefing_latest.json`, `docs/data/indicators.json`, `docs/data/projects_all.json` | `docs/data/briefing_visualizations.json` |

**Purpose:** Sits between the writers and the assembler. Reads all 8 writer fragments, identifies 2–4 narrative inflection points where an inline SVG chart would strengthen the reader's understanding, generates production-ready SVG charts, and outputs a manifest that tells the assembler exactly where to insert them.

**Key distinction from Agent 4 (Charts):** Agent 4 produces 28 mechanical JSON chart specs (2 national + 2×13 provinces) rendered by Chart.js on the data tabs. The Visualizer produces a small number (1–6) of editorially curated inline SVG charts for the TL;DR page and Markets tab. The two agents coexist — they serve different purposes on different parts of the dashboard.

**Validation:**
- `briefing_visualizations.json` exists and is valid JSON
- `chart_count` is between 1 and 6
- Each chart has: `id`, `tab`, `insertion_point`, `section`, `svg` (non-empty), `chart_type`, `data_keys_used`, `editorial_rationale` (non-empty)
- All `data_keys_used` values exist in `timeseries.json`

**Graceful degradation:** If the Visualizer fails, the assembler proceeds without charts. The briefing is complete and valid without editorial charts — they enhance but are not required.

---

## Phase 3.5 — Assembly (1 subagent)

| Agent | Reads | Writes |
|-------|-------|--------|
| **3E: Assembler** | `docs/data/briefing_macro.json`, `docs/data/briefing_provinces.json`, `docs/data/briefing_goods.json`, `docs/data/briefing_services.json`, `docs/data/briefing_market_commentary.json`, `docs/data/briefing_market_equities.json`, `docs/data/briefing_market_fx_yields.json`, `docs/data/briefing_market_commodities.json`, `docs/data/briefing_visualizations.json` (optional), `docs/data/briefing_latest.json` (for `id` increment and structural reference) | `docs/data/briefing_YYYY-MM-DD.json` |

**What the Assembler does:**
1. Reads the eight writer fragment files plus optional visualization manifest
2. Merges them into one complete briefing JSON matching the `TLDR_JSON_SPECIFICATION.md` schema
3. Increments the `id` field from last week's briefing
4. Sets `generated_at` and `updated_at` timestamps
5. Copies forward any structural fields from last week that aren't produced by the writers (e.g., `infographic_directives`)
6. Integrates inline SVG charts from `briefing_visualizations.json` at their specified insertion points (graceful degradation if absent)
7. Validates completeness: all required top-level fields present
8. Does NOT overwrite `briefing_latest.json`

**This agent does NO creative writing.** It is a mechanical merge and validation step.

**Validation:**
- Output file is valid JSON
- Contains all required top-level fields per `TLDR_JSON_SPECIFICATION.md`
- `goodsIndustries` count = 5, `servicesIndustries` count = 15, `provinces` count = 13, `global` count = 4
- `id` is incremented from last week
- `headline` is non-empty
- `executive_summary` is non-empty
- `_all_verified_sources` array is present (assembled from all eight fragments' source arrays)
- `financialMarkets` assembled from 3G (equities) and 3H (FX data)
- `commodities` sourced from 3I (market commodities)
- `yieldCurve` sourced from 3H (FX & yields)

---

## Phase 4 — Charts (1 subagent)

| Agent | Reads | Writes |
|-------|-------|--------|
| **4: Charts** | `docs/data/briefing_YYYY-MM-DD.json`, `docs/data/timeseries.json`, `.claude/skills/lagging_indicator_charts.md` | Updated `docs/data/briefing_YYYY-MM-DD.json` (adds `insightCharts` arrays) |

**Produces:** 28 chart specs total (2 national + 2 × 13 provinces).

**Validation:**
- Top-level `insightCharts` array has exactly 2 items
- Each of 13 province objects has `insightCharts` array with exactly 2 items
- Every `dataKey` in every chart spec exists in `timeseries.json`

---

## Phase 5 — Quality (2 parallel subagents)

| Agent | Reads | Writes |
|-------|-------|--------|
| **5: Auditor** | `docs/data/briefing_YYYY-MM-DD.json`, `docs/data/research_macro.md`, `docs/data/research_provinces.md`, `docs/data/research_sectors.md`, `docs/data/indicators.json` | `docs/data/audit_report.md` |
| **7: Discovery** | `docs/data/projects_all.json`, `docs/data/indicators.json` | `docs/data/discovery_batch.json` |

**Auditor runs 10 tests:**
1. Number Verification — metrics match authoritative sources
2. Citation Integrity — all `<sup>N</sup>` refs resolve to sources
3. Editorial Compliance — no banned words (worrying, promising, etc.)
4. Logic & Consistency — no internal contradictions
5. Completeness — all industries, provinces, structural fields present
6. Freshness — <50% similarity to last week's briefing
7. Schema Compliance — correct types and structures
8. Cross-Agent Consistency — no information corruption across fragments
9. Comparative Sanity — word counts and values are plausible
10. Security & Integrity — no PII, hallucinated URLs, prompt leakage

**Branching logic after Auditor:**
- **PASS** → Skip Phase 6, proceed to Deploy
- **PASS WITH WARNINGS** → Run Phase 6 for non-blocking fixes
- **FAIL** → Run Phase 6 (mandatory), optionally re-audit

---

## Phase 6 — Fix (1 subagent, conditional)

| Agent | Reads | Writes |
|-------|-------|--------|
| **6: Fixer** | `docs/data/audit_report.md`, `docs/data/briefing_YYYY-MM-DD.json`, `docs/data/dossier_macro.json`, `docs/data/dossier_provinces.json`, `docs/data/dossier_industries.json`, `docs/data/indicators.json`, `docs/data/projects_all.json` | Updated `docs/data/briefing_YYYY-MM-DD.json` |

Only runs if the Auditor returns a non-PASS verdict.

---

## Deploy (Bash, after user approval)

```
1. Back up current briefing_latest.json → briefing_{old_week}.json
2. Copy briefing_YYYY-MM-DD.json → briefing_latest.json
3. Update briefing_archive.json with new edition entry
4. Export PDF and DOCX via briefing_export.py
5. git add docs/data/ && git commit && git push origin main
```

---

---

# Project Track

The project track runs either in parallel with the briefing track or independently. It maintains the project database through monitoring, summarization, and update logging.

---

## Phase P0 — Project Monitoring (29 parallel subagents)

### National Monitor (1 subagent)

| Agent | Reads | Writes |
|-------|-------|--------|
| **P0-NAT: National Monitor** | `docs/data/projects_all.json` | `docs/data/monitor/national.json` |

Searches for nationally significant project announcements, federal infrastructure programs, cross-provincial projects, and major status changes. Focuses on projects >$500M that span multiple provinces or are federally led.

### Provincial Monitors (13 parallel subagents)

| Agent | Reads | Writes |
|-------|-------|--------|
| **P0-ON: Ontario Monitor** | `docs/data/projects_all.json` (filtered to ON) | `docs/data/monitor/ON.json` |
| **P0-QC: Quebec Monitor** | `docs/data/projects_all.json` (filtered to QC) | `docs/data/monitor/QC.json` |
| **P0-AB: Alberta Monitor** | `docs/data/projects_all.json` (filtered to AB) | `docs/data/monitor/AB.json` |
| **P0-BC: British Columbia Monitor** | `docs/data/projects_all.json` (filtered to BC) | `docs/data/monitor/BC.json` |
| **P0-SK: Saskatchewan Monitor** | `docs/data/projects_all.json` (filtered to SK) | `docs/data/monitor/SK.json` |
| **P0-MB: Manitoba Monitor** | `docs/data/projects_all.json` (filtered to MB) | `docs/data/monitor/MB.json` |
| **P0-NS: Nova Scotia Monitor** | `docs/data/projects_all.json` (filtered to NS) | `docs/data/monitor/NS.json` |
| **P0-NB: New Brunswick Monitor** | `docs/data/projects_all.json` (filtered to NB) | `docs/data/monitor/NB.json` |
| **P0-NL: Newfoundland Monitor** | `docs/data/projects_all.json` (filtered to NL) | `docs/data/monitor/NL.json` |
| **P0-PE: PEI Monitor** | `docs/data/projects_all.json` (filtered to PE) | `docs/data/monitor/PE.json` |
| **P0-YT: Yukon Monitor** | `docs/data/projects_all.json` (filtered to YT) | `docs/data/monitor/YT.json` |
| **P0-NT: NWT Monitor** | `docs/data/projects_all.json` (filtered to NT) | `docs/data/monitor/NT.json` |
| **P0-NU: Nunavut Monitor** | `docs/data/projects_all.json` (filtered to NU) | `docs/data/monitor/NU.json` |

### CMA Monitors (15 parallel subagents)

| Agent | Reads | Writes |
|-------|-------|--------|
| **P0-TOR: Toronto CMA** | `docs/data/projects_all.json` (filtered to Toronto CMA) | `docs/data/monitor/CMA_TOR.json` |
| **P0-MTL: Montréal CMA** | `docs/data/projects_all.json` (filtered to Montréal CMA) | `docs/data/monitor/CMA_MTL.json` |
| **P0-VAN: Vancouver CMA** | `docs/data/projects_all.json` (filtered to Vancouver CMA) | `docs/data/monitor/CMA_VAN.json` |
| **P0-CGY: Calgary CMA** | `docs/data/projects_all.json` (filtered to Calgary CMA) | `docs/data/monitor/CMA_CGY.json` |
| **P0-EDM: Edmonton CMA** | `docs/data/projects_all.json` (filtered to Edmonton CMA) | `docs/data/monitor/CMA_EDM.json` |
| **P0-OTT: Ottawa-Gatineau CMA** | `docs/data/projects_all.json` (filtered to Ottawa CMA) | `docs/data/monitor/CMA_OTT.json` |
| **P0-WPG: Winnipeg CMA** | `docs/data/projects_all.json` (filtered to Winnipeg CMA) | `docs/data/monitor/CMA_WPG.json` |
| **P0-QUE: Québec City CMA** | `docs/data/projects_all.json` (filtered to Québec CMA) | `docs/data/monitor/CMA_QUE.json` |
| **P0-HAM: Hamilton CMA** | `docs/data/projects_all.json` (filtered to Hamilton CMA) | `docs/data/monitor/CMA_HAM.json` |
| **P0-KIT: Kitchener CMA** | `docs/data/projects_all.json` (filtered to Kitchener CMA) | `docs/data/monitor/CMA_KIT.json` |
| **P0-LON: London CMA** | `docs/data/projects_all.json` (filtered to London CMA) | `docs/data/monitor/CMA_LON.json` |
| **P0-HAL: Halifax CMA** | `docs/data/projects_all.json` (filtered to Halifax CMA) | `docs/data/monitor/CMA_HAL.json` |
| **P0-VIC: Victoria CMA** | `docs/data/projects_all.json` (filtered to Victoria CMA) | `docs/data/monitor/CMA_VIC.json` |
| **P0-WIN: Windsor CMA** | `docs/data/projects_all.json` (filtered to Windsor CMA) | `docs/data/monitor/CMA_WIN.json` |
| **P0-STJ: St. John's CMA** | `docs/data/projects_all.json` (filtered to St. John's CMA) | `docs/data/monitor/CMA_STJ.json` |

**What each monitor does:**

1. Loads the subset of projects in its jurisdiction from `projects_all.json`
2. For each active project (status ≠ Cancelled, Complete): searches for recent news, status updates, regulatory filings, construction progress
3. For the jurisdiction overall: searches for new project announcements not yet in the database
4. Outputs a structured JSON file containing:

```json
{
  "jurisdiction": "ON",
  "type": "province",
  "run_date": "2026-03-31",
  "existing_projects_checked": 142,
  "status_updates": [
    {
      "project_name": "Highway 413",
      "current_status": "Under Review",
      "new_status": "Approved",
      "evidence_url": "https://...",
      "summary": "Ontario approved Highway 413 on March 28 following IAAC review."
    }
  ],
  "new_projects": [
    {
      "name": "Scarborough Subway Extension Phase 2",
      "province": "ON",
      "cma": "Toronto",
      "sector": "infrastructure",
      "value": "C$5.8B",
      "status": "Proposed",
      "proponent": "Metrolinx",
      "evidence_url": "https://...",
      "summary": "Metrolinx announced Phase 2 extension on March 25."
    }
  ],
  "projects_not_found": ["Project X"],
  "search_count": 45
}
```

**Validation per monitor:**
- Output JSON exists and is valid
- `existing_projects_checked` > 0 (unless province is genuinely empty)
- `status_updates` entries each have `evidence_url`
- `new_projects` entries each have `name`, `province`, `sector`, `evidence_url`

---

## Phase P1 — Project Summarizer (1–3 subagents)

| Agent | Reads | Writes |
|-------|-------|--------|
| **P1: Summarizer** | `docs/data/projects_all.json`, `docs/data/monitor/*.json` (all monitor outputs) | `docs/data/project_summaries.json`, `docs/data/project_updates.json` |

**Purpose:** Writes professional summaries for projects and creates update log entries that track how projects change over time. Readers see these in the project dropdown panels on the frontend.

### What it produces:

**1. Project Summaries** (`project_summaries.json`)

For each project that either (a) was newly discovered this week, (b) had a status change, or (c) has no existing summary and was first tracked within the last 6 months:

```json
{
  "norm_key": "highway-413-on",
  "summary": "Highway 413 is a proposed 59-kilometre controlled-access highway connecting Highway 400 in Vaughan to Highway 401/407 in Halton Hills. The $6.5B project, led by Ontario's Ministry of Transportation, would provide an alternative east-west corridor across the Greater Toronto Area's northwestern suburbs. The project entered the Impact Assessment process in 2021 and received provincial approval in March 2026.",
  "generated_at": "2026-03-31"
}
```

**Summary guidelines:**
- 2-4 sentences, factual, no editorializing
- Include: what the project is, location, value, proponent, current stage
- Use evidence URLs from the project record and monitor outputs for accuracy
- Match the editorial tone of the briefing (wire service, facts only)

**2. Project Update Logs** (`project_updates.json`)

For each project with a status change or significant new information this week:

```json
{
  "norm_key": "highway-413-on",
  "updates": [
    {
      "date": "2026-03-31",
      "type": "status_change",
      "from_status": "Under Review",
      "to_status": "Approved",
      "summary": "Ontario approved the Highway 413 project following completion of the provincial environmental assessment. The federal IAAC review remains ongoing.",
      "evidence_url": "https://..."
    }
  ]
}
```

**Update types:**
- `status_change` — project moved to a new status
- `value_revision` — estimated value changed
- `timeline_update` — completion date moved
- `proponent_change` — ownership or lead changed
- `regulatory_milestone` — IAAC, EA, or permitting milestone
- `construction_progress` — physical progress reported
- `new_evidence` — significant new source or filing discovered

**Update log guidelines:**
- 1-2 sentences per update, factual
- Always include what changed, from what to what, and the source
- These appear in the project dropdown on the frontend as a chronological timeline

### Backfill mode (one-time):

On first run, the summarizer identifies all projects with `firstTracked` within the last 6 months that have no summary. It generates summaries for these in batches. Given ~2,300 projects, this may need to run as 3 parallel subagents split alphabetically or by province to stay within context limits.

After the initial backfill, the summarizer runs incrementally — only processing new discoveries and status changes from the current week's monitor outputs.

**Validation:**
- `project_summaries.json` is valid JSON
- Each summary is 50-500 characters
- Each summary references a real project in `projects_all.json`
- `project_updates.json` is valid JSON
- Each update has `date`, `type`, `summary`, `evidence_url`

---

## Phase P2 — Database Update (Bash/Python)

After monitors and summarizer complete, a Python script:

1. Reads all `docs/data/monitor/*.json` files
2. Applies status updates to `dashboard.db` (respecting non-regression rules — status never goes backward)
3. Inserts new projects (with URL hard gate — no URL = no insert)
4. Merges evidence arrays (append, never overwrite)
5. Writes summaries into project `description` fields
6. Appends update logs to `statusHistory` arrays
7. Re-exports `docs/data/projects_all.json`

This is a Python script, not a Claude agent. It enforces the database rules that are too important to leave to an LLM.

---

---

# Complete File Contract Summary

## Intermediate Files

| File | Producer | Consumer | Persistent? |
|------|----------|----------|-------------|
| `data_gap_report.md` | Agent 0.5 | Agents 1A, 1B, 1C | Session only |
| `research_macro.md` | Agent 1A | Agent 2A, Agent 5 | Session only |
| `research_provinces.md` | Agent 1B | Agent 2B, Agent 5 | Session only |
| `research_sectors.md` | Agent 1C | Agent 2C, Agent 5 | Session only |
| `dossier_macro.json` | Agent 2A | Agent 3A | Session only |
| `dossier_provinces.json` | Agent 2B | Agent 3B | Session only |
| `dossier_industries.json` | Agent 2C | Agent 3C | Session only |
| `briefing_macro.json` | Agent 3A | Agent 3E | Session only |
| `briefing_provinces.json` | Agent 3B | Agent 3E | Session only |
| `briefing_goods.json` | Agent 3C | Agent 3E | Session only |
| `briefing_services.json` | Agent 3D | Agent 3E | Session only |
| `monitor/*.json` | P0 agents | P1, P2 | Session only |
| `project_summaries.json` | P1 | P2 | **Yes** |
| `project_updates.json` | P1 | P2 | **Yes** |

## Final Outputs

| File | Producer | Persistent? |
|------|----------|-------------|
| `briefing_YYYY-MM-DD.json` | Agent 3E → 4 → 6 | **Yes — archived** |
| `briefing_latest.json` | Deploy step | **Yes — live** |
| `audit_report.md` | Agent 5 | **Yes — archived** |
| `discovery_batch.json` | Agent 7 | **Yes — archived** |
| `projects_all.json` | P2 script | **Yes — live** |

---

# Critical Path (wall-clock time)

## Briefing Track

```
Step 1:  Agent 0 (Data Refresh)                    ~8 min
Step 2:  Agent 0.5 (Data Gap Audit)                ~5 min
Step 3:  Agents 1A + 1B + 1C (parallel)           ~20 min
Step 4:  Agents 2A + 2B + 2C (parallel)           ~12 min
Step 5:  Agents 3A-3D + 3F-3I (8 parallel)        ~20 min
Step 6:  Visualizer (Phase 3.25)                    ~5 min
Step 7:  Agent 3E (Assembly — 8 frags + charts)     ~8 min
Step 8:  Agent 4 (Charts)                           ~8 min
Step 9:  Agent 5 (Auditor) ‖ Agent 7               ~8 min
Step 10: Agent 6 (Fixer, if needed)                 ~8 min
Step 11: Deploy                                     ~3 min
                                            TOTAL: ~88–105 min
```

## Project Track (can run in parallel with briefing)

```
Step 1:  P0 monitors (29 parallel)          ~15 min
Step 2:  P1 summarizer                       ~20 min
Step 3:  P2 database update                   ~5 min
                                      TOTAL: ~40 min
```

## Combined (if run in parallel)

Briefing track and project track can start simultaneously. The project track results feed into `projects_all.json` which the briefing agents read. Two sequencing options:

- **Option A: Project first** — Run P0-P2, then start briefing. Projects data is maximally fresh. Adds ~40 min before briefing starts.
- **Option B: Parallel** — Start both tracks simultaneously. Briefing agents read the current `projects_all.json` (from last week's data + Python pipeline updates). Project track updates arrive after briefing is written. Next week's briefing benefits from this week's project updates.
- **Option C: Interleaved** — Run P0 monitors in parallel with Phase 0 + 0.5. Feed P0 results into P2 before Phase 1 starts, so researchers and analysts see fresh project data.

**Recommended: Option C** — maximizes data freshness without adding to wall-clock time.

---

# Skills Required

## Existing skills (no changes needed):
- `tldr-data-refresh` (Agent 0)
- `tldr-charts` (Agent 4)
- `tldr-auditor` (Agent 5)
- `tldr-fixer` (Agent 6)
- `tldr-discovery` (Agent 7)

## Existing skills to split into focused variants:
- `tldr-researcher` → `tldr-researcher-macro` (1A), `tldr-researcher-provincial` (1B), `tldr-researcher-sector` (1C)
- `tldr-analyst` → `tldr-analyst-macro` (2A), `tldr-analyst-provincial` (2B), `tldr-analyst-industry` (2C)
- `tldr-writer` → `tldr-writer-macro` (3A), `tldr-writer-provincial` (3B), `tldr-writer-goods` (3C), `tldr-writer-services` (3D)
- (new) `tldr-writer-market-commentary` (3F), `tldr-writer-market-equities` (3G), `tldr-writer-market-fx-yields` (3H), `tldr-writer-market-commodities` (3I)
- (new) `tldr-visualizer` (Phase 3.25) — editorial inline SVG chart generation

## New skills to create:
- `tldr-data-gap` (Agent 0.5) — data completeness audit and gap filling
- `tldr-assembler` (Agent 3E) — mechanical merge of 8 writing fragments + visualization manifest, citation re-numbering
- `tldr-project-monitor` (P0) — template skill for all 29 monitors (parameterized by jurisdiction)
- `tldr-project-summarizer` (P1) — summary and update log generation
- `tldr-conductor` — orchestration, dispatch, validation

## New Python script:
- `tools/project_monitor_ingest.py` (P2) — applies monitor results to database

---

# Error Handling Protocol

At every validation gate, if an output fails:

1. **Report** — Which agent, which check failed, what was expected vs. actual
2. **Ask** — Retry the agent, skip and proceed, or abort
3. **Retry** — Dispatch the same subagent with the same prompt (fresh context)
4. **Skip** — Note the gap, proceed (e.g., skip charts if timeseries is empty)
5. **Abort** — Stop the pipeline, preserve all intermediate files for debugging

**Never proceed silently past a validation failure.**

If the same agent fails twice, escalate to the user with the specific error. Do not retry indefinitely.

---

# Citation Chain Protocol

Every claim in the final briefing must trace back to a specific, verifiable source page — not a homepage, not a landing page, not a domain root. A citation to `statcan.gc.ca` is a failure. A citation to `https://www150.statcan.gc.ca/n1/daily-quotidien/260313/dq260313a-eng.htm` is correct.

This protocol governs how source URLs flow through every phase of the pipeline.

## Phase 1 — Researchers: Capture Exact URLs

Every fact a researcher records must include the exact URL where that fact was found.

**Acceptable URLs:**
- `https://www150.statcan.gc.ca/n1/daily-quotidien/260313/dq260313a-eng.htm` — specific StatCan release
- `https://www.bankofcanada.ca/2026/03/fad-press-release-2026-03-12/` — specific BoC announcement
- `https://iaac-aeic.gc.ca/050/evaluations/proj/84616` — specific IAAC project page
- `https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/housing-starts-february-2026` — specific CMHC release

**Unacceptable URLs:**
- `https://www.statcan.gc.ca` — homepage
- `https://www.bankofcanada.ca` — homepage
- `https://tradingeconomics.com/canada` — generic country page (must link to specific indicator)
- `https://majorprojects.alberta.ca` — registry landing page (must link to specific project)
- Empty string `""` — no URL at all

**Research output format:** Each source in the research brief must include:
```markdown
[N] Title of specific release or document
    URL: https://exact-page-url
    Date accessed: YYYY-MM-DD
    Claim supported: "specific fact or number from this source"
```

## Phase 2 — Analysts: Preserve and Cross-Reference URLs

Analysts inherit source URLs from the research briefs. When building dossier packages:

- Every `sources_registry` entry must have a non-empty, specific `url` field
- When cross-referencing a project with an indicator, both the project evidence URL and the indicator source URL must be preserved
- If an analyst finds a URL is generic (homepage), flag it in the dossier as `"url_quality": "generic"` so the writer knows not to cite it without finding a better source
- Analysts must NOT fabricate or guess URLs — if the researcher didn't provide one, mark it as `"url": "MISSING"` rather than inventing a plausible link

## Phase 3 — Writers: Attach Correct URLs to Citations

Every `<sup>N</sup>` in the HTML must resolve to a `sources[]` entry with a specific, verifiable URL.

**Rules:**
1. Never cite a fact without a source URL
2. Never use a homepage URL as a citation — find the specific release page
3. If the dossier has `"url": "MISSING"` for a source, the writer must either:
   - Find the exact URL via WebSearch
   - Rephrase the claim as attributed ("according to Statistics Canada's March 2026 release...") with a note in sources that the URL could not be verified
   - Drop the claim entirely if it can't be sourced
4. Source array entries follow this format:
   ```json
   {
     "id": 1,
     "title": "Statistics Canada — Labour Force Survey, March 2026",
     "url": "https://www150.statcan.gc.ca/n1/daily-quotidien/260313/dq260313a-eng.htm"
   }
   ```
5. The same source can be cited multiple times — use the same `id` rather than duplicating the entry

## Phase 3.5 — Assembler: Re-Number Without Losing URLs

When merging three writing fragments, the assembler must:

1. Collect all `sources[]` arrays from macro, province, and industry fragments
2. Assign globally unique IDs (macro sources start at 0, province sources continue from there, industry sources continue from there)
3. Re-map every `<sup>N</sup>` reference in every `analysis` HTML field to the new global ID
4. Deduplicate: if the same URL appears in multiple fragments, merge to a single entry and re-map all references to it
5. Build the unified `_all_verified_sources` array
6. Verify: every `<sup>N</sup>` in the final JSON resolves to an entry in `_all_verified_sources` with a non-empty `url`

## Phase 5 — Auditor: Verify URL Specificity

The auditor's Citation Integrity test (Test 2) must check:

1. **Resolution:** Every `<sup>N</sup>` maps to a source entry
2. **Completeness:** Every source entry has a non-empty `url` field
3. **Specificity:** No URL is a homepage or generic landing page. The auditor checks for known homepage patterns:
   - Exact match to domain root: `https://www.statcan.gc.ca`, `https://www.bankofcanada.ca`, etc.
   - Known generic paths: `/en/`, `/home`, `/index.html`, `/about`
   - URLs shorter than 40 characters (likely too generic)
   - URLs without a path component beyond `/`
4. **Plausibility:** The source title matches what you'd expect to find at that URL (e.g., a source titled "Labour Force Survey, March 2026" should not link to a GDP release page)
5. **No fabrication:** URLs should not look hallucinated — check for real domains, plausible date patterns, consistent formatting

**Audit verdict impact:**
- Any citation with an empty URL → FAIL
- Any citation pointing to a homepage → WARNING (fixable by Agent 6)
- >3 citations with generic URLs → FAIL

## Phase 6 — Fixer: Resolve Bad URLs

When the auditor flags generic or missing URLs, the fixer must:

1. Search for the specific source page using the source title and date
2. Replace the generic URL with the exact page URL
3. If the exact page cannot be found, add a note: `"url_note": "Exact release page not found; attributed to [institution] [date] release"`
4. Re-run the citation specificity check after fixes

## Project Track: Evidence URLs

The same standard applies to project evidence:

- Every `evidence_url` in monitor outputs must point to the specific page where the project or status change was documented
- Every `evidence` array entry in the project database must have a specific URL
- The project summarizer must reference these URLs in its summaries
- The P2 database update script must reject new projects or status updates that have only homepage URLs

**URL Hard Gate (existing rule, reinforced):** No project enters the database without at least one specific, verifiable source URL. This rule now extends to status updates — no status change is applied without an evidence URL pointing to the specific announcement or filing.

---

# Backward Compatibility

- The final `briefing_YYYY-MM-DD.json` output is identical in schema to what the current pipeline produces
- The frontend (`app.js`) needs no changes beyond the `insightCharts` support already added
- `briefing_latest.json` is published the same way
- PDF/DOCX export uses the same `briefing_export.py`
- GitHub Actions pipeline can remain as a fallback using `claude -p` with the original monolithic skills
- Project summaries and update logs are additive — they populate currently-empty fields (`description`, richer `statusHistory` entries)
