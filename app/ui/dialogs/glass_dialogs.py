# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel, QCheckBox, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen
from PyQt5.QtCore import Qt, QRectF

from app.ui.styles.glass_components import GlassTitleBar, FramelessBorderDialog
from app.ui.widgets.progress_bar import CyberEnergyBar

class GlassLoadingDialog(FramelessBorderDialog):
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = GlassTitleBar(title or "模型加载", self)
        self.title_bar.btn_min.hide()
        self.title_bar.btn_max.hide()
        self.title_bar.btn_close.hide()
        layout.addWidget(self.title_bar)

        content_widget = QWidget(self)
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
        self.setFixedSize(380, 200)

    def set_message(self, text):
        if self.label:
            self.label.setText(text)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
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
    def __init__(self, parent=None, title="", text="", buttons=None, checkbox_text=None):
        super().__init__(parent)
        self._result_key = None
        self._checkbox = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = GlassTitleBar(title or "提示", self)
        layout.addWidget(title_bar)

        content_widget = QWidget(self)
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
            btn.clicked.connect(lambda checked, k=key: self._on_button_clicked(k))
            btn_row.addWidget(btn)
        content_layout.addLayout(btn_row)

        layout.addWidget(content_widget)
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(420, 220)

    def _on_button_clicked(self, key):
        self._result_key = key
        self.accept()

    def result_key(self):
        return self._result_key

    def is_checked(self):
        if self._checkbox is None:
            return False
        return bool(self._checkbox.isChecked())
