"""
tests/test_export_dashboard.py — Unit tests for export_dashboard.py

Tests use in-memory SQLite via init_db(":memory:") for full isolation.
All 7 behaviors from PLAN spec are covered.
"""

import json
import os
import sys
import tempfile
import unittest

# Add parent directory to path so we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, upsert_project


def _make_ontario_project(value="$600M"):
    """Build an Ontario test project with the given value."""
    return {
        "name": f"Ontario Test Project {value}",
        "province": "Ontario",
        "cma": "Toronto",
        "sector": "Construction",
        "naics_code": "23",
        "naics_name": "Construction",
        "value": value,
        "status": "Proposed",
        "confidence": 0.8,
        "project_type": "greenfield",
        "is_brownfield": False,
        "proponent": "Test Corp",
        "description": "A test project in Ontario.",
        "completionDate": "2028-12-31",
        "firstTracked": "2026-01-01",
        "lastUpdated": "2026-03-01",
        "lastSeen": "2026-03-01",
        "evidence": [{"url": "https://example.com/test", "title": "Test Article"}],
        "statusHistory": [
            {"status": "Proposed", "date": "2026-01-01", "detail": "Filed."}
        ],
        "discovery_source": "rss_feed",
        "source_url_quality": "direct",
        "has_government_source": False,
        "evidence_count": 1,
        "tags": ["construction", "ontario"],
        "sources": [],
        "discovery_sources": ["rss_feed"],
        "anomalies": [],
    }


class TestParseValue(unittest.TestCase):
    """Test 1–3 related: _parse_value parsing behavior."""

    def setUp(self):
        from tools.export_dashboard import _parse_value
        self.parse = _parse_value

    def test_parse_billions(self):
        self.assertAlmostEqual(self.parse("$1.2B"), 1_200_000_000.0)

    def test_parse_millions(self):
        self.assertAlmostEqual(self.parse("$600M"), 600_000_000.0)

    def test_parse_written_billion(self):
        self.assertAlmostEqual(self.parse("$2.5 billion"), 2_500_000_000.0)

    def test_parse_not_disclosed(self):
        self.assertIsNone(self.parse("Not disclosed"))

    def test_parse_empty(self):
        self.assertIsNone(self.parse(""))

    def test_parse_none_input(self):
        self.assertIsNone(self.parse(None))

    def test_parse_unparseable(self):
        self.assertIsNone(self.parse("TBD"))


class TestExportProvinceProjects(unittest.TestCase):
    """Tests 1–4: export_province_projects filtering and field shaping."""

    def setUp(self):
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_export(self, threshold_val=500_000_000):
        from tools.export_dashboard import export_province_projects
        export_province_projects(self.conn, "Ontario", threshold_val, self.tmpdir)
        out_path = os.path.join(self.tmpdir, "projects_ontario.json")
        self.assertTrue(os.path.exists(out_path), "projects_ontario.json not created")
        with open(out_path, encoding="utf-8") as f:
            return json.load(f)

    # Test 1: $600M project included, $400M excluded (threshold $500M)
    def test_above_threshold_included(self):
        upsert_project(self.conn, _make_ontario_project("$600M"))
        projects = self._run_export(500_000_000)
        names = [p["name"] for p in projects]
        self.assertTrue(any("$600M" in n for n in names), "600M project should be included")

    def test_below_threshold_excluded(self):
        upsert_project(self.conn, _make_ontario_project("$400M"))
        projects = self._run_export(500_000_000)
        names = [p["name"] for p in projects]
        self.assertFalse(any("$400M" in n for n in names), "400M project should be excluded")

    # Test 2: "Not disclosed" projects included with value_confirmed=false
    def test_not_disclosed_included_unconfirmed(self):
        upsert_project(self.conn, _make_ontario_project("Not disclosed"))
        projects = self._run_export(500_000_000)
        unconfirmed = [p for p in projects if not p.get("value_confirmed", True)]
        self.assertTrue(len(unconfirmed) >= 1, "Not disclosed project should be included with value_confirmed=false")

    # Test 3: Unparseable value projects included with value_confirmed=false
    def test_unparseable_value_included_unconfirmed(self):
        upsert_project(self.conn, _make_ontario_project("TBD"))
        projects = self._run_export(500_000_000)
        unconfirmed = [p for p in projects if not p.get("value_confirmed", True)]
        self.assertTrue(len(unconfirmed) >= 1, "TBD project should be included with value_confirmed=false")

    # Test 4: JSON array fields are parsed from strings into proper arrays
    def test_json_array_fields_are_parsed(self):
        upsert_project(self.conn, _make_ontario_project("$600M"))
        projects = self._run_export(500_000_000)
        self.assertGreater(len(projects), 0, "Expected at least one project")
        proj = projects[0]
        # evidence and statusHistory must be lists, not strings
        self.assertIsInstance(proj.get("evidence"), list, "evidence must be a list")
        self.assertIsInstance(proj.get("statusHistory"), list, "statusHistory must be a list")


