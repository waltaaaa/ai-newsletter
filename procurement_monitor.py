"""
Government procurement monitor — tracks federal and provincial contract awards
and tender notices for infrastructure, construction, and major capital projects.

Sources (all free, structured data):
1. Open Canada Proactive Disclosure — awarded contracts with values and vendors
2. CanadaBuys open-data tender CSVs — federal tender notices
   (replaced BuyAndSell RSS — buyandsell.gc.ca DNS-dead, attempt removed
   2026-06-11; no fetch is made against the dead domain)
3. Ontario BPS Supply Chain — DEAD upstream (CKAN package removed 2026);
   skipped with a logged notice — ON coverage via CanadaBuys delivery-region rows
4. BC Bid — legacy RSS retired (platform moved to Ivalua, no public feed);
   skipped with a logged notice — BC coverage via CanadaBuys delivery-region rows
5. SEAO (Québec) — public procurement via Données Québec OCDS files
   (implemented quality-pass-1.4, live-verified 2026-06-10 and 2026-06-11)
6. Alberta Purchasing Connection — provincial RFPs (DARK: Angular SPA, no
   structured data — AB coverage via CanadaBuys delivery-region rows)
7. Defence Construction Canada — recently awarded contracts PDF
   (implemented quality-pass-1.4, live-verified 2026-06-10 and 2026-06-11)
8. SaskTenders — DARK: ASP.NET WebForms, no RSS/open data — SK coverage via
   CanadaBuys delivery-region rows

Instrumentation contract (2026-06-11 procurement fix): every live source prints
one "[PROCUREMENT] <source>: fetched N rows, M after keyword filter, K >= $5M"
line with INDEPENDENT counters (keyword and value predicates are evaluated for
every row, so neither filter can silently hide the other's drop count), and
every fetch failure prints "[PROCUREMENT] <source> FAILED: <error>" — the
exception stays swallowed so the run continues, but dead-source is now
distinguishable from genuinely-zero rows in the logs.

All sources are free. No API keys required for public procurement data.
"""
import json
import csv
import hashlib
import io
import re
from datetime import datetime, timedelta
import logging

# patch-1.2 (D-9): route every procurement fetch through the shared HTTP client.
# All four sources were dark — same root cause as D-8 (stale URLs + default
# python-requests User-Agent tripping bot-blocks on the CKAN portals). The
# browser UA + certifi TLS clears the bot-blocks. Endpoints live-verified
# 2026-06-09: Open Canada now queried via the CKAN datastore API (full CSV is
# ~627 MB); BuyAndSell replaced by the CanadaBuys open-data tender CSVs;
# Ontario BPS dataset removed upstream (no open-data successor); BC Bid legacy
# RSS retired (CanadaBuys BC-delivery rows used as fallback).
import http_client

logger = logging.getLogger(__name__)

# Minimum contract value to track (filter out small purchases)
MIN_CONTRACT_VALUE = 5_000_000  # $5M — focus on major capital projects

# Construction and infrastructure GSIN/UNSPSC codes to filter on
RELEVANT_GSIN_PREFIXES = [
    "R",   # Construction, maintenance, and repair of structures/facilities
    "N",   # Installation of equipment
    "F",   # Natural resources and conservation
    "S",   # Utilities and housekeeping
    "Z",   # Maintenance and repair of equipment
]

CONSTRUCTION_KEYWORDS = [
    "construction", "infrastructure", "bridge", "highway", "transit",
    "building", "renovation", "expansion", "remediation", "demolition",
    "water treatment", "wastewater", "power plant", "transmission line",
    "hospital", "school", "university", "airport", "port", "rail",
    "pipeline", "refinery", "mine", "processing plant", "data centre",
]

# quality-pass-1.4 G4/G9: French construction keywords (ADDITIVE — required
# for SEAO, whose tender titles are French). English list above is unchanged.
CONSTRUCTION_KEYWORDS_FR = [
    "réfection", "refection", "rénovation", "renovation",
    "agrandissement", "réhabilitation", "rehabilitation",
    "pont", "autoroute", "viaduc", "chaussée", "chaussee",
    "aqueduc", "égout", "egout", "eaux usées", "eaux usees",
    "usine de traitement", "usine d'épuration",
    "hôpital", "hopital", "école", "ecole", "cégep", "cegep",
    "aéroport", "aeroport", "chantier", "travaux de construction",
    "bâtiment", "batiment", "centrale", "ligne de transport",
    "caserne", "bibliothèque", "bibliotheque", "aréna", "arena",
]
CONSTRUCTION_KEYWORDS.extend(
    kw for kw in CONSTRUCTION_KEYWORDS_FR if kw not in CONSTRUCTION_KEYWORDS)


