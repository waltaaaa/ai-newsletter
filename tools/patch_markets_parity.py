"""
Bring docs/data/briefing_latest.json to demo parity for financialMarkets.indices
and commodities[].

Strategy:
- For items that exist in both (by canonical name): keep LIVE's richer entry
  (fresh values, commentary, week_of, etc.), rename to match demo's canonical
  name so the UI labels are identical.
- For items in demo but not live: append demo's entry verbatim (frozen Apr 10
  values) so the count/shape matches.

Demo source: docs/demo/data/briefing_latest.json (commit 2a28c82, frozen Apr 10).
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
LIVE = ROOT / "docs/data/briefing_latest.json"
DEMO = ROOT / "docs/demo/data/briefing_latest.json"

# Live name -> Demo canonical name
INDEX_RENAME = {
    "TSX Composite": "S&P/TSX Composite",
    "DJIA": "Dow Jones",
    "Nasdaq Composite": "NASDAQ Composite",
}

COMMODITY_RENAME = {
    "WTI Crude Oil": "WTI Crude",
    "Sugar": "Sugar #11",
    "Potash (Nutrien proxy)": "Potash (Nutrien NTR)",
    "Uranium (Sprott proxy)": "Uranium (Sprott URA ETF)",
    "Iron Ore": "Iron Ore (TSI 62% Fe)",
}


def patch_list(live_list, demo_list, key_field, rename_map):
    # Rename live entries to match demo canonical names
    for item in live_list:
        n = item.get(key_field)
        if n in rename_map:
            item[key_field] = rename_map[n]
    live_names = {item.get(key_field) for item in live_list}
    added = []
    for demo_item in demo_list:
        n = demo_item.get(key_field)
        if n not in live_names:
            live_list.append(demo_item)
            added.append(n)
    return added


def main():
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    demo = json.loads(DEMO.read_text(encoding="utf-8"))

    # Indices
    live_idx = live.setdefault("financialMarkets", {}).setdefault("indices", [])
    demo_idx = demo.get("financialMarkets", {}).get("indices", [])
    idx_before = len(live_idx)
    idx_added = patch_list(live_idx, demo_idx, "name", INDEX_RENAME)
    print(f"Indices: {idx_before} -> {len(live_idx)}. Added: {idx_added}")

    # Commodities
    live_com = live.setdefault("commodities", [])
    demo_com = demo.get("commodities", [])
    com_before = len(live_com)
    com_added = patch_list(live_com, demo_com, "name", COMMODITY_RENAME)
    print(f"Commodities: {com_before} -> {len(live_com)}. Added ({len(com_added)}): {com_added}")

    LIVE.write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {LIVE}")


if __name__ == "__main__":
    main()
