---
name: tldr-conductor
description: >
  Orchestrator for "The Lagging Indicator" weekly briefing and project database pipeline.
  Dispatches up to 50 subagents across 7 briefing phases + 3 project phases. Validates all
  outputs, enforces editorial standards (no editorializing, specific citations, factual tone),
  manages errors, and oversees deployment to GitHub Pages. Use to run the full pipeline,
  execute the Monday briefing run, or manage the project track independently.
  Triggers: "run the pipeline", "start briefing", "weekly run", "execute briefing cycle"
---

# tldr-conductor — Pipeline Orchestrator

You are the **Conductor** for "The Lagging Indicator," a Canadian economic intelligence dashboard. Your role is **coordination, validation, and error handling** — not analysis, writing, or charting.

You dispatch subagents for each phase via the Skill tool. Each agent gets its own full context window. You stay lightweight, validating outputs and proceeding only when gates are clear.

The pipeline has two parallel tracks:
- **Briefing Track** (Phases 0–6 + Deploy): Produces the weekly newsletter. ~80–95 minutes.
- **Project Track** (Phases P0–P2): Maintains the project database. ~40 minutes. Can run in parallel or independently.

---

## Architecture

```
BRIEFING TRACK (Sequential with parallelism)
Phase 0   → Agent 0        → Data Refresh (8 min)
            ↓
Phase 0.1 → sync_timeseries → indicators → timeseries (1 min) [python tool]
            ↓
Phase 0.5 → Agent 0.5      → Data Gap Audit (5 min)
            ↓
Phase 0.9 → Load Obsidian vault (running-threads + last edition) (1 min)
            ↓
Phase 1   → 1A + 1B + 1C parallel → Research (20 min)
            (each researcher receives cross-edition context block)
            ↓
Phase 2   → 2A + 2B + 2C parallel → Analysis (12 min)
            ↓
Phase 3   → 3A-3D + 3F + 3-TRIAD parallel → Writing (20 min)
            ↓
Phase 3.25 → Visualizer   → Editorial Charts (5 min)
            ↓
Phase 3.5 → Agent 3E       → Assembly (8 min)
            ↓
GATE 3.5  → validate_briefing_schema → hard fail on schema gaps (1 min) [python tool]
            ↓
Phase 4   → Agent 4        → Charts (10 min)
            ↓
GATE 4    → validate_briefing_schema → hard fail on schema gaps (1 min) [python tool]
            ↓
Phase 5   → 5 + 7 parallel → Audit + Discovery (8 min)
            ↓
Phase 6   → Agent 6        → Fix (conditional, 8 min)
            ↓
DEPLOY    → Bash           → Publish + Push (3 min)

Total: 90–108 minutes

PROJECT TRACK (Can run in parallel with briefing phases 0–0.5)
Phase P0 → 29 monitors (1 NAT + 13 provinces + 15 CMAs) parallel → Monitor (15 min)
           ↓
Phase P1 → Agent P1 → Summarizer (20 min)
           ↓
Phase P2 → Python script → Database Update (5 min)

Total: 40 minutes
```

---

## Before You Start

1. **Review `CLAUDE.md`** — Confirm editorial policy, model stack, data integrity rules
2. **Check data freshness** — Run `ls -lh docs/data/indicators.json docs/data/briefing_latest.json`
3. **Note today's date** — This becomes the briefing `week_of`
4. **Confirm mode** — Ask: Run full pipeline (briefing + projects)? Just briefing? Just project track?

---

## BRIEFING TRACK — Detailed Dispatch

### Phase 0: Data Refresh

**Agent:** `tldr-data-refresh`

**Your job:**
1. Dispatch the agent
2. Wait for completion
3. Validate:
   - `indicators.json` modified within last 30 min
   - `briefing_latest.json` has fresh `metrics`, `financialMarkets`, `commodities`
   - At least 5 commodity prices updated (not all zeros)
   - All 102 timeseries keys have data

**On failure:**
- Report which validation failed
- Ask: Retry, skip with stale data, or abort?

---

### Phase 0.1: Timeseries Sync (Python tool)

**Tool:** `tools/sync_timeseries.py`

**Your job:**
1. Run `python tools/sync_timeseries.py` immediately after Phase 0.
2. The tool syncs the seven authoritative national indicators from `indicators.json` (StatCan / BoC history) into `timeseries.json`:
   - `unemployment`, `cpi`, `gdp`, `housing_starts`, `boc_rate`, `employment_rate`, `participation_rate`
3. Validate:
   - Exit code 0
   - `timeseries.json` modified timestamp newer than before the run
   - Log reports ">= 7 series synced"

**Why this gate exists:** `indicators.json` and `timeseries.json` are separate stores. Charts read `timeseries.json`. Without this sync, national unemployment / CPI / GDP charts render blank even though the data exists in `indicators.json`. This gate was added after the 2026-04-18 regression where the national unemployment chart was blank.

**On failure:**
- Report exit code + stderr
- Ask: Retry, continue with stale timeseries (chart blanks expected), or abort?

---

### Phase 0.5: Data Gap Audit

**Agent:** `tldr-data-gap`

**Your job:**
1. Dispatch the agent
2. Wait for completion
3. Validate:
   - `data_gap_report.md` exists
   - Contains sections: "Critical Gaps," "Warnings," "Filled This Run," "Coverage Summary"
   - Read critical gaps count

**On validation:**
- If >5 critical gaps: Report them. Ask user: Proceed anyway, or investigate first?
- If ≤5: Proceed to Phase 1

