"""수집된 샘플의 배경색 분포를 본다. 실제 적대 배경 프레임이 있는지 확인용."""
import re
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import boss_debuff_detector as bd


def background_stats(roi_bgr):
    """글자 획을 뺀 배경의 중앙 색과 warm(R-B) 값."""
    channels = roi_bgr.astype(np.int16)
    warm = np.clip(channels[:, :, 2] - channels[:, :, 0], 0, 255).astype(np.uint8)
    score = cv2.morphologyEx(warm, cv2.MORPH_TOPHAT,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    text = cv2.dilate((score >= max(10, int(score.max() * 0.35))).astype(np.uint8),
                      np.ones((3, 3), np.uint8))
    pixels = roi_bgr[text == 0]
    if pixels.size == 0:
        return None
    median = np.median(pixels.reshape(-1, 3), axis=0)
    return median, float(median[2] - median[0])


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        bd.user_data_root() / "samples" / bd.DEFAULT_DEBUFF_ID
    buckets = Counter()
    rows = []
    for path in sorted(root.glob("*.png")):
        image = bd.read_image(path)
        if image is None:
            continue
        stats = background_stats(image)
        if stats is None:
            continue
        median, warm = stats
        session = re.match(r"\d{8}_(\d{2})(\d{2})", path.name)
        key = f"{session.group(1)}:{session.group(2)[0]}0" if session else "??"
        rows.append((key, warm, median))
        # 글자 warm 값은 약 105. 배경 warm 이 이에 가까우면 적대적이다.
        if warm >= 60:
            buckets[(key, "적대(warm>=60)")] += 1
        elif warm >= 20:
            buckets[(key, "주의(20~60)")] += 1
        else:
            buckets[(key, "안전(<20)")] += 1
    for key in sorted({k for k, _ in buckets}):
        parts = {label: buckets[(key, label)] for _, label in
                 [(key, "안전(<20)"), (key, "주의(20~60)"), (key, "적대(warm>=60)")]}
        print(f"{key}  {parts}")
    warms = [warm for _key, warm, _m in rows]
    print(f"\n전체 {len(rows)}장 · 배경 warm(R-B) 최소 {min(warms):.0f} "
          f"중앙 {np.median(warms):.0f} 최대 {max(warms):.0f}")
    hostile = [(k, w, m) for k, w, m in rows if w >= 60]
    print(f"적대 프레임 {len(hostile)}장")
    for key, warm, median in hostile[:10]:
        print(f"   {key} warm={warm:.0f} bgr={median.astype(int).tolist()}")


if __name__ == "__main__":
    main()
