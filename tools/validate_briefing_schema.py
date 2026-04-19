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

# Canonical global region names (app.js REGION_MAP in _renderGlobalSubtab)
CANONICAL_GLOBAL_REGIONS = {
    "United States", "China", "China / Asia", "European Union", "United Kingdom",
}

# Minimum analysis length thresholds. National is a multi-paragraph deep-dive;
# per-region global is a shorter 2-3 paragraph section. These floors catch
# "analysis will be available after next pipeline run" placeholders and
# accidental truncation. Tuned to the current writer's observed output:
# national ~4.8k chars, per-region global 1.2k-1.6k chars.
NATIONAL_ANALYSIS_MIN_LEN = 500
GLOBAL_ANALYSIS_MIN_LEN = 400

# Minimum sources count. National section cites many data points; per-region
# global is narrower. Frontend renders `<details>Sources (N)</details>` from
# the array, so an empty array means no citations at all.
NATIONAL_SOURCES_MIN_COUNT = 3
GLOBAL_SOURCES_MIN_COUNT = 1

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


def check_analysis_prose(results, label, text, min_len):
    """Validate a long-form analysis narrative string.

    Frontend reads `national.analysis` via `_natNarrative` and
    `global[i].analysis` via the same helper (app.js L2483-2487,
    L2725). Both render raw text — an empty or placeholder string
    leaves a blank section. The main BANNED_WORDS sweep runs over
    the full JSON blob at validator exit; this per-field check
    adds precise location info when editorial prose leaks in.

    Returns the number of FAILs added (0 = all checks passed).
    Aggregates banned-word hits into a single FAIL for count stability.
    """
    fails = 0
    # 1. Present + non-empty string
    present_ok = isinstance(text, str) and bool(text.strip())
    if not check(results, f"{label}.present", present_ok,
                 "Missing or empty analysis string"):
        fails += 1
        # Short-circuit: remaining checks are meaningless on empty text.
        return fails
    # 2. Minimum length
    n = len(text)
    if not check(results, f"{label}.length",
                 n >= min_len,
                 f"Length {n} below floor {min_len} — likely a placeholder or truncated output"):
        fails += 1
    # 3. Banned editorial words — aggregate single check (editorial policy)
    hits = []
    for word in BANNED_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE):
            hits.append(word)
    if not check(results, f"{label}.banned_words",
                 len(hits) == 0,
                 f"Contains banned editorial words: {', '.join(hits)}"):
        fails += 1
    return fails