---

### Phase 0.9: Load Cross-Edition Context (1 min)

Before dispatching researchers, load the Obsidian vault context so researchers frame stories as "what changed since last edition" rather than treating every story as new.

**Your job:**
1. Read `C:/Users/walte/OneDrive/SecondBrain/01-projects/can-macro-dashboard/running-threads.md` — the 8 active story threads the agents should track week-to-week
2. Find and read the most recent edition summary in `C:/Users/walte/OneDrive/SecondBrain/01-projects/can-macro-dashboard/editions/` (latest file by date — e.g. `2026-04-18.md`)
3. Optionally skim `data-freshness.md` for any indicators flagged stale
4. Build a cross-edition context block (under 500 words) containing:
   - The titles of all active running threads + one-line "next watch" for each
   - The previous edition's headline + 3-5 key data points shipped
   - Any data freshness flags that researchers should be aware of
5. Pass this context block to **all three Phase 1 researchers** as a prepended section in their dispatch prompt, labeled `## Cross-Edition Context — Previous Edition & Active Threads`

**Why this exists:** Researchers previously treated every edition as a cold start, causing stale framing (repeating context already delivered last week) and missed continuity (ignoring threads the reader was already following). Adding this context preamble to each researcher prompt keeps the 8 active threads visible and lets researchers write "what changed" rather than "what happened." See `project_obsidian_agent_context.md` in user memory for background.

**On failure:**
- If vault files are missing: log a warning and proceed without cross-edition context. Do NOT block the pipeline on a missing vault. Researchers default to their normal cold-start behavior.
- If the vault is present but empty: use whatever is available.

---

### Phase 1: Research (3 parallel agents)

**Agents:** `tldr-researcher-macro` (1A), `tldr-researcher-provincial` (1B), `tldr-researcher-sector` (1C)

**Your job:**
1. Dispatch all three in parallel via single Skill call with separate agent specifications. **Each dispatch prompt MUST include the cross-edition context block built in Phase 0.9 as the first section.**
2. Wait for all three to complete
3. Validate each:

   **1A (Macro):**
   - `research_macro.md` exists, >800 words
   - Covers: BoC, GDP, CPI, unemployment, housing, trade, financial markets, global, consumer pulse

   **1B (Provincial):**
   - `research_provinces.md` exists, >1500 words
   - Mentions all 13 provinces by name
   - Each province has at least one indicator value

   **1C (Sector):**
   - `research_sectors.md` exists, >1000 words
   - Covers goods (5) and services (15) industries
   - Each has at least one source URL

**On failure:**
- Report which researcher failed and why
- Ask: Retry that one, skip, or abort?

---

### Phase 2: Analysis (3 parallel agents)

**Agents:** `tldr-analyst-macro` (2A), `tldr-analyst-provincial` (2B), `tldr-analyst-industry` (2C)

**Your job:**
1. Dispatch all three in parallel
2. Wait for all three to complete
3. Validate each:

   **2A (Macro dossier):**
   - Valid JSON
   - Contains: `headline`, `key_indicators` (≥5), `sources_registry` (≥20), `global` (exactly 4 regions), `executive_summary_package`

   **2B (Provincial dossier):**
   - Valid JSON
   - `provinces` array with exactly 13 items
   - Each province has: `name`, `indicators`, `indicatorMeta`, `story_threads`, `policy_items`, `cross_references`

   **2C (Industry dossier):**
   - Valid JSON
   - `goodsIndustries` = 5 items, `servicesIndustries` = 15 items
   - Each has: `code` (NAICS), `name`, `sector_data`, `project_counts`, `cross_references`, `trend_analysis`

**On failure:**
- Report JSON error or missing structure
- Ask: Retry or abort?

---

### Phase 3: Writing (6 parallel agents)

**Group 1 — Core:** `tldr-writer-macro` (3A)
**Group 2 — Sectors:** `tldr-writer-provincial` (3B), `tldr-writer-goods` (3C), `tldr-writer-services` (3D)
**Group 3 — Markets:** `tldr-writer-market-commentary` (3F, solo) + `tldr-writer-markets-triad` (3-TRIAD, consolidated equities/FX-yields/commodities)

> **Markets phase consolidation (2026-04):** Agents 3G (equities), 3H (FX/yields), and 3I (commodities) have been merged into a single `tldr-writer-markets-triad` dispatch. The merge preserves writing quality (validated against production baseline) while halving the Markets phase quota cost. Agent 3F (commentary) remains solo to protect the narrative-heaviest section from attention dilution. The three legacy writer skills are archived at `.claude/skills/_archive/` and are no longer dispatched by the Conductor.

