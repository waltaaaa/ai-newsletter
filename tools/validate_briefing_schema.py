#!/usr/bin/env python3
"""
Schema validator for The Lagging Indicator briefing JSON.

Checks that pipeline output matches the frontend's expected field contract.
Run after assembly (Phase 3.5) and after charts (Phase 4), before shipping.

Usage:
    python tools/validate_briefing_schema.py docs/data/briefing_2026-04-18.json
    python tools/validate_briefing_schema.py  # defaults to briefing_latest.json

Exit codes:
    0 = PASS
    1 = FAIL (critical issues found)
    2 = WARN (non-critical issues found)
"""
import json
import re
import sys
import os

# ============================================================
# Canonical name registries
# ============================================================

# Commodity names must match _mktTsMap in app.js
COMMODITY_NAME_MAP = {
    "Crude Oil (WTI)": "wti",
    "Crude Oil (Brent)": "brent",
    "Natural Gas": "natural_gas",
    "Gold": "gold",
    "Silver": "silver",
    "Copper": "copper",
    "Lumber": "lumber",
    "Wheat": "wheat",
    "Potash (Nutrien)": "potash_nutrien",
    "Aluminum": "aluminum",
    "Platinum": "platinum",
    "Palladium": "palladium",
    "Corn": "corn",
    "Soybeans": "soybeans",
    "Coffee": "coffee",
    "Cocoa": "cocoa",
    "Sugar #11": "sugar",
    "Cotton": "cotton",
    "Rice": "rice",
}

# Equity index names must match _mktTsMap in app.js
EQUITY_NAME_MAP = {
    "TSX Composite": "tsx_composite",
    "S&P 500": "sp500",
    "Dow Jones": "djia",
    "NASDAQ": "nasdaq",
    "FTSE 100": "ftse100",
    "DAX": "dax",
    "Nikkei 225": "nikkei225",
}

# Required per-commodity fields
COMMODITY_FIELDS = ["name", "val", "day", "mm", "yy", "context", "unit", "category"]

# Required per-equity fields
EQUITY_FIELDS = ["name", "value", "day", "mm", "yy"]

# Required per-FX fields
FX_FIELDS = ["name", "value", "day", "mm", "yy"]

# Required yield curve item fields
YIELD_FIELDS = ["term", "yield", "prevYield"]

# Global indicator keys frontend hardcodes
GLOBAL_INDICATOR_KEYS = ["gdp", "cpi", "rate", "unemployment", "tradeBalance"]

# Banned editorial words
BANNED_WORDS = [
    "should", "must", "hopefully", "unfortunately", "worrying", "promising",
    "encouraging", "welcome", "bullish", "bearish", "concerning", "headwind",
    "tailwind", "thrilled", "feared", "hoped",
]

# Bad commodity names (pipeline defaults that don't match frontend)
BAD_COMMODITY_NAMES = [
    "WTI Crude Oil", "Brent Crude", "Natural Gas (Henry Hub)",
    "Potash (Nutrien proxy)", "DJIA", "Nasdaq Composite",
]


def load_json(path):
    with open(path) as f:
        return json.load(f)


