I need you to fix the pipeline's error handling. These changes make the difference between a crash losing all work vs. graceful degradation.

## Fix 1: Break the mega try/except into per-step isolation

File: `update_dashboard.py` lines ~3128-4155

The entire pipeline body is wrapped in a single try/except. If ANY late step crashes (Wayback archiving, quality report, anything), ALL remaining steps are skipped — including JSON export and deployment. Hours of work is lost.

Fix: Refactor so each major step has its own try/except. The pattern should be:

```python
steps = [
    ("Hard Data", step_hard_data),
    ("Discovery", step_discovery),
    ("Claude Analysis", step_claude_analysis),
    # ... etc
]

for step_name, step_fn in steps:
    try:
        step_fn(context)
        logger.log_step(step_name, "success")
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        # Continue to next step — don't abort
```

Critical steps (like export and deploy) should ALWAYS run even if earlier non-critical steps fail. The only steps that should abort the pipeline are: if hard data fetch fails completely, or if the export/deploy step itself fails.

## Fix 2: Orphaned "running" pipeline records

File: `pipeline_logging.py` lines ~94-100

If the pipeline crashes before `finalize()` is called, the pipeline_runs record stays as `status='running'` permanently.

Fix: At the start of each pipeline run, add a cleanup query:
```python
UPDATE pipeline_runs SET status='crashed', ended=datetime('now') 
WHERE status='running' AND started < datetime('now', '-4 hours')
```

Also wrap the pipeline execution in a context manager or try/finally that guarantees `finalize()` is called.

## Fix 3: Bare wayback import crashes pipeline

File: `update_dashboard.py` line ~3581

The `wayback` import is not wrapped in try/except, unlike every other late import. If the module has an import error, the pipeline crashes after completing all discovery and analysis.

Fix: Wrap it in try/except like the other imports:
```python
try:
    import wayback
except ImportError:
    wayback = None
    print("[WARN] wayback module not available, skipping archival")
```

## Fix 4: Add Claude 429 retry logic

File: `claude_reasoning.py`

Gemini has retry logic for 429 rate limits. Claude has none — a 429 returns None with no retry.

Fix: Add retry logic with exponential backoff for 429 responses. 4 retries, starting at 30 seconds (Claude rate limits are typically longer than Gemini's). Use the same pattern already established for Gemini retries.

## Fix 5: Replace bare `except: pass` blocks

File: `update_dashboard.py` (many locations throughout)

There are dozens of bare `except: pass` blocks, especially around indicator parsing. These hide API format changes — if StatCan or BoC changes their response format, the pipeline returns empty data with zero signal.

Fix: Search for all `except:` and `except Exception:` blocks that use `pass` or do nothing. Replace each with:
```python
except Exception as e:
    print(f"[WARN] {description}: {e}")
```

Where `description` is a brief label for what was being attempted. Do NOT change the control flow (still continue on error) — just make failures visible in the logs.
