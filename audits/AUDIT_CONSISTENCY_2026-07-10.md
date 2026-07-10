# Consistency Audit — Weekly Newsletter Output vs Demo Reference
Date: 2026-07-10. Repo: /home/user/ai-newsletter

## 0. The demo reference (where "how it SHOULD look" lives)

1. **Design spec (authoritative, still in repo):** `/home/user/ai-newsletter/APPROVED_TEMPLATES.md` plus the per-tab files `APPROVED_TEMPLATE_MARKETS.md`, `APPROVED_TEMPLATE_INDUSTRIES.md`, `APPROVED_TEMPLATE_PROJECTS.md`, `APPROVED_TEMPLATE_CALENDAR.md`, `APPROVED_TEMPLATE_EXPLORER.md`. Every tab is "locked" with exact section lists, field names, and counts (e.g. Markets: 9 equity pills / 7 FX pairs / 5 sections — APPROVED_TEMPLATES.md:327-337).
2. **Hand-tuned demo data snapshot (deleted from working tree, recoverable from git):** `docs/demo/` — added in commit `2a28c82` ("Add docs/demo snapshot of current prototype", 2026-04-12), removed in `95fdc1a` (2026-06-12 F14 cleanup). Recover with `git show 95fdc1a^:docs/demo/data/briefing_latest.json` (week_of 2026-03-24). `PATCH_LOG_SCHEMA_PARITY.md:5,13` explicitly calls this demo "the gold standard … hand-tuned to match the frontend; the pipeline was never systematically validated against frontend data paths."
3. `preview-patch-1.3/` is NOT the demo — it contains only a capital-map prototype and a gap-analysis doc. `archive/Index.html` is a legacy Firebase-era frontend, superseded.

---

## 1. Edition-to-edition schema drift (docs/data/briefing_*.json)

Across the 12 dated editions (2026-03-14 → 2026-06-22), **only 4 of 53 observed top-level keys are present in every edition**. Presence matrix highlights (X = present, per sorted date order 03-14…06-22):

| Key | Pattern | Notes |
|---|---|---|
| `insightCharts` | `....XX.XXXXX` | absent 03-14→03-30 and **04-20** |
| `marketCommentary` | `.....X.XXX..` | absent in **06-15 and 06-22 dated files** (present in briefing_latest) |
| `commodity_commentary` | `.....XXXXXXX` | born 04-18 |
| `yieldCurveCommentary` | `.......XXXXX` | born 05-15 |
| `wcs_analysis` | `.....XXXXXXX` | born 04-18 |
| `bocRate` | `.....X.XXX.X`-ish | intermittent |
| `_visualization_insertions` | `.....X.XXX.X` | **absent in 06-15**, present 06-22 — editorial SVG charts appear/disappear week to week |
| `watchlist` count | 15→20→21→19→**0 (04-20)**→19→21→23→18→**9 (06-22)** | no min-count gate |
| `charts`, `citation_audit` | 03-15→04-18 only | legacy keys silently dropped |
| `goods_industries`/`services_industries`/`fx` (snake_case) | **04-20 only** | one edition used a different casing convention entirely |
| `unsplash_image_url` | 03-31 onward | carried forward by assembler "preserve structure from latest" rule though the approved templates removed Unsplash banners |

Per-province object keys: **zero keys are stable across all 12 editions.** `consumerPulse`, `labourDeepDive`, `marketContext`, `sectorHighlights`, `tradeExposure`, `watchlistItems` only exist from 03-31 onward; `indicatorSources` disappears in 06-22; and the **06-15 edition uniquely leaked raw analyst-dossier fields into published provinces** (`news_stories`, `key_facts`, `story_threads`, `policy_items`, `cross_references` — shapes defined in `.claude/skills/tldr-analyst-provincial/SKILL.md:188-384`, never meant to ship).

Global region objects: `chart_callout` born 04-18; `insightCharts` born 06-08 with partial coverage (06-08: 1/4 regions, 06-15/06-22: 4/4) — so the four global sub-tab charts flip between narrative-driven and hardcoded `GLOBAL_CHART_CFG` fallback (docs/js/app.js:2342-2378) depending on edition. `emoji` present 03-15→05-15 then dropped (approved template says "No flag emojis" — APPROVED_TEMPLATES.md:140).

Industry charts: 04-20 shipped `goodsIndustries` with **0/5 insightCharts** (all other editions 5/5). Validator treats per-industry chart presence as WARN only (tools/validate_briefing_schema.py:2511).

