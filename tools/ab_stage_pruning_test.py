"""
Stage an A/B test for writer input pruning.

Produces two dossiers that can be fed to tldr-writer-provincial back-to-back,
so the ported output quality can be compared directly.

Usage:
    python tools/ab_stage_pruning_test.py --province ON

Output:
    docs/data/_abtest/dossier_provinces_full.json    (version A — current behavior)
    docs/data/_abtest/dossier_provinces_pruned.json  (version B — only the target province)

After running this, in the session:
    1. Invoke tldr-writer-provincial with dossier_provinces_full.json
       → save output as briefing_provinces_A.json
    2. Invoke tldr-writer-provincial with dossier_provinces_pruned.json
       → save output as briefing_provinces_B.json
    3. Run tools/diff_against_baseline.py to compare A vs B on quality metrics.
"""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOSSIER = ROOT / "docs/data/dossier_provinces.json"
OUT = ROOT / "docs/data/_abtest"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--province", default="ON", help="Province code (ON/QC/AB/...)")
    args = parser.parse_args()

    if not DOSSIER.exists():
        raise SystemExit(f"Dossier not found: {DOSSIER}. Run Phase 2 analyst first.")

    OUT.mkdir(parents=True, exist_ok=True)

    # Full (version A)
    shutil.copy(DOSSIER, OUT / "dossier_provinces_full.json")
    full = json.loads(DOSSIER.read_text(encoding="utf-8"))

    # Pruned (version B) — keep only the target province
    provinces = full.get("provinces", [])
    target = [p for p in provinces if p.get("code") == args.province
              or p.get("name", "").upper().startswith(args.province)]
    if not target:
        raise SystemExit(f"Province {args.province!r} not found in dossier.")

    pruned = {**full, "provinces": target}
    (OUT / "dossier_provinces_pruned.json").write_text(
        json.dumps(pruned, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Staged A/B test for province {args.province!r}.")
    print(f"  A (full):   {OUT / 'dossier_provinces_full.json'} "
          f"— {len(provinces)} provinces")
    print(f"  B (pruned): {OUT / 'dossier_provinces_pruned.json'} "
          f"— {len(target)} province")
    print("\nRun the writer twice; then `tools/diff_against_baseline.py`.")


if __name__ == "__main__":
    main()