class TestExportAll(unittest.TestCase):
    """Tests 5–7: export_all creates all expected files with valid JSON and manifest."""

    def setUp(self):
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()
        # Insert one above-threshold project for Ontario
        upsert_project(self.conn, _make_ontario_project("$600M"))

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # Test 5: export_all creates all expected files
    def test_all_expected_files_created(self):
        from tools.export_dashboard import export_all, PROVINCE_SLUGS
        result = export_all(conn=self.conn, output_dir=self.tmpdir)

        expected_files = [
            "briefing_latest.json",
            "briefing_archive.json",
            "indicators.json",
            "trends.json",
            "events.json",
            "microscope.json",
            "timeseries.json",
            "manifest.json",
        ]
        # Check all province slug files
        for slug in PROVINCE_SLUGS:
            expected_files.append(f"projects_{slug}.json")

        for fname in expected_files:
            path = os.path.join(self.tmpdir, fname)
            self.assertTrue(
                os.path.exists(path),
                f"Expected file missing: {fname}"
            )

    # Test 6: All output files contain valid JSON
    def test_all_files_valid_json(self):
        from tools.export_dashboard import export_all
        export_all(conn=self.conn, output_dir=self.tmpdir)

        import glob
        json_files = glob.glob(os.path.join(self.tmpdir, "*.json"))
        self.assertGreater(len(json_files), 0, "No JSON files produced")

        for fpath in json_files:
            with open(fpath, encoding="utf-8") as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {os.path.basename(fpath)}: {e}")

    # Test 7: manifest.json contains exported_at and file_list
    def test_manifest_has_required_fields(self):
        from tools.export_dashboard import export_all
        export_all(conn=self.conn, output_dir=self.tmpdir)

        manifest_path = os.path.join(self.tmpdir, "manifest.json")
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("exported_at", manifest, "manifest must have exported_at")
        self.assertIn("file_list", manifest, "manifest must have file_list")
        self.assertIsInstance(manifest["file_list"], list)
        self.assertGreater(len(manifest["file_list"]), 0, "file_list must be non-empty")


class TestExportAllProjects(unittest.TestCase):
    """Test export_all_projects creates file with all projects across provinces."""

    def setUp(self):
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_project(self, name, province):
        return {
            "name": name,
            "province": province,
            "cma": "",
            "sector": "Construction",
            "naics_code": "23",
            "naics_name": "Construction",
            "value": "$600M",
            "status": "Proposed",
            "confidence": 0.8,
            "project_type": "greenfield",
            "is_brownfield": False,
            "proponent": "Test Corp",
            "description": "Test project.",
            "completionDate": "2028-12-31",
            "firstTracked": "2026-01-01",
            "lastUpdated": "2026-03-01",
            "lastSeen": "2026-03-01",
            "evidence": [{"url": "https://example.com/test", "title": "Test"}],
            "statusHistory": [{"status": "Proposed", "date": "2026-01-01", "detail": "Filed."}],
            "discovery_source": "rss_feed",
            "source_url_quality": "direct",
            "has_government_source": False,
            "evidence_count": 1,
            "tags": [],
            "sources": [],
            "discovery_sources": ["rss_feed"],
            "anomalies": [],
        }

    def test_export_all_projects_creates_file(self):
        """Insert 3 projects across 2 provinces, verify all 3 in projects_all.json."""
        from tools.export_dashboard import export_all_projects
        upsert_project(self.conn, self._make_project("Project A", "Ontario"))
        upsert_project(self.conn, self._make_project("Project B", "Alberta"))
        upsert_project(self.conn, self._make_project("Project C", "Alberta"))

        path = export_all_projects(self.conn, self.tmpdir)
        self.assertTrue(os.path.exists(path), "projects_all.json not created")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertIsInstance(data, list)
        names = [p["name"] for p in data]
        self.assertIn("Project A", names)
        self.assertIn("Project B", names)
        self.assertIn("Project C", names)
        self.assertEqual(len(data), 3, "Expected all 3 projects")


