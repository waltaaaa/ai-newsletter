"""Tests for council_agenda_monitor.py (A3) — keyword scanning and parsing
against fixture HTML/JSON. No network: HTTP helpers are monkeypatched."""
import pytest

import council_agenda_monitor as cam


ESCRIBE_CALENDAR_JSON = {"d": [
    {"ID": "b821fe29-195b-4d3a-ab41-03290d7c23ea",
     "MeetingName": "Planning and Housing Committee",
     "StartDate": "2026/06/17 09:30:00"},
    {"ID": "c7777777-aaaa-bbbb-cccc-000000000001",
     "MeetingName": "City Council",
     "StartDate": "2026/06/24 10:00:00"},
    {"ID": "", "MeetingName": "Broken row", "StartDate": ""},
]}

ESCRIBE_AGENDA_HTML = """
<html><body>
 <div class="AgendaItemContainer">
   <a class="AgendaItemTitle" href="#i1">1. Declarations of Interest</a>
   <a class="AgendaItemTitle" href="#i2">
      3.1 Zoning By-law Amendment - 1770 Heatherington Road</a>
   <a class="AgendaItemTitle" href="#i3">
      4.2 Capital Budget Adjustment - $25 million Trillium Line works</a>
   <a class="AgendaItemTitle" href="#i4">
      4.2 Capital Budget Adjustment - $25 million Trillium Line works</a>
   <a class="AgendaItemTitle" href="#i5">5. Adjournment of meeting</a>
 </div>
</body></html>"""

WINDSOR_HTML = """
<html><body><table>
 <tr><td>
  <a href="https://www.citywindsor.ca/documents/city-hall/city-council-meetings/Council-2026/06-08/Agenda.pdf">Agenda</a>
  <a href="https://www.citywindsor.ca/documents/city-hall/city-council-meetings/Council-2026/06-08/Item11.2-RezoningApplication.pdf">Item 11.2 - Rezoning Application</a>
 </td></tr>
 <tr><td>
  <a href="https://www.citywindsor.ca/documents/city-hall/city-council-meetings/Standing%20Committees/2026/DHSC/06-01/Item10.1-AppendicesB&amp;C.pdf">Item 10.1 - S 50/2026 - Appendices B &amp; C</a>
  <a href="/Tools">not a pdf</a>
 </td></tr>
</table></body></html>"""


class TestScanTitle:
    def test_keyword_hit(self):
        assert "rezoning" in cam.scan_title("Rezoning Application - 123 Main St")

    def test_multiword_keyword(self):
        hits = cam.scan_title("Zoning By-law Amendment - Heatherington Road")
        assert "zoning by-law" in hits

    def test_dollar_regex(self):
        hits = cam.scan_title("Award of contract for $25 million arena works")
        assert any(h.startswith("dollar:") for h in hits)
        assert any("$25 million" in h for h in hits)

    def test_dollar_regex_billions_short_form(self):
        assert any(h.startswith("dollar:")
                   for h in cam.scan_title("a $1.4B commitment"))

    def test_no_signal(self):
        assert cam.scan_title("Declarations of Interest") == []
        assert cam.scan_title("") == []

    def test_case_insensitive(self):
        assert cam.scan_title("INFRASTRUCTURE update") == ["infrastructure"]


class TestEscribeParsing:
    def test_parse_meetings(self):
        ms = cam.parse_escribe_meetings(ESCRIBE_CALENDAR_JSON)
        assert len(ms) == 2  # broken row dropped
        assert ms[0]["id"].startswith("b821fe29")
        assert ms[0]["name"] == "Planning and Housing Committee"
        assert ms[0]["start"] == "2026-06-17"

    def test_parse_meetings_empty_payload(self):
        assert cam.parse_escribe_meetings({}) == []
        assert cam.parse_escribe_meetings(None) == []

    def test_parse_agenda_titles(self):
        titles = cam.parse_escribe_agenda_titles(ESCRIBE_AGENDA_HTML)
        assert "Zoning By-law Amendment - 1770 Heatherington Road" in titles
        # numbering prefix stripped, duplicates collapsed
        assert titles.count(
            "Capital Budget Adjustment - $25 million Trillium Line works") == 1
        assert "Declarations of Interest" in titles

    def test_collect_escribe_no_network(self, monkeypatch):
        monkeypatch.setattr(cam, "_post_json",
                            lambda url, payload: ESCRIBE_CALENDAR_JSON)
        monkeypatch.setattr(cam, "_get", lambda url: ESCRIBE_AGENDA_HTML)
        monkeypatch.setattr(cam.time, "sleep", lambda s: None)
        arts = cam.collect_escribe("Ottawa", "https://pub-ottawa.example/")
        # 2 meetings x 2 signal-bearing titles (zoning by-law + capital/$)
        assert len(arts) == 4
        a = arts[0]
        assert a["discovery_source"] == "council_agenda"
        assert a["cma"] == "Ottawa"
        assert a["published"] == "2026-06-17"
        assert "Planning and Housing Committee" in a["source"]
        for field in ("title", "url", "snippet", "source", "published"):
            assert a[field] is not None

    def test_collect_escribe_calendar_failure(self, monkeypatch):
        monkeypatch.setattr(cam, "_post_json", lambda url, payload: None)
        assert cam.collect_escribe("Ottawa", "https://x.example/") == []


