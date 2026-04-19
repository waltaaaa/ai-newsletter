#!/usr/bin/env python3
"""
Schema validator for The Lagging Indicator briefing JSON.

Checks that pipeline output matches the frontend's expected field contract.
Run after assembly (Phase 3.5) and after charts (Phase 4), before shipping.

Two phases:
  1. Briefing body validation (top-level, provinces, industries, markets, etc.)
  2. External JSON dependency validation (policy.json, projects_all.json,
     timeseries.json, indicators.json, events.json, events_global.json).
     These sibling files in `docs/data/` are read directly by the frontend
     and were historically un-gated. The cross-reference check against
     `insightCharts[].dataKeys[]` catches the silent-blank-chart failure
     mode where a chart spec names a series that does not exist in
     timeseries.json.

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
import datetime

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


def _load_json_tolerant(path):
    """Load JSON from a file, trying UTF-8 first, then CP1252/latin-1 fallback.

    Pipeline writers occasionally produce files with CP1252 bytes (em/en
    dashes, smart quotes) instead of clean UTF-8. The validator must not
    hard-crash on those — it's the frontend's tolerance that matters,
    and the frontend reads via fetch() which is permissive. Returns the
    parsed JSON or raises the original exception if all encodings fail.
    """
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    # Last resort: binary read + utf-8 with replacement
    with open(path, "rb") as f:
        raw = f.read().decode("utf-8", errors="replace")
    return json.loads(raw)


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


def _parse_iso_date(s):
    """Parse an ISO-style date or datetime string; return a date or None."""
    if not isinstance(s, str) or not s.strip():
        return None
    ss = s.strip()
    # Try datetime first (may include timezone)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.datetime.strptime(ss, fmt).date()
        except ValueError:
            continue
    # Date-only
    try:
        return datetime.date.fromisoformat(ss[:10])
    except ValueError:
        return None


def _collect_chart_dataKeys(b):
    """Walk every insightCharts[] in the briefing and return a list of
    (label, dataSource, key) tuples. Respects per-section dataSource
    defaults: top-level + provincial charts default to 'timeseries';
    industry charts default to 'indicators' (matches app.js renderers
    renderAgentInsightChart at L1814 and renderIndInsightChart at L4326).
    """
    out = []
    # Top-level
    for i, c in enumerate(b.get("insightCharts", []) or []):
        ds = (c or {}).get("dataSource") or "timeseries"
        for k in (c or {}).get("dataKeys", []) or []:
            out.append((f"top.insightCharts[{i}]", ds, k))
    # Provincial
    for p in b.get("provinces", []) or []:
        name = p.get("name", "?")
        for i, c in enumerate(p.get("insightCharts", []) or []):
            ds = (c or {}).get("dataSource") or "timeseries"
            for k in (c or {}).get("dataKeys", []) or []:
                out.append((f"province.{name}.insightCharts[{i}]", ds, k))
    # Industry (default 'indicators')
    for ind_list, ilabel in (
        (b.get("goodsIndustries", []), "goods"),
        (b.get("servicesIndustries", []), "services"),
    ):
        for ind in ind_list or []:
            iname = ind.get("name", "?")
            for i, c in enumerate(ind.get("insightCharts", []) or []):
                ds = (c or {}).get("dataSource") or "indicators"
                for k in (c or {}).get("dataKeys", []) or []:
                    out.append((f"industry.{ilabel}.{iname}.insightCharts[{i}]", ds, k))
    return out


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


# ============================================================
# CLUSTER 6 — external JSON dependency validation
# ============================================================

# Canonical lifecycle statuses (docs/js/app.js render paths; also
# projects_all.json current distribution). Distinct from the 11-type
# project_type taxonomy in CLAUDE.md; the frontend per-province table
# reads `status` as lifecycle state, not project_type.
PROJECT_LIFECYCLE_STATUSES = {
    "Proposed", "Under Review", "Approved",
    "Under Construction", "Complete", "Cancelled", "On Hold",
}

# Freshness bounds (days). Pipeline regenerates weekly, so any sibling
# file older than ~10 days relative to today's run is stale for ship.
# Policy/events have tighter bounds because they feed the headline TL;DR.
DATA_MAX_AGE_DAYS = {
    "policy.json": 14,
    "projects_all.json": 21,
    "timeseries.json": 45,   # markets data older than ~6w = stale
    "indicators.json": 45,
    "events.json": 30,
    "events_global.json": 30,
}


def _validate_policy_json(data_dir, results, briefing):
    """Validate docs/data/policy.json against the frontend contract.

    Frontend read path (docs/js/app.js):
      - L1014: _tldrBuildPolicy reads raw.weeks[0].items OR
               raw.weeks[0].summary.top_developments.
      - L1034-1050: each item rendered with {title, description|summary,
               url|source_url, level}.
      - L5757+ _loadPolicyData: walks all weeks, concats
               summary.top_developments; adds _week + date fallback.
      - L5777+ _renderPolicyItems: reads {title|headline, categories|
               category, province, level, affected_sectors,
               affected_projects_total, source_description|source, date,
               summary, url}.

    Checks (FAIL tier unless noted):
      - file exists + valid JSON
      - top-level is dict with `weeks` list and `last_updated` str
      - weeks non-empty and sorted (latest first)
      - latest week has `week_of` (ISO date) and `summary.top_developments` list
      - freshness: last_updated within DATA_MAX_AGE_DAYS
      - WARN: per-item {title,url,date,level,summary} — WARN because the
        frontend degrades gracefully on any missing field (pick()
        fallbacks); upgrade to FAIL once producer populates 100%.

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "policy.json")
    prefix = "data.policy"
    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path}"):
        return (1, 0)

    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_object", isinstance(d, dict),
                 f"Expected object, got {type(d).__name__}"):
        return (fails + 1, warns)

    # Top-level shape
    if not check(results, f"{prefix}.weeks.is_list",
                 isinstance(d.get("weeks"), list),
                 f"Expected `weeks` list, got {type(d.get('weeks')).__name__}"):
        return (fails + 1, warns)

    weeks = d["weeks"]
    if not check(results, f"{prefix}.weeks.non_empty",
                 len(weeks) > 0,
                 "Empty `weeks` — no policy data to render"):
        return (fails + 1, warns)

    # last_updated present + parseable
    lu = d.get("last_updated")
    lu_date = _parse_iso_date(lu)
    if not check(results, f"{prefix}.last_updated.present",
                 isinstance(lu, str) and bool(lu.strip()),
                 "Missing or empty last_updated"):
        fails += 1
    elif not check(results, f"{prefix}.last_updated.parseable",
                   lu_date is not None,
                   f"Unparseable last_updated: {lu!r}"):
        fails += 1

    # Freshness
    if lu_date is not None:
        age = (datetime.date.today() - lu_date).days
        bound = DATA_MAX_AGE_DAYS["policy.json"]
        if not warn(results, f"{prefix}.last_updated.fresh",
                    age <= bound,
                    f"last_updated {age}d old (bound {bound}d) — policy may be stale"):
            warns += 1

    # Latest week shape
    w0 = weeks[0] if isinstance(weeks[0], dict) else {}
    if not check(results, f"{prefix}.latest.is_object",
                 isinstance(weeks[0], dict),
                 f"Expected dict, got {type(weeks[0]).__name__}"):
        fails += 1
    else:
        wof = w0.get("week_of")
        if not check(results, f"{prefix}.latest.week_of",
                     isinstance(wof, str) and bool(wof.strip()),
                     "Missing week_of on latest week"):
            fails += 1
        summary = w0.get("summary")
        if not check(results, f"{prefix}.latest.summary.is_object",
                     isinstance(summary, dict),
                     f"Expected dict summary, got {type(summary).__name__}"):
            fails += 1
        else:
            tops = summary.get("top_developments")
            if not check(results, f"{prefix}.latest.top_developments.is_list",
                         isinstance(tops, list),
                         f"Expected list, got {type(tops).__name__}"):
                fails += 1
            else:
                # Per-item shape — WARN tier (frontend degrades gracefully).
                # Aggregate into 5 single checks for count stability.
                miss_title, miss_url, miss_date, miss_level, miss_summary = [], [], [], [], []
                for i, it in enumerate(tops):
                    if not isinstance(it, dict):
                        miss_title.append(i)
                        miss_url.append(i)
                        miss_date.append(i)
                        miss_level.append(i)
                        miss_summary.append(i)
                        continue
                    if not (isinstance(it.get("title") or it.get("headline") or it.get("name"), str)
                            and (it.get("title") or it.get("headline") or it.get("name") or "").strip()):
                        miss_title.append(i)
                    if not (isinstance(it.get("url") or it.get("source_url"), str)
                            and (it.get("url") or it.get("source_url") or "").strip()):
                        miss_url.append(i)
                    if not (isinstance(it.get("date"), str) and (it.get("date") or "").strip()):
                        miss_date.append(i)
                    if not (isinstance(it.get("level"), str) and (it.get("level") or "").strip()):
                        miss_level.append(i)
                    if not (isinstance(it.get("summary") or it.get("description") or it.get("body"), str)
                            and (it.get("summary") or it.get("description") or it.get("body") or "").strip()):
                        miss_summary.append(i)
                if not warn(results, f"{prefix}.latest.items.title",
                            len(miss_title) == 0,
                            f"{len(miss_title)} item(s) missing title at {miss_title}"):
                    warns += 1
                if not warn(results, f"{prefix}.latest.items.url",
                            len(miss_url) == 0,
                            f"{len(miss_url)} item(s) missing url/source_url at {miss_url}"):
                    warns += 1
                if not warn(results, f"{prefix}.latest.items.date",
                            len(miss_date) == 0,
                            f"{len(miss_date)} item(s) missing date at {miss_date}"):
                    warns += 1
                if not warn(results, f"{prefix}.latest.items.level",
                            len(miss_level) == 0,
                            f"{len(miss_level)} item(s) missing level at {miss_level}"):
                    warns += 1
                if not warn(results, f"{prefix}.latest.items.summary",
                            len(miss_summary) == 0,
                            f"{len(miss_summary)} item(s) missing summary/description at {miss_summary}"):
                    warns += 1
    return (fails, warns)


