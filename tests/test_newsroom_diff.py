"""Tests for corporate_newsroom_diff.py (A1) — URL extraction from fixture
sitemap XML / newsroom HTML, dedup against a seeded in-memory documents
table, no network anywhere.

Also hosts the OFFLINE tests for tools/wikidata_alias_harvest.py (A2) —
the quality-pass instructions restrict new tests to four named files, so the
alias-harvest tests live here rather than in a fifth file."""
import json
import sqlite3

import pytest

import corporate_newsroom_diff as cnd
from tools import wikidata_alias_harvest as wah


DOCUMENTS_DDL = """
CREATE TABLE documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    url_normalized  TEXT UNIQUE NOT NULL,
    content_hash    TEXT,
    title           TEXT,
    published_date  TEXT,
    fetch_date      TEXT DEFAULT (datetime('now')),
    source_tier     TEXT,
    source_type     TEXT,
    fetch_status    TEXT DEFAULT 'fetched',
    is_relevant     INTEGER,
    classification_json TEXT,
    language        TEXT DEFAULT 'en',
    created_at      TEXT DEFAULT (datetime('now'))
)"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(DOCUMENTS_DDL)
    yield c
    c.close()


SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://www.example.com/news/2026/big-pipeline-expansion</loc>
    <news:news>
      <news:title>Big Pipeline Expansion Announced</news:title>
      <news:publication_date>2026-06-01</news:publication_date>
    </news:news>
  </url>
  <url>
    <loc>https://www.example.com/news/2026/q1-results</loc>
    <lastmod>2026-05-01</lastmod>
  </url>
  <url>
    <loc>https://www.example.com/news/2026/q1-results</loc>
  </url>
</urlset>"""

NEWSROOM_HTML = """
<html><body>
  <nav><a href="/newsroom">Newsroom</a><a href="/about">About</a></nav>
  <a href="/newsroom/2026/2026-06-01-major-lng-expansion-announced/">
    Major LNG expansion announced</a>
  <a href="https://www.example.com/media/news-releases/new-mine-approved-2026">
    New mine approved</a>
  <a href="/newsroom/2026/2026-06-01-major-lng-expansion-announced/#section">
    duplicate via fragment</a>
  <a href="https://othersite.com/news/2026/offsite-story-about-us">offsite</a>
  <a href="/newsroom/glossary">Glossary</a>
  <a href="/careers/join-us-today-2026">Careers</a>
  <a href="/news/report.pdf">PDF report</a>
  <a href="mailto:x@example.com">mail</a>
</body></html>"""


class TestSitemapExtraction:
    def test_news_sitemap_titles_and_dates(self):
        items = cnd.extract_urls_from_sitemap(SITEMAP_XML)
        assert len(items) == 2  # third <url> is a duplicate loc
        first = items[0]
        assert first["url"].endswith("big-pipeline-expansion")
        assert first["title"] == "Big Pipeline Expansion Announced"
        assert first["published"] == "2026-06-01"

    def test_lastmod_used_when_no_news_date(self):
        items = cnd.extract_urls_from_sitemap(SITEMAP_XML)
        assert items[1]["published"] == "2026-05-01"

    def test_invalid_xml_returns_empty(self):
        assert cnd.extract_urls_from_sitemap("<not really xml") == []


class TestHtmlExtraction:
    def test_extracts_article_links_only(self):
        items = cnd.extract_urls_from_html(
            NEWSROOM_HTML, "https://www.example.com/newsroom")
        urls = {i["url"] for i in items}
        assert ("https://www.example.com/newsroom/2026/"
                "2026-06-01-major-lng-expansion-announced/") in urls
        assert ("https://www.example.com/media/news-releases/"
                "new-mine-approved-2026") in urls
        assert len(items) == 2  # nav, offsite, glossary, careers, pdf dropped

    def test_fragment_deduped(self):
        items = cnd.extract_urls_from_html(
            NEWSROOM_HTML, "https://www.example.com/newsroom")
        assert len({i["url"] for i in items}) == len(items)

    def test_titles_from_anchor_text(self):
        items = cnd.extract_urls_from_html(
            NEWSROOM_HTML, "https://www.example.com/newsroom")
        titles = {i["title"] for i in items}
        assert "Major LNG expansion announced" in titles

    def test_dispatch_detects_sitemap_vs_html(self):
        assert cnd.extract_article_urls(SITEMAP_XML, "https://x.com")[0][
            "title"] == "Big Pipeline Expansion Announced"
        assert cnd.extract_article_urls(
            NEWSROOM_HTML, "https://www.example.com/newsroom")


