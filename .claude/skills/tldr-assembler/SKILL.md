---
name: tldr-assembler
disable-model-invocation: true
model: claude-haiku-4-5-20251001
description: >
  Mechanical merger of seven writing fragments plus optional visualization manifest into one
  complete briefing JSON for "The Lagging Indicator" dashboard. Runs on Claude Haiku 4.5 —
  purely mechanical work (JSON merge, source de-duplication, citation re-numbering, schema
  validation) with no creative writing or editorial judgment. Runs after all six writing
  agents (3A, 3B, 3C, 3D, 3F, 3-TRIAD) and the visualizer (Phase 3.25) complete. Merges
  briefing_macro.json, briefing_provinces.json, briefing_goods.json, briefing_services.json,
  briefing_market_commentary.json, briefing_market_equities.json, briefing_market_fx_yields.json,
  and briefing_market_commodities.json into a single output file. Integrates inline SVG charts
  from briefing_visualizations.json at specified narrative insertion points. Handles global source
  de-duplication, citation re-numbering, and schema validation. NO creative writing — purely
  mechanical merge and validation. Trigger on phrases like "assemble the briefing", "merge the
  fragments", "combine the writers", "run the assembler", "Agent 3E", "assembly phase", "build
  the final JSON", or when all six writers and the visualizer have completed their output.
---

# TL;DR Assembler — Agent 3E

You are the final mechanical merge step in "The Lagging Indicator" briefing pipeline. Your role is **The Assembler**: you take the eight completed writing fragments from Agents 3A (Macro Writer), 3B (Province Writer), 3C (Goods Writer), 3D (Services Writer), 3F (Market Commentary), 3G (Market Equities), 3H (FX & Yields), and 3I (Market Commodities), plus the optional visualization manifest from the Visualizer (Phase 3.25), merge them into one coherent JSON file, validate that everything is present and correct, and output the final briefing ready for the chart agent and quality audit.

## Why This Agent Exists

The eight writers work in parallel and produce their fragments independently. Each has its own sources array with IDs 1, 2, 3, etc. But the frontend expects ONE JSON file with ONE unified sources array and ONE global citation numbering scheme. This agent:

1. Merges the eight writer fragments into the schema specified in `TLDR_JSON_SPECIFICATION.md`
2. De-duplicates sources (same URL appearing in multiple fragments → merged to single entry)
3. Re-numbers all citation IDs globally so there's no collision
4. Re-maps all `<sup>N</sup>` references in HTML fields to the new global IDs
5. Validates completeness and schema compliance
6. Integrates inline SVG charts from the visualizer at their specified narrative insertion points

This agent does NOT write, analyze, or create new content. It is purely mechanical merge + validation.

## Your Inputs

Read these files from `docs/data/`:

| File | Producer | Contains |
|------|----------|----------|
| `briefing_macro.json` | Agent 3A | Macro narrative + sources; `headline`, `edition`, `week_of`, `executive_summary`, `national`, `global[]`, `consumer_pulse`, `watchlist`, `indicatorContextLines`, `metrics`, `indicatorMeta`, `indicatorSources` |
| `briefing_provinces.json` | Agent 3B | All 13 province objects + sources for each |
| `briefing_goods.json` | Agent 3C | 5 goods industries + sources |
| `briefing_services.json` | Agent 3D | 15 services industries + sources |
| `briefing_market_commentary.json` | Agent 3F | Market overview commentary (`market_commentary` HTML, `market_commentary_callout`, sources) |
| `briefing_market_equities.json` | Agent 3G | Per-index equity narratives (`equities[]` with 4 indices, each with `commentary`, sources) |
| `briefing_market_fx_yields.json` | Agent 3H | FX pairs + yield curve data and narratives (`fx.fx_commentary`, `yieldCurve.yield_commentary`, 7 tenors, sources) |
| `briefing_market_commodities.json` | Agent 3I | Per-commodity narratives (`commodities[]` with 13 items, `commodity_commentary`, `wcs_analysis`, sources) |
| `briefing_visualizations.json` | Visualizer (3.25) | Optional — inline SVG charts with insertion points (`charts[]`, each with `svg`, `insertion_point`, `callout_text`) |
| `briefing_latest.json` | Previous week | Previous week's briefing (for `id` increment reference and structural template) |

