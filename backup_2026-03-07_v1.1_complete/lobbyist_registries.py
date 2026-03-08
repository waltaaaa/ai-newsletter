"""
lobbyist_registries.py — Federal lobbyist registry search for capital project signals.

The federal lobbyist registry publishes bulk CSV data at:
https://lobbycanada.gc.ca/en/open-data/

Strategy: Download the registrations CSV, filter for capital-project-related
subject matters and keywords, generate investigation queries.

These are SIGNALS (investigation queries), not confirmed projects.
"""

import csv
import io
import logging
import re
import requests
import zipfile

logger = logging.getLogger(__name__)

_REGISTRATIONS_ZIP_URL = "https://lobbycanada.gc.ca/media/zwcjycef/registrations_enregistrements_ocl_cal.zip"

# Subject matters and keywords that suggest capital project lobbying
_PROJECT_KEYWORDS = [
    'construction', 'infrastructure', 'facility', 'plant', 'mine',
    'pipeline', 'refinery', 'terminal', 'development', 'project',
    'environmental assessment', 'permit', 'approval', 'licence',
    'expansion', 'remediation', 'transit', 'highway', 'bridge',
    'port', 'airport', 'housing', 'energy', 'nuclear', 'lng',
    'broadband', 'data centre', 'data center',
]

# Subject matter categories from the registry that relate to capital projects
_RELEVANT_SUBJECTS = [
    'infrastructure', 'environment', 'energy', 'mining',
    'transport', 'housing', 'defence', 'science and technology',
    'natural resources', 'industry',
]

# Province mapping from registration data
_PROV_MAP = {
    'AB': 'Alberta', 'BC': 'British Columbia', 'MB': 'Manitoba',
    'NB': 'New Brunswick', 'NL': 'Newfoundland and Labrador',
    'NS': 'Nova Scotia', 'NT': 'Northwest Territories', 'NU': 'Nunavut',
    'ON': 'Ontario', 'PE': 'Prince Edward Island', 'QC': 'Quebec',
    'SK': 'Saskatchewan', 'YT': 'Yukon',
    'Alberta': 'Alberta', 'British Columbia': 'British Columbia',
    'Manitoba': 'Manitoba', 'New Brunswick': 'New Brunswick',
    'Ontario': 'Ontario', 'Quebec': 'Quebec', 'Saskatchewan': 'Saskatchewan',
}


def search_lobbyist_registries() -> list[dict]:
    """Search federal lobbyist registry for capital project signals.

    Downloads the bulk registrations CSV and filters for entries
    mentioning capital project keywords.

    Returns list of signal dicts with investigation queries.
    """
    print("  [LOBBY] Downloading federal lobbyist registrations...")
    signals = []

    try:
        resp = requests.get(_REGISTRATIONS_ZIP_URL, timeout=60,
                            headers={'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)'})
        if resp.status_code != 200:
            print(f"  [LOBBY] HTTP {resp.status_code} from lobbycanada.gc.ca")
            return []

        # Unzip in memory
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        csv_names = [n for n in zf.namelist() if n.endswith('.csv')]
        if not csv_names:
            print("  [LOBBY] No CSV found in ZIP archive")
            return []

        csv_data = zf.read(csv_names[0]).decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(csv_data))

        seen = set()
        row_count = 0
        recent_count = 0

        for row in reader:
            row_count += 1

            # Only look at recent registrations (last ~90 days)
            effective = row.get('EFFECTIVE_DATE', '') or row.get('effective_date', '')
            if effective and len(effective) >= 10:
                # Check if recent (crude date check — skip old entries)
                year_str = effective[:4]
                try:
                    year = int(year_str)
                    if year < 2025:
                        continue
                except (ValueError, TypeError):
                    continue
                recent_count += 1

            # Check subject matter and description for project keywords
            subject = (row.get('SUBJECT_MATTER', '') or row.get('subject_matter', '') or '').lower()
            description = (row.get('DESCRIPTION', '') or row.get('description_en', '') or
                          row.get('PARTICULARS', '') or '').lower()
            company = (row.get('CLIENT', '') or row.get('client_org_name', '') or
                      row.get('ORGANIZATION', '') or row.get('organization_name', '') or '')

            combined = f"{subject} {description}"

            # Check for relevant subject matters
            has_relevant_subject = any(s in subject for s in _RELEVANT_SUBJECTS)
            has_project_keyword = any(kw in combined for kw in _PROJECT_KEYWORDS)

            if not (has_relevant_subject and has_project_keyword):
                continue

            # Extract province
            province_raw = (row.get('PROVINCE', '') or row.get('province', '') or
                          row.get('CLIENT_PROVINCE', '') or '')
            province = _PROV_MAP.get(province_raw.strip(), '')

            # Build a unique key to avoid duplicate signals
            key = f"{company.lower()[:30]}|{subject[:50]}"
            if key in seen:
                continue
            seen.add(key)

            # Generate investigation query
            query_parts = []
            if company:
                query_parts.append(company)
            # Extract the most specific project reference from description
            for kw in _PROJECT_KEYWORDS:
                if kw in combined:
                    query_parts.append(kw)
                    break
            if province:
                query_parts.append(province)
            query_parts.append("capital project 2025 2026")

            signals.append({
                'query': ' '.join(query_parts[:5]),
                'province': province,
                'sector': _infer_lobby_sector(combined),
                'source': 'lobbyist_registry',
                'language': 'en',
                'geo_tier': 'federal',
                'company': company,
                'subject': subject[:200],
                'description': description[:300],
            })

            if len(signals) >= 50:
                break

        print(f"  [LOBBY] Scanned {row_count} registrations, "
              f"{recent_count} recent, {len(signals)} project-related signals")

    except requests.exceptions.Timeout:
        print("  [LOBBY] Download timed out (60s) — file may be very large")
    except Exception as e:
        print(f"  [LOBBY] Failed: {type(e).__name__}: {e}")

    return signals


def _infer_lobby_sector(text: str) -> str:
    """Infer sector from lobbying subject/description text."""
    t = text.lower()
    if any(x in t for x in ('oil', 'gas', 'pipeline', 'lng', 'refinery')):
        return 'Energy'
    if any(x in t for x in ('mine', 'mining', 'mineral')):
        return 'Mining'
    if any(x in t for x in ('nuclear', 'wind', 'solar', 'hydro', 'hydrogen', 'carbon')):
        return 'Clean Energy'
    if any(x in t for x in ('transit', 'rail', 'subway', 'lrt')):
        return 'Transit & Rail'
    if any(x in t for x in ('highway', 'bridge', 'road', 'infrastructure')):
        return 'Infrastructure'
    if any(x in t for x in ('housing', 'residential', 'affordable')):
        return 'Housing'
    if any(x in t for x in ('hospital', 'health', 'medical')):
        return 'Healthcare'
    if any(x in t for x in ('defence', 'defense', 'military')):
        return 'Defence'
    if any(x in t for x in ('port', 'terminal', 'airport')):
        return 'Ports & Logistics'
    return 'Infrastructure'