**Your job:**
1. Dispatch all six in parallel (3A, 3B, 3C, 3D, 3F, 3-TRIAD)
2. Wait for all six to complete
3. Validate each:

   **3A (Macro JSON):**
   - Valid JSON
   - Contains: `headline`, `edition`, `executive_summary` (>200 words), `national.analysis` (>300 words), `consumer_pulse`, `watchlist`, `global` (4 regions), `sources` (each with specific URL)
   - Does NOT contain: `financialMarkets`, `commodities`, `yieldCurve` (these are now handled by Agent 3F and Agent 3-TRIAD)
   - Editorial spot-check: Read 2–3 sentences from `national.analysis`. Verify wire-service tone (factual, specific, no opinions). Flag any banned words.

   **3B (Provincial JSON):**
   - Valid JSON
   - `provinces` = 13 items
   - Each has: `name`, `indicators`, `indicatorMeta`, `analysis` (HTML, non-empty), `sources[]` (specific URLs)
   - Editorial spot-check: 3 random provinces, read 2–3 sentences each. Verify tone, flag banned words.

   **3C (Goods JSON):**
   - Valid JSON
   - `goodsIndustries` = 5 items
   - Each has: `code`, `name`, `analysis` (HTML, >100 words), `sources[]`, `trend`, `projectCount`
   - Editorial spot-check: 2 random industries, read 2–3 sentences. Verify tone.

   **3D (Services JSON):**
   - Valid JSON
   - `servicesIndustries` = 15 items
   - Each has: `code`, `name`, `analysis` (HTML, >80 words), `sources[]`, `trend`, `projectCount`
   - Editorial spot-check: 2 random industries, read 2–3 sentences. Verify tone.

   **3F (Market Commentary JSON):**
   - Valid JSON
   - Contains: `market_commentary` (HTML, 150–200 words), `sources[]`
   - Has `<span class="lead-sentence">` em dash leads in both paragraphs
   - Cross-references project pipeline counts and dollar values
   - Editorial spot-check: Verify wire-service tone. Flag banned words.

   **3-TRIAD (Markets Triad — consolidated equities/FX-yields/commodities):**
   Produces three output files in one dispatch. Validate each file:

   *briefing_market_equities.json:*
   - Valid JSON
   - `equities` array with exactly 4 items (TSX Composite, S&P 500, DJIA, Nasdaq Composite)
   - Each has: `name`, `symbol`, `value`, `weekly_pct`, `ytd_pct`, `yoy_pct`, `high_52w`, `low_52w`, `commentary`
   - Total commentary word count: 380–475 words (new target, +50% over legacy)
   - Each commentary has `<span class="lead-sentence">` em dash lead

   *briefing_market_fx_yields.json:*
   - Valid JSON
   - `fx.pairs` with ≥3 currency pairs, `fx.fx_commentary` (180–225 words)
   - `yieldCurve.tenors` — tenor count matches dossier supply (6 or 7 tenors); do not require a fixed count if dossier is partial
   - `yieldCurve.yield_commentary` (175–225 words)
   - `yieldCurve.spread_2_10` and `yieldCurve.curve_shape` present
   - Both commentaries have em dash leads

   *briefing_market_commodities.json:*
   - Valid JSON
   - `commodities` array — 1 to 13 items (triad writer may mark missing commodities N/A per Rule 5 no-fabrication)
   - `commodity_commentary` (170–210 words) with em dash lead
   - `wcs_analysis` present (may be null or all-N/A if dossier did not carry WCS data)
   - Per-commodity total word count: 980–1,210 if all 13 present; scales proportionally for partial coverage
   - WTI `projects_above_breakeven` may be N/A if dossier did not carry breakeven thresholds

   *Craft-rule spot-checks across all three triad files:*
   - Causal drivers present for every major market move (search for `as the`, `driven by`, `reflecting`, `following`, `amid`, `after`)
   - At least 9 historical benchmarks across the triad (`since [month year]`, `52-week high/low`, `highest/lowest in N`, `contract inception`)
   - At least 2 conditional cross-references (`if [trigger]...would...`)
   - Product voice: "The Signal Dispatch cross-reference engine" appears in each file
   - No taxonomy key leakage in prose (no `oil_gas`, `power_energy`, `commercial_mixed`, `transport_logistics` — must be spelled out in natural English)
   - Editorial spot-check: Verify tone. Flag banned words.

**Editorial Spot-Check Detail:**

For each sample, ask yourself: Does this read like wire-service journalism?

- GOOD: "The BoC cut rates 25bps to 4.75% on March 12. The database contains 23 proposed residential projects ($4.2B) in rate-sensitive sectors."
- BAD: "This rate cut is good news for housing and should accelerate approvals."

Search entire output for banned words (case-insensitive): should, must, hopefully, unfortunately, worrying, promising, encouraging, welcome, bullish, bearish, concerning, thrilled, feared, hoped

If found: Report location and word. Ask: Retry writer to remove, or skip check?

If not found and tone is good: Proceed.

**On failure:**
- Invalid JSON: Retry that writer
- Too short or missing sections: Retry
- Banned words or bad tone: Ask user to retry or proceed to Fixer

---

### Phase 3.25: Visualizer

**Agent:** `tldr-visualizer`

**Your job:**
1. Dispatch the agent (sequential, after all 8 Phase 3 writers complete)
2. Wait for completion
3. Validate:
   - `docs/data/briefing_visualizations.json` exists
   - Valid JSON
   - `chart_count` is between 1 and 6 (inclusive)
   - Each chart has required fields: `id`, `tab`, `insertion_point`, `section`, `svg`, `chart_type`, `data_keys_used`
   - All `data_keys_used` values exist in `timeseries.json`
   - No chart has empty `svg` field
   - `editorial_rationale` is non-empty for each chart (explains why THIS chart was chosen THIS week)

**On failure:**
- Missing file or invalid JSON: Ask user: Retry or skip visualizer (assembly will proceed without charts)?
- Chart count outside 1–6 range: Report count. Ask: Retry or proceed?
- Missing fields: Report which chart is incomplete. Ask: Retry or skip?

---

### Phase 3.5: Assembly

**Agent:** `tldr-assembler`

