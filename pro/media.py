# pro/media.py
import os
import shutil
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QFileDialog
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen
from assets import USER_GIFS_DIR, USER_SOUNDS_DIR

# GifPackManager: allows pro users to add folders of gifs that can be randomly shown on the break overlay.  Each folder is treated as a separate pack, and all gifs within are used.  If not pro, shows a lock and hides the UI.
class GifPackManager(QWidget):
    def __init__(self, is_pro: bool, parent=None):
        super().__init__(parent)
        self._is_pro = is_pro
        self.setFixedSize(380, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        if self._is_pro:
            self._refresh_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Title bar
        tb = QHBoxLayout()
        title = QLabel("custom gif packs")
        title.setStyleSheet("color: rgba(255,255,255,180); font-size: 13px; font-family: 'Segoe UI';")
        tb.addWidget(title)
        tb.addStretch()
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,60); border: none; font-size: 16px; } QPushButton:hover { color: white; }")
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)
        root.addLayout(tb)

        if not self._is_pro:
            lock = QLabel("🔒 unlock unlimited gif packs with pro")
            lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lock.setStyleSheet("color: rgba(192,132,252,200); font-size: 11px; font-family: 'Segoe UI'; background: rgba(192,132,252,0.1); padding: 20px; border-radius: 8px;")
            root.addWidget(lock)
            root.addStretch()
            return

        # Pro UI
        self.list_w = QListWidget()
        self.list_w.setStyleSheet("""
            QListWidget { background: rgba(255,255,255,6); border: 1px solid rgba(255,255,255,14); border-radius: 8px; padding: 6px; color: white; font-size: 12px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid rgba(255,255,255,5); }
            QListWidget::item:selected { background: rgba(192,132,252,40); border-radius: 4px; }
        """)
        root.addWidget(self.list_w)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ add folder")
        btn_add.setStyleSheet("QPushButton { background: rgba(192,132,252,0.2); color: #d8b4fe; border-radius: 6px; padding: 8px; font-size: 11px;} QPushButton:hover { background: rgba(192,132,252,0.4); }")
        btn_add.clicked.connect(self._add_folder)
        
        btn_del = QPushButton("delete selected")
        btn_del.setStyleSheet("QPushButton { background: rgba(255,255,255,10); color: rgba(255,255,255,120); border-radius: 6px; padding: 8px; font-size: 11px;} QPushButton:hover { background: rgba(255,100,100,40); color: #ffaaaa; }")
        btn_del.clicked.connect(self._delete_folder)
        
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        root.addLayout(btn_row)

    def _refresh_list(self):
        self.list_w.clear()
        if os.path.isdir(USER_GIFS_DIR):
            for item in os.listdir(USER_GIFS_DIR):
                if os.path.isdir(os.path.join(USER_GIFS_DIR, item)):
                    self.list_w.addItem(item)

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder Containing GIFs")
        if not path:
            return
        
        folder_name = os.path.basename(path)
        dest = os.path.join(USER_GIFS_DIR, folder_name)
        
        if os.path.exists(dest):
            return # Already added
            
        try:
            shutil.copytree(path, dest)
            self._refresh_list()
        except Exception as e:
            print(f"[GIF Manager] Failed to copy folder: {e}")

    def _delete_folder(self):
        for item in self.list_w.selectedItems():
            folder_name = item.text()
            target = os.path.join(USER_GIFS_DIR, folder_name)
            try:
                shutil.rmtree(target)
                self._refresh_list()
            except Exception as e:
                print(f"[GIF Manager] Failed to delete folder: {e}")

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

# SoundManagerWindow: allows pro users to add custom sound files that can be played during breaks.  If not pro, shows a lock and hides the UI.
class SoundManagerWindow(QWidget):
    def __init__(self, is_pro: bool, parent=None):
        super().__init__(parent)
        self._is_pro = is_pro
        self.setFixedSize(380, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        if self._is_pro:
            self._refresh_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Title bar
        tb = QHBoxLayout()
        title = QLabel("custom sounds")
        title.setStyleSheet("color: rgba(255,255,255,180); font-size: 13px; font-family: 'Segoe UI';")
        tb.addWidget(title)
        tb.addStretch()
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,60); border: none; font-size: 16px; } QPushButton:hover { color: white; }")
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)
        root.addLayout(tb)

        if not self._is_pro:
            lock = QLabel("🔒 unlock custom sounds with pro")
            lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lock.setStyleSheet("color: rgba(192,132,252,200); font-size: 11px; font-family: 'Segoe UI'; background: rgba(192,132,252,0.1); padding: 20px; border-radius: 8px;")
            root.addWidget(lock)
            root.addStretch()
            return

        # Pro UI
        self.list_w = QListWidget()
        self.list_w.setStyleSheet("""
            QListWidget { background: rgba(255,255,255,6); border: 1px solid rgba(255,255,255,14); border-radius: 8px; padding: 6px; color: white; font-size: 12px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid rgba(255,255,255,5); }
            QListWidget::item:selected { background: rgba(192,132,252,40); border-radius: 4px; }
        """)
        root.addWidget(self.list_w)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ add sounds")
        btn_add.setStyleSheet("QPushButton { background: rgba(192,132,252,0.2); color: #d8b4fe; border-radius: 6px; padding: 8px; font-size: 11px;} QPushButton:hover { background: rgba(192,132,252,0.4); }")
        btn_add.clicked.connect(self._add_sounds)
        
        btn_del = QPushButton("delete selected")
        btn_del.setStyleSheet("QPushButton { background: rgba(255,255,255,10); color: rgba(255,255,255,120); border-radius: 6px; padding: 8px; font-size: 11px;} QPushButton:hover { background: rgba(255,100,100,40); color: #ffaaaa; }")
        btn_del.clicked.connect(self._delete_sounds)
        
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        root.addLayout(btn_row)

    def _refresh_list(self):
        self.list_w.clear()
        if os.path.isdir(USER_SOUNDS_DIR):
            for file in os.listdir(USER_SOUNDS_DIR):
                if file.lower().endswith((".mp3", ".wav", ".ogg")):
                    self.list_w.addItem(file)

    def _add_sounds(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Audio Files", "", "Audio Files (*.mp3 *.wav *.ogg)")
        if not files:
            return
            
        for file_path in files:
            file_name = os.path.basename(file_path)
            dest = os.path.join(USER_SOUNDS_DIR, file_name)
            if not os.path.exists(dest):
                try:
                    shutil.copy2(file_path, dest)
                except Exception as e:
                    print(f"[Sound Manager] Failed to copy {file_name}: {e}")
                    
        self._refresh_list()

    def _delete_sounds(self):
        for item in self.list_w.selectedItems():
            file_name = item.text()
            target = os.path.join(USER_SOUNDS_DIR, file_name)
            try:
                os.remove(target)
                self._refresh_list()
            except Exception as e:
                print(f"[Sound Manager] Failed to delete {file_name}: {e}")

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