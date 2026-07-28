"""Boss debuff banner shown on top of the party status panel.

Kept in its own module on purpose: the party panel visual redesign is being
developed in parallel, so this widget only needs its two public calls
(:meth:`set_local_state` / :meth:`ingest_party_states`) re-hooked after a merge.
"""

from __future__ import annotations

import math
import time

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

import boss_debuff_detector as bdd

# Party-sync channel: the panel skips every '_'-prefixed key when it renders
# skill badges, so a boss debuff report can never be drawn as a fake skill.
PARTY_STATE_PREFIX = "_bossdebuff:"
REPORT_STALE_AFTER = 6.0   # seconds without a refresh before a report is dropped


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
        self._accent_active = "#ff453a"
        self._accent_idle = "#8e8e93"

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
            f"font-size: {int(12 * self.ui_scale)}px; font-weight: 700; background: transparent; border: none;")
        self.detail_label.setStyleSheet(
            f"font-size: {int(9 * self.ui_scale)}px; font-weight: 600; color: #8e8e93; "
            "background: transparent; border: none;")
        self.value_label.setStyleSheet(
            f"font-size: {int(18 * self.ui_scale)}px; font-weight: 800; background: transparent; border: none;")

    def apply_theme(self, theme: dict) -> None:
        self._accent_active = theme.get("cooldown", "#ff453a")
        self._accent_idle = "#8e8e93"
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
            self.value_label.setStyleSheet(
                f"font-size: {int(18 * self.ui_scale)}px; font-weight: 800; color: {self._accent_idle}; "
                "background: transparent; border: none;")
            self.detail_label.setText("보스에게 없음")
            self.setStyleSheet(
                "QFrame.BossDebuffCard { background-color: rgba(255,255,255,0.03); "
                "border: 1.2px solid rgba(255,255,255,0.06); border-radius: 12px; }")
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
        self.value_label.setStyleSheet(
            f"font-size: {int(18 * self.ui_scale)}px; font-weight: 800; color: {self._accent_active}; "
            "background: transparent; border: none;")
        self.setStyleSheet(
            "QFrame.BossDebuffCard { background-color: rgba(255,69,58,0.10); "
            "border: 1.2px solid rgba(255,69,58,0.35); border-radius: 12px; }")

    def tick(self) -> None:
        """Called from the party panel's 60fps timer."""
        self.refresh()
