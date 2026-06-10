# -*- coding: utf-8 -*-
"""tavily_cost_batch.py — Operator-run Tavily cost-finding batch (staged).

One-time batch over projects with no disclosed value, separate from the weekly
cost_finder.py pass. Three stages, all resumable via the checkpoint JSONL:

  --search     Tavily searches (spends credits). Extracts a CANDIDATE value
               anchored to the best name-matching result and stores it with
               the source snippet. NO DB writes.
  --validate   Claude Code subprocess (sonnet, $0) reviews candidates in
               batches of 15 against their snippets — separates a project's
               own cost from program-level figures ("the $8B GO expansion
               includes this station") that defeat regex extraction.
  --apply      Writes validated values to the DB (value, value_millions,
               parsed_value, evidence append, confidence recalc) and search
               bookkeeping (cooldown/attempts) for misses.

BUDGET: user approved up to 2,000 Tavily credits for 2026-06 — a one-month
exception to the documented 1,000/month free tier. The shared monthly ledger
in dashboard_state is re-checked before every search; quota/429 responses
checkpoint and exit cleanly. tavily_search.py's weekly budget is untouched.

Usage:
    .venv\\Scripts\\python.exe tools\\tavily_cost_batch.py             # dry-run report
    .venv\\Scripts\\python.exe tools\\tavily_cost_batch.py --search
    .venv\\Scripts\\python.exe tools\\tavily_cost_batch.py --validate
    .venv\\Scripts\\python.exe tools\\tavily_cost_batch.py --apply
"""
import argparse
import asyncio
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

AUDIT_DIR = ROOT / ".audit"
SEARCH_CKPT = AUDIT_DIR / f"tavily_cost_batch_{date.today():%Y%m}.jsonl"
VALID_CKPT = AUDIT_DIR / f"tavily_cost_validated_{date.today():%Y%m}.jsonl"

APPROVED_CAP = 2000          # operator-approved ceiling for 2026-06
CONCURRENCY = 5
COOLDOWN_DAYS = 14
MAX_ATTEMPTS = 3

PRIORITY_SECTORS = {"oil_gas", "mining", "power_energy", "infrastructure",
                    "transport_logistics", "healthcare"}

_NO_VALUE = {"", "—", "not disclosed", "unknown", "n/a", "c$0m", "tbd",
             "not available", "undisclosed"}


class QuotaExhausted(Exception):
    pass


def _load_jsonl(path, key="norm_key"):
    out = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    out[rec[key]] = rec
                except (json.JSONDecodeError, KeyError):
                    continue
    return out


def select_candidates(conn, done, limit=None):
    """Valueless projects ordered by findability/payoff."""
    from db import get_all_projects
    from tools.dedup_projects_fuzzy import normalize_name, is_generic_name
    now = datetime.utcnow()
    out = []
    for p in get_all_projects(conn):
        nk = p.get("norm_key", "")
        if not nk or nk in done:
            continue
        val = (p.get("value") or "").strip().lower()
        if val and val not in _NO_VALUE:
            continue
        if p.get("parsed_value"):
            continue
        if (p.get("status") or "").lower() in ("cancelled", "canceled", "complete",
                                               "completed"):
            continue
        if p.get("cost_unfindable"):
            continue
        last = p.get("last_cost_search")
        if last:
            try:
                if (now - datetime.fromisoformat(str(last)[:10])).days < COOLDOWN_DAYS:
                    continue
            except (ValueError, TypeError):
                pass

        prio = 0
        if p.get("has_government_source"):
            prio += 500
        if (p.get("sector") or "") in PRIORITY_SECTORS:
            prio += 300
        # Generic registry names ("Wastewater Treatment Lagoon") are unsearchable
        if is_generic_name(normalize_name(p.get("name") or "")):
            prio -= 700
        if p.get("proponent"):
            prio += 100
        try:
            ev = json.loads(p.get("evidence") or "[]")
        except (json.JSONDecodeError, TypeError):
            ev = []
        if len(ev) >= 2:
            prio += 100
        seen = p.get("lastSeen") or p.get("firstTracked") or ""
        try:
            days = (now - datetime.fromisoformat(str(seen)[:10])).days
            prio += max(0, 90 - days)
        except (ValueError, TypeError):
            pass
        prio -= (p.get("cost_search_attempts") or 0) * 50
        out.append((prio, nk, p))

    out.sort(key=lambda x: -x[0])
    if limit:
        out = out[:limit]
    return [(nk, p) for _, nk, p in out]


