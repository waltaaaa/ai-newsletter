"""quality-pass-1.4 G3 — Northern & Indigenous coverage tests.

Covers the new gov_sources scrapers (NIRB, MVLWB, ISC infrastructure),
their registration in the master scrapers list, and the Indigenous
development corporation additions to config/corporate_watchlist.json.

All HTTP is mocked — endpoint shapes were live-verified 2026-06-10
(see SOURCE_ENDPOINTS_NEEDS_LIVE_VERIFICATION.md).
"""
import inspect
import io
import json
import zipfile
from pathlib import Path

import pytest

import gov_sources


class _FakeResp:
    def __init__(self, text="", content=b"", status_code=200):
        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        return json.loads(self.text)


# ── NIRB ──────────────────────────────────────────────────────────────────────

_NIRB_PAGE = """
<html><script>
var geometry_layer=[];
var geometry_layer = eval('([{"application_id":"123035","nirb_file_number":"00MN059","application_date":"2000-09-18","project_name":"Jericho Project","proponent_name":"Shear Diamonds (Nunavut) Corporation","activity_type":"Camp"},{"application_id":"123035","nirb_file_number":"00MN059","application_date":"2000-09-18","project_name":"Jericho Project","proponent_name":"Shear Diamonds (Nunavut) Corporation","activity_type":"Camp"},{"application_id":"126401","nirb_file_number":"26YN019","application_date":"2026-05-01","project_name":"Iqaluit Deepwater Port Expansion","proponent_name":"Government of Nunavut","activity_type":"Coastal Infrastucture"}])')
</script></html>
"""


def test_nirb_parses_embedded_geometry_layer(monkeypatch):
    def fake_post(url, data=None, timeout=None, headers=None):
        assert data["whattosearchfor"] == "project"
        assert data["searchonlyactive"] == "on"
        return _FakeResp(text=_NIRB_PAGE)

    monkeypatch.setattr(gov_sources.requests, "post", fake_post)
    projects = gov_sources._scrape_nunavut_nirb()

    # Dedup by application_id: 3 entries -> 2 projects
    assert len(projects) == 2
    names = {p["name"] for p in projects}
    assert "Jericho Project" in names
    assert "Iqaluit Deepwater Port Expansion" in names
    for p in projects:
        assert p["province"] == "Nunavut"
        assert p["discovery_source"] == "provincial_ea"
        assert p["source_url"].startswith("https://www.nirb.ca/project/")
        assert p["status"] == "Under Review"


def test_nirb_failure_returns_empty_without_tavily(monkeypatch):
    def fake_post(url, data=None, timeout=None, headers=None):
        return _FakeResp(text="", status_code=503)

    monkeypatch.setattr(gov_sources.requests, "post", fake_post)
    assert gov_sources._scrape_nunavut_nirb() == []


# ── MVLWB ─────────────────────────────────────────────────────────────────────

_MVLWB_TABLE = """
<html><table>
<tr><th>Company</th><th>Activity</th><th>File Number</th><th>Start Date</th><th>Expiry Date</th></tr>
<tr><td>Fortune Minerals Limited</td><td>Road Private</td>
    <td><a href="/registry/w2025f0007">W2025F0007</a></td>
    <td>May 11, 2026</td><td>May 10, 2031</td></tr>
<tr><td>(NONE)</td><td>Miscellaneous</td>
    <td><a href="/registry/n94x263">N94X263</a></td>
    <td>July 14, 1994</td><td>June 29, 1995</td></tr>
<tr><td>Teck Metals Ltd.</td><td>Mining Exploration</td>
    <td><a href="/registry/mv2026x0007">MV2026X0007</a></td>
    <td>May 16, 2026</td><td>May 15, 2031</td></tr>
</table></html>
"""


def test_mvlwb_parses_table_and_skips_none_company(monkeypatch):
    monkeypatch.setattr(gov_sources, "_get_html", lambda url, timeout=20: _MVLWB_TABLE)
    projects = gov_sources._scrape_nwt_mvlwb()

    assert len(projects) == 2  # (NONE) row skipped
    by_prop = {p["proponent"]: p for p in projects}
    assert "Fortune Minerals Limited" in by_prop
    assert "Teck Metals Ltd." in by_prop
    fortune = by_prop["Fortune Minerals Limited"]
    assert fortune["province"] == "Northwest Territories"
    assert fortune["status"] == "Approved"
    assert fortune["source_url"] == "https://mvlwb.com/registry/w2025f0007"
    assert "W2025F0007" in fortune["name"]


def test_mvlwb_no_html_returns_empty(monkeypatch):
    monkeypatch.setattr(gov_sources, "_get_html", lambda url, timeout=20: None)
    assert gov_sources._scrape_nwt_mvlwb() == []


# ── ISC Indigenous Community Infrastructure ───────────────────────────────────

_ISC_HEADER = ("Province/Territory,Community,Community Number,Community Type,"
               "Internal Project Number,Infrastructure Category,Project Name,"
               "Description,Project Status,ISC Departmental Investment,"
               "Additional Information 1,Additional Information 2,"
               "Longitude,Latitude,Coordinate System")

