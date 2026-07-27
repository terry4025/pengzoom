    def setup_ui(self):
        self.container = ResizableContainer()
        self.setCentralWidget(self.container)

        # v2.46 리디자인: 노랑/초록/파랑/빨강 원색 버튼 4개가 나란히 있던 구성을
        # 무채색 기반 + 단일 액센트(iOS 블루)로 바꿨다. 색은 상태를 표현할 때만
        # 쓰고, 평상시 크롬은 전부 회색조로 물러나 게임 화면을 방해하지 않는다.
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Malgun Gothic', sans-serif;
                color: #f5f5f7;
            }
            QLabel {
                font-size: 12px;
                background: transparent;
            }
            QLabel#BrandName {
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.2px;
                color: #f5f5f7;
            }
            QLabel#BrandVersion {
                font-size: 9px;
                font-weight: 700;
                color: rgba(245, 245, 247, 0.45);
                background-color: rgba(255, 255, 255, 0.07);
                border-radius: 6px;
                padding: 2px 6px;
            }
            QLabel#FieldLabel {
                font-size: 10px;
                font-weight: 700;
                color: rgba(245, 245, 247, 0.42);
            }
            QLabel#FieldValue {
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 11px;
                font-weight: 700;
                color: #f5f5f7;
            }

            /* 세그먼티드 컨트롤: 트랙 하나 안에 버튼 세 개 */
            QFrame#SegmentTrack {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 10px;
            }
            QPushButton {
                background-color: transparent;
                color: rgba(245, 245, 247, 0.62);
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
                color: #f5f5f7;
            }
            QPushButton.PrimaryActive {
                background-color: #0a84ff;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton.PrimaryActive:hover {
                background-color: #2b95ff;
            }

            /* 타이틀바 아이콘 버튼: 평상시 무채색, 호버에서만 의미색 노출 */
            QPushButton#MinimizeBtn, QPushButton#SettingsBtn,
            QPushButton#HelpBtn, QPushButton#CloseBtn {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 7px;
                padding: 0px;
            }
            QPushButton#MinimizeBtn:hover, QPushButton#SettingsBtn:hover,
            QPushButton#HelpBtn:hover {
                background-color: rgba(255, 255, 255, 0.16);
                border: 1px solid rgba(255, 255, 255, 0.22);
            }
            QPushButton#CloseBtn:hover {
                background-color: rgba(255, 69, 58, 0.85);
                border: 1px solid rgba(255, 69, 58, 0.9);
            }

            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.14);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0a84ff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 13px;
                height: 13px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
                width: 15px;
                margin-left: -1px;
                margin-right: -1px;
                border-radius: 7px;
            }
        """)

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(16, 14, 16, 14)
        self.main_layout.setSpacing(12)

        # 1. 브랜드 타이틀바 + 창 제어 (toggle 대상이라 컨테이너로 묶는다)
        self.top_control_widget = QWidget()
        top_bar_layout = QHBoxLayout(self.top_control_widget)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(7)

        self.brand_mark = QLabel()
        self.brand_mark.setFixedSize(22, 22)
        self.brand_mark.setPixmap(get_svg_pixmap(LUCIDE_PENGUIN_SVG, 22))
        top_bar_layout.addWidget(self.brand_mark)

        brand_name = QLabel("PENGU ZOOM")
        brand_name.setObjectName("BrandName")
        top_bar_layout.addWidget(brand_name)

        brand_version = QLabel("PRO 2.46")
        brand_version.setObjectName("BrandVersion")
        top_bar_layout.addWidget(brand_version)

        top_bar_layout.addStretch()

        # 아이콘은 전부 동일한 중성 회색으로 톤을 맞춘다.
        icon_tint = "#c7c7cc"
        for attr, object_name, svg, handler in (
            ("minimize_btn", "MinimizeBtn", LUCIDE_MINIMIZE_SVG, self.showMinimized),
            ("settings_btn", "SettingsBtn", LUCIDE_SETTINGS_SVG, self.show_settings),
            ("help_btn", "HelpBtn", LUCIDE_HELP_SVG, self.show_help),
            ("close_btn", "CloseBtn", LUCIDE_CLOSE_SVG, self.close),
        ):
            button = QPushButton()
            button.setObjectName(object_name)
            button.setFixedSize(23, 23)
            button.setIcon(get_svg_icon(recolor_svg_stroke(svg, icon_tint)))
            button.setIconSize(QSize(13, 13))
            button.clicked.connect(handler)
            top_bar_layout.addWidget(button)
            setattr(self, attr, button)

        self.main_layout.addWidget(self.top_control_widget)

        # 2. 세그먼티드 컨트롤: 흩어져 있던 토글 3개를 한 트랙으로 묶는다
        self.segment_track = QFrame()
        self.segment_track.setObjectName("SegmentTrack")
        segment_layout = QHBoxLayout(self.segment_track)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(3)

        self.select_btn = QPushButton('영역 지정')
        self.select_btn.clicked.connect(self.start_selection)
        segment_layout.addWidget(self.select_btn)

        self.follow_btn = QPushButton('따라오기 켬')
        self.follow_btn.setProperty("class", "PrimaryActive")
        self.follow_btn.clicked.connect(self.toggle_follow)
        segment_layout.addWidget(self.follow_btn)

        self.click_through_btn = QPushButton('마우스 투과 끔')
        self.click_through_btn.clicked.connect(self.toggle_click_through)
        segment_layout.addWidget(self.click_through_btn)

        self.main_layout.addWidget(self.segment_track)

        # 3. 확대 화면 (항상 표시)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(VIEWPORT_STYLE_FRAMED)
        self.label.setMinimumSize(100, 100)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(self.label)

        # 4. 하단 슬라이더 (toggle 대상)
        self.bottom_control_widget = QWidget()
        bottom_bar_layout = QVBoxLayout(self.bottom_control_widget)
        bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
        bottom_bar_layout.setSpacing(10)

        self.zoom_val_label = QLabel('2.0x')
        self.opacity_val_label = QLabel('100%')
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(20)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(15, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.on_opacity_slider_changed)

        # 라벨과 값을 슬라이더 위 한 줄에 올려 좌우 정렬을 맞춘다.
        for caption, value_label, slider in (
            ('배율', self.zoom_val_label, self.zoom_slider),
            ('투명도', self.opacity_val_label, self.opacity_slider),
        ):
            row = QVBoxLayout()
            row.setSpacing(3)

            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            caption_label = QLabel(caption)
            caption_label.setObjectName("FieldLabel")
            value_label.setObjectName("FieldValue")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            head.addWidget(caption_label)
            head.addStretch()
            head.addWidget(value_label)

            row.addLayout(head)
            row.addWidget(slider)
            bottom_bar_layout.addLayout(row)

        self.main_layout.addWidget(self.bottom_control_widget)

    # Dynamic visibility controller for minimalist HUD screen on click-through (now hides container border as well!)
    def update_ui_visibility(self):
        should_hide = self.click_through and self.hide_ui_on_transparent
        
        if should_hide:
            # 1. Capture the exact dimensions and screen coordinates self.label has BEFORE hiding layout
            global_pos = self.label.mapToGlobal(QPoint(0, 0))
            self.last_normal_size = self.size()
            
            w = max(30, self.label.width())
            h = max(30, self.label.height())
            
            # 2. Toggle control bar widgets visibility
            self.top_control_widget.setVisible(False)
            self.segment_track.setVisible(False)
            self.bottom_control_widget.setVisible(False)
            
            # 3. Toggle outer ResizableContainer frame style and margins
            self.container.setStyleSheet(CONTAINER_STYLE_BARE)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.container.grip.hide()
            self.label.setStyleSheet(VIEWPORT_STYLE_BARE)
            
            # 4. Dynamically shrink window constraints down to target label size
            self.setMinimumSize(30, 30)
            self.label.setMinimumSize(30, 30)
            self.resize(w, h)
            
            # 5. Relocate window so that the borderless zoom label aligns precisely to its original position
            self.move(global_pos)
        else:
            # 1. Capture the current global screen coordinates of the label
            global_pos = self.label.mapToGlobal(QPoint(0, 0))
            
            # 2. Retrieve previously stored size to restore exactly what the user size adjusted
            target_size = getattr(self, 'last_normal_size', None)
            if target_size is None or target_size.width() < 100 or target_size.height() < 100:
                target_size = self.size()
            
            # 3. Restore larger minimum size constraints for settings mode to prevent overlaps
            self.setMinimumSize(250, 300)
            self.label.setMinimumSize(100, 100)
            
            # 4. Toggle control bar widgets visibility
            self.top_control_widget.setVisible(True)
            self.segment_track.setVisible(True)
            self.bottom_control_widget.setVisible(True)
            
            # 5. Restore round corners, outer border frame and resize grip
            self.container.setStyleSheet(CONTAINER_STYLE_FRAMED)
            self.main_layout.setContentsMargins(16, 14, 16, 14)
            self.container.grip.show()
            self.label.setStyleSheet(VIEWPORT_STYLE_FRAMED)
            
            # 6. Restore original window size
            self.resize(target_size.width(), target_size.height())
            
            # 7. Auto position correct: calculate restored margins offset and move window to prevent graphic displacement
            new_label_global = self.label.mapToGlobal(QPoint(0, 0))
            offset_x = new_label_global.x() - self.x()
            offset_y = new_label_global.y() - self.y()
            self.move(global_pos.x() - offset_x, global_pos.y() - offset_y)

