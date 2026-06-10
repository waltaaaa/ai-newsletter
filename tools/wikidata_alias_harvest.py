"""
wikidata_alias_harvest.py — Monthly, operator-run organization alias harvest.

For each organization name found in:
  (a) the `organizations` table (canonical_name) when populated, and
  (b) `proponent` values in `projects` (top N by frequency, cleaned),
query the Wikidata API:
  1. wbsearchentities — resolve the name to an entity (best match only,
     accepted when the label/alias closely matches the query)
  2. wbgetentities props=aliases|labels, languages en|fr — harvest aliases

Results are:
  - inserted via the existing db.py organization helpers
    (db.resolve_organization to find-or-create the org, then
    organization_aliases rows via INSERT OR IGNORE) when --apply is passed
  - ALWAYS written as a flat snapshot to config/aliases.json:
        {canonical_name: [alias, ...], ...}

This tool does NOT modify project_dedup.py — consumer wiring happens later.

Politeness: 1 request/second, descriptive User-Agent (Wikimedia API
etiquette). Free public API, zero cost.

Usage (from backend/):
    python tools/wikidata_alias_harvest.py                # dry run, top 50
    python tools/wikidata_alias_harvest.py --limit 3      # smoke test
    python tools/wikidata_alias_harvest.py --apply        # write to DB too
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = ("CanadianMacroDashboard/1.0 "
              "(https://github.com/lagging-indicator; "
              "walterbolduc@gmail.com) org-alias-harvester")
RATE_LIMIT_S = 1.0
SNAPSHOT_PATH = _BACKEND_ROOT / "config" / "aliases.json"

# Proponent strings that are not a single resolvable organization.
_JUNK_PROPONENTS = {
    "", "unknown", "n/a", "na", "none", "various", "multiple",
    "multiple proponents", "tbd", "to be determined", "private", "public",
    "private developer", "not specified", "confidential",
}
_MIN_NAME_LEN = 4

_last_request_ts = 0.0


# ── HTTP (isolated so tests can monkeypatch _get_json) ───────────────────────

def _get_json(params: dict) -> dict:
    """Rate-limited GET against the Wikidata API. Returns parsed JSON
    ({} on failure)."""
    global _last_request_ts
    wait = RATE_LIMIT_S - (time.monotonic() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.monotonic()
    qs = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{qs}",
                                 headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [warn] Wikidata request failed: {e}")
        return {}


# ── Wikidata lookups ─────────────────────────────────────────────────────────

# An accepted entity's description must look like an ORGANIZATION — this
# rejects concept entities (a proponent string like "Transportation" resolves
# to the concept of transport, which is not an org and whose aliases would
# poison the alias table).
_ORG_DESC_HINTS = (
    "company", "corporation", "organization", "organisation", "agency",
    "utility", "government", "ministry", "department", "municipality",
    "university", "college", "authority", "cooperative", "co-operative",
    "subsidiary", "conglomerate", "enterprise", "manufacturer", "producer",
    "operator", "developer", "railway", "airline", "bank", "crown",
    "business", "firm", "miner", "mining", "energy", "pipeline",
    "telecommunications", "institution", "first nation", "band",
)


def _looks_like_org(description: str) -> bool:
    d = (description or "").lower()
    return any(h in d for h in _ORG_DESC_HINTS)


def search_entity(name: str) -> dict | None:
    """wbsearchentities: best matching item for an org name, or None.

    Accepts a hit only when (a) its label or one of its match aliases is a
    close string match to the query (ratio >= 0.85) AND (b) its description
    looks like an organization — guards against Wikidata returning a loosely
    related entity or a bare concept for an obscure proponent.
    """
    data = _get_json({
        "action": "wbsearchentities", "search": name,
        "language": "en", "uselang": "en", "type": "item", "limit": 5,
    })
    target = name.strip().lower()
    for hit in data.get("search", []):
        if not _looks_like_org(hit.get("description", "")):
            continue
        candidates = [hit.get("label", "")]
        match = hit.get("match") or {}
        if match.get("text"):
            candidates.append(match["text"])
        candidates.extend(hit.get("aliases") or [])
        for c in candidates:
            if c and SequenceMatcher(None, target, c.strip().lower()).ratio() >= 0.85:
                return {"id": hit.get("id"), "label": hit.get("label", ""),
                        "description": hit.get("description", "")}
    return None


def fetch_aliases(entity_id: str) -> list[str]:
    """wbgetentities props=aliases|labels for en + fr. Returns alias list."""
    data = _get_json({
        "action": "wbgetentities", "ids": entity_id,
        "props": "aliases|labels", "languages": "en|fr",
    })
    ent = (data.get("entities") or {}).get(entity_id) or {}
    out: list[str] = []
    for lang in ("en", "fr"):
        lbl = (ent.get("labels") or {}).get(lang)
        if lbl and lbl.get("value"):
            out.append(lbl["value"])
        for a in (ent.get("aliases") or {}).get(lang, []):
            if a.get("value"):
                out.append(a["value"])
    # Dedup preserving order, drop ticker-like noise and very short strings
    seen, cleaned = set(), []
    for a in out:
        a = re.sub(r"\s+", " ", a).strip()
        if len(a) < 2 or a.lower() in seen:
            continue
        seen.add(a.lower())
        cleaned.append(a)
    return cleaned


def harvest_for_name(name: str) -> dict | None:
    """Full harvest for one org name. Returns
    {name, entity_id, label, aliases[]} or None when unresolvable."""
    hit = search_entity(name)
    if not hit or not hit.get("id"):
        return None
    aliases = fetch_aliases(hit["id"])
    aliases = [a for a in aliases if a.strip().lower() != name.strip().lower()]
    return {"name": name, "entity_id": hit["id"],
            "label": hit.get("label", ""), "aliases": aliases}


# ── Name gathering ───────────────────────────────────────────────────────────

def clean_proponent(raw: str) -> str | None:
    """Normalize a proponent string; None when it's junk/unresolvable."""
    if not raw:
        return None
    s = re.sub(r"\s+", " ", raw).strip().strip(".,;")
    if len(s) < _MIN_NAME_LEN or s.lower() in _JUNK_PROPONENTS:
        return None
    # Un-invert registry-style names: "Whitehorse, City of" -> "City of Whitehorse"
    m = re.match(
        r"^(?P<place>.+?),\s*(?P<prefix>(?:City|Town|Village|Municipality|"
        r"District|County|Province|Government|Regional Municipality|"
        r"Rural Municipality) of)$", s, re.IGNORECASE)
    if m:
        s = f"{m.group('prefix')} {m.group('place')}"
    # Multi-org strings ("A / B joint venture", "A and B") resolve poorly —
    # take only clearly single names.
    if re.search(r"\b(joint venture|consortium|partnership)\b", s, re.I):
        return None
    if s.count("/") >= 1 or s.count(";") >= 1:
        return None
    return s


