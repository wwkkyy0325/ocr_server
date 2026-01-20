# -*- coding: utf-8 -*-

"""
模型选择、识别参数设置对话框
"""

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                                QPushButton, QLabel, QLineEdit, QCheckBox, 
                                QSpinBox, QDoubleSpinBox, QGroupBox, QComboBox,
                                QFileDialog, QMessageBox, QRadioButton, QButtonGroup)
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, UI will not be available")

try:
    import requests
except ImportError:
    pass

from app.ocr.client import OcrClient

class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        """
        初始化设置对话框

        Args:
            config_manager: 配置管理器实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.modified_configs = {}
        self.changed_categories = set()
        self.initial_settings = {}
        
        if PYQT_AVAILABLE:
            self.init_ui()
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
        values['det_model_dir'] = self.det_model_edit.text()
        values['rec_model_dir'] = self.rec_model_edit.text()
        values['cls_model_dir'] = self.cls_model_edit.text()
        
        # Processing settings
        values['use_gpu'] = self.use_gpu_checkbox.isChecked()
        values['use_preprocessing'] = self.preprocessing_checkbox.isChecked()
        values['use_skew_correction'] = self.skew_correction_checkbox.isChecked()
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


    def init_ui(self):
        """
        初始化UI界面
        """
        if not PYQT_AVAILABLE:
            return
            
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout()

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
        layout.addWidget(self.service_group)
        
        # OCR模型设置组
        self.model_group = QGroupBox("OCR模型设置")
        model_layout = QFormLayout()
        
        self.det_model_edit = QLineEdit()
        self.det_model_btn = QPushButton("浏览...")
        self.det_model_btn.clicked.connect(lambda: self.browse_directory(self.det_model_edit))
        det_layout = QHBoxLayout()
        det_layout.addWidget(self.det_model_edit)
        det_layout.addWidget(self.det_model_btn)
        
        self.rec_model_edit = QLineEdit()
        self.rec_model_btn = QPushButton("浏览...")
        self.rec_model_btn.clicked.connect(lambda: self.browse_directory(self.rec_model_edit))
        rec_layout = QHBoxLayout()
        rec_layout.addWidget(self.rec_model_edit)
        rec_layout.addWidget(self.rec_model_btn)
        
        self.cls_model_edit = QLineEdit()
        self.cls_model_btn = QPushButton("浏览...")
        self.cls_model_btn.clicked.connect(lambda: self.browse_directory(self.cls_model_edit))
        cls_layout = QHBoxLayout()
        cls_layout.addWidget(self.cls_model_edit)
        cls_layout.addWidget(self.cls_model_btn)
        
        model_layout.addRow("检测模型目录:", det_layout)
        model_layout.addRow("识别模型目录:", rec_layout)
        model_layout.addRow("方向分类模型目录:", cls_layout)
        
        self.model_group.setLayout(model_layout)
        layout.addWidget(self.model_group)
        
        # 处理设置组
        self.processing_group = QGroupBox("处理设置")
        processing_layout = QFormLayout()
        
        self.use_gpu_checkbox = QCheckBox("使用GPU加速")
        self.preprocessing_checkbox = QCheckBox("启用预处理")
        self.skew_correction_checkbox = QCheckBox("启用倾斜校正")
        
        self.process_count_spinbox = QSpinBox()
        self.process_count_spinbox.setRange(1, 16)
        self.process_count_spinbox.setValue(2)
        
        processing_layout.addRow(self.use_gpu_checkbox)
        processing_layout.addRow(self.preprocessing_checkbox)
        processing_layout.addRow(self.skew_correction_checkbox)
        processing_layout.addRow("处理进程数:", self.process_count_spinbox)
        
        self.processing_group.setLayout(processing_layout)
        layout.addWidget(self.processing_group)
        
        # 识别参数组
        self.recognition_group = QGroupBox("识别参数")
        recognition_layout = QFormLayout()
        
        self.drop_score_spinbox = QDoubleSpinBox()
        self.drop_score_spinbox.setRange(0.0, 1.0)
        self.drop_score_spinbox.setSingleStep(0.05)
        
        self.max_text_length_spinbox = QSpinBox()
        self.max_text_length_spinbox.setRange(1, 100)
        self.max_text_length_spinbox.setValue(25)
        
        recognition_layout.addRow("置信度阈值:", self.drop_score_spinbox)
        recognition_layout.addRow("最大文本长度:", self.max_text_length_spinbox)
        
        self.recognition_group.setLayout(recognition_layout)
        layout.addWidget(self.recognition_group)
        
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
        layout.addWidget(self.performance_group)
        
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
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

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
            
        # 加载模型路径
        self.det_model_edit.setText(self.config_manager.get_setting('det_model_dir', ''))
        self.rec_model_edit.setText(self.config_manager.get_setting('rec_model_dir', ''))
        self.cls_model_edit.setText(self.config_manager.get_setting('cls_model_dir', ''))
        
        # 加载处理设置
        self.use_gpu_checkbox.setChecked(self.config_manager.get_setting('use_gpu', False))
        self.preprocessing_checkbox.setChecked(self.config_manager.get_setting('use_preprocessing', True))
        self.skew_correction_checkbox.setChecked(self.config_manager.get_setting('use_skew_correction', False))
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
        if (current_values['det_model_dir'] != self.initial_settings.get('det_model_dir') or
            current_values['rec_model_dir'] != self.initial_settings.get('rec_model_dir') or
            current_values['cls_model_dir'] != self.initial_settings.get('cls_model_dir')):
            self.changed_categories.add('model')
            
        # 2. 检查处理设置
        if (current_values['use_gpu'] != self.initial_settings.get('use_gpu') or
            current_values['use_preprocessing'] != self.initial_settings.get('use_preprocessing') or
            current_values['use_skew_correction'] != self.initial_settings.get('use_skew_correction') or
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
            
        # 更新模型路径
        self.config_manager.set_setting('det_model_dir', self.det_model_edit.text())
        self.config_manager.set_setting('rec_model_dir', self.rec_model_edit.text())
        self.config_manager.set_setting('cls_model_dir', self.cls_model_edit.text())
        
        # 更新处理设置
        self.config_manager.set_setting('use_gpu', self.use_gpu_checkbox.isChecked())
        self.config_manager.set_setting('use_preprocessing', self.preprocessing_checkbox.isChecked())
        self.config_manager.set_setting('use_skew_correction', self.skew_correction_checkbox.isChecked())
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
        self.model_group.setEnabled(not is_online)
        self.processing_group.setEnabled(not is_online)
        self.recognition_group.setEnabled(not is_online)
        self.performance_group.setEnabled(not is_online)
        
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
