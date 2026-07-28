import math
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PyQt6.QtWidgets import QApplication

import magnifier  # noqa: E402
from cooldown_detector import CooldownDetector  # noqa: E402
from magnifier import MagnifierWindow, PartyPanel  # noqa: E402


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

    def test_repeated_keypress_during_cooldown_does_not_restart_the_timer(self):
        """쿨타임 중에 키를 또 눌러도 남은 시간이 되돌아가면 안 된다.

        스킬 키를 연타하거나 누른 채로 두면 pynput이 같은 키를 계속 보고한다.
        예전에는 그 입력마다 수동 타이머를 다시 시작해서, 진행 바가 0까지
        내려가지 못하고 중간에서 계속 처음 위치로 튀었다.
        """
        detector = CooldownDetector()
        detector.add_slot("skill", (0, 0, 10, 10), cooldown_duration=30)
        slot = detector.slots["skill"]

        first = time.time()
        detector.request_trigger("skill", trigger_monotonic=time.monotonic())
        detector._drain_trigger_requests()
        started_at = slot.cooldown_start_time
        self.assertGreater(started_at, 0.0)

        # 10초 지난 시점의 연타 입력 3번.
        slot.cooldown_start_time = first - 10.0
        for _ in range(3):
            detector.request_trigger("skill", trigger_monotonic=time.monotonic())
        detector._drain_trigger_requests()

        self.assertAlmostEqual(slot.cooldown_start_time, first - 10.0, places=3)
        self.assertAlmostEqual(detector.get_remaining_seconds_precise("skill"), 20.0, delta=0.5)

    def test_keypress_after_ready_restarts_the_timer(self):
        """반대로 스킬이 사용 가능해진 뒤의 입력은 정상적으로 새 쿨타임을 건다."""
        detector = CooldownDetector()
        detector.add_slot("skill", (0, 0, 10, 10), cooldown_duration=30)
        slot = detector.slots["skill"]
        slot.cooldown_start_time = time.time() - 40.0     # 이미 끝난 쿨타임

        detector.request_trigger("skill", trigger_monotonic=time.monotonic())
        detector._drain_trigger_requests()

        self.assertAlmostEqual(detector.get_remaining_seconds_precise("skill"), 30.0, delta=0.5)

    def test_charge_skill_recognized_as_ready_can_restart_early(self):
        """차지/게이지 스킬처럼 아직 사용 가능해 보이면 재사용을 허용한다."""
        detector = CooldownDetector()
        detector.add_slot("skill", (0, 0, 10, 10), cooldown_duration=30)
        slot = detector.slots["skill"]
        slot.cooldown_start_time = time.time() - 10.0
        slot.is_ready = True

        detector.request_trigger("skill", trigger_monotonic=time.monotonic())
        detector._drain_trigger_requests()

        self.assertAlmostEqual(detector.get_remaining_seconds_precise("skill"), 30.0, delta=0.5)

    def test_local_skill_bar_ignores_round_trip_report_noise(self):
        """내 스킬 진행 바는 서버 왕복 보고가 흔들려도 로컬 타이머만 따른다.

        키를 다시 누르지 않았는데도 바가 조금씩 되돌아가던 증상의 대책이다.
        보고에는 왕복 지연·서버 시각 보정·반올림 오차가 섞이지만, 내 쿨타임은
        이미 이 PC에 정확한 값으로 있으므로 그것을 그대로 쓴다.
        """
        detector = CooldownDetector()
        detector.add_slot("구원", (0, 0, 10, 10), cooldown_duration=30)
        slot = detector.slots["구원"]
        start = 3000.0
        slot.cooldown_start_time = start

        panel = PartyPanel()
        panel.timer.stop()
        # closeEvent 가 parent_window.save_settings() 를 부르므로 함께 넣어 준다.
        panel.parent_window = SimpleNamespace(
            player_name="펭구", detector=detector, save_settings=lambda: None)
        clock = {"now": start}
        # 보고 시각이 앞뒤로 튀고 남은 초도 정수로 반올림되어 들어온다.
        noise = [0.0, 0.9, -0.7, 1.1, -1.2, 0.6, -0.9, 1.3]

        with patch("magnifier.time.time", lambda: clock["now"]):
            values = []
            for step in range(0, 15):
                clock["now"] = start + step * 2.0
                remaining = max(0.0, 30.0 - (clock["now"] - start))
                panel.update_states({"펭구": {
                    "_class": "테스트",
                    "구원": {
                        "is_ready": False,
                        "cooldown_duration": math.ceil(remaining),
                        "timestamp": clock["now"] + noise[step % len(noise)],
                    }}})
                for _ in range(4):
                    clock["now"] += 0.5
                    panel.tick_timers()
                    values.append(panel.widgets["펭구"]["skill_widgets"]["구원"]["progress"].value)

            widgets = panel.widgets["펭구"]["skill_widgets"]["구원"]
            # 분모는 보고된 '남은 초'가 아니라 실제 총 쿨타임이어야 한다.
            self.assertAlmostEqual(widgets["cycle_total"], 30.0, places=3)
            self.assertAlmostEqual(widgets["cooldown_deadline"], start + 30.0, places=3)

        backwards = [(a, b) for a, b in zip(values, values[1:]) if b > a + 1e-6]
        self.assertFalse(backwards, f"진행 바가 되돌아갔습니다: {backwards[:3]}")
        self.assertLessEqual(values[-1], 1.0)
        panel.close()

    def test_transient_missing_skill_does_not_reset_the_cycle(self):
        """보고에서 한 번 빠진 스킬 때문에 사이클이 리셋되면 안 된다."""
        panel = PartyPanel()
        panel.timer.stop()
        start = 4000.0
        clock = {"now": start}
        with patch("magnifier.time.time", lambda: clock["now"]):
            panel.update_states({"펭구": {"_class": "테스트", "구원": {
                "is_ready": False, "cooldown_duration": 30, "timestamp": start}}})
            clock["now"] = start + 15.0
            panel.tick_timers()
            before = panel.widgets["펭구"]["skill_widgets"]["구원"]["progress"].value

            # 스냅샷이 한 번 스킬을 빼먹고 온다.
            panel.update_states({"펭구": {"_class": "테스트"}})
            self.assertIn("구원", panel.widgets["펭구"]["skill_widgets"])

            panel.update_states({"펭구": {"_class": "테스트", "구원": {
                "is_ready": False, "cooldown_duration": 15, "timestamp": clock["now"]}}})
            panel.tick_timers()
            after = panel.widgets["펭구"]["skill_widgets"]["구원"]["progress"].value

        self.assertLessEqual(after, before + 1e-6, "위젯이 새로 만들어져 바가 다시 찼습니다.")
        panel.close()

    def test_manual_cooldown_bar_never_moves_backwards(self):
        """수동 쿨타임 진행 바는 0까지 한 방향으로만 줄어야 한다.

        동기화 보고는 '남은 초'를 2초마다 실어 보내는데, 정수 반올림과 서버
        시각 보정 오차가 겹치면 수신 측이 계산한 종료 시각이 매번 조금씩
        달라진다. 예전에는 그 차이를 '재사용'으로 오인해 사이클을 다시 걸었고,
        진행 바가 쿨타임 도중 계속 앞쪽으로 되돌아갔다.
        """
        panel = PartyPanel()
        panel.timer.stop()
        start = 1000.0
        clock = {"now": start}
        total = 30.0
        jitter = [0.0, 0.42, -0.38, 0.5, -0.47, 0.31, -0.29, 0.48]

        def report(remaining, stamp):
            panel.update_states({
                "player": {
                    "_class": "테스트",
                    "skill": {
                        "is_ready": False,
                        # 예전 송신부가 그랬듯 정수로 올림해서 보낸다.
                        "cooldown_duration": math.ceil(remaining),
                        "timestamp": stamp,
                    }
                }
            })

        with patch("magnifier.time.time", lambda: clock["now"]):
            report(total, start)
            panel.tick_timers()
            gauge = panel.widgets["player"]["skill_widgets"]["skill"]["progress"]
            values = [gauge.value]
            for step in range(1, 16):
                clock["now"] = start + step * 2.0
                remaining = max(0.0, total - (clock["now"] - start))
                report(remaining, clock["now"] + jitter[step % len(jitter)])
                for _ in range(4):
                    clock["now"] += 0.5
                    panel.tick_timers()
                    values.append(gauge.value)

        backwards = [(before, after) for before, after in zip(values, values[1:])
                     if after > before + 1e-6]
        self.assertFalse(backwards, f"진행 바가 되돌아갔습니다: {backwards[:3]}")
        self.assertLessEqual(values[-1], 1.0, f"0까지 줄지 않았습니다: {values[-1]}")
        panel.close()

    def test_real_recast_refills_the_bar(self):
        """반대로 실제 재사용은 사이클을 새로 시작해 바를 다시 채워야 한다."""
        panel = PartyPanel()
        panel.timer.stop()
        start = 2000.0
        clock = {"now": start}
        with patch("magnifier.time.time", lambda: clock["now"]):
            panel.update_states({"player": {"skill": {
                "is_ready": False, "cooldown_duration": 30, "timestamp": start}}})
            panel.tick_timers()
            clock["now"] = start + 20.0
            panel.tick_timers()
            gauge = panel.widgets["player"]["skill_widgets"]["skill"]["progress"]
            self.assertLess(gauge.value, 40.0)
            # 쿨타임 도중 다시 사용: 남은 시간이 크게 늘어난다.
            panel.update_states({"player": {"skill": {
                "is_ready": False, "cooldown_duration": 30, "timestamp": clock["now"]}}})
            panel.tick_timers()
            self.assertGreater(gauge.value, 95.0)
        panel.close()

    def test_sync_sends_precise_remaining_when_available(self):
        detector = CooldownDetector()
        detector.add_slot("skill", (0, 0, 10, 10), cooldown_duration=30)
        slot = detector.slots["skill"]
        slot.cooldown_start_time = time.time() - 10.4

        precise = magnifier.sync_remaining_seconds(detector, "skill")

        self.assertAlmostEqual(precise, 19.6, delta=0.2)
        self.assertNotEqual(precise, detector.get_remaining_seconds("skill"))

    def test_skill_name_replaces_the_cd_and_rdy_labels(self):
        """RDY/CD 자리에는 사용자가 설정해 둔 스킬 이름이 상태색으로 들어간다."""
        panel = PartyPanel()
        panel.timer.stop()
        panel.update_states({
            "player": {
                "천상의 축복": {"is_ready": True, "cooldown_duration": 0, "timestamp": time.time()},
                "구원": {"is_ready": False, "cooldown_duration": 0, "timestamp": time.time()},
            }
        })
        panel.tick_timers()
        widgets = panel.widgets["player"]["skill_widgets"]

        text, colour, kind = panel._skill_status("천상의 축복", widgets["천상의 축복"], False)
        self.assertEqual((text, kind), ("천상의 축복", "name"))
        self.assertEqual(colour.name(), panel._c_ready.name())

        text, colour, kind = panel._skill_status("구원", widgets["구원"], False)
        self.assertEqual((text, kind), ("구원", "name"))
        self.assertEqual(colour.name(), panel._c_busy.name())
        self.assertNotEqual(colour.name(), panel._c_ready.name())
        panel.close()

    def test_known_seconds_still_show_the_number(self):
        panel = PartyPanel()
        panel.timer.stop()
        now = time.time()
        panel.update_states({"player": {"구원": {
            "is_ready": False, "cooldown_duration": 30, "timestamp": now}}})
        panel.tick_timers()
        widgets = panel.widgets["player"]["skill_widgets"]["구원"]

        text, _colour, kind = panel._skill_status("구원", widgets, False)

        self.assertEqual(kind, "number")
        self.assertEqual(text, "30")
        panel.close()

    def test_icons_only_mode_keeps_the_short_labels(self):
        """'아이콘만' 모드는 이름을 숨기는 설정이므로 약어를 유지한다."""
        panel = PartyPanel()
        panel.timer.stop()
        panel.display_mode = "아이콘만"
        panel.update_states({"player": {"구원": {
            "is_ready": True, "cooldown_duration": 0, "timestamp": time.time()}}})
        panel.tick_timers()
        widgets = panel.widgets["player"]["skill_widgets"]["구원"]

        text, _colour, kind = panel._skill_status("구원", widgets, False)

        self.assertEqual((text, kind), ("RDY", "label"))
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
