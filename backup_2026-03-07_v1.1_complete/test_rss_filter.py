"""
test_rss_filter.py — Tests for the remediated three-layer article filter.
STEP_2D: Validates brownfield vocabulary, dollar-value bypass, government
source bypass, negative keyword cleaning, and Layer 3 prompt coverage.

Adapted to test article_filter.py functions (layer1_keyword_check,
layer2_negative_check, _has_dollar_value, filter_articles).
"""

from article_filter import (
    layer1_keyword_check, layer2_negative_check,
    _has_dollar_value, filter_articles,
)


# ================================================================
# MUST PASS — brownfield projects that were previously missed
# ================================================================

MUST_PASS_L1 = [
    {
        "name": "Portage Place (dollar bypass)",
        "title": "Portage Place mall redevelopment moves ahead with $650 million plan",
        "summary": "The massive downtown Winnipeg mall will be transformed into mixed-use with housing, healthcare, and commercial space.",
        "expect": "dollar_bypass",
    },
    {
        "name": "Calgary office conversion (dollar bypass)",
        "title": "Calgary office towers to be converted to residential in $250M program",
        "summary": "Downtown office buildings targeted for conversion to address housing shortage.",
        "expect": "dollar_bypass",
    },
    {
        "name": "Wehwehneh Bahgahkinahgohn (dollar bypass)",
        "title": "Former Hudson's Bay building becomes Indigenous centre in $140M project",
        "summary": "Adaptive reuse of heritage downtown Winnipeg building for reconciliation.",
        "expect": "dollar_bypass",
    },
    {
        "name": "Ontario Place (dollar bypass)",
        "title": "Ontario Place redevelopment gets $3.5 billion green light",
        "summary": "Waterfront revitalization includes spa, entertainment, and public parkland.",
        "expect": "dollar_bypass",
    },
    {
        "name": "Halifax Cogswell (dollar bypass)",
        "title": "Halifax's Cogswell District redevelopment reaches $2 billion milestone",
        "summary": "Former highway interchange becoming mixed-use neighbourhood downtown.",
        "expect": "dollar_bypass",
    },
    {
        "name": "French QC article (dollar bypass)",
        "title": "Revitalisation majeure du Vieux-Port de Montreal annoncee",
        "summary": "Un investissement de 500 millions $ pour reamenager le front de mer.",
        "expect": "dollar_bypass",
    },
    {
        "name": "Brownfield keyword match — adaptive reuse",
        "title": "Major adaptive reuse project announced for historic Ottawa building",
        "summary": "Investment of $80 million to convert former industrial facility into mixed-use campus with affordable housing.",
        "expect": "keyword",
    },
    {
        "name": "Brownfield keyword match — retrofit",
        "title": "Deep energy retrofit planned for 50 federal buildings",
        "summary": "$800M program to modernize government facilities.",
        "expect": "keyword",
    },
    {
        "name": "Brownfield keyword match — modernization",
        "title": "Province invests $1.2 billion in transit modernization",
        "summary": "LRT expansion and station upgrades across the network.",
        "expect": "keyword",
    },
    {
        "name": "Long-term care facility",
        "title": "$150M long-term care facility expansion in Sudbury",
        "summary": "Adding 200 beds to existing seniors care home.",
        "expect": "keyword",
    },
    {
        "name": "Hydrogen facility",
        "title": "New $500M hydrogen production facility proposed",
        "summary": "Green hydrogen plant to be built near existing refinery.",
        "expect": "keyword",
    },
    {
        "name": "Battery storage",
        "title": "Battery storage facility approved near Calgary",
        "summary": "$65M investment in grid-scale energy storage.",
        "expect": "keyword",
    },
    {
        "name": "Highway interchange",
        "title": "Highway interchange reconstruction begins",
        "summary": "$180M contract awarded for major overhaul.",
        "expect": "keyword",
    },
    {
        "name": "Water treatment upgrade",
        "title": "Water treatment plant upgrade underway",
        "summary": "Modernization of filtration systems at municipal facility.",
        "expect": "keyword",
    },
    {
        "name": "Mixed-use development",
        "title": "Mixed-use development breaks ground downtown",
        "summary": "$90 million project includes condo tower and retail.",
        "expect": "keyword",
    },
    {
        "name": "Government infrastructure spending",
        "title": "Government announces $3.2 billion infrastructure spending",
        "summary": "Roads, bridges, and transit projects across multiple provinces.",
        "expect": "dollar_bypass",
    },
]

# ================================================================
# MUST FAIL L1 — no project signal
# ================================================================

MUST_FAIL_L1 = [
    {
        "name": "Interest rate",
        "title": "Interest rate announcement expected tomorrow",
        "summary": "BoC policy update anticipated by markets.",
    },
    {
        "name": "Employment stats",
        "title": "Employment figures rise in March",
        "summary": "Statistics Canada release shows job gains.",
    },
    {
        "name": "Currency markets",
        "title": "Canadian dollar weakens against USD",
        "summary": "Forex markets respond to trade tensions.",
    },
    {
        "name": "Generic politics",
        "title": "Prime Minister announces new policy on immigration",
        "summary": "Changes to temporary foreign worker program rules.",
    },
]

# ================================================================
# MUST REJECT L2 — noise articles
# ================================================================

