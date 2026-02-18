# -*- coding: utf-8 -*-

"""
模型选择、识别参数设置对话框
"""

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                                QPushButton, QLabel, QLineEdit, QCheckBox, 
                                QSpinBox, QDoubleSpinBox, QGroupBox, QComboBox,
                                QFileDialog, QMessageBox, QRadioButton, QButtonGroup,
                                QTabWidget, QWidget)
    from PyQt5.QtCore import Qt, QUrl
    from PyQt5.QtGui import QDesktopServices
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

class SettingsDialog(QDialog):
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
        # Model settings
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            if model_type in self.model_widgets:
                widgets = self.model_widgets[model_type]
                values[f'use_{model_type}_model'] = widgets['enable_cb'].isChecked()
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
        self.resize(600, 500)
        
        main_layout = QVBoxLayout()
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
        
        manage_group = QGroupBox("环境维护")
        manage_layout = QVBoxLayout()
        
        manage_desc = QLabel("如果要切换 PaddlePaddle 版本（例如升级到 GPU 版或回退到 CPU 版），\n或者修复环境问题，需要重启进入维护模式。")
        manage_desc.setWordWrap(True)
        manage_layout.addWidget(manage_desc)
        
        btn_manage = QPushButton("重启并进入环境管理器")
        btn_manage.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; padding: 8px;")
        btn_manage.clicked.connect(self.restart_to_manager)
        manage_layout.addWidget(btn_manage)
        
        manage_group.setLayout(manage_layout)
        env_layout.addWidget(manage_group)
        
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
        self.model_preset_combo = QComboBox()
        self.model_preset_combo.addItem("自定义配置 (Custom)", "custom")
        self.model_preset_combo.addItem("CPU 均衡模式 (Mobile Models)", "cpu")
        self.model_preset_combo.addItem("GPU 高精度模式 (Server Models)", "gpu")
        self.model_preset_combo.setToolTip("快速切换 CPU(轻量级) 或 GPU(高精度) 模型组合")
        
        self.model_preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.model_preset_combo)
        preset_layout.addStretch()
        
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
        
        main_layout.addWidget(self.main_tab_widget)
        
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
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def restart_to_manager(self):
        """重启应用并进入环境管理器模式"""
        try:
            import subprocess
            import os
            import sys
            from PyQt5.QtWidgets import QApplication
            
            reply = QMessageBox.question(
                self, 
                "确认重启", 
                "此操作将关闭当前应用并启动环境管理器。\n未保存的设置将丢失。\n是否继续？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 构造重启命令：启动 Launcher 并带上 --manage 参数
                # 注意：这里我们假设 run.py 或 launcher.py 在项目根目录
                
                # 获取项目根目录
                import sys
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                
                # 如果是打包环境，路径可能不同，这里主要处理开发环境
                launcher_path = os.path.join(project_root, "launcher.py")
                
                if os.path.exists(launcher_path):
                    cmd = [sys.executable, launcher_path, "--manage"]
                    # Use CREATE_NEW_CONSOLE to detach launcher from this dying process
                    creation_flags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                    subprocess.Popen(cmd, cwd=project_root, creationflags=creation_flags)
                    
                    # Force kill current process to ensure it closes thoroughly
                    # QApplication.quit() is not enough if there are background threads
                    os._exit(0)
                else:
                    QMessageBox.critical(self, "错误", f"找不到启动器文件：{launcher_path}")
                    
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重启失败: {str(e)}")

    def init_model_tab(self, model_type, title, parent_layout):
        container = QGroupBox(title)
        layout = QVBoxLayout(container)
        
        enable_cb = QCheckBox(f"启用 {title}")
        if model_type in ['det', 'rec', 'cls']:
            enable_cb.setChecked(True)
            enable_cb.setEnabled(False)
            enable_cb.setToolTip("此模型为必选项，无法禁用")
        else:
            enable_cb.setChecked(True)
            
        enable_cb.stateChanged.connect(lambda: self.on_model_enable_changed(model_type))
        layout.addWidget(enable_cb)
        
        group = QGroupBox("模型选择")
        group_layout = QVBoxLayout()
        
        desc_label = QLabel("选择模型版本：")
        group_layout.addWidget(desc_label)
        
        combo = QComboBox()
        combo.currentIndexChanged.connect(lambda idx: self.on_model_changed(model_type))
        group_layout.addWidget(combo)
        
        status_label = QLabel("")
        group_layout.addWidget(status_label)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        
        parent_layout.addWidget(container)
        
        self.model_widgets[model_type] = {
            'enable_cb': enable_cb,
            'combo': combo,
            'status_label': status_label,
            'group': group
        }
        
        models = self.config_manager.model_manager.get_available_models(model_type)
        for key, desc, is_downloaded, size in models:
            combo.addItem(f"{desc} : {size}", key)

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

    def on_model_enable_changed(self, model_type):
        widgets = self.model_widgets[model_type]
        enabled = widgets['enable_cb'].isChecked()
        widgets['group'].setEnabled(enabled)

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
        
        status_lbl = widgets['status_label']
        
        if is_downloaded:
            status_lbl.setText("当前模型已缓存，将按需自动加载。")
            status_lbl.setStyleSheet("color: green;")
        else:
            status_lbl.setText("当前模型将在首次使用时后台加载。")
            status_lbl.setStyleSheet("color: gray;")

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
            
        # 加载模型设置
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            widgets = self.model_widgets.get(model_type)
            if not widgets:
                continue
                
            # Load enable state
            is_enabled = self.config_manager.get_setting(f'use_{model_type}_model', True if model_type in ['det', 'rec', 'cls'] else False)
            
            # Enforce mandatory check
            if model_type in ['det', 'rec', 'cls']:
                is_enabled = True
                
            widgets['enable_cb'].setChecked(is_enabled)
            widgets['group'].setEnabled(is_enabled)
            
            # Load selected model
            current_key = self.config_manager.get_setting(f'{model_type}_model_key')
            combo = widgets['combo']
            
            # Find index
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
        model_changed = False
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            if model_type not in self.model_widgets:
                continue
                
            key_changed = current_values.get(f'{model_type}_model_key') != self.initial_settings.get(f'{model_type}_model_key')
            enable_changed = current_values.get(f'use_{model_type}_model') != self.initial_settings.get(f'use_{model_type}_model')
            if key_changed or enable_changed:
                model_changed = True
                break
        
        if model_changed:
            self.changed_categories.add('model')
            
        # 更新模型设置
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            if model_type not in self.model_widgets:
                continue
            self.config_manager.set_setting(f'use_{model_type}_model', current_values[f'use_{model_type}_model'])
            # ConfigManager.set_model handles setting the key and the dir
            self.config_manager.set_model(model_type, current_values[f'{model_type}_model_key'])
        
        # 保存配置
        self.config_manager.save_config()
        
        QMessageBox.information(self, "提示", "设置已保存!")

    def uninstall_local_models(self):
        """
        卸载本程序下载的本地模型文件（项目 models 目录及部分缓存目录）
        """
        if not PYQT_AVAILABLE:
            return

        reply = QMessageBox.question(
            self,
            "确认卸载模型",
            "此操作将尝试删除本程序下载的离线模型目录：\n"
            " - 项目目录下的 models/paddle_ocr\n"
            " - 如果设置了 PADDLEX_HOME / PADDLE_HUB_HOME 等环境变量，则尝试清理其中的模型缓存。\n\n"
            "该操作不会卸载 PaddlePaddle/PaddleOCR 代码本身，只清理模型文件。\n\n"
            "确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
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

        QMessageBox.information(self, "模型卸载完成", "\n".join(msg_lines))

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
        self.apply_settings()
        super().accept()

    def toggle_server_input(self):
        pass

    def test_connection(self):
        pass
