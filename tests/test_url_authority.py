"""Regression tests for federal canada.ca government-authority classification.

Before the fix, GOV_DOMAIN_PATTERNS only matched *.gc.ca and provincial/municipal
domains — bare canada.ca press releases classified as 'regional_news' (via
KNOWN_GOOD_DOMAINS) and got evidence source_type 'local_news' instead of
'gov_newsroom'.
"""
from db import _classify_source_type, SOURCE_WEIGHT
from url_utils import classify_source_authority, validate_url


class TestCanadaCaAuthority:
    def test_bare_canada_ca_is_government(self):
        assert classify_source_authority('https://www.canada.ca/en/news/x') == 'government'
        assert classify_source_authority('https://canada.ca/fr/nouvelles/y') == 'government'

    def test_canada_ca_subdomain_is_government(self):
        assert classify_source_authority('https://agriculture.canada.ca/en/news') == 'government'

    def test_existing_gov_domains_still_government(self):
        # Additive change — prior matches must be unaffected
        assert classify_source_authority('https://www.alberta.ca/r1') == 'government'
        assert classify_source_authority('https://www.iaac-aeic.gc.ca/proj/1') == 'government'
        assert classify_source_authority('https://news.ontario.ca/release') == 'government'

    def test_lookalike_domains_not_government(self):
        # '-canada.ca' / 'notcanada.ca' must not match the anchored pattern
        assert classify_source_authority('https://ici.radio-canada.ca/nouvelle/1') == 'major_news'
        assert classify_source_authority('https://notcanada.ca/article') == 'other'
        assert classify_source_authority('https://www.canada.ca.evil.com/phish') != 'government'

    def test_media_classifications_unchanged(self):
        assert classify_source_authority('https://www.cbc.ca/news/story') == 'major_news'
        assert classify_source_authority('https://renewcanada.net/article') == 'industry'
        assert classify_source_authority('https://www.saltwire.com/story') == 'regional_news'


class TestCanadaCaSourceType:
    def test_canada_ca_is_gov_newsroom(self):
        st = _classify_source_type('https://www.canada.ca/en/news/x')
        assert st == 'gov_newsroom'
        assert SOURCE_WEIGHT[st] > SOURCE_WEIGHT['local_news']

    def test_canada_ca_subdomain_is_gov_newsroom(self):
        assert _classify_source_type('https://infrastructure.canada.ca/plan') == 'gov_newsroom'

    def test_gc_ca_still_gov_newsroom(self):
        assert _classify_source_type('https://www.canada.gc.ca/x') == 'gov_newsroom'

    def test_radio_canada_not_gov_newsroom(self):
        assert _classify_source_type('https://ici.radio-canada.ca/nouvelle/1') != 'gov_newsroom'


class TestCanadaCaKnownSource:
    def test_canada_ca_subdomain_is_known_source(self):
        # Bare canada.ca was already known via KNOWN_GOOD_DOMAINS; subdomains
        # are now covered by the gov pattern too
        assert validate_url('https://agriculture.canada.ca/en/news')['is_known_source']