def fetch_open_canada_contracts(days_back=30):
    """
    Fetch recent awarded contracts from Open Canada Proactive Disclosure.
    Uses the CKAN API (free, no key required).

    Returns list of contract dicts.
    """
    contracts = []

    try:
        # Live-verified 2026-06-09 (D-9): the old CKAN package id
        # 'proactive-disclosure-contracts' is gone; the dataset moved to
        # 'd8f85d91-7dec-4fd1-8055-483b77225d8b' ("Proactive Publication -
        # Contracts"). Its full CSV is ~627 MB so we no longer download it;
        # the resource has an active CKAN datastore (1.29M rows), queried here
        # page-by-page sorted by contract_date desc until the lookback cutoff.
        # datastore_search_sql is disabled on open.canada.ca (verified 400),
        # so filtering on value/keywords stays client-side.
        url = "https://open.canada.ca/data/api/3/action/datastore_search"
        resource_id = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"  # Contracts over $10,000

        # Proactive disclosure is published QUARTERLY with a reporting lag
        # (verified 2026-06-09: in June the freshest bulk month was March), so
        # a strict 30-day window would be empty most weeks. Scan at least one
        # quarter back; award_date is carried on every row so downstream
        # consumers can still distinguish genuinely-new awards.
        effective_days = max(days_back, 90)
        cutoff = datetime.now() - timedelta(days=effective_days)
        # Rows with garbage future dates (e.g. 2029) sort first; anything more
        # than ~13 months out is treated as junk and never ends the scan.
        junk_horizon = datetime.now() + timedelta(days=400)
        max_pages = 20  # hard stop: 20 x 1000 rows

        # 2026-06-11 instrumentation: keyword and value predicates are
        # evaluated INDEPENDENTLY for every in-window row (the cheap numeric
        # value check runs first, but a value-fail no longer hides the keyword
        # count and vice versa), so the log shows exactly where rows die.
        fetched_rows = 0   # rows inside the lookback window
        kw_pass = 0        # rows matching a construction keyword
        val_pass = 0       # rows >= MIN_CONTRACT_VALUE

        reached_cutoff = False
        fetch_failed = False
        for page in range(max_pages):
            params = {
                "resource_id": resource_id,
                "limit": 1000,
                "offset": page * 1000,
                "sort": "contract_date desc",
            }
            resp = http_client.get(url, params=params, timeout=30)
            if resp is None or resp.status_code != 200:
                status = 'network' if resp is None else resp.status_code
                print(f"[PROCUREMENT] open_canada FAILED: status={status} (page {page})")
                fetch_failed = page == 0  # mid-scan failure still yields partial data
                break

            records = resp.json().get("result", {}).get("records", [])
            if not records:
                break

            for row in records:
                try:
                    row_date = None
                    raw_date = str(row.get("contract_date") or "")[:10]
                    try:
                        row_date = datetime.strptime(raw_date, "%Y-%m-%d")
                    except ValueError:
                        pass

                    # Sorted desc: a valid date older than the cutoff means
                    # every later row is older still.
                    if row_date is not None and row_date < cutoff:
                        reached_cutoff = True
                        break
                    if row_date is None or row_date > junk_horizon:
                        continue

                    fetched_rows += 1
                    value = _parse_value(row.get("contract_value", "0"))
                    val_ok = value >= MIN_CONTRACT_VALUE
                    description = str(row.get("description_en") or "").lower()
                    kw_ok = any(kw in description for kw in CONSTRUCTION_KEYWORDS)
                    if val_ok:
                        val_pass += 1
                    if kw_ok:
                        kw_pass += 1
                    if not (val_ok and kw_ok):
                        continue

                    contracts.append({
                        "source": "open_canada",
                        "vendor": row.get("vendor_name", "Unknown"),
                        "department": row.get("owner_org_title") or row.get("owner_org", ""),
                        "description": row.get("description_en", ""),
                        "value": value,
                        "award_date": raw_date,
                        "province": _infer_province(row),
                        "url": "https://search.open.canada.ca/contracts/",
                    })
                except Exception as e:
                    logger.debug(f"[PROCUREMENT] Skipped row: {e}")

            if reached_cutoff:
                break

        if fetch_failed:
            # Already printed the FAILED line above; nothing was scanned.
            pass
        else:
            print(f"[PROCUREMENT] open_canada: fetched {fetched_rows} rows, "
                  f"{kw_pass} after keyword filter, {val_pass} >= "
                  f"${MIN_CONTRACT_VALUE:,} -> {len(contracts)} final "
                  f"({fetched_rows - kw_pass} dropped by keyword, "
                  f"{kw_pass - len(contracts)} keyword-matched dropped by value)")

    except Exception as e:
        print(f"[PROCUREMENT] open_canada FAILED: {e}")

    return contracts


# Live-verified 2026-06-09 (D-9): buyandsell.gc.ca no longer resolves in DNS
# and canadabuys.canada.ca has no tender RSS feed (/en/tender-opportunities/rss
# is 404). CanadaBuys publishes open-data tender CSVs instead — both confirmed
# 200 with a stable bilingual-header schema.
_CANADABUYS_NEW_TENDERS_CSV = "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"
_CANADABUYS_OPEN_TENDERS_CSV = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"

# Per-run cache so the BC Bid fallback doesn't re-download the same CSV.
_canadabuys_cache = {}

_REGION_PROVINCE = {
    "british columbia": "BC", "colombie-britannique": "BC",
    "alberta": "AB", "saskatchewan": "SK", "manitoba": "MB",
    "ontario": "ON", "national capital region": "ON", "ottawa": "ON",
    "quebec": "QC", "québec": "QC",
    "nova scotia": "NS", "nouvelle-écosse": "NS",
    "new brunswick": "NB", "nouveau-brunswick": "NB",
    "newfoundland": "NL", "terre-neuve": "NL",
    "prince edward island": "PE", "yukon": "YT",
    "northwest territories": "NT", "nunavut": "NU",
}


def _fetch_canadabuys_rows(url):
    """
    Download and parse a CanadaBuys open-data tender CSV (cached per run).

    Returns a list of row dicts on success (possibly empty — genuinely no
    rows), or None on fetch/parse failure so callers can distinguish a dead
    source from a quiet week (2026-06-11 instrumentation contract).
    """
    if url in _canadabuys_cache:
        return _canadabuys_cache[url]
    resp = http_client.get(url, timeout=40)
    if resp is None or resp.status_code >= 400:
        status = 'network' if resp is None else resp.status_code
        print(f"[PROCUREMENT] canadabuys FAILED: status={status} {url[:80]}")
        return None
    try:
        rows = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig", errors="replace"))))
    except Exception as e:
        print(f"[PROCUREMENT] canadabuys FAILED: CSV parse error: {e}")
        return None
    _canadabuys_cache[url] = rows
    return rows


