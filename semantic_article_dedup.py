"""
semantic_article_dedup.py — NIM embedding-based semantic article deduplication.

Catches paraphrased near-duplicates that MinHash misses (different wording,
same story). Uses NIM Llama Nemotron Embed 1B v2 via nim_client.

Runs after MinHash dedup, before the 6-layer article filter.
Government source articles bypass entirely (never dropped).
"""

import logging
import math

from nim_client import get_client

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


def semantic_deduplicate_articles(
    articles: list[dict],
    threshold: float = SEMANTIC_SIMILARITY_THRESHOLD,
) -> tuple[list[dict], int]:
    """Remove semantic duplicates using NIM embeddings.

    Returns (deduplicated_list, dropped_count).
    Government articles are never dropped.
    """
    if not articles or len(articles) < 2:
        return articles, 0

    nim = get_client()

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

    # Batch embed all texts
    raw_texts = [t for _, t in texts_to_embed]
    embeddings = nim.embed_sync(raw_texts)
    if not embeddings or len(embeddings) != len(raw_texts):
        logger.warning("NIM embedding returned unexpected count, skipping semantic dedup")
        return articles, 0

    embed_to_orig = [idx for idx, _ in texts_to_embed]

    # Greedy dedup: for each embedding, check against all previous kept items
    keep_set = set(gov_indices)
    dropped = set()

    for i in range(len(embeddings)):
        orig_i = embed_to_orig[i]
        if orig_i in dropped:
            continue
        is_dup = False
        for j in range(i):
            orig_j = embed_to_orig[j]
            if orig_j in dropped:
                continue
            sim = _cosine_similarity(embeddings[i], embeddings[j])
            if sim >= threshold:
                # Keep the longer article
                if len(raw_texts[i]) >= len(raw_texts[j]):
                    dropped.add(orig_j)
                    keep_set.discard(orig_j)
                    keep_set.add(orig_i)
                else:
                    dropped.add(orig_i)
                    keep_set.add(orig_j)
                is_dup = True
                break
        if not is_dup:
            keep_set.add(orig_i)

    # Also keep articles too short for embedding
    for i in range(len(articles)):
        if i not in gov_indices and i not in keep_set and i not in dropped:
            keep_set.add(i)

    deduplicated = [articles[i] for i in sorted(keep_set)]
    drop_count = len(articles) - len(deduplicated)
    return deduplicated, drop_count
