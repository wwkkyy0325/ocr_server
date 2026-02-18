# -*- coding: utf-8 -*-

"""
界面布局文件（如Qt Designer生成）
"""

try:
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                QPushButton, QLabel, QTextEdit, QFileDialog, 
                                QListWidget, QGroupBox, QComboBox, QCheckBox,
                                QApplication, QAction, QMenuBar, QMenu, QTabWidget, QSpinBox,
                                QToolBar, QDockWidget, QSplitter, QStackedWidget)
    from PyQt5.QtCore import Qt, QSize
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, UI will not be available")


class Ui_MainWindow:
    def __init__(self):
        """
        初始化界面布局
        """
        self.central_widget = None # Keeping for compatibility if needed, though mostly unused in Dock layout
        self.start_button = None
        self.stop_button = None
        self.settings_action = None
        self.image_list = None
        self.result_display = None
        self.text_block_list = None
        self.result_tabs = None
        self.card_sort_widget = None
        self.card_cols_spin = None
        self.status_label = None
        # self.model_selector = None
        self.preprocessing_chk = None
        self.padding_chk = None
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
        self.mask_combo = None
        self.table_split_chk = None
        self.table_split_combo = None
        self.table_mode_combo = None
        self.ai_table_chk = None
        self.ai_table_model_combo = None
        self.ai_advanced_doc_chk = None
        
        # Docks
        self.dock_project = None
        self.dock_settings = None
        self.main_toolbar = None

    def setup_ui(self, main_window):
        """
        设置界面布局
        """
        if not PYQT_AVAILABLE:
            print("Cannot setup UI: PyQt5 not available")
            return
            
        print("Setting up UI for main window (Modern Layout)")
        
        # 设置主窗口属性
        if main_window:
            main_window.setWindowTitle("OCR日期识别系统")
            main_window.resize(1800, 1000)
            
            # 创建菜单栏
            self._create_menu_bar(main_window)
            
            # --- 1. 工具栏 (Toolbar) ---
            self.main_toolbar = QToolBar("主工具栏")
            self.main_toolbar.setIconSize(QSize(24, 24))
            self.main_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.main_toolbar.setMovable(False)
            main_window.addToolBar(Qt.TopToolBarArea, self.main_toolbar)
            
            # Buttons moved to bottom right
            
            # --- 2. 左侧：资源管理器 (Dock) ---
            self.dock_project = QDockWidget("资源管理器", main_window)
            self.dock_project.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.dock_project.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            
            project_widget = QWidget()
            project_layout = QVBoxLayout(project_widget)
            project_layout.setContentsMargins(5, 5, 5, 5)
            
            # 文件夹/文件
            folder_group = QGroupBox("图像来源")
            folder_layout = QVBoxLayout(folder_group)
            folder_btns = QHBoxLayout()
            self.folder_add_btn = QPushButton("添加文件夹")
            self.file_add_btn = QPushButton("添加文件")
            self.folder_remove_btn = QPushButton("移除")
            self.folder_clear_btn = QPushButton("清空")
            folder_btns.addWidget(self.folder_add_btn)
            folder_btns.addWidget(self.file_add_btn)
            folder_btns.addWidget(self.folder_remove_btn)
            folder_btns.addWidget(self.folder_clear_btn)
            self.folder_list = QListWidget()
            folder_layout.addLayout(folder_btns)
            folder_layout.addWidget(self.folder_list)
            
            # 图像
            image_group = QGroupBox("图像文件")
            image_layout = QVBoxLayout(image_group)
            self.image_list = QListWidget()
            image_layout.addWidget(self.image_list)
            
            project_layout.addWidget(folder_group, 1)
            project_layout.addWidget(image_group, 2)
            
            self.dock_project.setWidget(project_widget)
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.dock_project)
            
            # --- 3. 右侧：参数配置 (Dock) ---
            self.dock_settings = QDockWidget("参数配置", main_window)
            self.dock_settings.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.dock_settings.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            
            settings_widget = QWidget()
            settings_layout = QVBoxLayout(settings_widget)
            settings_layout.setContentsMargins(5, 5, 5, 5)
            
            # 蒙版设置
            mask_group = QGroupBox("蒙版设置")
            mask_layout = QVBoxLayout(mask_group)
            
            mask_row1 = QHBoxLayout()
            self.mask_chk_use = QCheckBox("启用蒙版裁剪")
            self.mask_btn_enable = QPushButton("绘制模式")
            self.mask_btn_enable.setCheckable(True)
            self.mask_btn_apply = QPushButton("应用")
            mask_row1.addWidget(self.mask_chk_use)
            mask_row1.addWidget(self.mask_btn_enable)
            mask_row1.addWidget(self.mask_btn_apply)
            
            mask_row2 = QHBoxLayout()
            self.mask_btn_clear = QPushButton("清除")
            self.mask_btn_save = QPushButton("保存")
            self.mask_btn_rename = QPushButton("重命名")
            self.mask_btn_delete = QPushButton("删除")
            self.mask_btn_export = QPushButton("导出")
            
            # Use Grid for compact buttons
            from PyQt5.QtWidgets import QGridLayout
            mask_grid = QGridLayout()
            mask_grid.addWidget(self.mask_btn_clear, 0, 0)
            mask_grid.addWidget(self.mask_btn_save, 0, 1)
            mask_grid.addWidget(self.mask_btn_rename, 1, 0)
            mask_grid.addWidget(self.mask_btn_delete, 1, 1)
            mask_grid.addWidget(self.mask_btn_export, 2, 0, 1, 2)
            
            mask_layout.addLayout(mask_row1)
            mask_layout.addLayout(mask_grid)
            
            processing_group = QGroupBox("处理设置")
            processing_layout = QVBoxLayout(processing_group)
            self.preprocessing_chk = QCheckBox("启用预处理")
            self.preprocessing_chk.setToolTip("对图像进行对比度增强和降噪处理，可提高文字识别准确率")
            self.padding_chk = QCheckBox("启用边缘补全 (Padding)")
            self.padding_chk.setToolTip("当图片边缘内容识别不全时启用，会在识别前给图片四周增加白边")
            processing_layout.addWidget(self.preprocessing_chk)
            processing_layout.addWidget(self.padding_chk)
            
            table_group = QGroupBox("表格识别")
            table_layout = QVBoxLayout(table_group)

            mode_row = QHBoxLayout()
            mode_label = QLabel("表格模式:")
            self.table_mode_combo = QComboBox()
            self.table_mode_combo.addItems(["关闭", "传统表格拆分", "AI 表格结构识别"])
            mode_row.addWidget(mode_label)
            mode_row.addWidget(self.table_mode_combo)
            table_layout.addLayout(mode_row)
            
            ai_table_label = QLabel("AI模型:")
            self.ai_table_model_combo = QComboBox()
            self.ai_table_model_combo.addItems(["SLANet (中文)", "SLANet (英文)"])
            self.ai_table_model_combo.setEnabled(False)
            table_layout.addWidget(ai_table_label)
            table_layout.addWidget(self.ai_table_model_combo)

            self.ai_advanced_doc_chk = QCheckBox("启用高级文档理解（公式/图表）")
            self.ai_advanced_doc_chk.setToolTip("在启用 AI 表格结构识别的基础上，额外开启公式识别与图表转表格等高级文档理解子模块，可能会进一步增加初始化与推理耗时。")
            self.ai_advanced_doc_chk.setEnabled(False)
            table_layout.addWidget(self.ai_advanced_doc_chk)

            settings_layout.addWidget(mask_group)
            settings_layout.addWidget(processing_group)
            settings_layout.addWidget(table_group)
            settings_layout.addStretch()
            
            self.dock_settings.setWidget(settings_widget)
            # Move settings dock to LeftDockWidgetArea to be next to project dock
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.dock_settings)
            # Tabify them so they share the same space initially, or just stack them?
            # User said "next to resource manager", could mean tabbed or stacked vertically.
            # Let's stack them vertically on the left.
            main_window.splitDockWidget(self.dock_project, self.dock_settings, Qt.Vertical)

            # --- 4. 中间区域 (Splitter only, no bottom bar) ---
            central_container = QWidget()
            central_layout = QVBoxLayout(central_container)
            central_layout.setContentsMargins(0, 0, 0, 0)
            central_layout.setSpacing(0)
            
            self.central_splitter = QSplitter(Qt.Horizontal)
            central_layout.addWidget(self.central_splitter)
            
            # --- Bottom Area: Start/Stop Buttons ---
            bottom_buttons_layout = QHBoxLayout()
            bottom_buttons_layout.setContentsMargins(10, 10, 10, 10)
            bottom_buttons_layout.addStretch() # Push buttons to center or right? Let's center them or keep right like toolbar?
            # User didn't specify alignment, but usually bottom center or right is good. 
            # Previous toolbar had them on left/center depending on implementation.
            # Let's put them in the center for visibility.
            
            self.start_button = QPushButton("开始处理")
            self.start_button.setCursor(Qt.PointingHandCursor)
            self.start_button.setStyleSheet("""
                QPushButton { 
                    font-weight: bold; 
                    font-size: 14px; 
                    padding: 8px 30px; 
                    background-color: #4CAF50; 
                    color: white; 
                    border-radius: 4px; 
                } 
                QPushButton:hover { 
                    background-color: #45a049; 
                }
            """)
            
            self.stop_button = QPushButton("停止处理")
            self.stop_button.setCursor(Qt.PointingHandCursor)
            self.stop_button.setStyleSheet("""
                QPushButton { 
                    font-weight: bold; 
                    font-size: 14px; 
                    padding: 8px 30px; 
                    background-color: #f44336; 
                    color: white; 
                    border-radius: 4px; 
                } 
                QPushButton:hover { 
                    background-color: #d32f2f; 
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            self.stop_button.setEnabled(False)
            
            bottom_buttons_layout.addWidget(self.start_button)
            bottom_buttons_layout.addSpacing(20)
            bottom_buttons_layout.addWidget(self.stop_button)
            bottom_buttons_layout.addStretch()
            
            central_layout.addLayout(bottom_buttons_layout)
            
            main_window.setCentralWidget(central_container)
            
            # 图像查看器
            try:
                from app.ui.widgets.image_viewer import ImageViewer
                self.image_viewer = ImageViewer()
                self.central_splitter.addWidget(self.image_viewer)
            except Exception as e:
                print(f"Failed to initialize ImageViewer: {e}")
                import traceback
                traceback.print_exc()
                lbl = QLabel(f"Image Viewer Error: {e}")
                lbl.setAlignment(Qt.AlignCenter)
                self.central_splitter.addWidget(lbl)
                self.image_viewer = None
            
            # 结果展示区容器
            result_container = QWidget()
            result_layout = QVBoxLayout(result_container)
            result_layout.setContentsMargins(0, 0, 0, 0)
            result_layout.setSpacing(5)

            if PYQT_AVAILABLE:
                try:
                    from app.ui.widgets.text_block_list import TextBlockListWidget
                    self.text_block_list = TextBlockListWidget()
                except ImportError as e:
                    self.text_block_list = None
                    print(f"TextBlockListWidget not available: {e}")
            
            if PYQT_AVAILABLE:
                try:
                    from app.ui.widgets.result_table_widget import ResultTableWidget
                    self.result_table = ResultTableWidget()
                except ImportError as e:
                    self.result_table = None
                    print(f"ResultTableWidget not available: {e}")

            self.struct_view_stack = QStackedWidget()
            if self.text_block_list:
                self.struct_view_stack.addWidget(self.text_block_list)
            if self.result_table:
                self.struct_view_stack.addWidget(self.result_table)

            self.result_display = QTextEdit()

            result_layout.addWidget(self.struct_view_stack)
            result_layout.addWidget(self.result_display)

            result_layout.setStretch(0, 2)
            result_layout.setStretch(1, 1)

            self.central_splitter.addWidget(result_container)

            # 设置比例 (3:1) - 图像占用更多空间，保持与原来一致
            self.central_splitter.setStretchFactor(0, 3)
            self.central_splitter.setStretchFactor(1, 1)
            
            # --- 5. 状态栏 ---
            self.status_label = QLabel("就绪")
            self.status_label.setStyleSheet("padding: 0 10px;")
            main_window.statusBar().addWidget(self.status_label)
            
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
        self.settings_action.setShortcut("Ctrl+S")
        file_menu.addAction(self.settings_action)
        
        file_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction("退出", main_window)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(main_window.close)
        file_menu.addAction(exit_action)

        # 视图菜单已移除，因为面板默认嵌入且无需单独切换
        # view_menu = QMenu("视图", main_window)
        # menu_bar.addMenu(view_menu)
        
        # if hasattr(self, 'dock_project') and self.dock_project:
        #     view_menu.addAction(self.dock_project.toggleViewAction())
        
        # if hasattr(self, 'dock_settings') and self.dock_settings:
        #     view_menu.addAction(self.dock_settings.toggleViewAction())

        # 数据库菜单
        db_menu = QMenu("数据库", main_window)
        menu_bar.addMenu(db_menu)

        # 1. 数据库管理
        self.db_manager_action = QAction("数据库管理 (导入/删除)", main_window)
        self.db_manager_action.setShortcut("Ctrl+M")
        db_menu.addAction(self.db_manager_action)
        
        # 2. 可视化绑定
        self.field_binding_action = QAction("可视化绑定", main_window)
        self.field_binding_action.setShortcut("Ctrl+B")
        db_menu.addAction(self.field_binding_action)
        
        # 3. 数据库查询
        self.query_db_action = QAction("数据库查询", main_window)
        self.query_db_action.setShortcut("Ctrl+F")
        db_menu.addAction(self.query_db_action)
        
        # Deprecated
        self.import_db_action = None