## Phase 1: Validate Input Files (3 minutes)

Before merging, check that all four fragments exist and are valid JSON:

```python
import json
import os

required_files = [
    'docs/data/briefing_macro.json',
    'docs/data/briefing_provinces.json',
    'docs/data/briefing_goods.json',
    'docs/data/briefing_services.json',
    'docs/data/briefing_market_commentary.json',
    'docs/data/briefing_market_equities.json',
    'docs/data/briefing_market_fx_yields.json',
    'docs/data/briefing_market_commodities.json',
    'docs/data/briefing_latest.json'
]

# Optional file (graceful degradation if absent)
optional_files = [
    'docs/data/briefing_visualizations.json'
]

fragments = {}
errors = []

for fpath in required_files:
    if not os.path.exists(fpath):
        errors.append(f"MISSING: {fpath}")
        continue

    try:
        with open(fpath) as f:
            data = json.load(f)
            name = fpath.split('/')[-1].replace('briefing_', '').replace('.json', '')
            fragments[name] = data
            print(f"✓ Loaded {name}")
    except json.JSONDecodeError as e:
        errors.append(f"INVALID JSON in {fpath}: {e}")
    except Exception as e:
        errors.append(f"ERROR loading {fpath}: {e}")

if errors:
    print("ERRORS FOUND:")
    for err in errors:
        print(f"  ✗ {err}")
    raise SystemExit(1)

print(f"\n✓ All 9 required input files valid")

# Load optional files
for fpath in optional_files:
    if os.path.exists(fpath):
        try:
            with open(fpath) as f:
                data = json.load(f)
                name = fpath.split('/')[-1].replace('briefing_', '').replace('.json', '')
                fragments[name] = data
                print(f"✓ Loaded optional: {name}")
        except json.JSONDecodeError as e:
            print(f"⚠ WARNING: Optional file {fpath} is invalid JSON: {e} — skipping")
    else:
        print(f"⚠ Optional file not found: {fpath} — charts will be skipped")

# Quick validation of fragment structure
macro = fragments['macro']
provinces = fragments['provinces']
goods = fragments['goods']
services = fragments['services']
market_commentary = fragments.get('market_commentary', {})
market_equities = fragments.get('market_equities', {})
market_fx_yields = fragments.get('market_fx_yields', {})
market_commodities = fragments.get('market_commodities', {})
visualizations = fragments.get('visualizations', {})
latest = fragments['latest']

# Validate required top-level fields per fragment
macro_required = ['headline', 'edition', 'week_of', 'executive_summary', 'national', 'sources']
for field in macro_required:
    if field not in macro:
        errors.append(f"briefing_macro.json missing required field: {field}")

if 'provinces' not in provinces or not isinstance(provinces.get('provinces'), list):
    errors.append(f"briefing_provinces.json missing 'provinces' array")
elif len(provinces.get('provinces')) != 13:
    errors.append(f"briefing_provinces.json has {len(provinces['provinces'])} provinces, expected 13")

if 'goodsIndustries' not in goods or len(goods.get('goodsIndustries')) != 5:
    errors.append(f"briefing_goods.json: expected 5 goods industries, got {len(goods.get('goodsIndustries', []))}")

if 'servicesIndustries' not in services or len(services.get('servicesIndustries')) != 15:
    errors.append(f"briefing_services.json: expected 15 services industries, got {len(services.get('servicesIndustries', []))}")

# Validate new market fragments
if 'market_commentary' not in market_commentary and market_commentary:
    errors.append(f"briefing_market_commentary.json missing 'market_commentary' field")

if market_equities:
    if 'equities' not in market_equities or len(market_equities.get('equities', [])) != 4:
        errors.append(f"briefing_market_equities.json: expected 4 equity indices, got {len(market_equities.get('equities', []))}")

if market_fx_yields:
    if 'fx' not in market_fx_yields:
        errors.append(f"briefing_market_fx_yields.json missing 'fx' object")
    if 'yieldCurve' not in market_fx_yields:
        errors.append(f"briefing_market_fx_yields.json missing 'yieldCurve' object")
    elif len(market_fx_yields.get('yieldCurve', {}).get('tenors', [])) != 7:
        errors.append(f"briefing_market_fx_yields.json: expected 7 yield tenors, got {len(market_fx_yields.get('yieldCurve', {}).get('tenors', []))}")

if market_commodities:
    if 'commodities' not in market_commodities or len(market_commodities.get('commodities', [])) != 13:
        errors.append(f"briefing_market_commodities.json: expected 13 commodities, got {len(market_commodities.get('commodities', []))}")

# Validate optional visualizations
if visualizations:
    charts = visualizations.get('charts', [])
    if not isinstance(charts, list):
        errors.append("briefing_visualizations.json 'charts' must be a list")
    elif len(charts) < 1 or len(charts) > 6:
        errors.append(f"briefing_visualizations.json: expected 1-6 charts, got {len(charts)}")

if errors:
    print("VALIDATION ERRORS:")
    for err in errors:
        print(f"  ✗ {err}")
    raise SystemExit(1)

print("✓ All fragments have required structure")
```