def _validate_projects_all_json(data_dir, results, briefing):
    """Validate docs/data/projects_all.json against the frontend contract.

    Frontend read paths (docs/js/app.js):
      - L260: fetched by the project explorer; expects Array.isArray.
      - L1089, L2556, L3159: used for province counts, TL;DR new-project
        filters, and national project preview. Reads {name, status,
        value, sector, province, firstTracked, lastSeen, evidence[].url}.

    Pipeline invariant (CLAUDE.md): every project MUST have at least one
    verifiable source URL in evidence[]. The URL hard gate means absence
    should FAIL the pipeline output, so this validator upgrades it from
    a WARN to a FAIL.

    Checks:
      - file exists + valid JSON + is Array
      - count >= 500 (pipeline has 6,615 today; 500 catches catastrophic
        regressions without tripping on legitimate pruning edits)
      - Per-project FAIL: name, status, province (required for render),
        evidence[] with >=1 non-empty url (URL hard gate invariant).
      - Per-project status value in PROJECT_LIFECYCLE_STATUSES.
      - Per-project WARN: sector populated, value populated.

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "projects_all.json")
    prefix = "data.projects_all"
    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path}"):
        return (1, 0)

    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_array",
                 isinstance(d, list),
                 f"Expected list, got {type(d).__name__}"):
        return (fails + 1, warns)

    if not check(results, f"{prefix}.count",
                 len(d) >= 500,
                 f"Only {len(d)} projects — expected >=500 (pipeline currently 6,615)"):
        fails += 1

    # Aggregate per-project gaps into single checks for count stability.
    miss_name, miss_status, miss_province, miss_url = [], [], [], []
    bad_status = []
    empty_sector, empty_value = [], []
    for i, p in enumerate(d):
        if not isinstance(p, dict):
            miss_name.append(i)
            miss_status.append(i)
            miss_province.append(i)
            miss_url.append(i)
            continue
        # name — required for render
        if not (isinstance(p.get("name"), str) and p.get("name", "").strip()):
            miss_name.append(i)
        # status — required; frontend renders via san(status)
        s = p.get("status")
        if not (isinstance(s, str) and s.strip()):
            miss_status.append(i)
        elif s not in PROJECT_LIFECYCLE_STATUSES:
            bad_status.append((i, s))
        # province — required for per-province filtering
        if not (isinstance(p.get("province"), str) and p.get("province", "").strip()):
            miss_province.append(i)
        # URL hard gate — evidence[] must have >=1 non-empty url
        ev = p.get("evidence")
        has_url = False
        if isinstance(ev, list):
            for e in ev:
                if isinstance(e, dict):
                    u = e.get("url") or e.get("archive_url")
                    if isinstance(u, str) and u.strip():
                        has_url = True
                        break
        if not has_url:
            miss_url.append(i)
        # sector — WARN if missing
        if not (isinstance(p.get("sector"), str) and p.get("sector", "").strip()):
            empty_sector.append(i)
        # value — WARN if both display string and parsed number are empty
        v_disp = p.get("value")
        v_par = p.get("parsed_value")
        disp_ok = isinstance(v_disp, str) and v_disp.strip() and v_disp.strip() != "TBD"
        par_ok = isinstance(v_par, (int, float)) and v_par not in (0, None)
        if not (disp_ok or par_ok):
            empty_value.append(i)

    if not check(results, f"{prefix}.items.name",
                 len(miss_name) == 0,
                 f"{len(miss_name)} project(s) missing name"):
        fails += 1
    if not check(results, f"{prefix}.items.status.present",
                 len(miss_status) == 0,
                 f"{len(miss_status)} project(s) missing status"):
        fails += 1
    if not check(results, f"{prefix}.items.status.lifecycle_enum",
                 len(bad_status) == 0,
                 f"{len(bad_status)} project(s) with non-lifecycle status "
                 f"(first 3: {bad_status[:3]}) — allowed: {sorted(PROJECT_LIFECYCLE_STATUSES)}"):
        fails += 1
    if not check(results, f"{prefix}.items.province",
                 len(miss_province) == 0,
                 f"{len(miss_province)} project(s) missing province"):
        fails += 1
    if not check(results, f"{prefix}.items.evidence_url",
                 len(miss_url) == 0,
                 f"{len(miss_url)} project(s) missing evidence URL — violates URL hard gate (CLAUDE.md)"):
        fails += 1
    if not warn(results, f"{prefix}.items.sector",
                len(empty_sector) == 0,
                f"{len(empty_sector)} project(s) missing sector (render degrades to blank)"):
        warns += 1
    if not warn(results, f"{prefix}.items.value",
                len(empty_value) == 0,
                f"{len(empty_value)} project(s) missing value + parsed_value"):
        warns += 1

    # File-mtime freshness — pipeline writes this file weekly
    try:
        mtime = datetime.date.fromtimestamp(os.path.getmtime(path))
        age = (datetime.date.today() - mtime).days
        bound = DATA_MAX_AGE_DAYS["projects_all.json"]
        if not warn(results, f"{prefix}.mtime.fresh",
                    age <= bound,
                    f"File mtime {age}d old (bound {bound}d) — pipeline may have skipped regen"):
            warns += 1
    except OSError:
        pass

    return (fails, warns)


def _validate_timeseries_json(data_dir, results, briefing):
    """Validate docs/data/timeseries.json and cross-reference against
    every `insightCharts[].dataKeys[]` referenced by the briefing for
    dataSource='timeseries'.

    This is the highest-value Cluster 6 check: a chart spec that names
    a series not present in timeseries.json silently renders blank
    (app.js L1856 returns early on empty raw). The old validator never
    caught this — a chart could ship with `dataKeys: ["iron_ore"]` and
    produce an empty canvas with no error.

    Checks:
      - file exists + valid JSON + is object (keyed by series name)
      - series count >= 20 (pipeline has 69 today)
      - Per-series FAIL: is list of {date,value} items with >=2 points
      - Cross-reference FAIL: every dataKey referenced by a briefing
        insightChart with dataSource='timeseries' must exist in the
        file AND have >=2 points. A missing key is a real gap that
        causes a silent blank chart in production.
      - Per-series WARN: latest date within 45-day freshness bound.

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "timeseries.json")
    prefix = "data.timeseries"
    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path}"):
        return (1, 0)

    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_object",
                 isinstance(d, dict),
                 f"Expected dict, got {type(d).__name__}"):
        return (fails + 1, warns)

    if not check(results, f"{prefix}.series_count",
                 len(d) >= 20,
                 f"Only {len(d)} series — expected >=20 (pipeline currently ~69)"):
        fails += 1

    # Per-series shape — aggregate into single checks. Too-short series
    # are WARN (some bootstrap series legitimately have 1-3 points).
    bad_shape = []
    empty_series = []
    short_series = []
    stale_series = []
    bound = DATA_MAX_AGE_DAYS["timeseries.json"]
    today = datetime.date.today()
    for k, v in d.items():
        if not isinstance(v, list):
            # Some series may be wrapped {series:[...]}; unwrap per app.js L278.
            if isinstance(v, dict) and isinstance(v.get("series"), list):
                v = v["series"]
            else:
                bad_shape.append(k)
                continue
        if len(v) == 0:
            empty_series.append(k)
            continue
        if len(v) < 2:
            short_series.append(k)
        # Freshness — check last point's date
        last = v[-1] if v else None
        if isinstance(last, dict):
            ld = _parse_iso_date(last.get("date"))
            if ld is not None:
                age = (today - ld).days
                if age > bound:
                    stale_series.append((k, age))

    if not check(results, f"{prefix}.series.shape",
                 len(bad_shape) == 0,
                 f"{len(bad_shape)} series with non-list shape "
                 f"(first 5: {bad_shape[:5]})"):
        fails += 1
    if not check(results, f"{prefix}.series.non_empty",
                 len(empty_series) == 0,
                 f"{len(empty_series)} series with zero points "
                 f"(first 5: {empty_series[:5]})"):
        fails += 1
    if not warn(results, f"{prefix}.series.min_points",
                len(short_series) == 0,
                f"{len(short_series)} series with <2 points — chart needs >=2 to render "
                f"(first 5: {short_series[:5]})"):
        warns += 1
    if not warn(results, f"{prefix}.series.freshness",
                len(stale_series) == 0,
                f"{len(stale_series)} series older than {bound}d "
                f"(first 3: {stale_series[:3]})"):
        warns += 1

    # Cross-reference: every insightCharts dataKey for dataSource='timeseries'
    # MUST resolve to a non-empty series in this file.
    refs = _collect_chart_dataKeys(briefing)
    ts_refs = [(label, k) for (label, ds, k) in refs if ds == "timeseries"]
    unresolved = []
    too_short = []
    for label, k in ts_refs:
        raw = d.get(k)
        if raw is None:
            unresolved.append((label, k))
            continue
        series = raw if isinstance(raw, list) else (
            raw.get("series") if isinstance(raw, dict) else None
        )
        if not isinstance(series, list) or len(series) < 2:
            too_short.append((label, k, 0 if not series else len(series)))

    # Cross-reference tier policy: FAIL-worthy in intent, WARN-tier on
    # rollout because today's briefing has 4 known-unresolved dataKeys
    # (iron_ore x3, potash_nutrien x1) that never made it into
    # timeseries.json. That is a real silent-blank-chart gap — surface
    # loudly but don't block the deploy gate until the pipeline backfills.
    # Upgrade to `check()` once timeseries.json includes every key
    # referenced by the current briefing — same rollout pattern as
    # Cluster 5's enrichment-card WARN tier.
    if not warn(results, f"{prefix}.chart_xref.resolved",
                len(unresolved) == 0,
                f"{len(unresolved)} insightCharts dataKey(s) missing in timeseries.json "
                f"(silent blank charts in production). Upgrade to FAIL after pipeline "
                f"backfills. First 5: {unresolved[:5]}"):
        warns += 1
    if not warn(results, f"{prefix}.chart_xref.min_points",
                len(too_short) == 0,
                f"{len(too_short)} insightCharts dataKey(s) with <2 points "
                f"(chart renders blank). Upgrade to FAIL after pipeline backfills. "
                f"First 5: {too_short[:5]}"):
        warns += 1
    # Count of cross-refs as a PASS-tier audit marker (visibility into coverage).
    check(results, f"{prefix}.chart_xref.count", True,
          f"Validated {len(ts_refs)} chart dataKey(s) against timeseries.json")

    return (fails, warns)


