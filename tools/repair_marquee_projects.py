"""
repair_marquee_projects.py — One-time repair from the 2026-06-10 miss diagnosis.

Seeds/repairs the highly-reported projects the pipeline failed to surface:
  1. Portage Place Redevelopment (MB) — never extracted despite a fetched article.
  2. Deep Sky Manitoba Carbon Removal Facility (MB) — only the Montréal/ENGIE
     story was captured (as QC duplicate rows); the $500M MB facility was absent.
  3. Alto High-Speed Rail (ON/QC) — six articles fetched, zero projects created.
  4. Lynn Lake Gold Project (MB) — IAAC row existed but carried no value,
     proponent, or news evidence; enriched from Alamos' 2026 guidance.
  5. Merges the two Deep Sky QC duplicate rows (same betakit article).

All writes go through db.upsert_project so every business rule applies
(URL hard gate, evidence merge, status non-regression, value_millions lockstep).
Facts verified against the cited sources on 2026-06-10.

Usage (from backend/):
    python tools/repair_marquee_projects.py            # dry run
    python tools/repair_marquee_projects.py --apply    # write
"""
import argparse
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

SEEDS = [
    {
        'name': 'Portage Place Redevelopment',
        'province': 'MB',
        'cma': 'Winnipeg',
        'sector': 'commercial_mixed',
        'project_type': 'redevelopment',
        'value': '$650M',
        'currency': 'CAD',
        'value_scope': 'program',
        'status': 'Under Construction',
        'confidence': 0.6,
        'proponent': 'True North Real Estate Development',
        'completionDate': '2028',
        'description': (
            'True North Real Estate Development is converting the Portage Place '
            'mall in downtown Winnipeg into a $650M mixed-use campus: a 12-storey '
            'Healthcare Centre of Excellence (>$300M, including Pan Am Clinic '
            'expansion and renal dialysis capacity), a 15-storey residential tower '
            'in partnership with the Southern Chiefs\' Organization, grocery, and '
            'public space. Atrium deconstruction completed; structural '
            'construction began 2026, completion targeted for 2028.'
        ),
        'discovery_source': 'manual_repair_2026_06_10',
        'has_government_source': True,
        'evidence': [
            {'url': 'https://portageplace.ca/development-updates/',
             'source_type': 'proponent', 'date': TODAY},
            {'url': 'https://news.gov.mb.ca/news/index.html?item=62837',
             'source_type': 'government', 'authority': 'government', 'date': TODAY},
            {'url': 'https://www.cbc.ca/news/canada/manitoba/portage-place-construction-9.7063848',
             'source_type': 'news', 'date': TODAY},
        ],
        'sources': [
            {'id': 1, 'title': 'Portage Place — Development Updates',
             'url': 'https://portageplace.ca/development-updates/'},
            {'id': 2, 'title': 'Province of Manitoba — Portage Place to be Redeveloped to bring More Health Care, Housing Downtown',
             'url': 'https://news.gov.mb.ca/news/index.html?item=62837'},
            {'id': 3, 'title': 'CBC — Portage Place atrium coming down as redevelopment project aims for 2028 completion',
             'url': 'https://www.cbc.ca/news/canada/manitoba/portage-place-construction-9.7063848'},
        ],
        'tags': ['downtown Winnipeg', 'healthcare campus', 'mixed-use',
                 'Southern Chiefs Organization', 'True North'],
    },
    {
        'name': 'Deep Sky Manitoba Carbon Removal Facility',
        'province': 'MB',
        'cma': '',
        'sector': 'environment',
        'project_type': 'greenfield',
        'value': '$500M',
        'currency': 'CAD',
        'value_scope': 'program',
        'value_notes': 'Phase 1: $200M for 30,000 t/yr; full build-out $500M for 500,000 t/yr',
        'status': 'Proposed',
        'confidence': 0.55,
        'proponent': 'Deep Sky Corp.',
        'completionDate': '',
        'description': (
            'Deep Sky Corp. plans a $500M direct-air-capture facility in '
            'southwestern Manitoba removing 500,000 tonnes of CO2 per year for '
            'permanent storage in a saline aquifer ~2 km underground. The first '
            '$200M phase targets 30,000 t/yr with construction expected to begin '
            'in 2026 (700–1,000 construction jobs). Announced October 9, 2025, '
            'with a declaration signed with the Dakota Nations of Manitoba.'
        ),
        'discovery_source': 'manual_repair_2026_06_10',
        'evidence': [
            {'url': 'https://www.deepskyclimate.com/blog/deep-sky-to-build-500-000-tonne-carbon-removal-facility---one-of-the-worlds-largest---in-manitoba-canada',
             'source_type': 'proponent', 'date': TODAY},
            {'url': 'https://www.cbc.ca/news/canada/manitoba/carbon-capture-deep-sky-manitoba-9.6933590',
             'source_type': 'news', 'date': TODAY},
            {'url': 'https://www.theglobeandmail.com/business/article-deep-sky-unveils-plans-for-one-of-the-worlds-biggest-direct-air-carbon/',
             'source_type': 'news', 'date': TODAY},
        ],
        'sources': [
            {'id': 1, 'title': 'Deep Sky — 500,000 tonne carbon removal facility in Manitoba',
             'url': 'https://www.deepskyclimate.com/blog/deep-sky-to-build-500-000-tonne-carbon-removal-facility---one-of-the-worlds-largest---in-manitoba-canada'},
            {'id': 2, 'title': 'CBC — Montreal startup plans $200M carbon-capture facility in southwestern Manitoba',
             'url': 'https://www.cbc.ca/news/canada/manitoba/carbon-capture-deep-sky-manitoba-9.6933590'},
            {'id': 3, 'title': 'Globe and Mail — Deep Sky unveils plans for one of the world\'s biggest direct air carbon capture facilities in Manitoba',
             'url': 'https://www.theglobeandmail.com/business/article-deep-sky-unveils-plans-for-one-of-the-worlds-biggest-direct-air-carbon/'},
        ],
        'tags': ['direct air capture', 'carbon removal', 'CDR', 'Dakota Nations',
                 'saline aquifer storage'],
        'announcement_date': '2025-10-09',
    },
    {
        'name': 'Alto High-Speed Rail',
        'province': 'ON',
        'provinces_additional': 'QC',
        'cma': 'Toronto',
        'sector': 'transport_logistics',
        'project_type': 'greenfield',
        'value': '$3.9B',
        'currency': 'CAD',
        'value_scope': 'phase',
        'value_notes': 'Co-development (design) phase $3.9B over six years; full network preliminary estimate $60B–$90B',
        'status': 'Under Review',
        'confidence': 0.6,
        'proponent': 'Alto (Crown corporation) / Cadence consortium',
        'completionDate': '',
        'description': (
            'Canada\'s Toronto–Québec City high-speed rail project, co-developed '
            'with the Cadence consortium under a six-year, $3.9B co-development '
            'phase. The Ottawa–Montréal section is confirmed as the first '
            'segment. Public consultations on corridor alignment and station '
            'locations began January 2026. Preliminary full-network cost '
            'estimate: $60B–$90B.'
        ),
        'discovery_source': 'manual_repair_2026_06_10',
        'has_government_source': True,
        'evidence': [
            {'url': 'https://www.altotrain.ca/en/shaping-canadas-future-high-speed-train',
             'source_type': 'proponent', 'authority': 'government', 'date': TODAY},
            {'url': 'https://www.canada.ca/en/privy-council/major-projects-office/projects/other/referred/alto.html',
             'source_type': 'government', 'authority': 'government', 'date': TODAY},
            {'url': 'https://www.globalrailwayreview.com/news/233691/canada-confirms-ottawa-montreal-as-first-segment-of-alto-high-speed-rail-project/',
             'source_type': 'news', 'date': TODAY},
        ],
        'sources': [
            {'id': 1, 'title': 'Alto — Building Canada\'s Future with High-Speed Rail',
             'url': 'https://www.altotrain.ca/en/shaping-canadas-future-high-speed-train'},
            {'id': 2, 'title': 'Major Projects Office — Alto High-Speed Rail',
             'url': 'https://www.canada.ca/en/privy-council/major-projects-office/projects/other/referred/alto.html'},
            {'id': 3, 'title': 'Global Railway Review — Canada confirms Ottawa–Montreal as first segment of Alto',
             'url': 'https://www.globalrailwayreview.com/news/233691/canada-confirms-ottawa-montreal-as-first-segment-of-alto-high-speed-rail-project/'},
        ],
        'tags': ['high-speed rail', 'Alto', 'Cadence', 'Toronto-Quebec corridor',
                 'Ottawa-Montreal'],
    },
    {
        # Exact-key merge into the existing IAAC row (lynnlakegoldproject__mb):
        # enriches value/status/proponent/evidence, never regresses.
        'name': 'Lynn Lake Gold Project',
        'province': 'MB',
        'cma': 'Lynn Lake',
        'sector': 'mining',
        'project_type': 'greenfield',
        'value': '$937M',
        'currency': 'USD',
        'value_scope': 'program',
        'value_notes': 'US$937M initial capital (Feb 2026 guidance; up from US$632M in 2023 feasibility). Covers MacLellan and Gordon sites.',
        'status': 'Under Construction',
        'confidence': 0.6,
        'proponent': 'Alamos Gold Inc.',
        'completionDate': '2029',
        'description': (
            'Alamos Gold\'s Lynn Lake gold project in northern Manitoba '
            '(MacLellan and Gordon sites). Positive construction decision '
            'announced January 13, 2025; initial capital US$937M per the '
            'February 2026 guidance (mill capacity increased 13% to 9,000 tpd). '
            'Construction ramping up spring 2026 after the 2025 wildfires; '
            'completion expected in the first half of 2029.'
        ),
        'discovery_source': 'manual_repair_2026_06_10',
        'has_government_source': True,
        'evidence': [
            {'url': 'https://iaac-aeic.gc.ca/050/evaluations/proj/80140',
             'source_type': 'government', 'authority': 'government', 'date': TODAY},
            {'url': 'https://www.alamosgold.com/projects/lynn-lake-project/',
             'source_type': 'proponent', 'date': TODAY},
            {'url': 'https://www.miningweekly.com/article/alamos-advances-to-900-000-ozy-with-lynne-lake-construction-decision-2025-01-14',
             'source_type': 'news', 'date': TODAY},
        ],
        'sources': [
            {'id': 1, 'title': 'IAAC — Lynn Lake Gold Project',
             'url': 'https://iaac-aeic.gc.ca/050/evaluations/proj/80140'},
            {'id': 2, 'title': 'Alamos Gold — Lynn Lake Project',
             'url': 'https://www.alamosgold.com/projects/lynn-lake-project/'},
            {'id': 3, 'title': 'Mining Weekly — Alamos to advance to 900,000 oz/y with Lynn Lake construction decision',
             'url': 'https://www.miningweekly.com/article/alamos-advances-to-900-000-ozy-with-lynne-lake-construction-decision-2025-01-14'},
        ],
        'tags': ['gold', 'Alamos Gold', 'MacLellan', 'Gordon', 'northern Manitoba'],
        'announcement_date': '2025-01-13',
    },
]

