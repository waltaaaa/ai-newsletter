"""
test_triangulation.py — G8 triangulation axes, G12 republication zero-weight,
A6 confidence-decay event logging (quality-pass-1.4).
"""

import pytest


@pytest.fixture
def conn():
    """Fresh in-memory DB for each test."""
    from db import init_db
    c = init_db(":memory:")
    yield c
    c.close()


# ── G8: axis classification ──────────────────────────────────────


class TestClassifyAxis:
    @pytest.mark.parametrize("source,axis", [
        ("iaac_registry", "regulatory"),
        ("provincial_ea", "regulatory"),
        ("cer_registry", "regulatory"),
        ("federal_registry", "regulatory"),
        ("gov_api_bc_mpi", "regulatory"),
        ("sedar_filings", "financial_disclosure"),
        ("corporate_newswire", "financial_disclosure"),
        ("corporate_ir", "financial_disclosure"),
        ("procurement", "commercial"),
        ("buyandsell", "commercial"),
        ("municipal_dev_app", "commercial"),
        ("building_permit", "commercial"),
        ("lobbyist_registries", "pre_public"),  # must NOT hit 'registry' token
        ("key_people", "pre_public"),
        ("corporate_watchlist", "pre_public"),
        ("google_news_rss", "media"),
        ("rss_feed", "media"),
        ("bing_news", "media"),
        ("", "media"),
    ])
    def test_source_mapping(self, source, axis):
        from triangulation import classify_axis
        assert classify_axis(source) == axis

    def test_government_url_fallback(self):
        # NOTE: bare canada.ca is NOT matched by url_utils.GOV_DOMAIN_PATTERNS
        # (only subdomain patterns like \.gc\.ca$) — use a provincial domain.
        from triangulation import classify_axis
        assert classify_axis("", "https://www.alberta.ca/release/x") == "regulatory"

    def test_sedar_url_fallback(self):
        from triangulation import classify_axis
        assert classify_axis("", "https://www.sedarplus.ca/filing/123") == "financial_disclosure"

    def test_media_url_fallback(self):
        from triangulation import classify_axis
        assert classify_axis("", "https://example-news.ca/story") == "media"


class TestAxesSatisfied:
    def test_empty(self):
        from triangulation import axes_satisfied
        assert axes_satisfied([], []) == 0

    def test_single_media(self):
        from triangulation import axes_satisfied
        assert axes_satisfied(
            [{"url": "https://example-news.ca/a", "source": "google_news_rss"}],
            ["google_news_rss"]) == 1

    def test_authority_field_maps_regulatory(self):
        from triangulation import axes_satisfied
        assert axes_satisfied(
            [{"url": "https://x.ca/a", "authority": "government"}], []) == 1

    def test_distinct_axes_counted_once(self):
        from triangulation import axes_satisfied
        n = axes_satisfied(
            [{"url": "https://www.canada.ca/r1", "authority": "government"},
             {"url": "https://example-news.ca/a", "source": "google_news_rss"}],
            ["sedar_filings", "procurement", "iaac_registry", "google_news_rss"],
        )
        assert n == 4  # regulatory, media, financial_disclosure, commercial

    def test_string_evidence_entries(self):
        from triangulation import axes_satisfied
        assert axes_satisfied(["https://www.alberta.ca/r1"], []) == 1

    def test_max_five(self):
        from triangulation import axes_satisfied
        n = axes_satisfied(
            [], ["iaac_registry", "sedar_filings", "procurement",
                 "lobbyist_registries", "google_news_rss", "rss_feed"])
        assert n == 5


# ── G8: persisted column via upsert_project ──────────────────────


class TestAxesColumn:
    def test_upsert_populates_axes(self, conn):
        from db import upsert_project
        key = upsert_project(conn, {
            "name": "Axes Project", "province": "Alberta",
            "evidence": [{"url": "https://www.alberta.ca/r1",
                          "authority": "government"}],
            "discovery_source": "provincial_ea",
            "discovery_sources": ["provincial_ea", "google_news_rss"],
        })
        row = dict(conn.execute(
            "SELECT * FROM projects WHERE norm_key = ?", (key,)).fetchone())
        assert row["axes_satisfied"] == 2  # regulatory + media

    def test_axes_grow_on_merge(self, conn):
        from db import upsert_project
        key = upsert_project(conn, {
            "name": "Axes Project", "province": "Alberta",
            "evidence": [{"url": "https://example-news.ca/a",
                          "source": "google_news_rss"}],
            "discovery_source": "google_news_rss",
        })
        row = dict(conn.execute(
            "SELECT axes_satisfied FROM projects WHERE norm_key = ?", (key,)).fetchone())
        assert row["axes_satisfied"] == 1
        upsert_project(conn, {
            "name": "Axes Project", "province": "Alberta",
            "evidence": [{"url": "https://www.sedarplus.ca/f1",
                          "source": "sedar_filings"}],
            "discovery_source": "sedar_filings",
        })
        row = dict(conn.execute(
            "SELECT axes_satisfied FROM projects WHERE norm_key = ?", (key,)).fetchone())
        assert row["axes_satisfied"] == 2


