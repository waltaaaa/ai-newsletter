"""
test_dedup.py — Unit tests for multi-source project deduplication.
STEP_2D: Validates merging, separation, confidence scaling, taxonomy enrichment.
"""

from project_dedup import (
    generate_dedup_key, deduplicate_projects, calculate_confidence,
)
from project_schema import normalize_project_type, is_brownfield, PROJECT_TYPES, SECTORS


def test_same_project_different_names():
    """Same project with slightly different names from different sources should merge."""
    projects = [
        {"name": "Portage Place Redevelopment",
         "location": {"city": "winnipeg", "province": "MB"},
         "value_millions": 650, "source_url": "https://cbc.ca/1",
         "status": "Approved", "discovery_source": "gemini_compound"},
        {"name": "The Portage Place New Redevelopment",
         "location": {"city": "winnipeg", "province": "MB"},
         "value_millions": 600, "source_url": "https://wpgfreepress.com/2",
         "status": "Proposed", "discovery_source": "rss_remediated"},
        {"name": "Portage Place Redevelopment Project",
         "location": {"city": "Winnipeg", "province": "MB"},
         "value_millions": 650, "source_url": "https://news.gov.mb.ca/3",
         "status": "Under Construction", "discovery_source": "federal_registry"},
    ]
    deduped = deduplicate_projects(projects)
    assert len(deduped) == 1, f"Expected 1, got {len(deduped)}"
    merged = deduped[0]
    assert merged["value_millions"] == 650, "Should keep highest value"
    assert merged["status"] == "Under Construction", f"Should keep most advanced status, got {merged['status']}"
    assert merged["_dedup_count"] == 3
    evidence_urls = {e.get("url") for e in merged.get("evidence", [])}
    assert len(evidence_urls) == 3, f"Expected 3 evidence URLs, got {len(evidence_urls)}"
    print(f"    3 mentions -> 1 project, {len(evidence_urls)} evidence, status={merged['status']}")


def test_different_projects_stay_separate():
    """Different projects in same province should not merge."""
    projects = [
        {"name": "Portage Place Redevelopment",
         "location": {"city": "winnipeg", "province": "MB"},
         "value_millions": 650, "source_url": "https://a.com"},
        {"name": "Winnipeg Transit BRT Extension",
         "location": {"city": "winnipeg", "province": "MB"},
         "value_millions": 500, "source_url": "https://b.com"},
    ]
    deduped = deduplicate_projects(projects)
    assert len(deduped) == 2, f"Expected 2, got {len(deduped)}"


def test_different_provinces_stay_separate():
    """Same name in different provinces should not merge."""
    projects = [
        {"name": "Community Centre Expansion",
         "province": "ON", "source_url": "https://a.com"},
        {"name": "Community Centre Expansion",
         "province": "BC", "source_url": "https://b.com"},
    ]
    deduped = deduplicate_projects(projects)
    assert len(deduped) == 2, f"Expected 2 (different provinces), got {len(deduped)}"


def test_confidence_increases_with_evidence():
    """More evidence sources should increase confidence."""
    single = [
        {"name": "Test Project",
         "location": {"city": "toronto", "province": "ON"},
         "source_url": "https://example.com/1"},
    ]
    multi = [
        {"name": "Test Project",
         "location": {"city": "toronto", "province": "ON"},
         "source_url": "https://example.com/1",
         "discovery_source": "gemini_compound"},
        {"name": "Test Project",
         "location": {"city": "toronto", "province": "ON"},
         "source_url": "https://news.ontario.ca/2",
         "discovery_source": "rss_remediated"},
        {"name": "Test Project",
         "location": {"city": "toronto", "province": "ON"},
         "source_url": "https://toronto.ca/3",
         "discovery_source": "federal_registry"},
    ]
    s_deduped = deduplicate_projects(single)
    m_deduped = deduplicate_projects(multi)
    assert m_deduped[0]["confidence"] > s_deduped[0]["confidence"], \
        f"Multi ({m_deduped[0]['confidence']}) should > single ({s_deduped[0]['confidence']})"
    print(f"    single={s_deduped[0]['confidence']}, multi={m_deduped[0]['confidence']}")


