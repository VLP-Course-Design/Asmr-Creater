import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from playback_converter import convert  # noqa: E402


class ConverterTests(unittest.TestCase):
    def test_with_depth_generates_two_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            report = convert(
                PROJECT_ROOT / "inputs/with_depth/example_coastal_bird_with_depth.json",
                Path(directory),
                PROJECT_ROOT / "config",
                18432,
                1800.0,
            )
            self.assertTrue(report["spatial_gate_passed"])
            self.assertTrue(Path(report["mono_plan"]).exists())
            self.assertTrue(Path(report["binaural_plan"]).exists())
            binaural = json.loads(Path(report["binaural_plan"]).read_text(encoding="utf-8"))
            self.assertEqual(binaural["schema_version"], "2.0-binaural")
            self.assertEqual(binaural["render"]["output_channels"], 2)

    def test_without_depth_generates_mono_only(self):
        with tempfile.TemporaryDirectory() as directory:
            report = convert(
                PROJECT_ROOT / "inputs/without_depth/example_study_keyboard_without_depth.json",
                Path(directory),
                PROJECT_ROOT / "config",
                18432,
                1800.0,
            )
            self.assertFalse(report["spatial_gate_passed"])
            self.assertIsNone(report["binaural_plan"])
            mono = json.loads(Path(report["mono_plan"]).read_text(encoding="utf-8"))
            self.assertEqual(mono["schema_version"], "2.0-mono")
            self.assertEqual(mono["fallback"]["failure_reasons"][0]["code"], "DEPTH_HINT_MISSING")


if __name__ == "__main__":
    unittest.main()

