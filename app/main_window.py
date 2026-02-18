# -*- coding: utf-8 -*-

"""
主窗口（集成所有UI组件和交互逻辑）
"""

import os
import threading
import json
from datetime import datetime
import time

from app.core.process_manager import ProcessManager
from app.core.mask_manager import MaskManager
from app.core.service_registry import ServiceRegistry
from app.core.clipboard_watcher import ClipboardWatcher
from app.ocr.engine import OcrEngine

try:
    from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QInputDialog, QListWidgetItem, QDialog, QTabWidget, QAction, QSystemTrayIcon, QMenu, QApplication, QStyle, QCheckBox, QProgressBar, QLabel, QProgressDialog
    from PyQt5.QtGui import QIcon
    from PyQt5.QtCore import QTimer, Qt, QEvent, QFileSystemWatcher, QThread, pyqtSignal
    from app.ui.widgets.floating_result_widget import FloatingResultWidget
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, using console mode")

# Define Worker Thread
if PYQT_AVAILABLE:
    class ModelLoaderThread(QThread):
        """
        Thread for loading OCR models asynchronously to prevent UI freezing
        """
        finished_signal = pyqtSignal(object, object) # detector, recognizer
        error_signal = pyqtSignal(str)

        def __init__(self, config_manager):
            super().__init__()
            self.config_manager = config_manager

        def run(self):
            try:
                print("Starting async model loading...")
                from app.ocr.detector import Detector
                from app.ocr.recognizer import Recognizer
                
                # Initialize new instances
                # This is the heavy operation
                detector = Detector(self.config_manager)
                recognizer = Recognizer(self.config_manager)
                
                self.finished_signal.emit(detector, recognizer)
                print("Async model loading finished")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.error_signal.emit(str(e))

    class ProcessingWorker(QThread):
        finished_signal = pyqtSignal()
        error_signal = pyqtSignal(str)

        def __init__(self, target, *args, **kwargs):
            super().__init__()
            self.target = target
            self.args = args
            self.kwargs = kwargs

        def run(self):
            try:
                self.target(*self.args, **self.kwargs)
                self.finished_signal.emit()
            except Exception as e:
                print(f"Error in processing thread: {e}")
                import traceback
                traceback.print_exc()
                self.error_signal.emit(str(e))

    class CustomMainWindow(QMainWindow):
        def __init__(self, controller):
            super().__init__()
            self.controller = controller

        def closeEvent(self, event):
            # If triggered by explicit quit action (e.g. tray menu), accept
            if getattr(self.controller, '_is_quitting', False):
                self.controller.cleanup()
                event.accept()
                return

            # Get setting
            close_action = self.controller.config_manager.get_setting('close_action', 'ask')

            if close_action == 'minimize':
                event.ignore()
                self.hide()
                # Ensure tray icon is visible
                self.controller.tray_icon.show()
                # self.controller.tray_icon.showMessage("已最小化", "程序已最小化到系统托盘", QSystemTrayIcon.Information, 2000)
                return
            
            if close_action == 'quit':
                self.controller.cleanup()
                event.accept()
                return
                
            # Default: Ask
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("退出确认")
            msg_box.setText("您想要如何操作？")
            
            btn_minimize = msg_box.addButton("最小化到托盘", QMessageBox.ActionRole)
            btn_quit = msg_box.addButton("直接退出", QMessageBox.ActionRole)
            btn_cancel = msg_box.addButton("取消", QMessageBox.RejectRole)
            
            chk_remember = QCheckBox("记住我的选择 (Remember my choice)")
            msg_box.setCheckBox(chk_remember)
            
            msg_box.exec_()
            
            if msg_box.clickedButton() == btn_cancel:
                event.ignore()
                return
                
            remember = chk_remember.isChecked()
            
            if msg_box.clickedButton() == btn_minimize:
                if remember:
                    self.controller.config_manager.set_setting('close_action', 'minimize')
                    self.controller.config_manager.save_config()
                event.ignore()
                self.hide()
                self.controller.tray_icon.show()
                # self.controller.tray_icon.showMessage("已最小化", "程序已最小化到系统托盘", QSystemTrayIcon.Information, 2000)
                
            elif msg_box.clickedButton() == btn_quit:
                if remember:
                    self.controller.config_manager.set_setting('close_action', 'quit')
                    self.controller.config_manager.save_config()
                
                self.controller.cleanup()
                event.accept()

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
from app.core.database_importer import DatabaseImporter
from app.ui.dialogs.db_query_dialog import DbQueryDialog
from app.ui.dialogs.db_selection_dialog import DbSelectionDialog
from app.ui.dialogs.db_manager_dialog import DbManagerDialog
from app.ui.dialogs.field_binding_dialog import FieldBindingDialog
if PYQT_AVAILABLE:
    from app.ui.dialogs.model_download_dialog import ModelDownloadDialog
    # from app.ui.dialogs.model_settings_dialog import ModelSettingsDialog