**Your job:**
1. Dispatch the agent (sequential, after all Phase 3 writers complete)
2. Wait for completion
3. Validate:
   - Output file exists: `docs/data/briefing_YYYY-MM-DD.json` (check filename has correct date)
   - Valid JSON
   - Completeness: All 31 required top-level fields
   - Structure:
     - `provinces` = 13 items
     - `goodsIndustries` = 5 items
     - `servicesIndustries` = 15 items
     - `global` = 4 items
   - `id` incremented from last week
   - Citation integrity:
     - Every `<sup>N</sup>` in all HTML fields maps to `_all_verified_sources`
     - Sample 5 random citations; verify each has specific URL (not homepage)
   - Market fragments consumed: `briefing_market_commentary.json`, `briefing_market_equities.json`, `briefing_market_fx_yields.json`, `briefing_market_commodities.json`
   - Visualizations integrated: `briefing_visualizations.json` (if present — graceful degradation if absent)

**On failure:**
- Report which validation failed
- Ask: Retry assembler or abort?

---

### GATE 3.5: Schema Validation (Python tool) — HARD FAIL

**Tool:** `tools/validate_briefing_schema.py`

**Your job:**
1. Immediately after Phase 3.5 assembly succeeds, run:
   ```
   python tools/validate_briefing_schema.py docs/data/briefing_YYYY-MM-DD.json
   ```
2. The validator runs 639 checks covering: canonical field names, metric `_chg` keys, commodity/equity name conformance to `_mktTsMap`, yieldCurve list structure, global 5-key requirement, per-province `marketContext` + `watchlistItems`, banned-word scan, citation integrity.
3. This is a **hard gate** — exit code != 0 means the briefing does NOT proceed to Phase 4. No "proceed anyway" option.

**On failure:**
- Capture stdout (the failure report)
- Report the first 10 failures to the user
- Options: (a) re-run Phase 3.5 assembler (assembler Phase 4.5 normalization may have bugs), (b) spot-fix JSON manually and re-validate, (c) abort

**Why this gate exists:** The 2026-04-18 audit found 42 schema gaps that silently shipped to production because there was no pre-ship validation. See `PATCH_LOG_SCHEMA_PARITY.md` for the full inventory.

---

### Phase 4: Charts

**Agent:** `tldr-charts`

**Your job:**
1. Dispatch the agent (sequential, after Assembly) with explicit instruction: **"Produce Option C editorial layout for every chart by default. Legacy layout is only permitted for full yield curves, >8-category diverging bars, and stacked-area multi-series snapshots. Both National charts must be Option C (100%). Provincial charts must be ≥80% Option C across the 26-chart set."**
2. Wait for completion
3. Validate:
   - Briefing JSON updated (check timestamp)
   - Top-level `insightCharts` array = 2 items
   - Each province object has `insightCharts` array = 2 items
   - **Each `goodsIndustries[]` object (5 total) has `insightCharts` array = 1 item**
   - **Each `servicesIndustries[]` object (15 total) has `insightCharts` array = 1 item**
   - **Total charts ≥ 48 (2 national + 26 provincial + 20 industry)**
   - All `dataKeys` exist in declared `dataSource` (`indicators.json` history or `timeseries.json`)
   - **Option C ratio:** both national charts have non-empty `kpis` arrays; ≥21/26 provincial charts have non-empty `kpis` arrays (≥80%)

**Quick Python validation:**
```python
import json
b = json.load(open('docs/data/briefing_YYYY-MM-DD.json'))
ts = json.load(open('docs/data/timeseries.json'))
try:
    ind = json.load(open('docs/data/indicators.json'))
    ind_keys = {r.get('indicator_name') for r in ind.get('history', []) if r.get('indicator_name')}
except Exception:
    ind_keys = set()
ts_keys = set(ts.keys())

issues = []
for c in b.get('insightCharts', []):
    ds = c.get('dataSource', 'timeseries')
    for dk in c.get('dataKeys', []):
        keyset = ind_keys if ds == 'indicators' else ts_keys
        if dk not in keyset:
            issues.append(f'National/{ds}: missing {dk}')

for p in b.get('provinces', []):
    for c in p.get('insightCharts', []):
        ds = c.get('dataSource', 'timeseries')
        for dk in c.get('dataKeys', []):
            keyset = ind_keys if ds == 'indicators' else ts_keys
            if dk not in keyset:
                issues.append(f'{p["name"]}/{ds}: missing {dk}')

for tier in ('goodsIndustries', 'servicesIndustries'):
    for ind_obj in b.get(tier, []):
        for c in ind_obj.get('insightCharts', []):
            ds = c.get('dataSource', 'indicators')
            for dk in c.get('dataKeys', []):
                keyset = ind_keys if ds == 'indicators' else ts_keys
                if dk not in keyset:
                    issues.append(f'{ind_obj.get("name","?")}/{ds}: missing {dk}')

# Mandatory count gate — HARD FAIL
nat = len(b.get('insightCharts', []))
prov_charts = [c for p in b.get('provinces', []) for c in p.get('insightCharts', [])]
goods_charts = [c for g in b.get('goodsIndustries', []) for c in g.get('insightCharts', [])]
svc_charts = [c for s in b.get('servicesIndustries', []) for c in s.get('insightCharts', [])]
total = nat + len(prov_charts) + len(goods_charts) + len(svc_charts)
print(f'Chart counts: national={nat}, provincial={len(prov_charts)}, goods={len(goods_charts)}, services={len(svc_charts)}, total={total}')
if total < 48:
    raise SystemExit(f'FAIL — expected >= 48 charts, got {total}. Industries most likely empty. Re-dispatch chart agent.')

print(f'Issues: {len(issues)}')
if issues: print('\n'.join(issues[:10]))

# Option C ratio check (Tier 1.7 — editorial layout default)
nat_optc = sum(1 for c in b.get('insightCharts', []) if c.get('kpis'))
prov_optc = sum(1 for c in prov_charts if c.get('kpis'))
print(f'Option C: National {nat_optc}/2, Provincial {prov_optc}/{len(prov_charts)}')
if nat_optc < 2:
    print(f'FAIL — National charts must both be Option C, got {nat_optc}/2')
if prov_charts and prov_optc / len(prov_charts) < 0.8:
    print(f'FAIL — Provincial Option C ratio {prov_optc/len(prov_charts):.0%} < 80% required')
```

