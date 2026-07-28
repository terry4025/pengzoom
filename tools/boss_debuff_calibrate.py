"""Calibrate the 암흑 수류탄 timer-digit recognizer.

Two input shapes are accepted:

1. Timer-ROI crops already labelled by the app's sample collector
   (``%APPDATA%/PengZoom/boss_debuff/samples/dark_grenade/*_09s.png``)::

       py tools/boss_debuff_calibrate.py --samples <folder>

2. Full game screenshots whose file name carries the visible remaining time
   (``카멘_9s.png``, ``boss_12s.png`` ...).  The debuff cell is located with the
   bundled icon template and the timer ROI is cut out automatically::

       py tools/boss_debuff_calibrate.py --screenshots boss_debuff_assets/samples/screenshots

Add ``--report`` to only print what the current profile knows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import boss_debuff_detector as bdd  # noqa: E402


def report(debuff_id: str) -> None:
    profile = bdd.TimerGlyphProfile.load_for(debuff_id)
    missing = [d for d in range(10) if d not in profile.digit_coverage]
    print(f"프로파일: {profile.profile_id} (source={profile.source}, 글자높이={profile.text_height}px)")
    print(f"  학습된 숫자: {profile.digit_coverage}")
    print(f"  부족한 숫자: {missing}")
    print(f"  숫자 표시 사용 가능: {'예' if profile.trusted else '아니오 (지속시간 추정만 사용)'}")


def extract_from_screenshots(paths: list[Path], debuff_id: str, out_dir: Path,
                             search_bottom_ratio: float, threshold: float) -> list[Path]:
    """Cut the timer ROI out of full screenshots, keeping the original label."""
    templates = bdd.load_icon_templates(debuff_id)
    if not templates:
        raise SystemExit("아이콘 템플릿이 없습니다: boss_debuff_assets/icons 를 확인해 주세요.")
    out_dir.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []
    for path in paths:
        label = bdd.parse_sample_label(path)
        image = bdd.read_image(path)
        if image is None:
            print(f"  skip {path.name}: 이미지를 읽을 수 없음")
            continue
        if label is None:
            print(f"  skip {path.name}: 파일명에 남은 초가 없습니다 (예: 카멘_9s.png)")
            continue
        # Search only the upper part of the frame: the identical item icon also
        # sits in the bottom-right battle-item hotkey bar.
        limit = max(60, int(image.shape[0] * search_bottom_ratio))
        gray = cv2.cvtColor(image[:limit], cv2.COLOR_BGR2GRAY)
        match = bdd.match_icon(gray, templates)
        if match is None or match.score < threshold:
            print(f"  skip {path.name}: 아이콘 미검출 (최고 일치율 "
                  f"{match.score if match else 0:.2f} < {threshold:.2f})")
            continue
        x, y, w, h = bdd.digit_roi_from_cell(match.x, match.y, match.size, match.size)
        x0, y0 = max(0, x), max(0, y)
        roi = image[y0:min(image.shape[0], y + h), x0:min(image.shape[1], x + w)]
        target = out_dir / f"{path.stem}_{label:02d}s.png"
        if bdd.write_image(target, roi):
            produced.append(target)
            print(f"  ok   {path.name}: 셀({match.x},{match.y},{match.size}) "
                  f"일치율 {match.score:.2f} -> {target.name}")
    return produced


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, help="라벨된 타이머 ROI 크롭 폴더")
    parser.add_argument("--screenshots", type=Path, help="전체 스크린샷 폴더")
    parser.add_argument("--debuff-id", default=bdd.DEFAULT_DEBUFF_ID)
    parser.add_argument("--threshold", type=float, default=bdd.DEFAULT_MATCH_THRESHOLD)
    parser.add_argument("--search-bottom-ratio", type=float, default=0.45,
                        help="스크린샷에서 아이콘을 찾을 상단 비율 (기본 0.45)")
    parser.add_argument("--output", type=Path, default=None, help="프로파일 저장 경로")
    parser.add_argument("--bundle", action="store_true",
                        help="사용자 폴더가 아니라 boss_debuff_assets 에 저장")
    parser.add_argument("--fresh", action="store_true", help="기존 글리프를 버리고 새로 학습")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report or (not args.samples and not args.screenshots):
        report(args.debuff_id)
        return 0

    crops: list[Path] = []
    if args.screenshots:
        shots = sorted(p for p in args.screenshots.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
        if not shots:
            print(f"스크린샷을 찾지 못했습니다: {args.screenshots}")
        else:
            print(f"스크린샷 {len(shots)}장에서 타이머 영역 추출:")
            crops += extract_from_screenshots(
                shots, args.debuff_id,
                args.screenshots / "_timer_roi", args.search_bottom_ratio, args.threshold,
            )
    if args.samples:
        crops += sorted(args.samples.glob("*.png"))

    if not crops:
        print("학습할 이미지가 없습니다.")
        return 1

    output = args.output
    if output is None and args.bundle:
        output = ROOT / "boss_debuff_assets" / "timer_profiles" / f"{args.debuff_id}.json"
    base = bdd.TimerGlyphProfile(profile_id=args.debuff_id) if args.fresh else None
    result = bdd.train_timer_profile(crops, args.debuff_id, base_profile=base, output_path=output)

    print(f"\n이미지 {result['used_images']}장 사용 · 글리프 {result['added_glyphs']}개 추가")
    print(f"학습된 숫자: {result['digits']}")
    if result["missing_digits"]:
        print(f"부족한 숫자: {result['missing_digits']} -> 해당 숫자가 보이는 표본을 더 넣어 주세요.")
    for line in result["skipped"]:
        print(f"  skip {line}")
    print(f"저장 위치: {result['output']}")
    print(f"숫자 표시 사용 가능: {'예' if result['trusted'] else '아니오'}")
    return 0 if result["used_images"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
