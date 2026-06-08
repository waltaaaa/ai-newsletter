"""
service_health.py — Global circuit breaker for external API services.

After N consecutive failures, marks a service as dead for the rest of the run.
All service-dependent code checks availability before making calls.

M-5: thresholds expanded to cover groq, claude_cli, anthropic_api,
statcan_wds/statcan_csv, and per-NIM-endpoint health. ServiceHealth.persist()
writes a snapshot to the service_health_history table so trend-over-time
is queryable instead of discarded at run end.
"""

import time
from datetime import datetime


class ServiceHealth:
    def __init__(self):
        self._failures = {}   # service -> consecutive failure count
        self._dead = {}       # service -> (timestamp, reason)
        self._thresholds = {
            # Existing
            "gemini": 3,
            "reddit": 2,
            "wayback": 2,
            "statcan": 3,
            "tavily": 3,
            "searxng": 3,
            "nvidia_nim": 3,
            # M-5: missing-services additions
            "claude_cli":     3,   # `claude -p` subprocess — most common failure
            "groq":           3,   # documented fallback classifier; 429s at 6K TPM
            "anthropic_api":  3,   # active when REASONING_AGENT_MODE=api
            # M-5: split StatCan endpoints (different failure modes)
            "statcan_wds":    3,
            "statcan_csv":    3,
            # M-5: per-NIM-endpoint thresholds = 3 each (shared budget masks
            # independent failures — run log showed Rerank 503 without
            # tripping the shared nvidia_nim breaker).
            "nim_nemotron":   3,
            "nim_deepseek":   3,
            "nim_rerank":     3,
            "nim_embed":      3,
            "nim_ocr":        3,
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
            "failure_counts": dict(self._failures),
        }

    def persist(self, conn, run_id):
        """M-5: write a snapshot of service health to service_health_history.

        Idempotent for a given (run_id, service) — uses INSERT OR REPLACE
        keyed on the composite. The table is created defensively if missing.

        Args:
            conn: sqlite3.Connection
            run_id: pipeline_runs.id from PipelineRunLogger._run_id

        Behaviour: never raises. A persist failure is logged via print but
        never affects the run.
        """
        if conn is None:
            return
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS service_health_history (
                    run_id        INTEGER,
                    service       TEXT,
                    status        TEXT,
                    failure_count INTEGER DEFAULT 0,
                    recorded_at   TEXT,
                    PRIMARY KEY (run_id, service)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_service_health_history_service "
                "ON service_health_history(service)"
            )

            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            # Persist every threshold'd service so trend lines are complete
            # (not just the failing ones).
            all_services = set(self._thresholds.keys()) | set(self._failures.keys()) | set(self._dead.keys())

            with conn:
                for svc in all_services:
                    failure_count = int(self._failures.get(svc, 0) or 0)
                    if svc in self._dead:
                        status = "dead"
                    elif failure_count > 0:
                        status = "degraded"
                    else:
                        status = "ok"
                    conn.execute(
                        """INSERT INTO service_health_history
                               (run_id, service, status, failure_count, recorded_at)
                           VALUES (?, ?, ?, ?, ?)
                           ON CONFLICT(run_id, service) DO UPDATE SET
                               status        = excluded.status,
                               failure_count = excluded.failure_count,
                               recorded_at   = excluded.recorded_at
                        """,
                        (run_id, svc, status, failure_count, now),
                    )
        except Exception as e:
            print(f"  [SERVICE HEALTH] persist failed (non-critical): {e}")


# Module-level singleton — created once per pipeline run via init()
_health = None


def init():
    """Create (or reset) the global ServiceHealth instance. Call at pipeline start."""
    global _health
    _health = ServiceHealth()
    return _health


def get():
    """Return the global ServiceHealth instance, creating if needed."""
    global _health
    if _health is None:
        _health = ServiceHealth()
    return _health