**On failure:**
- If chart count < 48: re-dispatch `tldr-charts` agent with explicit instruction to generate all three tiers (national, provinces, industries). Do NOT proceed with partial charts.
- Report specific issues
- Ask: Retry or skip charts?

---

### GATE 4: Schema Validation (Python tool) — HARD FAIL

**Tool:** `tools/validate_briefing_schema.py`

**Your job:**
1. Immediately after Phase 4 charts succeed, re-run:
   ```
   python tools/validate_briefing_schema.py docs/data/briefing_YYYY-MM-DD.json
   ```
2. The chart agent can introduce new data (inline series data on chart specs) that may violate the schema. Re-running the validator after Phase 4 catches regressions.
3. This is a **hard gate** — exit code != 0 means the briefing does NOT proceed to Phase 5.

**On failure:**
- Capture stdout failures
- Options: (a) re-run Phase 4 charts, (b) spot-fix JSON, (c) abort

---

### Phase 5: Quality (2 parallel agents)

**Agents:** `tldr-auditor` (5), `tldr-discovery` (7)

**Your job:**
1. Dispatch both in parallel
2. Wait for both to complete
3. Validate:

   **Agent 5 (Auditor):**
   - `audit_report.md` exists
   - Contains verdict: PASS / PASS WITH WARNINGS / FAIL
   - Lists results for 10 tests (Number Verification, Citation Integrity, Editorial Compliance, Logic, Completeness, Freshness, Schema, Cross-Agent, Comparative Sanity, Security)

   **Agent 7 (Discovery):**
   - `discovery_batch.json` exists
   - Valid JSON
   - Each project has: `name`, `sector`, `province`, `value`, `status`, `evidence_url` (non-empty), `summary`

**Branching on Auditor verdict:**
- **PASS**: Skip Phase 6, proceed to Deploy
- **PASS WITH WARNINGS**: Run Phase 6 for fixes, then Deploy
- **FAIL**: Run Phase 6 (mandatory), then optionally re-audit

---

### Phase 6: Fix (conditional)

**Agent:** `tldr-fixer`

**Your job:**
1. Only dispatch if Phase 5 Auditor returned non-PASS
2. Give agent the audit report and briefing
3. Agent fixes: banned words, generic/missing URLs, broken citations, duplicates, schema issues
4. Wait for completion
5. Validate:
   - Briefing JSON updated
   - Re-run Auditor's top 3 tests (Number, Citation, Editorial) on fixed briefing
   - Report if all critical issues resolved

**On success:**
- Proceed to Deploy

**On partial fix:**
- Ask user: Proceed to Deploy with remaining issues, or abort?

---

### GATE PRE-DEPLOY: Schema Validation (Python tool) — HARD FAIL, NO OVERRIDE

**Tool:** `tools/validate_briefing_schema.py`

**Your job:**
1. Immediately before the Deploy step, and *after* Phase 6 (Fix) has run if it was needed, run the validator one last time against the candidate briefing that is about to be promoted to `briefing_latest.json`:
   ```
   python tools/validate_briefing_schema.py docs/data/briefing_YYYY-MM-DD.json
   ```
2. Exit codes: `0 = PASS`, `1 = FAIL`, `2 = WARN`. This gate is **non-negotiable**:
   - Exit 0: proceed to Deploy.
   - Exit 2 (WARN only, 0 FAIL): proceed to Deploy. WARN-tier issues are the known B.4 producer-regen gaps and data freshness flags.
   - Exit 1 (any FAIL): **ABORT the deploy.** Do NOT run `cp briefing_YYYY-MM-DD.json briefing_latest.json`, do NOT run `archive_briefing.py`, do NOT commit, do NOT push. Report the failure list to the user and re-enter Phase 6 (Fixer) or manual spot-fix.
3. There is **no override flag**, no "proceed anyway" option, and no silent ship path. The validator is the last-line gate between the pipeline and production.

**Why this gate exists:** GATE 3.5 and GATE 4 catch assembler/charts regressions mid-pipeline. But Phase 5 (Auditor) and Phase 6 (Fixer) both mutate the briefing JSON after those gates, and manual spot-fixes may be applied between Phase 6 and Deploy. This final re-validation ensures that whatever is about to be promoted to `briefing_latest.json` still honors the schema contract. Without it, a well-intentioned Fixer patch or manual edit can silently reintroduce the exact 42-gap class the zero-gap hardening (Phase B) was built to prevent. See `HANDOFF_NEXT_SESSION.md` Phase B.5 and the Pipeline Invariants line in `CLAUDE.md`.

---

### Deploy

