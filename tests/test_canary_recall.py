"""Tests for the canary recall set (config/canary_projects.json) and the
recall scorecard harness (tools/canary_recall_check.py). No DB, no network —
the matching logic is exercised through pure functions on fixture dicts."""
import json
from pathlib import Path

import pytest

from tools.canary_recall_check import (
    CANARY_PATH,
    match_canary,
    score_canaries,
    _names_match,
    _name_keys,
)
from tools.dedup_projects_fuzzy import normalize_name, norm_province

BACKEND = Path(__file__).resolve().parent.parent

VALID_STAGES = {"Proposed", "Under Review", "Approved", "Under Construction"}
VALID_PROVINCES = {"BC", "AB", "SK", "MB", "ON", "QC", "NB", "NS", "PE",
                   "NL", "YT", "NT", "NU"}
VALID_SECTORS = {
    "oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
    "transport_logistics", "healthcare", "education", "residential",
    "commercial_mixed", "agriculture", "forestry", "defence", "telecom",
    "indigenous", "environment", "tourism_culture", "government",
}


@pytest.fixture(scope="module")
def canary_file():
    return json.loads(CANARY_PATH.read_text(encoding="utf-8"))


class TestCanaryConfig:
    def test_file_exists_and_has_meta(self, canary_file):
        assert "_meta" in canary_file
        assert "curation" in canary_file["_meta"]["curation_note"].lower()

    def test_about_fifty_canaries(self, canary_file):
        n = len(canary_file["canaries"])
        assert 45 <= n <= 65
        assert canary_file["_meta"]["count"] == n

    def test_all_thirteen_provinces_covered(self, canary_file):
        provs = {c["province"] for c in canary_file["canaries"]}
        assert provs == VALID_PROVINCES

    def test_all_eighteen_sectors_covered(self, canary_file):
        sectors = {c["sector"] for c in canary_file["canaries"]}
        assert sectors == VALID_SECTORS

    def test_schema_per_record(self, canary_file):
        for c in canary_file["canaries"]:
            assert c["name"]
            assert isinstance(c["aliases"], list)
            assert c["province"] in VALID_PROVINCES
            assert "cma" in c
            assert c["sector"] in VALID_SECTORS
            assert c["value_millions"] is None or c["value_millions"] > 0
            assert c["lifecycle_stage"] in VALID_STAGES
            assert isinstance(c["reference_urls"], list) and c["reference_urls"]
            assert all(u.startswith("http") for u in c["reference_urls"])
            assert c["curated_date"] == "2026-06-10"

    def test_lifecycle_stage_spread(self, canary_file):
        stages = {c["lifecycle_stage"] for c in canary_file["canaries"]}
        assert stages == VALID_STAGES  # Proposed -> Under Construction all present


class TestNameMatching:
    def test_exact_normalized_match(self):
        assert _names_match(normalize_name("Site C Dam"),
                            normalize_name("Site C Dam"))

    def test_fuzzy_match_distinctive_names(self):
        a = normalize_name("Darlington Refurbishment Project")
        b = normalize_name("Darlington Nuclear Refurbishment")
        assert _names_match(a, b)

    def test_unrelated_names_do_not_match(self):
        a = normalize_name("Site C Clean Energy Project")
        b = normalize_name("Cedar LNG")
        assert not _names_match(a, b)

    def test_generic_name_requires_cma_corroboration(self):
        a = normalize_name("Water Treatment Plant")
        b = normalize_name("Water Treatment Plant")
        assert not _names_match(a, b)  # no CMAs given
        assert not _names_match(a, b, "Arctic Bay", "Pond Inlet")
        assert _names_match(a, b, "Arctic Bay", "Arctic Bay")

    def test_generic_name_never_fuzzy_matches(self):
        a = normalize_name("Wastewater Treatment Plant")
        b = normalize_name("Water Treatment Plant Upgrades")
        assert not _names_match(a, b, "Town", "Town")

    def test_name_keys_include_aliases(self):
        canary = {"name": "Gordie Howe International Bridge",
                  "aliases": ["Gordie Howe Bridge", "Windsor-Detroit Bridge"]}
        keys = _name_keys(canary)
        assert len(keys) == 3
        assert normalize_name("Gordie Howe Bridge") in keys


