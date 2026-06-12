"""Tests for export_statcan_tables — the Data Explorer's full table directory.

Covers the identifier-search expansion: the legacy CANSIM table number must be
exported as ``s`` and all three identifier forms (table ID, dashless PID,
CANSIM number) must be embedded in the keyword blob so the frontend scorer
matches identifier queries.
"""

import csv
import json
import os

import pytest

from tools.export_dashboard import export_statcan_tables

REGISTRY_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "statcan_table_registry.csv",
)


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp("statcan_tables"))
    path = export_statcan_tables(None, out_dir)
    assert path, "export returned empty path — registry CSV missing?"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_row_count_matches_registry_rows(exported):
    with open(REGISTRY_CSV, encoding="utf-8-sig", newline="") as f:
        kept = [
            r for r in csv.DictReader(f)
            if (r.get("Status") or "").strip() in ("Current", "Archived")
            and (r.get("Table ID") or "").strip()
            and (r.get("Table Name") or "").strip()
        ]
    assert len(exported) == len(kept)
    assert len(exported) > 4000


def test_cansim_id_exported_as_s(exported):
    by_table = {r["t"]: r for r in exported}
    lfs = by_table.get("14-10-0287")
    assert lfs is not None
    assert lfs.get("s") == "282-0087"


def test_rows_without_cansim_omit_s(exported):
    missing = [r for r in exported if "s" not in r]
    assert missing, "expected some rows without a legacy CANSIM number"
    assert all("s" not in r for r in missing)


def test_identifiers_embedded_in_keyword_blob(exported):
    by_table = {r["t"]: r for r in exported}
    lfs = by_table["14-10-0287"]
    assert "14-10-0287" in lfs["k"]
    assert "14100287" in lfs["k"]
    assert "282-0087" in lfs["k"]


def test_compact_shape_preserved(exported):
    required = {"t", "n", "k", "c", "f", "g"}
    for r in exported[:50]:
        assert required.issubset(r.keys())
        assert set(r.keys()) <= required | {"s", "a"}


def test_archived_rows_flagged_and_other_statuses_skipped(tmp_path):
    header = (
        "Table Name,Table ID,Product ID (raw),CANSIM ID,Link,Frequency,"
        "Coverage,Focus,Subject Codes,Survey Codes,Start Date,End Date,"
        "Last Release,Status"
    )
    rows = [
        '"Live table",10-10-0001,10100001,176-0001,x,Monthly,National,Economic accounts,10,1,,,,Current',
        '"Dead table",10-10-0002,10100002,176-0002,x,Monthly,National,Economic accounts,10,1,,,,Archived',
        '"Weird table",10-10-0003,10100003,,x,Monthly,National,Economic accounts,10,1,,,,Code 3',
    ]
    csv_path = tmp_path / "registry.csv"
    csv_path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    out = export_statcan_tables(None, str(tmp_path), config_path=str(csv_path))
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    by_table = {r["t"]: r for r in data}
    assert set(by_table) == {"10-10-0001", "10-10-0002"}
    assert "a" not in by_table["10-10-0001"]
    assert by_table["10-10-0002"]["a"] == 1
    assert by_table["10-10-0002"]["s"] == "176-0002"
