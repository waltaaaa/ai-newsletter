"""deep_dedup_check.py — Deep fuzzy duplicate scan with comprehensive false-positive filtering."""

import sqlite3
import re
from collections import defaultdict
from difflib import SequenceMatcher

DB_PATH = "dashboard.db"

PHASE_PAT = re.compile(
    r'phase\s*[ivxlcdm\d]+|stage\s*\d|part\s*[a-d\d]|\(a\)|\(b\)|\(c\)|'
    r'contract\s*\d|line\s*\d|route\s*\d',
    re.IGNORECASE,
)


def is_false_positive(a, b):
    """Detect pairs that look similar but are legitimately different projects."""
    na = a["name"].lower()
    nb = b["name"].lower()

    # Different phase/part/contract
    a_ph = set(PHASE_PAT.findall(na))
    b_ph = set(PHASE_PAT.findall(nb))
    if a_ph and b_ph and a_ph != b_ph:
        return True

    # (A) vs (B)
    if ("(a)" in na and "(b)" in nb) or ("(b)" in na and "(a)" in nb):
        return True

    # Different numbered highways/routes
    a_hw = re.findall(r'(?:highway|hwy|route)\s*(\d+)', na)
    b_hw = re.findall(r'(?:highway|hwy|route)\s*(\d+)', nb)
    if a_hw and b_hw and set(a_hw) != set(b_hw):
        return True

    # Different addresses
    a_addr = re.findall(r'\d{3,}\s+\d+', na)
    b_addr = re.findall(r'\d{3,}\s+\d+', nb)
    if a_addr and b_addr and set(a_addr) != set(b_addr):
        return True

    # Different stations on same transit line
    st_pat = re.compile(r'(.+?)\s*(?:station|stop)\s*[-\u2013]\s*(.+)', re.IGNORECASE)
    a_st = st_pat.match(a["name"])
    b_st = st_pat.match(b["name"])
    if a_st and b_st:
        if a_st.group(2).strip().lower() == b_st.group(2).strip().lower():
            if a_st.group(1).strip().lower() != b_st.group(1).strip().lower():
                return True

    # Different schools (Quebec ecole pattern)
    if "cole" in na and "cole" in nb:
        a_after = na.split("scolaire")[-1] if "scolaire" in na else na
        b_after = nb.split("scolaire")[-1] if "scolaire" in nb else nb
        if SequenceMatcher(None, a_after, b_after).ratio() < 0.85:
            return True

    # Alberta Surgical Initiative at different hospitals
    if "surgical initiative" in na and "surgical initiative" in nb:
        a_s = re.search(r'\d+\s*-\s*(.+?)(?:\)|$)', na)
        b_s = re.search(r'\d+\s*-\s*(.+?)(?:\)|$)', nb)
        if a_s and b_s and a_s.group(1).strip() != b_s.group(1).strip():
            return True

    # MDR at different sites
    if "mdr" in na and "mdr" in nb:
        a_s = re.search(r'\((\d+)\s*-', na)
        b_s = re.search(r'\((\d+)\s*-', nb)
        if a_s and b_s and a_s.group(1) != b_s.group(1):
            return True

    # Water vs Wastewater
    a_ww = "wastewater" in na
    b_ww = "wastewater" in nb
    a_w = "water" in na and not a_ww
    b_w = "water" in nb and not b_ww
    if (a_w and b_ww) or (b_w and a_ww):
        return True

    # Opposite cardinal directions (North/South, East/West)
    dirs = {"north", "south", "east", "west"}
    a_dirs = dirs & set(na.split())
    b_dirs = dirs & set(nb.split())
    if a_dirs and b_dirs and a_dirs != b_dirs:
        a_no = " ".join(w for w in na.split() if w not in dirs)
        b_no = " ".join(w for w in nb.split() if w not in dirs)
        if SequenceMatcher(None, a_no, b_no).ratio() > 0.88:
            return True

    # Different GO stations
    if "go station" in na and "go station" in nb:
        a_n = na.replace("go station", "").strip()
        b_n = nb.replace("go station", "").strip()
        if a_n != b_n and SequenceMatcher(None, a_n, b_n).ratio() < 0.80:
            return True

    # Different ouvrage (retention basins)
    if "ouvrage" in na and "ouvrage" in nb:
        a_o = re.search(r'ouvrage\s+(\S+)', na)
        b_o = re.search(r'ouvrage\s+(\S+)', nb)
        if a_o and b_o and a_o.group(1) != b_o.group(1):
            return True

    # Different police posts in different communities
    if "police" in na and "police" in nb:
        a_loc = na.split("police")[-1]
        b_loc = nb.split("police")[-1]
        if SequenceMatcher(None, a_loc, b_loc).ratio() < 0.70:
            return True

    # Different years (2022-23 vs 2023-24)
    a_yr = re.findall(r'20\d{2}(?:-\d{2})?', na)
    b_yr = re.findall(r'20\d{2}(?:-\d{2})?', nb)
    if a_yr and b_yr and set(a_yr) != set(b_yr):
        return True

    # Different counties
    a_co = re.search(r'(\w+)\s+county', na)
    b_co = re.search(r'(\w+)\s+county', nb)
    if a_co and b_co and a_co.group(1) != b_co.group(1):
        return True

    # Different NEWPCC sub-projects
    if "newpcc" in na and "newpcc" in nb:
        a_sub = na.split("newpcc")[-1]
        b_sub = nb.split("newpcc")[-1]
        if SequenceMatcher(None, a_sub, b_sub).ratio() < 0.70:
            return True

    # Maisons des aines in different cities
    if "maison des" in na and "maison des" in nb:
        a_c = na.split("maison des")[-1]
        b_c = nb.split("maison des")[-1]
        if SequenceMatcher(None, a_c, b_c).ratio() < 0.70:
            return True

    # Different school grade ranges in same neighborhood
    grade_pat = re.compile(r'(?:k-?\d|\d+-\d+)\s+(?:school|catholic)')
    if grade_pat.search(na) and grade_pat.search(nb):
        a_g = grade_pat.search(na).group()
        b_g = grade_pat.search(nb).group()
        if a_g != b_g:
            return True

    # Different named towers/complexes (Sentinel vs Lincoln vs Gallery)
    for suffix in ["tower", "residential complex", "residential"]:
        if suffix in na and suffix in nb:
            a_pre = na.split(suffix)[0].strip().split()
            b_pre = nb.split(suffix)[0].strip().split()
            if a_pre and b_pre and a_pre[-1] != b_pre[-1]:
                return True

    # Different bridge rehab (Highway X over Y)
    if "bridge rehabilitation" in na and "bridge rehabilitation" in nb:
        if na != nb:
            return True

    # Different solar/wind projects with different proper names
    for proj_type in ["solar project", "solar", "wind project", "wind"]:
        if proj_type in na and proj_type in nb:
            a_pre = na.split(proj_type)[0].strip()
            b_pre = nb.split(proj_type)[0].strip()
            if a_pre and b_pre and SequenceMatcher(None, a_pre, b_pre).ratio() < 0.70:
                return True

    # Different hospitals
    if "hospital" in na and "hospital" in nb:
        a_h = na.split("hospital")[0].strip()
        b_h = nb.split("hospital")[0].strip()
        if SequenceMatcher(None, a_h, b_h).ratio() < 0.70:
            return True

    # Different long-term care homes in different cities
    if "long-term care" in na and "long-term care" in nb:
        a_c = na.split("long-term care")[0].strip()
        b_c = nb.split("long-term care")[0].strip()
        if a_c and b_c and SequenceMatcher(None, a_c, b_c).ratio() < 0.75:
            return True

    # Different affordable housing projects at different addresses
    if "affordable housing" in na and "affordable housing" in nb:
        a_pre = na.split("affordable housing")[0].strip()
        b_pre = nb.split("affordable housing")[0].strip()
        if a_pre and b_pre and a_pre != b_pre:
            return True

    # Different thermal/power plants with different names
    for plant in ["thermal power plant", "power plant", "thermal plant"]:
        if plant in na and plant in nb:
            a_pre = na.split(plant)[0].strip()
            b_pre = nb.split(plant)[0].strip()
            if a_pre and b_pre and a_pre != b_pre:
                return True

    # Different AI hubs
    if "artificial intelligence hub" in na and "artificial intelligence hub" in nb:
        a_pre = na.split("artificial intelligence")[0].strip()
        b_pre = nb.split("artificial intelligence")[0].strip()
        if a_pre != b_pre:
            return True

    # Different BRT segments
    if "segment" in na and "segment" in nb and "brt" in na.lower() and "brt" in nb.lower():
        a_seg = na.split("segment")[0].strip()
        b_seg = nb.split("segment")[0].strip()
        if a_seg != b_seg:
            return True

    # Different O-Train line directions/stations
    if "o-train" in na and "o-train" in nb:
        a_rest = na.split("o-train")
        b_rest = nb.split("o-train")
        if len(a_rest) > 1 and len(b_rest) > 1:
            if SequenceMatcher(None, a_rest[0], b_rest[0]).ratio() < 0.75:
                return True

    # Different des Neiges sectors
    if "secteur" in na and "secteur" in nb:
        a_sec = re.search(r'secteur\s+(\S+)', na)
        b_sec = re.search(r'secteur\s+(\S+)', nb)
        if a_sec and b_sec and a_sec.group(1) != b_sec.group(1):
            return True

    # Different office conversions at different addresses
    if "office conversion" in na and "office conversion" in nb:
        a_pre = na.split("office conversion")[0].strip()
        b_pre = nb.split("office conversion")[0].strip()
        if a_pre and b_pre and a_pre != b_pre:
            return True

    # Different haltes routieres
    if "halte" in na and "halte" in nb:
        a_h = na.split("halte")[-1]
        b_h = nb.split("halte")[-1]
        if SequenceMatcher(None, a_h, b_h).ratio() < 0.70:
            return True

    # Different hydrogen plants (chemical vs energy use)
    if "hydrog" in na and "hydrog" in nb:
        if ("chimique" in na) != ("chimique" in nb):
            return True
        if ("vert" in na) != ("vert" in nb):
            return True

    # Annacis vs Iona (different WWTP plants)
    proper_wwtp = re.compile(r'^(\w+(?:\s+\w+)?)\s+(?:island\s+)?(?:wastewater|water|wwtp|treatment)', re.IGNORECASE)
    a_wt = proper_wwtp.match(na)
    b_wt = proper_wwtp.match(nb)
    if a_wt and b_wt and a_wt.group(1) != b_wt.group(1):
        return True

    return False


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT rowid, name, province, sector, value, status, cma, proponent, "
        "description, norm_key, confidence FROM projects ORDER BY province, name"
    ).fetchall()
    projects = [dict(r) for r in rows]
    print(f"Total: {len(projects)}")

    by_prov = defaultdict(list)
    for p in projects:
        by_prov[p["province"]].append(p)

    candidates = []
    for prov, pp in by_prov.items():
        n = len(pp)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = pp[i], pp[j]
                na, nb = a["name"], b["name"]
                if abs(len(na) - len(nb)) > max(len(na), len(nb)) * 0.45:
                    continue
                ratio = SequenceMatcher(None, na.lower(), nb.lower()).ratio()
                if ratio < 0.82:
                    continue
                if is_false_positive(a, b):
                    continue

                score = ratio * 100
                if a["sector"] == b["sector"]:
                    score += 10
                if a["cma"] and a["cma"] == b["cma"]:
                    score += 5
                if na.lower() in nb.lower() or nb.lower() in na.lower():
                    score += 15
                if (a["proponent"] and b["proponent"]
                        and a["proponent"].lower() == b["proponent"].lower()):
                    score += 10

                candidates.append({"score": score, "ratio": ratio, "a": a, "b": b})

    candidates.sort(key=lambda x: -x["score"])

    seen = set()
    final = []
    for c in candidates:
        ai, bi = c["a"]["rowid"], c["b"]["rowid"]
        if ai in seen or bi in seen:
            continue
        seen.add(ai)
        seen.add(bi)
        final.append(c)

    print(f"Candidate pairs after filtering: {len(final)}\n")
    for i, c in enumerate(final):
        a, b = c["a"], c["b"]
        print(f"{i+1:2d}. [{c['score']:.0f}] {a['province']} | ratio={c['ratio']:.3f}")
        print(f"    A ({a['rowid']:5d}): {a['name'][:70]}")
        print(f"       sector={a['sector']:20s} status={a['status']:20s} val={str(a['value'])[:15]}")
        print(f"    B ({b['rowid']:5d}): {b['name'][:70]}")
        print(f"       sector={b['sector']:20s} status={b['status']:20s} val={str(b['value'])[:15]}")

    conn.close()


if __name__ == "__main__":
    main()
