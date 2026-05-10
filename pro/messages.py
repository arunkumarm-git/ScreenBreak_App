# pro/messages.py
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QLineEdit, QListWidgetItem
from PyQt6.QtCore import Qt, QRectF, QSettings
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen

# CustomMessagesWindow: allows pro users to add messages that appear on the break overlay
class CustomMessagesWindow(QWidget):
    def __init__(self, is_pro: bool, parent=None):
        super().__init__(parent)
        self._is_pro = is_pro
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        self._load_messages()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Title bar
        tb = QHBoxLayout()
        title = QLabel("custom messages")
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

        columns = QHBoxLayout()
        self.short_list = self._build_column(columns, "Short Break")
        self.long_list  = self._build_column(columns, "Long Break")
        root.addLayout(columns)

    def _build_column(self, parent_layout, title_text):
        col = QVBoxLayout()
        col.setSpacing(8)
        
        lbl = QLabel(title_text)
        lbl.setStyleSheet("color: rgba(255,255,255,120); font-size: 11px;")
        col.addWidget(lbl)

        # List Widget
        list_w = QListWidget()
        list_w.setStyleSheet("""
            QListWidget { background: rgba(255,255,255,6); border: 1px solid rgba(255,255,255,14); border-radius: 6px; padding: 4px; color: white; font-size: 11px;}
            QListWidget::item { padding: 4px; border-bottom: 1px solid rgba(255,255,255,5); }
            QListWidget::item:selected { background: rgba(192,132,252,40); border-radius: 4px;}
        """)
        col.addWidget(list_w)

        # Input fields
        input_style = "background: rgba(255,255,255,10); border: none; border-radius: 4px; padding: 4px 8px; color: white; font-size: 10px;"
        head_input = QLineEdit()
        head_input.setPlaceholderText("Headline (e.g. stretch)")
        head_input.setStyleSheet(input_style)
        col.addWidget(head_input)

        sub_input = QLineEdit()
        sub_input.setPlaceholderText("Subtitle (e.g. touch your toes)")
        sub_input.setStyleSheet(input_style)
        col.addWidget(sub_input)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_add = QPushButton("add" if self._is_pro else "🔒 pro")
        btn_add.setStyleSheet("QPushButton { background: rgba(192,132,252,0.2); color: #d8b4fe; border-radius: 4px; padding: 4px; font-size: 10px;} QPushButton:hover { background: rgba(192,132,252,0.4); }")
        
        btn_del = QPushButton("delete")
        btn_del.setStyleSheet("QPushButton { background: rgba(255,255,255,10); color: rgba(255,255,255,120); border-radius: 4px; padding: 4px; font-size: 10px;}")
        
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        col.addLayout(btn_row)

        parent_layout.addLayout(col)

        if not self._is_pro:
            btn_add.setEnabled(False)
            btn_del.setEnabled(False)
            head_input.setEnabled(False)
            sub_input.setEnabled(False)
        else:
            btn_add.clicked.connect(lambda: self._add_msg(list_w, head_input, sub_input))
            btn_del.clicked.connect(lambda: self._del_msg(list_w))

        return list_w

    def _add_msg(self, list_w, h_input, s_input):
        h, s = h_input.text().strip(), s_input.text().strip()
        if h and s:
            item = QListWidgetItem(f"{h}\n{s}")
            item.setData(Qt.ItemDataRole.UserRole, [h, s])
            list_w.addItem(item)
            h_input.clear()
            s_input.clear()
            self._save_messages()

    def _del_msg(self, list_w):
        for item in list_w.selectedItems():
            list_w.takeItem(list_w.row(item))
        self._save_messages()

    def _load_messages(self):
        s = QSettings("ScreenBreak", "ScreenBreak")
        short_raw = json.loads(s.value("custom_messages_short", "[]"))
        long_raw  = json.loads(s.value("custom_messages_long", "[]"))
        
        for h, sub in short_raw:
            item = QListWidgetItem(f"{h}\n{sub}")
            item.setData(Qt.ItemDataRole.UserRole, [h, sub])
            self.short_list.addItem(item)
            
        for h, sub in long_raw:
            item = QListWidgetItem(f"{h}\n{sub}")
            item.setData(Qt.ItemDataRole.UserRole, [h, sub])
            self.long_list.addItem(item)

    def _save_messages(self):
        short_msgs = [self.short_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.short_list.count())]
        long_msgs  = [self.long_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.long_list.count())]
        s = QSettings("ScreenBreak", "ScreenBreak")
        s.setValue("custom_messages_short", json.dumps(short_msgs))
        s.setValue("custom_messages_long", json.dumps(long_msgs))

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