# Same-article duplicate rows to merge: (keep_norm_key, remove_norm_key)
DUP_MERGES = [
    ('deepskycarbonremovalfacility__qc', 'deepskycarbonremovalengiepartnership__qc'),
    # NRCan backfill split the Lynn Lake Gold Project into its two mine sites;
    # they are parts of the one Alamos project (the $937M program value on the
    # parent covers both). Site evidence URLs survive on the parent.
    ('lynnlakegoldproject__mb', 'lynnlakemaclellansite__mb'),
    ('lynnlakegoldproject__mb', 'lynnlakegordonsite__mb'),
]


def merge_dup_rows(conn, keep_key, drop_key, apply):
    import sqlite3
    conn.row_factory = sqlite3.Row
    rows = {}
    for k in (keep_key, drop_key):
        r = conn.execute("SELECT * FROM projects WHERE norm_key = ?", (k,)).fetchone()
        if r is None:
            print(f"  [DUP] {k}: not found (already merged?) — skipping pair")
            return
        rows[k] = r
    print(f"  [DUP] merge '{rows[drop_key]['name']}' -> '{rows[keep_key]['name']}'")
    if not apply:
        return
    from tools.dedup_projects_fuzzy import load_projects, merge_cluster, write_back
    projects = []
    for k in (keep_key, drop_key):
        import json as _json
        d = {c: rows[k][c] for c in rows[k].keys()}
        for j in ('evidence', 'sources', 'discovery_sources', 'statusHistory',
                  'official_ids', 'tags', 'anomalies'):
            v = d.get(j)
            if isinstance(v, str):
                try:
                    d[j] = _json.loads(v) if v else []
                except Exception:
                    d[j] = []
        projects.append(d)
    primary, others = merge_cluster([0, 1], projects)
    secondary_keys = [projects[j]['norm_key'] for j in others]

    # Re-point child rows (FK on projects.rowid) to the kept row before the
    # secondary row is deleted — evidence URLs must survive the merge.
    keep_rowid = conn.execute(
        "SELECT rowid FROM projects WHERE norm_key = ?", (primary['norm_key'],)
    ).fetchone()[0]
    for sk in secondary_keys:
        drop_rowid_row = conn.execute(
            "SELECT rowid FROM projects WHERE norm_key = ?", (sk,)).fetchone()
        if drop_rowid_row is None:
            continue
        drop_rowid = drop_rowid_row[0]
        for child in ('evidence', 'project_events', 'project_organizations',
                      'project_identifiers'):
            try:
                conn.execute(
                    f"UPDATE OR IGNORE {child} SET project_id = ? WHERE project_id = ?",
                    (keep_rowid, drop_rowid))
                conn.execute(f"DELETE FROM {child} WHERE project_id = ?", (drop_rowid,))
            except Exception as e:
                print(f"  [DUP] {child} re-point skipped: {e}")

    write_back(conn, primary, secondary_keys)
    print(f"  [DUP] merged; removed {secondary_keys}")


