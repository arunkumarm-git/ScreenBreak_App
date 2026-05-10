# ui/break_overlay.py
import os
import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl, QSettings
from PyQt6.QtGui import QFont, QMovie, QPainter, QColor, QBrush, QLinearGradient
from controller import TimerController

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

# ──────────────────────────────────────────────
# BREAK OVERLAY
# ──────────────────────────────────────────────
BREAK_MESSAGES = {
    "Short Break": [
        ("short break", "step away from the screen"),
        ("breathe", "in through the nose, out through the mouth"),
        ("rest your eyes", "look at something distant"),
        ("quick reset", "shake out your hands and shoulders"),
    ],
    "Long Break": [
        ("long break", "you earned this one"),
        ("recharge", "step outside if you can"),
        ("move", "walk, stretch, hydrate"),
        ("rest", "no rush — take your time"),
    ],
}


class BreakOverlayWindow(QWidget):
    def __init__(self, controller: TimerController, is_pro: bool = False, muted: bool = False,
                 gif_path: str | None = None, sound_path: str | None = None):
        super().__init__()
        self.controller  = controller
        self._is_pro     = is_pro          
        self.muted       = muted
        self._gif_path   = gif_path
        self._sound_path = sound_path
        self._player     = None
        self._audio_out  = None
        self._pick_message()
        self._init_ui()
        self.controller.tick.connect(self._update_timer)
        self._update_timer(self.controller.remaining_secs)

        if not self.muted and self._sound_path:
            self._play_sound()

    # ── helpers ───────────────────────────────
    def _pick_message(self):
        s = QSettings("ScreenBreak", "ScreenBreak")
        if getattr(self, '_is_pro', False):
            short_raw = s.value("custom_messages_short", "[]")
            long_raw  = s.value("custom_messages_long",  "[]")
            custom_short = json.loads(short_raw) if short_raw else []
            custom_long  = json.loads(long_raw)  if long_raw  else []
        else:
            custom_short = custom_long = []

        pool_short = custom_short if custom_short else BREAK_MESSAGES["Short Break"]
        pool_long  = custom_long  if custom_long  else BREAK_MESSAGES["Long Break"]
        
        msgs = pool_long if self.controller.phase == "Long Break" else pool_short
        
        # Guard against empty custom lists saving an empty state
        if not msgs: 
            msgs = BREAK_MESSAGES["Short Break"]
            
        self._headline, self._subtitle = random.choice(msgs)

    def _play_sound(self):
        if not HAS_AUDIO or not self._sound_path:
            return
        try:
            self._player    = QMediaPlayer(self)
            self._audio_out = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_out)
            self._audio_out.setVolume(0.7)
            self._player.setSource(QUrl.fromLocalFile(os.path.abspath(self._sound_path)))
            self._player.play()
        except Exception:
            pass

    def _stop_sound(self):
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass

    # ── build ─────────────────────────────────
    def _init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)
        layout.setContentsMargins(80, 60, 80, 60)

        # phase tag
        phase_tag = QLabel(self.controller.phase.upper())
        phase_tag.setFont(QFont("Segoe UI", 10))
        phase_tag.setStyleSheet("color: rgba(255,255,255,45); letter-spacing: 3px;")
        phase_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(phase_tag)

        # headline
        hl = QLabel(self._headline)
        hl.setFont(QFont("Segoe UI", 36, QFont.Weight.Light))
        hl.setStyleSheet("color: rgba(255,255,255,220);")
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hl)

        # GIF
        self.gif_label = QLabel()
        if self._gif_path and os.path.exists(self._gif_path):
            self.movie = QMovie(self._gif_path)
            self.movie.setScaledSize(QSize(320, 320))
            self.gif_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.gif_label.setText("◡")
            self.gif_label.setFont(QFont("Segoe UI", 72, QFont.Weight.Light))
            self.gif_label.setStyleSheet("color: rgba(255,255,255,80);")
        self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gif_label)

        # countdown
        self.timer_label = QLabel("00:00")
        self.timer_label.setFont(QFont("Segoe UI", 72, QFont.Weight.Light))
        self.timer_label.setStyleSheet("color: rgba(255,255,255,190); letter-spacing: -2px;")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.timer_label)

        # subtitle
        sub = QLabel(self._subtitle)
        sub.setFont(QFont("Segoe UI", 13, QFont.Weight.Light))
        sub.setStyleSheet("color: rgba(255,255,255,90);")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        # bottom row — mute toggle + skip hint
        bottom = QHBoxLayout()
        bottom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom.setSpacing(28)

        self.btn_mute = QPushButton("🔇 mute" if not self.muted else "🔊 unmute")
        self.btn_mute.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,8);
                color: rgba(255,255,255,80);
                border: 1px solid rgba(255,255,255,14);
                border-radius: 16px;
                padding: 6px 18px;
                font-size: 11px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover { background: rgba(255,255,255,15); color: rgba(255,255,255,140); }
        """)
        self.btn_mute.clicked.connect(self._toggle_mute)
        bottom.addWidget(self.btn_mute)

        hint = QLabel("esc · skip")
        hint.setFont(QFont("Segoe UI", 11))
        hint.setStyleSheet("color: rgba(255,255,255,35);")
        bottom.addWidget(hint)

        layout.addLayout(bottom)

    def _toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self._stop_sound()
            self.btn_mute.setText("🔊 unmute")
        else:
            self.btn_mute.setText("🔇 mute")
            self._play_sound()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        if self.controller.phase == "Long Break":
            grad.setColorAt(0, QColor(6,  8, 22, 240))
            grad.setColorAt(1, QColor(8, 10, 30, 240))
        elif self.controller.phase == "Short Break":
            grad.setColorAt(0, QColor(4,  16, 14, 236))
            grad.setColorAt(1, QColor(6,  22, 18, 236))
        else:
            grad.setColorAt(0, QColor(8,  6, 18, 236))
            grad.setColorAt(1, QColor(12, 8, 24, 236))
        p.fillRect(self.rect(), QBrush(grad))
        p.end()

    def _update_timer(self, secs: int):
        """Update timer display; safely handle widget destruction."""
        try:
            # Check if widget is still valid (not destroyed)
            if not self.isVisible():
                return
            m, s = divmod(secs, 60)
            self.timer_label.setText(f"{m:02d}:{s:02d}")
        except RuntimeError:
            # Widget was destroyed; signal is being processed during cleanup
            pass
        except Exception as e:
            print(f"[ERROR] Timer update failed: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._stop_sound()
            # Disconnect the tick signal before closing to prevent stale updates
            try:
                self.controller.tick.disconnect(self._update_timer)
            except Exception:
                pass
            self.close()
            # Queue skip to allow overlay close to complete first (avoid re-entrant phase change)
            QTimer.singleShot(100, self.controller.skip)

    def closeEvent(self, event):
        """Clean up resources when overlay is closing."""
        self._stop_sound()
        # Disconnect all signals to prevent orphaned connections
        try:
            self.controller.tick.disconnect(self._update_timer)
        except Exception:
            pass
        super().closeEvent(event)