# -*- coding: utf-8 -*-

"""
模型选择、识别参数设置对话框
"""

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                                QPushButton, QLabel, QLineEdit, QCheckBox, 
                                QSpinBox, QDoubleSpinBox, QGroupBox, QComboBox,
                                QFileDialog, QMessageBox)
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, UI will not be available")


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
        
        if PYQT_AVAILABLE:
            self.init_ui()
            self.load_current_settings()

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
        
        # OCR模型设置组
        model_group = QGroupBox("OCR模型设置")
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
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # 处理设置组
        processing_group = QGroupBox("处理设置")
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
        
        processing_group.setLayout(processing_layout)
        layout.addWidget(processing_group)
        
        # 识别参数组
        recognition_group = QGroupBox("识别参数")
        recognition_layout = QFormLayout()
        
        self.drop_score_spinbox = QDoubleSpinBox()
        self.drop_score_spinbox.setRange(0.0, 1.0)
        self.drop_score_spinbox.setSingleStep(0.05)
        
        self.max_text_length_spinbox = QSpinBox()
        self.max_text_length_spinbox.setRange(1, 100)
        self.max_text_length_spinbox.setValue(25)
        
        recognition_layout.addRow("置信度阈值:", self.drop_score_spinbox)
        recognition_layout.addRow("最大文本长度:", self.max_text_length_spinbox)
        
        recognition_group.setLayout(recognition_layout)
        layout.addWidget(recognition_group)
        
        # 性能监控组
        performance_group = QGroupBox("性能设置")
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
        
        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)
        
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

    def apply_settings(self):
        """
        应用设置到配置管理器
        """
        if not PYQT_AVAILABLE:
            return
            
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
        
        # 保存配置
        self.config_manager.save_config()
        
        QMessageBox.information(self, "提示", "设置已保存!")

    def accept(self):
        """
        点击确定按钮时的操作
        """
        self.apply_settings()
        super().accept()
