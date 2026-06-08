"""
test_compound_queries.py — Unit tests for compound query loading and integrity.
STEP_2D: Validates query count, free tier compliance, lookback windows,
French coverage, geo tier coverage, province coverage, and sector coverage.
"""

from compound_queries import (
    load_queries, get_queries_by_language, get_queries_by_province,
    get_queries_by_tier, get_queries_by_sector,
)


def test_query_count():
    queries = load_queries()
    # NEW-8 (2026-06-08 audit): the query set is additive-only and has grown well
    # past the original 759 instruction-style queries (now ~2,649 incl. short
    # keyword RSS queries). Assert a floor, not an exact count, so the additive
    # invariant doesn't break the test on every expansion.
    assert len(queries) >= 759, f"Expected >= 759, got {len(queries)}"


def test_free_tier_compliance():
    queries = load_queries()
    daily = len(queries) / 7
    assert daily < 500, f"Exceeds free tier: {daily:.0f}/day (limit 500)"
    print(f"    Daily load: {daily:.0f}/day = {daily/500*100:.0f}% utilization")


def test_lookback_window():
    """Every instruction-style (agent) query must embed 4-week lookback language.

    NEW-8 (2026-06-08 audit): the query set now contains two classes —
    long agent-instruction queries (>=150 chars) that embed their own time window
    in the prompt text, and short keyword RSS strings (<=91 chars) whose 4-week
    window is applied at FETCH time via the Google News `when:` parameter (not in
    text). This test enforces lookback on the class that carries it in text; the
    keyword class is exercised by the fetch layer (see E-4). The two classes are
    cleanly separated by length (lookback queries are all >=250 chars).
    """
    missing = []
    for q in load_queries():
        if len(q["query"]) < 150:
            continue  # short keyword query — windowed at fetch time, not in text
        text = q["query"].lower()
        has_en = "four weeks" in text or "past 4 weeks" in text or "4 weeks" in text
        has_fr = "quatre" in text and "semaines" in text
        if not (has_en or has_fr):
            missing.append(q["query"][:80])
    assert not missing, f"Missing lookback in {len(missing)} instruction queries, first: {missing[0]}"


def test_french_coverage():
    fr = get_queries_by_language("fr")
    by_prov = {}
    for q in fr:
        p = q.get("province", "N/A")
        by_prov[p] = by_prov.get(p, 0) + 1

    assert by_prov.get("QC", 0) >= 18, f"QC has only {by_prov.get('QC', 0)} French queries"
    assert by_prov.get("NB", 0) >= 18, f"NB has only {by_prov.get('NB', 0)} French queries"
    assert by_prov.get("NS", 0) >= 5, f"NS has only {by_prov.get('NS', 0)} French queries"
    assert by_prov.get("PE", 0) >= 5, f"PE has only {by_prov.get('PE', 0)} French queries"
    assert by_prov.get("ON", 0) >= 5, f"ON has only {by_prov.get('ON', 0)} French queries"
    print(f"    French by province: {by_prov}")


def test_geo_tier_coverage():
    province = get_queries_by_tier("province")
    cma = get_queries_by_tier("cma")
    regional = get_queries_by_tier("regional_cluster")

    assert len(province) > 200, f"Province queries too low: {len(province)}"
    assert len(cma) > 250, f"CMA queries too low: {len(cma)}"
    assert len(regional) > 180, f"Regional queries too low: {len(regional)}"
    print(f"    province={len(province)}, cma={len(cma)}, regional={len(regional)}")


def test_all_provinces_covered():
    all_provinces = {'ON', 'QC', 'AB', 'BC', 'SK', 'MB', 'NS', 'NB', 'NL', 'PE', 'YT', 'NT', 'NU'}
    covered = set()
    for q in load_queries():
        if q.get("province"):
            covered.add(q["province"])
    missing = all_provinces - covered
    assert not missing, f"Missing provinces: {missing}"


def test_sector_coverage():
    sectors = set()
    for q in load_queries():
        s = q.get("sector", "")
        if s and "lifecycle" not in s:
            sectors.add(s)
    assert len(sectors) >= 18, f"Only {len(sectors)} sectors covered (need 18)"
    print(f"    {len(sectors)} sectors found")


if __name__ == "__main__":
    tests = [
        test_query_count, test_free_tier_compliance, test_lookback_window,
        test_french_coverage, test_geo_tier_coverage, test_all_provinces_covered,
        test_sector_coverage,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  [PASS] {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {e}")

    print(f"\n  {'=' * 60}")
    print(f"  COMPOUND QUERY TESTS: {passed} passed, {failed} failed")
    print(f"  {'=' * 60}")
