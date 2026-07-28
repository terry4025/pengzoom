"""임시: 따뜻한 배경에서 각 채널이 어떻게 실패하는지 본다."""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import boss_debuff_detector as bd
sys.path.insert(0, str(ROOT / "tools"))
import eval_timer_robustness as ev

VERIFIED = ROOT / "boss_debuff_assets" / "samples" / "verified"
paths = sorted(VERIFIED.glob("*.png"))
target = [p for p in paths if p.name.endswith("_08s.png")][:1] + \
         [p for p in paths if p.name.endswith("_17s.png")][:1]

for background in ("따뜻한 주황", "글자색과 유사한 살몬", "용암 붉은색"):
    print(f"===== {background}")
    for path in target:
        image = ev.composite(bd.read_image(path), background)
        big = bd.upscale_roi(image)
        print(f"  {path.name}")
        rows = []
        for mode in bd.TIMER_SCORE_MODES:
            score = bd.timer_score(big, mode)
            peak = int(score.max())
            for fraction in bd.TIMER_SCORE_FRACTIONS:
                thr = max(10, int(round(peak * fraction)))
                binary = (score >= thr).astype(np.uint8) * 255
                binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
                ink = np.count_nonzero(binary) / binary.size
                suffix, digits = bd.segment_timer_glyphs(binary)
                gate = bd.glyph_layout_ok(binary, suffix, digits)
                rows.append(f"    {mode:7s} f={fraction:.2f} peak={peak:3d} ink={ink:.2f} "
                            f"suffix={'Y' if suffix else 'N'} digits={len(digits)} gate={gate}")
        print("\n".join(rows))
