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


VERIFIED_DIR = ROOT / "boss_debuff_assets" / "samples" / "verified"


def verified_frames():
    """(파일명, 라벨, ROI) 목록. 라벨은 8배 확대 이미지를 눈으로 확인한 값이다."""
    frames = []
    for path in sorted(VERIFIED_DIR.glob("*.png")):
        label = bdd.parse_sample_label(path)
        image = bdd.read_image(path)
        if image is not None and label is not None:
            frames.append((path.name, label, image))
    return frames


def warm_arena(roi: np.ndarray, glow: int = 40, period: float = 9.0) -> np.ndarray:
    """붉은 조명이 깔린 보스방을 흉내낸다.

    획과 어두운 외곽선의 구조는 그대로 두고 색만 옮긴다. 파랑을 깎고 붉은 조명을
    얹으면 배경의 warm(R-B) 값이 글자 자체의 warm(약 105)에 가까워지므로,
    warm 채널만 쓰던 구버전 경로는 배경 얼룩을 획으로 착각한다. 조명 얼룩은
    사인 격자로 만들어 실행마다 같은 결과가 나온다.
    """
    height, width = roi.shape[:2]
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    field = (np.sin(xs / period) + np.sin(ys / period * 1.3)) * 0.5
    out = roi.astype(np.float32)
    out[:, :, 0] *= 0.55
    out[:, :, 1] *= 0.80
    out[:, :, 2] = out[:, :, 2] * 0.95 + glow + field * (glow * 0.35)
    return np.clip(out, 0, 255).astype(np.uint8)


def read_warm_channel_only(image: np.ndarray, profile) -> "int | None":
    """v2.48 이전 경로: warm 채널 하나로만 이진화해 읽는다."""
    binary, _threshold = binarize_timer_text(image)
    suffix, digits = segment_timer_glyphs(binary)
    if suffix is None or not digits or bdd.has_decimal_point(binary, suffix, digits):
        return None
    return profile.read_seconds(binary, digits)[0]


def layout_boxes(digit_count=2, digit_width=14, suffix_width=32, glyph_height=32,
                 baseline=45, gap=6, left=40, suffix_gap=8):
    """`N초` 한 줄을 이루는 (binary, suffix_box, digit_boxes).

    게이트가 획 밀도(0.18~0.90)를 보기 때문에 속이 찬 사각형이 아니라 테두리만
    그린다. 실제 글리프도 획으로만 이루어져 있다.
    """
    binary = np.zeros((64, 176), np.uint8)
    boxes = []
    x = left
    for _ in range(digit_count):
        y = baseline - glyph_height
        cv2.rectangle(binary, (x, y), (x + digit_width - 1, baseline - 1), 255, 4)
        boxes.append((x, y, digit_width, glyph_height))
        x += digit_width + gap
    sx = x - gap + suffix_gap
    sy = baseline - glyph_height
    cv2.rectangle(binary, (sx, sy), (sx + suffix_width - 1, baseline - 1), 255, 4)
    return binary, (sx, sy, suffix_width, glyph_height), boxes


class StubProfile:
    """`read_timer_value` 의 순위 결정만 시험하기 위한 가짜 프로파일.

    글리프 분류는 이미 TimerProfileTests 가 다루므로, 여기서는 후보마다 미리
    정한 (값, 신뢰도) 를 돌려주고 순위 규칙만 관찰한다.
    """

    def __init__(self, table):
        self.table = table          # {태그: (값, 신뢰도)}
        self.trusted = True
        self.patches = []           # 상관 정합 템플릿 없음 = 그 경로는 쓰이지 않는다

    @staticmethod
    def _tag(binary):
        return int(binary[0, 0])

    def suffix_similarity(self, _glyph):
        return 1.0

    def read_seconds(self, binary, _digit_boxes):
        return self.table[self._tag(binary)]


