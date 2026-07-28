"""임시: 레이아웃 게이트가 정상 프레임을 왜 거르는지 본다."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import boss_debuff_detector as bd

VERIFIED = ROOT / "boss_debuff_assets" / "samples" / "verified"


def why(binary, suffix, digits):
    if suffix is None or not digits:
        return "no-suffix-or-digits"
    h, w = binary.shape[:2]
    ink = float(np.count_nonzero(binary)) / float(h * w)
    if ink > 0.32:
        return f"ink={ink:.2f}"
    sx, sy, sw, sh = suffix
    widths = [b[2] for b in digits]
    if sw < 1.15 * float(np.median(widths)):
        return f"suffix-narrow sw={sw} med={np.median(widths)}"
    base = sy + sh
    for x, y, bw, bh in digits:
        if not (0.70 * sh <= bh <= 1.30 * sh):
            return f"height bh={bh} sh={sh}"
        if abs((y + bh) - base) > 0.28 * sh:
            return f"baseline {y + bh} vs {base} sh={sh}"
        crop = binary[max(0, y):y + bh, max(0, x):x + bw]
        fill = float(np.count_nonzero(crop)) / float(max(1, crop.size))
        if not (0.18 <= fill <= 0.90):
            return f"fill={fill:.2f}"
    return "OK"


counts = {}
for path in sorted(VERIFIED.glob("*.png")):
    label = bd.parse_sample_label(path)
    image = bd.read_image(path)
    binary, thr = bd.binarize_timer_text(image)          # 기준선과 같은 조건
    suffix, digits = bd.segment_timer_glyphs(binary)
    reason = why(binary, suffix, digits)
    counts[reason] = counts.get(reason, 0) + 1
    if reason != "OK":
        print(f"{path.name} label={label} thr={thr} -> {reason}")
print(counts)
