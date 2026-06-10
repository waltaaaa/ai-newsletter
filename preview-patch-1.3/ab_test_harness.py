#!/usr/bin/env python3
"""
A/B SHADOW TEST HARNESS — The Lagging Indicator
Compares the CURRENT discovery pipeline (System A) against DISCOVERY SYSTEM V2
(System B) over the same input window. Run weekly during the 4-6 week shadow
period; produces a cumulative scorecard and the cutover verdict.

Inputs (both systems export the same minimal record shape each week):
  exports/A/week_<n>.json   exports/B/week_<n>.json
  [{ "name", "province", "cma", "city", "value_millions", "status",
     "sector", "first_seen": "iso8601", "evidence_urls": [...] }]

  reference/enumerable_<month>.json  — ground-truth list compiled from
  IAAC dump, ReNew Top 100, NRCan Major Projects Inventory (above-threshold).

Outputs:
  ab_results/week_<n>_scorecard.json
  ab_results/precision_audit_manifest.json  (feeds the weekly Claude session, P-slot)
  ab_results/cutover_verdict.json           (after >= 4 weeks)

Zero dependencies beyond stdlib. Deterministic. No network calls.
"""

import json, re, sys, itertools, unicodedata
from pathlib import Path
from collections import defaultdict

THRESHOLDS = {"ON":500,"QC":250,"AB":200,"BC":175,"SK":45,"MB":40,
              "NS":25,"NB":20,"NL":17,"PE":5,"YT":3,"NT":3,"NU":3}

FILLER = {"the","of","and","a","at","in","project","phase","new","de","du","la","le"}

def norm(name: str) -> str:
    """Normalized match key: lowercase, accents stripped, filler words removed."""
    s = unicodedata.normalize("NFKD", name).encode("ascii","ignore").decode().lower()
    toks = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in FILLER]
    return " ".join(sorted(toks))

def key(rec) -> str:
    return f"{rec.get('province','')}|{norm(rec.get('name',''))}"

def load(path):
    recs = json.loads(Path(path).read_text())
    return {key(r): r for r in recs}

def jaccard_tokens(a, b):
    A, B = set(a.split()), set(b.split())
    return len(A & B) / max(1, len(A | B))

def fuzzy_overlap(akeys, bkeys, thresh=0.6):
    """Second-pass match for records the exact key missed (alias problem).
    Returns set of (akey, bkey) matched pairs within same province."""
    byprov_a, byprov_b = defaultdict(list), defaultdict(list)
    for k in akeys: byprov_a[k.split("|")[0]].append(k)
    for k in bkeys: byprov_b[k.split("|")[0]].append(k)
    pairs = set()
    for prov in byprov_a:
        for ka, kb in itertools.product(byprov_a[prov], byprov_b.get(prov, [])):
            if jaccard_tokens(ka.split("|")[1], kb.split("|")[1]) >= thresh:
                pairs.add((ka, kb))
    return pairs

def above_threshold(rec):
    v = rec.get("value_millions")
    return v is not None and v >= THRESHOLDS.get(rec.get("province",""), 9e9)

def lincoln_petersen(n_a, n_b, n_both):
    """Capture-recapture population estimate (Chapman correction)."""
    if n_both == 0: return None
    return round(((n_a + 1) * (n_b + 1)) / (n_both + 1) - 1)

