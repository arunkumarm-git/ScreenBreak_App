# ui/feedback.py
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen
from auth import get_supabase_client

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
            # ---> NEW: Use your existing client instead of os.getenv <---
            sb = get_supabase_client()
            if not sb:
                self.status_lbl.setText("couldn't connect to database")
                self.btn_submit.setText("send feedback")
                return

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
            print(f"Feedback error ({type(e).__name__}): {e}")
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