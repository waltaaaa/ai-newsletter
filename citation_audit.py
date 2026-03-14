"""
citation_audit.py — Post-writing citation audit for CAN-MACRO dashboard.

Runs after EACH writing call. Nothing publishes without passing.

Steps:
  1. Extract all citations from writing output (parse {id, title, url})
  2. Verify every URL via url_verify.verify_url()
  3. Detect unsourced claims using Gemini Flash
  4. Spot-check 3-5 citations per call using Claude Sonnet
  5. Handle failures: remove sentences with bad citations
  6. Archive all verified citation URLs via wayback.save_page()
  7. Return audit result with pass/fail status
"""

import json
import os
import re
import time
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

# Lazy imports to avoid circular deps
_verify_url = None
_quick_reject = None
_wayback_save = None

def _load_url_verify():
    global _verify_url, _quick_reject
    if _verify_url is None:
        from url_verify import verify_url, quick_reject
        _verify_url = verify_url
        _quick_reject = quick_reject

def _load_wayback():
    global _wayback_save
    if _wayback_save is None:
        from wayback import save_page
        _wayback_save = save_page

TODAY = date.today().isoformat()
from pipeline_config import SONNET_MODEL
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

# ── Citation rules block appended to all writing prompts ─────────────────────

CITATION_RULES = """
CITATION RULES — MANDATORY:
1. Every factual claim must have a footnote citation [1], [2], etc. using <sup>N</sup> tags.
2. Citation URLs must come ONLY from provided sources. NEVER invent a URL.
3. No source for a claim means DO NOT make the claim. Skip it entirely.
4. Each citation: {id, title, url} with exact headline and exact URL from provided materials.
5. General knowledge claims still require a provided source citation. If unsourced, omit.
6. One footnote per distinct claim. No bundling.
"""


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Extract citations from writing output
# ══════════════════════════════════════════════════════════════════════════════

def extract_citations(payload: dict) -> list[dict]:
    """
    Extract all citation objects from a Claude writing output payload.
    Searches for 'sources', 'industrySources', and similar keys recursively.
    Returns list of {id, title, url, location} dicts.
    """
    citations = []
    _extract_recursive(payload, citations, path='')
    return citations


def _extract_recursive(obj, citations: list, path: str):
    """Recursively find all source/citation arrays in the payload."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            current_path = f"{path}.{key}" if path else key
            if key in ('sources', 'industrySources') and isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and (item.get('url') or item.get('title')):
                        citations.append({
                            'id': item.get('id', ''),
                            'title': (item.get('title') or '').strip(),
                            'url': (item.get('url') or '').strip(),
                            'location': current_path,
                        })
            elif key == 'source' and isinstance(val, dict):
                if val.get('url') or val.get('title'):
                    citations.append({
                        'id': val.get('id', ''),
                        'title': (val.get('title') or '').strip(),
                        'url': (val.get('url') or '').strip(),
                        'location': current_path,
                    })
            else:
                _extract_recursive(val, citations, current_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _extract_recursive(item, citations, f"{path}[{i}]")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Verify citation URLs
# ══════════════════════════════════════════════════════════════════════════════

def verify_citation_urls(citations: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Verify all citation URLs using url_verify module.
    Returns (passed, failed) lists with verification results.
    """
    _load_url_verify()
    passed = []
    failed = []
    for cite in citations:
        url = cite.get('url', '')
        if not url:
            # No URL — pass with note (might be sourced by title only)
            cite['verify_status'] = 'no_url'
            passed.append(cite)
            continue
        if _quick_reject(url):
            cite['verify_status'] = 'rejected'
            cite['verify_reason'] = 'URL pattern rejected'
            failed.append(cite)
            continue
        result = _verify_url(url, cite.get('title', ''))
        cite['verify_status'] = result.get('status', 'unknown')
        cite['verify_accepted'] = result.get('accepted', False)
        cite['verify_reason'] = result.get('reason', '')
        if result.get('accepted'):
            passed.append(cite)
        else:
            failed.append(cite)
    return passed, failed


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Detect unsourced claims using Gemini Flash
# ══════════════════════════════════════════════════════════════════════════════

