# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor

class DynamicStatusBar(QWidget):
    """
    动态状态栏组件
    支持：
    1. 动态省略号动画 (Loading...)
    2. 不同状态颜色 (Info, Success, Warning, Error)
    3. 图标/文字显示
    """
    
    # 状态类型定义
    STATUS_READY = "ready"
    STATUS_INFO = "info"
    STATUS_SUCCESS = "success"
    STATUS_WARNING = "warning"
    STATUS_ERROR = "error"
    STATUS_WORKING = "working" # 包含动画
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)
        self.layout.setSpacing(10)
        
        # 状态指示灯（用颜色块或图标代替）
        self.indicator = QLabel(self)
        self.indicator.setFixedSize(10, 10)
        self.indicator.setStyleSheet("background-color: #00FF00; border-radius: 5px;")
        
        # 状态文本
        self.label = QLabel("就绪", self)
        self.label.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        
        self.layout.addWidget(self.indicator)
        self.layout.addWidget(self.label)
        self.layout.addStretch()
        
        # 动画定时器
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_dots = 0
        self.base_text = ""
        self.is_animating = False
        
        # 颜色配置
        self.colors = {
            self.STATUS_READY: "#00FF00",    # 绿色
            self.STATUS_INFO: "#3498db",     # 蓝色
            self.STATUS_SUCCESS: "#2ecc71",  # 绿色
            self.STATUS_WARNING: "#f1c40f",  # 黄色
            self.STATUS_ERROR: "#e74c3c",    # 红色
            self.STATUS_WORKING: "#9b59b6"   # 紫色
        }

    def set_status(self, text, status_type=STATUS_INFO):
        """
        设置状态
        Args:
            text: 显示文本
            status_type: 状态类型 (ready, info, success, warning, error, working)
        """
        self.base_text = text
        self.label.setText(text)
        
        # 设置指示器颜色
        color = self.colors.get(status_type, "#FFFFFF")
        self.indicator.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self.label.setStyleSheet(f"color: {color}; font-size: 12px;")
        
        # 处理动画
        if status_type == self.STATUS_WORKING:
            if not self.is_animating:
                self.is_animating = True
                self.animation_dots = 0
                self.animation_timer.start(500) # 500ms 更新一次
        else:
            if self.is_animating:
                self.is_animating = False
                self.animation_timer.stop()
                self.label.setText(text) # 恢复无省略号文本

    def _update_animation(self):
        """更新省略号动画"""
        self.animation_dots = (self.animation_dots + 1) % 4
        dots = "." * self.animation_dots
        self.label.setText(f"{self.base_text}{dots}")
