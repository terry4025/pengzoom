import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtWidgets import QApplication

from cooldown_detector import CooldownDetector
from magnifier import MagnifierWindow, PartyPanel


class _FakeScreenCapture:
    def __init__(self, image):
        self.image = image

    def grab(self, monitor):
        return self.image


class _FailingScreenCapture:
    def grab(self, monitor):
        raise OSError("capture unavailable")


class PartySyncSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_zero_duration_not_ready_state_stays_cooldown(self):
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
        self.assertFalse(widgets["is_ready"])
        self.assertEqual(widgets["status_text_lbl"].text(), "Cooldown")
        panel.close()

    def test_manual_remaining_seconds_are_sent_on_skill_state_change(self):
        sent = []
        client = SimpleNamespace(
            send_update=lambda name, ready, duration: sent.append((name, ready, duration))
        )
        slot = SimpleNamespace(is_ready=False, cooldown_duration=30)
        fake_window = SimpleNamespace(
            client_running=True,
            client=client,
            detector=SimpleNamespace(
                slots={"skill": slot},
                get_remaining_seconds=lambda name: 12,
            ),
        )

        MagnifierWindow.on_skill_state_changed(fake_window, "skill", False, 0.5)

        self.assertEqual(sent, [("skill", False, 12)])

    def test_legacy_ocr_configuration_cannot_enable_automatic_seconds(self):
        detector = CooldownDetector()
        detector.add_slot("skill", (0, 0, 10, 10), cooldown_duration=30)

        detector.configure_ocr("skill", mode="primary", save_diagnostics=True)

        slot = detector.slots["skill"]
        self.assertEqual(slot.ocr_mode, "off")
        self.assertFalse(slot.ocr_enabled)
        self.assertFalse(slot.ocr_save_diagnostics)

    def test_elapsed_countdown_does_not_promote_ready(self):
        panel = PartyPanel()
        panel.timer.stop()
        panel.update_states({
            "player": {
                "skill": {
                    "is_ready": False,
                    "cooldown_duration": 1,
                    "timestamp": time.time() - 5,
                }
            }
        })

        panel.tick_timers()

        widgets = panel.widgets["player"]["skill_widgets"]["skill"]
        self.assertFalse(widgets["is_ready"])
        self.assertEqual(widgets["status_text_lbl"].text(), "Cooldown")
        panel.close()

    def test_periodic_remaining_sync_does_not_reset_ring_total(self):
        panel = PartyPanel()
        panel.timer.stop()
        now = time.time()
        panel.update_states({
            "player": {
                "skill": {
                    "is_ready": False,
                    "cooldown_duration": 30,
                    "timestamp": now,
                }
            }
        })
        panel.update_states({
            "player": {
                "skill": {
                    "is_ready": False,
                    "cooldown_duration": 28,
                    "timestamp": now,
                }
            }
        })
        panel.tick_timers()

        widgets = panel.widgets["player"]["skill_widgets"]["skill"]
        self.assertEqual(widgets["cycle_total"], 30)
        self.assertLess(widgets["progress"].value, 95.0)
        panel.close()

    def test_new_positive_countdown_relatches_after_expired_cooldown(self):
        panel = PartyPanel()
        panel.timer.stop()
        now = time.time()
        panel.update_states({
            "player": {
                "skill": {
                    "is_ready": False,
                    "cooldown_duration": 3,
                    "timestamp": now - 5,
                }
            }
        })
        panel.update_states({
            "player": {
                "skill": {
                    "is_ready": False,
                    "cooldown_duration": 3,
                    "timestamp": now,
                }
            }
        })
        panel.tick_timers()

        widgets = panel.widgets["player"]["skill_widgets"]["skill"]
        self.assertGreater(widgets["cooldown_deadline"], now)
        self.assertGreater(widgets["progress"].value, 90.0)
        panel.close()

    def test_increased_countdown_relatches_before_old_deadline(self):
        panel = PartyPanel()
        panel.timer.stop()
        started_at = time.time()
        with patch("magnifier.time.time", return_value=started_at):
            panel.update_states({
                "player": {
                    "skill": {
                        "is_ready": False,
                        "cooldown_duration": 30,
                        "timestamp": started_at,
                    }
                }
            })
        with patch("magnifier.time.time", return_value=started_at + 10):
            panel.update_states({
                "player": {
                    "skill": {
                        "is_ready": False,
                        "cooldown_duration": 30,
                        "timestamp": started_at + 10,
                    }
                }
            })

        widgets = panel.widgets["player"]["skill_widgets"]["skill"]
        self.assertAlmostEqual(widgets["cooldown_deadline"], started_at + 40, places=3)
        self.assertEqual(widgets["cycle_total"], 30)
        panel.close()

    def test_malformed_skill_state_is_ignored(self):
        panel = PartyPanel()
        panel.timer.stop()
        panel.update_states({"player": {"_class": "테스트", "bad": "not-a-state"}})
        self.assertNotIn("bad", panel.widgets["player"]["skill_widgets"])
        panel.close()

    def test_template_mismatch_is_cooldown_in_manual_mode(self):
        detector = CooldownDetector()
        template = np.zeros((10, 10, 3), dtype=np.uint8)
        template[2:8, 2:8] = 255
        detector.add_slot("skill", (0, 0, 10, 10), template_img=template)
        capture = _FakeScreenCapture(np.zeros((10, 10, 4), dtype=np.uint8))

        for _ in range(4):
            detector.scan_all(capture)

        self.assertFalse(detector.slots["skill"].is_ready)

    def test_ready_requires_three_matching_template_frames(self):
        detector = CooldownDetector()
        template = np.zeros((10, 10, 3), dtype=np.uint8)
        template[2:8, 2:8] = 255
        detector.add_slot("skill", (0, 0, 10, 10), template_img=template)
        detector.configure_ocr("skill", mode="off")

        capture_image = np.zeros((10, 10, 4), dtype=np.uint8)
        capture_image[:, :, :3] = template[:, :, ::-1]
        capture_image[:, :, 3] = 255
        capture = _FakeScreenCapture(capture_image)

        detector.scan_all(capture)
        detector.scan_all(capture)
        self.assertFalse(detector.slots["skill"].is_ready)
        detector.scan_all(capture)
        self.assertTrue(detector.slots["skill"].is_ready)

    def test_darkened_correlated_icon_is_not_ready(self):
        detector = CooldownDetector()
        rng = np.random.default_rng(42)
        template = rng.integers(20, 236, size=(20, 20, 3), dtype=np.uint8)
        detector.add_slot("skill", (0, 0, 20, 20), template_img=template)
        detector.configure_ocr("skill", mode="off")

        dark_rgb = (template.astype(np.float32) * 0.35).astype(np.uint8)
        capture_image = np.zeros((20, 20, 4), dtype=np.uint8)
        capture_image[:, :, :3] = dark_rgb[:, :, ::-1]
        capture_image[:, :, 3] = 255
        capture = _FakeScreenCapture(capture_image)

        for _ in range(3):
            detector.scan_all(capture)

        slot = detector.slots["skill"]
        self.assertGreater(slot.last_similarity, 0.99)
        self.assertLess(slot.last_appearance_similarity, 0.82)
        self.assertFalse(slot.is_ready)

    def test_three_capture_failures_demote_stale_ready_state(self):
        detector = CooldownDetector()
        template = np.zeros((10, 10, 3), dtype=np.uint8)
        template[2:8, 2:8] = 255
        detector.add_slot("skill", (0, 0, 10, 10), template_img=template)
        detector.configure_ocr("skill", mode="off")

        ready_image = np.zeros((10, 10, 4), dtype=np.uint8)
        ready_image[:, :, :3] = template[:, :, ::-1]
        ready_image[:, :, 3] = 255
        for _ in range(3):
            detector.scan_all(_FakeScreenCapture(ready_image))
        self.assertTrue(detector.slots["skill"].is_ready)

        detector.scan_all(_FailingScreenCapture())
        detector.scan_all(_FailingScreenCapture())
        self.assertTrue(detector.slots["skill"].is_ready)
        detector.scan_all(_FailingScreenCapture())
        self.assertFalse(detector.slots["skill"].is_ready)

    def test_first_mismatch_does_not_clear_new_manual_timer(self):
        detector = CooldownDetector()
        template = np.zeros((10, 10, 3), dtype=np.uint8)
        template[2:8, 2:8] = 255
        detector.add_slot(
            "skill",
            (0, 0, 10, 10),
            template_img=template,
            cooldown_duration=30,
        )
        slot = detector.slots["skill"]
        slot.is_ready = True
        slot._ready_consec_frames = 3
        detector.request_trigger("skill")
        detector._drain_trigger_requests()

        detector.scan_all(_FakeScreenCapture(np.zeros((10, 10, 4), dtype=np.uint8)))

        self.assertTrue(slot.is_ready)
        self.assertGreater(slot.cooldown_start_time, 0.0)

    def test_manual_mode_preserves_skill_template_state_transitions(self):
        detector = CooldownDetector()
        template = np.zeros((10, 10, 3), dtype=np.uint8)
        template[2:8, 2:8] = 255
        detector.add_slot("skill", (0, 0, 10, 10), template_img=template)
        slot = detector.slots["skill"]

        ready_image = np.zeros((10, 10, 4), dtype=np.uint8)
        ready_image[:, :, :3] = template[:, :, ::-1]
        ready_image[:, :, 3] = 255
        ready_capture = _FakeScreenCapture(ready_image)
        for _ in range(3):
            detector.scan_all(ready_capture)
        self.assertTrue(slot.is_ready)

        mismatch_capture = _FakeScreenCapture(np.zeros((10, 10, 4), dtype=np.uint8))
        for _ in range(3):
            detector.scan_all(mismatch_capture)
        self.assertFalse(slot.is_ready)

    def test_developer_capture_writes_one_labeled_frame_per_second(self):
        detector = CooldownDetector()
        detector.add_slot(
            "파천",
            (0, 0, 10, 10),
            template_img=np.zeros((10, 10, 3), dtype=np.uint8),
            cooldown_duration=3,
        )
        detector.developer_capture_enabled = True
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as temp_dir:
            detector.developer_capture_root = Path(temp_dir)
            detector.request_trigger("파천", trigger_monotonic=100.0)
            detector._drain_trigger_requests(now_mono=100.0)
            detector._capture_developer_frame("파천", frame, 100.25)
            detector._capture_developer_frame("파천", frame, 101.25)
            detector._capture_developer_frame("파천", frame, 102.25)

            sessions = [path for path in Path(temp_dir).iterdir() if path.is_dir()]
            self.assertEqual(len(sessions), 1)
            self.assertEqual(
                {path.name for path in sessions[0].glob("*.png")},
                {"파천_3s.png", "파천_2s.png", "파천_1s.png"},
            )
            self.assertNotIn("파천", detector._developer_sessions)

    def test_delayed_trigger_processing_skips_stale_capture_labels(self):
        detector = CooldownDetector()
        detector.add_slot(
            "파천",
            (0, 0, 10, 10),
            template_img=np.zeros((10, 10, 3), dtype=np.uint8),
            cooldown_duration=3,
        )
        detector.developer_capture_enabled = True
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as temp_dir:
            detector.developer_capture_root = Path(temp_dir)
            detector.request_trigger("파천", trigger_monotonic=100.0)
            detector._drain_trigger_requests(now_mono=102.0)
            detector._capture_developer_frame("파천", frame, 102.0)
            detector._capture_developer_frame("파천", frame, 102.25)

            session = next(path for path in Path(temp_dir).iterdir() if path.is_dir())
            self.assertEqual(
                {path.name for path in session.glob("*.png")},
                {"파천_2s.png", "파천_1s.png"},
            )


if __name__ == "__main__":
    unittest.main()
