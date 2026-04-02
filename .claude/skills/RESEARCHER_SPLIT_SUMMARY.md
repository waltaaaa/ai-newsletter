# Researcher Agent Split — Summary

**Date created:** March 31, 2026

The monolithic `tldr-researcher` skill has been split into **three focused, parallel researcher agents** that align with the Phase 1 structure in `tldr-conductor/ARCHITECTURE.md`.

---

## Overview

**Old:** Single `tldr-researcher` (1,339 lines) covering everything: macro, all 13 provinces, all 20 NAICS industries, global context, consumer sentiment, events.

**New:** Three specialized agents (1,339 lines total, distributed):

| Agent | Focus | Input Files | Output File | Validation |
|-------|-------|------------|-------------|------------|
| **1A: tldr-researcher-macro** | National macro, markets, global context, consumer sentiment, events | briefing_latest.json, indicators.json, commodities.json, timeseries.json, events.json, data_gap_report.md | research_macro.md | >800 words, sections: macro, markets, global, consumer |
| **1B: tldr-researcher-provincial** | All 13 provinces + 3 territories — indicators, policy, projects, labour, IAAC, procurement | indicators.json, policy.json, projects_all.json, data_gap_report.md | research_provinces.md | >1500 words, ALL 16 regions mentioned |
| **1C: tldr-researcher-sector** | All 20 NAICS industries (5 goods + 15 services) — sector trends, projects, commodities, labour | projects_all.json, commodities.json, indicators.json, data_gap_report.md | research_sectors.md | >1000 words, covers goods + services |

All three agents run **in parallel** during Phase 1 of the pipeline.

---

## Search Wave Allocation

### Agent 1A (Macro & Markets)
- Wave 1: National Macro (8-10 searches)
- Wave 2: Trade & Geopolitics (6-8 searches)
- Wave 5: Financial Markets & Commodities (6-8 searches)
- Wave 6: Consumer & Labour (5-6 searches)
- Wave 8: Policy & Regulatory (5-6 searches)
- Wave 9: Global Context (6-8 searches)
- Phase 5: Consumer Sentiment Scan (5 searches)
- Phase 6: Upcoming Events (5 searches)
- **Total: ~45-50 searches**

### Agent 1B (Provincial)
- Wave 3: Provincial Scan (13 searches — one per province/territory)
- Policy & Regulatory Deep Dive (13 searches)
- Capital Projects by Province (13 searches)
- IAAC Status Monitoring (13 searches)
- Procurement Monitoring (13 searches)
- Labour Market by Province (13 searches)
- **Total: ~78 searches (13 regions × 6 search types)**

### Agent 1C (Sector & Industry)
- Wave 4: Sector-Specific (18 searches — project sectors)
- Wave 4b: NAICS GDP Industries (12 supplementary searches)
- Wave 7: Major Projects & Corporate (6-8 searches)
- Commodity Price Impact Analysis (per-sector deep dives)
- New Project Announcements by Sector (20 NAICS industries)
- Labour Market by Sector (per-sector searches)
- **Total: ~40-45 searches**

**Combined total: ~165-175 searches weekly** (vs. monolithic's ~95 searches) — each agent now runs a focused, manageable subset in parallel.

---

## Key Features Preserved

1. **Citation Chain Protocol:** Every fact includes the EXACT source URL.
2. **Factual Reporting Only:** No editorializing, no "good/bad/concerning/promising" language.
3. **Precision:** "unemployment fell 0.2pp to 6.5%" not "dropped" or "about 6.5%".
4. **Data Audit Checklists:** Each agent audits its input data before searching.
5. **Week-over-Week Change Detection:** Comparison against previous briefing.
6. **Master Source Registry:** Numbered URL list at the bottom of each research output.
7. **Acceptable Sources:** Specific release pages, government websites, official press releases. NO: homepages, domain roots, landing pages.

---

## Coverage Guarantees

- **Agent 1A:** Must cover macro, markets, global (4 regions: US, China, EU, UK), and consumer sentiment themes.
- **Agent 1B:** Must cover ALL 13 provinces AND 3 territories (16 total). If no developments found, state "No significant developments found in research for [Region] this week."
- **Agent 1C:** Must cover ALL 20 NAICS industries (5 goods + 15 services). If sparse data, state "No significant developments found in research for [Industry] this week."

---

## Output Structure

Each agent produces a markdown file with identical sections:

1. Data Quality Audit (freshness, coverage, completeness)
2. Week-over-week changes
3. Topical sections (macro stories, provincial spotlights, sector spotlights)
4. Emerging trends
5. Coverage gaps and priorities
6. Master Source Registry (numbered URL list)

---

## Integration with Conductor

In `tldr-conductor/ARCHITECTURE.md` Phase 1:

```
Agent 1A reads: briefing_latest.json, indicators.json, commodities.json, timeseries.json, events.json, data_gap_report.md
Agent 1B reads: indicators.json, policy.json, projects_all.json, data_gap_report.md
Agent 1C reads: projects_all.json, commodities.json, indicators.json, data_gap_report.md

All three agents run in parallel.
Each produces their research output.

Then Phase 2: Three analysts (2A, 2B, 2C) read the research outputs and produce dossiers in parallel.
Then Phase 3: Four writers synthesize the dossiers into the final briefing.
```

---

## Validation Checks

Before declaring success, verify:

- [ ] Agent 1A output `research_macro.md` exists, >800 words, contains macro/markets/global/consumer sections
- [ ] Agent 1B output `research_provinces.md` exists, >1500 words, mentions all 13 provinces + 3 territories
- [ ] Agent 1C output `research_sectors.md` exists, >1000 words, covers all 5 goods + all 15 services industries
- [ ] Each output has a Master Source Registry with numbered URLs
- [ ] No editorializing language found in any output
- [ ] All three agents receive `data_gap_report.md` and note priorities

---

## File Locations

```
.claude/skills/
├── tldr-researcher-macro/
│   └── SKILL.md (429 lines)
├── tldr-researcher-provincial/
│   └── SKILL.md (409 lines)
├── tldr-researcher-sector/
│   └── SKILL.md (501 lines)
└── RESEARCHER_SPLIT_SUMMARY.md (this file)
```

The old monolithic `tldr-researcher/SKILL.md` (1,339 lines) can be archived or deleted once the new agents are tested and integrated into the conductor workflow.

---

## Testing Recommendation

Before deploying to production, run a test cycle:

1. Call Agent 1A with sample data — verify output format, word count, sections.
2. Call Agent 1B with sample data — verify all 16 regions mentioned, coverage complete.
3. Call Agent 1C with sample data — verify all 20 NAICS covered, goods and services both present.
4. Verify all three complete without errors and produce valid markdown.
5. Check source registry counts (should be 30-50+ URLs per agent).
6. Integrate with conductor and run Phase 1-3 end-to-end.
