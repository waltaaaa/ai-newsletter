# Agent 1 (Researcher) Test Prompt

Copy everything below the line into a new Cowork chat with the "AI newsletter" folder selected.

---

I'm testing the TL;DR briefing pipeline for "The Lagging Indicator" Canadian macro dashboard. The project folder is already selected.

**Run Agent 1 (the Researcher) now.** Here's the context:

## What to do
Read and execute the skill at `.claude/skills/tldr-researcher/SKILL.md` exactly as written. This is Agent 1 — the deep researcher that performs ~90 WebSearches across 9 waves covering Canadian economic conditions for the week of March 30, 2026.

## Current data state
The data refresh agent (Agent 0) already ran today. The pipeline data files are up to date:
- `docs/data/briefing_latest.json` — updated March 30, 2026 (metrics, markets, commodities, yields all fresh)
- `docs/data/indicators.json` — 429 indicators, 26,264 history entries
- `docs/data/timeseries.json` — 113 time series keys, all sorted and deduped
- `docs/data/projects_all.json` — 2,304 tracked projects

Key numbers to reference: unemployment 6.6%, BoC rate 2.75%, CPI 2.6%, GDP +1.5%, housing starts 238,049, TSX 31,888, WTI $101.01 (elevated due to Iran/Hormuz tensions), gold $4,569.

## Expected output
The researcher should produce `docs/data/research_brief.md` — a 3,000-5,000 word research brief organized by the waves defined in the skill. It should cover national macro, trade/tariffs, all 13 provinces, 18 sectors, markets, consumer data, major projects, policy developments, and global context.

## Rules
- Follow the editorial policy in CLAUDE.md: REPORTING ONLY, no editorializing
- Every claim needs a source
- Use WebSearch for all research (HTTP APIs are blocked in this sandbox)
- Don't modify any existing data files — only create the research_brief.md output
- If you hit search limits, prioritize: national macro > provinces > sectors > markets > projects

After the research brief is complete, give me a summary of the top 5 stories found and flag any data gaps or concerns.
