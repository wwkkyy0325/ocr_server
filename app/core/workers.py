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

if PYQT_AVAILABLE:
    class ProcessingWorker(QThread):
        finished_signal = pyqtSignal()
        error_signal = pyqtSignal(str)
        # 添加进度/状态信号
        status_signal = pyqtSignal(str, str) # status_text, status_type

        def __init__(self, target, *args, **kwargs):
            super().__init__()
            self.target = target
            self.args = args
            self.kwargs = kwargs

        def run(self):
            try:
                self.target(*self.args, **self.kwargs)
                self.finished_signal.emit()
            except Exception as e:
                print(f"Error in processing thread: {e}")
                import traceback
                traceback.print_exc()
                self.error_signal.emit(str(e))
else:
    class ProcessingWorker:
        pass
