# -*- coding: utf-8 -*-

"""
主窗口（集成所有UI组件和交互逻辑）
"""

import os
import threading
import json
from datetime import datetime

from app.core.process_manager import ProcessManager
from app.core.mask_manager import MaskManager
from app.core.service_registry import ServiceRegistry
from app.core.clipboard_watcher import ClipboardWatcher

try:
    from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QInputDialog, QListWidgetItem, QDialog, QTabWidget, QAction, QSystemTrayIcon, QMenu, QApplication, QStyle, QCheckBox
    from PyQt5.QtGui import QIcon
    from PyQt5.QtCore import QTimer, Qt, QEvent, QFileSystemWatcher, QThread, pyqtSignal
    from app.ui.widgets.floating_result_widget import FloatingResultWidget
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, using console mode")

# Define Worker Thread
if PYQT_AVAILABLE:
    class ProcessingWorker(QThread):
        def __init__(self, target, *args, **kwargs):
            super().__init__()
            self.target = target
            self.args = args
            self.kwargs = kwargs

        def run(self):
            try:
                self.target(*self.args, **self.kwargs)
            except Exception as e:
                print(f"Error in processing thread: {e}")
                import traceback
                traceback.print_exc()

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
    from app.ui.widgets.card_sort_widget import CardSortWidget
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


