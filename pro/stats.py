# pro/stats.py
import datetime
import csv
from collections import defaultdict
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QApplication
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen
from auth import get_supabase_client

# StatsWindow: shows today's focus time, current streak, etc.  Data is loaded from Supabase and requires user to be logged in.  If not pro, shows a lock and hides the data.    
class StatsWindow(QWidget):
    def __init__(self, user_info: dict, is_pro: bool, parent=None):
        super().__init__(parent)
        self._user_info = user_info
        self._is_pro    = is_pro
        self.setFixedSize(320, 360)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        if is_pro:
            self._load_stats()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Title bar
        tb = QHBoxLayout()
        title = QLabel("focus stats")
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

        # Stats Grid
        self.lbl_today  = self._add_stat_row(root, "Today", "-- min")
        self.lbl_week   = self._add_stat_row(root, "This week", "-- sessions")
        self.lbl_streak = self._add_stat_row(root, "Current streak", "-- days")
        self.lbl_total  = self._add_stat_row(root, "Total focus", "-- hrs")

        root.addStretch()

        # Pro Lock / Export Button
        if not self._is_pro:
            lock = QLabel("🔒 unlock stats with pro")
            lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lock.setStyleSheet(
                "color: rgba(192,132,252,200); font-size: 11px; font-family: 'Segoe UI'; "
                "background: rgba(192,132,252,0.1); padding: 10px; border-radius: 8px;")
            root.addWidget(lock)
        else:
            self.btn_export = QPushButton("↓ export csv")
            self.btn_export.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,8); color: rgba(255,255,255,160); border-radius: 8px; padding: 6px; font-size: 10px; }
                QPushButton:hover { background: rgba(255,255,255,16); color: white; }
            """)
            self.btn_export.clicked.connect(self._export_csv)  # ── NEW: Wire the click
            root.addWidget(self.btn_export)

            # ── NEW: Status label for export feedback ──
            self.status_lbl = QLabel("")
            self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_lbl.setStyleSheet("color: rgba(255,255,255,80); font-size: 10px;")
            root.addWidget(self.status_lbl)

    def _export_csv(self):
        import csv
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Sessions", 
            f"screenbreak_{datetime.date.today()}.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return
            
        self.btn_export.setText("exporting...")
        QApplication.processEvents()
        
        try:
            sb = get_supabase_client()
            
            sub  = self._user_info.get("id")
            
            # Fetch all sessions for this user, newest first
            rows = (
                sb.table("sessions")
                .select("completed_at, duration_secs, phase")
                .eq("google_sub", sub)
                .order("completed_at", desc=True)
                .execute()
            ).data
            
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["date", "duration_min", "phase"])
                w.writeheader()
                for r in rows:
                    w.writerow({
                        "date":         r["completed_at"][:19].replace("T", " "),
                        "duration_min": round(r["duration_secs"] / 60, 1),
                        "phase":        r["phase"],
                    })
                    
            self.btn_export.setText("↓ export csv")
            self.status_lbl.setText(f"✓ exported {len(rows)} sessions")
            
        except Exception as e:
            self.btn_export.setText("↓ export csv")
            self.status_lbl.setText("export failed")
            print(f"[export] {e}")        

    def _add_stat_row(self, layout, label_text, val_text):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: rgba(255,255,255,120); font-size: 11px; font-family: 'Segoe UI';")
        val = QLabel(val_text)
        val.setStyleSheet("color: rgba(255,255,255,220); font-size: 12px; font-family: 'Segoe UI'; font-weight: 500;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        layout.addLayout(row)
        return val

    def _load_stats(self):
        self.lbl_today.setText("loading...")
        QApplication.processEvents()
        try:
            sb = get_supabase_client()
        
            sub  = self._user_info.get("id")
            rows = (
                sb.table("sessions")
                .select("completed_at, duration_secs")
                .eq("google_sub", sub)
                .eq("phase", "Work")
                .gte("completed_at", "now() - interval '30 days'")
                .execute()
            ).data
            self._render_stats(rows)
        except Exception as e:
            print(f"[stats] load failed: {e}")
            self.lbl_today.setText("error")

    def _render_stats(self, rows):
        from collections import defaultdict
        import datetime
        today = datetime.date.today()
        by_day = defaultdict(int)
        
        for r in rows:
            # Parse 'YYYY-MM-DD' from '2023-10-27T14:32:00+00:00'
            day = r["completed_at"][:10]
            by_day[day] += r["duration_secs"]
            
        today_mins  = by_day.get(str(today), 0) // 60
        week_count  = sum(1 for r in rows if r["completed_at"][:10] >= str(today - datetime.timedelta(days=6)))
        total_hours = sum(r["duration_secs"] for r in rows) / 3600
        
        streak = 0
        d = today
        while str(d) in by_day:
            streak += 1
            d -= datetime.timedelta(days=1)
            
        self.lbl_today.setText(f"{today_mins} min")
        self.lbl_week.setText(f"{week_count} sessions")
        self.lbl_streak.setText(f"{streak} days")
        self.lbl_total.setText(f"{total_hours:.1f} hrs")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 16, 16)
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0, QColor(16, 13, 26, 252))
        bg.setColorAt(1, QColor(10, 8, 20, 252))
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawPath(path)
        p.end()