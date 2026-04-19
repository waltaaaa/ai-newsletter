# SESSION HANDOFF — The Lagging Indicator: Callout Phase 4 + Full Newsletter Hardening

## Context (carry forward — do not re-derive)
You are resuming mid-execution. The prior session:

1. Refactored frontend chart chrome across TL;DR, National, Provinces, Industries (cream callout cards, red rule, Inter bold title, italic subtitle, italic source line, unified `_calloutChrome` wrapper, callout text placed between subtitle and chart body).
2. Added a callout quality contract to `.claude/skills/tldr-charts/SKILL.md` — 60–240 chars, cite ≥1 number, reference ≥1 pipeline-tracked artifact, zero banned editorial words, fail-loud on violation.
3. Added per-callout checks to `tools/validate_briefing_schema.py` — 5-rule check function applied at every tier (top-level `insightCharts`, per-province, per-industry, `national.chart_callout`, `global[i].chart_callout`).
4. Locked the invariant in `CLAUDE.md` "Pipeline Invariants" section.
5. Updated the frontend to read canonical `ch.callout` with legacy fallback to `ch.reasoning` / `chartSpec.context`.

Commits landed on `main`: `fd25f2c`, `f35dae0`, `0c906b8`, `bda6e9e`.
Validator baseline on `docs/data/briefing_latest.json`: **788 checks · 706 PASS · 82 FAIL** — all 82 are callout-contract violations on the CURRENT edition, expected to resolve after Phase A re-run below.

## Project facts (do not re-derive)
- Root: `C:\Users\walte\OneDrive\Desktop\AI newsletter`
- Pipeline writes SQLite `dashboard.db` → `docs/data/*.json` → GitHub Pages.
- Weekly Monday 5:30 AM ET + daily midnight ET runs. **Daily run CLOBBERS briefing JSON unless `dashboard_state.newsletter_latest` DB row is also updated** (DB-sync invariant).
- Model stack: Claude Code subscription agents (Opus = writing/reasoning, Sonnet = extraction, Haiku ONLY for `tldr-assembler`). Groq Llama 3.3 70B is fallback classifier. NIM Nemotron for L6. Tavily for targeted enrichment only (1,000 credits/mo free tier). No Anthropic API unless `REASONING_AGENT_MODE=api` is set. No Gemini Pro, no Perplexity, no GDELT, no Ollama/Qwen.
- Editorial policy: factual reporting only. Banned words (validator hard-fails): `welcome`, `concerning`, `worrying`, `promising`, `encouraging`, `unfortunately`, `hopefully`, `bullish`, `bearish`, `headwind`, `tailwind`, `thrilled`, `feared`, `hoped`, `should`, `must`.
- Pipeline invariants (from CLAUDE.md): ADDITIVE ONLY, URL hard gate, evidence merge never loses URLs, government source bypass, dollar-value bypass, 4-week lookback, status never regresses, confidence 0.0–1.0, callout quality contract.
- Local preview: `python -m http.server 8765` from `docs/`. URL `http://localhost:8765/`.

## Forbidden (strict, session-wide)
- Do NOT touch `docs/demo/`.
- Do NOT force-push; do NOT skip hooks (`--no-verify`).
- Do NOT invoke any agent that consumes Tavily credits without explicit approval.
- Do NOT route Opus to extraction or Sonnet to writing.
- Do NOT edit database schema (`ALTER TABLE` etc.) without approval.
- Do NOT hand-patch `docs/data/*.json` with fabricated content — daily runs clobber it.
- Do NOT add fallback placeholder text like "Analysis pending" in skills or frontend.
- Do NOT weaken the callout quality contract to pass the validator.
- Do NOT introduce paid services or APIs.
- Do NOT remove keywords/feeds/queries from `config/*` (additive-only).
- Do NOT do mobile/responsive work — desktop web only.
- Do NOT editorialize in any regenerated content.
- Do NOT skip `validate_briefing_schema.py` after any pipeline/skill/schema edit.
- Do NOT skip the DB-sync update if briefing JSON changes.

---

## ▼ PHASE A — Finish callout remediation (do this first)

