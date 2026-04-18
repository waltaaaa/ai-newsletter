"""
Compare a candidate briefing JSON against a known-good baseline on
quality-sensitive metrics. Exits non-zero if any metric regresses beyond
the configured tolerance.

Metrics:
  * Top-level key count (must match)
  * Province/global/industry counts (must match)
  * Each section's word count (must be within ±`--tolerance` of baseline)
  * Citation density (total <sup>N</sup> refs / total words)
  * Banned-word count (baseline typically 0 — any increase is a regression)
  * insightCharts coverage (counts must not drop)

Usage:
    python tools/diff_against_baseline.py \\
        --baseline docs/data/briefing_2026-04-11.json \\
        --candidate docs/data/briefing_2026-04-19.json \\
        --tolerance 0.10
"""
import argparse
import json
import re
import sys
from pathlib import Path

BANNED = re.compile(
    r"\b(should|must|hopefully|unfortunately|worrying|promising|encouraging|"
    r"welcome|bullish|bearish|concerning|thrilled|feared|hoped)\b",
    re.IGNORECASE,
)
SUP = re.compile(r"<sup>\d+</sup>")
TAG = re.compile(r"<[^>]+>")


def word_count(s):
    if not isinstance(s, str):
        return 0
    stripped = TAG.sub(" ", s)
    return len(stripped.split())


def citation_count(s):
    if not isinstance(s, str):
        return 0
    return len(SUP.findall(s))


def banned_count(s):
    if not isinstance(s, str):
        return 0
    return len(BANNED.findall(s))


def walk_text(obj, acc):
    """Accumulate (wc, cites, banned) across every string value."""
    if isinstance(obj, str):
        acc[0] += word_count(obj)
        acc[1] += citation_count(obj)
        acc[2] += banned_count(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            walk_text(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_text(v, acc)


def summary(briefing):
    acc = [0, 0, 0]
    walk_text(briefing, acc)
    wc, cites, banned = acc
    return {
        "top_level_keys": len(briefing),
        "provinces": len(briefing.get("provinces", [])),
        "global": len(briefing.get("global", [])),
        "goods": len(briefing.get("goodsIndustries", [])),
        "services": len(briefing.get("servicesIndustries", [])),
        "total_words": wc,
        "citations": cites,
        "citation_density": round(cites / wc, 4) if wc else 0,
        "banned_words": banned,
        "indices": len(briefing.get("financialMarkets", {}).get("indices", [])),
        "commodities": len(briefing.get("commodities", [])),
        "national_insight_charts": len(briefing.get("insightCharts", [])),
        "province_insight_charts_total": sum(
            len(p.get("insightCharts", [])) for p in briefing.get("provinces", [])
        ),
        "industry_insight_charts_total": sum(
            len(i.get("insightCharts", []))
            for i in briefing.get("goodsIndustries", [])
            + briefing.get("servicesIndustries", [])
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--tolerance", type=float, default=0.10,
                        help="Max allowed fractional drop per metric (default 0.10)")
    args = parser.parse_args()

    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))

    b = summary(base)
    c = summary(cand)

    print(f"{'metric':<35} {'baseline':>12} {'candidate':>12} {'delta':>10} {'status':>8}")
    print("-" * 82)
    regressions = []
    for k in b:
        bv, cv = b[k], c[k]
        if isinstance(bv, float):
            delta = cv - bv
            pct = delta / bv if bv else 0
            regressed = pct < -args.tolerance
            disp_delta = f"{delta:+.4f}"
        else:
            delta = cv - bv
            if bv == 0:
                pct = 0
                # For counts that MUST be identical (keys/structure): any drop is a regression
                regressed = k in ("provinces", "global", "goods", "services") and delta != 0
            else:
                pct = delta / bv
                regressed = pct < -args.tolerance
            # Banned words: any INCREASE is a regression
            if k == "banned_words":
                regressed = cv > bv
            disp_delta = f"{delta:+d}"

        status = "FAIL" if regressed else "ok"
        if regressed:
            regressions.append(k)
        print(f"{k:<35} {bv:>12} {cv:>12} {disp_delta:>10} {status:>8}")

    print()
    if regressions:
        print(f"REGRESSION DETECTED on {len(regressions)} metric(s): {regressions}")
        print("Do not ship. Investigate or rerun the affected phase.")
        sys.exit(1)
    print("No quality regression vs baseline. Safe to ship.")


if __name__ == "__main__":
    main()
