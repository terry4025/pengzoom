    def tick_timers(self):
        current_time = time.time()

        for player, p_data in list(self.widgets.items()):
            latest = float(p_data.get("latest_timestamp", 0.0) or 0.0)
            # 갱신이 끊긴 파티원은 오프라인으로 흐리게 표시한다.
            p_data["is_stale"] = bool(
                latest > 0.0 and (current_time - latest) > HUD_STALE_AFTER_SEC)

            for skill, s_widgets in list(p_data["skill_widgets"].items()):
                is_ready = bool(s_widgets.get("is_ready", False))
                try:
                    cycle_total = max(0.0, float(s_widgets.get("cycle_total", 0) or 0))
                except (TypeError, ValueError):
                    cycle_total = 0.0
                try:
                    cooldown_deadline = max(0.0, float(s_widgets.get("cooldown_deadline", 0) or 0))
                except (TypeError, ValueError):
                    cooldown_deadline = 0.0

                remaining = 0.0
                if not is_ready and cooldown_deadline > 0.0:
                    remaining = max(0.0, cooldown_deadline - current_time)

                if is_ready:
                    if not s_widgets.get("was_ready", True):
                        s_widgets["flash_val"] = 1.0
                    s_widgets["was_ready"] = True
                else:
                    s_widgets["was_ready"] = False

                flash_val = s_widgets.get("flash_val", 0.0)
                if flash_val > 0.0:
                    flash_val = max(0.0, flash_val - HUD_FLASH_DECAY)
                    s_widgets["flash_val"] = flash_val

                gauge = s_widgets["progress"]
                gauge.setFlash(flash_val)

                if is_ready:
                    s_widgets["glow"].show()
                    gauge.hide()
                    s_widgets["status_text_lbl"].setText("Ready")
                else:
                    s_widgets["glow"].hide()
                    gauge.show()

                    if cycle_total > 0.0 and remaining > 0.0:
                        pct = max(0.0, min(100.0, (remaining / cycle_total) * 100.0))
                        gauge.setValue(pct)

                        if remaining >= 1.0:
                            whole = f"{int(math.ceil(remaining))}"
                            gauge.setText(whole)
                            s_widgets["status_text_lbl"].setText(f"{whole}s")
                        else:
                            gauge.setText(f"{remaining:.1f}")
                            s_widgets["status_text_lbl"].setText(f"{remaining:.1f}s")
                    else:
                        # 카운트다운이 0에 닿아도 Ready는 아니다. 게이지 의존 스킬은
                        # Ready 템플릿이 실제로 인식될 때까지 사용 불가로 남는다.
                        gauge.setValue(0.0)
                        gauge.setText("…")
                        s_widgets["status_text_lbl"].setText("Cooldown")

        if self.isVisible():
            self.update()

    # ------------------------------------------------------------- 페인팅
    @staticmethod
    def _fill_round(painter, rect, radius, color):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QBrush(color))

    @staticmethod
    def _stroke_round(painter, rect, radius, color, width=1.0):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.strokePath(path, QPen(color, width))

    @staticmethod
    def _font(size, weight=400, mono=False, spacing=0.0):
        font = QFont("Consolas" if mono else "Segoe UI", max(6, int(round(size))))
        font.setWeight(QFont.Weight(weight))
        if spacing:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        return font

    @staticmethod
    def _elide(painter, text, width):
        return QFontMetrics(painter.font()).elidedText(
            str(text), Qt.TextElideMode.ElideRight, max(10, int(width)))

    @staticmethod
    def _tint(color, alpha):
        tinted = QColor(color)
        tinted.setAlpha(max(0, min(255, int(alpha))))
        return tinted

    def _pulse_scale(self):
        """Ready 표시용 호흡 애니메이션 값(0.0~1.0)."""
        elapsed = time.monotonic() - self._pulse_origin
        speed = max(0.1, float(self.speed or 1.0))
        return 0.5 + 0.5 * math.sin(elapsed * 2 * math.pi * 0.70 * speed)

    def _brand_mark(self, size):
        key = ("__brand__", int(size), "penguin")
        pixmap = _emblem_cache.get(key)
        if pixmap is None:
            pixmap = get_svg_pixmap(LUCIDE_PENGUIN_SVG, int(size))
            _emblem_cache[key] = pixmap
        return pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        scale = max(0.6, float(self.ui_scale or 1.0))
        frame = QRectF(HUD_EDGE, HUD_EDGE,
                       max(1, self.width() - HUD_EDGE * 2),
                       max(1, self.height() - HUD_EDGE * 2))
        radius = 16 * scale

        self._fill_round(painter, frame, radius, self._c_bg)
        border = (self._c_border if (self._hover and not self.panel_click_through)
                  else self._c_border_idle)
        self._stroke_round(painter, frame, radius, border, self._border_w)

        self._paint_header(painter, frame, scale)

        compact = self._is_compact()
        for entry in self._layout_cache:
            p_data = self.widgets.get(entry["player"])
            if not p_data:
                continue
            if compact:
                self._paint_player_compact(painter, entry, p_data, scale)
            else:
                self._paint_player_card(painter, entry, p_data, scale)

        if not self.widgets:
            painter.setPen(QPen(self._c_text_faint))
            painter.setFont(self._font(9 * scale, 500))
            painter.drawText(frame.adjusted(0, HUD_HEADER_H * scale, 0, 0),
                             Qt.AlignmentFlag.AlignCenter, "파티원 접속 대기 중")

    def _paint_header(self, painter, frame, scale):
        pad = HUD_PAD * scale
        x = frame.x() + pad
        width = frame.width() - pad * 2
        height = HUD_HEADER_H * scale
        y = frame.y() + pad * 0.55

        chip = QRectF(x, y + (height - 20 * scale) / 2.0, 20 * scale, 20 * scale)
        self._fill_round(painter, chip, 6 * scale, self._c_chrome)
        mark_size = int(round(14 * scale))
        mark = self._brand_mark(mark_size)
        if mark is not None and not mark.isNull():
            painter.drawPixmap(int(chip.center().x() - mark_size / 2.0),
                               int(chip.center().y() - mark_size / 2.0), mark)

        painter.setPen(QPen(self._c_text_dim))
        painter.setFont(self._font(8 * scale, 700, spacing=1.5 * scale))
        painter.drawText(QRectF(x + 27 * scale, y, max(40.0, width - 120 * scale), height),
                         Qt.AlignmentFlag.AlignVCenter, "PARTY STATUS")

        connected = bool(getattr(self.parent_window, "client_running", False)) if self.parent_window else False
        count = len(self.widgets)
        if connected or count:
            label, accent = f"LIVE {count}", self._c_ready
        else:
            label, accent = "OFFLINE", self._c_text_faint

        badge_w = 54 * scale
        badge = QRectF(frame.right() - pad - badge_w,
                       y + (height - 17 * scale) / 2.0, badge_w, 17 * scale)
        self._fill_round(painter, badge, badge.height() / 2.0, self._tint(accent, 34))
        self._stroke_round(painter, badge, badge.height() / 2.0, self._tint(accent, 80), 1.0)
        painter.setPen(QPen(accent))
        painter.setFont(self._font(7.5 * scale, 700))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_player_card(self, painter, entry, p_data, scale):
        card = entry["rect"]
        skills = entry["skills"]
        row_h = entry["row_h"]
        skill_widgets = p_data["skill_widgets"]
        stale = bool(p_data.get("is_stale"))
        ready_count = sum(1 for s in skills
                          if (skill_widgets.get(s) or {}).get("is_ready"))
        total = len(skills)

        self._fill_round(painter, card, 12 * scale, self._c_card)
        self._stroke_round(painter, card, 12 * scale, self._c_card_border, 1.0)

        # 카드 좌측 상태 바. 준비된 스킬 유무를 주변시로 즉시 알 수 있다.
        bar_color = self._c_ready if (ready_count and not stale) else self._c_idle_bar
        bar = QRectF(card.x() + 1.5 * scale, card.y() + 9 * scale,
                     3 * scale, max(4.0, card.height() - 18 * scale))
        self._fill_round(painter, bar, 1.5 * scale, bar_color)

        content_x = card.x() + 13 * scale
        name_x = content_x
        emblem = p_data.get("emblem")
        if emblem is not None and not emblem.isNull():
            painter.setOpacity(0.4 if stale else 1.0)
            painter.drawPixmap(int(content_x), int(card.y() + 10 * scale), emblem)
            painter.setOpacity(1.0)
            name_x = content_x + emblem.width() + 8 * scale

        summary_w = 78 * scale
        name_rect = QRectF(name_x, card.y() + 8 * scale,
                           max(30.0, card.right() - 13 * scale - summary_w - name_x),
                           HUD_NAME_ROW_H * scale)
        painter.setPen(QPen(self._c_text_faint if stale else self._c_text))
        painter.setFont(self._font(10.5 * scale, 700))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter,
                         self._elide(painter, entry["player"], name_rect.width()))

        painter.setFont(self._font(7.5 * scale, 700))
        if stale:
            painter.setPen(QPen(self._c_text_faint))
            summary = "오프라인"
        else:
            painter.setPen(QPen(self._c_ready if ready_count else self._c_text_faint))
            summary = f"{ready_count}/{total} READY" if total else "대기"
        painter.drawText(QRectF(card.x(), card.y() + 8 * scale,
                                card.width() - 13 * scale, HUD_NAME_ROW_H * scale),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         summary)

        row_y = card.y() + (8 + HUD_NAME_ROW_H) * scale
        row_w = max(40.0, card.right() - 13 * scale - content_x)
        for skill in skills:
            s_widgets = skill_widgets.get(skill)
            if s_widgets is None:
                continue
            self._paint_skill_row(painter, skill, s_widgets,
                                  QRectF(content_x, row_y, row_w, row_h), scale, stale)
            row_y += row_h

    def _paint_skill_row(self, painter, skill, s_widgets, rect, scale, stale):
        show_names = self._shows_names()
        is_ready = bool(s_widgets.get("is_ready"))
        flash = max(0.0, min(1.0, float(s_widgets.get("flash_val", 0.0) or 0.0)))
        gauge = s_widgets["progress"]
        accent = self._c_text_faint if stale else (self._c_ready if is_ready else self._c_cool)

        # Ready 행은 배경 틴트로 한 번 더 구분한다.
        if is_ready and not stale:
            self._fill_round(painter,
                             rect.adjusted(-5 * scale, 0, 5 * scale, -2 * scale),
                             7 * scale, self._tint(self._c_ready, 16 + 46 * flash))

        track_h = max(2.0, 3 * scale)
        if show_names:
            text_h = 15 * scale
            track_y = rect.y() + 18 * scale
        else:
            text_h = 12 * scale
            track_y = rect.y() + 13 * scale
        text_rect = QRectF(rect.x(), rect.y(), rect.width(), text_h)
        track = QRectF(rect.x(), track_y, rect.width(), track_h)

        if is_ready:
            value_text = "READY"
            value_font = self._font(7.5 * scale, 700)
        else:
            raw = s_widgets["status_text_lbl"].text()
            if raw.endswith("s"):
                value_text = raw
                value_font = self._font(9 * scale, 700, mono=True)
            else:
                value_text = "COOLDOWN"
                value_font = self._font(7 * scale, 700)

        value_w = 54 * scale
        if show_names:
            painter.setPen(QPen(self._c_text_faint if stale
                                else (self._c_text if is_ready else self._c_text_dim)))
            painter.setFont(self._font(9 * scale, 600))
            name_w = max(20.0, text_rect.width() - value_w)
            painter.drawText(QRectF(text_rect.x(), text_rect.y(), name_w, text_rect.height()),
                             Qt.AlignmentFlag.AlignVCenter,
                             self._elide(painter, skill, name_w))

        painter.setFont(value_font)
        painter.setPen(QPen(accent))
        painter.drawText(text_rect,
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         value_text)

        self._fill_round(painter, track, track_h / 2.0, self._c_track)

        has_cycle = float(s_widgets.get("cycle_total", 0.0) or 0.0) > 0.0
        ratio = 1.0 if is_ready else (
            max(0.0, min(1.0, gauge.value / 100.0)) if has_cycle else 0.0)

        if is_ready and not stale:
            # 호흡 헤일로. 준비 완료를 화면을 보지 않고도 감지할 수 있게 한다.
            pulse = self._pulse_scale() * max(0.0, min(2.0, float(self.intensity or 1.0)))
            grow = 1.6 * scale * pulse
            self._fill_round(painter, track.adjusted(0, -grow, 0, grow),
                             (track_h + 2 * grow) / 2.0,
                             self._tint(self._c_ready, 46 + 70 * pulse + 90 * flash))
        if ratio > 0.0:
            self._fill_round(painter,
                             QRectF(track.x(), track.y(),
                                    max(track_h, track.width() * ratio), track_h),
                             track_h / 2.0, accent)

    def _paint_player_compact(self, painter, entry, p_data, scale):
        card = entry["rect"]
        skills = entry["skills"]
        skill_widgets = p_data["skill_widgets"]
        stale = bool(p_data.get("is_stale"))
        ready_count = sum(1 for s in skills
                          if (skill_widgets.get(s) or {}).get("is_ready"))

        self._fill_round(painter, card, 8 * scale, self._c_card)
        self._stroke_round(painter, card, 8 * scale, self._c_card_border, 1.0)

        if ready_count and not stale:
            marker = QPainterPath()
            mid = card.center().y()
            marker.moveTo(card.x() + 5 * scale, mid - 5 * scale)
            marker.lineTo(card.x() + 11 * scale, mid)
            marker.lineTo(card.x() + 5 * scale, mid + 5 * scale)
            marker.closeSubpath()
            painter.fillPath(marker, QBrush(self._c_ready))

        info_x = card.x() + 16 * scale
        emblem = p_data.get("emblem")
        if emblem is not None and not emblem.isNull():
            painter.setOpacity(0.4 if stale else 1.0)
            painter.drawPixmap(int(info_x),
                               int(card.center().y() - emblem.height() / 2.0), emblem)
            painter.setOpacity(1.0)
            info_x += emblem.width() + 8 * scale

        name_w = 84 * scale
        painter.setPen(QPen(self._c_text_faint if stale else self._c_text))
        painter.setFont(self._font(9.5 * scale, 700))
        painter.drawText(QRectF(info_x, card.y() + 7 * scale, name_w, 15 * scale),
                         Qt.AlignmentFlag.AlignVCenter,
                         self._elide(painter, entry["player"], name_w))
        painter.setPen(QPen(self._c_text_faint))
        painter.setFont(self._font(7 * scale, 500))
        painter.drawText(QRectF(info_x, card.bottom() - 21 * scale, name_w, 14 * scale),
                         Qt.AlignmentFlag.AlignVCenter,
                         self._elide(painter,
                                     "오프라인" if stale else p_data.get("class_name", ""),
                                     name_w))

        cell_x = info_x + name_w + 6 * scale
        available = max(30.0, card.right() - 10 * scale - cell_x)
        cell_w = available / max(1, len(skills))
        for skill in skills:
            s_widgets = skill_widgets.get(skill)
            if s_widgets is None:
                continue
            cell = QRectF(cell_x, card.y() + 5 * scale,
                          max(26.0, cell_w - 5 * scale), card.height() - 10 * scale)
            self._paint_skill_cell(painter, skill, s_widgets, cell, scale, stale)
            cell_x += cell_w

    def _paint_skill_cell(self, painter, skill, s_widgets, cell, scale, stale):
        show_names = self._shows_names()
        is_ready = bool(s_widgets.get("is_ready"))
        flash = max(0.0, min(1.0, float(s_widgets.get("flash_val", 0.0) or 0.0)))
        gauge = s_widgets["progress"]
        accent = self._c_text_faint if stale else (self._c_ready if is_ready else self._c_cool)

        if is_ready and not stale:
            self._fill_round(painter, cell, 4 * scale,
                             self._tint(self._c_ready, 26 + 50 * flash))
            self._stroke_round(painter, cell, 4 * scale,
                               self._tint(self._c_ready, 96), 1.0)
        else:
            self._fill_round(painter, cell, 4 * scale, self._c_chrome)
            self._stroke_round(painter, cell, 4 * scale, self._c_card_border, 1.0)

        if show_names:
            painter.setPen(QPen(self._c_text_faint))
            painter.setFont(self._font(7 * scale, 600))
            painter.drawText(QRectF(cell.x() + 5 * scale, cell.y() + 3 * scale,
                                    cell.width() - 10 * scale, 12 * scale),
                             Qt.AlignmentFlag.AlignVCenter,
                             self._elide(painter, skill, cell.width() - 10 * scale))
            value_y = cell.y() + 14 * scale
        else:
            value_y = cell.y() + 8 * scale

        painter.setPen(QPen(accent))
        if is_ready:
            painter.setFont(self._font(11 * scale, 800))
            value_text = "RDY"
        else:
            raw = s_widgets["status_text_lbl"].text()
            if raw.endswith("s"):
                painter.setFont(self._font(13 * scale, 800, mono=True))
                value_text = raw[:-1]
            else:
                painter.setFont(self._font(8 * scale, 700))
                value_text = "CD"
        painter.drawText(QRectF(cell.x(), value_y, cell.width(), 20 * scale),
                         Qt.AlignmentFlag.AlignCenter, value_text)

        track_h = max(2.0, 2 * scale)
        track = QRectF(cell.x() + 4 * scale, cell.bottom() - 6 * scale,
                       max(8.0, cell.width() - 8 * scale), track_h)
        self._fill_round(painter, track, track_h / 2.0, self._c_track)

        has_cycle = float(s_widgets.get("cycle_total", 0.0) or 0.0) > 0.0
        ratio = 1.0 if is_ready else (
            max(0.0, min(1.0, gauge.value / 100.0)) if has_cycle else 0.0)
        if ratio > 0.0:
            self._fill_round(painter,
                             QRectF(track.x(), track.y(),
                                    max(track_h, track.width() * ratio), track_h),
                             track_h / 2.0, accent)

    # -------------------------------------------------------- 마우스/호버
    def enterEvent(self, event):
        if not self.panel_click_through:
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._hover:
            self._hover = False
            self.update()
        super().leaveEvent(event)

    def _near_right_edge(self, pos):
        return pos.x() >= self.width() - self.resize_border

    def mousePressEvent(self, event):
        if self.panel_click_through:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._near_right_edge(event.position().toPoint()):
                self.resize_dir = "Right"
            else:
                self.resize_dir = None
                self.drag_position = (event.globalPosition().toPoint()
                                      - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if self.panel_click_through:
            return
        # 높이는 카드 수에 맞춰 자동 조절되므로 사용자는 폭만 조절한다.
        if event.buttons() == Qt.MouseButton.NoButton:
            self.setCursor(Qt.CursorShape.SizeHorCursor
                           if self._near_right_edge(event.position().toPoint())
                           else Qt.CursorShape.ArrowCursor)
        elif event.buttons() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self.resize_dir == "Right":
                self.resize(max(self._min_content_width, global_pos.x() - self.x()),
                            self.height())
            elif self.drag_position is not None:
                self.move(global_pos - self.drag_position)

    def mouseReleaseEvent(self, event):
        self.resize_dir = None
        self.drag_position = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.parent_window:
            self.parent_window.save_settings()

