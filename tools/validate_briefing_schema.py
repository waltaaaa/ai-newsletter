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

# Audit P9: extended editorial vocabulary from editorial_rules.md. WARN-level
# (advisory) — these words appear in legitimate quoted statements, so a hard
# FAIL would block valid attribution. The primary list above stays FAIL.
EXTENDED_BANNED_WORDS = [
    "good news", "bad news", "robust", "impressive", "disappointing",
    "remarkable", "alarming", "optimistic", "pessimistic", "worrisome",
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
    # 4. Extended editorial vocabulary (audit P9) — advisory WARN only
    ext_hits = [w for w in EXTENDED_BANNED_WORDS
                if re.search(r"\b" + re.escape(w) + r"\b", text, re.IGNORECASE)]
    warn(results, f"{label}.extended_editorial_words",
         len(ext_hits) == 0,
         f"Contains extended editorial vocabulary (advisory): {', '.join(ext_hits)}")
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
    # 4. Homepage-grade citations (audit P10) — advisory WARN. A citation
    # pointing at a domain root or bare language landing page can't be used
    # to verify the specific claim it backs.
    generic = []
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            continue
        url = (s.get("url") or s.get("archive_url") or "").strip()
        if not url:
            continue
        m = re.match(r"https?://[^/]+(/.*)?$", url, re.IGNORECASE)
        path = (m.group(1) or "/") if m else "/"
        if path in ("/", "") or re.fullmatch(r"/(en|fr)/?", path):
            generic.append(i)
    warn(results, f"{label}.items.url_specificity",
         len(generic) == 0,
         f"{len(generic)} citation(s) point at a homepage (unverifiable) "
         f"at index {generic}")
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
    "timeseries.json": 45,   # markets data older than ~6w = stale (DEFAULT only)
    "indicators.json": 45,
    "events.json": 30,
    "events_global.json": 30,
}

