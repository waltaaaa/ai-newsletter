"""
tests/test_statcan_retrieval.py — 2026-06-11 data-retrieval fixes.

Covers:
  statcan_extended:
    - _is_fresh freshness gate by frequency
    - _normalize_obs_value scalar normalization per unit
    - _resolve_coordinate member-name matching (exact > prefix, loud abort
      on unmatched dimensions, naming-variant tolerance)
  phases.data_collection:
    - _norm_ref_period reference-period normalization
    - _fmt_indicator_change pp-vs-percent change convention
    - _archive_indicators_to_history stamps refPer (not run date), carries
      previous_value, and never saves _src/_date/_prev metadata as series
"""

import os
import sys
import types
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# phases.data_collection imports rss_monitor (feedparser) at module level;
# none of the functions under test touch RSS. Stub it when feedparser is
# unavailable so these tests stay runnable in minimal sandboxes.
try:
    import feedparser  # noqa: F401
except ImportError:
    sys.modules.setdefault("rss_monitor", types.ModuleType("rss_monitor"))

from statcan_extended import _is_fresh, _normalize_obs_value, _resolve_coordinate
from phases.data_collection import (
    _archive_indicators_to_history,
    _fmt_indicator_change,
    _norm_ref_period,
)


class TestIsFresh(unittest.TestCase):
    def test_recent_monthly_obs_is_fresh(self):
        recent = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
        self.assertTrue(_is_fresh(recent, "monthly"))

    def test_old_monthly_obs_is_stale(self):
        old = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        self.assertFalse(_is_fresh(old, "monthly"))

    def test_quarterly_window_is_wider(self):
        obs = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        self.assertTrue(_is_fresh(obs, "quarterly"))

    def test_frozen_2003_vector_is_stale(self):
        # The D-15 failure mode: agri_exports frozen at 2003 must never pass
        self.assertFalse(_is_fresh("2003-12-01", "monthly"))

    def test_garbage_refper_is_stale(self):
        self.assertFalse(_is_fresh("", "monthly"))
        self.assertFalse(_is_fresh("not-a-date", "monthly"))


class TestNormalizeObsValue(unittest.TestCase):
    def test_dollar_thousands_to_millions(self):
        # Permits cube reports x1,000 $ (scalar 3): 5,200,000 (k$) -> 5,200 $M
        self.assertAlmostEqual(_normalize_obs_value(5_200_000, 3, "$M"), 5_200_000 * 1000 / 1e6)

    def test_persons_thousands_passthrough(self):
        # LFS employment with scalar 3 is already "thousands of persons"
        self.assertAlmostEqual(_normalize_obs_value(1657.4, 3, "thousands"), 1657.4)

    def test_units_scaled(self):
        self.assertAlmostEqual(_normalize_obs_value(575.2, 3, "units"), 575_200)

    def test_rates_unscaled(self):
        self.assertAlmostEqual(_normalize_obs_value(65.0, 0, "%"), 65.0)
        self.assertAlmostEqual(_normalize_obs_value(36.5, 0, "$/hr"), 36.5)

    def test_bad_scalar_code_defaults_to_identity(self):
        self.assertAlmostEqual(_normalize_obs_value(65.0, None, "%"), 65.0)


def _cube_meta(dims):
    """dims: list of (dimension_name, [member names])"""
    return {
        "dimension": [
            {
                "dimensionNameEn": name,
                "member": [
                    {"memberId": i + 1, "memberNameEn": m}
                    for i, m in enumerate(members)
                ],
            }
            for name, members in dims
        ]
    }


_LFS_META = _cube_meta([
    ("Geography", ["Canada", "Newfoundland and Labrador", "Ontario"]),
    ("Labour force characteristics",
     ["Labour force", "Employment", "Full-time employment", "Employment rate",
      "Unemployment", "Unemployment rate", "Participation rate"]),
    ("North American Industry Classification System (NAICS)",
     ["Total, all industries", "Agriculture [111-112, 1100, 1151-1152]",
      "Utilities [22]", "Retail trade [44-45]",
      "Other services (except public administration) [81]",
      "Public administration [91]"]),
    ("Gender", ["Total - Gender", "Men+", "Women+"]),
    ("Age group", ["15 years and over", "15 to 24 years"]),
])


