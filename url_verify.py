"""
url_verify.py — Consolidated URL verification module for CAN-MACRO dashboard.

Three verification layers:
  1. verify_url_sync() — Synchronous single-URL content verification (was url_verify.py)
  2. verify_urls_async() — Async batch HEAD/GET reachability check (was url_verifier.py)
  3. verify_with_wayback_fallback() — Gemini-powered second-source confirmation
     for single-source projects (was deep_verification.py)

Also provides:
  - quick_reject() — fast pre-filter (no HTTP)
  - verify_urls_batch() — sync batch content verification
"""

import asyncio
import json
import re
import logging
import time
from datetime import datetime
from urllib.parse import urlparse

import aiohttp
import requests

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from url_utils import normalize_url

logger = logging.getLogger(__name__)

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

# Async verification constants
MAX_CONCURRENT_CHECKS = 30
TIMEOUT_SECONDS = 10

# Deep verification constants
MAX_VERIFICATION_PER_RUN = 50

VERIFY_SYSTEM_PROMPT = """You are a fact-checker for a Canadian infrastructure intelligence system.
Your job is to independently verify that a specific capital project exists and is real.
Search for the project name and proponent. Check government sites, news, and corporate announcements.

Return ONLY a valid JSON object (no markdown fences):
{
  "confirmed": true,
  "status": "Under Construction",
  "value_millions": 650,
  "source_url": "https://example.com/article",
  "source_name": "Source publication",
  "confidence_notes": "Any caveats or notes"
}

Rules:
- confirmed: true if you found independent evidence the project exists, false otherwise
- status: current project status if found (Proposed, Approved, Under Construction, Completed, Cancelled, Delayed)
- value_millions: project cost in millions CAD if found, null if not
- source_url: URL of the best independent source found
- source_name: name of the publication or organization
- If you cannot find independent evidence, set confirmed to false
- Do NOT fabricate information. If unsure, set confirmed to false
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1: Synchronous single-URL content verification
# ═══════════════════════════════════════════════════════════════════════════════

def verify_url_sync(url: str, claim_text: str, timeout: int = 15) -> dict:
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
    if _REJECT_PATTERNS.search(url):
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


# Backward-compatible alias — old name used by seed_projects_v2, citation_audit
verify_url = verify_url_sync


def verify_urls_batch(
    items: list[dict],
    url_key: str = 'url',
    claim_key: str = 'name',
    timeout: int = 12,
    delay: float = 0.3,
) -> tuple[list[dict], list[dict]]:
    """
    Verify a batch of items synchronously. Each item is a dict with at least
    url_key and claim_key.

    Returns (passed, failed) where each entry has the original item
    plus a '_verify' key with the verify_url_sync result.
    """
    passed = []
    failed = []
    for item in items:
        url   = item.get(url_key, '')
        claim = item.get(claim_key, '')
        result = verify_url_sync(url, claim, timeout=timeout)
        item['_verify'] = result
        if result['accepted']:
            passed.append(item)
        else:
            failed.append(item)
        if delay > 0:
            time.sleep(delay)
    return passed, failed


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


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2: Async batch HEAD/GET reachability check (was url_verifier.py)
# ═══════════════════════════════════════════════════════════════════════════════

async def _check_url_async(session, semaphore, url):
    """HEAD request to check if URL is reachable."""
    async with semaphore:
        try:
            async with session.head(
                url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                allow_redirects=True,
                headers={"User-Agent": _UA},
            ) as resp:
                return resp.status < 400
        except Exception:
            # Try GET as fallback (some servers reject HEAD)
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                    allow_redirects=True,
                    headers={"User-Agent": _UA},
                ) as resp:
                    return resp.status < 400
            except Exception:
                return False


async def verify_urls_async(projects):
    """Verify all evidence URLs across all projects via async HEAD/GET.

    Mutates projects in place — adds 'url_verified' field to each evidence entry.
    Returns count of verified vs broken URLs.
    """
    # Collect all unique URLs to check
    url_to_projects = {}  # url -> list of (project_index, evidence_index)
    for pi, project in enumerate(projects):
        for ei, ev in enumerate(project.get("evidence", [])):
            url = ev.get("url", "")
            if url and url.startswith("http"):
                url_to_projects.setdefault(url, []).append((pi, ei))

    unique_urls = list(url_to_projects.keys())
    if not unique_urls:
        return {"verified": 0, "broken": 0, "total": 0}

    logger.info(f"Verifying {len(unique_urls)} unique URLs across {len(projects)} projects")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    async with aiohttp.ClientSession() as session:
        tasks = [_check_url_async(session, semaphore, url) for url in unique_urls]
        checks = await asyncio.gather(*tasks, return_exceptions=True)

    verified = 0
    broken = 0

    for url, check in zip(unique_urls, checks):
        reachable = check if isinstance(check, bool) else False

        # Mark all evidence entries for this URL
        for pi, ei in url_to_projects[url]:
            projects[pi]["evidence"][ei]["url_verified"] = reachable
            projects[pi]["evidence"][ei]["url_checked"] = True

        if reachable:
            verified += 1
        else:
            broken += 1

    logger.info(f"URL verification: {verified} verified, {broken} broken out of {len(unique_urls)}")
    return {"verified": verified, "broken": broken, "total": len(unique_urls)}


def verify_urls_async_sync(projects):
    """Synchronous wrapper for verify_urls_async."""
    if not projects:
        return {"verified": 0, "broken": 0, "total": 0}

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(verify_urls_async(projects))
        else:
            return asyncio.run(verify_urls_async(projects))
    except RuntimeError:
        return asyncio.run(verify_urls_async(projects))


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 3: Gemini-powered second-source confirmation (was deep_verification.py)
# ═══════════════════════════════════════════════════════════════════════════════

def select_projects_for_verification(conn, max_candidates=MAX_VERIFICATION_PER_RUN):
    """Select single-source projects needing independent confirmation.

    Priority (highest first):
    1. evidence_count == 1, no gov/known source, high value
    2. evidence_count == 1, low confidence
    3. evidence_count == 1, recently discovered

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns list of (doc_id, project_dict).
    """
    candidates = []
    now = datetime.utcnow()

    if hasattr(conn, 'execute'):
        from db import get_all_projects
        all_projects = get_all_projects(conn)
        for data in all_projects:
            evidence_raw = data.get("evidence", "[]")
            if isinstance(evidence_raw, str):
                try:
                    evidence = json.loads(evidence_raw)
                except Exception:
                    evidence = []
            else:
                evidence = evidence_raw or []
            evidence_count = len(evidence)

            if evidence_count != 1:
                continue

            status = (data.get("status") or "").lower()
            if status in ("cancelled", "canceled", "completed"):
                continue

            last_check = data.get("last_verification_check", "")
            if last_check:
                try:
                    lc = datetime.fromisoformat(str(last_check)[:10])
                    if (now - lc).days < 30:
                        continue
                except (ValueError, TypeError):
                    pass

            value_m = _parse_value(data.get("value", ""))
            confidence = data.get("confidence", 0.5)
            has_gov = bool(data.get("has_government_source", False))
            has_known = bool(data.get("has_known_source", False))

            priority = value_m
            if not has_gov and not has_known:
                priority *= 2
            if confidence < 0.4:
                priority *= 1.5

            candidates.append((data.get("norm_key", ""), data, priority))

        candidates.sort(key=lambda x: x[2], reverse=True)
        return [(did, d) for did, d, _ in candidates[:max_candidates]]

    # Legacy Firestore path
    for doc in conn.collection("projects").stream():
        data = doc.to_dict()
        evidence = data.get("evidence", [])
        evidence_count = len(evidence)

        if evidence_count != 1:
            continue

        status = (data.get("status") or "").lower()
        if status in ("cancelled", "canceled", "completed"):
            continue

        # Skip recently verified
        last_check = data.get("last_verification_check", "")
        if last_check:
            try:
                lc = datetime.fromisoformat(str(last_check)[:10])
                if (now - lc).days < 30:
                    continue
            except (ValueError, TypeError):
                pass

        # Parse value for prioritization
        value_m = _parse_value(data.get("value", ""))
        confidence = data.get("confidence", 0.5)
        has_gov = data.get("has_government_source", False)
        has_known = data.get("has_known_source", False)

        priority = value_m
        if not has_gov and not has_known:
            priority *= 2
        if confidence < 0.4:
            priority *= 1.5

        candidates.append((doc.id, data, priority))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return [(did, d) for did, d, _ in candidates[:max_candidates]]


def build_verification_query(doc_id, project):
    """Build a Gemini query to independently confirm a project."""
    name = project.get("name", "Unknown")
    province = project.get("province", "")
    cma = project.get("cma", "")
    proponent = project.get("proponent", "")
    value = project.get("value", "")

    location = f"{cma}, {province}" if cma else province
    value_str = f" (estimated {value})" if value and value not in ("", "--", "Not disclosed") else ""
    proponent_str = f" by {proponent}" if proponent and proponent != "Unknown" else ""

    return {
        "query": (
            f"Independently verify: Does the {name} project{proponent_str} "
            f"exist in {location}, Canada{value_str}? "
            f"Find independent confirmation from government records, news articles, "
            f"industry publications, or corporate announcements. "
            f"Report: whether the project is confirmed, its current status, "
            f"estimated value, and your best source URL."
        ),
        "type": "verification",
        "doc_id": doc_id,
        "project_name": name,
    }


def _parse_verification_result(engine_result):
    """Parse a verification query result from gemini_engine."""
    text = engine_result.get("text", "")
    grounding_urls = [g["url"] if isinstance(g, dict) else g
                      for g in engine_result.get("grounding_urls", [])]

    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)

    obj_start = text.find('{')
    if obj_start >= 0:
        depth = 0
        for i in range(obj_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[obj_start:i + 1])
                        data["_grounding_urls"] = grounding_urls
                        return data
                    except json.JSONDecodeError:
                        pass
                    break

    return {"confirmed": False, "_grounding_urls": grounding_urls}


def apply_verification_results(conn, results):
    """Write verification results back to SQLite.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns {"confirmed": int, "unconfirmed": int, "errors": int}
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    confirmed = 0
    unconfirmed = 0
    errors = 0
    use_sqlite = hasattr(conn, 'execute')

    for r in results:
        if r.get("error"):
            errors += 1
            continue

        doc_id = r["query"]["doc_id"]
        parsed = r.get("parsed")
        if not parsed:
            errors += 1
            continue

        updates = {"last_verification_check": today}

        if parsed.get("confirmed"):
            confirmed += 1
            grounding_urls = parsed.get("_grounding_urls", [])
            source_url = parsed.get("source_url", "")

            if use_sqlite:
                try:
                    row = conn.execute(
                        "SELECT evidence, confidence, value FROM projects WHERE norm_key = ?",
                        (doc_id,),
                    ).fetchone()
                    if row:
                        evidence = json.loads(row["evidence"] or "[]")
                        existing_urls = {e.get("url") for e in evidence if e.get("url")}

                        if source_url and source_url.startswith("http") and source_url not in existing_urls:
                            evidence.append({
                                "url": source_url,
                                "name": parsed.get("source_name", ""),
                                "date": today,
                                "source_type": "verification",
                            })
                            existing_urls.add(source_url)

                        for url in grounding_urls:
                            if url and url.startswith("http") and url not in existing_urls:
                                evidence.append({
                                    "url": url, "name": "", "date": today,
                                    "source_type": "verification_grounding",
                                })
                                existing_urls.add(url)

                        updates["evidence"] = json.dumps(evidence, ensure_ascii=False)
                        updates["evidence_count"] = len(evidence)

                        old_conf = row["confidence"] or 0.3
                        if len(evidence) >= 2:
                            updates["confidence"] = max(old_conf, 0.7)
                        updates["verification_status"] = "confirmed"

                        # Update value if missing
                        val_m = parsed.get("value_millions")
                        if val_m and val_m > 0:
                            cur_val = (row["value"] or "").lower()
                            if cur_val in ("", "--", "not disclosed", "unknown", "n/a", "tbd"):
                                if val_m >= 1000:
                                    updates["value"] = f"C${val_m/1000:.1f}B"
                                else:
                                    updates["value"] = f"C${val_m:.0f}M"
                except Exception as e:
                    logger.warning(f"Verification evidence merge failed: {e}")
            else:
                # Firestore path
                try:
                    doc_ref = conn.collection("projects").document(doc_id)
                    existing = doc_ref.get().to_dict() or {}
                    evidence = existing.get("evidence", [])
                    existing_urls = {e.get("url") for e in evidence if e.get("url")}

                    if source_url and source_url.startswith("http") and source_url not in existing_urls:
                        evidence.append({
                            "url": source_url,
                            "name": parsed.get("source_name", ""),
                            "date": today,
                            "source_type": "verification",
                        })
                        existing_urls.add(source_url)

                    for url in grounding_urls:
                        if url and url.startswith("http") and url not in existing_urls:
                            evidence.append({"url": url, "name": "", "date": today,
                                             "source_type": "verification_grounding"})
                            existing_urls.add(url)

                    updates["evidence"] = evidence
                    updates["evidence_count"] = len(evidence)
                    old_conf = existing.get("confidence", 0.3)
                    if len(evidence) >= 2:
                        updates["confidence"] = max(old_conf, 0.7)
                    updates["verification_status"] = "confirmed"

                    val_m = parsed.get("value_millions")
                    if val_m and val_m > 0:
                        cur_val = (existing.get("value") or "").lower()
                        if cur_val in ("", "--", "not disclosed", "unknown", "n/a", "tbd"):
                            if val_m >= 1000:
                                updates["value"] = f"C${val_m/1000:.1f}B"
                            else:
                                updates["value"] = f"C${val_m:.0f}M"
                except Exception as e:
                    logger.warning(f"Verification evidence merge failed: {e}")

            print(f"    [VERIFIED] {r['query']['project_name'][:50]}")
        else:
            unconfirmed += 1
            updates["verification_status"] = "unconfirmed"
            print(f"    [UNVERIFIED] {r['query']['project_name'][:50]}")

        # Apply updates
        if use_sqlite:
            set_clauses = [f"{k} = ?" for k in updates]
            params = list(updates.values()) + [doc_id]
            try:
                with conn:
                    conn.execute(
                        f"UPDATE projects SET {', '.join(set_clauses)} WHERE norm_key = ?",
                        params,
                    )
            except Exception as e:
                logger.warning(f"[VERIFY] Update failed for {doc_id}: {e}")
        else:
            conn.collection("projects").document(doc_id).update(updates)

    return {"confirmed": confirmed, "unconfirmed": unconfirmed, "errors": errors}


