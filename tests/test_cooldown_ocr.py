import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from unittest import mock

from cooldown_ocr import (
    DEFAULT_PROFILE_ID,
    OcrDatasetCollector,
    OcrObservation,
    OcrProfileStore,
    _TemporalState,
    benchmark_profile,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "ocr_profiles" / f"{DEFAULT_PROFILE_ID}.json"
SAMPLE_PATH = ROOT / "쿨타임 이미지들"


class ProfileTests(unittest.TestCase):
    def test_bundled_profile_contains_all_digits(self):
        store = OcrProfileStore(PROFILE_PATH.parent)
        profile = store.load(DEFAULT_PROFILE_ID)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.trained)
        self.assertEqual(set(profile.labels), set(range(10)))

    def test_embedded_profile_fallback_needs_no_data_file(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "cooldown_ocr._resource_path", return_value=Path(temp) / "missing.json"
        ):
            profile = OcrProfileStore(Path(temp) / "profiles").load(DEFAULT_PROFILE_ID)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.trained)

    @unittest.skipUnless(SAMPLE_PATH.exists(), "local Lost Ark capture set is not present")
    def test_local_seed_benchmark_never_confirms_a_wrong_value(self):
        result = benchmark_profile(PROFILE_PATH, list(SAMPLE_PATH.glob("*.png")))
        self.assertEqual(result["false_confirm"], 0)
        continuous = [row for row in result["rows"] if row["file"].startswith("파천_")
                      and 1 <= row["expected"] <= 30]
        self.assertEqual(len(continuous), 30)
        self.assertTrue(all(row["accepted"] and row["observed"] == row["expected"] for row in continuous))


class TemporalFilterTests(unittest.TestCase):
    @staticmethod
    def observation(value, confidence=1.0):
        return OcrObservation(value, confidence, True, raw_seconds=value)

    def test_large_drop_needs_two_high_confidence_frames(self):
        state = _TemporalState()
        self.assertTrue(state.filter(self.observation(30), 1.0).accepted)
        first = state.filter(self.observation(20, 0.95), 1.1)
        second = state.filter(self.observation(20, 0.95), 1.2)
        self.assertFalse(first.accepted)
        self.assertEqual(first.reject_reason, "large_drop_needs_confirmation")
        self.assertTrue(second.accepted)

    def test_increase_is_allowed_only_after_ready(self):
        state = _TemporalState()
        state.filter(self.observation(10), 1.0)
        rejected = state.filter(self.observation(30), 1.1)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reject_reason, "increase_while_active")
        state.mark_ready()
        self.assertTrue(state.filter(self.observation(30), 2.0).accepted)


class DatasetCollectorTests(unittest.TestCase):
    def test_collector_writes_slot_crops_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            collector = OcrDatasetCollector(Path(temp))
            session = collector.start("테스트", 30, {"scale": 1.0})
            frame = np.zeros((43, 45, 3), dtype=np.uint8)
            self.assertTrue(collector.add_frame(frame, collector.started_at))
            collector.stop()
            self.assertEqual(len(list(session.glob("*.png"))), 1)
            self.assertTrue((session / "metadata.json").exists())


if __name__ == "__main__":
    unittest.main()