class TestLooksLikeArticle:
    def test_listing_root_rejected(self):
        assert not cnd._looks_like_article(
            "https://www.example.com/newsroom/", "example.com")

    def test_nav_leaf_without_slug_rejected(self):
        assert not cnd._looks_like_article(
            "https://www.example.com/news-and-stories/glossary", "example.com")

    def test_dated_release_accepted(self):
        assert cnd._looks_like_article(
            "https://www.example.com/announcements/2026/2026-05-01-q1-results/",
            "example.com")

    def test_other_domain_rejected(self):
        assert not cnd._looks_like_article(
            "https://evil.com/news/2026/totally-real-story", "example.com")


class TestDocumentsDiff:
    COMPANY = {"name": "Example Corp", "sector": "oil_gas",
               "hq_province": "AB", "newsroom_url": "https://www.example.com/news"}

    def test_seen_url_not_emitted(self, conn):
        import db as dbmod
        seen_url = "https://www.example.com/news/2026/old-story"
        dbmod.insert_document(conn, seen_url, title="Old story",
                              source_tier="corporate_newsroom")
        candidates = [
            {"url": seen_url, "title": "Old story", "published": ""},
            {"url": "https://www.example.com/news/2026/new-story",
             "title": "New story", "published": "2026-06-09"},
        ]
        out = cnd.diff_new_urls(conn, self.COMPANY, candidates)
        assert len(out) == 1
        assert out[0]["url"].endswith("new-story")
        assert out[0]["source"] == "Example Corp newsroom"
        assert out[0]["discovery_source"] == "corporate_newsroom_diff"

    def test_second_run_emits_nothing(self, conn):
        candidates = [{"url": "https://www.example.com/news/2026/story-x",
                       "title": "Story X", "published": ""}]
        first = cnd.diff_new_urls(conn, self.COMPANY, candidates)
        second = cnd.diff_new_urls(conn, self.COMPANY, candidates)
        assert len(first) == 1
        assert second == []

    def test_article_shape_for_filter(self, conn):
        candidates = [{"url": "https://www.example.com/news/2026/story-y",
                       "title": "Story Y", "published": "2026-06-08"}]
        (article,) = cnd.diff_new_urls(conn, self.COMPANY, candidates)
        for field in ("title", "url", "snippet", "source", "published"):
            assert field in article

    def test_collect_with_mocked_fetch_no_network(self, conn, monkeypatch):
        monkeypatch.setattr(cnd, "_fetch", lambda url, timeout=15: NEWSROOM_HTML
                            if "example.com" in url else None)
        arts = cnd.collect_new_articles(
            conn, companies=[self.COMPANY], jitter=False)
        assert len(arts) == 2
        # one fetch per domain: a second company on the same domain is skipped
        calls = []
        monkeypatch.setattr(cnd, "_fetch",
                            lambda url, timeout=15: calls.append(url) or NEWSROOM_HTML)
        twin = dict(self.COMPANY, name="Example Twin")
        cnd.collect_new_articles(conn, companies=[self.COMPANY, twin],
                                 jitter=False)
        assert len(calls) == 1

    def test_fetch_failure_logged_not_raised(self, conn, monkeypatch):
        monkeypatch.setattr(cnd, "_fetch", lambda url, timeout=15: None)
        assert cnd.collect_new_articles(
            conn, companies=[self.COMPANY], jitter=False) == []


class TestWatchlist:
    def test_watchlist_loads_companies_with_newsroom_urls(self):
        companies = cnd.load_watchlist()
        assert len(companies) >= 50
        assert all(c["newsroom_url"].startswith("http") for c in companies)


