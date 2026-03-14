I need you to fix several data quality issues. Read each file before making changes.

## Fix 1: Phase numbers stripped from dedup keys

File: `anomaly_detection.py`

Phase numbers are stripped during normalization, causing "LNG Canada Phase 1" and "LNG Canada Phase 2" to normalize identically and be flagged as cross-province duplicates.

Fix: Preserve numeric phase/stage identifiers in the normalization. The regex that strips numbers should exclude patterns like "Phase N", "Stage N", "Part N", "Unit N".

## Fix 2: Aggressive filler removal causes false merges

File: `project_dedup.py`

Words like "mall", "centre", "tower", "facility", "plant" are stripped from dedup keys. Two different projects at the same location whose names differ only by building type will merge incorrectly (e.g., "Westbank Centre" and "Westbank Tower").

Fix: Remove these building-type words from the filler list. They carry semantic meaning for project identity. Keep truly filler words like "the", "of", "a", "new", "project".

## Fix 3: URL hard gate not enforced at DB layer

File: `db.py`, function `upsert_project()`

The URL hard gate is enforced in `project_schema.py:build_project_document()` but not in `db.py:upsert_project()`. Code calling upsert directly (which `project_sync.py` does) can write projects with zero evidence URLs.

Fix: Add a check at the top of `upsert_project()`:
```python
evidence = project.get("evidence", "[]")
if isinstance(evidence, str):
    evidence = json.loads(evidence)
if not evidence or len(evidence) == 0:
    print(f"[DB] Rejected project with no evidence URL: {project.get('name', 'unknown')}")
    return None
```

## Fix 4: `cost_unfindable` has no reset mechanism

File: `cost_finder.py`

Once a project is marked `cost_unfindable` after 3 failed searches, it's permanently excluded even if cost information later becomes available.

Fix: Add a reset mechanism — clear the `cost_unfindable` flag for projects whose `lastSeen` has been updated in the last 7 days (meaning new evidence was found). Add this as a pre-step in the cost-finding process.

## Fix 5: Compound query count mismatch

File: `compound_queries_final.json`, `google_news_rss_search.py`

Documentation says 759 queries; actual file has 2,574. After `_shorten_query()`, many collapse to near-identical RSS URLs.

Fix: 
1. Add a dedup step in `google_news_rss_search.py` that compares the final shortened URLs and removes duplicates before fetching
2. Update the documentation to reflect the actual count
3. Log the dedup stats: "2,574 queries → {N} unique RSS URLs after dedup"

## Fix 6: `normalize_url` strips query parameters unconditionally

File: `url_utils.py` line ~105

Stripping ALL query params can merge distinct StatCan URLs (e.g., `?pid=1234` vs `?pid=5678`).

Fix: Only strip known tracking parameters (utm_source, utm_medium, utm_campaign, fbclid, gclid, etc.). Preserve other query parameters.

## Fix 7: Verify signals phase runs before analysis and narrative

File: `phases/` directory (after Prompt 8 refactor)

Prompt 8 already placed the signals phase (permits, lobbyists) before analysis in the phase execution order. Verify this is correct by checking `update_dashboard.py` — the order should be:

```
data_collection → discovery → filtering → signals → analysis → reasoning → narrative → verification → finalize
```

If for any reason signals ended up after narrative, move it to position 4 (after filtering, before analysis) to match CLAUDE.md. StatCan permit anomalies and lobbyist signals must be available to inform the Claude analysis calls and the weekly briefing.
