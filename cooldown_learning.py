"""스킬 쿨타임 총량을 스스로 학습한다.

## 왜 '실시간 판독'이 아니라 '총량 학습'인가
v2.46 에서 은퇴한 구조는 15Hz로 매 프레임 숫자를 읽어 그 값으로 카운트다운을
굴렸다. 한 프레임만 실패해도 화면에서 숫자가 튀었고, 스킬 아이콘은 직업·단축키마다
달라 실패가 잦았다. 그래서 목표를 바꾼다.

쿨타임 **총량은 스킬마다 고정된 상수**다. 한 번만 알아내면 그 뒤로는 기존 수동
카운트다운이 그대로 표시하면 된다. 즉 필요한 것은 "매 프레임 정확도"가 아니라
"한 번의 확실한 값"이다.

## 두 갈래로 재고 서로 검증한다

| 근거 | 방법 | 특징 |
|---|---|---|
| `ocr` | 캐스트 직후 숫자를 읽어 `총량 = 읽은 값 + 경과 시간` | 2초 안에 학습, 오독 위험 있음 |
| `ready` | 사용 직후부터 다시 사용 가능해질 때까지의 시간 | 오독 위험 0, 한 바퀴 관찰 필요 |

`ocr` 은 **두 프레임이 경과 시간과 일관되게 줄어들 때만**(예: 3초 뒤에 3초 줄었다)
후보로 삼는다. 배경 얼룩을 숫자로 착각한 값은 이 검사를 통과하지 못한다.

후보는 **서로 다른 캐스트에서 두 번** 같은 값이 나와야 확정된다. 쿨감(각인·장비)으로
값이 줄어드는 것도 같은 조건으로 받아들이므로, 학습값은 늘어날 수도 줄어들 수도
있다(보스 디버프 지속시간 학습에서 겪은 문제와 같다).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 캐스트 직후 이만큼만 숫자를 읽는다. 이때 값이 가장 크고 자리수도 많다.
SCAN_WINDOW = 2.0
# 두 판독 사이 간격이 이 범위를 벗어나면 짝으로 보지 않는다.
PAIR_MIN_GAP = 0.6
PAIR_MAX_GAP = 3.0
# 두 판독의 차이가 경과 시간과 이만큼 안에서 맞아야 한다.
PAIR_TOLERANCE = 0.6
# 상식적인 쿨타임 범위. 밖으로 나가는 값은 버린다.
MIN_COOLDOWN = 2
MAX_COOLDOWN = 600
# 확정에 필요한 (서로 다른 캐스트에서의) 일치 횟수.
REQUIRED_HITS = 2
# 후보가 이 시간 동안 보강되지 않으면 잊는다(엉뚱한 값이 굳지 않게).
CANDIDATE_TTL = 900.0


@dataclass
class SkillState:
    """한 스킬의 학습 상태."""

    learned: Optional[int] = None
    learned_source: str = ""
    candidate: Optional[int] = None
    candidate_hits: int = 0
    candidate_source: str = ""
    candidate_at: float = 0.0
    cast_at: Optional[float] = None
    scan_until: float = 0.0
    last_value: Optional[int] = None
    last_at: float = 0.0
    counted_this_cast: bool = False

    def to_dict(self) -> dict:
        return {"learned": self.learned, "source": self.learned_source,
                "candidate": self.candidate, "hits": self.candidate_hits}

    @classmethod
    def from_dict(cls, data: dict) -> "SkillState":
        state = cls()
        if not isinstance(data, dict):
            return state
        learned = data.get("learned")
        if isinstance(learned, (int, float)) and MIN_COOLDOWN <= learned <= MAX_COOLDOWN:
            state.learned = int(learned)
            state.learned_source = str(data.get("source", "") or "")
        candidate = data.get("candidate")
        if isinstance(candidate, (int, float)) and MIN_COOLDOWN <= candidate <= MAX_COOLDOWN:
            state.candidate = int(candidate)
            state.candidate_hits = max(0, min(REQUIRED_HITS - 1, int(data.get("hits", 1))))
        return state


class CooldownLearner:
    """스킬별 쿨타임 학습 상태 기계. Qt/화면에 의존하지 않는다."""

    def __init__(self):
        self.states: dict[str, SkillState] = {}

    # -- 상태 ---------------------------------------------------------------
    def state(self, name: str) -> SkillState:
        return self.states.setdefault(name, SkillState())

    def learned(self, name: str) -> Optional[int]:
        return self.state(name).learned

    def snapshot(self) -> dict:
        return {name: state.to_dict() for name, state in self.states.items()
                if state.learned is not None or state.candidate is not None}

    def restore(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        for name, payload in data.items():
            self.states[str(name)] = SkillState.from_dict(payload)

    def forget(self, name: Optional[str] = None) -> None:
        """학습값 초기화. 값이 실제보다 길게 굳었을 때 쓴다."""
        if name is None:
            self.states.clear()
            return
        self.states.pop(name, None)

    # -- 입력 ---------------------------------------------------------------
    def on_cast(self, name: str, now: float) -> None:
        """스킬을 썼다(트리거 키 또는 사용 가능 -> 불가 전환)."""
        state = self.state(name)
        state.cast_at = now
        state.scan_until = now + SCAN_WINDOW
        state.last_value = None
        state.last_at = 0.0
        state.counted_this_cast = False

    def should_scan(self, name: str, now: float) -> bool:
        state = self.state(name)
        if state.cast_at is None:
            return False
        if state.counted_this_cast:
            return False
        return now <= state.scan_until

    def expected(self, name: str, now: float) -> Optional[int]:
        """진행 중인 카운트다운에서 기대되는 남은 초(판독 후보 순위에 쓴다)."""
        state = self.state(name)
        if state.learned is None or state.cast_at is None:
            return None
        remaining = state.learned - (now - state.cast_at)
        return int(round(remaining)) if remaining >= 0 else None

    def on_reading(self, name: str, value: int, now: float) -> Optional[int]:
        """판독된 남은 초를 넣는다. 새로 확정된 값이 있으면 돌려준다.

        한 판독만으로는 아무것도 하지 않는다. 두 판독이 경과 시간과 일관될 때만
        총량 후보를 만든다.
        """
        state = self.state(name)
        if state.cast_at is None or value is None:
            return None
        if not MIN_COOLDOWN <= value <= MAX_COOLDOWN:
            return None

        previous_value, previous_at = state.last_value, state.last_at
        state.last_value, state.last_at = int(value), float(now)

        if previous_value is None:
            return None
        gap = now - previous_at
        if not PAIR_MIN_GAP <= gap <= PAIR_MAX_GAP:
            return None
        drop = previous_value - value
        if abs(drop - gap) > PAIR_TOLERANCE:
            return None                      # 카운트다운과 어긋나는 짝

        total = int(round(value + (now - state.cast_at)))
        state.counted_this_cast = True
        return self._propose(name, total, "ocr", now)

    def on_ready(self, name: str, now: float) -> Optional[int]:
        """스킬이 다시 사용 가능해졌다. 경과 시간이 곧 쿨타임이다."""
        state = self.state(name)
        if state.cast_at is None:
            return None
        elapsed = now - state.cast_at
        state.cast_at = None
        state.scan_until = 0.0
        state.last_value = None
        if not MIN_COOLDOWN <= elapsed <= MAX_COOLDOWN:
            return None
        return self._propose(name, int(round(elapsed)), "ready", now)

    # -- 확정 ---------------------------------------------------------------
    def _propose(self, name: str, total: int, source: str, now: float) -> Optional[int]:
        state = self.state(name)
        if not MIN_COOLDOWN <= total <= MAX_COOLDOWN:
            return None
        if state.candidate is not None and now - state.candidate_at > CANDIDATE_TTL:
            state.candidate, state.candidate_hits = None, 0

        if state.candidate is not None and abs(state.candidate - total) <= 1:
            state.candidate_hits += 1
            state.candidate = total
        else:
            state.candidate, state.candidate_hits = total, 1
        state.candidate_source = source
        state.candidate_at = now

        if state.candidate_hits < REQUIRED_HITS:
            return None
        if state.learned == state.candidate:
            return None
        state.learned = state.candidate
        state.learned_source = source
        return state.learned
