"""Tests for the rebuilt Tier 14 (institutional_capital.py, 2026-06-11).

Pure-function tests only — no network. The live path is exercised by running
the module standalone (python institutional_capital.py).
"""

import institutional_capital as ic


def _entry(title, link="https://news.google.com/articles/abc123",
           summary="", published_parsed=None):
    e = {"title": title, "link": link, "summary": summary}
    if published_parsed:
        e["published_parsed"] = published_parsed
    return e


def _source(**overrides):
    src = {
        "name": "Vancouver Fraser Port Authority", "category": "port",
        "province": "BC", "cma": "Vancouver", "domain": "portvancouver.com",
        "aliases": ["Port of Vancouver", "Vancouver Fraser Port", "Vancouver port"],
    }
    src.update(overrides)
    return src


# ── Dollar parsing ───────────────────────────────────────────────────────────

def test_parse_dollar_english_forms():
    assert ic._parse_dollar("a $3 Billion container terminal") == 3000
    assert ic._parse_dollar("receives $42.5 million investment") == 42.5
    assert ic._parse_dollar("the $15.3-million expansion") == 15.3
    assert ic._parse_dollar("Jansen is a $13.9B program") == 13900
    assert ic._parse_dollar("a $1,200 million bond") == 1200


def test_parse_dollar_french_forms():
    assert ic._parse_dollar("un projet de 13,9 G$") == 13900
    assert ic._parse_dollar("agrandissement de 450 M$") == 450
    assert ic._parse_dollar("un chantier de 1,5 milliard de dollars") == 1500


def test_parse_dollar_none_when_absent():
    assert ic._parse_dollar("Port unveils design for new terminal") is None


# ── Title handling ───────────────────────────────────────────────────────────

def test_split_publisher():
    title, pub = ic._split_publisher(
        "Peter Lougheed Centre's $151 million expansion complete - constructconnect.com")
    assert pub == "constructconnect.com"
    assert title.endswith("expansion complete")


def test_alias_gate_is_word_bounded():
    assert ic._title_mentions(["U of T"], "Ottawa puts $42.5M into U of T building")
    assert not ic._title_mentions(["STM"], "investment in postmodern art")


def test_infer_status():
    assert ic._infer_status("Hospital expansion complete") == "Complete"
    assert ic._infer_status("Port breaks ground on $1B terminal") == "Under Construction"
    assert ic._infer_status("Board approves $500M campus plan") == "Approved"
    assert ic._infer_status("University plans $600M residence tower") == "Proposed"
    # Figurative "groundbreaking" must NOT imply construction started.
    assert ic._infer_status("'Groundbreaking' $400M approach to research") == "Proposed"


# ── Entry → project gates ────────────────────────────────────────────────────

def test_entry_passes_all_gates():
    e = _entry("Port of Vancouver begins bidding for $3 Billion container "
               "terminal expansion - Daily Commercial News")
    proj = ic._entry_to_project(e, _source(), "name")
    assert proj is not None
    assert proj["value_millions"] == 3000
    assert proj["province"] == "BC"
    assert proj["sector"] == "transport_logistics"
    assert proj["naics_code"] == "48-49"
    assert proj["_source_type"] == "media"
    assert proj["source_url"] == e["link"]
    assert proj["_evidence"][0]["authority"] == "media"


def test_wrong_institution_rejected_on_name_query():
    # Foreign port story surfaced by the name query — alias not in title.
    e = _entry("AD Ports begins $380 million Luanda Terminal modernisation - Port Technology")
    assert ic._entry_to_project(e, _source(), "name") is None


def test_site_query_skips_alias_gate_but_keeps_value_gate():
    e = _entry("Authority advances $380 million terminal modernisation program here")
    proj = ic._entry_to_project(e, _source(), "site")
    assert proj is not None
    assert proj["_source_type"] == "government"
    assert proj["confidence"] == 0.6


def test_below_province_threshold_rejected():
    # BC threshold is $175M
    e = _entry("Port of Vancouver announces $50 million berth upgrade - BIV")
    assert ic._entry_to_project(e, _source(), "name") is None


def test_no_dollar_value_rejected():
    e = _entry("Port of Vancouver unveils design for new container terminal - BIV")
    assert ic._entry_to_project(e, _source(), "name") is None


def test_no_link_rejected_url_hard_gate():
    e = _entry("Port of Vancouver begins $3 Billion terminal expansion - DCN", link="")
    assert ic._entry_to_project(e, _source(), "name") is None


def test_no_capital_keyword_rejected():
    e = _entry("Port of Vancouver posts $200 million in quarterly revenue - BIV")
    assert ic._entry_to_project(e, _source(), "name") is None


# ── Same-announcement merge ──────────────────────────────────────────────────

def test_merge_appends_evidence_never_overwrites():
    src = _source()
    p1 = ic._entry_to_project(
        _entry("Port of Vancouver begins bidding for $3 Billion terminal expansion - DCN",
               link="https://news.google.com/articles/one"), src, "name")
    p2 = ic._entry_to_project(
        _entry("Port of Vancouver's $3 billion terminal construction gets green light - BIV",
               link="https://news.google.com/articles/two"), src, "name")
    merged = {}
    key = (src["name"], 3000)
    assert ic._merge_into(merged, key, p1) is True
    assert ic._merge_into(merged, key, p2) is False
    proj = merged[key]
    urls = {ev["url"] for ev in proj["_evidence"]}
    assert urls == {"https://news.google.com/articles/one",
                    "https://news.google.com/articles/two"}
    assert len(proj["sources"]) == 2
    assert proj["confidence"] == 0.55  # 0.5 base + 0.05 second source
    # "green light" advances Proposed -> Approved (non-regression upward)
    assert proj["status"] == "Approved"


def test_merge_status_never_regresses():
    src = _source()
    p1 = ic._entry_to_project(
        _entry("Port of Vancouver breaks ground on $3 billion terminal - DCN",
               link="https://news.google.com/articles/uc"), src, "name")
    p2 = ic._entry_to_project(
        _entry("Port of Vancouver plans $3 billion terminal expansion - BIV",
               link="https://news.google.com/articles/plan"), src, "name")
    merged = {}
    key = (src["name"], 3000)
    ic._merge_into(merged, key, p1)
    ic._merge_into(merged, key, p2)
    assert merged[key]["status"] == "Under Construction"


def test_merge_government_attribution_wins():
    src = _source()
    media = ic._entry_to_project(
        _entry("Port of Vancouver begins $3 billion terminal expansion - BIV",
               link="https://news.google.com/articles/m"), src, "name")
    gov = ic._entry_to_project(
        _entry("Authority launches $3 billion terminal expansion program now",
               link="https://news.google.com/articles/g"), src, "site")
    merged = {}
    key = (src["name"], 3000)
    ic._merge_into(merged, key, media)
    ic._merge_into(merged, key, gov)
    assert merged[key]["_source_type"] == "government"
    assert merged[key]["confidence"] >= 0.6


# ── Source list integrity ────────────────────────────────────────────────────

def test_all_sources_well_formed():
    for src in ic.INSTITUTIONAL_SOURCES:
        assert src["category"] in ic._TERMS_EN
        assert src["province"] in ic._THRESHOLDS_M
        assert src["aliases"], src["name"]
        # site-query domains must be bare hosts, not URLs
        if src.get("domain"):
            assert "://" not in src["domain"] and "/" not in src["domain"]


def test_signature_unchanged():
    import inspect
    sig = inspect.signature(ic.scrape_institutional_capital)
    assert len(sig.parameters) == 0
