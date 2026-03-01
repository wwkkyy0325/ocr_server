from PyQt5.QtCore import QThread, pyqtSignal
import traceback

class ModelLoaderThread(QThread):
    """
    Thread for loading OCR models asynchronously to prevent UI freezing
    """
    finished_signal = pyqtSignal(object, object) # detector, recognizer
    error_signal = pyqtSignal(str)

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager

    def run(self):
        try:
            print("Starting async model loading...")
            from app.ocr.engine import OcrEngine
            
            # 使用单例模式获取全局OCR引擎实例
            # 这样可以确保整个应用只有一个模型实例被加载
            ocr_engine = OcrEngine.get_instance(
                config_manager=self.config_manager, 
                detector=None, 
                recognizer=None,
                preset='mobile'  # 默认使用mobile预设节省资源
            )
            
            # 为了保持接口兼容性，我们仍然返回detector和recognizer
            # 但实际上它们会按需创建，不会立即加载模型
            detector = None  # 延迟创建
            recognizer = None  # 延迟创建
            
            self.finished_signal.emit(detector, recognizer)
            print("Async model loading finished - Global unified engine instance created")
        except Exception as e:
            traceback.print_exc()
            self.error_signal.emit(str(e))
