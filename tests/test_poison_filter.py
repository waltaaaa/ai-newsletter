"""
tests/test_poison_filter.py — D-6 commodity poison-filter fallback.

Covers phases.data_collection:
  - _within_poison_bounds rejects wti=1079.5, accepts wti=72
  - _poison_retry_value retry seam with a stubbed fetcher
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phases.data_collection import (
    _POISON_BOUNDS,
    _POISON_RETRY_TICKERS,
    _poison_retry_value,
    _within_poison_bounds,
)


class TestWithinPoisonBounds(unittest.TestCase):
    def test_rejects_scrambled_wti(self):
        self.assertFalse(_within_poison_bounds("wti", 1079.5))

    def test_accepts_plausible_wti(self):
        self.assertTrue(_within_poison_bounds("wti", 72))

    def test_rejects_scrambled_platinum(self):
        self.assertFalse(_within_poison_bounds("platinum", 67))

    def test_rejects_scrambled_soybean_oil(self):
        self.assertFalse(_within_poison_bounds("soybean_oil", 4761.9))

    def test_boundaries_inclusive(self):
        lo, hi = _POISON_BOUNDS["wti"]
        self.assertTrue(_within_poison_bounds("wti", lo))
        self.assertTrue(_within_poison_bounds("wti", hi))

    def test_unbounded_names_always_pass(self):
        self.assertTrue(_within_poison_bounds("tsx_composite", 999999))
        self.assertTrue(_within_poison_bounds("cadusd", 0.73))

    def test_unparseable_value_fails_for_bounded_name(self):
        self.assertFalse(_within_poison_bounds("wti", "n/a"))
        self.assertFalse(_within_poison_bounds("wti", None))

    def test_string_numeric_accepted(self):
        self.assertTrue(_within_poison_bounds("wti", "72.5"))


class TestPoisonRetryValue(unittest.TestCase):
    def test_retry_returns_in_bounds_value(self):
        calls = []

        def fetcher(ticker):
            calls.append(ticker)
            return 75.0

        self.assertEqual(_poison_retry_value("wti", fetcher=fetcher), 75.0)
        self.assertEqual(calls, ["CL=F"])  # one individual retry, right ticker

    def test_retry_still_out_of_bounds_returns_none(self):
        self.assertIsNone(_poison_retry_value("wti", fetcher=lambda t: 1079.5))

    def test_retry_fetch_failure_returns_none(self):
        def fetcher(ticker):
            raise RuntimeError("yfinance down")

        self.assertIsNone(_poison_retry_value("wti", fetcher=fetcher))

    def test_retry_fetch_none_returns_none(self):
        self.assertIsNone(_poison_retry_value("wti", fetcher=lambda t: None))

    def test_no_ticker_skips_fetcher(self):
        # lumber has poison bounds but no yfinance ticker — no retry possible
        self.assertNotIn("lumber", _POISON_RETRY_TICKERS)
        calls = []

        def fetcher(ticker):
            calls.append(ticker)
            return 500.0

        self.assertIsNone(_poison_retry_value("lumber", fetcher=fetcher))
        self.assertEqual(calls, [])

    def test_every_retry_ticker_has_bounds(self):
        # The retry map only makes sense for poison-bounded indicators
        for name in _POISON_RETRY_TICKERS:
            self.assertIn(name, _POISON_BOUNDS)


if __name__ == "__main__":
    unittest.main()
