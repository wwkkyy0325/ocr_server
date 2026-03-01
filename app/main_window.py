# -*- coding: utf-8 -*-

"""
主窗口（集成所有UI组件和交互逻辑）
"""

import os
import threading
import json
from datetime import datetime
import time
import sys
import ctypes
from ctypes import wintypes

from app.core.process_manager import ProcessManager
from app.core.mask_manager import MaskManager
from app.core.service_registry import ServiceRegistry
from app.core.clipboard_watcher import ClipboardWatcher
from app.ocr.engine import OcrEngine
from app.core.env_manager import EnvManager
from app.core.processing_controller import ProcessingController
from app.core.result_exporter import ResultExporter

try:
    from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QInputDialog, QListWidgetItem, QListWidget, QDialog, QTabWidget, QAction, QSystemTrayIcon, QMenu, QApplication, QStyle, QCheckBox, QProgressBar, QLabel, QProgressDialog, QMenuBar, QPushButton, QWidget, QHBoxLayout, QComboBox, QVBoxLayout
    from PyQt5.QtGui import QIcon, QPainter, QPen, QColor, QPainterPath, QRegion, QBrush, QRadialGradient, QLinearGradient
    from PyQt5.QtCore import QTimer, Qt, QEvent, QFileSystemWatcher, QThread, pyqtSignal, QPoint
    from app.ui.widgets.floating_result_widget import FloatingResultWidget
    from app.ui.widgets.progress_bar import CyberEnergyBar, AnnouncementBanner
    from app.ui.dialogs.mask_manager_dialog import MaskManagerDialog
    from app.core.model_loader import ModelLoaderThread
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, using console mode")

from app.ui.styles.glass_components import (
    GlassTitleBar,
    FramelessBorderWindow,
    FramelessBorderDialog,
    register_config_manager
)
from app.ui.dialogs.glass_dialogs import GlassLoadingDialog, GlassMessageDialog


# 移除旧的绘图函数，它们已迁移至 BackgroundPainter
# _get_glass_background_style, _paint_plain_glass_background, _paint_dots_background, _paint_frosted_background 已被移除

# Define Worker Thread
if PYQT_AVAILABLE:
    from app.core.workers import ProcessingWorker
    from app.ui.main_window_frame import CustomMainWindow
from app.core.config_manager import ConfigManager
from app.core.task_manager import TaskManager
from app.core.result_manager import ResultManager
from app.ocr.detector import Detector
from app.ocr.recognizer import Recognizer
from app.ocr.post_processor import PostProcessor
from app.image.converter import Converter
from app.image.preprocessor import Preprocessor
from app.image.cropper import Cropper
from app.utils.file_utils import FileUtils
from app.utils.logger import Logger
from app.utils.performance import PerformanceMonitor
from app.core.record_manager import RecordManager
from app.ui.controllers.database_controller import DatabaseController
from app.ui.controllers.screenshot_controller import ScreenshotController
if PYQT_AVAILABLE:
    from app.ui.dialogs.model_download_dialog import ModelDownloadDialog
    # from app.ui.dialogs.model_settings_dialog import ModelSettingsDialog
import json
from app.core.ocr_service import OcrBatchService



if PYQT_AVAILABLE:
    from PyQt5.QtCore import QObject
else:
    class QObject: pass