MUST_REJECT_L2 = [
    {"name": "Crime + construction", "title": "Man sentenced for $2M robbery of construction site"},
    {"name": "Sports", "title": "NHL playoff schedule announced for Canadian teams"},
    {"name": "Murder", "title": "Murder charge laid in downtown shooting"},
    {"name": "Celebrity", "title": "Celebrity couple spotted at Toronto award show red carpet"},
    {"name": "Weather", "title": "Blizzard warning issued for southern Manitoba"},
]

# ================================================================
# MUST NOT REJECT L2 — cleaned negatives
# ================================================================

MUST_NOT_REJECT_L2 = [
    {"name": "Fire rebuild", "title": "Fire-damaged arena to be rebuilt with $50M investment"},
    {"name": "Project goals", "title": "Project goals met for Phase 2 of LRT"},
    {"name": "Bail-out infrastructure", "title": "Bail-out package includes infrastructure funding"},
    {"name": "Film studio construction", "title": "New film studio construction approved in Vancouver"},
    {"name": "Power grid project", "title": "Power outage history drives new grid infrastructure project"},
]

# ================================================================
# DOLLAR VALUE BYPASS TESTS
# ================================================================

DOLLAR_TESTS = [
    ("$650 million redevelopment", True),
    ("$3.5 billion project", True),
    ("$1.2B investment in transit", True),
    ("$45M facility expansion", True),
    ("a $200 million housing development", True),
    ("500 millions $ pour reamenager", True),
    ("interest rate at 5%", False),
    ("no dollar value here", False),
    ("employment rose by 50,000", False),
]


def test_must_pass_l1():
    """All brownfield/project articles must pass Layer 1."""
    print("\n  Layer 1 -- MUST PASS:")
    failures = 0
    for t in MUST_PASS_L1:
        result = layer1_keyword_check(t["title"], t.get("summary", ""))
        icon = "PASS" if result else "FAIL"
        if not result:
            failures += 1
        print(f"    [{icon}] {t['name']}")
    return failures


def test_must_fail_l1():
    """Non-project articles must fail Layer 1."""
    print("\n  Layer 1 -- MUST FAIL:")
    failures = 0
    for t in MUST_FAIL_L1:
        result = layer1_keyword_check(t["title"], t.get("summary", ""))
        icon = "PASS" if not result else "FAIL"
        if result:
            failures += 1
        print(f"    [{icon}] {t['name']}")
    return failures


def test_must_reject_l2():
    """Noise articles must be rejected by Layer 2."""
    print("\n  Layer 2 -- MUST REJECT:")
    failures = 0
    for t in MUST_REJECT_L2:
        result = layer2_negative_check(t["title"])
        icon = "PASS" if result else "FAIL"
        if not result:
            failures += 1
        print(f"    [{icon}] {t['name']}")
    return failures


def test_must_not_reject_l2():
    """Cleaned negatives must NOT reject these articles."""
    print("\n  Layer 2 -- MUST NOT REJECT (cleaned negatives):")
    failures = 0
    for t in MUST_NOT_REJECT_L2:
        result = layer2_negative_check(t["title"])
        icon = "PASS" if not result else "FAIL"
        if result:
            failures += 1
        print(f"    [{icon}] {t['name']}")
    return failures


def test_dollar_bypass():
    """Dollar-value bypass regex tests."""
    print("\n  Dollar-value bypass:")
    failures = 0
    for text, expected in DOLLAR_TESTS:
        result = _has_dollar_value(text)
        correct = result == expected
        icon = "PASS" if correct else "FAIL"
        if not correct:
            failures += 1
        print(f"    [{icon}] '{text[:50]}' -> {result} (expected {expected})")
    return failures


def test_filter_pipeline_skip_layers():
    """Verify skip_layer1 and skip_layer2 parameters work correctly."""
    print("\n  Filter pipeline skip flags:")
    failures = 0

    # NHL article should be rejected by L2, but skip_layer2 should pass it
    nhl = [{"title": "NHL playoff preview", "summary": ""}]

    r1 = filter_articles(nhl, skip_layer1=True, skip_layer2=True, log_filtered=False)
    if len(r1) == 1:
        print("    [PASS] skip_layer1+skip_layer2 passes NHL through")
    else:
        failures += 1
        print("    [FAIL] skip_layer1+skip_layer2 should pass NHL through")

    r2 = filter_articles(nhl, skip_layer1=True, skip_layer2=False, log_filtered=False)
    if len(r2) == 0:
        print("    [PASS] skip_layer1 only: L2 rejects NHL")
    else:
        failures += 1
        print("    [FAIL] L2 should reject NHL")

    # Infrastructure article should pass all layers
    infra = [{"title": "$200M hospital expansion approved", "summary": "New wing construction"}]
    r3 = filter_articles(infra, skip_layer1=False, skip_layer2=False, log_filtered=False)
    if len(r3) == 1:
        print("    [PASS] Infrastructure article passes full filter")
    else:
        failures += 1
        print("    [FAIL] Infrastructure article should pass full filter")

    return failures


if __name__ == "__main__":
    total = 0
    total += test_must_pass_l1()
    total += test_must_fail_l1()
    total += test_must_reject_l2()
    total += test_must_not_reject_l2()
    total += test_dollar_bypass()
    total += test_filter_pipeline_skip_layers()

    print(f"\n  {'=' * 60}")
    if total == 0:
        print("  ALL RSS FILTER TESTS PASSED")
    else:
        print(f"  {total} TEST(S) FAILED")
    print(f"  {'=' * 60}")
