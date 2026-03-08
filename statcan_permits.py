"""
statcan_permits.py — Statistics Canada building permit signal detection.

Uses StatCan WDS API to pull Table 34-10-0066-01 (building permits by CMA).
Detects anomalies: municipalities with permit values significantly above
their historical average, signalling major project activity.

Produces investigation queries (not projects) that feed into Pro follow-up queue.
"""

import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

_STATCAN_WDS_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"

# Table 34-10-0066-01: Building permits, by type of structure and type of work
# These are total residential + non-residential permit values for major CMAs.
# Vector IDs for "Total value of permits" by CMA (seasonally adjusted).
_PERMIT_VECTORS = {
    # CMA: (vector_id, province)
    "Toronto":       (77987, "Ontario"),
    "Montreal":      (77971, "Quebec"),
    "Vancouver":     (78009, "British Columbia"),
    "Calgary":       (77951, "Alberta"),
    "Edmonton":      (77953, "Alberta"),
    "Ottawa":        (77979, "Ontario"),
    "Winnipeg":      (77967, "Manitoba"),
    "Quebec City":   (77973, "Quebec"),
    "Hamilton":      (77981, "Ontario"),
    "Kitchener":     (77985, "Ontario"),
    "London":        (77983, "Ontario"),
    "Halifax":       (77957, "Nova Scotia"),
    "Victoria":      (78007, "British Columbia"),
    "Windsor":       (77993, "Ontario"),
    "Saskatoon":     (77947, "Saskatchewan"),
    "Regina":        (77945, "Saskatchewan"),
    "St. John's":    (77939, "Newfoundland and Labrador"),
    "Kelowna":       (78005, "British Columbia"),
    "Abbotsford":    (78003, "British Columbia"),
    "Barrie":        (77997, "Ontario"),
}

# Flag if current month > Nx the 12-month moving average
ANOMALY_MULTIPLIER = 3.0


def _fetch_wds(vector_ids: list, n: int = 14) -> dict:
    """Fetch last N observations for StatCan WDS vector IDs."""
    payload = [{"vectorId": vid, "latestN": n} for vid in vector_ids]
    try:
        resp = requests.post(
            _STATCAN_WDS_URL, json=payload, timeout=25,
            headers={'Content-Type': 'application/json',
                     'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)'}
        )
        resp.raise_for_status()
        result = {}
        for item in resp.json():
            if item.get('status') != 'SUCCESS':
                continue
            obj = item.get('object', {})
            vid = obj.get('vectorId')
            points = sorted(
                [{'refPer': p.get('refPer', ''), 'value': p.get('value')}
                 for p in obj.get('vectorDataPoint', [])
                 if p.get('value') is not None],
                key=lambda x: x['refPer']
            )
            result[vid] = points
        return result
    except Exception as e:
        logger.warning(f"StatCan WDS fetch failed: {e}")
        return {}


def detect_permit_anomalies(db=None) -> list[dict]:
    """Detect building permit anomalies from StatCan Table 34-10-0066-01.

    Returns list of investigation query dicts for municipalities with
    permit values significantly above their 12-month average.

    Each dict has: query, province, sector, source, municipality, ratio
    """
    vector_ids = [vid for vid, _ in _PERMIT_VECTORS.values()]
    vid_to_cma = {vid: cma for cma, (vid, _) in _PERMIT_VECTORS.items()}
    vid_to_prov = {vid: prov for _, (vid, prov) in _PERMIT_VECTORS.items()}

    print("  [PERMITS] Fetching StatCan building permit data...")
    data = _fetch_wds(vector_ids, n=14)
    if not data:
        print("  [PERMITS] No data returned from StatCan WDS")
        return []

    anomalies = []
    for vid, points in data.items():
        if len(points) < 13:
            continue

        cma = vid_to_cma.get(vid, "Unknown")
        province = vid_to_prov.get(vid, "")

        # Latest observation
        latest = points[-1]
        latest_val = latest.get('value', 0)
        latest_period = latest.get('refPer', '')

        if not latest_val or latest_val <= 0:
            continue

        # 12-month moving average (excluding latest)
        historical = [p['value'] for p in points[-13:-1] if p.get('value') and p['value'] > 0]
        if len(historical) < 6:
            continue

        avg = sum(historical) / len(historical)
        if avg <= 0:
            continue

        ratio = latest_val / avg

        if ratio >= ANOMALY_MULTIPLIER:
            # Format period for query
            try:
                period_dt = datetime.strptime(latest_period[:10], '%Y-%m-%d')
                period_str = period_dt.strftime('%B %Y')
            except (ValueError, TypeError):
                period_str = latest_period[:7]

            anomalies.append({
                'query': (f"major construction development project approved {cma} "
                          f"{province} {period_str} new building"),
                'province': province,
                'sector': 'construction',
                'source': 'statcan_permits',
                'language': 'en',
                'geo_tier': 'cma',
                'municipality': cma,
                'current_value_millions': round(latest_val / 1000, 1),
                'average_value_millions': round(avg / 1000, 1),
                'ratio': round(ratio, 2),
                'period': latest_period[:10],
            })

    print(f"  [PERMITS] {len(anomalies)} anomalies detected from "
          f"{len(data)} CMAs (threshold: {ANOMALY_MULTIPLIER}x average)")
    return anomalies