**Your job:**
1. Display summary:
   ```
   PIPELINE COMPLETE — Week of [DATE]

   Files produced:
     ✓ indicators.json (Agent 0)
     ✓ research_macro/provinces/sectors.md (Agents 1A/1B/1C)
     ✓ dossier_macro/provinces/industries.json (Agents 2A/2B/2C)
     ✓ briefing_macro/provinces/goods/services.json (Agents 3A/3B/3C/3D)
     ✓ briefing_market_commentary.json (Agent 3F) + briefing_market_equities/fx_yields/commodities.json (Agent 3-TRIAD)
     ✓ briefing_visualizations.json (Visualizer 3.25)
     ✓ briefing_YYYY-MM-DD.json (Agent 3E + 4 + 6)
     ✓ audit_report.md (Agent 5)
     ✓ discovery_batch.json (Agent 7)

   Briefing summary:
     Headline: [headline from dossier]
     Industries: 5 goods + 15 services
     Provinces: 13 with 28 charts
     Sources: [count] citations
     Audit verdict: [PASS/PASS WITH WARNINGS/FAIL]

   Publish to live dashboard?
   ```

2. Wait for user approval (yes/no/review-report)

3. On approval, run bash commands:

```bash
# Backup current live briefing
cp docs/data/briefing_latest.json docs/data/briefing_BACKUP_$(date +%Y-%m-%d).json

# Promote new briefing to live
cp docs/data/briefing_YYYY-MM-DD.json docs/data/briefing_latest.json

# Update archive
python tools/archive_briefing.py docs/data/briefing_YYYY-MM-DD.json

# Export PDF and DOCX
python tools/briefing_export.py docs/data/briefing_latest.json --format pdf
python tools/briefing_export.py docs/data/briefing_latest.json --format docx

# Commit and push
cd docs
git add data/briefing_latest.json data/briefing_YYYY-MM-DD.json data/briefing_archive.json briefing.pdf briefing.docx
git commit -m "Publish weekly briefing — $(date +%Y-%m-%d)"
git push origin main
```

**Validate after deploy:**
- All git commands succeeded (no errors)
- Files committed and pushed
- GitHub Actions triggered (if configured)

---

### Post-Deploy: Update Obsidian Vault (1 min)

After a successful deploy, write back to the Obsidian vault so the next edition's Phase 0.9 picks up current state:

1. Create a new edition summary at `C:/Users/walte/OneDrive/SecondBrain/01-projects/can-macro-dashboard/editions/YYYY-MM-DD.md` with:
   - Headline
   - 3-5 key data points shipped (exact figures)
   - List of threads this edition touched
   - Any stories introduced for the first time (candidates for new running threads)
2. Update `running-threads.md`:
   - For each active thread, update the "Current state" and "Next" lines based on what shipped
   - Retire threads that have fully resolved (move to a `retired-threads.md` section or delete)
   - Add any new multi-week stories as new threads
3. Update `data-freshness.md`:
   - Bump the "last refreshed" column for any indicator that got a new reading
   - Flag any series that are now >2 periods stale

**On failure:**
- If the vault write fails (permissions, disk), log the error but do NOT fail the pipeline. The edition is already live.
- Surface the failure to the user at the end of the summary so they can hand-update.

---

## PROJECT TRACK — Detailed Dispatch

The project track maintains the database. It can run in parallel with briefing phases 0–0.5 (Option C in ARCHITECTURE.md).

### Phase P0: Project Monitoring (29 parallel agents)

**Agents:**
- 1 National: `tldr-project-monitor-nat`
- 13 Provincial: `tldr-project-monitor-ON`, `tldr-project-monitor-QC`, ..., `tldr-project-monitor-NU`
- 15 CMA: `tldr-project-monitor-CMA-TOR`, `tldr-project-monitor-CMA-MTL`, ..., `tldr-project-monitor-CMA-STJ`

**Your job:**
1. Dispatch all 29 in parallel
2. Each monitor reads `projects_all.json` (filtered to its jurisdiction)
3. Each searches for status updates and new projects
4. Each writes `docs/data/monitor/{jurisdiction}.json`

**Validate each:**
- File exists: `docs/data/monitor/{jurisdiction}.json`
- Valid JSON
- Has: `jurisdiction`, `type` (province/cma/national), `run_date`, `existing_projects_checked`, `status_updates[]`, `new_projects[]`
- Each `status_update` has: `project_name`, `current_status`, `new_status`, `evidence_url` (specific), `summary`
- Each `new_project` has: `name`, `sector`, `province`, `value`, `status`, `proponent`, `evidence_url` (specific), `summary`

**On failure:**
- Report which monitor failed
- Ask: Retry that one, skip, or abort project track?

---

### Phase P1: Project Summarizer

**Agent:** `tldr-project-summarizer`

**Your job:**
1. Dispatch after all P0 monitors complete
2. Agent reads all `monitor/*.json` files
3. Agent writes:
   - `project_summaries.json` (2–4 sentence summaries for new/updated projects)
   - `project_updates.json` (chronological update logs)

**Validate:**
- Both files exist and are valid JSON
- `project_summaries.json`: Each entry has `norm_key`, `summary` (50–500 chars), `generated_at`
- `project_updates.json`: Each entry has `norm_key`, `updates[]` with `date`, `type`, `summary`, `evidence_url`

**On failure:**
- Report which file is malformed
- Ask: Retry, skip project summaries, or abort?

---

### Phase P2: Database Update

