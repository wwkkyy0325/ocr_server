# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：封装主窗口的拖拽导入逻辑，筛选图片/PDF 并交由主流程处理
# - 核心实现：监听 DragEnter/Drop 事件，收集支持的文件路径与目录
# - 关联关系：与 MainWindow 的批处理入口对接，触发 ProcessingController 流程
import os


class DragDropHandler:
    def __init__(self, main_window):
        self.main_window = main_window

    def handle_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def handle_drop(self, event):
        files = []
        folders = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.pdf')):
                    files.append(path)
            elif os.path.isdir(path):
                folders.append(path)
        
        # 处理文件
        if files:
            # Call main window processing
            self.main_window._start_processing_files(files)
        
        # 处理文件夹（通过UI列表添加）
        for folder in folders:
            # 直接调用MainWindow的_add_folder方法来添加文件夹到UI
            if hasattr(self.main_window, '_add_folder_from_path'):
                self.main_window._add_folder_from_path(folder)
            else:
                # 如果没有专门的方法，直接添加到UI列表
                from PyQt5.QtWidgets import QListWidgetItem
                from PyQt5.QtCore import Qt
                folder_name = os.path.basename(folder) or folder
                item = QListWidgetItem(folder_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, folder)
                item.setToolTip(folder)
                self.main_window.ui.folder_list.addItem(item)