def run(apply: bool):
    from db import init_db, upsert_project

    if apply:
        backup = f"dashboard.db.prerepair_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        shutil.copy('dashboard.db', backup)
        print(f"[BACKUP] {backup}")

    conn = init_db()
    try:
        for seed in SEEDS:
            existing = conn.execute(
                "SELECT norm_key, name, status, value FROM projects WHERE norm_key LIKE ?",
                (seed['name'].lower().replace(' ', '').replace('-', '')[:20] + '%',)
            ).fetchall()
            print(f"\n[SEED] {seed['name']} ({seed['province']}) "
                  f"value={seed['value']} status={seed['status']}")
            if not apply:
                print("  [DRY RUN] would upsert")
                continue
            key = upsert_project(conn, dict(seed))
            # Dual-write evidence rows so the URL-first rediscovery lookup
            # (db._fuzzy_find_existing joins the evidence table) can match
            # future re-extractions of these articles to this project.
            try:
                from project_sync import _sync_evidence_and_org
                _sync_evidence_and_org(conn, key, dict(seed), None)
            except Exception as e:
                print(f"  [WARN] evidence dual-write failed: {e}")
            row = conn.execute(
                "SELECT name, status, value, value_millions, confidence, evidence_count "
                "FROM projects WHERE norm_key = ?", (key,)).fetchone()
            print(f"  -> {key}: {tuple(row)}")
        conn.commit()

        print("\n[DUP MERGES]")
        for keep, drop in DUP_MERGES:
            merge_dup_rows(conn, keep, drop, apply)
        conn.commit()
    finally:
        conn.close()
    print("\nDone." if apply else "\n[DRY RUN] no changes written. Re-run with --apply.")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    run(p.parse_args().apply)