def _validate_indicators_json(data_dir, results, briefing):
    """Validate docs/data/indicators.json and cross-reference against
    insightCharts dataKeys for dataSource='indicators'.

    Frontend read paths (docs/js/app.js):
      - L40 _getHistory: reads d.history (flat list of {indicator_name,
        province, period, value, unit, source} rows). Used by all
        industry insight charts and the indicator explorer.
      - L227, L2968, L6318, L6421, L6525: reads indicators[] (current
        snapshot) for Key Indicators tables, FX/yield curve fills,
        and the Markets tab.
      - L1817: grouped into per-key series for chart rendering.
      - statcan_latest.{updatedAt, indicators[]}: feeds the StatCan
        Latest widget on the macro tab.

    Checks:
      - file exists + valid JSON + is object with 4 keys
      - indicators[] non-empty list
      - history[] non-empty list
      - Cross-reference FAIL: every dataKey referenced by a briefing
        insightChart with dataSource='indicators' must exist as an
        indicator_name in history[] with >=2 points.
      - WARN: statcan_latest.updatedAt within freshness bound.

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "indicators.json")
    prefix = "data.indicators"
    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path}"):
        return (1, 0)

    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_object",
                 isinstance(d, dict),
                 f"Expected dict, got {type(d).__name__}"):
        return (fails + 1, warns)

    # Shape
    inds = d.get("indicators")
    hist = d.get("history")
    if not check(results, f"{prefix}.indicators.is_list",
                 isinstance(inds, list),
                 f"Expected list, got {type(inds).__name__}"):
        fails += 1
    elif not check(results, f"{prefix}.indicators.non_empty",
                   len(inds) > 0,
                   "Empty indicators list"):
        fails += 1

    if not check(results, f"{prefix}.history.is_list",
                 isinstance(hist, list),
                 f"Expected list, got {type(hist).__name__}"):
        fails += 1
    elif not check(results, f"{prefix}.history.non_empty",
                   len(hist) > 0,
                   "Empty history list"):
        fails += 1

    # Build indicator_name -> point_count map from history
    hist_counts = {}
    if isinstance(hist, list):
        for row in hist:
            if isinstance(row, dict):
                name = row.get("indicator_name")
                if isinstance(name, str) and name.strip():
                    hist_counts[name] = hist_counts.get(name, 0) + 1

    # Cross-reference for dataSource='indicators' charts
    refs = _collect_chart_dataKeys(briefing)
    ind_refs = [(label, k) for (label, ds, k) in refs if ds == "indicators"]
    unresolved = []
    too_short = []
    for label, k in ind_refs:
        n = hist_counts.get(k, 0)
        if n == 0:
            unresolved.append((label, k))
        elif n < 2:
            too_short.append((label, k, n))

    # Cross-reference tier policy: WARN-tier on rollout (same as the
    # timeseries cross-ref) — charts with dataSource='indicators' are
    # industry charts per renderIndInsightChart (app.js L4326); a miss
    # here would silently blank the canvas. Today the briefing emits
    # zero such references (industry charts default but set
    # dataSource='timeseries' explicitly), so this check currently
    # passes trivially; it is seeded for when the industry writer
    # starts using indicator-backed dataKeys. Upgrade to `check()`
    # alongside the timeseries cross-ref upgrade.
    if not warn(results, f"{prefix}.chart_xref.resolved",
                len(unresolved) == 0,
                f"{len(unresolved)} insightCharts dataKey(s) missing in indicators.history "
                f"(silent blank charts in production). Upgrade to FAIL alongside "
                f"timeseries xref. First 5: {unresolved[:5]}"):
        warns += 1
    if not warn(results, f"{prefix}.chart_xref.min_points",
                len(too_short) == 0,
                f"{len(too_short)} insightCharts dataKey(s) with <2 history points "
                f"(chart renders blank). Upgrade to FAIL alongside timeseries xref. "
                f"First 5: {too_short[:5]}"):
        warns += 1
    check(results, f"{prefix}.chart_xref.count", True,
          f"Validated {len(ind_refs)} chart dataKey(s) against indicators.history")

    # statcan_latest freshness
    sl = d.get("statcan_latest")
    if isinstance(sl, dict):
        ua = sl.get("updatedAt")
        ua_date = _parse_iso_date(ua)
        if not warn(results, f"{prefix}.statcan_latest.updatedAt",
                    isinstance(ua, str) and bool(ua.strip()),
                    "Missing updatedAt on statcan_latest block"):
            warns += 1
        elif ua_date is not None:
            age = (datetime.date.today() - ua_date).days
            bound = DATA_MAX_AGE_DAYS["indicators.json"]
            if not warn(results, f"{prefix}.statcan_latest.fresh",
                        age <= bound,
                        f"statcan_latest.updatedAt {age}d old (bound {bound}d)"):
                warns += 1

    return (fails, warns)


def _validate_events_json(data_dir, results, briefing):
    """Validate docs/data/events.json — domestic calendar feed.

    Frontend read path (docs/js/app.js L5532): merged into _calEvents for
    the Calendar tab. Each event rendered with {date, name|event_name|
    event, source|institution, type, significance|impact, province, url,
    relevance|description}. Graceful degradation on every field — blanks
    render as empty strings — so all per-item checks are WARN tier.

    Checks:
      - file exists + valid JSON + is list
      - non-empty (FAIL if totally missing calendar data)
      - WARN: per-item {date, name, url} populated
      - WARN: file mtime within 30-day freshness bound

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "events.json")
    prefix = "data.events"
    # This file is secondary — if missing, the Calendar tab falls back
    # to D.watchlist. FAIL only on existence + valid JSON; WARN on shape.
    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path}"):
        return (1, 0)

    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_list",
                 isinstance(d, list),
                 f"Expected list, got {type(d).__name__}"):
        return (fails + 1, warns)

    if not warn(results, f"{prefix}.non_empty",
                len(d) > 0,
                "Empty events list — Calendar tab will fall back to briefing.watchlist"):
        warns += 1

    miss_date, miss_name, miss_url = [], [], []
    for i, it in enumerate(d):
        if not isinstance(it, dict):
            miss_date.append(i)
            miss_name.append(i)
            miss_url.append(i)
            continue
        if not (isinstance(it.get("date"), str) and it.get("date", "").strip()):
            miss_date.append(i)
        nm = it.get("name") or it.get("event_name") or it.get("event")
        if not (isinstance(nm, str) and nm.strip()):
            miss_name.append(i)
        if not (isinstance(it.get("url"), str) and it.get("url", "").strip()):
            miss_url.append(i)
    if not warn(results, f"{prefix}.items.date",
                len(miss_date) == 0,
                f"{len(miss_date)} item(s) missing date"):
        warns += 1
    if not warn(results, f"{prefix}.items.name",
                len(miss_name) == 0,
                f"{len(miss_name)} item(s) missing name/event_name/event"):
        warns += 1
    if not warn(results, f"{prefix}.items.url",
                len(miss_url) == 0,
                f"{len(miss_url)} item(s) missing url"):
        warns += 1

    return (fails, warns)