class MainWindow(QObject):
    if PYQT_AVAILABLE:
        file_processed_signal = pyqtSignal(str, str)
        processing_finished_signal = pyqtSignal()
        ocr_result_ready_signal = pyqtSignal(str)

    def __init__(self, config_manager=None, is_gui_mode=False, detector=None, recognizer=None, post_processor=None,
                 converter=None, preprocessor=None, cropper=None, file_utils=None, logger=None,
                 performance_monitor=None):
        """
        初始化主窗口

        Args:
            config_manager: 配置管理器（可选）
            is_gui_mode: 是否为GUI模式
        """
        super().__init__()
        print("Initializing MainWindow")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Project root in MainWindow: {self.project_root}")
        
        self.build_flavor = EnvManager.get_build_flavor()

        if config_manager:
            self.config_manager = config_manager
        else:
            self.config_manager = ConfigManager(self.project_root)
            self.config_manager.load_config()
        register_config_manager(self.config_manager)
        
        # 启动时清理临时目录
        self._cleanup_temp_directory()
        
        # 启动时不再自动检查并下载模型，避免强制弹出下载对话框
        
        self.task_manager = TaskManager()
        self.result_manager = ResultManager()
        self.logger = logger or Logger(os.path.join(self.project_root, "logs", "ocr.log"))
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.results_by_filename = {}
        self.results_json_by_filename = {}
        self.processing_thread = None
        self._stop_flag = False
        self.file_map = {}
        self.is_padding_enabled = self.config_manager.get_setting('use_padding', True) # 默认启用
        
        # Async model loader
        self.model_loader_thread = None
        self.loading_progress_bar = None
        self.loading_status_label = None
        self.global_loading_dialog = None

        # Default output directory for global operations
        # 移除全局 output 目录的创建，改为仅在确实需要时（如导出汇总）使用临时目录或用户指定目录
        # self.output_dir = os.path.join(self.project_root, "output")
        # os.makedirs(self.output_dir, exist_ok=True)
        # self.output_dir = None # 除非显式需要，否则不再默认创建
        # 新需求：集中化输出目录
        self.output_dir = os.path.join(self.project_root, "data", "outputs")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 移除 Padding 功能相关的成员变量
        # self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)
        self.is_padding_enabled = False # 强制关闭
        
        # 存储所有文件夹和对应的模板映射
        self.folders = []  # 存储文件夹路径列表
        self.folder_mask_map = {}  # 存储文件夹路径 -> 模板名称的映射
        self.folder_list_items = {}  # 存储文件夹列表项

        # 存储当前选择的模板（用于处理时自动使用）
        self.current_selected_mask = None

        # 初始化OCR组件（延迟加载模式，避免主进程加载模型）
        self.detector = None  # 延迟创建
        self.recognizer = None  # 延迟创建
        
        # 延迟初始化OCR引擎 - UI作为纯粹前端壳子
        # OCR引擎将在首次处理任务时初始化
        print("UI initialized as pure frontend shell - OCR engine will be initialized on demand")

        self.post_processor = post_processor or PostProcessor()
        
        # 初始化图像处理组件
        self.converter = converter or Converter()
        self.preprocessor = preprocessor or Preprocessor()
        self.cropper = cropper or Cropper()
        
        # 初始化文件工具
        self.file_utils = FileUtils()
        
        # 初始化蒙版管理器
        self.mask_manager = MaskManager(self.project_root)
        
        # Initialize Database Controller
        self.database_controller = DatabaseController(self)
        
        # Initialize ProcessManager
        self.process_manager = ProcessManager.get_instance(self.config_manager)
        self.process_manager.start_processes()
        
        # Initialize OCR Service: always use local batch service
        self.ocr_service = OcrBatchService(self)
            
        ServiceRegistry.register("ocr_batch", self.ocr_service)
        
        # 初始化OCR子进程（如果启用）
        self._initialize_ocr_subprocess()
        
        # 初始化 ProcessingController
        self.processing_controller = ProcessingController(
            self.config_manager, self.file_utils, self.mask_manager,
            self.detector, self.recognizer, self.post_processor, self.cropper,
            self.performance_monitor, self.result_manager, self.output_dir
        )
        if PYQT_AVAILABLE:
            self.processing_controller.update_status_signal.connect(self.update_status)
            self.processing_controller.file_processed_signal.connect(self.on_file_processed)
            self.processing_controller.processing_finished_signal.connect(self.on_processing_finished)
        
        # 初始化定时器用于更新UI
        self.update_timer = None
        
        # 根据模式初始化UI
        self.is_gui_mode = is_gui_mode
        self.ui = None
        self.main_window = None
        self.announcement_banner = None
        from app.ui.styles.themes import THEME_DEFINITIONS
        self.theme_definitions = THEME_DEFINITIONS
        
        # 仅在GUI模式下初始化UI组件
        if PYQT_AVAILABLE and self.is_gui_mode:
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
                
                # 初始化蒙版设置状态
                use_mask = self.config_manager.get_setting('use_mask', False)
                # 使用新的 mask_chk 替代旧的 mask_chk_use
                if hasattr(self.ui, 'mask_chk'):
                    self.ui.mask_chk.setChecked(use_mask)
                    # 手动触发一次更新以同步按钮状态
                    self._on_use_mask_changed(use_mask)
                elif hasattr(self.ui, 'mask_chk_use'):
                     self.ui.mask_chk_use.setChecked(use_mask)
                     self._on_use_mask_changed(use_mask)

                # Legacy actionSettings support moved to _connect_signals or ignored if not used


                self._connect_signals()
                # 设置延迟更新模板列表，确保UI完全初始化
                if PYQT_AVAILABLE:
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(100, self._delayed_ui_setup)
                
                # Initialize Screenshot Controller
                self.screenshot_controller = ScreenshotController(self)

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

    def _check_and_download_models(self, is_gui_mode):
        """
        检查并下载缺失的模型
        """
        if not is_gui_mode:
            return
            
        model_manager = self.config_manager.model_manager
        
        # Get configured models from ConfigManager (which respects environment defaults)
        det_key = self.config_manager.get_setting('det_model_key', 'PP-OCRv5_mobile_det')
        rec_key = self.config_manager.get_setting('rec_model_key', 'PP-OCRv5_mobile_rec')
        cls_key = self.config_manager.get_setting('cls_model_key', 'PP-LCNet_x1_0_textline_ori')
        
        # Determine descriptions based on keys
        # Note: We could look up descriptions from model_manager.MODELS but simple mapping is safer if key missing
        det_desc = "检测模型"
        rec_desc = "识别模型"
        cls_desc = "方向分类模型"
        
        # Try to get better descriptions if available
        if det_key in model_manager.MODELS.get('det', {}):
            det_desc = model_manager.MODELS['det'][det_key].get('description', det_desc)
        if rec_key in model_manager.MODELS.get('rec', {}):
            rec_desc = model_manager.MODELS['rec'][rec_key].get('description', rec_desc)
            
        defaults = [
            ('det', det_key, det_desc),
            ('rec', rec_key, rec_desc),
            ('cls', cls_key, cls_desc)
        ]
        
        # Check if table recognition is enabled (Disabled by default now)
        # use_table = self.config_manager.get_setting('use_table_model', False)
        # if use_table:
        #     table_key = self.config_manager.get_setting('table_model_key', 'SLANet')
        #     table_desc = "表格结构识别模型"
        #     if table_key in model_manager.MODELS.get('table', {}):
        #         table_desc = model_manager.MODELS['table'][table_key].get('description', table_desc)
        #     defaults.append(('table', table_key, table_desc))
        
        missing = []
        for m_type, m_key, m_desc in defaults:
            if not model_manager.get_model_dir(m_type, m_key):
                missing.append((m_type, m_key, m_desc))
                
        if not missing:
            return
            
        print(f"Missing models: {missing}")
        
        if PYQT_AVAILABLE:
            from PyQt5.QtWidgets import QApplication
            
            # 确保QApplication已存在
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
                
            # 显示下载对话框
            dialog = ModelDownloadDialog(model_manager, missing)
            if dialog.exec_() != QDialog.Accepted:
                print("User cancelled model download")
                dlg = GlassMessageDialog(
                    self.main_window if PYQT_AVAILABLE else None,
                    title="警告",
                    text="未下载必要模型，本地OCR功能将无法使用！",
                    buttons=[("ok", "确定")],
                )
                dlg.exec_()
            else:
                print("Models downloaded successfully")

    def _delayed_ui_setup(self):
        """延迟执行的UI设置"""
        pass
        # try:
        #     self._setup_masks_file_watcher()
        # except Exception as e:
        #     print(f"Error in delayed masks setup: {e}")
        # try:
        #     self._update_mask_combo()
        # except Exception as e:
        #     print(f"Error in delayed mask combo update: {e}")

    def _initialize_ocr_subprocess(self):
        """初始化OCR子进程"""
        try:
            use_subprocess = self.config_manager.get_setting('use_ocr_subprocess', True)
            if use_subprocess:
                from app.core.ocr_subprocess import get_ocr_subprocess_manager
                subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
                
                # 确定预设配置
                det_key = self.config_manager.get_setting('det_model_key', 'PP-OCRv5_mobile_det')
                rec_key = self.config_manager.get_setting('rec_model_key', 'PP-OCRv5_mobile_rec')
                
                preset = 'custom'
                if (det_key == 'PP-OCRv5_mobile_det' and 
                    rec_key == 'PP-OCRv5_mobile_rec'):
                    preset = 'mobile'
                elif (det_key == 'PP-OCRv5_server_det' and 
                      rec_key == 'PP-OCRv5_server_rec'):
                    preset = 'server'
                
                # 如果是自定义配置，默认使用mobile预设
                if preset == 'custom':
                    preset = 'mobile'
                
                success = subprocess_manager.start_process(preset)
                if success:
                    print(f"OCR子进程初始化成功，预设: {preset}")
                else:
                    print("OCR子进程初始化失败")
        except Exception as e:
            print(f"初始化OCR子进程时出错: {e}")
    
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
        连接UI信号
        """
        print("Connecting UI signals")
        
        # Add Screenshot Mode Action to Menu
        menubar = getattr(self.ui, "menu_bar", None)
        if self.main_window and menubar:
            tools_menu = None
            for action in menubar.actions():
                if action.text() == "工具" or action.text() == "Tools":
                    tools_menu = action.menu()
                    break
            
            if not tools_menu:
                tools_menu = menubar.addMenu("工具")
                
            self.act_screenshot_mode = QAction("自动截屏识别模式 (Auto Screenshot OCR)", self.main_window)
            self.act_screenshot_mode.setCheckable(True)
            self.act_screenshot_mode.setShortcut("Ctrl+Alt+S")
            self.act_screenshot_mode.toggled.connect(self.toggle_screenshot_mode)
            tools_menu.addAction(self.act_screenshot_mode)

        if self.ui and self.main_window:
            if hasattr(self.ui, "window_min_button") and self.ui.window_min_button:
                self.ui.window_min_button.clicked.connect(self.main_window.showMinimized)
            if hasattr(self.ui, "window_max_button") and self.ui.window_max_button:
                def _toggle_max_restore():
                    if self.main_window.isMaximized():
                        self.main_window.showNormal()
                    else:
                        self.main_window.showMaximized()
                self.ui.window_max_button.clicked.connect(_toggle_max_restore)
            if hasattr(self.ui, "window_close_button") and self.ui.window_close_button:
                self.ui.window_close_button.clicked.connect(self.main_window.close)

        if self.ui and self.main_window:
            # 修复：使用 lambda 丢弃 clicked 信号传递的 checked 参数（布尔值）
            # 避免 _start_processing(folders_to_process=True) 这种情况发生
            self.ui.start_button.clicked.connect(lambda: self._start_processing())
            self.ui.stop_button.clicked.connect(self._stop_processing)
            if hasattr(self.ui, 'settings_button'):
                self.ui.settings_button.clicked.connect(self._open_settings_dialog)
            # self.ui.model_selector.currentIndexChanged.connect(self._on_model_changed)
            self.ui.image_list.itemClicked.connect(self._on_image_selected)
            
            # if hasattr(self.ui, 'preprocessing_chk'):
            #     self.ui.preprocessing_chk.stateChanged.connect(self._on_preprocessing_changed)
            # if hasattr(self.ui, 'padding_chk'):
            #     self.ui.padding_chk.stateChanged.connect(self._on_padding_changed)
            
            # Mask connections
            # Removed old mask connections
            if hasattr(self.ui, 'theme_combo'):
                try:
                    self.ui.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
                except Exception:
                    pass
            if hasattr(self.ui, 'background_combo'):
                try:
                    self.ui.background_combo.currentIndexChanged.connect(self._on_background_changed)
                except Exception:
                    pass
            
            # 表格模式：兼容旧下拉框与新单选按钮
            if hasattr(self.ui, 'table_mode_group') and self.ui.table_mode_group:
                try:
                    self.ui.table_mode_group.buttonToggled.connect(self._on_table_mode_button_toggled)
                except Exception:
                    pass
            elif hasattr(self.ui, 'table_mode_combo'):
                try:
                    self.ui.table_mode_combo.currentIndexChanged.connect(self._on_table_mode_changed)
                except Exception:
                    pass
            if hasattr(self.ui, 'ai_advanced_doc_chk'):
                self.ui.ai_advanced_doc_chk.toggled.connect(self._on_ai_advanced_doc_toggled)

            # Mask connections (Simplified)
            if hasattr(self.ui, 'mask_chk'):
                # 断开旧的连接以防万一
                try: self.ui.mask_chk.toggled.disconnect()
                except: pass
                self.ui.mask_chk.toggled.connect(self._on_use_mask_changed)
            
            if hasattr(self.ui, 'mask_btn_enable'):
                try: self.ui.mask_btn_enable.clicked.disconnect()
                except: pass
                # 确保是 checkable
                self.ui.mask_btn_enable.setCheckable(True)
                self.ui.mask_btn_enable.clicked.connect(self._toggle_mask_drawing)
                print("DEBUG: mask_btn_enable connected to _toggle_mask_drawing")
            
            if hasattr(self.ui, 'mask_btn_clear') and hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                try: self.ui.mask_btn_clear.clicked.disconnect()
                except: pass
                self.ui.mask_btn_clear.clicked.connect(self._clear_current_mask)

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
            
            # Database Manager connection
            if hasattr(self.ui, 'db_manager_action'):
                self.ui.db_manager_action.triggered.connect(self._open_db_manager_dialog)

            # Database Import connection (Deprecated)
            # if hasattr(self.ui, 'import_db_action'):
            #     self.ui.import_db_action.triggered.connect(self._open_db_import_dialog)
            
            # Database Query connection
            if hasattr(self.ui, 'query_db_action'):
                self.ui.query_db_action.triggered.connect(self._open_db_query_dialog)

            # Field Binding connection
            if hasattr(self.ui, 'field_binding_action'):
                self.ui.field_binding_action.triggered.connect(self._open_field_binding_dialog)

            # Settings connection
            if hasattr(self.ui, 'settings_action') and self.ui.settings_action:
                self.ui.settings_action.triggered.connect(self._open_settings_dialog)

            # Text Block List connections
            if hasattr(self.ui, 'text_block_list') and self.ui.text_block_list and self.ui.image_viewer:
                # ImageViewer -> TextBlockList
                self.ui.image_viewer.text_blocks_generated.connect(self.ui.text_block_list.set_blocks)
                self.ui.image_viewer.text_block_selected.connect(lambda idx, _: self.ui.text_block_list.select_block(idx))
                self.ui.image_viewer.text_blocks_selected.connect(self.ui.text_block_list.select_blocks)
                self.ui.image_viewer.text_block_hovered.connect(self.ui.text_block_list.set_hovered_block)
                
                # TextBlockList -> ImageViewer
                self.ui.text_block_list.block_selected.connect(self.ui.image_viewer.select_text_block)
                self.ui.text_block_list.selection_changed.connect(self.ui.image_viewer.select_text_blocks)
                self.ui.text_block_list.block_hovered.connect(self.ui.image_viewer.set_hovered_block)

            # ImageViewer 悬停同步到表格视图（表格模式）
            if hasattr(self.ui, 'result_table') and self.ui.result_table and self.ui.image_viewer:
                try:
                    # 注意：仅在表格视图显示表格结果时起作用
                    self.ui.image_viewer.text_block_hovered.connect(
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

    def _setup_masks_file_watcher(self):
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 确保文件存在
        masks_path = self.mask_manager.config_path
        if not os.path.exists(masks_path):
            try:
                with open(masks_path, 'w', encoding='utf-8') as f:
                    json.dump({'masks': {}, 'image_bindings': {}}, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"Error creating masks file: {e}")
                return
                
        # 初始化文件监听器
        self._masks_fs_watcher = QFileSystemWatcher()
        if not self._masks_fs_watcher.addPath(masks_path):
            print(f"Failed to watch masks file: {masks_path}")
            return
            
        # 确保连接信号
        try:
            self._masks_fs_watcher.fileChanged.disconnect()
        except:
            pass
        self._masks_fs_watcher.fileChanged.connect(self._on_masks_file_changed)
        
        # 初始加载一次
        self._on_masks_file_changed(masks_path)

    def _on_masks_file_changed(self, path):
        try:
            # 确保文件存在
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({'masks': {}, 'image_bindings': {}}, f, ensure_ascii=False, indent=4)
                    
            # 重新加载数据
            self.mask_manager.load_masks()
            self._update_mask_combo()
            
            # 更新UI状态
            if self.ui:
                if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                    self.ui.status_bar.set_status("模板文件已更新", self.ui.status_bar.STATUS_INFO)
                elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                    self.ui.status_label.setText("模板文件已更新")
                print(f"模板下拉框已更新，当前模板数量: {len(self.mask_manager.get_all_mask_names())}")
                
            # 重新添加监听（文件修改可能导致监听丢失）
            if hasattr(self, '_masks_fs_watcher') and self._masks_fs_watcher:
                if path not in self._masks_fs_watcher.files():
                    self._masks_fs_watcher.addPath(path)
                    
        except Exception as e:
            print(f"Error handling masks file change: {e}")
            if self.ui:
                if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                    self.ui.status_bar.set_status(f"模板更新失败: {str(e)}", self.ui.status_bar.STATUS_ERROR)
                elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                    self.ui.status_label.setText(f"模板更新失败: {str(e)}")

    def _on_use_mask_changed(self, state):
        # Fix: toggled signal emits bool, stateChanged emits int.
        # Since we use toggled for QCheckBox in connect_signals, state is bool.
        # But bool is subclass of int, so isinstance(True, int) is True.
        # True != Qt.Checked (2), so it was always False.
        # We should just use bool(state) if it's boolean or compare to Qt.Checked if it's strictly int (not bool).
        if isinstance(state, bool):
            is_checked = state
        else:
            is_checked = (state == Qt.Checked)
            
        print(f"DEBUG: Mask checkbox changed to {is_checked} (Raw state: {state})")
        
        self.config_manager.set_setting('use_mask', is_checked)
        self.config_manager.save_config()
        
        # 更新按钮启用状态
        # 注意：不要禁用 mask_chk 自身，否则用户无法重新开启
        if hasattr(self.ui, 'mask_btn_enable'):
            self.ui.mask_btn_enable.setEnabled(is_checked)
            # 强制刷新样式，确保视觉状态更新
            self.ui.mask_btn_enable.style().unpolish(self.ui.mask_btn_enable)
            self.ui.mask_btn_enable.style().polish(self.ui.mask_btn_enable)
            
            # 如果禁用了，确保退出绘制模式
            if not is_checked:
                if self.ui.mask_btn_enable.isChecked():
                    self.ui.mask_btn_enable.setChecked(False)
                if self.ui.image_viewer:
                     self.ui.image_viewer.start_mask_mode(False)
                self.ui.mask_btn_enable.setText("开始绘制")

        if hasattr(self.ui, 'mask_btn_clear'):
            self.ui.mask_btn_clear.setEnabled(is_checked)
            self.ui.mask_btn_clear.style().unpolish(self.ui.mask_btn_clear)
            self.ui.mask_btn_clear.style().polish(self.ui.mask_btn_clear)
            
        # 如果禁用了蒙版裁剪，清除当前图像上的蒙版
        if not is_checked and self.ui.image_viewer:
            self.ui.image_viewer.clear_masks()
            # 同时清除当前选中的蒙版记录
            self.current_selected_mask = None
            if hasattr(self, 'image_masks'):
                self.image_masks = {}
            if hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText("已禁用蒙版裁剪并清除当前蒙版")

    def _toggle_mask_drawing(self, checked):
        """切换蒙版绘制模式"""
        if self.ui.image_viewer:
            self.ui.image_viewer.start_mask_mode(checked)
            msg = "蒙版绘制模式已开启，请在图像上拖动选择区域" if checked else "蒙版绘制模式已关闭"
            
            # 记录当前绘制的蒙版（如果是关闭绘制模式）
            if not checked and self.ui.image_viewer.has_mask():
                try:
                    # 自动保存到 image_masks
                    if hasattr(self, 'current_image_path') and self.current_image_path:
                        if not hasattr(self, 'image_masks'):
                            self.image_masks = {}
                        self.image_masks[self.current_image_path] = self.ui.image_viewer.get_mask_data()
                except Exception:
                    pass
            
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(msg, self.ui.status_bar.STATUS_INFO)
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText(msg)
            
            # 更新按钮文本
            if hasattr(self.ui, 'mask_btn_enable'):
                if checked:
                    self.ui.mask_btn_enable.setText("停止绘制")
                else:
                    self.ui.mask_btn_enable.setText("开始绘制")

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

    def _on_table_mode_changed(self, index):
        """
        处理表格模式下拉框变化
        0: 关闭
        1: 传统表格拆分
        2: AI 表格结构识别
        """
        use_table_split = False
        use_ai_table = False

        if index == 1:
            use_table_split = True
        elif index == 2:
            use_ai_table = True

        self.config_manager.set_setting('use_table_split', use_table_split)
        self.config_manager.set_setting('use_ai_table', use_ai_table)

        if hasattr(self.ui, 'ai_table_model_combo'):
            self.ui.ai_table_model_combo.setEnabled(use_ai_table)
        if hasattr(self.ui, 'ai_advanced_doc_chk'):
            self.ui.ai_advanced_doc_chk.setEnabled(use_ai_table)
        if hasattr(self.ui, 'ai_options_container'):
            # 当 AI 模式未开启时，整块区域明显蒙灰，同时保证文字仍可读
            self.ui.ai_options_container.setEnabled(use_ai_table)
            if use_ai_table:
                # 启用时恢复主题默认样式
                self.ui.ai_options_container.setStyleSheet("")
            else:
                # 禁用时使用偏深的灰色蒙层 + 略偏浅的文字颜色，避免“全黑看不见”
                self.ui.ai_options_container.setStyleSheet("""
                    #ai_options_container {
                        background-color: rgba(40, 40, 40, 190);
                        border-radius: 4px;
                    }
                    #ai_options_container QLabel,
                    #ai_options_container QCheckBox {
                        color: #CCCCCC;
                    }
                    #ai_options_container QComboBox {
                        color: #CCCCCC;
                        background-color: rgba(30, 30, 30, 220);
                        border: 1px solid rgba(80, 80, 80, 255);
                    }
                """)

        self.config_manager.save_config()

    def _on_table_mode_button_toggled(self, button, checked):
        """
        表格模式单选按钮变化时的处理
        """
        if not checked or not hasattr(self.ui, 'table_mode_group') or not self.ui.table_mode_group:
            return
        try:
            index = self.ui.table_mode_group.id(button)
        except Exception:
            index = 0
        self._on_table_mode_changed(index)

    def _on_ai_advanced_doc_toggled(self, checked):
        """
        处理 AI 表格结构识别下的高级文档理解（公式/图表）从功能开关
        """
        self.config_manager.set_setting('enable_advanced_doc', checked)
        self.config_manager.save_config()

    def _sync_table_split_state(self):
        """
        同步表格模式状态（兼容旧配置）
        """
        use_table_split = self.config_manager.get_setting('use_table_split', False)
        use_ai_table = self.config_manager.get_setting('use_ai_table', False)
        if use_ai_table:
            index = 2
        elif use_table_split:
            index = 1
        else:
            index = 0

        if hasattr(self.ui, 'table_mode_group') and self.ui.table_mode_group:
            group = self.ui.table_mode_group
            try:
                group.blockSignals(True)
                if index == 2 and hasattr(self.ui, 'table_mode_ai_radio') and self.ui.table_mode_ai_radio:
                    self.ui.table_mode_ai_radio.setChecked(True)
                elif index == 1 and hasattr(self.ui, 'table_mode_split_radio') and self.ui.table_mode_split_radio:
                    self.ui.table_mode_split_radio.setChecked(True)
                elif hasattr(self.ui, 'table_mode_off_radio') and self.ui.table_mode_off_radio:
                    self.ui.table_mode_off_radio.setChecked(True)
            finally:
                group.blockSignals(False)
            self._on_table_mode_changed(index)
        elif hasattr(self.ui, 'table_mode_combo'):
            try:
                self.ui.table_mode_combo.blockSignals(True)
                self.ui.table_mode_combo.setCurrentIndex(index)
            finally:
                self.ui.table_mode_combo.blockSignals(False)
            self._on_table_mode_changed(index)

    def _on_preprocessing_changed(self, state):
        is_enabled = (state == Qt.Checked)
        self.config_manager.set_setting('use_preprocessing', is_enabled)
        self.config_manager.save_config()

    def _on_padding_changed(self, state):
        # 功能已移除，仅保留空函数以防信号连接报错
        self.is_padding_enabled = False
        self.config_manager.set_setting('use_padding', False)
        self.config_manager.save_config()
        
    # Removed old mask methods: _toggle_mask_drawing, _save_new_mask, _rename_mask, _delete_mask, _export_masks, _open_mask_manager_dialog
    # These are replaced by simplified mask logic.


    def _clear_current_mask(self):
        """清除当前图片的蒙版"""
        if self.ui and hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            self.ui.image_viewer.clear_masks()
            
            # 同时清除内存中的记录
            if hasattr(self, 'current_image_path') and self.current_image_path:
                if hasattr(self, 'image_masks') and self.current_image_path in self.image_masks:
                    del self.image_masks[self.current_image_path]
            
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status("已清除当前图片蒙版", self.ui.status_bar.STATUS_SUCCESS)

    def on_mask_updated(self, mask_data):
        """当蒙版数据更新时（绘制完成）"""
        if not hasattr(self, 'image_masks'):
            self.image_masks = {}
            
        if hasattr(self, 'current_image_path') and self.current_image_path:
            self.image_masks[self.current_image_path] = mask_data

        
    def _apply_selected_mask(self):
        """应用选中的模板（弹窗模式）"""
        selected_display_name = self._show_mask_selection_dialog()
        if selected_display_name:
            if selected_display_name == "不应用模板":
                if self.ui and hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                    self.ui.image_viewer.clear_masks()
                    self.ui.status_label.setText("已清除蒙版")
                self.current_selected_mask = None
                if self.ui and hasattr(self.ui, 'folder_list') and self.ui.folder_list:
                    current_folder_item = self.ui.folder_list.currentItem()
                    if current_folder_item:
                        directory = current_folder_item.data(Qt.UserRole)
                        if not directory:
                             directory = self.folder_list_items.get(current_folder_item.text())
                        
                        if directory and directory in self.folder_mask_map:
                            del self.folder_mask_map[directory]
                            if hasattr(self.ui, 'status_label') and self.ui.status_label:
                                self.ui.status_label.setText(f"已清除文件夹 '{os.path.basename(directory)}' 的模板")
                            self._update_folder_mask_display(directory)
            else:
                current_name = self._get_original_mask_name(selected_display_name)
                mask_data = self.mask_manager.get_mask(current_name)
                if mask_data and self.ui and hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                    self.ui.image_viewer.set_mask_data(mask_data)
                    if hasattr(self.ui, 'status_label') and self.ui.status_label:
                        self.ui.status_label.setText(f"已应用蒙版 '{selected_display_name}'")
                self.current_selected_mask = mask_data
                if self.ui and hasattr(self.ui, 'folder_list') and self.ui.folder_list:
                    current_folder_item = self.ui.folder_list.currentItem()
                    if current_folder_item:
                        directory = current_folder_item.data(Qt.UserRole)
                        if not directory:
                             directory = self.folder_list_items.get(current_folder_item.text())

                        if directory:
                            self.folder_mask_map[directory] = current_name
                            if hasattr(self.ui, 'status_label') and self.ui.status_label:
                                self.ui.status_label.setText(f"已将模板 '{selected_display_name}' 应用于文件夹 '{os.path.basename(directory)}'")
                            self._update_folder_mask_display(directory)

    def _update_mask_combo(self):
        """刷新蒙版下拉列表"""
        if not self.ui or not hasattr(self.ui, 'mask_combo') or self.ui.mask_combo is None:
            return
        current = self.ui.mask_combo.currentText()
        self.ui.mask_combo.clear()
        names = self.mask_manager.get_all_mask_names()
        self.ui.mask_combo.addItems(names)
        if current in names:
            self.ui.mask_combo.setCurrentText(current)
        elif names:
            self.ui.mask_combo.setCurrentIndex(0)
        
    def _get_original_mask_name(self, display_name):
        """获取显示名称对应的原始名称"""
        if hasattr(self, '_mask_name_mapping'):
            return self._mask_name_mapping.get(display_name, display_name)
        return display_name
        
    def _get_current_mask_display_name(self):
        """获取当前选中的模板显示名称"""
        if not self.ui or not hasattr(self.ui, 'mask_combo') or self.ui.mask_combo is None:
            return ""
        return self.ui.mask_combo.currentText()
    
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
                                        name = f"{base_no_ext}_page_{i+1}"
                                        vpath = f"{fp}|page={i+1}"
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
                        
                        if is_valid and local_path not in self.folders:
                            self.folders.append(local_path)
                            
                            # Add to UI
                            name = os.path.basename(local_path)
                            item = QListWidgetItem(name)
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(Qt.Checked)
                            item.setData(Qt.UserRole, local_path)
                            item.setToolTip(local_path)
                            
                            self.ui.folder_list.addItem(item)
                            self.folder_list_items[name] = local_path
                            added_count += 1

                            
                    if added_count > 0:
                        self.ui.status_label.setText(f"已添加 {added_count} 个项目")
                        
                    event.acceptProposedAction()
                    return True

        except Exception as e:
            print(f"Error handling drag-drop: {e}")
        return False

    def _on_model_changed(self, index):
        """
        模型选择改变时的处理
        
        Args:
            index: 选中的索引
        """
        model_names = ["默认模式", "高精度模式", "快速模式"]
        if index >= 0 and index < len(model_names):
            model_name = model_names[index]
            self.logger.info(f"切换到模式: {model_name}")
            
            # Apply presets based on selection
            if index == 0: # Default
                # Reset to reasonable defaults
                self.config_manager.set_setting('det_limit_side_len', 960)
                self.config_manager.set_setting('det_db_thresh', 0.3)
                self.config_manager.set_setting('det_db_box_thresh', 0.6)
                self.config_manager.set_setting('det_db_unclip_ratio', 1.5)
                # self.config_manager.set_setting('use_skew_correction', False) # Keep user preference or default? Let's reset for consistency
                
            elif index == 1: # High Accuracy
                # Optimize for accuracy
                self.config_manager.set_setting('det_limit_side_len', 1280) # Larger processing size
                self.config_manager.set_setting('det_db_thresh', 0.2) # Lower threshold to catch faint text
                self.config_manager.set_setting('det_db_box_thresh', 0.4)
                self.config_manager.set_setting('det_db_unclip_ratio', 1.8)
                # self.config_manager.set_setting('use_skew_correction', True) # Enable angle classification
                
            elif index == 2: # Fast
                # Optimize for speed
                self.config_manager.set_setting('det_limit_side_len', 640) # Smaller processing size
                self.config_manager.set_setting('det_db_thresh', 0.3)
                # self.config_manager.set_setting('use_skew_correction', False)
            
            # Save these temporary configs? Or just keep in memory? 
            # Ideally config_manager.set_setting updates memory and save_config saves to disk.
            # We probably want to save it so next time it remembers.
            self.config_manager.save_config()

            print(f"Reloading local OCR engine for {model_name}...")
            try:
                self.detector = Detector(self.config_manager)
                self.recognizer = Recognizer(self.config_manager)
                if hasattr(self.ui, 'status_label'):
                    self.ui.status_label.setText(f"已切换到: {model_name}")
            except Exception as e:
                print(f"Error reloading OCR engine: {e}")
                if hasattr(self.ui, 'status_label'):
                    self.ui.status_label.setText(f"切换失败: {e}")

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
            
            # 初始化状态
            use_mask = self.config_manager.get_setting('use_mask', False)
            if hasattr(self.ui, 'mask_chk'):
                self.ui.mask_chk.setChecked(use_mask)
            elif hasattr(self.ui, 'mask_chk_use'):
                self.ui.mask_chk_use.setChecked(use_mask)

            if hasattr(self.ui, 'ai_table_model_combo'):
                model = self.config_manager.get_setting('ai_table_model', 'SLANet')
                idx = 1 if model == 'SLANet_en' else 0
                self.ui.ai_table_model_combo.setCurrentIndex(idx)

            if hasattr(self.ui, 'ai_advanced_doc_chk'):
                enable_advanced = self.config_manager.get_setting('enable_advanced_doc', False)
                self.ui.ai_advanced_doc_chk.setChecked(enable_advanced)
            
            # 延迟更新蒙版列表，确保UI完全显示
            if PYQT_AVAILABLE:
                QTimer.singleShot(100, self._sync_table_split_state)
                # QTimer.singleShot(500, self._update_mask_combo)
            else:
                pass
                # self._update_mask_combo()
            
            # 启动定时器定期更新UI
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self._update_ui_status)
            self.update_timer.start(1000)  # 每秒更新一次
            
            self.main_window.show()
            print("Main window shown")
        else:
            print("Cannot show window: UI not available")

    def _update_ui_with_directories(self):
        """
        更新UI显示当前目录信息
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 更新状态栏显示目录信息
        folder_count = len(self.folders)
        status_text = f"已加载 {folder_count} 个文件夹"
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status(status_text, self.ui.status_bar.STATUS_INFO)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText(status_text)
        
        # 更新图像列表
        self._update_image_list()

    def _update_image_list(self):
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


    def _update_ui_status(self):
        """
        定期更新UI状态
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 这里可以添加更多状态更新逻辑
        # 例如: 更新进度条、显示处理状态等
        pass

    pass

    pass

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
        Slot called when models are successfully reloaded
        """
        print("Models reloaded successfully")
        self.detector = detector
        self.recognizer = recognizer
        
        # Hide progress
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

        # 底部状态栏提示
        if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
            self.ui.status_bar.set_status("正在加载模型，请稍候...", self.ui.status_bar.STATUS_WORKING)
        elif hasattr(self.ui, 'status_label') and self.ui.status_label:
            self.ui.status_label.setText("正在加载模型，请稍候...")

        # 可选：锁定设置对话框的交互
        try:
            dialog.setEnabled(False)
        except Exception:
            pass

        # 确保旧线程结束
        if self.model_loader_thread and self.model_loader_thread.isRunning():
            self.model_loader_thread.terminate()
            self.model_loader_thread.wait()

        # 启动新的模型加载线程
        self.model_loader_thread = ModelLoaderThread(self.config_manager)

        from functools import partial
        self.model_loader_thread.finished_signal.connect(
            partial(self._on_models_reloaded_from_settings, dialog, changed_model_types)
        )
        self.model_loader_thread.error_signal.connect(
            partial(self._on_model_load_error_from_settings, dialog, changed_model_types)
        )
        self.model_loader_thread.start()

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
        """
        print(f"Starting batch processing of folders (force_reprocess={force_reprocess})")
        
        # Collect folders
        if folders_to_process is None:
            folders_to_process = []
            if PYQT_AVAILABLE and self.ui and self.ui.folder_list:
                for i in range(self.ui.folder_list.count()):
                    item = self.ui.folder_list.item(i)
                    if item and item.checkState() == Qt.Checked:
                        directory = item.data(Qt.UserRole)
                        if not directory:
                            directory = self.folder_list_items.get(item.text())
                        if directory:
                            folders_to_process.append(directory)
            else:
                folders_to_process = self.folders
        
        if not folders_to_process:
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
            self.ui.start_button.setEnabled(False)
            self.ui.stop_button.setEnabled(True)
            if hasattr(self.ui, 'status_bar'):
                self.ui.status_bar.set_status(f"正在准备处理 {len(folders_to_process)} 个文件夹", self.ui.status_bar.STATUS_WORKING)
            
            # Save settings
            self.config_manager.set_setting('use_preprocessing', False)
            self.config_manager.save_config()

        self.results_by_filename = {}
        self.performance_monitor.reset()
        
        # Pass folder mask map to controller
        self.processing_controller.set_folder_mask_map(self.folder_mask_map)
        
        # Start processing via controller
        self.processing_controller.start_processing(folders_to_process, force_reprocess=force_reprocess)

    def _start_processing_files(self, files, force_reprocess=False, default_mask_data=None):
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
            
            # Save table settings if UI available (reusing logic)
            self._save_table_settings()

        self.performance_monitor.reset()
        
        # Interactive mask selection logic
        if default_mask_data is None and self.config_manager.get_setting('use_mask', False) and self.ui:
             if hasattr(self, 'current_selected_mask') and self.current_selected_mask:
                 default_mask_data = self.current_selected_mask
             elif self.config_manager.get_setting('interactive_selection', False):
                 current_mask_name = self._show_mask_selection_dialog()
                 if current_mask_name:
                     original_name = self._get_original_mask_name(current_mask_name)
                     default_mask_data = self.mask_manager.get_mask(original_name)

        # Start processing via controller
        self.processing_controller.start_processing(files, force_reprocess, default_mask_data)

    def _save_table_settings(self):
        """Helper to save table related settings from UI"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
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
            use_ai_table = (index == 2)
            self.config_manager.set_setting('use_table_split', use_table_split)
            self.config_manager.set_setting('use_ai_table', use_ai_table)
            if use_table_split:
                self.config_manager.set_setting('table_split_mode', 'cell')

        if hasattr(self.ui, 'ai_table_model_combo'):
            idx = self.ui.ai_table_model_combo.currentIndex()
            ai_table_model = 'SLANet' if idx == 0 else 'SLANet_en'
            self.config_manager.set_setting('ai_table_model', ai_table_model)

        if hasattr(self.ui, 'ai_advanced_doc_chk'):
            enable_advanced = bool(self.ui.ai_advanced_doc_chk.isChecked())
            self.config_manager.set_setting('enable_advanced_doc', enable_advanced)
        
        self.config_manager.save_config()

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
        # Try to load JSON cache to keep in sync if available
        # Note: ProcessingController saves JSON before emitting signal
        
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
        print("Stopping image processing")
        self._stop_flag = True
        self.processing_controller.stop()
            
        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(True)
            self.ui.stop_button.setEnabled(False)
            if hasattr(self.ui, 'status_bar'):
                self.ui.status_bar.set_status("处理已停止", self.ui.status_bar.STATUS_WARNING)



    def _display_result_for_item(self, item):
        if not item:
            return
        self._display_result_for_filename(item.text())

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
        # 如果内存中有text但没有json_data，也尝试加载json以补充
        if (not text or not json_data) and filename in self.file_map:
            image_path = self.file_map[filename]
            t2 = time.perf_counter()
            try:
                base_dir = os.path.dirname(image_path)
                base_name = os.path.splitext(filename)[0]
                
                # json_path = os.path.join(base_dir, "output", "json", f"{base_name}.json")
                
                # 新逻辑：从集中化目录加载
                parent_dir_name = os.path.basename(os.path.dirname(image_path))
                current_output_dir = os.path.join(self.output_dir, parent_dir_name)
                json_path = os.path.join(current_output_dir, "json", f"{base_name}.json")
                
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not text:
                            text = data.get('full_text', '')
                        if not json_data:
                            json_data = data
                
                if not text:
                    # txt_path = os.path.join(base_dir, "output", "txt", f"{base_name}_result.txt")
                    txt_path = os.path.join(current_output_dir, "txt", f"{base_name}_result.txt")
                    if os.path.exists(txt_path):
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            text = f.read()
                            
                if text:
                    self.results_by_filename[filename] = text
                    self.result_manager.store_result(image_path, text)
                    print(f"Loaded cached result for {filename}")
                
                if json_data:
                    self.results_json_by_filename[filename] = json_data
                    
            except Exception as e:
                print(f"Error loading cache for {filename}: {e}")
            finally:
                t3 = time.perf_counter()
                print(f"PERF[_display_result_for_filename] disk_load {filename}: {(t3 - t2) * 1000:.1f} ms")
                
        self.ui.result_display.setPlainText(text)

        # 为所有导出视图设置基础文件名（无论是否有表格信息）
        try:
            base_name_for_export = os.path.splitext(filename)[0]
        except Exception:
            base_name_for_export = filename
        if hasattr(self.ui, "result_table") and self.ui.result_table and hasattr(self.ui.result_table, "set_export_basename"):
            self.ui.result_table.set_export_basename(base_name_for_export)
        if hasattr(self.ui, "text_block_list") and self.ui.text_block_list and hasattr(self.ui.text_block_list, "set_export_basename"):
            self.ui.text_block_list.set_export_basename(base_name_for_export)
        
        # 准备显示数据
        t4 = time.perf_counter()
        items = []
        fields = []
        
        if json_data and 'regions' in json_data:
            regions = json_data['regions']
            for r in regions:
                box = None
                coords = r.get('coordinates')
                if coords is not None and len(coords) > 0:
                    try:
                        if len(coords) == 4 and isinstance(coords[0], list):
                            xs = [p[0] for p in coords]
                            ys = [p[1] for p in coords]
                            box = [min(xs), min(ys), max(xs), max(ys)]
                        elif len(coords) == 4 and isinstance(coords[0], (int, float)):
                            box = coords
                    except Exception:
                        pass
                        
                item = {
                    'text': r.get('text', ''),
                    'box': box,
                    'is_empty': False,
                    'original_data': r
                }
                items.append(item)
            
            fields = [('content', '内容')]
        elif text:
            lines = [line for line in text.split('\n') if line.strip()]
            items = [{'text': line, 'box': None, 'is_empty': False, 'original_data': None} for line in lines]
            fields = [('content', '内容')]

        t5 = time.perf_counter()
        print(f"PERF[_display_result_for_filename] build_items {filename}: {(t5 - t4) * 1000:.1f} ms (items={len(items)})")

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

        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            if has_table_info:
                if hasattr(self.ui.image_viewer, 'is_table_mode'):
                    self.ui.image_viewer.is_table_mode = True
                if hasattr(self.ui.image_viewer, 'show_text_mask'):
                    self.ui.image_viewer.show_text_mask = False
                self.ui.image_viewer.set_ocr_results([])
            else:
                if hasattr(self.ui.image_viewer, 'is_table_mode'):
                    self.ui.image_viewer.is_table_mode = False
                if hasattr(self.ui.image_viewer, 'show_text_mask'):
                    self.ui.image_viewer.show_text_mask = True
                self.ui.image_viewer.set_ocr_results(items)

        if hasattr(self.ui, 'result_table') and self.ui.result_table and hasattr(self.ui, 'struct_view_stack'):
            if has_table_info:
                self.ui.result_table.set_data(table_cells)
                index = self.ui.struct_view_stack.indexOf(self.ui.result_table)
                if index != -1:
                    self.ui.struct_view_stack.setCurrentIndex(index)
            else:
                self.ui.result_table.set_data([])
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
        
        # 移除“重新处理所在目录”功能（已移动到目录列表右键菜单）
        # menu.addSeparator()
        # reprocess_dir_action = menu.addAction("强制重新处理所在目录")
        # reprocess_dir_action.triggered.connect(self.reprocess_current_directory)
        
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

        # 自动确定蒙版数据（优先使用当前选中的蒙版或临时绘制的蒙版）
        mask_data = None
        
        # 1. 优先检查 ImageViewer 是否有正在绘制但未保存的蒙版
        # 如果用户正在绘制，直接获取当前绘制的内容作为临时蒙版
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer and self.ui.image_viewer.has_mask():
            try:
                # 无论是否处于“蒙版绘制模式”，只要图上有框，就拿来用
                temp_mask = self.ui.image_viewer.get_mask_data()
                if temp_mask:
                    mask_data = temp_mask
                    # 也可以顺便更新一下全局状态，方便后续使用
                    self.current_selected_mask = mask_data
                    self._update_current_mask_label("临时绘制蒙版")
                    print("Using temporary drawn mask for reprocessing")
            except Exception as e:
                print(f"Failed to get temporary mask: {e}")

        # 2. 如果图上没有，再看有没有已选中的全局蒙版
        if mask_data is None and hasattr(self, 'current_selected_mask') and self.current_selected_mask:
            mask_data = self.current_selected_mask
        
        # 即使没有选中特定蒙版，_start_processing_files 内部也会尝试查找文件绑定的蒙版
        # 所以这里传递 None 也是安全的，或者传递当前全局选中的蒙版
        
        print(f"Reprocessing {len(files_to_process)} files with mask_data={mask_data}")
        self._start_processing_files(files_to_process, force_reprocess=True, default_mask_data=mask_data)

    def _on_image_selected(self, item):
        if item:
            name = item.text()
            if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                path = self.file_map.get(name, None)
                if path:
                    self.ui.image_viewer.display_image(path)
        
        self._display_result_for_item(item)
        pass

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
        if directory and directory not in self.folders:
            self.folders.append(directory)
            
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
            self.folder_list_items[folder_name] = directory
            # 修复：同时存储完整路径作为 key，确保双重索引
            self.folder_list_items[directory] = directory
            self._update_folder_mask_display(directory)
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(f"已添加文件夹: {folder_name}", self.ui.status_bar.STATUS_INFO)
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText(f"已添加文件夹: {folder_name}")

    def _remove_selected_folder(self):
        """移除选中的项目(文件/文件夹)"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        current_item = self.ui.folder_list.currentItem()
        if current_item:
            # 优先使用 UserRole 获取路径
            path = current_item.data(Qt.UserRole)
            name = current_item.text()
            
            if not path and name in self.folder_list_items:
                 path = self.folder_list_items[name]

            if path:
                if path in self.folders:
                    self.folders.remove(path)
                # 清理相关映射
                keys_to_remove = [k for k, v in self.folder_list_items.items() if v == path]
                for k in keys_to_remove:
                    del self.folder_list_items[k]
                if path in self.folder_mask_map:
                    del self.folder_mask_map[path]
            
            row = self.ui.folder_list.row(current_item)
            self.ui.folder_list.takeItem(row)
            if hasattr(self.ui, 'status_bar') and self.ui.status_bar:
                self.ui.status_bar.set_status(f"已移除: {name}", self.ui.status_bar.STATUS_INFO)
            elif hasattr(self.ui, 'status_label') and self.ui.status_label:
                self.ui.status_label.setText(f"已移除: {name}")

            # 如果已经没有任何项目，则恢复到“无图片”初始状态
            if self.ui.folder_list.count() == 0:
                self._clear_all_folders()

    def _clear_all_folders(self):
        """清空所有项目"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 清空内部数据（即使当前 self.folders 已经是空的也安全）
        self.folders.clear()
        self.folder_list_items.clear()
        self.folder_mask_map.clear()
        self.file_map.clear()
        self.results_by_filename.clear()
        self.results_json_by_filename.clear()

        # 清空目录与文件列表
        if hasattr(self.ui, 'folder_list') and self.ui.folder_list:
            self.ui.folder_list.clear()
        if hasattr(self.ui, 'image_list') and self.ui.image_list:
            self.ui.image_list.clear()

        # 重置图像区域为“无图片”状态
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            viewer = self.ui.image_viewer
            try:
                viewer.set_ocr_results([])
            except Exception:
                pass
            try:
                viewer.clear_masks()
            except Exception:
                pass
            if hasattr(viewer, "pixmap"):
                viewer.pixmap = None
                viewer.image_size = None
                viewer.zoom_factor = 1.0
                viewer.pan_offset = QPoint(0, 0)
            viewer.update()

        # 清空文本结果与表格结果
        if hasattr(self.ui, 'result_display') and self.ui.result_display:
            self.ui.result_display.clear()

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
            
            # 显示当前文件夹的模板设置
            self._update_folder_mask_display(directory)
            
            # 根据文件夹模板更新预览蒙版
            if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                mask_name = self.folder_mask_map.get(directory)
                if mask_name:
                    mask_data = self.mask_manager.get_mask(mask_name)
                    self.ui.image_viewer.set_mask_data(mask_data)
                else:
                    self.ui.image_viewer.clear_masks()

    def _update_folder_mask_display(self, directory):
        """更新文件夹模板显示"""
        if not PYQT_AVAILABLE or not self.ui or not hasattr(self.ui, 'folder_list'):
            return
        
        for i in range(self.ui.folder_list.count()):
            item = self.ui.folder_list.item(i)
            item_dir = item.data(Qt.UserRole)
            if not item_dir:
                item_dir = self.folder_list_items.get(item.text())
            if item_dir == directory:
                base_name = os.path.basename(directory) or directory
                if directory in self.folder_mask_map:
                    mask_name = self.folder_mask_map[directory]
                    display_text = f"{base_name}  [{mask_name}]"
                    item.setToolTip(display_text)
                    item.setText(display_text)
                else:
                    item.setToolTip("")
                    item.setText(base_name)
                break

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


    def _enable_mask_mode(self):
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            self.ui.image_viewer.start_mask_mode(True)
            if PYQT_AVAILABLE and self.ui:
                self.ui.status_label.setText("蒙版绘制模式：拖拽选择区域后点击保存蒙版")

    def _update_current_mask_label(self, mask_name):
        """更新当前选择的模板显示标签"""
        if not PYQT_AVAILABLE or not self.ui or not hasattr(self.ui, 'current_mask_label'):
            return
            
        if mask_name == "无" or mask_name is None:
            self.ui.current_mask_label.setText("当前模板: 无")
        else:
            self.ui.current_mask_label.setText(f"当前模板: {mask_name}")

    def _save_default_mask(self):
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            ratios = self.ui.image_viewer.get_mask_coordinates_ratios()
            if ratios and len(ratios) == 4:
                text = ",".join(f"{r:.6f}" for r in ratios)
                self.config_manager.set_setting('default_coordinates', text)
                self.config_manager.set_setting('use_mask', True)
                self.config_manager.save_config()
                if PYQT_AVAILABLE and self.ui:
                    self.ui.status_label.setText("默认蒙版已保存")

    def _open_db_manager_dialog(self):
        """打开数据库管理对话框"""
        self.database_controller.open_db_manager_dialog()

    def _open_db_import_dialog(self):
        """打开数据库导入对话框"""
        self.database_controller.open_db_import_dialog()

    def _open_field_binding_dialog(self):
        """打开可视化字段绑定工作台"""
        self.database_controller.open_field_binding_dialog()

    def _open_db_query_dialog(self):
        """打开数据库查询对话框"""
        self.database_controller.open_db_query_dialog()

    def toggle_screenshot_mode(self, enabled):
        """Toggle Screenshot Auto-OCR Mode"""
        self.screenshot_controller.toggle_screenshot_mode(enabled)

    def _stop_screenshot_mode_action(self):
        """Action for tray menu to stop screenshot mode"""
        if hasattr(self, 'act_screenshot_mode') and self.act_screenshot_mode.isChecked():
            self.act_screenshot_mode.setChecked(False)
        else:
            self.toggle_screenshot_mode(False)

    def _restore_from_tray(self):
        """Restore main window from tray"""
        if hasattr(self, 'act_screenshot_mode') and self.act_screenshot_mode.isChecked():
             self.act_screenshot_mode.setChecked(False)
        
        # Fallback ensure window is shown
        if self.main_window and not self.main_window.isVisible():
            self.main_window.showNormal()
            self.main_window.activateWindow() 

    def _on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    def process_clipboard_image(self, qimage):
        """Handle new image from clipboard"""
        self.logger.info("Detected new clipboard image, starting OCR...")
        if self.floating_widget:
            self.floating_widget.set_text("正在识别... / Recognizing...")
            self.floating_widget.show()
            
        threading.Thread(target=self._run_ocr_on_image, args=(qimage,)).start()

    def _run_ocr_on_image(self, qimage):
        """Run OCR in background thread"""
        try:
            # Convert QImage to PIL Image
            from PIL import Image
            import io
            from PyQt5.QtCore import QBuffer, QIODevice
            
            buffer = QBuffer()
            buffer.open(QIODevice.ReadWrite)
            qimage.save(buffer, "PNG")
            pil_img = Image.open(io.BytesIO(buffer.data()))
            
            # Check if we have detector
            if not self.detector:
                self.detector = Detector(self.config_manager)
            
            # Use detector to detect (and implicitly recognize if configured)
            # detect_text_regions returns list of dicts: {'text': ..., 'confidence': ...}
            regions = self.detector.detect_text_regions(pil_img)
            
            # Extract text
            full_text = ""
            if regions:
                lines = [r['text'] for r in regions if 'text' in r]
                full_text = "\n".join(lines)
            else:
                full_text = "未检测到文本 / No text detected"
                
            self.ocr_result_ready_signal.emit(full_text)
                
        except Exception as e:
            self.logger.error(f"Screenshot OCR failed: {e}")
            import traceback
            traceback.print_exc()
            self.ocr_result_ready_signal.emit(f"Error: {e}")

    def _on_ocr_result_ready(self, text):
        """Update floating widget with result"""
        if self.floating_widget:
            self.floating_widget.set_text(text)

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
        
        # 停止定时器
        if PYQT_AVAILABLE and hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
            
        if PYQT_AVAILABLE and hasattr(self, 'check_progress_timer') and self.check_progress_timer:
            self.check_progress_timer.stop()
        
        # Stop clipboard watcher
        if hasattr(self, 'clipboard_watcher') and self.clipboard_watcher:
            self.clipboard_watcher.stop()

    # Legacy close method kept for compatibility but redirects to quit_application
    def close(self):
        self.quit_application()
