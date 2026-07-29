"""스킬 쿨타임 숫자 판독기와 총량 학습 회귀 테스트.

이 기능이 조용히 깨지는 방식은 두 가지다.

1. **오독** — 배경(스킬 아이콘)은 직업·단축키마다 달라 표본을 모을 수 없다.
   그래서 실측 글자를 적대적인 합성 배경 위에 얹어 시험하고, **틀린 값을 내지
   않는 것**을 통과 조건으로 둔다. 값을 못 읽는 것(거부)은 다음 사용에서 다시
   학습하면 되지만, 틀린 값은 파티 전체에 잘못 전파된다.
2. **학습 폭주** — 한 번 잘못 읽은 값이 그대로 쿨타임으로 굳으면 매 사용마다
   엉뚱한 카운트다운이 돈다. 그래서 두 프레임 일관성과 2회 합의를 검사한다.

`tools/eval_cooldown_ocr.py` 가 같은 척도를 더 큰 표본으로 재는 도구이고,
여기서는 그중 회귀로 굳혀야 하는 부분만 본다.
"""

import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from boss_debuff_detector import read_image  # noqa: E402
import cooldown_learning as cl  # noqa: E402
import cooldown_reader as cr  # noqa: E402
from build_cooldown_profile import train  # noqa: E402
import eval_cooldown_ocr as harness  # noqa: E402

SAMPLES = cr.samples_root()


def labelled_samples():
    return [p for p in cr.sample_paths(SAMPLES) if cr.parse_sample_label(p) is not None]


class BundledProfileTests(unittest.TestCase):
    """번들 프로파일만으로 설치 직후부터 동작해야 한다."""

    @classmethod
    def setUpClass(cls):
        cls.profile = cr.load_profile()

    def test_profile_is_bundled_and_trusted(self):
        self.assertIsNotNone(self.profile, "번들 글리프 프로파일이 없습니다.")
        self.assertEqual(len(self.profile.digit_coverage), 10, "0~9 가 모두 필요합니다.")
        self.assertTrue(self.profile.trusted)
        self.assertGreaterEqual(self.profile.accuracy, 0.95)

    def test_reads_every_real_sample_without_misreading(self):
        wrong = []
        rejected = 0
        for path in labelled_samples():
            label = cr.parse_sample_label(path)
            reading = cr.read_cooldown(read_image(path), self.profile)
            if reading.seconds is None:
                rejected += 1
            elif reading.seconds != label:
                wrong.append((path.name, label, reading.seconds))
        self.assertEqual(wrong, [], f"실측 샘플 오독: {wrong}")
        self.assertLessEqual(rejected, 2, f"거부가 너무 많습니다: {rejected}")

    def test_ready_frame_reads_nothing(self):
        """쿨타임이 끝난 슬롯에는 숫자가 없다. 여기서 값을 내면 학습이 오염된다."""
        ready = SAMPLES / "slotA_ready.png"
        self.assertTrue(ready.exists())
        reading = cr.read_cooldown(read_image(ready), self.profile)
        self.assertIsNone(reading.seconds, f"숫자 없는 프레임에서 {reading.seconds} 를 읽었습니다.")

    def test_two_digit_values_keep_the_leading_digit(self):
        """`17s` 를 `7s` 로 읽는 실패가 이 기능의 대표적 오류였다."""
        for name in ("slotA_11s.png", "slotA_15s.png", "slotA_17s.png",
                     "slotA_21s.png", "slotB_10s.png"):
            path = SAMPLES / name
            reading = cr.read_cooldown(read_image(path), self.profile)
            self.assertEqual(reading.seconds, cr.parse_sample_label(path), name)


class GeneralizationTests(unittest.TestCase):
    """학습에 쓰지 않은 아이콘으로 일반화되는지."""

    def test_cross_slot_reading(self):
        slot_a = [p for p in labelled_samples() if p.name.startswith("slotA")]
        slot_b = [p for p in labelled_samples() if p.name.startswith("slotB")]
        for train_paths, test_paths, tag in ((slot_a, slot_b, "slotA->slotB"),
                                             (slot_b, slot_a, "slotB->slotA")):
            profile = train(train_paths, verbose=False)
            cr.stencils_for(profile)          # 캐시를 새 프로파일로 교체
            correct = wrong = 0
            for path in test_paths:
                label = cr.parse_sample_label(path)
                reading = cr.read_cooldown(read_image(path), profile)
                if reading.seconds == label:
                    correct += 1
                elif reading.seconds is not None:
                    wrong += 1
            with self.subTest(direction=tag):
                self.assertEqual(wrong, 0, f"{tag} 오독 {wrong}건")
                self.assertGreaterEqual(correct / len(test_paths), 0.85,
                                        f"{tag} 정확도 {correct}/{len(test_paths)}")