def detect_unsourced_claims(text: str) -> list[str]:
    """
    Use Gemini Flash to find factual claims without footnote citations.
    Returns list of unsourced claim strings.
    """
    try:
        from google import genai
        from google.genai import types
        api_key = os.environ.get('GEMINI_API_KEY', '').strip()
        if not api_key:
            return []
        client = genai.Client(api_key=api_key)
        prompt = (
            "Analyze the following text. List any factual claims (specific numbers, dates, "
            "events, policy decisions, named entities with specific roles) that do NOT have a "
            "footnote citation (indicated by <sup>N</sup> tags).\n\n"
            "Return ONLY a JSON array of strings, where each string is the unsourced claim.\n"
            "If all claims are cited, return [].\n\n"
            f"TEXT:\n{text[:8000]}"
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                max_output_tokens=2048,
            )
        )
        raw = response.text.strip()
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"  [Citation Audit] Gemini unsourced detection error: {type(e).__name__}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Spot-check citations using Claude Sonnet
# ══════════════════════════════════════════════════════════════════════════════

def spot_check_citations(
    citations: list[dict],
    text: str,
    max_checks: int = 5,
    anthropic_client=None,
) -> list[dict]:
    """
    Spot-check a sample of citations using Claude Sonnet to verify claim-source alignment.
    Returns list of {citation, claim, supported, reason} dicts.
    """
    if not anthropic_client or not citations:
        return []

    # Select up to max_checks citations that have URLs and excerpts
    checkable = [c for c in citations if c.get('url') and c.get('verify_status') != 'no_url']
    import random
    sample = random.sample(checkable, min(max_checks, len(checkable)))

    results = []
    for cite in sample:
        # Find the claim that references this citation
        cite_id = cite.get('id', '')
        claim = _find_claim_for_citation(text, cite_id)
        if not claim:
            continue

        try:
            msg = anthropic_client.messages.create(
                model=SONNET_MODEL,
                max_tokens=200,
                messages=[{'role': 'user', 'content': (
                    f"Does this source support this claim?\n\n"
                    f"Claim: {claim}\n"
                    f"Source title: {cite.get('title', '')}\n"
                    f"Source URL: {cite.get('url', '')}\n\n"
                    f"Answer with ONLY 'Yes' or 'No' followed by a brief reason (one sentence)."
                )}],
            )
            answer = msg.content[0].text.strip()
            supported = answer.lower().startswith('yes')
            results.append({
                'citation': cite,
                'claim': claim,
                'supported': supported,
                'reason': answer,
            })
        except Exception as e:
            print(f"  [Citation Audit] Spot-check error: {type(e).__name__}")

    return results


def _find_claim_for_citation(text: str, cite_id) -> str:
    """Find the sentence containing a specific citation reference."""
    if not cite_id:
        return ''
    pattern = rf'[^.]*<sup>{cite_id}</sup>[^.]*\.'
    match = re.search(pattern, text)
    if match:
        return re.sub(r'<[^>]+>', '', match.group()).strip()
    return ''


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5-7: Full audit pipeline
# ══════════════════════════════════════════════════════════════════════════════

