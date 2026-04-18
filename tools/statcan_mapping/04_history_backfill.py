"""Backfill history for verified StatCan Daily items.

Reads config/statcan_daily_vector_map.json, fetches 2 years of history from
StatCan WDS for every verified/partial vectorId, and injects into
docs/data/indicators.json history array with indicator_name matching the
frontend's id convention: 'sc_' + sanitized name.
"""
import urllib.request, json, time, re, datetime

WDS_URL = 'https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods'


def fetch_history(vector_ids, n=104):
    """Batch-fetch history for up to 300 vector IDs at once. Returns {vid: [obs]}."""
    body = [{'vectorId': v, 'latestN': n} for v in vector_ids]
    req = urllib.request.Request(WDS_URL, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    out = {}
    for item in data:
        if item.get('status') == 'SUCCESS':
            vid = item['object']['vectorId']
            out[vid] = item['object'].get('vectorDataPoint', [])
    return out


def sanitize_id(name):
    """Match app.js convention: 'sc_' + lowercase + non-alphanum to underscore, trim, 80-char cap."""
    s = name.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return 'sc_' + s[:80]


def main():
    with open('config/statcan_daily_vector_map.json', encoding='utf-8') as f:
        cfg = json.load(f)

    mapping = cfg.get('mapping', {})
    mappable = [(nm, m) for nm, m in mapping.items()
                if m.get('status') in ('verified', 'partial') and m.get('vectorId')]
    print(f'Mapping entries: {len(mapping)}, fetchable: {len(mappable)}')

    # Batch-fetch in groups of 200 vectors (StatCan WDS supports up to 300)
    all_vectors = [m['vectorId'] for _, m in mappable]
    history = {}
    BATCH = 150
    for i in range(0, len(all_vectors), BATCH):
        chunk = all_vectors[i:i+BATCH]
        print(f'  Fetching batch {i+1}-{i+len(chunk)}...')
        try:
            got = fetch_history(chunk, n=104)
            history.update(got)
        except Exception as e:
            print(f'  Batch failed: {e}')
        time.sleep(0.5)

    # Load existing indicators.json
    with open('docs/data/indicators.json', encoding='utf-8') as f:
        inds = json.load(f)
    hist_list = inds.get('history', [])
    existing = {(h.get('indicator_name'), h.get('period'), h.get('province'))
                for h in hist_list}

    # Cross-reference: for each mappable item, get the frontend id and write history rows
    added = 0
    sources = {}  # keyed by frontend_id → indicator_name mapping info
    today_iso = datetime.date.today().isoformat()
    for name, m in mappable:
        vid = m['vectorId']
        dps = history.get(vid, [])
        fid = sanitize_id(name)
        sources[fid] = {'original_name': name, 'vectorId': vid, 'productId': m.get('pid')}
        for dp in dps:
            period = dp.get('refPer')
            val = dp.get('value')
            if period is None or val is None:
                continue
            key = (fid, period, 'national')
            if key in existing:
                continue
            hist_list.append({
                'indicator_name': fid,
                'period': period,
                'value': val,
                'province': 'national',
                'unit': '',
                'source': f'StatCan WDS (v{vid})',
            })
            existing.add(key)
            added += 1

    inds['history'] = hist_list
    # Also record which statcan_latest items are now history-linked for transparency
    inds['statcan_history_sources'] = sources

    with open('docs/data/indicators.json', 'w', encoding='utf-8') as f:
        json.dump(inds, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\nAdded {added} history rows. {len(sources)} items are now history-linked.')
    print('docs/data/indicators.json updated.')


if __name__ == '__main__':
    main()
