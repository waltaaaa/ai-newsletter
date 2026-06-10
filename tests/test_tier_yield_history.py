"""quality-pass-1.4 E7 — per-tier yield history pure-helper tests."""

from query_yield_audit import update_tier_history


def test_two_consecutive_zeros_degraded():
    history = {"tier13_municipal": [12, 0]}
    new_history, degraded = update_tier_history(history, {"tier13_municipal": 0})
    assert new_history["tier13_municipal"] == [12, 0, 0]
    assert ("tier13_municipal", 2) in degraded


def test_zero_then_nonzero_clean():
    history = {"tier13_municipal": [12, 0]}
    new_history, degraded = update_tier_history(history, {"tier13_municipal": 7})
    assert new_history["tier13_municipal"] == [12, 0, 7]
    assert degraded == []


def test_single_zero_not_degraded():
    new_history, degraded = update_tier_history({}, {"tier1_registries": 0})
    assert new_history["tier1_registries"] == [0]
    assert degraded == []


def test_truncation_at_eight():
    history = {"tier2_news_search": [1, 2, 3, 4, 5, 6, 7, 8]}
    new_history, degraded = update_tier_history(
        history, {"tier2_news_search": 9}, max_keep=8)
    assert new_history["tier2_news_search"] == [2, 3, 4, 5, 6, 7, 8, 9]
    assert degraded == []


def test_tier_missing_from_run_keeps_history():
    """A tier absent from this run keeps its history without a new entry."""
    history = {"tier14_institutional": [3, 4]}
    new_history, degraded = update_tier_history(history, {"tier1_registries": 5})
    assert new_history["tier14_institutional"] == [3, 4]
    assert new_history["tier1_registries"] == [5]
    assert degraded == []


def test_tolerates_bad_input_types():
    new_history, degraded = update_tier_history(None, None)
    assert new_history == {}
    assert degraded == []
