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
        # 번들 글리프 세트는 검증된 실측 프레임으로 학습되어 바로 쓸 수 있다.
        self.assertIn("숫자 인식 사용 중", dialog.boss_train_status.text())

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

    def test_shrinking_learned_duration_is_persisted_too(self):
        """부풀려진 학습값이 설정 파일에 영원히 남지 않아야 한다.

        예전에는 값이 커질 때만 저장했다. 그래서 20초 디버프가 28.8초로 한 번
        굳으면 재시작마다 28초부터 세는 것처럼 보였다.
        """
        self.window.on_boss_debuff_updated(bdd.DEFAULT_DEBUFF_ID, {
            "active": True, "remaining": 19.0, "source": "ocr",
            "score": 0.99, "learned_duration": 28.8,
        })
        self.assertAlmostEqual(self.window.boss_debuff_config["learned_duration"], 28.8)
        self.window.on_boss_debuff_updated(bdd.DEFAULT_DEBUFF_ID, {
            "active": True, "remaining": 19.0, "source": "ocr",
            "score": 0.99, "learned_duration": 19.0,
        })
        self.assertAlmostEqual(self.window.boss_debuff_config["learned_duration"], 19.0)
        self.window.load_settings()
        self.assertAlmostEqual(self.window.boss_debuff_config["learned_duration"], 19.0)

    def test_stored_learned_duration_does_not_inflate_the_tracker(self):
        tracker = self.window.boss_debuff_detector.tracker
        tracker.learned_duration = 12.0
        tracker.observed_max = 0.0
        self.window.boss_debuff_config["learned_duration"] = 28.8
        self.window.apply_boss_debuff_settings()
        self.assertAlmostEqual(tracker.learned_duration, 28.8)
        # 이 세션에서 숫자를 읽었다면 그 값이 우선이고 설정값이 덮어쓰지 않는다.
        tracker.observed_max = 19.0
        tracker.learned_duration = 19.0
        self.window.apply_boss_debuff_settings()
        self.assertAlmostEqual(tracker.learned_duration, 19.0)

    def test_reset_button_clears_the_learned_duration(self):
        self.window.boss_debuff_config["learned_duration"] = 28.8
        self.window.apply_boss_debuff_settings()
        dialog = magnifier.SettingsModal(self.window)
        try:
            dialog.refresh_boss_debuff_ui()
            self.assertIn("28.8", dialog.boss_learned_label.text())
            dialog.reset_boss_learned_duration()
            self.assertEqual(self.window.boss_debuff_config["learned_duration"], 0.0)
            self.assertEqual(
                self.window.boss_debuff_detector.tracker.learned_duration, 0.0)
            self.assertIn("없음", dialog.boss_learned_label.text())
            self.window.load_settings()
            self.assertEqual(self.window.boss_debuff_config["learned_duration"], 0.0)
        finally:
            dialog.deleteLater()

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
        # 숫자 인식이 가능한 상태라면 첫 순간에는 추정값을 내보내지 않는다.
        while now < 900.0 + bdd.OCR_GRACE_SEC + 0.3:
            state = detector.analyze_band(band, now)
            now += 0.1
        _app.processEvents()   # deliver the queued debuff_updated signal

        banner = self.window.party_panel.boss_banner
        self.assertBannerShown(banner)
        # 이 밴드에는 '9초' 가 찍혀 있다. 상관 정합 경로가 붙은 뒤로는 지속시간
        # 추정(10초) 대신 실제로 읽은 값이 배너에 올라간다.
        self.assertEqual(banner.value_label.text(), "9초")
        self.assertIn("OCR", banner.detail_label.text())


class BannerThemeContrastTests(unittest.TestCase):
    """모든 테마 프리셋에서 배너 글자가 읽히는지 검사한다.

    디버프 이름은 예전에 색을 지정하지 않아 앱 기본 팔레트(어두운 글자)를 그대로
    썼다. 배경이 어두운 프리셋에서는 검은 글자가 검은 배경 위에 놓여 보이지
    않았고, 반대로 남은 시간 강조색(주황)은 밝은 프리셋에서 대비가 1.6까지
    떨어졌다.
    """

    MINIMUM = 4.5

    @unittest.skipUnless(QT_READY, QT_ERROR)
    def test_every_theme_keeps_the_banner_readable(self):
        import boss_debuff_panel

        banner = boss_debuff_panel.BossDebuffBanner()
        self.addCleanup(banner.deleteLater)
        worst = ("", 99.0)
        for name, theme in magnifier.THEMES.items():
            banner.apply_theme(theme)
            background = boss_debuff_panel.parse_theme_color(theme.get("bg"), None) \
                if theme.get("bg") else None
            self.assertIsNotNone(background, f"{name}: bg 정의 없음")
            opaque = boss_debuff_panel.QColor(
                background.red(), background.green(), background.blue())
            tint = boss_debuff_panel.QColor(banner._accent_active)
            tint.setAlphaF(0.12)
            card = boss_debuff_panel.blend_over(tint, opaque)
            for label, colour in (("이름", banner._c_text),
                                  ("남은 시간", banner._accent_active)):
                ratio = boss_debuff_panel.wcag_contrast(colour, card)
                if ratio < worst[1]:
                    worst = (f"{name} {label}", ratio)
                self.assertGreaterEqual(
                    ratio, self.MINIMUM,
                    f"{name} 테마의 '{label}' 대비가 {ratio:.2f} 입니다 "
                    f"(기준 {self.MINIMUM}).")
        self.assertGreaterEqual(len(magnifier.THEMES), 6, "테마 프리셋이 줄었습니다.")

    @unittest.skipUnless(QT_READY, QT_ERROR)
    def test_theme_presets_are_complete(self):
        required = {"bg", "border", "accent", "accent_secondary", "ready",
                    "cooldown", "card_bg", "card_border", "shadow", "font_color"}
        for name, theme in magnifier.THEMES.items():
            missing = required - set(theme)
            self.assertFalse(missing, f"{name} 프리셋에 빠진 키: {missing}")


if __name__ == "__main__":
    unittest.main()
