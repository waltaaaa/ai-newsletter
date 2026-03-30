---
name: tldr-pipeline
description: >
  Master orchestrator for "The Lagging Indicator" weekly briefing pipeline. Runs all agents in
  sequence (0 through 6) with a single command, handling dependencies and producing a complete,
  publication-ready briefing. Use this skill whenever the user wants to run the full pipeline,
  produce the weekly briefing end-to-end, execute all agents, or automate the Monday run.
  Trigger on phrases like "run the pipeline", "run all agents", "full pipeline", "weekly run",
  "Monday briefing", "produce the briefing", "tldr pipeline", "run everything", "execute pipeline",
  "briefing pipeline", "generate this week's briefing", or any request to go from raw data to
  published briefing in one shot.
---

# TL;DR Pipeline Orchestrator — Master Controller

You are the orchestrator for "The Lagging Indicator" weekly Canadian economic intelligence briefing. You run all 7 agents in strict sequence, pass outputs between them, handle errors, and deliver a publication-ready briefing.

## Pipeline Architecture

```
Agent 0 (Data Refresh)  →  fresh data files
Agent 1 (Researcher)    →  docs/data/research_brief.md
Agent 2 (Analyst)       →  docs/data/analyst_dossier.json
Agent 3 (Writer)        →  docs/data/briefing_YYYY-MM-DD.json
Agent 4 (Auditor)       →  docs/data/audit_report.md
Agent 5 (Fixer)         →  updated briefing (if audit fails)
Agent 6 (Discovery)     →  docs/data/discovery_batch.json (independent)
```

Each agent depends on the previous agent's output. Run them strictly in order.

---

## Before You Start

1. **Read `CLAUDE.md`** in the project root for editorial policy and system constraints
2. **Confirm the data folder is accessible** at `docs/data/`
3. **Note today's date** — this becomes the `week_of` for the briefing

---

## Execution Protocol

### Agent 0 — Data Refresh

**Skill:** `.claude/skills/tldr-data-refresh/SKILL.md`

Read and execute the skill. This agent:
- Uses WebSearch to update indicators, markets, commodities, yields, and provincial data
- Updates `docs/data/briefing_latest.json`, `docs/data/indicators.json`, and `docs/data/data_snapshots.json`
- Produces a refresh report

**When to skip:** If the user says "data refresh already ran" or provides today's data state, skip to Agent 1.

**Status update after completion:**
> Agent 0 (Data Refresh) complete. [N] indicators updated, [N] market prices refreshed. Moving to Agent 1.

---

### Agent 1 — Researcher

**Skill:** `.claude/skills/tldr-researcher/SKILL.md`

Read and execute the skill. This agent:
- Reads all data files for audit
- Runs ~95 WebSearches across 9 waves (national macro, trade, provincial, sector, NAICS GDP industries, markets, consumer, projects, policy, global)
- Produces `docs/data/research_brief.md` (3,000-5,000 words)

**Critical checks before moving on:**
- `research_brief.md` exists and is >2,000 words
- All 13 provinces have dispatches
- All 20 NAICS industries have dispatches
- Master source registry has 30+ URLs

**Status update after completion:**
> Agent 1 (Researcher) complete. [N] searches completed, [N]-word research brief with [N] sources. Moving to Agent 2.

---

### Agent 2 — Analyst

**Skill:** `.claude/skills/tldr-analyst/SKILL.md`

Read and execute the skill. This agent:
- Reads `research_brief.md` + all pipeline data files
- Cross-references indicators with projects, stories with data, policy with sectors
- Builds packages for all 20 NAICS industries, 13 provinces, 4 global regions
- Produces `docs/data/analyst_dossier.json`

**Critical checks before moving on:**
- `analyst_dossier.json` exists and is valid JSON
- Contains exactly 5 goods industries and 15 services industries
- Contains 13 province packages
- Contains charts, infographic_directives, sources_registry
- Contains headline and key_indicators

