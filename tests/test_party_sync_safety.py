import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtWidgets import QApplication

from cooldown_detector import CooldownDetector
from cooldown_ocr import OcrObservation
from magnifier import PartyPanel


class _FakeScreenCapture:
    def __init__(self, image):
        self.image = image

    def grab(self, monitor):
        return self.image


class PartySyncSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_zero_duration_not_ready_state_is_indeterminate(self):
        panel = PartyPanel()
        panel.timer.stop()
        panel.update_states({
            "player": {
                "_class": "테스트",
                "skill": {
                    "is_ready": False,
                    "cooldown_duration": 0,
                    "timestamp": 0,
                },
            }
        })

        panel.tick_timers()

        widgets = panel.widgets["player"]["skill_widgets"]["skill"]
        self.assertEqual(widgets["status_text_lbl"].text(), "인식 중")
        panel.close()

    def test_malformed_skill_state_is_ignored(self):
        panel = PartyPanel()
        panel.timer.stop()
        panel.update_states({"player": {"_class": "테스트", "bad": "not-a-state"}})
        self.assertNotIn("bad", panel.widgets["player"]["skill_widgets"])
        panel.close()

    def test_primary_ocr_does_not_start_from_template_mismatch(self):
        detector = CooldownDetector()
        detector.ocr_engine.logger.enabled = False
        template = np.zeros((10, 10, 3), dtype=np.uint8)
        template[2:8, 2:8] = 255
        detector.add_slot("skill", (0, 0, 10, 10), template_img=template)
        detector.configure_ocr("skill", mode="primary")
        detector.ocr_engine.recognize = lambda *args, **kwargs: OcrObservation(
            None, 0.0, False, "suffix_not_found"
        )
        capture = _FakeScreenCapture(np.zeros((10, 10, 4), dtype=np.uint8))

        for _ in range(4):
            detector.scan_all(capture)

        self.assertTrue(detector.slots["skill"].is_ready)


if __name__ == "__main__":
    unittest.main()
