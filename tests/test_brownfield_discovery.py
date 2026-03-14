"""
test_brownfield_discovery.py — Integration test with live Gemini API.
STEP_2D: Validates that known brownfield projects are discoverable
by relevant compound queries.

Requires: GEMINI_API_KEY environment variable set.
Run with: python test_brownfield_discovery.py
"""

import asyncio
import os
import sys
from compound_queries import load_queries

# Known brownfield projects that MUST be discoverable
KNOWN_PROJECTS = [
    {"name": "Portage Place", "province": "MB",
     "sector_hints": ["healthcare", "residential", "commercial_mixed"]},
    {"name": "Ontario Place", "province": "ON",
     "sector_hints": ["commercial_mixed", "tourism_culture"]},
    {"name": "Cogswell", "province": "NS",
     "sector_hints": ["infrastructure", "commercial_mixed"]},
    {"name": "Calgary Event Centre", "province": "AB",
     "sector_hints": ["commercial_mixed", "tourism_culture"]},
    {"name": "LeBreton Flats", "province": "ON",
     "sector_hints": ["commercial_mixed", "residential"]},
]


async def test_known_project_discovery():
    """Test that known brownfield projects are found by relevant compound queries."""
    import aiohttp
    # compound_discovery removed (STEP_2Q) — test needs rewrite for google_news_rss_search
    print("  [SKIP] compound_discovery removed — test disabled")
    return 0
    from compound_discovery import _query_gemini  # noqa: unreachable

    if not os.environ.get("GEMINI_API_KEY"):
        print("  [SKIP] No GEMINI_API_KEY set -- skipping live test")
        return 0

    queries = load_queries()
    found_count = 0

    for known in KNOWN_PROJECTS:
        # Find queries most likely to discover this project
        relevant = [q for q in queries
                    if q.get("province") == known["province"]
                    and any(h in (q.get("sector") or "") for h in known["sector_hints"])]

        print(f"\n  Testing: {known['name']} ({known['province']})")
        print(f"    Relevant queries: {len(relevant)}")

        if not relevant:
            print(f"    [SKIP] No relevant queries found")
            continue

        # Test with first relevant query only (to save API calls)
        test_query = relevant[0]
        print(f"    Running query: [{test_query['sector']}]...")

        semaphore = asyncio.Semaphore(1)
        try:
            async with aiohttp.ClientSession() as session:
                result = await _query_gemini(session, semaphore, test_query)

            projects = result.get("projects", [])
            found = any(known["name"].lower() in p.get("name", "").lower()
                       for p in projects)

            if found:
                found_count += 1
                print(f"    [PASS] Found! ({len(projects)} projects in response)")
            else:
                names = [p.get("name", "?") for p in projects[:5]]
                print(f"    [WARN] Not in this response ({len(projects)} projects)")
                print(f"    Names: {names}")
        except Exception as e:
            print(f"    [ERROR] {type(e).__name__}: {e}")

    total = len(KNOWN_PROJECTS)
    print(f"\n  {'=' * 60}")
    print(f"  BROWNFIELD DISCOVERY: {found_count}/{total} known projects found")
    if found_count >= 3:
        print(f"  PASS (>= 3/5 threshold)")
    else:
        print(f"  WARN (< 3/5 threshold -- may need more query variants)")
    print(f"  {'=' * 60}")
    return found_count


def test_query_coverage_for_brownfield():
    """Verify that compound queries exist for known brownfield project locations."""
    queries = load_queries()
    print("\n  Query coverage for known brownfield projects:")

    for known in KNOWN_PROJECTS:
        matching = [q for q in queries if q.get("province") == known["province"]]
        sector_matches = [q for q in matching
                         if any(h in (q.get("sector") or "") for h in known["sector_hints"])]
        lifecycle = [q for q in matching if "lifecycle" in (q.get("sector") or "")]

        total = len(sector_matches) + len(lifecycle)
        icon = "PASS" if total >= 2 else "WARN"
        print(f"    [{icon}] {known['name']} ({known['province']}): "
              f"{len(sector_matches)} sector + {len(lifecycle)} lifecycle = {total} queries")


if __name__ == "__main__":
    # Non-API test first
    test_query_coverage_for_brownfield()

    # Live API test (if key available)
    if os.environ.get("GEMINI_API_KEY"):
        print("\n  Running live Gemini discovery test...")
        asyncio.run(test_known_project_discovery())
    else:
        print("\n  [SKIP] Set GEMINI_API_KEY to run live discovery test")
