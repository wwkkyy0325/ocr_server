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

try:
    from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QInputDialog
    from PyQt5.QtCore import QTimer, Qt, QEvent, QFileSystemWatcher
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, using console mode")

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
import json


class MainWindow:
    def __init__(self, config_manager=None, is_gui_mode=False, detector=None, recognizer=None, post_processor=None,
                 converter=None, preprocessor=None, cropper=None, file_utils=None, logger=None,
                 performance_monitor=None):
        """
        初始化主窗口

        Args:
            config_manager: 配置管理器（可选）
            is_gui_mode: 是否为GUI模式
        """
        print("Initializing MainWindow")
        # 获取项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Project root in MainWindow: {self.project_root}")
        
        # 初始化目录路径
        self.input_dir = "input"
        self.output_dir = "output"
        
        # 初始化配置管理器
        if config_manager:
            self.config_manager = config_manager
        else:
            self.config_manager = ConfigManager(self.project_root)
            self.config_manager.load_config()
        
        self.task_manager = TaskManager()
        self.result_manager = ResultManager()
        self.logger = logger or Logger(os.path.join(self.project_root, "logs", "ocr.log"))
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.results_by_filename = {}
        self.processing_thread = None
        self._stop_flag = False
        self.file_map = {}
        
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
        
        # 初始化处理管理器
        self.process_manager = None
        
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
                
                self.main_window = QMainWindow()
                self.ui = Ui_MainWindow()
                self.ui.setup_ui(self.main_window)
                try:
                    self.ui.image_list.setAcceptDrops(True)
                    self.ui.image_list.installEventFilter(self)
                except Exception:
                    pass
                self._connect_signals()
                # 设置延迟更新模板列表，确保UI完全初始化
                if PYQT_AVAILABLE:
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(100, self._delayed_ui_setup)
                print("UI initialized successfully")
            except Exception as e:
                print(f"Error setting up UI: {e}")
                import traceback
                traceback.print_exc()
                self.ui = None
                self.main_window = None  # 确保UI组件被设为None
                
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


    def _connect_signals(self):
        """
        连接UI信号
        """
        print("Connecting UI signals")
        if self.ui and self.main_window:
            self.ui.input_button.clicked.connect(self._select_input_directory)
            self.ui.output_button.clicked.connect(self._select_output_directory)
            self.ui.start_button.clicked.connect(self._start_processing)
            self.ui.stop_button.clicked.connect(self._stop_processing)
            self.ui.model_selector.currentIndexChanged.connect(self._on_model_changed)
            self.ui.image_list.itemClicked.connect(self._on_image_selected)
            
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
            if hasattr(self.ui, 'mask_btn_bind'):
                self.ui.mask_btn_bind.clicked.connect(self._bind_mask_to_current)
            if hasattr(self.ui, 'mask_btn_apply'):
                self.ui.mask_btn_apply.clicked.connect(self._apply_selected_mask)
            if hasattr(self.ui, 'mask_btn_clear'):
                self.ui.mask_btn_clear.clicked.connect(self.ui.image_viewer.clear_masks)
            # Folder management connections
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_add_btn'):
                self.ui.folder_add_btn.clicked.connect(self._add_folder)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_remove_btn'):
                self.ui.folder_remove_btn.clicked.connect(self._remove_selected_folder)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_clear_btn'):
                self.ui.folder_clear_btn.clicked.connect(self._clear_all_folders)
            if PYQT_AVAILABLE and self.ui and hasattr(self.ui, 'folder_list'):
                self.ui.folder_list.itemClicked.connect(self._on_folder_selected)
            
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

    def _bind_mask_to_current(self):
        """绑定模板到当前图像"""
        # 显示弹窗选择模板
        selected_display_name = self._show_mask_selection_dialog()
        if not selected_display_name:
            return
        
        # Get current image filename
        item = self.ui.image_list.currentItem()
        if not item:
            QMessageBox.warning(self.main_window, "提示", "请先选择一张图像")
            return
        filename = item.text()
        
        if selected_display_name == "不应用模板":
            # 解除绑定
            self.mask_manager.unbind_image(filename)
            self.ui.status_label.setText(f"已解除 '{filename}' 的模板绑定")
        else:
            current_name = self._get_original_mask_name(selected_display_name)
            self.mask_manager.bind_mask_to_image(filename, current_name)
            self.ui.status_label.setText(f"已将蒙版 '{selected_display_name}' 绑定到 '{filename}'")

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
                        folder_name = current_folder_item.text()
                        directory = self.folder_list_items.get(folder_name)
                        if directory and directory in self.folder_mask_map:
                            del self.folder_mask_map[directory]
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
                        folder_name = current_folder_item.text()
                        directory = self.folder_list_items.get(folder_name)
                        if directory:
                            self.folder_mask_map[directory] = current_name

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
            if PYQT_AVAILABLE and self.ui and obj == self.ui.image_list:
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
                        self.ui.image_list.addItem(name)
                    if dropped_files:
                        if self.processing_thread and self.processing_thread.is_alive():
                            if self.ui:
                                self.ui.status_label.setText("正在处理，请稍后再拖拽")
                        else:
                            self._start_processing_files(dropped_files)
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
        model_names = ["默认模型", "高精度模型", "快速模型"]
        if index >= 0 and index < len(model_names):
            model_name = model_names[index]
            self.logger.info(f"切换到模型: {model_name}")
            # 在这里可以根据选择的模型更新配置
            # 示例: self.config_manager.set_setting('selected_model', model_name)

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
        status_text = f"输入目录: {self.input_dir} | 输出目录: {self.output_dir}"
        self.ui.status_label.setText(status_text)
        
        # 更新图像列表
        self._update_image_list()

    def _update_image_list(self):
        """
        更新图像列表显示
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 清空当前列表
        self.ui.image_list.clear()
        
        # 获取图像文件列表并添加到列表中
        if os.path.exists(self.input_dir):
            image_files = self.file_utils.get_image_files(self.input_dir)
            self.file_map = {}
            for image_file in image_files:
                name = os.path.basename(image_file)
                self.file_map[name] = image_file
                self.ui.image_list.addItem(name)

    def _update_ui_status(self):
        """
        定期更新UI状态
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 这里可以添加更多状态更新逻辑
        # 例如: 更新进度条、显示处理状态等
        pass

    def _select_input_directory(self):
        """
        选择输入目录
        """
        print("Selecting input directory")
        if PYQT_AVAILABLE and self.main_window:
            directory = QFileDialog.getExistingDirectory(self.main_window, "选择输入目录", self.input_dir)
            if directory:
                self.input_dir = directory
                print(f"Selected input directory: {directory}")
                self._update_ui_with_directories()

    def _select_output_directory(self):
        """
        选择输出目录
        """
        print("Selecting output directory")
        if PYQT_AVAILABLE and self.main_window:
            directory = QFileDialog.getExistingDirectory(self.main_window, "选择输出目录", self.output_dir)
            if directory:
                self.output_dir = directory
                print(f"Selected output directory: {directory}")
                self._update_ui_with_directories()

    def _open_settings_dialog(self):
        """
        打开设置对话框
        """
        if not PYQT_AVAILABLE:
            return
            
        try:
            from app.ui.dialogs.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self.config_manager, self.main_window)
            dialog.exec_()
            
            # 重新加载配置到相关组件
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
        
        # 检查是否有文件夹需要处理
        if not self.folders:
            QMessageBox.warning(self.main_window, "提示", "请先添加要处理的文件夹")
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
                self.ui.start_button.setEnabled(False)
                self.ui.stop_button.setEnabled(True)
                self.ui.status_label.setText("正在批量处理...")
            self.results_by_filename = {}
            self._stop_flag = False
            
            # 创建处理线程
            self.processing_thread = threading.Thread(target=self._process_multiple_folders, daemon=True)
            self.processing_thread.start()
            if PYQT_AVAILABLE:
                self.check_progress_timer = QTimer()
                self.check_progress_timer.timeout.connect(self._check_processing_finished)
                self.check_progress_timer.start(300)
        except Exception as e:
            self.logger.error(f"批量处理过程中发生错误: {e}")
            if PYQT_AVAILABLE and self.main_window:
                QMessageBox.critical(self.main_window, "错误", f"批量处理过程中发生错误: {e}")
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(True)
                self.ui.stop_button.setEnabled(False)
                self.ui.status_label.setText("处理失败")

    def _process_multiple_folders(self):
        """处理多个文件夹"""
        self.performance_monitor.start_timer("total_processing")
        
        for folder_path in self.folders:
            if getattr(self, "_stop_flag", False):
                break
                
            # 获取该文件夹的模板设置
            mask_name = self.folder_mask_map.get(folder_path, None)
            mask_data = None
            if mask_name:
                mask_data = self.mask_manager.get_mask(mask_name)
            
            # 处理该文件夹
            self.logger.info(f"开始处理文件夹: {folder_path}")
            print(f"Processing folder: {folder_path}")
            
            # 创建子目录用于输出结果
            folder_name = os.path.basename(folder_path)
            output_subdir = os.path.join(self.output_dir, folder_name)
            os.makedirs(output_subdir, exist_ok=True)
            
            # 处理该文件夹下的所有图像
            self._process_images(folder_path, output_subdir, mask_data)
            
            if getattr(self, "_stop_flag", False):
                break
                
        total_time = self.performance_monitor.stop_timer("total_processing")
        self.logger.info(f"批量处理完成，总耗时: {total_time:.2f}秒")
        print(f"Batch processing completed in {total_time:.2f} seconds")
    
    def _start_processing_files(self, files):
        try:
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(False)
                self.ui.stop_button.setEnabled(True)
                self.ui.status_label.setText("正在处理拖入的文件...")
            self.results_by_filename = {}
            self._stop_flag = False
            
            # 获取当前选中的蒙版作为默认蒙版
            default_mask_data = None
            if self.config_manager.get_setting('use_mask', False) and self.ui:
                # 使用弹窗选择默认模板
                current_mask_name = self._show_mask_selection_dialog()
                if current_mask_name:
                    original_name = self._get_original_mask_name(current_mask_name)
                    default_mask_data = self.mask_manager.get_mask(original_name)

            self.processing_thread = threading.Thread(target=self._process_files, args=(files, self.output_dir, default_mask_data), daemon=True)
            self.processing_thread.start()
            if PYQT_AVAILABLE:
                self.check_progress_timer = QTimer()
                self.check_progress_timer.timeout.connect(self._check_processing_finished)
                self.check_progress_timer.start(300)
        except Exception as e:
            self.logger.error(f"处理拖入文件时发生错误: {e}")
            if PYQT_AVAILABLE and self.main_window:
                QMessageBox.critical(self.main_window, "错误", f"处理拖入文件时发生错误: {e}")
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(True)
                self.ui.stop_button.setEnabled(False)
                self.ui.status_label.setText("处理失败")

    def _check_processing_finished(self):
        if not PYQT_AVAILABLE or not self.ui:
            return
        if hasattr(self, 'processing_thread') and self.processing_thread and not self.processing_thread.is_alive():
            try:
                self.check_progress_timer.stop()
            except:
                pass
            self.ui.start_button.setEnabled(True)
            self.ui.stop_button.setEnabled(False)
            self.ui.status_label.setText("处理完成")
            if self.ui.image_list.count() > 0:
                item = self.ui.image_list.item(0)
                self._display_result_for_item(item)

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

    def _process_images(self, input_dir, output_dir, default_mask_data=None):
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
                elif default_mask_data:
                    mask_data = default_mask_data
                elif self.current_selected_mask:
                    mask_data = self.current_selected_mask
                
                # 规范化蒙版数据
                if mask_data:
                    if isinstance(mask_data, list):
                        if len(mask_data) > 0 and isinstance(mask_data[0], (int, float)):
                            masks_to_process = [{'rect': mask_data, 'label': 1}]
                        else:
                            masks_to_process = mask_data
                            # 按标签排序
                            masks_to_process.sort(key=lambda x: x.get('label', 0))
                
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

            for mask_info in masks_to_process:
                rect = mask_info.get('rect')
                
                # 裁剪
                image = original_image
                if rect and len(rect) == 4:
                    try:
                        w, h = image.size if hasattr(image, 'size') else (None, None)
                        if w and h:
                            x1 = int(rect[0] * w)
                            y1 = int(rect[1] * h)
                            x2 = int(rect[2] * w)
                            y2 = int(rect[3] * h)
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
                    image = self.preprocessor.comprehensive_preprocess(image, output_dir, preprocessed_filename)
                self.performance_monitor.stop_timer("preprocessing")
                
                # 检测与识别
                self.performance_monitor.start_timer("detection")
                text_regions = self.detector.detect_text_regions(image)
                self.performance_monitor.stop_timer("detection")
                
                # 提取文本
                part_texts = []
                for j, region in enumerate(text_regions):
                    self.performance_monitor.start_timer("recognition")
                    try:
                        text = region.get('text', '')
                        confidence = region.get('confidence', 0.0)
                        coordinates = region.get('coordinates', [])
                        
                        # 使用原始文本，不进行矫正
                        part_texts.append(text)
                        file_detailed_results.append({
                            'text': text,
                            'confidence': confidence,
                            'coordinates': coordinates,
                            'detection_confidence': confidence,
                            'mask_label': mask_info.get('label', 0)
                        })
                    except Exception as e:
                        self.logger.error(f"Error processing region {j} in {image_path}: {e}")
                    finally:
                        self.performance_monitor.stop_timer("recognition")
                
                if part_texts:
                    file_recognized_texts.append(" ".join(part_texts))
                
            full_text = "\n".join(file_recognized_texts)
            self.results_by_filename[os.path.basename(image_path)] = full_text
            
            # 保存TXT
            output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}_result.txt")
            try:
                self.file_utils.write_text_file(output_file, full_text)
            except Exception as e:
                print(f"Warning: Failed to write TXT file {output_file}: {e}")
            
            # 保存JSON
            json_output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}.json")
            try:
                json_result = {
                    'image_path': image_path,
                    'filename': os.path.basename(image_path),
                    'timestamp': datetime.now().isoformat(),
                    'full_text': full_text,
                    'regions': file_detailed_results
                }
                self.file_utils.write_json_file(json_output_file, json_result)
            except Exception as e:
                print(f"Warning: Failed to write JSON file {json_output_file}: {e}")
            
            # 存储结果
            self.result_manager.store_result(image_path, full_text)
            
            self.logger.info(f"完成处理: {image_path}")
            print(f"Finished processing: {image_path}")
    
    def _process_files(self, files, output_dir, default_mask_data=None):
        print(f"Processing dropped files to {output_dir}")
        self.performance_monitor.start_timer("total_processing")
        os.makedirs(output_dir, exist_ok=True)
        for i, image_path in enumerate(files):
            if getattr(self, "_stop_flag", False):
                break
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
                                masks_to_process.sort(key=lambda x: x.get('label', 0))
                    
                    if not masks_to_process:
                        masks_to_process = [{'rect': None, 'label': 0}]
                except Exception as e:
                    print(f"Error determining masks for {image_path}: {e}")
                    masks_to_process = [{'rect': None, 'label': 0}]

                file_recognized_texts = []
                file_detailed_results = []

                for mask_info in masks_to_process:
                    rect = mask_info.get('rect')
                    image = original_image
                    
                    if rect and len(rect) == 4:
                        try:
                            w, h = image.size if hasattr(image, 'size') else (None, None)
                            if w and h:
                                x1 = int(rect[0] * w)
                                y1 = int(rect[1] * h)
                                x2 = int(rect[2] * w)
                                y2 = int(rect[3] * h)
                                image = self.cropper.crop_text_region(image, [x1, y1, x2, y2])
                        except Exception as e:
                             print(f"Mask crop failed for dropped {image_path}: {e}")
                    
                    self.performance_monitor.start_timer("preprocessing")
                    preprocessed_filename = f"{os.path.splitext(os.path.basename(image_path))[0]}_part{mask_info.get('label', 0)}"
                    image = self.preprocessor.comprehensive_preprocess(image, output_dir, preprocessed_filename)
                    self.performance_monitor.stop_timer("preprocessing")
                    
                    self.performance_monitor.start_timer("detection")
                    text_regions = self.detector.detect_text_regions(image)
                    self.performance_monitor.stop_timer("detection")
                    
                    part_texts = []
                    for region in text_regions:
                        text = region.get('text', '')
                        confidence = region.get('confidence', 0.0)
                        coordinates = region.get('coordinates', [])
                        # 使用原始文本，不进行矫正
                        part_texts.append(text)
                        file_detailed_results.append({
                            'text': text,
                            'confidence': confidence,
                            'coordinates': coordinates,
                            'detection_confidence': confidence,
                            'mask_label': mask_info.get('label', 0)
                        })
                    
                    if part_texts:
                        file_recognized_texts.append(" ".join(part_texts))

                full_text = "\n".join(file_recognized_texts)
                self.results_by_filename[os.path.basename(image_path)] = full_text
                
                output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}_result.txt")
                self.file_utils.write_text_file(output_file, full_text)
                
                json_output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}.json")
                json_result = {
                    'image_path': image_path,
                    'filename': os.path.basename(image_path),
                    'timestamp': datetime.now().isoformat(),
                    'full_text': full_text,
                    'regions': file_detailed_results
                }
                self.file_utils.write_json_file(json_output_file, json_result)
                self.result_manager.store_result(image_path, full_text)
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
        text = self.results_by_filename.get(filename, "")
        self.ui.result_display.setPlainText(text)

    def _on_image_selected(self, item):
        self._display_result_for_item(item)
        if not item:
            return
        name = item.text()
        if hasattr(self.ui, 'image_viewer') and self.ui.image_viewer:
            path = self.file_map.get(name, None)
            if path:
                self.ui.image_viewer.display_image(path)
                
                # Check binding
                bound_mask = self.mask_manager.get_bound_mask(name)
                if bound_mask:
                    ratios = self.mask_manager.get_mask(bound_mask)
                    if ratios:
                        self.ui.image_viewer.set_mask_coordinates_ratios(ratios)
                        self.ui.mask_combo.setCurrentText(bound_mask)
                        # Update the current mask label when switching images
                        self._update_current_mask_label(f"绑定: {bound_mask}")
                else:
                    # No binding, show "无"
                    self._update_current_mask_label("无")

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
            
            item = self.ui.folder_list.addItem(folder_name)
            self.folder_list_items[folder_name] = directory
            self.ui.status_label.setText(f"已添加文件夹: {folder_name}")

    def _remove_selected_folder(self):
        """移除选中的文件夹"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        current_item = self.ui.folder_list.currentItem()
        if current_item:
            folder_name = current_item.text()
            if folder_name in self.folder_list_items:
                directory = self.folder_list_items[folder_name]
                if directory in self.folders:
                    self.folders.remove(directory)
                del self.folder_list_items[folder_name]
            
            row = self.ui.folder_list.row(current_item)
            self.ui.folder_list.takeItem(row)
            self.ui.status_label.setText(f"已移除文件夹: {folder_name}")

    def _clear_all_folders(self):
        """清空所有文件夹"""
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        if self.folders:
            self.folders.clear()
            self.folder_list_items.clear()
            self.ui.folder_list.clear()
            self.ui.status_label.setText("已清空所有文件夹")

    def _on_folder_selected(self, item):
        """文件夹选择变化处理"""
        if not item:
            return
            
        folder_name = item.text()
        if folder_name in self.folder_list_items:
            directory = self.folder_list_items[folder_name]
            
            # 更新图像列表显示该文件夹的内容
            self._update_image_list_for_folder(directory)
            
            # 显示当前文件夹的模板设置
            self._update_folder_mask_display(directory)

    def _update_folder_mask_display(self, directory):
        """更新文件夹模板显示"""
        if directory in self.folder_mask_map:
            mask_name = self.folder_mask_map[directory]
            self.ui.status_label.setText(f"当前文件夹模板: {mask_name}")
        else:
            self.ui.status_label.setText("当前文件夹模板: 无")

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
                self.ui.image_list.addItem(name)
                
            self.ui.status_label.setText(f"显示文件夹内容: {os.path.basename(directory)}")

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

    def close(self):
        """
        关闭主窗口
        """
        print("Closing main window")
        # 停止所有任务
        self.task_manager.stop_worker()
        
        # 停止定时器
        if PYQT_AVAILABLE and hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
            
        if PYQT_AVAILABLE and hasattr(self, 'check_progress_timer') and self.check_progress_timer:
            self.check_progress_timer.stop()
            
        if self.ui and self.main_window and PYQT_AVAILABLE:
            self.main_window.close()
