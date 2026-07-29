"""스킬 슬롯의 남은 쿨타임 숫자(`Ns`)를 읽는다.

## 왜 새 판독기인가
v2.46 에서 은퇴한 `cooldown_ocr` 는 세 가지 이유로 스킬마다 결과가 달랐다.

1. **슬롯 전체를 프로파일 크기로 리사이즈**했다. 사용자가 드래그한 ROI는 실측
   42x39~48x49 로 제각각이라, 가로세로가 다른 비율로 늘어나 글자가 찌그러지고
   HOG 특징이 어긋났다.
2. **단일 채널 + 고정 임계값 스윕**(`gray>=145..190 & S<=145`)이었다. 배경 밝기
   V가 233~255까지 오르는 밝은 아이콘에서는 밝기만으로 글자를 가를 수 없다.
3. **분리 실패 시 대안이 없었다.** 실측에서 밝은 주황 아이콘 3/10이 여기서
   탈락했다(오독은 아니지만 값을 얻지 못한다).

## 배경은 학습할 수 없다
스킬 아이콘은 직업·단축키마다 다르므로 배경을 표본으로 모으는 것은 불가능하다.
대신 배경과 무관하게 성립하는 성질만 쓴다(실측 41장).

| 성질 | 실측값 |
|---|---|
| 획 밝기 | V 218~239 (배경과 무관하게 일정) |
| 획 채도 | S 0~8 (거의 무채색) |
| 숫자 높이 | 12~13px, `s` 9px |
| 베이스라인 | 숫자와 `s` 의 아랫변이 1px 안에서 일치 |
| `s` 위치 | 항상 글자열 맨 오른쪽 |

배경은 두 부류로만 갈린다: 어두운 회색조(V 26~80, S 23) 또는 고채도(S 152~188).
어느 쪽도 '밝고 무채색'이 아니므로 그 결합이 1차 단서가 된다. 흰색·연회색
아이콘처럼 그 결합마저 통하지 않는 경우를 위해 밝기 top-hat / bottom-hat 채널을
함께 본다(보스 디버프 타이머에서 설원 보스방을 잡던 것과 같은 구조).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np

from boss_debuff_detector import (
    GLYPH_SIZE,
    TimerGlyphProfile,
    appearance_patch,
    glyph_features,
    normalize_glyph,
)

# --- 기하 상수 (모두 '글자 높이' 기준 비율 또는 원본 픽셀) -------------------
UPSCALE = 3                  # 12px 글자를 36px로 키워 분리를 안정화한다
TOPHAT_KERNEL = (5, 5)       # 원본 픽셀 기준. 획 두께(2px)의 2~3배.
                             # 글자 높이만큼 크게 잡으면(13px) 밝은 배경에서
                             # 글자 주변 그림자가 기준이 되어 배경이 획으로
                             # 뒤집힌다. 실측: 커널 13 → 실측 정확 75%,
                             # 커널 5 → 95%.
MIN_PEAK = 14                # 이보다 약하면 글자가 없는 프레임이다
SCORE_FRACTIONS = (0.45, 0.34, 0.58)

# 슬롯 높이에 대한 글자 높이 비율. 실측 12/49 ~ 13/37 = 0.24~0.35 이므로
# 여유를 둬 UI 배율·ROI 크기 변화를 흡수한다.
MIN_TEXT_RATIO = 0.14
MAX_TEXT_RATIO = 0.45
MIN_TEXT_PX = 5              # 원본 픽셀. 이보다 작으면 글리프로 정규화해도 못 읽는다

# 배치 검사 허용치 (업스케일된 픽셀 기준으로 환산해서 쓴다)
BASELINE_SLACK = 0.22        # * 글자 높이. 실측 편차는 1px(=0.08)
SUFFIX_HEIGHT_RANGE = (0.55, 0.95)   # * 숫자 높이. 실측 9/12 = 0.75
# 실측 's' 폭은 숫자 높이의 0.46~0.50. 상한을 두지 않으면 `4s` 처럼 앞 숫자와
# 붙어 버린 덩어리를 접미사로 받아들여 `14s` 를 `1s` 로 읽는다.
SUFFIX_WIDTH_RANGE = (0.28, 0.72)
DIGIT_WIDTH_RANGE = (0.12, 0.95)     # * 숫자 높이. '1' 은 3/12 = 0.25, '0' 은 8/12
DIGIT_GAP_LIMIT = 0.95       # * 숫자 높이. 이보다 벌어지면 다른 글자열이다
MAX_DIGITS = 3               # 999s 까지 (1분 넘는 스킬은 표기 형식 미확인)

# 실측(41장, 전 채널)으로 잰 글자 간격과 왼쪽 여백 잉크량.
#   pitch/h  p5 0.589  중앙 0.732  p95 0.825
#   gap/h    p5 0.059  중앙 0.184  p95 0.413
#   왼쪽 띠 잉크 밀도  중앙 0.000  p95 0.070
DIGIT_PITCH_RANGE = (0.50, 0.98)
# 마지막 숫자 왼쪽 끝에서 's' 왼쪽 끝까지의 거리. 실측 정답은 0.61~0.94.
# 이 값이 짧으면 숫자 하나가 통째로 지워진 뒤 그 자리를 's' 가 메운 후보다
# (`14s` 를 `1s` 로 읽던 실패).
SUFFIX_ADVANCE_RANGE = (0.55, 1.10)
LEFT_STRIP_WIDTH = 0.85      # * 숫자 높이. 앞자리 하나가 들어갈 폭
LEFT_STRIP_MAX_INK = 0.14    # 이보다 진하면 앞자리를 놓친 후보다
# 이진화가 앞자리를 아예 지워 버리면 잉크 검사로는 잡히지 않는다. 그 띠만 훨씬
# 낮은 임계값으로 다시 보고, 남은 덩어리가 숫자 모양이고 같은 베이스라인에 서
# 있으면 앞자리를 놓친 것으로 판정한다.
LEFT_STRIP_LOW_FRACTION = 0.22

CHANNELS = ("achro", "bright", "dark", "median_pos", "median_neg")
MEDIAN_KERNEL = 5            # 원본 픽셀. 얇은 획을 무시하는 배경 추정용

# 글리프 판정은 HOG 최근접이 아니라 **평균 스텐실과의 정규화 상관**으로 한다.
# 실측: slotA 로 배운 모양과 slotB 글자의 HOG 거리는 정답이어도 4.5~5.0 으로,
# 보스 타이머의 채택 상한(3.2)을 넘어 전부 거부됐다. 같은 쌍을 상관으로 보면
# 정답 0.90~0.99, 2등 0.63~0.75 로 확실히 갈린다. HOG는 획 두께와 안티에일리어싱
# 차이에 민감한데, 배경이 매번 다른 스킬 아이콘에서는 그 차이가 항상 생긴다.
MIN_GLYPH_NCC = 0.78         # 정답 상관 하한
MIN_GLYPH_MARGIN = 0.06      # 1등과 2등의 차이 하한
MIN_SUFFIX_NCC = 0.85        # 's' 모양 확인 하한. 실측 정답은 0.90~0.97,
                             # 숫자 하나를 접미사로 착각한 후보는 그 아래로 떨어진다
NCC_BLUR_SIGMA = 0.9         # 획 두께 차이를 흡수하는 정도
NCC_SHIFTS = (-1, 0, 1)      # 정규화 캔버스에서 1px 어긋남까지 허용

MIN_CONFIDENCE = 0.62        # 최종 신뢰도 하한
# 한 프레임 안에서 채널 x 임계값 조합이 9가지 나온다. 그중 **두 가지 이상이 같은
# 값을 낼 때만** 채택한다(신뢰도가 아주 높은 경우는 예외). 배경 무늬가 만든
# 우연한 후보는 다른 조합에서 재현되지 않는다. 실측 합성 배경에서 이 규칙만으로
# 오독 2건이 0건이 됐다.
MIN_AGREEMENT = 2
HIGH_CONFIDENCE = 0.90       # 단독 후보라도 채택하는 신뢰도
# 한 값이 이만큼 재현되면 남은 채널은 보지 않는다(비용 절감). 어두운 아이콘은
# 첫 채널에서 끝난다.
SETTLED_AGREEMENT = 3
SETTLED_CONFIDENCE = 0.80

PROFILE_VERSION = 1
DEFAULT_PROFILE_ID = "skill_cooldown"


def assets_root() -> Path:
    import sys

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "cooldown_assets"


def profile_path(profile_id: str = DEFAULT_PROFILE_ID) -> Path:
    return assets_root() / "profiles" / f"{profile_id}.json"


def samples_root() -> Path:
    return Path(__file__).resolve().parent / "cooldown_assets" / "samples"


_PROFILE_CACHE: dict[str, Optional[TimerGlyphProfile]] = {}


def load_profile(profile_id: str = DEFAULT_PROFILE_ID) -> Optional[TimerGlyphProfile]:
    """번들된 글리프 프로파일. 없거나 신뢰도가 낮으면 None.

    한 번 읽어 캐시한다. 읽기 실패나 미학습 프로파일은 None 으로 캐시해서
    스캔 루프가 매 프레임 파일을 두드리지 않게 한다.
    """
    if profile_id in _PROFILE_CACHE:
        return _PROFILE_CACHE[profile_id]
    profile = TimerGlyphProfile.load(profile_path(profile_id))
    if profile is not None and not profile.trusted:
        profile = None
    _PROFILE_CACHE[profile_id] = profile
    return profile


def reload_profile(profile_id: str = DEFAULT_PROFILE_ID) -> Optional[TimerGlyphProfile]:
    _PROFILE_CACHE.pop(profile_id, None)
    _STENCIL_CACHE.clear()
    return load_profile(profile_id)


# --- 채널 --------------------------------------------------------------------
def _tophat_kernel(upscale: int) -> np.ndarray:
    return cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(3, TOPHAT_KERNEL[0] * upscale), max(3, TOPHAT_KERNEL[1] * upscale)))


def upscale_slot(image_bgr: np.ndarray, upscale: int = UPSCALE) -> np.ndarray:
    upscale = max(1, int(upscale))
    if upscale == 1:
        return image_bgr
    return cv2.resize(image_bgr, None, fx=upscale, fy=upscale,
                      interpolation=cv2.INTER_CUBIC)


def channel_score(big_bgr: np.ndarray, mode: str, upscale: int = UPSCALE) -> np.ndarray:
    """업스케일된 슬롯에서 글자 획만 남기는 점수 이미지.

    한 채널로는 모든 아이콘을 덮을 수 없다.
      achro  : 밝고 무채색. 어두운 아이콘과 고채도 아이콘 모두에서 가장 강하다.
      bright : 밝기 top-hat. 배경에 질감이 있어 achro 가 흔들릴 때 받쳐 준다.
      dark   : 밝기 bottom-hat. 흰색·연회색 아이콘에서는 글자가 배경보다 어둡다.
    """
    kernel = _tophat_kernel(upscale)
    if big_bgr.ndim == 2:
        gray = big_bgr
        hsv = None
    else:
        gray = cv2.cvtColor(big_bgr, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(big_bgr, cv2.COLOR_BGR2HSV)

    if mode == "achro":
        if hsv is None:
            base = gray
        else:
            value = hsv[:, :, 2].astype(np.int16)
            sat = hsv[:, :, 1].astype(np.int16)
            # 채도가 높을수록 감점. 실측 글자 S<=8, 배경 S 23~188.
            base = np.clip(value - sat * 3, 0, 255).astype(np.uint8)
        return cv2.morphologyEx(base, cv2.MORPH_TOPHAT, kernel)
    if mode == "bright":
        return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    if mode == "dark":
        return cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    if mode in ("median_pos", "median_neg"):
        # 중간값 필터는 얇은 획을 무시하므로 '진짜 배경' 추정에 가깝다. 획이
        # 배경보다 밝은 경우(pos)와 어두운 경우(neg)를 각각 본다. 흰색 아이콘에서는
        # 글자가 배경보다 어둡기 때문에 neg 가 유일하게 동작하는 채널이 된다.
        size = max(3, MEDIAN_KERNEL * upscale)
        size += (size + 1) % 2
        base = cv2.medianBlur(gray, min(size, 31)).astype(np.int16)
        diff = gray.astype(np.int16) - base
        if mode == "median_pos":
            return np.clip(diff, 0, 255).astype(np.uint8)
        return np.clip(-diff, 0, 255).astype(np.uint8)
    raise ValueError(f"unknown cooldown channel: {mode}")


def binarize(score: np.ndarray, fraction: float) -> tuple[np.ndarray, int]:
    """가장 진한 획에서 유도한 임계값으로 이진화한다.

    고정 임계값 스윕은 프레임마다 다른 값을 골라 같은 `17s` 가 1~3조각으로
    갈라졌다. 그 프레임 안에서 상대적으로 정하면 아이콘 밝기와 무관해진다.
    """
    peak = int(score.max()) if score.size else 0
    if peak < MIN_PEAK:
        return np.zeros(score.shape, np.uint8), 0
    threshold = max(8, int(round(peak * fraction)))
    binary = (score >= threshold).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return binary, threshold


# --- 분리 --------------------------------------------------------------------
def _components(binary: np.ndarray, min_area: int) -> list[tuple[int, int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    out = []
    for x, y, w, h, area in stats[1:count]:
        if area >= min_area:
            out.append((int(x), int(y), int(w), int(h), int(area)))
    return out


def _merge_vertical_splits(boxes: list[tuple[int, int, int, int]],
                           max_height: float) -> list[tuple[int, int, int, int]]:
    """세로로 쪼개진 한 글자를 합친다(`9` 의 고리와 꼬리).

    두 조건을 모두 요구한다.
      * x 범위가 실제로 겹친다 — 겹치지 않으면 `17s` 의 `1` 과 `7` 이 붙는다.
      * 세로로 거의 맞닿아 있고, 합쳐도 글자 높이를 넘지 않는다 — 슬롯 전체를
        보면 아이콘 화살표·단축키 글자가 같은 x 위에 쌓여 있어서, 이 조건이
        없으면 세로로 전부 이어붙어 슬롯 높이만 한 덩어리가 된다.
    """
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda b: b[0]):
        for index, previous in enumerate(merged):
            overlap = (min(previous[0] + previous[2], box[0] + box[2])
                       - max(previous[0], box[0]))
            if overlap < 0.45 * min(previous[2], box[2]):
                continue
            gap = max(previous[1], box[1]) - min(previous[1] + previous[3],
                                                 box[1] + box[3])
            union_top = min(previous[1], box[1])
            union_bottom = max(previous[1] + previous[3], box[1] + box[3])
            if gap > 0.30 * max_height or (union_bottom - union_top) > max_height:
                continue
            x0 = min(previous[0], box[0])
            x1 = max(previous[0] + previous[2], box[0] + box[2])
            merged[index] = (x0, union_top, x1 - x0, union_bottom - union_top)
            break
        else:
            merged.append(tuple(int(v) for v in box))
    merged.sort(key=lambda b: b[0])
    return merged


@dataclass
class Layout:
    """한 후보의 글자 배치."""

    suffix: tuple[int, int, int, int]
    digits: list[tuple[int, int, int, int]]
    text_height: int

    @property
    def baseline(self) -> float:
        return float(np.median([b[1] + b[3] for b in self.digits]))


def segment(binary: np.ndarray, upscale: int = UPSCALE) -> list[Layout]:
    """`s` 접미사와 그 왼쪽 숫자들을 찾는다.

    쿨타임 표기는 슬롯 안에서 좌우로 움직이고(자리수에 따라), 아래에는 항상
    단축키 글자(`F`/`R`)가, 위에는 아이콘 화살표가 있다. 그래서 위치가 아니라
    **글자 높이와 베이스라인 일치**로 골라낸다.
    """
    height, width = binary.shape[:2]
    comps = _components(binary, min_area=max(3, 2 * upscale))
    if not comps:
        return []
    max_h = height * MAX_TEXT_RATIO
    boxes = _merge_vertical_splits([(c[0], c[1], c[2], c[3]) for c in comps], max_h)

    min_h = max(MIN_TEXT_PX * upscale, height * MIN_TEXT_RATIO)
    tall = [b for b in boxes
            if min_h <= b[3] <= max_h and b[2] <= max_h]
    if len(tall) < 2:
        return []

    layouts: list[Layout] = []
    for suffix in sorted(tall, key=lambda b: -b[0]):
        # 접미사는 글자열 맨 오른쪽이고, 숫자보다 낮다(9 vs 12px).
        left_of = [b for b in tall
                   if b[0] + b[2] <= suffix[0] + upscale and b[3] > suffix[3]]
        if not left_of:
            continue
        digit_h = float(max(b[3] for b in left_of))
        ratio = suffix[3] / max(1.0, digit_h)
        if not SUFFIX_HEIGHT_RANGE[0] <= ratio <= SUFFIX_HEIGHT_RANGE[1]:
            continue
        width_ratio = suffix[2] / max(1.0, digit_h)
        if not SUFFIX_WIDTH_RANGE[0] <= width_ratio <= SUFFIX_WIDTH_RANGE[1]:
            continue

        # `Ns` 의 오른쪽에는 같은 줄에 아무 글자도 없다. 오른쪽에 같은 베이스라인의
        # 글자가 남아 있으면, 숫자 하나를 접미사로 착각한 후보다(`14s` 를 `1s` 로
        # 읽던 실패).
        suffix_base = suffix[1] + suffix[3]
        slack = max(1.0, digit_h * BASELINE_SLACK)
        if any(b[0] >= suffix[0] + suffix[2] - upscale
               and abs((b[1] + b[3]) - suffix_base) <= slack for b in tall):
            continue

        # 베이스라인이 맞는 숫자만 남긴다. 아이콘 화살표와 단축키 글자는
        # 이 검사에서 떨어진다(실측 top 0 / 30~37 vs 글자 12~13).
        aligned = [b for b in left_of if abs((b[1] + b[3]) - suffix_base) <= slack]
        if not aligned:
            continue
        aligned = [b for b in aligned
                   if DIGIT_WIDTH_RANGE[0] * digit_h <= b[2] <= DIGIT_WIDTH_RANGE[1] * digit_h]
        if not aligned:
            continue

        # 접미사에 붙어 있는 연속열만 취한다.
        aligned.sort(key=lambda b: b[0])
        gap_limit = max(2.0, digit_h * DIGIT_GAP_LIMIT)
        kept = [aligned[-1]]
        if suffix[0] - (aligned[-1][0] + aligned[-1][2]) > gap_limit:
            continue
        for box in reversed(aligned[:-1]):
            if kept[0][0] - (box[0] + box[2]) <= gap_limit:
                kept.insert(0, box)
            else:
                break
        kept = kept[-MAX_DIGITS:]
        layouts.append(Layout(suffix=suffix, digits=kept, text_height=int(round(digit_h))))
    return layouts


def layout_ok(binary: np.ndarray, layout: Layout) -> bool:
    """글자열로 보이지 않는 후보를 버린다.

    글자는 한 베이스라인·한 크기로 그려진다. 잉크가 덩어리째 켜진 후보,
    높이가 들쭉날쭉한 후보, 숫자 사이 간격이 제멋대로인 후보는 배경 얼룩이다.
    """
    if not layout.digits:
        return False
    digit_h = layout.text_height
    if digit_h <= 0:
        return False

    heights = [b[3] for b in layout.digits]
    if max(heights) - min(heights) > max(2.0, digit_h * 0.30):
        return False

    bases = [b[1] + b[3] for b in layout.digits]
    if max(bases) - min(bases) > max(1.0, digit_h * BASELINE_SLACK):
        return False

    # 글자 영역의 잉크 밀도. 0.75 를 넘으면 획이 아니라 덩어리다.
    for box in layout.digits + [layout.suffix]:
        x, y, w, h = box
        crop = binary[y:y + h, x:x + w]
        if crop.size == 0:
            return False
        if float((crop > 0).mean()) > 0.80:
            return False

    # 숫자 사이 간격은 비슷해야 한다.
    if len(layout.digits) >= 3:
        gaps = [layout.digits[i + 1][0] - (layout.digits[i][0] + layout.digits[i][2])
                for i in range(len(layout.digits) - 1)]
        if max(gaps) - min(gaps) > max(2.0, digit_h * 0.45):
            return False

    # 글자 간격(advance)이 폰트 값에서 벗어나면 배경 얼룩을 한 자리로 세었거나
    # 두 자리를 하나로 뭉갠 후보다.
    for left, right in zip(layout.digits, layout.digits[1:]):
        pitch = (right[0] - left[0]) / digit_h
        if not DIGIT_PITCH_RANGE[0] <= pitch <= DIGIT_PITCH_RANGE[1]:
            return False

    # 마지막 숫자에서 's' 까지의 거리도 같은 폰트 간격을 따른다.
    advance = (layout.suffix[0] - layout.digits[-1][0]) / digit_h
    if not SUFFIX_ADVANCE_RANGE[0] <= advance <= SUFFIX_ADVANCE_RANGE[1]:
        return False

    # 앞자리를 놓친 후보 걸러내기: 맨 왼쪽 숫자의 왼쪽 띠에 글자 잉크가 남아
    # 있으면 그 후보는 버린다. `15s` 를 `5s` 로 읽는 실패가 전부 이 형태였다.
    first = layout.digits[0]
    band = int(round(digit_h * LEFT_STRIP_WIDTH))
    x_start = max(0, first[0] - band)
    top = min(b[1] for b in layout.digits)
    bottom = max(b[1] + b[3] for b in layout.digits)
    strip = binary[top:bottom, x_start:first[0]]
    if strip.size and float((strip > 0).mean()) > LEFT_STRIP_MAX_INK:
        return False
    return True


def left_strip_clear(score: np.ndarray, layout: Layout, upscale: int = UPSCALE) -> bool:
    """맨 왼쪽 숫자의 왼쪽 띠에 '숨은 앞자리'가 없는지 본다.

    이진화 임계값이 높으면 희미한 앞자리가 통째로 지워져서, 이진 잉크 검사로는
    `15s` 를 `5s` 로 읽는 후보를 걸러내지 못한다. 그래서 훨씬 낮은 임계값으로 그
    띠만 다시 이진화하고, 거기 남은 덩어리가 **숫자처럼 생겼고 같은 베이스라인에
    서 있는지**를 본다. 아이콘 무늬는 베이스라인을 맞추지 않는다.
    """
    if not layout.digits:
        return False
    digit_h = max(1, layout.text_height)
    first = layout.digits[0]
    band = int(round(digit_h * LEFT_STRIP_WIDTH))
    x_start = max(0, first[0] - band)
    if first[0] - x_start < max(2, digit_h * 0.2):
        return True                      # 띠를 만들 자리가 없다(슬롯 왼쪽 끝)

    top = max(0, min(b[1] for b in layout.digits) - upscale)
    bottom = min(score.shape[0], max(b[1] + b[3] for b in layout.digits) + upscale)
    baseline = float(np.median([b[1] + b[3] for b in layout.digits]))

    peak = float(score.max()) if score.size else 0.0
    if peak <= 0:
        return True
    low = (score[top:bottom, x_start:first[0]]
           >= max(6.0, peak * LEFT_STRIP_LOW_FRACTION)).astype(np.uint8)
    if not low.any():
        return True
    count, _, stats, _ = cv2.connectedComponentsWithStats(low, 8)
    slack = max(2.0, digit_h * BASELINE_SLACK)
    for x, y, w, h, area in stats[1:count]:
        if h < digit_h * 0.55 or w < digit_h * 0.12:
            continue
        if area < digit_h * 0.6:
            continue
        if abs((top + y + h) - baseline) <= slack:
            return False                 # 앞자리를 놓친 후보다
    return True


# --- 글리프 판정 (평균 스텐실 상관) ------------------------------------------
def _blur(canvas: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(canvas.astype(np.float32), (3, 3), NCC_BLUR_SIGMA)


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom > 1e-6 else 0.0


def _best_ncc(candidate: np.ndarray, reference: np.ndarray) -> float:
    best = -1.0
    for dy in NCC_SHIFTS:
        for dx in NCC_SHIFTS:
            moved = np.roll(np.roll(candidate, dy, axis=0), dx, axis=1)
            best = max(best, _ncc(moved, reference))
    return best


def _confidence(score: float, margin: float) -> float:
    """상관값과 1·2등 차이를 0~1 신뢰도로 합친다."""
    strength = np.clip((score - MIN_GLYPH_NCC) / (1.0 - MIN_GLYPH_NCC), 0.0, 1.0)
    separation = np.clip(margin / (MIN_GLYPH_MARGIN * 3.0), 0.0, 1.0)
    return float(0.55 + 0.30 * strength + 0.15 * separation)


class StencilSet:
    """프로파일에서 뽑은 숫자별/접미사 평균 모양(블러 적용)."""

    def __init__(self, profile: TimerGlyphProfile):
        digits, suffix = profile.stencils()
        self.digits = {int(d): _blur(np.clip(s, 0, 255)) for d, s in digits.items()}
        self.suffix = _blur(np.clip(suffix, 0, 255)) if suffix is not None else None

    def classify(self, glyph: np.ndarray) -> tuple[Optional[int], float, float]:
        if not self.digits:
            return None, 0.0, 0.0
        candidate = _blur(glyph)
        scores = sorted(((digit, _best_ncc(candidate, stencil))
                         for digit, stencil in self.digits.items()),
                        key=lambda item: -item[1])
        digit, best = scores[0]
        second = scores[1][1] if len(scores) > 1 else best - 1.0
        margin = best - second
        if best < MIN_GLYPH_NCC or margin < MIN_GLYPH_MARGIN:
            return None, best, margin
        return digit, best, margin

    def suffix_score(self, glyph: np.ndarray) -> float:
        if self.suffix is None:
            return 1.0
        return _best_ncc(_blur(glyph), self.suffix)


_STENCIL_CACHE: dict[tuple[int, int, int], StencilSet] = {}


def stencils_for(profile: TimerGlyphProfile) -> StencilSet:
    key = (id(profile), len(profile.glyphs), len(profile.suffix_glyphs))
    cached = _STENCIL_CACHE.get(key)
    if cached is None:
        cached = StencilSet(profile)
        _STENCIL_CACHE.clear()          # 프로파일은 한 번에 하나만 쓴다
        _STENCIL_CACHE[key] = cached
    return cached


def profile_accuracy(profile: TimerGlyphProfile) -> float:
    """저장된 글리프에 대한 leave-one-out 정확도(상관 척도 기준).

    `TimerGlyphProfile.self_accuracy()` 는 HOG 최근접 기준이라 실제로 쓰는
    판정과 다르다. 채택 게이트가 판정과 같은 척도를 봐야 의미가 있다.
    """
    from boss_debuff_detector import decode_png

    grouped: dict[int, list[np.ndarray]] = {}
    for label, encoded in zip(profile.labels, profile.glyphs):
        glyph = decode_png(encoded)
        if glyph is not None and glyph.shape[:2] == (GLYPH_SIZE[1], GLYPH_SIZE[0]):
            grouped.setdefault(int(label), []).append(glyph.astype(np.float32))
    scorable = {d: frames for d, frames in grouped.items() if len(frames) >= 2}
    if len(scorable) < 2:
        return 1.0

    sums = {d: np.sum(frames, axis=0) for d, frames in scorable.items()}
    counts = {d: len(frames) for d, frames in scorable.items()}
    correct = total = 0
    for digit, frames in scorable.items():
        for frame in frames:
            references = {}
            for other, total_sum in sums.items():
                if other == digit:
                    if counts[other] <= 1:
                        continue
                    mean = (total_sum - frame) / (counts[other] - 1)
                else:
                    mean = total_sum / counts[other]
                references[other] = _blur(np.clip(mean, 0, 255))
            if not references:
                continue
            candidate = _blur(frame)
            best = max(references.items(), key=lambda item: _best_ncc(candidate, item[1]))
            correct += int(best[0] == digit)
            total += 1
    return correct / float(total) if total else 1.0


# --- 판독 --------------------------------------------------------------------
@dataclass
class CooldownReading:
    seconds: Optional[int] = None
    confidence: float = 0.0
    channel: str = ""
    threshold: int = 0
    digits: int = 0
    text_height: int = 0
    agreement: int = 0            # 같은 값을 낸 (채널,임계값) 조합 수
    source: str = "segment"       # segment | correlation
    reject: str = ""
    layout: Optional["Layout"] = field(default=None, repr=False, compare=False)
    binary: Optional[np.ndarray] = field(default=None, repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return self.seconds is not None


def _read_layout(binary: np.ndarray, layout: Layout,
                 profile: TimerGlyphProfile) -> tuple[Optional[int], float]:
    stencils = stencils_for(profile)
    if not stencils.digits:
        return None, 0.0

    suffix_score = stencils.suffix_score(normalize_glyph(binary, layout.suffix))
    if suffix_score < MIN_SUFFIX_NCC:
        return None, 0.0

    value = 0
    scores = [_confidence(suffix_score, MIN_GLYPH_MARGIN)]
    for box in layout.digits:
        digit, score, margin = stencils.classify(normalize_glyph(binary, box))
        if digit is None:
            return None, 0.0
        value = value * 10 + int(digit)
        scores.append(_confidence(score, margin))
    return value, float(min(scores))


def _settled(candidates: list["CooldownReading"]) -> bool:
    """한 값이 충분히 재현됐는지(남은 채널을 건너뛸 근거)."""
    if not candidates:
        return False
    votes: dict[int, int] = {}
    for candidate in candidates:
        if candidate.confidence >= SETTLED_CONFIDENCE:
            votes[candidate.seconds] = votes.get(candidate.seconds, 0) + 1
    return any(count >= SETTLED_AGREEMENT for count in votes.values())


def read_cooldown(slot_bgr: np.ndarray, profile: TimerGlyphProfile,
                  upscale: int = UPSCALE,
                  expected: Optional[int] = None) -> CooldownReading:
    """슬롯 이미지 한 장에서 남은 초를 읽는다.

    채널 x 임계값 조합마다 후보를 만들고, 배치 검사를 통과한 것만 분류기에
    넘긴 뒤 아래 우선순위로 고른다.
      ① 진행 중인 카운트다운과 맞는 값 (`expected`)
      ② 자리수가 많은 쪽 (`17s` 의 앞자리 `1` 을 놓치는 것이 흔한 실패)
      ③ 분류 신뢰도
    """
    if slot_bgr is None or slot_bgr.size == 0:
        return CooldownReading(reject="empty")
    big = upscale_slot(slot_bgr, upscale)

    candidates: list[CooldownReading] = []
    rejects: list[str] = []
    for mode in CHANNELS:
        score = channel_score(big, mode, upscale)
        for fraction in SCORE_FRACTIONS:
            binary, threshold = binarize(score, fraction)
            if threshold == 0:
                rejects.append(f"{mode}:no_peak")
                continue
            layouts = segment(binary, upscale)
            if not layouts:
                rejects.append(f"{mode}:no_layout")
                continue
            for layout in layouts:
                if not layout_ok(binary, layout):
                    rejects.append(f"{mode}:layout")
                    continue
                if not left_strip_clear(score, layout):
                    rejects.append(f"{mode}:left_ink")
                    continue
                value, confidence = _read_layout(binary, layout, profile)
                if value is None:
                    rejects.append(f"{mode}:classify")
                    continue
                if confidence < MIN_CONFIDENCE:
                    rejects.append(f"{mode}:low_conf")
                    continue
                candidates.append(CooldownReading(
                    seconds=value, confidence=confidence, channel=mode,
                    threshold=threshold, digits=len(layout.digits),
                    text_height=layout.text_height, layout=layout, binary=binary))
        # 이미 충분히 재현된 값이 있으면 남은 채널은 건너뛴다. 어두운 아이콘은
        # 첫 채널에서 끝나므로 한 프레임 비용이 30ms -> 8ms 로 줄어든다.
        if _settled(candidates):
            break

    if not candidates:
        return CooldownReading(reject=rejects[0] if rejects else "no_candidate")

    # 같은 값을 낸 조합 수를 센다. 배경 무늬가 만든 우연한 후보는 다른 채널이나
    # 다른 임계값에서 재현되지 않는다.
    votes: dict[int, int] = {}
    for candidate in candidates:
        votes[candidate.seconds] = votes.get(candidate.seconds, 0) + 1

    best: Optional[CooldownReading] = None
    for candidate in candidates:
        candidate.agreement = votes.get(candidate.seconds, 0)
        if candidate.agreement < MIN_AGREEMENT and candidate.confidence < HIGH_CONFIDENCE:
            continue
        if best is None or _better(candidate, best, expected):
            best = candidate
    if best is None:
        return CooldownReading(reject="no_agreement")
    return best


def _better(candidate: CooldownReading, current: CooldownReading,
            expected: Optional[int]) -> bool:
    """후보 순위.

    ① 진행 중인 카운트다운과 맞는 값 ② 같은 값을 낸 조합 수 ③ 신뢰도 ④ 자리수.

    자리수를 앞세우면 배경 얼룩이 만든 가짜 앞자리(`1s` 를 `11s` 로)를 오히려
    선호하게 된다. 앞자리 누락은 `layout_ok` 의 왼쪽 띠 검사가 막으므로,
    순위는 재현성(조합 수)을 먼저 본다.
    """
    def rank(reading: CooldownReading) -> tuple:
        matches = 0
        if expected is not None and reading.seconds is not None:
            matches = 1 if abs(reading.seconds - expected) <= 1 else 0
        return (matches, reading.agreement, reading.confidence, reading.digits)

    return rank(candidate) > rank(current)


# --- 라벨 유틸 ---------------------------------------------------------------
_LABEL_RE = re.compile(r"_(\d+)s$", re.I)


def parse_sample_label(path: Path) -> Optional[int]:
    """`slotA_17s.png` -> 17. 숫자가 없는 프레임(`slotA_ready.png`)은 None."""
    match = _LABEL_RE.search(path.stem)
    return int(match.group(1)) if match else None


def sample_paths(root: Optional[Path] = None) -> list[Path]:
    root = Path(root) if root is not None else samples_root()
    return sorted(root.glob("*.png"))