class TestExportPipelineStatus(unittest.TestCase):
    """Test export_pipeline_status creates pipeline_status.json with correct structure."""

    def setUp(self):
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_pipeline_status_creates_file(self):
        """Insert a pipeline run row, call export_pipeline_status, verify file structure."""
        from db import save_pipeline_run, save_dashboard_state
        from tools.export_dashboard import export_pipeline_status

        # Insert a pipeline run
        save_pipeline_run(self.conn, {
            "type": "weekly",
            "status": "success",
            "started_at": "2026-03-07",
            "completed_at": "2026-03-07",
            "duration_seconds": 1800,
            "steps_completed": ["step_1", "step_2"],
            "errors": [],
            "discovery": {"articles_found": 100, "projects_added": 5},
            "api_usage": {
                "claude_sonnet_input_tokens": 50000,
                "claude_sonnet_output_tokens": 10000,
            },
        })

        # Insert tavily credits dashboard state
        save_dashboard_state(self.conn, "tavily_credits", {"used": 250, "month": "2026-03"})

        path = export_pipeline_status(self.conn, self.tmpdir)
        self.assertTrue(os.path.exists(path), "pipeline_status.json not created")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("last_run", data, "must have last_run key")
        self.assertIn("tavily", data, "must have tavily key")
        self.assertIn("claude_tokens", data, "must have claude_tokens key")
        self.assertIn("recent_runs", data, "must have recent_runs key")

        self.assertEqual(data["last_run"]["status"], "success")
        self.assertEqual(data["tavily"]["used"], 250)
        self.assertEqual(data["tavily"]["month"], "2026-03")
        self.assertEqual(data["claude_tokens"]["input"], 50000)
        self.assertEqual(data["claude_tokens"]["output"], 10000)


