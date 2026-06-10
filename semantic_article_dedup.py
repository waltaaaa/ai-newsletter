"""
semantic_article_dedup.py — NIM embedding-based semantic article deduplication.

Catches paraphrased near-duplicates that MinHash misses (different wording,
same story). Uses NIM Llama Nemotron Embed 1B v2 via nim_client.

Runs after MinHash dedup, before the 6-layer article filter.
Government source articles bypass entirely (never dropped).

E-7: embeddings are cached in the SQLite `cache` table (category 'embedding',
key = sha256 of text, 90-day TTL) when a DB connection is supplied — a cache
hit avoids the NIM API call entirely.
E-8: the greedy pairwise cosine loop is vectorized with numpy (pre-normalized
matrix, sims = M[:i] @ M[i]) with a pure-Python fallback if numpy is missing.
"""

import hashlib
import logging
import math
import time

from nim_client import get_client

try:
    import numpy as _np
except ImportError:  # pragma: no cover - numpy is installed in the venv
    _np = None

logger = logging.getLogger(__name__)

SEMANTIC_SIMILARITY_THRESHOLD = 0.92  # high threshold to avoid false positives
_GOV_SOURCE_LEVELS = frozenset({
    "federal", "provincial", "municipal", "crown", "government",
    "key_people", "regulatory",
})


def _is_gov_source(article: dict) -> bool:
    return (article.get("source_level") or "").lower() in _GOV_SOURCE_LEVELS


