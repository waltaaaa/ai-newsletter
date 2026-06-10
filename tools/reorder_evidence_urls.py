# -*- coding: utf-8 -*-
"""Reorder each project's evidence array so evidence[0] is the most
project-specific deep link (the frontend's SOURCE column links evidence[0]).

Scoring favours URLs/titles that mention the project name and have real paths;
penalizes homepages, landing pages, search/aggregator URLs. No URLs are
removed — order only (evidence-merge invariant preserved).

Dry-run by default; --apply commits.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

DB = Path(__file__).resolve().parents[1] / "dashboard.db"

STOP = {'the', 'of', 'and', 'a', 'an', 'in', 'at', 'to', 'for', 'de', 'la', 'le',
        'du', 'des', 'project', 'facility', 'centre', 'center', 'plant',
        'development', 'new', 'construction', 'expansion', 'program', 'phase'}

GENERIC_PATHS = {'', '/', '/en', '/fr', '/news', '/en/news', '/fr/nouvelles',
                 '/search', '/projects', '/index.html', '/home', '/en/home'}

AGGREGATOR_RE = re.compile(
    r'google\.com/search|news\.google\.|bing\.com/search|/rss\b|feedproxy|'
    r'twitter\.com/?$|facebook\.com/?$', re.I)


def name_tokens(name):
    return set(w for w in re.findall(r'[a-z0-9]+', (name or '').lower())
               if w not in STOP and len(w) > 2)


def score(entry, ntoks):
    if not isinstance(entry, dict):
        return -10
    url = entry.get('url') or ''
    if not url.startswith('http'):
        return -10
    s = 0
    try:
        parsed = urlparse(url)
    except ValueError:
        return -10
    path = (parsed.path or '').rstrip('/').lower() or '/'

    if path in GENERIC_PATHS:
        s -= 4
    if AGGREGATOR_RE.search(url):
        s -= 4
    depth = len([seg for seg in path.split('/') if seg])
    if depth >= 2:
        s += 1

    blob_url = url.lower()
    hits_url = sum(1 for t in ntoks if t in blob_url)
    s += min(hits_url * 2, 4)

    title = ((entry.get('title') or '') + ' ' + (entry.get('name') or '')).lower()
    hits_title = sum(1 for t in ntoks if t in title)
    if hits_title >= 2:
        s += 2
    elif hits_title == 1:
        s += 1

    snippet = (entry.get('snippet') or '').lower()
    if ntoks and sum(1 for t in ntoks if t in snippet) >= 2:
        s += 1
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    reordered = 0
    weak = []      # best evidence still scores <= 0 (no project-specific URL)
    polluted = 0   # suspiciously large evidence arrays (batch dumps)
    updates = []

    rows = cur.execute("SELECT rowid, name, evidence, quality_tier FROM projects").fetchall()
    for r in rows:
        try:
            ev = json.loads(r['evidence'] or '[]')
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, list) or len(ev) == 0:
            continue
        if len(ev) > 20:
            polluted += 1
        ntoks = name_tokens(r['name'])
        scored = [(score(e, ntoks), i, e) for i, e in enumerate(ev)]
        ordered = [e for _, _, e in sorted(scored, key=lambda x: (-x[0], x[1]))]
        best = max(s for s, _, _ in scored)
        if best <= 0 and r['quality_tier'] == 'featured':
            weak.append((r['rowid'], r['name'][:60],
                         (ev[0].get('url') if isinstance(ev[0], dict) else '')[:80]))
        if ordered[0] is not ev[0]:
            reordered += 1
            updates.append((json.dumps(ordered, ensure_ascii=False), r['rowid']))

    print(f"rows scanned          : {len(rows)}")
    print(f"evidence[0] improved  : {reordered}")
    print(f"polluted (>20 urls)   : {polluted}")
    print(f"featured rows w/o any project-specific URL: {len(weak)}")
    for rowid, n, u in weak[:20]:
        print(f"   weak {rowid} {n} | {u}")

    if args.apply:
        cur.executemany("UPDATE projects SET evidence=? WHERE rowid=?", updates)
        con.commit()
        print(f"\nAPPLIED: {len(updates)} rows updated")
    else:
        print("\nDRY RUN — re-run with --apply")


if __name__ == '__main__':
    main()
