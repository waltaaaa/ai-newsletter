# -*- coding: utf-8 -*-
"""One-shot project-list cleanup: sector normalization, Other reclassification,
parsed_value backfill, conservative project_type inference.

Dry-run by default; --apply commits. Prints per-step counts and a sample of
every change class. Does NOT delete rows, touch evidence, or regress status.
"""
import argparse
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normalize import parse_value  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "dashboard.db"

CANONICAL_SECTORS = {
    "oil_gas", "mining", "infrastructure", "power_energy", "manufacturing",
    "transport_logistics", "healthcare", "education", "residential",
    "commercial_mixed", "agriculture", "forestry", "defence", "telecom",
    "indigenous", "environment", "tourism_culture", "government",
}

# Display label (lowercased, trimmed) -> canonical key
SECTOR_LABEL_MAP = {
    "infrastructure": "infrastructure",
    "water & wastewater": "infrastructure",
    "dams": "infrastructure",
    "transit & rail": "transport_logistics",
    "transit": "transport_logistics",
    "railways": "transport_logistics",
    "ports & logistics": "transport_logistics",
    "marine port facilities": "transport_logistics",
    "marine port projects": "transport_logistics",
    "public highways": "transport_logistics",
    "energy": "power_energy",
    "clean energy": "power_energy",
    "power plants": "power_energy",
    "energy storage facilities": "power_energy",
    "electric transmission lines": "power_energy",
    "mining": "mining",
    "mineral mines": "mining",
    "coal mines": "mining",
    "sand and gravel pits": "mining",
    "construction stone and industrial mineral quarries": "mining",
    "housing": "residential",
    "healthcare": "healthcare",
    "education": "education",
    "technology": "telecom",
    "technology & data": "telecom",
    "telecommunications": "telecom",
    "defence": "defence",
    "manufacturing": "manufacturing",
    "oil refineries": "oil_gas",
    "transmission pipelines": "oil_gas",
    "natural gas processing plants": "oil_gas",
    "organic and inorganic chemical industry": "manufacturing",
    "non-metallic mineral products industries": "manufacturing",
    "solid waste management": "environment",
    "hazardous waste management": "environment",
    "local government solid waste management facilities": "environment",
    "water diversion": "environment",
    "groundwater extraction": "environment",
    "shoreline modification": "environment",
    "resort developments": "tourism_culture",
    "ski resorts": "tourism_culture",
    "agriculture": "agriculture",
}

# Ordered keyword rules for sector=Other reclassification. First match wins.
# Patterns are checked against lowercased "name + description".
OTHER_RULES = [
    ("power_energy", r"wind farm|solar|photovolta|hydroelectric|hydro dam|power plant|"
                     r"generating station|power grid|transmission line|substation|"
                     r"battery storage|energy storage|biomass power|nuclear|"
                     r"ev charging|electric vehicle charging|electrical upgrade|"
                     r"electrification|microgrid|power generation|transmission station|"
                     r"électri|énergie|\bkv\b"),
    ("oil_gas", r"\blng\b|natural gas|oil sands|refiner|petroleum|gas plant|"
                r"gas pipeline|oil pipeline|well site|drilling program"),
    ("mining", r"\bmine\b|\bmines\b|\bmining\b|quarry|tailings|gravel pit|"
               r"aggregate pit|mineral exploration|exploration drilling|"
               r"sand and gravel|peat extraction"),
    ("transport_logistics", r"highway|\broad\b|bridge|interchange|overpass|transit|"
                            r"\brail\b|railway|\bport\b|harbour|harbor|wharf|"
                            r"\bdock\b|dredging|airport|runway|ferry|trail bridge|"
                            r"navigation|asphalt|intersection"),
    ("healthcare", r"hospital|health centre|health center|long-term care|"
                   r"care facility|medical|clinic"),
    ("education", r"\bschool\b|university|college|campus|child care|childcare|daycare"),
    ("environment", r"remediation|landfill|waste management|wastewater lagoon|"
                    r"contaminated|septic|biocontrol|habitat|wetland|conservation|"
                    r"flood mitigation|flood protection|erosion|revetment|"
                    r"environmental assessment revitalization"),
    ("infrastructure", r"water treatment|wastewater|sewer|stormwater|drainage|"
                       r"ditching|water main|watermain|water system|water supply|"
                       r"lift station|lagoon|culvert|municipal well|"
                       r"\bdam\b|reservoir|diversion|retention facility|"
                       r"retention pond"),
    ("residential", r"housing|subdivision|residential|apartment|condominium|"
                    r"\bcondo\b|seniors' residence|duplex|cottage lot|"
                    r"cottage development"),
    ("defence", r"\bdnd\b|armoury|garrison|military|\bcfb\b|defence|naval"),
    ("government", r"courthouse|correctional|penitentiary|institution -|"
                   r"detachment|federal building|city hall|fire hall|fire station|"
                   r"police station|\bbed living unit\b"),
    ("tourism_culture", r"casino|resort|museum|campground|marina|arena|stadium|"
                        r"recreation centre|recreation center|cultural centre|"
                        r"wildlife centre|visitor centre|\bpark improvement|"
                        r"golf course|golf and country|\blodge\b"),
    ("forestry", r"sawmill|timber|logging|forest management|forestry|\blumber\b|"
                 r"wood product"),
    ("agriculture", r"\bfarm\b(?! site)|irrigation|grain|livestock|greenhouse|"
                    r"\bcrop\b|fertilizer|fertiliser|\bmink\b|\bhog\b|poultry|"
                    r"dairy|feedlot|abattoir|\bcanola\b|\bpotato"),
    ("manufacturing", r"processing plant|processing facility|packing facility|"
                      r"pet foods|pharmaceutical|ready mix|concrete plant|"
                      r"manufacturing|fabrication"),
    ("commercial_mixed", r"hotel|retail|\boffice\b|mixed-use|mixed use|shopping|"
                         r"warehouse|distribution centre|distribution center"),
    ("telecom", r"data centre|data center|\bai cent|broadband|fibre|fiber optic|"
                r"telecommunication|tower install|camera mast"),
    ("indigenous", r"first nation|\bcree\b|\binuit\b|m[ée]tis|ojibway|innu\b|"
                   r"mi'kmaq|band council"),
]

