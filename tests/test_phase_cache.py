"""
tests/test_phase_cache.py — E-2 phase-level cache TTL helpers.

Covers pipeline_cache.phase_cache_key / phase_cache_fresh / phase_cache_ttl_hours:
  - fresh-within-TTL payload accepted
  - expired payload rejected
  - missing _completed_at rejected (forces re-run)
Pure functions — no DB, no update_dashboard import.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline_cache import (
    PHASE_CACHE_TTL_HOURS_DEFAULT,
    phase_cache_fresh,
    phase_cache_key,
    phase_cache_ttl_hours,
)


def _payload(hours_ago: float, **extra) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    d = {"_completed": True, "_completed_at": ts.isoformat(), "some_key": "value"}
    d.update(extra)
    return d


class TestPhaseCacheKey(unittest.TestCase):
    def test_key_is_stable_and_date_free(self):
        key = phase_cache_key("Phase 1: Data Collection")
        self.assertEqual(key, "phase_cache_Phase_1:_Data_Collection")
        # Same input always yields the same key (no run-date component)
        self.assertEqual(key, phase_cache_key("Phase 1: Data Collection"))
        # No ISO date embedded
        self.assertNotRegex(key, r"\d{4}-\d{2}-\d{2}")

    def test_distinct_phases_get_distinct_keys(self):
        self.assertNotEqual(
            phase_cache_key("Phase 1: Data Collection"),
            phase_cache_key("Phase 2: Discovery"),
        )


class TestPhaseCacheFresh(unittest.TestCase):
    def test_fresh_within_ttl_accepted(self):
        self.assertTrue(phase_cache_fresh(_payload(hours_ago=1), ttl_hours=24))

    def test_just_inside_ttl_accepted(self):
        self.assertTrue(phase_cache_fresh(_payload(hours_ago=23.5), ttl_hours=24))

    def test_expired_rejected(self):
        self.assertFalse(phase_cache_fresh(_payload(hours_ago=25), ttl_hours=24))

    def test_missing_completed_at_rejected(self):
        payload = {"_completed": True, "some_key": "value"}
        self.assertFalse(phase_cache_fresh(payload, ttl_hours=24))

    def test_missing_completed_flag_rejected(self):
        payload = {"_completed_at": datetime.now(timezone.utc).isoformat()}
        self.assertFalse(phase_cache_fresh(payload, ttl_hours=24))

    def test_garbage_timestamp_rejected(self):
        self.assertFalse(
            phase_cache_fresh(_payload(hours_ago=1, _completed_at="not-a-date"),
                              ttl_hours=24))

    def test_non_dict_rejected(self):
        self.assertFalse(phase_cache_fresh(None, ttl_hours=24))
        self.assertFalse(phase_cache_fresh("cached", ttl_hours=24))

    def test_naive_utc_timestamp_accepted(self):
        # Tolerate a naive (no-tz) UTC ISO stamp
        ts = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        payload = {"_completed": True, "_completed_at": ts}
        self.assertTrue(phase_cache_fresh(payload, ttl_hours=24))

    def test_custom_short_ttl(self):
        payload = _payload(hours_ago=2)
        self.assertFalse(phase_cache_fresh(payload, ttl_hours=1))
        self.assertTrue(phase_cache_fresh(payload, ttl_hours=3))


class TestPhaseCacheTtlEnv(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("PHASE_CACHE_TTL_HOURS", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["PHASE_CACHE_TTL_HOURS"] = self._saved
        else:
            os.environ.pop("PHASE_CACHE_TTL_HOURS", None)

    def test_default_when_env_unset(self):
        self.assertEqual(phase_cache_ttl_hours(), PHASE_CACHE_TTL_HOURS_DEFAULT)

    def test_env_override(self):
        os.environ["PHASE_CACHE_TTL_HOURS"] = "6"
        self.assertEqual(phase_cache_ttl_hours(), 6.0)

    def test_invalid_env_falls_back_to_default(self):
        os.environ["PHASE_CACHE_TTL_HOURS"] = "banana"
        self.assertEqual(phase_cache_ttl_hours(), PHASE_CACHE_TTL_HOURS_DEFAULT)
        os.environ["PHASE_CACHE_TTL_HOURS"] = "-4"
        self.assertEqual(phase_cache_ttl_hours(), PHASE_CACHE_TTL_HOURS_DEFAULT)

    def test_fresh_uses_env_ttl_when_not_passed(self):
        os.environ["PHASE_CACHE_TTL_HOURS"] = "1"
        self.assertFalse(phase_cache_fresh(_payload(hours_ago=2)))
        os.environ["PHASE_CACHE_TTL_HOURS"] = "48"
        self.assertTrue(phase_cache_fresh(_payload(hours_ago=2)))


if __name__ == "__main__":
    unittest.main()
