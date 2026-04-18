"""Second-pass automapper: semantic member matching.

For each item still unmapped after v1, read the cube metadata and, for every
dimension, select member(s) whose memberNameEn contains a keyword from the
snapshot name. Build coords from the cross-product of these semantic matches
(much smaller search space). Verify by value + relaxed period match.

Relaxed period: quarterly refPer accepts any month within the quarter.
"""
import urllib.request, json, time, re, datetime, itertools

WDS = 'https://www150.statcan.gc.ca/t1/wds/rest'


def post(endpoint, body):
    url = f'{WDS}/{endpoint}'
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:
        return [{'status': 'ERROR', 'error': str(e)}]


def parse_value(v):
    if v is None:
        return None
    s = re.sub(r'[^\d.\-]', '', str(v).strip())
    try:
        return float(s) if s else None
    except Exception:
        return None


MONTH = {'january': [1], 'february': [2], 'march': [3], 'april': [4],
         'may': [5], 'june': [6], 'july': [7], 'august': [8],
         'september': [9], 'october': [10], 'november': [11], 'december': [12]}
QUARTER = {'first quarter': [1, 2, 3], 'second quarter': [4, 5, 6],
           'third quarter': [7, 8, 9], 'fourth quarter': [10, 11, 12]}


def period_matches(vector_period, refper):
    """Accept any month within the quarter for quarterly refPer."""
    if not vector_period or not refper:
        return False
    vp = vector_period[:10]
    rp = refper.strip().lower()
    year_m = re.search(r'(20\d{2})', rp)
    if not year_m:
        return False
    year = year_m.group(1)
    if rp == year:
        return vp.startswith(year)
    for k, months in MONTH.items():
        if k in rp:
            return vp in [f'{year}-{m:02}-01' for m in months]
    for k, months in QUARTER.items():
        if k in rp:
            return vp in [f'{year}-{m:02}-01' for m in months]
    return False


STOPWORDS = {'the', 'and', 'or', 'of', 'in', 'by', 'for', 'to', 'a', 'an',
             'from', 'with', 'on', 'at', 'as', 'excluding', 'including',
             'seasonally', 'adjusted', 'unadjusted', 'data', 'canada',
             'canadian', 'total', 'all', 'index', 'percent', 'change',
             'rate', 'year', 'over', 'month', 'quarter', 'level', 'amount'}


def tokens(s):
    return {t for t in re.split(r'[^a-z]+', s.lower()) if t and t not in STOPWORDS and len(t) > 2}


def semantic_coords(dims, snap_tokens, max_per_dim=3):
    """For each dim, select members whose names share tokens with snapshot.
    Fall back to first-3 members if no semantic matches.
    """
    dim_matches = []
    for d in dims:
        members = d.get('member') or []
        scored = []
        for mem in members:
            name = mem.get('memberNameEn', '')
            mt = tokens(name)
            overlap = len(mt & snap_tokens)
            mid = mem.get('memberId')
            if mid is None:
                continue
            scored.append((overlap, mid, name))
        # Prefer semantic matches, then fall back to first-N
        scored.sort(key=lambda x: (-x[0], x[1]))
        picked = []
        # Include all with overlap > 0
        for overlap, mid, name in scored:
            if overlap > 0 and len(picked) < max_per_dim + 2:
                picked.append(str(mid))
        # If no semantic hits, take first 3 members as fallback
        if not picked:
            picked = [str(m.get('memberId', 1)) for m in members[:max_per_dim]]
        if not picked:
            picked = ['1']
        dim_matches.append(picked)

    for combo in itertools.product(*dim_matches):
        parts = list(combo) + ['0'] * (10 - len(combo))
        yield '.'.join(parts[:10])