class TestResolveCoordinate(unittest.TestCase):
    def test_resolves_utilities_employment(self):
        patterns = ["Canada", "Employment", "Both sexes", "Total - Gender",
                    "15 years and over", "Utilities"]
        coord, unmatched = _resolve_coordinate(_LFS_META, patterns)
        self.assertEqual(unmatched, [])
        self.assertEqual(coord, "1.2.3.1.1.0.0.0.0.0")

    def test_exact_match_beats_prefix(self):
        # "Employment" must pick the exact "Employment" member, not
        # prefix-match "Employment rate"
        patterns = ["Canada", "Employment", "Total - Gender",
                    "15 years and over", "Total, all industries"]
        coord, unmatched = _resolve_coordinate(_LFS_META, patterns)
        self.assertEqual(unmatched, [])
        self.assertEqual(coord.split(".")[1], "2")

    def test_prefix_does_not_cross_match_public_admin(self):
        # "Public administration" must not match "Other services (except
        # public administration)" — prefix matching is anchored at the start
        patterns = ["Canada", "Employment", "Total - Gender",
                    "15 years and over", "Public administration"]
        coord, unmatched = _resolve_coordinate(_LFS_META, patterns)
        self.assertEqual(unmatched, [])
        self.assertEqual(coord.split(".")[2], "6")

    def test_naming_variant_tolerance(self):
        # Spec carries both "Both sexes" and "Total - Gender"; the unused
        # variant must not break resolution
        patterns = ["Canada", "Employment", "Both sexes", "Total - Gender",
                    "15 years and over", "Retail trade"]
        coord, unmatched = _resolve_coordinate(_LFS_META, patterns)
        self.assertEqual(unmatched, [])
        self.assertEqual(coord.split(".")[3], "1")

    def test_unmatched_dimension_aborts(self):
        patterns = ["Canada", "Employment", "15 years and over", "Utilities"]
        coord, unmatched = _resolve_coordinate(_LFS_META, patterns)
        self.assertIsNone(coord)
        self.assertIn("Gender", unmatched)

    def test_coordinate_padded_to_ten_positions(self):
        meta = _cube_meta([("Geography", ["Canada"]),
                           ("Statistics", ["Job vacancies", "Payroll employees"])])
        coord, unmatched = _resolve_coordinate(meta, ["Canada", "Job vacancies"])
        self.assertEqual(unmatched, [])
        self.assertEqual(coord, "1.1.0.0.0.0.0.0.0.0")


class TestNormRefPeriod(unittest.TestCase):
    def test_full_date_passthrough(self):
        self.assertEqual(_norm_ref_period("2026-05-01"), "2026-05-01")

    def test_year_month_padded(self):
        self.assertEqual(_norm_ref_period("2026-05"), "2026-05-01")

    def test_garbage_returns_none(self):
        self.assertIsNone(_norm_ref_period(""))
        self.assertIsNone(_norm_ref_period(None))
        self.assertIsNone(_norm_ref_period("May 2026"))


class TestFmtIndicatorChange(unittest.TestCase):
    def test_rate_values_get_pp(self):
        self.assertEqual(_fmt_indicator_change("65.0%", "64.9%"), "+0.1pp")

    def test_levels_get_percent(self):
        self.assertEqual(_fmt_indicator_change("279,317", "270,000"), "+3.5%")

    def test_missing_prev_returns_none(self):
        self.assertIsNone(_fmt_indicator_change("65.0%", None))
        self.assertIsNone(_fmt_indicator_change("65.0%", "N/A"))


class TestArchiveIndicatorsToHistory(unittest.TestCase):
    def _run_archive(self, primary_ind):
        saved = []
        with mock.patch("phases.data_collection.save_indicator",
                        side_effect=lambda conn, d: saved.append(d)):
            _archive_indicators_to_history(conn=None, primary_ind=primary_ind)
        return saved

    def test_national_period_is_reference_period_not_today(self):
        saved = self._run_archive({
            "national": {
                "values": {"participationRate": "65.0%"},
                "prev_values": {"participationRate": "64.9%"},
                "obs_dates": {"participationRate": "2026-05-01"},
                "sources": {"participationRate": "StatCan"},
            },
        })
        rec = next(d for d in saved if d["indicator"] == "participationRate")
        self.assertEqual(rec["date"], "2026-05-01")
        self.assertEqual(rec["previous_value"], "64.9%")
        self.assertEqual(rec["change"], "+0.1pp")
        self.assertEqual(rec["source_meta"]["reference_period"], "2026-05-01")

    def test_provincial_metadata_fields_not_saved_as_series(self):
        saved = self._run_archive({
            "provinces": {
                "Alberta": {
                    "participationRate": "69.1%",
                    "participationRate_src": "StatCan",
                    "participationRate_date": "2026-05-01",
                    "participationRate_prev": "69.3%",
                },
            },
        })
        names = [d["indicator"] for d in saved]
        self.assertEqual(names, ["participationRate"])
        rec = saved[0]
        self.assertEqual(rec["date"], "2026-05-01")
        self.assertEqual(rec["previous_value"], "69.3%")
        self.assertEqual(rec["change"], "-0.2pp")

    def test_missing_obs_date_skips_row(self):
        # Invariant: stamp the StatCan REFERENCE period, never the fetch date.
        # A row with no determinable reference period must be skipped, not
        # stamped with today (the forbidden run-date mis-stamping).
        saved = self._run_archive({
            "national": {
                "values": {"housingStarts": "279,317"},
                "sources": {"housingStarts": "CMHC"},
            },
        })
        self.assertEqual(saved, [])


if __name__ == "__main__":
    unittest.main()