def run_citation_audit(
    payload: dict,
    call_label: str,
    anthropic_client=None,
    archive_urls: bool = True,
) -> dict:
    """
    Run the full citation audit pipeline on a writing call output.

    Parameters
    ----------
    payload : dict
        The JSON output from a Claude writing call.
    call_label : str
        Label for logging (e.g., 'call1-macro').
    anthropic_client
        Anthropic client for spot-checks (optional).
    archive_urls : bool
        Whether to archive verified URLs via Wayback.

    Returns
    -------
    dict with keys:
        passed: bool — True if audit passed
        total_citations: int
        verified_count: int
        failed_count: int
        unsourced_claims: list[str]
        spot_check_failures: list[dict]
        removal_pct: float — % of citations that failed
        failed_citations: list[dict]
        archived_count: int
    """
    print(f"\n  [Citation Audit] {call_label}...")

    # Step 1: Extract citations
    citations = extract_citations(payload)
    print(f"    Found {len(citations)} citations")
    if not citations:
        return {
            'passed': True, 'total_citations': 0,
            'verified_count': 0, 'failed_count': 0,
            'unsourced_claims': [], 'spot_check_failures': [],
            'removal_pct': 0.0, 'failed_citations': [],
            'archived_count': 0,
        }

    # Step 2: Verify URLs
    passed_cites, failed_cites = verify_citation_urls(citations)
    print(f"    URL verify: {len(passed_cites)} passed, {len(failed_cites)} failed")

    # Step 3: Detect unsourced claims
    # Build text from all analysis fields
    analysis_text = _extract_analysis_text(payload)
    unsourced = detect_unsourced_claims(analysis_text) if analysis_text else []
    if unsourced:
        print(f"    Unsourced claims detected: {len(unsourced)}")

    # Step 4: Spot-check (3-5 citations)
    spot_failures = []
    if anthropic_client and passed_cites:
        checks = spot_check_citations(passed_cites, analysis_text, max_checks=5, anthropic_client=anthropic_client)
        spot_failures = [c for c in checks if not c.get('supported')]
        if spot_failures:
            print(f"    Spot-check failures: {len(spot_failures)}")

    # Step 5: Calculate removal percentage
    total = max(len(citations), 1)
    failure_count = len(failed_cites) + len(spot_failures)
    removal_pct = (failure_count / total) * 100

    # Step 6: Archive verified URLs
    archived = 0
    if archive_urls and passed_cites:
        _load_wayback()
        for cite in passed_cites:
            url = cite.get('url', '')
            if url and _wayback_save:
                archive_url = _wayback_save(url)
                if archive_url:
                    cite['archive_url'] = archive_url
                    archived += 1

    # Step 7: Determine pass/fail
    passed = removal_pct < 30.0
    status_str = 'PASSED' if passed else 'FAILED (>30% removal — flag for manual review)'
    print(f"    Audit {status_str}: {failure_count}/{len(citations)} citations failed ({removal_pct:.1f}%)")
    if archived:
        print(f"    Archived {archived} citation URLs")

    failed_citations_list = [
        {'id': c.get('id', ''), 'url': c.get('url', ''), 'title': c.get('title', ''),
         'reason': c.get('verify_reason', ''), 'location': c.get('location', '')}
        for c in failed_cites
    ]

    return {
        'passed': passed,
        'total_citations': len(citations),
        'verified_count': len(passed_cites),
        'failed_count': len(failed_cites),
        'unsourced_claims': unsourced,
        'spot_check_failures': [
            {'claim': f['claim'], 'reason': f['reason']}
            for f in spot_failures
        ],
        'removal_pct': removal_pct,
        'failed_citations': failed_citations_list,
        'archived_count': archived,
        'verified_citations': [
            {'url': c.get('url', ''), 'title': c.get('title', ''),
             'archive_url': c.get('archive_url', ''),
             'location': c.get('location', '')}
            for c in passed_cites
        ],
    }


