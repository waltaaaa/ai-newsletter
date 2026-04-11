"""
indicator_validator.py — Ground-truth validation layer for economic indicators.

Runs post-collection, pre-display. Each indicator is checked against:
  1. Range check — value within plausible bounds for its class
  2. Delta check — period-over-period change within max threshold
  3. Null consistency — if VALUE is null, CHG must be null and vice versa
  4. Period recency — reference period within expected freshness window
  5. CHG recomputation — independently verify change matches current - previous
  6. Duplicate detection — flag identical value+change across unrelated indicators
  7. Unit verification — cross-check displayed unit against source expectations

On validation failure: indicator is flagged. The export layer replaces it with
"— (under review)" rather than showing a wrong number.

Usage:
    from indicator_validator import validate_indicators, ValidationResult

    results = validate_indicators(conn)
    for r in results:
        if not r.passed:
            print(f"FAIL: {r.indicator_name} — {r.failures}")
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION RULES — bounds, deltas, units per indicator class
# ═══════════════════════════════════════════════════════════════════════════════

# Canadian indicators — StatCan as ground truth
CANADIAN_RULES = {
    "participation_rate": {
        "range": (55.0, 75.0), "max_delta_pp": 2.0, "unit": "%",
        "frequency": "monthly", "source": "StatCan 14-10-0287",
    },
    "unemployment_rate": {
        "range": (3.0, 15.0), "max_delta_pp": 2.0, "unit": "%",
        "frequency": "monthly", "source": "StatCan 14-10-0287",
    },
    "employment_rate": {
        "range": (50.0, 70.0), "max_delta_pp": 2.0, "unit": "%",
        "frequency": "monthly", "source": "StatCan 14-10-0287",
    },
    "cpi_yoy": {
        "range": (-2.0, 12.0), "max_delta_pp": 3.0, "unit": "%",
        "frequency": "monthly", "source": "StatCan 18-10-0004",
    },
    "cpi": {
        "range": (-2.0, 12.0), "max_delta_pp": 3.0, "unit": "%",
        "frequency": "monthly", "source": "StatCan 18-10-0004",
    },
    # CPI index values (base period = 100) — stored separately from YoY%
    "cpi_national": {
        "range": (80.0, 250.0), "max_delta_pct": 5.0, "unit": "index",
        "frequency": "monthly",
    },
    "housing_starts": {
        "range": (100000, 400000), "max_delta_pct": 50.0, "unit": "SAAR",
        "frequency": "monthly", "source": "StatCan 34-10-0143",
    },
    # Extended table vectors return raw monthly counts (not SAAR)
    "housing_starts_total": {
        "range": (5000, 40000), "max_delta_pct": 50.0, "unit": "units",
        "frequency": "monthly", "source": "StatCan 34-10-0143",
    },
    "housing_starts_single": {
        "range": (1000, 15000), "max_delta_pct": 50.0, "unit": "units",
        "frequency": "monthly", "source": "StatCan 34-10-0143",
    },
    "housing_starts_multi": {
        "range": (3000, 30000), "max_delta_pct": 50.0, "unit": "units",
        "frequency": "monthly", "source": "StatCan 34-10-0143",
    },
    "gdp_yoy": {
        "range": (-10.0, 10.0), "max_delta_pp": 5.0, "unit": "%",
        "frequency": "quarterly", "source": "StatCan 36-10-0434",
    },
    "building_permits": {
        "range": (5000, 15000), "max_delta_pct": 40.0, "unit": "$M",
        "frequency": "monthly", "source": "StatCan 34-10-0066",
    },
    "boc_rate": {
        "range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%",
        "frequency": "scheduled", "source": "BoC",
    },
    "prime_rate": {
        "range": (0.0, 12.0), "max_delta_pp": 1.0, "unit": "%",
        "frequency": "scheduled", "source": "BoC",
    },
    "bond_yield_10y": {
        "range": (0.0, 8.0), "max_delta_pp": 1.5, "unit": "%",
        "frequency": "daily", "source": "BoC",
    },
}

# Province-level indicators — mixed storage formats
# CPI stored as YoY% for named provinces, as index for XX_cpi prefixed
# GDP stored as absolute $M for provinces, employment_rate as employment count (thousands)
PROVINCE_RULES = {
    "unemployment_rate": {"range": (2.0, 25.0), "max_delta_pp": 3.0, "unit": "%", "frequency": "monthly"},
    "unemployment": {"range": (2.0, 25.0), "max_delta_pp": 3.0, "unit": "%", "frequency": "monthly"},
    "participation_rate": {"range": (50.0, 80.0), "max_delta_pp": 3.0, "unit": "%", "frequency": "monthly"},
    "cpi": {"range": (-5.0, 15.0), "max_delta_pp": 4.0, "unit": "%", "frequency": "monthly"},
    "qc_cpi": {"range": (80.0, 250.0), "max_delta_pct": 5.0, "unit": "index", "frequency": "monthly"},
    "housing_starts": {"range": (0, 120000), "max_delta_pct": 60.0, "unit": "units", "frequency": "monthly"},
}

# Indicators that use absolute values (not rates) — excluded from province rate rules
# These store levels ($M, thousands) not percentages
ABSOLUTE_VALUE_INDICATORS = {
    "gdp", "gdp_date", "real_gdp", "nominal_gdp", "monthly_gdp",
    "gdp_goods", "gdp_services",
    "employment_rate",  # confusingly named — stores employment level in thousands at province level
    "nat_employment_rate", "nat_unemployment", "nat_participation_rate",  # national variants — rates not levels
    "employment", "exports", "imports", "retail_sales",
    "manufacturing_sales", "bldg_permits", "business_investment",
    "capital_investment", "real_consumption", "real_household",
    "real_capital_investment", "intl_exports", "intl_imports",
}

# International indicators
INTERNATIONAL_RULES = {
    # US
    "us_cpi": {"range": (-2.0, 15.0), "max_delta_pp": 3.0, "unit": "%"},
    "us_gdp": {"range": (-10.0, 15.0), "max_delta_pp": 5.0, "unit": "%"},
    "us_policy_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    "us_unemployment": {"range": (2.0, 15.0), "max_delta_pp": 2.0, "unit": "%"},
    "fed_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    # China
    "cn_cpi": {"range": (-3.0, 15.0), "max_delta_pp": 5.0, "unit": "%"},
    "cn_gdp": {"range": (-5.0, 20.0), "max_delta_pp": 5.0, "unit": "%"},
    "cn_policy_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    "cn_unemployment": {"range": (2.0, 15.0), "max_delta_pp": 5.0, "unit": "%"},
    "china_cpi": {"range": (-3.0, 15.0), "max_delta_pp": 5.0, "unit": "%"},
    "china_gdp": {"range": (-5.0, 20.0), "max_delta_pp": 5.0, "unit": "%"},
    # EU
    "eu_cpi": {"range": (-2.0, 15.0), "max_delta_pp": 3.0, "unit": "%"},
    "eu_gdp": {"range": (-10.0, 15.0), "max_delta_pp": 5.0, "unit": "%"},
    "eu_policy_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    "ecb_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    "eu_unemployment": {"range": (3.0, 15.0), "max_delta_pp": 2.0, "unit": "%"},
    # UK
    "uk_cpi": {"range": (-2.0, 15.0), "max_delta_pp": 3.0, "unit": "%"},
    "uk_gdp": {"range": (-10.0, 15.0), "max_delta_pp": 5.0, "unit": "%"},
    "uk_policy_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    "boe_rate": {"range": (0.0, 10.0), "max_delta_pp": 1.0, "unit": "%"},
    "uk_unemployment": {"range": (2.0, 15.0), "max_delta_pp": 2.0, "unit": "%"},
}

# Commodity rules — yfinance as ground truth
# Ranges are sized to absorb multi-year price swings; tighten only when you're
# willing to re-audit them every time a commodity prints a fresh cycle high/low.
COMMODITY_RULES = {
    "wti": {"range": (20.0, 150.0), "max_delta_pct": 25.0, "unit": "$/bbl"},
    "wti_crude": {"range": (20.0, 150.0), "max_delta_pct": 25.0, "unit": "$/bbl"},
    "brent": {"range": (20.0, 160.0), "max_delta_pct": 25.0, "unit": "$/bbl"},
    "gold": {"range": (1200.0, 6000.0), "max_delta_pct": 15.0, "unit": "$/oz"},
    "silver": {"range": (10.0, 120.0), "max_delta_pct": 20.0, "unit": "$/oz"},
    "platinum": {"range": (500.0, 2500.0), "max_delta_pct": 20.0, "unit": "$/oz"},
    "copper": {"range": (1.5, 8.0), "max_delta_pct": 20.0, "unit": "$/lb"},
    "aluminum": {"range": (1200.0, 5000.0), "max_delta_pct": 20.0, "unit": "$/t"},
    "rice": {"range": (10.0, 2000.0), "max_delta_pct": 30.0, "unit": "¢/cwt"},
    "lumber": {"range": (200.0, 1800.0), "max_delta_pct": 30.0, "unit": "$/mbf"},
    "natural_gas": {"range": (1.0, 15.0), "max_delta_pct": 40.0, "unit": "$/MMBtu"},
    "uranium": {"range": (20.0, 200.0), "max_delta_pct": 25.0, "unit": "$/lb"},
    "cameco_uranium": {"range": (20.0, 200.0), "max_delta_pct": 25.0, "unit": "$/lb"},
    "tin": {"range": (15000.0, 60000.0), "max_delta_pct": 20.0, "unit": "$/t"},
    "potash": {"range": (100.0, 1000.0), "max_delta_pct": 30.0, "unit": "$/t"},
    "iron_ore": {"range": (50.0, 250.0), "max_delta_pct": 25.0, "unit": "$/t"},
    "nickel": {"range": (10000.0, 50000.0), "max_delta_pct": 20.0, "unit": "$/t"},
    "zinc": {"range": (1500.0, 5000.0), "max_delta_pct": 20.0, "unit": "$/t"},
    "palladium": {"range": (500.0, 3000.0), "max_delta_pct": 20.0, "unit": "$/oz"},
    "soybean_oil": {"range": (20.0, 90.0), "max_delta_pct": 25.0, "unit": "¢/lb"},
}

# StatCan Extended indicators
EXTENDED_RULES = {
    "construction_employment": {"range": (800.0, 2000.0), "max_delta_pct": 10.0, "unit": "thousands"},
    "mining_og_employment": {"range": (100.0, 500.0), "max_delta_pct": 15.0, "unit": "thousands"},
    "manufacturing_employment": {"range": (200.0, 2500.0), "max_delta_pct": 10.0, "unit": "thousands"},
    "construction_vacancies": {"range": (10000, 200000), "max_delta_pct": 40.0, "unit": "count"},
    "mining_vacancies": {"range": (1000, 50000), "max_delta_pct": 40.0, "unit": "count"},
    "energy_exports": {"range": (5000.0, 25000.0), "max_delta_pct": 30.0, "unit": "$M"},
    "mineral_exports": {"range": (50.0, 5000.0), "max_delta_pct": 30.0, "unit": "$M"},
    "forestry_exports": {"range": (500.0, 5000.0), "max_delta_pct": 30.0, "unit": "$M"},
    "agri_exports": {"range": (2000.0, 10000.0), "max_delta_pct": 30.0, "unit": "$M"},
    # Investment (quarterly) — StatCan publishes 60-90 days after reference quarter
    "residential_building_investment": {"range": (10000.0, 60000.0), "max_delta_pct": 20.0, "unit": "$M", "frequency": "quarterly"},
    "non_residential_building_investment": {"range": (5000.0, 30000.0), "max_delta_pct": 20.0, "unit": "$M", "frequency": "quarterly"},
    "industrial_building_investment": {"range": (1000.0, 10000.0), "max_delta_pct": 25.0, "unit": "$M", "frequency": "quarterly"},
    "commercial_building_investment": {"range": (2000.0, 15000.0), "max_delta_pct": 25.0, "unit": "$M", "frequency": "quarterly"},
    "institutional_building_investment": {"range": (1000.0, 10000.0), "max_delta_pct": 25.0, "unit": "$M", "frequency": "quarterly"},
    # Capital expenditures (annual, intentions survey — Q1 release for current year)
    "total_capex": {"range": (200000.0, 500000.0), "max_delta_pct": 20.0, "unit": "$M", "frequency": "annual"},
    "construction_capex": {"range": (100000.0, 300000.0), "max_delta_pct": 20.0, "unit": "$M", "frequency": "annual"},
    "machinery_capex": {"range": (50000.0, 200000.0), "max_delta_pct": 20.0, "unit": "$M", "frequency": "annual"},
    # Housing price index (monthly)
    "new_housing_price_index": {"range": (80.0, 200.0), "max_delta_pct": 10.0, "unit": "index", "frequency": "monthly"},
    "construction_price_index_composite": {"range": (80.0, 250.0), "max_delta_pct": 10.0, "unit": "index", "frequency": "quarterly"},
}

# Frequency → max staleness in days (before doubling for publication lag).
# These are wall-clock tolerances from the row's reference period: StatCan
# usually publishes monthly series 60-90 days after the reference month and
# quarterly series 80-120 days after the reference quarter, so "stale" is the
# 2x-publication-lag threshold below.
FREQUENCY_STALENESS = {
    "daily": 14,       # commodities/markets: weekends + holidays
    "weekly": 21,
    "monthly": 75,     # → 150-day cutoff after the *2 publication-lag buffer
    "quarterly": 240,  # → 480-day cutoff for slow Capex / Investment tables
    "annual": 400,
    "scheduled": 120,  # BoC rate decisions, ~8 per year
}


def _is_absolute_value_indicator(name: str) -> bool:
    """Check if this indicator stores absolute values ($M, thousands) rather than rates."""
    name_lower = name.lower()
    # Strip province prefix
    stripped = name_lower
    if len(name_lower) > 3 and name_lower[2] == '_':
        stripped = name_lower[3:]
    elif len(name_lower) > 4 and name_lower[3] == '_':
        stripped = name_lower[4:]

    for abs_key in ABSOLUTE_VALUE_INDICATORS:
        if abs_key in stripped:
            return True
    return False


def _get_rules(indicator_name: str, province: str) -> dict | None:
    """Look up validation rules for an indicator, searching all rule sets."""
    name = indicator_name.lower().strip()

    # Skip absolute-value indicators that don't have explicit rules
    # (GDP in $M, employment counts, etc. — can't validate with rate ranges)
    if _is_absolute_value_indicator(name):
        # Only return rules if there's an EXACT match in a rule set
        for ruleset in (CANADIAN_RULES, EXTENDED_RULES):
            if name in ruleset:
                return ruleset[name]
        return None

    # Skip metadata fields stored as indicators (gdp_date, cpi_prev, etc.)
    if name.endswith("_date") or name.endswith("_prev"):
        return None

    # Province-prefixed indicators (e.g., AB_cpi, ON_unemployment) → province rules
    # Strip 2-3 letter province prefix for matching
    stripped_name = name
    _PROVINCE_PREFIXES = {"ab_", "bc_", "mb_", "nb_", "nl_", "ns_", "on_", "pe_", "qc_", "sk_", "yt_", "nt_", "nu_"}
    for pfx in _PROVINCE_PREFIXES:
        if name.startswith(pfx):
            stripped_name = name[len(pfx):]
            break

    # Province-prefixed CPI indicators store INDEX values, not YoY%
    _CPI_INDEX_RULE = {"range": (80.0, 250.0), "max_delta_pct": 5.0, "unit": "index", "frequency": "monthly"}
    if stripped_name != name and stripped_name == "cpi":
        return _CPI_INDEX_RULE
    # us_cpi_index is also an index
    if "cpi_index" in name:
        return {"range": (80.0, 400.0), "max_delta_pct": 5.0, "unit": "index", "frequency": "monthly"}

    # Province-level indicators (explicit province OR province-prefixed name)
    is_province = province and province not in ("National", "national", "global", "")
    if is_province:
        # CPI for named provinces (province=Alberta, etc.) stored as YoY%
        for key, rules in PROVINCE_RULES.items():
            if stripped_name == key or name == key:
                return rules
            if key in stripped_name:
                return rules
    # Also match province-prefixed national rows
    if stripped_name != name:
        for key, rules in PROVINCE_RULES.items():
            if stripped_name == key or key in stripped_name:
                return rules

    # International CPI values stored with province=country (e.g., "United States")
    # These are YoY percentages, not indices — use international rules
    if "global_cpi" in name or "global_gdp" in name:
        return None  # Skip — mixed storage format

    # Exact match in any rule set
    for ruleset in (CANADIAN_RULES, INTERNATIONAL_RULES, COMMODITY_RULES, EXTENDED_RULES):
        if name in ruleset:
            return ruleset[name]

    # Partial match — indicator_name contains a rule key
    for ruleset in (CANADIAN_RULES, INTERNATIONAL_RULES, COMMODITY_RULES, EXTENDED_RULES):
        for key, rules in ruleset.items():
            if key in name or name in key:
                return rules

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION RESULT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Result of validating a single indicator row."""
    indicator_name: str
    province: str
    period: str
    passed: bool = True
    failures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def fail(self, rule: str, detail: str):
        self.passed = False
        self.failures.append(f"[{rule}] {detail}")

    def warn(self, rule: str, detail: str):
        self.warnings.append(f"[{rule}] {detail}")


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(v) -> float | None:
    """Convert a value to float, stripping common formatting."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("+", "")
    # Strip trailing % or pp
    s = re.sub(r'[%]$', '', s).strip()
    s = re.sub(r'pp$', '', s).strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def check_range(result: ValidationResult, value: float, rules: dict):
    """Rule 1: Value within plausible range."""
    rng = rules.get("range")
    if not rng:
        return
    lo, hi = rng
    if value < lo or value > hi:
        result.fail("RANGE", f"value={value}, valid_range=[{lo}, {hi}]")


def check_delta(result: ValidationResult, change: float | None, rules: dict):
    """Rule 2: Period-over-period change within threshold."""
    if change is None:
        return
    max_pp = rules.get("max_delta_pp")
    max_pct = rules.get("max_delta_pct")

    if max_pp is not None and abs(change) > max_pp:
        result.fail("DELTA", f"change={change}pp, max_delta_pp=±{max_pp}")
    if max_pct is not None and abs(change) > max_pct:
        result.fail("DELTA", f"change={change}%, max_delta_pct=±{max_pct}")


def check_null_consistency(result: ValidationResult, value, change):
    """Rule 3: If VALUE is null, CHG must be null. If CHG present, VALUE required."""
    if value is None and change is not None:
        result.fail("NULL_CONSISTENCY", "change present but value is null")
    # Note: value present but change null is OK (first observation)


def check_period_recency(result: ValidationResult, period: str, frequency: str):
    """Rule 4: Period must be within expected freshness window."""
    if not period:
        result.warn("PERIOD_RECENCY", "no period set")
        return

    try:
        # Parse various date formats
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                dt = datetime.strptime(period[:len(fmt.replace('%', 'X').replace('X', 'XX'))], fmt)
                break
            except ValueError:
                continue
        else:
            # Try parsing just the first 10 chars
            dt = datetime.strptime(period[:10], "%Y-%m-%d")
    except (ValueError, IndexError):
        result.warn("PERIOD_RECENCY", f"unparseable period: {period}")
        return

    max_days = FREQUENCY_STALENESS.get(frequency, 120)  # default assumes monthly with buffer
    # Double the window to allow for publication lag
    staleness_threshold = max_days * 2
    age_days = (datetime.now() - dt).days

    if age_days > staleness_threshold:
        result.fail("PERIOD_RECENCY", f"period={period}, age={age_days}d, max={staleness_threshold}d for {frequency}")


def check_chg_recomputation(result: ValidationResult, value: float | None,
                            previous_value: float | None, stored_change: float | None):
    """Rule 5: Verify stored change matches current - previous."""
    if value is None or previous_value is None or stored_change is None:
        return  # Can't verify without both values
    if previous_value == 0:
        return  # Avoid division by zero

    # Recompute change as percentage
    recomputed = ((value - previous_value) / abs(previous_value)) * 100

    # Allow 0.15pp tolerance for rounding
    if abs(recomputed - stored_change) > 0.15:
        result.warn("CHG_VERIFY", f"stored={stored_change:.2f}%, recomputed={recomputed:.2f}%")


def check_unit(result: ValidationResult, stored_unit: str, expected_unit: str | None):
    """Rule 7: Cross-check stored unit against expected unit."""
    if not expected_unit or not stored_unit:
        return

    s = stored_unit.strip().lower()
    e = expected_unit.strip().lower()

    # Normalize common variations
    norm = {"percent": "%", "pct": "%", "percentage": "%", "pp": "%",
            "dollars": "$", "cad": "$", "usd": "$", "million": "$m",
            "bil": "$b", "billion": "$b", "index_2017=100": "index",
            "index_201612=100": "index"}
    s = norm.get(s, s)
    e = norm.get(e, e)

    if s != e and s not in e and e not in s:
        result.warn("UNIT", f"stored='{stored_unit}', expected='{expected_unit}'")


# ═══════════════════════════════════════════════════════════════════════════════
# DUPLICATE DETECTION (Rule 6)
# ═══════════════════════════════════════════════════════════════════════════════

def check_duplicates(results: list[ValidationResult], rows: list[dict]):
    """Rule 6: Flag identical value+change across unrelated indicators.

    If two different indicators in the SAME scope (National/same-province)
    have the exact same value AND change, that's a potential data mapping
    error (e.g., Soybean Oil = Palladium bug).

    Cross-province duplicates are expected (same unemployment rate across
    different storage keys) and are NOT flagged.
    """
    # Group by (province, value, change) → list of indicator names
    # Only compare within same province scope
    sig_map: dict[tuple, list[str]] = {}
    for row in rows:
        v = _safe_float(row.get("value"))
        c = _safe_float(row.get("change"))
        if v is None or c is None:
            continue
        prov = (row.get("province") or "National").lower()
        sig = (prov, round(v, 4), round(c, 4))
        name = row.get("indicator_name", "")
        if sig not in sig_map:
            sig_map[sig] = []
        sig_map[sig].append(name)

    # Only flag commodity/market duplicates — those are the real data mapping errors
    _COMMODITY_PREFIXES = {"comm_", "wti", "gold", "silver", "platinum", "copper",
                           "aluminum", "rice", "palladium", "soybean", "nickel",
                           "zinc", "iron", "lumber", "uranium", "natural_gas",
                           "brent", "coal", "corn", "wheat", "sugar", "cotton",
                           "cocoa", "idx_", "dax", "ftse", "nikkei"}

    for sig, names in sig_map.items():
        if len(names) < 2:
            continue
        # Only flag if at least one name looks like a commodity/market indicator
        has_commodity = any(
            any(n.lower().startswith(p) for p in _COMMODITY_PREFIXES)
            for n in names
        )
        if not has_commodity:
            continue
        # Skip if names are just aliases (e.g., "gold" and "comm_gold")
        base_names = {n.replace("comm_", "").replace("idx_", "") for n in names}
        if len(base_names) == 1:
            continue

        for r in results:
            if r.indicator_name in names:
                others = [n for n in names if n != r.indicator_name]
                if others:
                    r.warn("DUPLICATE", f"identical value+change as: {', '.join(others[:3])}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN VALIDATION ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def validate_indicators(conn) -> list[ValidationResult]:
    """Run all validation checks on the latest indicator values.

    Args:
        conn: SQLite connection (from db.get_db()).

    Returns:
        List of ValidationResult objects. Check .passed for each.
    """
    import sqlite3 as _sql

    old_rf = conn.row_factory
    conn.row_factory = _sql.Row

    # Get latest value per (indicator_name, province) pair.
    # "Latest" = most recent `period`, tie-broken by rowid. MAX(id) alone would
    # pick whichever row was INSERTED last, which lets an old backfill with an
    # earlier reference period shadow the real current value.
    rows = conn.execute("""
        SELECT * FROM (
            SELECT ih.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY indicator_name, province
                       ORDER BY period DESC, id DESC
                   ) AS _rn
            FROM indicator_history ih
        )
        WHERE _rn = 1
        ORDER BY indicator_name
    """).fetchall()

    conn.row_factory = old_rf

    row_dicts = [dict(r) for r in rows]
    results = []

    for row in row_dicts:
        indicator_name = row.get("indicator_name", "")
        province = row.get("province", "National")
        period = row.get("period", "")
        frequency = row.get("frequency", "")

        result = ValidationResult(
            indicator_name=indicator_name,
            province=province,
            period=period,
        )

        value = _safe_float(row.get("value"))
        change = _safe_float(row.get("change"))
        previous_value = _safe_float(row.get("previous_value"))
        stored_unit = row.get("unit", "")

        # Rule 3: Null consistency (always run)
        check_null_consistency(result, value, change)

        # Look up rules for this indicator
        rules = _get_rules(indicator_name, province)

        if rules and value is not None:
            # Rule 1: Range check
            check_range(result, value, rules)

            # Rule 2: Delta check
            check_delta(result, change, rules)

            # Rule 4: Period recency
            freq = frequency or rules.get("frequency", "")
            if freq:
                check_period_recency(result, period, freq)

            # Rule 5: CHG recomputation
            check_chg_recomputation(result, value, previous_value, change)

            # Rule 7: Unit check
            expected_unit = rules.get("unit")
            check_unit(result, stored_unit, expected_unit)

        results.append(result)

    # Rule 6: Duplicate detection (cross-indicator)
    check_duplicates(results, row_dicts)

    return results


def run_validation_report(conn, verbose: bool = False) -> dict:
    """Run validation and return a summary report dict.

    Args:
        conn: SQLite connection.
        verbose: If True, print detailed results.

    Returns:
        dict with keys: total, passed, failed, warnings, failures_list
    """
    results = validate_indicators(conn)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    with_warnings = sum(1 for r in results if r.warnings)

    failures_list = []
    for r in results:
        if not r.passed:
            failures_list.append({
                "indicator": r.indicator_name,
                "province": r.province,
                "period": r.period,
                "failures": r.failures,
                "warnings": r.warnings,
            })

    if verbose or failed > 0:
        print(f"\n[VALIDATION] {total} indicators checked: "
              f"{passed} passed, {failed} FAILED, {with_warnings} with warnings")
        for r in results:
            if not r.passed:
                print(f"  FAIL: {r.indicator_name} ({r.province}) — {'; '.join(r.failures)}")
            elif r.warnings and verbose:
                print(f"  WARN: {r.indicator_name} ({r.province}) — {'; '.join(r.warnings)}")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "warnings": with_warnings,
        "failures_list": failures_list,
    }


def get_failed_indicators(conn) -> set[tuple[str, str]]:
    """Return set of (indicator_name, province) pairs that failed validation.

    Used by the export layer to exclude or flag these indicators.
    """
    results = validate_indicators(conn)
    return {(r.indicator_name, r.province) for r in results if not r.passed}