def check_sources_array(results, label, sources, min_count):
    """Validate a sources array for shape + per-item required fields.

    Frontend `_natSourcesSection` (app.js L2471-2482) reads `s.url`
    or `s.archive_url` for the link and `s.title` for the display
    text. An item missing both url fields renders as text-only with
    no way for the reader to verify. An item missing title falls
    back to the literal string 'Source'. Both degrade citation
    credibility, so both are required.

    Returns the number of FAILs added (0 = all checks passed).
    Aggregates per-item gaps into 2 single checks (url + title) for
    count stability.
    """
    fails = 0
    # 1. Is array
    if not isinstance(sources, list):
        check(results, f"{label}.is_array", False,
              f"Expected list, got {type(sources).__name__}")
        return 1
    check(results, f"{label}.is_array", True, "")
    # 2. Minimum count
    if not check(results, f"{label}.min_count",
                 len(sources) >= min_count,
                 f"Expected >={min_count}, got {len(sources)}"):
        fails += 1
    # 3. Every item has non-empty url (or archive_url fallback per frontend)
    missing_url = []
    missing_title = []
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            missing_url.append(i)
            missing_title.append(i)
            continue
        url = s.get("url") or s.get("archive_url")
        if not (isinstance(url, str) and url.strip()):
            missing_url.append(i)
        title = s.get("title")
        if not (isinstance(title, str) and title.strip()):
            missing_title.append(i)
    if not check(results, f"{label}.items.url",
                 len(missing_url) == 0,
                 f"{len(missing_url)} item(s) missing url/archive_url at index {missing_url}"):
        fails += 1
    if not check(results, f"{label}.items.title",
                 len(missing_title) == 0,
                 f"{len(missing_title)} item(s) missing title at index {missing_title}"):
        fails += 1
    return fails


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
    # 7. GLOBAL INDICATORS + ANALYSIS + SOURCES (per-region)
    # Frontend `_renderGlobalSubtab` (app.js L2705-2735) reads, per region:
    #   region, analysis, sources[].{url,title}, indicators.{5 keys},
    #   indicatorMeta[key].change, indicatorMeta[key].period (optional),
    #   indicatorMeta[key].nextRelease (optional), chart_callout (checked in 10.5).
    # This block guards every required read; chart_callout is handled in
    # section 10.5 (callout quality contract) and stays there.
    # ============================================================
    for g in b.get("global", []):
        region = g.get("region", "?")
        # 7a. region — required non-empty string, canonical name
        region_present = isinstance(region, str) and bool(region.strip()) and region != "?"
        if not check(results, f"global[{region}].region.present",
                      region_present,
                      "Missing or empty region string"):
            fails += 1
        if not check(results, f"global[{region}].region.canonical",
                      region in CANONICAL_GLOBAL_REGIONS,
                      f"Region '{region}' not in canonical list {sorted(CANONICAL_GLOBAL_REGIONS)}"):
            fails += 1

        # 7b. analysis — required non-empty prose, min length, no banned words
        fails += check_analysis_prose(
            results, f"global[{region}].analysis",
            g.get("analysis"), GLOBAL_ANALYSIS_MIN_LEN,
        )

        # 7c. sources — required non-empty array of {url,title} items
        fails += check_sources_array(
            results, f"global[{region}].sources",
            g.get("sources"), GLOBAL_SOURCES_MIN_COUNT,
        )

        # 7d. indicators — 5 required keys, each a non-empty string.
        # "N/A" is a legitimate absence signal (frontend `hasVal` filters it);
        # an empty string or null is not.
        inds = g.get("indicators", {}) or {}
        meta = g.get("indicatorMeta", {}) or {}
        for key in GLOBAL_INDICATOR_KEYS:
            val = inds.get(key)
            key_ok = key in inds and isinstance(val, str) and bool(val.strip())
            if not check(results, f"global.{region}.indicators.{key}",
                          key_ok,
                          f"Missing or non-string indicator: {val!r}"):
                fails += 1
            # indicatorMeta[key].change — frontend displays movement from
            # this field; absence leaves the change column blank. Producer
            # (tldr-analyst-macro) currently emits empty strings for every
            # global region × indicator pair — a real gap that causes every
            # global KPI movement column to render blank. Kept as WARN here
            # so Cluster 3 surfaces the gap in validator output without
            # immediately blocking deploys. Upgrade to `check()` (FAIL)
            # once the analyst is updated to populate this field. The
            # existing WARN at L338 of the pre-Cluster-3 validator only
            # tested key presence; this tightens to non-empty string.
            has_change = (
                key in meta
                and isinstance(meta.get(key), dict)
                and isinstance(meta[key].get("change"), str)
                and bool(meta[key].get("change", "").strip())
            )
            if not warn(results, f"global.{region}.indicatorMeta.{key}.change",
                         has_change,
                         f"Missing or empty indicatorMeta[{key}].change — movement signal will render blank"):
                warns += 1

    # ============================================================
    # 7.5 NATIONAL ANALYSIS + SOURCES
    # Frontend `_renderCanadaSubtab` (app.js L2561-2569) reads
    # `national.analysis` (main narrative), `national.sources` (citations
    # passed into `_natNarrative` footnote linking + sources `<details>`),
    # and `national.chart_callout` (handled in 10.5). The fallback
    # `D.national_analysis` is legacy — contract-ize the canonical path.
    # ============================================================
    nat = b.get("national") or {}
    fails += check_analysis_prose(
        results, "national.analysis",
        nat.get("analysis"), NATIONAL_ANALYSIS_MIN_LEN,
    )
    fails += check_sources_array(
        results, "national.sources",
        nat.get("sources"), NATIONAL_SOURCES_MIN_COUNT,
    )

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
    # 10.1 INDUSTRY HERO FIELDS (Cluster 4)
    # Frontend `_renderIndContent` (app.js L4464-4680) reads, per
    # selected industry, the hero-row metrics that drive the industry
    # header card and the movement-arrow CSS class:
    #   industry.mm          (L4479, GDP M/M string — display only)
    #   industry.yy          (L4480, GDP Y/Y string — display only)
    #   industry.isNegative  (L4481, boolean — drives up/down class)
    #   industry.industrySources (L4487, citation list powering the
    #                             footnote linker + sources strip).
    # Missing `mm`/`yy` leaves the hero card stats blank with em-dashes;
    # missing `isNegative` silently mis-renders direction arrows;
    # missing/empty `industrySources` breaks the footnote linker and
    # hides the sources `<details>` block entirely. All 20 industries
    # (5 goods + 15 services) must populate these four fields. The
    # sources-array shape reuses Cluster 3's helper — same {url,title}
    # contract as national.sources and global[i].sources.
    #
    # Per the audit TSV, these are `fix_layer=schema` rows flagged
    # validator-missing (rows 180-184 for goods, 206-207 for services
    # plus the shared isNegative + industrySources contract).
    # ============================================================
    for ind_list, ilabel in [(b.get("goodsIndustries", []), "goods"),
                              (b.get("servicesIndustries", []), "services")]:
        for ind in ind_list or []:
            iname = ind.get("name", "?")
            plabel = f"industry.{ilabel}.{iname}"
            # mm — required non-empty string (frontend renders raw via san())
            mm_val = ind.get("mm")
            mm_ok = isinstance(mm_val, str) and bool(mm_val.strip())
            if not check(results, f"{plabel}.mm",
                          mm_ok,
                          f"Missing or non-string mm (got {type(mm_val).__name__}: {mm_val!r}) — hero M/M stat renders as em-dash"):
                fails += 1
            # yy — required non-empty string
            yy_val = ind.get("yy")
            yy_ok = isinstance(yy_val, str) and bool(yy_val.strip())
            if not check(results, f"{plabel}.yy",
                          yy_ok,
                          f"Missing or non-string yy (got {type(yy_val).__name__}: {yy_val!r}) — hero Y/Y stat renders as em-dash"):
                fails += 1
            # isNegative — required boolean (!s.isNegative is truthy for
            # null/undefined, which silently mis-renders up-arrow on a
            # declining industry).
            isn_val = ind.get("isNegative")
            if not check(results, f"{plabel}.isNegative",
                          isinstance(isn_val, bool),
                          f"Missing or non-boolean isNegative (got {type(isn_val).__name__}: {isn_val!r}) — direction arrow mis-renders"):
                fails += 1
            # industrySources — required non-empty array of {url,title}
            # items. Reuses Cluster 3's check_sources_array helper: same
            # shape contract as national.sources / global[i].sources.
            fails += check_sources_array(
                results, f"{plabel}.industrySources",
                ind.get("industrySources"), 1,
            )

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
