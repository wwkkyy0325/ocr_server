# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：封装 OCR 图像处理主流程（预处理 → 统一引擎检测识别 → 后处理），对外提供 process_image
# - 核心实现：组合 Preprocessor 与 UnifiedOCREngine，坐标还原
# - 关联关系：被 ProcessingController 调用执行实际图像识别；依赖 ConfigManager 决定模型与开关；其输出交由 ResultAdapter/前端可视化

import traceback
import numpy as np
from PIL import Image
from app.core.ocr.unified_engine import UnifiedOCREngine
from app.config.config_manager import ConfigManager
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()


class OcrEngine:
    _instance = None
    _lock = None

    @classmethod
    def get_instance(cls, config_manager=None, preset='mobile'):
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info("ocr_engine", "creating_instance", f"Creating global OCR engine instance with preset:"
                                                                   f" {preset}")
                    cls._instance = cls(config_manager, preset=preset)
        return cls._instance

    def __init__(self, config_manager=None, preset='mobile'):
        """
        Initialize OCR Engine with necessary components
        
        Args:
            config_manager: ConfigManager instance
            preset: OCR preset mode ('mobile', 'server', 'ai_table')
        """
        self.config_manager = config_manager or ConfigManager()
        if not config_manager:
            self.config_manager.load_config()

        logger.info("ocr_engine", "initializing", f"OcrEngine initializing with preset: {preset}")


        # 初始化统一 OCR 引擎作为主引擎（使用传入的预设配置）
        self.unified_engine = UnifiedOCREngine(self.config_manager, preset=preset)

        logger.success("ocr_engine", "initialized", "Unified OCR Engine initialized as primary OCR processor")


    @handle_errors(error_code=ErrorCode.OCR_ENGINE_001, fallback_return={'full_text': '', 'regions': [], 'status': 'error'}, component="OcrEngine")
    def process_image(self, image, options=None):
        """
        Process an image using the unified OCR engine
        
        Args:
            image: PIL Image object
            options: Dictionary of processing options (overrides config)
            
        Returns:
            dict: Processing result
        """
        options = options or {}

        # Ensure image is PIL Image
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        # Skip preprocessing - handled by caller if needed
        if options.get('skip_preprocessing', False):
            # Ensure image is PIL Image even if skipped
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
        else:
            # Check if preprocessor is available
            if hasattr(self, 'preprocessor'):
                # We don't save temp files here
                image = self.preprocessor.comprehensive_preprocess(image, None, "temp")
            else:
                logger.debug("ocr_engine", "preprocessor_not_available", "Preprocessor not available, skipping preprocessing")

        # Get AI table setting from options or config
        use_ai_table = options.get('use_ai_table',
                                   self.config_manager.get_setting('use_ai_table', False))
        logger.debug("ocr_engine", "config_check", f"OcrEngine.process_image use_ai_table={use_ai_table} (from options)")

        # Process with unified engine
        logger.info("ocr_engine", "detection_method", "Using unified OCR engine for detection and recognition (primary method)")
        regions = self.unified_engine.process_image(image)
        
        # Convert regions list to standard format
        full_text = '\n'.join([region.get('text', '') for region in regions if region.get('text')])
        
        # Return result in standard format
        return {
            'full_text': full_text,
            'regions': regions,
            'status': 'success'
        }