def _province_from_cb_row(row):
    """Province code from a CanadaBuys row's delivery region, else from text."""
    region = (row.get("regionsOfDelivery-regionsLivraison-eng") or "").lower()
    for keyword, code in _REGION_PROVINCE.items():
        if keyword in region:
            return code
    return _extract_province_from_text(
        f"{row.get('title-titre-eng', '')} {row.get('tenderDescription-descriptionAppelOffres-eng', '')}"
    )


def fetch_buyandsell_rss():
    """
    Fetch recent federal tender notices via the CanadaBuys open-data CSV
    (new tender notices). Filters for construction/infrastructure keywords
    and the $5M value floor — both predicates are evaluated independently
    per row so the log shows what each filter dropped.

    Name kept for caller compatibility. The legacy BuyAndSell RSS attempt
    was REMOVED 2026-06-11: buyandsell.gc.ca no longer resolves in DNS
    (dead since at least 2026-06-09), so each weekly run burned a DNS
    timeout fetching it. Federal tender coverage is the CanadaBuys CSV.
    """
    tenders = []

    # Dead-source skip notice (replaces the removed buyandsell.gc.ca fetch).
    print("[PROCUREMENT] BuyAndSell RSS skipped — buyandsell.gc.ca DNS-dead "
          "(removed 2026-06-11); federal tender coverage via CanadaBuys CSV")

    rows = _fetch_canadabuys_rows(_CANADABUYS_NEW_TENDERS_CSV)
    if rows is None:
        # _fetch_canadabuys_rows already printed the FAILED line.
        return tenders

    kw_pass = 0   # rows matching a construction keyword
    val_pass = 0  # rows with an extractable text value >= $5M
    for row in rows:
        try:
            title = row.get("title-titre-eng", "")
            summary = row.get("tenderDescription-descriptionAppelOffres-eng", "")
            text = f"{title} {summary}".lower()

            # Independent predicates (2026-06-11): the value check is no
            # longer nested under the keyword check, so a keyword miss can't
            # hide the value count and vice versa.
            kw_ok = any(kw in text for kw in CONSTRUCTION_KEYWORDS)
            value = _extract_value_from_text(text)
            val_ok = bool(value and value >= MIN_CONTRACT_VALUE)
            if kw_ok:
                kw_pass += 1
            if val_ok:
                val_pass += 1
            if kw_ok and val_ok:
                tenders.append({
                    "source": "canadabuys",
                    "title": title,
                    "description": summary,
                    "value": value,
                    "date": row.get("publicationDate-datePublication", ""),
                    "url": row.get("noticeURL-URLavis-eng", ""),
                    "province": _province_from_cb_row(row),
                })
        except Exception as e:
            logger.debug(f"[PROCUREMENT] Skipped CanadaBuys row: {e}")

    print(f"[PROCUREMENT] canadabuys: fetched {len(rows)} rows, "
          f"{kw_pass} after keyword filter, {val_pass} >= "
          f"${MIN_CONTRACT_VALUE:,} -> {len(tenders)} final "
          f"(tender notices rarely state dollar values in text; "
          f"{len(rows) - kw_pass} dropped by keyword, "
          f"{kw_pass - len(tenders)} keyword-matched dropped by value)")
    return tenders


def fetch_ontario_bps():
    """
    Ontario BPS Supply Chain procurement — DEAD UPSTREAM, fetch removed.

    Live-verified DEAD 2026-06-09 (D-9) and still dead at the 2026-06-11
    procurement fix: the CKAN package
    'broader-public-sector-business-document-plan' was removed from
    data.ontario.ca and package_search found no open-data successor
    (Ontario tenders moved to the closed Ontario Tenders Portal/Jaggaer).
    The fetch attempt was removed 2026-06-11 — it cost an HTTP round-trip
    every weekly run for a guaranteed 404. Ontario coverage flows from the
    CanadaBuys CSV rows whose delivery region is Ontario (see
    fetch_buyandsell_rss / _province_from_cb_row). Name and empty-list
    return kept for caller compatibility.
    """
    print("[PROCUREMENT] Ontario BPS skipped — CKAN package removed upstream "
          "2026; ON coverage via CanadaBuys delivery-region rows")
    return []


def fetch_bc_bid():
    """
    Fetch BC construction tender opportunities.

    The legacy BC Bid RSS fetch was REMOVED 2026-06-11: the
    open.dll/RSSFeed path 404s and the refreshed BC Bid platform (Ivalua)
    exposes no public RSS (every page.aspx path returns the same JS app
    shell — live-verified dead 2026-06-09). BC coverage is the CanadaBuys
    open-tenders CSV filtered to British Columbia delivery, matching the
    construction keyword filter. Same semantics as the old BC feed — no
    minimum-value requirement (tender notices rarely state values), but the
    >= $5M count is logged for visibility. Name kept for caller compatibility.
    """
    opportunities = []

    try:
        # Dead-source skip notice (replaces the removed legacy RSS fetch).
        print("[PROCUREMENT] BC Bid legacy RSS skipped — platform retired to "
              "Ivalua 2026 (no public feed); BC coverage via CanadaBuys "
              "delivery-region rows")

        rows = _fetch_canadabuys_rows(_CANADABUYS_OPEN_TENDERS_CSV)
        if rows is None:
            # _fetch_canadabuys_rows already printed the FAILED line.
            print("[PROCUREMENT] bc_bid FAILED: CanadaBuys open-tenders CSV "
                  "unavailable — no BC coverage this run")
            return opportunities

        bc_rows = 0   # rows whose delivery region is BC
        val_pass = 0  # kept opportunities with an extractable value >= $5M
        for row in rows:
            try:
                if _province_from_cb_row(row) != "BC":
                    continue
                bc_rows += 1
                title = row.get("title-titre-eng", "")
                summary = row.get("tenderDescription-descriptionAppelOffres-eng", "")
                text = f"{title} {summary}".lower()
                if not any(kw in text for kw in CONSTRUCTION_KEYWORDS):
                    continue
                value = _extract_value_from_text(text)
                if value and value >= MIN_CONTRACT_VALUE:
                    val_pass += 1
                # 2026-06-11 red-team fix: most BC tender notices carry no
                # extractable dollar value. Emitting "value": None crashed
                # every consumer doing `c.get('value', 0) >= threshold`
                # (the key EXISTS, so the default never applies). Emit a
                # numeric 0 and keep the raw extraction separately.
                opportunities.append({
                    "source": "canadabuys_bc",
                    "title": title,
                    "description": summary,
                    "value": value or 0,
                    "value_extracted": value,
                    "province": "BC",
                    "url": row.get("noticeURL-URLavis-eng", ""),
                    "date": row.get("publicationDate-datePublication", ""),
                })
            except Exception as e:
                logger.debug(f"[PROCUREMENT] Skipped CanadaBuys BC row: {e}")

        print(f"[PROCUREMENT] bc_bid: fetched {len(rows)} rows ({bc_rows} BC "
              f"delivery), {len(opportunities)} kept (no value floor on BC "
              f"tender notices — parity with retired BC Bid feed; "
              f"{val_pass} of them have extractable values >= "
              f"${MIN_CONTRACT_VALUE:,})")
    except Exception as e:
        print(f"[PROCUREMENT] bc_bid FAILED: {e}")

    return opportunities


