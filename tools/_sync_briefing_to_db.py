"""One-shot: push current docs/data/briefing_latest.json into dashboard_state.newsletter_latest
and run export_all() so DB + disk are in sync. Does NOT restamp edition/week_of.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from db import get_db, save_dashboard_state, get_dashboard_state
from tools.export_dashboard import export_all

SRC = os.path.join(ROOT, "docs", "data", "briefing_latest.json")

with open(SRC, "r", encoding="utf-8") as f:
    payload = json.load(f)

print(f"Loaded {SRC}")
print(f"  id={payload.get('id')} week_of={payload.get('week_of')} updated_at={payload.get('updated_at')}")
print(f"  headline: {(payload.get('headline') or '')[:80]}")

conn = get_db()

prev = get_dashboard_state(conn, "newsletter_latest") or {}
prev_tldr = len(((prev.get("insightCharts") or []) if isinstance(prev, dict) else []))
new_tldr = len(payload.get("insightCharts") or [])
print(f"  prev_tldr_charts={prev_tldr}  new_tldr_charts={new_tldr}")

save_dashboard_state(conn, "newsletter_latest", payload)
wk = payload.get("week_of")
if wk:
    save_dashboard_state(conn, f"newsletter_{wk}", payload)
    print(f"  also saved newsletter_{wk}")

print("Running export_all()...")
result = export_all(conn=conn)
print(f"  exported {result.get('file_count','?')} files to {result.get('output_dir','?')}")

with open(SRC, "r", encoding="utf-8") as f:
    after = json.load(f)
print(f"After export: size={os.path.getsize(SRC)} bytes  id={after.get('id')} week_of={after.get('week_of')}")
print("DONE")
