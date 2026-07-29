"""쿨타임 판독기 오프라인 평가.

    py tools/eval_cooldown_ocr.py
    py tools/eval_cooldown_ocr.py --synthetic-only

세 가지를 따로 본다.

1. **실측 전량** — 학습에 쓴 샘플이라 상한값일 뿐이다(train=test).
2. **슬롯 교차** — slotA 로만 학습해 slotB 를 읽고, 그 반대도 한다. 아이콘이
   전혀 다른 스킬로 일반화되는지를 보는 유일한 실측 지표다.
3. **합성 적대 배경** — 스킬 아이콘은 직업·단축키마다 달라 표본을 모을 수 없다.
   그래서 실측 글자의 획(알파까지)을 떼어내 밝은 주황·순백·연회색·고주파 질감·
   그라데이션 같은 배경 위에 합성해 시험한다. 배경을 모으는 대신 만든다.

가장 중요한 수치는 정확도가 아니라 **오독률**이다. 값을 못 읽는 것(거부)은
쿨타임을 나중에 다시 학습하면 되지만, 틀린 값을 쓰면 파티 전체가 오정보를 본다.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from boss_debuff_detector import read_image  # noqa: E402
import cooldown_reader as cr  # noqa: E402
from build_cooldown_profile import train  # noqa: E402


@dataclass
class Score:
    total: int = 0
    correct: int = 0
    misread: int = 0
    rejected: int = 0

    def add(self, expected, got):
        self.total += 1
        if got is None:
            self.rejected += 1
        elif got == expected:
            self.correct += 1
        else:
            self.misread += 1

    def line(self, name):
        if not self.total:
            return f"{name:<28} (표본 없음)"
        return (f"{name:<28} 정확 {self.correct:>3}/{self.total:<3} "
                f"({self.correct / self.total:>6.1%})  "
                f"오독 {self.misread:>2} ({self.misread / self.total:>5.1%})  "
                f"거부 {self.rejected:>2}")


def evaluate(profile, paths, expect_none_ok=True):
    score = Score()
    negatives = Score()
    misreads = []
    for path in paths:
        label = cr.parse_sample_label(path)
        image = read_image(path)
        if image is None:
            continue
        reading = cr.read_cooldown(image, profile)
        if label is None:
            negatives.add(None, reading.seconds)
            if reading.seconds is not None:
                misreads.append((path.name, None, reading.seconds, reading.channel))
            continue
        score.add(label, reading.seconds)
        if reading.seconds is not None and reading.seconds != label:
            misreads.append((path.name, label, reading.seconds, reading.channel))
    return score, negatives, misreads


# --- 합성 적대 배경 ----------------------------------------------------------
def text_alpha(image_bgr, profile=None):
    """실측 슬롯에서 글자 획의 알파와 색을 떼어낸다.

    글자만 잘라 쓰지 않고 알파를 추정하는 이유: 인게임 글자는 안티에일리어싱이
    강해서, 이진 마스크로 오려 붙이면 실제와 다른(딱딱한) 획이 되어 시험이
    무의미해진다.
    """
    big = cr.upscale_slot(image_bgr)
    score = cr.channel_score(big, "achro")
    binary, threshold = cr.binarize(score, cr.SCORE_FRACTIONS[0])
    if threshold == 0:
        return None
    layouts = [l for l in cr.segment(binary) if cr.layout_ok(binary, l)]
    if not layouts:
        return None
    layout = max(layouts, key=lambda l: len(l.digits))
    boxes = layout.digits + [layout.suffix]
    x0 = min(b[0] for b in boxes) // cr.UPSCALE
    x1 = int(np.ceil(max(b[0] + b[2] for b in boxes) / cr.UPSCALE))
    y0 = min(b[1] for b in boxes) // cr.UPSCALE
    y1 = int(np.ceil(max(b[1] + b[3] for b in boxes) / cr.UPSCALE))
    pad = 2
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1 = min(image_bgr.shape[1], x1 + pad)
    y1 = min(image_bgr.shape[0], y1 + pad)

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2].astype(np.float32)
    sat = hsv[:, :, 1].astype(np.float32)
    # 밝고 무채색일수록 글자다. 실측 획 V 218~239 / S 0~8.
    alpha = np.clip((value - 150.0) / 80.0, 0.0, 1.0)
    alpha *= np.clip(1.0 - (sat - 40.0) / 60.0, 0.0, 1.0)
    mask = np.zeros(alpha.shape, np.float32)
    mask[y0:y1, x0:x1] = 1.0
    return alpha * mask, (x0, y0, x1, y1)


def synthetic_backgrounds(width, height, rng):
    """글자와 싸우는 배경들. 실제 아이콘을 대신한다."""
    def gradient(c0, c1, horizontal=True):
        ramp = np.linspace(0.0, 1.0, width if horizontal else height, dtype=np.float32)
        ramp = np.tile(ramp, (height, 1)) if horizontal else np.tile(ramp[:, None], (1, width))
        out = np.zeros((height, width, 3), np.float32)
        for i in range(3):
            out[:, :, i] = c0[i] + (c1[i] - c0[i]) * ramp
        return out

    backgrounds = {
        "white": np.full((height, width, 3), 250.0, np.float32),
        "light_gray": np.full((height, width, 3), 205.0, np.float32),
        "warm_bright": gradient((20, 120, 235), (10, 60, 160)),      # BGR 주황
        "warm_dark": gradient((5, 40, 90), (2, 15, 40)),
        "cyan_ready": gradient((235, 210, 60), (180, 150, 30)),
        "dark": np.full((height, width, 3), 30.0, np.float32),
    }
    # 고주파 질감(아이콘 아트 대용)과 밝은 얼룩
    texture = rng.normal(150, 55, (height, width)).astype(np.float32)
    texture = cv2.GaussianBlur(texture, (3, 3), 0)
    backgrounds["texture_mid"] = np.dstack([texture] * 3)
    stripes = np.zeros((height, width), np.float32)
    stripes[:, ::3] = 235.0
    stripes = cv2.GaussianBlur(stripes, (3, 3), 0) + 60.0
    backgrounds["stripes_bright"] = np.dstack([stripes] * 3)
    blobs = rng.uniform(0, 1, (height, width)).astype(np.float32)
    blobs = cv2.GaussianBlur(blobs, (7, 7), 0)
    blobs = np.clip((blobs - 0.45) * 900.0, 0, 255)
    backgrounds["glare"] = np.dstack([blobs * 0.6, blobs * 0.8, blobs])
    return {name: np.clip(bg, 0, 255) for name, bg in backgrounds.items()}


def composite(background, alpha, text_bgr=(236, 236, 236), shadow=True):
    """배경 위에 글자를 얹는다.

    인게임 글자에는 옅은 어두운 그림자가 따라붙는다(실측: 밝은 주황 아이콘에서
    글자 주변 V 135~186, 배경 p95 233). 그림자를 빼고 합성하면 흰 아이콘에서
    대비가 0에 가까워져 실제보다 훨씬 불리한 시험이 된다. 그래서 기본은 그림자를
    포함하고, `shadow=False` 로 그림자 없는 극단 사례도 함께 본다.
    """
    out = background.astype(np.float32).copy()
    if shadow:
        kernel = np.ones((3, 3), np.uint8)
        ring = cv2.dilate(alpha, kernel, iterations=1) - alpha
        ring = np.clip(cv2.GaussianBlur(ring, (3, 3), 0.6), 0.0, 1.0)
        # 실측 비율에 맞춘 감광. 밝은 주황 아이콘에서 글자 주변 V 186 / 배경 255
        # = 약 27% 어두움이었다.
        out *= (1.0 - 0.30 * ring[:, :, None])
    a = alpha[:, :, None]
    text = np.zeros_like(out)
    text[:, :] = text_bgr
    return np.clip(out * (1.0 - a) + text * a, 0, 255).astype(np.uint8)


def synthetic_suite(paths, rng, per_background=None):
    """(라벨, 합성 슬롯) 목록. 배경별로 그룹화해 돌려준다.

    `*_noshadow` 그룹은 글자 그림자를 뺀 극단 사례다(실제보다 불리하다).
    """
    suite: dict[str, list] = {}
    for path in paths:
        label = cr.parse_sample_label(path)
        if label is None:
            continue
        image = read_image(path)
        if image is None:
            continue
        extracted = text_alpha(image)
        if extracted is None:
            continue
        alpha, _box = extracted
        height, width = image.shape[:2]
        backgrounds = synthetic_backgrounds(width, height, rng)
        for name, background in backgrounds.items():
            group = suite.setdefault(name, [])
            if per_background is None or len(group) < per_background:
                group.append((label, composite(background, alpha)))
        for name in ("white", "texture_mid"):
            group = suite.setdefault(f"{name}_noshadow", [])
            if per_background is None or len(group) < per_background:
                group.append((label, composite(backgrounds[name], alpha, shadow=False)))
    return suite


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=cr.samples_root())
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    paths = cr.sample_paths(args.samples)
    slot_a = [p for p in paths if p.name.startswith("slotA")]
    slot_b = [p for p in paths if p.name.startswith("slotB")]
    print(f"샘플 {len(paths)}장 (slotA {len(slot_a)}, slotB {len(slot_b)})\n")

    print("[1] 실측 전량 (train=test 상한값)")
    full = train(paths, verbose=False)
    score, negatives, misreads = evaluate(full, paths)
    print("   ", score.line("전체"))
    print("   ", f"쿨 완료 프레임 오독: {negatives.misread}/{negatives.total}")
    for row in misreads:
        print("     오독:", row)
    print(f"    글리프 LOO 정확도: {full.accuracy:.4f}\n")

    if not args.synthetic_only:
        print("[2] 슬롯 교차 (아이콘이 다른 스킬로 일반화되는가)")
        for name, train_paths, test_paths in (("slotA -> slotB", slot_a, slot_b),
                                             ("slotB -> slotA", slot_b, slot_a)):
            profile = train(train_paths, verbose=False)
            score, negatives, misreads = evaluate(profile, test_paths)
            print("   ", score.line(name), f"LOO={profile.accuracy:.3f}")
            for row in misreads:
                print("     오독:", row)
        print()

    print("[3] 합성 적대 배경 (배경을 모으는 대신 만든다)")
    rng = np.random.default_rng(args.seed)
    suite = synthetic_suite(paths, rng)
    grand = Score()
    for name, cases in sorted(suite.items()):
        score = Score()
        for label, image in cases:
            reading = cr.read_cooldown(image, full)
            score.add(label, reading.seconds)
            grand.add(label, reading.seconds)
        print("   ", score.line(name))
    print("   ", grand.line("합계"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
