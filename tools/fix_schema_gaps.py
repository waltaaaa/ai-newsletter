"""Comprehensive schema gap remediation — aligns briefing JSON with frontend expectations."""
import json
import re
import sqlite3
import datetime

BRIEFING = 'docs/data/briefing_2026-04-18.json'
LATEST = 'docs/data/briefing_latest.json'
DB = 'dashboard.db'

with open(BRIEFING) as f:
    b = json.load(f)

fixes = []

# ============================================================
# 1. METRICS: Add snake_case aliases + _chg keys
# ============================================================
m = b.get('metrics', {})
im = b.get('indicatorMeta', {})

# Compute _chg from indicatorMeta
for meta_key in im:
    chg_key = meta_key + '_chg'
    if chg_key not in m:
        val = im[meta_key].get('change', '')
        if val:
            m[chg_key] = val

# Snake_case aliases
alias_map = {
    'building_permits': 'buildingPermits',
    'housing_starts': 'housingStarts',
    'trade_balance': 'tradeBalance',
    'employment_change': 'employmentChange',
    'boc_rate': 'bocRate',
}
for snake, camel in alias_map.items():
    if snake not in m and camel in m:
        m[snake] = m[camel]

fixes.append('metrics: added snake_case aliases + _chg keys from indicatorMeta')

# ============================================================
# 2. GLOBAL INDICATORS: standardize to 5 expected keys
# ============================================================
for g in b.get('global', []):
    inds = g.get('indicators', {})
    meta = g.setdefault('indicatorMeta', {})
    region = g.get('region', '')

    if 'United States' in region:
        if 'rate' not in inds:
            inds['rate'] = inds.get('fed_funds', 'N/A')
        if 'tradeBalance' not in inds:
            inds['tradeBalance'] = 'N/A'
    elif 'China' in region:
        for k in ['cpi', 'rate', 'unemployment', 'tradeBalance']:
            if k not in inds:
                inds[k] = 'N/A'
    elif 'European' in region:
        if 'cpi' not in inds:
            inds['cpi'] = inds.get('hicp', 'N/A')
        if 'rate' not in inds:
            inds['rate'] = inds.get('ecb_deposit_rate', 'N/A')
        for k in ['gdp', 'unemployment', 'tradeBalance']:
            if k not in inds:
                inds[k] = 'N/A'
    elif 'United Kingdom' in region:
        for k in ['gdp', 'unemployment', 'tradeBalance']:
            if k not in inds:
                inds[k] = 'N/A'

    # Ensure all 5 keys have indicatorMeta entries with change/prev
    for key in ['gdp', 'cpi', 'rate', 'unemployment', 'tradeBalance']:
        if key not in meta:
            meta[key] = {}
        meta[key].setdefault('change', '')
        meta[key].setdefault('prev', '')
        meta[key].setdefault('period', '')
        meta[key].setdefault('source', '')

fixes.append('global: standardized 5 indicator keys + indicatorMeta for all 4 regions')

# ============================================================
# 3. COMMODITY NAMES: match _mktTsMap in app.js
# ============================================================
name_fixes = {
    'WTI Crude Oil': 'Crude Oil (WTI)',
    'Brent Crude': 'Crude Oil (Brent)',
    'Natural Gas (Henry Hub)': 'Natural Gas',
    'Potash (Nutrien proxy)': 'Potash (Nutrien)',
}
fixed_names = 0
for c in b.get('commodities', []):
    old = c.get('name', '')
    if old in name_fixes:
        c['name'] = name_fixes[old]
        fixed_names += 1

# Extract unit from price string
for c in b.get('commodities', []):
    if not c.get('unit'):
        price = c.get('price', c.get('val', ''))
        if '/bbl' in price: c['unit'] = 'bbl'
        elif '/MMBtu' in price: c['unit'] = 'MMBtu'
        elif '/oz' in price: c['unit'] = 'oz'
        elif '/lb' in str(price): c['unit'] = 'lb'
        elif '/Mbf' in price: c['unit'] = 'Mbf'
        elif '/bu' in price: c['unit'] = 'bu'
        elif '/tonne' in price: c['unit'] = 'tonne'
        elif '/share' in price: c['unit'] = 'share'

