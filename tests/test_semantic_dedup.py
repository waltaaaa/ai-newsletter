"""
tests/test_semantic_dedup.py — E-8 numpy-vectorized semantic dedup.

Covers _dedup_from_embeddings (pure function — no network, no NIM):
  - identical vectors dedup keeping the longer text
  - orthogonal vectors are all kept
  - equivalence against a naive reference implementation on a random-seeded
    50-vector fixture
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from semantic_article_dedup import (
    SEMANTIC_SIMILARITY_THRESHOLD,
    _dedup_from_embeddings,
)


def _reference_dedup(embeddings, texts, threshold):
    """Naive O(N^2) greedy reference — mirrors the pre-E-8 loop semantics:
    compare i against the first earlier still-kept j with sim >= threshold;
    keep the longer text (ties keep i)."""
    M = np.asarray(embeddings, dtype=np.float64)
    norms = np.linalg.norm(M, axis=1)
    norms[norms == 0.0] = 1.0
    M = M / norms[:, None]

    dropped = set()
    n = len(embeddings)
    for i in range(1, n):
        for j in range(i):
            if j in dropped:
                continue
            if float(M[j] @ M[i]) >= threshold:
                if len(texts[i]) >= len(texts[j]):
                    dropped.add(j)
                else:
                    dropped.add(i)
                break
    keep = [i for i in range(n) if i not in dropped]
    return keep, dropped


class TestDedupFromEmbeddings(unittest.TestCase):
    def test_identical_vectors_keep_longer_text(self):
        embeddings = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        texts = ["short", "a much longer article text"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [1])
        self.assertEqual(dropped, {0})

    def test_identical_vectors_first_longer_kept(self):
        embeddings = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        texts = ["a much longer article text", "short"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [0])
        self.assertEqual(dropped, {1})

    def test_tie_keeps_current(self):
        # Equal lengths: len(texts[i]) >= len(texts[j]) keeps i, drops j
        embeddings = [[0.0, 1.0], [0.0, 1.0]]
        texts = ["aaaaa", "bbbbb"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [1])
        self.assertEqual(dropped, {0})

    def test_orthogonal_vectors_all_kept(self):
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        texts = ["one", "two", "three"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [0, 1, 2])
        self.assertEqual(dropped, set())

    def test_scale_invariance(self):
        # Cosine similarity ignores magnitude — scaled copies are duplicates
        embeddings = [[1.0, 1.0, 0.0], [10.0, 10.0, 0.0]]
        texts = ["short", "the longer one"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [1])
        self.assertEqual(dropped, {0})

    def test_zero_vector_never_matches(self):
        embeddings = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        texts = ["a", "bb", "ccc"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [0, 1, 2])
        self.assertEqual(dropped, set())

    def test_chained_duplicates_greedy(self):
        # 0 and 1 identical, 2 identical to both: after 1 drops 0 (longer),
        # 2 compares against 1 (first still-kept) and the longer wins again.
        embeddings = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
        texts = ["aa", "aaaa", "aaaaaa"]
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, [2])
        self.assertEqual(dropped, {0, 1})

    def test_equivalence_vs_reference_on_random_fixture(self):
        rng = np.random.default_rng(seed=42)
        dim = 32
        embeddings = []
        texts = []
        # 10 cluster centroids; 50 vectors = centroid + small noise so
        # intra-cluster sims are well above the 0.92 threshold and
        # inter-cluster sims (random gaussians, dim 32) are well below it.
        centroids = rng.normal(size=(10, dim))
        for k in range(50):
            c = centroids[k % 10]
            noise = rng.normal(scale=0.01, size=dim)
            embeddings.append((c + noise).tolist())
            texts.append("t" * int(rng.integers(5, 200)))

        ref_keep, ref_dropped = _reference_dedup(
            embeddings, texts, SEMANTIC_SIMILARITY_THRESHOLD)
        keep, dropped = _dedup_from_embeddings(embeddings, texts)

        self.assertEqual(keep, ref_keep)
        self.assertEqual(dropped, ref_dropped)
        # Sanity: clustering actually deduped down to ~10 representatives
        self.assertEqual(len(keep), 10)

    def test_equivalence_no_duplicates_fixture(self):
        rng = np.random.default_rng(seed=7)
        embeddings = rng.normal(size=(50, 64)).tolist()
        texts = ["x" * int(rng.integers(5, 100)) for _ in range(50)]
        ref_keep, ref_dropped = _reference_dedup(
            embeddings, texts, SEMANTIC_SIMILARITY_THRESHOLD)
        keep, dropped = _dedup_from_embeddings(embeddings, texts)
        self.assertEqual(keep, ref_keep)
        self.assertEqual(dropped, ref_dropped)


if __name__ == "__main__":
    unittest.main()
