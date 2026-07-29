"""쿨타임 숫자 글리프 프로파일을 샘플에서 학습한다.

    py tools/build_cooldown_profile.py
    py tools/build_cooldown_profile.py --samples cooldown_assets/samples --only slotA

스킬 아이콘(배경)은 직업·단축키마다 달라 표본으로 모을 수 없다. 학습 대상은
배경이 아니라 **글자 모양**이고, 그건 샘플 41장으로 이미 완비된다(0~9 전부 등장).

두 번에 걸쳐 학습한다.

1. **1차(부트스트랩)** — 가장 신뢰도 높은 채널(`achro`) 하나로만, 자리수가 라벨과
   맞는 후보에서 글리프를 뜬다. 여기서는 분류기가 없으니 기하 검사만 신뢰한다.
2. **2차(보강)** — 1차 프로파일로 후보를 *읽어서* 라벨과 일치할 때만 채택하고,
   모든 채널·임계값에서 글리프와 외형 패치를 모은다. 채널마다 획 두께가 달라서,
   한 채널만 배운 프로파일은 다른 채널로 잘라낸 자기 글자를 낮은 신뢰도로 밀어낸다.

학습 후 leave-one-out 정확도를 재서 프로파일에 기록한다. 이 값이 낮으면
`TimerGlyphProfile.trusted` 가 사용을 거부한다(라벨이 오염된 학습을 막는다).
"""

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from boss_debuff_detector import (  # noqa: E402
    TimerGlyphProfile,
    appearance_patch,
    glyph_variants,
    normalize_glyph,
    read_image,
)
import cooldown_reader as cr  # noqa: E402

BOOTSTRAP_CHANNEL = "achro"
BOOTSTRAP_FRACTION = cr.SCORE_FRACTIONS[0]


def _layout_candidates(slot_bgr, channel, fraction):
    big = cr.upscale_slot(slot_bgr)
    score = cr.channel_score(big, channel)
    binary, threshold = cr.binarize(score, fraction)
    if threshold == 0:
        return score, None, []
    return score, binary, [layout for layout in cr.segment(binary)
                           if cr.layout_ok(binary, layout)]


def _learn(profile, binary, layout, label, score=None, channel=""):
    """한 후보의 글리프(와 외형 패치)를 프로파일에 넣는다."""
    text = f"{label:0{len(layout.digits)}d}"
    if len(text) != len(layout.digits):
        return 0
    added = 0
    for digit_char, box in zip(text, layout.digits):
        for glyph in glyph_variants(binary, box):
            added += int(profile.add_digit(int(digit_char), glyph))
        if score is not None:
            patch = appearance_patch(score, box)
            if patch is not None:
                profile.add_patch(int(digit_char), patch, channel)
    for glyph in glyph_variants(binary, layout.suffix):
        added += int(profile.add_suffix(glyph))
    if score is not None:
        patch = appearance_patch(score, layout.suffix)
        if patch is not None:
            profile.add_patch(None, patch, channel)
    return added


def train(sample_paths, profile_id=cr.DEFAULT_PROFILE_ID, output=None, verbose=True):
    labelled = []
    for path in sample_paths:
        label = cr.parse_sample_label(path)
        image = read_image(path)
        if image is None:
            continue
        labelled.append((path, label, image))

    profile = TimerGlyphProfile(profile_id=profile_id, text_height=12,
                               source="cooldown_samples")

    # --- 1차: achro 채널 + 자리수 일치 후보만 -------------------------------
    bootstrap_used = 0
    for path, label, image in labelled:
        if label is None:
            continue
        _, binary, layouts = _layout_candidates(image, BOOTSTRAP_CHANNEL, BOOTSTRAP_FRACTION)
        if binary is None:
            continue
        digits_expected = len(str(label))
        exact = [l for l in layouts if len(l.digits) == digits_expected]
        if len(exact) != 1:
            continue
        _learn(profile, binary, exact[0], label)
        bootstrap_used += 1
    if verbose:
        print(f"1차: {bootstrap_used}/{sum(1 for _, l, _ in labelled if l is not None)}장에서 "
              f"글리프 {len(profile.glyphs)}개, 접미사 {len(profile.suffix_glyphs)}개")

    if not profile.glyphs:
        raise SystemExit("1차 학습에서 글리프를 얻지 못했습니다. 분리 규칙을 확인하세요.")

    # --- 2차: 모든 채널에서 '읽어서 라벨과 맞는' 후보만 ---------------------
    refined = 0
    for path, label, image in labelled:
        if label is None:
            continue
        hit = False
        for channel in cr.CHANNELS:
            for fraction in cr.SCORE_FRACTIONS:
                score, binary, layouts = _layout_candidates(image, channel, fraction)
                if binary is None:
                    continue
                for layout in layouts:
                    value, confidence = cr._read_layout(binary, layout, profile)
                    if value != label:
                        continue
                    _learn(profile, binary, layout, label, score, channel)
                    hit = True
        refined += int(hit)
    if verbose:
        print(f"2차: {refined}장 보강 → 글리프 {len(profile.glyphs)}개, "
              f"접미사 {len(profile.suffix_glyphs)}개, 패치 {len(profile.patches)}개")

    kept = profile.compact_patches()
    profile.accuracy = cr.profile_accuracy(profile)
    if verbose:
        print(f"패치 정리: {kept}개 (글자x채널 평균)")
        print(f"숫자 커버리지: {profile.digit_coverage}")
        print(f"leave-one-out 정확도(상관 기준): {profile.accuracy:.4f}  "
              f"trusted={profile.trusted}")

    if output is not None:
        path = profile.save(Path(output))
        size = path.stat().st_size / 1024
        if verbose:
            print(f"저장: {path} ({size:.0f}KB)")
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=cr.samples_root())
    parser.add_argument("--only", default=None,
                        help="파일명 접두사 필터 (예: slotA)")
    parser.add_argument("--out", type=Path, default=None,
                        help="기본값: cooldown_assets/profiles/skill_cooldown.json")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않는다")
    args = parser.parse_args(argv)

    paths = cr.sample_paths(args.samples)
    if args.only:
        paths = [p for p in paths if p.name.startswith(args.only)]
    if not paths:
        raise SystemExit(f"샘플이 없습니다: {args.samples}")
    print(f"샘플 {len(paths)}장 ({args.samples})")

    output = None if args.dry_run else (args.out or cr.profile_path())
    train(paths, output=output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
