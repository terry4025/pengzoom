"""One-shot bootstrap that turns the reference screenshots into bundled assets.

Run this only when a new reference screenshot arrives.  Normal calibration goes
through ``tools/boss_debuff_calibrate.py`` instead.

Usage:
    py tools/bootstrap_boss_debuff_assets.py <screenshot.png> <cell_x> <cell_y> <cell_size>
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from boss_debuff_detector import (  # noqa: E402
    DEFAULT_DEBUFF_ID,
    TimerGlyphProfile,
    binarize_timer_text,
    digit_roi_from_cell,
    normalize_glyph,
    segment_timer_glyphs,
)

ASSETS = ROOT / "boss_debuff_assets"


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"이미지를 읽을 수 없습니다: {path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise SystemExit(f"PNG 인코딩 실패: {path}")
    buf.tofile(str(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("cell_x", type=int)
    parser.add_argument("cell_y", type=int)
    parser.add_argument("cell_size", type=int)
    parser.add_argument("--label", type=int, default=None,
                        help="화면에 보이는 남은 초 (글리프 학습용)")
    parser.add_argument("--debuff-id", default=DEFAULT_DEBUFF_ID)
    args = parser.parse_args()

    shot = read_image(args.screenshot)
    x, y, size = args.cell_x, args.cell_y, args.cell_size
    cell = shot[y:y + size, x:x + size]
    if cell.shape[0] != size or cell.shape[1] != size:
        raise SystemExit("셀 좌표가 이미지 범위를 벗어났습니다.")

    icon_dir = ASSETS / "icons" / args.debuff_id
    write_image(icon_dir / f"ingame_cell_{size}.png", cell)
    # Only the full cell (icon art + 1px debuff border) is used for matching so
    # the matched rectangle always means the same thing when the timer ROI is
    # derived from it.  The art-only crop is kept for reference/debugging.
    write_image(ASSETS / "reference" / f"{args.debuff_id}_art_{size - 2}.png", cell[1:-1, 1:-1])
    print(f"[icon] {icon_dir / f'ingame_cell_{size}.png'}  ({size}x{size})")

    dx, dy, dw, dh = digit_roi_from_cell(x, y, size, size)
    dx0, dy0 = max(0, dx), max(0, dy)
    digit_bgr = shot[dy0:dy0 + dh, dx0:dx0 + dw]
    write_image(ASSETS / "samples" / f"timer_roi_{args.label or 'unknown'}s.png", digit_bgr)
    print(f"[timer roi] x={dx} y={dy} w={dw} h={dh}")

    binary, _ = binarize_timer_text(digit_bgr)
    suffix_box, digit_boxes = segment_timer_glyphs(binary)
    print(f"[segment] suffix={suffix_box} digits={digit_boxes}")
    if suffix_box is None or not digit_boxes:
        print("!! 글리프 분할 실패 - 좌표나 배율을 확인해 주세요.")
        return 1

    profile_path = ASSETS / "timer_profiles" / f"{args.debuff_id}.json"
    profile = TimerGlyphProfile.load(profile_path) or TimerGlyphProfile(
        profile_id=args.debuff_id, text_height=int(suffix_box[3])
    )

    if args.label is not None:
        text = str(args.label)
        if len(text) != len(digit_boxes):
            print(f"!! 라벨 자릿수({len(text)})와 검출 글리프 수({len(digit_boxes)})가 다릅니다.")
            return 1
        for char, box in zip(text, digit_boxes):
            profile.add_digit(int(char), normalize_glyph(binary, box))
    profile.add_suffix(normalize_glyph(binary, suffix_box))
    profile.text_height = int(suffix_box[3])
    profile.source = f"bootstrap:{args.screenshot.name}"
    profile.save(profile_path)
    print(f"[profile] {profile_path} digits={sorted(set(profile.labels))} "
          f"glyphs={len(profile.glyphs)} suffixes={len(profile.suffix_glyphs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
