# -*- coding: utf-8 -*-
from PyQt5.QtCore import QObject, pyqtSignal


try:
    from PyQt5.QtGui import QImage
except ImportError:
    QImage = object


class ProcessingSignals(QObject):
    status_updated = pyqtSignal(str, str)
    file_processed = pyqtSignal(str, str)
    processing_finished = pyqtSignal(float)
    progress_updated = pyqtSignal(int, int)
    ocr_result_ready = pyqtSignal(str)


class UISignals(QObject):
    text_blocks_generated = pyqtSignal(list)
    text_block_selected = pyqtSignal(int, object)
    text_blocks_selected = pyqtSignal(list)
    text_block_hovered = pyqtSignal(int)


class CaptureSignals(QObject):
    image_captured = pyqtSignal(QImage)


class DownloadSignals(QObject):
    model_download_progress = pyqtSignal(int, int)
    model_download_finished = pyqtSignal(bool, str)


class AutomationSignals(QObject):
    automation_update = pyqtSignal(dict)
    automation_finished = pyqtSignal(list)


class SignalBus(QObject):
    status_updated = pyqtSignal(str, str)
    file_processed = pyqtSignal(str, str)
    processing_finished = pyqtSignal(float)
    progress_updated = pyqtSignal(int, int)
    ocr_result_ready = pyqtSignal(str)
    image_captured = pyqtSignal(QImage)
    text_blocks_generated = pyqtSignal(list)
    text_block_selected = pyqtSignal(int, object)
    text_blocks_selected = pyqtSignal(list)
    text_block_hovered = pyqtSignal(int)
    model_download_progress = pyqtSignal(int, int)
    model_download_finished = pyqtSignal(bool, str)
    automation_update = pyqtSignal(dict)
    automation_finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.processing = ProcessingSignals()
        self.ui = UISignals()
        self.capture = CaptureSignals()
        self.download = DownloadSignals()
        self.automation = AutomationSignals()
        
        # 集成监控
        try:
            from app.core.signal_monitor import get_signal_monitor
            self.monitor = get_signal_monitor()
            self._connect_monitor()
        except Exception as e:
            print(f"Failed to init signal monitor: {e}")

        self.processing.status_updated.connect(self.status_updated)
        self.processing.file_processed.connect(self.file_processed)
        self.processing.processing_finished.connect(self.processing_finished)
        self.processing.progress_updated.connect(self.progress_updated)
        self.processing.ocr_result_ready.connect(self.ocr_result_ready)

        self.ui.text_blocks_generated.connect(self.text_blocks_generated)
        self.ui.text_block_selected.connect(self.text_block_selected)
        self.ui.text_blocks_selected.connect(self.text_blocks_selected)
        self.ui.text_block_hovered.connect(self.text_block_hovered)

        self.capture.image_captured.connect(self.image_captured)

        self.download.model_download_progress.connect(self.model_download_progress)
        self.download.model_download_finished.connect(self.model_download_finished)

        self.automation.automation_update.connect(self.automation_update)
        self.automation.automation_finished.connect(self.automation_finished)

    def _connect_monitor(self):
        """将所有信号连接到监控器"""
        if not hasattr(self, 'monitor'): return
        
        # 辅助函数：生成带名称的 lambda
        def make_recorder(name):
            return lambda *args: self.monitor.record_emit(name)

        # 遍历所有分域信号
        for domain_name in ['processing', 'ui', 'capture', 'download', 'automation']:
            domain_obj = getattr(self, domain_name)
            # 遍历域对象的所有属性，找到 pyqtBoundSignal
            # 注意：pyqtSignal 在实例上表现为 pyqtBoundSignal
            for attr_name in dir(domain_obj):
                if attr_name.startswith('_'): continue
                signal = getattr(domain_obj, attr_name)
                if hasattr(signal, 'connect'):
                    # 连接到监控器
                    # 注意：为了避免循环引用或过度开销，这里只记录计数
                    # 使用默认参数绑定 name
                    signal.connect(lambda *args, n=f"{domain_name}.{attr_name}": self.monitor.record_emit(n))


_global_bus = None


def get_signal_bus():
    global _global_bus
    if _global_bus is None:
        _global_bus = SignalBus()
        try:
            from app.core.service_registry import ServiceRegistry
            ServiceRegistry.register("signal_bus", _global_bus)
        except Exception:
            pass
    return _global_bus