class AdversarialBackgroundTests(unittest.TestCase):
    """배경을 모을 수 없으니 만들어서 시험한다.

    실측 글자의 획(알파 포함)을 떼어 밝은 주황·순백·연회색·고주파 질감·그라데이션
    위에 얹는다. 통과 조건은 **오독 0건**이다.
    """

    @classmethod
    def setUpClass(cls):
        cls.profile = cr.load_profile()
        cls.paths = labelled_samples()[::3]          # 테스트 시간 위해 1/3만
        cls.rng = np.random.default_rng(11)

    def test_no_misreads_on_synthetic_backgrounds(self):
        suite = harness.synthetic_suite(self.paths, self.rng)
        self.assertGreater(len(suite), 5, "합성 배경 세트가 만들어지지 않았습니다.")
        wrong = []
        total = read = 0
        for name, cases in suite.items():
            for label, image in cases:
                total += 1
                reading = cr.read_cooldown(image, self.profile)
                if reading.seconds is None:
                    continue
                read += 1
                if reading.seconds != label:
                    wrong.append((name, label, reading.seconds))
        self.assertEqual(wrong, [], f"합성 배경 오독: {wrong}")
        # 전부 거부해 버리면 오독 0은 의미가 없다.
        self.assertGreaterEqual(read / total, 0.5,
                                f"판독률이 너무 낮습니다: {read}/{total}")

    def test_empty_slot_is_never_read(self):
        """글자가 아예 없는 배경에서 값을 만들어내면 안 된다."""
        rng = np.random.default_rng(3)
        backgrounds = harness.synthetic_backgrounds(45, 43, rng)
        for name, background in backgrounds.items():
            image = background.astype(np.uint8)
            reading = cr.read_cooldown(image, self.profile)
            self.assertIsNone(reading.seconds,
                              f"{name} 빈 배경에서 {reading.seconds} 를 읽었습니다.")


class ReaderGuardTests(unittest.TestCase):
    """배치 검사 규칙이 살아 있는지(상수만 바꿔도 조용히 죽는다)."""

    def setUp(self):
        self.profile = cr.load_profile()

    def test_layout_rejects_wrong_suffix_advance(self):
        image = read_image(SAMPLES / "slotA_17s.png")
        big = cr.upscale_slot(image)
        score = cr.channel_score(big, "achro")
        binary, threshold = cr.binarize(score, cr.SCORE_FRACTIONS[0])
        self.assertGreater(threshold, 0)
        layouts = [l for l in cr.segment(binary) if cr.layout_ok(binary, l)]
        self.assertTrue(layouts)
        layout = layouts[0]
        # 접미사를 숫자 쪽으로 끌어다 붙이면(간격 위반) 배치 검사가 걸러야 한다.
        moved = cr.Layout(suffix=(layout.digits[-1][0] + 2, layout.suffix[1],
                                  layout.suffix[2], layout.suffix[3]),
                          digits=layout.digits, text_height=layout.text_height)
        self.assertFalse(cr.layout_ok(binary, moved))

    def test_channels_cover_both_polarities(self):
        """흰 아이콘에서는 글자가 배경보다 어둡다. 반대 극성 채널이 없으면 못 읽는다."""
        self.assertIn("dark", cr.CHANNELS)
        self.assertIn("median_neg", cr.CHANNELS)
        image = read_image(SAMPLES / "slotA_09s.png")
        big = cr.upscale_slot(image)
        for channel in cr.CHANNELS:
            score = cr.channel_score(big, channel)
            self.assertEqual(score.shape[:2], big.shape[:2])

    def test_agreement_rule_is_enforced(self):
        self.assertGreaterEqual(cr.MIN_AGREEMENT, 2)
        reading = cr.read_cooldown(read_image(SAMPLES / "slotA_09s.png"), self.profile)
        self.assertEqual(reading.seconds, 9)
        self.assertGreaterEqual(reading.agreement, cr.MIN_AGREEMENT)