# ── SEAO (Québec) via Données Québec — quality-pass-1.4 G4 ───────────────────
# Live-verified 2026-06-10: SEAO open data is republished on donneesquebec.ca
# (CKAN dataset 'systeme-electronique-dappel-doffres-seao') as weekly
# hebdo_YYYYMMDD_YYYYMMDD.json files in OCDS (Open Contracting Data Standard)
# format. Each release carries tender.title (French), buyer.name,
# awards[].value.amount (CAD), awards[].suppliers[].name. Download URL is
# the resource URL + 'download/{filename}'.

_SEAO_PACKAGE_URL = ("https://www.donneesquebec.ca/recherche/api/3/action/"
                     "package_show?id=systeme-electronique-dappel-doffres-seao")
_SEAO_MAX_WEEKLY_FILES = 4   # ~1 month of weekly OCDS files per run


def fetch_seao(days_back=30):
    """
    Fetch Québec SEAO construction awards from the Données Québec OCDS files.
    Returns list of contract dicts (source='seao', province='QC').
    """
    contracts = []
    try:
        resp = http_client.get(_SEAO_PACKAGE_URL, timeout=30)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT] seao FAILED: package_show status={status}")
            return []

        resources = resp.json().get("result", {}).get("resources", [])
        # Weekly files, newest first (names sort chronologically: hebdo_YYYYMMDD_…)
        weekly = sorted(
            (r for r in resources
             if (r.get("name") or "").lower().startswith("hebdo_")),
            key=lambda r: r.get("name", ""), reverse=True,
        )
        n_files = max(1, min(_SEAO_MAX_WEEKLY_FILES, (days_back + 6) // 7))
        seen_ocids = set()

        # 2026-06-11 instrumentation: independent counters across all weekly
        # files. fetched = releases carrying >= 1 award; keyword and value
        # predicates evaluated independently per release.
        fetched_releases = 0
        kw_pass = 0   # 'works' category or construction keyword (EN+FR)
        val_pass = 0  # release has >= 1 award >= $5M

        for res in weekly[:n_files]:
            name = res.get("name", "")
            base = (res.get("url") or "").rstrip("/")
            if not base:
                continue
            # CKAN resource URLs are usually already the full download link
            # (".../resource/{id}/download/{file}"); only append the download
            # suffix when it is missing (live-verified both shapes 2026-06-10).
            dl_url = base if "/download/" in base else f"{base}/download/{name}"
            file_resp = http_client.get(dl_url, timeout=60)
            if file_resp is None or file_resp.status_code != 200:
                status = 'network' if file_resp is None else file_resp.status_code
                print(f"[PROCUREMENT] seao FAILED: status={status} {name}")
                continue
            try:
                releases = file_resp.json().get("releases", [])
            except ValueError as e:
                print(f"[PROCUREMENT] seao FAILED: JSON parse error for {name}: {e}")
                continue

            for rel in releases:
                try:
                    ocid = rel.get("ocid") or rel.get("id")
                    if ocid in seen_ocids:
                        continue
                    awards = rel.get("awards") or []
                    if not awards:
                        continue
                    fetched_releases += 1
                    tender = rel.get("tender") or {}
                    title = tender.get("title") or ""
                    category = tender.get("mainProcurementCategory") or ""
                    text = title.lower()
                    # 'works' = construction in OCDS; otherwise keyword match
                    # (CONSTRUCTION_KEYWORDS includes the French additions).
                    kw_ok = category == "works" or any(
                        kw in text for kw in CONSTRUCTION_KEYWORDS)
                    val_ok = any(
                        float((a.get("value") or {}).get("amount") or 0)
                        >= MIN_CONTRACT_VALUE for a in awards)
                    if kw_ok:
                        kw_pass += 1
                    if val_ok:
                        val_pass += 1
                    if not kw_ok:
                        continue
                    for award in awards:
                        value = float((award.get("value") or {}).get("amount") or 0)
                        if value < MIN_CONTRACT_VALUE:
                            continue
                        suppliers = [s.get("name", "") for s in
                                     (award.get("suppliers") or [])]
                        seen_ocids.add(ocid)
                        contracts.append({
                            "source": "seao",
                            "ocid": ocid,
                            "title": title,
                            "description": tender.get("description", "") or title,
                            "vendor": suppliers[0] if suppliers else "Unknown",
                            "organization": (rel.get("buyer") or {}).get("name", ""),
                            "value": value,
                            "award_date": str(award.get("date") or "")[:10],
                            "province": "QC",
                            "url": "https://www.donneesquebec.ca/recherche/dataset/systeme-electronique-dappel-doffres-seao",
                        })
                except Exception as e:
                    logger.debug(f"[PROCUREMENT] Skipped SEAO release: {e}")

        # seen_ocids holds exactly the releases that yielded >= 1 kept award,
        # so kw_pass - len(seen_ocids) = keyword-matched releases whose every
        # award fell under the $5M floor.
        print(f"[PROCUREMENT] seao: fetched {fetched_releases} awarded "
              f"releases, {kw_pass} after keyword filter, {val_pass} >= "
              f"${MIN_CONTRACT_VALUE:,} -> {len(contracts)} final "
              f"({fetched_releases - kw_pass} dropped by keyword, "
              f"{kw_pass - len(seen_ocids)} keyword-matched dropped by value)")
    except Exception as e:
        print(f"[PROCUREMENT] seao FAILED: {e}")

    return contracts


# ── Defence Construction Canada — quality-pass-1.4 G4 ────────────────────────
# Live-verified 2026-06-10: DCC publishes recently awarded contracts ONLY as a
# PDF on its MFT share (no HTML table, CSV, or feed exists — the
# /industry/contract-awards path 404s). The PDF is tabular and extracts
# cleanly with PyMuPDF (fitz), which is already a project dependency.

_DCC_AWARDS_PDF = ("https://dccmft.dcc-cdc.gc.ca/"
                   "?u=contracts_public&p=public&path=/Recently_Awarded_Contracts.pdf")

_DCC_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DCC_AMOUNT_RE = re.compile(r"^\$[\d,]+(?:\.\d{2})?$")
# DCC project numbers look like CH260003 / PA000417
_DCC_PROJECT_NO_RE = re.compile(r"^[A-Z]{2,4}\d{5,8}$")


def fetch_dcc():
    """
    Fetch Defence Construction Canada recently awarded contracts (PDF).
    All DCC contracts are defence construction; the MIN_CONTRACT_VALUE
    floor still applies for consistency with the other sources.
    Returns list of contract dicts (source='dcc').
    """
    contracts = []
    try:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("[PROCUREMENT] dcc FAILED: PyMuPDF (fitz) not installed")
            return []

        resp = http_client.get(_DCC_AWARDS_PDF, timeout=40)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT] dcc FAILED: status={status}")
            return []
        if not (resp.content or b"").startswith(b"%PDF"):
            print("[PROCUREMENT] dcc FAILED: response is not a PDF")
            return []

        doc = fitz.open(stream=resp.content, filetype="pdf")
        lines = []
        for page in doc:
            lines.extend(page.get_text().split("\n"))

        # Rows are anchored by an award date line followed (within a few
        # lines) by a $ amount line. Description/location are the lines
        # between the project-number anchor and the date.
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i].strip()
            if _DCC_DATE_RE.match(line):
                award_date = line
                # amount: next 1-3 lines
                amount = None
                j = i + 1
                while j < min(i + 4, n):
                    if _DCC_AMOUNT_RE.match(lines[j].strip()):
                        amount = _parse_value(lines[j].strip())
                        break
                    j += 1
                # description/location: walk back to the project-number anchor
                desc_parts = []
                k = i - 1
                while k >= 0 and len(desc_parts) < 12:
                    back = lines[k].strip()
                    if _DCC_PROJECT_NO_RE.match(back) or _DCC_DATE_RE.match(back) \
                            or _DCC_AMOUNT_RE.match(back):
                        break
                    if back and not back.isdigit():
                        desc_parts.insert(0, back)
                    k -= 1
                # contractor: lines after the amount until next project number
                contractor_parts = []
                m = j + 1
                while m < min(j + 5, n):
                    fwd = lines[m].strip()
                    if (_DCC_PROJECT_NO_RE.match(fwd) or _DCC_DATE_RE.match(fwd)
                            or not fwd):
                        break
                    contractor_parts.append(fwd)
                    m += 1

                description = " ".join(desc_parts).strip()
                if amount is not None and description:
                    contracts.append({
                        "source": "dcc",
                        "title": description[:200],
                        "description": description,
                        "vendor": " ".join(contractor_parts)[:120] or "Unknown",
                        "value": amount,
                        "award_date": award_date,
                        "province": _extract_province_from_text(description),
                        "url": _DCC_AWARDS_PDF,
                    })
                i = j + 1
            i += 1

        # Apply the house value floor after parsing (DCC awards are mostly
        # small; the floor keeps semantics consistent across sources).
        total_parsed = len(contracts)
        contracts = [c for c in contracts if (c.get("value") or 0) >= MIN_CONTRACT_VALUE]
        # Every DCC award is defence construction by definition, so the
        # keyword filter is identity here (N after keyword == N fetched).
        print(f"[PROCUREMENT] dcc: fetched {total_parsed} rows, "
              f"{total_parsed} after keyword filter (all DCC awards are "
              f"defence construction), {len(contracts)} >= "
              f"${MIN_CONTRACT_VALUE:,} -> {len(contracts)} final "
              f"({total_parsed - len(contracts)} dropped by value)")
    except Exception as e:
        print(f"[PROCUREMENT] dcc FAILED: {e}")

    return contracts


