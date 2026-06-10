"""quality-pass-1.4 P5 — headline geography gating tests.

Headline/snippet province mentions only set `meta_provinces` when a
project-ish token co-occurs in the same text; otherwise the mention lands in
`meta_provinces_weak`. Domain signals are NOT gated.
"""

from metadata_tagger import tag_article


def test_province_mention_without_project_context_is_weak():
    art = tag_article({
        "title": "Canada's housing crisis: what Ontario teaches us",
        "link": "https://example-news.ca/opinion/housing-crisis",
        "summary": "",
    })
    assert "ON" not in art["meta_provinces"]
    assert "ON" in art["meta_provinces_weak"]


def test_province_mention_with_project_context_is_tagged():
    art = tag_article({
        "title": "Ontario announces $2B highway construction project",
        "link": "https://example-news.ca/news/highway",
        "summary": "",
    })
    assert "ON" in art["meta_provinces"]
    assert "ON" not in art["meta_provinces_weak"]


def test_government_domain_tags_province_regardless_of_text():
    """Domain signal is ungated — news.ontario.ca tags ON even with no
    project-context token and no province mention in the headline."""
    art = tag_article({
        "title": "Statement from the Premier",
        "link": "https://news.ontario.ca/en/release/100123/statement",
        "summary": "",
    })
    assert "ON" in art["meta_provinces"]


def test_weak_field_always_present():
    art = tag_article({
        "title": "Global markets steady",
        "link": "https://example-news.ca/markets",
        "summary": "",
    })
    assert art["meta_provinces_weak"] == []
    assert art["meta_provinces"] == []


def test_multiple_provinces_split_by_context():
    """'announced' grants hard tags to every province mentioned in the text."""
    art = tag_article({
        "title": "Alberta refinery expansion announced as Saskatchewan watches",
        "link": "https://example-news.ca/energy",
        "summary": "",
    })
    assert "AB" in art["meta_provinces"]
    assert "SK" in art["meta_provinces"]
