# -*- coding: utf-8 -*-

"""
界面布局文件（如Qt Designer生成）
"""

try:
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QPushButton, QLabel, QTextEdit, QFileDialog,
                                 QListWidget, QGroupBox, QComboBox, QCheckBox,
                                 QApplication, QAction, QMenuBar, QMenu, QTabWidget, QSpinBox,
                                 QToolBar, QDockWidget, QSplitter, QStackedWidget,
                                 QRadioButton, QButtonGroup)
    from PyQt5.QtCore import Qt, QSize
    from app.ui.styles.glass_components import GlassTitleBar
    from app.log.log_bus import get_logger

    PYQT_AVAILABLE = True
    logger = get_logger()
except ImportError:
    PYQT_AVAILABLE = False
    # 定义占位符类，防止 PyQt5 不可用时出错
    QMainWindow = None
    QWidget = None
    QVBoxLayout = None
    QHBoxLayout = None
    QPushButton = None
    QLabel = None
    QTextEdit = None
    QFileDialog = None
    QListWidget = None
    QGroupBox = None
    QComboBox = None
    QCheckBox = None
    QApplication = None
    QAction = None
    QMenuBar = None
    QMenu = None
    QTabWidget = None
    QSpinBox = None
    QToolBar = None
    QDockWidget = None
    QSplitter = None
    QStackedWidget = None
    QRadioButton = None
    QButtonGroup = None
    Qt = None
    QSize = None
    GlassTitleBar = None
    logger = None


    def get_logger():
        return None