# ── SaskTenders / Alberta Purchasing Connection — dark sources ───────────────
# Live-verified DARK 2026-06-10 (quality-pass-1.4 G4), same precedent as
# ontario_bps above:
#   - SaskTenders: apex sasktenders.ca times out; www.sasktenders.ca serves a
#     1.7 MB ASP.NET WebForms Search.aspx that requires __VIEWSTATE postbacks.
#     No RSS feed and no open-data export exist.
#   - Alberta Purchasing Connection (purchasingconnection.ca): Angular SPA —
#     every path returns the same JS app shell. No public API or RSS found.
# Neither exposes structured data, so no fetcher is implemented; SK and AB
# coverage flows from the CanadaBuys CSV rows whose delivery region is
# Saskatchewan / Alberta (see fetch_buyandsell_rss / _province_from_cb_row).


def _parse_value(value_str):
    """Parse a dollar value string into float."""
    if not value_str:
        return 0
    cleaned = re.sub(r'[,$\s]', '', str(value_str))
    try:
        return float(cleaned)
    except ValueError:
        return 0


def _extract_value_from_text(text):
    """Extract dollar values from free text.

    2026-06-11 red-team fix: the multiplier is bound to WHICH pattern matched
    instead of re-checking 'B'/'M' case-sensitively after the fact — callers
    lowercase their text first, so "$5m" / "$5 million" used to parse as 5.0
    dollars. Suffix matching is now fully case-insensitive.
    """
    patterns = [
        (r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|bn|b)\b', 1_000_000_000),
        (r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|m)\b', 1_000_000),
        (r'\$\s*([\d,]+(?:\.\d+)?)', 1),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(',', '')) * multiplier
    return None


