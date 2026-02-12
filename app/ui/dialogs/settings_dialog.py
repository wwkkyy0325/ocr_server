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
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

try:
    import requests
except ImportError:
    pass

from app.ocr.client import OcrClient
from app.ui.dialogs.model_download_dialog import ModelDownloadDialog

class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None, initial_tab_index=0):
        """
        初始化设置对话框

        Args:
            config_manager: 配置管理器实例
            parent: 父窗口
            initial_tab_index: 初始选中的标签页索引 (0: 常规设置, 1: 模型管理)
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
            set: 包含已更改类别的集合 {'model', 'processing', 'recognition', 'performance', 'ocr_service'}
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
        
        # Processing settings
        # values['use_gpu'] = self.use_gpu_checkbox.isChecked()
        values['use_preprocessing'] = self.preprocessing_checkbox.isChecked()
        values['use_skew_correction'] = True # Always enable skew correction as requested
        values['use_padding'] = self.padding_checkbox.isChecked()
        values['padding_size'] = self.padding_size_spinbox.value()
        values['processing_processes'] = self.process_count_spinbox.value()
        
        # Recognition settings
        values['drop_score'] = self.drop_score_spinbox.value()
        values['max_text_length'] = self.max_text_length_spinbox.value()
        
        # Performance settings
        values['cpu_limit'] = self.cpu_limit_spinbox.value()
        values['max_processing_time'] = self.max_time_spinbox.value()
        
        # OCR Service settings
        is_online = self.mode_online_radio.isChecked()
        values['is_online'] = is_online
        values['ocr_server_url'] = self.server_url_edit.text().strip() if is_online else ''
        
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
        
        # --- Tab 1: 常规设置 ---
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        # OCR服务设置组
        self.service_group = QGroupBox("OCR服务设置")
        service_layout = QFormLayout()

        self.mode_local_radio = QRadioButton("本地模式")
        self.mode_online_radio = QRadioButton("联机模式")
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_local_radio)
        mode_layout.addWidget(self.mode_online_radio)
        
        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("例如: http://127.0.0.1:8082")
        
        self.test_conn_btn = QPushButton("测试连接")
        self.test_conn_btn.clicked.connect(self.test_connection)
        self.conn_status_label = QLabel("未测试")
        self.conn_status_label.setStyleSheet("color: gray")
        
        conn_layout = QHBoxLayout()
        conn_layout.addWidget(self.server_url_edit)
        conn_layout.addWidget(self.test_conn_btn)
        conn_layout.addWidget(self.conn_status_label)
        
        service_layout.addRow("运行模式:", mode_layout)
        service_layout.addRow("服务器地址:", conn_layout)
        
        self.service_group.setLayout(service_layout)
        general_layout.addWidget(self.service_group)
        
        # 处理设置组
        self.processing_group = QGroupBox("处理设置")
        processing_layout = QFormLayout()
        
        self.preprocessing_checkbox = QCheckBox("启用预处理")
        self.preprocessing_checkbox.setToolTip("对图像进行对比度增强和降噪处理，可提高文字识别准确率")
        # self.skew_correction_checkbox = QCheckBox("启用倾斜校正") # Moved to Recognition Parameters
        
        self.padding_checkbox = QCheckBox("启用边缘补全 (Padding)")
        self.padding_checkbox.setToolTip("当图片边缘内容识别不全时启用，会在识别前给图片四周增加白边")
        
        self.padding_size_spinbox = QSpinBox()
        self.padding_size_spinbox.setRange(0, 500)
        self.padding_size_spinbox.setValue(50)
        self.padding_size_spinbox.setSuffix(" px")
        
        self.process_count_spinbox = QSpinBox()
        self.process_count_spinbox.setRange(1, 16)
        self.process_count_spinbox.setValue(2)
        
        processing_layout.addRow(self.preprocessing_checkbox)
        # processing_layout.addRow(self.skew_correction_checkbox) # Moved
        processing_layout.addRow(self.padding_checkbox)
        processing_layout.addRow("补全宽度:", self.padding_size_spinbox)
        processing_layout.addRow("处理进程数:", self.process_count_spinbox)
        
        self.processing_group.setLayout(processing_layout)
        general_layout.addWidget(self.processing_group)

        # Check GPU availability and disable checkbox if no GPU - REMOVED (Auto-detect only)
        # try:
        #     import paddle
        #     if not paddle.is_compiled_with_cuda():
        #         self.use_gpu_checkbox.setChecked(False)
        #         self.use_gpu_checkbox.setEnabled(False)
        #         self.use_gpu_checkbox.setText("使用GPU加速 (未检测到支持CUDA的PaddlePaddle)")
        #         self.use_gpu_checkbox.setToolTip("当前安装的 PaddlePaddle 不支持 GPU 或未检测到 CUDA，强制使用 CPU 模式")
        # except Exception:
        #     # If import fails, assume no GPU
        #     self.use_gpu_checkbox.setChecked(False)
        #     self.use_gpu_checkbox.setEnabled(False)
        #     self.use_gpu_checkbox.setText("使用GPU加速 (检测失败)")
        
        # 识别参数组
        self.recognition_group = QGroupBox("识别参数")
        recognition_layout = QFormLayout()
        
        # self.skew_correction_checkbox = QCheckBox("启用方向分类 (倾斜矫正)")
        # self.skew_correction_checkbox.setToolTip("启用方向分类模型(CLS)，可自动识别并纠正文本的 90°/180° 旋转")
        
        self.drop_score_spinbox = QDoubleSpinBox()
        self.drop_score_spinbox.setRange(0.0, 1.0)
        self.drop_score_spinbox.setSingleStep(0.05)
        
        self.max_text_length_spinbox = QSpinBox()
        self.max_text_length_spinbox.setRange(1, 100)
        self.max_text_length_spinbox.setValue(25)
        
        # recognition_layout.addRow(self.skew_correction_checkbox)
        recognition_layout.addRow("置信度阈值:", self.drop_score_spinbox)
        recognition_layout.addRow("最大文本长度:", self.max_text_length_spinbox)
        
        self.recognition_group.setLayout(recognition_layout)
        general_layout.addWidget(self.recognition_group)
        
        # 性能监控组
        self.performance_group = QGroupBox("性能设置")
        performance_layout = QFormLayout()
        
        self.cpu_limit_spinbox = QSpinBox()
        self.cpu_limit_spinbox.setRange(0, 100)
        self.cpu_limit_spinbox.setValue(70)
        self.cpu_limit_spinbox.setSuffix(" %")
        
        self.max_time_spinbox = QSpinBox()
        self.max_time_spinbox.setRange(1, 300)
        self.max_time_spinbox.setValue(30)
        self.max_time_spinbox.setSuffix(" 秒")
        
        performance_layout.addRow("CPU使用限制:", self.cpu_limit_spinbox)
        performance_layout.addRow("最大处理时间:", self.max_time_spinbox)
        
        self.performance_group.setLayout(performance_layout)
        general_layout.addWidget(self.performance_group)
        
        general_layout.addStretch()
        self.main_tab_widget.addTab(general_tab, "常规设置")
        
        # --- Tab 2: 环境管理 ---
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

        # --- Tab 3: 模型管理 ---
        model_mgt_tab = QWidget()
        model_mgt_layout = QVBoxLayout(model_mgt_tab)
        
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
        
        self.model_tab_widget = QTabWidget()
        self.model_widgets = {}
        
        # Tabs for Det, Rec, Cls, Unwarp
        self.init_model_tab("det", "检测模型 (Detection)")
        self.init_model_tab("rec", "识别模型 (Recognition)")
        self.init_model_tab("cls", "方向分类模型 (Classification)")
        self.init_model_tab("unwarp", "图像矫正模型 (Unwarping)")
        
        model_mgt_layout.addWidget(self.model_tab_widget)
        self.main_tab_widget.addTab(model_mgt_tab, "模型管理")
        
        main_layout.addWidget(self.main_tab_widget)
        
        # Set initial tab
        if initial_tab_index >= 0 and initial_tab_index < self.main_tab_widget.count():
            self.main_tab_widget.setCurrentIndex(initial_tab_index)
        
        # 模式切换事件
        self.mode_local_radio.toggled.connect(self.toggle_server_input)
        self.mode_online_radio.toggled.connect(self.toggle_server_input)
        
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

    def init_model_tab(self, model_type, title):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Enable Checkbox
        enable_cb = QCheckBox(f"启用 {title}")
        
        # Enforce mandatory models: Det, Rec, Cls
        if model_type in ['det', 'rec', 'cls']:
            enable_cb.setChecked(True)
            enable_cb.setEnabled(False) # Make it read-only
            enable_cb.setToolTip("此模型为必选项，无法禁用")
        else:
            enable_cb.setChecked(True) # Default for others (e.g. unwarp)
            
        enable_cb.stateChanged.connect(lambda: self.on_model_enable_changed(model_type))
        layout.addWidget(enable_cb)
        
        # Model Selection Group
        group = QGroupBox("模型选择")
        group_layout = QVBoxLayout()
        
        desc_label = QLabel(f"选择模型版本：")
        group_layout.addWidget(desc_label)
        
        combo_layout = QHBoxLayout()
        combo = QComboBox()
        combo.currentIndexChanged.connect(lambda idx: self.on_model_changed(model_type))
        combo_layout.addWidget(combo)
        
        download_btn = QPushButton("下载")
        download_btn.setEnabled(False)
        download_btn.clicked.connect(lambda: self.download_model(model_type))
        combo_layout.addWidget(download_btn)
        
        group_layout.addLayout(combo_layout)
        
        status_label = QLabel("")
        group_layout.addWidget(status_label)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        
        self.model_tab_widget.addTab(tab, title.split(" ")[0])
        
        # Store references
        self.model_widgets[model_type] = {
            'enable_cb': enable_cb,
            'combo': combo,
            'download_btn': download_btn,
            'status_label': status_label,
            'group': group
        }
        
        # Populate
        models = self.config_manager.model_manager.get_available_models(model_type)
        for key, desc, is_downloaded, size in models:
            status_icon = "✅" if is_downloaded else "☁️"
            combo.addItem(f"{status_icon} {desc} : {size}", key)

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
        
        btn = widgets['download_btn']
        status_lbl = widgets['status_label']
        
        if is_downloaded:
            btn.setEnabled(False)
            btn.setText("已就绪")
            status_lbl.setText(f"模型已下载，可以正常使用。\n路径: {self.config_manager.model_manager.get_model_dir(model_type, key)}")
            status_lbl.setStyleSheet("color: green;")
        else:
            btn.setEnabled(True)
            btn.setText("下载模型")
            status_lbl.setText("模型未下载，请点击下载按钮。")
            status_lbl.setStyleSheet("color: red;")
            
    def download_model(self, model_type):
        widgets = self.model_widgets[model_type]
        combo = widgets['combo']
        key = combo.itemData(combo.currentIndex())
        desc = combo.currentText()
        
        missing = [(model_type, key, desc)]
        dialog = ModelDownloadDialog(self.config_manager.model_manager, missing, self)
        if dialog.exec_() == QDialog.Accepted:
            # Refresh UI
            current_idx = combo.currentIndex()
            combo.clear()
            models = self.config_manager.model_manager.get_available_models(model_type)
            for k, d, is_downloaded, size in models:
                status_icon = "✅" if is_downloaded else "☁️"
                combo.addItem(f"{status_icon} {d} : {size}", k)
            combo.setCurrentIndex(current_idx)
            self.update_model_status(model_type)
            QMessageBox.information(self, "成功", "模型下载成功！")

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
            widgets = self.model_widgets[model_type]
            
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
            
        self.preprocessing_checkbox.setChecked(self.config_manager.get_setting('use_preprocessing', True))
        # self.skew_correction_checkbox.setChecked(self.config_manager.get_setting('use_skew_correction', False))
        self.padding_checkbox.setChecked(self.config_manager.get_setting('use_padding', False))
        self.padding_size_spinbox.setValue(self.config_manager.get_setting('padding_size', 50))
        self.process_count_spinbox.setValue(self.config_manager.get_setting('processing_processes', 2))
        
        # 加载识别参数
        self.drop_score_spinbox.setValue(self.config_manager.get_setting('drop_score', 0.5))
        self.max_text_length_spinbox.setValue(self.config_manager.get_setting('max_text_length', 25))
        
        # 加载性能设置
        self.cpu_limit_spinbox.setValue(self.config_manager.get_setting('cpu_limit', 70))
        self.max_time_spinbox.setValue(self.config_manager.get_setting('max_processing_time', 30))

        # 加载OCR服务设置
        server_url = self.config_manager.get_setting('ocr_server_url', '')
        if server_url:
            self.mode_online_radio.setChecked(True)
            self.server_url_edit.setText(server_url)
        else:
            self.mode_local_radio.setChecked(True)
            self.server_url_edit.setText("http://127.0.0.1:8082")
            
        # 强制更新UI状态
        self.toggle_server_input()
        
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
            key_changed = current_values.get(f'{model_type}_model_key') != self.initial_settings.get(f'{model_type}_model_key')
            enable_changed = current_values.get(f'use_{model_type}_model') != self.initial_settings.get(f'use_{model_type}_model')
            if key_changed or enable_changed:
                model_changed = True
                break
        
        if model_changed:
            self.changed_categories.add('model')
            
        # 2. 检查处理设置
        if (current_values['use_preprocessing'] != self.initial_settings.get('use_preprocessing') or
            current_values['use_skew_correction'] != self.initial_settings.get('use_skew_correction') or
            current_values['use_padding'] != self.initial_settings.get('use_padding') or
            current_values['padding_size'] != self.initial_settings.get('padding_size') or
            current_values['processing_processes'] != self.initial_settings.get('processing_processes')):
            self.changed_categories.add('processing')
            
        # 3. 检查识别参数
        if (current_values['drop_score'] != self.initial_settings.get('drop_score') or
            current_values['max_text_length'] != self.initial_settings.get('max_text_length')):
            self.changed_categories.add('recognition')
            
        # 4. 检查性能设置
        if (current_values['cpu_limit'] != self.initial_settings.get('cpu_limit') or
            current_values['max_processing_time'] != self.initial_settings.get('max_processing_time')):
            self.changed_categories.add('performance')
            
        # 5. 检查OCR服务设置
        if (current_values['is_online'] != self.initial_settings.get('is_online') or
            current_values['ocr_server_url'] != self.initial_settings.get('ocr_server_url')):
            self.changed_categories.add('ocr_service')
            
        # 更新模型设置
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            self.config_manager.set_setting(f'use_{model_type}_model', current_values[f'use_{model_type}_model'])
            # ConfigManager.set_model handles setting the key and the dir
            self.config_manager.set_model(model_type, current_values[f'{model_type}_model_key'])
        
        # 更新处理设置
        # self.config_manager.set_setting('use_gpu', self.use_gpu_checkbox.isChecked())
        self.config_manager.set_setting('use_preprocessing', self.preprocessing_checkbox.isChecked())
        # Force enable skew correction
        self.config_manager.set_setting('use_skew_correction', True)
        self.config_manager.set_setting('use_padding', self.padding_checkbox.isChecked())
        self.config_manager.set_setting('padding_size', self.padding_size_spinbox.value())
        self.config_manager.set_setting('processing_processes', self.process_count_spinbox.value())
        
        # 更新识别参数
        self.config_manager.set_setting('drop_score', self.drop_score_spinbox.value())
        self.config_manager.set_setting('max_text_length', self.max_text_length_spinbox.value())
        
        # 更新性能设置
        self.config_manager.set_setting('cpu_limit', self.cpu_limit_spinbox.value())
        self.config_manager.set_setting('max_processing_time', self.max_time_spinbox.value())
        
        # 更新OCR服务设置
        if self.mode_online_radio.isChecked():
            url = self.server_url_edit.text().strip()
            self.config_manager.set_setting('ocr_server_url', url)
        else:
            self.config_manager.set_setting('ocr_server_url', '')

        # 保存配置
        self.config_manager.save_config()
        
        QMessageBox.information(self, "提示", "设置已保存!")

    def accept(self):
        """
        点击确定按钮时的操作
        """
        self.apply_settings()
        super().accept()

    def toggle_server_input(self):
        """
        切换服务器地址输入框状态
        """
        is_online = self.mode_online_radio.isChecked()
        self.server_url_edit.setEnabled(is_online)
        self.test_conn_btn.setEnabled(is_online)
        
        # 联机模式下禁用本地设置
        self.processing_group.setEnabled(not is_online)
        self.recognition_group.setEnabled(not is_online)
        self.performance_group.setEnabled(not is_online)
        
        # Disable Model Management tab (index 1)
        if hasattr(self, 'main_tab_widget'):
            self.main_tab_widget.setTabEnabled(1, not is_online)
        
        if not is_online:
            self.conn_status_label.setText("未测试")
            self.conn_status_label.setStyleSheet("color: gray")

    def test_connection(self):
        """
        测试OCR服务器连接
        """
        url = self.server_url_edit.text().strip()
        if not url:
            self.conn_status_label.setText("请输入地址")
            self.conn_status_label.setStyleSheet("color: red")
            return
            
        self.test_conn_btn.setEnabled(False)
        self.conn_status_label.setText("正在连接...")
        self.conn_status_label.setStyleSheet("color: orange")
        
        # 使用QApplication.processEvents()刷新UI
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            client = OcrClient(url, timeout=3)
            is_ok = client.health_check()
            if is_ok:
                self.conn_status_label.setText("连接成功")
                self.conn_status_label.setStyleSheet("color: green")
            else:
                self.conn_status_label.setText("连接失败")
                self.conn_status_label.setStyleSheet("color: red")
        except Exception as e:
            self.conn_status_label.setText(f"连接错误")
            self.conn_status_label.setToolTip(str(e))
            self.conn_status_label.setStyleSheet("color: red")
        finally:
            self.test_conn_btn.setEnabled(True)
