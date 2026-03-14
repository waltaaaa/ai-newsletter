"""
service_health.py — Global circuit breaker for external API services.

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
            "failure_counts": dict(self._failures),
        }


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