def distinctive_name_tokens(name):
    from tools.dedup_projects_fuzzy import normalize_name, distinctive_tokens
    return distinctive_tokens(normalize_name(name or ""))


# ── Stage 1: search ──────────────────────────────────────────────────────────

async def _tavily_post(session, query, max_results=5):
    """Thin Tavily POST that surfaces quota errors (tavily_search.tavily_search
    swallows HTTP status, which would make the batch spin on a dead account)."""
    import os
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    payload = {"api_key": api_key, "query": query, "max_results": max_results,
               "search_depth": "basic", "include_answer": False,
               "include_raw_content": False}
    async with session.post("https://api.tavily.com/search", json=payload) as resp:
        if resp.status in (429, 432):
            raise QuotaExhausted(f"HTTP {resp.status}")
        if resp.status != 200:
            body = (await resp.text())[:200]
            if "usage" in body.lower() and "limit" in body.lower():
                raise QuotaExhausted(body)
            raise RuntimeError(f"HTTP {resp.status}: {body}")
        data = await resp.json()
        return data.get("results", [])


def _rank_on_topic(results, ntoks):
    """Rank results by distinctive-name-token hits (title hits weigh double)."""
    if not ntoks:
        return []
    ranked = []
    for r in results:
        title = (r.get("title") or "").lower()
        content = (r.get("content") or "").lower()
        hits = sum(2 for t in ntoks if t in title) + sum(1 for t in ntoks if t in content)
        if hits > 0:
            ranked.append((hits, r))
    ranked.sort(key=lambda x: -x[0])
    return ranked


def extract_candidate(results, ntoks):
    """Candidate value from the single best-matching result (not a max over
    combined text, which attributes program-level figures to projects).
    Returns (value_millions, snippet, url) or (None, best_snippet, url)."""
    from cost_finder import extract_cost_from_response
    need = min(2, max(1, len(ntoks)))
    best_snip, best_url = "", ""
    for hits, r in _rank_on_topic(results, ntoks):
        content = r.get("content") or ""
        if not best_snip:
            best_snip, best_url = content[:900], r.get("url") or ""
        if hits < need:
            continue
        cost = extract_cost_from_response(content, [])
        v = cost.get("value_millions")
        if cost["found"] and v and 1 <= v <= 100_000:
            return v, content[:900], r.get("url") or ""
    return None, best_snip, best_url


async def search_one(session, sem, ckpt_lock, nk, project, budget):
    async with sem:
        if not budget.allow():
            raise QuotaExhausted("local cap reached")
        name = project.get("name", "")
        province = project.get("province", "")
        cma = project.get("cma") or ""
        query = f"{name} {cma} {province} budget cost million billion investment".strip()

        results = await _tavily_post(session, query)
        budget.spend(1)

        prov_low = province.lower()
        if prov_low in ("quebec", "québec", "qc", "new brunswick", "nb") and budget.allow():
            fr_query = f"{name} {cma} {province} coût budget millions milliards investissement".strip()
            try:
                results += await _tavily_post(session, fr_query)
                budget.spend(1)
            except QuotaExhausted:
                raise
            except Exception:
                pass

        ntoks = distinctive_name_tokens(name)
        candidate, snippet, url = extract_candidate(results, ntoks)
        rec = {"norm_key": nk, "name": name, "province": province,
               "candidate_millions": candidate, "snippet": snippet,
               "source_url": url,
               "all_urls": [r.get("url") for r in results if r.get("url")][:5]}
        async with ckpt_lock:
            with open(SEARCH_CKPT, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


class Budget:
    """Hard cap against the SHARED monthly ledger in dashboard_state."""

    def __init__(self, conn, cap):
        self.conn = conn
        self.cap = cap

    def used(self):
        from db import get_tavily_credits
        return get_tavily_credits(self.conn)["used"]

    def allow(self):
        return self.used() < self.cap

    def spend(self, n):
        from db import increment_tavily_credits
        increment_tavily_credits(self.conn, n)


async def run_search(args):
    import aiohttp
    import db
    conn = db.init_db()
    done = _load_jsonl(SEARCH_CKPT)
    budget = Budget(conn, min(args.max_credits, APPROVED_CAP))

    used = budget.used()
    available = max(0, budget.cap - used)
    print(f"Tavily ledger: {used} used | cap {budget.cap} | available {available}")
    candidates = select_candidates(conn, done, min(args.limit or available, available))
    print(f"{len(done)} already searched | {len(candidates)} queued")

    AUDIT_DIR.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    ckpt_lock = asyncio.Lock()
    with_candidate = without = errors = 0

    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.ensure_future(search_one(session, sem, ckpt_lock, nk, p, budget))
                 for nk, p in candidates]
        try:
            for fut in asyncio.as_completed(tasks):
                try:
                    rec = await fut
                    if rec["candidate_millions"]:
                        with_candidate += 1
                    else:
                        without += 1
                    total = with_candidate + without
                    if total % 100 == 0:
                        print(f"  {total}/{len(candidates)} searched "
                              f"({with_candidate} candidates) | ledger {budget.used()}")
                except QuotaExhausted as e:
                    print(f"\nQUOTA EXHAUSTED ({e}) — checkpointed, exiting cleanly.")
                    break
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  error: {str(e)[:120]}")
        finally:
            for t in tasks:
                t.cancel()

    print(f"\nSearch done: {with_candidate} candidates / {without} no-value / "
          f"{errors} errors | ledger {budget.used()}")
    conn.close()