class TestPipelineIntegration(unittest.TestCase):
    """Tests 8–11: verify update_dashboard.py pipeline integration (EXP-05)."""

    UPDATE_DASHBOARD_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "update_dashboard.py",
    )

    def _read_source(self):
        with open(self.UPDATE_DASHBOARD_PATH, encoding="utf-8") as f:
            return f.read()

    # Test 8: import statement present
    def test_export_all_import_present(self):
        source = self._read_source()
        self.assertIn(
            "from tools.export_dashboard import export_all",
            source,
            "update_dashboard.py must import export_all from export_dashboard",
        )

    # Test 9: conn parameter passed
    def test_export_all_called_with_conn(self):
        source = self._read_source()
        self.assertIn(
            "export_all(conn=conn)",
            source,
            "update_dashboard.py must call export_all(conn=conn)",
        )

    # Test 10: step logging present
    def test_step_9_logging_present(self):
        source = self._read_source()
        self.assertIn(
            "step_9_json_export",
            source,
            "update_dashboard.py must log 'step_9_json_export' step",
        )

    # Test 11: export_all handles empty database without crashing
    def test_export_all_empty_db(self):
        from tools.export_dashboard import export_all
        import tempfile, shutil
        conn = init_db(":memory:")
        tmpdir = tempfile.mkdtemp()
        try:
            result = export_all(conn=conn, output_dir=tmpdir)
            self.assertIn("file_count", result, "result must have file_count key")
            self.assertIn("output_dir", result, "result must have output_dir key")
            self.assertIsInstance(result["file_count"], int)
            self.assertGreater(result["file_count"], 0, "should export at least one file (manifest)")
        finally:
            conn.close()
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestQualityPass14ExportFields(unittest.TestCase):
    """quality-pass-1.4 R7/E9: needs_value, is_stale, display_confidence."""

    def test_needs_value_true_when_unpriced(self):
        from tools.export_dashboard import _project_for_export
        shaped = _project_for_export({"name": "X", "value": "Not disclosed"})
        self.assertTrue(shaped["needs_value"])
        self.assertFalse(shaped["value_confirmed"])

    def test_needs_value_false_when_priced(self):
        from tools.export_dashboard import _project_for_export
        shaped = _project_for_export({"name": "X", "value": "$600M"})
        self.assertFalse(shaped["needs_value"])
        self.assertTrue(shaped["value_confirmed"])

    def test_is_stale_and_display_confidence_exported(self):
        from tools.export_dashboard import _project_for_export
        shaped = _project_for_export({
            "name": "X", "value": "$600M",
            "is_stale": 1, "display_confidence": 0.45,
        })
        self.assertIs(shaped["is_stale"], True)
        self.assertEqual(shaped["display_confidence"], 0.45)

    def test_is_stale_defaults_false(self):
        from tools.export_dashboard import _project_for_export
        shaped = _project_for_export({"name": "X", "value": "$600M"})
        self.assertIs(shaped["is_stale"], False)

    def test_db_round_trip_includes_new_fields(self):
        conn = init_db(":memory:")
        tmpdir = tempfile.mkdtemp()
        try:
            from tools.export_dashboard import export_province_projects
            upsert_project(conn, _make_ontario_project("$600M"))
            export_province_projects(conn, "Ontario", 500_000_000, tmpdir)
            with open(os.path.join(tmpdir, "projects_ontario.json"),
                      encoding="utf-8") as f:
                projects = json.load(f)
            self.assertGreater(len(projects), 0)
            proj = projects[0]
            self.assertIn("needs_value", proj)
            self.assertIn("is_stale", proj)
            self.assertIn("display_confidence", proj)
        finally:
            conn.close()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestExportProvinceCounts(unittest.TestCase):
    """quality-pass-1.4 P3: per-province accuracy counters."""

    def setUp(self):
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_mb(self, name, value):
        upsert_project(self.conn, {
            "name": name,
            "province": "Manitoba",
            "status": "Proposed",
            "value": value,
            "evidence": [{"url": f"https://example.gov.mb.ca/{name.replace(' ', '-').lower()}"}],
            "discovery_source": "provincial_ea",
        })

    def test_province_counts_math(self):
        """MB threshold $40M: 2 priced-above, 1 priced-below, 3 unpriced,
        1 stale → qualifying:2, tracked_unpriced:3, stale:1."""
        from tools.export_dashboard import export_province_counts

        # 2 priced above threshold
        self._seed_mb("Winnipeg Transit Garage Replacement", "$50M")
        self._seed_mb("Selkirk Steel Recycling Complex", "$100M")
        # 1 priced below threshold
        self._seed_mb("Brandon Pumphouse Refurbishment", "$10M")
        # 3 unpriced
        self._seed_mb("Churchill Port Modernization Initiative", "Not disclosed")
        self._seed_mb("Portage Diversion Upgrade Program", "Not disclosed")
        self._seed_mb("Thompson Mining Access Corridor", "Not disclosed")
        # 1 stale (priced above threshold but flagged stale)
        self._seed_mb("Dauphin Regional Health Campus", "$60M")
        self.conn.execute(
            "UPDATE projects SET is_stale = 1 WHERE name = ?",
            ("Dauphin Regional Health Campus",))
        self.conn.commit()

        path = export_province_counts(self.conn, self.tmpdir)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        mb = data["provinces"]["MB"]
        self.assertEqual(mb["qualifying"], 2)
        self.assertAlmostEqual(mb["qualifying_value"], 150_000_000.0)
        self.assertEqual(mb["tracked_unpriced"], 3)
        self.assertEqual(mb["stale"], 1)
        self.assertEqual(mb["threshold"], 40_000_000)
        # All 13 provinces present
        self.assertEqual(len(data["provinces"]), 13)

    def test_wired_into_export_all(self):
        from tools.export_dashboard import export_all
        result = export_all(conn=self.conn, output_dir=self.tmpdir)
        self.assertIn("province_counts.json", result["files_written"])
        self.assertIn("discovery_summary.json", result["files_written"])


