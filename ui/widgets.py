# ui/widgets.py
import math
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QSizePolicy
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QConicalGradient, QFont, QPainterPath, QLinearGradient
from controller import TimerController

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