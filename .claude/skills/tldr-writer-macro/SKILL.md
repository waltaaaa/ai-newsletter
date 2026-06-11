---
name: tldr-writer-macro
description: >
  Agent 3A — Writes the macro-level narrative sections of the weekly Canadian economic
  intelligence briefing. Produces headline, executive summary, national analysis, consumer
  pulse, global analysis (4 regions), watchlist, and all indicator context. Financial markets,
  commodities, and yield curve sections are now handled by dedicated market agents (3F–3I).
  Reads dossier_macro.json and writes briefing_macro.json as a JSON fragment. Part of the
  parallel Phase 3 writing stage. Trigger on "Agent 3A", "write the macro", "macro writer",
  or when the Conductor calls this skill during Phase 3.
---

# TL;DR Writer — Macro (Agent 3A)

## Role

National macro narrative writer. Takes Agent 2A's dossier and produces the headline, executive summary, national analysis, consumer pulse, global (4 regions), watchlist, and all indicator context. Does NOT write financial markets, commodities, or yield curve — those belong to agents 3F–3I.

## Inputs

- `docs/data/dossier_macro.json` (produced by Agent 2A) — primary input
- `docs/data/briefing_latest.json` — structural reference and data format
- `TLDR_JSON_SPECIFICATION.md` — complete schema (supplementary)

## Editorial rules

See `.claude/skills/references/editorial_rules.md` — banned words, cardinal rules, HTML formatting, wire-service examples. Do not restate here.

## One reference example (labour market connection)

**WRONG (disconnected):**
> "The labour market continued to weaken in March. Unemployment rose to 6.5%. Employment fell by 8,000 positions."

**RIGHT (wire-service reporting):**
> <span class="lead-sentence">Statistics Canada's Labour Force Survey recorded unemployment at 6.5% in March, up 0.3 percentage points from February</span> — the economy shed 8,000 positions<sup>1</sup> concentrated in retail trade and accommodation services. The project database tracks 412 retail and hospitality projects ($2.1B)<sup>2</sup> in proposed or planning stages, representing potential future employment in those sectors.

More examples: see `.claude/skills/references/editorial_rules.md#examples`.

## Output contract

Writes `docs/data/briefing_macro.json`. Full field tier definitions live in `.claude/skills/references/output_contracts.md` under top-level, `national.*`, and `global[i].*`.

Fields this skill owns (validator-gated FAIL unless marked otherwise):

| Field | Type / rule |
|---|---|
| `headline` | string |
| `edition` | string, format: `EDITION: Mon DD – Mon DD // STATUS: AI-SYNTHESIZED` |
| `week_of` | ISO date (Monday of briefing week) |
| `generated_at`, `updated_at` | ISO datetime / date |
| `executive_summary` | HTML, 300–500 words, `<p>` + `<sup>N</sup>` + `<span class="lead-sentence">` lead-in openings (no `<strong>`/`<b>`) |
| `national.analysis` | HTML, 400–600 words (validator min 500 chars), no banned words |
| `national.sources` | array, >=3 items, each `{id, title, url or archive_url}` |
| `consumer_pulse` | HTML, 200–300 words |
| `global` | array of 4 regions — each `{region (canonical), indicators (5 keys), indicatorMeta[key].change, analysis (>=400 chars), sources (>=1)}` |
| `globalVectors` | object `{us, china, eu}` (1–2 factual sentences each) |
| `indicatorContextLines` | object `{bocRate, cpi, unemployment, housingStarts, realGdp}` each a 1-sentence plain-English context |
| `watchlist` | watchlist package with descriptions written here |
| `metrics` | pass-through from dossier `national_analysis_package.metrics.*` — 12 enrichment keys (fulltime_change, parttime_change, private_sector_change, public_sector_change, core_cpi_median, shelter_cpi, food_cpi, energy_cpi, residential_permits, nonresidential_permits, merchandise_exports, merchandise_imports) — all non-empty strings (validator-gated). FORMAT: each value is a short data point (<=48 chars, contains a digit, e.g. "+1.5%", "$8.2B (Feb)") or exactly "N/A" — NEVER deferral prose like "See CPI April 2026 detail…" (renders in a narrow table cell; validator FAILs the deploy gate) |
| `indicatorMeta`, `indicatorSources`, `key_indicators`, `word_cloud_topics`, `discovery_stats` | pass-through from dossier |
| `sources` | from dossier.sources_registry |

**Do NOT emit** `financialMarkets`, `commodities`, `yieldCurve` keys — those are produced by Agents 3F–3I and merged by the assembler.

Encoding rule: all JSON reads/writes use `encoding='utf-8'`, `ensure_ascii=False`. See `.claude/skills/references/json_io_pattern.md`.

## Step-by-step process

### Step 1: Read the dossier

