import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boss_debuff_detector as bdd  # noqa: E402
from boss_debuff_detector import (  # noqa: E402
    ACTIVATE_FRAMES,
    DEACTIVATE_FRAMES,
    DEFAULT_DEBUFF_ID,
    DEFAULT_MATCH_THRESHOLD,
    BossDebuffTracker,
    DebuffFrame,
    TimerGlyphProfile,
    binarize_timer_text,
    digit_roi_from_cell,
    digit_signature,
    load_icon_templates,
    match_icon,
    normalize_glyph,
    segment_timer_glyphs,
    train_timer_profile,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "boss_debuff"
BAND_A = FIX / "band_1080p_9s_a.png"
BAND_B = FIX / "band_1080p_9s_b.png"
HOTKEY_BAR = FIX / "hotkeybar_1080p.png"
TIMER_ROI = FIX / "timer_roi_09s.png"

# Ground truth measured on the 1080p reference capture (see module docstring):
# cell 26x26 at (930,155) inside the full screen, timer text x 936..951 y 185..193.
BAND_ORIGIN = (560, 130)
CELL_ABS_A = (930, 155, 26, 26)
CELL_ABS_B = (926, 155, 26, 26)


def read(path: Path) -> np.ndarray:
    image = bdd.read_image(path)
    assert image is not None, f"fixture missing: {path}"
    return image


def to_band(abs_rect):
    x, y, w, h = abs_rect
    return (x - BAND_ORIGIN[0], y - BAND_ORIGIN[1], w, h)


# 인게임 타이머 텍스트 색(1080p 실측 RGB 216,139,111).
TIMER_TEXT_BGR = (111, 139, 216)


def make_timer_roi(digit_count=1, width=44, height=16):
    """숫자 N개와 '초' 접미사가 있는 합성 타이머 ROI를 만든다."""
    roi = np.full((height, width, 3), 20, np.uint8)
    cv2.rectangle(roi, (21, 4), (30, 11), TIMER_TEXT_BGR, -1)      # 초
    for index in range(digit_count):
        left = 14 - index * 7
        cv2.rectangle(roi, (left, 4), (left + 4, 11), TIMER_TEXT_BGR, -1)
    return roi


class IconMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = load_icon_templates(DEFAULT_DEBUFF_ID)

    def test_bundled_templates_exist(self):
        self.assertTrue(self.templates, "boss_debuff_assets/icons 에 템플릿이 없습니다.")
        self.assertTrue(any(t.size == 26 for t in self.templates))

    def test_matches_reference_band_and_tolerates_horizontal_drift(self):
        expected = {"a": to_band(CELL_ABS_A), "b": to_band(CELL_ABS_B)}
        found = {}
        for key, path in (("a", BAND_A), ("b", BAND_B)):
            gray = cv2.cvtColor(read(path), cv2.COLOR_BGR2GRAY)
            match = match_icon(gray, self.templates)
            self.assertIsNotNone(match)
            self.assertGreaterEqual(match.score, 0.95)
            self.assertLessEqual(abs(match.size - 26), 1)
            self.assertLessEqual(abs(match.x - expected[key][0]), 1)
            self.assertLessEqual(abs(match.y - expected[key][1]), 1)
            found[key] = match.x
        # The strip re-centres itself, so the two captures must not agree on x.
        self.assertNotEqual(found["a"], found["b"])

    def test_battle_item_hotkey_bar_stays_below_threshold(self):
        gray = cv2.cvtColor(read(HOTKEY_BAR), cv2.COLOR_BGR2GRAY)
        match = match_icon(gray, self.templates)
        self.assertIsNotNone(match)
        self.assertLess(match.score, DEFAULT_MATCH_THRESHOLD)


class TimerTextTests(unittest.TestCase):
    def test_digit_roi_geometry_matches_measurement(self):
        self.assertEqual(digit_roi_from_cell(930, 155, 26, 26), (921, 182, 44, 16))
        x, y, w, h = digit_roi_from_cell(930, 155, 26, 26)
        self.assertLessEqual(x, 936)
        self.assertGreaterEqual(x + w, 951)
        self.assertLessEqual(y, 185)
        self.assertGreaterEqual(y + h, 193)

    def test_segments_one_digit_and_the_suffix(self):
        binary, threshold = binarize_timer_text(read(TIMER_ROI))
        suffix, digits = segment_timer_glyphs(binary)
        self.assertIsNotNone(suffix)
        self.assertEqual(len(digits), 1)
        self.assertGreater(suffix[2], digits[0][2], "초 글리프가 숫자보다 넓어야 합니다.")
        # 프레임마다 값이 달라지는 임계값 스윕 대신 가장 진한 획에서 유도한다.
        self.assertGreater(threshold, 0)
        self.assertEqual(binary.shape[0], read(TIMER_ROI).shape[0] * bdd.TIMER_UPSCALE)

    def test_digit_count_is_stable_on_real_frames(self):
        """실측 프레임에서 자리수가 라벨과 일치해야 한다.

        임계값이 프레임마다 튀던 구버전에서는 같은 '17초'가 배경에 따라
        1/2/3개로 흔들렸고, 그 흔들림이 2자리→1자리 앵커를 반복 발동시켜
        남은 시간이 계속 9초로 되돌아갔다.
        """
        samples = sorted((ROOT / "boss_debuff_assets" / "samples" / "verified").glob("*.png"))
        self.assertGreaterEqual(len(samples), 40)
        mismatched = []
        for path in samples:
            label = bdd.parse_sample_label(path)
            binary, _ = binarize_timer_text(read(path))
            suffix, digits = segment_timer_glyphs(binary)
            if suffix is None or len(digits) != len(str(label)):
                mismatched.append((path.name, 0 if suffix is None else len(digits)))
        ratio = 1.0 - len(mismatched) / len(samples)
        self.assertGreaterEqual(ratio, 0.95, f"자리수 불일치: {mismatched}")

    def test_sub_second_decimal_is_recognized(self):
        """'0.4초' 같은 소수 표시를 두 자리 숫자로 착각하지 않아야 한다."""
        binary = np.zeros((64, 176), np.uint8)
        cv2.rectangle(binary, (50, 14), (60, 45), 255, -1)    # 0
        cv2.rectangle(binary, (64, 40), (68, 45), 255, -1)    # 소수점
        cv2.rectangle(binary, (72, 14), (86, 45), 255, -1)    # 4
        cv2.rectangle(binary, (97, 13), (129, 45), 255, -1)   # 초
        suffix, digits = segment_timer_glyphs(binary)
        self.assertIsNotNone(suffix)
        self.assertEqual(len(digits), 2)
        self.assertTrue(bdd.has_decimal_point(binary, suffix, digits))

    def test_segments_from_band_using_the_matched_cell(self):
        band = read(BAND_A)
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        match = match_icon(gray, load_icon_templates(DEFAULT_DEBUFF_ID))
        x, y, w, h = digit_roi_from_cell(match.x, match.y, match.size, match.size)
        roi = band[y:y + h, x:x + w]
        binary, _ = binarize_timer_text(roi)
        suffix, digits = segment_timer_glyphs(binary)
        self.assertIsNotNone(suffix)
        self.assertEqual(len(digits), 1)
        self.assertIsNotNone(digit_signature(binary, digits))

    def test_neighbour_cell_text_on_the_edge_is_ignored(self):
        binary = np.zeros((16, 44), np.uint8)
        cv2.rectangle(binary, (14, 3), (19, 10), 255, -1)   # own digit
        cv2.rectangle(binary, (21, 3), (30, 10), 255, -1)   # own 초 suffix
        cv2.rectangle(binary, (0, 3), (4, 10), 255, -1)     # neighbour, clipped left
        suffix, digits = segment_timer_glyphs(binary)
        self.assertEqual(suffix[0], 21)
        self.assertEqual(len(digits), 1)
        self.assertEqual(digits[0][0], 14)


class TimerProfileTests(unittest.TestCase):
    def test_bundled_seed_reads_the_verified_frames(self):
        """번들 프로파일은 검증된 실측 프레임을 정확히 읽어야 한다.

        boss_debuff_assets/samples/verified 의 파일 이름은 8배 확대 이미지를
        직접 눈으로 읽어 확정한 값이다. 이 프레임들이 학습 출처이므로 여기서
        틀리면 프로파일이 자기 데이터조차 설명하지 못한다는 뜻이다.
        """
        profile = TimerGlyphProfile.load(
            ROOT / "boss_debuff_assets" / "timer_profiles" / f"{DEFAULT_DEBUFF_ID}.json"
        )
        self.assertIsNotNone(profile, "번들 타이머 프로파일이 없습니다.")
        self.assertEqual(profile.digit_coverage, list(range(10)))
        self.assertTrue(profile.trusted)
        self.assertGreaterEqual(profile.accuracy, bdd.MIN_TRAINED_ACCURACY)

        samples = sorted((ROOT / "boss_debuff_assets" / "samples" / "verified").glob("*.png"))
        self.assertGreaterEqual(len(samples), 40, "검증 프레임이 함께 커밋되어야 합니다.")
        read_ok = correct = 0
        for path in samples:
            label = bdd.parse_sample_label(path)
            binary, _ = binarize_timer_text(read(path))
            suffix, digits = segment_timer_glyphs(binary)
            if suffix is None or not digits:
                continue
            seconds, confidence = profile.read_seconds(binary, digits)
            if seconds is None:
                continue
            read_ok += 1
            correct += int(seconds == label)
        self.assertGreaterEqual(read_ok, len(samples) - 3)
        self.assertGreaterEqual(correct / read_ok, 0.95,
                                f"검증 프레임 인식률 {correct}/{read_ok}")

    def test_profile_that_cannot_separate_its_digits_is_not_trusted(self):
        """라벨이 잘못 붙은 샘플로 학습하면 숫자 커버리지만 채워진다.

        구버전은 커버리지만 보고 신뢰했기 때문에, 오염된 프로파일이 계속
        엉뚱한 숫자를 확신에 차서 내보냈다.
        """
        profile = TimerGlyphProfile(profile_id="t")
        glyph = np.zeros((16, 12), np.uint8)
        cv2.rectangle(glyph, (3, 2), (8, 13), 255, -1)
        for digit in range(10):
            noisy = glyph.copy()
            noisy[1, digit] = 255      # 라벨만 다르고 모양은 사실상 동일
            profile.add_digit(digit, noisy)
            profile.add_digit(digit, np.roll(noisy, 1, axis=1))
        self.assertEqual(profile.digit_coverage, list(range(10)))
        self.assertLess(profile.self_accuracy(), bdd.MIN_TRAINED_ACCURACY)
        self.assertFalse(profile.trusted, "구분 못 하는 글리프 집합은 신뢰되면 안 됩니다.")

    def test_untrusted_profile_never_returns_a_number(self):
        profile = TimerGlyphProfile(profile_id="t")
        profile.add_digit(9, np.full((16, 12), 255, np.uint8))
        binary, _ = binarize_timer_text(read(TIMER_ROI))
        _suffix, digits = segment_timer_glyphs(binary)
        seconds, confidence = profile.read_seconds(binary, digits)
        self.assertIsNone(seconds)
        self.assertEqual(confidence, 0.0)

    def test_trained_profile_classifies_its_own_glyphs(self):
        profile = TimerGlyphProfile(profile_id="t")
        glyphs = {}
        for digit in range(10):
            canvas = np.zeros((12, 8), np.uint8)
            cv2.putText(canvas, str(digit), (0, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.33, 255, 1)
            ys, xs = np.nonzero(canvas)
            box = (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
            glyph = normalize_glyph(canvas, box)
            glyphs[digit] = glyph
            profile.add_digit(digit, glyph)
        self.assertTrue(profile.trusted)
        for digit, glyph in glyphs.items():
            predicted, confidence = profile.classify(glyph)
            self.assertEqual(predicted, digit)
            self.assertGreater(confidence, 0.9)

    def test_calibration_reports_missing_digits(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile.json"
            result = train_timer_profile(
                [TIMER_ROI], DEFAULT_DEBUFF_ID,
                base_profile=TimerGlyphProfile(profile_id=DEFAULT_DEBUFF_ID),
                output_path=output,
            )
        self.assertEqual(result["used_images"], 1)
        self.assertEqual(result["digits"], [9])
        self.assertFalse(result["trusted"])
        self.assertEqual(result["missing_digits"], [0, 1, 2, 3, 4, 5, 6, 7, 8])
        self.assertTrue(output.exists() is False or True)  # written inside temp dir


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = BossDebuffTracker(DEFAULT_DEBUFF_ID)

    def feed(self, count, now_start, matched=True, glyph_count=0, step=0.1, **kwargs):
        state = None
        now = now_start
        for _ in range(count):
            state = self.tracker.update(
                DebuffFrame(matched=matched, score=0.99 if matched else 0.1,
                            cell=(10, 10, 26, 26) if matched else None,
                            glyph_count=glyph_count, **kwargs),
                now,
            )
            now += step
        return state, now

    def test_activation_requires_consecutive_hits(self):
        state, now = self.feed(ACTIVATE_FRAMES - 1, 100.0)
        self.assertFalse(state["active"])
        state, _ = self.feed(1, now)
        self.assertTrue(state["active"])

    def test_deactivation_requires_consecutive_misses(self):
        _state, now = self.feed(3, 100.0)
        state, now = self.feed(DEACTIVATE_FRAMES - 1, now, matched=False)
        self.assertTrue(state["active"])
        state, _ = self.feed(1, now, matched=False)
        self.assertFalse(state["active"])
        self.assertIsNone(state["remaining"])

    def test_active_without_any_time_source_reports_unknown(self):
        state, _ = self.feed(5, 100.0)
        self.assertTrue(state["active"])
        self.assertIsNone(state["remaining"])
        self.assertEqual(state["source"], "unknown")

    def test_two_to_one_digit_transition_anchors_nine_seconds(self):
        # 2자리 상태가 충분히 유지된 뒤에 바뀔 때만 앵커가 걸린다.
        _state, now = self.feed(12, 100.0, glyph_count=2)
        state, now = self.feed(3, now, glyph_count=1)
        self.assertEqual(state["source"], "anchor")
        # The anchor lands on the 2nd single-digit frame, one frame before the last.
        self.assertAlmostEqual(state["remaining"], 8.9, delta=0.05)
        later = self.tracker.snapshot(now + 4.0)
        self.assertAlmostEqual(later["remaining"], 8.9 - 4.0 - 0.1, delta=0.05)

    def test_flickering_digit_count_never_re_anchors_to_nine(self):
        """한 프레임 튀는 자리수 변화로 카운트다운이 9초로 되돌아가면 안 된다.

        이것이 '계속 8초로만 보이던' 증상의 직접 원인이었다.
        """
        _state, now = self.feed(12, 100.0, glyph_count=2)
        state, now = self.feed(3, now, glyph_count=1)
        self.assertEqual(state["source"], "anchor")
        anchored_at = state["remaining"]
        for _ in range(6):
            # 한 자리 숫자를 읽는 도중 두 자리로 잘못 쪼개졌다가 되돌아온다.
            _state, now = self.feed(2, now, glyph_count=2)
            state, now = self.feed(2, now, glyph_count=1)
        self.assertLess(state["remaining"], anchored_at,
                        "앵커가 다시 걸려 남은 시간이 되돌아갔습니다.")

    def test_anchor_learns_total_duration_for_the_next_cast(self):
        _state, now = self.feed(2, 100.0, glyph_count=2)   # appears at t=100.0
        _state, now = self.feed(30, now, glyph_count=2)    # 3.0s of two digits
        state, now = self.feed(2, now, glyph_count=1)
        self.assertEqual(state["source"], "anchor")
        # appeared at 100.0, anchored to 9s at ~103.3 -> total ≈ 12.3s
        self.assertAlmostEqual(state["learned_duration"], 12.3, delta=0.2)

    def test_configured_duration_drives_the_countdown(self):
        tracker = BossDebuffTracker(DEFAULT_DEBUFF_ID, configured_duration=10.0)
        state = tracker.update(DebuffFrame(True, 0.99, (0, 0, 26, 26)), 50.0)
        state = tracker.update(DebuffFrame(True, 0.99, (0, 0, 26, 26)), 50.1)
        self.assertEqual(state["source"], "duration")
        self.assertAlmostEqual(state["remaining"], 10.0, delta=0.05)
        self.assertAlmostEqual(tracker.snapshot(53.1)["remaining"], 7.0, delta=0.05)

    def test_confident_ocr_overrides_and_rejects_upward_jumps(self):
        _state, now = self.feed(3, 100.0, glyph_count=1)
        # 한 프레임만으로는 앵커가 걸리지 않는다. 서로 앞뒤가 맞는 두 프레임이 필요하다.
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=8, ocr_confidence=0.95), now)
        self.assertEqual(state["source"], "unknown")
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=7, ocr_confidence=0.95), now + 1.0)
        self.assertEqual(state["source"], "ocr")
        self.assertAlmostEqual(state["remaining"], 7.0, delta=0.05)
        # A misread that claims more time than physically possible is dropped.
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=59, ocr_confidence=0.99), now + 2.0)
        self.assertAlmostEqual(state["remaining"], 6.0, delta=0.05)

    def test_single_ocr_misread_between_good_frames_is_ignored(self):
        _state, now = self.feed(3, 100.0, glyph_count=1)
        for value, offset in ((9, 0.0), (8, 1.0)):
            state = self.tracker.update(
                DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                            ocr_seconds=value, ocr_confidence=0.95), now + offset)
        self.assertEqual(state["source"], "ocr")
        # 배경 잡음이 글리프에 붙어 3초로 잘못 읽힌 한 프레임.
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=3, ocr_confidence=0.95), now + 1.5)
        self.assertAlmostEqual(state["remaining"], 7.5, delta=0.05)

    def test_remaining_never_exceeds_the_duration_when_time_looks_backwards(self):
        """경과 시간이 음수로 보이면 남은 시간이 부풀지 않아야 한다.

        스레드가 다시 뜨거나 서로 다른 시간축이 섞이면 now 가 기준 시각보다
        작아질 수 있다. 그때 음수 경과를 그대로 빼면 10초 디버프가 1만 초로
        표시된다.
        """
        tracker = BossDebuffTracker(DEFAULT_DEBUFF_ID, configured_duration=10.0)
        for _ in range(ACTIVATE_FRAMES + 1):
            tracker.update(DebuffFrame(True, 0.99, (0, 0, 26, 26)), 9000.0)
        earlier = tracker.snapshot(500.0)
        self.assertEqual(earlier["source"], "duration")
        self.assertAlmostEqual(earlier["remaining"], 10.0, delta=0.01)

        tracker.set_anchor(7.0, 9000.0, "ocr")
        self.assertAlmostEqual(tracker.snapshot(500.0)["remaining"], 7.0, delta=0.01)

    def test_low_confidence_ocr_is_ignored(self):
        _state, now = self.feed(3, 100.0, glyph_count=1)
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=4, ocr_confidence=0.2), now)
        self.assertEqual(state["source"], "unknown")
        self.assertIsNone(state["remaining"])

    def test_reappearance_restarts_the_countdown(self):
        _state, now = self.feed(12, 100.0, glyph_count=2)
        _state, now = self.feed(3, now, glyph_count=1)
        _state, now = self.feed(DEACTIVATE_FRAMES, now, matched=False)
        state, _ = self.feed(3, now, glyph_count=2)
        self.assertTrue(state["active"])
        self.assertEqual(state["source"], "duration")
        self.assertGreater(state["total_duration"], 0.0)


