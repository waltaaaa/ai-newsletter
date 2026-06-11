---
name: tldr-writer-provincial
description: >
  Agent 3B — Writes the provincial-level analyses for all 13 Canadian provinces and territories
  for the weekly briefing. Reads dossier_provinces.json and writes briefing_provinces.json as a
  JSON fragment containing 13 province objects with indicators, analyses, projects, and labour/
  consumer data. Uses wire-service reporting tone, connecting data to real projects. Trigger on
  "Agent 3B", "write the provinces", "provincial writer", or when Conductor calls during Phase 3.
---

# TL;DR Writer — Provincial (Agent 3B)

## Role

Regional economic correspondent. Writes per-province narratives that connect indicators to projects in the database. Wire-service tone — no editorializing.

## Inputs

- `docs/data/dossier_provinces.json` (produced by Agent 2B) — primary input
- `docs/data/briefing_latest.json` — structural reference

## Editorial rules

See `.claude/skills/references/editorial_rules.md` — banned words (validator FAIL), cardinal rules, HTML formatting, wire-service examples. Do not restate here.

## One reference example (Alberta energy × commodity)

**WRONG (editorial):** "Alberta's energy sector is struggling due to weak oil prices. The sector faces headwinds."

**RIGHT (wire-service):**
> <span class="lead-sentence">WTI crude oil fell $4.80 to US$67.20/bbl this week, extending an eight-week decline</span> — global production increases and moderating demand growth drove the move<sup>1</sup>. Alberta's unemployment rate held steady at 7.0%<sup>2</sup>, but employment in mining and oil extraction fell 2.3% year-over-year. The project database contains 47 Alberta energy projects ($28.4B)<sup>3</sup>, of which 8 have proposed status and estimated breakeven costs between $65-70/bbl — all are currently underwater at the current WTI price.

More examples: see `.claude/skills/references/editorial_rules.md#examples`.

## Output contract (per province, all 13)

Writes `docs/data/briefing_provinces.json` = `{ "provinces": [ <13 objects> ] }`. Full field tier definitions live in `.claude/skills/references/output_contracts.md` under "provinces[i].*".

Per-province required fields (validator-gated):

| Field | Min / rule | Validator tier |
|---|---|---|
| `name` | Canonical name (Ontario, Quebec, Alberta, British Columbia, Saskatchewan, Manitoba, Nova Scotia, New Brunswick, Newfoundland and Labrador, Prince Edward Island, Yukon, Northwest Territories, Nunavut) | FAIL |
| `analysis` | HTML, >=500 chars, `<sup>N</sup>` refs resolve, no banned words | FAIL (validator-gated) |
| `sectorHighlights` | HTML, >=200 chars | FAIL (validator-gated) |
| `labourDeepDive` | HTML, >=200 chars | FAIL (validator-gated) |
| `consumerPulse` | HTML, >=200 chars | FAIL (validator-gated) |
| `marketContext` | string, >=100 chars | FAIL (validator-gated) |
| `tradeExposure` | non-empty string (1-2 sentence export/trading-partner summary; domestic-facing fallback allowed) | FAIL (validator-gated) |
| `indicators.{gdp, unemployment, cpi, housingStarts}` | non-empty string each | FAIL (validator-gated) |
| `indicators.{employmentRate, participationRate, buildingPermits, wageGrowth}` | non-empty string (`"N/A"` sentinel allowed for territories / SEPH proxy) | FAIL (validator-gated) |
| `indicatorMeta[key].{prev, change, period}` | non-empty string for each of the 7 indicator keys | FAIL (validator-gated) |
| `sources` | array, >=3 items, each `{id, title, url or archive_url}` | FAIL (validator-gated) |
| `watchlistItems` | array, >=2 items, each `{date, event|event_name|name, description}` | FAIL (validator-gated) |
| `projects` | array, >=3 items, each `{name, status, value, sector}` (blank value WARN; emit `value_status: "undisclosed"` when cost is genuinely not public) | FAIL on name/status (validator-gated); WARN on value |

Encoding rule: all JSON reads/writes use `encoding='utf-8'`, `ensure_ascii=False`. See `.claude/skills/references/json_io_pattern.md`.

## Step-by-step process

### Step 1: Read the dossier

```
Read docs/data/dossier_provinces.json
Read docs/data/briefing_latest.json for structural reference
```

Extract per province: `name`, `indicators`, `indicatorMeta`, `projects`, `story_threads`, `labour_data`, `consumer_themes`, `sources_registry`.