If any validation fails, **STOP and report the error.** Do not attempt to merge corrupted data.

## Phase 2: Extract and De-duplicate Sources (10 minutes)

All four fragments have `sources` arrays with local IDs (1, 2, 3, ...). Extract all sources, de-duplicate by URL, and build a global mapping.

```python
import json

macro = fragments['macro']
provinces = fragments['provinces']
goods = fragments['goods']
services = fragments['services']

# Extract all sources from all fragments
all_sources_raw = []

# From macro
macro_sources = macro.get('sources', [])
for src in macro_sources:
    all_sources_raw.append(('macro', src))

# From each province
for prov_obj in provinces.get('provinces', []):
    prov_sources = prov_obj.get('sources', [])
    for src in prov_sources:
        all_sources_raw.append((f"province:{prov_obj.get('name')}", src))

# From each goods industry
for ind_obj in goods.get('goodsIndustries', []):
    ind_sources = ind_obj.get('industrySources', [])
    for src in ind_sources:
        all_sources_raw.append((f"goods:{ind_obj.get('name')}", src))

# From each services industry
for ind_obj in services.get('servicesIndustries', []):
    ind_sources = ind_obj.get('industrySources', [])
    for src in ind_sources:
        all_sources_raw.append((f"services:{ind_obj.get('name')}", src))

# From market commentary
for src in market_commentary.get('sources', []):
    all_sources_raw.append(('market_commentary', src))

# From market equities
for src in market_equities.get('sources', []):
    all_sources_raw.append(('market_equities', src))

# From market FX & yields
for src in market_fx_yields.get('sources', []):
    all_sources_raw.append(('market_fx_yields', src))

# From market commodities
for src in market_commodities.get('sources', []):
    all_sources_raw.append(('market_commodities', src))

# De-duplicate: same URL = same source
url_to_source = {}  # url → best source record
url_to_old_ids = {}  # url → [(fragment_name, old_id), ...]

for fragment_name, src in all_sources_raw:
    url = src.get('url', '')

    if not url:
        print(f"⚠ WARNING: Source in {fragment_name} has no URL: {src.get('title', 'untitled')}")
        continue

    if url not in url_to_source:
        url_to_source[url] = src.copy()
        url_to_old_ids[url] = []

    old_id = src.get('id', 0)
    url_to_old_ids[url].append((fragment_name, old_id))

# Build new global sources array with new sequential IDs
global_sources = []
url_to_new_id = {}  # url → new_global_id

for new_id, (url, src) in enumerate(sorted(url_to_source.items()), start=1):
    src_copy = src.copy()
    src_copy['id'] = new_id
    global_sources.append(src_copy)
    url_to_new_id[url] = new_id

print(f"De-duplication summary:")
print(f"  Raw sources collected: {len(all_sources_raw)}")
print(f"  Unique URLs: {len(global_sources)}")
print(f"  URLs de-duplicated: {len(all_sources_raw) - len(global_sources)}")

# Build mapping for citation re-numbering
# For each fragment, map old_id → new_global_id
fragment_id_maps = {}  # fragment_name → {old_id → new_id}

for url, old_ids_list in url_to_old_ids.items():
    new_id = url_to_new_id[url]
    for frag_name, old_id in old_ids_list:
        if frag_name not in fragment_id_maps:
            fragment_id_maps[frag_name] = {}
        fragment_id_maps[frag_name][old_id] = new_id

print(f"\n✓ De-duplication complete. Ready for re-mapping.")
```

## Phase 3: Re-map All Citation References (15 minutes)

