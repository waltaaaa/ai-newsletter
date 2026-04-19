# Kickoff — Double-Edition Catch-Up Run

**Scope:** one briefing covering the two-week window **Mar 31 – Apr 13, 2026**
(weeks ending Apr 6 and Apr 13). Not two editions — one combined release.

**Data pre-load is done** (commit `3bd216b` on main):

- OEA Q4 2025 backfilled (14 series, latest period 2025-10-01)
- ISQ refreshed (33 series, QC labour through Mar 2026, CPI through Feb 2026)
- `indicators.json` regenerated
- `briefing_latest.json` and `dashboard_state.newsletter_latest` hold the rich
  Apr 11 edition as the fallback baseline

Read `RUN_DOUBLE_EDITION.md` in the repo root **before** doing anything. It
contains: model routing, phases to skip, prompt-caching rules, ship checklist
(including the DB sync step that prevents daily-workflow regression).

---

## Step 1 — Read RUN_DOUBLE_EDITION.md end to end.

## Step 2 — A/B test the input-pruning optimization before dispatching writers.

This validates that passing each writer only its own dossier section does not
degrade quality vs the current behavior (writer reads full dossier).

```bash
python tools/ab_stage_pruning_test.py --province ON
```

Then in this session:

1. Invoke `tldr-writer-provincial` once with the **full** dossier
   (`docs/data/_abtest/dossier_provinces_full.json`), saving output to
   `docs/data/_abtest/briefing_A.json`.
2. Invoke `tldr-writer-provincial` once with the **pruned** dossier
   (`docs/data/_abtest/dossier_provinces_pruned.json`), saving output to
   `docs/data/_abtest/briefing_B.json`.
3. Compare:

```bash
python tools/diff_against_baseline.py \
  --baseline docs/data/_abtest/briefing_A.json \
  --candidate docs/data/_abtest/briefing_B.json \
  --tolerance 0.05
```

**If diff passes (exits 0):** adopt input pruning for Phase 3.
**If diff fails:** pass full dossiers to every writer in Phase 3.

## Step 3 — Invoke `/tldr-conductor` with this brief:

> Double-edition catch-up covering Mar 31 – Apr 13, 2026. Briefing track only —
> skip project track (P0/P1/P2). Skip Phase 0 and Phase 0.5 (data pre-loaded
> in commit 3bd216b). Start at Phase 1 (research).
>
> Instruct researchers explicitly that this covers a **two-week** window:
> Mar 31 – Apr 6 (week 1) and Apr 7 – Apr 13 (week 2). Call out what changed
> between week 1 and week 2 where the movement was material. Treat the Apr 10
> OEA Q4 2025 release and the Apr 10 StatCan LFS print as the two
> highest-signal releases.
>
> Model routing: all writers/researchers/analysts on Claude Code agents
> (subscription, $0). Only the assembler may use Haiku 4.5. No Opus fallback
> to API unless claude CLI is unavailable.
>
> Apply prompt caching (`cache_control: ephemeral`) on any skill that falls
> back to the Anthropic API — especially `tldr-researcher-provincial` and
> `tldr-writer-provincial` (13 invocations each, big cache win).
>
> Writer input pruning: **[ADOPT or SKIP per step 2 result]**.
>
> Hard gate on Phase 5 auditor verdict. Do not bypass a non-PASS verdict.

## Step 4 — Baseline diff before deploy.

After Phase 3.5 assembler produces `briefing_YYYY-MM-DD.json`, and *before*
deploy:

```bash
python tools/diff_against_baseline.py \
  --baseline docs/data/briefing_2026-04-11.json \
  --candidate docs/data/briefing_YYYY-MM-DD.json \
  --tolerance 0.10
```

If it fails, identify which metric regressed and rerun just the affected
phase. **Do not ship on a FAIL.**

## Step 5 — Ship per `RUN_DOUBLE_EDITION.md` section 7.

**Critical:** write the final briefing to **both**
`docs/data/briefing_latest.json` AND `dashboard_state.newsletter_latest` in
the DB. Skipping the DB write is what caused the Apr 12–18 stub regression.

```python
import sqlite3, json, datetime
txt = open('docs/data/briefing_latest.json').read()
c = sqlite3.connect('dashboard.db')
c.execute(
    "INSERT INTO dashboard_state (key, value, updated_at) VALUES ('newsletter_latest', ?, ?) "
    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
    (txt, datetime.datetime.now(datetime.UTC).isoformat())
)
c.commit()
```

## Step 6 — Push to main. Verify the live URL.

```bash
git add docs/data/briefing_latest.json docs/data/briefing_YYYY-MM-DD.json \
        docs/data/briefing_archive.json dashboard.db
git commit -m "Ship double edition — Mar 31 to Apr 13, 2026"
git push origin main
```

Verify `https://waltaaaa.github.io/ai-newsletter/data/briefing_latest.json`
serves the new edition (size >500 KB, correct `week_of`) within 1–2 minutes
of the push.

---

## Rollback anchors

- `backup-pre-data-fix-2026-04-18` — HEAD just before the Apr 18 restore.
- `demo-reference-2026-04-12` — frozen demo snapshot (commit `2a28c82`).
- `backup-2026-04-10` — last known-good pre-ship newsletter.
- `docs/demo/` is preserved as the live fallback at `/ai-newsletter/demo/`.
