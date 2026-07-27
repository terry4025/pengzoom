"""펭구 줌인 Pro — UI/UX 리디자인 시안 렌더러.

3개 시안(A: Obsidian Pro / B: Aurora Glass / C: Tactical HUD)의
파티 현황 패널과 메인 돋보기 창을 PNG로 렌더링한다.

실행:
    python design_preview/render_concepts.py

이 파일은 시안 확정용 목업 전용이며, 확정 후 실제 구현으로 이식한다.
"""

import os
import sys

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                         QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QWidget

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                         "PengZoom", "cache")

# ---------------------------------------------------------------- 목업 데이터
CLASS_KEY = {
    "홀리나이트": "holyknight",
    "바드": "bard",
    "도화가": "artist",
    "소서리스": "elemental_master",
    "브레이커": "breaker",
    "발키리": "valkyrie",
}

# (플레이어, 클래스, [(스킬명, 준비여부, 남은초, 전체쿨)])
PARTY = [
    ("펭구", "홀리나이트", [
        ("헤븐리블레싱", True, 0.0, 60.0),
        ("소드오브저지먼트", False, 18.4, 36.0),
    ]),
    ("테리4025", "바드", [
        ("천상의 하모니", True, 0.0, 45.0),
        ("사운드홀릭", False, 3.2, 24.0),
        ("하베스트송", False, 41.0, 60.0),
    ]),
    ("붓칼", "도화가", [
        ("문양: 해ризон", True, 0.0, 48.0),
        ("색채의 마술", False, 9.8, 30.0),
    ]),
    ("불꽃마법사", "소서리스", [
        ("점화", False, 27.5, 40.0),
    ]),
]
PARTY[2] = ("붓칼", "도화가", [
    ("문양: 해", True, 0.0, 48.0),
    ("색채의 마술", False, 9.8, 30.0),
])

_svg_cache: dict = {}


def emblem_pixmap(class_name: str, size: int, color: str) -> QPixmap:
    """로스트아크 공식 클래스 엠블럼을 단색 마스크로 렌더."""
    key = (class_name, size, color)
    if key in _svg_cache:
        return _svg_cache[key]
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    base = CLASS_KEY.get(class_name)
    path = os.path.join(CACHE_DIR, f"class_{base}.svg") if base else None
    if path and os.path.exists(path):
        renderer = QSvgRenderer(path)
        if renderer.isValid():
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(p)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            p.fillRect(pm.rect(), QColor(color))
            p.end()
            _svg_cache[key] = pm
            return pm
    # 폴백: 방패 실루엣
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path_obj = QPainterPath()
    path_obj.moveTo(size * 0.5, size * 0.06)
    path_obj.lineTo(size * 0.92, size * 0.26)
    path_obj.lineTo(size * 0.78, size * 0.88)
    path_obj.lineTo(size * 0.5, size * 0.98)
    path_obj.lineTo(size * 0.22, size * 0.88)
    path_obj.lineTo(size * 0.08, size * 0.26)
    path_obj.closeSubpath()
    p.fillPath(path_obj, QBrush(QColor(color)))
    p.end()
    _svg_cache[key] = pm
    return pm


def font(size: int, weight: int = 400, mono: bool = False) -> QFont:
    family = "Consolas" if mono else "Segoe UI"
    f = QFont(family, size)
    f.setWeight(QFont.Weight(weight))
    return f


def rounded(painter: QPainter, rect: QRectF, radius: float,
            fill: QColor | QBrush | None = None,
            border: QColor | None = None, border_w: float = 1.0) -> None:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    if fill is not None:
        painter.fillPath(path, QBrush(fill) if isinstance(fill, QColor) else fill)
    if border is not None:
        painter.strokePath(path, QPen(border, border_w))


def elide(painter: QPainter, text: str, width: int) -> str:
    return QFontMetrics(painter.font()).elidedText(
        text, Qt.TextElideMode.ElideRight, width)


# ===========================================================================
# 시안 A — Obsidian Pro : 무채색 + 단일 액센트, 절제된 프리미엄
# ===========================================================================
A = {
    "bg": QColor(14, 14, 17, 240),
    "border": QColor(255, 255, 255, 20),
    "hairline": QColor(255, 255, 255, 14),
    "text": QColor(245, 245, 247),
    "text_dim": QColor(245, 245, 247, 120),
    "text_faint": QColor(245, 245, 247, 80),
    "card": QColor(255, 255, 255, 8),
    "ready": QColor(48, 209, 88),
    "cool": QColor(255, 159, 10),
    "accent": QColor(10, 132, 255),
}


