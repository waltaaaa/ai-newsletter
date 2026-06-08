"""
pipeline_logging.py — Structured pipeline run logging to SQLite via db.py.

Tracks step completion, errors, discovery metrics, and API usage
for every pipeline run in the `pipeline_runs` table.
"""

import json
import logging
from datetime import datetime

from db import get_db, save_pipeline_run, update_pipeline_run

logger = logging.getLogger(__name__)


class PipelineRunLogger:
    """Logs structured pipeline run data to SQLite `pipeline_runs` table.

    Usage:
        from db import init_db
        conn = init_db()
        run_log = PipelineRunLogger(conn=conn, run_type="weekly")
        run_log.start()
        try:
            # ... pipeline steps ...
            run_log.log_step("step_1_hard_data")
            run_log.log_step("tier_2_google_news")
            run_log.log_metric("discovery", "articles_found", 47)
            run_log.finalize("success")
        except Exception as e:
            run_log.log_error("step_name", e)
            run_log.finalize("error")
    """

    def __init__(self, conn=None, run_type="weekly"):
        """Initialize logger.

        Args:
            conn: sqlite3.Connection from get_db() or init_db().
                  If None, a new connection is obtained via get_db().
            run_type: Pipeline run type label (e.g. "weekly", "manual").
        """
        self._conn = conn if conn is not None else get_db()
        self._run_type = run_type
        self._run_id = None
        self._started_at = None
        self._steps_completed = []
        self._errors = []
        # M-1: severity-aware error buckets. Only _errors_critical demotes the run.
        self._errors_critical = []
        self._discovery = {
            "articles_found": 0,
            "projects_added": 0,
            "projects_updated": 0,
            "projects_deduped": 0,
        }
        self._api_usage = {
            "tavily_searches": 0,
            "claude_sonnet_calls": 0,
            "claude_sonnet_input_tokens": 0,
            "claude_sonnet_output_tokens": 0,
        }
        self._active = False

    def start(self):
        """Create the run record in SQLite with status 'running'.

        Also cleans up any orphaned 'running' records from crashed runs
        (older than 4 hours).
        """
        # Clean up orphaned records from previous crashed runs
        try:
            self._conn.execute(
                "UPDATE pipeline_runs SET status='crashed', "
                "completed_at=datetime('now') "
                "WHERE status='running' AND started_at < datetime('now', '-4 hours')"
            )
            self._conn.commit()
        except Exception as e:
            logger.warning(f"Failed to clean up orphaned pipeline runs: {e}")

        self._started_at = datetime.utcnow()
        self._steps_completed = []
        self._errors = []
        self._errors_critical = []
        self._discovery = {
            "articles_found": 0,
            "projects_added": 0,
            "projects_updated": 0,
            "projects_deduped": 0,
        }
        self._api_usage = {
            "tavily_searches": 0,
            "claude_sonnet_calls": 0,
            "claude_sonnet_input_tokens": 0,
            "claude_sonnet_output_tokens": 0,
        }

        doc_data = {
            "type": self._run_type,
            "status": "running",
            "started_at": self._started_at.isoformat(),
            "completed_at": "",
            "duration_seconds": 0,
            "steps_completed": [],
            "errors": [],
            "discovery": self._discovery,
            "api_usage": self._api_usage,
        }

        try:
            self._run_id = save_pipeline_run(self._conn, doc_data)
            self._active = True
            print(f"  [LOG] Run logging started: run_id={self._run_id}")
        except Exception as e:
            logger.warning(f"Failed to create run log record: {e}")
            self._active = False

    def __enter__(self):
        """Context manager entry — calls start()."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — guarantees finalize() is called."""
        if exc_type is not None:
            # Uncaught exception escaped the with-block → pipeline-halting
            self.log_error("pipeline", exc_val or Exception("unknown"),
                           recovered=False, severity="critical")
            self.finalize("error")
        elif not self._run_id:
            pass  # start() failed, nothing to finalize
        else:
            # finalize() may have already been called explicitly
            # Only auto-finalize if still in 'running' state
            pass
        return False  # Don't suppress exceptions

    def log_step(self, step_name, status=None, detail=None):
        """Record a completed pipeline step.

        Args:
            step_name: Name of the pipeline step.
            status: Optional status string (ignored — kept for call-site compat).
            detail: Optional detail string (ignored — kept for call-site compat).
        """
        self._steps_completed.append(step_name)
        if self._active and self._run_id is not None:
            try:
                update_pipeline_run(self._conn, self._run_id, {
                    "steps_completed": json.dumps(self._steps_completed),
                })
            except Exception as e:
                logger.warning(f"Failed to log step {step_name}: {e}")

    def log_error(self, step, exception, recovered=True, severity="warn"):
        """Record an error that occurred during a step.

        Args:
            step: Pipeline step name where the error occurred.
            exception: The exception instance.
            recovered: Whether the pipeline recovered and continued.
            severity: One of "info", "warn", "critical". Only "critical" demotes
                a run to "partial" at finalize time. "warn" results in
                "degraded" (M-1). Defaults to "warn" to preserve old behavior
                of getting visibility without blocking.
        """
        if severity not in ("info", "warn", "critical"):
            logger.warning(f"log_error: unknown severity {severity!r}; treating as 'warn'")
            severity = "warn"
        error_entry = {
            "step": step,
            "error_type": type(exception).__name__,
            "message": str(exception)[:500],
            "recovered": recovered,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if severity == "critical":
            self._errors_critical.append(error_entry)
        else:
            self._errors.append(error_entry)
        if self._active and self._run_id is not None:
            try:
                # Persist both buckets via the existing 'errors' column.
                # Critical first so a reader sees blockers up top.
                combined = self._errors_critical + self._errors
                update_pipeline_run(self._conn, self._run_id, {
                    "errors": json.dumps(combined),
                })
            except Exception as e:
                logger.warning(f"Failed to log error for {step}: {e}")

    def log_metric(self, category, key, value):
        """Set a metric value in the in-memory dict and persist to SQLite.

        Args:
            category: "discovery" or "api_usage"
            key: metric name (e.g., "articles_found", "tavily_searches")
            value: value to set (int)
        """
        if category == "discovery":
            self._discovery[key] = value
            payload = self._discovery
        elif category == "api_usage":
            self._api_usage[key] = value
            payload = self._api_usage
        else:
            logger.warning(f"Unknown metric category: {category}")
            return

        if self._active and self._run_id is not None:
            try:
                update_pipeline_run(self._conn, self._run_id, {
                    category: json.dumps(payload),
                })
            except Exception as e:
                logger.warning(f"Failed to log metric {category}.{key}: {e}")

    def increment_metric(self, category, key, amount=1):
        """Increment a numeric metric counter.

        Args:
            category: "discovery" or "api_usage"
            key: metric name
            amount: amount to increment by (default 1)
        """
        if category == "discovery":
            self._discovery[key] = self._discovery.get(key, 0) + amount
            payload = self._discovery
        elif category == "api_usage":
            self._api_usage[key] = self._api_usage.get(key, 0) + amount
            payload = self._api_usage
        else:
            logger.warning(f"Unknown metric category: {category}")
            return

        if self._active and self._run_id is not None:
            try:
                update_pipeline_run(self._conn, self._run_id, {
                    category: json.dumps(payload),
                })
            except Exception as e:
                logger.warning(f"Failed to increment {category}.{key}: {e}")

    def finalize(self, status="success"):
        """Finalize the run log with completion data.

        Args:
            status: "success", "error", "partial", "degraded", or "crashed".
        """
        completed_at = datetime.utcnow()
        duration = (
            (completed_at - self._started_at).total_seconds()
            if self._started_at else 0
        )

        # M-1: severity-aware demotion.
        # CRITICAL errors → partial (true pipeline-blockers; conductor died,
        # validator FAIL, etc.).
        if status == "success" and self._errors_critical:
            status = "partial"
        # WARN errors → degraded (scraper 404s, SSL flakes; briefing still ships)
        if status == "success" and self._errors:
            status = "degraded"

        total_err = len(self._errors_critical) + len(self._errors)
        if self._active and self._run_id is not None:
            try:
                update_pipeline_run(self._conn, self._run_id, {
                    "status": status,
                    "completed_at": completed_at.isoformat(),
                    "duration_seconds": int(duration),
                })
                print(
                    f"  [LOG] Run finalized: {status} ({int(duration)}s, "
                    f"{len(self._steps_completed)} steps, "
                    f"{len(self._errors_critical)} critical / "
                    f"{len(self._errors)} warn)"
                )
            except Exception as e:
                logger.warning(f"Failed to finalize run log: {e}")
        else:
            print(
                f"  [LOG] Run complete (no SQLite): {status} ({int(duration)}s, "
                f"{len(self._steps_completed)} steps, "
                f"{len(self._errors_critical)} critical / "
                f"{len(self._errors)} warn)"
            )
