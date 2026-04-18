"""
Fill every demo-only field into the live briefing_latest.json, recursively.

Rule: if a path exists in demo but not in live, copy demo's value. Never
overwrite a value live already has (live reflects the current Apr 11 edition;
demo is the Apr 10 frozen preview — live's values are fresher).
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
LIVE = ROOT / "docs/data/briefing_latest.json"
DEMO = ROOT / "docs/demo/data/briefing_latest.json"


def merge_missing(live, demo, path=""):
    """Recursively add demo-only fields into live. Never overwrite."""
    added = []
    if isinstance(demo, dict) and isinstance(live, dict):
        for k, v in demo.items():
            p = f"{path}.{k}" if path else k
            if k not in live:
                live[k] = v
                added.append(p)
            else:
                added.extend(merge_missing(live[k], v, p))
    elif isinstance(demo, list) and isinstance(live, list):
        # For lists of dicts indexed by 'code' or 'name', merge per-item.
        demo_key = None
        for probe in ("code", "name"):
            if demo and isinstance(demo[0], dict) and probe in demo[0]:
                demo_key = probe
                break
        if demo_key and live and isinstance(live[0], dict) and demo_key in live[0]:
            live_idx = {item.get(demo_key): item for item in live if isinstance(item, dict)}
            for d_item in demo:
                k = d_item.get(demo_key)
                if k in live_idx:
                    added.extend(merge_missing(live_idx[k], d_item, f"{path}[{k}]"))
    return added


def main():
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    added = merge_missing(live, demo)
    print(f"Added {len(added)} demo-only fields into live briefing.")
    # Show top-level additions and a sample of nested
    toplevel = [p for p in added if "." not in p and "[" not in p]
    nested = [p for p in added if p not in toplevel]
    print(f"Top-level fields added ({len(toplevel)}): {toplevel}")
    print(f"Nested fields added ({len(nested)}, sample 30):")
    for p in nested[:30]:
        print(f"  {p}")
    if len(nested) > 30:
        print(f"  ... and {len(nested) - 30} more")

    LIVE.write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {LIVE}")


if __name__ == "__main__":
    main()