def _extract_province_from_text(text):
    """Simple province extraction from text."""
    province_map = {
        "ontario": "ON", "toronto": "ON", "ottawa": "ON",
        "quebec": "QC", "québec": "QC", "montréal": "QC", "montreal": "QC",
        "british columbia": "BC", "vancouver": "BC", "victoria bc": "BC",
        "alberta": "AB", "calgary": "AB", "edmonton": "AB",
        "saskatchewan": "SK", "saskatoon": "SK", "regina": "SK",
        "manitoba": "MB", "winnipeg": "MB",
        "nova scotia": "NS", "halifax": "NS",
        "new brunswick": "NB", "moncton": "NB",
        "newfoundland": "NL", "labrador": "NL",
    }
    text_lower = text.lower()
    for keyword, province in province_map.items():
        if keyword in text_lower:
            return province
    return None


def _infer_province(row):
    """Infer province from Open Canada contract row."""
    # Try explicit province field first, then description
    province = row.get("province", "")
    if province:
        return province
    return _extract_province_from_text(
        row.get("description_en", "") + " " + row.get("vendor_name", "")
    )


# 2026-06-11 red-team fix: vendor names whose normalized form is one of these
# generic words must never be used as a project-match key — "Les" matched 172
# QC projects, "Construction" 35+, spraying false linked_projects into the
# briefing (editorial fabrication).
_GENERIC_VENDOR_WORDS = {
    "construction", "les", "groupe", "gestion", "canada", "inc",
    "ltd", "ltee", "ltée", "limited", "corp", "corporation", "company",
    "compagnie", "services", "enterprises", "entreprises", "group",
}

# Corporate suffixes stripped from the tail of vendor names before matching.
_VENDOR_SUFFIXES = {
    "inc", "ltd", "ltee", "ltée", "limited", "corp", "corporation",
    "co", "cie", "llp", "llc", "lp", "plc", "sa", "senc", "sencrl",
}


def _normalize_vendor(vendor):
    """
    Normalize a vendor name into a full-name match key.

    Strips punctuation and trailing corporate suffixes. Returns '' when the
    remainder is shorter than 6 characters or is a generic word — callers
    must NOT link on such names (false links are editorial fabrication;
    linking less is fine).
    """
    name = re.sub(r"[.,;:()\[\]]", " ", str(vendor or ""))
    words = [w for w in name.split() if w]
    while words and words[-1].lower() in _VENDOR_SUFFIXES:
        words.pop()
    normalized = " ".join(words).strip()
    if len(normalized) < 6:
        return ""
    if normalized.lower() in _GENERIC_VENDOR_WORDS:
        return ""
    return normalized


def link_contracts_to_projects(contracts, conn):
    """
    Match procurement contracts to existing projects by vendor name
    and province.

    2026-06-11 red-team fix: the old second LIKE clause matched on the FIRST
    WORD of the vendor name ("Les", "Construction", ...), linking dozens of
    unrelated projects. Now only the full normalized vendor name is matched,
    against the project name OR proponent field.
    """
    cursor = conn.cursor()
    linked = []

    for contract in contracts:
        vendor = contract.get("vendor", contract.get("organization", ""))
        province = contract.get("province")

        if not vendor or vendor == "Unknown":
            continue

        vendor_norm = _normalize_vendor(vendor)
        if not vendor_norm:
            # Too short/generic to match safely — keep the contract but
            # never fabricate links from it.
            contract["linked_projects"] = []
            linked.append(contract)
            continue

        try:
            cursor.execute("""
                SELECT name, province, value, status, sector
                FROM projects
                WHERE (name LIKE ? OR proponent LIKE ?)
                AND (province = ? OR ? IS NULL)
                ORDER BY value DESC
                LIMIT 3
            """, (
                f"%{vendor_norm}%",
                f"%{vendor_norm}%",
                province, province,
            ))

            matches = cursor.fetchall()
            if matches:
                contract["linked_projects"] = [
                    {"name": m[0], "province": m[1], "value": m[2],
                     "status": m[3], "sector": m[4]}
                    for m in matches
                ]
            else:
                contract["linked_projects"] = []

            linked.append(contract)
        except Exception as e:
            logger.debug(f"[PROCUREMENT] Project linking failed: {e}")

    return linked


# Cross-run dedup state (2026-06-11 red-team fix): SEAO refetches the last 4
# weekly OCDS files every run and the snapshot stored the whole 30-day window
# weekly, so the same award was re-reported as fresh for up to 5 weeks.
_SEEN_OCIDS_STATE_KEY = "procurement_seen_ocids"
_SEEN_OCIDS_CAP = 5000  # FIFO cap on the persisted identity set

