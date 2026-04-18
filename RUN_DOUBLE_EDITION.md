# Double-Edition Catch-Up Run — 2026-04-18 Handoff

**Target:** One combined weekly briefing covering the two-week window
**Mar 31 – Apr 13, 2026** (weeks ending Apr 6 and Apr 13). Single run, not two.

**Why this doc exists:** the data pre-load (OEA + ISQ + DB refresh) was done in
a separate session; running the conductor in that same session would have
blown past the context budget mid-pipeline. Start a **fresh session** using
this plan and `/tldr-conductor`.

---

## 1. Pre-load state (already done, on disk in this commit)

- `dashboard.db`:
  - OEA backfill ran — 280 observations, 14 series, latest period **2025-10-01 (Q4 2025)**.
  - ISQ backfill ran — 373 observations, 33 series, latest periods range
    **2025-10-01 (quarterly GDP) → 2026-03-01 (labour) → 2026-02-01 (CPI, permits)**.
  - `dashboard_state.newsletter_latest` holds the rich Apr 11 briefing
    (801 KB). Do NOT overwrite with a stub during this run.
- `docs/data/indicators.json` (2.78 MB): includes OEA `on_*` + ISQ `qc_*`
  series in `history[]` for frontend charts.
- `docs/data/briefing_latest.json` (786 KB): currently the Apr 11 edition
  with full demo field parity. The double-edition run will replace this.

## 2. Model routing for this run (stick to CLAUDE.md)

| Phase | Skill | Model | Why |
|---|---|---|---|
| 1A/1B/1C | researchers | **Claude Code agent (subscription, $0)** | Research is long-form; subscription free |
| 2A/2B/2C | analysts | **Claude Code agent (subscription, $0)** | Synthesis of research + data |
| 3A/3B/3C/3D/3F | writers | **Claude Code agent (subscription, $0)** | Long-form writing, editorial judgment |
| 3-TRIAD | markets-triad | **Claude Code agent (subscription, $0)** | Three markets sections in one pass |
| 3.25 | visualizer | **Claude Code agent** | Chart selection is editorial |
| 3.5 | assembler | **Haiku 4.5** (only approved Haiku use) | Pure JSON merge, no editorial |
| 4 | charts | **Claude Code agent** | Chart selection per province/industry |
| 5 | auditor | **Claude Code agent** | Adversarial review needs judgment |
| 6 | fixer | **Claude Code agent** (only if auditor returns non-PASS) | Conditional — skip if auditor PASSes |
| 7 | discovery | **Claude Code agent (subscription, $0)** | Parallel with auditor |

API fallback (for GitHub Actions environments where `claude` CLI is absent):
set `REASONING_AGENT_MODE=api`, `WRITING_AGENT_MODE=api`, `PROVINCE_AGENT_MODE=api`.
Local runs should leave those unset — Claude Code agents on your subscription
cost $0 per call.

## 3. Phases to skip this run

Data is already fresh from the pre-load. Skip:

- **Phase 0 (tldr-data-refresh):** indicators.json was regenerated post-OEA/ISQ
  backfill. Skip. If markets data looks stale in the TL;DR tab after ship,
  run just this skill standalone as a follow-up.
- **Phase 0.5 (tldr-data-gap):** The gap audit from earlier in the session
  (`docs/_tmp_data_gap_audit.md`) is the authoritative baseline. Rerun only
  if Phase 5 auditor flags specific gaps.

Start the conductor at **Phase 1 (research)**.

## 4. Double-edition framing — instruct researchers explicitly

The default researcher skills assume "this week." For a two-week run, add
these lines to the researcher dispatch context:

> This is a **double-edition catch-up** covering Mar 31 – Apr 13, 2026
> (two consecutive Monday weeks). Research the full two-week window, not one
> week. Explicitly call out what changed between week 1 (Mar 31 – Apr 6) and
> week 2 (Apr 7 – Apr 13) where the movement was material. Treat the
> Apr 10 OEA Q4 2025 release and the Apr 10 StatCan LFS (Quebec cross-reads
> via ISQ-equivalent tables 14-10-0287/18-10-0004) as the two highest-signal
> releases of the window.

Writers inherit this framing from dossiers — no additional instruction needed
in Phase 3.

## 5. Prompt-engineering levers (use these to avoid blowing up usage)

Apply these in the conductor's subagent dispatch:

1. **Prompt caching.** If any skill falls back to the Anthropic API, the
   `system` array must end with `{"type": "text", "text": <SKILL.md>, "cache_control": {"type": "ephemeral"}}`.
   First call caches (5-min TTL); subsequent calls within the run hit cache
   at ~90% discount. Biggest wins: researcher-provincial (13 provinces, same
   skill, 13 cache hits) and tldr-writer-provincial (also 13 hits).

2. **Input pruning.** Don't pass the full analyst dossier to every writer.
   Writers need only their own section:
   - `tldr-writer-provincial` reads `dossier_provinces.json` only (not macro
     or industries).
   - `tldr-writer-goods` / `tldr-writer-services` read `dossier_industries.json`
     filtered to their NAICS bucket.
   - `tldr-writer-macro` reads `dossier_macro.json` only.
   The assembler merges at the end.

3. **Parallel dispatch where possible.** Phase 1 (3 agents), Phase 2 (3),
   Phase 3 (6), Phase 5 (2) all fan out. The conductor already handles this;
   do not serialize.

4. **Skip Phase 6 on PASS.** The conditional already exists; just make sure
   the conductor doesn't dispatch the fixer when auditor returns PASS.

5. **Do NOT run the project track this time.** That's 29 extra agent
   dispatches and the project database doesn't need to move for a briefing-only
   catch-up. Add `--briefing-only` flag to the conductor dispatch if the skill
   supports it; otherwise instruct the conductor in the first message:
   "Run briefing track only. Skip Phase P0/P1/P2."

## 6. Expected agent count

| Phase | Agents |
|---|---|
| 1 | 3 (macro, provincial, sector) |
| 2 | 3 (macro, provincial, industry analysts) |
| 3 | 6 (macro, provincial, goods, services, market-commentary, markets-triad) |
| 3.25 | 1 (visualizer) |
| 3.5 | 1 (assembler) |
| 4 | 1 (charts) |
| 5 | 2 parallel (auditor + discovery) |
| 6 | 0 or 1 (conditional on auditor) |
| **Total** | **17 – 18** agent calls |

Down from ~50 if the full pipeline ran with all phases and the project track.
With prompt caching, effective token cost is roughly 6–8 uncached-equivalent
calls across the run.

## 7. Ship checklist (do in this order at the end of the pipeline)

The conductor already automates most of this; just confirm:

1. [ ] `briefing_YYYY-MM-DD.json` produced by Phase 3.5 assembler.
2. [ ] Auditor returned PASS or PASS WITH WARNINGS.
3. [ ] Copy file to `briefing_latest.json` AND write the same JSON to
       `dashboard_state.newsletter_latest` via:
       ```python
       import sqlite3, json, datetime
       txt = open('docs/data/briefing_latest.json').read()
       c = sqlite3.connect('dashboard.db')
       c.execute("INSERT INTO dashboard_state (key,value,updated_at) VALUES ('newsletter_latest',?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                 (txt, datetime.datetime.now(datetime.UTC).isoformat()))
       c.commit()
       ```
       **Both the file AND the DB row must be written.** If the DB row is
       skipped, the next daily workflow run will overwrite the briefing with
       the old stub (this is exactly what happened Apr 12 – Apr 18).
4. [ ] `git add docs/data/briefing_latest.json docs/data/briefing_YYYY-MM-DD.json docs/data/briefing_archive.json dashboard.db`
5. [ ] Commit + push to `main`.
6. [ ] Verify `https://waltaaaa.github.io/ai-newsletter/data/briefing_latest.json`
       serves the new edition (size >500 KB, correct `week_of`).

## 8. Rollback tags available

- `backup-pre-data-fix-2026-04-18` — HEAD just before the Apr 11 restore.
- `demo-reference-2026-04-12` — frozen demo snapshot (commit `2a28c82`).
- `backup-2026-04-10` — last known-good pre-ship newsletter.
- This commit will be the next rollback anchor for the double-edition run.

## 9. Known leftovers (not blocking this run)

- Editorial-rules duplication across 8 writer skills (~60 KB per run).
  Refactor after this ship: extract to a shared
  `.claude/skills/_shared/editorial_rules.md` and have each writer
  `{{ include }}` or reference it.
- `tldr-data-gap` (963 lines), `tldr-visualizer` (856 lines),
  `tldr-assembler` (845 lines), `tldr-conductor` (815 lines) are the biggest
  prompts. Each has room to compress by 30–40% without changing behavior.
  Defer to a focused refactor session.
