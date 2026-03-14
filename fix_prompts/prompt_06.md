I need you to clean up dead files and consolidate related modules. 

## Part 1: Delete legacy/dead files

Move the following files to an `archive/` directory (create it if it doesn't exist). Do NOT delete them outright — move them so they're preserved but out of the active codebase.

Dead/legacy files to archive:
- `perplexity_search.py` (already removed from pipeline, flag disabled in Prompt 2)
- `gemini_search.py` (legacy search logging helper, search disabled)
- `seed_projects.py` (legacy seeder, superseded by v2)
- `historical_backfill.py`
- `backfill_indicator_history.py`
- `backfill_commodity_timeseries.py`
- `backfill_descriptions.py`
- `backfill_frontend_data.py`
- `backfill_global_indicators.py`
- `backfill_project_fields.py`
- `backfill_project_values.py`
- `backfill_timeseries.py`

After moving each file:
1. Search all .py files for imports of the moved module
2. Remove any dead imports
3. If removing an import would break a code path, check whether that code path is actually reachable in the weekly pipeline. If not, comment it out.

## Part 2: Consolidate URL verification files

Current state: `url_utils.py`, `url_verifier.py`, `url_verify.py`, `deep_verification.py` — 4 files doing overlapping work.

Consolidate into 2 files:
- `url_utils.py` — keep as-is for URL normalization
- `url_verify.py` — merge all verification logic from `url_verifier.py` (async), `url_verify.py` (sync), and `deep_verification.py` (Wayback fallback) into a single module with clear function names: `verify_url_sync()`, `verify_urls_async()`, `verify_with_wayback_fallback()`

After consolidation:
1. Update all imports across the codebase to use the new module
2. Move the old files to `archive/`

## Part 3: Consolidate missed project files

Merge `missed_project_enrichment.py` and `missed_project_diagnostics.py` into a single `missed_projects.py`. Both operate on the same `missed_projects` table. Combine their functionality and update all imports.

## Part 4: Consolidate pipeline state files

Merge `pipeline_state.py` (follow-up query storage) and `pipeline_cache.py` (in-memory TTL cache) into a single `pipeline_store.py`. Both are thin key-value wrappers. Use two clear class names: `PipelineCache` (TTL cache) and `PipelineState` (follow-up queries). Update all imports.

After all consolidation, run a search for any remaining imports of the old module names to make sure nothing is broken.
