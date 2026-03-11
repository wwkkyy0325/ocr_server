# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：统一的后台线程工作器封装，将耗时处理放入 QThread 运行并发射完成/错误/状态信号
# - 核心实现：包装目标函数与参数，在线程 run 中执行并捕获异常
# - 关联关系：由 ProcessingController 等模块创建并管理，用于后台批处理与进度更新
try:
    from PyQt5.QtCore import QThread, pyqtSignal

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QThread = object
    pyqtSignal = None

from app.infrastructure.error_handler import handle_errors, ErrorCode

if PYQT_AVAILABLE:
    class ProcessingWorker(QThread):
        finished_signal = pyqtSignal()
        error_signal = pyqtSignal(str)
        # 添加进度/状态信号
        status_signal = pyqtSignal(str, str)  # status_text, status_type

        def __init__(self, target, *args, **kwargs):
            super().__init__()
            self.target = target
            self.args = args
            self.kwargs = kwargs

        @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessingWorker")
        def run(self):
            """
            线程执行方法
            
            在线程中执行目标函数，并处理异常
            """
            logger = get_logger()
            try:
                logger.debug("workers", "task_start", f"开始执行任务：{self.target.__name__}")
                self.target(*self.args, **self.kwargs)
                logger.debug("workers", "task_complete", "任务执行完成")
                # noinspection PyUnresolvedReferences
                self.finished_signal.emit()
            except Exception as e:
                logger.error("workers", "thread_error", f"处理线程错误：{e}")
                import traceback
                traceback.print_exc()
                # noinspection PyUnresolvedReferences
                self.error_signal.emit(str(e))
else:
    class ProcessingWorker:
        """PyQt5 不可用时的占位类"""
        pass
