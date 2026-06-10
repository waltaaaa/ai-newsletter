"""Tests for geo_lookup.py (G11) — normalizer cases, CSD lookup via a small
fixture dict, CMA fallback, province fallback. The full
config/geo_municipalities.json is NOT loaded (fixture dict injected via the
_data parameter), so these tests stay fast and data-file independent."""
import pytest

from geo_lookup import (
    CMA_CENTROIDS,
    PROVINCE_CENTROIDS,
    lookup,
    norm_province,
    normalize_place,
)

FIXTURE = {
    "montreal|QC": {"lat": 45.53262, "lon": -73.61655, "csduid": "2466023"},
    "st johns|NL": {"lat": 47.55449, "lon": -52.74125, "csduid": "1001519"},
    "fort saskatchewan|AB": {"lat": 53.68789, "lon": -113.23524,
                             "csduid": "4811056"},
}


class TestNormalizePlace:
    def test_accents_stripped(self):
        assert normalize_place("Montréal") == "montreal"
        assert normalize_place("Trois-Rivières") == "trois rivieres"

    def test_case_insensitive(self):
        assert normalize_place("MONTREAL") == normalize_place("montreal")

    def test_apostrophes_removed_not_spaced(self):
        assert normalize_place("St. John's") == "st johns"

    def test_curly_apostrophe(self):
        assert normalize_place("St. John’s") == "st johns"

    def test_whitespace_and_punctuation_collapsed(self):
        assert normalize_place("  Sault   Ste.  Marie ") == "sault ste marie"

    def test_empty(self):
        assert normalize_place("") == ""
        assert normalize_place(None) == ""


class TestNormProvince:
    def test_two_letter_codes_pass_through(self):
        assert norm_province("qc") == "QC"
        assert norm_province("ON") == "ON"

    def test_full_names(self):
        assert norm_province("Quebec") == "QC"
        assert norm_province("Québec") == "QC"
        assert norm_province("Newfoundland and Labrador") == "NL"
        assert norm_province("northwest territories") == "NT"

    def test_unknown(self):
        assert norm_province("Atlantis") == ""
        assert norm_province("") == ""


class TestLookupExactCsd:
    def test_exact_match(self):
        r = lookup("Montréal", "Quebec", _data=FIXTURE)
        assert r["source"] == "csd"
        assert r["csduid"] == "2466023"
        assert r["lat"] == pytest.approx(45.53262)

    def test_accent_and_case_variants_hit_same_entry(self):
        a = lookup("montreal", "QC", _data=FIXTURE)
        b = lookup("MONTRÉAL", "qc", _data=FIXTURE)
        assert a == b

    def test_apostrophe_name(self):
        r = lookup("St. John's", "NL", _data=FIXTURE)
        assert r["csduid"] == "1001519"


class TestLookupCmaFallback:
    def test_falls_back_to_cma_centroid(self):
        # Toronto is not in the fixture dict but IS a hardcoded CMA centroid
        r = lookup("Toronto", "ON", _data=FIXTURE)
        assert r["source"] == "cma"
        assert r["csduid"] is None
        assert r["lat"] == pytest.approx(CMA_CENTROIDS[("toronto", "ON")][0])

    def test_cma_requires_matching_province(self):
        r = lookup("Toronto", "SK", _data=FIXTURE)
        assert r["source"] == "province"  # no Toronto, SK — falls through


class TestLookupProvinceFallback:
    def test_unknown_municipality_falls_back_to_province(self):
        r = lookup("Nowhereville", "SK", _data=FIXTURE)
        assert r["source"] == "province"
        assert (r["lat"], r["lon"]) == PROVINCE_CENTROIDS["SK"]

    def test_empty_municipality_still_resolves_province(self):
        r = lookup("", "YT", _data=FIXTURE)
        assert r["source"] == "province"

    def test_unknown_province_returns_none(self):
        assert lookup("Somewhere", "ZZ", _data=FIXTURE) is None
        assert lookup("Somewhere", "", _data=FIXTURE) is None


class TestHardcodedTables:
    def test_all_13_province_centroids(self):
        assert set(PROVINCE_CENTROIDS) == {
            "BC", "AB", "SK", "MB", "ON", "QC", "NB", "NS", "PE", "NL",
            "YT", "NT", "NU"}

    def test_about_35_cma_centroids(self):
        assert len(CMA_CENTROIDS) >= 35

    def test_cma_keys_are_normalized(self):
        for (name, prov) in CMA_CENTROIDS:
            assert name == normalize_place(name)
            assert prov in PROVINCE_CENTROIDS

    def test_centroids_inside_canada_bounds(self):
        for lat, lon in list(CMA_CENTROIDS.values()) + \
                list(PROVINCE_CENTROIDS.values()):
            assert 41.0 < lat < 84.0
            assert -141.5 < lon < -52.0