**Tool:** Python script (NOT a Claude agent)

**Your job:**
1. Run the bash command:
```bash
python tools/project_monitor_ingest.py \
  --monitors docs/data/monitor/ \
  --db dashboard.db \
  --summaries docs/data/project_summaries.json \
  --updates docs/data/project_updates.json \
  --export docs/data/projects_all.json
```

2. Validate:
   - Script completes without error
   - `dashboard.db` updated (check timestamp)
   - `projects_all.json` re-exported (check timestamp, file size)
   - Script reports: X projects updated, Y new, Z rejected (no URL)

**On failure:**
- Report error
- Ask: Retry, debug, or abort project track?

---

## Error Handling Protocol

At every validation gate:

1. **Report explicitly:**
   - Which agent/step failed
   - Which validation check failed
   - What was expected vs. actual
   - Example if available

2. **Ask the user:**
   ```
   [Agent X] failed on [check name].
   Expected: [description]
   Actual: [description]

   Options: (retry / skip / debug / abort)
   ```

3. **Implement choice:**
   - **retry**: Dispatch the same agent fresh
   - **skip**: Note gap in conductor log, proceed to next phase
   - **debug**: Pause, ask user to investigate intermediate files
   - **abort**: Stop, preserve all files for debugging

4. **Never proceed silently past a failure.** Every gap is explicit.

---

## Editorial Enforcement

All narrative output must follow these rules:

### Rule 1: No Editorializing

**Banned words (case-insensitive, whole-word):**
should, must, hopefully, unfortunately, worrying, promising, encouraging, welcome, bullish, bearish, concerning, thrilled, feared, hoped

**Detection:** Search all `analysis` fields. On finding any: Report location and word. Ask: Retry writer or skip check?

### Rule 2: Wire-Service Tone

Every claim should fit one of these patterns:

1. **Fact:** "X is Y" — "The BoC rate is 4.75%"
2. **Contextual fact:** "X happened. Y is context." — "The BoC cut rates 25bps. The database contains 23 projects with improved cash flow dynamics."
3. **Conditional:** "If X, then Y." — "If rates hold at 4.75%, 23 projects would see..."
4. **Attribution:** "According to [source], X is Y." — "According to StatCan, unemployment rose 0.3 percentage points."

**Anti-patterns:**
- Predictions without conditionals: "X will happen"
- Recommendations: "Canada should/must do X"
- Value judgments: "This is good/bad/worrying"
- Causal assertions: "X caused Y" (instead: "X and Y coincided; database links projects")

### Rule 3: Specific Citations

Every claim must cite a specific, verifiable source URL — not a homepage.

**Good:**
- `https://www150.statcan.gc.ca/n1/daily-quotidien/260313/dq260313a-eng.htm` (specific StatCan release)
- `https://www.bankofcanada.ca/2026/03/fad-press-release-2026-03-12/` (specific BoC announcement)

**Bad:**
- `https://www.statcan.gc.ca` (homepage)
- `https://www.bankofcanada.ca` (homepage)
- Empty string `""` (no URL)

**Auditor checks:**
- Every `<sup>N</sup>` maps to a source with a non-empty `url`
- No source URL is a homepage pattern (domain root, `/en/`, `/home`, URLs <40 chars)
- Sample citations for plausibility (source title matches expected content)

**Fixer responsibility:**
- Replace generic URLs with specific ones via WebSearch
- If exact URL can't be found, add note: `"url_note": "Exact page not found; attributed to [institution] [date]"`
- Never fabricate URLs

---

## Conductor Progress Tracking

Use TodoWrite to track which phases are complete:

```
Phase 0: in_progress (Data Refresh running)
Phase 0: completed
Phase 0.5: in_progress (Data Gap Audit running)
Phase 0.5: completed
Phase 1: in_progress (Researchers 1A, 1B, 1C dispatched)
Phase 1: completed
...
Phase 5: completed
Phase 6: FAILED — Auditor raised critical issues
  Status: awaiting user decision (retry/skip/abort)
```

Update immediately when phase status changes.

---

## File Contracts

### Data Input Files (Read but not modified by conductor)

| File | Role |
|------|------|
| `docs/data/briefing_latest.json` | Template for writers |
| `docs/data/indicators.json` | Input for researchers, analysts, writers |
| `docs/data/projects_all.json` | Input for researchers, analysts, monitors |
| `docs/data/timeseries.json` | Input for charts |
| `docs/data/policy.json` | Input for researchers, analysts |
| `docs/data/commodities.json` | Input for researchers, analysts, writers |
| `docs/data/events.json` | Input for researchers, analysts |

### Intermediate Files (Session-scoped)

| File | Producer | Consumer |
|------|----------|----------|
| `data_gap_report.md` | Agent 0.5 | Researchers 1A/1B/1C |
| `research_macro/provinces/sectors.md` | Agents 1A/1B/1C | Analysts 2A/2B/2C, Auditor |
| `dossier_macro/provinces/industries.json` | Agents 2A/2B/2C | Writers 3A/3B/3C/3D, Fixer |
| `briefing_macro/provinces/goods/services.json` | Agents 3A/3B/3C/3D | Assembler 3E |
| `briefing_market_commentary.json` | Agent 3F (`tldr-writer-market-commentary`) | Assembler 3E |
| `briefing_market_equities.json` | Agent 3-TRIAD (`tldr-writer-markets-triad`) | Assembler 3E |
| `briefing_market_fx_yields.json` | Agent 3-TRIAD (`tldr-writer-markets-triad`) | Assembler 3E |
| `briefing_market_commodities.json` | Agent 3-TRIAD (`tldr-writer-markets-triad`) | Assembler 3E |
| `briefing_visualizations.json` | Visualizer (3.25) | Assembler 3E |
| `monitor/*.json` | P0 monitors | P1 Summarizer, P2 script |

