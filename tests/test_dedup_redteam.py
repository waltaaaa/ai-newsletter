"""Red-team regression suite for the guarded dedup matcher (2026-06-10/11).

Every case here is a real failure mode found while diagnosing why marquee
projects (Lynn Lake Gold, Portage Place, Deep Sky Manitoba, Alto HSR) were
missed or duplicated. Positive cases are re-phrasings that MUST merge;
negative cases are distinct projects that MUST NOT, even when they share a
URL or a name prefix.
"""
import pytest

from tools.dedup_projects_fuzzy import (
    is_duplicate_pair, normalize_name, is_listing_url,
    proponents_contradict, proponents_match,
)

ARTICLE = 'https://betakit.com/montreals-deep-sky-partners-with-french-energy-company-engie/'
CBC = 'https://www.cbc.ca/news/canada/manitoba/carbon-capture-deep-sky-manitoba-9.6933590'
ROUNDUP = 'https://news.example.com/city-budget-roundup'


def pair(n1, n2, p1=None, p2=None, u1=None, u2=None, threshold=0.85):
    p1 = dict(p1 or {}, name=n1)
    p2 = dict(p2 or {}, name=n2)
    return is_duplicate_pair(p1, p2, normalize_name(n1), normalize_name(n2),
                             u1 or set(), u2 or set(), threshold)


# ── MUST MERGE — same project, re-phrased ───────────────────────────────────

def test_same_article_announcement_framing():
    assert pair('Deep Sky Carbon Removal Facility',
                'Deep Sky Carbon Removal — ENGIE Partnership',
                {'cma': 'Montréal'}, {'cma': 'Montréal'}, {ARTICLE}, {ARTICLE})


def test_same_article_synonym_rephrase_leading_bigram():
    assert pair('Deep Sky Manitoba Carbon Removal Facility',
                'Deep Sky direct air capture facility — Manitoba',
                {'cma': ''}, {'cma': ''}, {CBC}, {CBC})


def test_same_article_extension_rename():
    assert pair('Portage Place Redevelopment',
                'Portage Place Mall Redevelopment — True North Health Campus',
                {'cma': 'Winnipeg'}, {'cma': 'Winnipeg'}, {CBC}, {CBC})


def test_corporate_suffix_not_a_contradiction():
    assert pair('Lynn Lake Gold Project', 'Lynn Lake gold mine (Alamos Gold)',
                {'proponent': 'Alamos Gold Inc.'}, {'proponent': 'Alamos Gold'},
                {'https://www.alamosgold.com/projects/lynn-lake-project/'},
                {'https://www.alamosgold.com/projects/lynn-lake-project/'})


def test_milestone_rephrase_no_shared_url():
    # New article, no URL overlap — work-stage words must not block identity.
    assert pair('Deep Sky Manitoba Carbon Removal Facility',
                'Deep Sky Manitoba carbon removal facility construction',
                {'cma': ''}, {'cma': ''}, {CBC}, {'https://cbc.ca/new-article'})
    assert pair('Portage Place Redevelopment',
                'Portage Place Redevelopment — structural phase',
                {'cma': 'Winnipeg'}, {'cma': 'Winnipeg'},
                {CBC}, {'https://wfp.com/new-article'})


# ── MUST NOT MERGE — distinct projects ──────────────────────────────────────

def test_distinct_sites_same_proponent():
    assert not pair('Lynn Lake (MacLellan site)', 'Lynn Lake (Gordon site)',
                    {'proponent': 'Alamos Gold Inc.', 'parsed_value': 260598000.0},
                    {'proponent': 'Alamos Gold Inc.', 'parsed_value': 173732000.0})


def test_different_proponents_same_asset_name():
    assert not pair('Surmont Expansion (ConocoPhillips)', 'Surmont Expansion (MEG Energy)',
                    {'proponent': 'ConocoPhillips'}, {'proponent': 'MEG Energy'},
                    {ROUNDUP}, {ROUNDUP})


def test_phase_numbers_differ_raw_names():
    # normalize_name strips "Phase N" — the raw-name guard must still reject.
    assert not pair('Highway 3 Twinning Phase 2', 'Highway 3 Twinning Phase 4',
                    u1={ROUNDUP}, u2={ROUNDUP})


def test_place_prefix_with_shared_city_news_url():
    assert not pair('Prince Albert Leisure Centre',
                    'Prince Albert 2026 Road Rehabilitation and Construction',
                    {'cma': 'Prince Albert'}, {'cma': 'Prince Albert'},
                    {ROUNDUP}, {ROUNDUP})


def test_french_school_boilerplate_names():
    pqi = 'https://www.quebec.ca/gouvernement/politiques-orientations/plan-quebecois-infrastructures'
    assert is_listing_url(pqi)
    assert not pair(
        'École primaire du centre de services scolaire de Montréal (secteur Griffintown) – Construction',
        'École primaire du centre de services scolaire de Montréal (arrondissement de Rosemont–La Petite-Patrie) – Construction',
        {'cma': 'Montréal'}, {'cma': 'Montréal'}, {pqi}, {pqi})


def test_proponent_portfolio_on_registry_listing():
    ab = 'https://www.alberta.ca/environmental-impact-assessments-historical-projects'
    assert is_listing_url(ab)
    assert not pair('Shell Canada Ltd. – Quest Carbon Capture and Storage Project',
                    'Shell Canada Ltd. – Jackpine Mine Expansion & Pierre River Mine',
                    {'proponent': 'Shell Canada'}, {'proponent': 'Shell Canada'},
                    {ab}, {ab})


def test_generic_registry_names_need_corroboration():
    assert not pair('Wastewater Treatment Lagoon', 'Wastewater Treatment Lagoon',
                    {'cma': 'Brandon'}, {'cma': 'Steinbach'})


def test_value_ratio_contradiction():
    assert not pair('Toronto Waterfront Revitalization',
                    'Toronto Waterfront Revitalization East Island Park',
                    {'cma': 'Toronto', 'parsed_value': 5_000_000_000},
                    {'cma': 'Toronto', 'parsed_value': 100_000_000},
                    {ROUNDUP}, {ROUNDUP})


def test_single_shared_token_is_not_identity():
    assert not pair('Winnipeg Police Headquarters Renovation', 'Winnipeg Arena Expansion',
                    {'cma': 'Winnipeg'}, {'cma': 'Winnipeg'}, {ROUNDUP}, {ROUNDUP})


# ── Listing-URL classification ──────────────────────────────────────────────

@pytest.mark.parametrize('url', [
    'https://www.ontario.ca/page/ontario-builds',
    'https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html',
    'https://www.quebec.ca/gouvernement/politiques-orientations/plan-quebecois-infrastructures',
    'https://www.alberta.ca/environmental-impact-assessments-historical-projects',
])
def test_government_program_pages_are_listings(url):
    assert is_listing_url(url)


def test_specific_article_is_not_listing():
    assert not is_listing_url(CBC)


# ── Proponent normalization ─────────────────────────────────────────────────

def test_proponent_helpers():
    assert proponents_match('Alamos Gold Inc.', 'Alamos Gold')
    assert not proponents_contradict('Alamos Gold Inc.', 'Alamos Gold')
    assert proponents_contradict('ConocoPhillips', 'MEG Energy')
    assert not proponents_contradict('', 'MEG Energy')