_ISC_ROWS = [
    # Kept: ongoing capital water project (NT — territory priority)
    'Northwest\xa0Territories,Behdzi Ahda First Nation,999,First Nation,'
    '4-001,Water and wastewater,New Water Treatment Plant,'
    'Construction of a new water treatment plant.,Ongoing,"$2,500,000.00",,,,,',
    # Kept: ongoing education build (ON)
    'Ontario,Aamjiwnaang First Nation,172,First Nation,'
    '4-002,Education infrastructure,School Expansion Phase 2,'
    'Expansion of the community school.,Ongoing,Not Available,,,,,',
    # Skipped: Completed
    'Ontario,Aamjiwnaang First Nation,172,First Nation,'
    '4-003,Water and wastewater,Lagoon Upgrade,'
    'Upgrade of the sewage lagoon.,Completed,"$1,000,000.00",,,,,',
    # Skipped: Housing category excluded
    'Ontario,Aamjiwnaang First Nation,172,First Nation,'
    '4-004,Housing,Renovation - 10 Units,'
    'Renovation of ten housing units.,Ongoing,Not Available,,,,,',
    # Skipped: capacity-enhancement program row
    'Ontario,Aamjiwnaang First Nation,172,First Nation,'
    '4-005,Education infrastructure,Capacity Enhancement - Inspections,'
    'Construction inspections training.,Ongoing,Not Available,,,,,',
    # Skipped: no construction keyword
    'Ontario,Aamjiwnaang First Nation,172,First Nation,'
    '4-006,Roads and bridges,Winter Road Maintenance Program,'
    'Seasonal maintenance.,Ongoing,Not Available,,,,,',
]


def _isc_zip_bytes():
    csv_text = _ISC_HEADER + "\n" + "\n".join(_ISC_ROWS) + "\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Indigenous_community_infrastructure.csv", csv_text)
    return buf.getvalue()


def test_isc_filters_and_prioritizes_territories(monkeypatch):
    zip_bytes = _isc_zip_bytes()
    monkeypatch.setattr(
        gov_sources.http_client, "get",
        lambda url, timeout=30, **kw: _FakeResp(content=zip_bytes))

    projects = gov_sources._fetch_isc_infrastructure()
    assert len(projects) == 2
    # Territory row sorted first
    assert projects[0]["province"] == "Northwest Territories"
    assert "New Water Treatment Plant" in projects[0]["name"]
    assert projects[0]["status"] == "Under Construction"
    assert projects[0]["discovery_source"] == "federal_registry"
    assert projects[0]["sector"] == "Water & Wastewater"
    assert projects[0]["value"] == "$2,500,000.00"
    # Non-territory second; no value field when Not Available
    assert projects[1]["province"] == "Ontario"
    assert "value" not in projects[1]
    assert projects[1]["sector"] == "Education"
    # Every emitted project satisfies the URL hard gate
    assert all(p["source_url"].startswith("http") for p in projects)


def test_isc_http_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(
        gov_sources.http_client, "get",
        lambda url, timeout=30, **kw: _FakeResp(status_code=500))
    assert gov_sources._fetch_isc_infrastructure() == []


# ── Registration in the master scrapers list ─────────────────────────────────

def test_new_scrapers_registered_in_fetch_registry_projects():
    src = inspect.getsource(gov_sources.fetch_registry_projects)
    assert "_scrape_nunavut_nirb" in src
    assert "_scrape_nwt_mvlwb" in src
    assert "_fetch_isc_infrastructure" in src
    # Existing northern scrapers must still be registered (additive only)
    assert "_scrape_yukon_yesab" in src
    assert "_scrape_nwt_mvrb" in src


# ── Corporate watchlist additions ─────────────────────────────────────────────

_WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "corporate_watchlist.json"

_EXPECTED_INDIGENOUS = [
    "Inuvialuit Development Corporation",
    "Makivvik Corporation",
    "Nunasi Corporation",
    "Athabasca Basin Development",
    "Des Nedhe Group",
    "Fort McKay Group of Companies",
    "Membertou Development Corporation",
    "Nch'kay Development Corporation",
    "Haisla Nation / HaiSea Marine",
    "Six Nations of the Grand River Development Corporation",
    "Whitecap Development Corporation",
    "Miawpukek Horizon Maritime",
    "Tlicho Investment Corporation",
    "Penticton Indian Band Development Corporation",
    "Osoyoos Indian Band Development Corporation",
]


def test_watchlist_indigenous_entries_added_additively():
    data = json.loads(_WATCHLIST_PATH.read_text(encoding="utf-8"))
    companies = data["companies"]
    names = {c["name"] for c in companies}

    # New Indigenous development corporations are all present
    for expected in _EXPECTED_INDIGENOUS:
        assert expected in names, f"missing watchlist entry: {expected}"

    # ADDITIVE ONLY: pre-existing entries untouched (spot-check a sample)
    for legacy in ("Suncor Energy", "Hydro-Québec", "Volkswagen Group Canada",
                   "Canada Infrastructure Bank"):
        assert legacy in names

    assert len(companies) >= 80
    assert data["_meta"]["total_companies"] == len(companies)

    # Schema parity with existing entries
    for c in companies:
        assert set(c.keys()) == {"name", "ticker", "sector", "hq_province",
                                 "newsroom_url"}

    indigenous = [c for c in companies if c["name"] in _EXPECTED_INDIGENOUS]
    assert all(c["sector"] == "indigenous" for c in indigenous)
    # newsroom_url is either a verified URL or null (Osoyoos has none)
    for c in indigenous:
        assert c["newsroom_url"] is None or c["newsroom_url"].startswith("https://")
