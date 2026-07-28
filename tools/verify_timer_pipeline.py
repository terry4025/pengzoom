"""수집된 타이머 ROI 샘플로 새 인식 파이프라인을 검증한다.

정답 라벨은 8배 확대 몬타주를 눈으로 읽어 확정한 값이다(1~60번 프레임).
사용법:
    py -3.14 tools/verify_timer_pipeline.py [샘플폴더]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import boss_debuff_detector as bd  # noqa: E402

# 첫 번째 캐스트: 19초부터 1초까지 0.5초 간격, 이후 0.9/0.4초(소수 표시)
FIRST_CAST = [19, 19, 18, 18, 17, 17, 16, 16, 15, 15, 14, 14, 13, 13, 12, 12,
              11, 11, 10, 10, 9, 9, 8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 1, 1]
SECOND_CAST = [19, 19, 18, 18, 17, 17, 16, 16, 15, 15, 14, 14, 13, 13, 12, 12,
               11, 11, 10, 10]

GROUND_TRUTH = {index: value for index, value in enumerate(FIRST_CAST, start=1)}
GROUND_TRUTH.update({38: 0.9, 39: 0.4})
GROUND_TRUTH.update({index: value for index, value in enumerate(SECOND_CAST, start=41)})


# 정답 라벨을 눈으로 확인한 원본 수집 세션. 이후 세션은 같은 순번을 다시 쓰므로
# 시각으로 한정해야 순번 -> 파일 대응이 깨지지 않는다.
GT_SESSION_MAX_HHMMSS = 203000


def load_index(root: Path, session_max: int = GT_SESSION_MAX_HHMMSS) -> dict[int, Path]:
    index = {}
    for path in sorted(root.glob("*.png")):
        parts = path.stem.split("_")
        if len(parts) < 3 or not parts[2].isdigit():
            continue
        if session_max is not None and len(parts) >= 2 and parts[1].isdigit():
            if int(parts[1]) > session_max:
                continue
        sequence = int(parts[2])
        if sequence in index:
            raise SystemExit(
                f"순번 {sequence} 이 중복됩니다: {index[sequence].name} vs {path.name}\n"
                "정답 라벨 표는 원본 수집 세션의 순번을 기준으로 하므로, "
                "세션 범위를 좁혀야 합니다.")
        index[sequence] = path
    return index


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else bd.user_data_root() / "samples" / bd.DEFAULT_DEBUFF_ID
    index = load_index(root)
    if not index:
        print(f"샘플이 없습니다: {root}")
        return 1

    seg_ok = seg_bad = 0
    dataset = []
    for seq, truth in sorted(GROUND_TRUTH.items()):
        path = index.get(seq)
        if path is None:
            continue
        image = bd.read_image(path)
        binary, _thr = bd.binarize_timer_text(image)
        suffix, digits = bd.segment_timer_glyphs(binary)
        decimal = bd.has_decimal_point(binary, suffix, digits)
        sub_second = float(truth) < 1.0
        if sub_second:
            good = suffix is not None and decimal
        else:
            good = suffix is not None and not decimal and len(digits) == len(str(int(truth)))
            if good:
                for char, box in zip(str(int(truth)), digits):
                    dataset.append((int(char), bd.normalize_glyph(binary, box), seq))
        seg_ok += good
        seg_bad += not good
        if not good:
            print(f"  세그먼테이션 실패 seq={seq} 정답={truth} "
                  f"글리프={len(digits)} 소수점={decimal}")

    print(f"세그먼테이션: {seg_ok}/{seg_ok + seg_bad}")

    features = np.asarray([bd.glyph_features(g) for _d, g, _s in dataset], np.float32)
    labels = np.asarray([d for d, _g, _s in dataset], np.int32)
    frames = np.asarray([s for _d, _g, s in dataset], np.int32)
    coverage = {int(d): int((labels == d).sum()) for d in sorted(set(labels.tolist()))}
    print(f"글리프 {len(dataset)}개, 숫자별 {coverage}")

    correct = 0
    for i in range(len(dataset)):
        keep = frames != frames[i]          # 같은 프레임에서 온 글리프는 제외
        distances = np.linalg.norm(features[keep] - features[i], axis=1)
        if not distances.size:
            continue
        correct += int(labels[keep][int(np.argmin(distances))] == labels[i])
    accuracy = correct / max(1, len(dataset))
    print(f"leave-one-frame-out 정확도: {correct}/{len(dataset)} = {accuracy:.3f}")
    return 0 if (accuracy >= 0.95 and seg_ok >= seg_ok + seg_bad - 2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
