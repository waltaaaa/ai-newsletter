"""patch-1.3 discovery-pipeline regression tests.

Covers the 2026-06-08 discovery-improvement-plan items implemented in patch-1.3:
  C1 — fuzzy rediscovery fallback in the live upsert (guarded, strict)
  C5 — hold statuses gated behind explicit/government signals
  S1 — scrapers' source_url scalar folded into evidence[]
  S2 — source_url_quality stamped at write time
  E6 — per-reason rejection counters
"""
import json

import pytest

from db import (init_db, upsert_project, get_project, get_rejection_counters,
                get_merge_counters)
from project_sync import upsert_flat_projects


@pytest.fixture()
def conn():
    c = init_db(":memory:")
    get_rejection_counters(reset=True)
    get_merge_counters(reset=True)
    yield c
    c.close()


def _seed_site_c(conn):
    return upsert_project(conn, {
        "name": "Site C Hydroelectric Dam", "province": "British Columbia",
        "status": "Under Construction", "value": "C$16B",
        "proponent": "BC Hydro",
        "evidence": [{"url": "https://www.bchydro.com/sitec/project-update-2026",
                      "source": "crown_corp", "authority": "government"}],
        "discovery_source": "crown_corp",
    })


def test_c1_fuzzy_merge_decoration_variant(conn):
    """A '... Project' decoration variant merges into the existing row."""
    k1 = _seed_site_c(conn)
    k2 = upsert_project(conn, {
        "name": "Site C Hydroelectric Dam Project", "province": "BC",
        "status": "Proposed", "value": "C$16B",
        "proponent": "BC Hydro",
        "evidence": [{"url": "https://example-news.ca/site-c-dam-milestone",
                      "source": "google_news_rss"}],
        "discovery_source": "google_news_rss",
    })
    assert k1 == k2
    p = get_project(conn, k1)
    assert len(json.loads(p["evidence"])) == 2
    assert set(json.loads(p["discovery_sources"])) == {"crown_corp", "google_news_rss"}
    assert get_merge_counters().get("fuzzy_merged") == 1


def test_c1_guard_distinct_proponents_not_merged(conn):
    """Same site, different proponents (Surmont pattern) must stay distinct."""
    k3 = upsert_project(conn, {
        "name": "Surmont Expansion (ConocoPhillips)", "province": "Alberta",
        "status": "Proposed", "proponent": "ConocoPhillips",
        "evidence": [{"url": "https://example.com/surmont-conoco"}],
    })
    k4 = upsert_project(conn, {
        "name": "Surmont Expansion (MEG Energy)", "province": "Alberta",
        "status": "Proposed", "proponent": "MEG Energy",
        "evidence": [{"url": "https://example.com/surmont-meg"}],
    })
    assert k3 != k4


def test_c1_strict_matcher_skips_low_overlap_names(conn):
    """'Site C Dam' vs 'Site C Hydroelectric Dam' (Jaccard < 0.85, no shared
    URL) intentionally does NOT merge — false-negative bias by design."""
    k1 = _seed_site_c(conn)
    k2 = upsert_project(conn, {
        "name": "Site C Dam", "province": "BC", "status": "Proposed",
        "evidence": [{"url": "https://example-news.ca/site-c"}],
    })
    assert k1 != k2


def test_c5_media_hold_does_not_regress(conn):
    k1 = _seed_site_c(conn)
    upsert_project(conn, {
        "name": "Site C Hydroelectric Dam", "province": "BC",
        "status": "On Hold",
        "evidence": [{"url": "https://example-news.ca/site-c-delay-rumour",
                      "source": "google_news_rss"}],
    })
    assert get_project(conn, k1)["status"] == "Under Construction"


def test_c5_government_hold_applies(conn):
    k1 = _seed_site_c(conn)
    upsert_project(conn, {
        "name": "Site C Hydroelectric Dam", "province": "BC",
        "status": "On Hold", "has_government_source": True,
        "evidence": [{"url": "https://www.bcuc.com/site-c-suspension-order",
                      "authority": "government"}],
    })
    assert get_project(conn, k1)["status"] == "On Hold"


def test_c5_cancelled_remains_terminal(conn):
    k1 = _seed_site_c(conn)
    upsert_project(conn, {
        "name": "Site C Hydroelectric Dam", "province": "BC",
        "status": "Cancelled",
        "evidence": [{"url": "https://example-news.ca/cancelled"}],
    })
    assert get_project(conn, k1)["status"] == "Cancelled"


def test_s2_link_quality_stamped(conn):
    k1 = _seed_site_c(conn)
    assert get_project(conn, k1)["source_url_quality"] == "deep"
    k5 = upsert_project(conn, {
        "name": "Major Projects Inventory Entry Example", "province": "ON",
        "status": "Proposed",
        "evidence": [{"url": "https://ontario.ca/major-projects-inventory.pdf"}],
    })
    assert get_project(conn, k5)["source_url_quality"] == "listing"


def test_s1_source_url_folded_into_evidence(conn):
    res = upsert_flat_projects(conn, [{
        "name": "Example Wastewater Treatment Upgrade",
        "province": "Manitoba", "status": "Under Review",
        "source_url": "https://www.gov.mb.ca/sd/eal/registries/12345-example.html",
        "discovery_source": "provincial_ea",
    }])
    assert res["new"] == 1
    row = get_project(conn, "examplewastewatertreatmentupgrade__mb")
    ev = json.loads(row["evidence"])
    assert ev and ev[0]["url"].endswith("12345-example.html")
    assert ev[0]["authority"] == "government"


def test_e6_rejection_counters(conn):
    upsert_project(conn, {"name": "Open Data", "province": "ON",
                          "evidence": [{"url": "https://x.ca/a"}]})
    upsert_project(conn, {"name": "Real Project Name Here", "province": "ON",
                          "evidence": []})
    c = get_rejection_counters(reset=True)
    assert c.get("non_project_name") == 1
    assert c.get("no_url") == 1


def test_new_vs_updated_precheck_uses_db_key(conn):
    """patch-1.3 bug fix: the pre-check key must match db's code-based key, so
    a rediscovery counts as updated (previously '…__manitoba' never matched
    the stored '…__mb' and every rediscovery was counted new)."""
    payload = [{
        "name": "Example Wastewater Treatment Upgrade",
        "province": "Manitoba", "status": "Under Review",
        "source_url": "https://www.gov.mb.ca/sd/eal/registries/12345-example.html",
        "discovery_source": "provincial_ea",
    }]
    first = upsert_flat_projects(conn, payload)
    second = upsert_flat_projects(conn, payload)
    assert first["new"] == 1
    assert second["new"] == 0
    assert second["updated"] == 1