**Consequence:** the append-only `briefing_archive.json` dropdown (12 entries, all resolvable) permanently serves editions that render with entire sections missing — the 04-20 edition has no charts, no watchlist, snake_case industry keys the frontend doesn't read.

### 1b. briefing_latest.json diverges from its own dated archive copy
`briefing_latest.json` (week_of 2026-06-22) carries 4 keys the dated `briefing_2026-06-22.json` lacks: `bocRate`, `marketCommentary`, `word_count`, `yieldCurveLastYear`. Cause: commit `8f054bc` ("daily: indicators refresh 2026-06-24") mutates only `briefing_latest.json`; the dated file is written once at assembly (`.claude/skills/tldr-assembler/SKILL.md:961-1061` — "Write dated file only … briefing_latest.json is managed by deployment") and never re-synced. Post-publication fixes and daily enrichment therefore never reach the previous-editions dropdown → the same week renders differently live vs from the archive.

---

## 2. Demo (gold standard) vs live pipeline output

Comparing `git show 95fdc1a^:docs/demo/data/briefing_latest.json` against current `docs/data/briefing_latest.json`:

- Demo-only top-level: `charts`, `citation_audit`, `commoditiesFull`, `equities`, `fxYields`, `marketCommentaryCallout`, `wcsAnalysis`.
- Live-only: `_visualization_insertions`, `commodity_commentary`, `wcs_analysis`, `yieldCurveCommentary`, `word_count`, `yieldCurveLastYear`.
- `financialMarkets` object: demo = `{bocRate, bocRateChange, commentary, equityNarrative, fx, fxNarrative, indices, summary, yieldCurve, yieldNarrative}`; live = `{boc_rate, callout, fed_rate, fx, fx_commentary, indices, pairs, rate_differential_bp, summary}`. camelCase→snake_case drift, and three narrative fields renamed/moved.
- Counts vs locked Markets template (APPROVED_TEMPLATES.md:332): demo 9 indices / 7 FX; **live emits 4 indices / 6 FX**. Validator only requires `indices >= 4` (validate_briefing_schema.py:2011-2014), so the Markets tab shows less than half the approved pill set with a green validator.

### 2b. Orphaned narrative fields — written every week, never rendered (silent blanks)
| Pipeline writes | Frontend reads | Result |
|---|---|---|
| top-level `commodity_commentary` (assembler SKILL.md:459) | `fm.commodityNarrative \|\| fm.commodity_narrative \|\| D.commodityCommentary` (docs/js/app.js:5181-5182) | Agent 3I's 300-400-word commodity summary **never renders** |
| top-level `yieldCurveCommentary` (assembler SKILL.md:661) | `fm.yieldNarrative \|\| fm.yield_narrative` (app.js:5156) | Agent 3H's yield-curve narrative **never renders** |
| `financialMarkets.fx_commentary` (assembler SKILL.md:380,447) | nothing — no `fx_commentary`/`fxNarrative` read anywhere in app.js | FX narrative **never renders** |
| top-level `_visualization_insertions` (assembler SKILL.md:528; 4 inline SVGs with insertion points in current edition) | nothing — `grep insertion\|_visualization\|callout-box` in app.js: no consumer | **Entire Phase 3.25 visualizer output is dead weight**; also intermittent between editions (§1) |
| top-level `word_cloud_topics` | nothing (renderTLDRWordCloud removed in F12 cleanup, commit 5d1e92d) | orphaned |
| `infographic_directives` | nothing in app.js | orphaned, carried forward edition to edition by assembler rule 5 (SKILL.md:1059) |

These are exactly the class of "42-gap" name mismatches documented in `PATCH_LOG_SCHEMA_PARITY.md` (2026-04-19) — the class was patched for commodities/indices/metrics but has re-accumulated on the Markets narrative fields (the market writer agents 3F-3I were added AFTER the parity patch).

---

## 3. Agent/skill under-constraint (structural variability between runs)

