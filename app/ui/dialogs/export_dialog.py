# -*- coding: utf-8 -*-

"""
结果导出格式选择对话框
"""
# 文件说明：
# - 作用：提供 TXT/JSON/CSV 导出格式选择
# - 核心实现：简单单选按钮与按钮组，返回用户选择
# - 关联关系：由主界面或结果管理功能调用，决定导出格式

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QButtonGroup,
                                 QPushButton, QRadioButton, QLabel)
    from PyQt5.QtCore import Qt

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # 定义占位符，避免 NameError
    QDialog = None
    QVBoxLayout = None
    QHBoxLayout = None
    QButtonGroup = None
    QPushButton = None
    QRadioButton = None
    QLabel = None
    Qt = None


from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class ExportDialog:
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="ExportDialog")
    def __init__(self):
        """
        初始化导出对话框
        """
        logger = get_logger()
        logger.debug("export_dialog", "initializing", "Initializing export dialog")

        self.dialog = None
        self.format_group = None
        self.txt_radio = None
        self.json_radio = None
        self.csv_radio = None
        self.ok_button = None
        self.cancel_button = None

    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return="txt", component="ExportDialog")
    def select_export_format(self):
        """
        选择导出格式

        Returns:
            str: 导出格式
        """
        logger = get_logger()
        
        if not PYQT_AVAILABLE:
            logger.warning("export_dialog", "pyqt_unavailable", "Using default export format 'txt' (PyQt5 not available)")
            return "txt"

        logger.info("export_dialog", "selecting_format", "Selecting export format")

        # 创建对话框
        self.dialog = QDialog()
        self.dialog.setWindowTitle("选择导出格式")
        self.dialog.setModal(True)
        self.dialog.resize(250, 150)

        # 创建布局
        layout = QVBoxLayout(self.dialog)

        # 创建标签
        label = QLabel("请选择导出格式:")
        layout.addWidget(label)

        # 创建单选按钮组
        self.format_group = QButtonGroup()

        self.txt_radio = QRadioButton("TXT 格式")
        self.json_radio = QRadioButton("JSON 格式")
        self.csv_radio = QRadioButton("CSV 格式")

        self.txt_radio.setChecked(True)  # 默认选择 TXT

        self.format_group.addButton(self.txt_radio, 0)
        self.format_group.addButton(self.json_radio, 1)
        self.format_group.addButton(self.csv_radio, 2)

        layout.addWidget(self.txt_radio)
        layout.addWidget(self.json_radio)
        layout.addWidget(self.csv_radio)

        # 创建按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # 连接信号
        self.ok_button.clicked.connect(self.dialog.accept)  # type:  ignore
        self.cancel_button.clicked.connect(self.dialog.reject)  # type:  ignore

        # 显示对话框
        result = self.dialog.exec_()

        if result == QDialog.Accepted:
            if self.txt_radio.isChecked():
                selected_format = "txt"
            elif self.json_radio.isChecked():
                selected_format = "json"
            elif self.csv_radio.isChecked():
                selected_format = "csv"
            else:
                selected_format = "txt"
            
            logger.success("export_dialog", "format_selected", f"Export format selected: {selected_format}")
            return selected_format
        else:
            logger.debug("export_dialog", "cancelled", "Export format selection cancelled by user")
            return "txt"  # 默认返回 txt
