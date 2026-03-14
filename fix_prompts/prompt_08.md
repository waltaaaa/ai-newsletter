I need you to refactor `update_dashboard.py` from a ~4150-line monolith into a phase-based architecture. This is the biggest structural change — read the entire file first to understand the execution flow before making changes.

## New directory structure

Create a `phases/` directory with these files:

```
phases/
  __init__.py
  data_collection.py    # Current Steps 1, 1b
  discovery.py          # Current Tiers 1-14
  filtering.py          # RSS filter, dedup, URL hard gate
  signals.py            # Permits, lobbyists (current Step 2G) — MUST run before analysis
  analysis.py           # Claude calls 1-4, hard data override
  reasoning.py          # Gap analysis, dedup QA, extraction recovery, meta-analysis
  narrative.py          # Trends, market commentary, events, microscope, briefing
  verification.py       # Source verification, Wayback archival
  finalize.py           # Timeseries append, assembly, quality report, export, deploy
```

## Each phase file follows this pattern:

```python
"""Phase N: Description"""
import traceback

def run(conn, context, logger):
    """
    Args:
        conn: SQLite connection
        context: dict with shared state (health, config, intermediate results)
        logger: PipelineRunLogger instance
    Returns:
        dict of outputs this phase produces (stored in context for later phases)
    """
    step_name = "Phase N: Description"
    try:
        # ... phase logic extracted from update_dashboard.py ...
        logger.log_step(step_name, "success")
        return {"key_output": value}
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
```

## The new `update_dashboard.py` orchestrator (~200-300 lines):

**IMPORTANT:** The phase order below matches CLAUDE.md exactly. Signals (permits, lobbyists) run BEFORE analysis so their output can inform the Claude analysis calls and the weekly briefing.

```python
"""Signal Dispatch — Pipeline Orchestrator"""
from phases import (
    data_collection, discovery, filtering, signals, analysis,
    reasoning, narrative, verification, finalize
)
from service_health import ServiceHealth
from pipeline_logging import PipelineRunLogger
import db

def run_pipeline(mode="weekly"):
    conn = db.get_connection()
    logger = PipelineRunLogger(conn)
    logger.start()
    
    context = {
        "health": ServiceHealth(),
        "mode": mode,
        "run_id": logger.run_id,
    }
    
    # Phase order per CLAUDE.md — signals BEFORE analysis
    phases = [
        data_collection,   # Phase 1: Hard data from APIs
        discovery,         # Phase 2: Tiers 1-14
        filtering,         # Phase 3: RSS filter, dedup, URL hard gate
        signals,           # Phase 4: Permits, lobbyists
        analysis,          # Phase 5: Claude calls 1-4, hard data override
        reasoning,         # Phase 6: Gap analysis, dedup QA, meta-analysis
        narrative,         # Phase 7: Trends, commentary, briefing
        verification,      # Phase 8: Source verification, Wayback
        finalize,          # Phase 9: Assembly, export, deploy
    ]
    
    if mode == "indicators-only":
        phases = [data_collection, finalize]
    
    try:
        for phase in phases:
            result = phase.run(conn, context, logger)
            context.update(result or {})
    finally:
        logger.finalize(context.get("status", "completed"))
        conn.close()

if __name__ == "__main__":
    import sys
    mode = "weekly"
    if "--indicators-only" in sys.argv:
        mode = "indicators-only"
    elif "--deep-sweep" in sys.argv:
        mode = "deep-sweep"
    elif "--seed-projects" in sys.argv:
        mode = "seed-projects"
    elif "--test-feeds" in sys.argv:
        mode = "test-feeds"
    run_pipeline(mode)
```

## Important:
- Extract the logic from update_dashboard.py into the phase files — don't rewrite it. Copy the existing code blocks into their respective phase files.
- Each phase should checkpoint its key outputs (especially Claude responses) to the DB immediately.
- The `context` dict replaces the current pattern of passing data through local variables in the monolith.
- Make sure the `--indicators-only`, `--deep-sweep`, `--seed-projects`, and `--test-feeds` flags still work correctly.
- Keep `update_dashboard.py` as the entry point — just make it thin.

After extraction, verify that the CLI flags in the CLAUDE.md still map to the correct behavior.
