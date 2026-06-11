"""Edition-archive invariants — the previous-editions dropdown is append-only.

History: 2026-06-08, a wholesale archive rebuild collapsed the dropdown from
7 editions to 1 (manually restored in commit 3409046). These tests pin the
three defenses added since:
  1. export_briefings union-merges and never shrinks the on-disk archive,
     and preserves file_date through the merge
  2. validate_briefing_schema._validate_briefing_archive FAILs the deploy
     gate on lost editions / dropdown 404s
  3. tools/_rebuild_briefing_archive refuses to shrink without --force
     (covered implicitly via its merge logic mirroring 1)
"""
import json
import os

import pytest

from db import init_db, save_briefing


@pytest.fixture()
def conn():
    c = init_db(":memory:")
    yield c
    c.close()


def _write_archive(tmp_path, entries):
    path = os.path.join(tmp_path, "briefing_archive.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    return path


def _read_archive(tmp_path):
    with open(os.path.join(tmp_path, "briefing_archive.json"), encoding="utf-8") as f:
        return json.load(f)


def _entry(week_of, file_date=None, headline="Test headline", wc=500):
    e = {"week_of": week_of, "headline": headline, "word_count": wc,
         "generated_at": f"{week_of}T12:00:00Z"}
    if file_date:
        e["file_date"] = file_date
    return e


class TestExportMerge:
    def test_merge_never_shrinks(self, conn, tmp_path):
        """DB with 1 edition + disk with 3 -> all 3 survive (union)."""
        from tools.export_dashboard import export_briefings
        _write_archive(str(tmp_path), [
            _entry("2026-06-01"), _entry("2026-05-25"), _entry("2026-05-18")])
        save_briefing(conn, {
            "week_of": "2026-06-08", "headline": "New edition",
            "sections": {"a": "b"}, "word_count": 1200,
            "generated_at": "2026-06-08T12:00:00Z"})
        export_briefings(conn, str(tmp_path))
        weeks = {e["week_of"] for e in _read_archive(str(tmp_path))}
        assert {"2026-06-01", "2026-05-25", "2026-05-18", "2026-06-08"} <= weeks

    def test_merge_preserves_file_date(self, conn, tmp_path):
        """file_date pointing at an off-day dated file survives re-export."""
        from tools.export_dashboard import export_briefings
        _write_archive(str(tmp_path), [
            _entry("2026-05-11", file_date="2026-05-15")])
        export_briefings(conn, str(tmp_path))
        arch = {e["week_of"]: e for e in _read_archive(str(tmp_path))}
        assert arch["2026-05-11"]["file_date"] == "2026-05-15"

    def test_entries_get_default_file_date(self, conn, tmp_path):
        """Entries without file_date are stamped with week_of."""
        from tools.export_dashboard import export_briefings
        _write_archive(str(tmp_path), [_entry("2026-06-01")])
        export_briefings(conn, str(tmp_path))
        arch = {e["week_of"]: e for e in _read_archive(str(tmp_path))}
        assert arch["2026-06-01"]["file_date"] == "2026-06-01"


class TestValidatorGate:
    def _run(self, tmp_path, briefing=None):
        from tools.validate_briefing_schema import _validate_briefing_archive
        results = []
        fails, warns = _validate_briefing_archive(str(tmp_path), results,
                                                  briefing or {})
        return fails, warns, results

    def _touch_briefing(self, tmp_path, date):
        with open(os.path.join(str(tmp_path), f"briefing_{date}.json"), "w") as f:
            f.write("{}")

    def test_clean_archive_passes(self, tmp_path):
        _write_archive(str(tmp_path), [
            _entry("2026-06-08"), _entry("2026-05-11", file_date="2026-05-15")])
        self._touch_briefing(tmp_path, "2026-06-08")
        self._touch_briefing(tmp_path, "2026-05-15")
        fails, _, _ = self._run(tmp_path)
        assert fails == 0

    def test_missing_archive_fails(self, tmp_path):
        fails, _, _ = self._run(tmp_path)
        assert fails >= 1

    def test_empty_archive_fails(self, tmp_path):
        _write_archive(str(tmp_path), [])
        fails, _, _ = self._run(tmp_path)
        assert fails >= 1

    def test_dropdown_404_fails(self, tmp_path):
        """An entry whose dated file is missing blocks the deploy."""
        _write_archive(str(tmp_path), [_entry("2026-06-08")])
        fails, _, _ = self._run(tmp_path)
        assert fails >= 1

    def test_missing_week_of_fails(self, tmp_path):
        _write_archive(str(tmp_path), [{"headline": "no week"}])
        fails, _, _ = self._run(tmp_path)
        assert fails >= 1

    def test_current_week_missing_is_warn_only(self, tmp_path):
        _write_archive(str(tmp_path), [_entry("2026-06-01")])
        self._touch_briefing(tmp_path, "2026-06-01")
        fails, warns, _ = self._run(tmp_path, briefing={"week_of": "2026-06-08"})
        assert fails == 0
        assert warns >= 1

    def test_no_git_repo_skips_shrink_guard(self, tmp_path):
        """Outside a git repo (or no HEAD version) the shrink guard skips
        silently rather than erroring — tmp_path is not a repo."""
        _write_archive(str(tmp_path), [_entry("2026-06-08")])
        self._touch_briefing(tmp_path, "2026-06-08")
        fails, _, _ = self._run(tmp_path)
        assert fails == 0