def gather_org_names(conn, limit: int) -> list[str]:
    """Org names from organizations table first, topped up from proponents."""
    names: list[str] = []
    rows = conn.execute(
        "SELECT canonical_name FROM organizations ORDER BY id").fetchall()
    for r in rows:
        n = clean_proponent(r[0])
        if n and n not in names:
            names.append(n)

    if len(names) < limit:
        counts: Counter = Counter()
        for (prop,) in conn.execute(
                "SELECT proponent FROM projects "
                "WHERE proponent IS NOT NULL AND TRIM(proponent) != ''"):
            n = clean_proponent(prop)
            if n:
                counts[n] += 1
        for n, _c in counts.most_common():
            if n not in names:
                names.append(n)
            if len(names) >= limit:
                break
    return names[:limit]


# ── Persistence ──────────────────────────────────────────────────────────────

def apply_to_db(conn, harvested: list[dict]) -> int:
    """Insert aliases via the existing org helpers. Returns rows inserted."""
    import db as dbmod
    inserted = 0
    for h in harvested:
        org_id = dbmod.resolve_organization(conn, h["name"])
        if not org_id:
            continue
        for alias in h["aliases"]:
            norm = dbmod._normalize_org_name(alias).lower()
            if not norm:
                continue
            with conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO organization_aliases "
                    "(organization_id, alias, alias_normalized) VALUES (?, ?, ?)",
                    (org_id, alias, norm))
            inserted += cur.rowcount
    return inserted


def write_snapshot(harvested: list[dict], path: Path = SNAPSHOT_PATH) -> None:
    """Flat {canonical_name: [aliases...]} snapshot, merged over any existing
    file so repeated partial runs accumulate (additive only)."""
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    for h in harvested:
        prev = existing.get(h["name"], [])
        merged = list(prev)
        for a in h["aliases"]:
            if a not in merged:
                merged.append(a)
        existing[h["name"]] = merged
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False,
                               sort_keys=True), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=50,
                    help="Max org names to query (default 50)")
    ap.add_argument("--apply", action="store_true",
                    help="Write aliases to the DB (default: dry run)")
    ap.add_argument("--db", default=str(_BACKEND_ROOT / "dashboard.db"))
    args = ap.parse_args(argv)

    import sqlite3
    if args.apply:
        conn = sqlite3.connect(args.db)
    else:
        conn = sqlite3.connect(
            f"file:{Path(args.db).as_posix()}?mode=ro", uri=True)

    names = gather_org_names(conn, args.limit)
    print(f"{'APPLY' if args.apply else 'DRY RUN'}: querying Wikidata for "
          f"{len(names)} organization names (1 req/s)...")

    harvested = []
    for i, name in enumerate(names, 1):
        result = harvest_for_name(name)
        if result and result["aliases"]:
            harvested.append(result)
            print(f"  [{i}/{len(names)}] {name} -> {result['entity_id']} "
                  f"({len(result['aliases'])} aliases): "
                  f"{', '.join(result['aliases'][:5])}"
                  f"{' ...' if len(result['aliases']) > 5 else ''}")
        else:
            print(f"  [{i}/{len(names)}] {name} -> no confident match")

    write_snapshot(harvested)
    print(f"\nSnapshot written to {SNAPSHOT_PATH} "
          f"({len(harvested)} orgs with aliases).")

    if args.apply:
        n = apply_to_db(conn, harvested)
        print(f"Inserted {n} alias rows into organization_aliases.")
    else:
        total = sum(len(h["aliases"]) for h in harvested)
        print(f"Dry run — {total} aliases NOT written to DB. "
              f"Re-run with --apply to insert.")
    conn.close()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