### A.1 — Run tldr-charts against current edition
Invoke the `tldr-charts` skill on `docs/data/briefing_latest.json`. The skill MUST produce:
- 2 top-level `insightCharts` with canonical `callout` field
- 2 per-province `insightCharts` on each of 13 provinces + 3 territories (28 total)
- 1 per-industry `insightCharts` on each of 5 goods + 15 services (20 total)
- `national.chart_callout`
- `global[i].chart_callout` on each of US, China, EU, UK

Every callout MUST satisfy the 5-rule contract (skill's self-check is the enforcement path — do NOT produce partial output).

### A.2 — Validate
Run: `python tools/validate_briefing_schema.py docs/data/briefing_latest.json`
Target: **0 FAIL**. Acceptable: ≤5 WARN.
If any FAIL remains: STOP, paste the failure list, do not proceed to A.3.

### A.3 — DB sync + export
If validator passes:
1. Update the `dashboard_state.newsletter_latest` row in `dashboard.db` to reference the regenerated briefing (use the existing update path — grep for `newsletter_latest` to find it).
2. Run the existing export tool (`tools/deploy_to_github.py` or `tools/export_dashboard.py` — whichever is the active path).
3. Re-run the validator on the exported `docs/data/briefing_latest.json` to confirm it survived export.

### A.4 — Hard-reload preview + commit
1. Start the local server if not running (`python -m http.server 8765` from `docs/`).
2. Load `http://localhost:8765/` and visually verify the 6 callout surfaces: TL;DR × 2, National Canada unemployment, National US / China / EU / UK.
3. Commit: `data(briefing): regenerate callouts to satisfy quality contract`.

**STOP at end of Phase A.** Report results, then wait for approval to begin Phase B.

---

## ▼ PHASE B — Full Newsletter Zero-Gap Hardening

Goal: make the next edition bulletproof. Every frontend field that should be populated MUST have a pipeline producer, a quality contract in the owning skill, and a matching check in `tools/validate_briefing_schema.py`. Zero silent degradation across weekly/daily runs.

Same discipline as the callout work: fix UP the stack (skill > pipeline > schema > frontend), never hand-patch JSON, add a validator check for every gap so it cannot silently return.

### B.1 — Full frontend-to-JSON field audit (NO EDITS)
Walk every render path in `docs/js/app.js` and map every field it reads. Build a machine-readable inventory `.audit/field_contract.tsv` with columns:

```
tab | render_function | line | field_path | expected_type | expected_non_empty | current_producer_skill | current_producer_line | validator_check | status
```

Cover:
- **TL;DR tab**: headline, narrative, `executive_summary`, `insightCharts` (×2) × `callout` + `context` + `reasoning` + `source`, policy developments, project pipeline section, watchlist, sources list, every metric tile.
- **National tab — Canada**: `national.analysis`, `national.sources`, `national.chart_callout`, Canada indicators (unemployment, CPI, GDP, BoC rate, housing starts, trade, building permits), the unemployment chart wrapper, key-indicators table, project pipeline table, enrichment cards.
- **National tab — each of US / China / EU / UK**: `global[i].analysis`, `global[i].sources`, `global[i].chart_callout`, `global[i].indicators.{gdp,cpi,rate,unemployment,tradeBalance}`, `global[i].indicatorMeta` per key, country chart.
- **Provinces tab × 13 + 3 territories**: `analysis`, `indicators`, `indicatorMeta`, `sources`, `insightCharts`, `marketContext`, `kpis`, `context`, projects table, story threads, policy items, project pipeline.
- **Industries tab × 20**: `analysis`, `indicators`, `indicatorMeta`, `kpis`, `insightCharts[0]`, `callout`, sector sub-table, movers cards, pipeline value, new-this-week, status-changes.
- **Markets tab**: commodities list (all 13), equities (TSX/S&P/DJIA/Nasdaq), fx, `yieldCurve` (7 tenors) + `yieldCurveLastYear`, `marketCommentary`, `commodity_commentary`, per-commodity narratives, WCS analysis.
- **Shared**: `discovery_stats`, `pipeline_value`, `project_count`, `new_projects`, `sources[]`, `week_of`, `edition`, `id`, `generated_at`, `updated_at`, `infographic_directives`, `word_cloud_topics`, `_all_verified_sources`, `citation_audit`, `unsplash_image_url`.

**STOP after producing `.audit/field_contract.tsv`.** Output a summary: `N fields audited, M gaps found, broken into [schema-missing / producer-missing / validator-missing / frontend-fallback-only]`.

### B.2 — Root-cause & fix-layer decision
For each gap row in the TSV, fill the `fix_layer` column (`schema / skill / pipeline / db / frontend`). Prefer UP the stack. Output a markdown summary grouped by layer with estimated impact.

**STOP.** Wait for approval on which gaps to fix in this session vs. defer.

### B.3 — Apply durable fixes, one commit per gap cluster
Cluster gaps by fix layer + affected skill (e.g., "`tldr-writer-provincial` missing `marketContext` on 4 provinces"). For each cluster:
1. Update the owning skill's `SKILL.md` — add required field to output contract, examples, self-check.
2. Add matching check to `tools/validate_briefing_schema.py` (hard-fail if missing, not warn).
3. Add one-line invariant entry to `CLAUDE.md` "Pipeline Invariants" section if the fix introduces a new non-negotiable.
4. Commit: `fix(<skill>): <cluster description> + schema check`.
5. Report ✅ checkpoint. **STOP. Ask before next cluster.**

Tight constraints per cluster:
- Every new required field gets a length bound, a banned-word check if it's prose, and a type check.
- Prose fields (analysis narratives, context strings, callouts, commentary) get banned-word enforcement.
- Numeric fields get range/presence checks.
- Array fields get count + per-item required-field checks.
- Never add a field the frontend doesn't actually use. If the frontend no longer uses a field, flag it in `.audit/field_contract_dead_fields.md` for user review before deleting anything.

### B.4 — Regenerate current edition
After all skill + validator updates merged:
1. List the minimum agent subset that must re-run to populate the new required fields on `briefing_latest.json`.
2. Confirm **zero Tavily credit impact, zero Anthropic API cost**.
3. **STOP. Wait for approval before running.**
4. On approval: run the agents sequentially (or parallel if independent per conductor config), validator after each.
5. Final full-run validator MUST show **0 FAIL**.
6. DB-sync: update `dashboard_state.newsletter_latest`.
7. Export via the active deploy path.
8. Hard-reload local preview, visual spot-check of a representative sample (TL;DR + 1 province + 1 industry + Markets + each of 4 globals).
9. Commit: `data(briefing): regenerate all newly-required fields for zero-gap edition`.

### B.5 — Regression armor
After 0-FAIL achieved:
1. Add a pre-ship check to `tldr-conductor` (or the conductor's config) that calls `validate_briefing_schema.py` and BLOCKS deploy on any FAIL. No silent ship.
2. Add a post-daily-run check that re-validates `briefing_latest.json` and alerts if the daily workflow clobbered required fields.
3. Update `.github/workflows/*.yml` (or equivalent) to fail the build if the validator returns non-zero.
4. Update `CLAUDE.md` with the new validator-as-gate invariant.
5. Commit: `feat(pipeline): validator is a deploy gate; daily run cannot clobber required fields`.

---

## Stop conditions (MANDATORY)
- End of A.2 validator run — if any FAIL, STOP.
- End of A.4 — STOP before Phase B approval.
- End of B.1 audit — STOP, wait for prioritization.
- End of B.2 fix-layer map — STOP, wait for session-scope approval.
- After EACH cluster commit in B.3 — STOP, ask before next.
- Before any agent run in B.4 — STOP, approval required, zero-cost estimate shown.
- If validator FAILs at ANY step after A.2 — STOP, paste failure list.
- If any edit would touch database schema (`ALTER TABLE`, new table) — STOP, approval required.

## Checkpoint format
After every step: `✅ [phase.step] — [what changed] — [commit hash if committed] — [validator X/N pass if run]`

## Context budget discipline
Pause at ~45% context usage and create a fresh handoff prompt for the next session before continuing. Do NOT let context fill to the compaction threshold mid-cluster.

---

➡️ **Begin with Phase A.1** — invoke `tldr-charts` against `briefing_latest.json`. Do not proceed past A.2 validator result without showing the FAIL count.
