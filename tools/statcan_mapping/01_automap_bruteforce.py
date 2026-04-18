"""Smart StatCan Daily → WDS vector mapper.

For each statcan_latest item, enumerate coordinate candidates and score by
(value match, reference period match, change match). Emits
config/statcan_daily_vector_map.json with verified/partial/unmapped buckets.
"""
import urllib.request, json, time, re, datetime, itertools, sys

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


MONTH = {'january': '01', 'february': '02', 'march': '03', 'april': '04',
         'may': '05', 'june': '06', 'july': '07', 'august': '08',
         'september': '09', 'october': '10', 'november': '11', 'december': '12'}
QUARTER = {'first quarter': '03', 'second quarter': '06',
           'third quarter': '09', 'fourth quarter': '12'}


def period_matches(vector_period, refper):
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
    for k, mm in MONTH.items():
        if k in rp:
            return vp == f'{year}-{mm}-01'
    for k, mm in QUARTER.items():
        if k in rp:
            return vp == f'{year}-{mm}-01'
    return False


def enum_coords(dims, max_per_dim=6):
    dim_members = []
    for d in dims:
        members = d.get('member') or []
        ids = [str(m.get('memberId', 1)) for m in members[:max_per_dim]]
        if not ids:
            ids = ['1']
        dim_members.append(ids)
    for combo in itertools.product(*dim_members):
        parts = list(combo) + ['0'] * (10 - len(combo))
        yield '.'.join(parts[:10])


def main():
    with open('docs/data/indicators.json', encoding='utf-8') as f:
        inds = json.load(f)
    items = inds.get('statcan_latest', {}).get('indicators', [])
    print(f'Items to map: {len(items)}')

    meta_cache = {}
    results = {}
    start_time = time.time()

    for idx, item in enumerate(items, 1):
        name = item.get('name', '?')
        tableUrl = item.get('tableUrl', '')
        m = re.search(r'pid=(\d{8})', tableUrl)
        if not m:
            results[name] = {'status': 'no_pid'}
            continue
        pid = int(m.group(1))
        snap_val = parse_value(item.get('value'))
        snap_chg = parse_value(item.get('change'))
        refper = item.get('refPer', '')

        if pid not in meta_cache:
            r = post('getCubeMetadata', [{'productId': pid}])
            if r and r[0].get('status') == 'SUCCESS':
                meta_cache[pid] = r[0]['object']
            else:
                meta_cache[pid] = None
            time.sleep(0.1)

        cube = meta_cache[pid]
        if not cube:
            results[name] = {'status': 'no_cube', 'pid': pid}
            continue

        dims = cube.get('dimension', [])
        total = 1
        for d in dims:
            total *= max(min(len(d.get('member', [])), 6), 1)
        max_per = 3 if total > 60 else 6

        best = None
        candidates_tried = 0
        for coord in enum_coords(dims, max_per_dim=max_per):
            if candidates_tried >= 50:
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

            score = (2 if val_ok else 0) + (3 if period_ok else 0) + (1 if chg_ok else 0)

            if best is None or score > best['score']:
                best = {'coord': coord, 'vectorId': vid, 'latest_val': latest_val,
                        'latest_per': latest_per, 'score': score,
                        'val_ok': val_ok, 'period_ok': period_ok, 'chg_ok': chg_ok}
                if val_ok and period_ok:
                    break
            time.sleep(0.08)

        if best and best['score'] >= 4:
            results[name] = {'status': 'verified', 'pid': pid, **best,
                             'snap_val': snap_val, 'snap_chg': snap_chg,
                             'refper': refper,
                             'candidates_tried': candidates_tried}
        elif best and best['score'] >= 2:
            results[name] = {'status': 'partial', 'pid': pid, **best,
                             'snap_val': snap_val, 'snap_chg': snap_chg,
                             'refper': refper,
                             'candidates_tried': candidates_tried}
        else:
            results[name] = {'status': 'unmapped', 'pid': pid,
                             'snap_val': snap_val, 'refper': refper,
                             'candidates_tried': candidates_tried}

        if idx % 5 == 0:
            elapsed = time.time() - start_time
            v = sum(1 for r in results.values() if r.get('status') == 'verified')
            p = sum(1 for r in results.values() if r.get('status') == 'partial')
            print(f'  [{idx:3}/{len(items)}] verified={v} partial={p} elapsed={elapsed:.0f}s', flush=True)

    elapsed = time.time() - start_time
    v = sum(1 for r in results.values() if r.get('status') == 'verified')
    p = sum(1 for r in results.values() if r.get('status') == 'partial')
    u = sum(1 for r in results.values() if r.get('status') == 'unmapped')
    nc = sum(1 for r in results.values() if r.get('status') == 'no_cube')
    print(f'\nFinal: verified={v}, partial={p}, unmapped={u}, no_cube={nc}, elapsed={elapsed:.0f}s')

    with open('config/statcan_daily_vector_map.json', 'w', encoding='utf-8') as f:
        json.dump({'generated': datetime.date.today().isoformat(),
                   'scoring': 'value+period+change match across up to 50 coord candidates per table',
                   'verified_count': v, 'partial_count': p,
                   'unmapped_count': u,
                   'mapping': results}, f, ensure_ascii=False, indent=2)
    print('Updated config/statcan_daily_vector_map.json')


if __name__ == '__main__':
    main()
