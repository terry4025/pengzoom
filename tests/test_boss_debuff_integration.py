"""Integration checks for the boss debuff wiring inside the main window.

The whole process is redirected to a throwaway ``APPDATA`` before magnifier is
imported: ``MagnifierWindow`` auto-saves its config (including from ``atexit``),
and a test must never overwrite the real user settings.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_ISOLATED_APPDATA = tempfile.mkdtemp(prefix="pengzoom_test_")
os.environ["APPDATA"] = _ISOLATED_APPDATA
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import boss_debuff_detector as bdd  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication  # noqa: E402
    import magnifier  # noqa: E402
    QT_READY = True
    QT_ERROR = ""
except Exception as exc:  # pragma: no cover
    QT_READY = False
    QT_ERROR = str(exc)

ROOT = Path(__file__).resolve().parents[1]
BAND_A = ROOT / "tests" / "fixtures" / "boss_debuff" / "band_1080p_9s_a.png"
DEBUFF_KEY = f"_bossdebuff:{bdd.DEFAULT_DEBUFF_ID}"

_app = None


def setUpModule():
    global _app
    if QT_READY:
        _app = QApplication.instance() or QApplication([])


class FakeClient:
    def __init__(self):
        self.updates = []

    def send_update(self, skill_name, is_ready, cooldown_duration=0):
        self.updates.append((skill_name, is_ready, cooldown_duration))


@unittest.skipUnless(QT_READY, f"PyQt6 offscreen unavailable: {QT_ERROR}")
class BossDebuffWiringTests(unittest.TestCase):
    def setUp(self):
        # Every test starts from factory defaults: the party panel saves the
        # window config whenever it closes, so state would leak between tests.
        config = Path(_ISOLATED_APPDATA) / "PengZoom" / "config.json"
        if config.exists():
            config.unlink()
        self.window = magnifier.MagnifierWindow()
        self.addCleanup(self.cleanup)

    def assertBannerShown(self, banner, shown=True):
        # The party panel window itself is hidden in tests, so isVisible() is
        # always False; isHidden() reflects the explicit show/hide decision.
        self.assertEqual(not banner.isHidden(), shown)

    def cleanup(self):
        try:
            self.window.boss_debuff_detector.stop_detection()
        except Exception:
            pass
        try:
            self.window.detector.stop_detection()
        except Exception:
            pass
        self.window.party_panel.close()
        self.window.close()

    # -- settings UI --------------------------------------------------------
    def test_settings_modal_exposes_the_boss_debuff_tab(self):
        dialog = magnifier.SettingsModal(self.window)
        self.addCleanup(dialog.close)
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn("보스 디버프", titles)
        self.assertEqual(dialog.boss_region_label.text(), "영역 미지정")
        # The seed glyph set is intentionally not trusted yet.
        self.assertIn("표본 부족", dialog.boss_train_status.text())

    def test_region_capture_enables_the_detector(self):
        self.window.on_boss_debuff_region_captured(560, 130, 780, 80, None)
        self.assertEqual(self.window.boss_debuff_config["region"], [560, 130, 780, 80])
        self.assertEqual(self.window.boss_debuff_detector.region, [560, 130, 780, 80])
        # Region alone must not start scanning; the toggle still governs it.
        self.assertFalse(self.window.boss_debuff_detector.enabled)

        self.window.boss_debuff_config["enabled"] = True
        self.window.apply_boss_debuff_settings()
        self.assertTrue(self.window.boss_debuff_detector.enabled)
        self.assertBannerShown(self.window.party_panel.boss_banner)

    def test_too_small_region_is_rejected(self):
        self.window.on_boss_debuff_region_captured(10, 10, 12, 8, None)
        self.assertIsNone(self.window.boss_debuff_config["region"])

    def test_config_survives_save_and_load(self):
        self.window.boss_debuff_config.update({
            "enabled": True, "region": [100, 200, 640, 70],
            "threshold": 0.86, "duration": 12.5, "collect_samples": True,
        })
        self.window.save_settings()
        self.window.load_settings()
        config = self.window.boss_debuff_config
        self.assertTrue(config["enabled"])
        self.assertEqual(config["region"], [100, 200, 640, 70])
        self.assertAlmostEqual(config["threshold"], 0.86)
        self.assertAlmostEqual(config["duration"], 12.5)
        self.assertTrue(config["collect_samples"])

    # -- party panel --------------------------------------------------------
    def test_banner_shows_the_real_ingame_icon(self):
        banner = self.window.party_panel.boss_banner
        pixmap = banner.icon_label.pixmap()
        self.assertFalse(pixmap.isNull(), "번들 아이콘을 불러오지 못했습니다 (한글 경로 확인).")
        self.assertGreater(pixmap.width(), 8)

    def test_learned_duration_is_persisted_for_the_next_session(self):
        self.window.on_boss_debuff_updated(bdd.DEFAULT_DEBUFF_ID, {
            "active": True, "remaining": 9.0, "source": "anchor",
            "score": 0.99, "learned_duration": 12.3,
        })
        self.assertAlmostEqual(self.window.boss_debuff_config["learned_duration"], 12.3)
        self.window.load_settings()
        self.assertAlmostEqual(self.window.boss_debuff_config["learned_duration"], 12.3)
        self.window.apply_boss_debuff_settings()
        self.assertAlmostEqual(
            self.window.boss_debuff_detector.tracker.learned_duration, 12.3
        )

    def test_local_state_reaches_the_party_banner(self):
        self.window.on_boss_debuff_updated(bdd.DEFAULT_DEBUFF_ID, {
            "active": True, "remaining": 9.0, "source": "anchor", "score": 0.99,
        })
        banner = self.window.party_panel.boss_banner
        self.assertBannerShown(banner)
        self.assertEqual(banner.value_label.text(), "9초")
        self.assertIn("자동 보정", banner.detail_label.text())

        self.window.on_boss_debuff_updated(bdd.DEFAULT_DEBUFF_ID, {
            "active": False, "remaining": None, "source": "", "score": 0.2,
        })
        self.assertEqual(banner.value_label.text(), "OFF")

    def test_active_without_seconds_shows_on_instead_of_a_guess(self):
        self.window.on_boss_debuff_updated(bdd.DEFAULT_DEBUFF_ID, {
            "active": True, "remaining": None, "source": "unknown", "score": 0.99,
        })
        banner = self.window.party_panel.boss_banner
        self.assertEqual(banner.value_label.text(), "ON")
        self.assertIn("확인 불가", banner.detail_label.text())

    def test_party_report_is_rendered_without_local_detection(self):
        panel = self.window.party_panel
        panel.update_states({
            "펭도리": {
                "_class": "홀리나이트",
                DEBUFF_KEY: {"is_ready": True, "cooldown_duration": 7, "timestamp": time.time()},
            }
        })
        banner = panel.boss_banner
        self.assertBannerShown(banner)
        self.assertEqual(banner.value_label.text(), "7초")
        self.assertIn("펭도리", banner.detail_label.text())
        # The report must never be drawn as one of the player's skill badges.
        self.assertNotIn(DEBUFF_KEY, panel.widgets["펭도리"]["skill_widgets"])

    # -- party broadcast ----------------------------------------------------
    def test_broadcast_uses_the_prefixed_party_channel(self):
        client = FakeClient()
        self.window.client = client
        self.window.client_running = True
        self.window.boss_debuff_state = {"active": True, "remaining": 8.2, "source": "anchor"}
        self.window.broadcast_boss_debuff(force=True)
        self.assertEqual(client.updates, [(DEBUFF_KEY, True, 9)])
        self.assertTrue(DEBUFF_KEY.startswith("_"))

    def test_broadcast_is_skipped_when_sharing_is_off(self):
        client = FakeClient()
        self.window.client = client
        self.window.client_running = True
        self.window.boss_debuff_config["share_with_party"] = False
        self.window.boss_debuff_state = {"active": True, "remaining": 3.0, "source": "ocr"}
        self.window.broadcast_boss_debuff(force=True)
        self.assertEqual(client.updates, [])

    # -- end to end ---------------------------------------------------------
    def test_real_band_capture_flows_into_the_banner(self):
        band = bdd.read_image(BAND_A)
        self.assertIsNotNone(band)
        detector = self.window.boss_debuff_detector
        self.window.boss_debuff_config.update({
            "enabled": True, "region": [560, 130, 780, 80], "duration": 10.0,
        })
        self.window.apply_boss_debuff_settings()
        detector.stop_detection()  # drive the frames deterministically instead

        now = 900.0
        for _ in range(bdd.ACTIVATE_FRAMES + 1):
            state = detector.analyze_band(band, now)
            now += 0.1
        self.assertTrue(state["active"])
        _app.processEvents()   # deliver the queued debuff_updated signal

        banner = self.window.party_panel.boss_banner
        self.assertBannerShown(banner)
        self.assertEqual(banner.value_label.text(), "10초")
        self.assertIn("추정", banner.detail_label.text())


if __name__ == "__main__":
    unittest.main()
