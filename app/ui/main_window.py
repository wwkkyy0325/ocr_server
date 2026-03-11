# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：应用主窗口与业务中枢，承载 UI 组装、信号/槽交互、批处理入口与状态管理
# - 核心实现：组合 ProcessManager/ProcessingController/ResultManager 等核心服务，驱动各类对话框与控件完成导入、识别、导出全流程
# - 关联关系：作为 UI 顶层协调者与 ConfigManager、OcrEngine/UnifiedOCREngine、各 Widgets/Dialog 紧密协作，负责把核心处理结果同步到界面

"""
主窗口（集成所有UI组件和交互逻辑）
"""

import os
import time
from app.core.process.process_manager import ProcessManager
from app.infrastructure.service_registry import ServiceRegistry
from app.infrastructure.env_manager import EnvManager
from app.core.process.processing_controller import ProcessingController
from app.log.log_bus import get_logger
try:
    from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QInputDialog, QListWidgetItem, \
        QListWidget, QDialog, QTabWidget, QApplication, QStyle, QCheckBox, \
        QProgressBar, QLabel, QProgressDialog, QMenuBar, QPushButton, QWidget, QHBoxLayout, QComboBox, QVBoxLayout
    from PyQt5.QtGui import QIcon, QPainter, QPen, QColor, QPainterPath, QRegion, QBrush, QRadialGradient, \
        QLinearGradient
    from PyQt5.QtCore import QTimer, Qt, QEvent, QFileSystemWatcher, QThread, pyqtSignal, QPoint
    from app.ui.widgets.progress_bar import CyberEnergyBar, AnnouncementBanner
    from app.loader.model_loader import ModelLoaderThread

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logger = get_logger()
    if logger:
        logger.error("main_window", "pyqt5_not_available", "PyQt5 not available, using console mode")

from app.ui.styles.glass_components import (
    register_config_manager
)
from app.ui.dialogs.glass_dialogs import GlassMessageDialog
from app.event.event_bus import get_event_bus
# 🔥 添加UI扩展管理器导入
from app.ui.ui_extension_manager import UIExtensionManager, UIComponentType

# Define Worker Thread
if PYQT_AVAILABLE:
    from app.ui.main_window_frame import CustomMainWindow
from app.config.config_manager import ConfigManager
from app.infrastructure.threading.task_queue import TaskManager
from app.core.result.result_manager import ResultManager
from app.infrastructure.file_utils import FileUtils
from app.infrastructure.performance import PerformanceMonitor
from app.core.process.ocr_service import OcrBatchService

# 注意：不在模块级别调用 get_logger()，因为此时 LoggerController 可能还未初始化
# 将在 __init__ 方法中通过参数注入或延迟获取

if PYQT_AVAILABLE:
    from PyQt5.QtCore import QObject
else:
    class QObject:
        pass


