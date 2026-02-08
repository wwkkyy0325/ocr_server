# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QCursor

class FloatingResultWidget(QWidget):
    restore_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Frameless, Always on Top, Tool window (no taskbar entry)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container widget for background styling
        self.container = QWidget()
        self.container.setObjectName("Container")
        # Semi-transparent black background with border
        self.container.setStyleSheet("""
            QWidget#Container {
                background-color: rgba(0, 0, 0, 200);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 100);
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 5, 10, 10)
        
        # Title bar (for dragging and close)
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_title = QLabel("OCR Result")
        self.lbl_title.setStyleSheet("color: white; font-weight: bold; font-family: Microsoft YaHei;")
        
        btn_restore = QPushButton("❐")
        btn_restore.setFixedSize(24, 24)
        btn_restore.setCursor(Qt.PointingHandCursor)
        btn_restore.setToolTip("恢复主界面 / Restore Main Window")
        btn_restore.clicked.connect(self.restore_requested.emit)
        btn_restore.setStyleSheet("""
            QPushButton {
                background-color: transparent; 
                color: white; 
                border: none; 
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { color: #55ff55; }
        """)

        btn_close = QPushButton("×")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.hide)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent; 
                color: white; 
                border: none; 
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover { color: #ff5555; }
        """)
        
        title_bar.addWidget(self.lbl_title)
        title_bar.addStretch()
        title_bar.addWidget(btn_restore)
        title_bar.addWidget(btn_close)
        
        container_layout.addLayout(title_bar)
        
        # Text Area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(False) # Allow editing
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 14px;
                font-family: Microsoft YaHei;
            }
            QTextEdit::selection {
                background-color: #0078d7;
                color: white;
            }
        """)
        container_layout.addWidget(self.text_edit)
        
        layout.addWidget(self.container)
        
        self.resize(400, 300)
        
        # Dragging logic
        self.old_pos = None
        self.user_moved = False

    def set_text(self, text):
        self.text_edit.setPlainText(text)
        self.show()
        self.raise_()
        self.activateWindow()
        
        # If user hasn't moved the window, set to top-right of current screen
        if not self.user_moved:
            cursor_pos = QCursor.pos()
            screen_geo = QApplication.desktop().screenGeometry(cursor_pos)
            
            # Target: Top-Right (with some margin)
            target_x = screen_geo.right() - self.width() - 20
            target_y = screen_geo.top() + 50 # Leave some space for status bar or similar
            
            self.move(target_x, target_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()
            self.user_moved = True # Mark as moved by user

    def mouseReleaseEvent(self, event):
        self.old_pos = None