def _article_text(article: dict) -> str:
    title = (article.get("title") or "").strip()
    summary = (article.get("summary") or "").strip()
    return f"{title} {summary}".strip()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embedding_cache_key(text: str) -> str:
    """E-7: stable cache key for an article's embedding."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_pipeline_cache(conn):
    """Best-effort PipelineCache over the supplied conn. None when unavailable."""
    if conn is None:
        return None
    try:
        from pipeline_cache import PipelineCache
        return PipelineCache(conn)
    except Exception:
        return None


def _dedup_from_embeddings(
    embeddings: list,
    texts: list[str],
    threshold: float = SEMANTIC_SIMILARITY_THRESHOLD,
) -> tuple[list[int], set[int]]:
    """Pure greedy dedup over embedding indices.

    Semantics (identical to the original pairwise loop):
      - iterate i in order; compare against the FIRST earlier, still-kept j
        with cosine similarity >= threshold;
      - on a match, keep whichever of (i, j) has the longer text (ties keep i)
        and drop the other;
      - an i with no match is kept.

    Returns (keep_indices, dropped_indices) in embedding-index space.

    E-8: vectorized — vectors are L2-normalized into a matrix once, the inner
    loop becomes sims = M[:i] @ M[i]. Pure-Python fallback if numpy is missing.
    """
    n = len(embeddings)
    t0 = time.time()
    print(f"  [SEMANTIC] processing {n} embeddings "
          f"({'numpy vectorized' if _np is not None else 'pure-python fallback'})...")

    dropped: set[int] = set()

    if _np is not None:
        M = _np.asarray(embeddings, dtype=_np.float64)
        norms = _np.linalg.norm(M, axis=1)
        norms[norms == 0.0] = 1.0  # zero vectors stay zero → similarity 0
        M = M / norms[:, None]
    else:
        # Pre-normalize once so the fallback loop is a plain dot product.
        M = []
        for vec in embeddings:
            norm = math.sqrt(sum(x * x for x in vec))
            M.append([x / norm for x in vec] if norm else list(vec))

    for i in range(n):
        # M-9: periodic progress marker — keeps long runs observably alive.
        if (i + 1) % 100 == 0:
            print(f"  [SEMANTIC] processed {i + 1}/{n} comparisons "
                  f"(t+{time.time() - t0:.0f}s)")

        if i == 0:
            continue  # nothing earlier to compare against; index 0 is kept

        first_dup = -1
        if _np is not None:
            sims = M[:i] @ M[i]
            for j in _np.nonzero(sims >= threshold)[0]:
                if int(j) not in dropped:
                    first_dup = int(j)
                    break
        else:
            vi = M[i]
            for j in range(i):
                if j in dropped:
                    continue
                if sum(x * y for x, y in zip(M[j], vi)) >= threshold:
                    first_dup = j
                    break

        if first_dup >= 0:
            # Keep the longer article (ties keep the current one)
            if len(texts[i]) >= len(texts[first_dup]):
                dropped.add(first_dup)
            else:
                dropped.add(i)

    keep_indices = [i for i in range(n) if i not in dropped]
    print(f"  [SEMANTIC] dedup loop complete in {time.time() - t0:.0f}s "
          f"({len(dropped)} dropped, {len(keep_indices)} kept)")
    return keep_indices, dropped


def _get_embeddings(raw_texts: list[str], conn=None):
    """Embed texts via NIM, using the SQLite embedding cache when available.

    Returns a list of embeddings aligned with raw_texts, or None on failure.
    A full cache hit avoids the NIM client call entirely (E-7).
    """
    cache = _get_pipeline_cache(conn)
    embeddings: list = [None] * len(raw_texts)
    miss_idx = list(range(len(raw_texts)))

    if cache is not None:
        miss_idx = []
        for k, text in enumerate(raw_texts):
            cached = None
            try:
                cached = cache.get(_embedding_cache_key(text), "embedding")
            except Exception:
                cached = None
            if isinstance(cached, list) and cached:
                embeddings[k] = cached
            else:
                miss_idx.append(k)
        hits = len(raw_texts) - len(miss_idx)
        if hits:
            print(f"  [SEMANTIC] embedding cache: {hits} hits, "
                  f"{len(miss_idx)} misses")

    if miss_idx:
        nim = get_client()
        fetched = nim.embed_sync([raw_texts[k] for k in miss_idx])
        if not fetched or len(fetched) != len(miss_idx):
            logger.warning(
                "NIM embedding returned unexpected count, skipping semantic dedup")
            return None
        for k, emb in zip(miss_idx, fetched):
            embeddings[k] = emb
            if cache is not None:
                try:
                    cache.set(_embedding_cache_key(raw_texts[k]), emb, "embedding")
                except Exception:
                    pass  # caching is best-effort

    return embeddings


def semantic_deduplicate_articles(
    articles: list[dict],
    threshold: float = SEMANTIC_SIMILARITY_THRESHOLD,
    conn=None,
) -> tuple[list[dict], int]:
    """Remove semantic duplicates using NIM embeddings.

    Returns (deduplicated_list, dropped_count).
    Government articles are never dropped.

    Args:
        conn: optional SQLite connection — enables the persistent embedding
            cache (E-7). Degrades gracefully to direct NIM calls when absent.
    """
    if not articles or len(articles) < 2:
        return articles, 0

    # Separate gov articles (always kept) from embeddable articles
    gov_indices = set()
    texts_to_embed = []  # (original_index, text)
    for i, art in enumerate(articles):
        if _is_gov_source(art):
            gov_indices.add(i)
        else:
            text = _article_text(art)
            if text and len(text) >= 20:
                texts_to_embed.append((i, text))

    if len(texts_to_embed) < 2:
        return articles, 0

    # Batch embed all texts (cache-aware)
    raw_texts = [t for _, t in texts_to_embed]
    embeddings = _get_embeddings(raw_texts, conn=conn)
    if embeddings is None:
        return articles, 0

    embed_to_orig = [idx for idx, _ in texts_to_embed]

    # Greedy dedup in embedding-index space (E-8 vectorized pure function)
    keep_emb, dropped_emb = _dedup_from_embeddings(embeddings, raw_texts, threshold)

    keep_set = set(gov_indices)
    keep_set.update(embed_to_orig[k] for k in keep_emb)
    dropped = {embed_to_orig[k] for k in dropped_emb}

    # Also keep articles too short for embedding
    for i in range(len(articles)):
        if i not in gov_indices and i not in keep_set and i not in dropped:
            keep_set.add(i)

    deduplicated = [articles[i] for i in sorted(keep_set)]
    drop_count = len(articles) - len(deduplicated)
    return deduplicated, drop_count