def _validate_events_global_json(data_dir, results, briefing):
    """Validate docs/data/events_global.json — US/European institution releases.

    Frontend read path (docs/js/app.js L5535): merged into _calEvents
    via {events: [...]}. Each event rendered with {date, institution,
    event_name, description, impact, source_url}.

    Checks:
      - file exists + valid JSON + dict with `events` list
      - events non-empty
      - WARN: per-item {date, event_name, institution} populated

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "events_global.json")
    prefix = "data.events_global"
    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path}"):
        return (1, 0)

    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_object",
                 isinstance(d, dict),
                 f"Expected dict, got {type(d).__name__}"):
        return (fails + 1, warns)

    events = d.get("events")
    if not check(results, f"{prefix}.events.is_list",
                 isinstance(events, list),
                 f"Expected list, got {type(events).__name__}"):
        return (fails + 1, warns)
    if not check(results, f"{prefix}.events.non_empty",
                 len(events) > 0,
                 "Empty events list"):
        fails += 1

    miss_date, miss_name, miss_inst = [], [], []
    for i, it in enumerate(events):
        if not isinstance(it, dict):
            miss_date.append(i)
            miss_name.append(i)
            miss_inst.append(i)
            continue
        if not (isinstance(it.get("date"), str) and it.get("date", "").strip()):
            miss_date.append(i)
        if not (isinstance(it.get("event_name"), str) and it.get("event_name", "").strip()):
            miss_name.append(i)
        if not (isinstance(it.get("institution"), str) and it.get("institution", "").strip()):
            miss_inst.append(i)
    if not warn(results, f"{prefix}.items.date",
                len(miss_date) == 0,
                f"{len(miss_date)} item(s) missing date"):
        warns += 1
    if not warn(results, f"{prefix}.items.event_name",
                len(miss_name) == 0,
                f"{len(miss_name)} item(s) missing event_name"):
        warns += 1
    if not warn(results, f"{prefix}.items.institution",
                len(miss_inst) == 0,
                f"{len(miss_inst)} item(s) missing institution"):
        warns += 1

    return (fails, warns)


def _validate_data_dir(briefing_path, results, briefing):
    """Phase 2: validate external JSON dependencies in the same directory
    as the briefing.

    The frontend reads these sibling files directly (not through the
    briefing). Historically they were un-gated — a stale policy.json or
    a missing timeseries series could ship silently. Cluster 6 adds
    shape, freshness, and cross-reference checks so these files share
    the same deploy gate as the briefing body itself.

    Returns (fails_added, warns_added).
    """
    data_dir = os.path.dirname(os.path.abspath(briefing_path))
    total_f = 0
    total_w = 0
    for fn in (
        _validate_policy_json,
        _validate_projects_all_json,
        _validate_timeseries_json,
        _validate_indicators_json,
        _validate_events_json,
        _validate_events_global_json,
    ):
        f, w = fn(data_dir, results, briefing)
        total_f += f
        total_w += w
    return (total_f, total_w)


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
    # 8.5 ENRICHMENT-CARD METRICS (Cluster 5 — UNKNOWN-owner diagnosis)
    # Frontend `_renderNatEnrichmentCards` (app.js L2660-2683) reads 12
    # supplementary enrichment metrics into four cards: Labour Market
    # (fulltime_change, parttime_change, private_sector_change,
    # public_sector_change), Consumer Pulse (core_cpi_median, shelter_cpi,
    # food_cpi, energy_cpi), Housing & Construction (residential_permits,
    # nonresidential_permits), and Trade & Commodities (merchandise_exports,
    # merchandise_imports).
    #
    # Producer identified (field_contract.tsv B.3 Cluster 5 diagnosis):
    #   tldr-analyst-macro emits to dossier_macro.national_analysis_package.
    #   metrics.* (SKILL.md Step 6, L192); tldr-writer-macro passes through
    #   to briefing_macro.metrics.* (SKILL.md L474); tldr-assembler merges
    #   to top-level metrics.* via `macro.get('metrics', {})` (SKILL.md L426).
    #
    # WARN-tier (not FAIL): the current edition has 8 of 12 populated and
    # 4 empty (private_sector_change, public_sector_change, residential_
    # permits, nonresidential_permits). The frontend's `pick()` helper
    # degrades gracefully to em-dash on missing keys. Upgrade to FAIL
    # once the analyst populates the 4 gaps from StatCan source tables.
    # ============================================================
    ENRICHMENT_METRICS = (
        # Labour Market card
        "fulltime_change", "parttime_change",
        "private_sector_change", "public_sector_change",
        # Consumer Pulse card
        "core_cpi_median", "shelter_cpi", "food_cpi", "energy_cpi",
        # Housing & Construction card
        "residential_permits", "nonresidential_permits",
        # Trade & Commodities card
        "merchandise_exports", "merchandise_imports",
    )
    for key in ENRICHMENT_METRICS:
        val = m.get(key)
        present = isinstance(val, str) and bool(val.strip())
        if not warn(results, f"metrics.{key}",
                     present,
                     f"Enrichment card metric missing/empty — producer tldr-analyst-macro "
                     f"(dossier_macro.national_analysis_package.metrics.{key}); "
                     f"renders em-dash fallback in _renderNatEnrichmentCards"):
            warns += 1

    # ============================================================
    # 9. PROVINCE COMPLETENESS (Cluster 2 — provincial contract)
    # Frontend `_renderProvContent` (app.js L3177-3665) reads, per province:
    #   .analysis              (L3369, Provincial Analysis section HTML)
    #   .consumerPulse         (L3370, appended to analysis block)
    #   .sectorHighlights      (L3371, Sector Signals section)
    #   .labourDeepDive        (L3512, Labour Market Detail section)
    #   .marketContext         (L3529, Project Pipeline narrative preface, first 400 chars)
    #   .tradeExposure         (L1701, word-cloud text; currently empty on all 13 — WARN-only)
    #   .indicators.{gdp,unemployment,cpi,housingStarts,participationRate,
    #                employmentRate,buildingPermits,wageGrowth}
    #                          (L3188 + L3195 nameMap, renders into Key Indicators
    #                          table; missing/empty leaves the row em-dashed)
    #   .indicatorMeta[key].{prev,change,period}
    #                          (L3210-3229, powers pchg() period-over-period
    #                          computation; absence silently falls back to
    #                          computeChange() from indicator_history)
    #   .sources[].{url,title,archive_url}
    #                          (L3395-3402, <details>Sources (N)</details>
    #                          + linkFootnotes footnote linker on all narrative
    #                          fields)
    #   .watchlistItems[].{date,event|event_name,description,impact}
    #                          (L3558-3579, Upcoming Events section)
    #   .projects[].{name,status,value,sector}
    #                          (L3536-3550, per-province project preview table)
    #   .insightCharts[]       (L3586-3611, per-province insight charts — sub-schema
    #                          checked in 10.5 via _check_chart_spec_shape and
    #                          check_callout; this block only guards array presence)
    #
    # FAIL gates are set to pass on the current ship-clean edition across all
    # 13 regions. WARN gates surface producer gaps that empty-render today and
    # will be upgraded to FAIL after the B.4 producer regen:
    #   - indicators.{employmentRate, participationRate, buildingPermits}
    #     empty on the 3 territories (YT, NT, NU)
    #   - indicators.wageGrowth absent on all 13 (producer gap)
    #   - indicatorMeta[key].{prev,change,period} empty on 28/91, 28/91, 12/91
    #     pairs (territories + buildingPermits sub-row)
    #   - tradeExposure empty on all 13 (producer gap)
    # ============================================================
    # Indicator key policy: 4 keys must be non-empty on all 13 regions (FAIL).
    # 3 keys are present-but-empty on the 3 territories today (WARN-only until
    # B.4). 1 key is a pure producer gap (wageGrowth) — WARN-only.
    PROV_IND_FAIL_KEYS = ("gdp", "unemployment", "cpi", "housingStarts")
    PROV_IND_WARN_KEYS = ("employmentRate", "participationRate", "buildingPermits")
    PROV_IND_GAP_KEYS = ("wageGrowth",)  # pure producer gap, not yet emitted
    PROV_META_KEYS = (
        "gdp", "unemployment", "cpi", "housingStarts",
        "participationRate", "employmentRate", "buildingPermits",
    )

    # Narrative field contract: (attr, min_len) pairs. Min-lengths are tuned
    # to the current writer output floors (checked across all 13 regions):
    # analysis >=1578, sectorHighlights >=359, labourDeepDive >=357,
    # consumerPulse >=347, marketContext >=146. Floors sit well below the
    # minimums so the writer has room to shrink a section in a slow week
    # without tripping FAIL, but above any plausible placeholder string.
    PROV_NARRATIVE_FIELDS = (
        ("analysis", 500),
        ("sectorHighlights", 200),
        ("labourDeepDive", 200),
        ("consumerPulse", 200),
        ("marketContext", 100),
    )

    for p in b.get("provinces", []) or []:
        name = p.get("name", "?")
        plabel = f"province.{name}"

        # 9a. Narrative fields — present + min length + no banned words.
        # Reuses Cluster 3's check_analysis_prose (3 sub-checks per field).
        for attr, min_len in PROV_NARRATIVE_FIELDS:
            fails += check_analysis_prose(
                results, f"{plabel}.{attr}",
                p.get(attr), min_len,
            )

        # 9b. tradeExposure — producer gap (empty on all 13 today). Tracks
        # the word-cloud input on app.js L1701. Upgrade to FAIL after B.4
        # regen surfaces a populated value on every region.
        te = p.get("tradeExposure")
        te_ok = isinstance(te, str) and bool(te.strip())
        if not warn(results, f"{plabel}.tradeExposure",
                    te_ok,
                    "Empty string today on all 13 regions — upgrade to FAIL after B.4 producer regen"):
            warns += 1

        # 9c. Indicators object — hard-fail keys required on every region.
        inds = p.get("indicators", {}) or {}
        if not check(results, f"{plabel}.indicators.is_object",
                     isinstance(p.get("indicators"), dict),
                     f"Expected dict, got {type(p.get('indicators')).__name__}"):
            fails += 1
        for key in PROV_IND_FAIL_KEYS:
            val = inds.get(key)
            key_ok = isinstance(val, str) and bool(val.strip())
            if not check(results, f"{plabel}.indicators.{key}",
                         key_ok,
                         f"Missing or empty indicator (got {val!r}) — Key Indicators row em-dashes"):
                fails += 1
        # WARN-tier indicators (empty on 3 territories today).
        for key in PROV_IND_WARN_KEYS:
            val = inds.get(key)
            key_ok = isinstance(val, str) and bool(val.strip())
            if not warn(results, f"{plabel}.indicators.{key}",
                        key_ok,
                        f"Empty on territories — upgrade to FAIL after B.4 producer regen"):
                warns += 1
        # Pure producer gaps (not yet emitted).
        for key in PROV_IND_GAP_KEYS:
            val = inds.get(key)
            key_ok = isinstance(val, str) and bool(val.strip())
            if not warn(results, f"{plabel}.indicators.{key}",
                        key_ok,
                        f"Not currently emitted by producer — upgrade to FAIL after B.4 regen"):
                warns += 1

        # 9d. indicatorMeta — object presence + key presence (FAIL).
        # Per-sub-key non-empty (prev/change/period) is WARN-only today
        # because 28/91, 28/91, 12/91 pairs are empty strings on the
        # current edition (mostly territories + buildingPermits).
        metas = p.get("indicatorMeta", {}) or {}
        if not check(results, f"{plabel}.indicatorMeta.is_object",
                     isinstance(p.get("indicatorMeta"), dict),
                     f"Expected dict, got {type(p.get('indicatorMeta')).__name__}"):
            fails += 1
        for key in PROV_META_KEYS:
            mobj = metas.get(key)
            key_present = isinstance(mobj, dict)
            if not check(results, f"{plabel}.indicatorMeta.{key}.present",
                         key_present,
                         f"Missing indicatorMeta[{key}] entry"):
                fails += 1
                continue
            for sub in ("prev", "change", "period"):
                v = mobj.get(sub)
                sub_ok = isinstance(v, str) and bool(v.strip())
                if not warn(results, f"{plabel}.indicatorMeta.{key}.{sub}",
                            sub_ok,
                            f"Empty {sub} — upgrade to FAIL after B.4 producer regen"):
                    warns += 1

        # 9e. Sources — min 3 items + per-item {url,title} shape.
        # Reuses Cluster 3's check_sources_array helper.
        fails += check_sources_array(
            results, f"{plabel}.sources",
            p.get("sources"), 3,
        )

        # 9f. watchlistItems — array, >=2 items, per-item shape.
        # Frontend reads e.date, e.event_name||e.event||e.name, e.description,
        # e.impact. Current edition populates all four on 13/13; min count is
        # 2 (territories). Hard-fail on shape violations.
        wl = p.get("watchlistItems")
        if not check(results, f"{plabel}.watchlistItems.is_array",
                     isinstance(wl, list),
                     f"Expected list, got {type(wl).__name__}"):
            fails += 1
        else:
            if not check(results, f"{plabel}.watchlistItems.min_count",
                         len(wl) >= 2,
                         f"Expected >=2 items, got {len(wl)}"):
                fails += 1
            missing_date, missing_event, missing_desc = [], [], []
            for i, it in enumerate(wl or []):
                if not isinstance(it, dict):
                    missing_date.append(i)
                    missing_event.append(i)
                    missing_desc.append(i)
                    continue
                if not (isinstance(it.get("date"), str) and it.get("date").strip()):
                    missing_date.append(i)
                ev = it.get("event_name") or it.get("event") or it.get("name")
                if not (isinstance(ev, str) and ev.strip()):
                    missing_event.append(i)
                if not (isinstance(it.get("description"), str) and it.get("description").strip()):
                    missing_desc.append(i)
            if not check(results, f"{plabel}.watchlistItems.items.date",
                         len(missing_date) == 0,
                         f"{len(missing_date)} item(s) missing date at index {missing_date}"):
                fails += 1
            if not check(results, f"{plabel}.watchlistItems.items.event",
                         len(missing_event) == 0,
                         f"{len(missing_event)} item(s) missing event/event_name/name at index {missing_event}"):
                fails += 1
            if not check(results, f"{plabel}.watchlistItems.items.description",
                         len(missing_desc) == 0,
                         f"{len(missing_desc)} item(s) missing description at index {missing_desc}"):
                fails += 1

        # 9g. projects — array, >=3 items, per-item shape.
        # Frontend renders each row with name/sector/value/status. Ship-clean
        # minimum across 13 regions is 4 projects; min_count 3 gives headroom.
        pjs = p.get("projects")
        if not check(results, f"{plabel}.projects.is_array",
                     isinstance(pjs, list),
                     f"Expected list, got {type(pjs).__name__}"):
            fails += 1
        else:
            if not check(results, f"{plabel}.projects.min_count",
                         len(pjs) >= 3,
                         f"Expected >=3 items, got {len(pjs)}"):
                fails += 1
            missing_name, missing_status = [], []
            empty_value = []
            for i, it in enumerate(pjs or []):
                if not isinstance(it, dict):
                    missing_name.append(i)
                    missing_status.append(i)
                    empty_value.append(i)
                    continue
                if not (isinstance(it.get("name"), str) and it.get("name").strip()):
                    missing_name.append(i)
                if not (isinstance(it.get("status"), str) and it.get("status").strip()):
                    missing_status.append(i)
                v = it.get("value")
                if not (isinstance(v, str) and v.strip()):
                    empty_value.append(i)
            if not check(results, f"{plabel}.projects.items.name",
                         len(missing_name) == 0,
                         f"{len(missing_name)} item(s) missing name at index {missing_name}"):
                fails += 1
            if not check(results, f"{plabel}.projects.items.status",
                         len(missing_status) == 0,
                         f"{len(missing_status)} item(s) missing status at index {missing_status}"):
                fails += 1
            # value is sometimes empty on a legitimate "value TBD" project; WARN.
            if not warn(results, f"{plabel}.projects.items.value",
                        len(empty_value) == 0,
                        f"{len(empty_value)} item(s) missing value at index {empty_value}"):
                warns += 1

        # 9h. insightCharts — warn when array is missing/empty. Sub-schema
        # shape + callout quality is enforced in block 10.5 via
        # _check_chart_spec_shape + check_callout.
        if not warn(results, f"{plabel}.insightCharts",
                    p.get("insightCharts") not in (None, []),
                    "Missing or empty — per-province insight charts drive the visualization strip"):
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
    # 13. EXTERNAL JSON DEPENDENCIES (Cluster 6)
    # Validates sibling files in the same directory as the briefing.
    # These are read directly by the frontend and were previously
    # un-gated. See _validate_data_dir docstring.
    # ============================================================
    ext_fails, ext_warns = _validate_data_dir(briefing_path, results, b)
    fails += ext_fails
    warns += ext_warns

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