class TestWindsorParsing:
    def test_parse_links_dates_and_committees(self):
        docs = cam.parse_windsor_agenda_links(
            WINDSOR_HTML, "https://opendata.citywindsor.ca/Tools/CouncilAgendas")
        by_url = {d["url"]: d for d in docs}
        council = next(d for d in docs if "Item11.2" in d["url"])
        assert council["published"] == "2026-06-08"
        assert council["meeting"] == "Council"
        committee = next(d for d in docs if "DHSC" in d["url"])
        assert committee["published"] == "2026-06-01"
        assert committee["meeting"] == "DHSC"
        assert all(".pdf" in u.lower() for u in by_url)

    def test_titles_combine_text_and_filename(self):
        docs = cam.parse_windsor_agenda_links(
            WINDSOR_HTML, "https://opendata.citywindsor.ca/Tools/CouncilAgendas")
        rezoning = next(d for d in docs if "Rezoning" in d["url"])
        assert "Rezoning" in rezoning["title"]

    def test_collect_windsor_no_network(self, monkeypatch):
        monkeypatch.setattr(cam, "_get", lambda url: WINDSOR_HTML)
        # freeze the recency window around the fixture dates
        import datetime as dt

        class FakeDate(dt.date):
            @classmethod
            def today(cls):
                return cls(2026, 6, 10)
        monkeypatch.setattr(cam, "date", FakeDate)
        arts = cam.collect_windsor("Windsor", "https://x.example/")
        assert len(arts) == 1  # only the rezoning item carries a keyword
        assert arts[0]["cma"] == "Windsor"
        assert "rezoning" in arts[0]["snippet"].lower()

    def test_collect_windsor_fetch_failure(self, monkeypatch):
        monkeypatch.setattr(cam, "_get", lambda url: None)
        assert cam.collect_windsor("Windsor", "https://x.example/") == []


class TestCollectAgendaItems:
    def test_pilot_config_has_three_cmas_two_platforms(self):
        assert len(cam.PILOT_CMAS) == 3
        platforms = {cfg["platform"] for cfg in cam.PILOT_CMAS.values()}
        assert platforms == {"escribe", "windsor_opendata"}

    def test_unknown_platform_skipped(self, monkeypatch):
        arts = cam.collect_agenda_items(
            {"Fakeville": {"platform": "legistar", "base": "https://x/"}})
        assert arts == []

    def test_per_cma_failure_isolated(self, monkeypatch):
        def boom(cma, base, max_meetings=8):
            raise RuntimeError("driver blew up")
        monkeypatch.setattr(cam, "collect_escribe", boom)
        monkeypatch.setattr(cam, "_get", lambda url: WINDSOR_HTML)
        import datetime as dt

        class FakeDate(dt.date):
            @classmethod
            def today(cls):
                return cls(2026, 6, 10)
        monkeypatch.setattr(cam, "date", FakeDate)
        arts = cam.collect_agenda_items(cam.PILOT_CMAS)
        # eScribe CMAs fail but Windsor still returns its item
        assert len(arts) == 1
        assert arts[0]["cma"] == "Windsor"

    def test_make_article_shape(self):
        a = cam.make_article("Ottawa", "T", "http://u", "2026-06-10",
                             "City Council", ["capital"])
        assert a["discovery_source"] == "council_agenda"
        assert set(a) >= {"title", "url", "snippet", "source", "published"}
