# -*- coding: utf-8 -*-

"""
Glass style components for UI (TitleBar, FramelessWindow, FramelessDialog)
"""

import sys
import ctypes
from ctypes import wintypes

try:
    from PyQt5.QtWidgets import (
        QWidget, QHBoxLayout, QLabel, QPushButton, QMainWindow, QDialog,
        QMenuBar, QComboBox
    )
    from PyQt5.QtGui import (
        QPainter, QColor, QPainterPath, QRegion, QPen
    )
    from PyQt5.QtCore import Qt, QPoint, QRectF
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # Mock base classes to avoid NameError on import
    class QWidget: pass
    class QMainWindow: pass
    class QDialog: pass

from app.ui.styles.background_painter import BackgroundPainter

_GLOBAL_CONFIG_MANAGER = None
_GLOBAL_BACKGROUND_PAINTER = None

def register_config_manager(config_manager):
    global _GLOBAL_CONFIG_MANAGER
    _GLOBAL_CONFIG_MANAGER = config_manager
    # Reset painter when config manager changes (optional, but safer)
    global _GLOBAL_BACKGROUND_PAINTER
    _GLOBAL_BACKGROUND_PAINTER = None

def _get_background_painter():
    global _GLOBAL_BACKGROUND_PAINTER
    if _GLOBAL_BACKGROUND_PAINTER is None:
        _GLOBAL_BACKGROUND_PAINTER = BackgroundPainter(_GLOBAL_CONFIG_MANAGER)
    return _GLOBAL_BACKGROUND_PAINTER

def _paint_glass_background(painter, path, rect, is_main=False):
    _get_background_painter().paint_background(painter, path, rect, is_main)


class GlassTitleBar(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setObjectName("glassTitleBar")
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("glassTitleLabel")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.btn_min = QPushButton("─", self)
        self.btn_max = QPushButton("▢", self)
        self.btn_close = QPushButton("✕", self)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(24, 20)
            b.setFlat(True)
            b.setObjectName("glassTitleButton")

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

        self.btn_min.clicked.connect(self._on_minimize)
        self.btn_max.clicked.connect(self._on_max_restore)
        self.btn_close.clicked.connect(self._on_close)

    def _on_minimize(self):
        w = self.window()
        if hasattr(w, "showMinimized"):
            w.showMinimized()

    def _on_max_restore(self):
        w = self.window()
        if hasattr(w, "isMaximized") and hasattr(w, "showNormal") and hasattr(w, "showMaximized"):
            if w.isMaximized():
                w.showNormal()
            else:
                w.showMaximized()

    def _on_close(self):
        w = self.window()
        if hasattr(w, "reject"):
            w.reject()
        else:
            w.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class FramelessBorderWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._border_width = 20
        self._corner_radius = 14
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _update_mask(self):
        r = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)
        _paint_glass_background(painter, path, r, is_main=True)
        pen = QPen(QColor(255, 255, 255, 200))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()

    def nativeEvent(self, eventType, message):
        if sys.platform.startswith("win"):
            if eventType in ("windows_generic_MSG", b"windows_generic_MSG"):
                msg = wintypes.MSG.from_address(message.__int__())
                WM_NCHITTEST = 0x0084
                if msg.message == WM_NCHITTEST:
                    x = ctypes.c_short(msg.lParam & 0xffff).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
                    pos = self.mapFromGlobal(QPoint(x, y))
                    w = self.width()
                    h = self.height()

                    edge = 6
                    corner = 12
                    HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT, HTCAPTION = 10, 11, 12, 13, 14, 15, 16, 17, 2

                    if pos.x() < corner and pos.y() < corner:
                        return True, HTTOPLEFT
                    if pos.x() > w - corner and pos.y() < corner:
                        return True, HTTOPRIGHT
                    if pos.x() < corner and pos.y() > h - corner:
                        return True, HTBOTTOMLEFT
                    if pos.x() > w - corner and pos.y() > h - corner:
                        return True, HTBOTTOMRIGHT

                    if pos.y() < edge:
                        return True, HTTOP
                    if pos.y() > h - edge:
                        return True, HTBOTTOM
                    if pos.x() < edge:
                        return True, HTLEFT
                    if pos.x() > w - edge:
                        return True, HTRIGHT

                    hit_widget = self.childAt(pos)
                    if hit_widget is not None:
                        w = hit_widget
                        interactive_types = (QMenuBar, QPushButton, QComboBox)
                        while w is not None:
                            if isinstance(w, interactive_types):
                                return False, 0
                            w = w.parentWidget()

                    title_height = 60
                    if pos.y() < title_height:
                        return True, HTCAPTION
        return super().nativeEvent(eventType, message)


class FramelessBorderDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._corner_radius = 12
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("glassDialog")

    def _update_mask(self):
        r = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)

        _paint_glass_background(painter, path, r, is_main=False)

        pen = QPen(QColor(255, 255, 255, 180))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()
