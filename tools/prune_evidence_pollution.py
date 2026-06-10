# -*- coding: utf-8 -*-
"""Prune polluted evidence arrays (>20 URLs) left by a May 2026 RSS batch dump.

Keep rules, per row:
  1. ALWAYS keep government/registry entries (authority/source_type/gov domain).
  2. Keep on-topic entries: score > 0 against the project's name tokens
     (scoring reused from reorder_evidence_urls.py).
  3. Cap kept entries at --cap (default 15), ordered score-desc so evidence[0]
     stays the best deep link.
  4. Floor: never below 1 entry (URL hard gate). If nothing scores > 0, keep
     the top --min-keep (default 3) by score.

Every removed entry is written in full to .audit/evidence_prune_<date>.jsonl —
URLs are preserved there, not destroyed. The "evidence merge never loses URLs"
invariant governs PIPELINE merges; this tool is operator-approved remediation
outside the merge path, with complete recovery via the audit sidecar.

Dry-run by default; --apply commits. Also updates evidence_count and
source_url_quality on changed rows.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.reorder_evidence_urls import name_tokens, score  # noqa: E402
from url_utils import best_link_quality  # noqa: E402

AUDIT_DIR = ROOT / ".audit"

_GOV_DOMAIN_HINTS = (".gc.ca", ".canada.ca", "gov.bc.ca", "gov.ab.ca", "gov.sk.ca",
                     "gov.mb.ca", "ontario.ca", "quebec.ca", "gnb.ca", "gov.ns.ca",
                     "gov.pe.ca", "gov.nl.ca", "gov.nt.ca", "gov.nu.ca", "gov.yk.ca",
                     "yukon.ca", "saskatchewan.ca", "alberta.ca", "manitoba.ca",
                     ".gov.", "iaac-aeic", "cer-rec", "sedarplus")


def is_government_entry(entry):
    if not isinstance(entry, dict):
        return False
    if (entry.get("authority") or "").lower() == "government":
        return True
    if (entry.get("source_type") or "").lower() in ("government_registry", "government",
                                                    "provincial_ea", "federal_registry"):
        return True
    url = (entry.get("url") or "").lower()
    try:
        host = urlparse(url).netloc
    except ValueError:
        return False
    return any(h in host for h in _GOV_DOMAIN_HINTS)


def prune_row(name, evidence, cap, min_keep):
    """Return (kept, removed) for one row's evidence array."""
    ntoks = name_tokens(name)
    scored = [(score(e, ntoks), i, e) for i, e in enumerate(evidence)]
    # Stable order: score desc, original index asc
    ordered = sorted(scored, key=lambda x: (-x[0], x[1]))

    kept, removed = [], []
    for s, _, e in ordered:
        if len(kept) < cap and (is_government_entry(e) or s > 0):
            kept.append(e)
        else:
            removed.append(e)

    if not kept:
        # Nothing on-topic at all — keep the top min_keep by score (URL hard gate)
        kept = [e for _, _, e in ordered[:max(1, min_keep)]]
        removed = [e for _, _, e in ordered[max(1, min_keep):]]
    return kept, removed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cap", type=int, default=15)
    ap.add_argument("--min-keep", type=int, default=3)
    ap.add_argument("--over", type=int, default=20,
                    help="Only touch rows with more than this many evidence entries")
    args = ap.parse_args()

    import db
    conn = db.init_db()
    rows = conn.execute(
        "SELECT rowid, norm_key, name, evidence FROM projects").fetchall()

    AUDIT_DIR.mkdir(exist_ok=True)
    audit_path = AUDIT_DIR / f"evidence_prune_{date.today():%Y%m%d}.jsonl"

    touched = 0
    total_removed = 0
    audit_records = []
    updates = []

    for rowid, norm_key, name, evidence_json in rows:
        try:
            evidence = json.loads(evidence_json or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(evidence, list) or len(evidence) <= args.over:
            continue

        kept, removed = prune_row(name, evidence, args.cap, args.min_keep)
        if not removed:
            continue

        touched += 1
        total_removed += len(removed)
        audit_records.append({
            "norm_key": norm_key, "name": name,
            "before": len(evidence), "after": len(kept),
            "removed": removed,
        })
        new_quality = best_link_quality(
            [e.get("url") for e in kept if isinstance(e, dict) and e.get("url")])
        updates.append((json.dumps(kept, ensure_ascii=False), len(kept),
                        new_quality, rowid))

    print(f"rows over {args.over} URLs : {touched}")
    print(f"entries removed        : {total_removed}")
    for rec in audit_records[:10]:
        print(f"  {rec['name'][:60]}: {rec['before']} -> {rec['after']}")
    if len(audit_records) > 10:
        print(f"  ... and {len(audit_records) - 10} more rows")

    if args.apply:
        with open(audit_path, "a", encoding="utf-8") as f:
            for rec in audit_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        conn.executemany(
            "UPDATE projects SET evidence=?, evidence_count=?, source_url_quality=? "
            "WHERE rowid=?", updates)
        conn.commit()
        print(f"\nAPPLIED: {len(updates)} rows updated | audit: {audit_path}")
    else:
        print("\nDRY RUN — re-run with --apply")
    conn.close()


if __name__ == "__main__":
    main()
