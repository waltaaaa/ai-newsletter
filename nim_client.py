"""
nim_client.py — Shared NVIDIA NIM API client with unified rate limiting, batching, and concurrency.

All NIM model calls (K2.5 chat, embeddings, reranking) go through this single client.
One rate limiter (token bucket, 40 RPM) shared across all models.

Usage:
    from nim_client import get_client
    client = get_client()

    # Async
    response = await client.chat(model, messages)
    embeddings = await client.embed(["text1", "text2"])
    ranked = await client.rerank("query", ["passage1", "passage2"])

    # Sync (for non-async callers)
    embeddings = client.embed_sync(["text1", "text2"])
    ranked = client.rerank_sync("query", ["passage1", "passage2"])
"""

import asyncio
import time

import aiohttp

from pipeline_config import (
    NIM_BASE_URL,
    NIM_EMBEDDING_MODEL,
    NIM_EXTRACTION_MODEL,
    NIM_RATE_LIMIT_RPM,
    NIM_RERANK_BASE_URL,
    NIM_RERANK_MODEL,
    NIM_RERANK_URL_MODEL,
    NIM_THINKING_MODE,
    NVIDIA_API_KEY,
)
import service_health

REQUEST_TIMEOUT_SECONDS = 120

# ── Batch size limits (per NIM endpoint docs) ──
EMBED_BATCH_SIZE = 20        # texts per /v1/embeddings call
RERANK_MAX_PASSAGES = 512    # passages per /v1/ranking call (practical limit ~50)
VALIDATION_BATCH_SIZE = 5    # projects per Claude validation call
SEARCH_CONCURRENCY = 5       # parallel SearXNG requests (no rate limit)
EXTRACT_CONCURRENCY = 3      # parallel trafilatura fetches


class TokenBucket:
    """Simple async token bucket rate limiter."""

    def __init__(self, tokens: int, refill_per_minute: int):
        self._max_tokens = tokens
        self._tokens = float(tokens)
        self._refill_rate = refill_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available, then consume one."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

            # Not enough tokens — wait briefly and retry
            await asyncio.sleep(0.5)


