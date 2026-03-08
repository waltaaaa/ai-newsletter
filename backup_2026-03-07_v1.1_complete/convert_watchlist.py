"""
convert_watchlist.py — Convert canada_tracker_master_watchlist.csv to watchlist.json.

The CSV is the master for manual edits; watchlist.json is the machine-readable
derivative loaded by the pipeline at runtime.

Usage:
    python convert_watchlist.py
    python convert_watchlist.py --cross-reference   # Also cross-ref with rss_feeds.json
"""

import csv
import json
import os
import re
import sys

CSV_PATH  = os.path.join(os.path.dirname(__file__), 'canada_tracker_master_watchlist.csv')
JSON_PATH = os.path.join(os.path.dirname(__file__), 'watchlist.json')
RSS_PATH  = os.path.join(os.path.dirname(__file__), 'rss_feeds.json')


def _clean(val) -> str:
    """Strip whitespace from a CSV field. Handle non-string values."""
    if val is None:
        return ''
    if isinstance(val, list):
        return ', '.join(str(v) for v in val).strip()
    return str(val).strip()


def _extract_ticker(office_or_role: str) -> str:
    """Extract ticker from office_or_role like 'TSX:TECK.B' or 'Private'."""
    s = _clean(office_or_role)
    m = re.search(r'(TSX:[A-Z0-9.]+)', s, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    if 'private' in s.lower() or 'crown' in s.lower():
        return s
    return s


def convert():
    """Read the CSV and produce watchlist.json."""
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found.")
        sys.exit(1)

    # Read all rows
    rows = []
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: _clean(v) for k, v in row.items()})

    # Group by sheet
    by_sheet: dict[str, list[dict]] = {}
    for row in rows:
        sheet = row.get('sheet', '')
        if not sheet:
            continue
        by_sheet.setdefault(sheet, []).append(row)

    # ── Build output ──────────────────────────────────────────────────────
    output = {}

    # 1. Provincial Sources
    output['provincial_sources'] = []
    for r in by_sheet.get('Provincial_Sources', []):
        output['provincial_sources'].append({
            'jurisdiction': r.get('jurisdiction', ''),
            'entity_name':  r.get('entity_name', ''),
            'role':         r.get('office_or_role', ''),
            'current_holder': r.get('current_holder', ''),
            'source_url':   r.get('source_url', ''),
            'rss_url':      r.get('rss_url', ''),
            'priority':     r.get('priority', ''),
            'notes':        r.get('notes', ''),
        })

    # 2. CMA Watchlist
    output['cma_list'] = []
    for r in by_sheet.get('CMA_Watchlist', []):
        output['cma_list'].append({
            'jurisdiction': r.get('jurisdiction', ''),
            'cma_name':     r.get('entity_name', ''),
            'priority':     r.get('priority', ''),
        })

    # 3. Industry Sources
    output['industry_sources'] = []
    for r in by_sheet.get('Industry_Sources', []):
        output['industry_sources'].append({
            'industry':     r.get('industry_or_topic', ''),
            'entity_name':  r.get('entity_name', ''),
            'role':         r.get('office_or_role', ''),
            'source_url':   r.get('source_url', ''),
            'rss_url':      r.get('rss_url', ''),
            'naics':        r.get('sub_jurisdiction', ''),
            'priority':     r.get('priority', ''),
        })

    # 4. Public Figures Canada
    output['public_figures_canada'] = []
    for r in by_sheet.get('Public_Figures_Canada', []):
        output['public_figures_canada'].append({
            'name':           r.get('current_holder', '') or r.get('entity_name', ''),
            'role':           r.get('office_or_role', ''),
            'entity_name':    r.get('entity_name', ''),
            'current_holder': r.get('current_holder', ''),
            'priority':       r.get('priority', ''),
            'jurisdiction':   r.get('jurisdiction', ''),
            'why_it_matters': r.get('why_it_matters', ''),
        })

    # 5. Global Watchlist
    output['global_watchlist'] = []
    for r in by_sheet.get('Global_Watchlist', []):
        output['global_watchlist'].append({
            'jurisdiction':   r.get('jurisdiction', ''),
            'entity_name':    r.get('entity_name', ''),
            'role':           r.get('office_or_role', ''),
            'current_holder': r.get('current_holder', ''),
            'entity_type':    r.get('entity_type', ''),
            'priority':       r.get('priority', ''),
            'why_it_matters': r.get('why_it_matters', ''),
        })

    # 6. Provincial Officials
    output['provincial_officials'] = []
    for r in by_sheet.get('Provincial_Dept_Officials', []):
        output['provincial_officials'].append({
            'jurisdiction':   r.get('jurisdiction', ''),
            'entity_type':    r.get('entity_type', ''),
            'entity_name':    r.get('entity_name', ''),
            'role':           r.get('office_or_role', ''),
            'current_holder': r.get('current_holder', ''),
            'source_url':     r.get('source_url', ''),
            'priority':       r.get('priority', ''),
        })

    # 7. Provincial Companies
    output['provincial_companies'] = []
    for r in by_sheet.get('Provincial_Companies', []):
        output['provincial_companies'].append({
            'jurisdiction': r.get('jurisdiction', ''),
            'industry':     r.get('industry_or_topic', ''),
            'company_name': r.get('entity_name', ''),
            'ticker':       _extract_ticker(r.get('office_or_role', '')),
            'priority':     r.get('priority', ''),
        })

    # 8. Industry Companies
    output['industry_companies'] = []
    for r in by_sheet.get('Industry_Companies', []):
        output['industry_companies'].append({
            'industry':     r.get('industry_or_topic', ''),
            'company_name': r.get('entity_name', ''),
            'ticker':       _extract_ticker(r.get('office_or_role', '')),
            'priority':     r.get('priority', ''),
        })

    # ── Write JSON ────────────────────────────────────────────────────────
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"Converted {CSV_PATH} -> {JSON_PATH}")
    for key, val in output.items():
        print(f"  {key}: {len(val)} entries")
    total = sum(len(v) for v in output.values())
    print(f"  TOTAL: {total} entries")

    return output