# ── G12: content_hash + republication_of on the evidence table ───


def _make_project(conn, name="Evidence Host Project"):
    """Create a real project row (evidence FK is enforced) and return its rowid."""
    from db import upsert_project
    key = upsert_project(conn, {
        "name": name, "province": "Ontario",
        "evidence": [{"url": f"https://example-news.ca/{name.replace(' ', '-')}",
                      "source": "google_news_rss", "date": "2026-06-01"}],
        "discovery_source": "google_news_rss",
    })
    return conn.execute("SELECT rowid FROM projects WHERE norm_key = ?",
                        (key,)).fetchone()[0]


class TestRepublication:
    def test_republication_column_exists(self, conn):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(evidence)")}
        assert "republication_of" in cols
        assert "content_hash" in cols

    def test_content_hash_populated(self, conn):
        from db import insert_evidence
        pid = _make_project(conn)
        eid = insert_evidence(conn, pid, "https://a.ca/x",
                              title="Big Bridge Announced",
                              snippet="A $1B bridge was announced today.")
        row = conn.execute("SELECT content_hash, republication_of FROM evidence "
                           "WHERE id = ?", (eid,)).fetchone()
        assert row[0] is not None and len(row[0]) == 64
        assert row[1] is None

    def test_hash_normalizes_case_and_whitespace(self, conn):
        from db import _evidence_content_hash
        h1 = _evidence_content_hash("Big  Bridge\nAnnounced", "story   text")
        h2 = _evidence_content_hash("big bridge announced", "STORY TEXT")
        assert h1 == h2

    def test_empty_content_hash_is_null(self, conn):
        from db import insert_evidence
        pid = _make_project(conn)
        eid = insert_evidence(conn, pid, "https://a.ca/no-content")
        row = conn.execute("SELECT content_hash FROM evidence WHERE id = ?",
                           (eid,)).fetchone()
        assert row[0] is None

    def test_collision_same_project_marks_republication(self, conn):
        from db import insert_evidence
        pid = _make_project(conn)
        e1 = insert_evidence(conn, pid, "https://wire.ca/original",
                             title="Plant Expansion", snippet="Same wire copy.")
        e2 = insert_evidence(conn, pid, "https://local-news.ca/reprint",
                             title="Plant Expansion", snippet="Same wire copy.")
        assert e1 and e2
        row = conn.execute("SELECT republication_of FROM evidence WHERE id = ?",
                           (e2,)).fetchone()
        assert row[0] == e1
        # Original stays unmarked; both URLs kept
        assert conn.execute("SELECT republication_of FROM evidence WHERE id = ?",
                            (e1,)).fetchone()[0] is None
        assert conn.execute("SELECT COUNT(*) FROM evidence WHERE project_id = ?",
                            (pid,)).fetchone()[0] == 2

    def test_no_collision_across_projects(self, conn):
        from db import insert_evidence
        pid1 = _make_project(conn, "Host Project One")
        pid2 = _make_project(conn, "Host Project Two")
        insert_evidence(conn, pid1, "https://wire.ca/original",
                        title="Plant Expansion", snippet="Same wire copy.")
        e2 = insert_evidence(conn, pid2, "https://local-news.ca/reprint",
                             title="Plant Expansion", snippet="Same wire copy.")
        row = conn.execute("SELECT republication_of FROM evidence WHERE id = ?",
                           (e2,)).fetchone()
        assert row[0] is None

    def test_distinct_content_not_marked(self, conn):
        from db import insert_evidence
        pid = _make_project(conn)
        insert_evidence(conn, pid, "https://a.ca/one",
                        title="Story one", snippet="alpha")
        e2 = insert_evidence(conn, pid, "https://a.ca/two",
                             title="Story two", snippet="beta")
        assert conn.execute("SELECT republication_of FROM evidence WHERE id = ?",
                            (e2,)).fetchone()[0] is None


