"""
article_dedup.py — MinHash LSH article-level deduplication.

Removes near-duplicate articles across 314+ RSS feeds before they enter
the 6-layer filter and LLM classification. Syndicated articles (same story
from CBC, Globe, CTV) are collapsed to the longest version.

Algorithm:
  1. Create MinHash from word-level 3-grams of title + summary
  2. Insert into LSH index (threshold=0.7 Jaccard similarity)
  3. For each duplicate cluster, keep the article with the longest text
  4. Government source articles bypass entirely (never dropped)

Dependency: datasketch (added in Phase 0).
"""

import logging
from datasketch import MinHash, MinHashLSH

logger = logging.getLogger(__name__)

NUM_PERM = 128  # MinHash permutations (higher = more accurate, slower)
SHINGLE_SIZE = 3  # word-level n-gram size

# Government source levels that bypass dedup entirely
_GOV_SOURCE_LEVELS = frozenset({
    "federal", "provincial", "municipal", "crown", "government",
    "key_people", "regulatory",
})


def _shingle(text: str) -> set[str]:
    """Generate word-level n-gram shingles from text."""
    words = text.lower().split()
    if len(words) < SHINGLE_SIZE:
        return {text.lower()}
    return {
        " ".join(words[i:i + SHINGLE_SIZE])
        for i in range(len(words) - SHINGLE_SIZE + 1)
    }


def _make_minhash(text: str) -> MinHash:
    """Create a MinHash from text shingles."""
    m = MinHash(num_perm=NUM_PERM)
    for shingle in _shingle(text):
        m.update(shingle.encode("utf-8"))
    return m


def _article_text(article: dict, title_key: str, summary_key: str) -> str:
    """Extract combined text from an article for hashing."""
    title = (article.get(title_key) or "").strip()
    summary = (article.get(summary_key) or "").strip()
    return f"{title} {summary}".strip()


def _is_gov_source(article: dict) -> bool:
    """Check if article is from a government source (should bypass dedup)."""
    source_level = (article.get("source_level") or "").lower()
    return source_level in _GOV_SOURCE_LEVELS


def deduplicate_articles(
    articles: list[dict],
    threshold: float = 0.7,
    title_key: str = "title",
    summary_key: str = "summary",
) -> tuple[list[dict], int]:
    """Remove near-duplicate articles using MinHash LSH.

    Government source articles are never dropped.
    For each duplicate cluster, keeps the article with the longest text.

    Args:
        articles: List of article dicts.
        threshold: Jaccard similarity threshold for duplicate detection (0.0-1.0).
        title_key: Key for article title field.
        summary_key: Key for article summary/description field.

    Returns:
        Tuple of (deduplicated_list, dropped_count).
    """
    if not articles or len(articles) < 2:
        return articles, 0

    lsh = MinHashLSH(threshold=threshold, num_perm=NUM_PERM)
    minhashes: dict[int, MinHash] = {}
    gov_indices: set[int] = set()

    # Build MinHash for each article and insert into LSH
    for i, article in enumerate(articles):
        if _is_gov_source(article):
            gov_indices.add(i)
            continue

        text = _article_text(article, title_key, summary_key)
        if not text or len(text) < 10:
            continue

        m = _make_minhash(text)
        minhashes[i] = m
        try:
            lsh.insert(str(i), m)
        except ValueError:
            # Duplicate key — already inserted (identical hash)
            pass

    # Find duplicate clusters
    keep_indices: set[int] = set(gov_indices)  # always keep gov articles
    seen: set[int] = set()

    for i, m in minhashes.items():
        if i in seen:
            continue

        # Query LSH for similar articles
        try:
            candidates = [int(c) for c in lsh.query(m)]
        except Exception:
            candidates = [i]

        if len(candidates) <= 1:
            keep_indices.add(i)
            seen.add(i)
            continue

        # Pick the article with the longest text from the cluster
        best_idx = i
        best_len = len(_article_text(articles[i], title_key, summary_key))

        for c in candidates:
            if c in seen:
                continue
            c_len = len(_article_text(articles[c], title_key, summary_key))
            if c_len > best_len:
                best_idx = c
                best_len = c_len
            seen.add(c)

        keep_indices.add(best_idx)
        seen.add(i)

    # Also keep articles that were too short for MinHash
    for i in range(len(articles)):
        if i not in minhashes and i not in gov_indices:
            keep_indices.add(i)

    deduplicated = [articles[i] for i in sorted(keep_indices)]
    dropped = len(articles) - len(deduplicated)

    if dropped:
        logger.info(f"MinHash dedup: {len(articles)} -> {len(deduplicated)} ({dropped} near-duplicates removed)")

    return deduplicated, dropped
