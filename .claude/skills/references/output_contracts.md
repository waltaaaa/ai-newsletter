# Output Contracts — The Lagging Indicator briefing schema

Field-by-field contract for `docs/data/briefing_latest.json` plus the sibling data files read directly by the frontend. Every contract row names the producer skill, the validator check (if any), and the tier (FAIL blocks deploy, WARN does not).

Reference validator: `tools/validate_briefing_schema.py` — 0 FAIL required to ship.

## Tier legend

- **FAIL** — `tools/validate_briefing_schema.py` blocks deploy; pipeline aborts before GitHub Pages push.
- **WARN** — validator records the gap; deploy still proceeds. Producers should aspire to close these.
- **untracked** — producer responsibility, not yet validator-gated. Honor the contract anyway.

---

## Top-level fields (`briefing_latest.json` root)

| Field | Type | Required | Owner skill | Validator check | Tier |
|---|---|---|---|---|---|
| `headline` | string | yes | tldr-writer-macro | `top_level.headline` | FAIL |
| `week_of` | ISO date string | yes | tldr-writer-macro | `top_level.week_of` | FAIL |
| `id` | string | yes | tldr-assembler | `top_level.id` | FAIL |
| `edition` | string | yes | tldr-writer-macro | `top_level.edition` | FAIL |
| `executive_summary` | HTML string | yes | tldr-writer-macro | `top_level.executive_summary` | FAIL |
| `national` | object | yes | tldr-writer-macro | `top_level.national` | FAIL |
| `provinces` | array[13] | yes | tldr-writer-provincial | `count.provinces == 13` | FAIL |
| `goodsIndustries` | array[5] | yes | tldr-writer-goods | `count.goodsIndustries == 5` | FAIL |
| `servicesIndustries` | array[15] | yes | tldr-writer-services | `count.servicesIndustries == 15` | FAIL |
| `global` | array[4] | yes | tldr-writer-macro | `count.global == 4` | FAIL |
| `sources` | array, >=10 | yes | tldr-assembler | `count.sources >= 10` | FAIL |
| `commodities` | array, >=13 | yes | tldr-writer-market-commodities | `count.commodities >= 13` | FAIL |
| `financialMarkets` | object | yes | tldr-writer-market-equities + fx-yields | `top_level.financialMarkets` | FAIL |
| `yieldCurve` | array | yes | tldr-writer-market-fx-yields | `yieldCurve.is_list`, per-item `{term,yield,prevYield}` | FAIL |
| `consumer_pulse` | HTML string | yes | tldr-writer-macro | `top_level.consumer_pulse` | FAIL |
| `watchlist` | array | yes | tldr-writer-macro | `top_level.watchlist` | FAIL |
| `metrics` | object | yes | tldr-analyst-macro → writer-macro → assembler | `top_level.metrics` + enrichment-card subkeys | FAIL |
| `indicatorMeta` | object | yes | tldr-analyst-macro → writer-macro | `top_level.indicatorMeta` | FAIL |
| `insightCharts` | array[2] | yes | tldr-charts | `count.insightCharts == 2` | FAIL |
| `yieldCurveLastYear` | array | recommended | tldr-writer-market-fx-yields | `yieldCurveLastYear` | WARN |
| `bocRate` / `marketCommentary` / `pipeline_value` / `project_count` | alias fields | recommended | tldr-assembler | `top_level_alias.*` | WARN |

## `national.*`

| Field | Type | Required | Owner | Validator | Tier |
|---|---|---|---|---|---|
| `analysis` | HTML string, >=500 chars | yes | tldr-writer-macro | `national.analysis.present/length/banned_words` | FAIL |
| `sources` | array, >=3 items, each `{url, title}` | yes | tldr-writer-macro | `national.sources.*` | FAIL |
| `chart_callout` | 60–240 char string, cites >=1 number + >=1 pipeline artifact, no banned words | yes | tldr-charts | `callout.national.chart_callout.*` | FAIL |

## `global[i].*` (4 regions)

Canonical regions (`CANONICAL_GLOBAL_REGIONS` in validator): `United States`, `China`, `China / Asia`, `European Union`, `United Kingdom`.

