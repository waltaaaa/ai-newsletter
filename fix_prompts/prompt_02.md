I need you to fix 6 configuration issues. Read each file before making changes.

## Fix 1: Three different Sonnet model defaults

Files: `pipeline_config.py`, `claude_reasoning.py`, `citation_audit.py`

These files have different hardcoded Sonnet model defaults:
- pipeline_config.py: `claude-sonnet-4-6`
- claude_reasoning.py: `claude-sonnet-4-5-20250929`
- citation_audit.py: `claude-sonnet-4-5-20250514`

Fix: Make `pipeline_config.py` the single source of truth. Define `SONNET_MODEL` there with the correct default (`claude-sonnet-4-6`). In `claude_reasoning.py` and `citation_audit.py`, import from `pipeline_config` instead of defining their own defaults. Search for any other files that hardcode a Sonnet model string and fix them too.

## Fix 2: Claude cost pricing is wrong

File: `claude_reasoning.py` around line 121

Uses `$3/M input + $15/M output` which is old Sonnet 3.5 pricing. Look up what the current rates should be for the model defined in `pipeline_config.py` and update the cost calculation constants.

## Fix 3: Cost cap defined but never enforced

File: `pipeline_config.py` line ~397, and `claude_reasoning.py`

`CLAUDE_COST_CAP_USD = 4.00` exists in pipeline_config but is never imported or checked anywhere. 

Fix: In `claude_reasoning.py`, before each Claude API call:
1. Import `CLAUDE_COST_CAP_USD` from `pipeline_config`
2. Track cumulative cost across the run (use a module-level variable or pass through PipelineRunLogger)
3. If cumulative cost exceeds the cap, log a warning and skip remaining Claude calls
4. Return None/empty for skipped calls so the pipeline can handle it gracefully

## Fix 4: Perplexity still enabled

File: `pipeline_config.py` line ~366, `perplexity_search.py`

`PERPLEXITY_ENABLED` defaults to `'true'` despite being explicitly banned. 

Fix:
- Change the default to `'false'`
- Delete `perplexity_search.py` entirely
- Search for any imports of `perplexity_search` across all .py files and remove them
- Search for any references to `PERPLEXITY_ENABLED` and remove the conditional branches

## Fix 5: Cross-reference sector names don't match DB taxonomy

File: `cross_reference.py`

Uses human-readable names ("Real Estate", "Mining & O&G", "Construction") but the projects table uses NAICS keys ("residential", "oil_gas", "mining"). The cross-reference engine produces zero correlations because the names never match.

Fix: Create a mapping dict from NAICS keys to human-readable names (or vice versa), referencing the NAICS map in `pipeline_config.py`. Apply the mapping in cross_reference.py so the sector join actually works.

## Fix 6: Enrichment query cap logic is broken

File: `enrichment_queries.py` lines 108-113

`MAX_ENRICHMENT_QUERIES_PER_DAY` is 55, but when exceeded the code takes `investigations[:50] + detail_fills[:50]` = up to 100 queries, nearly double the cap.

Fix: Change the slicing so the total across both lists respects the cap. For example: allocate 60% to investigations and 40% to detail_fills, or split evenly, but ensure the sum never exceeds `MAX_ENRICHMENT_QUERIES_PER_DAY`.
