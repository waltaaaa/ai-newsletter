"""
classify_other_sectors.py — LLM sector classification for sector='Other' rows.

The 2026-06-09 keyword pass (clean_project_list.py) reclassified 1,413 of the
'Other' rows; the ~1,300 left are ambiguous provincial EA registry rows that
keywords can't disambiguate. This tool batches them through the Claude Code
CLI subprocess (user subscription, $0 API cost; model: sonnet — extraction
task, no Opus per CLAUDE.md) and applies classifications into the 18 canonical
NAICS sectors when confidence >= threshold. Low-confidence rows stay 'Other'.

Phases:
    --classify   run LLM batches, append results to the checkpoint JSONL
                 (resumable: rowids already in the checkpoint are skipped)
    (default)    dry-run report from the checkpoint: per-sector counts,
                 threshold pass/fail, samples
    --apply      apply checkpointed classifications >= threshold to the DB

Usage:
    .venv\\Scripts\\python.exe tools\\classify_other_sectors.py --classify
    .venv\\Scripts\\python.exe tools\\classify_other_sectors.py            # report
    .venv\\Scripts\\python.exe tools\\classify_other_sectors.py --apply
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.clean_project_list import CANONICAL_SECTORS  # noqa: E402

AUDIT_DIR = ROOT / ".audit"
CHECKPOINT = AUDIT_DIR / f"sector_classify_{date.today():%Y%m%d}.jsonl"

PROMPT_HEADER = """You are classifying Canadian capital projects into NAICS-aligned sectors.

The 18 canonical sector keys (use EXACTLY these strings):
- oil_gas: oil/gas extraction, pipelines, refineries, LNG
- mining: mines, quarries, mineral processing, smelters
- infrastructure: roads, bridges, water/wastewater, municipal works, flood control
- power_energy: generation, transmission, substations, renewables, nuclear
- manufacturing: factories, processing plants, industrial production
- transport_logistics: transit, rail, ports, airports, warehouses, distribution
- healthcare: hospitals, clinics, long-term care
- education: schools, universities, colleges, training centres
- residential: housing, apartments, subdivisions, condos
- commercial_mixed: offices, retail, hotels, mixed-use developments
- agriculture: farms, barns, feedlots, irrigation, food production (incl. hog/dairy operations)
- forestry: sawmills, pulp/paper, timber operations
- defence: military bases, defence manufacturing
- telecom: broadband, data centres, towers
- indigenous: Indigenous-led developments (when that is the defining characteristic)
- environment: remediation, conservation, waste management, recycling
- tourism_culture: arenas, museums, parks, recreation, casinos, stadiums
- government: government buildings, courthouses, correctional facilities

These are ambiguous provincial EA registry rows — names are often generic.
Use the name, province, proponent, and description together. When genuinely
ambiguous, return sector "Other" with low confidence. Do not guess.

Respond with ONLY a JSON array, no prose, one object per input row:
[{"rowid": <int>, "sector": "<key or Other>", "confidence": <0.0-1.0>}]

Rows to classify:
"""


def fetch_pending(conn, limit=None):
    rows = conn.execute(
        "SELECT rowid, name, province, proponent, description FROM projects "
        "WHERE TRIM(sector) = 'Other' ORDER BY rowid"
    ).fetchall()
    return rows[:limit] if limit else rows


def load_checkpoint():
    done = {}
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    done[rec["rowid"]] = rec
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def parse_array(text):
    """Extract a JSON array from LLM output (tolerates surrounding prose/fences)."""
    if not text:
        return None
    try:
        out = json.loads(text)
        return out if isinstance(out, list) else None
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            try:
                out = json.loads(m.group())
                return out if isinstance(out, list) else None
            except json.JSONDecodeError:
                return None
    return None


def classify_batch(rows, timeout=300):
    from claude_reasoning import _call_claude_code_sync

    lines = []
    for r in rows:
        desc = (r[4] or "").replace("\n", " ")[:300]
        lines.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3] or '-'} | {desc}")
    prompt = PROMPT_HEADER + "rowid | name | province | proponent | description\n" + "\n".join(lines)

    for attempt in (1, 2):
        text = _call_claude_code_sync(prompt, label=f"sector-classify x{len(rows)}",
                                      model="sonnet", timeout=timeout)
        parsed = parse_array(text)
        if parsed is not None:
            return parsed
        print(f"  batch parse failed (attempt {attempt})")
    return None


def run_classify(args):
    import db
    conn = db.init_db()
    done = load_checkpoint()
    pending = [r for r in fetch_pending(conn, args.limit) if r[0] not in done]
    conn.close()
    print(f"{len(done)} rows already checkpointed; {len(pending)} to classify "
          f"in batches of {args.batch_size}")

    AUDIT_DIR.mkdir(exist_ok=True)
    for i in range(0, len(pending), args.batch_size):
        batch = pending[i:i + args.batch_size]
        results = classify_batch(batch)
        if results is None:
            print(f"  SKIPPED batch at offset {i} (unparseable after retry)")
            continue
        by_rowid = {r[0]: r for r in batch}
        wrote = 0
        with open(CHECKPOINT, "a", encoding="utf-8") as f:
            for item in results:
                if not isinstance(item, dict):
                    continue
                rowid = item.get("rowid")
                if rowid not in by_rowid:
                    continue
                rec = {
                    "rowid": rowid,
                    "name": by_rowid[rowid][1],
                    "province": by_rowid[rowid][2],
                    "sector": str(item.get("sector", "Other")),
                    "confidence": float(item.get("confidence", 0.0) or 0.0),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                wrote += 1
        print(f"  batch {i // args.batch_size + 1}: {wrote}/{len(batch)} classified "
              f"({i + len(batch)}/{len(pending)} done)")


def run_report(args):
    done = load_checkpoint()
    if not done:
        print(f"No checkpoint at {CHECKPOINT} — run --classify first.")
        return
    passing = {k: v for k, v in done.items()
               if v["confidence"] >= args.threshold and v["sector"] in CANONICAL_SECTORS}
    sectors = Counter(v["sector"] for v in passing.values())
    print(f"Checkpointed: {len(done)} rows | pass threshold {args.threshold}: "
          f"{len(passing)} | stay Other: {len(done) - len(passing)}")
    for sector, n in sectors.most_common():
        print(f"  {sector}: {n}")
        samples = [v for v in passing.values() if v["sector"] == sector][:3]
        for s in samples:
            print(f"      e.g. [{s['confidence']:.2f}] {s['name']} ({s['province']})")


def run_apply(args):
    import db
    done = load_checkpoint()
    if not done:
        print(f"No checkpoint at {CHECKPOINT} — run --classify first.")
        return
    conn = db.init_db()
    applied = 0
    for rowid, rec in done.items():
        if rec["confidence"] < args.threshold or rec["sector"] not in CANONICAL_SECTORS:
            continue
        # Guard: only flip rows still 'Other' (reruns / concurrent edits safe)
        cur = conn.execute(
            "UPDATE projects SET sector = ? WHERE rowid = ? AND TRIM(sector) = 'Other'",
            (rec["sector"], rowid),
        )
        applied += cur.rowcount
    conn.commit()
    remaining = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE TRIM(sector) = 'Other'").fetchone()[0]
    conn.close()
    print(f"Applied {applied} sector updates; {remaining} rows remain 'Other'")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--classify", action="store_true", help="Run LLM batches into checkpoint")
    parser.add_argument("--apply", action="store_true", help="Apply checkpoint to DB")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.classify:
        run_classify(args)
        run_report(args)
    elif args.apply:
        run_apply(args)
    else:
        run_report(args)


if __name__ == "__main__":
    main()