class TestMatchCanary:
    @staticmethod
    def _projects_by_prov(projects):
        from collections import defaultdict
        out = defaultdict(list)
        for p in projects:
            out[norm_province(p["province"])].append({
                "name": p["name"], "norm": normalize_name(p["name"]),
                "status": p.get("status", ""), "cma": p.get("cma", ""),
            })
        return out

    def test_found_with_correct_status(self):
        canary = {"name": "Cedar LNG", "aliases": [], "province": "BC",
                  "cma": "Kitimat", "sector": "oil_gas",
                  "lifecycle_stage": "Approved"}
        projects = [{"name": "Cedar LNG", "province": "BC",
                     "status": "Approved", "cma": "Kitimat"}]
        r = match_canary(canary, self._projects_by_prov(projects))
        assert r["verdict"] == "found_with_correct_status"
        assert r["matched_name"] == "Cedar LNG"

    def test_found_with_status_mismatch(self):
        canary = {"name": "Cedar LNG", "aliases": [], "province": "BC",
                  "cma": "", "sector": "oil_gas",
                  "lifecycle_stage": "Under Construction"}
        projects = [{"name": "Cedar LNG", "province": "BC",
                     "status": "Approved", "cma": ""}]
        r = match_canary(canary, self._projects_by_prov(projects))
        assert r["verdict"] == "found"
        assert r["matched_status"] == "Approved"

    def test_alias_match(self):
        canary = {"name": "Reseau express metropolitain (REM)",
                  "aliases": ["REM Antenne Ouest"], "province": "QC",
                  "cma": "", "lifecycle_stage": "Under Construction",
                  "sector": "transport_logistics"}
        projects = [{"name": "REM Antenne Ouest", "province": "QC",
                     "status": "Under Construction", "cma": ""}]
        r = match_canary(canary, self._projects_by_prov(projects))
        assert r["verdict"] == "found_with_correct_status"

    def test_missed_when_absent(self):
        canary = {"name": "Gordie Howe International Bridge", "aliases": [],
                  "province": "ON", "cma": "Windsor",
                  "lifecycle_stage": "Under Construction",
                  "sector": "transport_logistics"}
        projects = [{"name": "Ontario Line", "province": "ON",
                     "status": "Under Construction", "cma": "Toronto"}]
        r = match_canary(canary, self._projects_by_prov(projects))
        assert r["verdict"] == "missed"
        assert r["matched_name"] is None

    def test_wrong_province_does_not_match(self):
        canary = {"name": "Cedar LNG", "aliases": [], "province": "AB",
                  "cma": "", "lifecycle_stage": "Approved",
                  "sector": "oil_gas"}
        projects = [{"name": "Cedar LNG", "province": "BC",
                     "status": "Approved", "cma": ""}]
        r = match_canary(canary, self._projects_by_prov(projects))
        assert r["verdict"] == "missed"

    def test_equivalent_status_rank_counts_as_correct(self):
        # 'Announced' ranks with 'Proposed' in STATUS_ORDER
        canary = {"name": "Heartland Hydrogen Hub", "aliases": [],
                  "province": "AB", "cma": "", "lifecycle_stage": "Proposed",
                  "sector": "oil_gas"}
        projects = [{"name": "Heartland Hydrogen Hub", "province": "AB",
                     "status": "Announced", "cma": ""}]
        r = match_canary(canary, self._projects_by_prov(projects))
        assert r["verdict"] == "found_with_correct_status"


class TestScoreCanaries:
    CANARIES = [
        {"name": "Cedar LNG", "aliases": [], "province": "BC", "cma": "",
         "sector": "oil_gas", "lifecycle_stage": "Approved"},
        {"name": "Ontario Line", "aliases": [], "province": "ON", "cma": "",
         "sector": "transport_logistics",
         "lifecycle_stage": "Under Construction"},
        {"name": "Phantom Project Q", "aliases": [], "province": "SK",
         "cma": "", "sector": "mining", "lifecycle_stage": "Proposed"},
    ]
    PROJECTS = [
        {"name": "Cedar LNG", "province": "BC", "status": "Approved", "cma": ""},
        {"name": "Ontario Line", "province": "ON", "status": "Proposed", "cma": ""},
    ]

    def test_totals_and_buckets(self):
        snap = score_canaries(self.CANARIES, self.PROJECTS)
        t = snap["totals"]
        assert t["total"] == 3
        assert t["found_with_correct_status"] == 1
        assert t["found"] == 1
        assert t["missed"] == 1
        assert t["recall"] == round(2 / 3, 3)
        assert t["status_accurate_recall"] == round(1 / 3, 3)
        assert snap["by_province"]["SK"]["missed"] == 1
        assert snap["by_sector"]["oil_gas"]["found_with_correct_status"] == 1

    def test_snapshot_is_json_serializable(self):
        snap = score_canaries(self.CANARIES, self.PROJECTS)
        assert json.loads(json.dumps(snap))["canary_count"] == 3