def _extract_analysis_text(payload: dict) -> str:
    """Extract all analysis/text content from a payload for unsourced claim detection."""
    parts = []
    if payload.get('executive_summary'):
        parts.append(payload['executive_summary'])
    if payload.get('national', {}).get('analysis'):
        parts.append(payload['national']['analysis'])
    if payload.get('consumer_pulse'):
        parts.append(payload['consumer_pulse'])
    if payload.get('industry_executive_summary'):
        parts.append(payload['industry_executive_summary'])
    for g in payload.get('global', []):
        if g.get('analysis'):
            parts.append(g['analysis'])
    # Global vectors dict
    gv = payload.get('global_vectors') or payload.get('globalVectors') or {}
    if isinstance(gv, dict):
        for region in ('us', 'china', 'eu', 'uk'):
            if gv.get(region):
                parts.append(gv[region])
    for ind in payload.get('goodsIndustries', []) + payload.get('servicesIndustries', []):
        if ind.get('analysis'):
            parts.append(ind['analysis'])
    for prov in payload.get('provinces', []):
        if prov.get('analysis'):
            parts.append(prov['analysis'])
    return '\n\n'.join(parts)


def remove_failed_claims(text: str, failed_citations: list[dict], unsourced_claims: list[str]) -> str:
    """
    Remove sentences that reference failed citations or contain unsourced claims.

    Returns the cleaned text with failed sentences removed.
    """
    if not text:
        return text

    # Remove sentences referencing failed citation IDs
    for fc in failed_citations:
        cite_id = fc.get('id', '')
        if cite_id:
            # Remove sentence containing the failed citation reference
            pattern = rf'[^.]*<sup>{re.escape(str(cite_id))}</sup>[^.]*\.\s*'
            text = re.sub(pattern, '', text)

    # Remove unsourced claims (match by substring)
    for claim in unsourced_claims:
        if len(claim) < 20:
            continue  # too short to safely match
        # Escape for regex and match the surrounding sentence
        escaped = re.escape(claim[:80])
        pattern = rf'[^.]*{escaped}[^.]*\.\s*'
        text = re.sub(pattern, '', text, count=1)

    return text.strip()


def save_audit_log(audits: list[dict], filepath: str | None = None):
    """Save citation audit results to a text file."""
    if filepath is None:
        filepath = f'citation_audit_{TODAY}.txt'

    lines = [f"Citation Audit Report — {TODAY}", "=" * 60, ""]
    total_citations = 0
    total_failed = 0

    for audit in audits:
        label = audit.get('_label', 'unknown')
        lines.append(f"── {label} ──")
        lines.append(f"  Citations: {audit.get('total_citations', 0)}")
        lines.append(f"  Verified: {audit.get('verified_count', 0)}")
        lines.append(f"  Failed: {audit.get('failed_count', 0)}")
        lines.append(f"  Unsourced claims: {len(audit.get('unsourced_claims', []))}")
        lines.append(f"  Spot-check failures: {len(audit.get('spot_check_failures', []))}")
        lines.append(f"  Removal %: {audit.get('removal_pct', 0):.1f}%")
        lines.append(f"  Result: {'PASSED' if audit.get('passed') else 'FAILED'}")
        lines.append(f"  Archived: {audit.get('archived_count', 0)} URLs")
        total_citations += audit.get('total_citations', 0)
        total_failed += audit.get('failed_count', 0)

        if audit.get('failed_citations'):
            lines.append("  Failed citations:")
            for fc in audit['failed_citations']:
                lines.append(f"    URL: {fc.get('url', '')[:80]}")
                lines.append(f"    Reason: {fc.get('reason', '')}")
                lines.append(f"    Location: {fc.get('location', '')}")

        if audit.get('unsourced_claims'):
            lines.append("  Unsourced claims:")
            for claim in audit['unsourced_claims']:
                lines.append(f"    - {claim[:100]}")

        if audit.get('spot_check_failures'):
            lines.append("  Spot-check failures:")
            for sf in audit['spot_check_failures']:
                lines.append(f"    Claim: {sf.get('claim', '')[:100]}")
                lines.append(f"    Reason: {sf.get('reason', '')}")

        lines.append("")

    lines.append(f"TOTAL: {total_citations} citations, {total_failed} failed")
    lines.append("=" * 60)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  [Citation Audit] Log saved to {filepath}")
