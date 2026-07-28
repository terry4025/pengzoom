"""임시: 적대 배경에서 실제로 어떤 이진 이미지가 나오는지 눈으로 본다."""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import boss_debuff_detector as bd
import eval_timer_robustness as ev

VERIFIED = ROOT / "boss_debuff_assets" / "samples" / "verified"
name = sys.argv[1] if len(sys.argv) > 1 else "dark_grenade_023_08s.png"
image0 = bd.read_image(VERIFIED / name)

rows = []
for background in ("원본", "차가운 파랑", "따뜻한 주황", "글자색과 유사한 살몬"):
    image = image0 if background == "원본" else ev.composite(image0, background)
    big = bd.upscale_roi(image)
    panels = [big]
    for mode in ("warm", "bright"):
        score = bd.timer_score(big, mode)
        peak = int(score.max())
        thr = max(10, int(round(peak * 0.42)))
        binary = (score >= thr).astype(np.uint8) * 255
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        panels.append(cv2.cvtColor(cv2.normalize(score, None, 0, 255, cv2.NORM_MINMAX),
                                   cv2.COLOR_GRAY2BGR))
        panels.append(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))
    rows.append(np.hstack(panels))

grid = np.vstack(rows)
bd.write_image(Path("tools/_adv.png"), grid)
print("tools/_adv.png", grid.shape, "행=원본/파랑/주황/살몬, 열=이미지 warm점수 warm이진 bright점수 bright이진")