# Conservative project_type inference. First match wins; only fills NULLs.
TYPE_RULES = [
    ("expansion", r"expansion|\bexpand\b"),
    ("redevelopment", r"redevelopment"),
    ("adaptive_reuse", r"adaptive reuse|adaptive re-use"),
    ("major_renovation", r"renovation"),
    ("retrofit", r"retrofit"),
    ("restoration", r"restoration"),
    ("remediation", r"remediation"),
    ("conversion", r"\bconversion\b"),
    ("modernization", r"moderni[sz]ation|\bupgrade"),
    ("decommission_replace", r"replacement|decommission|\breplace\b"),
]

OTHER_RULES = [(k, re.compile(p)) for k, p in OTHER_RULES]
TYPE_RULES = [(k, re.compile(p)) for k, p in TYPE_RULES]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform changes (default: dry-run)")
    args = ap.parse_args()

    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ---- Step 1: parsed_value backfill -------------------------------------
    updates_pv = []
    for r in cur.execute("SELECT rowid, value FROM projects WHERE parsed_value IS NULL"):
        pv = parse_value(r["value"])
        if pv is not None and pv > 0:
            updates_pv.append((pv, r["rowid"]))
    print(f"[1] parsed_value backfill: {len(updates_pv)} rows parseable "
          f"(of {cur.execute('SELECT COUNT(*) FROM projects WHERE parsed_value IS NULL').fetchone()[0]} NULL)")

    # ---- Step 2: sector label normalization ---------------------------------
    updates_sector = []
    label_counts = Counter()
    for r in cur.execute("SELECT rowid, sector FROM projects WHERE sector IS NOT NULL"):
        raw = (r["sector"] or "").strip()
        if raw in CANONICAL_SECTORS or not raw:
            continue
        key = SECTOR_LABEL_MAP.get(raw.lower())
        if key:
            updates_sector.append((key, r["rowid"]))
            label_counts[f"{raw} -> {key}"] += 1
    print(f"[2] sector label normalization: {len(updates_sector)} rows")
    for lbl, c in label_counts.most_common(12):
        print(f"      {lbl}: {c}")

    # ---- Step 3: sector=Other keyword reclassification ----------------------
    updates_other = []
    other_counts = Counter()
    unmatched = 0
    for r in cur.execute("SELECT rowid, name, description FROM projects WHERE TRIM(sector)='Other'"):
        text = ((r["name"] or "") + " " + (r["description"] or "")).lower()
        for key, pat in OTHER_RULES:
            if pat.search(text):
                updates_other.append((key, r["rowid"]))
                other_counts[key] += 1
                break
        else:
            unmatched += 1
    print(f"[3] Other reclassification: {len(updates_other)} matched, {unmatched} stay Other")
    for k, c in other_counts.most_common():
        print(f"      -> {k}: {c}")

    # ---- Step 4: project_type inference -------------------------------------
    updates_type = []
    type_counts = Counter()
    for r in cur.execute("""SELECT rowid, name, description FROM projects
                            WHERE project_type IS NULL OR TRIM(project_type)=''"""):
        text = ((r["name"] or "") + " " + (r["description"] or "")).lower()
        for key, pat in TYPE_RULES:
            if pat.search(text):
                updates_type.append((key, r["rowid"]))
                type_counts[key] += 1
                break
    n_null_type = cur.execute(
        "SELECT COUNT(*) FROM projects WHERE project_type IS NULL OR TRIM(project_type)=''"
    ).fetchone()[0]
    print(f"[4] project_type inference: {len(updates_type)} of {n_null_type} NULL rows")
    for k, c in type_counts.most_common():
        print(f"      -> {k}: {c}")

    if not args.apply:
        print("\nDRY RUN — no changes written. Re-run with --apply.")
        return

    cur.executemany("UPDATE projects SET parsed_value=? WHERE rowid=?", updates_pv)
    cur.executemany("UPDATE projects SET sector=? WHERE rowid=?", updates_sector)
    cur.executemany("UPDATE projects SET sector=? WHERE rowid=?", updates_other)
    cur.executemany("UPDATE projects SET project_type=? WHERE rowid=?", updates_type)
    con.commit()
    print(f"\nAPPLIED: {len(updates_pv)} parsed_value, {len(updates_sector)} sector labels, "
          f"{len(updates_other)} Other reclasses, {len(updates_type)} project_types.")


if __name__ == "__main__":
    main()
