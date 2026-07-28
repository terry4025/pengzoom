"""Boss debuff banner shown on top of the party status panel.

Kept in its own module on purpose: the party panel visual redesign is being
developed in parallel, so this widget only needs its two public calls
(:meth:`set_local_state` / :meth:`ingest_party_states`) re-hooked after a merge.
"""

from __future__ import annotations

import math
import re
import time

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

import boss_debuff_detector as bdd

# Party-sync channel: the panel skips every '_'-prefixed key when it renders
# skill badges, so a boss debuff report can never be drawn as a fake skill.
PARTY_STATE_PREFIX = "_bossdebuff:"
REPORT_STALE_AFTER = 6.0   # seconds without a refresh before a report is dropped

_RGBA_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")


def parse_theme_color(value, fallback: QColor) -> QColor:
    """THEMES 프리셋의 '#hex' / 'rgba(r,g,b,a)' 문자열을 QColor로 바꾼다.

    magnifier 의 동일 헬퍼를 import 하면 순환 참조가 되므로 여기에 둔다.
    """
    if isinstance(value, QColor):
        return QColor(value)
    if isinstance(value, str):
        match = _RGBA_RE.search(value)
        if match:
            red, green, blue, alpha = match.groups()
            alpha_255 = 255 if alpha is None else int(round(float(alpha) * 255))
            return QColor(int(red), int(green), int(blue), max(0, min(255, alpha_255)))
        stripped = value.strip()
        if stripped.startswith("#"):
            color = QColor(stripped)
            if color.isValid():
                return color
    return QColor(fallback)


def css_rgba(color: QColor, alpha: float = None) -> str:
    """QColor를 QSS 에 넣을 rgba() 문자열로 만든다."""
    opacity = color.alphaF() if alpha is None else max(0.0, min(1.0, float(alpha)))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {opacity:.3f})"


def blend_over(front: QColor, back: QColor) -> QColor:
    """알파가 있는 색을 배경 위에 합성한 실제 표시색."""
    alpha = front.alphaF()
    return QColor(
        int(round(front.red() * alpha + back.red() * (1.0 - alpha))),
        int(round(front.green() * alpha + back.green() * (1.0 - alpha))),
        int(round(front.blue() * alpha + back.blue() * (1.0 - alpha))),
    )


def _relative_luminance(color: QColor) -> float:
    def channel(value: int) -> float:
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4
    return (0.2126 * channel(color.red())
            + 0.7152 * channel(color.green())
            + 0.0722 * channel(color.blue()))


def wcag_contrast(first: QColor, second: QColor) -> float:
    """WCAG 명도 대비비. 본문 글자는 4.5 이상이 필요하다."""
    a, b = _relative_luminance(first), _relative_luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(color: QColor, background: QColor, minimum: float = 4.5) -> QColor:
    """배경 대비가 부족한 색의 명도만 조절해 읽을 수 있게 만든다.

    프리셋의 강조색(주황·빨강)은 어두운 배경을 전제로 골라져 있어서, 밝은 테마
    위에 그대로 올리면 대비가 1.6까지 떨어진다. 색조/채도는 유지하고 명도만
    배경 반대 방향으로 옮긴다.
    """
    adjusted = QColor(color)
    darken = background.lightnessF() > 0.5
    for _ in range(30):
        if wcag_contrast(adjusted, background) >= minimum:
            break
        hue, saturation, lightness, alpha = adjusted.getHslF()
        lightness = max(0.0, lightness - 0.035) if darken else min(1.0, lightness + 0.035)
        adjusted.setHslF(hue, saturation, lightness, alpha)
    return adjusted


def party_state_key(debuff_id: str = bdd.DEFAULT_DEBUFF_ID) -> str:
    return f"{PARTY_STATE_PREFIX}{debuff_id}"


def _icon_pixmap(debuff_id: str, size: int) -> QPixmap:
    """Real in-game cell crop, so the banner shows the icon players know."""
    for root in (bdd.assets_root() / "icons" / debuff_id,
                 bdd.user_data_root() / "icons" / debuff_id):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.png")):
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                # Fall back to a numpy decode: QPixmap can fail on some
                # non-ASCII install paths, and this project ships under 펭줌/.
                image = bdd.read_image(path)
                if image is None:
                    continue
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                pixmap = QPixmap.fromImage(
                    QImage(rgb.tobytes(), width, height, width * 3, QImage.Format.Format_RGB888)
                )
            if not pixmap.isNull():
                return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
    return QPixmap()


