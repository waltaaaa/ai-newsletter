"""
test_value_semantics.py — G7 (quality-pass-1.4): value semantics columns,
normalization defaults, and government-beats-media value-merge precedence.
"""

import pytest


@pytest.fixture
def conn():
    """Fresh in-memory DB for each test."""
    from db import init_db
    c = init_db(":memory:")
    yield c
    c.close()


def _base_project(**overrides):
    p = {
        "name": "Test Energy Project",
        "province": "Ontario",
        "sector": "power_energy",
        "status": "Proposed",
        "evidence": [{
            "url": "https://example-news.ca/article-1",
            "source": "google_news_rss",
            "date": "2026-06-01",
        }],
        "discovery_source": "google_news_rss",
    }
    p.update(overrides)
    return p


def _get_row(conn, key):
    row = conn.execute("SELECT * FROM projects WHERE norm_key = ?", (key,)).fetchone()
    return dict(row) if row else None


# ── Columns + migration defaults ─────────────────────────────────


class TestColumns:
    def test_new_columns_exist(self, conn):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
        assert {"currency", "value_low", "value_high", "value_scope",
                "axes_satisfied"} <= cols

    def test_migration_is_idempotent(self, conn):
        from db import init_db
        # init_db on the same connection path must not raise
        c2 = init_db(":memory:")
        cols = {r[1] for r in c2.execute("PRAGMA table_info(projects)")}
        assert "currency" in cols
        c2.close()

    def test_insert_defaults(self, conn):
        from db import upsert_project
        key = upsert_project(conn, _base_project())
        row = _get_row(conn, key)
        assert row["currency"] == "CAD"
        assert row["value_low"] is None
        assert row["value_high"] is None
        assert row["value_scope"] == ""

    def test_insert_persists_value_semantics(self, conn):
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="US$100M-$200M",
            currency="USD", value_low=100.0, value_high=200.0,
            value_scope="phase",
        ))
        row = _get_row(conn, key)
        assert row["currency"] == "USD"
        assert row["value_low"] == 100.0
        assert row["value_high"] == 200.0
        assert row["value_scope"] == "phase"

    def test_point_value_does_not_fabricate_range(self, conn):
        from db import upsert_project
        key = upsert_project(conn, _base_project(value="C$500M"))
        row = _get_row(conn, key)
        assert row["value_low"] is None
        assert row["value_high"] is None


# ── build_project_document normalization defaults ────────────────


class TestSchemaDefaults:
    def _extracted(self, **overrides):
        d = {
            "name": "Schema Test Project",
            "source_url": "https://example.com/story",
            "value_millions": 500,
        }
        d.update(overrides)
        return d

    def test_currency_defaults_cad_when_absent(self):
        from project_schema import build_project_document
        doc = build_project_document(self._extracted())
        assert doc["currency"] == "CAD"

    def test_currency_defaults_cad_when_empty(self):
        from project_schema import build_project_document
        doc = build_project_document(self._extracted(currency=""))
        assert doc["currency"] == "CAD"

    def test_point_value_leaves_range_null(self):
        from project_schema import build_project_document
        doc = build_project_document(self._extracted())
        assert doc["value_low"] is None
        assert doc["value_high"] is None
        assert doc["value_scope"] == ""

    def test_explicit_range_passes_through(self):
        from project_schema import build_project_document
        doc = build_project_document(self._extracted(
            currency="USD", value_low=400, value_high=600, value_scope="program"))
        assert doc["currency"] == "USD"
        assert doc["value_low"] == 400
        assert doc["value_high"] == 600
        assert doc["value_scope"] == "program"


# ── Extraction prompts request the four fields ───────────────────


class TestPrompts:
    def test_recovery_prompt_requests_fields(self):
        from claude_reasoning import RECOVERY_SYSTEM
        for field in ("currency", "value_low", "value_high", "value_scope"):
            assert field in RECOVERY_SYSTEM

    def test_selective_prompt_requests_scope_and_currency(self):
        from claude_reasoning import SELECTIVE_EXTRACT_SYSTEM
        assert "value_scope" in SELECTIVE_EXTRACT_SYSTEM
        assert "capex_currency" in SELECTIVE_EXTRACT_SYSTEM
        assert "capex_low" in SELECTIVE_EXTRACT_SYSTEM
        assert "capex_high" in SELECTIVE_EXTRACT_SYSTEM


# ── Merge precedence: government beats media regardless of recency ──


GOV_EVIDENCE = [{
    "url": "https://www.canada.ca/en/release-1",
    "source": "federal_registry",
    "date": "2026-01-15",
    "authority": "government",
}]

