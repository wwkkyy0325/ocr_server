# -*- coding: utf-8 -*-

"""
界面布局文件（如Qt Designer生成）
"""

try:
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                QPushButton, QLabel, QTextEdit, QFileDialog, 
                                QListWidget, QGroupBox, QComboBox, QCheckBox,
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
        self.image_list = None
        self.result_display = None
        self.status_label = None
        self.model_selector = None
        self.mask_chk_use = None
        self.mask_btn_enable = None
        self.mask_btn_save = None
        self.mask_btn_clear = None
        self.mask_btn_apply = None
        self.mask_btn_bind = None
        self.mask_btn_rename = None
        self.mask_btn_delete = None
        self.mask_btn_export = None
        self.image_viewer = None
        self.mask_combo = None  # 添加缺失的mask_combo属性

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
            main_window.resize(1000, 800)
            
            # 创建菜单栏
            self._create_menu_bar(main_window)
            
            # 创建中央部件
            self.central_widget = QWidget(main_window)
            main_window.setCentralWidget(self.central_widget)
            
            # 创建主布局
            main_layout = QVBoxLayout(self.central_widget)
            
            # 1. 顶部控制区域
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
            
            # 2. 蒙版管理区域
            mask_group = QGroupBox("蒙版管理")
            mask_layout = QVBoxLayout(mask_group)
            
            # 第一行：蒙版选择与绘制开关
            mask_row1 = QHBoxLayout()
            self.mask_chk_use = QCheckBox("启用蒙版裁剪")
            self.mask_btn_enable = QPushButton("开启绘制模式")
            self.mask_btn_enable.setCheckable(True)
            self.mask_btn_clear = QPushButton("清除绘制")
            
            self.mask_btn_apply = QPushButton("应用蒙版")
            self.mask_btn_bind = QPushButton("绑定到当前图")
            
            # 添加模板显示标签
            self.current_mask_label = QLabel("当前模板: 无")
            self.current_mask_label.setStyleSheet("background-color: #f0f0f0; padding: 3px; border: 1px solid #ccc; border-radius: 3px;")
            self.current_mask_label.setMaximumHeight(30)
            
            mask_row1.addWidget(self.mask_chk_use)
            mask_row1.addWidget(self.mask_btn_enable)
            mask_row1.addWidget(self.mask_btn_clear)
            mask_row1.addStretch()
            mask_row1.addWidget(self.mask_btn_apply)
            mask_row1.addWidget(self.mask_btn_bind)
            mask_row1.addWidget(self.current_mask_label)
            
            # 第二行：蒙版操作
            mask_row2 = QHBoxLayout()
            self.mask_btn_save = QPushButton("保存新蒙版")
            self.mask_btn_rename = QPushButton("重命名")
            self.mask_btn_delete = QPushButton("删除")
            self.mask_btn_export = QPushButton("导出配置")
            
            mask_row2.addWidget(self.mask_btn_save)
            mask_row2.addWidget(self.mask_btn_rename)
            mask_row2.addWidget(self.mask_btn_delete)
            mask_row2.addWidget(self.mask_btn_export)
            
            mask_layout.addLayout(mask_row1)
            mask_layout.addLayout(mask_row2)

            # 3. 模型选择区域
            model_layout = QHBoxLayout()
            model_label = QLabel("选择模型:")
            self.model_selector = QComboBox()
            self.model_selector.addItems(["默认模型", "高精度模型", "快速模型"])
            model_layout.addWidget(model_label)
            model_layout.addWidget(self.model_selector)
            
            # 4. 状态标签
            self.status_label = QLabel("就绪")
            self.status_label.setAlignment(Qt.AlignCenter)
            
            # 5. 中间内容区域
            content_layout = QHBoxLayout()
            
            # 左侧文件夹和图像列表
            left_layout = QVBoxLayout()
            
            # 文件夹管理区域
            folder_group = QGroupBox("文件夹管理")
            folder_layout = QVBoxLayout(folder_group)
            
            # 文件夹操作按钮
            folder_button_layout = QHBoxLayout()
            self.folder_add_btn = QPushButton("添加文件夹")
            self.folder_remove_btn = QPushButton("移除选中")
            self.folder_clear_btn = QPushButton("清空列表")
            
            folder_button_layout.addWidget(self.folder_add_btn)
            folder_button_layout.addWidget(self.folder_remove_btn)
            folder_button_layout.addWidget(self.folder_clear_btn)
            
            # 文件夹列表
            self.folder_list = QListWidget()
            
            folder_layout.addLayout(folder_button_layout)
            folder_layout.addWidget(self.folder_list)
            
            # 图像列表
            image_group = QGroupBox("图像列表")
            image_layout = QVBoxLayout(image_group)
            self.image_list = QListWidget()
            image_layout.addWidget(self.image_list)
            
            left_layout.addWidget(folder_group, 1)
            left_layout.addWidget(image_group, 2)
            
            # 右侧结果展示
            result_group = QGroupBox("识别结果")
            result_layout = QVBoxLayout(result_group)
            try:
                from app.ui.widgets.image_viewer import ImageViewer
                self.image_viewer = ImageViewer()
                result_layout.addWidget(self.image_viewer, 2)
            except Exception:
                pass
            self.result_display = QTextEdit()
            # 移除只读设置，允许用户编辑
            # self.result_display.setReadOnly(True)
            result_layout.addWidget(self.result_display, 1)
            
            content_layout.addLayout(left_layout, 1)
            content_layout.addWidget(result_group, 2)
            
            # 添加所有组件到主布局
            main_layout.addWidget(control_group)
            main_layout.addWidget(mask_group)
            main_layout.addLayout(model_layout)
            main_layout.addLayout(content_layout)
            main_layout.addWidget(self.status_label)
            
    def _on_mask_list_changed(self, current, previous):
        """模板列表选项变化时的处理"""
        if PYQT_AVAILABLE and hasattr(self, 'mask_combo') and current:
            current_text = current.text()
            print(f"Mask list selection changed to: {current_text}")
            
    def _on_mask_combo_changed(self, index):
        """下拉框选项变化时的处理（兼容性保留）"""
        if PYQT_AVAILABLE and hasattr(self, 'mask_combo'):
            current_text = self.mask_combo.currentText()
            print(f"Mask combo changed to: {current_text} (index: {index})")
            
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
