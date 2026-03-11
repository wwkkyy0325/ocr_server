# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：异步加载（或初始化）OCR 模型以避免阻塞 UI 线程
# - 核心实现：在 QThread 中获取统一 OCR 引擎实例，并通过信号返回结果/错误
# - 关联关系：由 MainWindow 等在模型切换或首次启动时使用，配合 EnvManager/ConfigManager 工作
from PyQt5.QtCore import QThread, pyqtSignal
import traceback


class ModelLoaderThread(QThread):
    """
    Model loading thread
    """
    model_loaded = pyqtSignal(object)  # type: pyqtSignal
    model_load_failed = pyqtSignal(str)  # type: pyqtSignal

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager

    def run(self):
        try:
            from app.core.ocr.engine import OcrEngine
            # Just create the engine (it will load models internally if needed)
            engine = OcrEngine(self.config_manager)
            self.model_loaded.emit(engine)  # type: ignore[attr-defined]
        except Exception as e:
            traceback.print_exc()
            self.model_load_failed.emit(str(e))  # type: ignore[attr-defined]
