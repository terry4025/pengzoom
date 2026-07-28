"""타이머 숫자 인식을 실측 프레임으로 평가한다.

평가 세트는 두 갈래다.

* 검증 프레임(boss_debuff_assets/samples/verified): 8배 확대 이미지를 눈으로 읽어
  라벨을 확정한 57장. 파란 계열 배경.
* 사용자 수집 프레임: '소멸 시점 역산' 라벨링이 들어간 이후(21:00~)의 파일만 쓴다.
  이 라벨은 캐스트 전체의 카운트다운 정렬 점수를 통과해야 기록되므로 신뢰할 수
  있다. 배경의 warm(R-B) 값으로 안전/적대 그룹으로 나눈다. 글자 자체의 warm 값이
  약 105이므로, 배경이 그 값에 가까울수록 분리가 어렵다.

실행:
    py -3.14 tools/eval_timer_robustness.py
"""
import re
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import boss_debuff_detector as bd  # noqa: E402

VERIFIED = ROOT / "boss_debuff_assets" / "samples" / "verified"
# 이 시각 이전 파일은 옛 자기참조 라벨링 결과라 라벨을 믿을 수 없다.
TRUSTED_AFTER_HHMMSS = 210000
HOSTILE_WARM = 20.0


def background_warm(roi_bgr: np.ndarray) -> float:
    """글자 획을 뺀 배경의 warm(R-B) 중앙값."""
    channels = roi_bgr.astype(np.int16)
    warm = np.clip(channels[:, :, 2] - channels[:, :, 0], 0, 255).astype(np.uint8)
    score = cv2.morphologyEx(warm, cv2.MORPH_TOPHAT,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    text = cv2.dilate((score >= max(10, int(score.max() * 0.35))).astype(np.uint8),
                      np.ones((3, 3), np.uint8))
    pixels = roi_bgr[text == 0]
    if pixels.size == 0:
        return -255.0
    median = np.median(pixels.reshape(-1, 3), axis=0)
    return float(median[2] - median[0])


def load_user_frames(root: Path):
    """(이미지, 라벨, 배경warm) 목록. 라벨을 믿을 수 있는 파일만."""
    frames = []
    for path in sorted(root.glob("*.png")):
        stamp = re.match(r"\d{8}_(\d{6})_", path.name)
        label = bd.parse_sample_label(path)
        if not stamp or label is None:
            continue
        if int(stamp.group(1)) < TRUSTED_AFTER_HHMMSS:
            continue
        image = bd.read_image(path)
        if image is None:
            continue
        frames.append((image, label, background_warm(image), path.name))
    return frames


def load_user_casts(root: Path):
    """캐스트별 프레임 목록. 라벨은 캐스트마다 1초 어긋날 수 있어 참고용이다.

    한 캐스트는 소멸 시점에 한꺼번에 기록되므로 파일 시각이 거의 같고 순번이
    이어진다.
    """
    entries = []
    for path in sorted(root.glob("*.png")):
        match = re.match(r"(\d{8})_(\d{6})_(\d{5})_(\d{1,3})s\.png$", path.name)
        if not match:
            continue
        if int(match.group(2)) < TRUSTED_AFTER_HHMMSS:
            continue
        entries.append((int(match.group(2)), int(match.group(3)), path,
                        int(match.group(4))))
    entries.sort()

    casts, current = [], []
    for stamp, sequence, path, label in entries:
        if current:
            prev_stamp, prev_seq = current[-1][0], current[-1][1]
            if sequence != prev_seq + 1 or abs(stamp - prev_stamp) > 3:
                casts.append(current)
                current = []
        current.append((stamp, sequence, path, label))
    if current:
        casts.append(current)
    return [[(path, label) for _s, _q, path, label in cast]
            for cast in casts if len(cast) >= 6]


def consistency_report(casts, profile, reader):
    """라벨 없이 판정한다: 한 캐스트 안에서 읽은 값은 1초씩 단조 감소해야 한다."""
    frames = read = steps = violations = 0
    hostile_frames = hostile_read = 0
    for cast in casts:
        values = []
        for path, _label in cast:
            image = bd.read_image(path)
            if image is None:
                continue
            frames += 1
            warm = background_warm(image)
            if warm >= HOSTILE_WARM:
                hostile_frames += 1
            value = reader(image, profile)
            if value is not None:
                read += 1
                if warm >= HOSTILE_WARM:
                    hostile_read += 1
            values.append(value)
        previous = None
        for value in values:
            if value is None:
                continue
            if previous is not None:
                steps += 1
                if not (0 <= previous - value <= 1):
                    violations += 1
            previous = value
    return {"frames": frames, "read": read, "steps": steps, "violations": violations,
            "hostile_frames": hostile_frames, "hostile_read": hostile_read}


def read_current(image, profile):
    binary, _ = bd.binarize_timer_text(image)
    suffix, digits = bd.segment_timer_glyphs(binary)
    if suffix is None or not digits or bd.has_decimal_point(binary, suffix, digits):
        return None
    seconds, _confidence = profile.read_seconds(binary, digits)
    return seconds


def read_new(image, profile):
    return bd.read_timer_value(image, profile).value


def measure(pairs, profile, reader):
    read = correct = 0
    wrong = []
    for image, label, *_rest in pairs:
        value = reader(image, profile)
        if value is None:
            continue
        read += 1
        if value == label:
            correct += 1
        else:
            wrong.append((label, value))
    return {"total": len(pairs), "read": read, "correct": correct, "wrong": wrong}


def report(title, stats, show_wrong=False):
    total, read, correct = stats["total"], stats["read"], stats["correct"]
    print(f"  {title:<10} 읽음 {read:>4}/{total:<4} ({read / max(1, total):6.1%})  "
          f"정확 {correct:>4} ({correct / max(1, total):6.1%})  "
          f"오독 {len(stats['wrong'])}")
    if show_wrong and stats["wrong"]:
        print(f"             오독 예: {stats['wrong'][:8]}")


def main() -> int:
    profile = bd.TimerGlyphProfile.load_for(bd.DEFAULT_DEBUFF_ID)
    print(f"프로파일: 숫자 {profile.digit_coverage} 정확도 {profile.accuracy} "
          f"신뢰 {profile.trusted} 글리프 {len(profile.glyphs)}")
    readers = [("현재", read_current), ("신규", read_new)]
    label_shift = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if label_shift:
        print(f"(라벨 보정 {label_shift:+d} 적용)")

    verified = []
    for path in sorted(VERIFIED.glob("*.png")):
        label = bd.parse_sample_label(path)
        image = bd.read_image(path)
        if image is not None and label is not None:
            verified.append((image, label))
    print(f"\n[검증 프레임] {len(verified)}장 · 눈으로 라벨 확인")
    for name, reader in readers:
        report(name, measure(verified, profile, reader))

    frames = load_user_frames(bd.user_data_root() / "samples" / bd.DEFAULT_DEBUFF_ID)
    frames = [(image, label + label_shift, warm, name) for image, label, warm, name in frames]
    safe = [f for f in frames if f[2] < HOSTILE_WARM]
    hostile = [f for f in frames if f[2] >= HOSTILE_WARM]
    print(f"\n[사용자 수집] 신뢰 라벨 {len(frames)}장 "
          f"(안전 {len(safe)} / 적대 {len(hostile)})")
    if safe:
        print(f"  -- 안전 배경 (warm < {HOSTILE_WARM:.0f})")
        for name, reader in readers:
            report(name, measure(safe, profile, reader))
    if hostile:
        warms = [f[2] for f in hostile]
        print(f"  -- 적대 배경 (warm {min(warms):.0f}~{max(warms):.0f}, "
              f"글자 warm 은 약 105)")
        for name, reader in readers:
            report(name, measure(hostile, profile, reader), show_wrong=True)

    casts = load_user_casts(bd.user_data_root() / "samples" / bd.DEFAULT_DEBUFF_ID)
    print(f"\n[캐스트 단조성] 캐스트 {len(casts)}개 · 라벨을 쓰지 않는 판정")
    print("   한 캐스트 안에서 읽은 값은 0 또는 1초씩만 줄어야 한다.")
    for name, reader in readers:
        stats = consistency_report(casts, profile, reader)
        print(f"  {name:<10} 읽음 {stats['read']:>4}/{stats['frames']:<4} "
              f"({stats['read'] / max(1, stats['frames']):6.1%})  "
              f"적대배경 읽음 {stats['hostile_read']:>3}/{stats['hostile_frames']:<3} "
              f"({stats['hostile_read'] / max(1, stats['hostile_frames']):6.1%})  "
              f"모순 {stats['violations']}/{stats['steps']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