Extract: `headline`, `executive_summary_package`, `national_package`, `financial_markets_package` (for context only), `consumer_pulse_package`, `watchlist_package`, `global_package`, `sources_registry`.

### Step 2: Write the executive summary (300–500 words)

Structure:
1. Opening paragraph: lead with headline fact + specific number + citation + baseline context.
2. Body paragraphs (2–3): cover the next 3–5 most significant developments; connect each indicator to real projects or policy from the dossier's cross-references.
3. Closing paragraph: upcoming events that will affect the picture next week.

Format as `<p>` HTML with `<sup>N</sup>` citations. Every narrative paragraph MUST open with `<span class="lead-sentence">Lead-in sentence stating the paragraph's single core fact</span> — ` (no terminal period inside the span; space, em-dash, space after `</span>`; continuation starts lowercase unless it begins with a proper noun). Never emit `<strong>` or `<b>` — the lead-in's bolding comes from frontend CSS (`.lead-sentence{font-weight:600}`). Numbers stay specific but unbolded.

### Step 3: Write the national analysis (400–600 words)

Cover the headline macro figure, industry GDP movements (cite StatCan tables + NAICS), labour market (employment, unemployment, participation, wages), trade, housing, notable sector developments. Opening example:

```html
<p><span class="lead-sentence">Canada's real GDP contracted at an annualized rate of -0.6% in the
fourth quarter, marking the second consecutive quarter of decline</span> — the contraction met
technical recession criteria, according to Statistics Canada.<sup>1</sup> The decline was broad-based,
with goods-producing sectors declining 1.2% and services-producing sectors
down 0.3%...</p>
```

### Step 4: [REMOVED — Financial Markets]

Agent 3A no longer writes `financialMarkets`, `commodities`, or `yieldCurve`. Those are produced by Agents 3F–3I and assembled by Agent 3E.

### Step 5: Write consumer pulse (200–300 words)

Use `consumer_pulse_package` themes. Reference Reddit sentiment trends, Google Trends signals, tie to CPI components and e-commerce/retail data.

### Step 6: Write global analyses (per region, 150–250 words each)

For US, China, EU, UK in `global_package`: specific numbers, Canada-relevant connection (trade, FX, commodity demand, policy), no editorializing. Every region's `analysis` must be >=400 chars (validator floor) and its `indicators` must fill all 5 keys (gdp, cpi, rate, unemployment, tradeBalance) with non-empty strings (use `"N/A"` sentinel where data unavailable).

### Step 7: Write global vectors (1–2 sentences each)

Factual one-liner per region for `globalVectors.{us, china, eu}` — summarize key Canada-relevant development.

### Step 8: Write indicator context lines

Single plain-English sentence per key: `bocRate`, `cpi`, `unemployment`, `housingStarts`, `realGdp`. Each sentence explains the current value in context.

### Step 9: Write event descriptions for watchlist

For each `watchlist_package` item, ensure `description` is 1–2 factual sentences explaining the event and affected sectors/indicators.

### Step 10: Assemble the JSON fragment

```json
{
  "headline": "<from dossier>",
  "edition": "EDITION: Mon DD – Mon DD // STATUS: AI-SYNTHESIZED",
  "week_of": "<Monday ISO>",
  "generated_at": "<ISO datetime>",
  "updated_at": "<ISO date>",
  "executive_summary": "<HTML from Step 2>",
  "national": {"analysis": "<HTML from Step 3>", "sources": [...], "chart_callout": "<from charts agent later>"},
  "consumer_pulse": "<HTML from Step 5>",
  "global": [
    {"region": "United States", "indicators": {...5 keys...}, "indicatorMeta": {...}, "analysis": "<HTML>", "sources": [...]},
    {"region": "China", ...},
    {"region": "European Union", ...},
    {"region": "United Kingdom", ...}
  ],
  "globalVectors": {"us": "...", "china": "...", "eu": "..."},
  "indicatorContextLines": {"bocRate": "...", "cpi": "...", "unemployment": "...", "housingStarts": "...", "realGdp": "..."},
  "watchlist": "<from dossier.watchlist_package with descriptions>",
  "key_indicators": "<from dossier>",
  "metrics": "<from dossier.national_package.metrics — 12 enrichment keys>",
  "indicatorMeta": "<from dossier>",
  "indicatorSources": "<from dossier>",
  "word_cloud_topics": "<from dossier>",
  "discovery_stats": "<from dossier>",
  "sources": "<from dossier.sources_registry>"
}
```

### Step 11: Self-check before save

Follow the canonical block in `.claude/skills/references/self_check_template.md`. In addition, assert the macro contract:

```python
import re

# Required top-level keys
required = ['headline', 'executive_summary', 'national', 'consumer_pulse',
            'global', 'globalVectors', 'indicatorContextLines', 'watchlist',
            'sources', 'metrics']
missing = [k for k in required if k not in data]
assert not missing, f"MISSING KEYS: {missing}"

# Agent 3A MUST NOT emit market fields
for field in ['financialMarkets', 'commodities', 'yieldCurve']:
    assert field not in data, f"Agent 3A must not emit {field} — belongs to 3F-3I"

# 4 canonical global regions, each with full contract
canonical_regions = {"United States", "China", "China / Asia", "European Union", "United Kingdom"}
assert len(data['global']) == 4
for g in data['global']:
    assert g.get('region') in canonical_regions, f"Non-canonical region: {g.get('region')}"
    assert len(g.get('analysis') or '') >= 400, f"{g['region']}.analysis < 400 chars"
    for ikey in ('gdp', 'cpi', 'rate', 'unemployment', 'tradeBalance'):
        v = (g.get('indicators') or {}).get(ikey)
        assert isinstance(v, str) and v.strip(), f"{g['region']}.indicators.{ikey} empty"
        mch = ((g.get('indicatorMeta') or {}).get(ikey) or {}).get('change')
        assert isinstance(mch, str) and mch.strip(), f"{g['region']}.indicatorMeta.{ikey}.change empty"
    srcs = g.get('sources') or []
    assert len(srcs) >= 1, f"{g['region']}.sources < 1"

# 12 enrichment metrics — non-empty strings that LOOK like data points.
# These render in narrow numeric table cells: a value is <=48 chars with a
# digit (or "little changed (Apr)"-style), or exactly "N/A" when the series
# isn't in the dossier. Deferral prose ("See CPI April 2026 detail...;
# pending in dossier") is a contract breach — it wraps across ~10 lines in
# production and the schema validator FAILs the deploy gate on it.
enrichment = ['fulltime_change', 'parttime_change', 'private_sector_change', 'public_sector_change',
              'core_cpi_median', 'shelter_cpi', 'food_cpi', 'energy_cpi',
              'residential_permits', 'nonresidential_permits',
              'merchandise_exports', 'merchandise_imports']
prose_re = re.compile(r'(?i)\b(see|pending|per\s+statcan|release|detail|dossier|cited|documented|narrative|awaiting|forthcoming|tbd)\b')
for k in enrichment:
    v = data['metrics'].get(k)
    assert isinstance(v, str) and v.strip(), f"metrics.{k} empty — enrichment card renders em-dash"
    vv = v.strip()
    assert vv == 'N/A' or (len(vv) <= 48 and not prose_re.search(vv)
                           and (re.search(r'\d', vv) or re.match(r'(?i)^(little changed|unchanged|flat)\b', vv))), \
        f"metrics.{k} is prose/deferral text, not a data point: {vv!r} — use a short value or exactly 'N/A'"

# Word counts
def wc(html): return len(re.sub(r'<[^>]+>', '', html).split())
assert 300 <= wc(data['executive_summary']) <= 550, f"exec summary word count off"
assert wc(data['national']['analysis']) >= 400, f"national analysis word count off"
assert 200 <= wc(data['consumer_pulse']) <= 320, f"consumer pulse word count off"
```

Raise a loud error on any assertion failure.

### Step 12: Save the fragment

```python
with open('docs/data/briefing_macro.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

### Step 13: Signal completion

```
✓ Agent 3A (Macro Writer) complete
  - Headline: [headline]
  - Executive Summary: [N] words
  - National Analysis: [N] words
  - Global regions: 4
  - Sources: [N] citations
Output: docs/data/briefing_macro.json
```

## Section word-count targets

| Section | Target | Min | Max |
|---|---|---|---|
| Executive summary | 400 | 300 | 500 |
| National analysis | 500 | 400 | 600 |
| Consumer pulse | 250 | 200 | 300 |
| Per-global region | 200 | 150 | 250 |

## Production feedback loop

The deploy gate runs `tools/validate_briefing_schema.py`. Any FAIL blocks the weekly ship. Your self-check is a superset of the validator.

## Common pitfalls

1. Don't invent data — if the dossier doesn't have a number, carry forward or leave the field empty.
2. Don't round hard data — BoC rate 2.25% is 2.25%, not "approximately 2.3%."
3. Don't drop the lead-in pattern — every narrative paragraph must open with `<span class="lead-sentence">...</span> — ` (em-dash delimiter), and `<strong>`/`<b>` must NOT appear anywhere in prose. Don't forget `<sup>N</sup>` citation wrapping.
4. Don't editorialize — banned words list is non-negotiable.
5. Don't break JSON — always validate before save.
6. Don't cite vague sources — every `<sup>N</sup>` must resolve.
7. Don't emit market fields — `financialMarkets`, `commodities`, `yieldCurve` belong to agents 3F–3I.

## Encoding rule

All JSON reads/writes use `encoding='utf-8'`, `ensure_ascii=False`. See `.claude/skills/references/json_io_pattern.md`.