# Frequency-aware overrides for timeseries.json freshness. StatCan quarterly
# provincial GDP components publish with a ~2-3 month lag, so the flat 45d
# bound produced false-positive WARNs every week. These overrides reflect
# actual release cadence + publication lag for each series family.
#
# QUARTERLY provincial accounts (Ontario OEA / Quebec ISQ comptes
#   trimestriels): each observation is dated to quarter-start (Q4 -> Oct 1).
#   The next quarter (Q1) typically publishes late May/June, so the Q4 point
#   is legitimately the newest for ~240d, and up to ~300d if a release slips.
#   Bound = 300d: covers normal publication cadence without perpetual
#   false-positive WARNs, while still flagging a series with no update for
#   ~1.5+ quarters (genuinely dead source). Raised from 220 -> 300 on
#   2026-05-15 after refreshing OEA/ISQ to their latest published quarter
#   (2025Q4 = 226d old) still tripped the old 220d bound by 6 days.
# MONTHLY provincial series (LFS/retail/manufacturing/permits/housing):
#   monthly cadence + 60-90d lag. Allow up to 120d.
#
# When no override matches, fall back to DATA_MAX_AGE_DAYS["timeseries.json"].
TIMESERIES_FRESHNESS_OVERRIDES = {
    # Ontario Economic Accounts (quarterly; quarter-start dated, ~1-2q lag)
    "ON_on_exports": 300,
    "ON_on_imports": 300,
    "ON_on_gdp_goods": 300,
    "ON_on_real_capital_investment": 300,
    "ON_on_real_consumption": 300,
    "ON_on_real_household": 300,
    # Quebec provincial accounts (quarterly; quarter-start dated, ~1-2q lag)
    "QC_qc_real_gdp": 300,
    "QC_qc_business_investment": 300,
    "QC_qc_exports": 300,
    "QC_qc_imports": 300,
    # Quebec monthly (retail/trade/permits/housing/LFS, 45-90d lag)
    "QC_qc_intl_exports": 120,
    "QC_qc_intl_imports": 120,
    "QC_qc_retail_sales": 120,
    "QC_qc_manufacturing_sales": 120,
    "QC_qc_housing_starts": 120,
    "QC_qc_bldg_permits_res": 120,
    "QC_qc_bldg_permits_nonres": 120,
    "QC_qc_employment": 90,
    "QC_qc_unemployment_rate": 90,
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
    default_bound = DATA_MAX_AGE_DAYS["timeseries.json"]
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
        # Freshness — check MAX date across all points (some legacy series
        # were stored descending; taking v[-1] alone gave false positives).
        # Apply frequency-aware bound when the series has a known cadence
        # override (quarterly/monthly provincial data with publication lag).
        dates = [_parse_iso_date(p.get("date")) for p in v if isinstance(p, dict)]
        dates = [dd for dd in dates if dd is not None]
        if not dates:
            continue
        latest = max(dates)
        age = (today - latest).days
        bound = TIMESERIES_FRESHNESS_OVERRIDES.get(k, default_bound)
        if age > bound:
            stale_series.append((k, age, bound))

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
                f"{len(stale_series)} series exceed their freshness bound "
                f"(default {default_bound}d; frequency-aware overrides in "
                f"TIMESERIES_FRESHNESS_OVERRIDES). First 3: "
                f"{stale_series[:3]}"):
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

    # Cross-reference tier policy: FAIL-tier as of 2026-04-19. The
    # previous WARN tier existed because iron_ore x3 and potash_nutrien x1
    # were known-unresolved; tools/refresh_timeseries_commodity.py now
    # backfills both via free data sources (VALE / NTR.TO equity proxies
    # on yfinance). An unresolved dataKey is a silent-blank-chart in
    # production and MUST block deploy.
    if not check(results, f"{prefix}.chart_xref.resolved",
                 len(unresolved) == 0,
                 f"{len(unresolved)} insightCharts dataKey(s) missing in "
                 f"timeseries.json (silent blank chart in production). "
                 f"First 5: {unresolved[:5]}"):
        fails += 1
    if not check(results, f"{prefix}.chart_xref.min_points",
                 len(too_short) == 0,
                 f"{len(too_short)} insightCharts dataKey(s) with <2 points "
                 f"(chart renders blank). First 5: {too_short[:5]}"):
        fails += 1
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

    # Cross-reference tier: FAIL-tier (upgraded 2026-04-19 alongside the
    # timeseries.chart_xref upgrade). Industry charts with
    # dataSource='indicators' (renderIndInsightChart, app.js L4326)
    # silently blank the canvas on an unresolved dataKey — same silent-
    # failure mode as the timeseries cross-ref. Today the briefing emits
    # zero such references (industry charts default but set
    # dataSource='timeseries' explicitly), so this check passes trivially;
    # it is seeded to block the moment the industry writer starts using
    # indicator-backed dataKeys.
    if not check(results, f"{prefix}.chart_xref.resolved",
                 len(unresolved) == 0,
                 f"{len(unresolved)} insightCharts dataKey(s) missing in "
                 f"indicators.history (silent blank chart in production). "
                 f"First 5: {unresolved[:5]}"):
        fails += 1
    if not check(results, f"{prefix}.chart_xref.min_points",
                 len(too_short) == 0,
                 f"{len(too_short)} insightCharts dataKey(s) with <2 "
                 f"history points (chart renders blank). First 5: "
                 f"{too_short[:5]}"):
        fails += 1
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
    # Upgraded WARN -> FAIL 2026-04-19: event_calendar.py STATCAN_RECURRING
    # + BOC + PROVINCIAL_BUDGET_URLS now stamp url on every synthesized
    # event, and pipeline-sourced events already carry source urls. A
    # blank url is a producer bug — the Calendar tab renders events as
    # bare text with no click-through. Block deploy on regression.
    if not check(results, f"{prefix}.items.url",
                 len(miss_url) == 0,
                 f"{len(miss_url)} item(s) missing url"):
        fails += 1

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


# Frontend daily-cadence series hardcoded in docs/js/app.js GLOBAL_CHART_CFG.
# Used by _validate_global_chart_cfg to stale-flag beyond this many days.
# Daily equity/FX close series should never fall more than ~14d behind.
GLOBAL_CHART_CFG_DAILY_STALE_DAYS = 14