class MainWindow(QObject):
    if PYQT_AVAILABLE:
        file_processed_signal = pyqtSignal(str, str)
        processing_finished_signal = pyqtSignal()
        ocr_result_ready_signal = pyqtSignal(str)

    def __init__(self, config_manager=None, logger=None, performance_monitor=None):
        """
        初始化主窗口（仅GUI模式）
    
        Args:
            config_manager: 配置管理器（可选）
            logger: 日志记录器（可选）
            performance_monitor: 性能监控器（可选）
        """
        super().__init__()
        # 使用传入的 logger 或获取全局 logger
        self.logger = logger or get_logger()
        if not self.logger:
            # 如果 logger 仍然为 None，说明 LoggerController 未初始化，这是致命错误
            raise RuntimeError("LoggerController not initialized! Cannot create MainWindow without logger.")
        
        # 🔥 只支持GUI模式
        self.is_gui_mode = True
        
        self.logger.info("main_window", "initializing", "Initializing MainWindow")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.logger.debug("main_window", "project_root", f"Project root in MainWindow: {self.project_root}")

        self.build_flavor = EnvManager.get_build_flavor()

        if config_manager:
            self.config_manager = config_manager
        else:
            self.config_manager = ConfigManager(self.project_root)
            self.config_manager.load_config()
        register_config_manager(self.config_manager)

        # 启动时清理临时目录
        self._cleanup_temp_directory()

        # 🔥 初始化文件工具
        self.file_utils = FileUtils()

        # 启动时不再自动检查并下载模型，避免强制弹出下载对话框

        self.task_manager = TaskManager()
        self.result_manager = ResultManager()

        # 启用文件日志记录
        log_file = os.path.join(self.project_root, "logs", "ocr.log")
        self.logger.enable_file_logging(log_file)

        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.results_by_filename = {}
        self.results_json_by_filename = {}
        self.processing_thread = None
        self._stop_flag = False
        self.file_map = {}

        # Async model loader
        self.model_loader_thread = None
        self.loading_progress_bar = None
        self.loading_status_label = None
        self.global_loading_dialog = None

        # 新需求：集中化输出目录
        self.output_dir = os.path.join(self.project_root, "data", "outputs")
        os.makedirs(self.output_dir, exist_ok=True)

        # 初始化 OCR 组件（延迟加载模式，避免主进程加载模型）
        # 🔥 重构：OCR 引擎完全由 OCRPipeline 管理，UI 层不再直接持有

        # 延迟初始化 OCR 引擎 - UI 作为纯粹前端壳子
        # OCR 引擎将在首次处理任务时初始化
        self.logger.info("main_window", "ui_shell_initialized", "UI initialized as pure frontend shell - OCR engine will be initialized on demand")

        # 🔥 初始化UI扩展管理器
        from app.ui.ui_extension_manager import UIExtensionManager
        self.ui_extension_manager = UIExtensionManager(self)

        # Initialize ProcessManager
        self.process_manager = ProcessManager.get_instance(self.config_manager)
        self.process_manager.start_processes()

        # Initialize OCR Service: always use local batch service
        self.ocr_service = OcrBatchService(self)

        ServiceRegistry.register("ocr_batch", self.ocr_service)

        # 🔥 重构：ProcessingController 内部已创建 OCRPipeline
        self.processing_controller = ProcessingController(
            self.config_manager, self.file_utils,
            self.performance_monitor, self.result_manager, self.output_dir
        )

        if PYQT_AVAILABLE:
            bus = get_event_bus()
            self.processing_controller.update_status_signal.connect(bus.processing.status_updated)
            self.processing_controller.file_processed_signal.connect(bus.processing.file_processed)
            self.processing_controller.processing_finished_signal.connect(bus.processing.processing_finished)
            self.processing_controller.progress_update_signal.connect(bus.processing.progress_updated)
            self.processing_controller.processed_result_ready_signal.connect(bus.processing.processed_result_ready)
            bus.processing.status_updated.connect(self.update_status)
            bus.processing.file_processed.connect(self.on_file_processed)
            bus.processing.processing_finished.connect(self.on_processing_finished)

        # 注册 EventMonitor 到 TickScheduler (每秒报告一次)
        try:
            from app.scheduler.tick_scheduler import get_tick_scheduler
            from app.event.event_bus import get_event_monitor
            monitor = get_event_monitor()
            get_tick_scheduler().register_system("EventMonitor", monitor.report, every_ticks=20)  # 20 ticks ≈ 1 sec
        except Exception as e:
            self.logger.error("main_window", "event_monitor_register_failed", f"Failed to register EventMonitor: {e}")

        # 🔥 设置主窗口引用到PluginManager
        from app.api.plugin_manager import PluginManager
        plugin_manager = PluginManager()
        plugin_manager.set_main_window(self)
        
        # 根据模式初始化UI
        self.ui = None
        self.main_window = None
        self.announcement_banner = None
        from app.ui.styles.themes import THEME_DEFINITIONS
        self.theme_definitions = THEME_DEFINITIONS

        # 🔥 仅GUI模式下初始化UI组件
        if PYQT_AVAILABLE:
            try:
                from PyQt5.QtWidgets import QApplication
                from app.ui.ui_mainwindow import Ui_MainWindow

                # 确保QApplication已存在
                app = QApplication.instance()
                if app is None:  # 如果没有现有的实例，则创建新的
                    app = QApplication([])

                self.main_window = CustomMainWindow(self)
                self.ui = Ui_MainWindow()
                self.ui.setup_ui(self.main_window)
                theme_name = self.config_manager.get_setting('theme', 'classic')
                theme_index = 3
                if theme_name == 'cyber_neon':
                    theme_index = 0
                elif theme_name == 'cyber_purple':
                    theme_index = 1
                elif theme_name == 'cyber_orange':
                    theme_index = 2
                elif theme_name == 'minimalist':
                    theme_index = 4
                if hasattr(self.ui, 'theme_combo'):
                    self.ui.theme_combo.setCurrentIndex(theme_index)
                if hasattr(self.ui, 'background_combo'):
                    bg_style = self.config_manager.get_setting('glass_background', 'dots')
                    bg_index = 1
                    if bg_style == 'glass':
                        bg_index = 0
                    elif bg_style == 'dots':
                        bg_index = 1
                    elif bg_style == 'frosted':
                        bg_index = 2
                    self.ui.background_combo.setCurrentIndex(bg_index)
                try:
                    from PyQt5.QtWidgets import QAbstractItemView
                    self.ui.image_list.setAcceptDrops(True)
                    self.ui.image_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
                    self.ui.image_list.setContextMenuPolicy(Qt.CustomContextMenu)
                    self.ui.image_list.customContextMenuRequested.connect(self._show_file_list_context_menu)
                    self.ui.image_list.installEventFilter(self)

                    # Configure folder_list for drag & drop
                    self.ui.folder_list.setAcceptDrops(True)
                    self.ui.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
                    self.ui.folder_list.setContextMenuPolicy(Qt.CustomContextMenu)
                    self.ui.folder_list.customContextMenuRequested.connect(self._show_folder_list_context_menu)
                    self.ui.folder_list.installEventFilter(self)
                except Exception as e:
                    print(f"Error configuring image_list: {e}")
                    pass

                try:
                    self._apply_build_flavor_constraints()
                except Exception as e:
                    print(f"Error applying build flavor constraints: {e}")

                if hasattr(self.main_window, 'statusBar'):
                    try:
                        self.announcement_banner = AnnouncementBanner(self.main_window)
                        self.announcement_banner.set_announcement_text(
                            "软件是免费软件，如果付费获得请退款并联系 1074446976@qq.com"
                        )
                        self.main_window.statusBar().addPermanentWidget(self.announcement_banner)
                    except Exception as e:
                        print(f"Error setting announcement banner: {e}")

                # if hasattr(self.ui, 'padding_chk'):
                #     self.ui.padding_chk.setChecked(
                #         self.config_manager.get_setting('use_padding', True)
                #     )
                # if hasattr(self.ui, 'preprocessing_chk'):
                #     self.ui.preprocessing_chk.setChecked(
                #         self.config_manager.get_setting('use_preprocessing', True)
                #     )

                # Legacy actionSettings support moved to _connect_signals or ignored if not used

                self._connect_signals()
                # 设置延迟更新模板列表，确保 UI 完全初始化
                if PYQT_AVAILABLE:
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(100, self._delayed_ui_setup)

                theme_name = self.config_manager.get_setting('theme', 'cyber_neon')
                theme_def = self.theme_definitions.get(theme_name, self.theme_definitions['cyber_neon'])
                if isinstance(self.main_window, CustomMainWindow):
                    self.main_window.apply_theme(theme_name, theme_def)
                print("UI initialized successfully")
            except Exception as e:
                print(f"Error setting up UI: {e}")
                import traceback
                traceback.print_exc()
                self.ui = None
                self.main_window = None  # 确保UI组件被设为None

    def _cleanup_temp_directory(self):
        """清理临时目录 (temp)"""
        temp_dir = os.path.join(self.project_root, "temp")
        if os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                print(f"Failed to cleanup temp directory: {e}")

    def show(self):
        """显示主窗口"""
        if self.main_window:
            self.main_window.show()
            # 恢复之前的位置和大小
            self.main_window.restore_geometry()
            print("Main window shown")

            # 显示公告横幅
            if self.announcement_banner:
                self.announcement_banner.show()

            # 延迟初始化
            if PYQT_AVAILABLE:
                QTimer.singleShot(500, self._delayed_ui_setup)

            # 强制应用一次当前主题
            theme_idx = 0
            if hasattr(self.ui, 'theme_combo'):
                theme_idx = self.ui.theme_combo.currentIndex()
            self._on_theme_changed(theme_idx)

            # 强制应用一次当前背景
            bg_idx = 1
            if hasattr(self.ui, 'background_combo'):
                bg_idx = self.ui.background_combo.currentIndex()
            self._on_background_changed(bg_idx)

    def _delayed_ui_setup(self):
        """延迟执行的UI设置"""
        pass

    def _apply_build_flavor_constraints(self):
        if self.build_flavor != "normal":
            return
        if hasattr(self, "config_manager") and self.config_manager:
            self.config_manager.set_setting("use_ai_table", False)
            self.config_manager.set_setting("enable_advanced_doc", False)
            try:
                self.config_manager.save_config()
            except Exception as e:
                print(f"Error saving config for build flavor constraints: {e}")
        if not PYQT_AVAILABLE or not self.ui:
            return
        if hasattr(self.ui, "table_mode_ai_radio") and self.ui.table_mode_ai_radio:
            self.ui.table_mode_ai_radio.setEnabled(False)
            self.ui.table_mode_ai_radio.setToolTip("当前为普通版，AI 表格结构识别仅在 AI 版中提供。")
            if self.ui.table_mode_ai_radio.isChecked():
                self.ui.table_mode_ai_radio.setChecked(False)
                if hasattr(self.ui, "table_mode_off_radio") and self.ui.table_mode_off_radio:
                    self.ui.table_mode_off_radio.setChecked(True)
        if hasattr(self.ui, "ai_options_container") and self.ui.ai_options_container:
            self.ui.ai_options_container.setEnabled(False)
        if hasattr(self.ui, "ai_table_model_combo") and self.ui.ai_table_model_combo:
            self.ui.ai_table_model_combo.setEnabled(False)
        if hasattr(self.ui, "ai_advanced_doc_chk") and self.ui.ai_advanced_doc_chk:
            self.ui.ai_advanced_doc_chk.setChecked(False)
            self.ui.ai_advanced_doc_chk.setEnabled(False)

    def open_settings(self):
        """打开模型设置对话框"""
        self._open_settings_dialog(initial_tab_index=1)

    def _on_result_table_preferred_width(self, desired_width):
        if not PYQT_AVAILABLE or not self.ui:
            return
        splitter = getattr(self.ui, "central_splitter", None)
        if splitter is None:
            return
        total_width = splitter.size().width()
        if total_width <= 0:
            return
        min_left = max(int(total_width * 0.2), 200)
        right = max(desired_width, 100)
        if right > total_width - min_left:
            right = total_width - min_left
        left = total_width - right
        if left < min_left:
            left = min_left
            right = total_width - left
        splitter.setSizes([left, right])

    def update_status(self, text, status_type="working"):
        """
        更新状态栏状态（线程安全）
        """
        if not PYQT_AVAILABLE or not self.ui:
            print(f"Status: {text} ({status_type})")
            return

        if hasattr(self.ui, 'status_bar'):
            # 将 status_type 映射为 StatusBar 的常量
            status_code = self.ui.status_bar.STATUS_WORKING
            if status_type == "success":
                status_code = self.ui.status_bar.STATUS_SUCCESS
            elif status_type == "error":
                status_code = self.ui.status_bar.STATUS_ERROR
            elif status_type == "warning":
                status_code = self.ui.status_bar.STATUS_WARNING
            elif status_type == "ready":
                status_code = self.ui.status_bar.STATUS_READY

            self.ui.status_bar.set_status(text, status_code)
        else:
            # Fallback for console or simple UI
            print(f"Status: {text} ({status_type})")

    def _connect_signals(self):
        """
        连接 UI 信号 - 使用三层架构管理窗口控制按钮
        """
        print("Connecting UI signals")

        # ========== 窗口控制按钮：三层架构管理 ==========
        if self.ui and self.main_window and hasattr(self.ui, 'title_bar') and self.ui.title_bar:
            try:
                from app.ui.button_system import (
                    get_button_registry, 
                    WindowButtonId,
                    register_window_buttons
                )
                from app.ui.button_system.actions import WindowActionProvider
                
                registry = get_button_registry()
                registry.reset()  # 重置注册表
                
                # 第 1 层：从 GlassTitleBar 获取 UI组件
                title_bar = self.ui.title_bar
                ui_buttons = {
                    WindowButtonId.WINDOW_MINIMIZE: title_bar.btn_min,
                    WindowButtonId.WINDOW_MAXIMIZE: title_bar.btn_max,
                    WindowButtonId.WINDOW_CLOSE: title_bar.btn_close,
                }
                
                # 调试输出
                for btn_id, btn in ui_buttons.items():
                    if btn is None:
                        print(f"⚠️  警告：按钮 {btn_id.name} 为 None")
                    else:
                        print(f"✅ 按钮 {btn_id.name}: {type(btn).__name__}")
                
                # 第 3 层：使用动作提供者（纯业务逻辑）
                provider = WindowActionProvider(self.main_window)
                actions = {
                    WindowButtonId.WINDOW_MINIMIZE: provider.on_minimize,
                    WindowButtonId.WINDOW_MAXIMIZE: provider.on_maximize_toggle,
                    WindowButtonId.WINDOW_CLOSE: provider.on_close,
                }
                
                # 第 2 层：统一注册并连接
                count = register_window_buttons(ui_buttons, actions)
                print(f"Window control buttons connected: {count}/3")
                
                # 验证连接结果
                stats = registry.get_statistics()
                print(f"Registry stats: {stats}")
                
            except Exception as e:
                import traceback
                print(f"❌ 按钮系统初始化失败：{e}")
                print(traceback.format_exc())
                # 降级处理：直接连接
                if hasattr(self.ui, "window_min_button") and self.ui.window_min_button:
                    self.ui.window_min_button.clicked.connect(self.main_window.showMinimized)
                if hasattr(self.ui, "window_max_button") and self.ui.window_max_button:
                    self.ui.window_max_button.clicked.connect(self.main_window.showMaximized)
                if hasattr(self.ui, "window_close_button") and self.ui.window_close_button:
                    self.ui.window_close_button.clicked.connect(self.main_window.close)

        # ========== 其他按钮连接 ==========
        if self.ui and self.main_window:
            # 🔥 关键修复：确保 start_button 连接到正确的处理方法
            # 使用 lambda 丢弃 clicked 信号的参数，并确保调用文件夹批处理
            self.ui.start_button.clicked.connect(lambda: self._start_processing(folders_to_process=None, force_reprocess=False))
            
            # 🔥 添加调试输出确认按钮被点击
            def _on_start_clicked():
                print("[DEBUG] Start button clicked!")
                self._start_processing(folders_to_process=None, force_reprocess=False)
            
            # 重新连接以确保使用新方法
            try:
                self.ui.start_button.clicked.disconnect()
            except:
                pass
            self.ui.start_button.clicked.connect(_on_start_clicked)
            
            self.ui.stop_button.clicked.connect(self._stop_processing)
            if hasattr(self.ui, 'background_combo'):
                try:
                    self.ui.background_combo.currentIndexChanged.connect(self._on_background_changed)
                except Exception:
                    pass

            # 引入 ConfigBinder 简化设置同步
            try:
                from app.ui.utils.config_binder import ConfigBinder
                self.binder = ConfigBinder(self.config_manager)

                # 绑定 AI 表格设置
                if hasattr(self.ui, 'ai_table_chk'):
                    self.binder.bind_checkbox(self.ui.ai_table_chk, 'use_ai_table')

                # 引入 UIConstraintManager 处理复杂互斥逻辑
                try:
                    from app.ui.utils.ui_constraint_manager import UIConstraintManager
                    self.constraint_manager = UIConstraintManager(self.config_manager)

                except Exception as e:
                    print(f"Failed to init UIConstraintManager: {e}")

            except Exception as e:
                print(f"Failed to init ConfigBinder: {e}")

            # Folder management connections
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_add_btn'):
                self.ui.folder_add_btn.clicked.connect(self._add_folder)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'file_add_btn'):
                self.ui.file_add_btn.clicked.connect(self._add_files)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_remove_btn'):
                self.ui.folder_remove_btn.clicked.connect(self._remove_selected_folder)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_clear_btn'):
                self.ui.folder_clear_btn.clicked.connect(self._clear_all_folders)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_list'):
                self.ui.folder_list.itemClicked.connect(self._on_folder_selected)
            
            # 🔥 关键修复：连接 image_list 选中信号到显示方法
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'image_list'):
                self.ui.image_list.itemClicked.connect(self._on_image_selected)

            # Settings connection
            if hasattr(self.ui, 'settings_action') and self.ui.settings_action:
                self.ui.settings_action.triggered.connect(self._open_settings_dialog)

            # Text Block List connections
            if hasattr(self.ui, 'text_block_list') and self.ui.text_block_list and self.ui.image_viewer:
                bus = get_event_bus()
                # ImageViewer -> TextBlockList
                self.ui.image_viewer.text_blocks_generated.connect(bus.ui.text_blocks_generated)
                self.ui.image_viewer.text_block_selected.connect(bus.ui.text_block_selected)
                self.ui.image_viewer.text_blocks_selected.connect(bus.ui.text_blocks_selected)
                self.ui.image_viewer.text_block_hovered.connect(bus.ui.text_block_hovered)

                bus.ui.text_blocks_generated.connect(self.ui.text_block_list.set_blocks)
                bus.ui.text_block_selected.connect(lambda idx, _: self.ui.text_block_list.select_block(idx))
                bus.ui.text_blocks_selected.connect(self.ui.text_block_list.select_blocks)
                bus.ui.text_block_hovered.connect(self.ui.text_block_list.set_hovered_block)

                # TextBlockList -> ImageViewer
                self.ui.text_block_list.block_selected.connect(self.ui.image_viewer.select_text_block)
                self.ui.text_block_list.selection_changed.connect(self.ui.image_viewer.select_text_blocks)
                self.ui.text_block_list.block_hovered.connect(self.ui.image_viewer.set_hovered_block)

            # ImageViewer 悬停同步到表格视图（表格模式）
            if hasattr(self.ui, 'result_table') and self.ui.result_table and self.ui.image_viewer:
                try:
                    # 注意：仅在表格视图显示表格结果时起作用
                    get_event_bus().ui.text_block_hovered.connect(
                        lambda idx: getattr(self.ui.result_table, "set_hovered_block", lambda *_: None)(idx)
                    )
                except Exception:
                    pass

            if hasattr(self.ui, 'result_table') and self.ui.result_table and hasattr(self.ui, 'central_splitter'):
                try:
                    self.ui.result_table.request_preferred_width.connect(self._on_result_table_preferred_width)
                except Exception:
                    pass
            if hasattr(self.ui, 'text_block_list') and self.ui.text_block_list and hasattr(self.ui, 'central_splitter'):
                try:
                    table_widget = getattr(self.ui.text_block_list, "table_widget", None)
                    if table_widget is not None and hasattr(table_widget, "request_preferred_width"):
                        table_widget.request_preferred_width.connect(self._on_result_table_preferred_width)
                except Exception:
                    pass

            print("UI signals connected")

    def _on_theme_changed(self, index):
        theme_key = 'classic'
        if index == 0:
            theme_key = 'cyber_neon'
        elif index == 1:
            theme_key = 'cyber_purple'
        elif index == 2:
            theme_key = 'cyber_orange'
        elif index == 3:
            theme_key = 'classic'
        elif index == 4:
            theme_key = 'minimalist'
        self.config_manager.set_setting('theme', theme_key)
        self.config_manager.save_config()
        if PYQT_AVAILABLE and isinstance(self.main_window, QMainWindow):
            theme_def = self.theme_definitions.get(theme_key, self.theme_definitions['cyber_neon'])
            if isinstance(self.main_window, CustomMainWindow):
                self.main_window.apply_theme(theme_key, theme_def)

    def _on_background_changed(self, index):
        style_key = 'dots'
        if index == 0:
            style_key = 'glass'
        elif index == 1:
            style_key = 'dots'
        elif index == 2:
            style_key = 'frosted'
        self.config_manager.set_setting('glass_background', style_key)
        self.config_manager.save_config()
        if self.main_window:
            self.main_window.update()

    def eventFilter(self, obj, event):
        try:
            if not PYQT_AVAILABLE or not self.ui:
                return False

            # Handle Drag & Drop for Image List
            if obj == self.ui.image_list:
                if event.type() == QEvent.DragEnter:
                    if event.mimeData().hasUrls():
                        event.acceptProposedAction()
                        return True
                if event.type() == QEvent.Drop:
                    urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
                    dropped_files = []
                    for url in urls:
                        local_path = url.toLocalFile()
                        if local_path and os.path.isfile(local_path):
                            ext = os.path.splitext(local_path)[1].lower()
                            if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"]:
                                dropped_files.append(local_path)
                        files_to_process = []
                        for fp in dropped_files:
                            if fp.lower().endswith('.pdf'):
                                try:
                                    cnt = self.file_utils.get_pdf_page_count(fp)
                                    base = os.path.basename(fp)
                                    base_no_ext = os.path.splitext(base)[0]
                                    for i in range(cnt):
                                        name = f"{base_no_ext}_page_{i + 1}"
                                        vpath = f"{fp}|page={i + 1}"
                                        self.file_map[name] = vpath
                                        item = QListWidgetItem(name)
                                        item.setData(Qt.UserRole, vpath)
                                        self.ui.image_list.addItem(item)
                                        # Select the last added item
                                        self.ui.image_list.setCurrentItem(item)
                                        files_to_process.append(vpath)
                                except:
                                    pass
                            else:
                                name = os.path.basename(fp)
                                self.file_map[name] = fp
                                item = QListWidgetItem(name)
                                item.setData(Qt.UserRole, fp)
                                self.ui.image_list.addItem(item)
                                # Select the last added item
                                self.ui.image_list.setCurrentItem(item)
                                files_to_process.append(fp)
                        if files_to_process:
                            if self.processing_thread and self.processing_thread.is_alive():
                                if self.ui:
                                    self.ui.status_label.setText("正在处理，请稍后再拖拽")
                            else:
                                self._start_processing_files(files_to_process)
                    event.acceptProposedAction()
                    return True

            # Handle Drag & Drop for Folder List (Source List)
            if obj == self.ui.folder_list:
                if event.type() == QEvent.DragEnter:
                    if event.mimeData().hasUrls():
                        event.acceptProposedAction()
                        return True
                if event.type() == QEvent.Drop:
                    urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
                    added_count = 0

                    for url in urls:
                        local_path = url.toLocalFile()
                        if not local_path:
                            continue

                        # Check if valid file or directory
                        is_valid = False
                        if os.path.isdir(local_path):
                            is_valid = True
                        elif os.path.isfile(local_path):
                            ext = os.path.splitext(local_path)[1].lower()
                            if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"]:
                                is_valid = True

                        if is_valid:
                            # Add to UI
                            name = os.path.basename(local_path)
                            item = QListWidgetItem(name)
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(Qt.Checked)
                            item.setData(Qt.UserRole, local_path)
                            item.setToolTip(local_path)

                            self.ui.folder_list.addItem(item)
                            added_count += 1

                    if added_count > 0:
                        # 更新状态栏：显示已添加的数量和总数
                        total_folders = self.ui.folder_list.count()
                        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                            self.ui.status_bar.set_status(
                                f"已添加 {added_count} 个文件夹 (共 {total_folders} 个)",
                                self.ui.status_bar.STATUS_INFO
                            )
                        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                            self.ui.status_label.setText(f"已添加 {added_count} 个文件夹 (共 {total_folders} 个)")

                    event.acceptProposedAction()
                    return True

        except Exception as e:
            print(f"Error handling drag-drop: {e}")
        return False

    def _add_files(self):
        """添加单个文件到处理列表"""
        if not PYQT_AVAILABLE or not self.main_window:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self.main_window,
            "选择要添加的图像文件",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.pdf);;All Files (*)"
        )

        if not files:
            return

        added_count = 0
        for file_path in files:
            if file_path:
                # 显示文件名
                name = os.path.basename(file_path)
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, file_path)
                item.setToolTip(file_path)

                self.ui.folder_list.addItem(item)
                added_count += 1

        if added_count > 0:
            # 更新状态栏：显示已添加的数量和总数
            total_folders = self.ui.folder_list.count()
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(
                    f"已添加 {added_count} 个文件 (共 {total_folders} 个)",
                    self.ui.status_bar.STATUS_INFO
                )
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText(f"已添加 {added_count} 个文件 (共 {total_folders} 个)")


    def run(self, input_dir, output_dir):
        """
        运行主窗口（命令行模式）

        Args:
            input_dir: 输入目录路径
            output_dir: 输出目录路径
        """
        print(f"MainWindow running with input_dir: {input_dir}, output_dir: {output_dir}")

        # 设置输入输出目录
        self.input_dir = input_dir
        self.output_dir = output_dir

        # 检查输入目录是否存在
        if not os.path.exists(input_dir):
            self.logger.error(f"Input directory does not exist: {input_dir}")
            return

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        pm = ProcessManager(self.config_manager)
        export_path = pm.process_directory(input_dir, output_dir, self.result_manager)
        if export_path:
            print(f"Results exported to: {export_path}")

    def show(self):
        """
        显示主窗口（GUI模式）
        """
        print("Showing main window")
        if self.ui and self.main_window and PYQT_AVAILABLE:
            # 更新UI显示初始目录
            self._update_ui_with_directories()

            # 启动 TickScheduler (如果尚未启动)
            # 注意：SignalMonitor 可能已经注册，这里只需确保 start
            try:
                from app.scheduler.tick_scheduler import get_tick_scheduler
                self.tick_scheduler = get_tick_scheduler()

                self.tick_scheduler.start()
            except ImportError:
                print("TickScheduler not available")
                self.tick_scheduler = None

            self.main_window.show()
            print("Main window shown")
        else:
            print("Cannot show window: UI not available")
        """
        更新图像列表显示
        """
        if not PYQT_AVAILABLE or not self.ui:
            return

        # 尝试刷新当前选中文件夹的内容
        if hasattr(self.ui, 'folder_list'):
            current_item = self.ui.folder_list.currentItem()
            if current_item:
                directory = current_item.data(Qt.UserRole)
                if not directory and hasattr(self, 'folder_list_items'):
                    directory = self.folder_list_items.get(current_item.text())
                if directory:
                    self._update_image_list_for_folder(directory)

    def _open_settings_dialog(self, initial_tab_index=0):
        """
        打开设置对话框
        """
        if not PYQT_AVAILABLE:
            return

        try:
            from app.ui.dialogs.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self.config_manager, self.main_window, initial_tab_index=initial_tab_index)
            if PYQT_AVAILABLE and hasattr(dialog, 'model_settings_applied'):
                dialog.model_settings_applied.connect(self._on_model_settings_applied)

            result = dialog.exec_()

            if result == QDialog.Accepted:
                changed_categories = dialog.get_changed_categories()
                print(f"Settings changed categories: {changed_categories}")

                # 仅保留与处理参数相关的同步行为；模型重载已在对话框内部流程中完成
                if 'processing' in changed_categories:
                    self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)

        except Exception as e:
            self.logger.error(f"打开设置对话框失败: {e}")
            dlg = GlassMessageDialog(
                self.main_window,
                title="错误",
                text=f"打开设置对话框失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg.exec_()

    def on_models_reloaded(self, detector, recognizer):
        """
        Slot called when models are successfully reloaded (Deprecated)
        
        Note: Model reloading is now handled automatically by UnifiedOCREngine
        through config changes. This method is kept for backward compatibility.
        """
        print("Models reloaded successfully (via UnifiedOCREngine)")
        # Detector and Recognizer have been removed - using UnifiedOCREngine instead
        # No action needed here anymore
        if hasattr(self, 'global_energy_bar') and self.global_energy_bar:
            try:
                self.global_energy_bar.stop_indeterminate()
                self.global_energy_bar.set_value(self.global_energy_bar.maximum())
            except Exception:
                pass
        if self.global_loading_dialog:
            self.global_loading_dialog.hide()
            self.global_loading_dialog = None

        # Update status
        if hasattr(self.ui, 'status_label'):
            self.ui.status_label.setText("模型加载完成")

        # Enable controls
        if hasattr(self.ui, 'start_button'):
            self.ui.start_button.setEnabled(True)
        if hasattr(self.ui, 'model_selector'):
            self.ui.model_selector.setEnabled(True)

        dlg = GlassMessageDialog(
            self.main_window,
            title="完成",
            text="OCR模型加载完成",
            buttons=[("ok", "确定")],
        )
        dlg.exec_()

    def _on_model_settings_applied(self, changed_model_types):
        """
        从设置对话框发起的模型变更：在对话框仍然打开时启动异步模型重载。
        仅锁定设置对话框本身，使用其内置能量条展示状态。
        """
        if not PYQT_AVAILABLE:
            return

        dialog = self.sender()
        if dialog is None:
            return

        print(f"Model settings applied from SettingsDialog, changed types: {changed_model_types}")

        # 子进程模式下，我们不需要在主进程重新加载模型
        # 子进程管理由 SettingsDialog._check_and_stop_subprocess_on_model_change 处理
        # 所以这里我们只需要通知 UI 模型设置已更新，并解锁对话框

        # 底部状态栏提示
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("模型设置已更新 (子进程将在下次任务时自动加载)",
                                          self.ui.status_bar.STATUS_SUCCESS)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText("模型设置已更新")

        # 同步更新设置对话框中的能量条为“就绪”状态
        try:
            if hasattr(dialog, "finalize_model_energy"):
                dialog.finalize_model_energy(changed_model_types, success=True)
        except Exception:
            pass

        # 不需要调用 ModelLoaderThread，因为我们现在完全依赖子进程
        # 旧的逻辑会启动 ModelLoaderThread，这会导致主进程也加载模型，造成资源浪费
        print("Models reloaded successfully (Subprocess Mode)")

        # 弹出完成提示
        dlg = GlassMessageDialog(
            dialog,
            title="完成",
            text="模型设置已更新，将在下次任务时自动加载",
            buttons=[("ok", "确定")],
        )
        dlg.exec_()



    def _on_models_reloaded_from_settings(self, dialog, changed_model_types, detector, recognizer):
        """
        设置对话框发起的模型重载成功回调：
        - 更新 MainWindow 的 detector/recognizer
        - 解除对话框锁定
        - 弹出“完成”提示，必要时关闭设置对话框
        """
        print("Models reloaded successfully (from SettingsDialog)")
        self.detector = detector
        self.recognizer = recognizer

        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("模型加载完成", self.ui.status_bar.STATUS_SUCCESS)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText("模型加载完成")

        # 解除对话框锁定
        if dialog is not None:
            try:
                dialog.setEnabled(True)
            except Exception:
                pass

            # 同步更新设置对话框中的能量条为“就绪”状态
            try:
                if hasattr(dialog, "finalize_model_energy"):
                    dialog.finalize_model_energy(changed_model_types, success=True)
            except Exception:
                pass

        # 弹出完成提示，父窗口使用设置对话框本身，这样用户确认后再关闭对话框
        parent = dialog if dialog is not None else self.main_window
        dlg = GlassMessageDialog(
            parent,
            title="完成",
            text="OCR模型加载完成",
            buttons=[("ok", "确定")],
        )
        dlg.exec_()

        # 如果本次是通过“确定”发起的变更，则在完成提示确认后关闭设置窗口
        try:
            if dialog is not None and getattr(dialog, "_closing_after_model_reload", False):
                dialog._closing_after_model_reload = False
                dialog.accept()
        except Exception:
            pass

    def _on_model_load_error_from_settings(self, dialog, changed_model_types, error_msg):
        """
        设置对话框发起的模型重载失败回调
        """
        print(f"Model load error (from SettingsDialog): {error_msg}")

        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("模型加载失败", self.ui.status_bar.STATUS_ERROR)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText("模型加载失败")

        # 解除对话框锁定，允许用户修改配置后重试
        if dialog is not None:
            try:
                dialog.setEnabled(True)
            except Exception:
                pass

            # 同步更新能量条为失败状态，回落到“待应用”
            try:
                if hasattr(dialog, "finalize_model_energy"):
                    dialog.finalize_model_energy(changed_model_types, success=False)
            except Exception:
                pass

        parent = dialog if dialog is not None else self.main_window
        dlg = GlassMessageDialog(
            parent,
            title="错误",
            text=f"模型加载失败: {error_msg}",
            buttons=[("ok", "确定")],
        )
        dlg.exec_()

    def on_model_load_error(self, error_msg):
        """
        Slot called when model loading fails
        """
        print(f"Model load error: {error_msg}")

        # Hide progress
        if hasattr(self, 'global_energy_bar') and self.global_energy_bar:
            try:
                self.global_energy_bar.stop_indeterminate()
            except Exception:
                pass
        if self.global_loading_dialog:
            self.global_loading_dialog.hide()
            self.global_loading_dialog = None

        # Update status
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("模型加载失败", self.ui.status_bar.STATUS_ERROR)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText("模型加载失败")

        # Enable controls (so user can retry)
        if hasattr(self.ui, 'start_button'):
            self.ui.start_button.setEnabled(True)
        if hasattr(self.ui, 'model_selector'):
            self.ui.model_selector.setEnabled(True)

        dlg = GlassMessageDialog(
            self.main_window,
            title="错误",
            text=f"模型加载失败: {error_msg}",
            buttons=[("ok", "确定")],
        )
        dlg.exec_()

    def _start_processing(self, folders_to_process=None, force_reprocess=False):
        """
        Start processing folders using ProcessingController
        
        Args:
            folders_to_process: 可选的文件夹列表，如果为 None 则从 folder_list 获取所有勾选的文件夹
            force_reprocess: 是否强制重新处理
        """
        # 🔥 关键修复：使用 info 级别确保日志可见
        self.logger.info("main_window", "starting_batch_processing", f"Starting batch processing of folders (force_reprocess={force_reprocess})")
        print(f"[DEBUG] _start_processing called with folders_to_process={folders_to_process}, force_reprocess={force_reprocess}")

        # Collect folders
        if folders_to_process is None:
            folders_to_process = []
            
            # 🔥 从 folder_list 获取所有勾选的文件夹（保持原有逻辑）
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_list') and self.ui.folder_list:
                folder_count = self.ui.folder_list.count()
                self.logger.info("main_window", "collecting_folders_from_ui", 
                                f"UI folder_list exists, count={folder_count}")
                print(f"[DEBUG] folder_list count: {folder_count}")
                
                for i in range(self.ui.folder_list.count()):
                    item = self.ui.folder_list.item(i)
                    if item and item.checkState() == Qt.Checked:
                        directory = item.data(Qt.UserRole)
                        
                        # 🔥 兼容旧代码：如果没有 UserRole 数据，尝试从文本映射获取
                        if not directory:
                            directory = getattr(self, 'folder_list_items', {}).get(item.text())
                        
                        self.logger.info("main_window", "folder_checked", 
                                        f"Found checked folder at index {i}: {directory}")
                        print(f"[DEBUG] Checked folder[{i}]: {directory}")
                        if directory:
                            folders_to_process.append(directory)
            else:
                ui_exists = self.ui is not None
                folder_list_exists = hasattr(self.ui, 'folder_list') if self.ui else False
                self.logger.warning("main_window", "folder_list_not_available", 
                                  f"folder_list not available: ui_exists={ui_exists}, folder_list_exists={folder_list_exists}")
                print(f"[DEBUG] folder_list NOT available: ui_exists={ui_exists}, folder_list_exists={folder_list_exists}")

        self.logger.info("main_window", "folders_collected", 
                         f"Collected {len(folders_to_process)} folders to process: {folders_to_process}")
        print(f"[DEBUG] Final folders_to_process: {folders_to_process}")

        if not folders_to_process:
            self.logger.warning("main_window", "no_folders_selected", "No folders selected for processing")
            print("[DEBUG] No folders selected, showing dialog")
            if PYQT_AVAILABLE and self.main_window:
                dlg = GlassMessageDialog(
                    self.main_window,
                    title="提示",
                    text="请先添加并勾选要处理的文件夹",
                    buttons=[("ok", "确定")],
                )
                dlg.exec_()
            return

        # Prepare UI
        if PYQT_AVAILABLE and self.ui:
            self.logger.info("main_window", "preparing_ui_for_processing", 
                           f"Preparing UI for processing {len(folders_to_process)} folders")
            print(f"[DEBUG] Preparing UI, disabling start button")
            self.ui.start_button.setEnabled(False)
            self.ui.stop_button.setEnabled(True)
            if hasattr(self.ui, 'status_bar'):
                self.ui.status_bar.set_status(f"正在准备处理 {len(folders_to_process)} 个文件夹",
                                              self.ui.status_bar.STATUS_WORKING)

            # Save settings
            self.config_manager.set_setting('use_preprocessing', False)
            self.config_manager.save_config()

        self.results_by_filename = {}
        self.performance_monitor.reset()

        self.logger.info("main_window", "calling_controller_start", 
                        f"Calling processing_controller.start_processing with {len(folders_to_process)} folders")
        print(f"[DEBUG] About to call processing_controller.start_processing")
        
        # Start processing via controller
        self.processing_controller.start_processing(folders_to_process, force_reprocess=force_reprocess)
        print(f"[DEBUG] processing_controller.start_processing called successfully")

    def _start_processing_files(self, files, force_reprocess=False):
        """
        Start processing specific files (Drag & Drop) using ProcessingController
        """
        if not files:
            return

        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(False)
            self.ui.stop_button.setEnabled(True)
            msg = "正在重新处理选中的文件" if force_reprocess else "正在处理文件"
            if hasattr(self.ui, 'status_bar'):
                self.ui.status_bar.set_status(msg, self.ui.status_bar.STATUS_WORKING)

        self.performance_monitor.reset()
        
        # 🔥 重构：使用 ProcessingController 启动处理（内部会调用 OCRPipeline）
        self.processing_controller.start_processing(files, force_reprocess)

    def on_processing_status_update(self, text, status_type):
        """Signal handler for processing status updates"""

        index = 0
        if hasattr(self.ui, 'table_mode_group') and self.ui.table_mode_group:
            try:
                checked_button = self.ui.table_mode_group.checkedButton()
                if checked_button is not None:
                    index = self.ui.table_mode_group.id(checked_button)
            except Exception:
                index = 0
        elif hasattr(self.ui, 'table_mode_combo'):
            index = self.ui.table_mode_combo.currentIndex()

        if index is not None:
            use_table_split = (index == 1)
            # AI 表格模式已不再主窗口 UI 中显示，仅保留配置用于兼容
            # use_ai_table = (index == 2)

            # 🔥 关键修复：传统表格识别模式应该可以随时启用/关闭
            print(f"DEBUG: 表格模式切换 - index={index}, use_table_split={use_table_split}")

            self.config_manager.set_setting('use_table_split', use_table_split)
            if use_table_split:
                # 传统表格识别使用 cell 模式
                self.config_manager.set_setting('table_split_mode', 'cell')
                print("DEBUG: 已启用传统表格识别模式（基于物理规则）")
            else:
                print("DEBUG: 已关闭传统表格识别模式")

        # ai_table_model_combo 和 ai_advanced_doc_chk 已移除，不再需要保存

        # 注意：不在这里立即保存到磁盘，避免频繁 IO
        # self.config_manager.save_config()

    def on_processing_status_update(self, text, status_type):
        """Signal handler for processing status updates"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        import time
        current_time = time.time()
        if not hasattr(self, '_last_status_update_time'):
            self._last_status_update_time = 0

        if (current_time - self._last_status_update_time > 0.1) or (status_type != "working") or ("完成" in text):
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(text, status_type)
            self._last_status_update_time = current_time

    def on_file_processed(self, filename, text):
        """Signal handler for file processing completion"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        self.results_by_filename[filename] = text

        # 尝试从 MessagePack 缓存加载 json_data 以保持同步
        # ProcessingController 在发射信号之前已经保存了 MessagePack
        try:
            if filename in self.file_map:
                image_path = self.file_map[filename]
                base_name = os.path.splitext(filename)[0]
                parent_dir_name = os.path.basename(os.path.dirname(image_path))
                current_output_dir = os.path.join(self.output_dir, parent_dir_name)
                msgpack_path = os.path.join(current_output_dir, "msgpack", f"{base_name}.msgpack")

                if os.path.exists(msgpack_path):
                    from app.infrastructure.message_pack_serializer import MessagePackSerializer
                    data = MessagePackSerializer.load_from_file(msgpack_path)
                    if isinstance(data, dict):
                        self.results_json_by_filename[filename] = data
                        print(f"DEBUG [on_file_processed] Loaded MessagePack into cache: {filename}")
        except Exception as e:
            print(f"Error loading MessagePack cache in on_file_processed: {e}")

        # Check if we need to update the display
        if self.ui.image_list.count() > 0:
            current_item = self.ui.image_list.currentItem()
            if current_item and current_item.text() == filename:
                self._display_result_for_item(current_item)

    def on_processing_finished(self, total_time=0):
        """Signal handler for batch processing completion"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        self.ui.start_button.setEnabled(True)
        self.ui.stop_button.setEnabled(False)
        if hasattr(self.ui, 'status_bar'):
            self.ui.status_bar.set_status(f"处理完成 (耗时: {total_time:.2f}s)", self.ui.status_bar.STATUS_SUCCESS)

        # Refresh current item display
        if self.ui.image_list.count() > 0:
            item = self.ui.image_list.currentItem()
            if not item:
                item = self.ui.image_list.item(0)
                self.ui.image_list.setCurrentItem(item)
            self._display_result_for_item(item)

    def on_processing_error(self, error_msg):
        """Signal handler for processing errors"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        self.logger.error(f"Processing error: {error_msg}")
        dlg = GlassMessageDialog(
            self.main_window,
            title="处理错误",
            text=f"处理过程中发生错误:\n{error_msg}",
            buttons=[("ok", "确定")],
        )
        dlg.exec_()

        self.ui.start_button.setEnabled(True)
        self.ui.stop_button.setEnabled(False)
        if hasattr(self.ui, 'status_bar'):
            self.ui.status_bar.set_status("处理出错", self.ui.status_bar.STATUS_ERROR)

    def _stop_processing(self):
        """Stop processing"""
        print(f"[DEBUG] _stop_processing called! Stop flag={self._stop_flag}")
        import traceback
        print("[DEBUG] Stack trace when _stop_processing was called:")
        traceback.print_stack()
        
        self._stop_flag = True
        self.processing_controller.stop()

        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(True)
            self.ui.stop_button.setEnabled(False)
            if hasattr(self.ui, 'status_bar'):
                self.ui.status_bar.set_status("处理已停止", self.ui.status_bar.STATUS_WARNING)

    def _display_result_for_filename(self, filename):
        start_total = time.perf_counter()
        if not PYQT_AVAILABLE or not self.ui:
            return

        # 1. 尝试从内存获取
        t0 = time.perf_counter()
        text = self.results_by_filename.get(filename, "")
        json_data = self.results_json_by_filename.get(filename, None)
        t1 = time.perf_counter()
        print(f"PERF[_display_result_for_filename] cache_lookup {filename}: {(t1 - t0) * 1000:.1f} ms")

        # 2. 如果内存没有，尝试从文件缓存加载
        # 如果内存中有 text 但没有 json_data，也尝试加载 json 以补充
        if (not text or not json_data) and filename in self.file_map:
            image_path = self.file_map[filename]
            t2 = time.perf_counter()
            try:
                base_dir = os.path.dirname(image_path)
                base_name = os.path.splitext(filename)[0]

                # 新逻辑：从集中化目录加载 msgpack
                parent_dir_name = os.path.basename(os.path.dirname(image_path))
                current_output_dir = os.path.join(self.output_dir, parent_dir_name)
                msgpack_path = os.path.join(current_output_dir, "msgpack", f"{base_name}.msgpack")

                if os.path.exists(msgpack_path):
                    from app.infrastructure.message_pack_serializer import MessagePackSerializer
                    data = MessagePackSerializer.load_from_file(msgpack_path)
                    print(f"\nDEBUG [Load MessagePack] File: {msgpack_path}")
                    print(f"  Loaded data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    if isinstance(data, dict) and 'regions' in data:
                        regions = data['regions']
                        print(f"  Regions count: {len(regions)}")
                        if regions:
                            print(f"  First region keys: {list(regions[0].keys())}")
                            print(f"    text: {regions[0].get('text', '')[:20]}...")
                            print(f"    Has box: {'box' in regions[0]}")
                            print(f"    Has polygon: {'polygon' in regions[0]}")
                            print(f"    Has table_info: {'table_info' in regions[0]}")
                            if 'box' in regions[0]:
                                print(f"    box value: {regions[0]['box']}")
                            if 'polygon' in regions[0]:
                                print(f"    polygon value: {regions[0]['polygon'][:2]}...")
                        # 重要：打印所有 regions 用于调试
                        print(f"  All regions text preview: {[r.get('text', '')[:10] for r in regions[:5]]}")

                    # 🔥 关键修改：文本结果栏直接从 msgpack 的 regions 中提取文本
                    # 按照阅读顺序拼接所有文本（用换行符分隔）
                    if isinstance(data, dict) and 'regions' in data:
                        regions = data.get('regions', [])
                        # 按 y 坐标排序（从上到下），然后按 x 坐标排序（从左到右）
                        sorted_regions = sorted(
                            regions,
                            key=lambda r: (
                                r.get('box', [0, 0, 0, 0])[1],  # y1
                                r.get('box', [0, 0, 0, 0])[0]  # x1
                            )
                        )
                        text_lines = [r.get('text', '') for r in sorted_regions if r.get('text', '').strip()]
                        text = "\n".join(text_lines)
                        print(f"DEBUG: Extracted {len(text_lines)} lines from msgpack regions for text display")

                        if not self.results_by_filename.get(filename):
                            self.results_by_filename[filename] = text

                    # 如果没有 regions，尝试使用 full_text 字段
                    if not text:
                        text = data.get('full_text', '')

                    if not json_data:
                        json_data = data

                if json_data:
                    self.results_json_by_filename[filename] = json_data

                # 存储提取的文本到缓存和结果管理器
                if text:
                    self.results_by_filename[filename] = text
                    self.result_manager.store_result(image_path, text)
                    print(f"Loaded cached result for {filename}")

            except Exception as e:
                print(f"Error loading cache for {filename}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                t3 = time.perf_counter()
                print(f"PERF[_display_result_for_filename] disk_load {filename}: {(t3 - t2) * 1000:.1f} ms")

        # 显示纯文本到文本结果栏
        self.ui.result_display.setPlainText(text)

        # 为所有导出视图设置基础文件名（无论是否有表格信息）
        try:
            base_name_for_export = os.path.splitext(filename)[0]
        except Exception:
            base_name_for_export = filename
        if hasattr(self.ui, "result_table") and self.ui.result_table and hasattr(self.ui.result_table,
                                                                                 "set_export_basename"):
            self.ui.result_table.set_export_basename(base_name_for_export)
        if hasattr(self.ui, "text_block_list") and self.ui.text_block_list and hasattr(self.ui.text_block_list,
                                                                                       "set_export_basename"):
            self.ui.text_block_list.set_export_basename(base_name_for_export)

        # 准备显示数据
        t4 = time.perf_counter()
        items = []
        fields = []

        if json_data and 'regions' in json_data:
            regions = json_data['regions']
            print(f"\nDEBUG [UI Display] Building display items from {len(regions)} regions")
            if regions:
                print(f"  First region keys: {list(regions[0].keys())}")
                print(f"  Has box: {'box' in regions[0]}")
                print(f"  Has polygon: {'polygon' in regions[0]}")
                print(f"  Has table_info: {'table_info' in regions[0]}")
                if 'box' in regions[0]:
                    print(f"  First box: {regions[0]['box']}")
                if 'polygon' in regions[0]:
                    print(f"  First polygon: {regions[0]['polygon'][:2]}...")

            for i, r in enumerate(regions):
                # 直接使用 ResultAdapter 处理后的标准化字段
                item = {
                    'text': r.get('text', ''),
                    'confidence': r.get('confidence', 0.0),
                    'box': r.get('box'),  # ResultAdapter 已经计算好的边界框
                    'polygon': r.get('polygon'),  # ResultAdapter 提供的多边形坐标
                    'table_info': r.get('table_info'),  # ResultAdapter 提供的表格信息
                    'is_empty': False,
                    'original_data': r
                }
                items.append(item)

                # 打印前 3 个和后 3 个的详细信息
                if i < 3 or i >= len(regions) - 3:
                    print(
                        f"  Item[{i}]: text='{r.get('text', '')[:10]}...', box={r.get('box')}, has_table_info={bool(r.get('table_info'))}")
                elif i == 3:
                    print(f"  ... ({len(regions) - 6} more items) ...")

            fields = [('content', '内容')]
            print(f"  Built {len(items)} display items")
            print(f"  Sample item keys: {list(items[0].keys()) if items else 'None'}")
            if items:
                print(f"  Sample box: {items[0].get('box')}")
                print(f"  Sample polygon: {items[0].get('polygon')}")
                print(f"  Sample table_info: {items[0].get('table_info')}")
            print()
        elif text:
            lines = [line for line in text.split('\n') if line.strip()]
            items = [{'text': line, 'box': None, 'is_empty': False, 'original_data': None} for line in lines]
            fields = [('content', '内容')]

        t5 = time.perf_counter()
        print(
            f"PERF[_display_result_for_filename] build_items {filename}: {(t5 - t4) * 1000:.1f} ms (items={len(items)})")

        has_table_info = False
        table_cells = []
        if json_data and 'regions' in json_data:
            # Use regions list order and table_info row/col directly to preserve true table layout
            for r in json_data['regions']:
                table_info = r.get('table_info')
                if not table_info:
                    continue
                has_table_info = True
                cell = {
                    'text': r.get('text', ''),
                    'table_info': {
                        'row': table_info.get('row', 0),
                        'col': table_info.get('col', 0),
                        'rowspan': table_info.get('rowspan', 1),
                        'colspan': table_info.get('colspan', 1),
                        'is_header': table_info.get('is_header', False)
                    }
                }
                table_cells.append(cell)

        # 更新UI视图
        # 如果有表格信息，优先显示表格视图

        # 重新检查 table_info (ResultAdapter 已经统一了格式)
        table_cells = []
        has_table_info = False

        for item in items:
            # ResultAdapter returns standardized structure:
            # item['table_info'] is a dict or None
            if item.get('table_info'):
                has_table_info = True
                # 直接使用适配后的数据
                cell = {
                    'text': item.get('text', ''),
                    'confidence': item.get('confidence', 0.0),
                    'table_info': item['table_info']
                }
                table_cells.append(cell)

        # 强制更新 ResultTableWidget 数据，即使为空也要清空
        if hasattr(self.ui, 'result_table') and self.ui.result_table:
            self.ui.result_table.set_data(table_cells if has_table_info else [])

        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            # 始终设置 OCR 结果到 ImageViewer，让它自己决定如何显示
            if hasattr(self.ui.image_viewer, 'is_table_mode'):
                self.ui.image_viewer.is_table_mode = has_table_info

            # 始终传递结果，即使在表格模式下也允许显示（如果用户需要）
            # 或者由 ImageViewer 内部决定是否显示
            self.ui.image_viewer.set_ocr_results(items)

        if hasattr(self.ui, 'result_table') and self.ui.result_table and hasattr(self.ui, 'struct_view_stack'):
            if has_table_info:
                # 只有当确实有表格信息时才自动切换到表格视图
                index = self.ui.struct_view_stack.indexOf(self.ui.result_table)
                if index != -1:
                    self.ui.struct_view_stack.setCurrentIndex(index)
            else:
                # 没有表格信息，切换回文本块列表
                if hasattr(self.ui, 'text_block_list') and self.ui.text_block_list:
                    index = self.ui.struct_view_stack.indexOf(self.ui.text_block_list)
                    if index != -1:
                        self.ui.struct_view_stack.setCurrentIndex(index)

        end_total = time.perf_counter()
        print(f"PERF[_display_result_for_filename] total {filename}: {(end_total - start_total) * 1000:.1f} ms")

    def _show_file_list_context_menu(self, position):
        """显示文件列表右键菜单"""
        if not PYQT_AVAILABLE:
            return

        from PyQt5.QtWidgets import QMenu
        menu = QMenu()

        reprocess_action = menu.addAction("强制重新OCR处理")
        reprocess_action.triggered.connect(self.reprocess_selected_files)

        menu.exec_(self.ui.image_list.mapToGlobal(position))

    def _show_folder_list_context_menu(self, position):
        """显示文件夹列表右键菜单"""
        if not PYQT_AVAILABLE:
            return

        # 获取所有选中的项目
        selected_items = self.ui.folder_list.selectedItems()
        if not selected_items:
            # 尝试获取当前点击位置的项目（如果未选中）
            item = self.ui.folder_list.itemAt(position)
            if item:
                selected_items = [item]
            else:
                return

        from PyQt5.QtWidgets import QMenu
        menu = QMenu()

        # 重新处理目录动作
        count = len(selected_items)
        action_text = f"强制重新OCR处理选中的 {count} 个目录" if count > 1 else "强制重新OCR处理整个目录"
        reprocess_action = menu.addAction(action_text)
        reprocess_action.triggered.connect(lambda: self.reprocess_directories(selected_items))

        menu.addSeparator()

        # 移除目录动作
        remove_action = menu.addAction(f"移除选中的 {count} 个目录" if count > 1 else "移除目录")
        remove_action.triggered.connect(self._remove_selected_folder)

        menu.exec_(self.ui.folder_list.mapToGlobal(position))

    def reprocess_directories(self, items):
        """强制重新处理选中的多个目录"""
        if not items:
            return

        directories = []
        for item in items:
            directory = item.data(Qt.UserRole)
            if not directory:
                directory = self.folder_list_items.get(item.text())

            if directory:
                directories.append(directory)

        if not directories:
            return

        # 确认弹窗
        dir_names = [os.path.basename(d) for d in directories]
        display_names = ", ".join(dir_names[:3])
        if len(dir_names) > 3:
            display_names += f" 等 {len(dir_names)} 个目录"

        dlg = GlassMessageDialog(
            self.main_window,
            title="确认",
            text=f"确定要重新处理以下目录下的所有文件吗？\n{display_names}\n这将覆盖现有的结果。",
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg.exec_()
        if dlg.result_key() != "yes":
            return

        # 调用批量处理文件夹逻辑，传递 force_reprocess=True
        self._start_processing(directories, force_reprocess=True)

    def reprocess_directory(self, item):
        """(Deprecated) 强制重新处理指定目录 - 保留以兼容旧代码，建议使用 reprocess_directories"""
        if item:
            self.reprocess_directories([item])

    def reprocess_current_directory(self):
        """强制重新处理当前选中文件所在的目录"""
        selected_items = self.ui.image_list.selectedItems()
        if not selected_items:
            # 如果没选中文件，但列表里有文件，默认处理第一个文件所在的目录
            if self.ui.image_list.count() > 0:
                item = self.ui.image_list.item(0)
            else:
                return
        else:
            item = selected_items[0]

        filename = item.text()
        if filename not in self.file_map:
            return

        file_path = self.file_map[filename]
        # 获取目录路径
        # 注意：如果 file_path 是虚拟路径（如 PDF 页面），需要解析出真实目录
        if "|page=" in file_path:
            real_path = file_path.split("|")[0]
            dir_path = os.path.dirname(real_path)
        else:
            dir_path = os.path.dirname(file_path)

        # 确认弹窗
        dlg = GlassMessageDialog(
            self.main_window,
            title="确认",
            text=f"确定要重新处理目录 '{os.path.basename(dir_path)}' 下的所有文件吗？\n这将覆盖现有的结果。",
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg.exec_()
        if dlg.result_key() != "yes":
            return

        # 调用批量处理文件夹逻辑
        # 我们需要构造一个只包含该文件夹的列表
        self._start_processing([dir_path])

    def reprocess_selected_files(self):
        """强制重新处理选中的文件"""
        selected_items = self.ui.image_list.selectedItems()
        if not selected_items:
            return

        files_to_process = []
        for item in selected_items:
            filename = item.text()
            if filename in self.file_map:
                files_to_process.append(self.file_map[filename])

        if not files_to_process:
            return

        dlg = GlassMessageDialog(
            self.main_window,
            title="确认",
            text=f"确定要重新处理选中的 {len(files_to_process)} 个文件吗？\n这将覆盖现有的结果。",
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg.exec_()
        if dlg.result_key() != "yes":
            return

        # 如果正在处理中，不允许重新处理
        is_processing = False
        if hasattr(self.processing_controller, 'processing_thread') and self.processing_controller.processing_thread:
            if hasattr(self.processing_controller.processing_thread, 'isRunning'):
                if self.processing_controller.processing_thread.isRunning():
                    is_processing = True
            elif hasattr(self.processing_controller.processing_thread, 'is_alive'):
                if self.processing_controller.processing_thread.is_alive():
                    is_processing = True

        if is_processing:
            dlg_busy = GlassMessageDialog(
                self.main_window,
                title="提示",
                text="当前有任务正在进行中，请等待完成后再操作",
                buttons=[("ok", "确定")],
            )
            dlg_busy.exec_()
            return


        print(f"Reprocessing {len(files_to_process)} files")
        self._start_processing_files(files_to_process, force_reprocess=True)

    def _on_image_selected(self, item):
        """当图像列表中的项被选中时显示图像和结果"""
        print(f"[DEBUG] _on_image_selected called with item: {item}")
        if not item:
            print("[DEBUG] Item is None, returning")
            return
            
        name = item.text()
        print(f"[DEBUG] Selected item text: {name}")
        
        # 1. 显示图像
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            path = self.file_map.get(name, None)
            print(f"[DEBUG] Image path from file_map: {path}")
            if path:
                try:
                    self.ui.image_viewer.display_image(path)
                    print(f"[DEBUG] Successfully displayed image: {path}")
                except Exception as e:
                    print(f"[DEBUG] Error displaying image: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[DEBUG] No path found for {name} in file_map")
        else:
            print(f"[DEBUG] image_viewer not available")
        
        # 2. 显示识别结果
        print(f"[DEBUG] About to display result for: {name}")
        self._display_result_for_filename(name)

    def _add_files(self):
        """添加单个文件到处理列表"""
        if not PYQT_AVAILABLE or not self.main_window:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self.main_window,
            "选择要添加的图像文件",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.pdf);;All Files (*)"
        )

        if not files:
            return

        added_count = 0
        for file_path in files:
            if file_path and file_path not in self.folders:
                self.folders.append(file_path)

                # 显示文件名
                file_name = os.path.basename(file_path)

                item = QListWidgetItem(file_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, file_path)
                item.setToolTip(file_path)

                self.ui.folder_list.addItem(item)
                # 修复：同时存储文件名和完整路径作为 key，确保双重索引
                self.folder_list_items[file_name] = file_path
                self.folder_list_items[file_path] = file_path
                added_count += 1

        if added_count > 0:
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(f"已添加 {added_count} 个文件", self.ui.status_bar.STATUS_INFO)
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText(f"已添加 {added_count} 个文件")

    def _add_folder(self):
        """添加文件夹到处理列表"""
        if not PYQT_AVAILABLE or not self.main_window:
            return

        directory = QFileDialog.getExistingDirectory(self.main_window, "选择要添加的文件夹")
        if directory:
            # 显示文件夹名称而不是完整路径
            folder_name = os.path.basename(directory)
            if not folder_name:  # 如果是根目录，使用完整路径
                folder_name = directory

            item = QListWidgetItem(folder_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, directory)
            item.setToolTip(directory)

            self.ui.folder_list.addItem(item)

            # 更新状态栏：显示已添加的文件夹和总数
            total_folders = self.ui.folder_list.count()
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(
                    f"已添加文件夹：{folder_name} (共 {total_folders} 个)",
                    self.ui.status_bar.STATUS_INFO
                )
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText(f"已添加文件夹：{folder_name} (共 {total_folders} 个)")

    def _add_folder_from_path(self, directory):
        """从路径添加文件夹到处理列表（用于拖拽等场景）"""
        if not PYQT_AVAILABLE or not self.ui or not directory:
            return
            
        # 显示文件夹名称而不是完整路径
        folder_name = os.path.basename(directory)
        if not folder_name:  # 如果是根目录，使用完整路径
            folder_name = directory

        item = QListWidgetItem(folder_name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setData(Qt.UserRole, directory)
        item.setToolTip(directory)

        self.ui.folder_list.addItem(item)

        # 更新状态栏：显示已添加的文件夹和总数
        total_folders = self.ui.folder_list.count()
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status(
                f"已添加文件夹：{folder_name} (共 {total_folders} 个)",
                self.ui.status_bar.STATUS_INFO
            )
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText(f"已添加文件夹：{folder_name} (共 {total_folders} 个)")

    def _remove_selected_folder(self):
        """移除选中的项目(文件/文件夹)"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        current_item = self.ui.folder_list.currentItem()
        if current_item:
            row = self.ui.folder_list.row(current_item)
            self.ui.folder_list.takeItem(row)

            # 更新状态栏：显示移除的文件夹和剩余数量
            remaining_folders = self.ui.folder_list.count()
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                if remaining_folders > 0:
                    self.ui.status_bar.set_status(
                        f"已移除：{current_item.text()} (剩余 {remaining_folders} 个)",
                        self.ui.status_bar.STATUS_INFO
                    )
                else:
                    self.ui.status_bar.set_status("文件夹列表已清空", self.ui.status_bar.STATUS_INFO)
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                if remaining_folders > 0:
                    self.ui.status_label.setText(f"已移除：{current_item.text()} (剩余 {remaining_folders} 个)")
                else:
                    self.ui.status_label.setText("文件夹列表已清空")

            # 如果已经没有任何项目，则恢复到“无图片”初始状态
            if self.ui.folder_list.count() == 0:
                self._clear_all_folders()

    def _clear_all_folders(self):
        """清空所有项目"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        # 清空内部数据
        self.file_map.clear()
        self.results_by_filename.clear()
        self.results_json_by_filename.clear()

        # 清空 UI 列表
        self.ui.folder_list.clear()
        self.ui.image_list.clear()

        # 更新状态栏
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("已清空所有项目", self.ui.status_bar.STATUS_INFO)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText("已清空所有项目")

    def _update_ui_with_directories(self):

        if hasattr(self.ui, 'result_table') and self.ui.result_table:
            try:
                self.ui.result_table.set_data([])
            except Exception:
                pass

        if hasattr(self.ui, 'text_block_list') and self.ui.text_block_list:
            tbl = self.ui.text_block_list
            try:
                tbl.set_blocks([])
            except Exception:
                try:
                    table = getattr(tbl, "list_widget", None)
                    if table is not None:
                        table.clearContents()
                        table.setRowCount(0)
                except Exception:
                    pass

        # 默认切回文本视图
        if hasattr(self.ui, 'struct_view_stack') and self.ui.struct_view_stack:
            if hasattr(self.ui, 'text_block_list') and self.ui.text_block_list:
                idx = self.ui.struct_view_stack.indexOf(self.ui.text_block_list)
                if idx != -1:
                    self.ui.struct_view_stack.setCurrentIndex(idx)

        # 更新状态栏
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("已清空所有项目", self.ui.status_bar.STATUS_INFO)

    def _on_image_selected(self, item):
        """当图像列表中的项被选中时显示结果"""
        if not item:
            return
            
        # 显示选中文件的结果
        self._display_result_for_filename(item.text())

    def _on_folder_selected(self, item):
        """文件夹选择变化处理"""
        if not item:
            return

        directory = item.data(Qt.UserRole)
        if not directory:
            directory = self.folder_list_items.get(item.text())

        if directory:
            # 更新图像列表显示该文件夹的内容
            self._update_image_list_for_folder(directory)

            # 自动显示第一张图片
            if self.ui.image_list.count() > 0:
                first_item = self.ui.image_list.item(0)
                self.ui.image_list.setCurrentRow(0)
                self._on_image_selected(first_item)

            # 蒙版功能已移除
    def _update_image_list_for_folder(self, directory):
        """更新图像列表显示指定文件夹的内容"""
        if not PYQT_AVAILABLE or not self.ui:
            return

        self.ui.image_list.clear()
        self.file_map = {}

        if os.path.exists(directory):
            # Check if it's a PDF file (treated as folder)
            if os.path.isfile(directory) and directory.lower().endswith('.pdf'):
                try:
                    page_count = self.file_utils.get_pdf_page_count(directory)
                    base_name = os.path.basename(directory)
                    name_prefix = os.path.splitext(base_name)[0]

                    for i in range(page_count):
                        page_idx = i + 1
                        display_name = f"{name_prefix}_page_{page_idx}"
                        virtual_path = f"{directory}|page={page_idx}"

                        self.file_map[display_name] = virtual_path
                        item = QListWidgetItem(display_name)
                        item.setData(Qt.UserRole, virtual_path)
                        self.ui.image_list.addItem(item)
                except Exception as e:
                    print(f"Error listing PDF pages: {e}")
            else:
                image_files = self.file_utils.get_image_files(directory)
                for image_file in image_files:
                    name = os.path.basename(image_file)
                    self.file_map[name] = image_file
                    item = QListWidgetItem(name)
                    item.setData(Qt.UserRole, image_file)
                    self.ui.image_list.addItem(item)



    def quit_application(self):
        """
        退出应用程序（清理资源并关闭）
        """
        print("Quitting application...")
        self._is_quitting = True
        if self.main_window:
            self.main_window.close()

    def cleanup(self):
        """
        清理资源
        """
        print("Cleaning up resources...")

        # Stop ProcessManager
        if self.process_manager:
            self.process_manager.stop_processes()

        # 停止所有任务
        if hasattr(self, 'task_manager'):
            self.task_manager.stop_worker()

        # 停止 TickScheduler
        try:
            from app.scheduler.tick_scheduler import get_tick_scheduler
            scheduler = get_tick_scheduler()
            scheduler.unregister_system("ocr_subprocess_health_check")
            scheduler.unregister_system("SignalMonitor")
            scheduler.stop()
        except ImportError:
            pass

        # 停止定时器 (Legacy)
        if PYQT_AVAILABLE and hasattr(self, 'tick_scheduler') and self.tick_scheduler:
            self.tick_scheduler.stop()

        if PYQT_AVAILABLE and hasattr(self, 'check_progress_timer') and self.check_progress_timer:
            self.check_progress_timer.stop()

    # Legacy close method kept for compatibility but redirects to quit_application
    def close(self):
        self.quit_application()
