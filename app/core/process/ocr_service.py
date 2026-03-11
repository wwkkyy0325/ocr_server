# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：批处理服务门面，向 MainWindow/控制层提供统一的状态更新回调与处理入口
# - 核心实现：将状态更新汇总到 status_signal，协调主窗口的批量文件/文件夹处理方法
# - 关联关系：由主窗口构造并注入，用于在多线程/服务模式中安全地汇报进度与触发处理
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class OcrBatchService:
    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.status_signal = None

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="OcrBatchService")
    def set_status_signal(self, signal):
        self.status_signal = signal

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="OcrBatchService")
    def update_status(self, text, status_type="working"):
        if self.status_signal:
            self.status_signal.emit(text, status_type)
        else:
            # Fallback: 使用日志管理器记录状态（降级为 debug 以减少噪声）
            logger = get_logger()
            logger.debug("ocr_service", "status_update", f"{text} ({status_type})")

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="OcrBatchService")
    def process_folders(self, folders_to_process=None, force_reprocess=False):
        self.main_window._start_processing(folders_to_process=folders_to_process,
                                           force_reprocess=force_reprocess)

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="OcrBatchService")
    def process_files(self, files, force_reprocess=False):
        # 直接调用主窗口的 _start_processing_files 方法
        self.main_window._start_processing_files(files,  # type: ignore[attr-defined]
                                                 force_reprocess=force_reprocess)