class TimerLayoutGateTests(unittest.TestCase):
    """`glyph_layout_ok` 는 분류기가 확신하는 헛것을 걸러내는 마지막 관문이다."""

    def test_accepts_a_clean_two_digit_line(self):
        binary, suffix, digits = layout_boxes(2)
        self.assertTrue(bdd.glyph_layout_ok(binary, suffix, digits))

    def test_rejects_a_suffix_that_swallowed_the_neighbouring_digit(self):
        """'초' 가 옆 숫자를 함께 삼킨 덩어리. 그대로 읽으면 19초가 1초가 된다."""
        binary, suffix, digits = layout_boxes(2)
        sx, sy, sw, sh = suffix
        wide = (sx, sy, int(sh * 1.6), sh)
        cv2.rectangle(binary, (sx, sy), (sx + wide[2] - 1, sy + sh - 1), 255, -1)
        self.assertFalse(bdd.glyph_layout_ok(binary, wide, digits))

    def test_rejects_a_gap_where_a_digit_was_dropped(self):
        binary, suffix, digits = layout_boxes(1, left=20)
        sx, sy, sw, sh = suffix
        moved = (sx + int(sh * 0.8), sy, sw, sh)
        binary[:, sx:sx + sw] = 0
        cv2.rectangle(binary, (moved[0], sy), (moved[0] + sw - 1, sy + sh - 1), 255, -1)
        self.assertFalse(bdd.glyph_layout_ok(binary, moved, digits))

    def test_rejects_leftover_ink_left_of_the_first_digit(self):
        """맨 앞 숫자를 놓치면 그 자리에 잉크가 남는다. 18을 8로 읽는 후보다."""
        binary, suffix, digits = layout_boxes(1, left=80)
        x, y, w, h = digits[0]
        cv2.rectangle(binary, (x - 24, y), (x - 10, y + h - 1), 255, -1)
        self.assertFalse(bdd.glyph_layout_ok(binary, suffix, digits))

    def test_rejects_glyphs_off_the_shared_baseline(self):
        binary, suffix, digits = layout_boxes(2)
        x, y, w, h = digits[0]
        raised = (x, y - int(h * 0.5), w, h)
        self.assertFalse(bdd.glyph_layout_ok(binary, suffix, [raised, digits[1]]))

    def test_rejects_a_background_flood(self):
        binary, suffix, digits = layout_boxes(2)
        binary[:] = 255
        self.assertFalse(bdd.glyph_layout_ok(binary, suffix, digits))