- **tldr-writer-macro** (`.claude/skills/tldr-writer-macro/SKILL.md`): `watchlist` is a pass-through of `dossier.watchlist_package` (L138) with **no minimum item count** → 9 vs 23 events between editions; TL;DR "Looking Ahead" and Calendar merge shrink/grow arbitrarily. `headline`, `executive_summary` have no length/shape gates in the skill's self-check (only national/global analysis ≥400 chars, L172-203).
- **tldr-assembler** (`SKILL.md:52,1071`): `briefing_visualizations.json` is "Optional — graceful degradation" → editorial SVG presence is nondeterministic per run (§1). Rule 5 (L1059) copies unknown structural fields forward from the previous `briefing_latest.json`, so stale fields (`unsplash_image_url`, `infographic_directives`) propagate by inheritance rather than regeneration, and a field dropped once disappears from all future editions.
- **tldr-assembler alias emission:** `bocRate`/`marketCommentary` top-level aliases are validator WARN-only (validate_briefing_schema.py:2631-2636) and were absent in the 06-22 dated file; AUDIT_LOG B5/M3 flagged this, fixed by hand in latest only.
- **tldr-charts** is now well-constrained (48-chart hard gate, fail-loud callouts — SKILL.md:23-32,313) — the 04-18 "empty industry charts" regression is fixed at the source, BUT the *validator* backstop for industry charts is still WARN-only (validate_briefing_schema.py:2511), and global-region `insightCharts` (1 per region, SKILL.md:207-221) has no validator count gate at all — a partial charts run deploys.
- **tldr-writer-provincial / analyst-provincial:** the 06-15 dossier-field leak (§1) shows the writer/assembler does not whitelist province output keys; validator does not reject unknown keys, so shape drift ships.
- **Markets writers 3F-3I vs assembler vs frontend** have three different names for the same narrative (e.g. `yield_commentary` in fragment → `yieldCurveCommentary` top-level → `yieldNarrative` expected by app.js). No contract test covers fragment→assembled→rendered naming end-to-end.

---

## 4. Validator gaps (tools/validate_briefing_schema.py) vs the demo look

What it enforces well: top-level presence (L1920-1931), counts for provinces/global/insightCharts/goods/services (L1955-1963), freshness (L1939-1950), analysis prose floors + banned words, province narrative floors (L2308-2331), callout contract (L2578-2627), external data files, archive shrink guard (L1449+), market fact-checking.

What it does NOT enforce (all observed to vary between editions):
1. **`marketCommentary` / `bocRate` / `pipeline_value` / `project_count`** — WARN-only "aliases" (L2631-2636). Market Commentary section silently absent when missing because `_buildMktCommentary` returns `''` (app.js:5024-5026), unless `fm.summary` covers it.
2. **`commodity_commentary`, `yieldCurveCommentary`, `fx_commentary`** — not checked at all, and not readable by the frontend anyway (§2b). Validator's own frontend-contract comments (L2043+) were never extended to the Markets narrative reads at app.js:5156/5181.
3. **Watchlist minimum count** — presence only; 0-item and 9-item editions both pass.
4. **Equity/FX pill counts vs locked template** — `indices >= 4` (should be 9 per MKT-20), FX has no count check at all.
5. **Per-industry insightCharts presence** — WARN (L2511); global-region insightCharts — no count/presence check (only `chart_callout` when analysis exists, L2621-2626).
6. **`executive_summary` / `headline`** — presence only; no length, no lead-sentence/`<strong>` structure the TL;DR template expects (APPROVED_TEMPLATES.md:84-89).
7. **Unknown-key rejection** — extra/leaked keys (06-15 dossier fields, 04-20 snake_case duplicates) pass silently.
8. **Dated-file ↔ latest parity** — validator validates one file; nothing asserts `briefing_<week_of>.json` deep-equals `briefing_latest.json` at deploy (§1b).
9. **`_visualization_insertions`** — no check (shape or presence), consistent with it having no consumer.
10. **`yieldCurveLastYear`** — WARN only (L1988); year-ago comparison line appears/disappears between editions (all-or-nothing build, DEEP_DIAG M2, phases/data_collection.py:1850).

---

## 5. Frontend silent-degradation paths (docs/js/app.js)

