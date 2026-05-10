# pro/gate.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen, QDesktopServices
from PyQt6.QtCore import QUrl
from auth import get_supabase_client

class UpgradeDialog(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFixedSize(360, 480)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(14)

        # Title
        tb = QHBoxLayout()
        title = QLabel("unlock screenbreak pro")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold; font-family: 'Segoe UI';")
        tb.addWidget(title)
        tb.addStretch()
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,60); border: none; font-size: 16px; } QPushButton:hover { color: white; }")
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)
        root.addLayout(tb)

        # Features List
        features = [
            "✦ Focus stats dashboard",
            "✦ Session history export",
            "✦ Custom break messages",
            "✦ Unlimited GIF packs",
            "✦ Custom sounds",
            "✦ Sessions-per-cycle control",
            "✦ Supporter badge"
        ]
        for f in features:
            lbl = QLabel(f)
            lbl.setStyleSheet("color: rgba(255,255,255,180); font-size: 12px; font-family: 'Segoe UI'; padding: 2px 0px;")
            root.addWidget(lbl)

        root.addStretch()

        # Buy Button
        self.btn_buy = QPushButton("get pro — $9 / lifetime")
        self.btn_buy.setStyleSheet("QPushButton { background: rgba(192,132,252,0.25); color: #d8b4fe; border: 1px solid rgba(192,132,252,0.5); border-radius: 8px; padding: 12px; font-size: 12px; font-weight: bold; } QPushButton:hover { background: rgba(192,132,252,0.4); }")
        # Replace with your actual LemonSqueezy/Gumroad link
        self.btn_buy.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://your-store.com/checkout")))
        root.addWidget(self.btn_buy)

        # License Activation
        key_layout = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Already have a key? Enter here...")
        self.key_input.setStyleSheet("background: rgba(255,255,255,10); border: none; border-radius: 6px; padding: 8px; color: white; font-size: 11px;")
        key_layout.addWidget(self.key_input)

        self.btn_activate = QPushButton("activate")
        self.btn_activate.setStyleSheet("QPushButton { background: rgba(255,255,255,15); color: white; border-radius: 6px; padding: 8px 12px; font-size: 11px; } QPushButton:hover { background: rgba(255,255,255,25); }")
        self.btn_activate.clicked.connect(self._try_activate)
        key_layout.addWidget(self.btn_activate)
        
        root.addLayout(key_layout)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: rgba(255,255,255,100); font-size: 10px;")
        root.addWidget(self.status)

    def _try_activate(self):
        key = self.key_input.text().strip()
        sub = self.main_window._user_info.get("id") if self.main_window._user_info else None
        
        if not sub:
            self.status.setText("please log in first via the main window")
            return
            
        self.btn_activate.setText("...")
        QApplication.processEvents()
        
        try:
            sb = get_supabase_client()
            row = sb.table("licenses").select("*").eq("key", key).single().execute()
            
            if row.data and not row.data.get("redeemed_by"):
                # Mark license as used and update user row
                sb.table("licenses").update({"redeemed_by": sub, "redeemed_at": "now()"}).eq("key", key).execute()
                sb.table("users").update({"is_pro": True}).eq("google_sub", sub).execute()
                
                # Update main window state natively
                self.main_window._is_pro = True
                self.main_window._user_info["is_pro"] = True
                self.main_window._refresh_pro_badge()
                
                self.status.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
                self.status.setText("✓ pro activated! welcome!")
                QTimer.singleShot(2000, self.close)
            else:
                self.btn_activate.setText("activate")
                self.status.setStyleSheet("color: #f87171; font-size: 10px;")
                self.status.setText("invalid or already used key")
        except Exception as e:
            self.btn_activate.setText("activate")
            self.status.setText("couldn't verify — check connection")
            print(f"[activate error] {e}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 16, 16)
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0, QColor(20, 16, 32, 252))
        bg.setColorAt(1, QColor(12, 10, 24, 252))
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(QColor(192, 132, 252, 40), 1))
        p.drawPath(path)
        p.end()