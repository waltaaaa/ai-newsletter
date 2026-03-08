"""
url_verify.py — URL verification module for CAN-MACRO dashboard.

Every source URL must pass verification before entering the database.
Valid: specific article, registry page, press release, RSS item landing page,
       API endpoint, StatCan table, Wayback snapshot.
Never valid: homepage, search results, section landing, RSS feed XML URL itself,
             generic about page, non-200, page not mentioning claim, AI-invented URL.
"""

import re
import sys
import time
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

# ── Constants ────────────────────────────────────────────────────────────────

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/2.0'
_HEADERS = {
    'User-Agent': _UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# Patterns that indicate search/listing/category pages — always reject
_REJECT_PATTERNS = re.compile(
    r'(search\?|[?&]q=|/results|/tag/|/category/|/topics?/'
    r'|/archive/?$|/page/\d|/feed/?$|\.rss$|\.atom$|\.xml$)',
    re.IGNORECASE,
)

# Status constants
DIRECT   = 'DIRECT'    # Page is specifically about this claim/project
RELEVANT = 'RELEVANT'  # Page mentions the claim among other content
GENERIC  = 'GENERIC'   # Homepage or section landing page
DEAD     = 'DEAD'      # Returns non-200 or times out


# ── Main verify function ─────────────────────────────────────────────────────

def verify_url(url: str, claim_text: str, timeout: int = 15) -> dict:
    """
    Verify a URL is a valid, direct source for the given claim.

    Parameters
    ----------
    url : str
        The URL to verify.
    claim_text : str
        The claim, project name, or text that should appear on the page.
    timeout : int
        HTTP request timeout in seconds.

    Returns
    -------
    dict with keys:
        status   : DIRECT | RELEVANT | GENERIC | DEAD
        accepted : bool (True if DIRECT or RELEVANT)
        reason   : str (human-readable explanation)
        excerpt  : str (snippet from page mentioning claim, if found)
        url      : str (the URL that was tested, for logging)
    """
    result = {'url': url, 'status': DEAD, 'accepted': False, 'reason': '', 'excerpt': ''}

    # ── 0. Basic validation ───────────────────────────────────────────────
    if not url or not url.startswith('http'):
        result['reason'] = 'Empty or non-HTTP URL'
        return result

    parsed = urlparse(url)
    path_segs = [s for s in parsed.path.split('/') if s]

    # ── 1. Reject homepage (<2 path segments unless has query params) ─────
    if len(path_segs) < 2 and not parsed.query:
        result['status'] = GENERIC
        result['reason'] = f'Homepage — only {len(path_segs)} path segment(s), no query params'
        return result

    # ── 2. Reject search/listing patterns ─────────────────────────────────
    full_url = url
    if _REJECT_PATTERNS.search(full_url):
        result['status'] = GENERIC
        result['reason'] = 'Search/listing/category/feed page detected'
        return result

    # ── 3. HTTP GET with browser User-Agent ───────────────────────────────
    try:
        r = requests.get(url, timeout=timeout, headers=_HEADERS, allow_redirects=True)
    except requests.exceptions.Timeout:
        result['reason'] = f'Timeout after {timeout}s'
        return result
    except requests.exceptions.ConnectionError as e:
        result['reason'] = f'Connection error: {str(e)[:80]}'
        return result
    except Exception as e:
        result['reason'] = f'GET error: {type(e).__name__}: {str(e)[:80]}'
        return result

    # ── 4. Must be 200 ────────────────────────────────────────────────────
    if r.status_code != 200:
        result['reason'] = f'HTTP {r.status_code}'
        return result

    # ── 5. Content relevance check ────────────────────────────────────────
    page_text = r.text[:20000].lower()

    # Check if page title is just a generic site name
    if _HAS_BS4:
        try:
            soup = BeautifulSoup(r.text[:5000], 'html.parser')
            title_el = soup.find('title')
            title_text = (title_el.get_text(strip=True) if title_el else '').lower()
            if title_text and len(title_text) < 25 and len(page_text) < 2000:
                result['status'] = GENERIC
                result['reason'] = f'Page title too generic: "{title_text[:50]}"'
                return result
        except Exception:
            pass

    # Extract keywords from claim (4+ chars for meaningful matching)
    claim_words = [w for w in claim_text.lower().split() if len(w) >= 4]
    if not claim_words:
        # Fall back to 3+ chars
        claim_words = [w for w in claim_text.lower().split() if len(w) >= 3]
    if not claim_words:
        result['status'] = GENERIC
        result['reason'] = 'Claim text too short to verify against page content'
        return result

    matched = sum(1 for w in claim_words if w in page_text)
    match_ratio = matched / len(claim_words) if claim_words else 0

    if matched == 0:
        result['status'] = GENERIC
        result['reason'] = (f'Claim not found on page — 0/{len(claim_words)} '
                            f'keywords matched')
        return result

    # Extract excerpt around first match
    excerpt = ''
    for w in claim_words:
        idx = page_text.find(w)
        if idx >= 0:
            start = max(0, idx - 100)
            end   = min(len(r.text), idx + 300)
            excerpt = r.text[start:end].strip()
            excerpt = re.sub(r'\s+', ' ', excerpt)[:500]
            break

    # Determine quality: exact match = DIRECT, 60%+ keyword = RELEVANT
    if match_ratio >= 0.6 and len(path_segs) >= 2:
        result['status'] = DIRECT
        result['accepted'] = True
        result['reason'] = f'{matched}/{len(claim_words)} keywords matched (DIRECT)'
    elif matched >= 1:
        result['status'] = RELEVANT
        result['accepted'] = True
        result['reason'] = f'{matched}/{len(claim_words)} keywords matched (RELEVANT)'
    else:
        result['status'] = GENERIC
        result['reason'] = f'Only {matched}/{len(claim_words)} keywords matched'

    result['excerpt'] = excerpt
    return result


# ── Batch verification ────────────────────────────────────────────────────────

def verify_urls_batch(
    items: list[dict],
    url_key: str = 'url',
    claim_key: str = 'name',
    timeout: int = 12,
    delay: float = 0.3,
) -> tuple[list[dict], list[dict]]:
    """
    Verify a batch of items. Each item is a dict with at least url_key and claim_key.

    Returns (passed, failed) where each entry has the original item
    plus a '_verify' key with the verify_url result.
    """
    passed = []
    failed = []
    for item in items:
        url   = item.get(url_key, '')
        claim = item.get(claim_key, '')
        result = verify_url(url, claim, timeout=timeout)
        item['_verify'] = result
        if result['accepted']:
            passed.append(item)
        else:
            failed.append(item)
        if delay > 0:
            time.sleep(delay)
    return passed, failed


# ── Quick URL pre-filter (no HTTP, just pattern checks) ──────────────────────

def quick_reject(url: str) -> str | None:
    """
    Fast pre-filter that rejects obviously bad URLs without making HTTP requests.
    Returns rejection reason string, or None if URL passes pre-filter.
    """
    if not url or not url.startswith('http'):
        return 'Empty or non-HTTP URL'
    parsed = urlparse(url)
    path_segs = [s for s in parsed.path.split('/') if s]
    if len(path_segs) < 2 and not parsed.query:
        return f'Homepage — {len(path_segs)} path segment(s)'
    if _REJECT_PATTERNS.search(url):
        return 'Search/listing/category/feed page'
    return None
