# -*- coding: utf-8 -*-

"""
识别进度条（尤其批量处理时）
"""

try:
    from PyQt5.QtWidgets import QProgressBar, QWidget, QVBoxLayout, QLabel
    from PyQt5.QtCore import Qt
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
