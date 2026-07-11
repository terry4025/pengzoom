import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
import time

class PartyOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)
        
        # Title Label
        self.title_label = QLabel("⚔️ 파티 스킬 상태")
        self.title_label.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 14px; background-color: rgba(0, 0, 0, 180); padding: 5px; border-radius: 5px;")
        self.layout.addWidget(self.title_label)
        
        self.status_labels = {} # {player_name: QLabel}
        
        # Initial position (Top-Right)
        # Will be adjusted by main window
        self.move(100, 100)
        
    def update_status(self, party_states):
        current_time = time.time()
        active_players = set()
        
        for player, skills in party_states.items():
            active_players.add(player)
            if player not in self.status_labels:
                lbl = QLabel()
                lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px; background-color: rgba(0, 0, 0, 150); padding: 5px; border-radius: 5px;")
                self.layout.addWidget(lbl)
                self.status_labels[player] = lbl
                
            skill_text = ""
            is_offline = False
            for skill_name, state in skills.items():
                timestamp = state.get("timestamp", 0)
                # If no update for 5 seconds, consider offline or disconnected
                if current_time - timestamp > 5.0:
                    is_offline = True
                    
                status_icon = "🟢" if state.get("is_ready", False) else "🔴"
                if is_offline:
                    status_icon = "⚪ (오프라인)"
                    
                skill_text += f"{skill_name}: {status_icon} "
                
            self.status_labels[player].setText(f"[{player}] {skill_text}")
            
        # Clean up stale labels
        for player in list(self.status_labels.keys()):
            if player not in active_players:
                lbl = self.status_labels.pop(player)
                self.layout.removeWidget(lbl)
                lbl.deleteLater()
                
        self.adjustSize()
