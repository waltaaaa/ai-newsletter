"""
Local LLM inference via llama-cpp-python.
Drop-in replacement for gemini_engine.py classification and extraction tasks.
Uses a quantized 3B parameter model — no API key, no quota, no network calls.
"""
import json
import os
import logging

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)

_model = None


def get_model():
    """Lazy-load the model on first call. Stays in memory for the run."""
    global _model
    if Llama is None:
        return None
    if _model is None:
        model_path = os.environ.get(
            "LOCAL_MODEL_PATH",
            "models/qwen2.5-3b-instruct-q4_k_m.gguf"
        )
        if not os.path.exists(model_path):
            print(f"[LOCAL LLM] Model not found at {model_path}, skipping local inference")
            return None
        _model = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=int(os.environ.get("LOCAL_LLM_THREADS", "2")),
            verbose=False
        )
        print(f"[LOCAL LLM] Loaded model from {model_path}")
    return _model


def classify_article(headline, snippet=""):
    """Binary RELEVANT/IRRELEVANT classification for RSS filter L6."""
    model = get_model()
    if model is None:
        return "RELEVANT"  # fail-open if model unavailable
    resp = model.create_chat_completion(messages=[
        {"role": "system", "content": (
            "You classify news articles as RELEVANT or IRRELEVANT to Canadian "
            "economic development, infrastructure projects, or major capital "
            "investment. Respond with exactly one word: RELEVANT or IRRELEVANT."
        )},
        {"role": "user", "content": f"Headline: {headline}\nSnippet: {snippet[:500]}"}
    ], max_tokens=10, temperature=0)
    result = resp["choices"][0]["message"]["content"].strip().upper()
    return "RELEVANT" if "RELEVANT" in result else "IRRELEVANT"


def batch_classify(items, system_prompt):
    """Classify a batch of items. Each item is a dict with 'headline' and optional 'snippet'.

    Returns list of classification strings, one per item.
    """
    model = get_model()
    if model is None:
        return ["RELEVANT"] * len(items)

    # Batch into groups of 25 for efficiency
    results = []
    for i in range(0, len(items), 25):
        batch = items[i:i + 25]
        batch_text = "\n".join(
            f"{j + 1}. {item.get('headline', item.get('title', str(item)))}"
            for j, item in enumerate(batch)
        )
        resp = model.create_chat_completion(messages=[
            {"role": "system", "content": (
                system_prompt
                + "\nRespond with a JSON array of classifications, one per item. "
                "Example: [\"RELEVANT\", \"IRRELEVANT\", \"RELEVANT\"]"
            )},
            {"role": "user", "content": batch_text}
        ], max_tokens=512, temperature=0)
        try:
            parsed = json.loads(resp["choices"][0]["message"]["content"])
            results.extend(parsed)
        except (json.JSONDecodeError, KeyError):
            results.extend(["RELEVANT"] * len(batch))  # fail-open
    return results


def extract_sentiment(posts):
    """Batch sentiment classification for Reddit posts."""
    model = get_model()
    if model is None:
        return []
    resp = model.create_chat_completion(messages=[
        {"role": "system", "content": (
            "Rate each post as positive, negative, or neutral toward the Canadian "
            "economy. Return a JSON array of objects: "
            '[{"sentiment": "positive|negative|neutral", "summary": "brief reason"}]'
        )},
        {"role": "user", "content": json.dumps(posts[:30], default=str)}
    ], max_tokens=2048, temperature=0)
    try:
        return json.loads(resp["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return []


def repair_json(broken_json):
    """Attempt JSON repair with local model.

    For complex repairs, caller should escalate to Claude Haiku.
    Returns parsed dict/list on success, None on failure.
    """
    model = get_model()
    if model is None:
        return None
    resp = model.create_chat_completion(messages=[
        {"role": "system", "content": (
            "The following JSON is truncated or malformed. Complete/fix it and "
            "return ONLY valid JSON. No explanation, no markdown fences."
        )},
        {"role": "user", "content": broken_json[-3000:]}  # last 3000 chars for context
    ], max_tokens=4096, temperature=0)
    try:
        return json.loads(resp["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return None
