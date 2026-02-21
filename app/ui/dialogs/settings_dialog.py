# -*- coding: utf-8 -*-

"""
模型选择、识别参数设置对话框
"""

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                                QPushButton, QLabel, QLineEdit, QCheckBox, 
                                QSpinBox, QDoubleSpinBox, QGroupBox, QComboBox,
                                QFileDialog, QRadioButton, QButtonGroup,
                                QTabWidget, QWidget)
    from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal
    from PyQt5.QtGui import QDesktopServices
    from app.main_window import FramelessBorderDialog, GlassTitleBar, GlassMessageDialog
    from app.ui.widgets.progress_bar import CyberEnergyBar
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

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
        self.applied_model_keys = {}
        self.energy_anim_timers = {}
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
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            if model_type in self.model_widgets:
                widgets = self.model_widgets[model_type]
                combo = widgets['combo']
                idx = combo.currentIndex()
                if idx >= 0:
                    values[f'{model_type}_model_key'] = combo.itemData(idx)
                else:
                    values[f'{model_type}_model_key'] = None
        
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
        
        # 一键切换配置组
        preset_group = QGroupBox("快捷配置 (Quick Switch)")
        preset_layout = QHBoxLayout()
        
        preset_label = QLabel("一键切换模型组合:")
        preset_label.setMinimumWidth(120)
        preset_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.model_preset_combo = QComboBox()
        self.model_preset_combo.setMinimumWidth(260)
        self.model_preset_combo.setMaximumWidth(260)
        self.model_preset_combo.addItem("自定义配置 (Custom)", "custom")
        self.model_preset_combo.addItem("CPU 均衡模式 (Mobile Models)", "cpu")
        self.model_preset_combo.addItem("GPU 高精度模式 (Server Models)", "gpu")
        self.model_preset_combo.setToolTip("快速切换 CPU(轻量级) 或 GPU(高精度) 模型组合")
        self._center_align_combo_items(self.model_preset_combo)
        
        self.model_preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addStretch()
        preset_layout.addWidget(self.model_preset_combo)
        
        preset_group.setLayout(preset_layout)
        model_mgt_layout.addWidget(preset_group)
        
        self.model_widgets = {}
        
        self.init_model_tab("det", "检测模型 (Detection)", model_mgt_layout)
        self.init_model_tab("rec", "识别模型 (Recognition)", model_mgt_layout)
        self.init_model_tab("cls", "方向分类模型 (Classification)", model_mgt_layout)
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
            'group': container
        }
        
        models = self.config_manager.model_manager.get_available_models(model_type)
        for key, desc, is_downloaded, size in models:
            combo.addItem(f"{desc} : {size}", key)
        self._center_align_combo_items(combo)

    def _center_align_combo_items(self, combo):
        for i in range(combo.count()):
            combo.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)

    def on_preset_changed(self, index):
        """处理预设切换"""
        preset = self.model_preset_combo.itemData(index)
        if preset == 'custom':
            return
            
        # Define presets
        presets = {
            'cpu': {
                'det': 'PP-OCRv5_mobile_det',
                'rec': 'PP-OCRv5_mobile_rec'
            },
            'gpu': {
                'det': 'PP-OCRv5_server_det',
                'rec': 'PP-OCRv5_server_rec'
            }
        }
        
        target_models = presets.get(preset)
        if not target_models:
            return
            
        # Apply models
        for model_type, model_key in target_models.items():
            if model_type in self.model_widgets:
                combo = self.model_widgets[model_type]['combo']
                # Find index of key
                idx = combo.findData(model_key)
                if idx >= 0:
                    # Block signals to prevent recursive check_preset_match
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
                    # Manually trigger status update
                    self.update_model_status(model_type)

    def check_preset_match(self):
        """检查当前选择是否匹配预设"""
        if not hasattr(self, 'model_preset_combo'):
            return
            
        current_det = self._get_current_model_key('det')
        current_rec = self._get_current_model_key('rec')
        
        target_preset = 'custom'
        
        if (current_det == 'PP-OCRv5_mobile_det' and 
            current_rec == 'PP-OCRv5_mobile_rec'):
            target_preset = 'cpu'
        elif (current_det == 'PP-OCRv5_server_det' and 
              current_rec == 'PP-OCRv5_server_rec'):
            target_preset = 'gpu'
            
        # Update combo without triggering signal
        idx = self.model_preset_combo.findData(target_preset)
        if idx >= 0 and idx != self.model_preset_combo.currentIndex():
            self.model_preset_combo.blockSignals(True)
            self.model_preset_combo.setCurrentIndex(idx)
            self.model_preset_combo.blockSignals(False)

    def _get_current_model_key(self, model_type):
        if model_type in self.model_widgets:
            combo = self.model_widgets[model_type]['combo']
            idx = combo.currentIndex()
            if idx >= 0:
                return combo.itemData(idx)
        return None

    def on_model_changed(self, model_type):
        self.update_model_status(model_type)
        self.check_preset_match()
        
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
            
        # 加载模型设置（仅加载当前选择的模型）
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            widgets = self.model_widgets.get(model_type)
            if not widgets:
                continue

            current_key = self.config_manager.get_setting(f'{model_type}_model_key')
            combo = widgets['combo']

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

            # 记录当前视图中认为“已应用”的模型键，用于能量条状态判断
            if combo.currentIndex() >= 0:
                self.applied_model_keys[model_type] = combo.itemData(combo.currentIndex())
            else:
                self.applied_model_keys[model_type] = None

            self.update_model_status(model_type)

        # 加载处理设置
        # use_gpu_setting = self.config_manager.get_setting('use_gpu', False)
        # if self.use_gpu_checkbox.isEnabled():
        #     self.use_gpu_checkbox.setChecked(use_gpu_setting)
        # else:
        #     # If disabled (no GPU), force unchecked
        #     self.use_gpu_checkbox.setChecked(False)

        # 加载OCR服务设置
        # Check preset match after loading all models
        self.check_preset_match()
        
        # 保存初始设置状态用于差量更新检查
        self.initial_settings = self._get_ui_values()

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
        # 这里的“是否需要重载模型”以 self.applied_model_keys 为基准，
        # 表示当前 OCR 引擎正在使用的模型键；只有与之不一致才触发真实重载。
        model_changed = False
        changed_model_types = []
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            if model_type not in self.model_widgets:
                continue
            current_key = current_values.get(f'{model_type}_model_key')
            applied_key = self.applied_model_keys.get(model_type)
            key_changed = current_key != applied_key
            if key_changed:
                model_changed = True
                changed_model_types.append(model_type)
        
        if model_changed:
            self.changed_categories.add('model')
            
        # 更新模型设置
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            if model_type not in self.model_widgets:
                continue
            # ConfigManager.set_model handles setting the key and the dir
            self.config_manager.set_model(model_type, current_values[f'{model_type}_model_key'])
        
        # 保存配置
        self.config_manager.save_config()

        # 启动对应模型能量条动画 + 通知主窗口进行真实模型重载
        if changed_model_types:
            self._start_model_energy_animation(changed_model_types, current_values)
            if PYQT_AVAILABLE and hasattr(self, 'model_settings_applied'):
                try:
                    self.model_settings_applied.emit(changed_model_types)
                except Exception:
                    pass
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
                # 成功时将该模型类型标记为“当前已应用”的新基线
                if model_type in self.model_widgets:
                    combo = self.model_widgets[model_type]['combo']
                    idx = combo.currentIndex()
                    if idx >= 0:
                        self.applied_model_keys[model_type] = combo.itemData(idx)
            else:
                energy_bar.set_range(0, 100)
                energy_bar.set_value(0)
                energy_bar.set_ready_text("待应用")

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
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
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
            if current_key is not None:
                target_idx = -1
                for i in range(combo.count()):
                    if combo.itemData(i) == current_key:
                        target_idx = i
                        break
                if target_idx >= 0:
                    combo.setCurrentIndex(target_idx)
                elif combo.count() > 0:
                    combo.setCurrentIndex(0)
            elif combo.count() > 0:
                combo.setCurrentIndex(0)

            self.update_model_status(model_type)

        # 同步预设下拉的状态
        self.check_preset_match()

    def accept(self):
        """
        点击确定按钮时的操作
        """
        self._closing_after_model_reload = True
        self.apply_settings()
        # 如果本次没有模型变更，则直接关闭；有模型变更时，等主窗口模型重载完成后再关闭
        if 'model' not in self.changed_categories:
            super().accept()

    def toggle_server_input(self):
        pass

    def test_connection(self):
        pass