class HttpOcrBatchService:
    def __init__(self, main_window, base_url: str, logger=None, timeout: float = 60.0):
        self.main_window = main_window
        self.base_url = base_url.rstrip("/")
        self.logger = logger
        self.timeout = timeout

    def _post_json(self, path: str, payload: dict):
        import json as _json
        from urllib import request as _request, error as _error

        url = f"{self.base_url}{path}"
        data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = _request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with _request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                text = body.decode("utf-8", errors="ignore")
                try:
                    result = _json.loads(text or "{}")
                except Exception:
                    result = {"error": "invalid_json_response", "raw": text}
        except _error.URLError as e:
            raise RuntimeError(f"OCR HTTP request failed: {e}") from e

        if self.logger:
            self.logger.info(f"OCR HTTP {path} response: {result}")
        return result

    def process_folders(self, folders_to_process=None):
        self.main_window._process_multiple_folders(folders_to_process=folders_to_process)

    def process_files(self, files, output_dir, default_mask_data=None, force_reprocess=False):
        self.main_window._process_files(files, output_dir, default_mask_data=default_mask_data, force_reprocess=force_reprocess)

    def predict(self, image):
        """
        Send image to server for OCR prediction
        """
        import base64
        import io
        from PIL import Image
        import numpy as np
        
        # Convert numpy array to PIL Image if necessary
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Convert PIL image to base64
        buffered = io.BytesIO()
        # Ensure image is in RGB mode
        if hasattr(image, 'mode') and image.mode != 'RGB':
             image = image.convert('RGB')
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        payload = {
            "image_base64": img_str,
            "options": {"use_gpu": self.main_window.config_manager.get_setting('use_gpu', False)}
        }
        
        try:
            resp = self._post_json("/ocr/predict", payload)
            if resp.get("status") == "success":
                # Convert server result format to Detector format
                # Server returns: {'full_text': '...', 'regions': [...]}
                # Detector expects: [{'text': '...', ...}, ...] (list of regions)
                result = resp.get("result", [])
                if isinstance(result, dict) and 'regions' in result:
                    return result['regions']
                return result
            else:
                print(f"OCR Server Error: {resp.get('error')}")
                return None
        except Exception as e:
            print(f"Prediction failed: {e}")
            return None


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
        
        # 检查并下载模型 (在OCR组件初始化之前)
        if PYQT_AVAILABLE and is_gui_mode:
            self._check_and_download_models(is_gui_mode)
        
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
        
        # Initialize OCR Service based on configuration
        ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
        if ocr_server_url:
            try:
                self.ocr_service = HttpOcrBatchService(self, ocr_server_url, logger=self.logger)
                print(f"Initialized in Online Mode: {ocr_server_url}")
            except Exception as e:
                print(f"Failed to initialize Online Mode: {e}")
                # User requested strict online mode if configured, but for safety in initialization we might need a fallback
                # However, since user explicitly said "don't use local if I set online", we should respect that intent
                # But to avoid crash on startup, we might keep it as None or a dummy that raises error on usage
                # For now, let's just log it. If self.ocr_service is not set, it might crash later, so let's set it to HttpOcrBatchService anyway
                # which will fail during predict if url is bad, but won't silently use local.
                self.ocr_service = HttpOcrBatchService(self, ocr_server_url, logger=self.logger)
        else:
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
                
                # 初始化UI控件状态
                # if hasattr(self.ui, 'padding_chk'):
                #     self.ui.padding_chk.setChecked(self.is_padding_enabled)

                # Initialize model selector state based on online mode
                ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
                is_online = bool(ocr_server_url)
                # if hasattr(self.ui, 'model_selector'):
                    # Rename items to "Mode" instead of "Model"
                    # self.ui.model_selector.clear()
                    # self.ui.model_selector.addItems(["默认模式", "高精度模式", "快速模式"])
                    
                    # self.ui.model_selector.setEnabled(not is_online)
                    # if is_online:
                    #     self.ui.model_selector.setToolTip("联机模式下无法调整本地模型参数")
                    # else:
                    #     self.ui.model_selector.setToolTip("选择本地OCR处理模式")
                
                
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
            
        # 如果配置了在线OCR服务，则不需要下载本地模型
        ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
        if ocr_server_url:
            return

        model_manager = self.config_manager.model_manager
        defaults = [
            ('det', 'ch_PP-OCRv4_det', "中文检测模型"),
            ('rec', 'ch_PP-OCRv4_rec', "中文识别模型"),
            ('cls', 'ch_ppocr_mobile_v2.0_cls', "方向分类模型")
        ]
        
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
            
            # Padding connection - Removed as requested (UI element removed)
            # if hasattr(self.ui, 'padding_chk'):
            #     self.ui.padding_chk.stateChanged.connect(self._on_padding_changed)
            
            # Mask connections
            if hasattr(self.ui, 'mask_btn_enable'):
                self.ui.mask_btn_enable.clicked.connect(self._toggle_mask_drawing)
            if hasattr(self.ui, 'mask_chk_use'):
                self.ui.mask_chk_use.stateChanged.connect(self._on_use_mask_changed)
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

            # Card Sort Widget connection
            if hasattr(self.ui, 'card_sort_widget') and self.ui.card_sort_widget:
                self.ui.card_sort_widget.data_changed.connect(self._on_card_data_changed)
                if hasattr(self.ui, 'card_cols_spin') and self.ui.card_cols_spin:
                    self.ui.card_cols_spin.valueChanged.connect(self.ui.card_sort_widget.set_columns)

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

    # def _on_padding_changed(self, state):
    #     """边缘填充开关变化处理"""
    #     is_enabled = (state == Qt.Checked)
    #     self.is_padding_enabled = is_enabled
    #     self.config_manager.set_setting('use_padding', is_enabled)
    #     self.config_manager.save_config()
    #     print(f"Padding {'enabled' if is_enabled else 'disabled'}")
        
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
                            if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
                                dropped_files.append(local_path)
                    for fp in dropped_files:
                        name = os.path.basename(fp)
                        self.file_map[name] = fp
                        item = QListWidgetItem(name)
                        self.ui.image_list.addItem(item)
                        # Select the last added item
                        self.ui.image_list.setCurrentItem(item)
                    if dropped_files:
                        if self.processing_thread and self.processing_thread.is_alive():
                            if self.ui:
                                self.ui.status_label.setText("正在处理，请稍后再拖拽")
                        else:
                            self._start_processing_files(dropped_files)
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
                            if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
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

            # Only reload if we are in local mode
            ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
            if not ocr_server_url:
                print(f"Reloading local OCR engine for {model_name}...")
                try:
                    self.detector = Detector(self.config_manager)
                    self.recognizer = Recognizer(self.config_manager)
                    
                    # Update status
                    if hasattr(self.ui, 'status_label'):
                        self.ui.status_label.setText(f"已切换到: {model_name}")
                except Exception as e:
                     print(f"Error reloading OCR engine: {e}")
                     if hasattr(self.ui, 'status_label'):
                        self.ui.status_label.setText(f"切换失败: {e}")
            else:
                 # In online mode
                 print("Model switch only affects local mode settings")
                 if hasattr(self.ui, 'status_label'):
                    self.ui.status_label.setText(f"模型设置已更新 (仅本地模式生效)")

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
            
            # 初始化 CheckBox 状态
            if hasattr(self.ui, 'mask_chk_use'):
                self.ui.mask_chk_use.setChecked(self.config_manager.get_setting('use_mask', False))
                
            if hasattr(self.ui, 'table_split_chk'):
                use_split = self.config_manager.get_setting('use_table_split', False)
                self.ui.table_split_chk.setChecked(use_split)
                
            if hasattr(self.ui, 'table_split_combo'):
                mode = self.config_manager.get_setting('table_split_mode', 'horizontal')
                mode_map = {'horizontal': 0, 'vertical': 1, 'cell': 2}
                self.ui.table_split_combo.setCurrentIndex(mode_map.get(mode, 0))
                self.ui.table_split_combo.setEnabled(self.config_manager.get_setting('use_table_split', False))
            
            # 延迟更新蒙版列表，确保UI完全显示
            if PYQT_AVAILABLE:
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
                ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
                is_online = bool(ocr_server_url)
                
                # 1. 如果模型设置改变且在本地模式，重新初始化OCR组件
                if 'model' in changed_categories and not is_online:
                    print("Reloading OCR models...")
                    self.detector = Detector(self.config_manager)
                    self.recognizer = Recognizer(self.config_manager)
                
                # 2. 如果处理设置改变
                if 'processing' in changed_categories:
                    self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)
                    
                # 3. 如果OCR服务设置改变
                if 'ocr_service' in changed_categories or True: # Always check online status to update UI
                    if is_online:
                        try:
                            # 切换到在线服务
                            self.ocr_service = HttpOcrBatchService(self, ocr_server_url, logger=self.logger)
                            ServiceRegistry.register("ocr_batch", self.ocr_service)
                            print(f"Switched to OCR HTTP service: {ocr_server_url}")
                            
                            # Disable local model selector in online mode
                            if hasattr(self.ui, 'model_selector'):
                                self.ui.model_selector.setEnabled(False)
                                self.ui.model_selector.setToolTip("联机模式下无法调整本地模型参数")
                                
                        except Exception as e:
                            print(f"Failed to switch to OCR HTTP service: {e}")
                            QMessageBox.warning(self.main_window, "警告", f"切换到OCR服务失败: {e}")
                    else:
                        # 切换回本地服务
                        self.ocr_service = OcrBatchService(self)
                        ServiceRegistry.register("ocr_batch", self.ocr_service)
                        print("Switched to Local OCR service")
                        
                        # Enable local model selector in local mode
                        if hasattr(self.ui, 'model_selector'):
                            self.ui.model_selector.setEnabled(True)
                            self.ui.model_selector.setToolTip("选择本地OCR处理模式")
                        
                        # 如果从在线切回本地，可能需要确保Detector已初始化
                        if self.detector is None or self.detector.ocr_engine is None:
                            self.detector = Detector(self.config_manager)
                            self.recognizer = Recognizer(self.config_manager)

        except Exception as e:
            self.logger.error(f"打开设置对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"打开设置对话框失败: {e}")

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
                # if hasattr(self.ui, 'padding_chk'):
                #     self.is_padding_enabled = bool(self.ui.padding_chk.isChecked())
                #     self.config_manager.set_setting('use_padding', self.is_padding_enabled)
                self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)
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
                # if hasattr(self.ui, 'padding_chk'):
                #     self.is_padding_enabled = bool(self.ui.padding_chk.isChecked())
                #     self.config_manager.set_setting('use_padding', self.is_padding_enabled)
                self.is_padding_enabled = self.config_manager.get_setting('use_padding', True)
                
                # 保存表格拆分设置
                if hasattr(self.ui, 'table_split_chk'):
                    use_table_split = bool(self.ui.table_split_chk.isChecked())
                    self.config_manager.set_setting('use_table_split', use_table_split)
                    
                    if hasattr(self.ui, 'table_split_combo'):
                        mode_map = {0: 'horizontal', 1: 'vertical', 2: 'cell'}
                        idx = self.ui.table_split_combo.currentIndex()
                        split_mode = mode_map.get(idx, 'horizontal')
                        self.config_manager.set_setting('table_split_mode', split_mode)
                
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
            filename = os.path.basename(image_path)
            current_file_dir = os.path.dirname(image_path)
            current_output_dir = os.path.join(current_file_dir, "output")
            
            input_record_mgr = RecordManager.get_instance(current_file_dir)
            output_record_mgr = RecordManager.get_instance(current_output_dir)
            
            # 双重核验：必须两个记录都存在，且输出文件实际存在
            is_processed = False
            json_output_file = os.path.join(current_output_dir, "json", f"{os.path.splitext(filename)[0]}.json")
            
            if input_record_mgr.is_recorded(filename) and output_record_mgr.is_recorded(filename):
                if os.path.exists(json_output_file):
                    is_processed = True
            
            if is_processed:
                # 检查结果文件状态
                try:
                    with open(json_output_file, 'r', encoding='utf-8') as f:
                        cached_result = json.load(f)
                    
                    if cached_result.get('status', 'success') != 'success':
                        print(f"File {filename} was processed with error, reprocessing...")
                        is_processed = False
                except Exception as e:
                    print(f"Error checking cached result for {image_path}: {e}")
                    is_processed = False

            if is_processed:
                self.logger.info(f"跳过已处理文件 (加载缓存): {image_path}")
                print(f"Skipping processed file (loading cache): {image_path}")
                
                # 加载已有结果
                try:
                    full_text = cached_result.get('full_text', '')
                    self.results_by_filename[os.path.basename(image_path)] = full_text
                    self.result_manager.store_result(image_path, full_text)
                    
                    # Emit signal for UI update
                    if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                        self.file_processed_signal.emit(os.path.basename(image_path), full_text)
                    
                    # 如果有UI更新需求，可以在这里触发
                    # 但在批量处理中，通常是在最后或定时器中更新UI
                except Exception as e:
                    print(f"Error loading cached result for {image_path}: {e}")
                    # 如果加载失败，视为未处理，继续处理
                    pass
                else:
                    continue
            
            self.logger.info(f"处理图像 ({i+1}/{len(image_files)}): {image_path}")
            print(f"Processing image ({i+1}/{len(image_files)}): {image_path}")
            
            # 读取图像
            original_image = self.file_utils.read_image(image_path)
            if original_image is None:
                print(f"Failed to read image: {image_path}")
                continue
            
            # 确定使用的蒙版列表
            masks_to_process = []
            try:
                mask_data = None
                filename = os.path.basename(image_path)
                
                # 优先级: 1. 图像绑定的模板 2. 文件夹级别的模板 3. 全局默认模板
                bound_mask = self.mask_manager.get_bound_mask(filename)
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
                    
                # 打印调试信息
                print(f"Processing image {image_path} with masks: {masks_to_process}")
                
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
                            # 为了防止用户画框太紧导致边缘文字丢失，这里向四周外扩一定比例或像素
                            # 例如：左右外扩 5%，上下外扩 2%，或者固定像素
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
                
                if use_preprocessing:
                    preprocessed_filename = f"{os.path.splitext(os.path.basename(image_path))[0]}_part{mask_info.get('label', 0)}"
                    use_padding = getattr(self, "is_padding_enabled", True)
                    # 预处理时不保存临时文件
                    image = self.preprocessor.comprehensive_preprocess(image, None, preprocessed_filename, use_padding=use_padding)
                self.performance_monitor.stop_timer("preprocessing")
                
                # 检测与识别
                self.performance_monitor.start_timer("detection")
                
                # Strict Mode Check: If online mode is configured, DO NOT use local detector
                ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
                
                if ocr_server_url:
                    # Online Mode
                    if hasattr(self, 'ocr_service') and isinstance(self.ocr_service, HttpOcrBatchService):
                        text_regions = self.ocr_service.predict(image)
                    else:
                        # Should not happen if initialized correctly, but strictly enforce online
                        print("Warning: Online mode configured but service mismatch. Forcing online usage.")
                        temp_service = HttpOcrBatchService(self, ocr_server_url, logger=self.logger)
                        text_regions = temp_service.predict(image)
                else:
                    # Local Mode
                    text_regions = self.detector.detect_text_regions(image)
                    
                self.performance_monitor.stop_timer("detection")
                
                if text_regions is None:
                    print(f"Error: Detection failed for {image_path} (mask {mask_info.get('label', 0)})")
                    file_processing_failed = True
                    break

                # 提取文本
                part_texts = []
                current_line_idx = -1
                current_line_texts = []
                
                # 获取置信度阈值
                drop_score = 0.5
                if self.config_manager:
                    drop_score = float(self.config_manager.get_setting('drop_score', 0.5))
                
                for j, region in enumerate(text_regions):
                    self.performance_monitor.start_timer("recognition")
                    try:
                        text = region.get('text', '')
                        confidence = region.get('confidence', 0.0)
                        line_idx = region.get('line_index', -1)
                        
                        # 过滤低置信度结果
                        if confidence < drop_score:
                            print(f"Filtered low confidence result: '{text}' (score: {confidence:.4f} < threshold: {drop_score})")
                            continue
                            
                        coordinates = region.get('coordinates', [])
                        
                        if hasattr(coordinates, 'tolist'):
                            coordinates = coordinates.tolist()
                        
                        # 处理换行
                        if line_idx != -1:
                            if current_line_idx != -1 and line_idx != current_line_idx:
                                if current_line_texts:
                                    part_texts.append(" ".join(current_line_texts))
                                    current_line_texts = []
                            current_line_idx = line_idx
                        
                        # 使用原始文本，不进行矫正
                        current_line_texts.append(text)
                        
                        file_detailed_results.append({
                            'text': text,
                            'confidence': confidence,
                            'coordinates': coordinates,
                            'detection_confidence': confidence,
                            'mask_label': mask_info.get('label', 0),
                            'line_index': line_idx
                        })
                    except Exception as e:
                        self.logger.error(f"Error processing region {j} in {image_path}: {e}")
                    finally:
                        self.performance_monitor.stop_timer("recognition")
                
                # 添加最后一行
                if current_line_texts:
                    part_texts.append(" ".join(current_line_texts))
                
                if part_texts:
                    file_recognized_texts.append("\n".join(part_texts))
                
            if file_processing_failed:
                print(f"Skipping result saving for {image_path} due to failure")
            else:
                full_text = "\n".join(file_recognized_texts)
                # self.results_by_filename[os.path.basename(image_path)] = full_text # Moved to after JSON update to ensure consistency
                
                # Create subdirectories for organized output
                # 根据用户需求，输出目录生成到对应输入文件夹的下级中
                current_file_dir = os.path.dirname(image_path)
                current_output_dir = os.path.join(current_file_dir, "output")
                
                txt_output_dir = os.path.join(current_output_dir, "txt")
                json_output_dir = os.path.join(current_output_dir, "json")
                
                os.makedirs(txt_output_dir, exist_ok=True)
                os.makedirs(json_output_dir, exist_ok=True)
                
                # Save TXT
                output_file = os.path.join(txt_output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}_result.txt")
                try:
                    self.file_utils.write_text_file(output_file, full_text)
                except Exception as e:
                    print(f"Warning: Failed to write TXT file {output_file}: {e}")
                
                # Save JSON
                json_output_file = os.path.join(json_output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}.json")
                try:
                    json_result = {
                        'image_path': image_path,
                        'filename': os.path.basename(image_path),
                        'timestamp': datetime.now().isoformat(),
                        'full_text': full_text,
                        'regions': file_detailed_results,
                        'status': 'success'
                    }
                    self.file_utils.write_json_file(json_output_file, json_result)
                    self.results_json_by_filename[os.path.basename(image_path)] = json_result
                except Exception as e:
                    print(f"Warning: Failed to write JSON file {json_output_file}: {e}")
                
                self.results_by_filename[os.path.basename(image_path)] = full_text
                    
                # 存储结果
                self.result_manager.store_result(image_path, full_text)
                
                # Emit signal for UI update
                if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                    self.file_processed_signal.emit(os.path.basename(image_path), full_text)
                
                # 记录已处理
                input_record_mgr.add_record(filename)
                output_record_mgr.add_record(filename)
            
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
                    self.results_by_filename[os.path.basename(image_path)] = full_text
                    self.result_manager.store_result(image_path, full_text)
                    
                    # Emit signal for UI update
                    if PYQT_AVAILABLE and hasattr(self, 'file_processed_signal'):
                        self.file_processed_signal.emit(os.path.basename(image_path), full_text)
                        
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
                    filename = os.path.basename(image_path)
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
                    preprocessed_filename = f"{os.path.splitext(os.path.basename(image_path))[0]}_part{mask_info.get('label', 0)}"
                    use_padding = getattr(self, "is_padding_enabled", True)
                    # 预处理时不保存临时文件
                    image = self.preprocessor.comprehensive_preprocess(image, None, preprocessed_filename, use_padding=use_padding)
                    self.performance_monitor.stop_timer("preprocessing")
                    
                    self.performance_monitor.start_timer("detection")
                    
                    # Strict Mode Check: If online mode is configured, DO NOT use local detector
                    ocr_server_url = self.config_manager.get_setting('ocr_server_url', '')
                    
                    if ocr_server_url:
                        # Online Mode
                        if hasattr(self, 'ocr_service') and isinstance(self.ocr_service, HttpOcrBatchService):
                            text_regions = self.ocr_service.predict(image)
                        else:
                            # Should not happen if initialized correctly, but strictly enforce online
                            print("Warning: Online mode configured but service mismatch. Forcing online usage.")
                            temp_service = HttpOcrBatchService(self, ocr_server_url, logger=self.logger)
                            text_regions = temp_service.predict(image)
                    else:
                        # Local Mode
                        text_regions = self.detector.detect_text_regions(image)
                        
                    self.performance_monitor.stop_timer("detection")
                    
                    if text_regions is None:
                        print(f"Error: Detection failed for dropped file {image_path}")
                        file_processing_failed = True
                        break

                    part_texts = []
                    current_line_idx = -1
                    current_line_texts = []
                    
                    # 获取置信度阈值
                    drop_score = 0.5
                    if self.config_manager:
                        drop_score = float(self.config_manager.get_setting('drop_score', 0.5))

                    for region in text_regions:
                        text = region.get('text', '')
                        confidence = region.get('confidence', 0.0)
                        line_idx = region.get('line_index', -1)
                        
                        # 过滤低置信度结果
                        if confidence < drop_score:
                            print(f"Filtered low confidence result (batch): '{text}' (score: {confidence:.4f} < threshold: {drop_score})")
                            continue

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
                            file_detailed_results.append({
                                'text': text,
                                'confidence': confidence,
                                'coordinates': coordinates,
                                'detection_confidence': confidence,
                                'mask_label': mask_info.get('label', 0),
                                'line_index': line_idx
                            })
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
                
                output_file = os.path.join(txt_output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}_result.txt")
                self.file_utils.write_text_file(output_file, full_text)
                
                json_output_file = os.path.join(json_output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}.json")
                json_result = {
                    'image_path': image_path,
                    'filename': os.path.basename(image_path),
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
                    self.file_processed_signal.emit(os.path.basename(image_path), full_text)
                
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
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 1. 尝试从内存获取
        text = self.results_by_filename.get(filename, "")
        json_data = self.results_json_by_filename.get(filename, None)
        
        # 2. 如果内存没有，尝试从文件缓存加载
        # 如果内存中有text但没有json_data，也尝试加载json以补充
        if (not text or not json_data) and filename in self.file_map:
            image_path = self.file_map[filename]
            try:
                # 构建缓存路径
                base_dir = os.path.dirname(image_path)
                base_name = os.path.splitext(filename)[0]
                
                # 优先尝试 JSON
                json_path = os.path.join(base_dir, "output", "json", f"{base_name}.json")
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not text:
                            text = data.get('full_text', '')
                        if not json_data:
                            json_data = data
                
                # 其次尝试 TXT
                if not text:
                    txt_path = os.path.join(base_dir, "output", "txt", f"{base_name}_result.txt")
                    if os.path.exists(txt_path):
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            text = f.read()
                            
                # 如果找到了缓存结果，更新到内存
                if text:
                    self.results_by_filename[filename] = text
                    self.result_manager.store_result(image_path, text)
                    print(f"Loaded cached result for {filename}")
                
                if json_data:
                    self.results_json_by_filename[filename] = json_data
                    
            except Exception as e:
                print(f"Error loading cache for {filename}: {e}")
                
        self.ui.result_display.setPlainText(text)
        
        # 更新 CardSortWidget
        if hasattr(self.ui, 'card_sort_widget') and self.ui.card_sort_widget:
            if json_data and 'regions' in json_data:
                regions = json_data['regions']
                items = []
                for r in regions:
                    # 转换坐标格式: 4点 -> [x1, y1, x2, y2]
                    box = None
                    coords = r.get('coordinates')
                    if coords is not None and len(coords) > 0:
                        try:
                            if len(coords) == 4 and isinstance(coords[0], list): # [[x,y],...]
                                xs = [p[0] for p in coords]
                                ys = [p[1] for p in coords]
                                box = [min(xs), min(ys), max(xs), max(ys)]
                            elif len(coords) == 4 and isinstance(coords[0], (int, float)): # [x1, y1, x2, y2]
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
                
                # 使用单字段 "内容"
                fields = [('content', '内容')]
                self.ui.card_sort_widget.setup(fields, items)
            elif text:
                # 只有文本，按行分割
                lines = [line for line in text.split('\n') if line.strip()]
                items = [{'text': line, 'box': None, 'is_empty': False, 'original_data': None} for line in lines]
                fields = [('content', '内容')]
                self.ui.card_sort_widget.setup(fields, items)
            else:
                self.ui.card_sort_widget.setup([], [])

    def _on_card_data_changed(self, items):
        """处理卡片排序控件数据变化"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        current_item = self.ui.image_list.currentItem()
        if not current_item:
            return
            
        filename = current_item.text()
        
        # 1. 更新全文本
        texts = [item.get('text', '') for item in items if not item.get('is_empty')]
        full_text = "\n".join(texts)
        
        # 更新UI文本显示
        self.ui.result_display.setPlainText(full_text)
        
        # 更新内存
        self.results_by_filename[filename] = full_text
        if filename in self.file_map:
            self.result_manager.store_result(self.file_map[filename], full_text)
            
        # 2. 更新JSON数据
        if filename in self.results_json_by_filename:
            json_data = self.results_json_by_filename[filename]
            
            # 更新regions
            new_regions = []
            for item in items:
                if item.get('is_empty'):
                    continue
                    
                # 优先使用原始数据保留坐标和置信度
                original = item.get('original_data')
                
                coords = []
                confidence = 1.0
                
                # 如果有原始数据且文本未变，可能只是移动了位置，坐标仍有效
                # 但如果是合并后的，就没有original_data
                if original and original.get('text') == item.get('text'):
                    coords = original.get('coordinates', [])
                    confidence = original.get('confidence', 1.0)
                else:
                    # 还原坐标格式 (box -> coordinates)
                    box = item.get('box')
                    if box:
                        x1, y1, x2, y2 = box
                        coords = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                
                region = {
                    'text': item.get('text', ''),
                    'coordinates': coords,
                    'confidence': confidence
                }
                new_regions.append(region)
            
            json_data['regions'] = new_regions
            json_data['full_text'] = full_text
            
            # 3. 保存到文件
            # 只有当原始文件存在时才保存，避免创建垃圾文件
            # 或者总是保存? 用户编辑了就应该保存。
            if filename in self.file_map:
                image_path = self.file_map[filename]
                base_dir = os.path.dirname(image_path)
                base_name = os.path.splitext(filename)[0]
                
                # 保存JSON
                json_path = os.path.join(base_dir, "output", "json", f"{base_name}.json")
                try:
                    os.makedirs(os.path.dirname(json_path), exist_ok=True)
                    self.file_utils.write_json_file(json_path, json_data)
                except Exception as e:
                    print(f"Failed to save updated JSON for {filename}: {e}")
                    
                # 保存TXT
                txt_path = os.path.join(base_dir, "output", "txt", f"{base_name}_result.txt")
                try:
                    os.makedirs(os.path.dirname(txt_path), exist_ok=True)
                    self.file_utils.write_text_file(txt_path, full_text)
                except Exception as e:
                    print(f"Failed to save updated TXT for {filename}: {e}")

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
        self._display_result_for_item(item)
        if not item:
            return
        name = item.text()
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            path = self.file_map.get(name, None)
            if path:
                self.ui.image_viewer.display_image(path)
                pass

    def _add_files(self):
        """添加单个文件到处理列表"""
        if not PYQT_AVAILABLE or not self.main_window:
            return
            
        files, _ = QFileDialog.getOpenFileNames(
            self.main_window, 
            "选择要添加的图像文件", 
            "", 
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff *.tif);;All Files (*)"
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
        dialog = FieldBindingDialog(self.main_window)
        dialog.config_saved.connect(self._on_binding_config_saved)
        dialog.exec_()

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
