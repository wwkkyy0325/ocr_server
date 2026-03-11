# -*- coding: utf-8 -*-

"""
批量识别配置对话框
"""
# 文件说明：
# - 作用：配置批量处理参数（递归/并行/线程数/导出格式）
# - 核心实现：表单式参数收集，返回配置字典
# - 关联关系：由主流程在批量任务开始前调用，指导 ProcessManager/导出逻辑

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                                 QPushButton, QCheckBox, QSpinBox, QComboBox, QLabel)
    from PyQt5.QtCore import Qt

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # 定义占位符，避免 NameError
    QDialog = None
    QVBoxLayout = None
    QHBoxLayout = None
    QFormLayout = None
    QPushButton = None
    QCheckBox = None
    QSpinBox = None
    QComboBox = None
    QLabel = None
    Qt = None

from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class BatchDialog:
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="BatchDialog")
    def __init__(self):
        """
        初始化批量处理对话框
        """
        logger = get_logger()
        logger.debug("batch_dialog", "initializing", "Initializing batch dialog")
        
        self.dialog = None
        self.recursive_checkbox = None
        self.parallel_checkbox = None
        self.thread_count_spinbox = None
        self.format_combobox = None
        self.ok_button = None
        self.cancel_button = None

    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="BatchDialog")
    def configure_batch_processing(self):
        """
        配置批量处理参数

        Returns:
            dict: 批量处理配置
        """
        logger = get_logger()
        
        if not PYQT_AVAILABLE:
            logger.warning("batch_dialog", "pyqt_unavailable", "PyQt5 not available, using default configuration")
            return {
                'recursive': False,
                'parallel': True,
                'thread_count': 4,
                'output_format': 'txt'
            }

        logger.info("batch_dialog", "configuring", "Configuring batch processing parameters")

        # 创建对话框
        self.dialog = QDialog()
        self.dialog.setWindowTitle("批量处理配置")
        self.dialog.setModal(True)
        self.dialog.resize(300, 200)

        # 创建布局
        layout = QVBoxLayout(self.dialog)

        # 创建表单布局
        form_layout = QFormLayout()

        # 递归处理选项
        self.recursive_checkbox = QCheckBox("递归处理子目录")
        self.recursive_checkbox.setChecked(False)
        form_layout.addRow(self.recursive_checkbox)

        # 并行处理选项
        self.parallel_checkbox = QCheckBox("并行处理")
        self.parallel_checkbox.setChecked(True)
        form_layout.addRow(self.parallel_checkbox)

        # 线程数设置
        self.thread_count_spinbox = QSpinBox()
        self.thread_count_spinbox.setRange(1, 16)
        self.thread_count_spinbox.setValue(4)
        form_layout.addRow("线程数:", self.thread_count_spinbox)

        # 输出格式选择
        self.format_combobox = QComboBox()
        self.format_combobox.addItems(["txt", "json", "csv"])
        form_layout.addRow("输出格式:", self.format_combobox)

        layout.addLayout(form_layout)

        # 创建按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # 连接信号
        self.ok_button.clicked.connect(self.dialog.accept)   # type: ignore
        self.cancel_button.clicked.connect(self.dialog.reject)   # type: ignore

        # 显示对话框
        result = self.dialog.exec_()

        if result == QDialog.Accepted:
            config = {
                'recursive': self.recursive_checkbox.isChecked(),
                'parallel': self.parallel_checkbox.isChecked(),
                'thread_count': self.thread_count_spinbox.value(),
                'output_format': self.format_combobox.currentText()
            }
            logger.success("batch_dialog", "configured", 
                          f"Batch config: recursive={config['recursive']}, parallel={config['parallel']}, threads={config['thread_count']}, format={config['output_format']}")
            return config
        else:
            logger.debug("batch_dialog", "cancelled", "Batch configuration cancelled by user")
            return None