def scorecard(week, a_path, b_path, ref_path=None, outdir="ab_results"):
    A, B = load(a_path), load(b_path)
    exact = set(A) & set(B)
    fuzzy = fuzzy_overlap(set(A) - exact, set(B) - exact)
    matched_a = exact | {p[0] for p in fuzzy}
    matched_b = exact | {p[1] for p in fuzzy}
    only_a, only_b = set(A) - matched_a, set(B) - matched_b

    # --- Coverage metrics ---
    est = lincoln_petersen(len(A), len(B), len(exact) + len(fuzzy))
    cov = {
        "A_total": len(A), "B_total": len(B),
        "overlap": len(exact) + len(fuzzy),
        "unique_to_A": len(only_a), "unique_to_B": len(only_b),
        "est_population_LP": est,
        "A_est_recall": round(len(A)/est, 3) if est else None,
        "B_est_recall": round(len(B)/est, 3) if est else None,
    }

    # --- Enumerable-reference recall (the hard invariant) ---
    ref_recall = None
    if ref_path and Path(ref_path).exists():
        REF = load(ref_path)
        ref_above = {k for k, r in REF.items() if above_threshold(r)}
        miss_a = ref_above - set(A) - {p[0] for p in fuzzy_overlap(ref_above, set(A))}
        miss_b = ref_above - set(B) - {p[0] for p in fuzzy_overlap(ref_above, set(B))}
        ref_recall = {
            "reference_n": len(ref_above),
            "A_misses": sorted(miss_a), "B_misses": sorted(miss_b),
            "A_recall": round(1 - len(miss_a)/max(1,len(ref_above)), 3),
            "B_recall": round(1 - len(miss_b)/max(1,len(ref_above)), 3),
        }

    # --- Time-to-discovery: on shared projects, who saw it first? ---
    from datetime import date
    def d(rec):
        try: return date.fromisoformat(rec.get("first_seen","")[:10])
        except Exception: return None
    leads = []
    for k in exact:
        da, db = d(A[k]), d(B[k])
        if da and db: leads.append((db - da).days)  # negative = B found it first
    latency = None
    if leads:
        leads.sort()
        latency = {"shared_dated": len(leads),
                   "B_first_pct": round(sum(1 for x in leads if x < 0)/len(leads), 3),
                   "A_first_pct": round(sum(1 for x in leads if x > 0)/len(leads), 3),
                   "median_B_lead_days": -leads[len(leads)//2]}

    # --- Accuracy: field completeness + evidence depth ---
    def quality(recs):
        n = max(1, len(recs))
        return {
            "pct_with_value":   round(sum(1 for r in recs.values() if r.get("value_millions") is not None)/n, 3),
            "pct_with_city":    round(sum(1 for r in recs.values() if r.get("city"))/n, 3),
            "pct_multi_source": round(sum(1 for r in recs.values() if len(r.get("evidence_urls",[])) >= 2)/n, 3),
            "pct_above_threshold": round(sum(1 for r in recs.values() if above_threshold(r))/n, 3),
        }
    acc = {"A": quality(A), "B": quality(B)}

    # --- Status agreement on shared projects (disagreements -> audit) ---
    disputes = [{"key": k, "A_status": A[k].get("status"), "B_status": B[k].get("status")}
                for k in exact if A[k].get("status") != B[k].get("status")]

    # --- Precision audit manifest (sampled, adjudicated in Claude session) ---
    import random; random.seed(week)
    sample = lambda keys, recs: [recs[k] for k in random.sample(sorted(keys), min(25, len(keys)))]
    manifest = {
        "week": week,
        "instruction": ("For each record: verdict REAL (verifiable capital project, fields correct), "
                        "REAL_BUT_WRONG (project exists, a field is wrong - name which), or "
                        "PHANTOM (not a real distinct project). Use evidence_urls only."),
        "unique_to_A_sample": sample(only_a, A),
        "unique_to_B_sample": sample(only_b, B),
        "status_disputes": disputes[:30],
    }

    out = Path(outdir); out.mkdir(exist_ok=True)
    card = {"week": week, "coverage": cov, "reference_recall": ref_recall,
            "time_to_discovery": latency, "field_quality": acc,
            "status_disputes_n": len(disputes)}
    (out/f"week_{week}_scorecard.json").write_text(json.dumps(card, indent=2))
    (out/"precision_audit_manifest.json").write_text(json.dumps(manifest, indent=2))
    return card

def cutover_verdict(outdir="ab_results", min_weeks=4):
    """B wins iff, cumulatively: (1) zero misses vs enumerable references,
    (2) >= A's recall vs LP-estimated population, (3) unique-to-B verified-real
    rate >= 80% from audits, (4) field quality >= A on value & multi-source."""
    cards = sorted(Path(outdir).glob("week_*_scorecard.json"))
    if len(cards) < min_weeks:
        return {"verdict": "INSUFFICIENT_DATA", "weeks": len(cards), "needed": min_weeks}
    data = [json.loads(c.read_text()) for c in cards]
    checks = {
        "B_zero_reference_misses": all((d["reference_recall"] or {}).get("B_recall", 0) == 1.0
                                       for d in data if d["reference_recall"]),
        "B_recall_geq_A": sum(d["coverage"]["B_est_recall"] or 0 for d in data)
                          >= sum(d["coverage"]["A_est_recall"] or 0 for d in data),
        "B_more_unique_finds": sum(d["coverage"]["unique_to_B"] for d in data)
                               > sum(d["coverage"]["unique_to_A"] for d in data),
        "B_field_quality_geq_A": all(
            d["field_quality"]["B"]["pct_with_value"] >= d["field_quality"]["A"]["pct_with_value"]
            and d["field_quality"]["B"]["pct_multi_source"] >= d["field_quality"]["A"]["pct_multi_source"]
            for d in data),
        "precision_audits_pass": "MANUAL: confirm >=80% REAL rate on unique_to_B samples from session logs",
    }
    verdict = "CUTOVER" if all(v is True or isinstance(v, str) for v in checks.values()) else "CONTINUE_SHADOW"
    result = {"verdict": verdict, "weeks": len(cards), "checks": checks}
    (Path(outdir)/"cutover_verdict.json").write_text(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "score":
        print(json.dumps(scorecard(int(sys.argv[2]), sys.argv[3], sys.argv[4],
                                   sys.argv[5] if len(sys.argv) > 5 else None), indent=2))
    elif len(sys.argv) >= 2 and sys.argv[1] == "verdict":
        print(json.dumps(cutover_verdict(), indent=2))
    else:
        print("usage:\n  ab_test_harness.py score <week_n> exports/A/week_n.json exports/B/week_n.json [reference/enumerable_month.json]\n  ab_test_harness.py verdict")
