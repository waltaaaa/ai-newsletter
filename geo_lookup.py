"""
geo_lookup.py — Offline municipality geocoding (NO runtime network).

lookup(municipality, province) resolves a Canadian municipality to a
lat/lon with three fallback tiers:

  1. Exact census-subdivision match against config/geo_municipalities.json
     (built once by tools/build_geo_lookup.py from the StatsCan 2021 Census
     Geographic Attribute File, ~5,200 CSDs, population-weighted
     representative points)
  2. CMA centroid (the ~40 major CMA/CA centroids hardcoded below)
  3. Province centroid (13 provinces/territories hardcoded below)

Returns {"lat": float, "lon": float, "source": "csd"|"cma"|"province",
"csduid": str|None} or None when even the province is unknown.

The name normalizer lives HERE and is imported by the builder so the two
can never drift: lowercase, accents stripped, whitespace/punctuation
collapsed ("Montréal" == "montreal", "St. John's" == "st johns").
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
GEO_DATA_PATH = _BACKEND_ROOT / "config" / "geo_municipalities.json"

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")

# Province/territory name -> 2-letter code
_PROV_CODES = {
    "british columbia": "BC", "alberta": "AB", "saskatchewan": "SK",
    "manitoba": "MB", "ontario": "ON", "quebec": "QC",
    "new brunswick": "NB", "nova scotia": "NS",
    "prince edward island": "PE", "pei": "PE",
    "newfoundland and labrador": "NL", "newfoundland": "NL",
    "yukon": "YT", "northwest territories": "NT", "nunavut": "NU",
}
_VALID_CODES = {"BC", "AB", "SK", "MB", "ON", "QC", "NB", "NS", "PE", "NL",
                "YT", "NT", "NU"}


def normalize_place(name: str) -> str:
    """Normalize a municipality name for matching.

    Lowercase, strip accents (NFKD fold to ASCII), strip punctuation,
    collapse whitespace. 'Montréal' -> 'montreal'; "St. John's" -> 'st johns'.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = s.replace("'", "")  # St. John's -> st johns (not 'st john s')
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def norm_province(raw: str) -> str:
    """Province name or code -> 2-letter code ('' when unrecognized)."""
    if not raw:
        return ""
    s = str(raw).strip()
    if len(s) == 2 and s.upper() in _VALID_CODES:
        return s.upper()
    return _PROV_CODES.get(normalize_place(s), "")


# ── Hardcoded fallback centroids ─────────────────────────────────────────────

# ~40 major CMA/CA centroids (city hall / urban core, approximate).
CMA_CENTROIDS = {
    ("toronto", "ON"): (43.6532, -79.3832),
    ("montreal", "QC"): (45.5019, -73.5674),
    ("vancouver", "BC"): (49.2827, -123.1207),
    ("calgary", "AB"): (51.0447, -114.0719),
    ("edmonton", "AB"): (53.5461, -113.4938),
    ("ottawa", "ON"): (45.4215, -75.6972),
    ("gatineau", "QC"): (45.4765, -75.7013),
    ("winnipeg", "MB"): (49.8951, -97.1384),
    ("quebec", "QC"): (46.8139, -71.2080),
    ("quebec city", "QC"): (46.8139, -71.2080),
    ("hamilton", "ON"): (43.2557, -79.8711),
    ("kitchener", "ON"): (43.4516, -80.4925),
    ("waterloo", "ON"): (43.4643, -80.5204),
    ("london", "ON"): (42.9849, -81.2453),
    ("victoria", "BC"): (48.4284, -123.3656),
    ("halifax", "NS"): (44.6488, -63.5752),
    ("oshawa", "ON"): (43.8971, -78.8658),
    ("windsor", "ON"): (42.3149, -83.0364),
    ("saskatoon", "SK"): (52.1332, -106.6700),
    ("regina", "SK"): (50.4452, -104.6189),
    ("st catharines", "ON"): (43.1594, -79.2469),
    ("niagara falls", "ON"): (43.0896, -79.0849),
    ("st johns", "NL"): (47.5615, -52.7126),
    ("barrie", "ON"): (44.3894, -79.6903),
    ("kelowna", "BC"): (49.8880, -119.4960),
    ("sherbrooke", "QC"): (45.4042, -71.8929),
    ("guelph", "ON"): (43.5448, -80.2482),
    ("abbotsford", "BC"): (49.0504, -122.3045),
    ("kingston", "ON"): (44.2312, -76.4860),
    ("trois rivieres", "QC"): (46.3432, -72.5430),
    ("moncton", "NB"): (46.0878, -64.7782),
    ("saguenay", "QC"): (48.4279, -71.0686),
    ("brantford", "ON"): (43.1394, -80.2644),
    ("thunder bay", "ON"): (48.3809, -89.2477),
    ("sudbury", "ON"): (46.4917, -80.9930),
    ("greater sudbury", "ON"): (46.4917, -80.9930),
    ("peterborough", "ON"): (44.3091, -78.3197),
    ("saint john", "NB"): (45.2733, -66.0633),
    ("lethbridge", "AB"): (49.6956, -112.8451),
    ("red deer", "AB"): (52.2681, -113.8112),
    ("nanaimo", "BC"): (49.1659, -123.9401),
    ("fredericton", "NB"): (45.9636, -66.6431),
    ("charlottetown", "PE"): (46.2382, -63.1311),
    ("whitehorse", "YT"): (60.7212, -135.0568),
    ("yellowknife", "NT"): (62.4540, -114.3718),
    ("iqaluit", "NU"): (63.7467, -68.5170),
}

# 13 province/territory geographic centroids (approximate).
PROVINCE_CENTROIDS = {
    "BC": (54.7267, -127.6476),
    "AB": (55.0000, -115.0000),
    "SK": (54.6000, -105.8000),
    "MB": (54.8000, -97.7000),
    "ON": (50.0000, -85.0000),
    "QC": (52.0000, -71.7500),
    "NB": (46.5000, -66.4600),
    "NS": (45.1000, -63.2000),
    "PE": (46.4000, -63.3000),
    "NL": (53.1000, -60.0000),
    "YT": (64.0000, -135.0000),
    "NT": (64.8000, -121.0000),
    "NU": (66.0000, -94.0000),
}


# ── Data file (lazy singleton) ───────────────────────────────────────────────

_geo_data: dict | None = None


def _load_geo_data(path: Path = GEO_DATA_PATH) -> dict:
    global _geo_data
    if _geo_data is None:
        try:
            _geo_data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            _geo_data = {}
        _geo_data.pop("_meta", None)
    return _geo_data


# ── Public API ───────────────────────────────────────────────────────────────

def lookup(municipality: str, province: str,
           _data: dict | None = None) -> dict | None:
    """Resolve a municipality + province to lat/lon. No network, ever.

    Fallback chain: exact CSD -> CMA centroid -> province centroid -> None.
    `_data` lets tests inject a small fixture dict instead of the full file.
    """
    prov = norm_province(province)
    muni = normalize_place(municipality)

    if prov and muni:
        data = _data if _data is not None else _load_geo_data()
        hit = data.get(f"{muni}|{prov}")
        if hit:
            return {"lat": hit["lat"], "lon": hit["lon"],
                    "source": "csd", "csduid": hit.get("csduid")}
        cma = CMA_CENTROIDS.get((muni, prov))
        if cma:
            return {"lat": cma[0], "lon": cma[1],
                    "source": "cma", "csduid": None}

    if prov in PROVINCE_CENTROIDS:
        lat, lon = PROVINCE_CENTROIDS[prov]
        return {"lat": lat, "lon": lon, "source": "province", "csduid": None}
    return None