async def _run_deep_verification_async(conn, max_queries=MAX_VERIFICATION_PER_RUN):
    """Run verification queries for single-source projects."""
    from gemini_engine import run_batch

    candidates = select_projects_for_verification(conn, max_queries)
    if not candidates:
        print("  [VERIFY] No single-source projects need verification.")
        return {"confirmed": 0, "unconfirmed": 0, "errors": 0}

    queries = [build_verification_query(did, p) for did, p in candidates]
    print(f"  [VERIFY] Checking {len(queries)} single-source projects...")

    raw_results = await run_batch(queries, VERIFY_SYSTEM_PROMPT,
                                  max_concurrent=10, tag="VERIFY")

    # Parse each result
    results = []
    for r in raw_results:
        parsed = _parse_verification_result(r)
        results.append({
            "query": r["query"],
            "parsed": parsed,
            "error": r.get("error"),
        })

    summary = apply_verification_results(conn, results)
    print(f"  [VERIFY] {summary['confirmed']} confirmed, "
          f"{summary['unconfirmed']} unconfirmed, {summary['errors']} errors")
    return summary


def verify_with_wayback_fallback(conn, max_queries=MAX_VERIFICATION_PER_RUN):
    """Synchronous entry point for deep verification (second-source confirmation).

    Formerly deep_verification.run_verification().
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                _run_deep_verification_async(conn, max_queries))
        else:
            return asyncio.run(_run_deep_verification_async(conn, max_queries))
    except RuntimeError:
        return asyncio.run(_run_deep_verification_async(conn, max_queries))


# Backward-compatible alias — capacity_scheduler uses run_verification
run_verification = verify_with_wayback_fallback


def _parse_value(val_str):
    """Parse value string to millions float."""
    if not val_str:
        return 0
    s = str(val_str).upper().replace(',', '').replace('$', '').replace('C', '')
    m = re.match(r'\s*(\d+(?:\.\d+)?)\s*(B|M|K)?', s)
    if not m:
        return 0
    n = float(m.group(1))
    unit = (m.group(2) or 'M')
    if unit == 'B':
        n *= 1000
    elif unit == 'K':
        n /= 1000
    return n
