"""Repair two post-ship issues found in the live site:

1. U+FFFD (?) replacement characters across briefing/dossier files — mojibake from
   an em-dash and an o-circumflex that got corrupted in a prior write path.
2. Blank metrics._chg strings on cadUsd and tsx that render as empty KPI cells.

Also walks all siblings in docs/data/ that ship to GitHub Pages so the fix is
consistent everywhere.
"""
import json
import os
import glob
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "docs", "data")

# Substitutions (order matters — run Côte first so the C\uFFFDte form is handled
# before the generic em-dash replacement hits the same char).
SUBS = [
    ("C\uFFFDte", "Côte"),     # Côte-Nord, Québec
    ("\uFFFD", "\u2014"),      # everything else — was em-dash
]


def patch_text(s: str) -> tuple[str, int]:
    total = 0
    for bad, good in SUBS:
        count = s.count(bad)
        if count:
            s = s.replace(bad, good)
            total += count
    return s, total


def fix_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    patched, mojibake_fixed = patch_text(raw)
    # If this is a briefing-shape JSON, also repair blank _chg fields
    chg_filled = 0
    try:
        obj = json.loads(patched)
    except json.JSONDecodeError:
        if mojibake_fixed:
            with open(path, "w", encoding="utf-8") as f:
                f.write(patched)
        return {"path": path, "mojibake": mojibake_fixed, "chg": 0, "json": False}

    if isinstance(obj, dict) and isinstance(obj.get("metrics"), dict):
        metrics = obj["metrics"]
        # Source: top-level key_indicators has authoritative change text for most row
        ki = obj.get("key_indicators") or []
        name_to_change = {}
        for row in ki:
            if isinstance(row, dict):
                name = (row.get("label") or row.get("name") or row.get("indicator") or "").strip().upper()
                chg = (row.get("change") or "").strip()
                if name and chg:
                    name_to_change[name] = chg
        # Map metric keys → key_indicators names
        KI_MAP = {
            "cadUsd_chg": "CAD/USD",
            "tsx_chg": "TSX",
        }
        for mkey, kiname in KI_MAP.items():
            cur = metrics.get(mkey, "")
            if (not cur) or (isinstance(cur, str) and not cur.strip()):
                src = name_to_change.get(kiname.upper())
                if src:
                    metrics[mkey] = src
                    chg_filled += 1

    patched2 = json.dumps(obj, indent=2, ensure_ascii=False)
    if patched2 != raw:
        with open(path, "w", encoding="utf-8") as f:
            f.write(patched2)
    return {"path": path, "mojibake": mojibake_fixed, "chg": chg_filled, "json": True}


def main():
    targets = []
    # Briefing-shape files
    for fn in ("briefing_latest.json", "briefing_2026-04-18.json",
               "briefing_macro.json", "briefing_provinces.json",
               "briefing_goods.json", "briefing_services.json",
               "briefing_market_commentary.json", "briefing_market_equities.json",
               "briefing_market_fx_yields.json", "briefing_market_commodities.json",
               "dossier_macro.json", "dossier_provinces.json",
               "dossier_industries.json"):
        p = os.path.join(DATA, fn)
        if os.path.exists(p):
            targets.append(p)

    totals = {"mojibake": 0, "chg": 0, "files_touched": 0}
    for p in targets:
        r = fix_file(p)
        if r["mojibake"] or r["chg"]:
            totals["files_touched"] += 1
            totals["mojibake"] += r["mojibake"]
            totals["chg"] += r["chg"]
            print(f"  {os.path.basename(p):<40} mojibake={r['mojibake']:<3} chg_filled={r['chg']}")
        else:
            print(f"  {os.path.basename(p):<40} clean")

    print()
    print(f"Total mojibake chars replaced: {totals['mojibake']}")
    print(f"Total blank _chg fields filled: {totals['chg']}")
    print(f"Files modified: {totals['files_touched']}")

    # DB-sync briefing_latest -> dashboard_state.newsletter_latest
    try:
        sys.path.insert(0, ROOT)
        from db import get_db, save_dashboard_state
        with open(os.path.join(DATA, "briefing_latest.json"), "r", encoding="utf-8") as f:
            payload = json.load(f)
        conn = get_db()
        save_dashboard_state(conn, "newsletter_latest", payload)
        wk = payload.get("week_of")
        if wk:
            save_dashboard_state(conn, f"newsletter_{wk}", payload)
        print("\nDB-sync: newsletter_latest updated")
    except Exception as e:
        print(f"\nDB-sync skipped: {e}")


if __name__ == "__main__":
    main()
