"""
backfill_indicator_history.py — Backfill 5 years of indicator data to indicator_history collection.

Sources (all free APIs):
  - Bank of Canada Valet API: overnight rate, GoC yields
  - Statistics Canada WDS: CPI, unemployment (national + provincial)
  - Yahoo Finance: commodities (WTI, gold, lumber, TSX, etc.)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import time
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
load_dotenv()

import requests
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa:
        cred = credentials.Certificate(json.loads(sa))
    else:
        cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()


def backfill_boc(years=5):
    """Backfill Bank of Canada series: overnight rate, GoC yields."""
    print("\n[BOC] Backfilling Bank of Canada indicators...")

    series = {
        'overnight_rate': 'V39079',
        'goc_2y_yield': 'BD.CDN.2YR.DQ.YLD',
        'goc_5y_yield': 'BD.CDN.5YR.DQ.YLD',
        'goc_10y_yield': 'BD.CDN.10YR.DQ.YLD',
        'prime_rate': 'V80691335',
    }

    start_date = (date.today() - timedelta(days=years * 365)).isoformat()
    total = 0

    for indicator_name, series_id in series.items():
        try:
            url = f"https://www.bankofcanada.ca/valet/observations/{series_id}/json?start_date={start_date}"
            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"  [BOC] {indicator_name}: HTTP {resp.status_code}")
                continue

            data = resp.json()
            observations = data.get('observations', [])
            print(f"  [BOC] {indicator_name}: {len(observations)} observations")

            batch = db.batch()
            count = 0
            for obs in observations:
                obs_date = obs.get('d', '')
                val = obs.get(series_id, {})
                if isinstance(val, dict):
                    val = val.get('v', '')
                if not obs_date or not val or val == '':
                    continue

                doc_id = f"{obs_date}_{indicator_name}_national"
                ref = db.collection('indicator_history').document(doc_id)
                batch.set(ref, {
                    'indicator': indicator_name,
                    'province': 'national',
                    'date': obs_date,
                    'value': str(val),
                    'unit': '%',
                    'source': 'Bank of Canada Valet',
                    'frequency': 'daily' if 'yield' in indicator_name else 'scheduled',
                    'backfilled': True,
                })
                count += 1

                if count % 490 == 0:
                    batch.commit()
                    batch = db.batch()

            if count % 490 != 0:
                batch.commit()
            total += count
            time.sleep(1)

        except Exception as e:
            print(f"  [BOC] {indicator_name} error: {e}")

    print(f"  [BOC] Total: {total} observations written")
    return total


def backfill_statcan(years=5):
    """Backfill Statistics Canada: CPI and unemployment via WDS API."""
    print("\n[STATCAN] Backfilling StatCan indicators...")

    vectors = {
        'cpi_national': '41690973',
        'unemployment_national': '2062815',
        # Provincial unemployment
        'unemployment_NL': '2063004',
        'unemployment_PEI': '2063193',
        'unemployment_NS': '2063382',
        'unemployment_NB': '2063571',
        'unemployment_QC': '2063760',
        'unemployment_ON': '2063949',
        'unemployment_MB': '2064138',
        'unemployment_SK': '2064327',
        'unemployment_AB': '2064516',
        'unemployment_BC': '2064705',
    }

    total = 0
    wds_url = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"

    for indicator_name, vector_id in vectors.items():
        try:
            payload = [{"vectorId": int(vector_id), "latestN": years * 12 + 6}]
            resp = requests.post(
                wds_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if resp.status_code != 200:
                print(f"  [STATCAN] {indicator_name}: HTTP {resp.status_code}")
                continue

            data = resp.json()
            # WDS returns [{"status": "SUCCESS", "object": {"vectorDataPoint": [...]}}]
            obs_list = []
            if isinstance(data, list):
                for series in data:
                    obj = series.get('object', {})
                    for dp in obj.get('vectorDataPoint', []):
                        obs_list.append({
                            'date': dp.get('refPer', ''),
                            'value': dp.get('value', ''),
                        })
            elif isinstance(data, dict):
                for dp in data.get('object', {}).get('vectorDataPoint', []):
                    obs_list.append({
                        'date': dp.get('refPer', ''),
                        'value': dp.get('value', ''),
                    })

            # Determine province from indicator name
            parts = indicator_name.split('_')
            if len(parts) >= 2 and parts[-1] in ('NL', 'PEI', 'NS', 'NB', 'QC', 'ON', 'MB', 'SK', 'AB', 'BC'):
                province = parts[-1]
                base_indicator = '_'.join(parts[:-1])
            else:
                province = 'national'
                base_indicator = indicator_name

            print(f"  [STATCAN] {indicator_name}: {len(obs_list)} observations")

            batch = db.batch()
            count = 0
            for obs in obs_list:
                obs_date = obs['date'][:10] if obs['date'] else ''
                val = obs['value']
                if not obs_date or val == '' or val is None:
                    continue

                doc_id = f"{obs_date}_{base_indicator}_{province}"
                ref = db.collection('indicator_history').document(doc_id)
                batch.set(ref, {
                    'indicator': base_indicator,
                    'province': province,
                    'date': obs_date,
                    'value': str(val),
                    'unit': '%',
                    'source': 'Statistics Canada WDS',
                    'frequency': 'monthly',
                    'backfilled': True,
                })
                count += 1

                if count % 490 == 0:
                    batch.commit()
                    batch = db.batch()

            if count % 490 != 0:
                batch.commit()
            total += count
            time.sleep(0.5)

        except Exception as e:
            print(f"  [STATCAN] {indicator_name} error: {e}")

    print(f"  [STATCAN] Total: {total} observations written")
    return total


def backfill_yahoo(years=5):
    """Backfill Yahoo Finance commodities: oil, gold, lumber, TSX, CAD."""
    print("\n[YAHOO] Backfilling Yahoo Finance commodities...")

    try:
        import yfinance as yf
    except ImportError:
        print("  [YAHOO] yfinance not installed, skipping")
        return 0

    tickers = {
        'wti_oil': 'CL=F',
        'gold': 'GC=F',
        'lumber': 'LBS=F',
        'tsx_composite': '^GSPTSE',
        'cad_usd': 'CADUSD=X',
        'natural_gas': 'NG=F',
        'copper': 'HG=F',
    }

    total = 0
    for indicator_name, ticker in tickers.items():
        try:
            data = yf.download(ticker, period=f"{years}y", progress=False)
            if data is None or len(data) == 0:
                print(f"  [YAHOO] {indicator_name}: no data")
                continue

            # Sample weekly (every 5th trading day) to reduce document count
            sampled = data.iloc[::5]
            print(f"  [YAHOO] {indicator_name}: {len(sampled)} weekly samples from {len(data)} daily")

            batch = db.batch()
            count = 0
            for idx, row in sampled.iterrows():
                obs_date = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
                try:
                    val = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
                except (TypeError, ValueError, IndexError):
                    continue

                doc_id = f"{obs_date}_{indicator_name}_global"
                ref = db.collection('indicator_history').document(doc_id)
                batch.set(ref, {
                    'indicator': indicator_name,
                    'province': 'global',
                    'date': obs_date,
                    'value': str(round(val, 2)),
                    'unit': 'USD' if indicator_name != 'tsx_composite' else 'CAD',
                    'source': 'Yahoo Finance',
                    'frequency': 'weekly',
                    'backfilled': True,
                })
                count += 1

                if count % 490 == 0:
                    batch.commit()
                    batch = db.batch()

            if count % 490 != 0:
                batch.commit()
            total += count
            time.sleep(1)

        except Exception as e:
            print(f"  [YAHOO] {indicator_name} error: {e}")

    print(f"  [YAHOO] Total: {total} observations written")
    return total


if __name__ == "__main__":
    print("=" * 60)
    print("INDICATOR HISTORY BACKFILL — 5 years")
    print("=" * 60)

    boc_count = backfill_boc(years=5)
    statcan_count = backfill_statcan(years=5)
    yahoo_count = backfill_yahoo(years=5)

    print(f"\n{'=' * 60}")
    print(f"BACKFILL COMPLETE")
    print(f"  BoC:     {boc_count} observations")
    print(f"  StatCan: {statcan_count} observations")
    print(f"  Yahoo:   {yahoo_count} observations")
    print(f"  TOTAL:   {boc_count + statcan_count + yahoo_count} observations")
    print(f"{'=' * 60}")
