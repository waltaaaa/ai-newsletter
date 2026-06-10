"""
tests/test_conductor_model.py — NEW-5 conductor model pinning.

The conductor must not float on the CLI 'opus' alias: with CONDUCTOR_MODEL
unset, it resolves to the concrete OPUS_MODEL constant from pipeline_config.
"""

import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConductorModelPinning(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("CONDUCTOR_MODEL", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["CONDUCTOR_MODEL"] = self._saved
        else:
            os.environ.pop("CONDUCTOR_MODEL", None)
        # Restore module state computed from the (restored) environment
        import phases.conductor as conductor
        importlib.reload(conductor)

    def test_default_resolves_to_pinned_opus_constant(self):
        import phases.conductor as conductor
        importlib.reload(conductor)
        from pipeline_config import OPUS_MODEL
        self.assertEqual(conductor.CONDUCTOR_MODEL, OPUS_MODEL)
        # Never the floating CLI alias
        self.assertNotEqual(conductor.CONDUCTOR_MODEL, "opus")

    def test_env_override_wins(self):
        os.environ["CONDUCTOR_MODEL"] = "claude-test-model-1"
        import phases.conductor as conductor
        importlib.reload(conductor)
        self.assertEqual(conductor.CONDUCTOR_MODEL, "claude-test-model-1")

    def test_empty_env_falls_back_to_pinned(self):
        os.environ["CONDUCTOR_MODEL"] = ""
        import phases.conductor as conductor
        importlib.reload(conductor)
        from pipeline_config import OPUS_MODEL
        self.assertEqual(conductor.CONDUCTOR_MODEL, OPUS_MODEL)


if __name__ == "__main__":
    unittest.main()