# Per-source fetch-health state (2026-06-19 false-alarm fix): the upstream
# sources fetch a ROLLING WINDOW every run (Open Canada scans >=90 days; SEAO
# re-reads the last 4 weekly OCDS files; CanadaBuys re-downloads the full CSV),
# so after the first run ~100% of fetched contracts are repeats and the
# post-dedup procurement_contracts list is empty MOST weeks even when every
# source is healthy. The post-dedup zero is therefore NOT a useful alarm. We
# instead record, per source, the PRE-dedup raw-row count each run and alarm
# only when a source that has historically yielded rows goes dark (0 raw rows /
# FAILED fetch) for several consecutive runs. The correct pre-dedup whole-run
# [PROCUREMENT DEGRADED] signal in run_procurement_monitor is left unchanged.
_SOURCE_HEALTH_STATE_KEY = "procurement_source_health"
_SOURCE_HEALTH_CAP = 8  # rolling window of recent runs kept per source
_SOURCE_DARK_CONSECUTIVE = 3  # consecutive 0-row runs before a source is "dark"


def _contract_dedup_key(contract):
    """
    Stable cross-run identity key for a contract.

    SEAO rows carry an OCDS ocid — use it directly. Rows from sources without
    one (open_canada / dcc / canadabuys) are keyed by a stable hash of
    (vendor, value, description[:80]).
    """
    ocid = contract.get("ocid")
    if ocid:
        return f"ocid:{ocid}"
    basis = "|".join([
        str(contract.get("vendor") or contract.get("organization") or ""),
        str(contract.get("value") or 0),
        str(contract.get("description") or contract.get("title") or "")[:80],
    ])
    return "h:" + hashlib.sha256(basis.encode("utf-8", "replace")).hexdigest()[:32]


def _filter_first_seen(conn, contracts):
    """
    Mark each contract dict with "first_seen" (bool) against the persisted
    identity set in dashboard_state, return the first-seen subset, and persist
    the updated set (FIFO-capped at _SEEN_OCIDS_CAP).

    Persistence failures degrade gracefully (everything treated as first-seen)
    so a missing dashboard_state table can't kill the monitor.
    """
    import db as _db

    try:
        seen_list = _db.get_dashboard_state(conn, _SEEN_OCIDS_STATE_KEY) or []
        if not isinstance(seen_list, list):
            seen_list = []
    except Exception as e:
        logger.debug(f"[PROCUREMENT] seen-OCID state load failed: {e}")
        seen_list = []
    seen_set = set(seen_list)

    new_contracts = []
    for c in contracts:
        key = _contract_dedup_key(c)
        first = key not in seen_set
        c["first_seen"] = first
        if first:
            new_contracts.append(c)
            seen_set.add(key)
            seen_list.append(key)

    if len(seen_list) > _SEEN_OCIDS_CAP:
        seen_list = seen_list[-_SEEN_OCIDS_CAP:]
    try:
        _db.save_dashboard_state(conn, _SEEN_OCIDS_STATE_KEY, seen_list)
    except Exception as e:
        logger.debug(f"[PROCUREMENT] seen-OCID state save failed: {e}")

    return new_contracts


def _update_source_health(conn, per_source):
    """
    Persist a rolling per-source fetch-health record to dashboard_state and
    return (health, dark_sources, any_rows).

    `per_source` maps source name -> {"fetched_rows": int, "errored": bool} for
    THIS run (pre-dedup raw rows). For each source we keep the last
    _SOURCE_HEALTH_CAP runs as a list of {"rows": int, "errored": bool} plus the
    most recent "fetched_rows". A source is reported "dark" only when it has
    historically yielded rows (max rows over its window > 0) yet has returned 0
    raw rows for >= _SOURCE_DARK_CONSECUTIVE consecutive runs — distinguishing a
    dead endpoint from a healthy-but-all-deduped quiet week.

    Persistence failures degrade gracefully (no alarm state lost beyond this
    run) so a missing dashboard_state table can't kill the monitor.
    """
    import db as _db

    try:
        health = _db.get_dashboard_state(conn, _SOURCE_HEALTH_STATE_KEY) or {}
        if not isinstance(health, dict):
            health = {}
    except Exception as e:
        logger.debug(f"[PROCUREMENT] source-health state load failed: {e}")
        health = {}

    dark_sources = []
    any_rows = False
    for source, info in per_source.items():
        rows = int(info.get("fetched_rows") or 0)
        errored = bool(info.get("errored"))
        if rows > 0:
            any_rows = True

        rec = health.get(source)
        if not isinstance(rec, dict):
            rec = {}
        window = rec.get("runs")
        if not isinstance(window, list):
            window = []
        window.append({"rows": rows, "errored": errored})
        if len(window) > _SOURCE_HEALTH_CAP:
            window = window[-_SOURCE_HEALTH_CAP:]
        rec["runs"] = window
        rec["fetched_rows"] = rows
        health[source] = rec

        # "dark" = historically productive but now zero for N consecutive runs.
        ever_yielded = any((r.get("rows") or 0) > 0 for r in window)
        consecutive_zero = 0
        for r in reversed(window):
            if (r.get("rows") or 0) == 0:
                consecutive_zero += 1
            else:
                break
        if ever_yielded and consecutive_zero >= _SOURCE_DARK_CONSECUTIVE:
            dark_sources.append((source, consecutive_zero))

    try:
        _db.save_dashboard_state(conn, _SOURCE_HEALTH_STATE_KEY, health)
    except Exception as e:
        logger.debug(f"[PROCUREMENT] source-health state save failed: {e}")

    return health, dark_sources, any_rows