def _chunked(lst, size):
    """Yield successive chunks of `size` from `lst`."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


class NIMClient:
    """Single client for all NIM model calls. 40 RPM shared budget."""

    def __init__(self):
        self._rate_limiter = TokenBucket(
            tokens=NIM_RATE_LIMIT_RPM,
            refill_per_minute=NIM_RATE_LIMIT_RPM,
        )
        self._session = None
        self._sync_loop = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy-init aiohttp session (no timeout — we use asyncio.wait_for instead)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _check_health(self):
        """Check circuit breaker before making a NIM call."""
        health = service_health.get()
        if not health.is_available("nvidia_nim"):
            raise RuntimeError("NIM circuit breaker is open — service marked dead")

    def _record_failure(self, reason: str):
        """Record a failure with the circuit breaker."""
        health = service_health.get()
        health.record_failure("nvidia_nim", reason)

    def _record_success(self):
        """Record a success with the circuit breaker."""
        health = service_health.get()
        health.record_success("nvidia_nim")

    async def _post(self, url: str, payload: dict) -> dict:
        """POST JSON to a NIM endpoint with timeout. Returns parsed JSON response."""
        session = await self._get_session()

        async def _do_request():
            async with session.post(url, json=payload) as resp:
                text = await resp.text()
                return resp.status, text

        try:
            status, text = await asyncio.wait_for(
                _do_request(), timeout=REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            self._record_failure(f"Timeout after {REQUEST_TIMEOUT_SECONDS}s")
            raise RuntimeError(f"NIM request timed out after {REQUEST_TIMEOUT_SECONDS}s: {url}")
        except aiohttp.ClientError as e:
            self._record_failure(str(e))
            raise RuntimeError(f"NIM connection error: {e}") from e

        if status != 200:
            self._record_failure(f"HTTP {status}: {text[:200]}")
            raise RuntimeError(f"NIM error {status}: {text[:200]}")

        self._record_success()
        import json
        return json.loads(text)

    # ── Chat (K2.5 extraction) ──

    async def chat(self, model: str = NIM_EXTRACTION_MODEL, messages: list[dict] = None,
                   thinking: bool = None, **kwargs) -> str:
        """Chat completion via NIM. Returns the assistant message content.

        Args:
            model: NIM model ID (default: K2.5)
            messages: List of {"role": ..., "content": ...} dicts
            thinking: Enable thinking mode (default: from NIM_THINKING_MODE config)
            **kwargs: Additional params passed to the API (temperature, max_tokens, etc.)
        """
        if not NVIDIA_API_KEY:
            raise RuntimeError("NVIDIA_API_KEY not set")
        self._check_health()

        if thinking is None:
            thinking = NIM_THINKING_MODE

        await self._rate_limiter.acquire()

        payload = {
            "model": model,
            "messages": messages or [],
            **kwargs,
        }
        if thinking:
            payload["thinking"] = {"type": "enabled", "budget_tokens": 4096}

        data = await self._post(f"{NIM_BASE_URL}/chat/completions", payload)

        # Extract content, skipping thinking blocks if present
        choice = data["choices"][0]["message"]
        if isinstance(choice.get("content"), list):
            # Multi-part response (thinking + text)
            for part in choice["content"]:
                if part.get("type") == "text":
                    return part["text"]
            return ""
        return choice.get("content", "")

    async def extract_concurrent(self, items: list[dict],
                                  max_concurrent: int = EXTRACT_CONCURRENCY) -> list[str]:
        """Pipeline K2.5 extraction calls with concurrency control.

        Args:
            items: List of dicts, each with "model", "messages", and optional "thinking" keys
            max_concurrent: Max parallel requests

        Returns:
            List of response strings in order (empty string on failure)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = [None] * len(items)

        async def _extract_one(idx, item):
            async with semaphore:
                try:
                    result = await self.chat(
                        model=item.get("model", NIM_EXTRACTION_MODEL),
                        messages=item.get("messages", []),
                        thinking=item.get("thinking"),
                    )
                    results[idx] = result
                except Exception as e:
                    print(f"[WARN] NIM extraction {idx} failed: {e}")
                    results[idx] = ""

        await asyncio.gather(*[_extract_one(i, item) for i, item in enumerate(items)])
        return results

    # ── Embeddings (batchable) ──

    async def embed(self, texts: list[str], model: str = NIM_EMBEDDING_MODEL) -> list[list[float]]:
        """Batch embedding. Automatically chunks into EMBED_BATCH_SIZE per API call.

        Example: 200 texts -> 10 API calls (20 each) instead of 200 calls.
        """
        if not NVIDIA_API_KEY:
            raise RuntimeError("NVIDIA_API_KEY not set")
        if not texts:
            return []
        self._check_health()

        results = []
        for chunk in _chunked(texts, EMBED_BATCH_SIZE):
            await self._rate_limiter.acquire()
            payload = {
                "model": model,
                "input": list(chunk),
                "input_type": "query",
                "encoding_format": "float",
            }
            data = await self._post(f"{NIM_BASE_URL}/embeddings", payload)
            # Sort by index to maintain order
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            results.extend(item["embedding"] for item in sorted_data)
        return results

    # ── Reranking (already batched by design) ──

    async def rerank(self, query: str, passages: list[str],
                     model: str = NIM_RERANK_MODEL, top_n: int = 5) -> list[dict]:
        """Rerank passages by relevance to query.

        Returns list of {"index": int, "logit": float, "text": str} sorted by relevance.
        """
        if not NVIDIA_API_KEY:
            raise RuntimeError("NVIDIA_API_KEY not set")
        if not passages:
            return []
        self._check_health()

        await self._rate_limiter.acquire()

        # Format passages as objects with text field
        passage_objects = [{"text": p} for p in passages[:RERANK_MAX_PASSAGES]]

        payload = {
            "model": model,
            "query": {"text": query},
            "passages": passage_objects,
            "top_n": min(top_n, len(passages)),
        }

        rerank_url = f"{NIM_RERANK_BASE_URL}/{NIM_RERANK_URL_MODEL}/reranking"
        data = await self._post(rerank_url, payload)

        # Normalize response — attach original text
        rankings = data.get("rankings", [])
        for item in rankings:
            idx = item.get("index", 0)
            if idx < len(passages):
                item["text"] = passages[idx]
        return rankings

    # ── Sync wrappers ──

    def _run_sync(self, coro):
        """Run an async coroutine synchronously using a background event loop thread.

        A dedicated thread runs the event loop, so asyncio.current_task() works
        correctly for aiohttp timeouts. The loop persists across calls so
        the aiohttp session stays valid.
        """
        import threading

        if self._sync_loop is None or self._sync_loop.is_closed():
            self._sync_loop = asyncio.new_event_loop()
            t = threading.Thread(target=self._sync_loop.run_forever, daemon=True)
            t.start()

        future = asyncio.run_coroutine_threadsafe(coro, self._sync_loop)
        return future.result(timeout=REQUEST_TIMEOUT_SECONDS + 10)

    def chat_sync(self, **kwargs) -> str:
        """Sync wrapper for chat."""
        return self._run_sync(self.chat(**kwargs))

    def embed_sync(self, texts: list[str], **kwargs) -> list[list[float]]:
        """Sync wrapper for embedding."""
        return self._run_sync(self.embed(texts, **kwargs))

    def rerank_sync(self, query: str, passages: list[str], **kwargs) -> list[dict]:
        """Sync wrapper for reranking."""
        return self._run_sync(self.rerank(query, passages, **kwargs))


# ── Module-level singleton ──

_client = None


def get_client() -> NIMClient:
    """Return the global NIMClient singleton."""
    global _client
    if _client is None:
        _client = NIMClient()
    return _client
