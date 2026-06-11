"""Rebuild docs/data/briefing_archive.json from dated briefing files that are
actually present (tracked in git + on live CDN). The frontend's edition
dropdown reads this file; stale entries pointing to missing files cause 404s,
and missing entries hide editions that actually exist on disk.

Only includes dated briefings that are tracked in git (so they ship to Pages).
Sorted newest first.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "docs", "data")


def tracked_dated_briefings():
    out = subprocess.check_output(
        ["git", "-C", ROOT, "ls-files", "docs/data/briefing_2*.json"],
        text=True,
    ).strip().splitlines()
    # Filter out _backup / corrupt / bak variants
    return [p for p in out if "_backup" not in p and "_corrupt" not in p and ".bak" not in p]


def summarize(path):
    with open(path, "r", encoding="utf-8") as f:
        p = json.load(f)
    headline = p.get("headline") or p.get("title") or ""
    import re
    exec_html = p.get("executive_summary") or ""
    text = re.sub(r"<[^>]+>", " ", exec_html)
    wc = len(text.split())
    # file_date = the date in the actual filename (briefing_<file_date>.json).
    # This is the id the frontend must fetch by; week_of can differ from it
    # (week_of is editorial, the filename uses the generation date), which
    # otherwise 404s the edition and silently falls back to "latest".
    file_date = ""
    m = re.search(r"briefing_(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    if m:
        file_date = m.group(1)
    week_of = p.get("week_of") or file_date
    return {
        "week_of": week_of or "",
        "file_date": file_date,
        "headline": headline,
        "word_count": wc,
        "generated_at": p.get("generated_at") or p.get("updated_at") or "",
    }


def main():
    force = "--force" in sys.argv

    files = tracked_dated_briefings()
    print(f"tracked dated briefings: {len(files)}")
    entries = []
    for rel in files:
        full = os.path.join(ROOT, rel)
        if not os.path.exists(full):
            continue
        try:
            entries.append(summarize(full))
        except Exception as e:
            print(f"  skip {rel}: {e}")

    # Editions are APPEND-ONLY (the 2026-06-08 incident collapsed the dropdown
    # to one entry). Merge with the existing archive so entries that can't be
    # re-derived from dated files are preserved, and refuse to shrink the
    # archive without --force.
    out = os.path.join(DATA, "briefing_archive.json")
    by_week = {e["week_of"]: e for e in entries if e.get("week_of")}
    prior = []
    try:
        with open(out, "r", encoding="utf-8") as f:
            prior = json.load(f) or []
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        prior = []
    for e in prior:
        wk = (e or {}).get("week_of", "")
        if wk and wk not in by_week:
            print(f"  preserving existing entry not re-derivable from files: {wk}")
            by_week[wk] = e

    merged = sorted(by_week.values(), key=lambda e: e.get("week_of") or "", reverse=True)
    if len(merged) < len(prior) and not force:
        print(f"REFUSING to shrink archive {len(prior)} -> {len(merged)} "
              f"(pass --force to override)")
        sys.exit(1)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"\nwrote {out} with {len(merged)} entries:")
    for e in merged:
        print(f"  {e['week_of']} — {(e.get('headline') or '')[:70]!r} ({e.get('word_count', 0)}w)")


if __name__ == "__main__":
    main()
