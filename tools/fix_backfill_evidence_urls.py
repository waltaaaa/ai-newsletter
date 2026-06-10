"""
fix_backfill_evidence_urls.py — One-shot remediation for bare domain-root evidence URLs.

Root cause (fixed in backfill_projects.py the same day): the --load path
reconstructed evidence from bare domain roots because the review CSV dropped
the parser's per-project source_url. Provincial EA scrapers left a smaller
cohort of bare-root links the same way.

This tool rewrites bare-root evidence URLs (path '' or '/', no query) to the
source's actual registry/inventory listing page — a strict same-source upgrade.
Domains without a known listing page are reported, never touched. URL counts
per row never change, so the evidence-merge invariant is untouched.

Every change is logged to .audit/backfill_url_fix_<date>.jsonl for surgical
rollback. Dry-run by default; pass --apply to write.

Usage:
    .venv\\Scripts\\python.exe tools\\fix_backfill_evidence_urls.py          # dry run
    .venv\\Scripts\\python.exe tools\\fix_backfill_evidence_urls.py --apply
"""

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from url_utils import best_link_quality  # noqa: E402

DB_PATH = ROOT / "dashboard.db"
AUDIT_DIR = ROOT / ".audit"

# Bare domain root -> the source's actual listing/inventory page.
# Same-source upgrades only; do not guess pages for unmapped domains.
ROOT_URL_REPLACEMENTS = {
    "publications.saskatchewan.ca": (
        "https://www.saskatchewan.ca/business/environmental-protection-and-sustainability/"
        "environmental-assessment/environmental-assessment-projects"
    ),
    "www2.gnb.ca": (
        "https://www.gnb.ca/en/topic/environment-resources/"
        "environmental-assessment/projects/current.html"
    ),
    "www.infrastructure.gc.ca": "https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html",
    "natural-resources.canada.ca": (
        "https://natural-resources.canada.ca/energy/energy-sources-distribution/"
        "canadian-energy-resource-development/major-projects-inventory/18702"
    ),
    "www2.gov.bc.ca": (
        "https://www2.gov.bc.ca/gov/content/employment-business/economic-development/"
        "industry/bc-major-projects-inventory"
    ),
    "www.quebec.ca": (
        "https://www.quebec.ca/gouvernement/politiques-orientations/"
        "plan-quebecois-infrastructures"
    ),
    "www.gov.mb.ca": "https://www.gov.mb.ca/sd/eal/registries/",
    # majorprojects.alberta.ca intentionally absent: its domain root IS the
    # program inventory page, so a bare root there is already the listing.
}


def is_bare_root(url):
    if not url or not url.startswith("http"):
        return False
    p = urlparse(url)
    return p.path in ("", "/") and not p.query and not p.fragment


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = parser.parse_args()

    import db

    conn = db.init_db()
    conn.row_factory = None
    rows = conn.execute(
        "SELECT norm_key, name, evidence, source_url_quality FROM projects"
    ).fetchall()

    AUDIT_DIR.mkdir(exist_ok=True)
    audit_path = AUDIT_DIR / f"backfill_url_fix_{date.today():%Y%m%d}.jsonl"

    changed_rows = 0
    changed_urls = 0
    unmapped = Counter()
    audit_records = []

    for norm_key, name, evidence_json, old_quality in rows:
        try:
            evidence = json.loads(evidence_json or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(evidence, list):
            continue

        row_changes = []
        for entry in evidence:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url") or ""
            if not is_bare_root(url):
                continue
            domain = urlparse(url).netloc.lower()
            replacement = ROOT_URL_REPLACEMENTS.get(domain)
            if not replacement:
                unmapped[domain] += 1
                continue
            row_changes.append({"old_url": url, "new_url": replacement})
            entry["url"] = replacement

        if not row_changes:
            continue

        changed_rows += 1
        changed_urls += len(row_changes)
        new_quality = best_link_quality(
            [e.get("url") for e in evidence if isinstance(e, dict) and e.get("url")]
        )
        audit_records.append({
            "norm_key": norm_key,
            "name": name,
            "changes": row_changes,
            "source_url_quality": {"old": old_quality, "new": new_quality},
        })

        if args.apply:
            conn.execute(
                "UPDATE projects SET evidence = ?, source_url_quality = ? WHERE norm_key = ?",
                (json.dumps(evidence, ensure_ascii=False), new_quality, norm_key),
            )

    if args.apply:
        with open(audit_path, "a", encoding="utf-8") as f:
            for rec in audit_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        conn.commit()

    conn.close()

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] {changed_rows} rows / {changed_urls} bare-root URLs rewritten")
    if args.apply:
        print(f"Audit log: {audit_path}")
    for rec in audit_records[:10]:
        for ch in rec["changes"]:
            print(f"  {rec['norm_key']}: {ch['old_url']} -> {ch['new_url']}")
    if len(audit_records) > 10:
        print(f"  ... and {len(audit_records) - 10} more rows")
    if unmapped:
        print("Unmapped bare-root domains (left untouched):")
        for dom, n in unmapped.most_common():
            print(f"  {dom}: {n}")


if __name__ == "__main__":
    main()
