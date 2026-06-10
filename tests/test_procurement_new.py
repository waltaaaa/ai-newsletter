"""quality-pass-1.4 G4 — procurement remainder tests.

Covers fetch_seao (Québec OCDS via Données Québec), fetch_dcc (Defence
Construction Canada awarded-contracts PDF), the additive French
construction keywords, and the run_procurement_monitor wiring.

All HTTP is mocked — endpoint shapes were live-verified 2026-06-10
(see SOURCE_ENDPOINTS_NEEDS_LIVE_VERIFICATION.md).
"""
import json
import sqlite3

import pytest

import procurement_monitor as pm


class _FakeResp:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._payload


# ── French construction keywords (additive) ──────────────────────────────────

def test_french_keywords_added_additively():
    # Original anglo keywords untouched
    for kw in ("construction", "bridge", "wastewater", "data centre"):
        assert kw in pm.CONSTRUCTION_KEYWORDS
    # French additions present
    for kw in ("réfection", "agrandissement", "pont", "eaux usées",
               "école", "chantier"):
        assert kw in pm.CONSTRUCTION_KEYWORDS
    assert pm.CONSTRUCTION_KEYWORDS_FR  # the additive list itself exists


# ── SEAO ──────────────────────────────────────────────────────────────────────

_SEAO_PACKAGE = {
    "result": {
        "resources": [
            {"name": "hebdo_20260601_20260607.json",
             "url": ("https://www.donneesquebec.ca/recherche/dataset/d23b2e02/"
                     "resource/aaa/download/hebdo_20260601_20260607.json")},
            {"name": "mensuel_20260501_20260531.json",
             "url": "https://example.org/should-not-be-fetched"},
        ]
    }
}

_SEAO_OCDS = {
    "releases": [
        {   # construction works award above the floor — KEPT
            "ocid": "ocid-1",
            "tender": {"title": "Construction d'une voie de contournement",
                       "mainProcurementCategory": "works"},
            "buyer": {"name": "Ville de Québec"},
            "awards": [{"value": {"amount": 7_800_000, "currency": "CAD"},
                        "date": "2026-06-01T00:00:00-04:00",
                        "suppliers": [{"name": "Entreprises ABC Inc."}]}],
        },
        {   # below the floor — DROPPED
            "ocid": "ocid-2",
            "tender": {"title": "Réfection du pont local",
                       "mainProcurementCategory": "works"},
            "buyer": {"name": "Ville de Montmagny"},
            "awards": [{"value": {"amount": 90_000, "currency": "CAD"},
                        "suppliers": [{"name": "PME Inc."}]}],
        },
        {   # services, no construction keyword — DROPPED
            # (note: avoids 'port'-substring words like "Support"; the
            # keyword check is substring-based, house style)
            "ocid": "ocid-3",
            "tender": {"title": "Licences logicielles et soutien technique",
                       "mainProcurementCategory": "services"},
            "buyer": {"name": "SCT"},
            "awards": [{"value": {"amount": 9_000_000, "currency": "CAD"},
                        "suppliers": [{"name": "TI Corp"}]}],
        },
        {   # services but FRENCH construction keyword in title — KEPT
            "ocid": "ocid-4",
            "tender": {"title": "Agrandissement de l'école secondaire",
                       "mainProcurementCategory": "services"},
            "buyer": {"name": "Centre de services scolaire"},
            "awards": [{"value": {"amount": 42_600_000, "currency": "CAD"},
                        "suppliers": [{"name": "Construction SOCAM"}]}],
        },
        {   # no award yet — DROPPED
            "ocid": "ocid-5",
            "tender": {"title": "Construction d'un hôpital",
                       "mainProcurementCategory": "works"},
            "awards": [],
        },
    ]
}


def test_fetch_seao_parses_ocds_and_filters(monkeypatch):
    fetched = []

    def fake_get(url, timeout=30, **kw):
        fetched.append(url)
        if "package_show" in url:
            return _FakeResp(payload=_SEAO_PACKAGE)
        if "hebdo_20260601_20260607.json" in url:
            return _FakeResp(payload=_SEAO_OCDS)
        raise AssertionError(f"unexpected URL fetched: {url}")

    monkeypatch.setattr(pm.http_client, "get", fake_get)
    contracts = pm.fetch_seao(days_back=7)

    assert len(contracts) == 2
    ocids_kept = {c["title"] for c in contracts}
    assert "Construction d'une voie de contournement" in ocids_kept
    assert "Agrandissement de l'école secondaire" in ocids_kept
    for c in contracts:
        assert c["source"] == "seao"
        assert c["province"] == "QC"
        assert c["value"] >= pm.MIN_CONTRACT_VALUE
        assert c["url"].startswith("https://")
    # monthly file must not have been fetched
    assert not any("should-not-be-fetched" in u for u in fetched)


