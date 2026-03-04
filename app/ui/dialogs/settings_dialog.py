from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIntValidator, QDesktopServices
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QPushButton, QTabWidget, QWidget, QMessageBox, QFileDialog, QFrame
)
from PyQt5.QtCore import QUrl
import json
import os
import time
import queue
import traceback
from typing import Dict, Any, List, Optional

# Import custom components
try:
    from app.ui.widgets.progress_bar import CyberEnergyBar
    from app.ui.dialogs.glass_dialogs import GlassTitleBar, GlassMessageDialog, FramelessBorderDialog
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("警告: PyQt5 组件导入失败，UI 功能将不可用")


class SettingsDialog(FramelessBorderDialog):
    if PYQT_AVAILABLE:
        model_settings_applied = pyqtSignal(list)

    def __init__(self, config_manager, parent=None, initial_tab_index=0):
        """
        初始化设置对话框
        
        Args:
            config_manager: 配置管理器实例
            parent: 父窗口
            initial_tab_index: 初始选中的标签页索引 (0: 环境管理, 1: 模型管理)
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.modified_configs = {}
        self.changed_categories = set()
        self.initial_settings = {}
        self.model_widgets = {}
        self.applied_model_keys = {}  # 记录加载对话框时或应用后的模型键
        self.applied_model_enabled_states = {} # 记录启用状态
        self.energy_anim_timers = {}
        self.initial_preset = None
        self._closing_after_model_reload = False
        
        if PYQT_AVAILABLE:
            self.init_ui(initial_tab_index)
            self.load_current_settings()

    def get_changed_categories(self):
        """
        获取已更改的设置类别
        Returns:
            set: 包含已更改类别的集合 {'model', 'recognition', 'ocr_service'}
        """
        return self.changed_categories

    def _get_ui_values(self):
        """
        获取当前UI控件的值
        Returns:
            dict: 当前设置值字典
        """
        if not PYQT_AVAILABLE:
            return {}
            
        values = {}
        # Model settings（仅记录模型选择，不再区分启用/禁用）
        for model_type in ['det', 'rec', 'cls', 'doc_ori', 'unwarp']:
            if model_type in self.model_widgets:
                widgets = self.model_widgets[model_type]
                combo = widgets['combo']
                idx = combo.currentIndex()
                if idx >= 0:
                    values[f'{model_type}_model_key'] = combo.itemData(idx)
                else:
                    values[f'{model_type}_model_key'] = None
                
                # 获取复选框状态
                if 'checkbox' in widgets:
                    values[f'use_{model_type}_model'] = widgets['checkbox'].isChecked()
        
        return values


    def init_ui(self, initial_tab_index=0):
        """
        初始化UI界面
        """
        if not PYQT_AVAILABLE:
            return
            
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(720, 520)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = GlassTitleBar("设置", self)
        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(8)

        self.main_tab_widget = QTabWidget()
        
        # --- Tab 1: 环境管理 ---
        env_tab = QWidget()
        env_layout = QVBoxLayout(env_tab)
        
        env_info_group = QGroupBox("当前环境信息")
        env_info_layout = QFormLayout()
        
        # Get info safely without heavy imports if possible, or just display what we know
        from app.core.env_manager import EnvManager
        sys_info = EnvManager.get_system_info()
        paddle_status = EnvManager.get_paddle_status()
        
        # CPU Info Logic
        cpu_vendor = EnvManager.get_cpu_vendor()
        cpu_display = f"{cpu_vendor}"
        if cpu_vendor == "Intel":
            cpu_display += " (已启用CPU加速)"
        elif cpu_vendor == "AMD":
            cpu_display += " (不支持CPU加速)"
        else:
            cpu_display += " (未启用加速)"
            
        env_info_layout.addRow("CPU:", QLabel(cpu_display))
        env_info_layout.addRow("Python:", QLabel(sys_info['python']))
        env_info_layout.addRow("CUDA:", QLabel(sys_info['cuda_version']))
        env_info_layout.addRow("GPU:", QLabel(sys_info['gpu_name']))
        env_info_layout.addRow("PaddlePaddle:", QLabel(f"{paddle_status['version']} (GPU: {paddle_status['gpu_support']})"))
        
        env_info_group.setLayout(env_info_layout)
        env_layout.addWidget(env_info_group)
        
        env_layout.addStretch()
        self.main_tab_widget.addTab(env_tab, "环境管理")

        # --- Tab 2: 模型管理 ---
        model_mgt_tab = QWidget()
        model_mgt_layout = QVBoxLayout(model_mgt_tab)

        cache_path_layout = QHBoxLayout()
        cache_root = getattr(self.config_manager.model_manager, 'models_root', '')
        self.cache_path_label = QLabel(f"模型缓存路径: {cache_root}")
        open_cache_btn = QPushButton("打开目录")
        def _open_cache_dir():
            if cache_root:
                QDesktopServices.openUrl(QUrl.fromLocalFile(cache_root))
        open_cache_btn.clicked.connect(_open_cache_dir)
        cache_path_layout.addWidget(self.cache_path_label)
        cache_path_layout.addWidget(open_cache_btn)
        cache_path_layout.addStretch()
        model_mgt_layout.addLayout(cache_path_layout)
        
        # 子进程模式控制 - 已移除，强制开启
        # subprocess_group = QGroupBox("处理模式")
        # subprocess_layout = QHBoxLayout()
        # 
        # self.use_subprocess_checkbox = QCheckBox("使用子进程模式 (推荐)")
        # self.use_subprocess_checkbox.setChecked(True)
        # self.use_subprocess_checkbox.setToolTip("启用子进程模式可避免模型重复加载，提升性能和稳定性")
        # self.use_subprocess_checkbox.stateChanged.connect(self.on_subprocess_mode_changed)
        # 
        # subprocess_layout.addWidget(self.use_subprocess_checkbox)
        # subprocess_layout.addStretch()
        # subprocess_group.setLayout(subprocess_layout)
        # model_mgt_layout.addWidget(subprocess_group)
        
        # 模型组合选择
        model_combo_group = QGroupBox("模型组合")
        model_combo_layout = QVBoxLayout(model_combo_group)
                
        combo_desc = QLabel("选择 OCR 识别的模型组合配置：")
        combo_desc.setWordWrap(True)
        combo_desc.setStyleSheet("color: #999;")
        model_combo_layout.addWidget(combo_desc)
                
        combo_row = QHBoxLayout()
        combo_label = QLabel("模型组合:")
        combo_label.setMinimumWidth(120)
        combo_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        self.model_combo.setMaximumWidth(300)
        self.model_combo.addItem("轻量级模型组 (PP-OCRv5_mobile)", "mobile")
        self.model_combo.addItem("重量级模型组 (PP-OCRv5-server)", "server")
        self.model_combo.addItem("PP-Structure 文档智能解析", "ai_table")
                
        # 设置选项提示
        self.model_combo.setItemData(0, "适合 CPU 运行，速度快但精度较低", Qt.ToolTipRole)
        self.model_combo.setItemData(1, "建议 GPU 运行，精度高但速度较慢", Qt.ToolTipRole)
        self.model_combo.setItemData(2, "基于 PP-Structure 的完整文档解析管线（版面分析/表格识别/公式检测等），启用后其他辅助模型将失效", Qt.ToolTipRole)
                
        self.model_combo.setToolTip("选择预设的模型组合配置")
        self._center_align_combo_items(self.model_combo)
                
        self.model_combo.currentIndexChanged.connect(self.on_model_combo_changed)
                
        combo_row.addWidget(combo_label)
        combo_row.addStretch()
        combo_row.addWidget(self.model_combo)
        model_combo_layout.addLayout(combo_row)
                
        model_mgt_layout.addWidget(model_combo_group)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        model_mgt_layout.addWidget(separator)
        
        self.model_widgets = {}
        
        # 只显示 cls 和 unwarp 模型（det 和 rec 由组合控制）
        self.init_model_tab("cls", "文本行方向分类 (Textline Orientation)", model_mgt_layout)
        self.init_model_tab("doc_ori", "文档方向分类 (Document Orientation)", model_mgt_layout)
        self.init_model_tab("unwarp", "图像矫正模型 (Unwarping)", model_mgt_layout)

        # 模型卸载区域
        uninstall_group = QGroupBox("模型卸载")
        uninstall_layout = QVBoxLayout()
        uninstall_desc = QLabel("卸载本程序下载的离线模型文件（项目 models 目录及相关缓存）。\n"
                                "建议在卸载应用前先执行一次清理。")
        uninstall_desc.setWordWrap(True)
        uninstall_layout.addWidget(uninstall_desc)

        btn_uninstall_models = QPushButton("卸载本地模型")
        btn_uninstall_models.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        btn_uninstall_models.clicked.connect(self.uninstall_local_models)
        uninstall_layout.addWidget(btn_uninstall_models)

        # 缓存清理区域 (新增)
        cache_group = QGroupBox("结果缓存清理")
        cache_layout = QVBoxLayout()
        cache_desc = QLabel("清理所有OCR处理结果缓存（包括 data/outputs 目录下的所有文件以及数据库中的处理记录）。\n"
                            "执行后，所有文件将被视为未处理状态。")
        cache_desc.setWordWrap(True)
        cache_layout.addWidget(cache_desc)

        btn_clear_cache = QPushButton("清除所有结果缓存")
        btn_clear_cache.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        btn_clear_cache.clicked.connect(self.clear_all_cache)
        cache_layout.addWidget(btn_clear_cache)

        cache_group.setLayout(cache_layout)
        model_mgt_layout.addWidget(cache_group)

        uninstall_group.setLayout(uninstall_layout)
        model_mgt_layout.addWidget(uninstall_group)

        self.main_tab_widget.addTab(model_mgt_tab, "模型管理")
        
        content_layout.addWidget(self.main_tab_widget)
        
        # Set initial tab
        if initial_tab_index >= 0 and initial_tab_index < self.main_tab_widget.count():
            self.main_tab_widget.setCurrentIndex(initial_tab_index)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        apply_button = QPushButton("应用")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        apply_button.clicked.connect(self.apply_settings)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(apply_button)
        
        content_layout.addLayout(button_layout)
        main_layout.addWidget(content_widget)
        self.setLayout(main_layout)


    def init_model_tab(self, model_type, title, parent_layout):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 启用开关
        enable_checkbox = QCheckBox()
        enable_checkbox.setToolTip("启用/禁用此模型")
        # 默认选中，后续会在 load_current_settings 中根据配置更新
        enable_checkbox.setChecked(True)
        layout.addWidget(enable_checkbox)

        short_title = title.split(" ")[0] if title else model_type
        label = QLabel(f"{short_title}：")
        label.setObjectName("modelLabel")
        label.setMinimumWidth(120)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label)

        combo = QComboBox()
        combo.setMinimumWidth(260)
        combo.setMaximumWidth(260)
        combo.currentIndexChanged.connect(lambda idx: self.on_model_changed(model_type))

        # 关联复选框状态和组合框启用状态
        enable_checkbox.stateChanged.connect(lambda state: combo.setEnabled(state == Qt.Checked))

        energy_bar = CyberEnergyBar(container)
        energy_bar.setToolTip("当前模型状态")
        energy_bar.set_ready_text("就绪")
        layout.addWidget(energy_bar)
        layout.addStretch()
        layout.addWidget(combo)

        parent_layout.addWidget(container)

        self.model_widgets[model_type] = {
            'combo': combo,
            'energy_bar': energy_bar,
            'checkbox': enable_checkbox,
            'group': container
        }
        
        models = self.config_manager.model_manager.get_available_models(model_type)
        for key, desc, is_downloaded, size in models:
            combo.addItem(f"{desc} : {size}", key)
        self._center_align_combo_items(combo)

    def _center_align_combo_items(self, combo):
        for i in range(combo.count()):
            combo.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)

    def on_model_combo_changed(self, index):
        """处理模型组合切换 (仅更新 UI 状态，不立即应用)"""
        combo_preset = self.model_combo.itemData(index)
        
        # 如果选择了 PP-Structure 文档智能解析模式，禁用其他辅助模型
        is_ai_table_mode = (combo_preset == 'ai_table')
        
        # 禁用/启用 cls, doc_ori, unwarp 模型
        for model_type in ['cls', 'doc_ori', 'unwarp']:
            if model_type in self.model_widgets:
                widgets = self.model_widgets[model_type]
                widgets['checkbox'].setEnabled(not is_ai_table_mode)
                widgets['combo'].setEnabled(not is_ai_table_mode)
                if is_ai_table_mode:
                    widgets['checkbox'].setChecked(False)
        
        # 不要在这里调用 check_preset_match，避免在设置辅助模型状态时误触发配置覆盖
        # check_preset_match 只会在 apply_settings 时根据最终 UI 状态来保存配置

    def check_preset_match(self):
        """检查当前选择是否匹配预设"""
        if not hasattr(self, 'model_combo'):
            return
                
        # 优先尊重用户在 UI 上的手动选择
        current_ui_preset = self.model_combo.itemData(self.model_combo.currentIndex())
            
        # 如果用户已经选择了某个预设，就保持这个选择
        if current_ui_preset in ['mobile', 'server', 'ai_table']:
            target_preset = current_ui_preset
        else:
            # 只有在没有明确选择时，才根据 det/rec 模型推断
            current_det = self.config_manager.get_setting('det_model_key')
            current_rec = self.config_manager.get_setting('rec_model_key')
                
            # 默认为 mobile，如果匹配 server 则切换
            target_preset = 'mobile'
                
            if (current_det == 'PP-OCRv5_server_det' and 
                current_rec == 'PP-OCRv5_server_rec'):
                target_preset = 'server'
            
        # Update combo without triggering signal
        idx = self.model_combo.findData(target_preset)
        if idx >= 0 and idx != self.model_combo.currentIndex():
            self.model_combo.blockSignals(True)
            self.model_combo.setCurrentIndex(idx)
            self.model_combo.blockSignals(False)
                
        # 记录初始选中的预设
        self.initial_preset = target_preset
            
        # 不要在 load_current_settings 时覆盖配置，只在 apply_settings 时保存
        # self.config_manager.set_setting('current_ocr_preset', target_preset)

    def _get_current_model_key(self, model_type):
        if model_type in self.model_widgets:
            combo = self.model_widgets[model_type]['combo']
            idx = combo.currentIndex()
            if idx >= 0:
                return combo.itemData(idx)
        return None

    def on_model_changed(self, model_type):
        """处理单个模型变化"""
        self.update_model_status(model_type)
        # 不要在这里调用 check_preset_match，避免在加载设置或切换 ai_table 模式时误触发配置覆盖
        # check_preset_match 只会在 apply_settings 时根据最终 UI 状态来保存配置
        
    def update_model_status(self, model_type):
        widgets = self.model_widgets[model_type]
        combo = widgets['combo']
        idx = combo.currentIndex()
        if idx < 0:
            return
            
        key = combo.itemData(idx)
        models = self.config_manager.model_manager.get_available_models(model_type)
        
        # Find model info
        is_downloaded = False
        desc = ""
        for k, d, downloaded, _ in models:
            if k == key:
                is_downloaded = downloaded
                desc = d
                break
        
        energy_bar = widgets.get('energy_bar')
        if not energy_bar:
            return

        # stop any running animation for this model_type
        timer = self.energy_anim_timers.get(model_type)
        if timer and timer.isActive():
            timer.stop()

        energy_bar.set_range(0, 100)

        applied_key = self.applied_model_keys.get(model_type)
        if applied_key is not None and key == applied_key:
            energy_bar.set_value(energy_bar.maximum())
            energy_bar.set_ready_text("就绪")
        else:
            energy_bar.set_value(0)
            if is_downloaded:
                energy_bar.set_ready_text("待应用 (已缓存)")
            else:
                energy_bar.set_ready_text("待应用")

        if is_downloaded:
            energy_bar.setToolTip("模型已缓存，将按需自动加载。")
        else:
            energy_bar.setToolTip("模型将在首次使用时后台加载。")

    def browse_directory(self, line_edit):
        """
        浏览目录并设置到指定的LineEdit控件
        
        Args:
            line_edit: QLineEdit控件
        """
        if not PYQT_AVAILABLE:
            return
            
        directory = QFileDialog.getExistingDirectory(self, "选择目录", line_edit.text())
        if directory:
            line_edit.setText(directory)

    def load_current_settings(self):
        """
        加载当前配置到UI控件
        """
        if not PYQT_AVAILABLE:
            return
            
        # 加载模型设置（仅加载 cls 和 unwarp 模型）
        for model_type in ['cls', 'doc_ori', 'unwarp']:
            widgets = self.model_widgets.get(model_type)
            if not widgets:
                continue

            # Special handling for doc_ori_model_key which might not exist in old configs
            if model_type == 'doc_ori':
                current_key = self.config_manager.get_setting(f'{model_type}_model_key', 'PP-LCNet_x1_0_doc_ori')
                is_enabled = self.config_manager.get_setting(f'use_{model_type}_model', False)
            elif model_type == 'cls':
                current_key = self.config_manager.get_setting(f'{model_type}_model_key')
                is_enabled = self.config_manager.get_setting(f'use_{model_type}_model', True)
            elif model_type == 'unwarp':
                current_key = self.config_manager.get_setting(f'{model_type}_model_key')
                is_enabled = self.config_manager.get_setting(f'use_{model_type}_model', False)
            else:
                current_key = self.config_manager.get_setting(f'{model_type}_model_key')
                is_enabled = True # Default enabled for others
                
            combo = widgets['combo']
            
            # 设置复选框状态
            if 'checkbox' in widgets:
                widgets['checkbox'].setChecked(is_enabled)
                combo.setEnabled(is_enabled)

            idx = -1
            if current_key:
                for i in range(combo.count()):
                    if combo.itemData(i) == current_key:
                        idx = i
                        break

            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif combo.count() > 0:
                combo.setCurrentIndex(0)

            # 记录当前视图中认为"已应用"的模型键，用于能量条状态判断
            if combo.currentIndex() >= 0:
                self.applied_model_keys[model_type] = combo.itemData(combo.currentIndex())
            else:
                self.applied_model_keys[model_type] = None
                
            # 记录当前视图中认为"已应用"的启用状态
            if 'checkbox' in widgets:
                self.applied_model_enabled_states[model_type] = widgets['checkbox'].isChecked()

            self.update_model_status(model_type)
        
        # 根据当前选择的模型组合，设置辅助模型的启用/禁用状态
        current_preset = self.config_manager.get_setting('current_ocr_preset', 'mobile')
        is_ai_table_mode = (current_preset == 'ai_table')
        
        # 先设置 model_combo 到正确的预设位置
        preset_idx = self.model_combo.findData(current_preset)
        if preset_idx >= 0:
            self.model_combo.blockSignals(True)
            self.model_combo.setCurrentIndex(preset_idx)
            self.model_combo.blockSignals(False)
            print(f"DEBUG: Loaded model combo with preset: {current_preset}")
        else:
            print(f"DEBUG: Preset {current_preset} not found in model_combo, defaulting to mobile")
        
        for model_type in ['cls', 'doc_ori', 'unwarp']:
            if model_type in self.model_widgets:
                widgets = self.model_widgets[model_type]
                if is_ai_table_mode:
                    widgets['checkbox'].setEnabled(False)
                    widgets['combo'].setEnabled(False)
                    widgets['checkbox'].setChecked(False)
        
        # 加载子进程模式设置 - 强制启用
        # use_subprocess = self.config_manager.get_setting('use_ocr_subprocess', True)
        # self.use_subprocess_checkbox.setChecked(use_subprocess)
        
        # 加载OCR服务设置
        # Check preset match after loading all models
        self.check_preset_match()
        
        # 保存初始设置状态用于差量更新检查
        self.initial_settings = self._get_ui_values()
        
        # 补充表格识别相关设置（不在 UI 中，但需要监控变化）
        # AI 表格识别已在模型管理页面的 UI 控件中直接处理
        self.initial_settings['use_table_split'] = self.config_manager.get_setting('use_table_split', False)

    def apply_settings(self):
        """
        应用设置到配置管理器
        """
        if not PYQT_AVAILABLE:
            return
            
        # 检查更改的类别
        current_values = self._get_ui_values()
        self.changed_categories.clear()
        
        # 1. 检查模型设置
        # 这里的"是否需要重载模型"以 self.applied_model_keys 为基准，
        # 表示当前 OCR 引擎正在使用的模型键；只有与之不一致才触发真实重载。
        model_changed = False
        changed_model_types = []
        # 检查 cls, doc_ori 和 unwarp 模型
        for model_type in ['cls', 'doc_ori', 'unwarp']:
            if model_type not in self.model_widgets:
                continue
            
            # Check key change
            current_key = current_values.get(f'{model_type}_model_key')
            applied_key = self.applied_model_keys.get(model_type)
            key_changed = current_key != applied_key
            
            # Check enabled state change
            current_enabled = current_values.get(f'use_{model_type}_model')
            # Default fallback must match ConfigManager defaults
            default_enabled = True if model_type == 'cls' else False
            saved_enabled = self.config_manager.get_setting(f'use_{model_type}_model', default_enabled)
            enabled_changed = current_enabled != saved_enabled
            
            if key_changed or enabled_changed:
                model_changed = True
                changed_model_types.append(model_type)
        
        # 检查 det 和 rec 模型（通过组合选择）
        combo_preset = self.model_combo.itemData(self.model_combo.currentIndex())
        # 确保预设值为有效值
        if combo_preset not in ['mobile', 'server', 'ai_table']:
             combo_preset = 'mobile'
        
        # AI 表格识别模式不需要检查 det/rec 模型变化，它使用自己内置的完整模型栈
        if combo_preset != 'ai_table':
            # 获取当前配置的 det/rec 模型
            current_det = self.config_manager.get_setting('det_model_key')
            current_rec = self.config_manager.get_setting('rec_model_key')
            
            # 获取目标模型
            presets = {
                'mobile': {
                    'det': 'PP-OCRv5_mobile_det',
                    'rec': 'PP-OCRv5_mobile_rec'
                },
                'server': {
                    'det': 'PP-OCRv5_server_det',
                    'rec': 'PP-OCRv5_server_rec'
                }
            }
            target_models = presets.get(combo_preset, {})
            target_det = target_models.get('det')
            target_rec = target_models.get('rec')
            
            # 检查是否需要更新
            if current_det != target_det or current_rec != target_rec:
                model_changed = True
                # 添加到 changed_model_types 以便触发重载
                if 'det' not in changed_model_types:
                    changed_model_types.append('det')
                if 'rec' not in changed_model_types:
                    changed_model_types.append('rec')
        else:
            # AI 表格模式：不检查 det/rec，因为它是独立的完整 OCR 系统
            print("AI Table mode: Using built-in complete OCR system (no det/rec check needed)")
        
        # 检查是否切换了预设（这通常意味着需要重启子进程）
        preset_changed = False
        # 显式比较当前选择的预设与已保存的预设
        saved_preset = self.config_manager.get_setting('current_ocr_preset', 'mobile')
        if combo_preset != saved_preset:
            preset_changed = True
            print(f"预设变更：{saved_preset} -> {combo_preset}")
                
        # 重要：如果切换到或切出 AI 表格模式，必须强制重启子进程
        if combo_preset == 'ai_table' or saved_preset == 'ai_table':
            if combo_preset != saved_preset:
                preset_changed = True
                print(f"AI 表格模式切换：强制重启子进程")
                
        if hasattr(self, 'initial_preset') and self.initial_preset != combo_preset:
            preset_changed = True
            print(f"预设变更 (UI): {self.initial_preset} -> {combo_preset}")
        
        if model_changed or preset_changed:
            self.changed_categories.add('model')
            
        # 更新模型设置
        # 更新 cls, doc_ori 和 unwarp 模型
        for model_type in ['cls', 'doc_ori', 'unwarp']:
            if model_type not in self.model_widgets:
                continue
            # ConfigManager.set_model handles setting the key and the dir
            self.config_manager.set_model(model_type, current_values[f'{model_type}_model_key'])
            
            # Save enabled state
            if f'use_{model_type}_model' in current_values:
                 self.config_manager.set_setting(f'use_{model_type}_model', current_values[f'use_{model_type}_model'])
        
        # 更新 det 和 rec 模型（通过组合选择）- AI 表格模式不需要
        if combo_preset != 'ai_table' and 'det' in target_models:
            self.config_manager.set_model('det', target_models['det'])
        if combo_preset != 'ai_table' and 'rec' in target_models:
            self.config_manager.set_model('rec', target_models['rec'])
        
        # 🔥 关键修复：AI 表格模式和其他配置是互斥的
        if combo_preset == 'ai_table':
            # ✅ 启用 AI 表格识别
            self.config_manager.set_setting('use_ai_table', True)
            self.config_manager.set_setting('current_ocr_preset', 'ai_table')
            
            # ❌ 禁用三个矫正模型
            self.config_manager.set_setting('use_cls_model', False)
            self.config_manager.set_setting('use_doc_ori_model', False)
            self.config_manager.set_setting('use_unwarp_model', False)
            
            # ❌ 禁用传统表格识别
            self.config_manager.set_setting('use_table_split', False)
            
            print("✅ 已切换到 AI 表格识别专用模型组")
            print("❌ 已禁用：文档方向分类、文档矫正、文本行方向、传统表格拆分")
        else:
            # 非 AI 表格模式
            self.config_manager.set_setting('use_ai_table', False)
            
        # 保存当前选择的预设，确保下次启动使用正确预设
        self.config_manager.set_setting('current_ocr_preset', combo_preset)
        
        # 检查是否有表格识别设置变化（兼容旧逻辑，仅用于传统表格拆分 use_table_split）
        # AI 表格识别已在上面直接处理
        current_use_table_split = self.config_manager.get_setting('use_table_split', False)
        saved_use_table_split = self.initial_settings.get('use_table_split', False)
        if current_use_table_split != saved_use_table_split:
            print(f"检测到 use_table_split 设置变化：{saved_use_table_split} -> {current_use_table_split}")
            print("传统表格拆分仅基于物理规则，将在下次处理时自动应用新设置")
        
        # 更新子进程模式设置 - 强制启用
        self.config_manager.set_setting('use_ocr_subprocess', True)
        
        # 保存配置
        self.config_manager.save_config()

        # 启动对应模型能量条动画 + 通知主窗口进行真实模型重载
        if changed_model_types or preset_changed:
            self._start_model_energy_animation(changed_model_types, current_values)
            if PYQT_AVAILABLE and hasattr(self, 'model_settings_applied'):
                try:
                    self.model_settings_applied.emit(changed_model_types)
                except Exception:
                    pass
            
            # 只有在真正应用并保存配置时，才重启子进程
            # 检查模型变化并在保存时立即停止子进程
            self._check_and_stop_subprocess_on_model_change(current_values, force_restart=preset_changed)
            
            # 如果预设变更，还需要更新 initial_preset
            if preset_changed:
                self.initial_preset = combo_preset
            
            # 更新已应用的配置记录，避免重复触发
            for model_type in ['cls', 'doc_ori', 'unwarp']:
                if model_type in self.model_widgets:
                    # Update keys
                    self.applied_model_keys[model_type] = current_values.get(f'{model_type}_model_key')
                    # Update enabled states
                    self.applied_model_enabled_states[model_type] = current_values.get(f'use_{model_type}_model')
                    
        else:
            dlg_saved = GlassMessageDialog(
                self,
                title="提示",
                text="设置已保存!",
                buttons=[("ok", "确定")],
            )
            dlg_saved.exec_()

    def _start_model_energy_animation(self, changed_model_types, current_values):
        """
        为发生变化的模型行启动一次从 0-100 的能量条过渡动画
        """
        if not PYQT_AVAILABLE:
            return

        for model_type in changed_model_types:
            widgets = self.model_widgets.get(model_type)
            if not widgets:
                continue
            energy_bar = widgets.get('energy_bar')
            if not energy_bar:
                continue

            # 停止旧的计时器
            old_timer = self.energy_anim_timers.get(model_type)
            if old_timer and old_timer.isActive():
                old_timer.stop()

            energy_bar.set_range(0, 100)
            energy_bar.set_value(0)
            energy_bar.set_ready_text("应用中...")

            timer = QTimer(self)
            timer.setInterval(80)

            def _on_tick(mt=model_type, bar=energy_bar):
                v = bar.value() + 1
                # 进度条最多推进到 95%，剩余 5% 等待真实模型加载完成时一次性填满
                if v >= bar.maximum() - 5:
                    bar.set_value(bar.maximum() - 5)
                    t = self.energy_anim_timers.get(mt)
                    if t and t.isActive():
                        t.stop()
                    return
                bar.set_value(v)

            timer.timeout.connect(_on_tick)
            self.energy_anim_timers[model_type] = timer
            timer.start()

    def finalize_model_energy(self, changed_model_types, success=True):
        """
        在主窗口收到 OCR 模型加载成功/失败回调时，统一更新相应能量条的最终状态
        """
        if not PYQT_AVAILABLE:
            return

        for model_type in changed_model_types or []:
            widgets = self.model_widgets.get(model_type)
            if not widgets:
                continue
            energy_bar = widgets.get('energy_bar')
            if not energy_bar:
                continue

            # 停止动画计时器
            timer = self.energy_anim_timers.get(model_type)
            if timer and timer.isActive():
                timer.stop()

            if success:
                energy_bar.set_range(0, 100)
                energy_bar.set_value(energy_bar.maximum())
                energy_bar.set_ready_text("就绪")
                # 成功时将该模型类型标记为"当前已应用"的新基线
                if model_type in self.model_widgets:
                    combo = self.model_widgets[model_type]['combo']
                    idx = combo.currentIndex()
                    if idx >= 0:
                        self.applied_model_keys[model_type] = combo.itemData(idx)
            else:
                energy_bar.set_range(0, 100)
                energy_bar.set_value(0)
                energy_bar.set_ready_text("待应用")

    def _switch_subprocess_preset(self, target_preset):
        """
        切换子进程预设
        """
        print(f"开始切换子进程预设至: {target_preset}")
        try:
            from app.core.ocr_subprocess import get_ocr_subprocess_manager
            subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
            
            print(f"当前子进程状态: 运行={subprocess_manager.is_running()}, 预设={subprocess_manager.current_preset}")
            
            if subprocess_manager.is_running():
                print(f"正在切换预设...")
                success = subprocess_manager.switch_preset(target_preset)
                if success:
                    print(f"✅ 子进程预设切换成功: {target_preset}")
                    # 验证切换结果
                    time.sleep(0.5)  # 等待切换完成
                    status = subprocess_manager.get_status()
                    print(f"切换后状态: {status}")
                else:
                    print(f"❌ 子进程预设切换失败: {target_preset}")
                    # 尝试重新启动
                    print("尝试重新启动子进程...")
                    subprocess_manager.cleanup()
                    time.sleep(1)
                    restart_success = subprocess_manager.start_process(target_preset)
                    if restart_success:
                        print(f"✅ 子进程重新启动成功: {target_preset}")
                    else:
                        print(f"❌ 子进程重新启动失败: {target_preset}")
            else:
                print("子进程未运行，启动新进程")
                success = subprocess_manager.start_process(target_preset)
                if success:
                    print(f"✅ 子进程启动成功: {target_preset}")
                else:
                    print(f"❌ 子进程启动失败: {target_preset}")
        except Exception as e:
            print(f"❌ 切换子进程预设时发生异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_and_stop_subprocess_on_model_change(self, current_values, force_restart=False):
        """
        检查模型变化并在保存时立即停止子进程
        """
        print("开始检查模型变化并停止子进程...")
        try:
            # 确定目标预设 (从 UI 组合框获取)
            combo_preset = self.model_combo.itemData(self.model_combo.currentIndex())
            # 确保预设值为有效值
            target_preset = combo_preset if combo_preset in ['mobile', 'server', 'ai_table'] else 'mobile'
                        
            print(f"检测到的目标预设：{target_preset} (UI Selection: {combo_preset})")
            
            # 保存当前预设到配置，供后续使用
            self.config_manager.set_setting('current_ocr_preset', target_preset)
            
            # 如果强制重启或检测到模型变化，则停止子进程
            if force_restart:
                print(f"检测到预设/模型变化，立即停止当前子进程")
                self._stop_current_subprocess()
                print(f"子进程已停止，将在下次处理时重新启动新预设: {target_preset}")
            else:
                 # 检查是否有其他模型变化 (cls, doc_ori, unwarp)
                if self._has_other_model_changes(current_values):
                    print("检测到其他模型变化，停止子进程")
                    self._stop_current_subprocess()

        except Exception as e:
            print(f"检查模型变化时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _has_other_model_changes(self, current_values):
        """
        检查除了det/rec之外的其他模型是否有变化
        """
        try:
            # 检查cls, doc_ori和unwarp模型
            for model_type in ['cls', 'doc_ori', 'unwarp']:
                # 检查Key变化
                current_key = current_values.get(f'{model_type}_model_key')
                applied_key = self.applied_model_keys.get(model_type)
                if current_key != applied_key:
                    print(f"检测到{model_type}模型Key变化: {applied_key} -> {current_key}")
                    return True
                
                # 检查Enabled变化
                current_enabled = current_values.get(f'use_{model_type}_model')
                applied_enabled = self.applied_model_enabled_states.get(model_type)
                # 注意：如果applied_enabled未记录，默认视为True(cls)或False(others)
                if applied_enabled is None:
                    applied_enabled = True if model_type == 'cls' else False
                
                if current_enabled is not None and current_enabled != applied_enabled:
                    print(f"检测到{model_type}模型启用状态变化: {applied_enabled} -> {current_enabled}")
                    return True
                    
            return False
        except Exception as e:
            print(f"检查其他模型变化时出错: {e}")
            return False
    
    def _stop_current_subprocess(self):
        """
        立即停止当前子进程
        """
        try:
            from app.core.ocr_subprocess import get_ocr_subprocess_manager
            subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
            
            if subprocess_manager.is_running():
                print(f"正在停止当前子进程 PID: {subprocess_manager.process.pid if subprocess_manager.process else 'None'}")
                subprocess_manager.stop_process()
                print("子进程已成功停止")
            else:
                print("子进程未运行，无需停止")
        except Exception as e:
            print(f"停止子进程时出错: {e}")
            import traceback
            traceback.print_exc()

    def uninstall_local_models(self):
        """
        卸载本程序下载的本地模型文件（项目 models 目录及部分缓存目录）
        """
        if not PYQT_AVAILABLE:
            return

        dlg_confirm = GlassMessageDialog(
            self,
            title="确认卸载模型",
            text="此操作将尝试删除本程序下载的离线模型目录：\n"
                 " - 项目目录下的 models/paddle_ocr\n"
                 " - 如果设置了 PADDLEX_HOME / PADDLEX_CACHE_DIR 等环境变量，则尝试清理其中的模型缓存。\n\n"
                 "该操作不会卸载 PaddlePaddle/PaddleOCR 代码本身，只清理模型文件。\n\n"
                 "确定要继续吗？",
            buttons=[("yes", "是"), ("no", "否")],
        )
        dlg_confirm.exec_()

        if dlg_confirm.result_key() != "yes":
            return

        import shutil
        import os

        removed_paths = []
        failed_paths = []

        # 1. 项目目录下的 models 目录
        try:
            project_root = self.config_manager.project_root
            models_root = os.path.join(project_root, 'models')
            if os.path.exists(models_root):
                shutil.rmtree(models_root, ignore_errors=False)
                removed_paths.append(models_root)
        except Exception as e:
            failed_paths.append(f"{models_root} ({str(e)})")

        # 2. ModelManager 当前使用的模型根目录（通常位于用户主目录 .paddlex 下）
        try:
            mm_root = getattr(self.config_manager.model_manager, "models_root", None)
            if mm_root and os.path.exists(mm_root):
                shutil.rmtree(mm_root, ignore_errors=False)
                removed_paths.append(mm_root)
        except Exception as e:
            if 'mm_root' in locals():
                failed_paths.append(f"{mm_root} ({str(e)})")

        # 3. 按环境变量约定的几个常见缓存目录
        env_keys = ['PADDLEX_HOME', 'PADDLEX_CACHE_DIR', 'PADDLE_HUB_HOME', 'HUB_HOME']
        for key in env_keys:
            path = os.environ.get(key)
            if not path:
                continue
            try:
                if os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=False)
                    removed_paths.append(path)
            except Exception as e:
                failed_paths.append(f"{path} ({str(e)})")

        # 4. 默认的 ~/.paddlex 目录（如果存在）
        try:
            default_paddlex = os.path.join(os.path.expanduser("~"), ".paddlex")
            if os.path.exists(default_paddlex):
                shutil.rmtree(default_paddlex, ignore_errors=False)
                removed_paths.append(default_paddlex)
        except Exception as e:
            failed_paths.append(f"{default_paddlex} ({str(e)})")

        msg_lines = []
        if removed_paths:
            msg_lines.append("以下目录已清理：")
            msg_lines.extend(removed_paths)
        if failed_paths:
            if removed_paths:
                msg_lines.append("")
            msg_lines.append("以下目录清理失败（可能无权限或不存在）：")
            msg_lines.extend(failed_paths)
        if not removed_paths and not failed_paths:
            msg_lines.append("未发现可清理的模型目录。")

        dlg_info = GlassMessageDialog(
            self,
            title="模型卸载完成",
            text="\n".join(msg_lines),
            buttons=[("ok", "确定")],
        )
        dlg_info.exec_()

        # 卸载后刷新模型管理 UI 状态
        for model_type in ['cls', 'doc_ori', 'unwarp']:
            widgets = self.model_widgets.get(model_type)
            if not widgets:
                continue

            combo = widgets['combo']
            current_key = None
            if combo.count() > 0:
                idx = combo.currentIndex()
                if idx >= 0:
                    current_key = combo.itemData(idx)

            combo.clear()
            models = self.config_manager.model_manager.get_available_models(model_type)
            for k, d, is_downloaded, size in models:
                status_icon = "✅" if is_downloaded else "☁️"
                combo.addItem(f"{status_icon} {d} : {size}", k)
            self._center_align_combo_items(combo)

            # 恢复之前选中的 key，如果还存在的话
            if current_key:
                idx = combo.findData(current_key)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            
            self.update_model_status(model_type)

    def clear_all_cache(self):
        """
        清除所有结果缓存（文件 + 数据库）
        """
        if not PYQT_AVAILABLE:
            return

        dlg_confirm = GlassMessageDialog(
            self,
            title="确认清除缓存",
            text="此操作将：\n"
                 "1. 删除 'data/outputs' 目录下的所有OCR结果文件（JSON/TXT）。\n"
                 "2. 清空 'data/processed_records.db' 数据库中的所有处理记录。\n\n"
                 "执行后，所有图片将需要重新进行OCR识别。\n"
                 "确定要继续吗？",
            buttons=[("yes", "是"), ("no", "否")],
        )
        dlg_confirm.exec_()

        if dlg_confirm.result_key() != "yes":
            return

        import shutil
        import os
        from app.core.record_manager import RecordManager

        success_count = 0
        error_msgs = []

        # 1. 清理文件系统 (data/outputs)
        try:
            project_root = self.config_manager.project_root
            outputs_dir = os.path.join(project_root, 'data', 'outputs')
            if os.path.exists(outputs_dir):
                shutil.rmtree(outputs_dir)
                os.makedirs(outputs_dir, exist_ok=True) # 重建空目录
                success_count += 1
            else:
                success_count += 1 # 目录本来就不存在，也算成功
        except Exception as e:
            error_msgs.append(f"清理文件缓存失败: {e}")

        # 2. 清理数据库记录
        try:
            record_mgr = RecordManager.get_instance(project_root)
            if record_mgr.clear_all_records():
                success_count += 1
            else:
                error_msgs.append("清理数据库记录失败")
        except Exception as e:
            error_msgs.append(f"清理数据库时发生错误: {e}")

        # 结果反馈
        if not error_msgs:
            dlg_success = GlassMessageDialog(
                self,
                title="成功",
                text="所有缓存已成功清除！",
                buttons=[("ok", "确定")],
            )
            dlg_success.exec_()
        else:
            dlg_error = GlassMessageDialog(
                self,
                title="部分失败",
                text="清除缓存过程中出现错误：\n" + "\n".join(error_msgs),
                buttons=[("ok", "确定")],
            )
            dlg_error.exec_()

    def accept(self):
        """
        点击确定按钮时的操作
        """
        self._closing_after_model_reload = True
        self.apply_settings()
        # 如果本次没有模型变更，则直接关闭；有模型变更时，等主窗口模型重载完成后再关闭
        if 'model' not in self.changed_categories:
            super().accept()

    def on_subprocess_mode_changed(self, state):
        """处理子进程模式切换 (已废弃，始终启用)"""
        pass
    
    def _ensure_subprocess_started(self):
        """确保子进程已启动"""
        try:
            from app.core.ocr_subprocess import get_ocr_subprocess_manager
            subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
            
            if not subprocess_manager.is_running():
                # 确定当前预设
                current_preset = 'mobile'  # 默认预设
                preset_idx = self.model_combo.currentIndex()
                if preset_idx >= 0:
                    preset_data = self.model_combo.itemData(preset_idx)
                    if preset_data in ['mobile', 'server']:
                        current_preset = preset_data
                
                success = subprocess_manager.start_process(current_preset)
                if success:
                    print(f"OCR子进程已启动，预设: {current_preset}")
                else:
                    print("OCR子进程启动失败")
        except Exception as e:
            print(f"启动子进程时出错: {e}")
    
    def _stop_subprocess(self):
        """停止子进程"""
        try:
            from app.core.ocr_subprocess import get_ocr_subprocess_manager
            subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
            subprocess_manager.stop_process()
            print("OCR子进程已停止")
        except Exception as e:
            print(f"停止子进程时出错: {e}")

    def toggle_server_input(self):
        pass

    def test_connection(self):
        pass