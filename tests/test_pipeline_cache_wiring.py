"""
tests/test_pipeline_cache_wiring.py — E-7 pipeline_cache wiring.

Covers:
  - PipelineCache set/get round-trip against the real `cache` table
  - TTL expiry returns a miss (and deletes the row)
  - semantic dedup embedding-cache hit avoids calling the (faked) NIM client
  - snippet enhancer page-text cache hit avoids the page fetch
  - both paths are no-ops when no conn/cache is available
"""

import hashlib
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db
from pipeline_cache import PipelineCache

import semantic_article_dedup
import snippet_enhancer


class TestCacheRoundTrip(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.cache = PipelineCache(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_set_get_round_trip_str(self):
        self.cache.set("https://example.com/a", "extracted page text", "page_text")
        self.assertEqual(
            self.cache.get("https://example.com/a", "page_text"),
            "extracted page text")

    def test_set_get_round_trip_list(self):
        vec = [0.1, 0.2, 0.3]
        self.cache.set("somekey", vec, "embedding")
        self.assertEqual(self.cache.get("somekey", "embedding"), vec)

    def test_miss_returns_none(self):
        self.assertIsNone(self.cache.get("absent", "page_text"))

    def test_type_isolation(self):
        self.cache.set("k1", "text", "page_text")
        self.assertIsNone(self.cache.get("k1", "embedding"))

    def test_ttl_expiry(self):
        self.cache.set("k-exp", "old value", "page_text", ttl_days=14)
        # Force the row into the past
        past = (datetime.utcnow() - timedelta(days=1)).isoformat()
        self.conn.execute(
            "UPDATE cache SET expires_at = ? WHERE cache_key = ?", (past, "k-exp"))
        self.conn.commit()
        self.assertIsNone(self.cache.get("k-exp", "page_text"))
        # Expired row is deleted on read
        row = self.conn.execute(
            "SELECT 1 FROM cache WHERE cache_key = ?", ("k-exp",)).fetchone()
        self.assertIsNone(row)


class _FakeNimClient:
    """Counts embed calls; returns deterministic distinct embeddings."""

    def __init__(self):
        self.calls = 0

    def embed_sync(self, texts):
        self.calls += 1
        out = []
        for i, _ in enumerate(texts):
            vec = [0.0] * 8
            vec[i % 8] = 1.0
            out.append(vec)
        return out


def _articles():
    return [
        {"title": "Toronto transit expansion announced",
         "summary": "A new subway line worth $5B announced for Toronto."},
        {"title": "Calgary refinery retrofit moves ahead",
         "summary": "The refinery retrofit project enters construction phase."},
    ]


class TestEmbeddingCacheWiring(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.fake = _FakeNimClient()
        self._orig_get_client = semantic_article_dedup.get_client
        semantic_article_dedup.get_client = lambda: self.fake

    def tearDown(self):
        semantic_article_dedup.get_client = self._orig_get_client
        self.conn.close()

    def test_cache_hit_avoids_nim_call(self):
        arts = _articles()
        cache = PipelineCache(self.conn)
        # Pre-populate embeddings for both article texts (orthogonal vectors)
        for i, art in enumerate(arts):
            text = semantic_article_dedup._article_text(art)
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            vec = [0.0] * 8
            vec[i] = 1.0
            cache.set(key, vec, "embedding")

        result, dropped = semantic_article_dedup.semantic_deduplicate_articles(
            arts, conn=self.conn)
        self.assertEqual(self.fake.calls, 0)  # full cache hit — no NIM call
        self.assertEqual(len(result), 2)
        self.assertEqual(dropped, 0)

    def test_miss_calls_nim_then_populates_cache(self):
        arts = _articles()
        result, dropped = semantic_article_dedup.semantic_deduplicate_articles(
            arts, conn=self.conn)
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(len(result), 2)
        # Second run: embeddings now cached, no further NIM call
        result2, _ = semantic_article_dedup.semantic_deduplicate_articles(
            arts, conn=self.conn)
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(len(result2), 2)

    def test_no_conn_is_a_noop_passthrough(self):
        arts = _articles()
        result, dropped = semantic_article_dedup.semantic_deduplicate_articles(
            arts, conn=None)
        self.assertEqual(self.fake.calls, 1)  # straight to NIM, no cache layer
        self.assertEqual(len(result), 2)
        self.assertEqual(dropped, 0)


class TestPageTextCacheWiring(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.cache = PipelineCache(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_cache_hit_avoids_fetch(self):
        url = "https://news.example.com/story?utm_source=feed"
        key = snippet_enhancer._page_text_cache_key(url)
        # Normalized key strips the tracking param
        self.assertNotIn("utm_source", key)
        self.cache.set(key, "Cached article body text.", "page_text")

        # If the cache were missed this would hit the network and fail/return ""
        text = snippet_enhancer._fetch_article_text(url, cache=self.cache)
        self.assertEqual(text, "Cached article body text.")

    def test_enhance_batch_without_conn_keeps_working(self):
        # Articles whose snippets are already long enough are untouched and
        # require neither a conn nor any network access.
        long_snippet = "x" * (snippet_enhancer.MIN_SNIPPET_LENGTH + 5)
        arts = [{"url": "https://example.com/a", "snippet": long_snippet}]
        out = snippet_enhancer.enhance_batch(arts, conn=None)
        self.assertEqual(out[0]["snippet"], long_snippet)

    def test_get_pipeline_cache_none_conn(self):
        self.assertIsNone(snippet_enhancer._get_pipeline_cache(None))
        self.assertIsNotNone(snippet_enhancer._get_pipeline_cache(self.conn))


if __name__ == "__main__":
    unittest.main()