def test_fetch_seao_package_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(pm.http_client, "get",
                        lambda url, timeout=30, **kw: _FakeResp(status_code=503))
    assert pm.fetch_seao() == []


# ── DCC ───────────────────────────────────────────────────────────────────────

def _build_dcc_pdf():
    """Build a small PDF mimicking the DCC Recently Awarded Contracts layout."""
    fitz = pytest.importorskip("fitz")
    lines = [
        "Recently Awarded Contracts", "2026-06-10", "1",
        "Project", "Number", "Contract", "Number", "MERX", "Number",
        "Contract Description", "Location", "Award", "Date", "Award",
        "Amount", "Contractor/Consultant", "City of", "Contractor", "Province",
        # Row 1: above the $5M floor — KEPT
        "CH260099", "87099", "",
        "Construct Single Quarters Buildings",
        "Dundurn, Saskatchewan",
        "2026-06-09", "$11,990,771.00",
        "Wright Construction Western Inc.", "Saskatoon", "SK",
        # Row 2: small contract — parsed but dropped by the floor
        "PA000417", "86722", "",
        "Upgrade Montgomery Hill Road Design", "Petawawa, Ontario",
        "2026-06-09", "$156,920.00",
        "AECOM Canada ULC", "Markham", "ON",
    ]
    doc = fitz.open()
    page = doc.new_page()
    y = 50
    for line in lines:
        page.insert_text((50, y), line, fontsize=8)
        y += 11
    return doc.tobytes()


def test_fetch_dcc_parses_pdf_and_applies_floor(monkeypatch):
    pdf_bytes = _build_dcc_pdf()
    monkeypatch.setattr(pm.http_client, "get",
                        lambda url, timeout=30, **kw: _FakeResp(content=pdf_bytes))
    contracts = pm.fetch_dcc()

    assert len(contracts) == 1
    c = contracts[0]
    assert c["source"] == "dcc"
    assert c["value"] == 11_990_771.0
    assert "Construct Single Quarters Buildings" in c["description"]
    assert c["award_date"] == "2026-06-09"
    assert c["province"] == "SK"  # from "Saskatchewan" in the description


def test_fetch_dcc_non_pdf_response_skipped(monkeypatch):
    monkeypatch.setattr(pm.http_client, "get",
                        lambda url, timeout=30, **kw: _FakeResp(content=b"<html>nope</html>"))
    assert pm.fetch_dcc() == []


def test_fetch_dcc_http_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(pm.http_client, "get",
                        lambda url, timeout=30, **kw: _FakeResp(status_code=503))
    assert pm.fetch_dcc() == []


# ── run_procurement_monitor wiring ────────────────────────────────────────────

def test_run_procurement_monitor_includes_new_sources(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE projects (
        norm_key TEXT, name TEXT, province TEXT, value TEXT,
        status TEXT, sector TEXT)""")

    monkeypatch.setattr(pm, "fetch_open_canada_contracts", lambda days_back=30: [])
    monkeypatch.setattr(pm, "fetch_buyandsell_rss", lambda: [])
    monkeypatch.setattr(pm, "fetch_ontario_bps", lambda: [])
    monkeypatch.setattr(pm, "fetch_bc_bid", lambda: [])
    monkeypatch.setattr(pm, "fetch_seao", lambda days_back=30: [
        {"source": "seao", "title": "Agrandissement", "vendor": "X",
         "value": 9_000_000, "province": "QC", "url": "https://x"}])
    monkeypatch.setattr(pm, "fetch_dcc", lambda: [
        {"source": "dcc", "title": "Hangar", "vendor": "Y",
         "value": 12_000_000, "province": "ON", "url": "https://y"}])

    result = pm.run_procurement_monitor(conn)
    sources = set(result["procurement_sources"])
    assert {"seao", "dcc"} <= sources
    assert result["procurement_total_value"] == 21_000_000


def test_run_procurement_monitor_isolates_new_source_errors(monkeypatch):
    """A SEAO/DCC blow-up must not kill the monitor run."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE projects (
        norm_key TEXT, name TEXT, province TEXT, value TEXT,
        status TEXT, sector TEXT)""")

    monkeypatch.setattr(pm, "fetch_open_canada_contracts", lambda days_back=30: [])
    monkeypatch.setattr(pm, "fetch_buyandsell_rss", lambda: [])
    monkeypatch.setattr(pm, "fetch_ontario_bps", lambda: [])
    monkeypatch.setattr(pm, "fetch_bc_bid", lambda: [
        {"source": "bc_bid", "title": "ok", "value": None,
         "province": "BC", "url": "https://z"}])

    def boom(*a, **kw):
        raise RuntimeError("seao exploded")
    monkeypatch.setattr(pm, "fetch_seao", boom)
    monkeypatch.setattr(pm, "fetch_dcc", boom)

    result = pm.run_procurement_monitor(conn)
    assert "bc_bid" in result["procurement_sources"]