def main():
    with open('config/statcan_daily_vector_map.json', encoding='utf-8') as f:
        cfg = json.load(f)

    mapping = cfg['mapping']
    # Re-attempt only items that are unmapped OR partial (keep verified as-is)
    to_retry = [(n, d) for n, d in mapping.items()
                if d.get('status') in ('unmapped', 'partial')]
    print(f'Re-attempting {len(to_retry)} items with semantic matching')

    with open('docs/data/indicators.json', encoding='utf-8') as f:
        inds = json.load(f)
    items_by_name = {i.get('name'): i for i in inds.get('statcan_latest', {}).get('indicators', [])}

    meta_cache = {}
    start_time = time.time()

    for idx, (name, old) in enumerate(to_retry, 1):
        pid = old.get('pid')
        if not pid:
            continue
        item = items_by_name.get(name, {})
        snap_val = parse_value(item.get('value'))
        snap_chg = parse_value(item.get('change'))
        refper = item.get('refPer', '')
        snap_tokens = tokens(name)

        if pid not in meta_cache:
            r = post('getCubeMetadata', [{'productId': pid}])
            meta_cache[pid] = r[0]['object'] if r and r[0].get('status') == 'SUCCESS' else None
            time.sleep(0.1)
        cube = meta_cache[pid]
        if not cube:
            continue

        dims = cube.get('dimension', [])
        best = None
        candidates_tried = 0
        for coord in semantic_coords(dims, snap_tokens, max_per_dim=4):
            if candidates_tried >= 80:
                break
            candidates_tried += 1
            r = post('getSeriesInfoFromCubePidCoord',
                     [{'productId': pid, 'coordinate': coord}])
            if not r or r[0].get('status') != 'SUCCESS':
                continue
            vid = r[0]['object'].get('vectorId')
            if not vid:
                continue
            r2 = post('getDataFromVectorsAndLatestNPeriods',
                      [{'vectorId': vid, 'latestN': 2}])
            if not r2 or r2[0].get('status') != 'SUCCESS':
                continue
            dps = r2[0]['object'].get('vectorDataPoint', [])
            if not dps:
                continue
            latest = dps[-1]
            latest_val = latest.get('value')
            latest_per = latest.get('refPer', '')
            if latest_val is None:
                continue

            period_ok = period_matches(latest_per, refper)
            val_ok = (snap_val is not None and
                      abs(latest_val - snap_val) / max(abs(snap_val), 1e-6) < 0.02)
            chg_ok = False
            if snap_chg is not None and len(dps) >= 2:
                prev = dps[-2].get('value')
                if prev is not None:
                    raw_chg = latest_val - prev
                    pct_chg = (raw_chg / prev * 100) if prev else 0
                    if abs(raw_chg - snap_chg) < 0.15 or abs(pct_chg - snap_chg) < 0.5:
                        chg_ok = True

            score = (3 if val_ok else 0) + (2 if period_ok else 0) + (1 if chg_ok else 0)

            if best is None or score > best['score']:
                best = {'coord': coord, 'vectorId': vid, 'latest_val': latest_val,
                        'latest_per': latest_per, 'score': score,
                        'val_ok': val_ok, 'period_ok': period_ok, 'chg_ok': chg_ok}
                if val_ok and period_ok:
                    break
            time.sleep(0.08)

        if best and best['score'] >= 5:
            mapping[name] = {'status': 'verified', 'pid': pid, **best,
                             'snap_val': snap_val, 'snap_chg': snap_chg,
                             'refper': refper,
                             'candidates_tried': candidates_tried,
                             'match_method': 'semantic'}
        elif best and best['score'] >= 3:
            mapping[name] = {'status': 'partial', 'pid': pid, **best,
                             'snap_val': snap_val, 'snap_chg': snap_chg,
                             'refper': refper,
                             'candidates_tried': candidates_tried,
                             'match_method': 'semantic'}
        elif best:
            # Only update if we improved score
            if best['score'] > old.get('score', 0):
                mapping[name] = {'status': 'unmapped', 'pid': pid, **best,
                                 'snap_val': snap_val, 'refper': refper,
                                 'candidates_tried': candidates_tried,
                                 'match_method': 'semantic_weak'}

        if idx % 5 == 0:
            v = sum(1 for m in mapping.values() if m.get('status') == 'verified')
            p = sum(1 for m in mapping.values() if m.get('status') == 'partial')
            print(f'  [{idx:3}/{len(to_retry)}] verified={v} partial={p} elapsed={time.time()-start_time:.0f}s', flush=True)

    v = sum(1 for m in mapping.values() if m.get('status') == 'verified')
    p = sum(1 for m in mapping.values() if m.get('status') == 'partial')
    u = sum(1 for m in mapping.values() if m.get('status') == 'unmapped')
    print(f'\nFinal after v2: verified={v}, partial={p}, unmapped={u}')

    cfg['mapping'] = mapping
    cfg['verified_count'] = v
    cfg['partial_count'] = p
    cfg['unmapped_count'] = u
    cfg['v2_semantic_applied'] = datetime.date.today().isoformat()
    with open('config/statcan_daily_vector_map.json', 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print('Updated config/statcan_daily_vector_map.json')


if __name__ == '__main__':
    main()