# ── Stage 2: validate via Claude ─────────────────────────────────────────────

VALIDATE_PROMPT = """You are validating extracted cost figures for Canadian capital projects.

For each item below you get: the project name/province, a CANDIDATE dollar value
(in millions CAD) that regex extraction pulled from a news/government snippet,
and the snippet itself.

Decide whether the candidate is the cost of THAT SPECIFIC PROJECT.
Common failure you must catch: the snippet cites a PROGRAM or PORTFOLIO figure
("the $8B GO expansion program includes this station") — that is NOT the
project's own cost. Phase figures: if the snippet gives the project's own
phase cost, use it. If the snippet states a different, clearly correct value
for the project, return that corrected value.

Respond with ONLY a JSON array:
[{"norm_key": "...", "value_millions": <number or null>, "reason": "<short>"}]
- value_millions: the project's own cost in millions CAD, or null if the
  snippet only supports program-level/unrelated/ambiguous figures.

Items:
"""


def run_validate(args):
    from claude_reasoning import _call_claude_code_sync
    searched = _load_jsonl(SEARCH_CKPT)
    validated = _load_jsonl(VALID_CKPT)
    pending = [r for r in searched.values()
               if r.get("candidate_millions") and r["norm_key"] not in validated]
    print(f"{len(validated)} validated | {len(pending)} candidates pending")

    batch_size = 15
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        blocks = []
        for r in batch:
            blocks.append(json.dumps({
                "norm_key": r["norm_key"], "name": r["name"],
                "province": r["province"],
                "candidate_millions": r["candidate_millions"],
                "snippet": r["snippet"],
            }, ensure_ascii=False))
        prompt = VALIDATE_PROMPT + "\n".join(blocks)

        parsed = None
        for attempt in (1, 2):
            text = _call_claude_code_sync(prompt, label=f"cost-validate x{len(batch)}",
                                          model="sonnet", timeout=300)
            if text:
                m = re.search(r"\[[\s\S]*\]", text)
                if m:
                    try:
                        parsed = json.loads(m.group())
                        break
                    except json.JSONDecodeError:
                        pass
            print(f"  batch parse failed (attempt {attempt})")
        if parsed is None:
            print(f"  SKIPPED batch at offset {i}")
            continue

        by_key = {r["norm_key"]: r for r in batch}
        kept = 0
        with open(VALID_CKPT, "a", encoding="utf-8") as f:
            for item in parsed:
                if not isinstance(item, dict) or item.get("norm_key") not in by_key:
                    continue
                v = item.get("value_millions")
                if v is not None:
                    try:
                        v = float(v)
                        if not (1 <= v <= 100_000):
                            v = None
                    except (TypeError, ValueError):
                        v = None
                src = by_key[item["norm_key"]]
                f.write(json.dumps({
                    "norm_key": item["norm_key"], "name": src["name"],
                    "value_millions": v, "reason": str(item.get("reason", ""))[:200],
                    "source_url": src.get("source_url", ""),
                    "all_urls": src.get("all_urls", []),
                }, ensure_ascii=False) + "\n")
                if v:
                    kept += 1
        print(f"  batch {i // batch_size + 1}: {kept}/{len(batch)} confirmed "
              f"({min(i + batch_size, len(pending))}/{len(pending)})")


# ── Stage 3: apply ───────────────────────────────────────────────────────────

