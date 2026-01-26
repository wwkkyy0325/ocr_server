# -*- coding: utf-8 -*-

"""
结果导出格式选择对话框
"""

try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QButtonGroup, 
                                QPushButton, QRadioButton, QLabel)
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class ExportDialog:
    def __init__(self):
        """
        初始化导出对话框
        """
        self.dialog = None
        self.format_group = None
        self.txt_radio = None
        self.json_radio = None
        self.csv_radio = None
        self.ok_button = None
        self.cancel_button = None

    def select_export_format(self):
        """
        选择导出格式

        Returns:
            str: 导出格式
        """
        if not PYQT_AVAILABLE:
            print("Using default export format 'txt' (PyQt5 not available)")
            return "txt"
            
        print("Selecting export format")
        
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
        
        self.txt_radio.setChecked(True)  # 默认选择TXT
        
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
        self.ok_button.clicked.connect(self.dialog.accept)
        self.cancel_button.clicked.connect(self.dialog.reject)
        
        # 显示对话框
        result = self.dialog.exec_()
        
        if result == QDialog.Accepted:
            if self.txt_radio.isChecked():
                return "txt"
            elif self.json_radio.isChecked():
                return "json"
            elif self.csv_radio.isChecked():
                return "csv"
        
        return "txt"  # 默认返回txt
