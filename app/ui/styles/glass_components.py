# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：实现玻璃风格 UI 组件（TitleBar、无边框窗口/对话框）
# - 核心实现：自绘圆角背景与边框，支持拖拽移动/最小化/最大化/关闭
# - 关联关系：主窗口与各对话框复用这些基类，背景绘制委托给 BackgroundPainter
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
    class QWidget:
        pass


    class QHBoxLayout:
        pass


    class QLabel:
        pass


    class QPushButton:
        pass


    class QMainWindow:
        pass


    class QDialog:
        pass


    class QMenuBar:
        pass


    class QComboBox:
        pass


    class QPainter:
        pass


    class QColor:
        pass


    class QPainterPath:
        pass


    class QRegion:
        pass


    class QPen:
        pass


    class Qt:
        pass


    class QPoint:
        pass


    class QRectF:
        pass

from app.ui.styles.background_painter import BackgroundPainter
from app.infrastructure.error_handler import handle_errors, ErrorCode
from app.log.log_bus import get_logger

logger = get_logger()

_GLOBAL_CONFIG_MANAGER = None
_GLOBAL_BACKGROUND_PAINTER = None


def register_config_manager(config_manager):
    global _GLOBAL_CONFIG_MANAGER
    _GLOBAL_CONFIG_MANAGER = config_manager
    # Reset painter when config manager changes (optional, but safer)
    global _GLOBAL_BACKGROUND_PAINTER
    _GLOBAL_BACKGROUND_PAINTER = None


@handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
def _get_background_painter():
    global _GLOBAL_BACKGROUND_PAINTER
    try:
        if _GLOBAL_BACKGROUND_PAINTER is None:
            _GLOBAL_BACKGROUND_PAINTER = BackgroundPainter(_GLOBAL_CONFIG_MANAGER)
        return _GLOBAL_BACKGROUND_PAINTER
    except Exception as e:
        logger.error("glass_components", "painter_init_failed", f"背景绘制器初始化失败：{e}", exc_info=True)
        # 降级：返回一个临时的无配置绘制器
        return BackgroundPainter(None)


@handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
def _paint_glass_background(painter, path, rect, is_main=False):
    try:
        _get_background_painter().paint_background(painter, path, rect, is_main)
    except Exception as e:
        logger.error("glass_components", "background_paint_failed", f"玻璃背景绘制失败：{e}", exc_info=True)
        # 降级处理：绘制纯色背景
        if painter and path:
            painter.fillPath(path, QColor(8, 12, 26, 220))


class GlassTitleBar(QWidget):
    def __init__(self, title="", parent=None):
        try:
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
            
            logger.debug("glass_components", "titlebar_initialized", f"GlassTitleBar initialized with title: {title}")
        except Exception as e:
            logger.error("glass_components", "titlebar_init_failed", f"标题栏初始化失败：{e}", exc_info=True)
            raise

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def _on_minimize(self):
        try:
            w = self.window()
            if hasattr(w, "showMinimized"):
                w.showMinimized()
        except Exception as e:
            logger.error("glass_components", "minimize_failed", f"最小化窗口失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def _on_max_restore(self):
        try:
            w = self.window()
            if hasattr(w, "isMaximized") and hasattr(w, "showNormal") and hasattr(w, "showMaximized"):
                if w.isMaximized():
                    w.showNormal()
                else:
                    w.showMaximized()
        except Exception as e:
            logger.error("glass_components", "maximize_failed", f"最大化/还原窗口失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def _on_close(self):
        try:
            w = self.window()
            if hasattr(w, "reject"):
                w.reject()
            else:
                w.close()
        except Exception as e:
            logger.error("glass_components", "close_failed", f"关闭窗口失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
            super().mousePressEvent(event)
        except Exception as e:
            logger.error("glass_components", "mouse_press_failed", f"鼠标按下事件处理失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def mouseMoveEvent(self, event):
        try:
            if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
                self.window().move(event.globalPos() - self._drag_pos)
            super().mouseMoveEvent(event)
        except Exception as e:
            logger.error("glass_components", "mouse_move_failed", f"鼠标移动事件处理失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def mouseReleaseEvent(self, event):
        try:
            self._drag_pos = None
            super().mouseReleaseEvent(event)
        except Exception as e:
            logger.error("glass_components", "mouse_release_failed", f"鼠标释放事件处理失败：{e}", exc_info=True)


class FramelessBorderWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
            self._border_width = 20
            self._corner_radius = 14
            self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            logger.debug("glass_components", "frameless_window_initialized", "FramelessBorderWindow initialized")
        except Exception as e:
            logger.error("glass_components", "frameless_window_init_failed", f"无边框窗口初始化失败：{e}", exc_info=True)
            raise

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def _update_mask(self):
        try:
            r = self.rect().adjusted(0, 0, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)
            region = QRegion(path.toFillPolygon().toPolygon())
            self.setMask(region)
        except Exception as e:
            logger.error("glass_components", "mask_update_failed", f"更新遮罩失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UI_RENDER_002, fallback_return=None, component="GlassComponents")
    def paintEvent(self, event):
        try:
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
        except Exception as e:
            logger.error("glass_components", "window_paint_failed", f"窗口绘制失败：{e}", exc_info=True)
            # 降级处理：绘制纯色背景
            if painter:
                painter.fillRect(self.rect(), QColor(8, 12, 26, 220))

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            self._update_mask()
        except Exception as e:
            logger.error("glass_components", "window_resize_failed", f"窗口大小调整失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=False, component="GlassComponents")
    def nativeEvent(self, eventType, message):
        """处理 Windows 原生事件（用于无边框窗口的拖拽和调整大小）"""
        # 🔥 关键修复：确保返回值类型正确 (bool, int) 或 None
        if not PYQT_AVAILABLE:
            return False, 0
            
        try:
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
            
            # 非 Windows 平台或非消息类型：调用父类并返回其结果
            result = super().nativeEvent(eventType, message)
            # 确保返回值有效
            if result is None:
                return False, 0
            return result
            
        except Exception as e:
            logger.error("glass_components", "native_event_failed", f"原生事件处理失败：{e}", exc_info=True)
            # 降级处理：返回安全默认值
            return False, 0


class FramelessBorderDialog(QDialog):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
            self._corner_radius = 12
            self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setObjectName("glassDialog")
            logger.debug("glass_components", "frameless_dialog_initialized", "FramelessBorderDialog initialized")
        except Exception as e:
            logger.error("glass_components", "frameless_dialog_init_failed", f"无边框对话框初始化失败：{e}", exc_info=True)
            raise

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def _update_mask(self):
        try:
            r = self.rect().adjusted(0, 0, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)
            region = QRegion(path.toFillPolygon().toPolygon())
            self.setMask(region)
        except Exception as e:
            logger.error("glass_components", "dialog_mask_update_failed", f"对话框遮罩更新失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UI_RENDER_002, fallback_return=None, component="GlassComponents")
    def paintEvent(self, event):
        try:
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
        except Exception as e:
            logger.error("glass_components", "dialog_paint_failed", f"对话框绘制失败：{e}", exc_info=True)
            # 降级处理：绘制纯色背景
            if painter:
                painter.fillRect(self.rect(), QColor(20, 25, 40, 210))

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassComponents")
    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            self._update_mask()
        except Exception as e:
            logger.error("glass_components", "dialog_resize_failed", f"对话框大小调整失败：{e}", exc_info=True)