MEDIA_EVIDENCE = [{
    "url": "https://example-news.ca/article-2",
    "source": "google_news_rss",
    "date": "2026-06-09",
}]


class TestValueMergePrecedence:
    def test_gov_value_not_overwritten_by_media(self, conn):
        """Existing gov-backed value beats a NEWER media value."""
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$500M", evidence=list(GOV_EVIDENCE),
            has_government_source=True,
            discovery_source="federal_registry"))
        upsert_project(conn, _base_project(
            value="C$900M", evidence=list(MEDIA_EVIDENCE)))
        row = _get_row(conn, key)
        assert row["value"] == "C$500M"
        assert row["parsed_value"] == 500_000_000

    def test_gov_value_keeps_value_semantics_fields(self, conn):
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$500M", evidence=list(GOV_EVIDENCE),
            has_government_source=True, value_scope="phase",
            discovery_source="federal_registry"))
        upsert_project(conn, _base_project(
            value="C$900M", evidence=list(MEDIA_EVIDENCE),
            value_scope="program"))
        row = _get_row(conn, key)
        assert row["value_scope"] == "phase"

    def test_gov_value_beats_existing_media_value(self, conn):
        """Incoming gov-backed value replaces an older media value."""
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$900M", evidence=list(MEDIA_EVIDENCE)))
        upsert_project(conn, _base_project(
            value="C$500M", evidence=list(GOV_EVIDENCE),
            has_government_source=True,
            discovery_source="federal_registry"))
        row = _get_row(conn, key)
        assert row["value"] == "C$500M"

    def test_media_tie_keeps_existing_behavior(self, conn):
        """Media vs media: incoming non-empty value still wins (unchanged)."""
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$300M", evidence=list(MEDIA_EVIDENCE)))
        upsert_project(conn, _base_project(value="C$350M"))
        row = _get_row(conn, key)
        assert row["value"] == "C$350M"

    def test_gov_tie_keeps_existing_behavior(self, conn):
        """Gov vs gov: incoming non-empty value still wins (unchanged)."""
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$500M", evidence=list(GOV_EVIDENCE),
            has_government_source=True,
            discovery_source="federal_registry"))
        upsert_project(conn, _base_project(
            value="C$550M",
            evidence=[{"url": "https://www.ontario.ca/release-2",
                       "source": "provincial_ea", "date": "2026-06-09",
                       "authority": "government"}]))
        row = _get_row(conn, key)
        assert row["value"] == "C$550M"

    def test_placeholder_incoming_value_never_wins(self, conn):
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$500M", evidence=list(GOV_EVIDENCE),
            has_government_source=True,
            discovery_source="federal_registry"))
        upsert_project(conn, _base_project(
            value="—", evidence=list(MEDIA_EVIDENCE)))
        row = _get_row(conn, key)
        assert row["value"] == "C$500M"

    def test_evidence_urls_never_lost_during_precedence(self, conn):
        import json as _json
        from db import upsert_project
        key = upsert_project(conn, _base_project(
            value="C$500M", evidence=list(GOV_EVIDENCE),
            has_government_source=True,
            discovery_source="federal_registry"))
        upsert_project(conn, _base_project(
            value="C$900M", evidence=list(MEDIA_EVIDENCE)))
        row = _get_row(conn, key)
        urls = {e["url"] for e in _json.loads(row["evidence"])}
        assert GOV_EVIDENCE[0]["url"] in urls
        assert MEDIA_EVIDENCE[0]["url"] in urls


# ── project_sync passthrough ─────────────────────────────────────


class TestSyncPassthrough:
    def test_upsert_flat_projects_carries_value_semantics(self, conn):
        from project_sync import upsert_flat_projects
        upsert_flat_projects(conn, [{
            "name": "Flat Sync Project",
            "province": "Ontario",
            "value": "US$120M-$180M",
            "currency": "USD",
            "value_low": 120.0,
            "value_high": 180.0,
            "value_scope": "program",
            "sources": ["https://example.com/flat-1"],
            "evidence": [{"url": "https://example.com/flat-1",
                          "source": "google_news_rss", "date": "2026-06-01"}],
            "discovery_source": "google_news_rss",
        }])
        row = conn.execute(
            "SELECT * FROM projects WHERE name = 'Flat Sync Project'").fetchone()
        assert row is not None
        row = dict(row)
        assert row["currency"] == "USD"
        assert row["value_low"] == 120.0
        assert row["value_high"] == 180.0
        assert row["value_scope"] == "program"
