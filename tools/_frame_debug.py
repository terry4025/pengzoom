"""임시: 특정 프레임에서 가설이 왜 라벨과 안 맞는지 본다."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import boss_debuff_detector as bd

VERIFIED = ROOT / "boss_debuff_assets" / "samples" / "verified"
names = [n for n in sys.argv[1:]] or ["dark_grenade_059_10s.png", "dark_grenade_023_08s.png"]
for name in names:
    path = VERIFIED / name
    image = bd.read_image(path)
    label = bd.parse_sample_label(path)
    print(f"--- {name} label={label}")
    big = bd.upscale_roi(image)
    for mode in bd.TIMER_SCORE_MODES:
        score = bd.timer_score(big, mode)
        peak = int(score.max())
        for fraction in bd.TIMER_SCORE_FRACTIONS:
            import cv2
            thr = max(10, int(round(peak * fraction)))
            binary = (score >= thr).astype(np.uint8) * 255
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
            suffix, digits = bd.segment_timer_glyphs(binary)
            gate = bd.glyph_layout_ok(binary, suffix, digits)
            ink = np.count_nonzero(binary) / binary.size
            detail = ""
            if suffix and digits:
                detail = (f"sh={suffix[3]} widths={[b[2] for b in digits]} "
                          f"heights={[b[3] for b in digits]} "
                          f"baselines={[b[1] + b[3] for b in digits]} sbase={suffix[1] + suffix[3]}")
            print(f"  {mode:7s} f={fraction:.2f} ink={ink:.2f} digits={len(digits)} "
                  f"gate={gate} {detail}")
