# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：玻璃风格加载/消息对话框集合，统一模态提示与加载动画
# - 核心实现：FramelessBorderDialog 基础上自绘背景与标题栏，集成能量条进度
# - 关联关系：主窗口在模型加载、错误提示等场景中调用这些对话框
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QLabel, QCheckBox, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen
from PyQt5.QtCore import Qt, QRectF

from app.ui.styles.glass_components import GlassTitleBar, FramelessBorderDialog
from app.ui.widgets.progress_bar import CyberEnergyBar
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class GlassLoadingDialog(FramelessBorderDialog):
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="GlassLoadingDialog")
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent)
        logger = get_logger()
        logger.debug("glass_loading_dialog", "initializing", f"Initializing loading dialog: {title or '模型加载'}")
        
        self.setModal(True)  # type: ignore
        self.setWindowModality(Qt.ApplicationModal)  # type: ignore
        layout = QVBoxLayout(self)  # type: ignore
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = GlassTitleBar(title or "模型加载", self)
        self.title_bar.btn_min.hide()
        self.title_bar.btn_max.hide()
        self.title_bar.btn_close.hide()
        layout.addWidget(self.title_bar)

        content_widget = QWidget(self)  # type: ignore
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 12, 16, 16)
        content_layout.setSpacing(12)

        self.label = QLabel(message or "正在加载模型，请稍候...", content_widget)
        self.label.setWordWrap(True)
        content_layout.addWidget(self.label)

        self.energy_bar = CyberEnergyBar(content_widget)
        self.energy_bar.setToolTip("模型加载中")
        self.energy_bar.set_ready_text("就绪")
        content_layout.addWidget(self.energy_bar)

        layout.addWidget(content_widget)
        self.setFixedSize(380, 200)  # type: ignore
        
        logger.success("glass_loading_dialog", "initialized", "Loading dialog initialized successfully")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassLoadingDialog")
    def set_message(self, text):
        """设置加载消息"""
        if self.label:
            self.label.setText(text)
            logger = get_logger()
            logger.debug("glass_loading_dialog", "message_updated", f"Message updated: {text[:50]}...")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)  # type: ignore
        path = QPainterPath()
        path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), self._corner_radius, self._corner_radius)

        bg = QColor(8, 12, 26, 220)
        painter.fillPath(path, bg)

        pen = QPen(QColor(255, 255, 255, 180))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()


class GlassMessageDialog(FramelessBorderDialog):
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="GlassMessageDialog")
    def __init__(self, parent=None, title="", text="", buttons=None, checkbox_text=None):
        super().__init__(parent)
        logger = get_logger()
        logger.debug("glass_message_dialog", "initializing", f"Initializing message dialog: {title or '提示'}")
        
        self._result_key = None
        self._checkbox = None
        layout = QVBoxLayout(self)  # type: ignore
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = GlassTitleBar(title or "提示", self)
        layout.addWidget(title_bar)

        content_widget = QWidget(self)  # type: ignore
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 12, 16, 16)
        content_layout.setSpacing(12)

        label = QLabel(text or "", content_widget)
        label.setWordWrap(True)
        content_layout.addWidget(label)

        if checkbox_text:
            cb = QCheckBox(checkbox_text, content_widget)
            self._checkbox = cb
            content_layout.addWidget(cb)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._buttons = []
        if not buttons:
            buttons = [("ok", "确定")]
        for key, caption in buttons:
            btn = QPushButton(caption, self)
            self._buttons.append((key, btn))
            btn.clicked.connect(lambda checked, k=key: self._on_button_clicked(k))  # type: ignore
            btn_row.addWidget(btn)
        content_layout.addLayout(btn_row)

        layout.addWidget(content_widget)
        self.setModal(True)  # type: ignore
        self.setWindowModality(Qt.ApplicationModal)  # type: ignore
        self.setFixedSize(420, 220)  # type: ignore
        
        logger.success("glass_message_dialog", "initialized", "Message dialog initialized successfully")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="GlassMessageDialog")
    def _on_button_clicked(self, key):
        """按钮点击处理"""
        self._result_key = key
        logger = get_logger()
        logger.debug("glass_message_dialog", "button_clicked", f"Button clicked: {key}")
        self.accept()   # type:  ignore

    def result_key(self):
        return self._result_key

    def is_checked(self):
        if self._checkbox is None:
            return False
        return bool(self._checkbox.isChecked())
