# Full Pipeline Test Prompt — The Lagging Indicator

Copy everything below the line into a new Cowork chat with the **"AI newsletter"** folder selected.

---

I'm running a full test of the TL;DR briefing pipeline for "The Lagging Indicator" Canadian macro dashboard. Run all 6 agents in sequence. The data refresh (Agent 0) already ran — all data files are current as of March 30, 2026.

## Pipeline order

Run each agent by reading and executing its skill file. Each agent depends on the previous agent's output, so run them strictly in order. After each agent completes, give me a 2-3 sentence status update before moving to the next one.

### Agent 1 — Researcher
- Skill: `.claude/skills/tldr-researcher/SKILL.md`
- ~90 WebSearches across 9 waves (national macro, trade, provincial, sector, markets, consumer, projects, policy, global)
- Output: `docs/data/research_brief.md` (3,000-5,000 words)

### Agent 2 — Analyst
- Skill: `.claude/skills/tldr-analyst/SKILL.md`
- Cross-references research_brief.md + pipeline data files (indicators.json, projects_all.json, timeseries.json, briefing_latest.json)
- Output: `docs/data/analyst_dossier.json`

### Agent 3 — Writer
- Skill: `.claude/skills/tldr-writer/SKILL.md`
- Transforms the dossier into narrative HTML sections following the 8-section briefing structure
- Output: `docs/data/briefing_YYYY-MM-DD.json` (dated file, does NOT auto-overwrite briefing_latest.json)

### Agent 4 — Auditor
- Skill: `.claude/skills/tldr-auditor/SKILL.md`
- 10-test adversarial audit (numbers, citations, editorial, logic, completeness, freshness, schema, cross-agent, sanity, security)
- Output: `docs/data/audit_report.md`

### Agent 5 — Fixer
- Skill: `.claude/skills/tldr-fixer/SKILL.md`
- Reads audit failures and makes targeted fixes, up to 3 passes
- Output: updated briefing JSON + fix log
- **If the auditor returns PASS, skip this agent**

### Agent 6 — Discovery (run last, independent)
- Skill: `.claude/skills/tldr-discovery/SKILL.md`
- 48 targeted searches for thin sectors (telecom, forestry, environment, indigenous, defence, agriculture) and thin provinces (NS, SK, NL, MB, NU)
- Output: `docs/data/discovery_batch.json`

## Current data state
- `docs/data/briefing_latest.json` — updated 2026-03-30
- `docs/data/indicators.json` — 429 indicators, 26,264 history entries
- `docs/data/timeseries.json` — 113 time series, all sorted/deduped
- `docs/data/projects_all.json` — 2,304 tracked projects
- `docs/data/data_snapshots.json` — 1 snapshot (2026-03-30)

Key numbers: unemployment 6.6%, BoC rate 2.75%, CPI 2.6%, GDP +1.5%, housing starts 238,049, TSX 31,888, WTI $101.01 (Iran/Hormuz tensions), Brent $114.90, gold $4,569, CAD/USD 0.7194, 10Y GoC yield 3.48%.

## Rules for all agents
- Read CLAUDE.md first for editorial policy and system constraints
- REPORTING ONLY — no editorializing, no banned words (should, worrying, promising, etc.)
- Every claim needs a source
- Use WebSearch for all external research (HTTP APIs are blocked)
- Don't fabricate data — if something can't be found, say so
- Preserve existing data file integrity (dedup, sort, no overwrites without explicit instruction)

## After all agents finish
Give me a final summary: what was produced, any audit failures and how they were resolved, how many new projects were discovered, and your assessment of overall briefing quality.