def run_procurement_monitor(conn, days_back=30):
    """
    Main entry point. Fetch from all procurement sources, filter, link to projects.

    Returns dict with procurement data for the pipeline context.
    """
    all_contracts = []

    # Per-source raw-row capture (2026-06-19): record how many rows each source
    # returned PRE-dedup and whether the fetch errored, so the rolling
    # source-health alarm below can tell "source went dark" from "healthy but
    # everything deduped". Each fetcher already catches internally and returns a
    # list; the per-source try here only flags the errored case for the record.
    per_source = {}

    def _capture(source, fetch_fn):
        try:
            rows = fetch_fn() or []
            per_source[source] = {"fetched_rows": len(rows), "errored": False}
            all_contracts.extend(rows)
        except Exception as e:
            # Mirrors the existing isolated-failure print style below.
            print(f"[PROCUREMENT] {source} FAILED (isolated): {e}")
            per_source[source] = {"fetched_rows": 0, "errored": True}

    # Federal sources
    _capture("open_canada", lambda: fetch_open_canada_contracts(days_back))
    _capture("canadabuys", fetch_buyandsell_rss)

    # Provincial sources
    _capture("ontario_bps", fetch_ontario_bps)
    _capture("bc_bid", fetch_bc_bid)

    # quality-pass-1.4 G4: Québec SEAO (Données Québec OCDS) and Defence
    # Construction Canada — error-isolated like the sources above (each
    # fetcher already catches internally; the belt-and-braces try keeps a
    # pathological failure from killing the whole monitor run).
    _capture("seao", lambda: fetch_seao(days_back))
    _capture("dcc", fetch_dcc)

    print(f"[PROCUREMENT] Total: {len(all_contracts)} relevant contracts across all sources")

    # Rolling per-source fetch-health record + "source went dark" alarm
    # (2026-06-19). This is the alarm that should fire on a FAILED/dead fetch —
    # NOT on a post-dedup zero, which is the intended steady state given the
    # rolling-window sources. A source is "dark" only when it historically
    # yielded rows yet has returned 0 raw rows for >= _SOURCE_DARK_CONSECUTIVE
    # consecutive runs.
    try:
        _health, dark_sources, sources_had_rows = _update_source_health(conn, per_source)
    except Exception as e:
        logger.debug(f"[PROCUREMENT] source-health update failed: {e}")
        dark_sources = []
        sources_had_rows = any(
            (info.get("fetched_rows") or 0) > 0 for info in per_source.values())
    for source, streak in dark_sources:
        print(f"[PROCUREMENT DARK] {source} returned 0 raw rows for {streak} "
              f"consecutive runs (>= {_SOURCE_DARK_CONSECUTIVE}) after previously "
              f"yielding rows — likely a dead endpoint, not an all-deduped week")

    # patch-1.2: min-yield DEGRADE log. All four procurement sources were dark
    # (D-9); a whole-run zero means dead endpoints, not a quiet week. The
    # per-source instrumentation lines above (2026-06-11) say whether each
    # zero was a FAILED fetch or rows genuinely dropped by filters.
    if not all_contracts:
        print("[PROCUREMENT DEGRADED] 0 items — all procurement sources "
              "returned zero (see per-source lines above: FAILED = dead "
              "fetch, otherwise counts show keyword/value drops)")

    # Cross-run dedup (2026-06-11 red-team fix): only contracts never seen in
    # a previous run flow to the snapshot and briefing context; the full fetch
    # window is still returned under procurement_contracts_all.
    new_contracts = _filter_first_seen(conn, all_contracts)
    print(f"[PROCUREMENT] Cross-run dedup: {len(new_contracts)} first-seen of "
          f"{len(all_contracts)} fetched "
          f"({len(all_contracts) - len(new_contracts)} repeats suppressed)")

    # Link to existing projects (first-seen only — these feed the briefing)
    linked = link_contracts_to_projects(new_contracts, conn)
    linked_count = sum(1 for c in linked if c.get("linked_projects"))
    print(f"[PROCUREMENT] Linked {linked_count}/{len(linked)} contracts to existing projects")

    # Save snapshot (first-seen only — no re-reporting old awards as fresh)
    save_procurement_snapshot(conn, new_contracts)

    # Warehouse instrumentation (RC-6): record the connection outcome. A run
    # where no source returned raw rows is failed; errored sources or dark
    # streaks degrade an otherwise-ok run. Never raises.
    try:
        from data_warehouse import record_run
        _errored = [s for s, i in per_source.items() if i.get("errored")]
        if not sources_had_rows:
            _wh_status = "failed"
            _wh_err = "no procurement source returned raw rows"
        elif _errored or dark_sources:
            _wh_status = "degraded"
            _wh_err = "; ".join(
                ([f"errored: {', '.join(_errored)}"] if _errored else [])
                + ([f"dark: {', '.join(s for s, _ in dark_sources)}"] if dark_sources else []))
        else:
            _wh_status, _wh_err = "ok", ""
        record_run("procurement_monitor", _wh_status,
                   items_fetched=len(all_contracts), items_saved=len(new_contracts),
                   error=_wh_err, conn=conn)
    except Exception as _wh_e:
        print(f"[WAREHOUSE] procurement recording failed (non-critical): {_wh_e}")

    return {
        "procurement_contracts": new_contracts,
        "procurement_contracts_all": all_contracts,
        "procurement_linked": linked,
        "procurement_total_value": sum(c.get("value", 0) for c in new_contracts if c.get("value")),
        "procurement_sources": list(set(c["source"] for c in new_contracts)),
        # 2026-06-19: did ANY source return raw rows pre-dedup this run? The
        # dashboard gates its procurement alarm on this instead of on
        # len(procurement_contracts), which is ~0 most weeks by design.
        "procurement_sources_had_rows": sources_had_rows,
    }


def save_procurement_snapshot(conn, contracts):
    """Save weekly procurement snapshot for historical tracking."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS procurement_snapshots (
            week_of     TEXT NOT NULL,
            data        TEXT NOT NULL,
            created     TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (week_of)
        )
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO procurement_snapshots (week_of, data)
        VALUES (?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d"),
        json.dumps(contracts, default=str),
    ))
    conn.commit()