import json
class OcrBatchService:
    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window

    def process_folders(self, folders_to_process=None):
        self.main_window._process_multiple_folders(folders_to_process=folders_to_process)

    def process_files(self, files, output_dir, default_mask_data=None, force_reprocess=False):
        self.main_window._process_files(files, output_dir, default_mask_data=default_mask_data, force_reprocess=force_reprocess)



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
        # 获取项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Project root in MainWindow: {self.project_root}")
        
        # 初始化配置管理器
        if config_manager:
            self.config_manager = config_manager
        else:
            self.config_manager = ConfigManager(self.project_root)
            self.config_manager.load_config()
        
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

        # Default output directory for global operations (like drag-drop export summary)
        self.output_dir = os.path.join(self.project_root, "output")
        
        # 存储所有文件夹和对应的模板映射
        self.folders = []  # 存储文件夹路径列表
        self.folder_mask_map = {}  # 存储文件夹路径 -> 模板名称的映射
        self.folder_list_items = {}  # 存储文件夹列表项

        # 存储当前选择的模板（用于处理时自动使用）
        self.current_selected_mask = None

        # 初始化OCR组件
        self.detector = detector or Detector(self.config_manager)
        self.recognizer = recognizer or Recognizer(self.config_manager)
        self.post_processor = post_processor or PostProcessor()
        
        # 初始化图像处理组件
        self.converter = converter or Converter()
        self.preprocessor = preprocessor or Preprocessor()
        self.cropper = cropper or Cropper()
        
        # 初始化文件工具
        self.file_utils = FileUtils()
        
        # 初始化蒙版管理器
        self.mask_manager = MaskManager(self.project_root)
        
        self.process_manager = None
        
        # Initialize OCR Service: always use local batch service
        self.ocr_service = OcrBatchService(self)
            
        ServiceRegistry.register("ocr_batch", self.ocr_service)
        
        # 初始化定时器用于更新UI
        self.update_timer = None
        
        # 根据模式初始化UI
        self.is_gui_mode = is_gui_mode
        self.ui = None
        self.main_window = None
        
        # 仅在GUI模式下初始化UI组件
        if PYQT_AVAILABLE and self.is_gui_mode:
            try:
                from PyQt5.QtWidgets import QApplication
                from app.ui.ui_mainwindow import Ui_MainWindow
                
                # 确保QApplication已存在
                app = QApplication.instance()
                if app is None:  # 如果没有现有的实例，则创建新的
                    app = QApplication([])
                
                # self.main_window = QMainWindow()
                self.main_window = CustomMainWindow(self)
                self.ui = Ui_MainWindow()
                self.ui.setup_ui(self.main_window)
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
                    self.ui.folder_list.installEventFilter(self)
                except Exception as e:
                    print(f"Error configuring image_list: {e}")
                    pass

                if hasattr(self.ui, 'padding_chk'):
                    self.ui.padding_chk.setChecked(
                        self.config_manager.get_setting('use_padding', True)
                    )
                if hasattr(self.ui, 'preprocessing_chk'):
                    self.ui.preprocessing_chk.setChecked(
                        self.config_manager.get_setting('use_preprocessing', True)
                    )

                # Legacy actionSettings support moved to _connect_signals or ignored if not used


                self._connect_signals()
                # 设置延迟更新模板列表，确保UI完全初始化
                if PYQT_AVAILABLE:
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(100, self._delayed_ui_setup)
                
                # Screenshot Mode Init
                self.clipboard_watcher = ClipboardWatcher()
                self.clipboard_watcher.image_captured.connect(self.process_clipboard_image)
                self.floating_widget = FloatingResultWidget()
                self.ocr_result_ready_signal.connect(self._on_ocr_result_ready)
                self.floating_widget.restore_requested.connect(self._restore_from_tray)
                
                # Tray Icon
                self.tray_icon = QSystemTrayIcon(self.main_window)
                
                # Try to get window icon, fallback to system icon
                icon = self.main_window.windowIcon()
                if icon.isNull():
                    icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
                self.tray_icon.setIcon(icon)
                
                self.tray_menu = QMenu()
                self.act_restore = QAction("显示主界面 (Show Main Window)", self.main_window)
                self.act_restore.triggered.connect(self._restore_from_tray)
                
                self.act_stop_screenshot_mode = QAction("停止自动截屏 (Stop Auto-OCR)", self.main_window)
                self.act_stop_screenshot_mode.triggered.connect(self._stop_screenshot_mode_action)
                # Initially hidden or disabled, handled in toggle
                
                self.act_quit = QAction("退出程序 (Quit)", self.main_window)
                self.act_quit.triggered.connect(self.quit_application)
                
                self.tray_menu.addAction(self.act_restore)
                self.tray_menu.addAction(self.act_stop_screenshot_mode)
                self.tray_menu.addSeparator()
                self.tray_menu.addAction(self.act_quit)
                
                self.tray_icon.setContextMenu(self.tray_menu)
                self.tray_icon.activated.connect(self._on_tray_icon_activated)

                print("UI initialized successfully")
            except Exception as e:
                print(f"Error setting up UI: {e}")
                import traceback
                traceback.print_exc()
                self.ui = None
                self.main_window = None  # 确保UI组件被设为None
                
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
                QMessageBox.warning(None, "警告", "未下载必要模型，本地OCR功能将无法使用！")
            else:
                print("Models downloaded successfully")

    def _delayed_ui_setup(self):
        """延迟执行的UI设置"""
        try:
            self._setup_masks_file_watcher()
        except Exception as e:
            print(f"Error in delayed masks setup: {e}")
        try:
            self._update_mask_combo()
        except Exception as e:
            print(f"Error in delayed mask combo update: {e}")

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

    def _connect_signals(self):
        """
        连接UI信号
        """
        print("Connecting UI signals")
        
        # Add Screenshot Mode Action to Menu
        if self.main_window and hasattr(self.main_window, 'menuBar'):
            menubar = self.main_window.menuBar()
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
            self.ui.start_button.clicked.connect(self._start_processing)
            self.ui.stop_button.clicked.connect(self._stop_processing)
            if hasattr(self.ui, 'settings_button'):
                self.ui.settings_button.clicked.connect(self._open_settings_dialog)
            # self.ui.model_selector.currentIndexChanged.connect(self._on_model_changed)
            self.ui.image_list.itemClicked.connect(self._on_image_selected)
            
            if hasattr(self.ui, 'preprocessing_chk'):
                self.ui.preprocessing_chk.stateChanged.connect(self._on_preprocessing_changed)
            if hasattr(self.ui, 'padding_chk'):
                self.ui.padding_chk.stateChanged.connect(self._on_padding_changed)
            
            # Mask connections
            if hasattr(self.ui, 'mask_btn_enable'):
                self.ui.mask_btn_enable.clicked.connect(self._toggle_mask_drawing)
            if hasattr(self.ui, 'mask_chk_use'):
                self.ui.mask_chk_use.stateChanged.connect(self._on_use_mask_changed)
            
            if hasattr(self.ui, 'table_mode_combo'):
                try:
                    self.ui.table_mode_combo.currentIndexChanged.connect(self._on_table_mode_changed)
                except Exception:
                    pass
            if hasattr(self.ui, 'ai_advanced_doc_chk'):
                self.ui.ai_advanced_doc_chk.toggled.connect(self._on_ai_advanced_doc_toggled)

            if hasattr(self.ui, 'mask_btn_save'):
                self.ui.mask_btn_save.clicked.connect(self._save_new_mask)
            if hasattr(self.ui, 'mask_btn_rename'):
                self.ui.mask_btn_rename.clicked.connect(self._rename_mask)
            if hasattr(self.ui, 'mask_btn_delete'):
                self.ui.mask_btn_delete.clicked.connect(self._delete_mask)
            if hasattr(self.ui, 'mask_btn_export'):
                self.ui.mask_btn_export.clicked.connect(self._export_masks)
            if hasattr(self.ui, 'mask_btn_apply'):
                self.ui.mask_btn_apply.clicked.connect(self._apply_selected_mask)
            if hasattr(self.ui, 'mask_btn_clear') and hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                self.ui.mask_btn_clear.clicked.connect(self.ui.image_viewer.clear_masks)
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
                self.ui.status_label.setText("模板文件已更新")
                print(f"模板下拉框已更新，当前模板数量: {len(self.mask_manager.get_all_mask_names())}")
                
            # 重新添加监听（文件修改可能导致监听丢失）
            if hasattr(self, '_masks_fs_watcher') and self._masks_fs_watcher:
                if path not in self._masks_fs_watcher.files():
                    self._masks_fs_watcher.addPath(path)
                    
        except Exception as e:
            print(f"Error handling masks file change: {e}")
            if self.ui:
                self.ui.status_label.setText(f"模板更新失败: {str(e)}")

    def _on_use_mask_changed(self, state):
        self.config_manager.set_setting('use_mask', state == Qt.Checked)
        self.config_manager.save_config()

    def _on_table_mode_changed(self, index):
        """
        处理表格模式下拉框变化
        0: 关闭
        1: 传统表格拆分
        2: AI 表格结构识别
        """
        use_table_split = False
        use_ai_table = False
        use_table_model = False

        if index == 1:
            use_table_split = True
        elif index == 2:
            use_ai_table = True
            use_table_model = True

        self.config_manager.set_setting('use_table_split', use_table_split)
        self.config_manager.set_setting('use_ai_table', use_ai_table)
        self.config_manager.set_setting('use_table_model', use_table_model)

        if hasattr(self.ui, 'ai_table_model_combo'):
            self.ui.ai_table_model_combo.setEnabled(use_ai_table)
        if hasattr(self.ui, 'ai_advanced_doc_chk'):
            self.ui.ai_advanced_doc_chk.setEnabled(use_ai_table)

        self.config_manager.save_config()

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
        if hasattr(self.ui, 'table_mode_combo'):
            use_table_split = self.config_manager.get_setting('use_table_split', False)
            use_ai_table = self.config_manager.get_setting('use_ai_table', False)
            if use_ai_table:
                index = 2
            elif use_table_split:
                index = 1
            else:
                index = 0
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
        is_enabled = (state == Qt.Checked)
        self.is_padding_enabled = is_enabled
        self.config_manager.set_setting('use_padding', is_enabled)
        self.config_manager.save_config()
        
    def _toggle_mask_drawing(self, checked):
        if self.ui.image_viewer:
            self.ui.image_viewer.start_mask_mode(checked)
            msg = "蒙版绘制模式已开启" if checked else "蒙版绘制模式已关闭"
            self.ui.status_label.setText(msg)
            
            # 更新按钮文本
            if hasattr(self.ui, 'mask_btn_enable'):
                if checked:
                    self.ui.mask_btn_enable.setText("正在绘制")
                else:
                    self.ui.mask_btn_enable.setText("开启绘制模式")

    def _save_new_mask(self):
        if not self.ui.image_viewer or not self.ui.image_viewer.has_mask():
            QMessageBox.warning(self.main_window, "提示", "请先在图像上绘制蒙版")
            return
        name, ok = QInputDialog.getText(self.main_window, "保存蒙版", "请输入蒙版名称:")
        if ok and name:
            if name in self.mask_manager.get_all_mask_names():
                 if QMessageBox.question(self.main_window, "确认", "蒙版名称已存在，是否覆盖？") != QMessageBox.Yes:
                     return
            mask_data = self.ui.image_viewer.get_mask_data()
            self.mask_manager.add_mask(name, mask_data)
            self._update_mask_combo()
            self.ui.status_label.setText(f"蒙版 '{name}' 已保存")

    def _rename_mask(self):
        """重命名模板"""
        # 显示弹窗选择要重命名的模板
        selected_display_name = self._show_mask_selection_dialog()
        if not selected_display_name or selected_display_name == "不应用模板":
            return
            
        current_name = self._get_original_mask_name(selected_display_name)
        new_name, ok = QInputDialog.getText(self.main_window, "重命名蒙版", "请输入新名称:", text=selected_display_name)
        if ok and new_name and new_name != selected_display_name:
            self.mask_manager.rename_mask(current_name, new_name)
            self.ui.status_label.setText(f"蒙版 '{selected_display_name}' 已重命名为 '{new_name}'")

    def _delete_mask(self):
        """删除模板"""
        # 显示弹窗选择要删除的模板
        selected_display_name = self._show_mask_selection_dialog()
        if not selected_display_name or selected_display_name == "不应用模板":
            return
            
        current_name = self._get_original_mask_name(selected_display_name)
        if QMessageBox.question(self.main_window, "确认", f"确定要删除蒙版 '{selected_display_name}' 吗？") == QMessageBox.Yes:
            self.mask_manager.delete_mask(current_name)
            self.ui.status_label.setText(f"蒙版 '{selected_display_name}' 已删除")

    def _export_masks(self):
        file_path, _ = QFileDialog.getSaveFileName(self.main_window, "导出蒙版配置", "", "JSON Files (*.json)")
        if file_path:
            self.mask_manager.export_masks(file_path)
            self.ui.status_label.setText(f"蒙版配置已导出到 {file_path}")

    pass

    def _show_mask_selection_dialog(self):
        """显示模板选择弹窗"""
        if not PYQT_AVAILABLE or not self.main_window:
            return None
            
        # 创建简单的选择对话框
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel, QListWidgetItem
        
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("选择模板")
        dialog.resize(300, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 添加说明标签
        label = QLabel("请选择要使用的模板:")
        layout.addWidget(label)
        
        # 创建列表控件
        list_widget = QListWidget()
        names = self.mask_manager.get_all_mask_names()
        
        # 添加"不应用模板"选项
        no_mask_item = QListWidgetItem("不应用模板")
        no_mask_item.setData(Qt.UserRole, None)
        list_widget.addItem(no_mask_item)
        
        # 添加友好的显示名称
        display_names = []
        self._mask_name_mapping = {}
        for name in names:
            if name.isdigit():
                display_name = f"模板 {name}"
            else:
                display_name = name
            display_names.append(display_name)
            self._mask_name_mapping[display_name] = name
            
        list_widget.addItems(display_names)
        
        # 添加模板信息显示区域
        info_label = QLabel("当前模板信息将显示在这里")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        info_label.setStyleSheet("background-color: #f5f5f5; padding: 5px;")
        
        # 当选择变化时更新信息
        def update_info(item):
            if item and item.text() == "不应用模板":
                info_label.setText("不应用任何模板")
            elif item:
                mask_name = self._get_original_mask_name(item.text())
                mask_data = self.mask_manager.get_mask(mask_name)
                if mask_data:
                    info_text = f"模板名称: {mask_name}\n"
                    if isinstance(mask_data, list):
                        if len(mask_data) > 0 and isinstance(mask_data[0], (int, float)):
                            info_text += f"区域坐标: {mask_data}"
                        else:
                            info_text += f"包含 {len(mask_data)} 个子区域"
                    info_label.setText(info_text)
                else:
                    info_label.setText(f"模板 {mask_name} 信息不可用")
        
        list_widget.currentItemChanged.connect(update_info)
        layout.addWidget(info_label)
        
        # 创建按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        layout.addWidget(list_widget)
        layout.addWidget(button_box)
        
        # 显示对话框并等待用户选择
        if dialog.exec_() == QDialog.Accepted:
            current_item = list_widget.currentItem()
            if current_item:
                return current_item.text()
        return None
        
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
                            self.ui.status_label.setText(f"已清除文件夹 '{os.path.basename(directory)}' 的模板")
                            self._update_folder_mask_display(directory)
            else:
                current_name = self._get_original_mask_name(selected_display_name)
                mask_data = self.mask_manager.get_mask(current_name)
                if mask_data and self.ui and hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
                    self.ui.image_viewer.set_mask_data(mask_data)
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
            if hasattr(self.ui, 'mask_chk_use'):
                self.ui.mask_chk_use.setChecked(self.config_manager.get_setting('use_mask', False))

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
                QTimer.singleShot(500, self._update_mask_combo)
            else:
                self._update_mask_combo()
            
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
        if hasattr(self.ui, 'status_label'):
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
            result = dialog.exec_()
            
            if result == QDialog.Accepted:
                changed_categories = dialog.get_changed_categories()
                print(f"Settings changed categories: {changed_categories}")
                
                # 差量更新逻辑
                # 1. 如果模型设置改变，重新初始化OCR组件（使用全局加载锁）
                if 'model' in changed_categories:
                    print("Initiating async OCR model reload...")

                    if hasattr(self.main_window, 'statusBar'):
                        if not self.loading_progress_bar:
                            self.loading_progress_bar = QProgressBar()
                            self.loading_progress_bar.setRange(0, 0)
                            self.loading_progress_bar.setMaximumWidth(200)
                            self.loading_progress_bar.setVisible(False)
                            self.main_window.statusBar().addPermanentWidget(self.loading_progress_bar)
                        self.loading_progress_bar.setVisible(True)
                        if hasattr(self.ui, 'status_label'):
                            self.ui.status_label.setText("正在加载模型，请稍候...")

                    if PYQT_AVAILABLE:
                        from PyQt5.QtCore import Qt
                        if not self.global_loading_dialog:
                            self.global_loading_dialog = QProgressDialog("正在加载模型，请稍候...", None, 0, 0, self.main_window)
                            self.global_loading_dialog.setWindowModality(Qt.ApplicationModal)
                            self.global_loading_dialog.setCancelButton(None)
                            self.global_loading_dialog.setMinimumDuration(0)
                            flags = self.global_loading_dialog.windowFlags()
                            self.global_loading_dialog.setWindowFlags(flags & ~Qt.WindowCloseButtonHint)
                        self.global_loading_dialog.setLabelText("正在加载模型，请稍候...")
                        self.global_loading_dialog.show()

                    if hasattr(self.ui, 'start_button'):
                        self.ui.start_button.setEnabled(False)
                    if hasattr(self.ui, 'model_selector'):
                        self.ui.model_selector.setEnabled(False)

                    if self.model_loader_thread and self.model_loader_thread.isRunning():
                        self.model_loader_thread.terminate()
                        self.model_loader_thread.wait()

                    self.model_loader_thread = ModelLoaderThread(self.config_manager)
                    self.model_loader_thread.finished_signal.connect(self.on_models_reloaded)
                    self.model_loader_thread.error_signal.connect(self.on_model_load_error)
                    self.model_loader_thread.start()
                    
                # 2. 如果处理设置改变
                if 'processing' in changed_categories:
                    self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)

        except Exception as e:
            self.logger.error(f"打开设置对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"打开设置对话框失败: {e}")

    def on_models_reloaded(self, detector, recognizer):
        """
        Slot called when models are successfully reloaded
        """
        print("Models reloaded successfully")
        self.detector = detector
        self.recognizer = recognizer
        
        # Hide progress
        if self.loading_progress_bar:
            self.loading_progress_bar.setVisible(False)
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
            
        QMessageBox.information(self.main_window, "完成", "OCR模型加载完成")

    def on_model_load_error(self, error_msg):
        """
        Slot called when model loading fails
        """
        print(f"Model load error: {error_msg}")
        
        # Hide progress
        if self.loading_progress_bar:
            self.loading_progress_bar.setVisible(False)
        if self.global_loading_dialog:
            self.global_loading_dialog.hide()
            self.global_loading_dialog = None
            
        # Update status
        if hasattr(self.ui, 'status_label'):
            self.ui.status_label.setText("模型加载失败")
            
        # Enable controls (so user can retry)
        if hasattr(self.ui, 'start_button'):
            self.ui.start_button.setEnabled(True)
        if hasattr(self.ui, 'model_selector'):
            self.ui.model_selector.setEnabled(True)
            
        QMessageBox.critical(self.main_window, "错误", f"模型加载失败: {error_msg}")

    def _start_processing(self):
        """
        开始处理多个文件夹
        """
        print("Starting batch processing of folders")
        
        # 收集需要处理的文件夹（被勾选的）
        folders_to_process = []
        if PYQT_AVAILABLE and self.ui and self.ui.folder_list:
            for i in range(self.ui.folder_list.count()):
                item = self.ui.folder_list.item(i)
                if item.checkState() == Qt.Checked:
                    directory = item.data(Qt.UserRole)
                    if not directory: # Fallback
                        directory = self.folder_list_items.get(item.text())
                    
                    if directory:
                        folders_to_process.append(directory)
        else:
            folders_to_process = self.folders # 非GUI模式处理所有
        
        # 检查是否有文件夹需要处理
        if not folders_to_process:
            QMessageBox.warning(self.main_window, "提示", "请先添加并勾选要处理的文件夹")
            return
            
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

        # 更新UI状态
        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(False)
            self.ui.stop_button.setEnabled(True)
            self.ui.status_label.setText("正在批量处理...")

        try:
            if PYQT_AVAILABLE and self.ui:
                if hasattr(self.ui, 'preprocessing_chk'):
                    self.config_manager.set_setting(
                        'use_preprocessing',
                        bool(self.ui.preprocessing_chk.isChecked())
                    )
                if hasattr(self.ui, 'padding_chk'):
                    self.is_padding_enabled = bool(self.ui.padding_chk.isChecked())
                else:
                    self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)
                self.config_manager.set_setting('use_padding', self.is_padding_enabled)
                self.config_manager.save_config()
                
                self.ui.start_button.setEnabled(False)
                self.ui.stop_button.setEnabled(True)
                self.ui.status_label.setText(f"正在批量处理 {len(folders_to_process)} 个文件夹...")
                
            self.results_by_filename = {}
            self._stop_flag = False
            self.performance_monitor.reset()
            
            service = ServiceRegistry.get("ocr_batch") or self.ocr_service
            
            if PYQT_AVAILABLE:
                self.processing_worker = ProcessingWorker(
                    target=service.process_folders,
                    folders_to_process=folders_to_process
                )
                self.processing_worker.finished.connect(self.on_processing_finished)
                self.processing_worker.error_signal.connect(self.on_processing_error)
                
                # Connect file processed signal safely
                try:
                    self.file_processed_signal.disconnect()
                except:
                    pass
                self.file_processed_signal.connect(self.on_file_processed)
                
                self.processing_worker.start()
            else:
                self.processing_thread = threading.Thread(
                    target=service.process_folders,
                    args=(folders_to_process,),
                    daemon=True,
                )
                self.processing_thread.start()
        except Exception as e:
            self.logger.error(f"批量处理过程中发生错误: {e}")
            if PYQT_AVAILABLE and self.main_window:
                QMessageBox.critical(self.main_window, "错误", f"批量处理过程中发生错误: {e}")
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(True)
                self.ui.stop_button.setEnabled(False)
                self.ui.status_label.setText("处理失败")

    def _process_multiple_folders(self, folders_to_process=None):
        """处理多个文件夹"""
        self.performance_monitor.start_timer("total_processing")
        
        target_folders = folders_to_process if folders_to_process is not None else self.folders
        
        for folder_path in target_folders:
            if getattr(self, "_stop_flag", False):
                break
                
            # 获取该文件夹的模板设置
            mask_name = self.folder_mask_map.get(folder_path, None)
            mask_data = None
            if mask_name:
                mask_data = self.mask_manager.get_mask(mask_name)
            
            # 处理该文件夹
            self.logger.info(f"开始处理文件夹: {folder_path} (使用模板: {mask_name if mask_name else '默认/无'})")
            print(f"Processing folder: {folder_path} (Mask: {mask_name})")
            
            # 创建子目录用于输出结果
            # folder_name = os.path.basename(folder_path)
            # output_subdir = os.path.join(self.output_dir, folder_name)
            if os.path.isfile(folder_path):
                output_subdir = os.path.join(os.path.dirname(folder_path), "output")
            else:
                output_subdir = os.path.join(folder_path, "output")
            os.makedirs(output_subdir, exist_ok=True)
            
            # 处理该文件夹下的所有图像（批处理禁止使用全局选中模板作为回退）
            self._process_images(folder_path, output_subdir, mask_data, use_global_selected_mask=False)
            
            if getattr(self, "_stop_flag", False):
                break
                
        total_time = self.performance_monitor.stop_timer("total_processing")
        self.logger.info(f"批量处理完成，总耗时: {total_time:.2f}秒")
        print(f"Batch processing completed in {total_time:.2f} seconds")
    
    def _start_processing_files(self, files, force_reprocess=False):
        try:
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(False)
                self.ui.stop_button.setEnabled(True)
                if force_reprocess:
                    self.ui.status_label.setText("正在重新处理选中的文件...")
                else:
                    self.ui.status_label.setText("正在处理拖入的文件...")

                if hasattr(self.ui, 'preprocessing_chk'):
                    self.config_manager.set_setting(
                        'use_preprocessing',
                        bool(self.ui.preprocessing_chk.isChecked())
                    )
                if hasattr(self.ui, 'padding_chk'):
                    self.is_padding_enabled = bool(self.ui.padding_chk.isChecked())
                else:
                    self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)
                self.config_manager.set_setting('use_padding', self.is_padding_enabled)

                # 保存表格识别模式与相关设置
                if hasattr(self.ui, 'table_mode_combo'):
                    index = self.ui.table_mode_combo.currentIndex()
                    use_table_split = (index == 1)
                    use_ai_table = (index == 2)
                    self.config_manager.set_setting('use_table_split', use_table_split)
                    self.config_manager.set_setting('use_ai_table', use_ai_table)
                    self.config_manager.set_setting('use_table_model', use_ai_table)
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
            self.results_by_filename = {}
            self.results_json_by_filename = {} # Clear JSON cache on new processing
            self._stop_flag = False
            self.performance_monitor.reset()
            
            # 获取当前选中的蒙版作为默认蒙版
            default_mask_data = None
            if self.config_manager.get_setting('use_mask', False) and self.ui:
                # 使用弹窗选择默认模板
                current_mask_name = self._show_mask_selection_dialog()
                if current_mask_name:
                    original_name = self._get_original_mask_name(current_mask_name)
                    default_mask_data = self.mask_manager.get_mask(original_name)

            service = ServiceRegistry.get("ocr_batch") or self.ocr_service
            
            if PYQT_AVAILABLE:
                self.processing_worker = ProcessingWorker(
                    target=service.process_files,
                    files=files,
                    output_dir=self.output_dir,
                    default_mask_data=default_mask_data,
                    force_reprocess=force_reprocess
                )
                self.processing_worker.finished.connect(self.on_processing_finished)
                self.processing_worker.error_signal.connect(self.on_processing_error)
                
                # Connect file processed signal safely
                try:
                    self.file_processed_signal.disconnect()
                except:
                    pass
                self.file_processed_signal.connect(self.on_file_processed)
                
                self.processing_worker.start()
            else:
                self.processing_thread = threading.Thread(
                    target=service.process_files,
                    args=(files, self.output_dir, default_mask_data, force_reprocess),
                    daemon=True,
                )
                self.processing_thread.start()
        except Exception as e:
            self.logger.error(f"处理拖入文件时发生错误: {e}")
            if PYQT_AVAILABLE and self.main_window:
                QMessageBox.critical(self.main_window, "错误", f"处理拖入文件时发生错误: {e}")
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(True)
                self.ui.stop_button.setEnabled(False)
                self.ui.status_label.setText("处理失败")

    def on_file_processed(self, filename, text):
        """Signal handler for file processing completion"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # Update results cache (redundant if already done in thread, but safe)
        self.results_by_filename[filename] = text
        
        # Check if we need to update the display for the currently selected item
        if self.ui.image_list.count() > 0:
            current_item = self.ui.image_list.currentItem()
            if current_item and current_item.text() == filename:
                self._display_result_for_item(current_item)

    def on_processing_finished(self):
        """Signal handler for batch processing completion"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        self.ui.start_button.setEnabled(True)
        self.ui.stop_button.setEnabled(False)
        self.ui.status_label.setText("处理完成")
        
        # Update display for the currently selected item one last time
        if self.ui.image_list.count() > 0:
            item = self.ui.image_list.currentItem()
            if not item:
                item = self.ui.image_list.item(0)
                self.ui.image_list.setCurrentItem(item)
            self._display_result_for_item(item)
            
        # Clean up worker
        if hasattr(self, 'processing_worker'):
            self.processing_worker = None

    def on_processing_error(self, error_msg):
        """Signal handler for processing errors"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        self.logger.error(f"Processing error: {error_msg}")
        QMessageBox.critical(self.main_window, "处理错误", f"处理过程中发生错误:\n{error_msg}")
        
        # Reset UI state
        self.ui.start_button.setEnabled(True)
        self.ui.stop_button.setEnabled(False)
        self.ui.status_label.setText("处理出错")
        
        # Clean up worker
        if hasattr(self, 'processing_worker'):
            self.processing_worker = None

    def _check_processing_finished(self):
        # Legacy polling method, kept for reference but unused in new async mode
        pass

    def _stop_processing(self):
        """
        停止处理
        """
        print("Stopping image processing")
        self._stop_flag = True
        self.task_manager.stop_worker()
            
        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(True)
            self.ui.stop_button.setEnabled(False)
            self.ui.status_label.setText("处理已停止")

    def _process_single_image_task(self, original_image, image_path, mask_lookup_name, result_base_name, default_mask_data=None, use_global_selected_mask=True):
        """
        Process a single image task (page or file)
        """
        # Determine masks
        masks_to_process = []
        try:
            mask_data = None
            
            # 优先级: 1. 图像绑定的模板 2. 文件夹级别的模板 3. 全局默认模板
            bound_mask = self.mask_manager.get_bound_mask(mask_lookup_name)
            if bound_mask:
                mask_data = self.mask_manager.get_mask(bound_mask)
            elif default_mask_data is not None:
                mask_data = default_mask_data
            elif use_global_selected_mask and self.current_selected_mask:
                mask_data = self.current_selected_mask
            
            # 规范化蒙版数据
            if mask_data:
                if isinstance(mask_data, list):
                    if len(mask_data) > 0 and isinstance(mask_data[0], (int, float)):
                        masks_to_process = [{'rect': mask_data, 'label': 1}]
                    else:
                        masks_to_process = mask_data
                        # 按空间位置排序 (从上到下，从左到右)
                        masks_to_process.sort(key=lambda x: (x.get('rect', [0, 0, 0, 0])[1] if x.get('rect') else 0, x.get('rect', [0, 0, 0, 0])[0] if x.get('rect') else 0))
            
            # 如果没有蒙版，则处理全图
            if not masks_to_process:
                masks_to_process = [{'rect': None, 'label': 0}]
                
        except Exception as e:
            print(f"Error determining masks for {image_path}: {e}")
            masks_to_process = [{'rect': None, 'label': 0}]

        file_recognized_texts = []
        file_detailed_results = []
        file_processing_failed = False

        for mask_info in masks_to_process:
            rect = mask_info.get('rect')
            
            # 裁剪
            image = original_image
            if rect and len(rect) == 4:
                try:
                    w, h = image.size if hasattr(image, 'size') else (None, None)
                    if w and h:
                        # 计算原始坐标
                        x1 = int(rect[0] * w)
                        y1 = int(rect[1] * h)
                        x2 = int(rect[2] * w)
                        y2 = int(rect[3] * h)
                        
                        # 增加外扩 (Expansion)
                        expansion_ratio_w = 0.05  # 宽度外扩 5%
                        expansion_ratio_h = 0.02  # 高度外扩 2%
                        
                        crop_w = x2 - x1
                        crop_h = y2 - y1
                        
                        # 计算外扩量
                        expand_w = int(crop_w * expansion_ratio_w)
                        expand_h = int(crop_h * expansion_ratio_h)
                        
                        # 应用外扩并确保不越界
                        x1 = max(0, x1 - expand_w)
                        y1 = max(0, y1 - expand_h)
                        x2 = min(w, x2 + expand_w)
                        y2 = min(h, y2 + expand_h)
                        
                        image = self.cropper.crop_text_region(image, [x1, y1, x2, y2])
                except Exception as e:
                    print(f"Mask crop failed for {image_path}: {e}")
            
            # 预处理
            self.performance_monitor.start_timer("preprocessing")
            use_preprocessing = True
            if self.config_manager:
                use_preprocessing = self.config_manager.get_setting('use_preprocessing', True)
            if hasattr(self.ui, 'preprocessing_chk'):
                use_preprocessing = bool(self.ui.preprocessing_chk.isChecked())
            if use_preprocessing:
                preprocessed_filename = f"{result_base_name}_part{mask_info.get('label', 0)}"
                use_padding = getattr(self, "is_padding_enabled", True)
                image = self.preprocessor.comprehensive_preprocess(
                    image, None, preprocessed_filename, use_padding=use_padding
                )
            self.performance_monitor.stop_timer("preprocessing")
            
            # 检测与识别
            self.performance_monitor.start_timer("detection")
            print("DEBUG: Using Local Mode (OcrEngine)")
            try:
                if not hasattr(self, 'ocr_engine') or self.ocr_engine is None:
                    self.ocr_engine = OcrEngine(self.config_manager, detector=self.detector, recognizer=self.recognizer)
                process_options = {
                    'skip_preprocessing': True,
                    'use_table_model': self.config_manager.get_setting('use_table_model', False),
                    'ai_table_model': self.config_manager.get_setting('ai_table_model', 'SLANet'),
                    'use_ai_table': self.config_manager.get_setting('use_ai_table', False)
                }
                print(f"DEBUG: Calling process_image with options: {process_options}")
                result = self.ocr_engine.process_image(image, process_options)
                text_regions = result.get('regions', [])
                print(f"DEBUG: process_image returned {len(text_regions)} regions")
            except Exception as e:
                print(f"Error in OcrEngine processing: {e}")
                import traceback
                traceback.print_exc()
                text_regions = self.detector.detect_text_regions(image)
                
            self.performance_monitor.stop_timer("detection")
            
            if text_regions is None:
                print(f"Error: Detection failed for {image_path} (mask {mask_info.get('label', 0)})")
                file_processing_failed = True
                break

            part_texts = []
            current_line_idx = -1
            current_line_texts = []
            
            for j, region in enumerate(text_regions):
                self.performance_monitor.start_timer("recognition")
                try:
                    text = region.get('text', '')
                    confidence = region.get('confidence', 0.0)
                    line_idx = region.get('line_index', -1)
                    coordinates = region.get('coordinates', [])
                    if hasattr(coordinates, 'tolist'):
                        coordinates = coordinates.tolist()
                    
                    if line_idx != -1:
                        if current_line_idx != -1 and line_idx != current_line_idx:
                            if current_line_texts:
                                part_texts.append(" ".join(current_line_texts))
                                current_line_texts = []
                        current_line_idx = line_idx
                    
                    current_line_texts.append(text)
                    
                    res_item = {
                        'text': text,
                        'confidence': confidence,
                        'coordinates': coordinates,
                        'detection_confidence': confidence,
                        'mask_label': mask_info.get('label', 0),
                        'line_index': line_idx
                    }
                    if 'table_info' in region:
                        res_item['table_info'] = region['table_info']
                    
                    file_detailed_results.append(res_item)
                except Exception as e:
                    self.logger.error(f"Error processing region {j} in {image_path}: {e}")
                finally:
                    self.performance_monitor.stop_timer("recognition")
            
            if current_line_texts:
                part_texts.append(" ".join(current_line_texts))
            
            if part_texts:
                file_recognized_texts.append("\n".join(part_texts))
            
        if file_processing_failed:
            print(f"Skipping result saving for {result_base_name} due to failure")
            return None, None
        else:
            full_text = "\n".join(file_recognized_texts)
            
            current_file_dir = os.path.dirname(image_path)
            current_output_dir = os.path.join(current_file_dir, "output")
            
            txt_output_dir = os.path.join(current_output_dir, "txt")
            json_output_dir = os.path.join(current_output_dir, "json")
            
            os.makedirs(txt_output_dir, exist_ok=True)
            os.makedirs(json_output_dir, exist_ok=True)
            
            # Save TXT
            output_file = os.path.join(txt_output_dir, f"{result_base_name}_result.txt")
            try:
                self.file_utils.write_text_file(output_file, full_text)
            except Exception as e:
                print(f"Warning: Failed to write TXT file {output_file}: {e}")
            
            # Save JSON
            json_output_file = os.path.join(json_output_dir, f"{result_base_name}.json")
            try:
                json_result = {
                    'image_path': image_path,
                    'filename': result_base_name,
                    'timestamp': datetime.now().isoformat(),
                    'full_text': full_text,
                    'regions': file_detailed_results,
                    'status': 'success'
                }
                self.file_utils.write_json_file(json_output_file, json_result)
                self.results_json_by_filename[result_base_name + ".json"] = json_result
            except Exception as e:
                print(f"Warning: Failed to write JSON file {json_output_file}: {e}")
            
            return full_text, file_detailed_results

    def _process_images(self, input_dir, output_dir, default_mask_data=None, use_global_selected_mask=True):
        """
        处理图像

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            default_mask_data: 默认蒙版数据（可选）
        """
        print(f"Processing images from {input_dir} to {output_dir}")
        self.logger.info(f"开始处理目录: {input_dir}")
        self.performance_monitor.start_timer("total_processing")
        
        # 获取图像文件列表
        image_files = self.file_utils.get_image_files(input_dir)
        self.logger.info(f"找到 {len(image_files)} 个图像文件")
        print(f"Found {len(image_files)} image files")
        
        if not image_files:
            self.logger.warning("未找到图像文件")
            return
            
        # 处理每个图像文件
        for i, image_path in enumerate(image_files):
            if getattr(self, "_stop_flag", False):
                break
            
            # 检查重复处理
            if "|page=" in image_path:
                # Virtual path handling
                real_path_part = image_path.split("|")[0]
                page_part = image_path.split("|")[1]
                try:
                    page_num = page_part.split("=")[1]
                    base = os.path.basename(real_path_part)
                    filename = f"{os.path.splitext(base)[0]}_page_{page_num}"
                except:
                    filename = os.path.basename(image_path)
                
                current_file_dir = os.path.dirname(real_path_part)
            else:
                filename = os.path.basename(image_path)
                current_file_dir = os.path.dirname(image_path)
                
            current_output_dir = os.path.join(current_file_dir, "output")
            
            input_record_mgr = RecordManager.get_instance(current_file_dir)
            output_record_mgr = RecordManager.get_instance(current_output_dir)
            
            # Check if PDF
            is_pdf = image_path.lower().endswith('.pdf')

            # 双重核验：必须两个记录都存在，且输出文件实际存在
            is_processed = False
            json_output_file = os.path.join(current_output_dir, "json", f"{os.path.splitext(filename)[0]}.json")
            
            if input_record_mgr.is_recorded(filename) and output_record_mgr.is_recorded(filename):
                # For PDF, we trust the record manager as we don't produce a single JSON file for the whole PDF usually
                if is_pdf:
                    is_processed = True
                elif os.path.exists(json_output_file):
                    is_processed = True
            
            if is_processed:
                self.logger.info(f"跳过已处理文件 (加载缓存): {image_path}")
                print(f"Skipping processed file (loading cache): {image_path}")
                
                # 加载已有结果
                try:
                    # For PDF, we might need to load multiple pages or just skip.
                    # Currently, we just skip re-processing.
                    # If it's a normal image, load the result.
                    if not is_pdf:
                        with open(json_output_file, 'r', encoding='utf-8') as f:
                            cached_result = json.load(f)
                        full_text = cached_result.get('full_text', '')
                        self.results_by_filename[os.path.basename(image_path)] = full_text
                        self.result_manager.store_result(image_path, full_text)
                        
                        # Emit signal for UI update
                        if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                            self.file_processed_signal.emit(os.path.basename(image_path), full_text)
                    else:
                        # For PDF, we just skip. If we want to show results, we'd need to load all page jsons.
                        # For now, skipping is enough to avoid re-processing.
                        pass
                except Exception as e:
                    print(f"Error loading cached result for {image_path}: {e}")
                    # 如果加载失败，视为未处理，继续处理
                    pass
                else:
                    continue
            
            self.logger.info(f"处理图像 ({i+1}/{len(image_files)}): {image_path}")
            print(f"Processing image ({i+1}/{len(image_files)}): {image_path}")
            
            if is_pdf:
                # Process PDF Pages
                images = self.file_utils.read_pdf_images(image_path)
                if not images:
                    print(f"Failed to read PDF: {image_path}")
                    continue
                
                print(f"Processing PDF with {len(images)} pages: {image_path}")
                
                pdf_full_texts = []
                pdf_processing_failed = False

                for page_idx, image in enumerate(images):
                    if getattr(self, "_stop_flag", False):
                        break
                    
                    # Use page-specific naming
                    page_base_name = f"{os.path.splitext(filename)[0]}_page_{page_idx+1}"
                    
                    full_text, _ = self._process_single_image_task(
                        image, 
                        image_path, 
                        mask_lookup_name=filename, 
                        result_base_name=page_base_name, 
                        default_mask_data=default_mask_data, 
                        use_global_selected_mask=use_global_selected_mask
                    )
                    
                    if full_text:
                        pdf_full_texts.append(f"--- Page {page_idx+1} ---\n{full_text}")
                    else:
                        # Consider if one page fails, does the whole PDF fail?
                        # Let's continue processing other pages.
                        pass
                
                # After all pages
                if pdf_full_texts:
                    combined_text = "\n\n".join(pdf_full_texts)
                    
                    # Update cache and UI
                    self.results_by_filename[filename] = combined_text
                    self.result_manager.store_result(image_path, combined_text)
                    
                    if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                        self.file_processed_signal.emit(filename, combined_text)
                        
                    # Mark as processed
                    input_record_mgr.add_record(filename)
                    output_record_mgr.add_record(filename)

            else:
                # Process Single Image
                original_image = self.file_utils.read_image(image_path)
                if original_image is None:
                    print(f"Failed to read image: {image_path}")
                    continue
                
                full_text, _ = self._process_single_image_task(
                    original_image, 
                    image_path, 
                    mask_lookup_name=filename, 
                    result_base_name=os.path.splitext(filename)[0], 
                    default_mask_data=default_mask_data, 
                    use_global_selected_mask=use_global_selected_mask
                )
                
                if full_text is not None:
                    # Mark as processed
                    input_record_mgr.add_record(filename)
                    output_record_mgr.add_record(filename)
                    
                    self.results_by_filename[filename] = full_text
                    self.result_manager.store_result(image_path, full_text)
                    
                    if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                        self.file_processed_signal.emit(filename, full_text)
            
            self.logger.info(f"完成处理: {image_path}")
            print(f"Finished processing: {image_path}")    
    def _process_files(self, files, output_dir, default_mask_data=None, force_reprocess=False):
        print(f"Processing dropped files to {output_dir}")
        self.performance_monitor.start_timer("total_processing")
        os.makedirs(output_dir, exist_ok=True)
        for i, image_path in enumerate(files):
            if getattr(self, "_stop_flag", False):
                break
                
            # 检查重复处理
            # Handle Virtual Path
            real_path = image_path
            page_suffix = ""
            if "|page=" in image_path:
                parts = image_path.split("|page=")
                if len(parts) == 2:
                    real_path = parts[0]
                    page_suffix = f"_page_{parts[1]}"
            
            # Determine filename and directory
            if page_suffix:
                base_name = os.path.basename(real_path)
                # Construct unique filename: name_page_N.ext
                filename = f"{os.path.splitext(base_name)[0]}{page_suffix}{os.path.splitext(base_name)[1]}"
                current_file_dir = os.path.dirname(real_path)
            else:
                filename = os.path.basename(image_path)
                current_file_dir = os.path.dirname(image_path)
                
            current_output_dir = os.path.join(current_file_dir, "output")
            
            input_record_mgr = RecordManager.get_instance(current_file_dir)
            output_record_mgr = RecordManager.get_instance(current_output_dir)
            
            # 双重核验：必须两个记录都存在，且输出文件实际存在
            is_processed = False
            json_output_file = os.path.join(current_output_dir, "json", f"{os.path.splitext(filename)[0]}.json")
            
            if not force_reprocess:
                if input_record_mgr.is_recorded(filename) and output_record_mgr.is_recorded(filename):
                    if os.path.exists(json_output_file):
                        is_processed = True
            
            if is_processed:
                # 检查结果文件状态
                try:
                    with open(json_output_file, 'r', encoding='utf-8') as f:
                        check_result = json.load(f)
                    
                    if check_result.get('status', 'success') != 'success':
                        print(f"File {filename} was processed with error, reprocessing...")
                        is_processed = False
                except Exception as e:
                    print(f"Error checking cached result for {image_path}: {e}")
                    is_processed = False

            if is_processed:
                print(f"Skipping processed file (loading cache): {image_path}")
                try:
                    with open(json_output_file, 'r', encoding='utf-8') as f:
                        cached_result = json.load(f)
                    
                    full_text = cached_result.get('full_text', '')
                    self.results_by_filename[filename] = full_text
                    self.result_manager.store_result(image_path, full_text)
                    
                    # Emit signal for UI update
                    if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                        self.file_processed_signal.emit(filename, full_text)
                        
                    print(f"Finished processing dropped (cached): {image_path}")
                except Exception as e:
                    print(f"Error loading cached result for {image_path}: {e}")
                    pass
                else:
                    continue
                
            try:
                original_image = self.file_utils.read_image(image_path)
                if original_image is None:
                    continue
                
                # Determine masks
                masks_to_process = []
                try:
                    mask_data = None
                    # filename is already determined at start of loop
                    # filename = os.path.basename(image_path) 
                    bound_mask = self.mask_manager.get_bound_mask(filename)
                    if bound_mask:
                        mask_data = self.mask_manager.get_mask(bound_mask)
                    else:
                        if default_mask_data:
                            mask_data = default_mask_data
                        
                    if mask_data:
                        if isinstance(mask_data, list):
                            if len(mask_data) > 0 and isinstance(mask_data[0], (int, float)):
                                masks_to_process = [{'rect': mask_data, 'label': 1}]
                            else:
                                masks_to_process = mask_data
                                # 按空间位置排序 (从上到下，从左到右)
                                masks_to_process.sort(key=lambda x: (x.get('rect', [0, 0, 0, 0])[1] if x.get('rect') else 0, x.get('rect', [0, 0, 0, 0])[0] if x.get('rect') else 0))
                    
                    if not masks_to_process:
                        masks_to_process = [{'rect': None, 'label': 0}]
                except Exception as e:
                    print(f"Error determining masks for {image_path}: {e}")
                    masks_to_process = [{'rect': None, 'label': 0}]

                file_recognized_texts = []
                file_detailed_results = []
                file_processing_failed = False

                for mask_info in masks_to_process:
                    rect = mask_info.get('rect')
                    image = original_image
                    offset_x, offset_y = 0, 0
                    
                    if rect and len(rect) == 4:
                        try:
                            w, h = image.size if hasattr(image, 'size') else (None, None)
                            if w and h:
                                # 计算原始坐标
                                x1 = int(rect[0] * w)
                                y1 = int(rect[1] * h)
                                x2 = int(rect[2] * w)
                                y2 = int(rect[3] * h)
                                
                                # 增加外扩 (Expansion)
                                # 为了防止用户画框太紧导致边缘文字丢失，这里向四周外扩一定比例或像素
                                # 例如：左右外扩 5%，上下外扩 2%
                                expansion_ratio_w = 0.05  # 宽度外扩 5%
                                expansion_ratio_h = 0.02  # 高度外扩 2%
                                
                                crop_w = x2 - x1
                                crop_h = y2 - y1
                                
                                # 计算外扩量
                                expand_w = int(crop_w * expansion_ratio_w)
                                expand_h = int(crop_h * expansion_ratio_h)
                                
                                # 应用外扩并确保不越界
                                x1 = max(0, x1 - expand_w)
                                y1 = max(0, y1 - expand_h)
                                x2 = min(w, x2 + expand_w)
                                y2 = min(h, y2 + expand_h)
                                
                                offset_x, offset_y = x1, y1
                                image = self.cropper.crop_text_region(image, [x1, y1, x2, y2])
                        except Exception as e:
                             print(f"Mask crop failed for dropped {image_path}: {e}")
                    
                    self.performance_monitor.start_timer("preprocessing")
                    use_preprocessing = True
                    if self.config_manager:
                        use_preprocessing = self.config_manager.get_setting('use_preprocessing', True)
                    if hasattr(self.ui, 'preprocessing_chk'):
                        use_preprocessing = bool(self.ui.preprocessing_chk.isChecked())
                    if use_preprocessing:
                        preprocessed_filename = f"{os.path.splitext(filename)[0]}_part{mask_info.get('label', 0)}"
                        use_padding = getattr(self, "is_padding_enabled", True)
                        image = self.preprocessor.comprehensive_preprocess(
                            image, None, preprocessed_filename, use_padding=use_padding
                        )
                    self.performance_monitor.stop_timer("preprocessing")
                    
                    self.performance_monitor.start_timer("detection")
                    try:
                        if not hasattr(self, 'ocr_engine') or self.ocr_engine is None:
                            self.ocr_engine = OcrEngine(self.config_manager, detector=self.detector, recognizer=self.recognizer)
                        use_table_model = self.config_manager.get_setting('use_table_split', False)
                        process_options = {
                            'skip_preprocessing': True,
                            'use_table_model': use_table_model,
                            'ai_table_model': self.config_manager.get_setting('ai_table_model', 'SLANet'),
                            'use_ai_table': self.config_manager.get_setting('use_ai_table', False)
                        }
                        self.logger.info(f"DEBUG: Batch/Drop processing calling process_image with options: {process_options}")
                        print(f"=== DEBUG: Calling OcrEngine with options: {process_options} ===")
                        result = self.ocr_engine.process_image(image, process_options)
                        text_regions = result.get('regions', [])
                        self.logger.info(f"DEBUG: Batch/Drop process_image returned {len(text_regions)} regions")
                        print(f"=== DEBUG: OcrEngine returned {len(text_regions)} regions. First region keys: {list(text_regions[0].keys()) if text_regions else 'None'} ===")
                    except Exception as e:
                        print(f"Error in OcrEngine processing (batch): {e}")
                        import traceback
                        traceback.print_exc()
                        text_regions = self.detector.detect_text_regions(image)
                    self.performance_monitor.stop_timer("detection")
                    
                    if text_regions is None:
                        print(f"Error: Detection failed for dropped file {image_path}")
                        file_processing_failed = True
                        break

                    part_texts = []
                    current_line_idx = -1
                    current_line_texts = []

                    for region in text_regions:
                        text = region.get('text', '')
                        confidence = region.get('confidence', 0.0)
                        line_idx = region.get('line_index', -1)
                        coordinates = region.get('coordinates', [])
                        
                        if hasattr(coordinates, 'tolist'):
                            coordinates = coordinates.tolist()

                        # Apply mask offset to restore original coordinates
                        if coordinates and (offset_x != 0 or offset_y != 0):
                            new_coords = []
                            for point in coordinates:
                                if isinstance(point, (list, tuple)) and len(point) >= 2:
                                    new_coords.append([point[0] + offset_x, point[1] + offset_y])
                            coordinates = new_coords

                        # 处理换行
                        if line_idx != -1:
                            if current_line_idx != -1 and line_idx != current_line_idx:
                                if current_line_texts:
                                    part_texts.append(" ".join(current_line_texts))
                                    current_line_texts = []
                            current_line_idx = line_idx
                        
                        # 使用原始文本，不进行矫正
                        self.performance_monitor.start_timer("recognition")
                        try:
                            current_line_texts.append(text)
                            
                            res_item = {
                                'text': text,
                                'confidence': confidence,
                                'coordinates': coordinates,
                                'detection_confidence': confidence,
                                'mask_label': mask_info.get('label', 0),
                                'line_index': line_idx
                            }
                            if 'table_info' in region:
                                res_item['table_info'] = region['table_info']
                            
                            file_detailed_results.append(res_item)
                        finally:
                            self.performance_monitor.stop_timer("recognition")
                    
                    # 添加最后一行
                    if current_line_texts:
                        part_texts.append(" ".join(current_line_texts))
                    
                    if part_texts:
                        file_recognized_texts.append("\n".join(part_texts))

                if file_processing_failed:
                    print(f"Skipping result saving for {image_path} due to failure")
                    continue

                full_text = "\n".join(file_recognized_texts)
                # self.results_by_filename[os.path.basename(image_path)] = full_text # Moved to after JSON update
                
                # Create subdirectories for organized output
                # 根据用户需求，输出目录生成到对应输入文件夹的下级中
                current_file_dir = os.path.dirname(image_path)
                current_output_dir = os.path.join(current_file_dir, "output")
                
                txt_output_dir = os.path.join(current_output_dir, "txt")
                json_output_dir = os.path.join(current_output_dir, "json")
                
                os.makedirs(txt_output_dir, exist_ok=True)
                os.makedirs(json_output_dir, exist_ok=True)
                
                output_file = os.path.join(txt_output_dir, f"{os.path.splitext(filename)[0]}_result.txt")
                self.file_utils.write_text_file(output_file, full_text)
                
                json_output_file = os.path.join(json_output_dir, f"{os.path.splitext(filename)[0]}.json")
                json_result = {
                    'image_path': image_path,
                    'filename': filename,
                    'timestamp': datetime.now().isoformat(),
                    'full_text': full_text,
                    'regions': file_detailed_results,
                    'status': 'success'
                }
                self.file_utils.write_json_file(json_output_file, json_result)
                self.results_json_by_filename[filename] = json_result # Update memory cache
                self.results_by_filename[filename] = full_text # Update text cache AFTER JSON cache
                
                self.result_manager.store_result(image_path, full_text)
                
                # Emit signal for UI update
                if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                    self.file_processed_signal.emit(filename, full_text)
                
                # 记录已处理
                input_record_mgr.add_record(filename)
                output_record_mgr.add_record(filename)
                
                print(f"Finished processing dropped: {image_path}")
            except Exception as e:
                print(f"Error processing dropped file {image_path}: {e}")
                continue
        export_path = self.result_manager.export_results(output_dir, 'json')
        print(f"Results exported to: {export_path}")
        total_time = self.performance_monitor.stop_timer("total_processing")
        self.logger.info(f"处理完成，总耗时: {total_time:.2f}秒")
        print(f"Total processing time: {total_time:.2f} seconds")
        
        # UI 更新在主线程的定时器中完成
        
        # 打印性能统计
        stats = self.performance_monitor.get_stats()
        for task, stat in stats.items():
            self.logger.info(f"{task}: 平均{stat['average']:.2f}秒, 总计{stat['count']}次, 总耗时{stat['total']:.2f}秒")
            print(f"{task}: 平均{stat['average']:.2f}秒, 总计{stat['count']}次, 总耗时{stat['total']:.2f}秒")

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
                
                json_path = os.path.join(base_dir, "output", "json", f"{base_name}.json")
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not text:
                            text = data.get('full_text', '')
                        if not json_data:
                            json_data = data
                
                if not text:
                    txt_path = os.path.join(base_dir, "output", "txt", f"{base_name}_result.txt")
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
        
        menu.exec_(self.ui.image_list.mapToGlobal(position))

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
            
        if QMessageBox.question(self.main_window, "确认", 
                              f"确定要重新处理选中的 {len(files_to_process)} 个文件吗？\n这将覆盖现有的结果。",
                              QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
            
        # 如果正在处理中，不允许重新处理
        if self.processing_thread and self.processing_thread.is_alive():
            QMessageBox.warning(self.main_window, "提示", "当前有任务正在进行中，请等待完成后再操作")
            return

        self._start_processing_files(files_to_process, force_reprocess=True)

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
                self.folder_list_items[file_name] = file_path
                added_count += 1
        
        if added_count > 0:
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
            
            self.ui.folder_list.addItem(item)
            self.folder_list_items[folder_name] = directory
            self._update_folder_mask_display(directory)
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
            self.ui.status_label.setText(f"已移除: {name}")

    def _clear_all_folders(self):
        """清空所有项目"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        if self.folders:
            self.folders.clear()
            self.folder_list_items.clear()
            self.ui.folder_list.clear()
            self.ui.status_label.setText("已清空所有项目")

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
        if not PYQT_AVAILABLE:
            return
            
        db_dir = os.path.join(self.project_root, "databases")
        dialog = DbManagerDialog(db_dir, self.main_window)
        dialog.exec_()

    def _open_db_import_dialog(self):
        """打开数据库导入对话框"""
        if not PYQT_AVAILABLE:
            return
            
        # 选择导入模式
        items = ["从TXT/JSON数据文件导入", "导入现有数据库文件(.db)"]
        item, ok = QInputDialog.getItem(self.main_window, "选择导入方式", "请选择导入类型:", items, 0, False)
        if not ok or not item:
            return
            
        if item == "导入现有数据库文件(.db)":
            self._import_existing_db()
        else:
            self._import_from_data_files()
            
    def _import_existing_db(self):
        """导入现有数据库文件"""
        source_db, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "选择现有数据库文件",
            "",
            "SQLite Database (*.db);;All Files (*)"
        )
        if not source_db:
            return
            
        import shutil
        
        # 目标目录
        db_dir = os.path.join(self.project_root, "databases")
        os.makedirs(db_dir, exist_ok=True)
        
        # 目标文件名 (保持原名，如果有重名则询问)
        base_name = os.path.basename(source_db)
        target_path = os.path.join(db_dir, base_name)
        
        if os.path.exists(target_path):
             # 询问是否覆盖或重命名
             reply = QMessageBox.question(
                 self.main_window, 
                 "文件已存在", 
                 f"数据库 '{base_name}' 已存在。\n是否覆盖？\n(选择No则取消导入)",
                 QMessageBox.Yes | QMessageBox.No
             )
             if reply != QMessageBox.Yes:
                 return
                 
        try:
            shutil.copy2(source_db, target_path)
            QMessageBox.information(self.main_window, "成功", f"数据库已成功导入到:\n{target_path}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"导入数据库失败: {e}")

    def _import_from_data_files(self):
        """从数据文件导入"""
        # 1. 选择源目录
        input_dir = QFileDialog.getExistingDirectory(
            self.main_window, 
            "选择源目录 (将递归查找 .txt/.json)",
            self.project_root
        )
        if not input_dir:
            return
            
        # 2. 选择目标数据库
        items = ["新建数据库", "选择现有数据库"]
        item, ok = QInputDialog.getItem(self.main_window, "选择目标数据库", "请选择:", items, 0, False)
        if not ok or not item:
            return

        db_path = ""
        if item == "新建数据库":
             db_name, ok = QInputDialog.getText(self.main_window, "新建数据库", "请输入数据库名称 (无需后缀):")
             if not ok or not db_name:
                 return
             db_dir = os.path.join(self.project_root, "databases")
             os.makedirs(db_dir, exist_ok=True)
             db_path = os.path.join(db_dir, f"{db_name}.db")
             if os.path.exists(db_path):
                 if QMessageBox.question(self.main_window, "确认", "数据库已存在，是否覆盖？") != QMessageBox.Yes:
                     return
        else: # 选择现有数据库
             db_dir = os.path.join(self.project_root, "databases")
             selection_dialog = DbSelectionDialog(db_dir, self.main_window)
             if selection_dialog.exec_() == QDialog.Accepted:
                 db_path = selection_dialog.selected_db_path
             else:
                 return
        
        if not db_path:
             return
            
        # 3. 执行导入 (使用进度条)
        try:
            from PyQt5.QtWidgets import QProgressDialog
            from PyQt5.QtCore import Qt
            from PyQt5.QtWidgets import QApplication
            
            # 创建进度对话框 (初始范围未知)
            progress = QProgressDialog("正在扫描文件...", "取消", 0, 0, self.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            
            importer = DatabaseImporter(db_path)
            
            def progress_callback(current, total, filename):
                if progress.wasCanceled():
                    return
                if progress.maximum() != total:
                    progress.setMaximum(total)
                progress.setValue(current)
                progress.setLabelText(f"正在处理 ({current}/{total}): {filename}")
                QApplication.processEvents()
                
            processed_count, added_records = importer.import_from_directory(input_dir, progress_callback)
            
            progress.setValue(progress.maximum())
            
            if progress.wasCanceled():
                QMessageBox.warning(self.main_window, "已取消", "导入过程已取消")
            else:
                QMessageBox.information(
                    self.main_window, 
                    "导入完成", 
                    f"数据库: {os.path.basename(db_path)}\n处理文件数: {processed_count}\n新增记录数: {added_records}"
                )
            
        except Exception as e:
            self.logger.error(f"数据库导入失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"数据库导入失败: {e}")

    def _open_db_import_dialog(self):
        """打开数据库导入对话框"""
        # ... (previous implementation logic if exists or generic file picker)
        # Note: If this method already exists, we should just check it.
        # But based on read, it's not visible here. I'll add the new dialog handler.
        
        # This seems to be missing in the previous read. I will add the _open_field_binding_dialog.

    def _open_field_binding_dialog(self):
        """打开可视化字段绑定工作台"""
        if not PYQT_AVAILABLE:
            return
            
        # 直接打开对话框，不依赖主窗口选图
        dialog = FieldBindingDialog(self.main_window, config_manager=self.config_manager)
        dialog.config_saved.connect(self._on_binding_config_saved)
        dialog.exec_()
        
        # Clear cache and refresh current view after dialog closes
        # This ensures that if files were reprocessed in the dialog, the main window reflects the changes
        self.results_json_by_filename.clear()
        self.results_by_filename.clear()
        
        if self.ui and hasattr(self.ui, 'image_list'):
            current_item = self.ui.image_list.currentItem()
            if current_item:
                self._display_result_for_item(current_item)

    def _on_binding_config_saved(self, config):
        """处理保存的绑定配置"""
        print(f"Binding config saved: {config}")
        # 保存到本地配置或数据库
        # 这里我们可以将其保存为一种特殊的"导入模板"
        template_name = config.get('template_name')
        if template_name:
            # Save to templates directory
            templates_dir = os.path.join(os.getcwd(), 'templates')
            os.makedirs(templates_dir, exist_ok=True)
            save_path = os.path.join(templates_dir, f"{template_name}.json")
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self.main_window, "成功", f"模板 '{template_name}' 已保存")

    def _open_db_query_dialog(self):
        """打开数据库查询对话框"""
        if not PYQT_AVAILABLE:
            return
            
        # 数据库目录
        db_dir = os.path.join(self.project_root, "databases")
        
        # 使用自定义选择对话框
        selection_dialog = DbSelectionDialog(db_dir, self.main_window)
        if selection_dialog.exec_() == QDialog.Accepted:
            db_path = selection_dialog.selected_db_path
            if db_path and os.path.exists(db_path):
                dialog = DbQueryDialog(db_path, self.main_window)
                dialog.exec_()
            else:
                QMessageBox.warning(self.main_window, "提示", "所选数据库文件不存在")

    def toggle_screenshot_mode(self, enabled):
        """Toggle Screenshot Auto-OCR Mode"""
        if not hasattr(self, 'clipboard_watcher') or not self.clipboard_watcher:
            return
            
        if enabled:
            self.clipboard_watcher.start()
            self.logger.info("Screenshot Auto-OCR Mode Enabled")
            
            # Hide main window and show tray
            if self.main_window:
                self.tray_icon.show()
                self.tray_icon.showMessage("自动截屏识别已开启", "软件已隐藏到后台，监测到截屏时将自动识别。\n双击托盘图标可恢复主界面。", QSystemTrayIcon.Information, 3000)
                self.main_window.hide()
                
            if hasattr(self, 'act_stop_screenshot_mode'):
                self.act_stop_screenshot_mode.setVisible(True)
        else:
            self.clipboard_watcher.stop()
            self.logger.info("Screenshot Auto-OCR Mode Disabled")
            if self.main_window:
                self.main_window.showNormal()
                self.main_window.activateWindow()
                self.tray_icon.hide()
                self.main_window.statusBar().showMessage("自动截屏识别模式已关闭")
                
            if hasattr(self, 'act_stop_screenshot_mode'):
                self.act_stop_screenshot_mode.setVisible(False)

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
