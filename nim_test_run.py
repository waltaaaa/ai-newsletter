"""
nim_test_run.py — Test the NIM pipeline with a small query set.

Uses Tavily for search (SearXNG Docker not yet running), NIM rerank + K2.5 extraction.
Compares results against existing dashboard.db projects.
"""

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from nim_client import get_client
from nim_deep_search import (
    SECTORS, JSON_INSTRUCTIONS, extract_json_array, normalize_project, dedup_key,
    SYSTEM_PROMPT, fetch_page_text,
)
from pipeline_config import NIM_RERANK_ENABLED

# ── Test queries (10 strategic queries spanning sectors) ──────────────────
TEST_QUERIES = [
    {"search": "Canada LNG terminal project 2025 2026 construction", "province": "National", "sector": "oil_gas"},
    {"search": "Ontario hospital construction project billion 2025 2026", "province": "Ontario", "sector": "healthcare"},
    {"search": "Alberta oil sands CCUS carbon capture project 2025 2026", "province": "Alberta", "sector": "oil_gas"},
    {"search": "British Columbia transit LRT SkyTrain project 2025 2026", "province": "British Columbia", "sector": "infrastructure"},
    {"search": "Canada data centre AI campus construction 2025 2026", "province": "National", "sector": "manufacturing"},
    {"search": "Quebec infrastructure bridge highway project billion 2025", "province": "Quebec", "sector": "infrastructure"},
    {"search": "Saskatchewan potash uranium mining project 2025 2026", "province": "Saskatchewan", "sector": "mining"},
    {"search": "Canada EV battery gigafactory manufacturing 2025 2026", "province": "National", "sector": "manufacturing"},
    {"search": "Canada nuclear SMR small modular reactor project 2025 2026", "province": "National", "sector": "power_energy"},
    {"search": "Calgary Edmonton residential housing tower construction 2025 2026", "province": "Alberta", "sector": "residential"},
]