# ─────────────────────────────────────────────────────────────────────────────
# A2 — wikidata_alias_harvest offline tests (mocked _get_json, no network)
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanProponent:
    def test_junk_rejected(self):
        for junk in ("", "  ", "N/A", "Various", "Multiple", "TBD", "abc"):
            assert wah.clean_proponent(junk) is None

    def test_multi_org_strings_rejected(self):
        assert wah.clean_proponent("Acme / Beta Joint Venture") is None
        assert wah.clean_proponent("Suncor; Cenovus") is None

    def test_inverted_municipal_names_uninverted(self):
        assert wah.clean_proponent("Whitehorse, City of") == "City of Whitehorse"
        assert wah.clean_proponent("Nova Scotia, Province of") == \
            "Province of Nova Scotia"

    def test_plain_name_passthrough(self):
        # trailing punctuation is stripped by design
        assert wah.clean_proponent("  Enbridge   Inc. ") == "Enbridge Inc"


class TestWikidataMocked:
    SEARCH_RESPONSE = {"search": [
        {"id": "Q999", "label": "Concept of Transport",
         "description": "movement of goods", "match": {"text": "Transport"}},
        {"id": "Q1339966", "label": "Enbridge",
         "description": "Canadian pipeline company",
         "match": {"text": "Enbridge"}, "aliases": []},
    ]}
    ENTITY_RESPONSE = {"entities": {"Q1339966": {
        "labels": {"en": {"value": "Enbridge"},
                   "fr": {"value": "Enbridge"}},
        "aliases": {"en": [{"value": "Enbridge Inc"},
                           {"value": "Enbridge Inc."}],
                    "fr": [{"value": "Enbridge Inc"}]},
    }}}

    def test_search_entity_requires_org_description(self, monkeypatch):
        monkeypatch.setattr(wah, "_get_json",
                            lambda params: self.SEARCH_RESPONSE)
        hit = wah.search_entity("Enbridge")
        assert hit["id"] == "Q1339966"  # concept entity skipped

    def test_search_entity_rejects_loose_label(self, monkeypatch):
        monkeypatch.setattr(wah, "_get_json", lambda params: {"search": [
            {"id": "Q1", "label": "Completely Different Company",
             "description": "a company", "match": {"text": "whatever"}}]})
        assert wah.search_entity("Enbridge") is None

    def test_fetch_aliases_dedupes_en_fr(self, monkeypatch):
        monkeypatch.setattr(wah, "_get_json",
                            lambda params: self.ENTITY_RESPONSE)
        aliases = wah.fetch_aliases("Q1339966")
        assert aliases == ["Enbridge", "Enbridge Inc", "Enbridge Inc."]

    def test_harvest_excludes_self_alias(self, monkeypatch):
        def fake(params):
            if params.get("action") == "wbsearchentities":
                return self.SEARCH_RESPONSE
            return self.ENTITY_RESPONSE
        monkeypatch.setattr(wah, "_get_json", fake)
        result = wah.harvest_for_name("Enbridge")
        assert result["entity_id"] == "Q1339966"
        assert "Enbridge" not in result["aliases"]
        assert "Enbridge Inc" in result["aliases"]

    def test_api_failure_returns_none(self, monkeypatch):
        monkeypatch.setattr(wah, "_get_json", lambda params: {})
        assert wah.search_entity("Enbridge") is None
        assert wah.harvest_for_name("Enbridge") is None


class TestSnapshotWrite:
    def test_snapshot_merges_additively(self, tmp_path):
        path = tmp_path / "aliases.json"
        wah.write_snapshot([{"name": "Enbridge", "entity_id": "Q1",
                             "label": "Enbridge",
                             "aliases": ["Enbridge Inc"]}], path=path)
        wah.write_snapshot([{"name": "Enbridge", "entity_id": "Q1",
                             "label": "Enbridge",
                             "aliases": ["Enbridge Inc.", "Enbridge Inc"]},
                            {"name": "BC Hydro", "entity_id": "Q2",
                             "label": "BC Hydro",
                             "aliases": ["British Columbia Hydro and Power Authority"]}],
                           path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["Enbridge"] == ["Enbridge Inc", "Enbridge Inc."]
        assert data["BC Hydro"] == ["British Columbia Hydro and Power Authority"]
