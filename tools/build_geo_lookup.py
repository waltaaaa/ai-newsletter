"""
build_geo_lookup.py — One-time builder for config/geo_municipalities.json.

Downloads the StatsCan 2021 Census Geographic Attribute File (GAF,
publication 92-151-X — confirmed live 2026-06-10):

    https://www12.statcan.gc.ca/census-recensement/2021/geo/aip-pia/
        attribute-attribs/files-fichiers/2021_92-151_X.zip
    (~9.8 MB zip containing 2021_92-151_X.csv, ~285 MB, one row per
     dissemination block)

The GAF carries a representative-point lat/lon per DISSEMINATION AREA
(columns DARPLAT_ADLAT / DARPLONG_ADLONG) plus the census subdivision id,
name and province for every block. This builder aggregates DA rep points to
a population-weighted centroid per CSD (~5,160 CSDs) and emits:

    config/geo_municipalities.json
    {"<normalized_csd_name>|<2-letter-prov>":
        {"lat": .., "lon": .., "csduid": "....."}, ...}

Name normalization is imported from the runtime module geo_lookup.py
(normalize_place) so builder and runtime can never drift. When two CSDs in
the same province share a normalized name (e.g. several "Sainte-Anne" type
villages), the higher-population CSD wins and the collision is reported.

Usage (from backend/, network required for --download):
    python tools/build_geo_lookup.py                 # download + build
    python tools/build_geo_lookup.py --zip path.zip  # reuse a local zip

Zero cost — StatCan census geography files are free public data.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from geo_lookup import normalize_place  # noqa: E402 — single normalizer

GAF_URL = ("https://www12.statcan.gc.ca/census-recensement/2021/geo/aip-pia/"
           "attribute-attribs/files-fichiers/2021_92-151_X.zip")
OUT_PATH = _BACKEND_ROOT / "config" / "geo_municipalities.json"
USER_AGENT = ("CanadianMacroDashboard/1.0 "
              "(+https://github.com/lagging-indicator; geo lookup builder; "
              "contact: walterbolduc@gmail.com)")

# 2021 PRUID -> 2-letter province code
PRUID_TO_CODE = {
    "10": "NL", "11": "PE", "12": "NS", "13": "NB", "24": "QC", "35": "ON",
    "46": "MB", "47": "SK", "48": "AB", "59": "BC", "60": "YT", "61": "NT",
    "62": "NU",
}

# GAF column names (English_French headers)
COL_PRUID = "PRUID_PRIDU"
COL_CSDUID = "CSDUID_SDRIDU"
COL_CSDNAME = "CSDNAME_SDRNOM"
COL_LAT = "DARPLAT_ADLAT"
COL_LON = "DARPLONG_ADLONG"
COL_POP = "DBPOP2021_IDPOP2021"


def download(url: str = GAF_URL, dest: Path | None = None) -> Path:
    dest = dest or (_BACKEND_ROOT / ".tmp_geo" / "gaf2021.zip")
    dest.parent.mkdir(exist_ok=True)
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as resp:
        dest.write_bytes(resp.read())
    print(f"  -> {dest} ({dest.stat().st_size:,} bytes)")
    return dest


def build_from_zip(zip_path: Path) -> dict:
    """Stream the GAF CSV and aggregate DA rep points to CSD centroids."""
    # Per CSD: [sum_w_lat, sum_w_lon, sum_w, pop, name, prov]
    agg: dict[str, list] = {}
    z = zipfile.ZipFile(zip_path)
    csv_name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    rows = 0
    with z.open(csv_name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))
        for row in reader:
            rows += 1
            csduid = row.get(COL_CSDUID) or ""
            if not csduid:
                continue
            try:
                lat = float(row.get(COL_LAT) or "")
                lon = float(row.get(COL_LON) or "")
            except ValueError:
                continue
            try:
                pop = float(row.get(COL_POP) or 0) or 0.0
            except ValueError:
                pop = 0.0
            w = pop if pop > 0 else 0.001  # zero-pop blocks still count a little
            a = agg.get(csduid)
            if a is None:
                prov = PRUID_TO_CODE.get((row.get(COL_PRUID) or "").strip(), "")
                agg[csduid] = [w * lat, w * lon, w, pop,
                               (row.get(COL_CSDNAME) or "").strip(), prov]
            else:
                a[0] += w * lat
                a[1] += w * lon
                a[2] += w
                a[3] += pop
    print(f"  scanned {rows:,} dissemination blocks -> {len(agg):,} CSDs")

    out: dict[str, dict] = {}
    pop_by_key: dict[str, float] = {}
    collisions = defaultdict(int)
    for csduid, (slat, slon, sw, pop, name, prov) in agg.items():
        if not (name and prov and sw > 0):
            continue
        key = f"{normalize_place(name)}|{prov}"
        if key in out:
            collisions[key] += 1
            if pop <= pop_by_key[key]:
                continue  # keep the more populous CSD
        out[key] = {"lat": round(slat / sw, 5), "lon": round(slon / sw, 5),
                    "csduid": csduid}
        pop_by_key[key] = pop
    if collisions:
        print(f"  {len(collisions)} normalized-name collisions resolved by "
              f"population (e.g. {list(collisions)[:3]})")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", help="Reuse a local GAF zip instead of downloading")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args(argv)

    zip_path = Path(args.zip) if args.zip else download()
    data = build_from_zip(zip_path)

    payload = {"_meta": {
        "source": GAF_URL,
        "description": "CSD population-weighted representative-point "
                       "centroids from the StatsCan 2021 Census Geographic "
                       "Attribute File (92-151-X). Built by "
                       "tools/build_geo_lookup.py. Keys are "
                       "normalize_place(csd_name)|prov_code.",
        "entries": len(data),
    }}
    payload.update(dict(sorted(data.items())))
    Path(args.out).write_text(
        json.dumps(payload, indent=0, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(data):,} entries to {args.out}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
