"""
embeddings_cache.py — NIM-backed embedding cache (nv-embedqa-e5-v5). Zero local RAM.

In-memory hash cache avoids redundant NIM API calls within a single run.
Used by project_dedup.py for semantic similarity scoring.

Graceful degradation: if NIM is unavailable, get_similarity() returns 0.0
and dedup falls back to string matching (existing behavior).
"""

import hashlib
import math
import logging

from nim_client import get_client

logger = logging.getLogger(__name__)

_cache: dict[str, list[float]] = {}


def get_embedding(text: str) -> list[float] | None:
    """Get embedding from NIM. Returns cached if available.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector, or None if NIM unavailable.
    """
    text_hash = hashlib.md5(text.encode()).hexdigest()
    if text_hash in _cache:
        return _cache[text_hash]
    try:
        result = get_client().embed_sync([text])
        if result:
            _cache[text_hash] = result[0]
            return result[0]
        return None
    except Exception as e:
        logger.debug(f"NIM embedding failed: {e}")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity via NIM embeddings. Returns 0.0 if unavailable.

    Args:
        text_a: First text.
        text_b: Second text.

    Returns:
        Similarity score 0.0-1.0, or 0.0 on failure.
    """
    emb_a = get_embedding(text_a)
    emb_b = get_embedding(text_b)
    if emb_a is None or emb_b is None:
        return 0.0
    return cosine_similarity(emb_a, emb_b)


def cache_stats() -> dict:
    """Return cache statistics."""
    return {"cached_embeddings": len(_cache)}