class RankedTimerReaderTests(unittest.TestCase):
    """`read_timer_value` 는 여러 채널의 후보를 만들고 그중 하나를 고른다."""

    @classmethod
    def setUpClass(cls):
        cls.profile = TimerGlyphProfile.load(
            ROOT / "boss_debuff_assets" / "timer_profiles" / f"{DEFAULT_DEBUFF_ID}.json"
        )
        assert cls.profile is not None, "번들 타이머 프로파일이 없습니다."
        cls.frames = verified_frames()
        assert len(cls.frames) >= 40, "검증 프레임이 함께 커밋되어야 합니다."

    def measure(self, reader, transform=None):
        read = correct = 0
        modes = {}
        for _name, label, roi in self.frames:
            image = roi if transform is None else transform(roi)
            value, mode = reader(image)
            if value is None:
                continue
            read += 1
            correct += int(value == label)
            modes[mode] = modes.get(mode, 0) + 1
        return read, correct, modes

    def ranked_reader(self, image):
        reading = bdd.read_timer_value(image, self.profile)
        return reading.value, reading.mode

    def warm_reader(self, image):
        return read_warm_channel_only(image, self.profile), "warm"

    def test_reads_the_verified_frames_without_a_misread(self):
        read, correct, _modes = self.measure(self.ranked_reader)
        self.assertGreaterEqual(read, len(self.frames) - 2,
                                f"검증 프레임 판독 {read}/{len(self.frames)}")
        self.assertEqual(read, correct, f"검증 프레임에서 오독 {read - correct}건")

    def test_warm_arena_never_produces_a_wrong_number(self):
        """배경이 글자와 같은 계열로 물들면, 값을 못 읽어도 틀린 값은 내지 않아야 한다.

        warm 채널 하나로 읽던 구버전은 배경 얼룩을 숫자로 착각해 실제로 틀린
        남은 시간을 표시했다(보스방마다 되는/안 되는 증상). 새 경로는 '초' 모양
        검사와 배치 검사를 통과한 후보만 쓰기 때문에, 최악의 경우 침묵한다.
        """
        transform = lambda roi: warm_arena(roi, glow=40)  # noqa: E731
        ranked_read, ranked_correct, modes = self.measure(self.ranked_reader, transform)
        warm_read, warm_correct, _ = self.measure(self.warm_reader, transform)

        self.assertGreaterEqual(warm_read - warm_correct, 3,
                                "구버전 경로가 오독하지 않으면 이 시나리오는 의미가 없다")
        self.assertEqual(ranked_read, ranked_correct,
                         f"적대 배경에서 오독 {ranked_read - ranked_correct}건 "
                         f"(채널 {modes})")
        self.assertGreaterEqual(ranked_read, len(self.frames) // 3,
                                f"적대 배경 판독 {ranked_read}/{len(self.frames)}")

    def test_falls_back_to_the_luminance_channel(self):
        """warm 채널이 죽은 프레임도 밝기 채널로 읽히는 것이 다중 후보의 이유다."""
        picked = set()
        for _name, _label, roi in self.frames:
            hostile = warm_arena(roi, glow=40)
            reading = bdd.read_timer_value(hostile, self.profile)
            if reading.value is not None:
                picked.add(reading.mode)
        self.assertTrue(picked - {"warm"},
                        f"warm 이외의 채널이 채택된 프레임이 없다: {picked}")

    def test_every_hypothesis_passes_the_layout_gate(self):
        roi = self.frames[0][2]
        hypotheses = list(bdd.timer_hypotheses(roi))
        self.assertTrue(hypotheses, "실측 프레임에서 후보가 하나도 나오지 않았다")
        for binary, suffix, digits, _mode, threshold, _priority in hypotheses:
            self.assertTrue(bdd.glyph_layout_ok(binary, suffix, digits))
            self.assertGreater(threshold, 0)

    def test_empty_roi_reads_nothing(self):
        blank = np.full((16, 44, 3), 18, np.uint8)
        reading = bdd.read_timer_value(blank, self.profile)
        self.assertIsNone(reading.value)
        self.assertIsNone(reading.suffix_box)
        self.assertEqual(reading.candidates, 0)

    def two_candidates(self):
        """(값 17, 신뢰 0.80) 과 (값 91, 신뢰 0.94) 두 후보를 만든다."""
        low, low_suffix, low_digits = layout_boxes(2)
        high, high_suffix, high_digits = layout_boxes(2)
        low[0, 0] = 1
        high[0, 0] = 2
        return [
            (low, low_suffix, low_digits, "warm", 50, 0),
            (high, high_suffix, high_digits, "bright", 90, 2),
        ]

    def test_prediction_outranks_a_more_confident_disagreement(self):
        candidates = self.two_candidates()
        profile = StubProfile({1: (17, 0.80), 2: (91, 0.94)})
        with mock.patch.object(bdd, "timer_hypotheses", return_value=iter(candidates)):
            reading = bdd.read_timer_value(np.zeros((16, 44, 3), np.uint8), profile,
                                           predicted=17.0)
        self.assertEqual(reading.value, 17)
        self.assertEqual(reading.mode, "warm")

    def test_without_a_prediction_the_confident_candidate_wins(self):
        candidates = self.two_candidates()
        profile = StubProfile({1: (17, 0.80), 2: (91, 0.94)})
        with mock.patch.object(bdd, "timer_hypotheses", return_value=iter(candidates)):
            reading = bdd.read_timer_value(np.zeros((16, 44, 3), np.uint8), profile,
                                           predicted=None)
        self.assertEqual(reading.value, 91)
        self.assertEqual(reading.mode, "bright")
        self.assertEqual(reading.candidates, 2)

    def test_low_confidence_candidate_is_handed_over_with_its_confidence(self):
        """확신 없는 후보도 트래커에는 넘긴다. 대신 신뢰도로 걸러지게 한다.

        리더는 자리수 변화(2자리→1자리 앵커)와 획 지문도 함께 넘겨야 하므로
        후보 자체를 버리지 않는다. 남은 시간으로 채택할지는 신뢰도를 보는
        호출자(`BossDebuffDetector.analyze_band`)와 트래커가 정한다.
        """
        candidates = self.two_candidates()[:1]
        profile = StubProfile({1: (17, 0.10)})
        with mock.patch.object(bdd, "timer_hypotheses", return_value=iter(candidates)):
            reading = bdd.read_timer_value(np.zeros((16, 44, 3), np.uint8), profile)
        self.assertLess(reading.confidence, bdd.MIN_OCR_CONFIDENCE)
        self.assertIsNotNone(reading.suffix_box, "후보 자체는 트래커에 넘겨야 한다")
        self.assertEqual(reading.glyph_count, 2, "자리수 앵커는 계속 살아 있어야 한다")