| Field | Type | Required | Owner | Validator | Tier |
|---|---|---|---|---|---|
| `region` | string, canonical | yes | tldr-writer-macro | `global[i].region.present/canonical` | FAIL |
| `analysis` | HTML string, >=400 chars, no banned words | yes | tldr-writer-macro | `global[i].analysis.*` | FAIL |
| `sources` | array, >=1 `{url, title}` item | yes | tldr-writer-macro | `global[i].sources.*` | FAIL |
| `indicators.{gdp,cpi,rate,unemployment,tradeBalance}` | non-empty string each (or `"N/A"`) | yes | tldr-writer-macro | `global.<region>.indicators.<key>` | FAIL |
| `indicatorMeta.<key>.change` | non-empty string | yes | tldr-writer-macro | `global.<region>.indicatorMeta.<key>.change` | FAIL |
| `chart_callout` | 60–240 char callout | yes (when region has analysis) | tldr-charts | `callout.global.<region>.chart_callout.*` | FAIL |

## `provinces[i].*` (13 regions)

Narrative fields (`PROV_NARRATIVE_FIELDS` — min length tuned to writer floors, no banned words):

| Field | Min length | Owner | Validator | Tier |
|---|---|---|---|---|
| `analysis` | 500 | tldr-writer-provincial | `province.<name>.analysis.*` | FAIL |
| `sectorHighlights` | 200 | tldr-writer-provincial | `province.<name>.sectorHighlights.*` | FAIL |
| `labourDeepDive` | 200 | tldr-writer-provincial | `province.<name>.labourDeepDive.*` | FAIL |
| `consumerPulse` | 200 | tldr-writer-provincial | `province.<name>.consumerPulse.*` | FAIL |
| `marketContext` | 100 | tldr-writer-provincial | `province.<name>.marketContext.*` | FAIL |
| `tradeExposure` | non-empty string | tldr-writer-provincial | `province.<name>.tradeExposure` | FAIL |

Indicator map (`PROV_IND_FAIL_KEYS`, `PROV_IND_WARN_KEYS` post-B.4 promoted to FAIL, `PROV_IND_GAP_KEYS` likewise):

| Key | Tier | Notes |
|---|---|---|
| `gdp` | FAIL | all 13 regions, non-empty string |
| `unemployment` | FAIL | all 13 regions |
| `cpi` | FAIL | all 13 regions |
| `housingStarts` | FAIL | all 13 regions |
| `employmentRate` | FAIL | territories allowed `"N/A"` sentinel |
| `participationRate` | FAIL | territories allowed `"N/A"` sentinel |
| `buildingPermits` | FAIL | territories allowed `"N/A"` sentinel |
| `wageGrowth` | FAIL | national SEPH proxy or `"N/A"` |

`indicatorMeta[key].{prev, change, period}` — all three required as non-empty strings for every key above on every region (FAIL).

Other province arrays:

| Field | Rule | Tier |
|---|---|---|
| `sources` | array, >=3 items, `{url, title}` | FAIL |
| `watchlistItems` | array, >=2 items, each `{date, event or event_name or name, description}` | FAIL |
| `projects` | array, >=3 items, each `{name, status, value, sector}`; value can be blank when TBD | FAIL name/status; WARN value |
| `insightCharts` | non-empty array per province | WARN (shape + callout enforced in 10.5) |

## `goodsIndustries[i].*` (5) and `servicesIndustries[i].*` (15)

| Field | Rule | Owner | Tier |
|---|---|---|---|
| `name` | non-empty string | tldr-analyst-industry | FAIL (implicit count) |
| `analysis` | non-empty HTML prose | tldr-writer-goods / tldr-writer-services | WARN |
| `mm` | non-empty string (GDP M/M display) | tldr-writer-goods / services | FAIL |
| `yy` | non-empty string (GDP Y/Y display) | tldr-writer-goods / services | FAIL |
| `isNegative` | boolean | tldr-writer-goods / services | FAIL |
| `industrySources` | array, >=1 `{url, title}` | tldr-writer-goods / services | FAIL |
| `insightCharts` | non-empty array | tldr-charts | WARN (shape + callout enforced in 10.5) |

## `metrics.*` enrichment card keys

Every key below must be a non-empty string (`"N/A"` allowed when data is genuinely unavailable):

- Labour Market: `fulltime_change`, `parttime_change`, `private_sector_change`, `public_sector_change`
- Consumer Pulse: `core_cpi_median`, `shelter_cpi`, `food_cpi`, `energy_cpi`
- Housing & Construction: `residential_permits`, `nonresidential_permits`
- Trade & Commodities: `merchandise_exports`, `merchandise_imports`