def test_taxonomy_enrichment():
    """Projects should get normalized project_type and is_brownfield."""
    projects = [
        {"name": "Retrofit Test", "province": "ON",
         "project_type": "deep_retrofit", "source_url": "https://x.com"},
        {"name": "Greenfield Test", "province": "BC",
         "project_type": "", "source_url": "https://y.com"},
        {"name": "Adaptive Test", "province": "QC",
         "project_type": "adaptive_reuse", "source_url": "https://z.com"},
    ]
    deduped = deduplicate_projects(projects)
    for p in deduped:
        assert "project_type" in p, f"Missing project_type on {p['name']}"
        assert "is_brownfield" in p, f"Missing is_brownfield on {p['name']}"

    retrofit = next(p for p in deduped if "Retrofit" in p["name"])
    assert retrofit["project_type"] == "retrofit"
    assert retrofit["is_brownfield"] is True

    greenfield = next(p for p in deduped if "Greenfield" in p["name"])
    assert greenfield["project_type"] == "greenfield"
    assert greenfield["is_brownfield"] is False

    adaptive = next(p for p in deduped if "Adaptive" in p["name"])
    assert adaptive["project_type"] == "adaptive_reuse"
    assert adaptive["is_brownfield"] is True


def test_value_takes_highest():
    """Dedup should keep the highest value_millions."""
    projects = [
        {"name": "Big Project", "province": "AB",
         "value_millions": 500, "source_url": "https://a.com"},
        {"name": "Big Project", "province": "AB",
         "value_millions": 800, "source_url": "https://b.com"},
        {"name": "Big Project", "province": "AB",
         "value_millions": 600, "source_url": "https://c.com"},
    ]
    deduped = deduplicate_projects(projects)
    assert len(deduped) == 1
    assert deduped[0]["value_millions"] == 800, f"Expected 800, got {deduped[0]['value_millions']}"


def test_empty_input():
    """Empty input should return empty list."""
    assert deduplicate_projects([]) == []
    assert deduplicate_projects(None) == []


def test_schema_completeness():
    """Verify project schema has expected types and sectors."""
    assert len(PROJECT_TYPES) == 11, f"Expected 11 project types, got {len(PROJECT_TYPES)}"
    assert len(SECTORS) == 18, f"Expected 18 sectors, got {len(SECTORS)}"
    assert "greenfield" in PROJECT_TYPES
    assert "adaptive_reuse" in PROJECT_TYPES
    assert "retrofit" in PROJECT_TYPES
    assert normalize_project_type("deep_retrofit") == "retrofit"
    assert normalize_project_type("repurpose") == "adaptive_reuse"
    assert normalize_project_type("") == "greenfield"


def test_dedup_key_generation():
    """Verify dedup keys are stable and normalized."""
    k1 = generate_dedup_key({"name": "Portage Place Redevelopment",
                              "location": {"city": "Winnipeg", "province": "MB"}})
    k2 = generate_dedup_key({"name": "Portage Place New Redevelopment",
                              "location": {"city": "winnipeg", "province": "MB"}})
    k3 = generate_dedup_key({"name": "PORTAGE PLACE",
                              "location": {"city": "WINNIPEG", "province": "mb"}})
    assert k1 == k2, f"Keys should match: {k1} vs {k2}"
    assert k1 == k3, f"Keys should match: {k1} vs {k3}"
    # Mall is a building-type word — NOT filler. Different project.
    k_mall = generate_dedup_key({"name": "Portage Place Mall Redevelopment",
                                  "location": {"city": "Winnipeg", "province": "MB"}})
    assert k1 != k_mall, "Mall carries semantic meaning — different project"

    # Different project, same city
    k4 = generate_dedup_key({"name": "Transit BRT Extension",
                              "location": {"city": "winnipeg", "province": "MB"}})
    assert k1 != k4, f"Different projects should have different keys"


if __name__ == "__main__":
    tests = [
        test_same_project_different_names,
        test_different_projects_stay_separate,
        test_different_provinces_stay_separate,
        test_confidence_increases_with_evidence,
        test_taxonomy_enrichment,
        test_value_takes_highest,
        test_empty_input,
        test_schema_completeness,
        test_dedup_key_generation,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  [PASS] {t.__name__}")
        except (AssertionError, Exception) as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {e}")

    print(f"\n  {'=' * 60}")
    print(f"  DEDUP TESTS: {passed} passed, {failed} failed")
    print(f"  {'=' * 60}")
