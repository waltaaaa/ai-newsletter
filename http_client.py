"""
http_client.py — Shared HTTP client for the Lagging Indicator discovery pipeline.

Patch v1.2 (audit issues D-7, D-8, D-9): every government / municipal / institutional
scraper that hit a default ``python-requests/2.x`` User-Agent was getting silently
bot-blocked (HTTP 403) or failing TLS verification on Windows OpenSSL stores that lack
intermediate CAs (CERTIFICATE_VERIFY_FAILED, e.g. IWK Health).

This module centralises:
  * a realistic desktop-browser User-Agent + Accept / Accept-Language (en-CA) /
    Accept-Encoding headers (clears most uniform 403 bot blocks),
  * ``verify=certifi.where()`` on every request (fixes the Windows CA-chain TLS
    failures without disabling verification),
  * a sane 20 s default timeout,
  * per-host exponential-backoff retry (2 retries by default) on transient
    network errors and 429 / 5xx responses.

Public API (keep stable — scrapers depend on these signatures):
  make_session(**overrides)            -> requests.Session   (session factory)
  get(url, **kw)                       -> requests.Response | None
  get_json(url, **kw)                  -> parsed JSON | None
  head(url, **kw)                      -> requests.Response | None

The fetch helpers NEVER raise on network/HTTP failure: they print a structured
``[http_client] <METHOD> <url> FAILED ...`` line and return ``None`` so callers
can degrade gracefully. Callers that need the raw exception can still use a
session from ``make_session()`` directly.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

try:
    import certifi
    _CA_BUNDLE = certifi.where()
except Exception:  # pragma: no cover - certifi should always be present
    certifi = None
    _CA_BUNDLE = True  # fall back to requests' default verification

# Realistic desktop-Chrome User-Agent. The trailing product token lets operators
# identify our traffic in server logs without tripping naive bot heuristics.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Lagging-Indicator/1.2"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
    # No "br": requests can only decode brotli if the optional brotli package
    # is installed; advertising it without the decoder turns ArcGIS Online
    # (and any other brotli-preferring host) responses into undecodable bytes.
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

DEFAULT_TIMEOUT = 20      # seconds
DEFAULT_RETRIES = 2       # number of *retries* after the first attempt
_BACKOFF_BASE = 0.75      # seconds; doubles each retry (0.75, 1.5, 3.0, ...)
# HTTP status codes worth retrying (transient server / rate-limit conditions).
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def make_session(**overrides) -> requests.Session:
    """
    Build a ``requests.Session`` pre-loaded with browser-like headers and
    certifi-backed TLS verification.

    Args:
        **overrides: extra default headers to merge in (e.g. a JSON Accept).
                     Any key matching a DEFAULT_HEADERS key overrides it.

    The returned session works fully offline — no network call is made here.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if overrides:
        # Only string header values are merged; this keeps the factory simple
        # and lets callers do make_session(Accept="application/json").
        session.headers.update({k: v for k, v in overrides.items()
                                if isinstance(v, str)})
    session.verify = _CA_BUNDLE
    return session


# A module-level shared session keeps connection pooling across the many
# per-host requests a single pipeline run makes.
_SHARED_SESSION: Optional[requests.Session] = None


def _session() -> requests.Session:
    global _SHARED_SESSION
    if _SHARED_SESSION is None:
        _SHARED_SESSION = make_session()
    return _SHARED_SESSION


def _request(method: str, url: str, *,
             session: Optional[requests.Session] = None,
             retries: int = DEFAULT_RETRIES,
             timeout: int = DEFAULT_TIMEOUT,
             raise_for_status: bool = False,
             **kw) -> Optional[requests.Response]:
    """
    Core request helper with per-host exponential-backoff retry.

    Returns the Response on success, or None on hard failure (after retries).
    Never raises for network/HTTP errors unless ``raise_for_status=True`` is set
    AND the final response is >=400 (then it raises requests.HTTPError).
    """
    sess = session or _session()
    kw.setdefault("timeout", timeout)
    # Ensure certifi verification even when a one-off session isn't used.
    kw.setdefault("verify", _CA_BUNDLE)

    last_exc: Optional[Exception] = None
    resp: Optional[requests.Response] = None

    for attempt in range(retries + 1):
        try:
            resp = sess.request(method, url, **kw)
            if resp.status_code in _RETRY_STATUSES and attempt < retries:
                time.sleep(_BACKOFF_BASE * (2 ** attempt))
                continue
            if raise_for_status:
                resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(_BACKOFF_BASE * (2 ** attempt))
                continue
            # Final attempt failed.
            print(f"[http_client] {method} {url[:80]} FAILED "
                  f"{type(e).__name__}: {e}")
            return None

    # Exhausted retries on a retryable status code without exception.
    if resp is not None:
        if raise_for_status and resp.status_code >= 400:
            resp.raise_for_status()
        return resp
    if last_exc is not None:
        print(f"[http_client] {method} {url[:80]} FAILED "
              f"{type(last_exc).__name__}: {last_exc}")
    return None


def get(url: str, **kw) -> Optional[requests.Response]:
    """GET ``url`` with browser headers + retry. Returns Response or None."""
    return _request("GET", url, **kw)


def head(url: str, **kw) -> Optional[requests.Response]:
    """HEAD ``url`` (health probe). Follows redirects by default."""
    kw.setdefault("allow_redirects", True)
    return _request("HEAD", url, **kw)


def get_json(url: str, **kw) -> Optional[object]:
    """
    GET ``url`` and parse the body as JSON. Returns the parsed object, or None
    on network failure, non-2xx status, or JSON decode error.
    """
    resp = _request("GET", url, **kw)
    if resp is None:
        return None
    if resp.status_code >= 400:
        print(f"[http_client] GET-JSON {url[:80]} FAILED status={resp.status_code}")
        return None
    try:
        return resp.json()
    except ValueError as e:
        print(f"[http_client] GET-JSON {url[:80]} decode error: {e}")
        return None