class LearnerTests(unittest.TestCase):
    """쿨타임 총량 학습 상태 기계."""

    def setUp(self):
        self.learner = cl.CooldownLearner()

    def test_single_reading_learns_nothing(self):
        self.learner.on_cast("A", 100.0)
        self.assertIsNone(self.learner.on_reading("A", 24, 100.3))
        self.assertIsNone(self.learner.learned("A"))

    def test_two_consistent_readings_over_two_casts_learn(self):
        self.learner.on_cast("A", 100.0)
        self.assertIsNone(self.learner.on_reading("A", 24, 100.2))
        self.assertIsNone(self.learner.on_reading("A", 23, 101.2))   # 1차 후보
        self.learner.on_cast("A", 200.0)
        self.assertIsNone(self.learner.on_reading("A", 24, 200.2))
        self.assertEqual(self.learner.on_reading("A", 23, 201.2), 24)
        self.assertEqual(self.learner.learned("A"), 24)

    def test_inconsistent_pair_is_ignored(self):
        """경과 시간과 어긋나는 두 값은 배경 얼룩이다."""
        self.learner.on_cast("A", 100.0)
        self.learner.on_reading("A", 24, 100.2)
        self.assertIsNone(self.learner.on_reading("A", 9, 101.2))    # 1초에 15초 감소
        self.learner.on_cast("A", 200.0)
        self.learner.on_reading("A", 24, 200.2)
        self.assertIsNone(self.learner.on_reading("A", 9, 201.2))
        self.assertIsNone(self.learner.learned("A"))

    def test_scan_window_closes(self):
        self.learner.on_cast("A", 100.0)
        self.assertTrue(self.learner.should_scan("A", 100.5))
        self.assertFalse(self.learner.should_scan("A", 100.0 + cl.SCAN_WINDOW + 0.1))

    def test_scan_stops_once_the_cast_produced_a_candidate(self):
        self.learner.on_cast("A", 100.0)
        self.learner.on_reading("A", 24, 100.2)
        self.learner.on_reading("A", 23, 101.2)
        self.assertFalse(self.learner.should_scan("A", 101.3))

    def test_ready_transition_learns_without_ocr(self):
        """레디 전환 시간만으로도 학습된다(오독 위험 0인 경로)."""
        self.learner.on_cast("A", 0.0)
        self.assertIsNone(self.learner.on_ready("A", 30.2))
        self.learner.on_cast("A", 100.0)
        self.assertEqual(self.learner.on_ready("A", 130.1), 30)
        self.assertEqual(self.learner.state("A").learned_source, "ready")

    def test_learned_value_can_shrink(self):
        """쿨감(각인·장비)으로 짧아진 값도 두 번 관측되면 받아들인다."""
        self.learner.on_cast("A", 0.0)
        self.learner.on_ready("A", 30.0)
        self.learner.on_cast("A", 100.0)
        self.assertEqual(self.learner.on_ready("A", 130.0), 30)
        for base in (200.0, 300.0):
            self.learner.on_cast("A", base)
            result = self.learner.on_ready("A", base + 24.0)
        self.assertEqual(result, 24)
        self.assertEqual(self.learner.learned("A"), 24)

    def test_out_of_range_values_are_dropped(self):
        self.learner.on_cast("A", 0.0)
        self.assertIsNone(self.learner.on_ready("A", 0.5))            # 너무 짧다
        self.learner.on_cast("B", 0.0)
        self.assertIsNone(self.learner.on_ready("B", cl.MAX_COOLDOWN + 10))

    def test_persistence_round_trip(self):
        self.learner.on_cast("A", 0.0)
        self.learner.on_ready("A", 30.0)
        self.learner.on_cast("A", 100.0)
        self.learner.on_ready("A", 130.0)
        payload = json.loads(json.dumps(self.learner.snapshot()))
        restored = cl.CooldownLearner()
        restored.restore(payload)
        self.assertEqual(restored.learned("A"), 30)

    def test_forget_clears_a_stuck_value(self):
        self.learner.on_cast("A", 0.0)
        self.learner.on_ready("A", 30.0)
        self.learner.on_cast("A", 100.0)
        self.learner.on_ready("A", 130.0)
        self.learner.forget("A")
        self.assertIsNone(self.learner.learned("A"))

    def test_expected_tracks_the_running_countdown(self):
        self.learner.on_cast("A", 0.0)
        self.learner.on_ready("A", 30.0)
        self.learner.on_cast("A", 100.0)
        self.learner.on_ready("A", 130.0)
        self.learner.on_cast("A", 200.0)
        self.assertEqual(self.learner.expected("A", 205.0), 25)


class DetectorWiringTests(unittest.TestCase):
    """감지 스레드와 설정 저장에 실제로 연결돼 있는지(정적 검사)."""

    def setUp(self):
        self.detector_source = (ROOT / "cooldown_detector.py").read_text(encoding="utf-8")
        self.app_source = (ROOT / "magnifier.py").read_text(encoding="utf-8")

    def test_detector_scans_only_after_a_cast(self):
        self.assertIn("self.learner.should_scan(name, now_mono)", self.detector_source)
        self.assertIn("self.learner.on_cast(name, trigger_mono)", self.detector_source)
        self.assertIn("self.learner.on_ready(name, now_mono)", self.detector_source)

    def test_manual_duration_is_never_overwritten(self):
        self.assertIn("if slot is not None and slot.cooldown_duration <= 0:",
                      self.detector_source)

    def test_settings_persist_learned_values(self):
        self.assertIn("'learned_cooldowns': self.detector.learned_snapshot()",
                      self.app_source)
        self.assertIn("data.get('learned_cooldowns', {})", self.app_source)
        self.assertIn("self.chk_cooldown_learning", self.app_source)


if __name__ == "__main__":
    unittest.main()
