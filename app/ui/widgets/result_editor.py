# Path: src/app/ui/widgets/result_editor.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
识别结果编辑框（支持手动修正）
"""

try:
    from PyQt5.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class ResultEditor(QWidget):
    def __init__(self):
        """
        初始化结果编辑器
        """
        super().__init__()
        self.text_edit = None
        self.original_text = ""
        
        if PYQT_AVAILABLE:
            self._setup_ui()

    def _setup_ui(self):
        """
        设置UI界面
        """
        layout = QVBoxLayout()
        
        # 创建标签
        label = QLabel("识别结果 (可编辑):")
        layout.addWidget(label)
        
        # 创建文本编辑框
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存修改")
        reset_button = QPushButton("重置")
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 连接信号
        save_button.clicked.connect(self.save_changes)
        reset_button.clicked.connect(self.reset_changes)
        
        self.setLayout(layout)

    def edit_result(self, ocr_result):
        """
        编辑OCR结果

        Args:
            ocr_result: OCR识别结果

        Returns:
            str: 编辑后的结果
        """
        print(f"Editing OCR result: {ocr_result}")
        self.original_text = ocr_result
        
        if PYQT_AVAILABLE and self.text_edit:
            self.text_edit.setPlainText(ocr_result)
            
        return ocr_result
        
    def save_changes(self):
        """
        保存修改
        """
        if PYQT_AVAILABLE and self.text_edit:
            modified_text = self.text_edit.toPlainText()
            print(f"Saved modified text: {modified_text}")
            # 在实际应用中，这里应该发出信号或调用回调函数来处理保存的文本
            
    def reset_changes(self):
        """
        重置修改
        """
        if PYQT_AVAILABLE and self.text_edit:
            self.text_edit.setPlainText(self.original_text)
            print("Reset to original text")
