# Path: src/app/ui/ui_mainwindow.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
界面布局文件（如Qt Designer生成）
"""

try:
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                QPushButton, QLabel, QTextEdit, QFileDialog, 
                                QProgressBar, QListWidget, QGroupBox, QComboBox,
                                QApplication, QAction, QMenuBar, QMenu)
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, UI will not be available")


class Ui_MainWindow:
    def __init__(self):
        """
        初始化界面布局
        """
        self.central_widget = None
        self.input_button = None
        self.output_button = None
        self.start_button = None
        self.stop_button = None
        self.settings_action = None
        self.progress_bar = None
        self.image_list = None
        self.result_display = None
        self.status_label = None
        self.model_selector = None

    def setup_ui(self, main_window):
        """
        设置界面布局

        Args:
            main_window: 主窗口对象
        """
        if not PYQT_AVAILABLE:
            print("Cannot setup UI: PyQt5 not available")
            return
            
        print("Setting up UI for main window")
        
        # 设置主窗口属性
        if main_window:
            main_window.setWindowTitle("OCR日期识别系统")
            main_window.resize(1000, 700)
            
            # 创建菜单栏
            self._create_menu_bar(main_window)
            
            # 创建中央部件
            self.central_widget = QWidget(main_window)
            main_window.setCentralWidget(self.central_widget)
            
            # 创建主布局
            main_layout = QVBoxLayout(self.central_widget)
            
            # 创建顶部控制区域
            control_group = QGroupBox("控制面板")
            control_layout = QHBoxLayout(control_group)
            
            self.input_button = QPushButton("选择输入目录")
            self.output_button = QPushButton("选择输出目录")
            self.start_button = QPushButton("开始处理")
            self.stop_button = QPushButton("停止处理")
            self.stop_button.setEnabled(False)
            
            control_layout.addWidget(self.input_button)
            control_layout.addWidget(self.output_button)
            control_layout.addWidget(self.start_button)
            control_layout.addWidget(self.stop_button)
            
            # 创建模型选择区域
            model_layout = QHBoxLayout()
            model_label = QLabel("选择模型:")
            self.model_selector = QComboBox()
            self.model_selector.addItems(["默认模型", "高精度模型", "快速模型"])
            model_layout.addWidget(model_label)
            model_layout.addWidget(self.model_selector)
            
            # 创建进度条
            self.progress_bar = QProgressBar()
            self.progress_bar.setValue(0)
            
            # 创建状态标签
            self.status_label = QLabel("就绪")
            self.status_label.setAlignment(Qt.AlignCenter)
            
            # 创建中间内容区域
            content_layout = QHBoxLayout()
            
            # 左侧图像列表
            image_group = QGroupBox("图像列表")
            image_layout = QVBoxLayout(image_group)
            self.image_list = QListWidget()
            image_layout.addWidget(self.image_list)
            
            # 右侧结果展示
            result_group = QGroupBox("识别结果")
            result_layout = QVBoxLayout(result_group)
            self.result_display = QTextEdit()
            self.result_display.setReadOnly(True)
            result_layout.addWidget(self.result_display)
            
            content_layout.addWidget(image_group, 1)
            content_layout.addWidget(result_group, 2)
            
            # 添加所有组件到主布局
            main_layout.addWidget(control_group)
            main_layout.addLayout(model_layout)
            main_layout.addWidget(self.progress_bar)
            main_layout.addLayout(content_layout)
            main_layout.addWidget(self.status_label)
            
    def _create_menu_bar(self, main_window):
        """
        创建菜单栏
        
        Args:
            main_window: 主窗口对象
        """
        if not PYQT_AVAILABLE:
            return
            
        menu_bar = QMenuBar(main_window)
        main_window.setMenuBar(menu_bar)
        
        # 文件菜单
        file_menu = QMenu("文件", main_window)
        menu_bar.addMenu(file_menu)
        
        # 设置动作
        self.settings_action = QAction("设置", main_window)
        self.settings_action.setShortcut("Ctrl+,")
        file_menu.addAction(self.settings_action)
        
        # 添加分隔符和退出动作
        file_menu.addSeparator()
        exit_action = QAction("退出", main_window)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(main_window.close)
        file_menu.addAction(exit_action)