class BossDebuffBanner(QFrame):
    """Single-row readout: is the boss carrying 암흑 수류탄, and for how long."""

    def __init__(self, parent=None, debuff_id: str = bdd.DEFAULT_DEBUFF_ID, ui_scale: float = 1.0):
        super().__init__(parent)
        self.debuff_id = debuff_id
        self.ui_scale = ui_scale
        self.setProperty("class", "BossDebuffCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._reports: dict[str, dict] = {}
        # 테마에서 채워지는 색. 디버프 이름은 예전에 색을 지정하지 않아
        # 앱 기본 팔레트(어두운 글자)를 그대로 썼고, 배경이 어두운 프리셋에서는
        # 검은 글자가 검은 배경 위에 놓여 보이지 않았다.
        self._c_text = QColor(245, 245, 247)
        self._c_bg = QColor(18, 18, 23)
        self._accent_active = QColor(48, 209, 88)
        self._accent_idle = QColor(142, 142, 147)
        self._card_bg_active = QColor(28, 44, 32)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(8)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(int(24 * ui_scale), int(24 * ui_scale))
        self.icon_label.setPixmap(_icon_pixmap(debuff_id, int(24 * ui_scale)))
        row.addWidget(self.icon_label)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(0)
        self.name_label = QLabel(bdd.DEBUFF_DISPLAY_NAMES.get(debuff_id, debuff_id))
        self.detail_label = QLabel("감지 대기")
        text_column.addWidget(self.name_label)
        text_column.addWidget(self.detail_label)
        row.addLayout(text_column)
        row.addStretch()

        self.value_label = QLabel("OFF")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.value_label)

        self.apply_scale(ui_scale)
        self.refresh()

    # -- styling ------------------------------------------------------------
    def apply_scale(self, ui_scale: float) -> None:
        self.ui_scale = max(0.5, float(ui_scale or 1.0))
        size = int(24 * self.ui_scale)
        self.icon_label.setFixedSize(size, size)
        self.icon_label.setPixmap(_icon_pixmap(self.debuff_id, size))
        self.name_label.setStyleSheet(
            f"font-size: {int(12 * self.ui_scale)}px; font-weight: 700; "
            f"color: {css_rgba(self._c_text, 1.0)}; background: transparent; border: none;")
        self.detail_label.setStyleSheet(
            f"font-size: {int(9 * self.ui_scale)}px; font-weight: 600; "
            f"color: {css_rgba(self._c_text, 0.60)}; background: transparent; border: none;")
        self.value_label.setStyleSheet(self._value_style(self._accent_idle))

    def _value_style(self, color: QColor) -> str:
        return (f"font-size: {int(18 * self.ui_scale)}px; font-weight: 800; "
                f"color: {css_rgba(color, 1.0)}; background: transparent; border: none;")

    def _card_style(self, active: bool) -> str:
        """카드 배경도 테마에서 유도한다.

        예전에는 흰색 3% / 빨강 10%로 고정돼 있어서 밝은 테마에서는 아무것도
        보이지 않았다.
        """
        if active:
            fill = css_rgba(self._accent_active, 0.12)
            line = css_rgba(self._accent_active, 0.38)
        else:
            fill = css_rgba(self._c_text, 0.05)
            line = css_rgba(self._c_text, 0.10)
        return ("QFrame.BossDebuffCard { background-color: %s; "
                "border: 1.2px solid %s; border-radius: 12px; }" % (fill, line))

    def apply_theme(self, theme: dict) -> None:
        theme = theme or {}
        self._c_bg = parse_theme_color(theme.get("bg"), QColor(18, 18, 23))
        # 디버프 이름/설명은 테마의 본문 글자색을 그대로 쓴다. 프리셋마다 배경과
        # 대비되도록 정의된 값이므로 어떤 테마에서도 읽을 수 있다.
        default_text = QColor(29, 29, 31) if self._c_bg.lightnessF() > 0.5 else QColor(245, 245, 247)
        self._c_text = parse_theme_color(theme.get("font_color"), default_text)

        # 강조색은 배경 위에 실제로 합성된 카드 색과 대비를 재서, 부족하면
        # 명도를 조절한다. 밝은 테마에서 주황색 남은 시간이 안 보이던 문제.
        # 지속 중은 '감지되어 정보가 있다'는 신호이므로 스킬 준비 완료와 같은
        # 초록(ready)을 쓴다. 없을 때는 회색(OFF).
        opaque_bg = QColor(self._c_bg.red(), self._c_bg.green(), self._c_bg.blue())
        active_raw = parse_theme_color(theme.get("ready"), QColor(48, 209, 88))
        idle_raw = parse_theme_color(theme.get("accent_secondary"), QColor(142, 142, 147))
        tint = QColor(active_raw)
        tint.setAlphaF(0.12)
        self._card_bg_active = blend_over(tint, opaque_bg)
        # 목표를 6.0으로 잡는다. 패널은 반투명이라 게임 화면이 비쳐 실제 배경이
        # 이보다 밝거나 어두워질 수 있어서, 기준선(4.5)에 여유를 둬야 한다.
        self._accent_active = readable_on(active_raw, self._card_bg_active, 6.0)
        self._accent_idle = readable_on(idle_raw, opaque_bg, 3.5)
        self.apply_scale(self.ui_scale)
        self.refresh()

    # -- report ingestion ---------------------------------------------------
    def set_local_state(self, state: dict) -> None:
        """Feed a :class:`BossDebuffDetector` snapshot for this machine."""
        self._store("나", state.get("active"), state.get("remaining"), state.get("source", ""))

    def ingest_party_states(self, party_states: dict, exclude_player: str = "") -> None:
        """Pick up boss debuff reports relayed from other party members."""
        key = party_state_key(self.debuff_id)
        now = time.time()
        for player, entries in (party_states or {}).items():
            if not isinstance(entries, dict) or player == exclude_player:
                continue
            report = entries.get(key)
            if not isinstance(report, dict):
                continue
            try:
                timestamp = float(report.get("timestamp", now) or now)
                remaining = float(report.get("cooldown_duration", 0) or 0)
            except (TypeError, ValueError):
                continue
            # Reports arrive with the sender's remaining time; age it locally.
            aged = remaining - max(0.0, now - timestamp)
            self._store(player, bool(report.get("is_ready", False)),
                        aged if remaining > 0 else None, "party", received_at=timestamp)

    def _store(self, origin: str, active, remaining, source: str, received_at: float = None) -> None:
        now = time.time()
        received_at = now if received_at is None else min(float(received_at), now)
        deadline = None
        if remaining is not None:
            try:
                deadline = received_at + max(0.0, float(remaining))
            except (TypeError, ValueError):
                deadline = None
        self._reports[origin] = {
            "active": bool(active),
            "deadline": deadline,
            "source": source or "",
            "received_at": received_at,
        }
        self.refresh()

    def clear(self) -> None:
        self._reports.clear()
        self.refresh()

    def clear_local(self) -> None:
        """Drop only this machine's report; party reports stay visible."""
        self._reports.pop("나", None)
        self.refresh()

    def has_reports(self) -> bool:
        now = time.time()
        return any(now - v["received_at"] <= REPORT_STALE_AFTER for v in self._reports.values())

    # -- rendering ----------------------------------------------------------
    def _best_report(self):
        now = time.time()
        fresh = {k: v for k, v in self._reports.items() if now - v["received_at"] <= REPORT_STALE_AFTER}
        self._reports = fresh
        active = [(k, v) for k, v in fresh.items() if v["active"]]
        if not active:
            return None, None
        # Local detection wins; otherwise the most recent party report does.
        active.sort(key=lambda item: (item[0] != "나", -item[1]["received_at"]))
        return active[0]

    def refresh(self) -> None:
        origin, report = self._best_report()
        if report is None:
            self.value_label.setText("OFF")
            self.value_label.setStyleSheet(self._value_style(self._accent_idle))
            self.detail_label.setText("보스에게 없음")
            self.setStyleSheet(self._card_style(False))
            return

        deadline = report.get("deadline")
        remaining = None if deadline is None else max(0.0, deadline - time.time())
        if remaining is None:
            self.value_label.setText("ON")
            detail = "적용 중 · 남은 시간 확인 불가"
        elif remaining >= 1.0:
            self.value_label.setText(f"{int(math.ceil(remaining))}초")
            detail = "적용 중"
        else:
            self.value_label.setText(f"{remaining:.1f}초")
            detail = "곧 해제"

        source = report.get("source", "")
        if source == "duration":
            detail += " · 추정"
        elif source == "ocr":
            detail += " · OCR"
        elif source == "anchor":
            detail += " · 자동 보정"
        if origin and origin != "나":
            detail += f" · {origin} 감지"

        self.detail_label.setText(detail)
        self.value_label.setStyleSheet(self._value_style(self._accent_active))
        self.setStyleSheet(self._card_style(True))

    def tick(self) -> None:
        """Called from the party panel's 60fps timer."""
        self.refresh()