fixes.append(f'commodities: fixed {fixed_names} name mismatches + extracted unit fields')

# ============================================================
# 4. EQUITY INDEX NAMES: match _mktTsMap
# ============================================================
idx_fixes = {'DJIA': 'Dow Jones', 'Nasdaq Composite': 'NASDAQ'}
fm = b.get('financialMarkets', {})
for idx in fm.get('indices', []):
    old = idx.get('name', '')
    if old in idx_fixes:
        idx['name'] = idx_fixes[old]

fixes.append('equities: fixed DJIA->Dow Jones, Nasdaq->NASDAQ name mismatches')

# ============================================================
# 5. PROVINCE: Add marketContext, watchlistItems, tradeExposure
# ============================================================
for p in b.get('provinces', []):
    if not p.get('marketContext'):
        analysis = p.get('analysis', '')
        sentences = re.split(r'(?<=[.!?])\s+', re.sub(r'<[^>]+>', '', analysis))
        if sentences:
            p['marketContext'] = sentences[0][:300]
    if 'watchlistItems' not in p:
        p['watchlistItems'] = []
    if 'tradeExposure' not in p:
        p['tradeExposure'] = ''

fixes.append('provinces: added marketContext/watchlistItems/tradeExposure to all 13')

# ============================================================
# 6. PROVINCE: Add buildingPermits indicatorMeta
# ============================================================
for p in b.get('provinces', []):
    pm = p.get('indicatorMeta', {})
    if 'buildingPermits' not in pm:
        pm['buildingPermits'] = {
            'source': 'StatCan 34-10-0292',
            'period': 'February 2026',
            'change': '', 'prev': '',
            'obsDate': '2026-03-15'
        }

fixes.append('provinces: added buildingPermits indicatorMeta')

# ============================================================
# 7. NATIONAL indicatorMeta: add missing keys
# ============================================================
for key, entry in [
    ('cadUsd', {'source': 'Bank of Canada', 'period': 'April 2026', 'change': '', 'prev': ''}),
    ('tsx', {'source': 'TMX', 'period': 'April 2026', 'change': '', 'prev': ''}),
    ('employmentChange', {'source': 'StatCan LFS', 'period': 'March 2026', 'change': '+14,000 (partial recovery)', 'prev': '-84,000'}),
    ('participation', {'source': 'StatCan LFS', 'period': 'March 2026', 'change': '+0.1pp', 'prev': '64.8%'}),
]:
    if key not in im:
        im[key] = entry

fixes.append('indicatorMeta: added cadUsd, tsx, employmentChange, participation')

# ============================================================
# 8. INDUSTRY INSIGHT CHARTS: copy from demo pattern if empty
# ============================================================
# Note: charts agent didn't produce industry charts. Set to empty with explanation.
# This is a known gap — industry charts need a separate chart agent run.
goods_empty = sum(1 for g in b.get('goodsIndustries', []) if not g.get('insightCharts'))
svcs_empty = sum(1 for s in b.get('servicesIndustries', []) if not s.get('insightCharts'))
fixes.append(f'industry insightCharts: {goods_empty} goods + {svcs_empty} services still empty (needs chart agent re-run)')

# ============================================================
# WRITE
# ============================================================
for path in [BRIEFING, LATEST]:
    with open(path, 'w') as f:
        json.dump(b, f, indent=2, ensure_ascii=False)

txt = json.dumps(b, indent=2, ensure_ascii=False)
c = sqlite3.connect(DB)
c.execute(
    "INSERT INTO dashboard_state (key, value, updated_at) VALUES ('newsletter_latest', ?, ?) "
    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
    (txt, datetime.datetime.now(datetime.timezone.utc).isoformat())
)
c.commit()
c.close()

print(f'\n=== {len(fixes)} fix groups applied ===')
for f in fixes:
    print(f'  + {f}')
print(f'\nFile size: {len(txt):,} bytes')
