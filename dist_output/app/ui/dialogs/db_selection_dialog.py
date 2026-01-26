# -*- coding: utf-8 -*-

import os
import glob
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QPushButton, 
                             QLabel, QHBoxLayout, QMessageBox, QInputDialog)
from PyQt5.QtCore import Qt

class DbSelectionDialog(QDialog):
    def __init__(self, db_dir, parent=None):
        super().__init__(parent)
        self.db_dir = db_dir
        self.selected_db_path = None
        
        self.setWindowTitle("选择数据库")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 说明标签
        layout.addWidget(QLabel("请选择要查询的数据库:"))
        
        # 数据库列表
        self.db_list = QListWidget()
        self.db_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.db_list)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        self.confirm_btn = QPushButton("确定")
        self.confirm_btn.clicked.connect(self.accept_selection)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self.load_databases()
        
    def load_databases(self):
        self.db_list.clear()
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)
            
        # 获取所有.db文件
        db_files = glob.glob(os.path.join(self.db_dir, "*.db"))
        
        # 还要检查根目录下的ocr_data.db（为了兼容旧数据）
        root_db = os.path.join(os.path.dirname(self.db_dir), "ocr_data.db")
        if os.path.exists(root_db):
            db_files.append(root_db)
            
        for db_path in db_files:
            filename = os.path.basename(db_path)
            self.db_list.addItem(filename)
            # 存储完整路径
            item = self.db_list.item(self.db_list.count() - 1)
            item.setData(Qt.UserRole, db_path)
            
    def on_item_double_clicked(self, item):
        self.accept_selection()
        
    def accept_selection(self):
        current_item = self.db_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择一个数据库")
            return
            
        self.selected_db_path = current_item.data(Qt.UserRole)
        self.accept()
