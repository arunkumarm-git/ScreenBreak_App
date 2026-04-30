import sys, ctypes, platform

if platform.system() == "Windows":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ScreenBreak")

import os
import random
import math
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QSystemTrayIcon, QMenu, QSizePolicy,
    QGraphicsDropShadowEffect, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRectF, QSize, QPoint, QUrl, QSettings
from PyQt6.QtGui import (
    QFont, QMovie, QPainter, QColor, QPen, QBrush, QLinearGradient,
    QPainterPath, QIcon, QAction, QPixmap, QConicalGradient, QRadialGradient
)
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth.transport.requests
import google.oauth2.credentials

from PIL import Image

import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Assets directory — always relative to this script file
def _get_base_path():
    """Works both in dev and when bundled by PyInstaller."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS   # PyInstaller's temp extraction folder
    return os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(_get_base_path(), "assets")


# ──────────────────────────────────────────────
# LOCAL ASSET PICKER
# Picks a random GIF and sound from the local
# assets/ folder.  No network calls at all.
# ──────────────────────────────────────────────
class LocalAssetPicker:
    """
    Picks a random GIF from assets/gifs/<subfolder>/ and a random sound
    from assets/sounds/.  Both calls are instant (local disk), so no
    background thread is required.
    """

    _GIF_SUBFOLDERS = ["break time", "cat", "hydrate"]

    def __init__(self):
        self._gif_path:   str | None = None
        self._sound_path: str | None = None

    # ── public ──────────────────────────────
    def start(self):
        """Pre-pick assets for the next break."""
        self._gif_path   = self._pick_random_gif()
        self._sound_path = self._pick_random_sound()
        print(f"[assets] GIF  : {self._gif_path or 'none'}")
        print(f"[assets] Sound: {self._sound_path or 'none'}")

    def pop(self) -> tuple[str | None, str | None]:
        """Return (gif_path, sound_path) and clear the cache."""
        gif, sound = self._gif_path, self._sound_path
        self._gif_path = self._sound_path = None
        return gif, sound

    # ── internal ────────────────────────────
    def _pick_random_gif(self) -> str | None:
        subfolders = self._GIF_SUBFOLDERS[:]
        random.shuffle(subfolders)
        for subfolder in subfolders:
            folder = os.path.join(ASSETS_DIR, "gifs", subfolder)
            if not os.path.isdir(folder):
                continue
            gifs = [f for f in os.listdir(folder) if f.lower().endswith(".gif")]
            if gifs:
                return os.path.join(folder, random.choice(gifs))
        print("[assets] No GIFs found — check assets/gifs/ subfolders")
        return None

    def _pick_random_sound(self) -> str | None:
        sounds_dir = os.path.join(ASSETS_DIR, "sounds")
        if not os.path.isdir(sounds_dir):
            return None
        sounds = [
            f for f in os.listdir(sounds_dir)
            if f.lower().endswith((".mp3", ".wav", ".ogg"))
        ]
        if sounds:
            return os.path.join(sounds_dir, random.choice(sounds))
        return None


# ──────────────────────────────────────────────
# CONTROLLER LOGIC
# ──────────────────────────────────────────────
class TimerController(QObject):
    tick            = pyqtSignal(int)
    phase_changed   = pyqtSignal(str)
    session_done    = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.work_secs          = 25 * 60
        self.short_break_secs   = 5  * 60
        self.long_break_secs    = 15 * 60
        self.sessions_per_cycle = 4

        # break flow: "auto" | "always_short" | "always_long"
        self.break_flow = "auto"

        self.phase          = "Work"
        self.remaining_secs = self.work_secs
        self.total_secs     = self.work_secs
        self.is_running     = False
        self.work_sessions  = 0

        self._qtimer = QTimer()
        self._qtimer.timeout.connect(self._on_tick)

        # Guard against re-entrant / rapid skip calls
        self._skip_in_progress = False
        self._skip_cooldown = QTimer()
        self._skip_cooldown.setSingleShot(True)
        self._skip_cooldown.setInterval(400)   # ms — ignore repeated clicks within 400 ms
        self._skip_cooldown.timeout.connect(self._clear_skip_cooldown)

    def _clear_skip_cooldown(self):
        self._skip_in_progress = False

    # ── public API ──────────────────────────
    def start(self):
        if not self.is_running:
            self.is_running = True
            self._qtimer.start(1000)

    def pause(self):
        self.is_running = False
        self._qtimer.stop()

    def reset(self):
        self.pause()
        self._skip_in_progress = False
        self._skip_cooldown.stop()
        self.work_sessions = 0
        self.set_phase("Work")

    def skip(self):
        # Debounce: ignore if a skip is already being processed
        if self._skip_in_progress:
            return
        self._skip_in_progress = True
        self._skip_cooldown.start()

        # Stop the tick timer during transition to avoid re-entrant ticks
        was_running = self.is_running
        self._qtimer.stop()
        self.is_running = False

        if self.phase == "Work":
            self.work_sessions += 1
            self.session_done.emit(self.work_sessions)
            self.set_phase(self._decide_break())
        else:
            self.set_phase("Work")

        # Resume ticking if timer was active
        if was_running:
            self.is_running = True
            self._qtimer.start(1000)

    def _decide_break(self) -> str:
        if self.break_flow == "always_short":
            return "Short Break"
        elif self.break_flow == "always_long":
            return "Long Break"
        else:  # auto
            if self.work_sessions % self.sessions_per_cycle == 0:
                return "Long Break"
            return "Short Break"

    def set_phase(self, phase: str):
        self.phase = phase
        durations = {
            "Work":        self.work_secs,
            "Short Break": self.short_break_secs,
            "Long Break":  self.long_break_secs,
        }
        secs = durations.get(phase, self.work_secs)
        self.remaining_secs = self.total_secs = secs
        self.phase_changed.emit(self.phase)
        self.tick.emit(self.remaining_secs)

    def update_settings(self, work_s: int, short_s: int, long_s: int, flow: str):
        changed = (self.work_secs != work_s or
                   self.short_break_secs != short_s or
                   self.long_break_secs != long_s or
                   self.break_flow != flow)
        if not changed:
            return
        self.work_secs        = work_s
        self.short_break_secs = short_s
        self.long_break_secs  = long_s
        self.break_flow       = flow
        self.reset()

    def progress(self) -> float:
        if self.total_secs == 0:
            return 0.0
        return 1.0 - (self.remaining_secs / self.total_secs)

    def _on_tick(self):
        self.remaining_secs -= 1
        self.tick.emit(self.remaining_secs)
        if self.remaining_secs <= 0:
            self.skip()


# ──────────────────────────────────────────────
# PHASE COLOURS
# ──────────────────────────────────────────────
PHASE_COLORS = {
    "Work":        ("#c084fc", "#f472b6"),
    "Short Break": ("#34d399", "#10b981"),
    "Long Break":  ("#60a5fa", "#38bdf8"),
}


# ──────────────────────────────────────────────
# CIRCULAR TIMER WIDGET
# ──────────────────────────────────────────────
class CircularTimer(QWidget):
    def __init__(self, controller: TimerController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._phase     = "Work"
        self._progress  = 0.0
        self._time_text = "25:00"

        controller.tick.connect(self._on_tick)
        controller.phase_changed.connect(self._on_phase)

    def _on_tick(self, secs: int):
        m, s = divmod(secs, 60)
        self._time_text = f"{m:02d}:{s:02d}"
        self._progress  = self.controller.progress()
        self.update()

    def _on_phase(self, phase: str):
        self._phase    = phase
        self._progress = 0.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        size   = min(w, h)
        margin = size * 0.12
        rect   = QRectF(
            margin + (w - size) / 2,
            margin + (h - size) / 2,
            size - 2 * margin,
            size - 2 * margin
        )
        cx, cy = w / 2, h / 2

        # track
        track_pen = QPen(QColor(255, 255, 255, 14), size * 0.038)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawEllipse(rect)

        # progress arc
        c1, c2 = PHASE_COLORS.get(self._phase, ("#c084fc", "#f472b6"))
        col1, col2 = QColor(c1), QColor(c2)

        if self._progress > 0.002:
            span_deg = self._progress * 360
            span_val = -int(span_deg * 16)

            # soft glow
            glow_pen = QPen(
                QColor(col1.red(), col1.green(), col1.blue(), 28),
                size * 0.075
            )
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(glow_pen)
            p.drawArc(rect, 90 * 16, span_val)

            # arc
            conic = QConicalGradient(rect.center(), 90)
            conic.setColorAt(0.0,            col1)
            conic.setColorAt(self._progress, col2)
            conic.setColorAt(1.0,            col1)

            arc_pen = QPen(QBrush(conic), size * 0.038)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)
            p.drawArc(rect, 90 * 16, span_val)

            # tip dot
            angle_rad = math.radians(90 - span_deg)
            r_mid     = rect.width() / 2
            dot_x     = cx + r_mid * math.cos(angle_rad)
            dot_y     = cy - r_mid * math.sin(angle_rad)
            dot_r     = size * 0.030
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(col2))
            p.drawEllipse(QRectF(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2))

        # time text
        font = QFont("Segoe UI", int(size * 0.165), QFont.Weight.Light)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 230))
        p.drawText(QRectF(0, cy - size * 0.13, w, size * 0.22),
                   Qt.AlignmentFlag.AlignCenter, self._time_text)

        # phase label
        lbl_font = QFont("Segoe UI", int(size * 0.058))
        p.setFont(lbl_font)
        p.setPen(QColor(255, 255, 255, 160))
        p.drawText(QRectF(0, cy + size * 0.10, w, size * 0.10),
                   Qt.AlignmentFlag.AlignCenter, self._phase.upper())

        p.end()


# ──────────────────────────────────────────────
# MINIMAL CARD
# ──────────────────────────────────────────────
class Card(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        p.fillPath(path, QBrush(QColor(255, 255, 255, 7)))
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.drawPath(path)
        p.end()


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
    def __init__(self, controller: TimerController, muted: bool = False,
                 gif_path: str | None = None, sound_path: str | None = None):
        super().__init__()
        self.controller  = controller
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
        msgs = BREAK_MESSAGES.get(self.controller.phase, BREAK_MESSAGES["Short Break"])
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


# ──────────────────────────────────────────────
# DURATION SPIN  (min + sec)
# ──────────────────────────────────────────────
class DurationSpin(QWidget):
    """A compact paired spinner: MM min  SS sec  → returns total seconds."""

    def __init__(self, default_secs: int, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        spin_style = """
            QSpinBox {
                background: rgba(255,255,255,6);
                border: 1px solid rgba(255,255,255,14);
                border-radius: 7px;
                padding: 3px 6px;
                color: rgba(255,255,255,190);
                font-size: 11px;
                min-width: 44px; max-width: 52px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: rgba(255,255,255,10);
                border: none; width: 12px;
            }
        """
        unit_style = "color: rgba(255,255,255,120); font-size: 10px; font-family: 'Segoe UI';"

        default_m = default_secs // 60
        default_s = default_secs  % 60

        self._min_spin = QSpinBox()
        self._min_spin.setRange(0, 180)
        self._min_spin.setValue(default_m)
        self._min_spin.setStyleSheet(spin_style)

        lbl_m = QLabel("min")
        lbl_m.setStyleSheet(unit_style)

        self._sec_spin = QSpinBox()
        self._sec_spin.setRange(0, 59)
        self._sec_spin.setValue(default_s)
        self._sec_spin.setStyleSheet(spin_style)

        lbl_s = QLabel("sec")
        lbl_s.setStyleSheet(unit_style)

        layout.addWidget(self._min_spin)
        layout.addWidget(lbl_m)
        layout.addWidget(self._sec_spin)
        layout.addWidget(lbl_s)

    def value_secs(self) -> int:
        return self._min_spin.value() * 60 + self._sec_spin.value()


# ──────────────────────────────────────────────
# MAIN WINDOW
# ──────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self, controller: TimerController):
        super().__init__()
        self.controller  = controller
        self.overlay     = None
        self._overlay_closing = False  # Guard against re-entrant overlay close operations
        self._drag_pos   = None
        self._muted      = False
        self._user_info  = {}
        self._picker     = LocalAssetPicker()

        self.setWindowTitle("ScreenBreak")
        self.setFixedSize(400, 660)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()
        self._setup_tray()
        self._connect_signals()
        self._load_settings()
        self.controller.reset()

        # Pre-pick assets for the first break
        self._picker.start()

    # ── UI construction ───────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── title bar ─────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(4, 0, 2, 0)

        logo = QLabel("screenbreak")
        logo.setFont(QFont("Segoe UI", 11))
        logo.setStyleSheet("color: rgba(255,255,255,160); letter-spacing: 1.5px;")
        tb.addWidget(logo)
        tb.addStretch()

        self.btn_login = QPushButton("login")
        self.btn_login.setFixedHeight(24)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,8);
                color: rgba(255,255,255,180);
                border: 1px solid rgba(255,255,255,14);
                border-radius: 12px;
                padding: 0px 12px;
                font-size: 10px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover { background: rgba(255,255,255,15); color: #ffffff; }
        """)
        self.btn_login.clicked.connect(self._do_google_login)
        tb.addWidget(self.btn_login)

        # mute button in title bar
        self.btn_global_mute = QPushButton("🔊")
        self.btn_global_mute.setFixedSize(24, 24)
        self.btn_global_mute.setToolTip("Mute break sounds")
        self.btn_global_mute.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255,255,255,55);
                border: none;
                font-size: 12px;
                border-radius: 12px;
            }
            QPushButton:hover { background: rgba(255,255,255,10); color: rgba(255,255,255,120); }
        """)
        self.btn_global_mute.clicked.connect(self._toggle_global_mute)
        tb.addWidget(self.btn_global_mute)

        for symbol, handler in [("−", self._minimize_to_tray),
                                  ("×", self._quit_app)]:
            btn = QPushButton(symbol)
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,16);
                    color: rgba(255,255,255,160);
                    border: 1px solid rgba(255,255,255,28);
                    border-radius: 12px;
                    font-size: 14px;
                }
                QPushButton:hover { background: rgba(255,255,255,32); color: rgba(255,255,255,240); }
                QPushButton:pressed { background: rgba(255,255,255,22); }
            """)
            btn.clicked.connect(handler)
            tb.addWidget(btn)

        root.addWidget(title_bar)

        # ── session progress indicator ─────────
        # Shows "break 1 of 4 ● ○ ○ ○" so users understand what the dots mean
        session_row = QHBoxLayout()
        session_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_row.setSpacing(8)

        self.session_label = QLabel("session 1 of 4")
        self.session_label.setFont(QFont("Segoe UI", 8))
        self.session_label.setStyleSheet(
            "color: rgba(255,255,255,55); letter-spacing: 0.5px;")
        session_row.addWidget(self.session_label)

        self.session_dots = QLabel("○  ○  ○  ○")
        self.session_dots.setFont(QFont("Segoe UI", 9))
        self.session_dots.setStyleSheet(
            "color: rgba(255,255,255,80); letter-spacing: 6px;")
        session_row.addWidget(self.session_dots)

        root.addLayout(session_row)

        # ── circular timer ────────────────────
        self.circ = CircularTimer(self.controller)
        self.circ.setFixedSize(210, 210)
        timer_row = QHBoxLayout()
        timer_row.addWidget(self.circ, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addLayout(timer_row)

        # ── control buttons ───────────────────
        ctrl_card = Card()
        ctrl_lay  = QHBoxLayout(ctrl_card)
        ctrl_lay.setContentsMargins(14, 10, 14, 10)
        ctrl_lay.setSpacing(8)

        ghost = """
            QPushButton {
                background: rgba(255,255,255,6);
                color: rgba(255,255,255,200);
                border: 1px solid rgba(255,255,255,18);
                border-radius: 14px;
                padding: 6px 16px;
                font-size: 11px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background: rgba(255,255,255,14);
                color: rgba(255,255,255,240);
            }
        """
        primary = """
            QPushButton {
                background: rgba(192, 132, 252, 0.20);
                color: rgba(216,180,254,220);
                border: 1px solid rgba(192,132,252,0.30);
                border-radius: 14px;
                padding: 6px 22px;
                font-size: 11px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background: rgba(192,132,252,0.32);
                color: rgba(233,213,255,240);
            }
        """

        self.btn_start = QPushButton("▶  start")
        self.btn_start.setStyleSheet(primary)
        self.btn_pause = QPushButton("⏸  pause")
        self.btn_pause.setStyleSheet(ghost)
        self.btn_pause.hide()
        self.btn_skip  = QPushButton("skip")
        self.btn_skip.setStyleSheet(ghost)
        self.btn_reset = QPushButton("reset")
        self.btn_reset.setStyleSheet(ghost)

        for b in (self.btn_start, self.btn_pause, self.btn_skip, self.btn_reset):
            ctrl_lay.addWidget(b)

        root.addWidget(ctrl_card)

        # ── settings card ─────────────────────
        sett_card = Card()
        sett_lay  = QVBoxLayout(sett_card)
        sett_lay.setContentsMargins(20, 14, 20, 14)
        sett_lay.setSpacing(10)

        sett_title = QLabel("SETTINGS")
        sett_title.setStyleSheet(
            "color: rgba(255,255,255,110); font-size: 8px; "
            "letter-spacing: 3px; font-weight: bold;")
        sett_lay.addWidget(sett_title)

        lbl_style = (
            "color: rgba(255,255,255,200); font-size: 11px; font-family: 'Segoe UI';")

        rows = [
            ("Work",        "work",  25 * 60),
            ("Short break", "short",  5 * 60),
            ("Long break",  "long",  15 * 60),
        ]
        self._dur_spins = {}
        for label, key, default_s in rows:
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setStyleSheet(lbl_style)
            ds = DurationSpin(default_s)
            self._dur_spins[key] = ds
            rl.addWidget(lbl)
            rl.addStretch()
            rl.addWidget(ds)
            sett_lay.addWidget(row_w)

        # ── break flow row ────────────────────
        flow_row = QWidget()
        flow_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        fl = QHBoxLayout(flow_row)
        fl.setContentsMargins(0, 0, 0, 0)

        flow_lbl = QLabel("Break flow")
        flow_lbl.setStyleSheet(lbl_style)
        fl.addWidget(flow_lbl)
        fl.addStretch()

        self._flow_combo = QComboBox()
        self._flow_combo.addItems([
            "Auto (4 short breaks → long break)",
            "Always short",
            "Always long",
        ])
        self._flow_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,6);
                border: 1px solid rgba(255,255,255,14);
                border-radius: 7px;
                padding: 3px 10px;
                color: rgba(255,255,255,160);
                font-size: 11px;
                font-family: 'Segoe UI';
                min-width: 130px;
            }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background: #16131f;
                color: rgba(255,255,255,160);
                border: 1px solid rgba(255,255,255,16);
                selection-background-color: rgba(192,132,252,0.25);
                font-size: 11px;
            }
        """)
        fl.addWidget(self._flow_combo)
        sett_lay.addWidget(flow_row)

        # apply button
        self.btn_apply = QPushButton("apply")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: rgba(192,132,252,0.22);
                color: rgba(216,180,254,230);
                border: 1px solid rgba(192,132,252,0.45);
                border-radius: 8px;
                padding: 7px;
                font-size: 11px;
                font-family: 'Segoe UI';
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(192,132,252,0.36);
                color: rgba(233,213,255,255);
                border-color: rgba(192,132,252,0.65);
            }
            QPushButton:pressed {
                background: rgba(192,132,252,0.28);
            }
        """)
        sett_lay.addWidget(self.btn_apply)
        root.addWidget(sett_card)

        # ── status bar ────────────────────────
        self.status_label = QLabel("ready")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: rgba(255,255,255,90);")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status_label)

    # ── system tray ───────────────────────────
    def _setup_tray(self):
        tray_icon = None
        icon_path = os.path.join(ASSETS_DIR, "icon.png")
        if os.path.exists(icon_path):
            tray_icon = QIcon(icon_path)

        if tray_icon is None or tray_icon.isNull():
            tray_icon = self._generate_tray_icon()

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip("ScreenBreak")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f0d1a;
                color: rgba(255,255,255,170);
                border: 1px solid rgba(255,255,255,14);
                border-radius: 9px;
                padding: 4px;
            }
            QMenu::item { padding: 7px 20px; border-radius: 5px; font-size: 11px; }
            QMenu::item:selected { background: rgba(192,132,252,0.22); }
            QMenu::separator { background: rgba(255,255,255,10); height: 1px; margin: 3px 8px; }
        """)

        act_show = QAction("Show window", self)
        act_show.triggered.connect(self._show_from_tray)
        self._act_toggle = QAction("Pause timer", self)
        self._act_toggle.triggered.connect(self._tray_toggle_timer)
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self._quit_app)
        act_feedback = QAction("Send feedback", self)
        act_feedback.triggered.connect(self._open_feedback)

        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(self._act_toggle)
        menu.addSeparator()
        menu.addAction(act_feedback)
        menu.addSeparator()
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if not self.tray.isVisible():
            self.tray.show()

    def _open_feedback(self):
        email = self._user_info.get("email", "")
        self._feedback_win = FeedbackWindow(user_email=email)
        self._feedback_win.show()

    def _generate_tray_icon(self) -> QIcon:
        px = QPixmap(32, 32)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 32, 32)
        grad.setColorAt(0, QColor("#c084fc"))
        grad.setColorAt(1, QColor("#f472b6"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 28, 28)
        p.end()
        return QIcon(px)

    # ── signal wiring ─────────────────────────
    def _connect_signals(self):
        self.btn_start.clicked.connect(self._ui_start)
        self.btn_pause.clicked.connect(self._ui_pause)
        self.btn_skip.clicked.connect(self._ui_skip)
        self.btn_reset.clicked.connect(self._ui_reset)
        self.btn_apply.clicked.connect(self._apply_settings)
        self.controller.phase_changed.connect(self._on_phase_changed)
        self.controller.session_done.connect(self._on_session_done)

    def _ui_skip(self):
        """Debounce wrapper: disable the button briefly, then call controller.skip()."""
        self.btn_skip.setEnabled(False)
        self.controller.skip()
        QTimer.singleShot(500, lambda: self.btn_skip.setEnabled(True))

    # ── button handlers ───────────────────────
    def _ui_start(self):
        self.btn_start.hide()
        self.btn_pause.show()
        self._act_toggle.setText("Pause timer")
        self.controller.start()
        self.status_label.setText("focusing")
        self.status_label.setStyleSheet("color: rgba(192,132,252,130); font-size: 9px;")

    def _ui_pause(self):
        self.btn_pause.hide()
        self.btn_start.show()
        self._act_toggle.setText("Resume timer")
        self.controller.pause()
        self.status_label.setText("paused")
        self.status_label.setStyleSheet("color: rgba(255,255,255,110); font-size: 9px;")

    def _ui_reset(self):
        self.btn_pause.hide()
        self.btn_start.show()
        self._act_toggle.setText("Pause timer")
        self.controller.reset()
        self.session_dots.setText("○  ○  ○  ○")
        self.session_dots.setStyleSheet("color: rgba(255,255,255,80); font-size: 9px; letter-spacing: 6px;")
        self.session_label.setText("session 1 of 4")
        self.session_label.setStyleSheet("color: rgba(255,255,255,55); font-size: 8px; letter-spacing: 0.5px;")
        self.status_label.setText("ready")
        self.status_label.setStyleSheet("color: rgba(255,255,255,90); font-size: 9px;")

    # ── Login / logout ────────────────────────
    def _load_saved_login(self):
        """Restore login state from QSettings on startup."""
        s = QSettings("ScreenBreak", "ScreenBreak")
        saved = s.value("user_info", None)
        if saved:
            try:
                info = json.loads(saved)
                first_name = info.get("given_name", "user")
                self._user_info = info
                self.btn_login.setText(f"hi, {first_name.lower()}")
                self.btn_login.clicked.disconnect()
                self.btn_login.clicked.connect(self._show_logout_menu)
            except Exception:
                pass

    def _do_google_login(self):
        self.btn_login.setText("loading...")
        QApplication.processEvents()
        try:
            SCOPES = [
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ]
            flow  = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)

            session = google.auth.transport.requests.AuthorizedSession(creds)
            info    = session.get("https://www.googleapis.com/oauth2/v2/userinfo").json()

            first_name      = info.get("given_name", "user")
            self._user_info = info
            self.btn_login.setText(f"hi, {first_name.lower()}")

            s = QSettings("ScreenBreak", "ScreenBreak")
            s.setValue("user_info", json.dumps(info))

            self.btn_login.clicked.disconnect()
            self.btn_login.clicked.connect(self._show_logout_menu)
            print("Logged in as:", info.get("email"))
        except Exception as e:
            self.btn_login.setText("login")
            print(f"Auth error: {e}")

    def _show_logout_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #16131f;
                color: rgba(255,255,255,180);
                border: 1px solid rgba(255,255,255,16);
                border-radius: 8px;
                padding: 4px;
                font-size: 11px;
                font-family: 'Segoe UI';
            }
            QMenu::item { padding: 6px 18px; border-radius: 5px; }
            QMenu::item:selected { background: rgba(192,132,252,0.22); }
        """)
        email = self._user_info.get("email", "")
        if email:
            lbl = QAction(email, self)
            lbl.setEnabled(False)
            menu.addAction(lbl)
            menu.addSeparator()
        act_logout = QAction("log out", self)
        act_logout.triggered.connect(self._do_logout)
        menu.addAction(act_logout)
        pos = self.btn_login.mapToGlobal(self.btn_login.rect().bottomLeft())
        menu.exec(pos)

    def _do_logout(self):
        self._user_info = {}
        s = QSettings("ScreenBreak", "ScreenBreak")
        s.remove("user_info")
        self.btn_login.setText("login")
        self.btn_login.clicked.disconnect()
        self.btn_login.clicked.connect(self._do_google_login)

    def _close_overlay_safely(self):
        """Safely close the overlay with proper state management and signal cleanup."""
        if self.overlay is None or self._overlay_closing:
            return
        
        self._overlay_closing = True
        try:
            # Disconnect tick signal to prevent stale updates after close
            try:
                self.overlay.controller.tick.disconnect(self.overlay._update_timer)
            except Exception:
                pass
            # Close the overlay widget
            _ov = self.overlay
            self.overlay = None
            _ov.close()
        except Exception as e:
            print(f"[ERROR] Overlay close failed: {e}")
        finally:
            self._overlay_closing = False

    def _toggle_global_mute(self):
        self._muted = not self._muted
        self.btn_global_mute.setText("🔇" if self._muted else "🔊")
        if self.overlay and self._muted:
            self.overlay._stop_sound()
        QSettings("ScreenBreak", "ScreenBreak").setValue("muted", self._muted)

    def _tray_toggle_timer(self):
        if self.controller.is_running:
            self._ui_pause()
        else:
            self._ui_start()

    def _apply_settings(self):
        """Apply settings with safe overlay cleanup before controller reset."""
        # Close any live break overlay before resetting the controller,
        # because update_settings → reset → phase_changed would otherwise
        # try to manipulate a partially-destroyed overlay.
        self._close_overlay_safely()

        try:
            flow_map = {0: "auto", 1: "always_short", 2: "always_long"}
            flow = flow_map.get(self._flow_combo.currentIndex(), "auto")
            self.controller.update_settings(
                self._dur_spins["work"].value_secs(),
                self._dur_spins["short"].value_secs(),
                self._dur_spins["long"].value_secs(),
                flow
            )
            self.btn_pause.hide()
            self.btn_start.show()
            self._act_toggle.setText("Pause timer")
            self.status_label.setText("saved")
            self.status_label.setStyleSheet("color: rgba(192,132,252,110); font-size: 9px;")
            s = QSettings("ScreenBreak", "ScreenBreak")
            s.setValue("work_secs",  self._dur_spins["work"].value_secs())
            s.setValue("short_secs", self._dur_spins["short"].value_secs())
            s.setValue("long_secs",  self._dur_spins["long"].value_secs())
            s.setValue("break_flow", self._flow_combo.currentIndex())
            s.setValue("muted",      self._muted)
        except Exception as e:
            print(f"[ERROR] Apply settings failed: {e}")
            self.status_label.setText("error saving settings")
            self.status_label.setStyleSheet("color: rgba(255,100,100,140); font-size: 9px;")

    def _load_settings(self):
        s       = QSettings("ScreenBreak", "ScreenBreak")
        work_s  = int(s.value("work_secs",  25 * 60))
        short_s = int(s.value("short_secs",  5 * 60))
        long_s  = int(s.value("long_secs",  15 * 60))
        flow_i  = int(s.value("break_flow", 0))
        muted   = s.value("muted", False) == "true"

        self._dur_spins["work"]._min_spin.setValue(work_s // 60)
        self._dur_spins["work"]._sec_spin.setValue(work_s % 60)
        self._dur_spins["short"]._min_spin.setValue(short_s // 60)
        self._dur_spins["short"]._sec_spin.setValue(short_s % 60)
        self._dur_spins["long"]._min_spin.setValue(long_s // 60)
        self._dur_spins["long"]._sec_spin.setValue(long_s % 60)
        self._flow_combo.setCurrentIndex(flow_i)

        if muted:
            self._muted = True
            self.btn_global_mute.setText("🔇")

        self._apply_settings()
        self._load_saved_login()

    # ── controller callbacks ──────────────────
    def _on_phase_changed(self, phase: str):
        """Handle phase transitions with proper overlay state management."""
        # Skip overlay manipulation if a close operation is already in progress
        if self._overlay_closing:
            return
        
        if phase == "Work":
            # Close any active overlay when returning to work phase
            self._close_overlay_safely()
            self.status_label.setText("focusing")
            self.status_label.setStyleSheet(
                "color: rgba(192,132,252,120); font-size: 9px;")
            # Pre-pick assets for the next break
            self._picker.start()
        else:
            # Close any existing overlay before creating new one
            self._close_overlay_safely()
            try:
                gif_path, sound_path = self._picker.pop()
                self.overlay = BreakOverlayWindow(
                    self.controller,
                    muted=self._muted,
                    gif_path=gif_path,
                    sound_path=sound_path,
                )
                self.overlay.showFullScreen()
                self.tray.showMessage(
                    "break time",
                    f"{phase} — step away",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
            except Exception as e:
                print(f"[ERROR] Failed to create break overlay: {e}")
                self.overlay = None

    def _on_session_done(self, count: int):
        pos = count % self.controller.sessions_per_cycle or \
              self.controller.sessions_per_cycle
        dots = "●  " * pos + "○  " * (self.controller.sessions_per_cycle - pos)
        self.session_dots.setText(dots.strip())
        self.session_dots.setStyleSheet(
            "color: rgba(192,132,252,160); font-size: 9px; letter-spacing: 6px;")
        self.session_label.setText(f"session {pos} of {self.controller.sessions_per_cycle}")
        self.session_label.setStyleSheet(
            "color: rgba(192,132,252,100); font-size: 8px; letter-spacing: 0.5px;")

    # ── tray helpers ──────────────────────────
    def _minimize_to_tray(self):
        self.hide()
        self.tray.showMessage(
            "ScreenBreak",
            "Running in tray — click to restore.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    # ── painting ─────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0, QColor(13, 11, 22, 248))
        bg.setColorAt(1, QColor(9,   8, 18, 250))
        p.fillPath(path, QBrush(bg))

        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawPath(path)

        glow = QLinearGradient(0, 0, self.width(), 0)
        glow.setColorAt(0.0, QColor(192, 132, 252,  0))
        glow.setColorAt(0.5, QColor(192, 132, 252, 35))
        glow.setColorAt(1.0, QColor(244, 114, 182,  0))
        glow_path = QPainterPath()
        glow_path.addRoundedRect(QRectF(0, 0, self.width(), 2), 1, 1)
        p.fillPath(glow_path, QBrush(glow))

        p.end()

    # ── dragging ─────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (event.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                QTimer.singleShot(0, self._minimize_to_tray)
        super().changeEvent(event)

    def _quit_app(self):
        """Fully quit the application — used by the × title-bar button."""
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        # OS close (Alt+F4, taskbar close, etc.) → also quit fully.
        self.tray.hide()
        event.accept()
        QApplication.quit()


# ──────────────────────────────────────────────
# FEEDBACK WINDOW  (Supabase used here only)
# ──────────────────────────────────────────────
class FeedbackWindow(QWidget):
    def __init__(self, user_email: str = "", parent=None):
        super().__init__(parent)
        self.user_email = user_email
        self.setWindowTitle("Send Feedback")
        self.setFixedSize(380, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._rating = 0
        self._build_ui()

    def _build_ui(self):
        from PyQt6.QtWidgets import QTextEdit
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Title bar
        tb = QHBoxLayout()
        title = QLabel("feedback")
        title.setStyleSheet("color: rgba(255,255,255,180); font-size: 13px; font-family: 'Segoe UI';")
        tb.addWidget(title)
        tb.addStretch()
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: rgba(255,255,255,60); border: none; font-size: 16px; } "
            "QPushButton:hover { color: white; }")
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)
        root.addLayout(tb)

        # Star rating
        rating_lbl = QLabel("how's your experience?")
        rating_lbl.setStyleSheet("color: rgba(255,255,255,100); font-size: 11px; font-family: 'Segoe UI';")
        root.addWidget(rating_lbl)

        stars_row = QHBoxLayout()
        self._star_btns = []
        for i in range(1, 6):
            s = QPushButton("☆")
            s.setFixedSize(36, 36)
            s.setStyleSheet(
                "QPushButton { background: transparent; color: rgba(255,255,255,60); border: none; font-size: 20px; } "
                "QPushButton:hover { color: #f472b6; }")
            s.clicked.connect(lambda _, r=i: self._set_rating(r))
            stars_row.addWidget(s)
            self._star_btns.append(s)
        stars_row.addStretch()
        root.addLayout(stars_row)

        # Message box
        msg_lbl = QLabel("tell us more (optional)")
        msg_lbl.setStyleSheet("color: rgba(255,255,255,100); font-size: 11px; font-family: 'Segoe UI';")
        root.addWidget(msg_lbl)

        self.msg_box = QTextEdit()
        self.msg_box.setPlaceholderText("what could be better?")
        self.msg_box.setFixedHeight(100)
        self.msg_box.setStyleSheet("""
            QTextEdit {
                background: rgba(255,255,255,6);
                border: 1px solid rgba(255,255,255,14);
                border-radius: 8px;
                padding: 8px;
                color: rgba(255,255,255,190);
                font-size: 11px;
                font-family: 'Segoe UI';
            }
        """)
        root.addWidget(self.msg_box)

        # Submit button
        self.btn_submit = QPushButton("send feedback")
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background: rgba(192,132,252,0.22);
                color: rgba(216,180,254,220);
                border: 1px solid rgba(192,132,252,0.30);
                border-radius: 10px;
                padding: 8px;
                font-size: 11px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover { background: rgba(192,132,252,0.35); }
        """)
        self.btn_submit.clicked.connect(self._submit)
        root.addWidget(self.btn_submit)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: rgba(255,255,255,80); font-size: 10px;")
        root.addWidget(self.status_lbl)

    def _set_rating(self, rating: int):
        self._rating = rating
        for i, btn in enumerate(self._star_btns):
            btn.setText("★" if i < rating else "☆")
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; font-size: 20px; "
                f"color: {'#c084fc' if i < rating else 'rgba(255,255,255,40)'}; }}"
                f"QPushButton:hover {{ color: #f472b6; }}"
            )

    def _submit(self):
        if self._rating == 0:
            self.status_lbl.setText("please select a rating ★")
            return
        self.btn_submit.setText("sending...")
        QApplication.processEvents()
        try:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            if not url or not key:
                self.status_lbl.setText("couldn't send — missing config")
                print(f"Feedback error: SUPABASE_URL={url!r}, SUPABASE_KEY={key!r}")
                self.btn_submit.setText("send feedback")
                return
            sb = create_client(url, key)
            sb.table("feedback").insert({
                "email":   self.user_email or "anonymous",
                "rating":  self._rating,
                "message": self.msg_box.toPlainText().strip(),
            }).execute()
            self.status_lbl.setText("✓ thanks for your feedback!")
            self.btn_submit.setText("sent!")
            QTimer.singleShot(2000, self.close)
        except Exception as e:
            self.status_lbl.setText("couldn't send — check your connection")
            self.btn_submit.setText("send feedback")
            print(f"Feedback error ({type(e).__name__}): {e}")  # ← was swallowing details
            import traceback; traceback.print_exc()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 16, 16)
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0, QColor(13, 11, 22, 252))
        bg.setColorAt(1, QColor(9, 8, 18, 252))
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawPath(path)
        p.end()


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Set taskbar / dock icon (overrides the default Python icon)
    icon_path = os.path.join(ASSETS_DIR, "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    controller = TimerController()
    window     = MainWindow(controller)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()