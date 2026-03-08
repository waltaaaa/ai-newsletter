"""
backfill_global_indicators.py

Patches the live 'latest' dashboard_state document with indicators for each
global tile (US, China, EU, UK). Makes 4 Perplexity queries then a single
Claude Sonnet call to structure the values, then writes back to SQLite.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import os
import time
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()

from db import init_db, get_dashboard_state, save_dashboard_state

conn = init_db()
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def query_perplexity(query: str) -> str:
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a global economic data researcher. Provide current, factual figures only."},
            {"role": "user",   "content": query},
        ],
        "max_tokens": 600,
    }
    try:
        r = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [PERPLEXITY ERROR] {e}")
        return ""


COUNTRIES = [
    ("United States", "🇺🇸", "US Federal Reserve federal funds rate"),
    ("China",         "🇨🇳", "People's Bank of China 1-year loan prime rate (LPR)"),
    ("European Union","🇪🇺", "ECB deposit facility rate"),
    ("United Kingdom","🇬🇧", "Bank of England Bank Rate"),
]

print("Fetching current indicators from Perplexity...")
research = {}
for name, emoji, rate_label in COUNTRIES:
    print(f"  {name}...", end=" ", flush=True)
    result = query_perplexity(
        f"What are the current economic indicators for {name}? "
        f"Provide: (1) latest GDP growth rate YoY%, (2) latest CPI inflation YoY%, "
        f"(3) current {rate_label} as a percentage, (4) latest unemployment rate. "
        f"Give exact figures with dates. Be concise."
    )
    research[name] = result
    print("done")
    time.sleep(2)

print("\nStructuring with Claude Sonnet...")
research_text = "\n\n".join(f"=== {name} ===\n{text}" for name, text in research.items() if text)

msg = anthropic_client.messages.create(
    model=os.environ.get("SONNET_MODEL", "claude-sonnet-4-5"),
    max_tokens=1024,
    system="You are a data extraction assistant. Return ONLY valid JSON. No markdown. No explanation.",
    messages=[{"role": "user", "content": f"""Extract the 4 key indicators for each country from the research below.

Return this exact JSON structure:
{{
    "United States": {{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}},
    "China":         {{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}},
    "European Union":{{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}},
    "United Kingdom":{{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}}
}}

Use realistic sign prefixes: "+" for positive GDP/CPI, no sign for rates/unemployment.
If a figure is genuinely unknown, use "—".

RESEARCH:
{research_text}"""}]
)

content = msg.content[0].text.strip()
if content.startswith("```"):
    parts = content.split("```")
    content = parts[1] if len(parts) > 1 else content
    if content.startswith("json"):
        content = content[4:]

indicators_map = json.loads(content)
print("  Indicators structured:")
for country, ind in indicators_map.items():
    print(f"    {country}: GDP {ind['gdp']}  CPI {ind['cpi']}  Rate {ind['rate']}  Unemployment {ind['unemployment']}")

# ── Patch SQLite 'latest' document ─────────────────────────────────────────
print("\nPatching SQLite 'latest' document...")
doc_data = get_dashboard_state(conn, 'latest')

if not doc_data:
    print("[ERROR] 'latest' document not found.")
    conn.close()
    exit(1)

global_arr = doc_data.get('global', [])

patched = 0
for entry in global_arr:
    region = entry.get('region', '')
    if region in indicators_map:
        entry['indicators'] = indicators_map[region]
        patched += 1

doc_data['global'] = global_arr
save_dashboard_state(conn, 'latest', doc_data)
print(f"  Patched {patched} global entries.")

# Also patch the dated document for today
from datetime import date, datetime
import pytz
toronto_tz = pytz.timezone('America/Toronto')
dated_id = datetime.now(toronto_tz).strftime('%Y-%m-%d')
dated_doc = get_dashboard_state(conn, f'newsletter_{dated_id}')
if dated_doc:
    dated_doc['global'] = global_arr
    save_dashboard_state(conn, f'newsletter_{dated_id}', dated_doc)
    print(f"  Also patched dated document '{dated_id}'.")

conn.close()
print("\n[OK] Global indicators backfill complete.")
