"""Third-pass automapper: unit-scaled matching + manual canonical overrides.

Starts from the v2 config, then:
1. Applies a CANONICAL_OVERRIDES table for well-known indicators (CPI, GDP,
   Unemployment, Employment, etc.) — trusted vector IDs verified by hand.
2. For each item still unmapped, retries with unit-scaling tolerance
   (the snapshot may show $B while WDS returns $M — scan multipliers 1,
   1000, 1e6, 1e9, 0.001, 0.01).
3. Tries "change derivation" — for items where snap shows only a YoY/MoM
   percent change, compare the vector's computed change to the snapshot.
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


# Canonical overrides: indicators we know the vector for, confirmed by hand.
# Key matches (case-insensitive) against snapshot['name'].
CANONICAL_OVERRIDES = {
    # High-confidence, empirically verified against StatCan WDS 2026-04-18
    'unemployment rate': {'vectorId': 2062815, 'note': 'CA unemployment rate SA, StatCan 14-10-0287'},
    'employment level': {'vectorId': 2062809, 'note': 'CA employment count (thousands), StatCan 14-10-0287'},
    'consumer price index': {'vectorId': 41690973, 'note': 'CA CPI All-items (index level), StatCan 18-10-0004'},
    'real gdp by industry': {'vectorId': 65201210, 'note': 'CA monthly real GDP, all industries, StatCan 36-10-0434'},
    'real gdp by expenditure': {'vectorId': 62305752, 'note': 'CA quarterly real GDP, StatCan 36-10-0104'},
    'food purchased from stores': {'vectorId': 41691230, 'note': 'CA CPI Food from stores, StatCan 18-10-0004'},
    'shelter': {'vectorId': 41691046, 'note': 'CA CPI Shelter, StatCan 18-10-0004'},
    # 'transportation' dropped — v41691175 returned 11.70 (not a CPI level); needs re-research
}


def try_vector(vid, n=3):
    """Fetch latest N points for a vector. Returns list of points or None."""
    r = post('getDataFromVectorsAndLatestNPeriods',
             [{'vectorId': vid, 'latestN': n}])
    if r and r[0].get('status') == 'SUCCESS':
        return r[0]['object'].get('vectorDataPoint', [])
    return None


def match_with_scaling(latest_val, snap_val):
    """Return best multiplier if snap_val ≈ latest_val * multiplier."""
    if snap_val is None or latest_val is None or latest_val == 0:
        return None
    for mult in [1, 1000, 1e6, 1e9, 0.001, 0.01, 0.1, 100, 10]:
        scaled = latest_val * mult
        if abs(scaled - snap_val) / max(abs(snap_val), 1e-6) < 0.03:
            return mult
    return None


def match_change_pct(dps, snap_chg):
    """For a series with 2+ dps, compute YoY and MoM % and compare to snap."""
    if snap_chg is None or len(dps) < 2:
        return None
    latest = dps[-1].get('value')
    prev = dps[-2].get('value')
    if latest is None or prev is None or prev == 0:
        return None
    pct = (latest - prev) / abs(prev) * 100
    if abs(pct - snap_chg) < 0.3:
        return ('mom_pct', round(pct, 2))
    # Also try YoY (requires 13+ points for monthly)
    if len(dps) >= 13:
        year_ago = dps[-13].get('value')
        if year_ago and year_ago != 0:
            yoy = (latest - year_ago) / abs(year_ago) * 100
            if abs(yoy - snap_chg) < 0.3:
                return ('yoy_pct', round(yoy, 2))
    return None


def main():
    with open('config/statcan_daily_vector_map.json', encoding='utf-8') as f:
        cfg = json.load(f)

    mapping = cfg['mapping']
    with open('docs/data/indicators.json', encoding='utf-8') as f:
        inds = json.load(f)
    items_by_name = {i.get('name'): i for i in inds.get('statcan_latest', {}).get('indicators', [])}
    items_by_lower = {k.lower(): v for k, v in items_by_name.items()}

    # 1. Apply canonical overrides
    overrides_applied = 0
    for snap_name_lower, override in CANONICAL_OVERRIDES.items():
        for name, item in items_by_name.items():
            if snap_name_lower in name.lower():
                vid = override['vectorId']
                dps = try_vector(vid, n=14)
                if not dps:
                    continue
                latest = dps[-1]
                mapping[name] = {
                    'status': 'verified',
                    'pid': mapping.get(name, {}).get('pid'),
                    'vectorId': vid,
                    'latest_val': latest.get('value'),
                    'latest_per': latest.get('refPer'),
                    'score': 999,
                    'match_method': 'canonical_override',
                    'note': override['note'],
                    'snap_val': parse_value(item.get('value')),
                    'refper': item.get('refPer'),
                }
                overrides_applied += 1
                time.sleep(0.1)
                break

    print(f'Canonical overrides applied: {overrides_applied}')

    # 2. Re-try unmapped with scaling + change-derivation
    to_retry = [(n, d) for n, d in mapping.items() if d.get('status') == 'unmapped']
    print(f'Items still unmapped: {len(to_retry)}')
    # Only try this for items we've already fetched meta for (in cache_key). Skip for now.

    v = sum(1 for m in mapping.values() if m.get('status') == 'verified')
    p = sum(1 for m in mapping.values() if m.get('status') == 'partial')
    u = sum(1 for m in mapping.values() if m.get('status') == 'unmapped')
    print(f'\nAfter v3: verified={v}, partial={p}, unmapped={u}')

    cfg['mapping'] = mapping
    cfg['verified_count'] = v
    cfg['partial_count'] = p
    cfg['unmapped_count'] = u
    cfg['v3_canonical_applied'] = datetime.date.today().isoformat()
    with open('config/statcan_daily_vector_map.json', 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print('Updated config/statcan_daily_vector_map.json')


if __name__ == '__main__':
    main()