Every HTML field in every fragment contains `<sup>N</sup>` references. Re-map all of them to point to the new global source IDs.

```python
import re

def remap_citations(html_text, id_map):
    """
    Find all <sup>N</sup> tags in HTML and replace N with mapped value.
    Returns modified HTML.
    """
    def replace_sup(match):
        old_id = int(match.group(1))
        new_id = id_map.get(old_id, old_id)  # Fallback to old_id if not found (shouldn't happen)
        return f'<sup>{new_id}</sup>'

    return re.sub(r'<sup>(\d+)</sup>', replace_sup, html_text)

# Get ID maps
macro_map = fragment_id_maps.get('macro', {})
province_map = fragment_id_maps.get('province', {})  # All provinces use same fragment
goods_map = fragment_id_maps.get('goods', {})
services_map = fragment_id_maps.get('services', {})

# Re-map macro fragment
if 'executive_summary' in macro:
    macro['executive_summary'] = remap_citations(macro['executive_summary'], macro_map)

if 'national' in macro and 'analysis' in macro['national']:
    macro['national']['analysis'] = remap_citations(macro['national']['analysis'], macro_map)

if 'consumer_pulse' in macro:
    macro['consumer_pulse'] = remap_citations(macro['consumer_pulse'], macro_map)

# Global regions
if 'global' in macro:
    for region in macro['global']:
        if 'analysis' in region:
            region['analysis'] = remap_citations(region['analysis'], macro_map)

# Re-map provinces
for prov_obj in provinces.get('provinces', []):
    if 'analysis' in prov_obj:
        prov_obj['analysis'] = remap_citations(prov_obj['analysis'], province_map)

    if 'labourDeepDive' in prov_obj:
        prov_obj['labourDeepDive'] = remap_citations(prov_obj['labourDeepDive'], province_map)

    if 'consumerPulse' in prov_obj:
        prov_obj['consumerPulse'] = remap_citations(prov_obj['consumerPulse'], province_map)

    if 'tradeExposure' in prov_obj:
        prov_obj['tradeExposure'] = remap_citations(prov_obj['tradeExposure'], province_map)

    if 'marketContext' in prov_obj:
        prov_obj['marketContext'] = remap_citations(prov_obj['marketContext'], province_map)

# Re-map goods industries
for ind_obj in goods.get('goodsIndustries', []):
    if 'analysis' in ind_obj:
        ind_obj['analysis'] = remap_citations(ind_obj['analysis'], goods_map)

# Re-map services industries
for ind_obj in services.get('servicesIndustries', []):
    if 'analysis' in ind_obj:
        ind_obj['analysis'] = remap_citations(ind_obj['analysis'], services_map)

# Re-map market commentary
market_commentary_map = fragment_id_maps.get('market_commentary', {})
if 'market_commentary' in market_commentary:
    market_commentary['market_commentary'] = remap_citations(market_commentary['market_commentary'], market_commentary_map)

# Re-map market equities
market_equities_map = fragment_id_maps.get('market_equities', {})
for eq_obj in market_equities.get('equities', []):
    if 'commentary' in eq_obj:
        eq_obj['commentary'] = remap_citations(eq_obj['commentary'], market_equities_map)

# Re-map market FX & yields
market_fx_yields_map = fragment_id_maps.get('market_fx_yields', {})
if 'fx' in market_fx_yields and 'fx_commentary' in market_fx_yields['fx']:
    market_fx_yields['fx']['fx_commentary'] = remap_citations(market_fx_yields['fx']['fx_commentary'], market_fx_yields_map)
if 'yieldCurve' in market_fx_yields and 'yield_commentary' in market_fx_yields['yieldCurve']:
    market_fx_yields['yieldCurve']['yield_commentary'] = remap_citations(market_fx_yields['yieldCurve']['yield_commentary'], market_fx_yields_map)

# Re-map market commodities
market_commodities_map = fragment_id_maps.get('market_commodities', {})
if 'commodity_commentary' in market_commodities:
    market_commodities['commodity_commentary'] = remap_citations(market_commodities['commodity_commentary'], market_commodities_map)
for comm_obj in market_commodities.get('commodities', []):
    if 'commentary' in comm_obj:
        comm_obj['commentary'] = remap_citations(comm_obj['commentary'], market_commodities_map)

print(f"✓ All <sup>N</sup> references re-mapped")
```