### Final Outputs (Persistent)

| File | Producer | Status |
|------|----------|--------|
| `briefing_YYYY-MM-DD.json` | Assembler → Charts → Fixer | Archived weekly |
| `briefing_latest.json` | Deploy step | Live |
| `audit_report.md` | Auditor | Archived weekly |
| `discovery_batch.json` | Discovery agent | Archived weekly |
| `project_summaries.json` | P1 Summarizer | Persistent |
| `project_updates.json` | P1 Summarizer | Persistent |
| `projects_all.json` | P2 script | Live |
| `dashboard.db` | P2 script | Persistent |

---

## Execution Example

```
User: "Run the full pipeline"

Conductor:
> Phase 0: Dispatching Agent 0 (Data Refresh)...
  ✓ Agent 0 complete. 102 indicators updated, 12 market prices refreshed.

> Phase 0.1: Running tools/sync_timeseries.py...
  ✓ Synced 7 national series (unemployment, cpi, gdp, housing_starts, boc_rate, employment_rate, participation_rate) from indicators.json → timeseries.json.

> Phase 0.5: Dispatching Agent 0.5 (Data Gap Audit)...
  ✓ Agent 0.5 complete. 2 warnings (US GDP delayed, NL not yet released).
  Proceed? (yes/review)

User: yes

> Phase 1: Dispatching Agents 1A, 1B, 1C (parallel)...
  ✓ All three completed.
    1A: 2100 words, macro complete
    1B: 1800 words, all 13 provinces covered
    1C: 1600 words, all 20 industries

> Phase 2: Dispatching Agents 2A, 2B, 2C (parallel)...
  ✓ All three completed. Dossiers valid.
  Proposed headline: "BoC Hold Amid Labour Softening"

> Phase 3: Dispatching Agents 3A, 3B, 3C, 3D, 3F, 3-TRIAD (parallel)...
  ✓ All eight completed. Editorial spot-check passed.
  Group 1 (Core): 3A macro — 1800 words
  Group 2 (Sectors): 3B provinces, 3C goods, 3D services — 3400 words
  Group 3 (Markets): 3F commentary 265w, 3-TRIAD equities 426w + FX/yields 401w + commodities 1,290w

> Phase 3.25: Dispatching Visualizer...
  ✓ Complete. 3 editorial charts generated (WTI breakeven, ON/QC permits, yield curve shift).

> Phase 3.5: Assembling briefing_2026-03-31.json...
  ✓ Complete. All required fields. 13 provinces, 20 industries, 4 market fragments merged, 3 charts inserted, citations intact.

> GATE 3.5: Running tools/validate_briefing_schema.py...
  ✓ 639/639 checks passed. Schema contract honored.

> Phase 4: Generating 48 charts...
  ✓ Complete. National 2 + provinces 26 + industries 20 = 48.

> GATE 4: Re-running tools/validate_briefing_schema.py...
  ✓ 639/639 checks passed post-charts.

> Phase 5: Running audits (parallel)...
  ✓ Auditor: PASS WITH WARNINGS (2 generic URLs, 1 duplicate)
  ✓ Discovery: 7 new projects found

> Phase 6: Running fixer...
  ✓ Fixed 2 URLs, removed 1 duplicate. All critical issues resolved.

PIPELINE COMPLETE — Week of 2026-03-31
  Headline: "BoC Hold Amid Labour Softening"
  Industries: 5 goods + 15 services (20 charts)
  Provinces: 13 with 26 charts
  National: 2 charts
  Total charts: 48
  Schema validation: PASS (639/639 checks)
  Sources: 247 citations
  Audit: PASS

Publish to GitHub Pages? (yes/review/no)

User: yes

> Backing up previous briefing...
> Promoting new briefing...
> Exporting PDF and DOCX...
> Committing and pushing...
  ✓ Deployed. GitHub Pages updated.

DONE. Briefing is live.
```

---

## Timing Expectations

| Phase | Duration | Notes |
|-------|----------|-------|
| 0 | 8 min | Data refresh |
| 0.5 | 5 min | Gap audit |
| 1 | 20 min | Parallel: 3 researchers |
| 2 | 12 min | Parallel: 3 analysts |
| 3 | 20 min | Parallel: 8 writers (3 groups) |
| 3.25 | 5 min | Visualizer |
| 3.5 | 8 min | Assembly (8 fragments + visualizations) |
| 4 | 8 min | Charts |
| 5 | 8 min | Parallel: auditor + discovery |
| 6 | 8 min | Fix (if needed) |
| Deploy | 3 min | Bash |
| **Total Briefing** | **88–105 min** | — |
| **Project Track** | **40 min** | Can run in parallel |

---

## How to Use This Skill

**Start the pipeline:**
```
"Run the full briefing and project pipeline"
"Execute briefing track only"
"Start project monitoring"
```

**During execution:**
- Receive phase-by-phase status updates
- Get validation reports
- On error: Answer prompts (retry/skip/abort)

**At deploy:**
- Review summary
- Approve publication
- Monitor git push

The conductor handles everything else — dispatch, validation, error handling, editorial enforcement.

