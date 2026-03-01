# -*- coding: utf-8 -*-
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