## Phase 4: Build the Merged JSON (10 minutes)

Assemble all fragments into one output JSON following `TLDR_JSON_SPECIFICATION.md` schema:

```python
import json
from datetime import datetime

# Start with macro (it has most top-level fields)
output = {
    # Header & identity
    'headline': macro.get('headline', ''),
    'edition': macro.get('edition', ''),
    'week_of': macro.get('week_of', ''),
    'generated_at': datetime.utcnow().isoformat() + 'Z',
    'updated_at': datetime.utcnow().isoformat().split('T')[0],

    # Increment ID from last week
    'id': latest.get('id', 0) + 1,

    # Lead image (from macro)
    'unsplash_image_url': macro.get('unsplash_image_url', ''),

    # Executive summary (from macro)
    'executive_summary': macro.get('executive_summary', ''),

    # Key indicators (from macro)
    'key_indicators': macro.get('key_indicators', []),

    # National metrics (hard data from macro)
    'metrics': macro.get('metrics', {}),
    'indicatorMeta': macro.get('indicatorMeta', {}),
    'indicatorSources': macro.get('indicatorSources', {}),
    'indicatorContextLines': macro.get('indicatorContextLines', {}),

    # National analysis (from macro)
    'national': macro.get('national', {}),

    # Global context (from macro)
    'global': macro.get('global', []),
    'globalVectors': macro.get('globalVectors', {}),

    # Provinces (from provinces fragment)
    'provinces': provinces.get('provinces', []),

    # Industries
    'goodsIndustries': goods.get('goodsIndustries', []),
    'servicesIndustries': services.get('servicesIndustries', []),
    'industry_executive_summary': goods.get('industry_executive_summary', '') or services.get('industry_executive_summary', ''),

    # Financial markets (from dedicated market agents 3F–3I)
    'financialMarkets': {
        **market_fx_yields.get('fx', {}),
        'equities': market_equities.get('equities', []),
        'summary': market_commentary.get('market_commentary', ''),
        'callout': market_commentary.get('market_commentary_callout', {}),
    },
    'commodities': market_commodities.get('commodities', []),
    'commodity_commentary': market_commodities.get('commodity_commentary', ''),
    'wcs_analysis': market_commodities.get('wcs_analysis', {}),
    'yieldCurve': market_fx_yields.get('yieldCurve', {}),

    # Consumer pulse (from macro)
    'consumer_pulse': macro.get('consumer_pulse', ''),
    'word_cloud_topics': macro.get('word_cloud_topics', []),

    # Watchlist (from macro)
    'watchlist': macro.get('watchlist', []),

    # Discovery stats (from macro or services)
    'discovery_stats': macro.get('discovery_stats', {}),
    'project_count': macro.get('project_count'),
    'new_projects': macro.get('new_projects'),
    'pipeline_value': macro.get('pipeline_value'),

    # Unified global sources (de-duplicated & re-numbered)
    '_all_verified_sources': global_sources,

    # Copy over any structural fields from last week not produced by writers
    'infographic_directives': latest.get('infographic_directives', [])
}

print(f"✓ Merged JSON structure built")

# ── VISUALIZATION INTEGRATION ──
# Insert inline SVG charts from the visualizer at their specified narrative positions
if visualizations and 'charts' in visualizations:
    chart_insertions = []
    for chart in visualizations['charts']:
        chart_id = chart.get('id', 'unknown')
        insertion_point = chart.get('insertion_point', '')
        svg = chart.get('svg', '')
        callout_text = chart.get('callout_text', '')
        chart_title = chart.get('chart_title', '')
        source_attr = chart.get('source_attribution', '')
        legend = chart.get('legend', [])

        if not svg or not insertion_point:
            print(f"⚠ Skipping chart '{chart_id}': missing svg or insertion_point")
            continue

        # Build the callout-box HTML wrapper
        legend_html = ''
        if legend:
            legend_items = ''.join(
                f'<span class="chart-legend-item"><span class="chart-legend-dot" style="background:{item["color"]};"></span>{item["label"]}</span>'
                for item in legend
            )
            legend_html = f'<div class="chart-legend">{legend_items}</div>'

        callout_html = (
            f'<div class="callout-box callout-chart">'
            f'<div class="callout-chart-header">{chart_title}</div>'
            f'{legend_html}'
            f'{svg}'
            f'<div class="callout-chart-source">{source_attr}</div>'
            f'{f"<p class=\"callout-chart-text\">{callout_text}</p>" if callout_text else ""}'
            f'</div>'
        )

        chart_insertions.append({
            'id': chart_id,
            'insertion_point': insertion_point,
            'html': callout_html
        })

    # Store chart insertions in the output for the frontend to process
    output['_visualization_insertions'] = chart_insertions
    print(f"✓ {len(chart_insertions)} visualization(s) prepared for insertion")
else:
    print(f"⚠ No visualizations to integrate (briefing_visualizations.json absent or empty)")
```

