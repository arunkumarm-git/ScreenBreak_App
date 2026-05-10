import sys
import ctypes
import platform
import os
import json

if platform.system() == "Windows":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ScreenBreak")

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QSystemTrayIcon, QMenu, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QSettings
from PyQt6.QtGui import (
    QFont, QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath, 
    QIcon, QAction, QPixmap
)

# ── Local Modular Imports ──────────────────────────────────────────────
from controller import TimerController
from assets import LocalAssetPicker, ASSETS_DIR
from auth import perform_login, load_cached_user, logout_user

from ui.widgets import CircularTimer, Card, DurationSpin
from ui.break_overlay import BreakOverlayWindow
from ui.feedback import FeedbackWindow

from pro.gate import UpgradeDialog
from pro.stats import StatsWindow
from pro.messages import CustomMessagesWindow
from pro.media import GifPackManager, SoundManagerWindow
# ───────────────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    def __init__(self, controller: TimerController):
        super().__init__()
        self.controller  = controller
        self.overlay     = None
        self._overlay_closing = False
        self._drag_pos   = None
        self._muted      = False
        self._user_info  = {}
        self._is_pro     = False
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

        self._picker.start(is_pro=self._is_pro)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Title bar ─────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(4, 0, 2, 0)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(6)
        logo_row.setContentsMargins(0, 0, 0, 0)

        logo = QLabel("screenbreak")
        logo.setFont(QFont("Segoe UI", 11))
        logo.setStyleSheet("color: rgba(255,255,255,160); letter-spacing: 1.5px;")
        logo_row.addWidget(logo)

        self.pro_badge = QLabel("✦ pro")
        self.pro_badge.setFont(QFont("Segoe UI", 8))
        self.pro_badge.setStyleSheet(
            "color: rgba(192,132,252,200); letter-spacing: 1px; "
            "background: rgba(192,132,252,0.12); border-radius: 6px; padding: 1px 5px;"
        )
        self.pro_badge.hide()
        logo_row.addWidget(self.pro_badge)
        logo_row.addStretch()
        tb.addLayout(logo_row)

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

        self.btn_stats = QPushButton("📊")
        self.btn_stats.setFixedSize(24, 24)
        self.btn_stats.setToolTip("Focus Stats")
        self.btn_stats.setStyleSheet("""
            QPushButton { background: transparent; color: rgba(255,255,255,55); border: none; font-size: 12px; border-radius: 12px; }
            QPushButton:hover { background: rgba(255,255,255,10); color: rgba(255,255,255,120); }
        """)
        self.btn_stats.clicked.connect(self._show_stats)
        tb.addWidget(self.btn_stats)

        self.btn_global_mute = QPushButton("🔊")
        self.btn_global_mute.setFixedSize(24, 24)
        self.btn_global_mute.setToolTip("Mute break sounds")
        self.btn_global_mute.setStyleSheet(self.btn_stats.styleSheet())
        self.btn_global_mute.clicked.connect(self._toggle_global_mute)
        tb.addWidget(self.btn_global_mute)

        for symbol, handler in [("−", self._minimize_to_tray), ("×", self._quit_app)]:
            btn = QPushButton(symbol)
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,16); color: rgba(255,255,255,160); border: 1px solid rgba(255,255,255,28); border-radius: 12px; font-size: 14px; }
                QPushButton:hover { background: rgba(255,255,255,32); color: rgba(255,255,255,240); }
                QPushButton:pressed { background: rgba(255,255,255,22); }
            """)
            btn.clicked.connect(handler)
            tb.addWidget(btn)
        root.addWidget(title_bar)

        # ── Session progress indicator ─────────
        session_row = QHBoxLayout()
        session_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_row.setSpacing(8)
        self.session_label = QLabel("session 1 of 4")
        self.session_label.setFont(QFont("Segoe UI", 8))
        self.session_label.setStyleSheet("color: rgba(255,255,255,55); letter-spacing: 0.5px;")
        session_row.addWidget(self.session_label)

        self.session_dots = QLabel("○  ○  ○  ○")
        self.session_dots.setFont(QFont("Segoe UI", 9))
        self.session_dots.setStyleSheet("color: rgba(255,255,255,80); letter-spacing: 6px;")
        session_row.addWidget(self.session_dots)
        root.addLayout(session_row)

        # ── Circular Timer ────────────────────
        self.circ = CircularTimer(self.controller)
        self.circ.setFixedSize(210, 210)
        timer_row = QHBoxLayout()
        timer_row.addWidget(self.circ, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addLayout(timer_row)

        # ── Control Buttons ───────────────────
        ctrl_card = Card()
        ctrl_lay  = QHBoxLayout(ctrl_card)
        ctrl_lay.setContentsMargins(14, 10, 14, 10)
        ctrl_lay.setSpacing(8)

        ghost = "QPushButton { background: rgba(255,255,255,6); color: rgba(255,255,255,200); border: 1px solid rgba(255,255,255,18); border-radius: 14px; padding: 6px 16px; font-size: 11px; font-family: 'Segoe UI'; } QPushButton:hover { background: rgba(255,255,255,14); color: rgba(255,255,255,240); }"
        primary = "QPushButton { background: rgba(192, 132, 252, 0.20); color: rgba(216,180,254,220); border: 1px solid rgba(192,132,252,0.30); border-radius: 14px; padding: 6px 22px; font-size: 11px; font-family: 'Segoe UI'; } QPushButton:hover { background: rgba(192,132,252,0.32); color: rgba(233,213,255,240); }"

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

        # ── Settings Card ─────────────────────
        sett_card = Card()
        sett_lay  = QVBoxLayout(sett_card)
        sett_lay.setContentsMargins(20, 14, 20, 14)
        sett_lay.setSpacing(10)

        sett_title = QLabel("SETTINGS")
        sett_title.setStyleSheet("color: rgba(255,255,255,110); font-size: 8px; letter-spacing: 3px; font-weight: bold;")
        sett_lay.addWidget(sett_title)

        lbl_style = "color: rgba(255,255,255,200); font-size: 11px; font-family: 'Segoe UI';"

        self._dur_spins = {}
        for label, key, default_s in [("Work", "work", 25*60), ("Short break", "short", 5*60), ("Long break", "long", 15*60)]:
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

        # Break flow
        flow_row = QWidget()
        flow_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        fl = QHBoxLayout(flow_row)
        fl.setContentsMargins(0, 0, 0, 0)
        flow_lbl = QLabel("Break flow")
        flow_lbl.setStyleSheet(lbl_style)
        fl.addWidget(flow_lbl)
        fl.addStretch()

        self._flow_combo = QComboBox()
        self._flow_combo.addItems(["Auto (4 short breaks → long break)", "Always short", "Always long"])
        self._flow_combo.setStyleSheet("""
            QComboBox { background: rgba(255,255,255,6); border: 1px solid rgba(255,255,255,14); border-radius: 7px; padding: 3px 10px; color: rgba(255,255,255,160); font-size: 11px; font-family: 'Segoe UI'; min-width: 130px; }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView { background: #16131f; color: rgba(255,255,255,160); border: 1px solid rgba(255,255,255,16); selection-background-color: rgba(192,132,252,0.25); font-size: 11px; }
        """)
        fl.addWidget(self._flow_combo)
        sett_lay.addWidget(flow_row)

        # Sessions per cycle (Pro)
        spc_row = QWidget()
        spc_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        sl = QHBoxLayout(spc_row)
        sl.setContentsMargins(0, 0, 0, 0)
        spc_lbl = QLabel("Sessions per cycle")
        spc_lbl.setStyleSheet(lbl_style)
        sl.addWidget(spc_lbl)
        sl.addStretch()
        self._spc_spin = QSpinBox()
        self._spc_spin.setRange(1, 12)
        self._spc_spin.setValue(4)
        self._spc_spin.setEnabled(False)
        self._spc_spin.setStyleSheet("QSpinBox { background: rgba(255,255,255,6); border: 1px solid rgba(255,255,255,14); border-radius: 7px; padding: 3px 6px; color: rgba(255,255,255,190); font-size: 11px; min-width: 44px; max-width: 52px; } QSpinBox::up-button, QSpinBox::down-button { background: rgba(255,255,255,10); border: none; width: 12px; }")
        sl.addWidget(self._spc_spin)
        self._spc_lock = QLabel("🔒 pro")
        self._spc_lock.setStyleSheet("color: rgba(192,132,252,120); font-size: 9px;")
        sl.addWidget(self._spc_lock)
        sett_lay.addWidget(spc_row)

        edit_btn_style = "QPushButton { background: rgba(255,255,255,6); color: rgba(255,255,255,160); border-radius: 7px; padding: 4px 10px; font-size: 10px; } QPushButton:hover { background: rgba(255,255,255,12); color: white; }"

        # Custom Messages (Pro)
        msg_row = QWidget()
        msg_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        ml = QHBoxLayout(msg_row)
        ml.setContentsMargins(0, 0, 0, 0)
        msg_lbl = QLabel("Custom messages")
        msg_lbl.setStyleSheet(lbl_style)
        ml.addWidget(msg_lbl)
        ml.addStretch()
        self.btn_custom_msgs = QPushButton("✎ edit")
        self.btn_custom_msgs.setStyleSheet(edit_btn_style)
        self.btn_custom_msgs.clicked.connect(self._show_custom_msgs)
        ml.addWidget(self.btn_custom_msgs)
        sett_lay.addWidget(msg_row)

        # Custom GIFs (Pro)
        gif_row = QWidget()
        gif_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        gl = QHBoxLayout(gif_row)
        gl.setContentsMargins(0, 0, 0, 0)
        gif_lbl = QLabel("Custom GIFs")
        gif_lbl.setStyleSheet(lbl_style)
        gl.addWidget(gif_lbl)
        gl.addStretch()
        self.btn_custom_gifs = QPushButton("📁 manage")
        self.btn_custom_gifs.setStyleSheet(edit_btn_style)
        self.btn_custom_gifs.clicked.connect(self._show_gif_manager)
        gl.addWidget(self.btn_custom_gifs)
        sett_lay.addWidget(gif_row)

        # Custom Sounds (Pro)
        sound_row = QWidget()
        sound_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        sdl = QHBoxLayout(sound_row)
        sdl.setContentsMargins(0, 0, 0, 0)
        sound_lbl = QLabel("Custom Sounds")
        sound_lbl.setStyleSheet(lbl_style)
        sdl.addWidget(sound_lbl)
        sdl.addStretch()
        self.btn_custom_sounds = QPushButton("📁 manage")
        self.btn_custom_sounds.setStyleSheet(edit_btn_style)
        self.btn_custom_sounds.clicked.connect(self._show_sound_manager)
        sdl.addWidget(self.btn_custom_sounds)
        sett_lay.addWidget(sound_row)

        # Apply Button
        self.btn_apply = QPushButton("apply")
        self.btn_apply.setStyleSheet("""
            QPushButton { background: rgba(192,132,252,0.22); color: rgba(216,180,254,230); border: 1px solid rgba(192,132,252,0.45); border-radius: 8px; padding: 7px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 500; }
            QPushButton:hover { background: rgba(192,132,252,0.36); color: rgba(233,213,255,255); border-color: rgba(192,132,252,0.65); }
            QPushButton:pressed { background: rgba(192,132,252,0.28); }
        """)
        sett_lay.addWidget(self.btn_apply)
        root.addWidget(sett_card)

        self.status_label = QLabel("ready")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: rgba(255,255,255,90);")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status_label)

    # ── Application Routing & Windows ────────
    def _refresh_pro_badge(self):
        if getattr(self, '_is_pro', False):
            self.pro_badge.show()
            self._spc_spin.setEnabled(True)
            self._spc_lock.hide()
        else:
            self.pro_badge.hide()
            self._spc_spin.setEnabled(False)
            self._spc_lock.show()

    def _show_stats(self):
        if not self._user_info:
            self.status_label.setText("please log in to view stats")
            return
        self._stats_win = StatsWindow(user_info=self._user_info, is_pro=self._is_pro)
        self._stats_win.show()

    def _show_custom_msgs(self):
        if not self._is_pro: return self._show_upgrade_dialog()
        self._msg_win = CustomMessagesWindow(is_pro=self._is_pro)
        self._msg_win.show()

    def _show_gif_manager(self):
        if not self._is_pro: return self._show_upgrade_dialog()
        self._gif_win = GifPackManager(is_pro=self._is_pro)
        self._gif_win.show()

    def _show_sound_manager(self):
        if not self._is_pro: return self._show_upgrade_dialog()
        self._sound_win = SoundManagerWindow(is_pro=self._is_pro)
        self._sound_win.show()

    def _show_upgrade_dialog(self):
        if not hasattr(self, '_upgrade_win') or not self._upgrade_win.isVisible():
            self._upgrade_win = UpgradeDialog(main_window=self)
            self._upgrade_win.show()

    def _open_feedback(self):
        email = self._user_info.get("email", "")
        self._feedback_win = FeedbackWindow(user_email=email)
        self._feedback_win.show()

    # ── Auth & Initialization ─────────
    def _load_saved_login(self):
        info = load_cached_user()
        if info:
            self._user_info = info
            self._is_pro = info.get("is_pro", False)
            self._refresh_pro_badge()
            self.btn_login.setText(f"hi, {info.get('given_name', 'user').lower()}")
            self.btn_login.clicked.disconnect()
            self.btn_login.clicked.connect(self._show_logout_menu)

    def _do_google_login(self):
        self.btn_login.setText("loading...")
        QApplication.processEvents()
        try:
            info = perform_login()
            self._user_info = info
            self._is_pro = info.get("is_pro", False)
            self._refresh_pro_badge()
            self.btn_login.setText(f"hi, {info.get('given_name', 'user').lower()}")
            self.btn_login.clicked.disconnect()
            self.btn_login.clicked.connect(self._show_logout_menu)
        except Exception as e:
            self.btn_login.setText("login")
            print(f"Auth error: {e}")

    def _show_logout_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #16131f; color: rgba(255,255,255,180); border: 1px solid rgba(255,255,255,16); border-radius: 8px; padding: 4px; font-size: 11px; font-family: 'Segoe UI'; }
            QMenu::item { padding: 6px 18px; border-radius: 5px; } QMenu::item:selected { background: rgba(192,132,252,0.22); }
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
        menu.exec(self.btn_login.mapToGlobal(self.btn_login.rect().bottomLeft()))

    def _do_logout(self):
        logout_user()
        self._user_info = {}
        self._is_pro = False
        self._refresh_pro_badge()
        self.btn_login.setText("login")
        self.btn_login.clicked.disconnect()
        self.btn_login.clicked.connect(self._do_google_login)

    # ── Signals & Timers ─────────
    def _setup_tray(self):
        tray_icon = QIcon(os.path.join(ASSETS_DIR, "icon.png"))
        if tray_icon.isNull():
            px = QPixmap(32, 32); px.fill(Qt.GlobalColor.transparent); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            grad = QLinearGradient(0, 0, 32, 32); grad.setColorAt(0, QColor("#c084fc")); grad.setColorAt(1, QColor("#f472b6"))
            p.setBrush(QBrush(grad)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(2, 2, 28, 28); p.end(); tray_icon = QIcon(px)

        self.tray = QSystemTrayIcon(tray_icon, self)
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #0f0d1a; color: rgba(255,255,255,170); border: 1px solid rgba(255,255,255,14); border-radius: 9px; padding: 4px; } QMenu::item { padding: 7px 20px; border-radius: 5px; font-size: 11px; } QMenu::item:selected { background: rgba(192,132,252,0.22); }")

        act_show = QAction("Show window", self); act_show.triggered.connect(self._show_from_tray)
        act_stats = QAction("Focus stats", self); act_stats.triggered.connect(self._show_stats)
        self._act_toggle = QAction("Pause timer", self); self._act_toggle.triggered.connect(self._tray_toggle_timer)
        act_feedback = QAction("Send feedback", self); act_feedback.triggered.connect(self._open_feedback)
        act_quit = QAction("Quit", self); act_quit.triggered.connect(self._quit_app)

        menu.addActions([act_show, act_stats])
        menu.addSeparator()
        menu.addAction(self._act_toggle)
        menu.addSeparator()
        menu.addActions([act_feedback, act_quit])

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._ui_start)
        self.btn_pause.clicked.connect(self._ui_pause)
        self.btn_skip.clicked.connect(self._ui_skip)
        self.btn_reset.clicked.connect(self._ui_reset)
        self.btn_apply.clicked.connect(self._apply_settings)
        self.controller.phase_changed.connect(self._on_phase_changed)
        self.controller.session_done.connect(self._on_session_done)
        
        # We hook _save_session natively since the method is right below this
        self.controller.session_recorded.connect(self._save_session)

    def _save_session(self, duration_secs: int, phase: str):
        sub = self._user_info.get("id")
        if not sub: return
        try:
            from auth import get_supabase_client
            sb = get_supabase_client()
            if sb:
                sb.table("sessions").insert({"google_sub": sub, "duration_secs": duration_secs, "phase": phase}).execute()
        except Exception as e:
            print(f"[session] save failed: {e}")

    def _ui_start(self): self.btn_start.hide(); self.btn_pause.show(); self._act_toggle.setText("Pause timer"); self.controller.start(); self.status_label.setText("focusing"); self.status_label.setStyleSheet("color: rgba(192,132,252,130); font-size: 9px;")
    def _ui_pause(self): self.btn_pause.hide(); self.btn_start.show(); self._act_toggle.setText("Resume timer"); self.controller.pause(); self.status_label.setText("paused"); self.status_label.setStyleSheet("color: rgba(255,255,255,110); font-size: 9px;")
    def _ui_skip(self): self.btn_skip.setEnabled(False); self.controller.skip(); QTimer.singleShot(500, lambda: self.btn_skip.setEnabled(True))
    def _ui_reset(self): self.btn_pause.hide(); self.btn_start.show(); self._act_toggle.setText("Pause timer"); self.controller.reset(); self.session_dots.setText("○  ○  ○  ○"); self.session_dots.setStyleSheet("color: rgba(255,255,255,80); font-size: 9px; letter-spacing: 6px;"); self.session_label.setText(f"session 1 of {self.controller.sessions_per_cycle}"); self.status_label.setText("ready"); self.status_label.setStyleSheet("color: rgba(255,255,255,90); font-size: 9px;")

    def _close_overlay_safely(self):
        if self.overlay is None or self._overlay_closing: return
        self._overlay_closing = True
        try:
            try: self.overlay.controller.tick.disconnect(self.overlay._update_timer)
            except Exception: pass
            _ov = self.overlay; self.overlay = None; _ov.close()
        except Exception as e: print(f"[ERROR] Overlay close failed: {e}")
        finally: self._overlay_closing = False

    def _toggle_global_mute(self):
        self._muted = not self._muted
        self.btn_global_mute.setText("🔇" if self._muted else "🔊")
        if self.overlay and self._muted: self.overlay._stop_sound()
        QSettings("ScreenBreak", "ScreenBreak").setValue("muted", self._muted)

    def _tray_toggle_timer(self):
        self._ui_pause() if self.controller.is_running else self._ui_start()

    def _apply_settings(self):
        self._close_overlay_safely()
        try:
            flow = {0: "auto", 1: "always_short", 2: "always_long"}.get(self._flow_combo.currentIndex(), "auto")
            self.controller.update_settings(self._dur_spins["work"].value_secs(), self._dur_spins["short"].value_secs(), self._dur_spins["long"].value_secs(), flow)
            
            s = QSettings("ScreenBreak", "ScreenBreak")
            if self._is_pro:
                self.controller.sessions_per_cycle = self._spc_spin.value()
                s.setValue("sessions_per_cycle", self._spc_spin.value())
                
            self.btn_pause.hide(); self.btn_start.show(); self._act_toggle.setText("Pause timer")
            self.status_label.setText("saved"); self.status_label.setStyleSheet("color: rgba(192,132,252,110); font-size: 9px;")
            
            s.setValue("work_secs", self._dur_spins["work"].value_secs()); s.setValue("short_secs", self._dur_spins["short"].value_secs()); s.setValue("long_secs", self._dur_spins["long"].value_secs()); s.setValue("break_flow", self._flow_combo.currentIndex()); s.setValue("muted", self._muted)
        except Exception as e:
            self.status_label.setText("error saving settings"); self.status_label.setStyleSheet("color: rgba(255,100,100,140); font-size: 9px;")

    def _load_settings(self):
        s = QSettings("ScreenBreak", "ScreenBreak")
        self._dur_spins["work"]._min_spin.setValue(int(s.value("work_secs", 25*60)) // 60); self._dur_spins["work"]._sec_spin.setValue(int(s.value("work_secs", 25*60)) % 60)
        self._dur_spins["short"]._min_spin.setValue(int(s.value("short_secs", 5*60)) // 60); self._dur_spins["short"]._sec_spin.setValue(int(s.value("short_secs", 5*60)) % 60)
        self._dur_spins["long"]._min_spin.setValue(int(s.value("long_secs", 15*60)) // 60); self._dur_spins["long"]._sec_spin.setValue(int(s.value("long_secs", 15*60)) % 60)
        self._flow_combo.setCurrentIndex(int(s.value("break_flow", 0)))
        
        spc = int(s.value("sessions_per_cycle", 4))
        self._spc_spin.setValue(spc)
        if self._is_pro: self.controller.sessions_per_cycle = spc
            
        if s.value("muted", False) == "true": self._muted = True; self.btn_global_mute.setText("🔇")
        self._load_saved_login()
        self._apply_settings()

    def _on_phase_changed(self, phase: str):
        if self._overlay_closing: return
        if phase == "Work":
            self._close_overlay_safely(); self.status_label.setText("focusing"); self.status_label.setStyleSheet("color: rgba(192,132,252,120); font-size: 9px;"); self._picker.start(is_pro=self._is_pro)
        else:
            self._close_overlay_safely()
            try:
                gif, sound = self._picker.pop()
                self.overlay = BreakOverlayWindow(self.controller, is_pro=self._is_pro, muted=self._muted, gif_path=gif, sound_path=sound)
                self.overlay.showFullScreen()
                self.tray.showMessage("break time", f"{phase} — step away", QSystemTrayIcon.MessageIcon.Information, 3000)
            except Exception as e: print(f"[ERROR] Failed to create break overlay: {e}")

    def _on_session_done(self, count: int):
        pos = count % self.controller.sessions_per_cycle or self.controller.sessions_per_cycle
        dots = "●  " * pos + "○  " * (self.controller.sessions_per_cycle - pos)
        self.session_dots.setText(dots.strip()); self.session_dots.setStyleSheet("color: rgba(192,132,252,160); font-size: 9px; letter-spacing: 6px;")
        self.session_label.setText(f"session {pos} of {self.controller.sessions_per_cycle}"); self.session_label.setStyleSheet("color: rgba(192,132,252,100); font-size: 8px; letter-spacing: 0.5px;")

    def _minimize_to_tray(self): self.hide(); self.tray.showMessage("ScreenBreak", "Running in tray — click to restore.", QSystemTrayIcon.MessageIcon.Information, 2000)
    def _show_from_tray(self): self.showNormal(); self.activateWindow(); self.raise_()
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: self._show_from_tray()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos: self.move(event.globalPosition().toPoint() - self._drag_pos)
    def mouseReleaseEvent(self, event): self._drag_pos = None
    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized(): QTimer.singleShot(0, self._minimize_to_tray)
        super().changeEvent(event)
    def _quit_app(self): self.tray.hide(); QApplication.quit()
    def closeEvent(self, event): self.tray.hide(); event.accept(); QApplication.quit()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); path = QPainterPath(); path.addRoundedRect(QRectF(self.rect()), 18, 18)
        bg = QLinearGradient(0, 0, 0, self.height()); bg.setColorAt(0, QColor(13, 11, 22, 248)); bg.setColorAt(1, QColor(9, 8, 18, 250)); p.fillPath(path, QBrush(bg))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1)); p.drawPath(path)
        glow = QLinearGradient(0, 0, self.width(), 0); glow.setColorAt(0.0, QColor(192, 132, 252, 0)); glow.setColorAt(0.5, QColor(192, 132, 252, 35)); glow.setColorAt(1.0, QColor(244, 114, 182, 0))
        glow_path = QPainterPath(); glow_path.addRoundedRect(QRectF(0, 0, self.width(), 2), 1, 1); p.fillPath(glow_path, QBrush(glow)); p.end()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon_path = os.path.join(ASSETS_DIR, "icon.png")
    if os.path.exists(icon_path): app.setWindowIcon(QIcon(icon_path))
    
    controller = TimerController()
    window = MainWindow(controller)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()