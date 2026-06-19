"""
groq_client.py — Groq API client for classification tasks.

Replaces Gemini Flash as the primary classifier. Uses LLaMA 3.3 70B
via Groq's OpenAI-compatible API. Free tier: 6,000 TPM / 500K TPD.

Fallback chain: local LLM → Groq → fail-open (classify as RELEVANT).
Gemini is fully removed from the active classification path.

Cost: $0 (Groq free tier, no billing account required).
"""

import json
import logging
import os
import time
import threading

from pipeline_config import GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL, GROQ_TPM_LIMIT, GROQ_TPD_LIMIT

logger = logging.getLogger(__name__)

# ── Rate tracking ─────────────────────────────────────────────────────

_lock = threading.Lock()
_tokens_this_minute = 0
_tokens_today = 0
_minute_start = time.time()
_day_start = time.time()


def _reset_minute():
    global _tokens_this_minute, _minute_start
    now = time.time()
    if now - _minute_start > 60:
        _tokens_this_minute = 0
        _minute_start = now


def _reset_day():
    global _tokens_today, _day_start
    now = time.time()
    if now - _day_start > 86400:
        _tokens_today = 0
        _day_start = now


def can_use_groq(estimated_tokens=2000):
    """Check if Groq budget allows more calls."""
    if not GROQ_API_KEY:
        return False
    with _lock:
        _reset_minute()
        _reset_day()
        return (_tokens_this_minute + estimated_tokens <= GROQ_TPM_LIMIT and
                _tokens_today + estimated_tokens <= GROQ_TPD_LIMIT)


def _record_tokens(tokens_used):
    global _tokens_this_minute, _tokens_today
    with _lock:
        _reset_minute()
        _reset_day()
        _tokens_this_minute += tokens_used
        _tokens_today += tokens_used


# ── Classification ────────────────────────────────────────────────────

def batch_classify(articles, system_prompt, batch_size=20):
    """Classify articles via Groq LLaMA 3.3 70B.

    Drop-in replacement for Gemini Flash Layer 6 classification.
    Returns list of indices that are RELEVANT.

    Args:
        articles: list of dicts with 'title' and optionally 'summary'
        system_prompt: classification prompt (same format as Gemini L3 prompt)
        batch_size: articles per API call

    Returns:
        list[int]: indices of relevant articles
    """
    if not GROQ_API_KEY:
        logger.warning("[GROQ] No API key — passing all articles through")
        return list(range(len(articles)))

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("[GROQ] openai package not installed — passing all articles through")
        return list(range(len(articles)))

    # Red-team F2 (2026-06-11): the OpenAI client defaults to a 600s timeout x
    # 2 retries — a hung connection could eat ~30 min of the conductor's phase
    # budget. Groq normally answers in seconds; fail fast and fall through.
    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL,
                    timeout=120, max_retries=1)
    relevant_indices = []

    for batch_start in range(0, len(articles), batch_size):
        if not can_use_groq():
            logger.warning("[GROQ] Rate limit reached — passing remaining articles through")
            relevant_indices.extend(range(batch_start, len(articles)))
            break

        batch = articles[batch_start:batch_start + batch_size]
        items_text = '\n'.join(
            f"[{i}] {a.get('title', '')} — {(a.get('summary', '') or '')[:150]}"
            for i, a in enumerate(batch)
        )

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": items_text},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=2048,
            )

            usage = response.usage
            if usage:
                _record_tokens((usage.prompt_tokens or 0) + (usage.completion_tokens or 0))

            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)

            # Handle both formats: {"results": [...]} or bare [...]
            items = parsed if isinstance(parsed, list) else parsed.get("results", parsed.get("articles", []))
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, int):
                        if 0 <= item < len(batch):
                            relevant_indices.append(batch_start + item)
                    elif isinstance(item, dict):
                        idx = item.get('index', -1)
                        is_relevant = item.get('is_relevant', True)
                        if 0 <= idx < len(batch) and is_relevant:
                            relevant_indices.append(batch_start + idx)
            elif isinstance(items, dict):
                # Single-object wrapper — check each key
                for key, val in items.items():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict):
                                idx = item.get('index', -1)
                                is_relevant = item.get('is_relevant', True)
                                if 0 <= idx < len(batch) and is_relevant:
                                    relevant_indices.append(batch_start + idx)

        except json.JSONDecodeError as e:
            logger.warning(f"[GROQ] JSON parse error: {e} — passing batch through")
            relevant_indices.extend(range(batch_start, batch_start + len(batch)))
        except Exception as e:
            logger.warning(f"[GROQ] API error: {e} — passing batch through")
            relevant_indices.extend(range(batch_start, batch_start + len(batch)))

    return relevant_indices


def generate(system_prompt, user_prompt, max_tokens=2048, temperature=0.1):
    """General-purpose Groq generation. Used for JSON repair, sentiment, etc.

    Returns:
        str: response text, or None on failure
    """
    if not GROQ_API_KEY:
        return None

    if not can_use_groq():
        logger.warning("[GROQ] Rate limit reached")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    # Red-team F2: explicit timeout — default 600s x 2 retries could stall the
    # conductor pre-steps for ~30 min on a hung connection.
    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL,
                    timeout=120, max_retries=1)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        usage = response.usage
        if usage:
            _record_tokens((usage.prompt_tokens or 0) + (usage.completion_tokens or 0))

        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"[GROQ] generate error: {e}")
        return None


def repair_json(broken_json, label=""):
    """Attempt JSON repair via Groq. Returns parsed dict or None."""
    prompt = (
        f"The following JSON for '{label}' is malformed. "
        "Fix it and return ONLY valid JSON. No explanation.\n\n"
        f"{broken_json[:3000]}"
    )
    result = generate("You are a JSON repair tool. Return only valid JSON.", prompt)
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            pass
    return None
