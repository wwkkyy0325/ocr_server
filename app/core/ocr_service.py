# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：批处理服务门面，向 MainWindow/控制层提供统一的状态更新回调与处理入口
# - 核心实现：将状态更新汇总到 status_signal，协调主窗口的批量文件/文件夹处理方法
# - 关联关系：由主窗口构造并注入，用于在多线程/服务模式中安全地汇报进度与触发处理
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.main_window import MainWindow

class OcrBatchService:
    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.status_signal = None

    def set_status_signal(self, signal):
        self.status_signal = signal

    def update_status(self, text, status_type="working"):
        if self.status_signal:
            self.status_signal.emit(text, status_type)
        else:
            # Fallback to direct UI update if running in main thread (not recommended but safe fallback)
            # Or just print
            print(f"Status Update: {text} ({status_type})")

    def process_folders(self, folders_to_process=None, force_reprocess=False):
        self.main_window._process_multiple_folders(folders_to_process=folders_to_process, force_reprocess=force_reprocess, status_callback=self.update_status)

    def process_files(self, files, output_dir, default_mask_data=None, force_reprocess=False):
        # Inject self into main_window temporarily to allow it to use update_status via service?
        # Actually, main_window methods call self.ui.status_bar directly which is BAD in thread.
        # We need to monkey patch or redirect status updates in main_window logic.
        
        # Better approach: process_files calls main_window._process_files
        # We need to make _process_files use a thread-safe status update mechanism.
        # Since _process_files is a method of MainWindow, it has access to self.
        # We can add a method thread_safe_set_status to MainWindow.
        
        self.main_window._process_files(files, output_dir, default_mask_data=default_mask_data, force_reprocess=force_reprocess, status_callback=self.update_status)