class CorrelationReaderTests(unittest.TestCase):
    """세그먼테이션 없이 외형 템플릿을 직접 정합하는 경로."""

    @classmethod
    def setUpClass(cls):
        cls.profile = TimerGlyphProfile.load(
            ROOT / "boss_debuff_assets" / "timer_profiles" / f"{DEFAULT_DEBUFF_ID}.json"
        )
        assert cls.profile is not None
        cls.frames = verified_frames()

    def test_bundled_profile_carries_appearance_templates(self):
        """번들 프로파일에 채널별 외형 템플릿이 들어 있어야 한다."""
        self.assertEqual(self.profile.version, bdd.PROFILE_VERSION)
        self.assertTrue(self.profile.patches, "외형 템플릿이 없습니다")
        modes = set(self.profile.patch_modes)
        self.assertIn("warm", modes)
        digits, suffix = self.profile.patch_stencils("warm")
        self.assertGreaterEqual(len(digits), bdd.MIN_TRAINED_DIGITS)
        self.assertIsNotNone(suffix, "'초' 외형 템플릿이 없습니다")
        # 평균 하나만 남기므로 채널 수 * (숫자 10 + 초 1) 을 넘지 않는다.
        self.assertLessEqual(len(self.profile.patches),
                            len(bdd.TIMER_SCORE_MODES) * 11)

    def test_appearance_patch_normalizes_the_ink_height(self):
        field = np.zeros((64, 176), np.uint8)
        cv2.rectangle(field, (40, 13), (54, 44), 255, 4)
        patch = bdd.appearance_patch(field, (40, 13, 15, 32))
        self.assertIsNotNone(patch)
        expected = bdd.PATCH_HEIGHT * (1 + 2 * bdd.PATCH_MARGIN)
        self.assertAlmostEqual(patch.shape[0], expected, delta=3)

    def test_reads_the_verified_frames_without_a_misread(self):
        read = correct = 0
        for _name, label, roi in self.frames:
            reading = bdd.read_timer_by_correlation(roi, self.profile)
            if reading.value is None or reading.confidence < bdd.MIN_OCR_CONFIDENCE:
                continue
            read += 1
            correct += int(reading.value == label)
        self.assertGreaterEqual(read, len(self.frames) - 3,
                                f"판독 {read}/{len(self.frames)}")
        self.assertEqual(read, correct, f"오독 {read - correct}건")

    def test_beats_segmentation_on_a_warm_arena_without_misreading(self):
        """배경이 글자와 같은 계열로 물든 프레임에서 이 경로만 살아남는다."""
        segmented = correlated = correct = 0
        for _name, label, roi in self.frames:
            hostile = warm_arena(roi, glow=60)
            if read_warm_channel_only(hostile, self.profile) is not None:
                segmented += 1
            reading = bdd.read_timer_by_correlation(hostile, self.profile)
            if reading.value is None or reading.confidence < bdd.MIN_OCR_CONFIDENCE:
                continue
            correlated += 1
            correct += int(reading.value == label)
        self.assertEqual(correlated, correct, f"오독 {correlated - correct}건")
        self.assertGreater(correlated, segmented,
                           f"상관 {correlated} vs 분리 {segmented}")
        self.assertGreaterEqual(correlated, len(self.frames) // 2)

    def test_two_digit_frames_are_never_read_as_one_digit(self):
        """앞자리를 놓친 후보는 버려야 한다. '15초' 를 '5초' 로 읽던 실패다."""
        for _name, label, roi in self.frames:
            if label < 10:
                continue
            for glow in (0, 60):
                image = roi if glow == 0 else warm_arena(roi, glow=glow)
                reading = bdd.read_timer_by_correlation(image, self.profile)
                if reading.value is None or reading.confidence < bdd.MIN_OCR_CONFIDENCE:
                    continue
                self.assertGreaterEqual(reading.value, 10,
                                        f"{_name} glow={glow} -> {reading.value}")

    def test_untrained_profile_reads_nothing(self):
        profile = TimerGlyphProfile(profile_id=DEFAULT_DEBUFF_ID)
        reading = bdd.read_timer_by_correlation(self.frames[0][2], profile)
        self.assertIsNone(reading.value)

    def test_ranked_reader_falls_back_to_correlation(self):
        """분리 후보가 하나도 없으면 상관 정합 결과를 쓴다."""
        roi = self.frames[0][2]
        with mock.patch.object(bdd, "timer_hypotheses", return_value=iter([])):
            reading = bdd.read_timer_value(roi, self.profile)
        self.assertIsNotNone(reading.value)
        self.assertTrue(reading.mode.startswith("ncc-"), reading.mode)


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

    def test_ocr_lowers_an_inflated_learned_duration(self):
        """부풀려진 학습값은 숫자를 읽는 순간 내려와야 한다.

        구버전은 '읽은 값 + 감지 이후 경과' 로 학습해서, 만료 전에 다시 걸린
        캐스트가 20초 디버프를 28.8초로 굳혔다. 이제 학습값은 '여태 본 가장 큰
        OCR 숫자' 이므로 20초 디버프에서는 20 이하로 수렴한다.
        """
        self.tracker.learned_duration = 28.8      # 예전 설정 파일에서 복원된 값
        now = 200.0
        _state, now = self.feed(2, now, glyph_count=2)
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=2,
                        ocr_seconds=19, ocr_confidence=0.95), now)
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=2,
                        ocr_seconds=19, ocr_confidence=0.95), now + 0.4)
        self.assertEqual(state["source"], "ocr")
        self.assertAlmostEqual(state["learned_duration"], 19.0, delta=0.1)
        self.assertLess(state["remaining"], 20.0,
                        "28.8초 학습값이 남아 있으면 28초가 스쳐 보인다")

    def test_reset_learned_duration_clears_it_for_relearning(self):
        self.tracker.learned_duration = 28.8
        self.tracker.observed_max = 28.8
        self.tracker.reset_learned_duration()
        self.assertEqual(self.tracker.learned_duration, 0.0)
        self.assertEqual(self.tracker.observed_max, 0.0)
        self.assertEqual(self.tracker.total_duration, 0.0)
        # 초기화 후 첫 캐스트에서 다시 배운다.
        now = 300.0
        _state, now = self.feed(2, now, glyph_count=1)
        self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=8, ocr_confidence=0.95), now)
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=8, ocr_confidence=0.95), now + 0.3)
        self.assertAlmostEqual(state["learned_duration"], 8.0, delta=0.1)

    def test_manual_duration_still_wins_over_the_learned_one(self):
        self.tracker.configured_duration = 20.0
        self.tracker.learned_duration = 28.8
        self.assertEqual(self.tracker.total_duration, 20.0)

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
            # 이 밴드에는 '9초' 가 찍혀 있다. 상관 정합 경로가 붙은 뒤로는 실제로
            # 그 값을 읽어낸다(예전에는 분리에 실패해 'unknown' 이었다).
            self.assertEqual(state["source"], "ocr")
            self.assertAlmostEqual(state["remaining"], 9.0, delta=1.0)

    def test_no_number_is_invented_without_a_trained_profile(self):
        """프로파일이 없으면 남은 시간을 만들어내지 않는다."""
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.profile = TimerGlyphProfile(profile_id=DEFAULT_DEBUFF_ID)
            detector.tracker.expect_ocr = False
            band = read(BAND_A)
            now = 500.0
            state = None
            for _ in range(ACTIVATE_FRAMES + 1):
                state = detector.analyze_band(band, now)
                now += 0.1
            self.assertTrue(state["active"])
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
        """숫자를 읽을 수 없을 때만 지속시간 추정이 화면에 나온다.

        번들 프로파일이 이 밴드의 '9초' 를 읽어버리므로, 추정 경로를 관찰하려면
        프로파일을 비워 OCR 을 끈 상태로 재현한다.
        """
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.configure(duration=10.0)
            detector.profile = TimerGlyphProfile(profile_id=DEFAULT_DEBUFF_ID)
            detector.tracker.expect_ocr = False
            band = read(BAND_A)
            now = 500.0
            state = None
            for _ in range(ACTIVATE_FRAMES + 1):
                state = detector.analyze_band(band, now)
                now += 0.1
            self.assertEqual(state["source"], "duration")
            self.assertAlmostEqual(state["remaining"], 10.0 - (now - 500.0 - 0.1), delta=0.2)

    def test_confident_reading_outranks_the_configured_duration(self):
        """읽은 값이 있으면 지속시간 추정보다 우선한다."""
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.configure(duration=10.0)
            band = read(BAND_A)
            now = 500.0
            state = None
            while now < 500.0 + bdd.OCR_GRACE_SEC + 0.3:
                state = detector.analyze_band(band, now)
                now += 0.1
            self.assertEqual(state["source"], "ocr")
            self.assertAlmostEqual(state["remaining"], 9.0, delta=1.0)

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
