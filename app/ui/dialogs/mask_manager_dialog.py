# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QListWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, 
    QWidget, QFileDialog, QInputDialog
)
from app.ui.styles.glass_components import GlassTitleBar, FramelessBorderDialog
from app.ui.dialogs.glass_dialogs import GlassMessageDialog

class MaskManagerDialog(FramelessBorderDialog):
    def __init__(self, mask_manager, parent=None):
        super().__init__(parent)
        self.mask_manager = mask_manager
        self.setWindowTitle("蒙版管理")
        self.resize(420, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = GlassTitleBar("蒙版管理", self)
        layout.addWidget(title_bar)

        content_widget = QWidget(self)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 12, 16, 16)
        content_layout.setSpacing(8)
        layout.addWidget(content_widget)

        self.list_widget = QListWidget()
        content_layout.addWidget(self.list_widget)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        content_layout.addWidget(self.info_label)

        btn_row = QHBoxLayout()
        self.btn_rename = QPushButton("重命名")
        self.btn_delete = QPushButton("删除")
        self.btn_export = QPushButton("导出全部")
        self.btn_import = QPushButton("导入")
        btn_row.addWidget(self.btn_rename)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_import)
        content_layout.addLayout(btn_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        close_row.addWidget(btn_close)
        content_layout.addLayout(close_row)

        self._load_masks()

        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.btn_rename.clicked.connect(self._on_rename_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_import.clicked.connect(self._on_import_clicked)

    def _load_masks(self):
        self.list_widget.clear()
        names = self.mask_manager.get_all_mask_names()
        for name in names:
            self.list_widget.addItem(name)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self.info_label.setText("暂无蒙版，请在主界面绘制并保存。")

    def _current_mask_name(self):
        item = self.list_widget.currentItem()
        return item.text() if item else None

    def _on_current_changed(self, current, previous):
        name = current.text() if current else None
        if not name:
            self.info_label.setText("")
            return
        data = self.mask_manager.get_mask(name)
        if not data:
            self.info_label.setText("蒙版数据不可用")
            return
        if isinstance(data, list) and data and isinstance(data[0], dict):
            count = len(data)
            self.info_label.setText(f"蒙版名称: {name}\n包含 {count} 个区域")
        else:
            self.info_label.setText(f"蒙版名称: {name}")

    def _on_rename_clicked(self):
        name = self._current_mask_name()
        if not name:
            return
        new_name, ok = QInputDialog.getText(self, "重命名蒙版", "请输入新名称:", text=name)
        if ok and new_name and new_name != name:
            self.mask_manager.rename_mask(name, new_name)
            self._load_masks()

    def _on_delete_clicked(self):
        name = self._current_mask_name()
        if not name:
            return
        dlg = GlassMessageDialog(
            self,
            title="确认删除",
            text=f"确定要删除蒙版 '{name}' 吗？",
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg.exec_()
        if dlg.result_key() == "yes":
            self.mask_manager.delete_mask(name)
            self._load_masks()

    def _on_export_clicked(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出蒙版配置", "", "JSON Files (*.json)")
        if file_path:
            self.mask_manager.export_masks(file_path)

    def _on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入蒙版配置", "", "JSON Files (*.json)")
        if file_path:
            self.mask_manager.import_masks(file_path)
            self._load_masks()