def check(results, name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append({"name": name, "status": status, "detail": detail})
    return condition


def warn(results, name, condition, detail=""):
    status = "PASS" if condition else "WARN"
    results.append({"name": name, "status": status, "detail": detail})
    return condition


# Callout quality subset — validator hard-fails on any match (enforces editorial policy
# at the chart level, where casual editorializing is most likely to slip in).
CALLOUT_BANNED_WORDS = [
    "welcome", "concerning", "worrying", "promising", "encouraging",
    "unfortunately", "hopefully", "bullish", "bearish",
]


# Allowed chart types — frontend renderers (`_svgCalloutChart`, `renderAgentInsightChart`,
# `renderIndInsightChart` in app.js) branch exclusively on these four values.
ALLOWED_CHART_TYPES = ("line", "multi_line", "bar", "diverging_bar")


def _check_chart_spec_shape(results, chart, label):
    """Validate a single chart spec's structural sub-schema.

    Frontend reads `chartType`, `title`, `dataKeys`, and `subtitle`. Missing
    `dataKeys` means the chart silently does not render; missing `chartType`
    or `title` means the chart renders degraded with generic fallbacks. Per
    the tldr-charts SKILL contract, all three are hard-required; `subtitle`
    is recommended (warn).

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    if not isinstance(chart, dict):
        check(results, f"chart.{label}.is_object", False,
              f"Chart spec is not an object: {type(chart).__name__}")
        return (1, 0)

    # chartType — non-empty string, in enum
    ct = chart.get("chartType")
    if not isinstance(ct, str) or not ct.strip():
        check(results, f"chart.{label}.chartType", False,
              "Missing or empty chartType")
        fails += 1
    elif ct not in ALLOWED_CHART_TYPES:
        check(results, f"chart.{label}.chartType.enum", False,
              f"chartType '{ct}' not in {list(ALLOWED_CHART_TYPES)}")
        fails += 1
    else:
        check(results, f"chart.{label}.chartType", True, "")

    # title — non-empty string
    title = chart.get("title")
    if not isinstance(title, str) or not title.strip():
        check(results, f"chart.{label}.title", False,
              "Missing or empty title")
        fails += 1
    else:
        check(results, f"chart.{label}.title", True, "")

    # dataKeys — non-empty array of non-empty strings
    dk = chart.get("dataKeys")
    if not isinstance(dk, list) or len(dk) == 0:
        check(results, f"chart.{label}.dataKeys", False,
              "Missing or empty dataKeys array — frontend will not render this chart")
        fails += 1
    elif not all(isinstance(k, str) and k.strip() for k in dk):
        check(results, f"chart.{label}.dataKeys.items", False,
              "dataKeys contains non-string or empty entries")
        fails += 1
    else:
        check(results, f"chart.{label}.dataKeys", True, "")

    # subtitle — recommended (warn if missing/empty)
    sub = chart.get("subtitle")
    if not isinstance(sub, str) or not sub.strip():
        warn(results, f"chart.{label}.subtitle", False,
             "Missing or empty subtitle (recommended per tldr-charts skill)")
        warns += 1
    else:
        warn(results, f"chart.{label}.subtitle", True, "")

    return (fails, warns)


def check_callout(results, label, text):
    """Validate a single callout string against the 5-rule Quality Contract.

    Returns the number of FAILs added (0 = all checks passed).
    """
    fails = 0
    if text is None or not isinstance(text, str) or not text.strip():
        check(results, f"callout.{label}.present", False, "Missing or empty")
        return 1
    n = len(text)
    if not check(results, f"callout.{label}.length",
                 60 <= n <= 240,
                 f"Length {n} not in [60, 240]"):
        fails += 1
    if not check(results, f"callout.{label}.cites_number",
                 bool(re.search(r"[-+]?\d", text)),
                 "No numeric data point cited"):
        fails += 1
    crossref_patterns = [
        r"\btracked\b", r"\btracks\b", r"\bpipeline\b", r"\bdatabase\b",
        r"\b\d+\s+projects?\b", r"\$\s*[\d.,]+\s*[BM]\b",
    ]
    if not check(results, f"callout.{label}.cross_reference",
                 any(re.search(p, text, re.IGNORECASE) for p in crossref_patterns),
                 "No pipeline-tracked artifact referenced"):
        fails += 1
    for word in CALLOUT_BANNED_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE):
            check(results, f"callout.{label}.banned_word.{word}", False,
                  f"Contains banned editorial word: {word}")
            fails += 1
    return fails


def validate(briefing_path):
    b = load_json(briefing_path)
    results = []
    fails = 0
    warns = 0

    # ============================================================
    # 1. TOP-LEVEL STRUCTURE
    # ============================================================
    required_top = [
        "headline", "week_of", "id", "edition", "executive_summary",
        "national", "provinces", "goodsIndustries", "servicesIndustries",
        "global", "sources", "commodities", "financialMarkets",
        "yieldCurve", "consumer_pulse", "watchlist", "metrics",
        "indicatorMeta", "insightCharts",
    ]
    for key in required_top:
        if not check(results, f"top_level.{key}", key in b and b[key] is not None,
                      f"Missing or null: {key}"):
            fails += 1

    # ============================================================
    # 2. ARRAY COUNTS
    # ============================================================
    count_checks = [
        ("provinces", 13), ("goodsIndustries", 5), ("servicesIndustries", 15),
        ("global", 4), ("insightCharts", 2),
    ]
    for key, expected in count_checks:
        actual = len(b.get(key, []))
        if not check(results, f"count.{key}", actual == expected,
                      f"Expected {expected}, got {actual}"):
            fails += 1

    if not check(results, "count.commodities", len(b.get("commodities", [])) >= 13,
                  f"Expected >=13, got {len(b.get('commodities', []))}"):
        fails += 1

    if not check(results, "count.sources", len(b.get("sources", [])) >= 10,
                  f"Expected >=10, got {len(b.get('sources', []))}"):
        fails += 1

    # ============================================================
    # 3. YIELD CURVE FORMAT
    # ============================================================
    yc = b.get("yieldCurve")
    if not check(results, "yieldCurve.is_list", isinstance(yc, list),
                  f"Expected list, got {type(yc).__name__}"):
        fails += 1
    elif yc:
        for field in YIELD_FIELDS:
            if not check(results, f"yieldCurve[0].{field}", field in yc[0],
                          f"Missing field in yield curve items"):
                fails += 1

    if not warn(results, "yieldCurveLastYear", b.get("yieldCurveLastYear") is not None,
                 "Missing — SVG will not show 1-year-ago comparison line"):
        warns += 1

    # ============================================================
    # 4. COMMODITY VALIDATION
    # ============================================================
    for i, c in enumerate(b.get("commodities", [])):
        name = c.get("name", f"[{i}]")
        # Check required fields
        for field in COMMODITY_FIELDS:
            if not warn(results, f"commodity.{name}.{field}",
                         field in c and c[field] not in (None, ""),
                         f"Missing or empty"):
                warns += 1

        # Check name is canonical
        if name in BAD_COMMODITY_NAMES:
            check(results, f"commodity.{name}.canonical_name", False,
                  f"Non-canonical name — must match _mktTsMap in app.js")
            fails += 1

    # ============================================================
    # 5. EQUITY INDEX VALIDATION
    # ============================================================
    fm = b.get("financialMarkets", {})
    indices = fm.get("indices", [])
    if not check(results, "equities.count", len(indices) >= 4,
                  f"Expected >=4, got {len(indices)}"):
        fails += 1

    for idx in indices:
        name = idx.get("name", "?")
        for field in EQUITY_FIELDS:
            if not warn(results, f"equity.{name}.{field}",
                         field in idx and idx[field] not in (None, ""),
                         f"Missing or empty"):
                warns += 1
        if name in BAD_COMMODITY_NAMES:
            check(results, f"equity.{name}.canonical_name", False,
                  f"Non-canonical name")
            fails += 1

    # ============================================================
    # 6. FX VALIDATION
    # ============================================================
    for fx in fm.get("fx", []):
        name = fx.get("name", "?")
        for field in FX_FIELDS:
            if not warn(results, f"fx.{name}.{field}",
                         field in fx and fx[field] not in (None, ""),
                         f"Missing or empty"):
                warns += 1

    # ============================================================
    # 7. GLOBAL INDICATORS
    # ============================================================
    for g in b.get("global", []):
        region = g.get("region", "?")
        inds = g.get("indicators", {})
        meta = g.get("indicatorMeta", {})
        for key in GLOBAL_INDICATOR_KEYS:
            if not check(results, f"global.{region}.indicators.{key}",
                          key in inds, f"Missing standard indicator key"):
                fails += 1
            if not warn(results, f"global.{region}.indicatorMeta.{key}",
                         key in meta and "change" in meta.get(key, {}),
                         f"Missing indicatorMeta with change field"):
                warns += 1

    # ============================================================
    # 8. METRICS _CHG KEYS
    # ============================================================
    m = b.get("metrics", {})
    im = b.get("indicatorMeta", {})
    for meta_key in im:
        chg_key = meta_key + "_chg"
        if not warn(results, f"metrics.{chg_key}",
                     chg_key in m,
                     f"Missing _chg key for {meta_key}"):
            warns += 1

    # Snake_case aliases
    aliases = {
        "building_permits": "buildingPermits",
        "housing_starts": "housingStarts",
        "trade_balance": "tradeBalance",
    }
    for snake, camel in aliases.items():
        if camel in m:
            if not warn(results, f"metrics.{snake}_alias",
                         snake in m, f"Missing snake_case alias for {camel}"):
                warns += 1

    # ============================================================
    # 9. PROVINCE COMPLETENESS
    # ============================================================
    for p in b.get("provinces", []):
        name = p.get("name", "?")
        for field in ["analysis", "indicators", "indicatorMeta", "sources",
                       "insightCharts", "marketContext"]:
            val = p.get(field)
            if not warn(results, f"province.{name}.{field}",
                         val is not None and val != "" and val != [],
                         f"Missing or empty"):
                warns += 1

    # ============================================================
    # 10. INDUSTRY COMPLETENESS
    # ============================================================
    for ind_list, label in [(b.get("goodsIndustries", []), "goods"),
                             (b.get("servicesIndustries", []), "services")]:
        for ind in ind_list:
            name = ind.get("name", "?")
            if not warn(results, f"industry.{label}.{name}.insightCharts",
                         ind.get("insightCharts") not in (None, []),
                         f"Missing or empty insight charts"):
                warns += 1
            if not warn(results, f"industry.{label}.{name}.analysis",
                         ind.get("analysis") not in (None, ""),
                         f"Missing analysis"):
                warns += 1

    # ============================================================
    # 10.5 CALLOUT QUALITY CONTRACT
    # Every callout at every tier MUST satisfy 5 rules:
    # length 60-240, cite >=1 number, reference pipeline artifact,
    # no banned editorial words, no empty/placeholder.
    # See .claude/skills/tldr-charts/SKILL.md for the full contract.
    # ============================================================
    # Top-level insightCharts
    for i, ch in enumerate(b.get("insightCharts", []) or []):
        label = f"top.insightCharts[{i}]"
        f, w = _check_chart_spec_shape(results, ch, label)
        fails += f
        warns += w
        cb = (ch or {}).get("callout") or (ch or {}).get("reasoning")  # legacy fallback during migration
        fails += check_callout(results, label, cb)

    # Per-province insightCharts
    for p in b.get("provinces", []) or []:
        name = p.get("name", "?")
        for i, ch in enumerate(p.get("insightCharts", []) or []):
            label = f"province.{name}.insightCharts[{i}]"
            f, w = _check_chart_spec_shape(results, ch, label)
            fails += f
            warns += w
            cb = (ch or {}).get("callout") or (ch or {}).get("context") or (ch or {}).get("reasoning")
            fails += check_callout(results, label, cb)

    # Per-industry insightCharts
    for ind_list, ilabel in [(b.get("goodsIndustries", []), "goods"),
                              (b.get("servicesIndustries", []), "services")]:
        for ind in ind_list or []:
            iname = ind.get("name", "?")
            for i, ch in enumerate(ind.get("insightCharts", []) or []):
                label = f"industry.{ilabel}.{iname}.insightCharts[{i}]"
                f, w = _check_chart_spec_shape(results, ch, label)
                fails += f
                warns += w
                cb = (ch or {}).get("callout") or (ch or {}).get("reasoning")
                fails += check_callout(results, label, cb)

    # National Canada chart callout
    nat = b.get("national") or {}
    fails += check_callout(results, "national.chart_callout", nat.get("chart_callout"))

    # Per-region global chart callouts (only when region has analysis)
    for g in b.get("global", []) or []:
        region = g.get("region", "?")
        if g.get("analysis"):
            fails += check_callout(results, f"global.{region}.chart_callout",
                                   g.get("chart_callout"))

    # ============================================================
    # 11. TOP-LEVEL ALIASES
    # ============================================================
    for key in ["bocRate", "marketCommentary", "pipeline_value", "project_count"]:
        if not warn(results, f"top_level_alias.{key}",
                     key in b and b[key] is not None,
                     f"Missing top-level alias"):
            warns += 1

    # ============================================================
    # 12. BANNED WORDS
    # ============================================================
    all_text = json.dumps(b)
    for word in BANNED_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        matches = re.findall(pattern, all_text, re.IGNORECASE)
        if matches:
            check(results, f"editorial.banned_word.{word}", False,
                  f"Found {len(matches)} occurrence(s)")
            fails += 1

    # ============================================================
    # REPORT
    # ============================================================
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = sum(1 for r in results if r["status"] == "WARN")

    print(f"\n{'='*60}")
    print(f"SCHEMA VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"File: {briefing_path}")
    print(f"Checks: {len(results)}  |  PASS: {pass_count}  |  FAIL: {fail_count}  |  WARN: {warn_count}")
    print(f"{'='*60}")

    if fail_count > 0:
        print(f"\n--- FAILURES ({fail_count}) ---")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  FAIL  {r['name']}: {r['detail']}")

    if warn_count > 0:
        print(f"\n--- WARNINGS ({warn_count}) ---")
        for r in results:
            if r["status"] == "WARN":
                print(f"  WARN  {r['name']}: {r['detail']}")

    if fail_count == 0 and warn_count == 0:
        print("\nAll checks passed. Safe to ship.")

    verdict = "FAIL" if fail_count > 0 else ("WARN" if warn_count > 0 else "PASS")
    print(f"\nVERDICT: {verdict}")
    return 1 if fail_count > 0 else (2 if warn_count > 0 else 0)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/data/briefing_latest.json"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)
    sys.exit(validate(path))
