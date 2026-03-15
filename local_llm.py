"""
Local LLM inference via Ollama (HTTP API on localhost:11434).
Drop-in replacement for gemini_engine.py classification and extraction tasks.
Uses Qwen 2.5 3B — no API key, no quota, no network calls beyond localhost.
"""
import json
import os
import logging
import re
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


def chat(messages, max_tokens=512, temperature=0):
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
    msg = data.get("message")
    if not msg or not isinstance(msg, dict):
        raise ValueError(f"Ollama returned unexpected response structure: {list(data.keys())}")
    return msg.get("content", "")


def classify_article(headline, snippet=""):
    """Binary RELEVANT/IRRELEVANT classification for RSS filter L6."""
    if not _check_available():
        return "RELEVANT"  # fail-open if model unavailable
    try:
        result = chat([
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


_BATCH_SIZE = 80  # headlines per Ollama call (increased from 30 for throughput)

# Lean binary prompt with compact numbered output format.
# Ollama callers only use RELEVANT/IRRELEVANT, so skip the 12-field JSON
# the full _L3_PROMPT asks for. Numbered "1.R" format ensures exact 1:1 mapping,
# avoids JSON parse issues, and cuts eval tokens by ~50%.
_LEAN_CLASSIFY_PROMPT = """\
Classify each numbered headline for a Canadian capital projects and economic development tracker.

R = RELEVANT. Includes: construction, renovation, retrofit, expansion, infrastructure, \
housing development, condo towers, mixed-use, transit, highway, bridge, energy (solar, wind, \
LNG, pipeline, nuclear, hydrogen, battery), mining, data centres, defence, water/wastewater, \
institutional (hospital, school, arena), government capital spending, P3, funding announcements, \
building permits, housing starts, industrial facilities, environmental remediation, adaptive reuse.

I = IRRELEVANT. Only: sports scores/trades/playoffs, crime/court/sentencing, entertainment/concerts, \
weather alerts, health outbreaks, opinion/editorial without project details, dollar figures that are \
lawsuits/salaries/fines.

If uncertain, output R.

Output format: one line per headline — number, period, R or I. Nothing else.

Example:
1.R
2.I
3.R"""


def _classify_one_batch(batch, system_prompt):
    """Classify a single batch. Returns list of classification strings."""
    batch_text = "\n".join(
        f"{j + 1}. {item.get('headline', item.get('title', str(item)))}"
        for j, item in enumerate(batch)
    )
    try:
        resp = chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": batch_text}
        ], max_tokens=len(batch) * 5 + 20)  # ~5 chars per "N.R\n" verdict
        # Parse numbered R/I format: "1.R\n2.I\n3.R\n..."
        verdicts = re.findall(r'(\d+)\.([RI])', resp, re.IGNORECASE)
        # Build result keyed by 1-based index
        result_map = {int(num): v.upper() for num, v in verdicts}
        results = []
        for j in range(len(batch)):
            v = result_map.get(j + 1, "R")  # fail-open if missing
            results.append("RELEVANT" if v == "R" else "IRRELEVANT")
        return results
    except Exception:
        return ["RELEVANT"] * len(batch)


def batch_classify(items, system_prompt=None):
    """Classify a batch of items. Returns list of classification strings.

    Uses a lean binary prompt for speed (the full _L3_PROMPT with 12-field JSON
    is only useful for the Gemini path — Ollama callers discard everything except
    RELEVANT/IRRELEVANT). Processes batches sequentially through Ollama.
    """
    if not _check_available():
        return ["RELEVANT"] * len(items)

    # Always use the lean prompt for Ollama — callers only check for "RELEVANT"
    prompt = _LEAN_CLASSIFY_PROMPT

    results = []
    total_batches = (len(items) + _BATCH_SIZE - 1) // _BATCH_SIZE
    for i in range(0, len(items), _BATCH_SIZE):
        batch = items[i:i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        classifications = _classify_one_batch(batch, prompt)
        results.extend(classifications)
        if batch_num % 5 == 0 or batch_num == total_batches:
            print(f"  [LOCAL LLM] {batch_num}/{total_batches} batches done")

    return results


def extract_sentiment(posts):
    """Batch sentiment classification for Reddit posts."""
    if not _check_available():
        return []
    try:
        resp = chat([
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
        resp = chat([
            {"role": "system", "content": (
                "The following JSON is truncated or malformed. Complete/fix it and "
                "return ONLY valid JSON. No explanation, no markdown fences."
            )},
            {"role": "user", "content": broken_json[-3000:]}
        ], max_tokens=4096)
        return json.loads(resp)
    except (json.JSONDecodeError, Exception):
        return None