**Status update after completion:**
> Agent 2 (Analyst) complete. Dossier built with [N] industries, [N] provinces, [N] sources. Moving to Agent 3.

---

### Agent 3 — Writer

**Skill:** `.claude/skills/tldr-writer/SKILL.md`

Read and execute the skill. This agent:
- Reads `analyst_dossier.json` and last week's `briefing_latest.json`
- Writes narrative HTML for all sections (executive summary, national, 20 industries, 13 provinces, 4 global regions, consumer pulse)
- Assembles complete JSON with ALL 31 required fields
- Saves to `docs/data/briefing_YYYY-MM-DD.json` (dated file, does NOT overwrite briefing_latest.json)
- Updates `docs/data/briefing_archive.json`

**Critical checks before moving on:**
- Dated briefing file exists and is valid JSON
- Contains exactly 5 goodsIndustries and 15 servicesIndustries
- Contains exactly 13 provinces
- Contains charts, id, infographic_directives, citation_audit, _all_verified_sources
- `briefing_latest.json` is NOT overwritten (preserved for comparison)

**Status update after completion:**
> Agent 3 (Writer) complete. Briefing written with [N] words, [N] industries, [N] provinces, [N] citations. Moving to Agent 4.

---

### Agent 4 — Auditor

**Skill:** `.claude/skills/tldr-auditor/SKILL.md`

Read and execute the skill. This agent runs 10 adversarial tests:
1. Number Verification — all metrics match authoritative data
2. Citation Integrity — all `<sup>N</sup>` refs have matching sources
3. Editorial Compliance — no banned words
4. Logic & Consistency — no internal contradictions
5. Completeness — all 5+15 industries, 13 provinces, structural fields
6. Freshness — <50% similarity to last week
7. Schema Compliance — correct types and structures
8. Cross-Agent Consistency — no information corruption
9. Comparative Sanity — word counts, plausibility
10. Security & Integrity — no PII, hallucinated URLs, prompt leakage

Produces `docs/data/audit_report.md`

**Branching logic:**
- **PASS** → Skip Agent 5, proceed to Agent 6
- **PASS WITH WARNINGS** → Run Agent 5 for non-blocking fixes, then Agent 6
- **FAIL** → Run Agent 5 (mandatory), re-audit if needed, then Agent 6

**Status update after completion:**
> Agent 4 (Auditor) complete. Verdict: [PASS/PASS WITH WARNINGS/FAIL]. [N] issues found. [Skipping Agent 5 / Moving to Agent 5].

---

### Agent 5 — Fixer (conditional)

**Skill:** `.claude/skills/tldr-fixer/SKILL.md`

**Only runs if the Auditor returns non-PASS verdict.**

Read and execute the skill. This agent:
- Reads `audit_report.md` for specific issues
- Makes targeted fixes (number corrections, editorial rewrites, missing sections, structural fields)
- Re-validates after each fix pass (up to 3 passes)
- Saves updated briefing to the same dated file

**Status update after completion:**
> Agent 5 (Fixer) complete. Fixed [N] issues in [N] passes. Re-validation: [PASS/still has issues].

---

### Agent 6 — Discovery (independent)

**Skill:** `.claude/skills/tldr-discovery/SKILL.md`

Read and execute the skill. This agent:
- Loads project database and maps coverage gaps
- Runs 48 targeted searches for thin sectors (telecom, forestry, environment, indigenous, defence, agriculture) and thin provinces (NS, SK, NL, MB, NU)
- Cross-references against existing database to dedup
- Produces `docs/data/discovery_batch.json`

**Status update after completion:**
> Agent 6 (Discovery) complete. Found [N] new projects across [N] sectors and [N] provinces. Saved to discovery_batch.json.

---

## Post-Pipeline: Publish

After all agents complete, present the results and ask for publication approval:

```
Pipeline Complete — Week of [DATE]

Files produced:
  - docs/data/research_brief.md (Agent 1)
  - docs/data/analyst_dossier.json (Agent 2)
  - docs/data/briefing_YYYY-MM-DD.json (Agent 3, fixed by Agent 5 if needed)
  - docs/data/audit_report.md (Agent 4)
  - docs/data/discovery_batch.json (Agent 6)

Briefing summary:
  - Headline: [headline]
  - Key indicators: [N] items
  - Industries: [N] goods + [N] services
  - Provinces: [N]
  - Sources: [N] citations
  - Word count: Exec [N], National [N], Industry [N]

Audit verdict: [verdict]
  - Issues found: [N]
  - Issues fixed: [N]

Discovery: [N] new projects found

The live dashboard still shows last week's briefing.
Would you like me to publish this edition to the live dashboard?
```

### Publishing (only after user approval):

```python
import json, shutil, os

dated_file = f'docs/data/briefing_{week_of}.json'
live_file = 'docs/data/briefing_latest.json'

# Back up current live file if not already backed up
if os.path.exists(live_file):
    current = json.load(open(live_file))
    old_week = current.get('week_of', 'unknown')
    backup = f'docs/data/briefing_{old_week}.json'
    if not os.path.exists(backup):
        shutil.copy2(live_file, backup)

# Publish
shutil.copy2(dated_file, live_file)
```

### Push to GitHub (only after publishing):

After `briefing_latest.json` has been updated, push to GitHub so GitHub Pages serves the new edition:

```bash
cd /path/to/project/root

# Stage all updated data files
git add docs/data/briefing_latest.json docs/data/briefing_*.json docs/data/research_brief.md docs/data/analyst_dossier.json docs/data/audit_report.md docs/data/discovery_batch.json docs/data/briefing_archive.json docs/data/indicators.json docs/data/data_snapshots.json docs/data/projects_all.json

# Commit with descriptive message
git commit -m "Weekly pipeline run: week ending $(date +%B\ %d,\ %Y)"

# Push to origin main (GitHub Pages deploys automatically)
git push origin main
```

**Status update after push:**
> Published and pushed to GitHub. The live dashboard at GitHub Pages will update within 1-2 minutes.

**If push fails:**
- Check `git status` for conflicts or uncommitted changes
- If there are upstream changes, run `git pull --rebase origin main` first, then push
- If authentication fails, note the error and ask the user to push manually
- Never force-push (`--force`) — always resolve conflicts properly

---

## Error Handling

If any agent fails:

1. **Data Refresh fails:** Proceed with existing data. Note which indicators may be stale.
2. **Researcher fails mid-search:** Save partial research brief. Note which waves were incomplete. Proceed to Analyst with available material.
3. **Analyst fails:** Check if dossier was partially written. If JSON is invalid, re-run. If structural fields are missing, the Fixer can handle it.
4. **Writer fails:** Check for JSON serialization errors. Fix and re-run the assembly step.
5. **Auditor fails:** The briefing may still be publishable — present findings to user for manual review.
6. **Fixer fails after 3 passes:** Flag remaining issues for manual intervention. Present the briefing with known issues documented.
7. **Discovery fails:** Non-blocking. The briefing pipeline is independent of discovery. Note the failure and proceed.

Never abandon the pipeline entirely. Partial output is better than no output. If an agent produces partial results, note what's missing and continue.

---

## Rules

1. **Run agents in order.** Each depends on the previous agent's output (except Agent 6 which is independent).
2. **Read each skill file before executing.** The skill files contain detailed instructions.
3. **Give status updates.** After each agent, provide a 2-3 sentence summary before moving on.
4. **Don't auto-publish.** The dated briefing file is saved separately. Publishing to `briefing_latest.json` requires explicit user approval.
5. **Follow CLAUDE.md.** Editorial policy (reporting only, no editorializing) and system constraints (model stack, cost caps) apply to all agents.
6. **Preserve data integrity.** Never overwrite files without backing up. Dedup, sort, and validate before writing.
