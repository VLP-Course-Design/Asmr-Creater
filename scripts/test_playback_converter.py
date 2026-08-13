"""
test_playback_converter.py —— 音频决策层播放计划转换器测试

覆盖: 带深度输入 → 单声道+双耳双计划 / 不带深度输入 → 仅单声道回退

用法: python scripts/test_playback_converter.py
      或 python -m unittest scripts.test_playback_converter -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from audio.playback_converter import convert  # noqa: E402

EXAMPLES_DIR = REPO_ROOT / "contracts" / "playback_proposal" / "examples"
CONFIG_DIR = REPO_ROOT / "configs" / "playback"


class ConverterTests(unittest.TestCase):
    def test_with_depth_generates_two_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            report = convert(
                EXAMPLES_DIR / "with_depth/example_coastal_bird_with_depth.json",
                Path(directory),
                CONFIG_DIR,
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
                EXAMPLES_DIR / "without_depth/example_study_keyboard_without_depth.json",
                Path(directory),
                CONFIG_DIR,
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