class Ui_MainWindow:
    def __init__(self):
        """
        初始化界面布局
        """
        self.central_widget = None  # Keeping for compatibility if needed, though mostly unused in Dock layout
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
        # 蒙版相关控件已移除
        self.image_viewer = None

        # Docks
        self.dock_project = None
        self.dock_settings = None
        self.main_toolbar = None
        self.menu_bar = None
        self.title_bar = None
        self.window_min_button = None
        self.window_max_button = None
        self.window_close_button = None

    def setup_ui(self, main_window):
        """
        设置界面布局
        """
        if not PYQT_AVAILABLE:
            if logger:
                logger.error("ui_mainwindow", "setup_failed", "Cannot setup UI: PyQt5 not available")
            return

        if logger:
            logger.info("ui_mainwindow", "setup_start", "Setting up UI for main window (Modern Layout)")

        # 设置主窗口属性
        if main_window:
            main_window.setWindowTitle("OCR日期识别系统")
            main_window.resize(1800, 1000)

            # 创建菜单栏和自定义顶部栏（主题切换移动到菜单栏区域）
            self._create_menu_bar(main_window)

            # Buttons moved to bottom right

            # --- 2. 左侧：资源组件（目录 + 文件） ---
            project_widget = QWidget()
            project_layout = QVBoxLayout(project_widget)
            project_layout.setContentsMargins(5, 5, 5, 5)

            resource_group = QGroupBox("资源")
            resource_layout = QVBoxLayout(resource_group)
            folder_btns = QHBoxLayout()
            self.folder_add_btn = QPushButton("添加文件夹")
            self.file_add_btn = QPushButton("添加文件")
            self.folder_remove_btn = QPushButton("移除")
            self.folder_clear_btn = QPushButton("清空")
            folder_btns.addWidget(self.folder_add_btn)
            folder_btns.addWidget(self.file_add_btn)
            folder_btns.addWidget(self.folder_remove_btn)
            folder_btns.addWidget(self.folder_clear_btn)
            resource_layout.addLayout(folder_btns)

            lists_row = QHBoxLayout()
            lists_row.setSpacing(6)

            folder_col = QVBoxLayout()
            folder_label = QLabel("目录")
            self.folder_list = QListWidget()
            folder_col.addWidget(folder_label)
            folder_col.addWidget(self.folder_list)

            image_col = QVBoxLayout()
            image_label = QLabel("文件")
            self.image_list = QListWidget()
            image_col.addWidget(image_label)
            image_col.addWidget(self.image_list)

            lists_row.addLayout(folder_col, 1)
            lists_row.addLayout(image_col, 1)
            resource_layout.addLayout(lists_row)

            project_layout.addWidget(resource_group, 2)

            # --- 4. 中间区域（左资源/仪表盘 + 中央图像/结果） ---
            central_container = QWidget()
            central_layout = QVBoxLayout(central_container)
            central_layout.setContentsMargins(8, 8, 8, 8)
            central_layout.setSpacing(4)

            main_row_layout = QHBoxLayout()
            main_row_layout.setContentsMargins(0, 0, 0, 0)
            main_row_layout.setSpacing(8)

            self.central_splitter = QSplitter(Qt.Horizontal)
            main_row_layout.addWidget(project_widget, 1)
            main_row_layout.addWidget(self.central_splitter, 4)

            # --- Bottom Area: Start/Stop Buttons ---
            bottom_buttons_layout = QHBoxLayout()
            bottom_buttons_layout.setContentsMargins(10, 10, 10, 10)
            bottom_buttons_layout.addStretch()

            self.start_button = QPushButton("开始处理")
            self.start_button.setObjectName("primaryStartButton")
            self.start_button.setCursor(Qt.PointingHandCursor)

            self.stop_button = QPushButton("停止处理")
            self.stop_button.setObjectName("primaryStopButton")
            self.stop_button.setCursor(Qt.PointingHandCursor)
            self.stop_button.setEnabled(False)

            bottom_buttons_layout.addWidget(self.start_button)
            bottom_buttons_layout.addSpacing(20)
            bottom_buttons_layout.addWidget(self.stop_button)
            bottom_buttons_layout.addStretch()

            central_layout.addLayout(main_row_layout)
            central_layout.addLayout(bottom_buttons_layout)

            main_window.setCentralWidget(central_container)

            # 图像查看器
            try:
                from app.ui.widgets.image_viewer import ImageViewer
                self.image_viewer = ImageViewer()
                self.image_viewer.setObjectName("imageViewerPanel")
                self.central_splitter.addWidget(self.image_viewer)
            except Exception as e:
                error_msg = f"Failed to initialize ImageViewer: {e}"
                if logger:
                    logger.error("ui_mainwindow", "image_viewer_init_failed", error_msg)
                import traceback
                if logger:
                    logger.debug("ui_mainwindow", "traceback", traceback.format_exc())
                lbl = QLabel(f"Image Viewer Error: {e}")
                lbl.setAlignment(Qt.AlignCenter)
                self.central_splitter.addWidget(lbl)
                self.image_viewer = None

            # 结果展示区容器
            result_container = QWidget()
            result_layout = QVBoxLayout(result_container)
            result_layout.setContentsMargins(0, 0, 0, 0)
            result_layout.setSpacing(5)

            self.text_block_list = None
            self.result_table = None

            # 延迟导入以避免循环依赖和满足类型检查
            TextBlockListWidget = None
            ResultTableWidget = None

            if PYQT_AVAILABLE:
                try:
                    from app.ui.widgets.text_block_list import TextBlockListWidget
                    self.text_block_list = TextBlockListWidget()
                    if hasattr(self.text_block_list, 'setObjectName'):
                        self.text_block_list.setObjectName("textResultList")
                except ImportError as e:
                    self.text_block_list = None
                    error_msg = f"TextBlockListWidget not available: {e}"
                    if logger:
                        logger.error("ui_mainwindow", "text_block_list_import_failed", error_msg)

                try:
                    from app.ui.widgets.result_table_widget import ResultTableWidget
                    self.result_table = ResultTableWidget()
                except ImportError as e:
                    self.result_table = None
                    error_msg = f"ResultTableWidget not available: {e}"
                    if logger:
                        logger.error("ui_mainwindow", "result_table_import_failed", error_msg)

            self.struct_view_stack = QStackedWidget()
            if self.text_block_list:
                self.struct_view_stack.addWidget(self.text_block_list)
            if self.result_table:
                self.struct_view_stack.addWidget(self.result_table)

            self.result_display = QTextEdit()
            self.result_display.setObjectName("rawTextResult")

            result_layout.addWidget(self.struct_view_stack)
            result_layout.addWidget(self.result_display)

            result_layout.setStretch(0, 2)
            result_layout.setStretch(1, 1)

            self.central_splitter.addWidget(result_container)

            # 设置比例 (3:1) - 图像占用更多空间，保持与原来一致
            self.central_splitter.setStretchFactor(0, 3)
            self.central_splitter.setStretchFactor(1, 1)

            # --- 5. 状态栏 ---
            # self.status_label = QLabel("就绪")
            # self.status_label.setStyleSheet("padding: 0 10px;")
            # main_window.statusBar().addWidget(self.status_label)

            try:
                from app.ui.widgets.status_bar import DynamicStatusBar
                self.status_bar = DynamicStatusBar(main_window)
                main_window.statusBar().addWidget(self.status_bar)
                if logger:
                    logger.debug("ui_mainwindow", "status_bar_initialized", "DynamicStatusBar initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize status bar: {e}"
                if logger:
                    logger.error("ui_mainwindow", "status_bar_init_failed", error_msg)
                import traceback
                if logger:
                    logger.debug("ui_mainwindow", "traceback", traceback.format_exc())
                self.status_bar = None

    def _create_menu_bar(self, main_window):
        """
        创建菜单栏
        
        Args:
            main_window: 主窗口对象
        """
        if not PYQT_AVAILABLE:
            return

        menu_bar = QMenuBar()
        self.menu_bar = menu_bar

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if GlassTitleBar is not None and main_window is not None:
            try:
                title_bar = GlassTitleBar("OCR 日期识别系统", main_window)
                self.title_bar = title_bar
                if logger:
                    logger.debug("ui_mainwindow", "glass_title_bar_initialized",
                                 "GlassTitleBar initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize GlassTitleBar: {e}"
                if logger:
                    logger.error("ui_mainwindow", "glass_title_bar_init_failed", error_msg)
                import traceback
                if logger:
                    logger.debug("ui_mainwindow", "traceback", traceback.format_exc())
                title_bar = QWidget()
                self.title_bar = title_bar
        else:
            title_bar = QWidget()
            self.title_bar = title_bar
            title_layout = QHBoxLayout(title_bar)
            title_layout.setContentsMargins(10, 4, 10, 4)
            title_layout.setSpacing(6)
            title_label = QLabel("OCR日期识别系统")
            title_label.setObjectName("titleLabel")
            title_layout.addWidget(title_label)
            title_layout.addStretch()

        layout.addWidget(title_bar)
        layout.addWidget(menu_bar)

        # 在菜单栏右侧放置主题/背景切换（现代简洁风格）
        theme_selector_container = QWidget()
        theme_layout = QHBoxLayout(theme_selector_container)
        theme_layout.setContentsMargins(8, 0, 8, 0)
        theme_layout.setSpacing(6)
        theme_label = QLabel("主题")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["霓虹", "紫域", "炽橙", "经典暗色", "简约黑白"])
        bg_label = QLabel("背景")
        self.background_combo = QComboBox()
        self.background_combo.addItems(["清透玻璃", "波点", "磨砂玻璃"])
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addSpacing(10)
        theme_layout.addWidget(bg_label)
        theme_layout.addWidget(self.background_combo)
        menu_bar.setCornerWidget(theme_selector_container, Qt.TopRightCorner)

        main_window.setMenuWidget(container)

        # 文件菜单
        file_menu = QMenu("文件", main_window)
        menu_bar.addMenu(file_menu)

        # 退出动作
        exit_action = QAction("退出", main_window)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(main_window.close)
        file_menu.addAction(exit_action)

        # 设置菜单项 (直接放在顶级菜单栏)
        self.settings_action = QAction("设置", main_window)
        self.settings_action.setShortcut("Ctrl+S")
        menu_bar.addAction(self.settings_action)
