I need you to create a local LLM module that replaces Gemini for classification, extraction, and JSON repair tasks. This will eliminate the Gemini free-tier quota bottleneck.

## Part 1: Create `local_llm.py`

Create a new file `local_llm.py` with the following structure:

```python
"""
Local LLM inference via llama-cpp-python.
Drop-in replacement for gemini_engine.py classification and extraction tasks.
Uses a quantized 3B parameter model — no API key, no quota, no network calls.
"""
from llama_cpp import Llama
import json
import os

_model = None

def get_model():
    """Lazy-load the model on first call. Stays in memory for the run."""
    global _model
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
        {"role": "system", "content": "You classify news articles as RELEVANT or IRRELEVANT to Canadian economic development, infrastructure projects, or major capital investment. Respond with exactly one word: RELEVANT or IRRELEVANT."},
        {"role": "user", "content": f"Headline: {headline}\nSnippet: {snippet[:500]}"}
    ], max_tokens=10, temperature=0)
    result = resp["choices"][0]["message"]["content"].strip().upper()
    return "RELEVANT" if "RELEVANT" in result else "IRRELEVANT"

def batch_classify(items, system_prompt):
    """Classify a batch of items. Each item is a dict with 'headline' and optional 'snippet'."""
    model = get_model()
    if model is None:
        return ["RELEVANT"] * len(items)
    
    # Batch into groups of 25 for efficiency
    results = []
    for i in range(0, len(items), 25):
        batch = items[i:i+25]
        batch_text = "\n".join(
            f"{j+1}. {item.get('headline', item.get('title', str(item)))}" 
            for j, item in enumerate(batch)
        )
        resp = model.create_chat_completion(messages=[
            {"role": "system", "content": system_prompt + "\nRespond with a JSON array of classifications, one per item. Example: [\"RELEVANT\", \"IRRELEVANT\", \"RELEVANT\"]"},
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
        {"role": "system", "content": "Rate each post as positive, negative, or neutral toward the Canadian economy. Return a JSON array of objects: [{\"sentiment\": \"positive|negative|neutral\", \"summary\": \"brief reason\"}]"},
        {"role": "user", "content": json.dumps(posts[:30], default=str)}
    ], max_tokens=2048, temperature=0)
    try:
        return json.loads(resp["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return []

def repair_json(broken_json):
    """
    Attempt JSON repair with local model.
    For complex repairs, caller should escalate to Claude Haiku.
    """
    model = get_model()
    if model is None:
        return None
    resp = model.create_chat_completion(messages=[
        {"role": "system", "content": "The following JSON is truncated or malformed. Complete/fix it and return ONLY valid JSON. No explanation, no markdown fences."},
        {"role": "user", "content": broken_json[-3000:]}  # last 3000 chars for context
    ], max_tokens=4096, temperature=0)
    try:
        return json.loads(resp["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return None
```

## Part 2: Update `gemini_engine.py` to use local LLM as primary

In `gemini_engine.py`, modify the classification and extraction functions to try local LLM first, fall back to Gemini only if the local model is unavailable AND Gemini is available (via the circuit breaker from Prompt 4):

```python
import local_llm
from service_health import health  # or however it's accessed

def classify_article(headline, snippet=""):
    # Try local first
    result = local_llm.classify_article(headline, snippet)
    if result is not None:
        return result
    # Fall back to Gemini if available
    if not health.is_available("gemini"):
        return "RELEVANT"  # fail-open
    # ... existing Gemini code ...
```

Apply this pattern to all Gemini-dependent functions: classify, extract, sentiment, enrichment.

For JSON repair specifically, the fallback chain should be:
1. Local LLM repair
2. Claude Haiku repair (add a new function in `claude_reasoning.py` for this)
3. Gemini repair (only if available)

## Part 3: Update requirements.txt

Add `llama-cpp-python` to requirements.txt.

## Part 4: GitHub Actions model caching

In both `.github/workflows/weekly-pipeline.yml` and `daily-indicators.yml`, add a cache step for the model file:

```yaml
- name: Cache local LLM model
  uses: actions/cache@v4
  with:
    path: models/
    key: local-llm-qwen25-3b-q4km-v1

- name: Download model if not cached
  run: |
    if [ ! -f models/qwen2.5-3b-instruct-q4_k_m.gguf ]; then
      mkdir -p models
      wget -q https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf -O models/qwen2.5-3b-instruct-q4_k_m.gguf
    fi
```

Add env var to workflows: `LOCAL_MODEL_PATH: models/qwen2.5-3b-instruct-q4_k_m.gguf`