class PartyA(QWidget):
    """헤더 + 좌측 상태바 + 스킬 칩. 정보 위계를 폰트/명도로만 구분."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(312, 452)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(6, 6, self.width() - 12, self.height() - 12)
        rounded(p, r, 18, A["bg"], A["border"], 1.2)

        x, w = r.x() + 16, r.width() - 32
        y = r.y() + 15

        # 헤더: 브랜드 마크 + 워드마크 + 인원 배지
        rounded(p, QRectF(x, y, 20, 20), 6, QColor(255, 255, 255, 16))
        p.setPen(QPen(A["text"]))
        p.setFont(font(9, 700))
        p.drawText(QRectF(x, y, 20, 20), Qt.AlignmentFlag.AlignCenter, "🐧")

        p.setFont(font(9, 700))
        p.setPen(QPen(A["text_dim"]))
        f = p.font()
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.6)
        p.setFont(f)
        p.drawText(QRectF(x + 28, y, 160, 20),
                   Qt.AlignmentFlag.AlignVCenter, "PARTY  STATUS")

        badge = QRectF(r.right() - 16 - 46, y + 2, 46, 16)
        rounded(p, badge, 8, QColor(48, 209, 88, 28), QColor(48, 209, 88, 70), 1.0)
        p.setPen(QPen(A["ready"]))
        p.setFont(font(8, 700))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, "LIVE  4")

        y += 30
        p.setPen(QPen(A["hairline"], 1))
        p.drawLine(int(x), int(y), int(x + w), int(y))
        y += 12

        for name, cls, skills in PARTY:
            any_ready = any(s[1] for s in skills)
            rows = len(skills)
            ch = 34 + rows * 24
            card = QRectF(x, y, w, ch)
            rounded(p, card, 12, A["card"], QColor(255, 255, 255, 10), 1.0)

            # 좌측 상태 액센트 바 (준비 스킬 유무)
            bar = QRectF(x + 1.5, y + 9, 3, ch - 18)
            rounded(p, bar, 1.5,
                    A["ready"] if any_ready else QColor(255, 255, 255, 26))

            ix = x + 14
            p.drawPixmap(int(ix), int(y + 9), emblem_pixmap(cls, 22, "#f5f5f7"))
            p.setPen(QPen(A["text"]))
            p.setFont(font(11, 700))
            p.drawText(QRectF(ix + 30, y + 8, w - 120, 24),
                       Qt.AlignmentFlag.AlignVCenter, name)

            rd = sum(1 for s in skills if s[1])
            p.setFont(font(8, 600))
            p.setPen(QPen(A["ready"] if rd else A["text_faint"]))
            p.drawText(QRectF(x, y + 8, w - 14, 24),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{rd}/{rows} READY")

            sy = y + 32
            for sname, ready, rem, total in skills:
                chip = QRectF(ix, sy, w - 28, 20)
                if ready:
                    rounded(p, chip, 7, QColor(48, 209, 88, 26),
                            QColor(48, 209, 88, 64), 1.0)
                    p.setBrush(QBrush(A["ready"]))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(chip.x() + 11, chip.center().y()), 3.2, 3.2)
                    p.setPen(QPen(A["text"]))
                    p.setFont(font(9, 600))
                    p.drawText(QRectF(chip.x() + 22, chip.y(), chip.width() - 70, 20),
                               Qt.AlignmentFlag.AlignVCenter, elide(p, sname, int(chip.width()) - 70))
                    p.setPen(QPen(A["ready"]))
                    p.setFont(font(8, 700))
                    p.drawText(chip.adjusted(0, 0, -9, 0),
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                               "READY")
                else:
                    rounded(p, chip, 7, QColor(255, 255, 255, 6),
                            QColor(255, 255, 255, 12), 1.0)
                    # 미니 링
                    ring = QRectF(chip.x() + 5, chip.y() + 4, 12, 12)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(255, 255, 255, 24), 2))
                    p.drawEllipse(ring)
                    pen = QPen(A["cool"], 2)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen)
                    p.drawArc(ring, 90 * 16, -int((rem / total) * 360 * 16))
                    p.setPen(QPen(A["text_dim"]))
                    p.setFont(font(9, 500))
                    p.drawText(QRectF(chip.x() + 22, chip.y(), chip.width() - 70, 20),
                               Qt.AlignmentFlag.AlignVCenter, elide(p, sname, int(chip.width()) - 70))
                    p.setPen(QPen(A["cool"]))
                    p.setFont(font(9, 700, mono=True))
                    txt = f"{rem:.1f}s" if rem < 10 else f"{int(rem)}s"
                    p.drawText(chip.adjusted(0, 0, -9, 0),
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, txt)
                sy += 24
            y += ch + 8


class MainA(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(424, 544)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(6, 6, self.width() - 12, self.height() - 12)
        rounded(p, r, 18, QColor(20, 20, 23, 240), A["border"], 1.4)

        x, w = r.x() + 16, r.width() - 32
        y = r.y() + 14

        # 브랜드 타이틀바 (신규)
        rounded(p, QRectF(x, y, 22, 22), 7, QColor(255, 255, 255, 16))
        p.setPen(QPen(A["text"]))
        p.setFont(font(10, 700))
        p.drawText(QRectF(x, y, 22, 22), Qt.AlignmentFlag.AlignCenter, "🐧")
        p.setFont(font(10, 700))
        p.drawText(QRectF(x + 30, y, 140, 22), Qt.AlignmentFlag.AlignVCenter, "PENGU ZOOM")
        vb = QRectF(x + 122, y + 5, 34, 13)
        rounded(p, vb, 6, QColor(255, 255, 255, 16))
        p.setPen(QPen(A["text_faint"]))
        p.setFont(font(7, 600))
        p.drawText(vb, Qt.AlignmentFlag.AlignCenter, "2.46")

        # 무채색 아이콘 버튼 4개 (원색 제거)
        bx = r.right() - 16 - 26
        for glyph in ("✕", "?", "⚙", "—"):
            b = QRectF(bx, y, 22, 22)
            rounded(p, b, 7, QColor(255, 255, 255, 10), QColor(255, 255, 255, 16), 1.0)
            p.setPen(QPen(A["text_dim"]))
            p.setFont(font(9, 600))
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, glyph)
            bx -= 26
        y += 34

        # 세그먼티드 컨트롤 (영역지정 / 따라오기 / 투과)
        seg = QRectF(x, y, w, 30)
        rounded(p, seg, 9, QColor(255, 255, 255, 8), QColor(255, 255, 255, 12), 1.0)
        sw = w / 3
        active = QRectF(x + sw + 2, y + 2, sw - 4, 26)
        rounded(p, active, 7, QColor(10, 132, 255, 210))
        for i, lbl in enumerate(("영역 지정", "따라오기", "마우스 투과")):
            p.setPen(QPen(A["text"] if i == 1 else A["text_dim"]))
            p.setFont(font(9, 700 if i == 1 else 500))
            p.drawText(QRectF(x + sw * i, y, sw, 30), Qt.AlignmentFlag.AlignCenter, lbl)
        y += 40

        # 뷰포트
        vp = QRectF(x, y, w, r.bottom() - y - 92)
        rounded(p, vp, 12, QColor(0, 0, 0), QColor(255, 255, 255, 18), 1.0)
        clip = QPainterPath()
        clip.addRoundedRect(vp, 12, 12)
        p.save()
        p.setClipPath(clip)
        g = QLinearGradient(vp.topLeft(), vp.bottomRight())
        g.setColorAt(0.0, QColor(30, 41, 59))
        g.setColorAt(0.5, QColor(15, 23, 42))
        g.setColorAt(1.0, QColor(38, 24, 44))
        p.fillRect(vp, QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        step = 22
        gx = vp.x()
        while gx < vp.right():
            p.drawLine(int(gx), int(vp.y()), int(gx), int(vp.bottom()))
            gx += step
        gy = vp.y()
        while gy < vp.bottom():
            p.drawLine(int(vp.x()), int(gy), int(vp.right()), int(gy))
            gy += step
        p.setPen(QPen(QColor(255, 255, 255, 90)))
        p.setFont(font(9, 500))
        p.drawText(vp, Qt.AlignmentFlag.AlignCenter, "확대 화면 (2.0x)")
        p.restore()
        # 좌상단 배율 HUD 배지 (신규)
        hud = QRectF(vp.x() + 10, vp.y() + 10, 50, 20)
        rounded(p, hud, 7, QColor(0, 0, 0, 150), QColor(255, 255, 255, 24), 1.0)
        p.setPen(QPen(A["text"]))
        p.setFont(font(9, 700, mono=True))
        p.drawText(hud, Qt.AlignmentFlag.AlignCenter, "2.0x")
        y = vp.bottom() + 14

        for label, val, pct, accent in (("배율", "2.0x", 0.10, A["accent"]),
                                        ("투명도", "100%", 1.0, A["accent"])):
            p.setPen(QPen(A["text_faint"]))
            p.setFont(font(8, 600))
            p.drawText(QRectF(x, y, 60, 14), Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QPen(A["text"]))
            p.setFont(font(9, 700, mono=True))
            p.drawText(QRectF(x, y, w, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)
            track = QRectF(x, y + 19, w, 4)
            rounded(p, track, 2, QColor(255, 255, 255, 22))
            rounded(p, QRectF(x, y + 19, w * pct, 4), 2, accent)
            p.setBrush(QBrush(QColor(255, 255, 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x + w * pct, y + 21), 6, 6)
            y += 34


# ===========================================================================
# 시안 B — Aurora Glass : 글래스모피즘 + 클래스 컬러 그라디언트, 화려한 프리미엄
# ===========================================================================
CLASS_COLOR = {
    "홀리나이트": (QColor(96, 165, 250), QColor(59, 130, 246)),
    "바드": (QColor(196, 181, 253), QColor(139, 92, 246)),
    "도화가": (QColor(253, 186, 116), QColor(244, 114, 182)),
    "소서리스": (QColor(94, 234, 212), QColor(45, 212, 191)),
}
B = {
    "bg": QColor(11, 13, 18, 226),
    "text": QColor(232, 236, 245),
    "dim": QColor(232, 236, 245, 130),
    "faint": QColor(232, 236, 245, 85),
    "ready": QColor(52, 211, 153),
    "cool": QColor(251, 146, 60),
}


def glow(p: QPainter, center: QPointF, radius: float, color: QColor, alpha: int):
    g = QRadialGradient(center, radius)
    c0 = QColor(color)
    c0.setAlpha(alpha)
    c1 = QColor(color)
    c1.setAlpha(0)
    g.setColorAt(0.0, c0)
    g.setColorAt(1.0, c1)
    p.setBrush(QBrush(g))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(center, radius, radius)


class PartyB(QWidget):
    """카드 상단 클래스 컬러 헤어라인 + 선형 게이지 + 발광 Ready 카드."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(330, 512)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(8, 8, self.width() - 16, self.height() - 16)

        # 외곽 그라디언트 보더
        border = QLinearGradient(r.topLeft(), r.bottomRight())
        border.setColorAt(0.0, QColor(99, 102, 241, 150))
        border.setColorAt(0.5, QColor(168, 85, 247, 90))
        border.setColorAt(1.0, QColor(56, 189, 248, 130))
        rounded(p, r, 22, B["bg"])
        path = QPainterPath()
        path.addRoundedRect(r, 22, 22)
        p.strokePath(path, QPen(QBrush(border), 1.6))

        x, w = r.x() + 18, r.width() - 36
        y = r.y() + 16

        # 헤더
        p.setPen(QPen(B["text"]))
        p.setFont(font(13, 800))
        p.drawText(QRectF(x, y, 200, 20), Qt.AlignmentFlag.AlignVCenter, "파티 현황")
        p.setPen(QPen(B["faint"]))
        p.setFont(font(8, 500))
        p.drawText(QRectF(x, y + 19, 220, 14),
                   Qt.AlignmentFlag.AlignVCenter, "실시간 쿨타임 동기화 · 4명 접속")
        dot = QPointF(r.right() - 26, y + 10)
        glow(p, dot, 9, B["ready"], 110)
        p.setBrush(QBrush(B["ready"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(dot, 3.4, 3.4)
        y += 42

        for name, cls, skills in PARTY:
            c0, c1 = CLASS_COLOR.get(cls, (QColor(148, 163, 184), QColor(100, 116, 139)))
            any_ready = any(s[1] for s in skills)
            ch = 36 + len(skills) * 28
            card = QRectF(x, y, w, ch)

            if any_ready:
                glow(p, QPointF(card.x() + 14, card.center().y()), 46, B["ready"], 42)
            rounded(p, card, 16, QColor(255, 255, 255, 10), QColor(255, 255, 255, 16), 1.0)

            # 상단 클래스 컬러 헤어라인
            hair = QLinearGradient(card.topLeft(), card.topRight())
            hair.setColorAt(0.0, c0)
            hc = QColor(c1)
            hc.setAlpha(0)
            hair.setColorAt(1.0, hc)
            hp = QPainterPath()
            hp.addRoundedRect(QRectF(card.x() + 10, card.y(), card.width() - 20, 2), 1, 1)
            p.fillPath(hp, QBrush(hair))

            # 엠블럼 (클래스 컬러 링)
            ec = QPointF(card.x() + 24, card.y() + 22)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(c0.red(), c0.green(), c0.blue(), 130), 1.4))
            p.drawEllipse(ec, 14, 14)
            p.drawPixmap(int(ec.x() - 10), int(ec.y() - 10), emblem_pixmap(cls, 20, c0.name()))

            p.setPen(QPen(B["text"]))
            p.setFont(font(12, 700))
            p.drawText(QRectF(card.x() + 44, card.y() + 10, w - 130, 24),
                       Qt.AlignmentFlag.AlignVCenter, name)
            rd = sum(1 for s in skills if s[1])
            pill = QRectF(card.right() - 14 - 60, card.y() + 14, 60, 16)
            rounded(p, pill, 8,
                    QColor(52, 211, 153, 34) if rd else QColor(255, 255, 255, 10),
                    QColor(52, 211, 153, 90) if rd else QColor(255, 255, 255, 16), 1.0)
            p.setPen(QPen(B["ready"] if rd else B["faint"]))
            p.setFont(font(8, 700))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, f"{rd}/{len(skills)} READY")

            sy = card.y() + 38
            for sname, ready, rem, total in skills:
                p.setPen(QPen(B["text"] if ready else B["dim"]))
                p.setFont(font(9, 600))
                p.drawText(QRectF(card.x() + 16, sy, w - 100, 14),
                           Qt.AlignmentFlag.AlignVCenter, elide(p, sname, int(w) - 100))
                p.setFont(font(10, 700, mono=True))
                p.setPen(QPen(B["ready"] if ready else B["cool"]))
                p.drawText(QRectF(card.x(), sy, w - 16, 14),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           "READY" if ready else (f"{rem:.1f}" if rem < 10 else f"{int(rem)}"))
                track = QRectF(card.x() + 16, sy + 17, w - 32, 4)
                rounded(p, track, 2, QColor(255, 255, 255, 18))
                pct = 1.0 if ready else max(0.02, rem / total)
                fg = QLinearGradient(track.topLeft(), track.topRight())
                if ready:
                    fg.setColorAt(0.0, QColor(52, 211, 153))
                    fg.setColorAt(1.0, QColor(16, 185, 129))
                else:
                    fg.setColorAt(0.0, QColor(251, 191, 36))
                    fg.setColorAt(1.0, QColor(249, 115, 22))
                rounded(p, QRectF(track.x(), track.y(), track.width() * pct, 4), 2, QBrush(fg))
                sy += 28
            y += ch + 10


