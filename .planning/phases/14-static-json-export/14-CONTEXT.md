# Phase 14: Static JSON Export - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Build `export_dashboard.py` to read all dashboard data from SQLite via `db.py` and write static JSON files to the output directory. These files represent the complete dataset the frontend needs to render without any database connection. This phase does NOT modify the frontend — it only produces the JSON files that Phase 15 will consume.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions were delegated to Claude. The following areas should be resolved during planning based on the codebase analysis and requirements:

**Output file structure:**
- File organization in docs/data/ (granular per-data-type vs combined files)
- Whether to include a projects_all.json or have the frontend combine per-province files
- Output directory path (docs/data/ vs public/data/ — align with Phase 16 deployment plan)
- Timeseries file strategy (per-ticker vs single bundled file)

**Project filtering logic:**
- How no-value projects are labeled as "unconfirmed" (EXP-03) — inline flag vs separate files
- GDP threshold enforcement per province (EXP-02) — filter at export time
- Which project fields to include/exclude for frontend consumption
- Whether to enforce a per-province project count limit (current frontend uses 5000)

**Pipeline integration:**
- When export runs (every pipeline run vs weekly only) — must satisfy EXP-05
- Error handling strategy (graceful partial export vs atomic all-or-nothing)
- Standalone mode (python export_dashboard.py) vs pipeline-only callable
- Output verbosity / logging level

**Data freshness & size:**
- Whether to include export timestamps (manifest.json, per-file, or none)
- Indicator history depth (full vs rolling window)
- JSON formatting (compact vs readable)
- Briefing archive depth (full content vs metadata-only for older entries)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — user delegated all implementation choices to Claude. Key constraints come from the requirements:
- EXP-01: export_dashboard.py generates all static JSON files from SQLite
- EXP-02: Per-province files respect GDP thresholds
- EXP-03: No-value projects included as "unconfirmed"
- EXP-04: Latest briefing, briefing archive, indicators, trends, events, microscope history all exported
- EXP-05: Export runs as final step of weekly pipeline automatically

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `db.py`: Complete SQLite interface with all query functions needed:
  - `get_projects(conn, province=)` — filters by province, returns full project dicts
  - `get_indicators(conn, category=)` — indicator history with optional category filter
  - `get_briefing_archive(conn, limit=52)` — recent briefings
  - `get_trend_snapshots(conn, limit=12)` — trend analysis snapshots
  - `get_dashboard_state(conn, key)` — key-value store (latest_briefing, microscope_*, etc.)
- `pipeline_config.py`: PROVINCES list with GDP thresholds (13 entries with `threshold_val`)
- `event_calendar.py`: `get_upcoming_events(conn=, days_ahead=14)` — upcoming BoC/StatCan/budget events

### Established Patterns
- JSON serialization: `json.loads(row["field"] or "[]")` for array fields (evidence, statusHistory)
- db.py returns `sqlite3.Row` objects — need dict conversion for JSON export
- Province names match between `pipeline_config.PROVINCES[*]["name"]` and project `province` field
- Duck-typing pattern: `hasattr(conn, 'execute')` for backward compat (not needed in new code)

### Integration Points
- `update_dashboard.py` — final step insertion point (after all discovery/analysis/briefing steps)
- `docs/data/` — output directory (created by this phase, served by Phase 16 via GitHub Pages)
- `public/js/app.js` — current frontend loads from 7 Firestore collections; Phase 15 will rewrite to fetch these JSON files

### Frontend Data Dependencies (from app.js Firestore queries)
1. `newsletters` collection — briefing content by ID, archive list (ordered by updated_at desc, limit 30)
2. `statcan_indicators/latest` — single doc with latest StatCan indicator values
3. `projects` — by province (two queries: code + full name), or all (limit 5000, ordered by lastSeen desc)
4. `timeseries/{ticker}` — per-ticker commodity/market data (cached client-side)
5. `indicator_history` — time series filtered by indicator name, ordered by date
6. `dashboard_state/latest_briefing` — latest briefing metadata + trend report
7. `missed_projects` — addDoc for user submissions (handled by Phase 17, not export)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-static-json-export*
*Context gathered: 2026-03-08*