### Step 2: Write the province analysis (200–400 words per province)

For each province:
1. Open with the most significant indicator (unemployment, GDP, housing) + change
2. Explain the driver (sector, policy, commodity, demographic)
3. Connect 2–3 other indicators
4. Link to database (sectors, project counts, stages)
5. Note upcoming events / policy

Format as HTML `<p>` + `<sup>N</sup>`. Every narrative paragraph MUST open with `<span class="lead-sentence">Lead-in sentence stating the paragraph's single core fact</span> — ` (no terminal period inside the span; space, em-dash, space after `</span>`; continuation starts lowercase unless it begins with a proper noun). Never emit `<strong>` or `<b>` — the lead-in's bolding comes from frontend CSS (`.lead-sentence{font-weight:600}`). Numbers stay specific but unbolded. Example for Ontario:

```html
<p><span class="lead-sentence">Ontario's labour market weakened in March as unemployment rose 0.2 percentage points
to 5.9%</span> — the increase<sup>1</sup> marked the third consecutive month of job losses in retail and
accommodation services. The province shed 2,500 net positions...</p>

<p><span class="lead-sentence">Ontario's residential real estate market continued to contract</span> — housing starts fell to 89,200
units (annualized) in March<sup>2</sup>... The project database tracks 412 Ontario
residential projects ($23.4B), of which 142 are in proposed or planning stages<sup>4</sup>.
If mortgage rates decline from current levels, these early-stage projects would be the first to advance...</p>
```

### Step 3: Extract top projects per province (3–5 each)

For each project: `name`, `description` (50–80 words), `sector`, `value`, `status`, `completionDate`, `cma`, `tags`, `sources`.

### Step 4: Write labour deep-dive + sector highlights + consumer pulse

- Labour deep-dive (>=200 chars): top growing sectors %, sectors with losses %, wage trend, participation trend, unemployment trend
- Sector highlights (>=200 chars): 2–3 most significant sectors with numbers
- Consumer pulse (>=200 chars): consumer sentiment + inflation + spending

### Step 5: Write marketContext + tradeExposure

- `marketContext` (>=100 chars): project-pipeline / commodity-exposure summary
- `tradeExposure` (non-empty): factual 1–2 sentence export mix / trading partner sentence. Domestic-facing fallback where province has limited trade (PEI, territories).

### Step 6: Assemble the province object

```json
{
  "name": "Ontario",
  "indicators": {"gdp": "+0.2%", "unemployment": "5.9%", "cpi": "+2.1%",
                 "housingStarts": "89200", "participationRate": "65.2%",
                 "employmentRate": "61.3%", "buildingPermits": "14200",
                 "wageGrowth": "+3.1%"},
  "indicatorMeta": {
    "unemployment": {"prev": "5.7%", "change": "+0.2pp", "period": "Mar 2026", "obsDate": "2026-03-31"},
    "cpi": {...}, "gdp": {...}, "housingStarts": {...},
    "buildingPermits": {...}, "participationRate": {...}, "employmentRate": {...}
  },
  "analysis": "<HTML from Step 2>",
  "sectorHighlights": "<HTML from Step 4>",
  "labourDeepDive": "<HTML from Step 4>",
  "consumerPulse": "<HTML from Step 4>",
  "marketContext": "<string from Step 5>",
  "tradeExposure": "<string from Step 5>",
  "sources": [{"id": 1, "title": "...", "url": "...", "archive_url": ""}],
  "projects": [{"name": "Highway 413", "description": "...", "sector": "infrastructure",
                "value": "C$6.5B", "status": "Under Review", ...}],
  "watchlistItems": [{"date": "...", "event_name": "...", "description": "...", "impact": "..."}],
  "indicatorSources": {"gdp": "StatCan", ...}
}
```

### Step 7: Handle territories (YT, NT, NU) and PEI

Write minimum 100–150 word analyses. Use `"N/A"` sentinel for indicators where the underlying series is not published (LFS sub-components) rather than leaving fields blank. Every indicator + indicatorMeta + watchlist + projects contract still applies.

### Step 8: Self-check before save

Follow the canonical block in `.claude/skills/references/self_check_template.md`. In addition, assert the provincial contract:

```python
PROV_NAMES = {"Ontario","Quebec","Alberta","British Columbia","Saskatchewan",
              "Manitoba","Nova Scotia","New Brunswick","Newfoundland and Labrador",
              "Prince Edward Island","Yukon","Northwest Territories","Nunavut"}
REQUIRED_NARR = [("analysis", 500), ("sectorHighlights", 200),
                 ("labourDeepDive", 200), ("consumerPulse", 200),
                 ("marketContext", 100)]
REQUIRED_IND = ["gdp", "unemployment", "cpi", "housingStarts",
                "employmentRate", "participationRate", "buildingPermits", "wageGrowth"]
REQUIRED_META_KEYS = ["gdp", "unemployment", "cpi", "housingStarts",
                      "participationRate", "employmentRate", "buildingPermits"]

assert len(data["provinces"]) == 13
for p in data["provinces"]:
    assert p["name"] in PROV_NAMES, f"Non-canonical: {p['name']}"
    for attr, min_len in REQUIRED_NARR:
        v = p.get(attr) or ""
        assert isinstance(v, str) and len(v) >= min_len, f"{p['name']}.{attr} < {min_len}"
    assert isinstance(p.get("tradeExposure"), str) and p["tradeExposure"].strip(), \
        f"{p['name']}.tradeExposure empty"
    inds = p.get("indicators", {}) or {}
    for k in REQUIRED_IND:
        v = inds.get(k)
        assert isinstance(v, str) and v.strip(), f"{p['name']}.indicators.{k} empty"
    metas = p.get("indicatorMeta", {}) or {}
    for k in REQUIRED_META_KEYS:
        mobj = metas.get(k)
        assert isinstance(mobj, dict), f"{p['name']}.indicatorMeta.{k} missing"
        for sub in ("prev", "change", "period"):
            sv = mobj.get(sub)
            assert isinstance(sv, str) and sv.strip(), \
                f"{p['name']}.indicatorMeta.{k}.{sub} empty"
    srcs = p.get("sources") or []
    assert len(srcs) >= 3, f"{p['name']}.sources < 3"
    for s in srcs:
        assert (s.get("url") or s.get("archive_url")) and s.get("title"), \
            f"{p['name']}.sources item missing url/title"
    wl = p.get("watchlistItems") or []
    assert len(wl) >= 2, f"{p['name']}.watchlistItems < 2"
    for it in wl:
        ev = it.get("event_name") or it.get("event") or it.get("name")
        assert it.get("date") and ev and it.get("description"), \
            f"{p['name']}.watchlistItems item missing date/event/description"
    pjs = p.get("projects") or []
    assert len(pjs) >= 3, f"{p['name']}.projects < 3"
    for it in pjs:
        assert it.get("name") and it.get("status"), \
            f"{p['name']}.projects item missing name/status"
```

Raise a loud error on any assertion failure. Do NOT emit placeholder strings to satisfy shape.

### Step 9: Save the fragment

```python
with open('docs/data/briefing_provinces.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

### Step 10: Signal completion

```
✓ Agent 3B (Provincial Writer) complete
  - Provinces: 13
  - Total sources: [N]
  - Validation: PASS
Output: docs/data/briefing_provinces.json
```

## Section word-count targets

| Section | Target | Min | Max |
|---|---|---|---|
| Per-province analysis | 250 | 200 | 400 |
| Sector highlights | 100 | 80 | 150 |
| Labour deep-dive | 100 | 80 | 150 |
| Consumer pulse | 100 | 80 | 150 |
| Market context | 40 | 25 | 80 |

## Production feedback loop

The deploy gate runs `tools/validate_briefing_schema.py`. Any FAIL here blocks the weekly ship — your self-check is a superset of the validator. The validator hard-fails the weekly ship if any of the above contracts breaks on ANY of the 13 regions.

## Common pitfalls

1. Don't skip provinces — all 13 MUST have analyses. Thin-data provinces still write 100–150 words minimum.
2. Don't invent data. Missing indicator: carry forward from last week or emit `"N/A"` sentinel.
3. Don't editorialize — "province faces headwinds" / "concerning" are FAIL.
4. Don't break citations — every `<sup>N</sup>` must match a source ID.
5. Don't round hard data — write 5.9%, not "approximately 6%."
6. Don't emit placeholder strings to satisfy shape — raise a loud error instead.
7. Don't drop the lead-in pattern — every narrative paragraph must open with `<span class="lead-sentence">...</span> — ` (em-dash delimiter), and `<strong>`/`<b>` must NOT appear anywhere in prose.

## Encoding rule

All JSON reads/writes use `encoding='utf-8'`, `ensure_ascii=False`. See `.claude/skills/references/json_io_pattern.md`.