def tavily_search(query: str, max_results: int = 8) -> list[dict]:
    """Search using Tavily API (temporary until SearXNG Docker is up)."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return []

    import requests
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "include_raw_content": False,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        })
    return results


def search_rerank_extract(query_info: dict, client) -> list[dict]:
    """Full pipeline: Tavily search -> NIM rerank -> trafilatura -> K2.5 extract."""
    search_q = query_info["search"]
    province = query_info["province"]
    sector = query_info["sector"]

    # Step 1: Search
    results = tavily_search(search_q)
    if not results:
        print(f"  No search results for: {search_q[:50]}")
        return []
    print(f"  Search: {len(results)} results")

    # Step 2: Rerank
    if NIM_RERANK_ENABLED and len(results) > 3:
        try:
            passages = [f"{r['title']} {r['content']}" for r in results]
            ranked = client.rerank_sync(search_q, passages, top_n=5)
            reranked = [results[r["index"]] for r in ranked if r["index"] < len(results)]
            if reranked:
                results = reranked
                print(f"  Rerank: top {len(results)} selected")
        except Exception as e:
            print(f"  Rerank failed: {e}")
            results = results[:5]
    else:
        results = results[:5]

    # Step 3: Fetch full text
    page_texts = []
    for r in results[:4]:
        url = r.get("url", "")
        if not url:
            continue
        text = fetch_page_text(url)
        if text:
            page_texts.append(f"Source: {url}\nTitle: {r.get('title', '')}\n\n{text[:3000]}")
        elif r.get("content"):
            page_texts.append(f"Source: {url}\nTitle: {r.get('title', '')}\n\n{r['content']}")

    if not page_texts:
        # Use Tavily snippets as fallback
        for r in results[:5]:
            if r.get("content"):
                page_texts.append(f"Source: {r['url']}\nTitle: {r['title']}\n\n{r['content']}")

    if not page_texts:
        return []
    print(f"  Pages: {len(page_texts)} extracted")

    combined = "\n\n---\n\n".join(page_texts)

    # Step 4: K2.5 extraction
    sector_desc = SECTORS.get(sector, sector)
    extraction_prompt = (
        f"Extract all Canadian capital projects ({sector_desc}) from these search results. "
        f"Focus on projects in {province if province != 'National' else 'Canada'}.\n\n"
        f"{JSON_INSTRUCTIONS}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{extraction_prompt}\n\nWeb search results:\n\n{combined}"},
    ]

    try:
        response = client.chat_sync(
            messages=messages, thinking=True, max_tokens=8192, temperature=0.3,
        )
        print(f"  K2.5: response received ({len(response)} chars)")
    except Exception as e:
        print(f"  K2.5 FAILED: {e}")
        return []

    return extract_json_array(response)


def load_db_projects() -> dict:
    """Load existing projects from dashboard.db for comparison."""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT name, province, sector, value, status FROM projects").fetchall()
    projects = {}
    for r in rows:
        key = re.sub(r'[^a-z0-9]', '', r["name"].lower())
        projects[key] = dict(r)
    conn.close()
    return projects


def fuzzy_match(name: str, db_projects: dict) -> str | None:
    """Check if a project name fuzzy-matches something in the DB."""
    key = re.sub(r'[^a-z0-9]', '', name.lower())
    if key in db_projects:
        return db_projects[key]["name"]

    # Partial match
    for db_key, db_proj in db_projects.items():
        if len(key) > 8 and len(db_key) > 8:
            if key[:12] == db_key[:12]:
                return db_proj["name"]
            if key in db_key or db_key in key:
                return db_proj["name"]
    return None


def main():
    print("=" * 80)
    print("NIM PIPELINE TEST RUN")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Queries: {len(TEST_QUERIES)}")
    print("Search: Tavily (temporary) | Rerank: NIM | Extract: K2.5 thinking")
    print("=" * 80)

    client = get_client()
    db_projects = load_db_projects()
    print(f"\nExisting DB: {len(db_projects)} projects loaded for comparison\n")

    all_extracted = []
    seen_keys = set()
    query_stats = []

    for i, q in enumerate(TEST_QUERIES):
        print(f"\n[{i+1}/{len(TEST_QUERIES)}] {q['search'][:60]}")
        print(f"  Province: {q['province']}, Sector: {q['sector']}")

        start = time.time()
        raw_projects = search_rerank_extract(q, client)
        elapsed = time.time() - start

        new_count = 0
        for proj in raw_projects:
            normalized = normalize_project(proj, q["province"], q["sector"])
            if not normalized["project_name"]:
                continue
            key = dedup_key(normalized)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_extracted.append(normalized)
            new_count += 1

        print(f"  Result: {len(raw_projects)} extracted, {new_count} unique ({elapsed:.1f}s)")
        query_stats.append({
            "query": q["search"][:50],
            "raw": len(raw_projects),
            "new": new_count,
            "time": elapsed,
        })

        # Brief pause for rate limiting
        time.sleep(2)

    # ── Comparison ────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("COMPARISON WITH EXISTING DATABASE")
    print("=" * 80)

    in_db = []
    not_in_db = []

    for proj in all_extracted:
        name = proj["project_name"]
        match = fuzzy_match(name, db_projects)
        if match:
            in_db.append({"extracted": name, "db_match": match})
        else:
            not_in_db.append(proj)

    print(f"\nTotal unique projects extracted: {len(all_extracted)}")
    print(f"Already in database: {len(in_db)} ({len(in_db)/max(len(all_extracted),1)*100:.0f}%)")
    print(f"NEW (not in database): {len(not_in_db)} ({len(not_in_db)/max(len(all_extracted),1)*100:.0f}%)")

    if in_db:
        print(f"\n--- CONFIRMED MATCHES ({len(in_db)}) ---")
        for m in in_db[:15]:
            print(f"  [MATCH] {m['extracted'][:45]} <-> {m['db_match'][:45]}")

    if not_in_db:
        print(f"\n--- POTENTIALLY NEW PROJECTS ({len(not_in_db)}) ---")
        for p in not_in_db:
            val = p.get("estimated_value", "N/A")
            status = p.get("status", "?")
            print(f"  [NEW] {p['project_name'][:50]} | {p['province']} | {val} | {status}")

    # Province/sector breakdown of new projects
    if not_in_db:
        prov_counts = {}
        sec_counts = {}
        for p in not_in_db:
            prov_counts[p["province"]] = prov_counts.get(p["province"], 0) + 1
            sec_counts[p["sector"]] = sec_counts.get(p["sector"], 0) + 1
        print(f"\nNew projects by province: {dict(sorted(prov_counts.items(), key=lambda x: -x[1]))}")
        print(f"New projects by sector: {dict(sorted(sec_counts.items(), key=lambda x: -x[1]))}")

    # Query performance
    print(f"\n--- QUERY PERFORMANCE ---")
    for qs in query_stats:
        print(f"  {qs['query'][:45]:45s} | {qs['raw']:2d} raw | {qs['new']:2d} new | {qs['time']:.1f}s")

    total_time = sum(qs["time"] for qs in query_stats)
    print(f"\nTotal time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Avg per query: {total_time/len(TEST_QUERIES):.1f}s")
    est_full = total_time / len(TEST_QUERIES) * 421
    print(f"Estimated full 421-query sweep: {est_full/60:.0f} min ({est_full/3600:.1f} hr)")


if __name__ == "__main__":
    main()
