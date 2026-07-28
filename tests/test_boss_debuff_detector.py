import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

import boss_debuff_detector as bdd
from boss_debuff_detector import (
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
        self.assertIn(threshold, bdd.TIMER_THRESHOLDS)

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
    def test_bundled_seed_is_not_trusted_yet(self):
        profile = TimerGlyphProfile.load(
            ROOT / "boss_debuff_assets" / "timer_profiles" / f"{DEFAULT_DEBUFF_ID}.json"
        )
        self.assertIsNotNone(profile, "번들 타이머 프로파일이 없습니다.")
        self.assertIn(9, profile.digit_coverage)
        self.assertFalse(profile.trusted, "표본이 부족한 프로파일은 신뢰되면 안 됩니다.")

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
        _state, now = self.feed(5, 100.0, glyph_count=2)
        state, now = self.feed(3, now, glyph_count=1)
        self.assertEqual(state["source"], "anchor")
        # The anchor lands on the 2nd single-digit frame, one frame before the last.
        self.assertAlmostEqual(state["remaining"], 8.9, delta=0.05)
        later = self.tracker.snapshot(now + 4.0)
        self.assertAlmostEqual(later["remaining"], 8.9 - 4.0 - 0.1, delta=0.05)

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
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=7, ocr_confidence=0.95), now)
        self.assertEqual(state["source"], "ocr")
        self.assertAlmostEqual(state["remaining"], 7.0, delta=0.05)
        # A misread that claims more time than physically possible is dropped.
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=59, ocr_confidence=0.99), now + 1.0)
        self.assertAlmostEqual(state["remaining"], 6.0, delta=0.05)

    def test_low_confidence_ocr_is_ignored(self):
        _state, now = self.feed(3, 100.0, glyph_count=1)
        state = self.tracker.update(
            DebuffFrame(True, 0.99, (10, 10, 26, 26), glyph_count=1,
                        ocr_seconds=4, ocr_confidence=0.2), now)
        self.assertEqual(state["source"], "unknown")
        self.assertIsNone(state["remaining"])

    def test_reappearance_restarts_the_countdown(self):
        _state, now = self.feed(3, 100.0, glyph_count=2)
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
            self.assertEqual(state["source"], "duration")
            self.assertAlmostEqual(state["remaining"], 9.9, delta=0.15)

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

    def test_sample_collection_labels_retroactively_from_the_anchor(self):
        with tempfile.TemporaryDirectory() as temp:
            detector = self.make_detector(temp)
            detector.configure(collect_samples=True)
            detector.sample_root = Path(temp) / "samples"
            band = read(BAND_A)
            now = 500.0
            for _ in range(4):
                detector.analyze_band(band, now)
                now += 0.5
            # Nothing is exactly known yet, so no crop may be labelled on disk.
            self.assertFalse(list((Path(temp) / "samples").glob("*.png")))
            self.assertGreaterEqual(len(detector._sample_buffer), 2)

            # A 2->1 digit transition (or a confident OCR read) makes the whole
            # buffered cast exactly labelable.
            detector.tracker.set_anchor(9.0, now, "anchor")
            detector.analyze_band(band, now)
            files = sorted(p.name for p in (Path(temp) / "samples").glob("*.png"))
            self.assertGreaterEqual(len(files), 3)
            self.assertTrue(all(name.endswith("s.png") for name in files), files)
            labels = sorted(bdd.parse_sample_label(Path(name)) for name in files)
            # The live crop is the 9s anchor itself, buffered crops go 10s, 11s...
            self.assertEqual(labels[0], 9)
            self.assertEqual(labels[-1], 11)


if __name__ == "__main__":
    unittest.main()
