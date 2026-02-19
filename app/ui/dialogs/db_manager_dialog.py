# -*- coding: utf-8 -*-
import os
import shutil
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QPushButton, QLabel, QFileDialog, 
                             QListWidgetItem, QInputDialog, QLineEdit)
from PyQt5.QtCore import Qt
from app.main_window import FramelessBorderDialog, GlassTitleBar, GlassMessageDialog

class DbManagerDialog(FramelessBorderDialog):
    def __init__(self, db_dir, parent=None):
        super().__init__(parent)
        self.db_dir = db_dir
        self.setWindowTitle("数据库管理")
        self.resize(400, 300)
        
        # Ensure directory exists
        os.makedirs(self.db_dir, exist_ok=True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = GlassTitleBar("数据库管理", self)
        main_layout.addWidget(title_bar)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(12, 8, 12, 12)
        self.layout.setSpacing(8)
        main_layout.addLayout(self.layout)
        
        # Title / Description
        self.label = QLabel("现有数据库列表:")
        self.layout.addWidget(self.label)
        
        # Database List
        self.db_list = QListWidget()
        self.layout.addWidget(self.db_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("导入外部数据库")
        self.import_btn.clicked.connect(self.import_db)
        
        self.delete_btn = QPushButton("删除选中数据库")
        self.delete_btn.clicked.connect(self.delete_db)
        
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.delete_btn)
        self.layout.addLayout(btn_layout)
        
        # Refresh list
        self.refresh_list()
        
    def refresh_list(self):
        self.db_list.clear()
        if not os.path.exists(self.db_dir):
            return
            
        files = [f for f in os.listdir(self.db_dir) if f.endswith('.db')]
        for f in files:
            item = QListWidgetItem(f)
            self.db_list.addItem(item)
            
    def import_db(self):
        source_db, _ = QFileDialog.getOpenFileName(
            self,
            "选择现有数据库文件",
            "",
            "SQLite Database (*.db);;All Files (*)"
        )
        if not source_db:
            return
            
        base_name = os.path.basename(source_db)
        target_path = os.path.join(self.db_dir, base_name)
        
        if os.path.exists(target_path):
            # 生成默认的不重复名称
            name_root, ext = os.path.splitext(base_name)
            counter = 1
            new_name = f"{name_root}-{counter}{ext}"
            while os.path.exists(os.path.join(self.db_dir, new_name)):
                counter += 1
                new_name = f"{name_root}-{counter}{ext}"
            
            # 提示用户重命名
            text, ok = QInputDialog.getText(
                self, 
                "文件名冲突", 
                f"数据库 '{base_name}' 已存在。\n为了防止覆盖，请确认新的保存名称:",
                QLineEdit.Normal, 
                new_name
            )
            
            if not ok or not text.strip():
                return
            
            base_name = text.strip()
            # 确保后缀正确
            if not base_name.lower().endswith('.db'):
                base_name += '.db'
                
            target_path = os.path.join(self.db_dir, base_name)
            
            # 如果用户手动修改的名字仍然冲突，再次确认覆盖
            if os.path.exists(target_path):
                 dlg = GlassMessageDialog(
                     self, 
                     title="文件已存在", 
                     text=f"数据库 '{base_name}' 仍然存在。\n是否覆盖？",
                     buttons=[("yes", "是"), ("no", "否")],
                 )
                 dlg.exec_()
                 if dlg.result_key() != "yes":
                     return
                 
        try:
            shutil.copy2(source_db, target_path)
            self.refresh_list()
            dlg_ok = GlassMessageDialog(
                self,
                title="成功",
                text=f"数据库已成功导入",
                buttons=[("ok", "确定")],
            )
            dlg_ok.exec_()
        except Exception as e:
            dlg_err = GlassMessageDialog(
                self,
                title="错误",
                text=f"导入数据库失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err.exec_()

    def delete_db(self):
        current_item = self.db_list.currentItem()
        if not current_item:
            dlg = GlassMessageDialog(
                self,
                title="提示",
                text="请先选择要删除的数据库",
                buttons=[("ok", "确定")],
            )
            dlg.exec_()
            return
            
        db_name = current_item.text()
        db_path = os.path.join(self.db_dir, db_name)
        
        dlg_confirm = GlassMessageDialog(
            self,
            title="确认删除",
            text=f"确定要删除数据库 '{db_name}' 吗？\n此操作不可恢复！",
            buttons=[("yes", "是"), ("no", "否")],
        )
        dlg_confirm.exec_()
        
        if dlg_confirm.result_key() == "yes":
            try:
                os.remove(db_path)
                self.refresh_list()
                dlg_ok2 = GlassMessageDialog(
                    self,
                    title="成功",
                    text="数据库已删除",
                    buttons=[("ok", "确定")],
                )
                dlg_ok2.exec_()
            except Exception as e:
                dlg_err2 = GlassMessageDialog(
                    self,
                    title="错误",
                    text=f"删除失败: {e}",
                    buttons=[("ok", "确定")],
                )
                dlg_err2.exec_()