class TestExportDiscoverySummary(unittest.TestCase):
    """quality-pass-1.4 E8: weekly discovery summary."""

    def setUp(self):
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()
        from datetime import date, timedelta
        today = date.today()
        self.week_start = (today - timedelta(days=today.weekday())).isoformat()

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed(self, name, first_tracked, last_seen):
        upsert_project(self.conn, {
            "name": name, "province": "Alberta", "status": "Proposed",
            "value": "$300M",
            "evidence": [{"url": f"https://example.ca/{name.replace(' ', '-').lower()}"}],
        })
        self.conn.execute(
            "UPDATE projects SET firstTracked = ?, lastSeen = ? WHERE name = ?",
            (first_tracked, last_seen, name))
        self.conn.commit()

    def test_discovery_summary_counts(self):
        from tools.export_dashboard import export_discovery_summary

        # New this week: firstTracked >= week start
        self._seed("Calgary Hydrogen Production Hub",
                   self.week_start, self.week_start)
        # Rediscovered: tracked before this week, seen this week
        self._seed("Edmonton Petrochemical Upgrader Expansion",
                   "2026-01-15", self.week_start)
        # Untouched this week: counted in neither bucket
        self._seed("Fort McMurray Bitumen Terminal",
                   "2026-01-15", "2026-02-01")
        # Status change rows this week (one status, one cost — only status counts)
        self.conn.execute(
            "INSERT INTO project_changes (project_id, change_date, change_type, "
            "field, old_value, new_value) VALUES (1, ?, 'status', 'status', "
            "'Proposed', 'Approved')", (self.week_start,))
        self.conn.execute(
            "INSERT INTO project_changes (project_id, change_date, change_type, "
            "field, old_value, new_value) VALUES (1, ?, 'cost', 'value', "
            "'$300M', '$350M')", (self.week_start,))
        self.conn.commit()

        path = export_discovery_summary(self.conn, self.tmpdir)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["week_of"], self.week_start)
        self.assertEqual(data["new"], 1)
        self.assertEqual(data["rediscovered"], 1)
        self.assertEqual(data["status_changes"], 1)
        self.assertIn("fuzzy_merges", data)


class TestTimeseriesStaleReport(unittest.TestCase):
    """NEW-9: timeseries stale-series report (warn-first, prune only on env)."""

    def setUp(self):
        from datetime import date, timedelta
        self.conn = init_db(":memory:")
        self.tmpdir = tempfile.mkdtemp()
        self.fresh_date = date.today().isoformat()
        self.stale_date = (date.today() - timedelta(days=600)).isoformat()
        # Pre-seed an existing timeseries.json the preserve-merge will keep
        self.existing = {
            "stale_series": [
                {"date": self.stale_date, "value": "1.0", "unit": "", "source": "test"},
            ],
            "fresh_series": [
                {"date": self.fresh_date, "value": "2.0", "unit": "", "source": "test"},
            ],
        }
        with open(os.path.join(self.tmpdir, "timeseries.json"), "w",
                  encoding="utf-8") as f:
            json.dump(self.existing, f)
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ("TIMESERIES_PRUNE", "TIMESERIES_STALE_DAYS")
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        self.conn.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_export(self):
        from tools.export_dashboard import export_timeseries
        out_path = export_timeseries(self.conn, self.tmpdir)
        with open(out_path, encoding="utf-8") as f:
            merged = json.load(f)
        report_path = os.path.join(self.tmpdir, "timeseries_stale_report.json")
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        return merged, report

    def test_find_stale_series_helper(self):
        from tools.export_dashboard import _find_stale_series
        stale = _find_stale_series(self.existing, stale_days=540)
        self.assertEqual(stale, {"stale_series": self.stale_date})

    def test_stale_series_appears_in_report_not_pruned(self):
        merged, report = self._run_export()
        self.assertIn("stale_series", report["stale_series"])
        self.assertEqual(report["stale_series"]["stale_series"], self.stale_date)
        self.assertFalse(report["pruned"])
        # Default is warn-first: the stale key is still exported
        self.assertIn("stale_series", merged)
        self.assertIn("fresh_series", merged)

    def test_prune_env_removes_stale_series(self):
        os.environ["TIMESERIES_PRUNE"] = "1"
        merged, report = self._run_export()
        self.assertTrue(report["pruned"])
        self.assertIn("stale_series", report["stale_series"])
        self.assertNotIn("stale_series", merged)
        # Fresh series untouched
        self.assertIn("fresh_series", merged)
        self.assertEqual(merged["fresh_series"], self.existing["fresh_series"])

    def test_fresh_series_not_reported(self):
        _, report = self._run_export()
        self.assertNotIn("fresh_series", report["stale_series"])

    def test_stale_days_env_override(self):
        # With a huge threshold nothing is stale
        os.environ["TIMESERIES_STALE_DAYS"] = "100000"
        merged, report = self._run_export()
        self.assertEqual(report["stale_series"], {})
        self.assertEqual(report["stale_days_threshold"], 100000)
        self.assertIn("stale_series", merged)


if __name__ == "__main__":
    unittest.main()
