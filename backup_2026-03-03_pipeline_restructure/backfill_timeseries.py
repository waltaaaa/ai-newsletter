"""
backfill_timeseries.py — Populate /timeseries from historical /newsletters docs.

Reads every dated /newsletters/{YYYY-MM-DD} document and extracts the same
variables that append_to_timeseries() writes on each pipeline run. Skips dates
already present in each timeseries document to make it safe to re-run.

Usage:
    python backfill_timeseries.py
"""

import re
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

ts_ref = db.collection('timeseries')

# ── Variable definitions (mirrors append_to_timeseries) ──────────────────────
VARS = {
    'boc_rate':           ('BoC Policy Rate',    '%',   'National'),
    'canada_cpi':         ('Canada CPI (YoY)',   '%',   'National'),
    'canada_unemployment':('Canada Unemployment', '%',  'National'),
    'cadusd':             ('CAD/USD Rate',        'USD', 'Foreign Exchange'),
    'tsx_composite':      ('TSX Composite',       'pts', 'Equity Indices'),
}

YIELD_LABELS = {
    '1m': '1M', '2m': '2M', '3m': '3M', '6m': '6M',
    '1y': '1Y', '2y': '2Y', '3y': '3Y', '5y': '5Y',
    '7y': '7Y', '10y': '10Y', '20y': '20Y', '30y': '30Y',
    'long': 'Long',
}


def to_float(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).replace('%', '').replace('$', '').replace(',', '').replace('+', '').strip())
    except Exception:
        return None


def extract_points(doc_id: str, data: dict) -> dict[str, float]:
    """Return {var_id: float_value} for one dated newsletter document."""
    points = {}

    m = data.get('metrics', {})

    # BoC rate
    v = to_float(m.get('bocRate') or data.get('bocRate'))
    if v is not None:
        points['boc_rate'] = v

    # CPI
    v = to_float(m.get('cpi'))
    if v is not None:
        points['canada_cpi'] = v

    # Unemployment
    v = to_float(m.get('unemployment'))
    if v is not None:
        points['canada_unemployment'] = v

    # CAD/USD from financialMarkets.fx
    for fx in data.get('financialMarkets', {}).get('fx', []):
        name = fx.get('name', '')
        if 'CAD' in name and 'USD' in name:
            v = to_float(fx.get('value', '').replace(',', ''))
            if v is not None:
                points['cadusd'] = v
            break

    # TSX from financialMarkets.indices
    for idx in data.get('financialMarkets', {}).get('indices', []):
        if 'TSX' in idx.get('name', ''):
            v = to_float(idx.get('value', '').replace(',', ''))
            if v is not None:
                points['tsx_composite'] = v
            break

    # Yield curve terms
    for yc in data.get('yieldCurve', []):
        term = yc.get('term', '').strip()
        if not term:
            continue
        var_id = f"yield_{term.lower()}"
        v = to_float(yc.get('yield', ''))
        if v is not None:
            points[var_id] = v

    return points


def backfill():
    # ── Load all dated newsletter docs ───────────────────────────────────────
    print("Loading historical newsletter documents...")
    dated_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    newsletter_ref = db.collection('newsletters')
    all_docs = newsletter_ref.stream()

    dated = []
    for snap in all_docs:
        if dated_re.match(snap.id):
            dated.append((snap.id, snap.to_dict()))

    dated.sort(key=lambda x: x[0])
    first = dated[0][0] if dated else 'none'
    last  = dated[-1][0] if dated else 'none'
    print(f"  Found {len(dated)} dated documents: {first} to {last}")

    if not dated:
        print("No dated documents found. Run the pipeline first.")
        return

    # ── Load existing timeseries docs to find already-present dates ──────────
    print("\nLoading existing timeseries documents...")
    existing: dict[str, set] = {}   # var_id -> set of date strings already stored
    ts_meta: dict[str, dict] = {}   # var_id -> {label, unit, category}

    for snap in ts_ref.stream():
        existing[snap.id] = {p['date'] for p in snap.to_dict().get('series', [])}
        d = snap.to_dict()
        ts_meta[snap.id] = {'label': d.get('label',''), 'unit': d.get('unit',''), 'category': d.get('category','')}

    print(f"  Found {len(existing)} existing timeseries variables.")

    # ── Process each dated doc ────────────────────────────────────────────────
    added_total = 0
    skipped_total = 0

    for doc_id, data in dated:
        points = extract_points(doc_id, data)
        if not points:
            print(f"  [{doc_id}] No extractable values — skipping.")
            continue

        for var_id, val in points.items():
            if var_id in existing and doc_id in existing[var_id]:
                skipped_total += 1
                continue

            point = {'date': doc_id, 'value': val}
            doc_ref = ts_ref.document(var_id)

            if var_id in existing:
                doc_ref.update({'series': firestore.ArrayUnion([point])})
                existing[var_id].add(doc_id)
            else:
                # Determine label/unit/category
                if var_id in VARS:
                    label, unit, category = VARS[var_id]
                elif var_id.startswith('yield_'):
                    term_key = var_id[6:]
                    term_label = YIELD_LABELS.get(term_key, term_key.upper())
                    label    = f'GoC {term_label} Yield'
                    unit     = '%'
                    category = 'Yield Curve'
                else:
                    label, unit, category = var_id, '', 'Other'

                doc_ref.set({'label': label, 'unit': unit, 'category': category, 'series': [point]})
                existing[var_id] = {doc_id}
                ts_meta[var_id] = {'label': label, 'unit': unit, 'category': category}

            added_total += 1

        n_added = sum(1 for v in points if v not in existing or doc_id not in existing.get(v, set()))
        print(f"  [{doc_id}] {len(points)} variables, {n_added} added")

    print(f"\nBackfill complete.")
    print(f"  Dated docs processed: {len(dated)}")
    print(f"  Data points added:    {added_total}")
    print(f"  Already present:      {skipped_total}")
    print(f"  Timeseries variables: {len(existing)}")
    print(f"\nVariables now in timeseries:")
    for var_id in sorted(existing):
        print(f"    {var_id}: {len(existing[var_id])} points")


if __name__ == '__main__':
    backfill()