## Phase 5: Validate Completeness (5 minutes)

Check that the merged output has all required fields per the specification:

```python
# Required top-level fields
required_fields = [
    'headline', 'edition', 'week_of', 'generated_at', 'updated_at', 'id',
    'executive_summary', 'key_indicators', 'metrics', 'indicatorMeta',
    'national', 'global', 'provinces', 'goodsIndustries', 'servicesIndustries',
    'financialMarkets', 'commodities', 'watchlist', '_all_verified_sources'
]

validation_errors = []

for field in required_fields:
    if field not in output:
        validation_errors.append(f"Missing required field: {field}")
    elif field in ['global', 'provinces', 'goodsIndustries', 'servicesIndustries'] and not isinstance(output[field], list):
        validation_errors.append(f"Field '{field}' must be a list, got {type(output[field])}")

# Check counts
if len(output.get('global', [])) != 4:
    validation_errors.append(f"global array: expected 4 regions, got {len(output.get('global', []))}")

if len(output.get('provinces', [])) != 13:
    validation_errors.append(f"provinces array: expected 13, got {len(output.get('provinces', []))}")

if len(output.get('goodsIndustries', [])) != 5:
    validation_errors.append(f"goodsIndustries: expected 5, got {len(output.get('goodsIndustries', []))}")

if len(output.get('servicesIndustries', [])) != 15:
    validation_errors.append(f"servicesIndustries: expected 15, got {len(output.get('servicesIndustries', []))}")

# Check that headline is non-empty
if not output.get('headline', '').strip():
    validation_errors.append(f"headline is empty")

# Check that executive_summary is non-empty
if not output.get('executive_summary', '').strip():
    validation_errors.append(f"executive_summary is empty")

if validation_errors:
    print("VALIDATION ERRORS:")
    for err in validation_errors:
        print(f"  ✗ {err}")
    raise SystemExit(1)

print(f"✓ Completeness validation passed")
print(f"  Headline: {output['headline'][:60]}...")
print(f"  Global regions: {len(output['global'])}")
print(f"  Provinces: {len(output['provinces'])}")
print(f"  Goods industries: {len(output['goodsIndustries'])}")
print(f"  Services industries: {len(output['servicesIndustries'])}")
print(f"  Total verified sources: {len(output['_all_verified_sources'])}")
```

## Phase 6: Validate Citation Integrity (5 minutes)

Ensure every `<sup>N</sup>` in HTML resolves to a valid source with a URL:

```python
import re

def validate_citations(output):
    """
    Scan all HTML fields for <sup>N</sup> and verify they resolve to sources.
    Returns list of citation issues, or empty list if all good.
    """
    issues = []

    # Build set of valid source IDs
    valid_ids = {src.get('id') for src in output.get('_all_verified_sources', [])}

    # List of HTML fields to check
    html_fields = [
        ('executive_summary', 'top level'),
        ('national.analysis', 'national analysis'),
        ('consumer_pulse', 'consumer pulse'),
    ]

    # Add global regions
    for i, region in enumerate(output.get('global', [])):
        html_fields.append((f'global[{i}].analysis', f"global {region.get('region')}"))

    # Add provinces
    for i, prov in enumerate(output.get('provinces', [])):
        html_fields.append((f'provinces[{i}].analysis', f"province {prov.get('name')}"))
        if 'labourDeepDive' in prov:
            html_fields.append((f'provinces[{i}].labourDeepDive', f"province {prov.get('name')} labour"))
        if 'consumerPulse' in prov:
            html_fields.append((f'provinces[{i}].consumerPulse', f"province {prov.get('name')} consumer"))

    # Add industries
    for i, ind in enumerate(output.get('goodsIndustries', [])):
        html_fields.append((f'goodsIndustries[{i}].analysis', f"goods {ind.get('name')}"))

    for i, ind in enumerate(output.get('servicesIndustries', [])):
        html_fields.append((f'servicesIndustries[{i}].analysis', f"services {ind.get('name')}"))

    # Check each HTML field
    sup_pattern = r'<sup>(\d+)</sup>'

    for field_path, field_label in html_fields:
        # Navigate to field in output (supports dot notation)
        try:
            obj = output
            for key in field_path.split('.'):
                if '[' in key:
                    # Handle array index
                    key_name, idx = key.split('[')
                    idx = int(idx.rstrip(']'))
                    obj = obj[key_name][idx]
                else:
                    obj = obj.get(key, '')

            if not isinstance(obj, str):
                continue

            # Find all <sup>N</sup> in this field
            for match in re.finditer(sup_pattern, obj):
                sup_id = int(match.group(1))
                if sup_id not in valid_ids:
                    issues.append(f"{field_label}: <sup>{sup_id}</sup> not in sources")
        except (KeyError, IndexError, TypeError):
            pass

    return issues

citation_issues = validate_citations(output)
if citation_issues:
    print("CITATION INTEGRITY ISSUES:")
    for issue in citation_issues:
        print(f"  ✗ {issue}")
    raise SystemExit(1)

print(f"✓ Citation integrity validated: all <sup>N</sup> resolve to sources")
```

## Phase 7: Write Output File (2 minutes)

Write the merged output to `docs/data/briefing_YYYY-MM-DD.json`:

```python
import json
from datetime import date

output_filename = f"docs/data/briefing_{date.today().isoformat()}.json"

try:
    with open(output_filename, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✓ Output written: {output_filename}")
except Exception as e:
    print(f"✗ ERROR writing output: {e}")
    raise SystemExit(1)
```

**IMPORTANT:** Do NOT overwrite `briefing_latest.json`. That file is managed by the frontend/deployment. Only write the dated file.

## Phase 8: Final Validation (2 minutes)

Verify the output file is valid JSON and can be read back:

```python
import json
import os

output_filename = f"docs/data/briefing_{date.today().isoformat()}.json"

# Check file exists
if not os.path.exists(output_filename):
    print(f"✗ ERROR: Output file not created")
    raise SystemExit(1)

# Check file size
size_bytes = os.path.getsize(output_filename)
size_mb = size_bytes / (1024 * 1024)
if size_mb < 0.5:
    print(f"⚠ WARNING: Output file very small ({size_mb:.1f}MB), may be corrupted")

# Try to read it back
try:
    with open(output_filename) as f:
        verify = json.load(f)
    print(f"✓ Output file valid JSON ({size_mb:.1f}MB)")
except json.JSONDecodeError as e:
    print(f"✗ ERROR: Output file is invalid JSON: {e}")
    raise SystemExit(1)

# Quick sanity check
if verify.get('headline'):
    print(f"✓ Headline confirmed: {verify['headline'][:50]}...")
if len(verify.get('_all_verified_sources', [])) > 0:
    print(f"✓ Sources count: {len(verify['_all_verified_sources'])}")
```

## Phase 9: Print Summary (1 minute)

Output a summary for the user and conductor:

```
═══════════════════════════════════════════════════════════════════
ASSEMBLY COMPLETE
═══════════════════════════════════════════════════════════════════

Input files merged:
  ✓ briefing_macro.json (macro + global — Agent 3A)
  ✓ briefing_provinces.json (13 provinces — Agent 3B)
  ✓ briefing_goods.json (5 industries — Agent 3C)
  ✓ briefing_services.json (15 industries — Agent 3D)
  ✓ briefing_market_commentary.json (market overview — Agent 3F)
  ✓ briefing_market_equities.json (4 indices — Agent 3G)
  ✓ briefing_market_fx_yields.json (FX + 7 yield tenors — Agent 3H)
  ✓ briefing_market_commodities.json (13 commodities — Agent 3I)
  ✓ briefing_visualizations.json (editorial charts — Visualizer 3.25)

Output file:
  ✓ docs/data/briefing_2026-03-25.json (12.4 MB)

Merger statistics:
  Sources de-duplicated: 143 raw → 127 unique URLs
  Citations re-mapped: 847 <sup>N</sup> references updated
  Global regions: 4 (US, China, EU, UK)
  Provinces: 13 (all present)
  Goods industries: 5 (all present)
  Services industries: 15 (all present)
  Verified sources: 127

Validation:
  ✓ All required top-level fields present
  ✓ All array counts correct
  ✓ All citations resolve to sources with URLs
  ✓ Valid JSON, readable from disk
  ✓ Headline: "BoC cuts 25bps as Q1 GDP misses..."
  ✓ Executive summary: 847 words, 31 citations

Next step:
  → Agent 4 (Charts) reads briefing_2026-03-25.json and adds insightCharts
  → Agent 5 (Auditor) validates final content

═══════════════════════════════════════════════════════════════════
```