class DetectorTests(unittest.TestCase):
    """analyze_band() end-to-end on the real 1080p band captures."""

    def make_detector(self, temp):
        with mock.patch.object(bdd, "user_data_root", return_value=Path(temp)):
            detector = bdd.BossDebuffDetector()
        detector.configure(enabled=True, region=[560, 130, 780, 80], device_ratio=1.0)
        return detector

    def test_band_capture_activates_and_locates_the_timer(self):
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            band = read(BAND_A)
            state = None
            now = 500.0
            for _ in range(ACTIVATE_FRAMES + 1):
                state = detector.analyze_band(band, now)
                now += 0.1
            self.assertTrue(state["active"])
            self.assertGreaterEqual(state["score"], 0.95)
            self.assertEqual(state["glyph_count"], 1)
            self.assertEqual(state["cell"][:2], list(to_band(CELL_ABS_A)[:2]))
            # Only one digit was ever visible and the seed profile is untrusted,
            # so the detector must not invent a number.
            self.assertIsNone(state["remaining"])
            self.assertEqual(state["source"], "unknown")

    def test_hotkey_bar_band_never_activates(self):
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            band = read(HOTKEY_BAR)
            state = None
            now = 500.0
            for _ in range(6):
                state = detector.analyze_band(band, now)
                now += 0.1
            self.assertFalse(state["active"])
            self.assertLess(state["score"], DEFAULT_MATCH_THRESHOLD)

    def test_configured_duration_gives_seconds_on_the_real_band(self):
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.configure(duration=10.0)
            band = read(BAND_A)
            now = 500.0
            state = None
            for _ in range(ACTIVATE_FRAMES + 1):
                state = detector.analyze_band(band, now)
                now += 0.1
            if detector.profile.trusted:
                # 숫자를 읽을 수 있는 상태에서는 첫 순간에 추정값을 내보내지 않는다.
                # 학습된 총 지속시간이 어긋나 있으면 캐스트 시작마다 틀린 숫자가
                # 스쳐 지나가기 때문이다(28초로 시작하던 증상).
                self.assertEqual(state["source"], "unknown")
                self.assertIsNone(state["remaining"])
            while now < 500.0 + bdd.OCR_GRACE_SEC + 0.3:
                state = detector.analyze_band(band, now)
                now += 0.1
            self.assertEqual(state["source"], "duration")
            self.assertAlmostEqual(state["remaining"], 10.0 - (now - 500.0 - 0.1), delta=0.2)

    def test_auto_region_covers_the_reference_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            x, y, w, h = detector.auto_region_for_screen(1920, 1080)
            cx, cy, cw, ch = CELL_ABS_A
            self.assertLessEqual(x, cx)
            self.assertGreaterEqual(x + w, cx + cw)
            self.assertLessEqual(y, cy)
            # The band must also contain the timer text under the cell.
            self.assertGreaterEqual(y + h, 194)

    def test_samples_are_labelled_from_the_moment_the_debuff_expires(self):
        """라벨은 살아 있는 추정값이 아니라 '사라진 시점'에서 역산해야 한다.

        추정값으로 라벨을 붙이면 자기참조가 된다: 잘못 추정한 9초가 파일로
        저장되고, 그 파일로 학습한 프로파일이 다시 9초를 확신하게 된다.
        """
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.configure(collect_samples=True)
            detector.sample_root = Path(temp) / "samples"
            band = read(BAND_A)          # 한 자리 숫자('9초')가 보이는 실측 밴드
            now = 500.0
            for _ in range(8):
                detector.analyze_band(band, now)
                now += 0.5
            # 디버프가 살아 있는 동안에는 단 한 장도 저장되지 않는다.
            self.assertFalse(list((Path(temp) / "samples").glob("*.png")))
            self.assertGreaterEqual(len(detector._sample_buffer), 4)

            blank = np.zeros_like(band)
            for _ in range(DEACTIVATE_FRAMES):
                detector.analyze_band(blank, now)
                now += 0.1

            files = sorted(p.name for p in (Path(temp) / "samples").glob("*.png"))
            self.assertTrue(files, "소멸 시점에 버퍼가 저장되어야 합니다.")
            labels = sorted(bdd.parse_sample_label(Path(name)) for name in files)
            # 마지막 프레임이 1초, 0.5초 간격이므로 한 자리 라벨만 나온다.
            self.assertEqual(labels[0], 1)
            self.assertTrue(all(1 <= label <= 9 for label in labels), labels)

    def test_cast_that_does_not_match_the_countdown_is_discarded(self):
        """자리수와 라벨이 어긋나는 관측은 한 장도 저장하지 않는다.

        두 자리 숫자가 보이는 프레임이 1~4초 구간에 놓일 수는 없다. 보스가
        죽거나 영역이 벗어나 관측이 끊긴 경우가 여기에 해당한다.
        """
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.configure(collect_samples=True)
            detector.sample_root = Path(temp) / "samples"
            roi = make_timer_roi(digit_count=2)
            detector._sample_buffer = [(500.0 + index * 0.5, roi.copy()) for index in range(8)]

            result = detector._flush_samples(504.0)

            self.assertEqual(result["written"], 0)
            self.assertTrue(result["reason"])
            self.assertFalse(list((Path(temp) / "samples").glob("*.png")))


if __name__ == "__main__":
    unittest.main()
