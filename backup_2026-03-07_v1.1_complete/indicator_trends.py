"""
indicator_trends.py -- Macro indicator trend computation.

Computes period-over-period changes, rates of change, and trend
direction for economic indicators stored in Firestore timeseries.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Key indicators to track trends for
KEY_INDICATORS = [
    "boc_overnight_rate",
    "cpi_yoy",
    "unemployment_rate",
    "gdp_quarterly",
    "wti_crude",
    "cad_usd",
    "sp_tsx",
    "housing_starts",
]


def _safe_float(val):
    """Convert value to float, return None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def compute_indicator_trend(values, periods=4):
    """Compute trend for a single indicator time series.

    Args:
        values: list of (date_str, numeric_value) sorted oldest-first
        periods: number of recent periods to analyze

    Returns:
        dict with current, previous, change, pct_change, direction, streak
    """
    if not values or len(values) < 2:
        return {"direction": "insufficient_data", "data_points": len(values or [])}

    # Get recent values
    recent = values[-periods:] if len(values) >= periods else values
    current = _safe_float(recent[-1][1])
    previous = _safe_float(recent[-2][1])

    if current is None or previous is None:
        return {"direction": "insufficient_data"}

    change = round(current - previous, 4)
    pct_change = round((change / abs(previous)) * 100, 2) if previous != 0 else 0.0

    # Determine direction
    if abs(pct_change) < 0.5:
        direction = "stable"
    elif change > 0:
        direction = "rising"
    else:
        direction = "falling"

    # Calculate streak (consecutive moves in same direction)
    streak = 0
    for i in range(len(recent) - 1, 0, -1):
        v1 = _safe_float(recent[i][1])
        v0 = _safe_float(recent[i - 1][1])
        if v1 is None or v0 is None:
            break
        if (direction == "rising" and v1 > v0) or (direction == "falling" and v1 < v0):
            streak += 1
        else:
            break

    return {
        "current": current,
        "previous": previous,
        "change": change,
        "pct_change": pct_change,
        "direction": direction,
        "streak": streak,
        "data_points": len(values),
    }


def compute_rate_of_change(values, window=3):
    """Compute average rate of change over a window of observations.

    Returns annualized rate if dates are available.
    """
    if not values or len(values) < window + 1:
        return None

    recent = values[-(window + 1):]
    changes = []
    for i in range(1, len(recent)):
        v1 = _safe_float(recent[i][1])
        v0 = _safe_float(recent[i - 1][1])
        if v1 is not None and v0 is not None and v0 != 0:
            changes.append((v1 - v0) / abs(v0))

    if not changes:
        return None

    avg_change = sum(changes) / len(changes)
    return round(avg_change * 100, 2)


def compute_indicator_trends(db):
    """Main entry point: compute trends for all key indicators.

    Reads from Firestore timeseries collection.

    Args:
        db: Firestore client

    Returns:
        dict mapping indicator_name -> trend info
    """
    print("\n[TRENDS] Computing indicator trends...")
    results = {}

    # Read from timeseries collection
    ts_ref = db.collection("timeseries")

    for indicator in KEY_INDICATORS:
        try:
            doc = ts_ref.document(indicator).get()
            if not doc.exists:
                results[indicator] = {"direction": "no_data"}
                continue

            data = doc.to_dict()
            # timeseries docs store values as {date: value} or as a list
            series = data.get("values", {})

            if isinstance(series, dict):
                # Convert {date: value} to sorted list of tuples
                values = sorted(series.items(), key=lambda x: x[0])
            elif isinstance(series, list):
                values = [(item.get("date", ""), item.get("value"))
                          for item in series]
                values.sort(key=lambda x: x[0])
            else:
                results[indicator] = {"direction": "bad_format"}
                continue

            trend = compute_indicator_trend(values)
            trend["rate_of_change"] = compute_rate_of_change(values)
            results[indicator] = trend

        except Exception as e:
            logger.warning(f"Failed to compute trend for {indicator}: {e}")
            results[indicator] = {"direction": "error", "error": str(e)}

    # Also check latest newsletter for current values
    try:
        nl_docs = list(db.collection("newsletters")
                       .order_by("weekOf", direction="DESCENDING")
                       .limit(2)
                       .stream())
        if len(nl_docs) >= 2:
            current_nl = nl_docs[0].to_dict()
            previous_nl = nl_docs[1].to_dict()
            results["_newsletter_comparison"] = _compare_newsletters(
                current_nl, previous_nl
            )
    except Exception as e:
        logger.warning(f"Newsletter comparison failed: {e}")

    # Summary
    directions = {}
    for k, v in results.items():
        if k.startswith("_"):
            continue
        d = v.get("direction", "unknown")
        directions[d] = directions.get(d, 0) + 1

    print(f"  [TRENDS] Indicators: {directions}")
    return results


def _compare_newsletters(current, previous):
    """Compare key fields between two newsletter docs."""
    comparisons = {}
    fields_to_compare = [
        "boc_rate", "cpi", "unemployment", "gdp_growth",
        "wti", "cad_usd", "tsx",
    ]
    for field in fields_to_compare:
        cur_val = _safe_float(current.get(field))
        prev_val = _safe_float(previous.get(field))
        if cur_val is not None and prev_val is not None:
            change = round(cur_val - prev_val, 4)
            comparisons[field] = {
                "current": cur_val,
                "previous": prev_val,
                "change": change,
                "direction": "rising" if change > 0 else ("falling" if change < 0 else "stable"),
            }
    return comparisons
