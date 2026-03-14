I need you to add two new infrastructure patterns to the pipeline: a circuit breaker for external services, and checkpointing for Claude API calls.

## Part 1: Circuit Breaker

Create a new file `service_health.py`:

```python
"""
Global circuit breaker for external API services.
After N consecutive failures, marks a service as dead for the rest of the run.
All service-dependent code checks availability before making calls.
"""
import time

class ServiceHealth:
    def __init__(self):
        self._failures = {}   # service -> consecutive failure count
        self._dead = {}       # service -> (timestamp, reason)
        self._thresholds = {
            "gemini": 3,
            "reddit": 2,
            "wayback": 2,
            "statcan": 3,
            "tavily": 3,
        }
    
    def record_failure(self, service, reason=""):
        count = self._failures.get(service, 0) + 1
        self._failures[service] = count
        threshold = self._thresholds.get(service, 3)
        if count >= threshold:
            self._dead[service] = (time.time(), reason)
            print(f"[CIRCUIT BREAKER] {service} marked dead after {count} failures: {reason}")
    
    def record_success(self, service):
        self._failures[service] = 0
    
    def is_available(self, service):
        return service not in self._dead
    
    def get_status(self):
        return {
            "dead": {k: v[1] for k, v in self._dead.items()},
            "failure_counts": dict(self._failures)
        }
```

Then integrate it:
1. In `update_dashboard.py`, create a `ServiceHealth()` instance at the start of the pipeline run
2. Pass it to (or make it importable by) `gemini_engine.py`, `sentiment.py`, `wayback.py`, `enrichment_queries.py`, and any other module that calls external APIs
3. In `gemini_engine.py`: before every Gemini call, check `health.is_available("gemini")`. On 429 or connection errors, call `health.record_failure("gemini", "429 RESOURCE_EXHAUSTED")`. On success, call `health.record_success("gemini")`
4. In `wayback.py`: same pattern with `health.is_available("wayback")`
5. In `sentiment.py` (Reddit calls): same pattern with `health.is_available("reddit")`
6. Write the final health status to the pipeline_runs log

## Part 2: Claude Checkpointing

File: `db.py` — add a new table:

```sql
CREATE TABLE IF NOT EXISTS claude_checkpoints (
    run_id    TEXT NOT NULL,
    call_name TEXT NOT NULL,
    response  TEXT,
    cost_usd  REAL DEFAULT 0,
    created   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, call_name)
);
```

Add helper functions `save_checkpoint(conn, run_id, call_name, response, cost)` and `get_checkpoint(conn, run_id, call_name)`.

Then in `update_dashboard.py` (or wherever Claude calls are orchestrated):
- After each successful Claude API call (calls 1-4, briefing, market commentary, etc.), immediately save the raw response to the checkpoint table
- Before making a Claude call, check if a checkpoint already exists for this run_id + call_name. If so, use the cached response instead of re-calling (this enables resume-after-crash)
- The run_id should be the pipeline_runs ID for the current run

## Part 3: Fix Claude JSON truncation

File: `update_dashboard.py` or wherever `max_tokens` is set for Claude calls 2 and 3

Both calls hit exactly 10,000 output tokens on every attempt, causing truncation. The responses need ~12,000-15,000 tokens to complete.

Fix:
1. Increase `max_tokens` to 16384 for call2-industries and call3-provinces
2. Add a truncation detection check: after receiving a response, check if it ends with valid JSON closure (ends with `}` or `]` after stripping whitespace). If not, log it as "truncated response" rather than "JSON parse error" — and if retrying, increase max_tokens by 4096 for the retry
3. For JSON repair fallback: try Claude Haiku first (cheap, always available), then Gemini only if Haiku fails and Gemini is available via the circuit breaker