Owner: tldr-analyst-macro emits to `dossier_macro.national_analysis_package.metrics.*`; tldr-writer-macro passes through to `briefing_macro.metrics.*`; tldr-assembler merges to top-level `metrics.*`. Validator: `metrics.<key>` FAIL.

Also required `_chg` companions per `indicatorMeta[key]`: `metrics.<key>_chg` (WARN).

## `insightCharts[*]` (top-level, per-province, per-industry)

Every chart spec at every tier must include:

| Field | Rule | Validator | Tier |
|---|---|---|---|
| `chartType` | enum: `line`, `multi_line`, `bar`, `diverging_bar` | `chart.<label>.chartType[.enum]` | FAIL |
| `title` | non-empty string | `chart.<label>.title` | FAIL |
| `dataKeys` | non-empty array of non-empty strings | `chart.<label>.dataKeys[.items]` | FAIL |
| `subtitle` | non-empty string recommended | `chart.<label>.subtitle` | WARN |
| `callout` | 60–240 chars, cites >=1 number, references pipeline-tracked artifact, no `CALLOUT_BANNED_WORDS` | `callout.<label>.*` | FAIL |
| `dataSource` | `timeseries` (default for top/provincial) or `indicators` (default for industry) | validated via cross-reference | FAIL |

Every `dataKeys[]` value must exist in the underlying data file (`docs/data/timeseries.json` or `indicators.history`) — validator `_validate_timeseries_json` and `_validate_indicators_json` cross-reference FAIL.

## `commodities[i].*`

Required per-item fields (`COMMODITY_FIELDS`): `name`, `val`, `day`, `mm`, `yy`, `context`, `unit`, `category`. Validator: `commodity.<name>.<field>` — WARN (frontend degrades). Name must not match `BAD_COMMODITY_NAMES` (pipeline-default aliases) — FAIL.

## `financialMarkets.*`

- `indices` — array, >=4 items, each with `EQUITY_FIELDS = {name, value, day, mm, yy}` (per-item WARN).
- `fx` — each item with `FX_FIELDS = {name, value, day, mm, yy}` (per-item WARN).

## `yieldCurve[*]`

Each item: `{term, yield, prevYield}` (FAIL per field). `yieldCurveLastYear` top-level companion recommended (WARN).

## Sibling data files (direct frontend reads)

All paths are `docs/data/*.json` — validator Phase 2 `_validate_data_dir` gates these. Freshness bounds in `DATA_MAX_AGE_DAYS` (see validator).

- `policy.json` — array of `{title, url, date, level, summary}`; FAIL on totally missing; WARN per-item shape.
- `projects_all.json` — array of projects; per-project FAIL on `{name, status, province}`; WARN on `sector`, `value`.
- `timeseries.json` — object of series; each series is a list of `{date, value}` items with >=2 points (FAIL). Every briefing-referenced `dataKey` must resolve here (cross-reference FAIL).
- `indicators.json` — object with `.history` series; cross-reference every briefing `dataKey` with `dataSource=indicators` (FAIL). `statcan_latest.updatedAt` freshness (WARN).
- `events.json` — object/array holding Canadian calendar items, per-item `{date, name, url}` WARN. Events are mirrored into `watchlist` (FAIL when totally missing; STATCAN_RECURRING-tier checks are FAIL).
- `events_global.json` — global calendar, per-item `{date, event_name, institution}` WARN.

## Callout quality contract (applies to every insightCharts callout)

- Length 60–240 chars
- Cites >=1 numeric data point (regex: `[-+]?\d`)
- References >=1 pipeline artifact — match one of: `tracked`, `tracks`, `pipeline`, `database`, `\d+ projects?`, `$<amount>[BM]`
- Contains zero `CALLOUT_BANNED_WORDS`
- No empty / placeholder string

Owner: tldr-charts (for structured charts) + tldr-visualizer (for editorial SVG charts).

## Pipeline Invariants this schema serves

From `CLAUDE.md` "Pipeline Invariants":

- **Callout quality contract.** Every insight chart spec MUST carry a non-empty `callout` string. Skills must raise a loud error rather than emit empty or placeholder callouts.
- **External data files are validator-gated.** Frontend reads `policy.json`, `projects_all.json`, `timeseries.json`, `indicators.json`, `events.json`, `events_global.json` directly.
- **Validator is a deploy gate.** Any FAIL blocks export. WARN does not block. No override flag.