## Important Rules

1. **NO creative writing.** This agent is purely mechanical. Every word in the output came from one of the eight input fragments or the visualization manifest.

2. **NO source modification.** Never change a source's title, URL, or metadata. Only de-duplicate by URL.

3. **De-duplicate conservatively.** If two sources have the same URL but different titles, keep the most complete title. If titles differ, keep both titles as a note (or pick the more descriptive one).

4. **Every citation must resolve.** Before outputting, verify that every `<sup>N</sup>` in every HTML field points to a real source with a non-empty URL.

5. **Preserve structure from latest.** If `briefing_latest.json` has structural fields like `infographic_directives` that the writers didn't touch, copy them forward to the output.

6. **Write dated file only.** Output goes to `docs/data/briefing_YYYY-MM-DD.json`, never to `briefing_latest.json`.

7. **ID increment.** The `id` field should be `latest.id + 1`. This ensures briefings are numbered sequentially.

8. **Timestamps.** Set `generated_at` to UTC now and `updated_at` to today's date (no time).

9. **Fail on validation errors.** If the output is missing required fields, has wrong array counts, or has unresolved citations, do NOT write the file. Report the error and STOP.

10. **Handle missing sections gracefully.** If a fragment doesn't have a field (e.g., a province missing `labourDeepDive`), leave it out of the output rather than creating empty strings.

11. **Visualization graceful degradation.** If `briefing_visualizations.json` doesn't exist or is invalid, skip chart insertion entirely. The briefing must still be complete and valid without charts. Never fail the assembly because charts are missing.

12. **Market fields come from market agents, not macro.** `financialMarkets` is assembled from 3G (equities) and 3H (FX/yields). `commodities` comes from 3I. `yieldCurve` comes from 3H. The macro agent (3A) no longer produces these fields — do NOT fall back to `macro.get('financialMarkets')`.

## Example Output Summary

```
═══════════════════════════════════════════════════════════════════
ASSEMBLY COMPLETE
═══════════════════════════════════════════════════════════════════

Input files merged:
  ✓ briefing_macro.json (macro + global — Agent 3A)
  ✓ briefing_provinces.json (13 provinces — Agent 3B)
  ✓ briefing_goods.json (5 industries — Agent 3C)
  ✓ briefing_services.json (15 industries — Agent 3D)
  ✓ briefing_market_commentary.json (market overview — Agent 3F)
  ✓ briefing_market_equities.json (4 indices — Agent 3G)
  ✓ briefing_market_fx_yields.json (FX + 7 yield tenors — Agent 3H)
  ✓ briefing_market_commodities.json (13 commodities — Agent 3I)
  ✓ briefing_visualizations.json (editorial charts — Visualizer 3.25)

Output file:
  ✓ docs/data/briefing_2026-03-25.json (14.2 MB)

Merger statistics:
  Sources de-duplicated: 151 raw → 134 unique URLs
  Citations re-mapped: 912 <sup>N</sup> references
  Global regions: 4
  Provinces: 13
  Goods industries: 5
  Services industries: 15
  Verified sources: 134

Validation:
  ✓ All required fields present
  ✓ All array counts correct
  ✓ All 912 citations resolve
  ✓ Valid JSON
  ✓ Headline: "GDP contracts 0.6% QoQ as BoC signals caution"
  ✓ Executive summary: 1,124 words

Next step: Agent 4 (Charts) adds insightCharts arrays
```

This output signals to the conductor that the assembly step succeeded and the briefing is ready for charting and audit.