class TestRepublicationZeroWeight:
    def test_compute_confidence_ignores_republications(self, conn):
        """Republished evidence contributes zero — score equals the
        distinct-content-only project."""
        from db import insert_evidence
        from confidence_decay import compute_confidence
        # Project 1: gov row + media story + republication of the same story
        # on a HIGHER-weight domain (cbc.ca = business_media). Without the G12
        # filter the republication would add a new source_type (bigger
        # agreement bonus), inflating the score.
        pid1 = _make_project(conn, "Weight Project One")
        pid2 = _make_project(conn, "Weight Project Two")
        insert_evidence(conn, pid1, "https://www.alberta.ca/r1",
                        title="Gov release", snippet="official text")
        insert_evidence(conn, pid1, "https://media-a.ca/s",
                        title="Wire story", snippet="same copy")
        insert_evidence(conn, pid1, "https://www.cbc.ca/reprint",
                        title="Wire story", snippet="same copy")
        # Project 2: same distinct content only
        insert_evidence(conn, pid2, "https://www.alberta.ca/r1",
                        title="Gov release", snippet="official text")
        insert_evidence(conn, pid2, "https://media-a.ca/s",
                        title="Wire story", snippet="same copy")
        # Sanity: the reprint row was actually marked as a republication
        marked = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE project_id = ? "
            "AND republication_of IS NOT NULL", (pid1,)).fetchone()[0]
        assert marked == 1
        assert compute_confidence(pid1, conn) == compute_confidence(pid2, conn)

    def test_scorer_distinct_evidence_count(self):
        from confidence_scorer import _distinct_evidence_count
        evidence = [
            {"url": "https://a.ca/1", "name": "Wire story", "snippet": "same copy"},
            {"url": "https://b.ca/1", "name": "Wire story", "snippet": "same copy"},
            {"url": "https://a.ca/1", "name": "", "snippet": ""},  # dup URL
            {"url": "https://c.ca/1", "name": "Other story", "snippet": "different"},
        ]
        assert _distinct_evidence_count(evidence) == 2

    def test_corroboration_score_uses_distinct_count(self):
        from confidence_scorer import _corroboration_score
        dup = {"url": "https://a.ca/1", "name": "Same", "snippet": "copy"}
        reprint = {"url": "https://b.ca/1", "name": "Same", "snippet": "copy"}
        project = {"evidence": [dup, reprint, reprint], "discovery_sources": []}
        # 3 raw entries but only 1 distinct -> no corroboration bonus
        assert _corroboration_score(project) == 0.0


# ── A6: confidence decay event logging ───────────────────────────


class TestDecayEventLogging:
    def _make_stale_project(self, conn, days=100):
        from datetime import datetime, timedelta
        from db import upsert_project
        key = upsert_project(conn, {
            "name": "Stale Project", "province": "Ontario",
            "evidence": [{"url": "https://example-news.ca/old",
                          "source": "google_news_rss", "date": "2026-01-01"}],
            "discovery_source": "google_news_rss",
        })
        old = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn.execute("UPDATE projects SET lastSeen = ?, lastUpdated = ? "
                     "WHERE norm_key = ?", (old, old, key))
        conn.commit()
        return key

    def test_decay_writes_event(self, conn):
        from confidence_decay import apply_confidence_decay
        key = self._make_stale_project(conn, days=100)
        apply_confidence_decay(conn)
        rowid = conn.execute("SELECT rowid FROM projects WHERE norm_key = ?",
                             (key,)).fetchone()[0]
        events = conn.execute(
            "SELECT summary FROM project_events WHERE project_id = ? "
            "AND event_type = 'confidence_decay'", (rowid,)).fetchall()
        assert len(events) == 1
        summary = events[0][0]
        assert "->" in summary
        assert "days since" in summary
        assert "bucket -" in summary

    def test_decay_event_not_duplicated_across_runs(self, conn):
        """Second run with unchanged display value writes no new event."""
        from confidence_decay import apply_confidence_decay
        key = self._make_stale_project(conn, days=100)
        apply_confidence_decay(conn)
        apply_confidence_decay(conn)
        rowid = conn.execute("SELECT rowid FROM projects WHERE norm_key = ?",
                             (key,)).fetchone()[0]
        n = conn.execute(
            "SELECT COUNT(*) FROM project_events WHERE project_id = ? "
            "AND event_type = 'confidence_decay'", (rowid,)).fetchone()[0]
        assert n == 1

    def test_fresh_project_gets_no_decay_event(self, conn):
        from db import upsert_project
        from confidence_decay import apply_confidence_decay
        key = upsert_project(conn, {
            "name": "Fresh Project", "province": "Ontario",
            "evidence": [{"url": "https://example-news.ca/new",
                          "source": "google_news_rss", "date": "2026-06-09"}],
            "discovery_source": "google_news_rss",
        })
        apply_confidence_decay(conn)
        rowid = conn.execute("SELECT rowid FROM projects WHERE norm_key = ?",
                             (key,)).fetchone()[0]
        n = conn.execute(
            "SELECT COUNT(*) FROM project_events WHERE project_id = ? "
            "AND event_type = 'confidence_decay'", (rowid,)).fetchone()[0]
        assert n == 0
