# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：封装主窗口的拖拽导入逻辑，筛选图片/PDF 并交由主流程处理
# - 核心实现：监听 DragEnter/Drop 事件，收集支持的文件路径与目录
# - 关联关系：与 MainWindow 的批处理入口对接，触发 ProcessingController 流程
import os
from PyQt5.QtCore import Qt

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
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.pdf')):
                    files.append(path)
            elif os.path.isdir(path):
                # If folder, maybe add all images? 
                # For now, let's just add the folder path if supported, or scan it
                # MainWindow logic seems to handle folders via _process_multiple_folders
                # But here we are collecting files.
                # Let's see what MainWindow does.
                self.main_window.folders.append(path)
                # And scan files?
                pass
        
        if files:
            # Call main window processing
            self.main_window._start_processing_files(files)