class MainB(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(424, 544)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(8, 8, self.width() - 16, self.height() - 16)
        rounded(p, r, 22, QColor(11, 13, 18, 232))
        bg = QLinearGradient(r.topLeft(), r.bottomRight())
        bg.setColorAt(0.0, QColor(99, 102, 241, 140))
        bg.setColorAt(0.5, QColor(168, 85, 247, 80))
        bg.setColorAt(1.0, QColor(56, 189, 248, 120))
        path = QPainterPath()
        path.addRoundedRect(r, 22, 22)
        p.strokePath(path, QPen(QBrush(bg), 1.6))

        x, w = r.x() + 18, r.width() - 36
        y = r.y() + 16
        glow(p, QPointF(x + 12, y + 12), 26, QColor(129, 140, 248), 90)
        p.drawPixmap(int(x), int(y), 24, 24, penguin_badge(24))
        p.setPen(QPen(B["text"]))
        p.setFont(font(12, 800))
        p.drawText(QRectF(x + 32, y - 2, 200, 18), Qt.AlignmentFlag.AlignVCenter, "Pengu Zoom")
        p.setPen(QPen(B["faint"]))
        p.setFont(font(7, 600))
        p.drawText(QRectF(x + 32, y + 15, 200, 12), Qt.AlignmentFlag.AlignVCenter, "PRO  v2.46")
        bx = r.right() - 18 - 24
        for glyph, col in (("✕", QColor(248, 113, 113)), ("?", B["dim"]),
                           ("⚙", B["dim"]), ("—", B["dim"])):
            b = QRectF(bx, y + 1, 22, 22)
            rounded(p, b, 11, QColor(255, 255, 255, 12), QColor(255, 255, 255, 20), 1.0)
            p.setPen(QPen(col))
            p.setFont(font(9, 700))
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, glyph)
            bx -= 26
        y += 40

        vp = QRectF(x, y, w, r.bottom() - y - 118)
        rounded(p, vp, 16, QColor(0, 0, 0))
        clip = QPainterPath()
        clip.addRoundedRect(vp, 16, 16)
        p.save()
        p.setClipPath(clip)
        g = QLinearGradient(vp.topLeft(), vp.bottomRight())
        g.setColorAt(0.0, QColor(30, 41, 59))
        g.setColorAt(0.5, QColor(15, 23, 42))
        g.setColorAt(1.0, QColor(49, 22, 60))
        p.fillRect(vp, QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 10), 1))
        gx = vp.x()
        while gx < vp.right():
            p.drawLine(int(gx), int(vp.y()), int(gx), int(vp.bottom()))
            gx += 22
        gy = vp.y()
        while gy < vp.bottom():
            p.drawLine(int(vp.x()), int(gy), int(vp.right()), int(gy))
            gy += 22
        p.setPen(QPen(QColor(255, 255, 255, 95)))
        p.setFont(font(9, 500))
        p.drawText(vp, Qt.AlignmentFlag.AlignCenter, "확대 화면 (2.0x)")
        p.restore()
        p.strokePath(clip, QPen(QBrush(bg), 1.2))
        y = vp.bottom() + 14

        # 플로팅 독 (컨트롤 집약)
        dock = QRectF(x, y, w, 40)
        rounded(p, dock, 14, QColor(255, 255, 255, 12), QColor(255, 255, 255, 22), 1.0)
        items = [("영역 지정", False), ("따라오기", True), ("투과", False), ("숨김", False)]
        iw = w / len(items)
        for i, (lbl, on) in enumerate(items):
            cell = QRectF(x + iw * i, y, iw, 40)
            if on:
                inner = QRectF(cell.x() + 5, y + 5, iw - 10, 30)
                ig = QLinearGradient(inner.topLeft(), inner.bottomRight())
                ig.setColorAt(0.0, QColor(99, 102, 241, 230))
                ig.setColorAt(1.0, QColor(168, 85, 247, 210))
                rounded(p, inner, 11, QBrush(ig))
            p.setPen(QPen(B["text"] if on else B["dim"]))
            p.setFont(font(9, 700 if on else 500))
            p.drawText(cell, Qt.AlignmentFlag.AlignCenter, lbl)
        y += 50

        for label, val, pct in (("배율", "2.0x", 0.10), ("투명도", "100%", 1.0)):
            p.setPen(QPen(B["faint"]))
            p.setFont(font(8, 600))
            p.drawText(QRectF(x, y, 60, 14), Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QPen(B["text"]))
            p.setFont(font(9, 700, mono=True))
            p.drawText(QRectF(x, y, w, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)
            track = QRectF(x, y + 18, w, 5)
            rounded(p, track, 2.5, QColor(255, 255, 255, 20))
            fg = QLinearGradient(track.topLeft(), track.topRight())
            fg.setColorAt(0.0, QColor(99, 102, 241))
            fg.setColorAt(1.0, QColor(168, 85, 247))
            rounded(p, QRectF(x, y + 18, max(10.0, w * pct), 5), 2.5, QBrush(fg))
            glow(p, QPointF(x + max(10.0, w * pct), y + 20.5), 12, QColor(168, 85, 247), 120)
            p.setBrush(QBrush(QColor(255, 255, 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x + max(10.0, w * pct), y + 20.5), 6, 6)
            y += 32


def penguin_badge(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0.0, QColor(129, 140, 248))
    g.setColorAt(1.0, QColor(56, 189, 248))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), size * 0.3, size * 0.3)
    p.fillPath(path, QBrush(g))
    p.setPen(QPen(QColor(255, 255, 255)))
    f = QFont("Segoe UI Emoji", int(size * 0.45))
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "🐧")
    p.end()
    return pm


