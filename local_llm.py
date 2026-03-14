"""
Local LLM inference via Ollama (HTTP API on localhost:11434).
Drop-in replacement for gemini_engine.py classification and extraction tasks.
Uses Qwen 2.5 3B — no API key, no quota, no network calls beyond localhost.
"""
import json
import os
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

_OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5:3b")
_available = None  # cached availability check


def _check_available():
    """Check if Ollama is running and the model is available."""
    global _available
    if _available is not None:
        return _available
    try:
        req = urllib.request.Request(f"{_OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            if _MODEL in models or any(m.startswith(_MODEL.split(":")[0]) for m in models):
                _available = True
                print(f"[LOCAL LLM] Ollama available, model: {_MODEL}")
            else:
                _available = False
                print(f"[LOCAL LLM] Model {_MODEL} not found in Ollama. Available: {models}")
    except (urllib.error.URLError, OSError, TimeoutError):
        _available = False
        print("[LOCAL LLM] Ollama not reachable at localhost:11434, falling back to Gemini")
    return _available


def get_model():
    """Check availability. Returns True if Ollama is ready, None otherwise."""
    if _check_available():
        return True
    return None


def _chat(messages, max_tokens=512, temperature=0):
    """Send a chat completion request to Ollama."""
    payload = json.dumps({
        "model": _MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        }
    }).encode()
    req = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


def classify_article(headline, snippet=""):
    """Binary RELEVANT/IRRELEVANT classification for RSS filter L6."""
    if not _check_available():
        return "RELEVANT"  # fail-open if model unavailable
    try:
        result = _chat([
            {"role": "system", "content": (
                "You classify news articles as RELEVANT or IRRELEVANT to Canadian "
                "economic development, infrastructure projects, or major capital "
                "investment. Respond with exactly one word: RELEVANT or IRRELEVANT."
            )},
            {"role": "user", "content": f"Headline: {headline}\nSnippet: {snippet[:500]}"}
        ], max_tokens=10)
        return "RELEVANT" if "RELEVANT" in result.strip().upper() else "IRRELEVANT"
    except Exception as e:
        logger.warning(f"[LOCAL LLM] classify_article failed: {e}")
        return "RELEVANT"  # fail-open


def batch_classify(items, system_prompt):
    """Classify a batch of items. Returns list of classification strings."""
    if not _check_available():
        return ["RELEVANT"] * len(items)

    results = []
    for i in range(0, len(items), 25):
        batch = items[i:i + 25]
        batch_text = "\n".join(
            f"{j + 1}. {item.get('headline', item.get('title', str(item)))}"
            for j, item in enumerate(batch)
        )
        try:
            resp = _chat([
                {"role": "system", "content": (
                    system_prompt
                    + "\nRespond with a JSON array of classifications, one per item. "
                    "Example: [\"RELEVANT\", \"IRRELEVANT\", \"RELEVANT\"]"
                )},
                {"role": "user", "content": batch_text}
            ], max_tokens=512)
            parsed = json.loads(resp)
            results.extend(parsed)
        except (json.JSONDecodeError, Exception):
            results.extend(["RELEVANT"] * len(batch))  # fail-open
    return results


def extract_sentiment(posts):
    """Batch sentiment classification for Reddit posts."""
    if not _check_available():
        return []
    try:
        resp = _chat([
            {"role": "system", "content": (
                "Rate each post as positive, negative, or neutral toward the Canadian "
                "economy. Return a JSON array of objects: "
                '[{"sentiment": "positive|negative|neutral", "summary": "brief reason"}]'
            )},
            {"role": "user", "content": json.dumps(posts[:30], default=str)}
        ], max_tokens=2048)
        return json.loads(resp)
    except (json.JSONDecodeError, Exception):
        return []


def repair_json(broken_json):
    """Attempt JSON repair with local model. Returns parsed dict/list or None."""
    if not _check_available():
        return None
    try:
        resp = _chat([
            {"role": "system", "content": (
                "The following JSON is truncated or malformed. Complete/fix it and "
                "return ONLY valid JSON. No explanation, no markdown fences."
            )},
            {"role": "user", "content": broken_json[-3000:]}
        ], max_tokens=4096)
        return json.loads(resp)
    except (json.JSONDecodeError, Exception):
        return None
