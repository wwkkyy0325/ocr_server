# -*- coding: utf-8 -*-

"""
识别进度条（尤其批量处理时）
"""

try:
    from PyQt5.QtWidgets import QProgressBar, QWidget, QVBoxLayout, QLabel, QSizePolicy, QHBoxLayout
    from PyQt5.QtCore import Qt, QSize, pyqtProperty, QTimer, QRect
    from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QFont, QPen
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class ProgressBar(QWidget):
    def __init__(self):
        """
        初始化进度条
        """
        super().__init__()
        self.current_progress = 0
        self.max_progress = 100
        
        # 创建UI组件
        self.progress_bar = None
        self.status_label = None
        
        if PYQT_AVAILABLE:
            self._setup_ui()

    def _setup_ui(self):
        """
        设置UI界面
        """
        layout = QVBoxLayout()
        
        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(self.max_progress)
        self.progress_bar.setValue(self.current_progress)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)

    def update_progress(self, value, status_text=None):
        """
        更新进度

        Args:
            value: 进度值
            status_text: 状态文本
        """
        self.current_progress = value
        print(f"Progress: {value}/{self.max_progress}")
        
        if PYQT_AVAILABLE:
            self.progress_bar.setValue(value)
            if status_text:
                self.status_label.setText(status_text)
            self.progress_bar.update()

    def reset(self):
        """
        重置进度条
        """
        self.current_progress = 0
        self.max_progress = 100
        print("Progress bar reset")
        
        if PYQT_AVAILABLE:
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(100)
            self.status_label.setText("准备就绪")

    def set_max_progress(self, max_value):
        """
        设置最大进度值

        Args:
            max_value: 最大进度值
        """
        self.max_progress = max_value
        if PYQT_AVAILABLE:
            self.progress_bar.setMaximum(max_value)


class CyberEnergyBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self._ready_text = "就绪"
        self._bg_color = QColor("#050814")
        self._border_color_outer = QColor("#00FF66")
        self._border_color_inner = QColor("#00CC44")
        self._fill_start = QColor("#00FF66")
        self._fill_end = QColor("#A4FF2F")
        self._text_color = QColor("#E0F7FF")
        self._auto_animating = False
        self._anim_timer = None
        if PYQT_AVAILABLE:
            self.setMinimumHeight(18)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def paintEvent(self, event):
        if not PYQT_AVAILABLE:
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        radius = rect.height() / 2.0

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(rect, radius, radius)

        span = self._maximum - self._minimum
        if span > 0 and self._value > self._minimum:
            ratio = float(self._value - self._minimum) / float(span)
            if ratio < 0.0:
                ratio = 0.0
            if ratio > 1.0:
                ratio = 1.0
            w = int(rect.width() * ratio)
            if w > 0:
                fill_rect = QRect(rect.x(), rect.y(), w, rect.height())
                grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
                grad.setColorAt(0.0, self._fill_start)
                grad.setColorAt(1.0, self._fill_end)
                painter.setBrush(grad)
                painter.drawRoundedRect(fill_rect, radius, radius)

        outer_pen = QPen(self._border_color_outer)
        outer_pen.setWidthF(1.0)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(outer_pen)
        painter.drawRoundedRect(rect, radius, radius)

        inner = rect.adjusted(1, 1, -1, -1)
        inner_pen = QPen(self._border_color_inner)
        inner_pen.setWidthF(0.8)
        painter.setPen(inner_pen)
        painter.drawRoundedRect(inner, inner.height() / 2.0, inner.height() / 2.0)

        painter.setPen(self._text_color)
        painter.setFont(self.font())
        text = self._ready_text or ""
        painter.drawText(rect, Qt.AlignCenter, text)

    def sizeHint(self):
        if not PYQT_AVAILABLE:
            return super().sizeHint()
        h = max(self.minimumHeight(), int(self.fontMetrics().height() * 1.6))
        return QSize(260, h)

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def set_range(self, minimum, maximum):
        if maximum <= minimum:
            minimum, maximum = 0, 100
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        if self._value < self._minimum:
            self._value = self._minimum
        if self._value > self._maximum:
            self._value = self._maximum
        self.update()

    def value(self):
        return self._value

    def set_value(self, value):
        v = int(value)
        if v < self._minimum:
            v = self._minimum
        if v > self._maximum:
            v = self._maximum
        if v == self._value:
            return
        self._value = v
        if self._auto_animating and self._value >= self._maximum:
            self.stop_indeterminate()
        self.update()

    def set_ready_text(self, text):
        self._ready_text = str(text)
        self.update()

    progress = pyqtProperty(int, fget=value, fset=set_value)

    def start_indeterminate(self, interval_ms=80):
        if not PYQT_AVAILABLE:
            return
        self._auto_animating = True
        if self._anim_timer is None:
            self._anim_timer = QTimer(self)
            self._anim_timer.timeout.connect(self._on_anim_step)
        if not self._anim_timer.isActive():
            self._anim_timer.start(interval_ms)

    def stop_indeterminate(self):
        self._auto_animating = False
        if self._anim_timer and self._anim_timer.isActive():
            self._anim_timer.stop()

    def _on_anim_step(self):
        if not self._auto_animating:
            return
        span = self._maximum - self._minimum
        if span <= 0:
            span = 100
            self._minimum = 0
            self._maximum = span
        step = max(1, span // 60)
        self._value += step
        if self._value >= self._maximum:
            self._value = self._minimum
        self.update()


class MarqueeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._marquee_text = ""
        self._offset = 0
        self._timer = None
        if PYQT_AVAILABLE:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_timeout)
            self._timer.start(50)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.setText("")

    def set_marquee_text(self, text):
        self._marquee_text = str(text) if text else ""
        self._offset = 0
        self.update()

    def marquee_text(self):
        return self._marquee_text

    def paintEvent(self, event):
        if not PYQT_AVAILABLE:
            return super().paintEvent(event)

        if not self._marquee_text:
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = self.rect()
        fm = self.fontMetrics()
        text = self._marquee_text
        text_width = fm.width(text)
        if text_width <= 0:
            return

        spacing = 40
        total = text_width + spacing

        x = -self._offset
        y = (rect.height() + fm.ascent() - fm.descent()) // 2

        painter.setPen(self.palette().color(self.foregroundRole()))
        while x < rect.width():
            painter.drawText(x, y, text)
            x += total

    def _on_timeout(self):
        if not self._marquee_text:
            return
        fm = self.fontMetrics()
        text_width = fm.width(self._marquee_text)
        if text_width <= 0:
            return
        self._offset += 2
        spacing = 40
        total = text_width + spacing
        if self._offset >= total:
            self._offset = 0
        self.update()


class AnnouncementBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prefix_label = None
        self.marquee_label = None
        if PYQT_AVAILABLE:
            layout = QHBoxLayout()
            layout.setContentsMargins(4, 0, 4, 0)
            layout.setSpacing(6)
            self.prefix_label = QLabel("公告：", self)
            self.prefix_label.setObjectName("announcementPrefix")
            self.marquee_label = MarqueeLabel(self)
            self.marquee_label.setObjectName("announcementText")
            layout.addWidget(self.prefix_label)
            layout.addWidget(self.marquee_label)
            self.setLayout(layout)

    def set_announcement_text(self, text):
        if PYQT_AVAILABLE and self.marquee_label:
            self.marquee_label.set_marquee_text(text or "")

    def announcement_text(self):
        if PYQT_AVAILABLE and self.marquee_label:
            return self.marquee_label.marquee_text()
        return ""
