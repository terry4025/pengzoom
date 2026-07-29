"""마스코트 인트로 애니메이션 회귀 테스트.

이 기능은 두 층으로 조용히 깨진다.

1. **자원 층** — 생성 모델이 뽑은 스프라이트 시트는 칸마다 캐릭터의 크기와
   위치가 흔들린다. `tools/build_intro_frames.py` 가 발바닥 기준선과 배 타원
   중심으로 정규화하는데, 이 정렬이 어긋나면 예외 없이 재생 중 펭구가
   덜컹거리기만 한다. 그래서 프레임 파일을 직접 재측정한다.
2. **타임라인 층** — 프레임 전환/스쿼시/페이드는 그림이 아니라 코드가 만든다.
   `state_at()` 이 순수 함수라 Qt 없이 검사할 수 있다.

위젯 층(투명 창, 건너뛰기, finished 1회 발생)은 offscreen 플랫폼에서 확인한다.
"""

import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QKeyEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import intro_animation  # noqa: E402
from build_intro_frames import alpha_bbox, belly_metrics  # noqa: E402

FRAMES_DIR = ROOT / "intro_assets" / "frames"


def qt_app():
    return QApplication.instance() or QApplication([])


class FrameAssetTests(unittest.TestCase):
    """정규화된 프레임 자체를 재측정한다."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((FRAMES_DIR / "manifest.json").read_text(encoding="utf-8"))
        cls.frames = []
        for index in range(1, intro_animation.FRAME_COUNT + 1):
            path = FRAMES_DIR / f"frame_{index}.png"
            cls.frames.append((path, np.array(Image.open(path).convert("RGBA"))))

    def test_all_frames_exist(self):
        for path, _ in self.frames:
            self.assertTrue(path.exists(), f"프레임이 없습니다: {path}")

    def test_frames_share_one_canvas(self):
        canvas = tuple(self.manifest["canvas"])
        for path, array in self.frames:
            self.assertEqual((array.shape[1], array.shape[0]), canvas,
                             f"{path.name} 의 캔버스 크기가 다릅니다.")

    def test_frames_carry_real_alpha(self):
        for path, array in self.frames:
            alpha = array[..., 3]
            self.assertEqual(int(alpha.min()), 0, f"{path.name} 에 투명 영역이 없습니다.")
            self.assertEqual(int(alpha.max()), 255, f"{path.name} 이 전부 반투명합니다.")
            # 배경 제거를 억지로 한 이미지는 경계에 흰 링이 남는다. 경계
            # 픽셀 평균이 밝으면 재생 시 캐릭터에 흰 테가 둘린다.
            edge = (alpha > 30) & (alpha < 120)
            if edge.sum() > 50:
                mean = array[..., :3][edge].mean()
                self.assertLess(mean, 200.0, f"{path.name} 경계에 흰 테가 있습니다.")

    def test_feet_baseline_is_aligned(self):
        """발바닥이 프레임마다 다르면 재생 중 캐릭터가 위아래로 튄다."""
        baselines = [alpha_bbox(array)[3] for _, array in self.frames]
        self.assertLessEqual(max(baselines) - min(baselines), 2,
                             f"발바닥 기준선이 어긋났습니다: {baselines}")

    def test_body_center_is_aligned(self):
        """배 중심이 흔들리면 좌우로 미끄러진다."""
        centers = [belly_metrics(array)["center_x"] for _, array in self.frames]
        self.assertLessEqual(max(centers) - min(centers), 2.0,
                             f"몸통 중심이 어긋났습니다: {centers}")

    def test_body_scale_is_normalized(self):
        """의도적 변형(웅크림) 프레임을 뺀 나머지는 같은 크기여야 한다."""
        widths = []
        for row, (_, array) in zip(self.manifest["frames"], self.frames):
            if not row.get("deformed"):
                widths.append(belly_metrics(array)["width"])
        spread = (max(widths) - min(widths)) / min(widths)
        self.assertLess(spread, 0.03, f"프레임 간 크기 편차가 큽니다: {widths}")

    def test_squash_pose_keeps_its_deformation(self):
        """웅크린 프레임을 배 폭으로 정규화하면 스쿼시가 사라진다.

        그 프레임은 중앙값 기준 배율을 받아야 하므로, 배가 여전히 더 넓어야 한다.
        """
        deformed = [row for row in self.manifest["frames"] if row.get("deformed")]
        if not deformed:
            self.skipTest("변형으로 분류된 프레임이 없습니다.")
        normal = [row["belly_width"] for row in self.manifest["frames"]
                  if not row.get("deformed")]
        for row in deformed:
            index = int(row["file"].split("_")[1].split(".")[0]) - 1
            measured = belly_metrics(self.frames[index][1])["width"]
            self.assertGreater(measured, max(normal) * 0.98,
                               f"{row['file']} 의 변형이 정규화에 지워졌습니다.")

    def test_normalization_never_upscales(self):
        """확대가 섞이면 프레임마다 선명도가 달라진다."""
        for row in self.manifest["frames"]:
            self.assertLessEqual(row["scale"], 1.0 + 1e-9,
                                 f"{row['file']} 이 확대되었습니다: {row['scale']}")

    def test_anchor_sits_inside_the_canvas(self):
        anchor_x, anchor_y = self.manifest["anchor"]
        canvas_w, canvas_h = self.manifest["canvas"]
        self.assertTrue(0 < anchor_x < canvas_w)
        self.assertTrue(0 < anchor_y <= canvas_h)


class TimelineTests(unittest.TestCase):
    """`state_at()` 순수 함수 검사."""

    def test_total_duration_is_short(self):
        total = intro_animation.total_duration_ms()
        self.assertGreaterEqual(total, 1500)
        self.assertLessEqual(total, 2800, "인트로가 길면 기동이 느리게 느껴진다.")

    def test_every_step_points_at_a_real_frame(self):
        for step in intro_animation.TIMELINE:
            self.assertIn(step.frame, range(1, intro_animation.FRAME_COUNT + 1))
            self.assertGreater(step.duration, 0)

    def test_manifest_and_module_agree_on_frame_count(self):
        manifest = json.loads((FRAMES_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("frame_count"), intro_animation.FRAME_COUNT)

    def test_all_poses_are_used(self):
        """12장을 받아 놓고 몇 장만 쓰면 그림값을 버리는 셈이다."""
        used = {step.frame for step in intro_animation.TIMELINE}
        self.assertEqual(used, set(range(1, intro_animation.FRAME_COUNT + 1)),
                         f"쓰이지 않는 프레임: {set(range(1, 13)) - used}")

    def test_starts_invisible_and_crouched(self):
        first = intro_animation.state_at(0)
        self.assertAlmostEqual(first.opacity, 0.0, places=6)
        self.assertLess(first.scale_y, first.scale_x, "등장 첫 프레임은 눌려 있어야 한다.")
        self.assertAlmostEqual(first.dy, 0.0, places=6, msg="등장은 땅에서 시작한다.")

    def test_jump_rises_and_lands(self):
        """점프가 실제로 궤적을 그리는지: 올라갔다가 기준선으로 돌아온다."""
        samples = [intro_animation.state_at(t).dy
                   for t in range(0, intro_animation.total_duration_ms(), 5)]
        apex = min(samples)
        self.assertLess(apex, -0.15, f"점프가 너무 얕습니다: {apex}")
        apex_index = samples.index(apex)
        self.assertAlmostEqual(samples[-1], 0.0, delta=0.05)
        # 정점 이후 착지까지 다시 내려와야 한다.
        self.assertGreater(max(samples[apex_index:]), -0.02)

    def test_landing_squashes_the_body(self):
        """착지 순간에 세로가 눌려야 무게가 느껴진다."""
        squashes = [intro_animation.state_at(t).scale_y / intro_animation.state_at(t).scale_x
                    for t in range(0, intro_animation.total_duration_ms(), 5)]
        self.assertLess(min(squashes), 0.85, "스쿼시가 없습니다.")
        self.assertGreater(max(squashes), 1.05, "스트레치가 없습니다.")

    def test_wave_tilts_the_body(self):
        rotations = [intro_animation.state_at(t).rotation
                     for t in range(0, intro_animation.total_duration_ms(), 5)]
        self.assertLess(min(rotations), -2.0, "손 들 때 기울기가 없습니다.")
        self.assertGreater(max(rotations), 2.0, "인사 기울기가 없습니다.")

    def test_ends_transparent_and_done(self):
        total = intro_animation.total_duration_ms()
        last = intro_animation.state_at(total)
        self.assertTrue(last.done)
        self.assertAlmostEqual(last.opacity, 0.0, places=6)
        # 끝난 뒤 더 흘러도 같은 상태를 유지한다(타이머가 늦게 들어와도 안전).
        self.assertEqual(intro_animation.state_at(total + 5000), last)

    def test_negative_elapsed_is_clamped(self):
        self.assertEqual(intro_animation.state_at(-100), intro_animation.state_at(0))

    def test_wave_alternates_through_three_wing_angles(self):
        """웨이브는 45°(5) → 최대(6) → 손끝 꺾임(7) 순서로 두 번 지나간다."""
        frames = [step.frame for step in intro_animation.TIMELINE]
        self.assertEqual(frames.count(6), 2, "날개 최대 프레임이 두 번 나와야 한다.")
        self.assertEqual(frames.count(7), 2)
        for index, frame in enumerate(frames):
            if frame == 6:
                self.assertIn(frames[index - 1], (5, 7))
                self.assertEqual(frames[index + 1], 7)

    def test_blink_passes_through_the_half_closed_pose(self):
        """눈은 반쯤 감은 프레임을 거쳐야 깜빡임으로 보인다."""
        frames = [step.frame for step in intro_animation.TIMELINE]
        closed = frames.index(9)
        self.assertEqual(frames[closed - 1], 8)
        self.assertEqual(frames[closed + 1], 8)

    def test_opacity_and_scale_stay_in_range(self):
        total = intro_animation.total_duration_ms()
        peak = intro_animation.max_scale()
        for elapsed in range(0, total + 1, 5):
            state = intro_animation.state_at(elapsed)
            self.assertGreaterEqual(state.opacity, 0.0)
            self.assertLessEqual(state.opacity, 1.0)
            self.assertLessEqual(max(state.scale_x, state.scale_y), peak + 1e-9)

    def test_frame_sequence_is_continuous_in_time(self):
        """단계 경계에서 프레임이 누락되지 않는지 확인한다.

        시간을 훑어 얻은 프레임 순서가 타임라인 선언(연속 중복 제거)과 같아야
        한다. 어느 단계의 길이가 0에 가깝게 줄면 그 프레임은 화면에 나타나지
        않는데, 선언만 보면 그 사실이 드러나지 않는다.
        """
        declared = []
        for step in intro_animation.TIMELINE:
            if not declared or declared[-1] != step.frame:
                declared.append(step.frame)

        seen = []
        for elapsed in range(0, intro_animation.total_duration_ms(), 5):
            frame = intro_animation.state_at(elapsed).frame
            if not seen or seen[-1] != frame:
                seen.append(frame)

        self.assertEqual(seen, declared)


class SettingTests(unittest.TestCase):
    """인트로는 창이 만들어지기 전에 설정을 직접 읽는다."""

    def test_missing_config_defaults_to_enabled(self):
        self.assertTrue(intro_animation.intro_enabled(ROOT / "no_such_config.json"))

    def test_broken_config_defaults_to_enabled(self):
        path = ROOT / "_test_broken_config.json"
        path.write_text("{ not json", encoding="utf-8")
        self.addCleanup(path.unlink)
        self.assertTrue(intro_animation.intro_enabled(path))

    def test_flag_is_honoured(self):
        path = ROOT / "_test_intro_config.json"
        self.addCleanup(path.unlink)
        path.write_text(json.dumps({"show_intro": False}), encoding="utf-8")
        self.assertFalse(intro_animation.intro_enabled(path))
        path.write_text(json.dumps({"show_intro": True}), encoding="utf-8")
        self.assertTrue(intro_animation.intro_enabled(path))

    def test_settings_modal_persists_the_flag(self):
        source = (ROOT / "magnifier.py").read_text(encoding="utf-8")
        self.assertIn("self.chk_show_intro", source)
        self.assertIn("'show_intro': bool(getattr(self, 'show_intro', True))", source)
        self.assertIn("data.get('show_intro', True)", source)


class SplashWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = qt_app()
        self.splash = intro_animation.create_intro()
        self.assertIsNotNone(self.splash, "인트로 자원을 찾지 못했습니다.")
        self.addCleanup(self.splash.close)

    def test_window_is_frameless_translucent_and_on_top(self):
        flags = self.splash.windowFlags()
        self.assertTrue(flags & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(flags & Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(
            self.splash.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))

    def test_window_has_room_for_the_jump_and_overshoot(self):
        peak = intro_animation.max_scale()
        rise = intro_animation.max_rise()
        self.assertGreaterEqual(self.splash.width(),
                                self.splash.display_w * peak)
        self.assertGreaterEqual(self.splash.height(),
                                self.splash.display_h * (peak + rise))
        # 기준선이 창 안에 있고, 아래로 처지는 동작도 잘리지 않는다.
        self.assertLess(self.splash.baseline_y(), self.splash.height())
        self.assertGreater(self.splash.baseline_y(),
                           self.splash.display_h * (peak + rise) - 1)

    def test_art_never_leaves_the_window(self):
        """점프 정점과 최대 배율에서도 그림이 창 밖으로 나가지 않아야 한다."""
        canvas_w, canvas_h = self.splash.canvas_size
        for elapsed in range(0, intro_animation.total_duration_ms() + 1, 10):
            state = intro_animation.state_at(elapsed)
            base = self.splash.base_scale
            top = (self.splash.baseline_y() + state.dy * self.splash.display_h
                   - self.splash.anchor[1] * base * state.scale_y)
            half = self.splash.anchor[0] * base * state.scale_x
            self.assertGreaterEqual(top, -1.0, f"{elapsed}ms 에서 위가 잘립니다.")
            self.assertLessEqual(self.splash.width() / 2.0 + half,
                                 self.splash.width() + 1.0,
                                 f"{elapsed}ms 에서 옆이 잘립니다.")

    def test_never_upscales_the_source_art(self):
        """물리 픽셀 기준으로도 원본을 확대하지 않아야 선이 흐려지지 않는다."""
        effective = (self.splash.base_scale
                     * intro_animation.max_scale()
                     * max(1.0, self.splash.device_ratio))
        self.assertLessEqual(effective, 1.0 + 1e-9)

    def test_frames_load_as_pixmaps(self):
        for index in range(1, intro_animation.FRAME_COUNT + 1):
            pixmap = self.splash.frame_pixmap(index)
            self.assertIsNotNone(pixmap, f"frame_{index}.png 를 읽지 못했습니다.")
            self.assertFalse(pixmap.isNull())

    def test_missing_frame_is_tolerated(self):
        splash = intro_animation.IntroSplash(root=ROOT / "no_such_dir")
        self.addCleanup(splash.close)
        self.assertIsNone(splash.frame_pixmap(1))

    def test_create_intro_returns_none_without_assets(self):
        self.assertIsNone(intro_animation.create_intro(root=ROOT / "no_such_dir"))

    def test_finished_fires_once_at_the_end(self):
        calls = []
        self.splash.finished.connect(lambda: calls.append(1))
        self.splash.render_at(intro_animation.total_duration_ms() + 100)
        self.splash.render_at(intro_animation.total_duration_ms() + 500)
        self.assertEqual(calls, [1])
        self.assertFalse(self.splash.isVisible())

    def test_skip_fires_finished_once(self):
        calls = []
        self.splash.finished.connect(lambda: calls.append(1))
        self.splash.skip()
        self.splash.skip()
        self.assertEqual(calls, [1])

    def test_escape_skips(self):
        calls = []
        self.splash.finished.connect(lambda: calls.append(1))
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape,
                          Qt.KeyboardModifier.NoModifier)
        self.splash.keyPressEvent(event)
        self.assertEqual(calls, [1])

    def test_paints_without_error_across_the_timeline(self):
        # offscreen 에서도 paintEvent 를 실제로 태워 변환 계산이 터지지 않는지 본다.
        from PyQt6.QtGui import QPixmap

        target = QPixmap(self.splash.size())
        for elapsed in range(0, intro_animation.total_duration_ms() + 1, 40):
            self.splash._state = intro_animation.state_at(elapsed)
            target.fill(Qt.GlobalColor.transparent)
            self.splash.render(target)

    def test_launch_wiring_survives_the_intro_window_closing(self):
        """인트로가 닫힐 때 본 창이 없으면 앱이 종료되므로 그 가드를 검사한다."""
        source = (ROOT / "magnifier.py").read_text(encoding="utf-8")
        self.assertIn("app.setQuitOnLastWindowClosed(False)", source)
        self.assertIn("intro.finished.connect(launch_main_window)", source)
        self.assertIn("app.setQuitOnLastWindowClosed(True)", source)


if __name__ == "__main__":
    unittest.main()
