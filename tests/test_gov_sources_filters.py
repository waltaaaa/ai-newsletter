"""quality-pass-1.4 P1 — ingestion doctype filter tests.

db.is_non_project_doctype (promoted from tools/export_dashboard) is applied
in gov_sources at ingestion: registry rows that are DOCUMENT filings (Forest
Management Plans, EIS, terms of reference, notices) with no dollar value are
skipped before the upsert. Rows that carry a dollar value always pass.
"""

from db import is_non_project_doctype, NON_PROJECT_DOCTYPE_RE
from gov_sources import _skip_non_project_filing, _parse_text_for_projects


def test_helper_filters_forest_management_plan():
    assert is_non_project_doctype("XYZ Forest Management Plan 2024-2034")


def test_helper_filters_environmental_impact_statement():
    assert is_non_project_doctype("Project ABC Environmental Impact Statement")


def test_helper_passes_real_project():
    assert not is_non_project_doctype("Forest Products Mill Expansion $120M")


def test_helper_passes_empty_name():
    assert not is_non_project_doctype("")
    assert not is_non_project_doctype(None)


def test_skip_gate_respects_dollar_value():
    # Doctype match + no value → skipped
    assert _skip_non_project_filing("Mine Site Annual Report 2025")
    # Doctype match but dollar amount in the name → kept
    assert not _skip_non_project_filing(
        "Environmental Impact Statement for $120M Mill Expansion")
    # Doctype match but explicit value field → kept
    assert not _skip_non_project_filing("Mine Site Annual Report 2025",
                                        value="$50M")
    # Non-doctype name → kept
    assert not _skip_non_project_filing("Forest Products Mill Expansion $120M")


def test_parse_text_seam_filters_filings():
    """The shared text-parse helper (SK/YT scrapers) drops value-less
    document filings but keeps real project lines."""
    text = "\n".join([
        "XYZ Forest Management Plan 2024-2034",
        "Project ABC Environmental Impact Statement",
        "Forest Products Mill Expansion $120M",
    ])
    projects = _parse_text_for_projects(
        text, "Saskatchewan", "provincial_ea", "https://example.gov/ea")
    names = [p["name"] for p in projects]
    assert "Forest Products Mill Expansion $120M" in names
    assert all("Forest Management Plan" not in n for n in names)
    assert all("Environmental Impact Statement" not in n for n in names)


def test_regex_exported_for_export_dashboard():
    """tools/export_dashboard imports the same regex from db."""
    from tools.export_dashboard import _NON_PROJECT_DOCTYPE_RE
    assert _NON_PROJECT_DOCTYPE_RE is NON_PROJECT_DOCTYPE_RE
