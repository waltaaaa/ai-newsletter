#!/usr/bin/env python3
"""
Timeseries sync — ensures timeseries.json contains all indicator history
the frontend charts need.

Run after data collection (Phase 0) and before chart generation (Phase 4).
Also run standalone to fix stale timeseries.json.

Usage:
    python tools/sync_timeseries.py
    python tools/sync_timeseries.py --dry-run   # report only, don't write

Sources:
    1. indicators.json history[] — national + provincial economic indicators
    2. Existing timeseries.json — preserves commodity/market data already there

Key mapping:
    - National indicators synced under their indicator_name
    - Provincial indicators synced under {PROV_CODE}_{indicator_name}
    - Aliases added for frontend lookup variations
"""
import json
import sys
import os

TIMESERIES_PATH = 'docs/data/timeseries.json'
INDICATORS_PATH = 'docs/data/indicators.json'

# Frontend chart code looks up these keys — ensure they exist
REQUIRED_NATIONAL_KEYS = [
    'unemployment', 'cpi', 'realGdp', 'housingStarts',
    'overnight_rate', 'prime_rate', 'wti_oil',
    'employment_rate', 'participation_rate', 'wage_growth',
    'building_permits', 'trade_balance',
    'manufacturing_sales', 'retail_sales',
]

# Aliases: frontend might look up different names for the same data
ALIASES = {
    'unemployment': ['unemployment_rate'],
    'overnight_rate': ['boc_rate'],
    'wti_oil': ['wti_crude'],
    'cpi': ['cpi_national'],
    'realGdp': ['real_gdp', 'gdp'],
    'housingStarts': ['housing_starts'],
    'employment_rate': ['employmentRate'],
    'participation_rate': ['participationRate'],
    'wage_growth': ['wageGrowth'],
}

# Reverse lookup: indicator_name in DB → desired timeseries key
# When data is stored under camelCase but we need snake_case
REVERSE_MAP = {
    'participationRate': 'participation_rate',
    'wageGrowth': 'wage_growth',
    'employmentRate': 'employment_rate',
}

PROV_CODES = {
    'Ontario': 'ON', 'Quebec': 'QC', 'Alberta': 'AB',
    'British Columbia': 'BC', 'Saskatchewan': 'SK', 'Manitoba': 'MB',
    'Nova Scotia': 'NS', 'New Brunswick': 'NB',
    'Newfoundland and Labrador': 'NL', 'Prince Edward Island': 'PE',
    'Yukon': 'YT', 'Northwest Territories': 'NT', 'Nunavut': 'NU',
}

# Provincial indicators to sync (per-province chart data)
PROVINCIAL_INDICATORS = [
    'unemployment', 'cpi', 'employment_rate', 'participation_rate',
    'housingStarts', 'building_permits', 'gdp',
]

# Minimum data points required to sync (skip sparse indicators)
MIN_POINTS = 3


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def build_series(history, indicator_name, province_filter=None):
    """Extract timeseries from indicators.json history for a given indicator."""
    pts = []
    for h in history:
        if h.get('indicator_name') != indicator_name:
            continue
        prov = (h.get('province', '') or '').lower()
        if province_filter is not None:
            if prov != province_filter.lower():
                continue
        elif prov not in ('national', ''):
            continue

        period = h.get('period')
        value = h.get('value')
        if not period or value is None:
            continue
        try:
            val = float(value)
            pts.append({'date': period, 'value': val})
        except (ValueError, TypeError):
            continue

    pts.sort(key=lambda x: x['date'])
    return pts


def sync():
    dry_run = '--dry-run' in sys.argv

    ts = load_json(TIMESERIES_PATH)
    ind = load_json(INDICATORS_PATH)
    history = ind.get('history', [])

    if not history:
        print('[sync_timeseries] No history data in indicators.json')
        return

    added = []
    updated = []
    skipped = []

    # 1. Sync national indicators
    # Collect all unique national indicator names
    national_names = set()
    for h in history:
        prov = (h.get('province', '') or '').lower()
        if prov in ('national', ''):
            national_names.add(h.get('indicator_name', ''))
    national_names.discard('')

    for name in sorted(national_names):
        series = build_series(history, name)
        if len(series) < MIN_POINTS:
            skipped.append(f'{name} ({len(series)} pts)')
            continue

        # Determine the canonical key (apply reverse mapping if needed)
        canonical = REVERSE_MAP.get(name, name)

        existing = ts.get(canonical, [])
        if existing and len(existing) >= len(series):
            existing_latest = existing[-1].get('date', '') if existing else ''
            new_latest = series[-1].get('date', '') if series else ''
            if existing_latest >= new_latest:
                continue  # existing is already up to date

        ts[canonical] = series
        if canonical != name:
            ts[name] = series  # also write under original name
            added.append(f'{canonical}: {len(series)} pts (from {name})')
        elif existing:
            updated.append(f'{name}: {len(series)} pts (was {len(existing)})')
        else:
            added.append(f'{name}: {len(series)} pts')

        # Add aliases
        for alias in ALIASES.get(canonical, []):
            ts[alias] = series
            added.append(f'  alias {alias} -> {canonical}')

    # 2. Sync provincial indicators
    for prov_name, code in PROV_CODES.items():
        for ind_name in PROVINCIAL_INDICATORS:
            key = f'{code}_{ind_name}'
            series = build_series(history, ind_name, province_filter=prov_name)
            if len(series) < MIN_POINTS:
                continue

            existing = ts.get(key, [])
            if existing and len(existing) >= len(series):
                existing_latest = existing[-1].get('date', '') if existing else ''
                new_latest = series[-1].get('date', '') if series else ''
                if existing_latest >= new_latest:
                    continue

            ts[key] = series
            if existing:
                updated.append(f'{key}: {len(series)} pts')
            else:
                added.append(f'{key}: {len(series)} pts')

    # 3. Check for required keys still missing
    missing_required = []
    for key in REQUIRED_NATIONAL_KEYS:
        if key not in ts:
            missing_required.append(key)

    # Report
    print(f'\n[sync_timeseries] Results:')
    print(f'  Added: {len(added)} keys')
    print(f'  Updated: {len(updated)} keys')
    print(f'  Skipped (< {MIN_POINTS} pts): {len(skipped)}')
    print(f'  Total keys in timeseries.json: {len(ts)}')

    if added:
        print(f'\n  New keys:')
        for a in added[:30]:
            print(f'    + {a}')
        if len(added) > 30:
            print(f'    ... and {len(added)-30} more')

    if updated:
        print(f'\n  Updated keys:')
        for u in updated[:20]:
            print(f'    ~ {u}')

    if missing_required:
        print(f'\n  WARNING — required keys still missing:')
        for m in missing_required:
            print(f'    ! {m}')

    if dry_run:
        print('\n  [DRY RUN] No files written.')
        return

    # Write
    with open(TIMESERIES_PATH, 'w') as f:
        json.dump(ts, f, indent=2, ensure_ascii=False)
    print(f'\n  Written to {TIMESERIES_PATH}')


if __name__ == '__main__':
    sync()