def cross_reference():
    """
    Cross-reference watchlist.json with rss_feeds.json.
    Add any watchlist RSS URLs not already in rss_feeds.json.
    """
    if not os.path.exists(JSON_PATH):
        print("Run convert first (no watchlist.json found).")
        return
    if not os.path.exists(RSS_PATH):
        print(f"No rss_feeds.json found at {RSS_PATH}.")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        watchlist = json.load(f)
    with open(RSS_PATH, 'r', encoding='utf-8') as f:
        rss_config = json.load(f)

    # Collect all existing RSS URLs from rss_feeds.json
    existing_urls = set()
    for section in ('federal', 'provincial', 'municipal'):
        for feed in rss_config.get(section, []):
            url = feed.get('url', '').strip().rstrip('/')
            if url:
                existing_urls.add(url.lower())

    # Check watchlist for RSS URLs not in rss_feeds.json
    new_feeds = []
    sources_to_check = (
        watchlist.get('provincial_sources', []) +
        watchlist.get('industry_sources', [])
    )

    for entry in sources_to_check:
        rss_url = (entry.get('rss_url') or '').strip().rstrip('/')
        if rss_url and rss_url.lower() not in existing_urls:
            new_feeds.append({
                'entity': entry.get('entity_name', ''),
                'rss_url': rss_url,
                'source': 'watchlist',
            })

    if new_feeds:
        print(f"\n[Cross-ref] Found {len(new_feeds)} RSS URLs in watchlist not in rss_feeds.json:")
        for nf in new_feeds:
            print(f"  {nf['entity']}: {nf['rss_url']}")
        print("  (Add these to rss_feeds.json manually or via --test-feeds auto-discovery)")
    else:
        print("\n[Cross-ref] All watchlist RSS URLs already in rss_feeds.json.")

    # Also check for canada.ca departments that might have .atom.xml feeds
    canada_ca_pattern = re.compile(r'https?://(www\.)?canada\.ca/en/([^/]+)', re.IGNORECASE)
    potential_feeds = []
    for entry in watchlist.get('industry_sources', []):
        source_url = (entry.get('source_url') or '').strip()
        m = canada_ca_pattern.match(source_url)
        if m:
            dept_slug = m.group(2)
            atom_url = f'https://www.canada.ca/en/{dept_slug}.atom.xml'
            if atom_url.lower() not in existing_urls:
                potential_feeds.append({
                    'entity': entry.get('entity_name', ''),
                    'atom_url': atom_url,
                })

    if potential_feeds:
        print(f"\n[Cross-ref] {len(potential_feeds)} potential canada.ca .atom.xml feeds to verify:")
        for pf in potential_feeds:
            print(f"  {pf['entity']}: {pf['atom_url']}")
    else:
        print("[Cross-ref] No additional canada.ca atom feeds discovered.")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Convert watchlist CSV to JSON')
    parser.add_argument('--cross-reference', action='store_true',
                        help='Cross-reference with rss_feeds.json')
    args = parser.parse_args()

    output = convert()

    if args.cross_reference:
        cross_reference()