def run_apply(args):
    import db
    from cost_finder import _format_value
    searched = _load_jsonl(SEARCH_CKPT)
    validated = _load_jsonl(VALID_CKPT)
    if not searched:
        print("Nothing searched yet.")
        return
    conn = db.init_db()
    now_iso = datetime.utcnow().isoformat()
    today = now_iso[:10]
    applied = misses = 0

    for nk, srec in searched.items():
        vrec = validated.get(nk)
        confirmed = vrec and vrec.get("value_millions")
        row = conn.execute(
            "SELECT value, parsed_value, evidence, cost_search_attempts, "
            "has_government_source, status, name, province, sector "
            "FROM projects WHERE norm_key = ?", (nk,)).fetchone()
        if row is None:
            continue
        # Skip rows that gained a value some other way since the search
        if confirmed and row[1]:
            continue

        if confirmed:
            v = float(vrec["value_millions"])
            value_str = _format_value(v)
            evidence = json.loads(row[2] or "[]")
            existing_urls = {e.get("url") for e in evidence if isinstance(e, dict)}
            urls = [vrec.get("source_url")] + list(vrec.get("all_urls", []))
            for url in urls:
                if url and url.startswith("http") and url not in existing_urls:
                    evidence.append({"url": url, "name": "", "date": today,
                                     "source_type": "cost_finding"})
                    existing_urls.add(url)
                    break  # one corroborating URL is enough — keep arrays clean
            confidence = None
            try:
                from project_dedup import calculate_confidence
                temp = {"name": row[6], "province": row[7], "sector": row[8],
                        "status": row[5], "value": value_str, "evidence": evidence,
                        "has_government_source": row[4]}
                confidence = calculate_confidence(temp)
            except Exception:
                pass
            sets = ("value = ?, value_millions = ?, parsed_value = ?, "
                    "last_cost_search = ?, cost_search_attempts = 0, "
                    "lastUpdated = ?, evidence = ?, evidence_count = ?")
            params = [value_str, v, v * 1_000_000, now_iso, now_iso,
                      json.dumps(evidence, ensure_ascii=False), len(evidence)]
            if confidence is not None:
                sets += ", confidence = ?"
                params.append(confidence)
            params.append(nk)
            conn.execute(f"UPDATE projects SET {sets} WHERE norm_key = ?", params)
            applied += 1
        else:
            attempts = (row[3] or 0) + 1
            unfindable = 1 if attempts >= MAX_ATTEMPTS else 0
            conn.execute(
                "UPDATE projects SET last_cost_search = ?, cost_search_attempts = ?, "
                "cost_unfindable = ? WHERE norm_key = ?",
                (now_iso, attempts, unfindable, nk))
            misses += 1

    conn.commit()
    conn.close()
    print(f"APPLIED: {applied} values written | {misses} misses bookkept "
          f"(cooldown {COOLDOWN_DAYS}d, unfindable after {MAX_ATTEMPTS} attempts)")


def run_report(args):
    import db
    conn = db.init_db()
    budget = Budget(conn, min(args.max_credits, APPROVED_CAP))
    used = budget.used()
    searched = _load_jsonl(SEARCH_CKPT)
    validated = _load_jsonl(VALID_CKPT)
    confirmed = sum(1 for v in validated.values() if v.get("value_millions"))
    print(f"Ledger: {used}/{budget.cap} | searched: {len(searched)} | "
          f"candidates: {sum(1 for r in searched.values() if r.get('candidate_millions'))} | "
          f"validated: {len(validated)} ({confirmed} confirmed)")
    candidates = select_candidates(conn, searched, 20)
    print("Next 20 in queue:")
    for nk, p in candidates:
        print(f"  [{p.get('sector', '?'):20s}] {p.get('name', '')[:70]} ({p.get('province', '')})")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--search", action="store_true", help="Run Tavily searches (spends credits)")
    ap.add_argument("--validate", action="store_true", help="Validate candidates via Claude")
    ap.add_argument("--apply", action="store_true", help="Write validated values to DB")
    ap.add_argument("--max-credits", type=int, default=APPROVED_CAP,
                    help="Monthly ledger ceiling (hard-capped at 2000)")
    ap.add_argument("--limit", type=int, default=None, help="Max projects this run")
    args = ap.parse_args()

    if args.search:
        asyncio.run(run_search(args))
    elif args.validate:
        run_validate(args)
    elif args.apply:
        run_apply(args)
    else:
        run_report(args)


if __name__ == "__main__":
    main()