def _parse_global_chart_cfg(app_js_text):
    """Parse the literal GLOBAL_CHART_CFG object in docs/js/app.js to
    recover each region's tsKeys list. The object is a tiny single-level
    declaration like:

        const GLOBAL_CHART_CFG={
          us:{tsKeys:['idx_sp500','sp500'],...},
          china:{tsKeys:['usdcny','usd_cny'],...},
          ...
        };

    Returns a dict { region_key: [tsKey, ...] }. Missing / malformed
    declarations return {}.
    """
    # Locate the declaration
    m = re.search(r"GLOBAL_CHART_CFG\s*=\s*\{", app_js_text)
    if not m:
        return {}
    # Brace-match forward from the opening brace to capture the object body
    start = m.end() - 1  # index of '{'
    depth = 0
    end = None
    i = start
    n = len(app_js_text)
    in_str = None  # track ' " ` strings
    while i < n:
        ch = app_js_text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"', "`"):
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        i += 1
    if end is None:
        return {}
    body = app_js_text[start + 1:end]
    # Find each region entry by matching `<key>:{...tsKeys:[...],...}`
    out = {}
    # Match region entries at the top level of the body — each looks like
    # us:{tsKeys:['idx_sp500','sp500'],title:'S&P 500 — ...',...}
    pattern = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{([^{}]*)\}"
    )
    for entry in pattern.finditer(body):
        region = entry.group(1)
        inner = entry.group(2)
        km = re.search(r"tsKeys\s*:\s*\[([^\]]*)\]", inner)
        if not km:
            continue
        keys_raw = km.group(1)
        keys = re.findall(r"['\"]([^'\"]+)['\"]", keys_raw)
        if keys:
            out[region] = keys
    return out


def _find_app_js_path(data_dir):
    """Locate the deployed app.js.

    Originally `docs/js/app.js` lived next to `docs/data` in a co-located
    backend+frontend tree. After the backend↔frontend split, app.js moved to
    `<repo>/frontend/docs/js/app.js`. Try the legacy path first for back-compat,
    then walk to the sibling frontend tree.
    """
    docs_dir = os.path.dirname(os.path.abspath(data_dir))
    legacy = os.path.join(docs_dir, "js", "app.js")
    if os.path.exists(legacy):
        return legacy

    # docs_dir = .../backend/docs → repo root = parent of backend
    repo_root = os.path.dirname(os.path.dirname(docs_dir))
    for rel in ("frontend/docs/js/app.js",
                "frontend/public/js/app.js",
                "frontend/docs/demo/js/app.js"):
        candidate = os.path.join(repo_root, *rel.split("/"))
        if os.path.exists(candidate):
            return candidate
    return legacy  # return the legacy path so the failure message points somewhere


def _validate_global_chart_cfg(data_dir, results, briefing):
    """Validate that every region's GLOBAL_CHART_CFG.tsKeys in app.js
    resolves to at least one non-empty series in timeseries.json.

    This closes a silent-failure gap: the National tab global subtabs
    (United States / China / European Union / United Kingdom) each
    render a 12-month Chart.js line from hardcoded tsKeys in
    docs/js/app.js. Those keys are NOT referenced by any
    insightCharts[].dataKeys[] spec in the briefing, so the existing
    chart_xref check never sees them. When a producer stopped
    maintaining china_pmi, the chart silently rendered blank without
    any validator signal.

    Checks (FAIL tier):
      - app.js is readable + GLOBAL_CHART_CFG parseable
      - For each region (us, china, eu, uk), at least ONE tsKey resolves
        to a series with >=2 points in timeseries.json.

    Checks (WARN tier):
      - For each region whose winning series is older than
        GLOBAL_CHART_CFG_DAILY_STALE_DAYS (14d) by last-point date.
        These are daily equity/FX series that should stay current.

    Returns (fails_added, warns_added).
    """
    fails = 0
    warns = 0
    prefix = "data.timeseries.global_chart_cfg"

    app_js_path = _find_app_js_path(data_dir)
    if not check(results, f"{prefix}.app_js.exists",
                 os.path.exists(app_js_path),
                 f"File missing: {app_js_path}"):
        return (1, 0)

    try:
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js_text = f.read()
    except OSError as e:
        check(results, f"{prefix}.app_js.readable", False,
              f"Read error: {e}")
        return (1, 0)

    cfg = _parse_global_chart_cfg(app_js_text)
    if not check(results, f"{prefix}.parsed",
                 len(cfg) > 0,
                 "Failed to parse GLOBAL_CHART_CFG from app.js — "
                 "structure may have changed"):
        return (1, 0)

    # Load timeseries.json
    ts_path = os.path.join(data_dir, "timeseries.json")
    try:
        ts = _load_json_tolerant(ts_path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.timeseries.readable", False,
              f"Read error: {e}")
        return (1, 0)

    today = datetime.date.today()
    stale_bound = GLOBAL_CHART_CFG_DAILY_STALE_DAYS

    unresolved_regions = []
    stale_regions = []
    for region, keys in cfg.items():
        winning = None
        for k in keys:
            raw = ts.get(k)
            if raw is None:
                continue
            series = raw if isinstance(raw, list) else (
                raw.get("series") if isinstance(raw, dict) else None
            )
            if not isinstance(series, list) or len(series) < 2:
                continue
            # Track the winning (most-recent) candidate by last date
            last_date = _parse_iso_date(series[-1].get("date"))
            if winning is None or (last_date and (winning[2] is None
                                                  or last_date > winning[2])):
                winning = (k, len(series), last_date)
        if winning is None:
            unresolved_regions.append((region, keys))
        else:
            k, npts, last_date = winning
            if last_date is not None:
                age = (today - last_date).days
                if age > stale_bound:
                    stale_regions.append((region, k, age, stale_bound))

    if not check(results, f"{prefix}.resolved",
                 len(unresolved_regions) == 0,
                 f"{len(unresolved_regions)} GLOBAL_CHART_CFG region(s) "
                 f"have NO resolvable tsKey in timeseries.json "
                 f"(silent blank chart on National tab). "
                 f"Unresolved: {unresolved_regions}"):
        fails += 1

    if not warn(results, f"{prefix}.freshness",
                len(stale_regions) == 0,
                f"{len(stale_regions)} GLOBAL_CHART_CFG region(s) "
                f"exceed the {stale_bound}d daily-cadence bound "
                f"(National tab chart shows stale data). "
                f"Stale: {stale_regions}"):
        warns += 1

    # Visibility: count of regions validated.
    check(results, f"{prefix}.count", True,
          f"Validated {len(cfg)} GLOBAL_CHART_CFG region(s) "
          f"against timeseries.json")

    return (fails, warns)


def _validate_briefing_archive(data_dir, results, briefing):
    """Validate docs/data/briefing_archive.json — the previous-editions dropdown.

    Frontend read path (docs/js/app.js L199): loadEditionList() renders one
    dropdown item per entry; switchEdition() loads briefing_<file_date>.json
    (falling back to briefing_<week_of>.json for legacy entries).

    HISTORY: on 2026-06-08 a wholesale rebuild collapsed the archive from
    7 entries to 1 (restored by hand in commit 3409046). The exporter now
    union-merges and refuses to shrink, but nothing gated the published file
    itself — these checks make edition loss a deploy-blocking FAIL:

      - FAIL: file missing / invalid / not a list / empty
      - FAIL: entry missing week_of
      - FAIL: an entry's dated briefing file (file_date, else week_of) does
              not exist — that dropdown item would 404 in production
      - FAIL: SHRINK GUARD — any week_of present in git HEAD's version of
              this file is missing from the working copy (editions are
              append-only; never overwritten down to one week). Skipped
              gracefully when git/HEAD-version is unavailable.
      - WARN: the current briefing's week_of has no archive entry

    Returns (fails_added, warns_added).
    """
    import subprocess
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "briefing_archive.json")
    prefix = "data.briefing_archive"

    if not check(results, f"{prefix}.exists", os.path.exists(path),
                 f"File missing: {path} — edition dropdown will be empty"):
        return (1, 0)
    try:
        d = _load_json_tolerant(path)
    except (OSError, json.JSONDecodeError) as e:
        check(results, f"{prefix}.valid_json", False, f"Parse error: {e}")
        return (1, 0)
    check(results, f"{prefix}.valid_json", True, "")

    if not check(results, f"{prefix}.is_list", isinstance(d, list),
                 f"Expected list, got {type(d).__name__}"):
        return (fails + 1, warns)
    if not check(results, f"{prefix}.non_empty", len(d) > 0,
                 "Archive is empty — every previous edition has been lost"):
        return (fails + 1, warns)

    weeks = set()
    missing_files = []
    for i, e in enumerate(d):
        wk = (e or {}).get("week_of", "")
        if not check(results, f"{prefix}[{i}].week_of", bool(wk),
                     "Entry missing week_of — dropdown item unloadable"):
            fails += 1
            continue
        weeks.add(wk)
        fd = e.get("file_date") or wk
        dated = os.path.join(data_dir, f"briefing_{fd}.json")
        if not os.path.exists(dated):
            missing_files.append(f"{wk} -> briefing_{fd}.json")
    if not check(results, f"{prefix}.dated_files_exist", not missing_files,
                 f"{len(missing_files)} archive entr(ies) point at missing briefing "
                 f"files (dropdown 404s): {missing_files[:5]}"):
        fails += 1

    # Shrink guard vs last published state (git HEAD). Editions are
    # append-only: anything published before must still be present.
    head_weeks = set()
    try:
        r = subprocess.run(
            ["git", "show", "HEAD:./briefing_archive.json"],
            capture_output=True, cwd=data_dir, timeout=15)
        if r.returncode == 0 and r.stdout:
            for e in json.loads(r.stdout.decode("utf-8", errors="replace")) or []:
                wk = (e or {}).get("week_of", "")
                if wk:
                    head_weeks.add(wk)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError,
            ValueError, TypeError):
        head_weeks = set()
    if head_weeks:
        lost = sorted(head_weeks - weeks)
        if not check(results, f"{prefix}.no_lost_editions", not lost,
                     f"Editions present in the last published archive are GONE "
                     f"from the working copy: {lost} — archive is append-only"):
            fails += 1

    cur_week = (briefing or {}).get("week_of", "")
    if cur_week:
        if not warn(results, f"{prefix}.has_current_week", cur_week in weeks,
                    f"Current briefing week_of {cur_week} has no archive entry "
                    f"yet (expected after export step)"):
            warns += 1

    return (fails, warns)


# ── Audit P5 (2026-06-11): mechanical numeric fact-check ──────────────────
# The 2026-06-08 edition shipped market prints that contradicted the
# pipeline's own data (wheat "$671.75 fresh 52-wk high" vs actual ~$581;
# potash carrying the prior edition's value with the weekly direction
# inverted; silver off -18%). Writers sourced those numbers from WebSearch
# instead of the injected timeseries. This gate reconciles every structured
# market print in the briefing against timeseries.json at the briefing's
# own week_of date. Severity is freshness-aware: a briefing <= FRESH_DAYS
# old gets hard FAILs (the conductor's fixer loop remediates before deploy);
# an older briefing re-validated by the daily run gets WARNs so legitimate
# mid-week market drift can't block an indicator refresh.

MARKET_FACT_FRESH_DAYS = 2
MARKET_FACT_WARN_PCT = 1.5     # relative % diff that triggers a WARN
MARKET_FACT_FAIL_PCT = 5.0     # relative % diff that triggers a FAIL (fresh)
MARKET_FACT_YIELD_WARN = 0.06  # absolute pp diff for GoC yields → WARN
MARKET_FACT_YIELD_FAIL = 0.25  # absolute pp diff for GoC yields → FAIL (fresh)
MARKET_FACT_MAX_POINT_AGE = 14  # skip series whose nearest point is older

# briefing commodities[].name → timeseries.json key
COMMODITY_TS_MAP = {
    "Crude Oil (WTI)": "wti",
    "Crude Oil (Brent)": "brent",
    "Natural Gas": "natural_gas",
    "Gold": "gold",
    "Silver": "silver",
    "Copper": "copper",
    "Uranium": "uranium",
    "Nickel": "nickel",
    "Wheat": "wheat",
    "Canola": "canola",
    "Potash (Nutrien)": "potash_nutrien",
    "Lumber": "lumber",
}

# Red-team F4: series that are PROXIES in a different unit/currency than the
# briefing print (potash_nutrien = NTR.TO in CAD vs a US$ print; uranium =
# mixed spot/fund-unit lineage; nickel = FRED monthly average vs spot).
# Divergence on these is informative but must never hard-FAIL a deploy.
MARKET_FACT_PROXY_KEYS = {"potash_nutrien", "uranium", "nickel"}

# briefing fx[].name → (timeseries key, invert?)
FX_TS_MAP = {
    "CAD/USD": ("cadusd", False),
    "USD/CAD": ("cadusd", True),
    "EUR/USD": ("eurusd", False),
    "USD/JPY": ("usdjpy", False),
    "USD/CNY": ("usdcny", False),
}

# briefing yieldCurve[].term → timeseries key
YIELD_TS_MAP = {
    "2Y": "goc_2y_yield",
    "3Y": "goc_3y_yield",
    "5Y": "goc_5y_yield",
    "7Y": "goc_7y_yield",
    "10Y": "goc_10y_yield",
}


def _parse_print(val):
    """Parse a briefing market print like '$4,336.78', '34,413', '0.7169',
    '3.45%', 'C$56.01', 'US$92.00/bbl'.

    Returns float or None for N/A / unparseable / qualified values ('$3.00+').
    Red-team F5: the original parser was trivially bypassed by currency
    prefixes, unit suffixes, and '%' — a wrong print written 'C$56.01'
    silently escaped the gate entirely.
    """
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    s = val.strip()
    if not s or s.upper() in ("N/A", "NA", "—", "-"):
        return None
    if s.endswith("+"):  # qualified print ('$3.00+') — not a checkable claim
        return None
    # Extract the first number, tolerating currency prefixes (US$, C$, CA$),
    # approximation markers (~), thousands separators, unit suffixes
    # (/bbl, /oz, bps), and '%'.
    m = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", s.replace("~", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _ts_points(raw):
    """Normalize a timeseries.json entry to a list of {date, value} dicts.

    Red-team F1: dict-shaped series ({"unit":..., "history":[...]}) are a
    legal shape elsewhere in the toolchain and crashed the fact-check with a
    bare AttributeError (exit 1, no report). Tolerate every shape.
    """
    if isinstance(raw, dict):
        raw = raw.get("history") or raw.get("series") or raw.get("points") or []
    if not isinstance(raw, list):
        return []
    return [pt for pt in raw if isinstance(pt, dict)]


def _ts_anchors(series, target_date, max_age_days=MARKET_FACT_MAX_POINT_AGE):
    """Candidate comparison anchors for a market print dated target_date.

    Returns up to two (value, date_str) tuples: the latest point STRICTLY
    BEFORE target_date (the prior close a writer legitimately quotes — a
    Monday-morning intraday bar at week_of must not fail a correct
    Friday-close print; red-team F3) and the latest point AT/BEFORE
    target_date. The caller takes the minimum divergence across anchors.
    """
    best_le = None   # latest point <= target (date, value)
    best_lt = None   # latest point <  target
    for pt in _ts_points(series):
        d = _parse_iso_date(pt.get("date"))
        v = pt.get("value")
        if d is None or v is None or d > target_date:
            continue
        if best_le is None or d > best_le[0]:
            best_le = (d, v)
        if d < target_date and (best_lt is None or d > best_lt[0]):
            best_lt = (d, v)
    anchors = []
    for cand in (best_lt, best_le):
        if cand is None or (target_date - cand[0]).days > max_age_days:
            continue
        try:
            tup = (float(cand[1]), cand[0].isoformat())
        except (TypeError, ValueError):
            continue
        if tup not in anchors:
            anchors.append(tup)
    return anchors


def _validate_market_facts(data_dir, results, briefing):
    """Reconcile structured market prints against timeseries.json (audit P5)."""
    fails = 0
    warns = 0
    ts_path = os.path.join(data_dir, "timeseries.json")
    if not os.path.exists(ts_path):
        # Presence is FAIL-checked elsewhere; still flag that this gate is off.
        warn(results, "fact.gate.active", False,
             "timeseries.json missing — market fact-check gate is OFF")
        return (0, 1)
    try:
        ts = _load_json_tolerant(ts_path)
    except Exception as e:
        warn(results, "fact.gate.active", False,
             f"timeseries.json unparseable ({type(e).__name__}) — market "
             f"fact-check gate is OFF")
        return (0, 1)

    week_of = _parse_iso_date(briefing.get("week_of"))
    if week_of is None:
        # Red-team F10: a self-disabled gate must be visible, not silent.
        warn(results, "fact.gate.active", False,
             f"week_of unparseable ({briefing.get('week_of')!r}) — market "
             f"fact-check gate is OFF for this briefing")
        return (0, 1)
    from datetime import date as _date
    # Red-team F2: freshness keys off WHEN THE CONTENT WAS PRODUCED, not
    # which week it describes — a briefing regenerated/fixed days after its
    # week_of must still face hard FAILs. generated_at preferred; week_of
    # fallback.
    gen = _parse_iso_date(briefing.get("generated_at")
                          or briefing.get("updated_at") or "")
    anchor_day = max(d for d in (gen, week_of) if d is not None)
    fresh = (_date.today() - anchor_day).days <= MARKET_FACT_FRESH_DAYS
    gate = check if fresh else warn

    def _compare(label, claimed, ts_key, invert=False, absolute=None):
        nonlocal fails, warns
        series = ts.get(ts_key)
        if not series:
            return
        anchors = _ts_anchors(series, week_of)
        if not anchors:
            if not warn(results, f"fact.{label}.verifiable", False,
                        f"timeseries '{ts_key}' has no point within "
                        f"{MARKET_FACT_MAX_POINT_AGE}d of week_of — unverifiable"):
                warns += 1
            return
        # Min divergence across anchors (prior close + at-date point): a
        # correct Friday-close print must not fail against a Monday bar.
        best = None
        for actual, at in anchors:
            if invert:
                if actual == 0:
                    continue
                actual = 1.0 / actual
            if absolute is not None:
                diff = abs(claimed - actual)
                metric = diff
                detail = (f"briefing says {claimed}, timeseries '{ts_key}' = "
                          f"{actual:.2f} @ {at} (diff {diff:.2f}pp)")
                thresholds = (MARKET_FACT_YIELD_WARN, MARKET_FACT_YIELD_FAIL)
            else:
                if actual == 0:
                    continue
                pct = abs(claimed - actual) / abs(actual) * 100.0
                metric = pct
                detail = (f"briefing says {claimed}, timeseries '{ts_key}' = "
                          f"{actual:.2f} @ {at} (diff {pct:.1f}%)")
                thresholds = (MARKET_FACT_WARN_PCT, MARKET_FACT_FAIL_PCT)
            if best is None or metric < best[0]:
                best = (metric, detail, thresholds)
        if best is None:
            return
        metric, detail, (warn_t, fail_t) = best
        proxy = ts_key in MARKET_FACT_PROXY_KEYS
        if metric > fail_t and not proxy:
            if not gate(results, f"fact.{label}", False,
                        detail + " — writer print contradicts pipeline data"):
                if fresh:
                    fails += 1
                else:
                    warns += 1
        elif metric > warn_t:
            suffix = " (proxy series — unit/currency may differ)" if proxy else ""
            if not warn(results, f"fact.{label}", False, detail + suffix):
                warns += 1
        else:
            check(results, f"fact.{label}", True, "")

    # Commodities
    for c in briefing.get("commodities") or []:
        name = c.get("name", "?")
        ts_key = COMMODITY_TS_MAP.get(name)
        if not ts_key:
            continue
        claimed = _parse_print(c.get("val"))
        if claimed is None:
            continue
        _compare(f"commodity.{name}", claimed, ts_key)

    fm = briefing.get("financialMarkets") or {}
    # Equity indices — try 'val' first, fall through to 'value' when 'val'
    # is unparseable (red-team F5: "N/A" in val must not shadow a real value)
    for idx in fm.get("indices") or []:
        name = idx.get("name", "?")
        ts_key = EQUITY_NAME_MAP.get(name)
        if not ts_key:
            continue
        claimed = _parse_print(idx.get("val"))
        if claimed is None:
            claimed = _parse_print(idx.get("value"))
        if claimed is None:
            continue
        _compare(f"equity.{name}", claimed, ts_key)
    # FX pairs
    for fx in fm.get("fx") or []:
        name = fx.get("name", "?")
        mapping = FX_TS_MAP.get(name)
        if not mapping:
            continue
        ts_key, invert = mapping
        claimed = _parse_print(fx.get("val"))
        if claimed is None:
            claimed = _parse_print(fx.get("value"))
        if claimed is None:
            continue
        _compare(f"fx.{name}", claimed, ts_key, invert=invert)
    # GoC yield curve
    for y in briefing.get("yieldCurve") or []:
        term = y.get("term", "?")
        ts_key = YIELD_TS_MAP.get(term)
        if not ts_key:
            continue
        claimed = _parse_print(y.get("yield"))
        if claimed is None:
            continue
        _compare(f"yield.{term}", claimed, ts_key, absolute=True)

    return (fails, warns)


def _validate_microscope_json(data_dir, results, briefing):
    """microscope.json must be a {"topics": [...]} object, never null (audit C7).

    Production shipped a literal `null` for months. Empty topics is a WARN
    (a quiet week is legal); a malformed/null file is a FAIL — the exporter
    now always writes a well-formed object, so null means a broken export.
    """
    fails = 0
    warns = 0
    path = os.path.join(data_dir, "microscope.json")
    if not os.path.exists(path):
        if not warn(results, "data.microscope.present", False,
                    "microscope.json missing from data dir"):
            warns += 1
        return (fails, warns)
    try:
        m = _load_json_tolerant(path)
    except Exception as e:
        check(results, "data.microscope.parse", False, f"unparseable: {e}")
        return (1, 0)
    if not (isinstance(m, dict) and isinstance(m.get("topics"), list)):
        # Red-team F9: WARN, not FAIL — the frontend does not read
        # microscope.json yet (no fetch in app.js/index.html), so a malformed
        # file must not block the deploy of features that DO ship. Upgrade to
        # FAIL when the frontend section is wired.
        if not warn(results, "data.microscope.shape", False,
                    f"expected {{'topics': [...]}}, got {type(m).__name__} "
                    f"— export_microscope null-guard regressed (WARN-only: "
                    f"frontend does not consume this file yet)"):
            warns += 1
        return (fails, warns)
    check(results, "data.microscope.shape", True, "")
    if not warn(results, "data.microscope.topics", len(m["topics"]) > 0,
                "Under the Microscope has no topics — section empty in "
                "production (topic selection failed or never ran)"):
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
        _validate_global_chart_cfg,
        _validate_briefing_archive,
        _validate_market_facts,
        _validate_microscope_json,
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
            # H6: the assembler writes 'val'; the frontend reads value||val.
            # Accept either spelling for the value field.
            present = (field in idx and idx[field] not in (None, "")) or \
                      (field == "value" and idx.get("val") not in (None, ""))
            if not warn(results, f"equity.{name}.{field}", present,
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
            # H6: accept 'val' as an alias for 'value' (frontend reads both)
            present = (field in fx and fx[field] not in (None, "")) or \
                      (field == "value" and fx.get("val") not in (None, ""))
            if not warn(results, f"fx.{name}.{field}", present,
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
            # this field; absence leaves the change column blank. B.4
            # producer regen (dossier_macro + briefing_macro) now guarantees
            # every global region × indicator pair has a non-empty string
            # (real value or "N/A" sentinel). Upgraded from WARN to FAIL —
            # an empty value here means the producer pipeline regressed.
            has_change = (
                key in meta
                and isinstance(meta.get(key), dict)
                and isinstance(meta[key].get("change"), str)
                and bool(meta[key].get("change", "").strip())
            )
            if not check(results, f"global.{region}.indicatorMeta.{key}.change",
                         has_change,
                         f"Missing or empty indicatorMeta[{key}].change — movement signal will render blank"):
                fails += 1

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
    # B.4 producer regen closed the 4 empty enrichment metrics —
    # residential_permits / nonresidential_permits now sourced from
    # national_analysis_package narrative ($135.6M / -$1.3B, Feb 2026),
    # private_sector_change / public_sector_change carry "N/A" where
    # LFS sector split isn't in the dossier. All 12 keys must now hold a
    # non-empty string. Upgraded from WARN to FAIL.
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
    # Format gate (2026-06-11): these values render inside narrow numeric
    # table cells. The 2026-06-08 edition shipped deferral prose ("See CPI
    # April 2026 detail (StatCan 18-10-0004); category data pending in
    # dossier") which wrapped across ~10 lines per cell in production.
    # A value must LOOK like a data point: exactly "N/A" when the series
    # isn't available, or a short string (<=48 chars) containing a digit
    # (or a recognized qualitative print like "little changed (Apr)"),
    # with no deferral/reference language.
    _ENRICH_PROSE_RE = re.compile(
        r"(?i)\b(see|pending|per\s+statcan|release|detail|dossier|cited|"
        r"documented|narrative|awaiting|forthcoming|tbd)\b")
    _ENRICH_QUALITATIVE_RE = re.compile(r"(?i)^(little changed|unchanged|flat)\b")
    for key in ENRICHMENT_METRICS:
        val = m.get(key)
        present = isinstance(val, str) and bool(val.strip())
        if not check(results, f"metrics.{key}",
                     present,
                     f"Enrichment card metric missing/empty — producer tldr-analyst-macro "
                     f"(dossier_macro.national_analysis_package.metrics.{key}); "
                     f"renders em-dash fallback in _renderNatEnrichmentCards"):
            fails += 1
            continue
        v = val.strip()
        looks_like_data = v == "N/A" or (
            len(v) <= 48
            and not _ENRICH_PROSE_RE.search(v)
            and (re.search(r"\d", v) or _ENRICH_QUALITATIVE_RE.match(v))
        )
        if not check(results, f"metrics.{key}_format",
                     bool(looks_like_data),
                     f"Enrichment metric is prose/deferral text, not a data point "
                     f"({v[:70]!r}) — must be a short value like '+1.5%', "
                     f"'$8.2B (Feb)', or exactly 'N/A' when unavailable; it renders "
                     f"in a narrow table cell and prose wraps across many lines"):
            fails += 1

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

        # 9b. tradeExposure — B.4 producer regen closed this gap on all 13
        # regions (deterministic per-region sentence based on dominant
        # export mix / trading partner). Upgraded from WARN to FAIL.
        te = p.get("tradeExposure")
        te_ok = isinstance(te, str) and bool(te.strip())
        if not check(results, f"{plabel}.tradeExposure",
                    te_ok,
                    "Empty tradeExposure — B.4 producer regen should emit a non-empty "
                    "factual sentence (or the domestic-facing fallback) on every region"):
            fails += 1

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
        # B.4 producer regen closed this gap — territories now carry either
        # a real value (where LFS publishes) or the "N/A" sentinel. Upgraded
        # from WARN to FAIL.
        for key in PROV_IND_WARN_KEYS:
            val = inds.get(key)
            key_ok = isinstance(val, str) and bool(val.strip())
            if not check(results, f"{plabel}.indicators.{key}",
                        key_ok,
                        f"Empty indicator — B.4 regen should emit a non-empty string "
                        f"(real value or 'N/A' sentinel) on every region"):
                fails += 1
        # B.4 producer regen added wageGrowth across all 13 regions (national
        # SEPH proxy where provincial series unavailable). Upgraded to FAIL.
        for key in PROV_IND_GAP_KEYS:
            val = inds.get(key)
            key_ok = isinstance(val, str) and bool(val.strip())
            if not check(results, f"{plabel}.indicators.{key}",
                        key_ok,
                        f"Empty wageGrowth — B.4 regen should emit the national SEPH "
                        f"proxy or 'N/A' on every region"):
                fails += 1

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
                if not check(results, f"{plabel}.indicatorMeta.{key}.{sub}",
                            sub_ok,
                            f"Empty {sub} — B.4 regen should emit a non-empty string "
                            f"(real value or 'N/A' sentinel)"):
                    fails += 1

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