# ===========================================================================
# 시안 C — Tactical HUD : 각진 프레임 + 테이블형 고밀도, 실전 가독성 최우선
# ===========================================================================
C = {
    "bg": QColor(8, 9, 11, 242),
    "line": QColor(42, 47, 58),
    "row": QColor(22, 25, 31),
    "text": QColor(226, 232, 240),
    "dim": QColor(148, 163, 184),
    "gold": QColor(232, 180, 74),
    "ready": QColor(74, 222, 128),
    "cool": QColor(248, 113, 113),
}


def bracket(p: QPainter, r: QRectF, size: float, color: QColor, w: float = 1.6):
    p.setPen(QPen(color, w))
    for cx, cy, dx, dy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                           (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
        p.drawLine(QPointF(cx, cy), QPointF(cx + size * dx, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + size * dy))


class PartyC(QWidget):
    """행=플레이어, 열=스킬. 4인 파티를 한 화면에서 스캔."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(392, 306)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(8, 8, self.width() - 16, self.height() - 16)
        rounded(p, r, 5, C["bg"], C["line"], 1.2)
        bracket(p, r.adjusted(3, 3, -3, -3), 11, C["gold"], 1.6)

        x, w = r.x() + 14, r.width() - 28
        y = r.y() + 13

        p.setFont(font(9, 800, mono=True))
        f = p.font()
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
        p.setFont(f)
        p.setPen(QPen(C["gold"]))
        p.drawText(QRectF(x, y, 240, 16), Qt.AlignmentFlag.AlignVCenter,
                   "PARTY // COOLDOWN")
        p.setPen(QPen(C["ready"]))
        p.setFont(font(8, 700, mono=True))
        p.drawText(QRectF(x, y, w, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "● LIVE")
        y += 20
        p.setPen(QPen(C["gold"], 1))
        p.drawLine(int(x), int(y), int(x + w), int(y))
        y += 4

        p.setPen(QPen(C["dim"]))
        p.setFont(font(7, 700, mono=True))
        p.drawText(QRectF(x + 4, y, 120, 14), Qt.AlignmentFlag.AlignVCenter, "OPERATIVE")
        p.drawText(QRectF(x + 132, y, w - 136, 14), Qt.AlignmentFlag.AlignVCenter, "SKILL / STATE")
        y += 18

        for idx, (name, cls, skills) in enumerate(PARTY):
            rh = 26 + max(0, len(skills) - 1) * 0
            row = QRectF(x, y, w, 50)
            if idx % 2 == 0:
                rounded(p, row, 3, C["row"])
            any_ready = any(s[1] for s in skills)
            if any_ready:
                p.setBrush(QBrush(C["ready"]))
                p.setPen(Qt.PenStyle.NoPen)
                tri = QPainterPath()
                tri.moveTo(row.x() + 3, row.center().y() - 5)
                tri.lineTo(row.x() + 9, row.center().y())
                tri.lineTo(row.x() + 3, row.center().y() + 5)
                tri.closeSubpath()
                p.fillPath(tri, QBrush(C["ready"]))

            p.drawPixmap(int(row.x() + 15), int(row.y() + 6), emblem_pixmap(cls, 18, "#e2e8f0"))
            p.setPen(QPen(C["text"]))
            p.setFont(font(10, 700))
            p.drawText(QRectF(row.x() + 38, row.y() + 4, 92, 16),
                       Qt.AlignmentFlag.AlignVCenter, elide(p, name, 92))
            p.setPen(QPen(C["dim"]))
            p.setFont(font(7, 500))
            p.drawText(QRectF(row.x() + 38, row.y() + 20, 92, 14),
                       Qt.AlignmentFlag.AlignVCenter, cls)

            cx = row.x() + 134
            cell_w = (row.width() - 140) / max(1, len(skills))
            for sname, ready, rem, total in skills:
                cell = QRectF(cx, row.y() + 4, cell_w - 5, 42)
                rounded(p, cell, 3,
                        QColor(74, 222, 128, 26) if ready else QColor(255, 255, 255, 8),
                        QColor(74, 222, 128, 96) if ready else C["line"], 1.0)
                p.setPen(QPen(C["dim"]))
                p.setFont(font(7, 600))
                p.drawText(QRectF(cell.x() + 5, cell.y() + 2, cell.width() - 10, 12),
                           Qt.AlignmentFlag.AlignVCenter, elide(p, sname, int(cell.width()) - 10))
                if ready:
                    p.setPen(QPen(C["ready"]))
                    p.setFont(font(13, 800, mono=True))
                    p.drawText(QRectF(cell.x(), cell.y() + 13, cell.width(), 20),
                               Qt.AlignmentFlag.AlignCenter, "RDY")
                else:
                    p.setPen(QPen(C["text"]))
                    p.setFont(font(15, 800, mono=True))
                    txt = f"{rem:.1f}" if rem < 10 else f"{int(rem)}"
                    p.drawText(QRectF(cell.x(), cell.y() + 12, cell.width(), 22),
                               Qt.AlignmentFlag.AlignCenter, txt)
                    track = QRectF(cell.x() + 4, cell.bottom() - 6, cell.width() - 8, 2)
                    rounded(p, track, 1, QColor(255, 255, 255, 22))
                    rounded(p, QRectF(track.x(), track.y(),
                                      track.width() * (rem / total), 2), 1, C["cool"])
                cx += cell_w
            y += 54
            if idx < len(PARTY) - 1:
                p.setPen(QPen(C["line"], 1))
                p.drawLine(int(x), int(y - 3), int(x + w), int(y - 3))


class MainC(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(424, 544)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(8, 8, self.width() - 16, self.height() - 16)
        rounded(p, r, 6, C["bg"], C["line"], 1.4)
        bracket(p, r.adjusted(4, 4, -4, -4), 14, C["gold"], 1.8)

        x, w = r.x() + 16, r.width() - 32
        y = r.y() + 15

        p.setPen(QPen(C["gold"], 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(x, y, 22, 22))
        p.setFont(font(10, 800))
        p.drawText(QRectF(x, y, 22, 22), Qt.AlignmentFlag.AlignCenter, "P")
        p.setPen(QPen(C["text"]))
        p.setFont(font(10, 800, mono=True))
        fx = p.font()
        fx.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        p.setFont(fx)
        p.drawText(QRectF(x + 30, y - 2, 200, 18), Qt.AlignmentFlag.AlignVCenter, "PENGU ZOOM")
        p.setPen(QPen(C["gold"]))
        p.setFont(font(7, 700, mono=True))
        p.drawText(QRectF(x + 30, y + 14, 200, 12), Qt.AlignmentFlag.AlignVCenter, "PRO v2.46")

        bx = r.right() - 16 - 24
        for glyph, col in (("✕", C["cool"]), ("?", C["dim"]), ("⚙", C["dim"]), ("—", C["dim"])):
            b = QRectF(bx, y, 22, 22)
            rounded(p, b, 3, QColor(255, 255, 255, 8), C["line"], 1.0)
            p.setPen(QPen(col))
            p.setFont(font(9, 700))
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, glyph)
            bx -= 27
        y += 32
        p.setPen(QPen(C["line"], 1))
        p.drawLine(int(x), int(y), int(x + w), int(y))
        y += 10

        for i, (lbl, on) in enumerate((("AREA", False), ("FOLLOW", True),
                                       ("PASS-THRU", False), ("HIDE", False))):
            bw = w / 4
            b = QRectF(x + bw * i + 2, y, bw - 4, 26)
            rounded(p, b, 3,
                    QColor(232, 180, 74, 34) if on else QColor(255, 255, 255, 8),
                    C["gold"] if on else C["line"], 1.0)
            p.setPen(QPen(C["gold"] if on else C["dim"]))
            p.setFont(font(8, 800, mono=True))
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, lbl)
        y += 36

        vp = QRectF(x, y, w, r.bottom() - y - 96)
        rounded(p, vp, 3, QColor(0, 0, 0), C["line"], 1.0)
        clip = QPainterPath()
        clip.addRoundedRect(vp, 3, 3)
        p.save()
        p.setClipPath(clip)
        g = QLinearGradient(vp.topLeft(), vp.bottomRight())
        g.setColorAt(0.0, QColor(24, 28, 34))
        g.setColorAt(1.0, QColor(12, 14, 18))
        p.fillRect(vp, QBrush(g))
        p.setPen(QPen(QColor(232, 180, 74, 22), 1))
        gx = vp.x()
        while gx < vp.right():
            p.drawLine(int(gx), int(vp.y()), int(gx), int(vp.bottom()))
            gx += 24
        gy = vp.y()
        while gy < vp.bottom():
            p.drawLine(int(vp.x()), int(gy), int(vp.right()), int(gy))
            gy += 24
        # 크로스헤어
        p.setPen(QPen(QColor(232, 180, 74, 120), 1))
        cx0, cy0 = vp.center().x(), vp.center().y()
        p.drawLine(int(cx0 - 14), int(cy0), int(cx0 - 4), int(cy0))
        p.drawLine(int(cx0 + 4), int(cy0), int(cx0 + 14), int(cy0))
        p.drawLine(int(cx0), int(cy0 - 14), int(cx0), int(cy0 - 4))
        p.drawLine(int(cx0), int(cy0 + 4), int(cx0), int(cy0 + 14))
        p.setPen(QPen(QColor(226, 232, 240, 90)))
        p.setFont(font(8, 600, mono=True))
        p.drawText(QRectF(vp.x(), vp.bottom() - 26, vp.width(), 16),
                   Qt.AlignmentFlag.AlignCenter, "LIVE  MAGNIFIER  FEED")
        p.restore()
        hud = QRectF(vp.x() + 8, vp.y() + 8, 58, 18)
        rounded(p, hud, 2, QColor(0, 0, 0, 170), C["gold"], 1.0)
        p.setPen(QPen(C["gold"]))
        p.setFont(font(8, 800, mono=True))
        p.drawText(hud, Qt.AlignmentFlag.AlignCenter, "ZOOM 2.0x")
        y = vp.bottom() + 12

        for label, val, pct in (("ZOOM", "2.0x", 0.10), ("OPACITY", "100%", 1.0)):
            p.setPen(QPen(C["dim"]))
            p.setFont(font(7, 800, mono=True))
            p.drawText(QRectF(x, y, 80, 13), Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QPen(C["gold"]))
            p.setFont(font(9, 800, mono=True))
            p.drawText(QRectF(x, y, w, 13),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)
            track = QRectF(x, y + 17, w, 6)
            rounded(p, track, 1, QColor(255, 255, 255, 14), C["line"], 1.0)
            seg_w = 5.0
            filled = w * pct
            sx = track.x() + 1
            while sx < track.x() + filled - seg_w:
                p.fillRect(QRectF(sx, track.y() + 1.5, seg_w - 2, 3), QBrush(C["gold"]))
                sx += seg_w
            y += 32


# ---------------------------------------------------------------- 렌더 실행
def render(widget: QWidget, filename: str, scale: int = 2) -> str:
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    pm = QPixmap(widget.size() * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(QColor(58, 62, 72))  # 게임 배경 대신 중간 회색으로 반투명 확인
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    widget.render(painter)
    painter.end()
    out = os.path.join(OUT_DIR, filename)
    pm.save(out, "PNG")
    print(f"saved: {out}  ({pm.width()}x{pm.height()})")
    return out


def main():
    app = QApplication(sys.argv)
    jobs = [
        (PartyA(), "A_party_obsidian_pro.png"),
        (MainA(), "A_main_obsidian_pro.png"),
        (PartyB(), "B_party_aurora_glass.png"),
        (MainB(), "B_main_aurora_glass.png"),
        (PartyC(), "C_party_tactical_hud.png"),
        (MainC(), "C_main_tactical_hud.png"),
    ]
    for widget, name in jobs:
        render(widget, name)
    del app


if __name__ == "__main__":
    main()