- `renderAgentInsightChart` returns `''`/no-op when spec lacks `dataKeys` (app.js:1764,1776) — chart silently vanishes (documented invariant in CLAUDE.md).
- Province insight charts filtered to specs with dataKeys, else legacy single `insightChart`, else nothing (app.js:3559-3561).
- Global sub-tab charts: briefing spec → fallback to hardcoded `GLOBAL_CHART_CFG` → "No data" placeholder (app.js:2342-2393) — three different visual outcomes depending on edition content.
- `_buildMktCommentary` returns `''` when no summary/commentary → whole Market Commentary section-block absent (app.js:5024-5026).
- Commodity/yield/FX narratives: read keys the pipeline never writes (app.js:5156,5181) → permanently blank (§2b).
- Equity per-index commentary: empty string when `it.commentary` absent (app.js:4986-4993) — pre-triad editions have none.
- Sector Signals section hidden entirely when `sectorHighlights` < 20 chars (APPROVED_TEMPLATES.md:280; app.js:3476-3482); Labour Market Detail only if `labourDeepDive` present (app.js:3485-3490) → pre-03-31 archive editions lose 4+ sections quietly.
- National/global analysis fallback text "available after next pipeline run" (app.js:2455,2665) — visible degradation for legacy archive editions.
- TL;DR callouts: if `insightCharts` empty falls back to a discovery-stats cross-reference box, or nothing (app.js:732-752).
- WCS block renders only when `wcs_analysis.narrative` (dict) or `wcsAnalysis` (HTML) present (app.js:5184-5205) — absent pre-04-18.
- Calendar: briefing watchlist non-empty ⇒ events.json never loaded (F8 in AUDIT_LOG — fixed 2026-06-12 per fix dispatch, commit cc80c28/e854102) — verify.

---

## 6. Known issues from prior audits — fixed vs still open

**Fixed (per AUDIT_LOG_2026-06-12.md "Fix dispatch" + remediation pass — don't re-litigate):**
F1 (val/value pills), F3 (hero chart dataSource), F4 (callout vs reasoning read), F5, F7/C3 (province filter), F8/C6 (impact mapping), F9, F10, F11, F13; D1 (provincial timeseries export by full name), D2 (canola), D4 (WCS ticker), D5/D6 (run-date stamping), D7 (preserve-merge), D9, D10, D11, D13, D14; C2 (commodity prints), C7 (BoC dates), C8 (cross-tab totals), F6 (China chart via global insightCharts), F12, F14 (demo/backup pruning), F15/B1 (doc drift).

**Still open / structural (relevant to inconsistency):**
- DEEP_DIAG C1/C2 (L7 rerank fail-open + Phase 3 timeout backlog): fixes committed but were untested in production as of 2026-06-11 — recall variance between editions feeds content variance.
- DEEP_DIAG C3 (jobs.json always empty), C4 (procurement always empty), C5/C6 (municipal/institutional tiers 0), H5 (policy tracker drops 93%), H10 (Tier 12 off): briefing "signal" sections are built on inputs that are silently dead → week-to-week signal sections vary by which tier happens to work, and empty-state copy appears (e.g. app.js:1131 policy empty-state).
- DEEP_DIAG H1 (no failure notification), H7 (run counters never wired), H8 (Phases 1-4 failures still deploy, `_analysis_incomplete`/partial runs like 04-20 shipped) — **H8 is the direct enabler of the 04-20 malformed edition living in the archive**.
- DEEP_DIAG H9 / AUDIT B2/B3/C9 partial: stale/short chart series shrink the chart agent's palette differently each week.
- DEEP_DIAG M1 (non-atomic export), M2 (yieldCurveLastYear all-or-nothing) — open.
- AUDIT F2: ~34 IND_KEY_INDICATORS keys absent from exports (root cause D1 partially fixed; balance open pending live run).
- D8 (QC ISQ staleness) — deferred.

---

## 7. Ranked remediation targets

1. Enforce a machine-readable field contract (single JSON schema) shared by assembler + validator + a frontend-read manifest; reject unknown keys and require the Markets narrative fields under the names app.js actually reads.
2. Fix the three Markets narrative name mismatches (either app.js reads `commodity_commentary`/`yieldCurveCommentary`/`fx_commentary`, or assembler writes `fm.commodityNarrative`/`fm.yieldNarrative`/`fm.fxNarrative`).
3. Render or remove `_visualization_insertions`; make visualizer presence mandatory-or-never rather than optional.
4. Re-sync dated archive file whenever briefing_latest is mutated (daily refresh, fixer, manual edits); add a parity check at deploy.
5. Upgrade WARN→FAIL: marketCommentary/bocRate aliases, industry chart presence, global chart count, watchlist min count (e.g. ≥8), equity/FX pill counts per locked template.
6. Backfill or gracefully version legacy archive editions (schema_version field + renderer awareness), or regenerate 04-20.
7. Land the dead-tier fixes (jobs/procurement/municipal/institutional) or drop their sections deterministically so empty-state vs populated isn't a coin flip.
