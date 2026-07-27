    def update_states(self, party_states):
        received_at = time.time()
        if not isinstance(party_states, dict):
            party_states = {}
        current_players = set(party_states.keys())

        # 사라진 파티원 제거. 위젯 트리가 없으므로 deleteLater가 필요 없다.
        for player in list(self.widgets.keys()):
            if player not in current_players:
                del self.widgets[player]

        for player, skills in party_states.items():
            if player not in self.widgets:
                self.widgets[player] = {
                    "skill_widgets": {},
                    "emblem": None,
                    "class_name": "",
                    "latest_timestamp": 0.0,
                    "is_stale": False,
                }
            p_data = self.widgets[player]

            # 서버가 보낸 클래스 또는 로컬 매핑으로 엠블럼을 결정한다.
            if isinstance(skills, dict):
                class_name = skills.get("_class") or self.player_classes.get(player, "홀리나이트")
            else:
                class_name = "홀리나이트"
            self.player_classes[player] = class_name
            if p_data.get("class_name") != class_name or p_data.get("emblem") is None:
                p_data["class_name"] = class_name
                p_data["emblem"] = self._resolve_emblem(class_name, player)

            skill_map = skills if isinstance(skills, dict) else {}
            for dropped in list(p_data["skill_widgets"].keys()):
                if dropped not in skill_map:
                    del p_data["skill_widgets"][dropped]

            latest_timestamp = 0.0
            for skill, s_info in skill_map.items():
                if not isinstance(skill, str) or skill.startswith('_') or not isinstance(s_info, dict):
                    continue
                is_ready = bool(s_info.get("is_ready", False))
                try:
                    cooldown_duration = max(0.0, float(s_info.get("cooldown_duration", 0) or 0))
                except (TypeError, ValueError):
                    cooldown_duration = 0.0
                try:
                    timestamp = float(s_info.get("timestamp", 0.0) or 0.0)
                except (TypeError, ValueError):
                    timestamp = 0.0
                latest_timestamp = max(latest_timestamp, timestamp)
                reported_deadline = (
                    timestamp + cooldown_duration
                    if not is_ready and cooldown_duration > 0.0
                    else 0.0
                )

                if skill not in p_data["skill_widgets"]:
                    glow = ReadyPulse(self._c_ready.name())
                    glow.speed = self.speed
                    glow.intensity = self.intensity
                    p_data["skill_widgets"][skill] = {
                        "glow": glow,
                        "progress": SkillGauge(self._c_cool.name()),
                        "skill_name_lbl": LabelState(skill),
                        "status_text_lbl": LabelState("Ready"),
                        "is_ready": is_ready,
                        "cooldown_duration": cooldown_duration,
                        "timestamp": timestamp,
                        "cycle_total": cooldown_duration if not is_ready else 0.0,
                        "cooldown_deadline": reported_deadline,
                        "flash_val": 0.0,
                        "was_ready": is_ready
                    }
                else:
                    s_widgets = p_data["skill_widgets"][skill]
                    previous_ready = bool(s_widgets.get("is_ready", False))
                    previous_total = max(0.0, float(s_widgets.get("cycle_total", 0.0) or 0.0))
                    previous_deadline = max(0.0, float(s_widgets.get("cooldown_deadline", 0.0) or 0.0))
                    expected_remaining = max(0.0, previous_deadline - received_at)
                    restarted_while_cooldown = (
                        reported_deadline > 0.0
                        and (
                            previous_deadline <= received_at
                            or cooldown_duration > expected_remaining + 1.25
                        )
                    )

                    if is_ready:
                        cycle_total = 0.0
                        cooldown_deadline = 0.0
                    elif previous_ready:
                        # A Ready -> Cooldown transition starts a new visual cycle.
                        cycle_total = cooldown_duration
                        cooldown_deadline = reported_deadline
                    elif restarted_while_cooldown:
                        # Gauge skills or cooldown resets can start another cycle
                        # without a debounced Ready frame between the two uses.
                        # A meaningful increase beyond the expected remaining
                        # time re-latches the total and deadline.
                        cycle_total = cooldown_duration
                        cooldown_deadline = reported_deadline
                    else:
                        # Periodic sync reports the *remaining* seconds.  Keep the
                        # first total as the ring denominator and only allow the
                        # estimated deadline to move earlier (OCR cooldown cut).
                        cycle_total = max(previous_total, cooldown_duration)
                        if previous_deadline > 0.0 and reported_deadline > 0.0:
                            cooldown_deadline = min(previous_deadline, reported_deadline)
                        elif previous_deadline > 0.0:
                            cooldown_deadline = previous_deadline
                        else:
                            cooldown_deadline = reported_deadline

                    s_widgets["is_ready"] = is_ready
                    s_widgets["cooldown_duration"] = cooldown_duration
                    s_widgets["timestamp"] = timestamp
                    s_widgets["cycle_total"] = cycle_total
                    s_widgets["cooldown_deadline"] = cooldown_deadline

            p_data["latest_timestamp"] = latest_timestamp

        self._relayout()
        self._autofit_size()
        if self.isVisible():
            self.update()
