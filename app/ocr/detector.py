# -*- coding: utf-8 -*-

"""
文本检测（调用PaddleOCR检测接口）
"""

import os
try:
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    PADDLE_OCR_AVAILABLE = False
    print("PaddleOCR not available, using mock implementation")

from app.utils.ocr_utils import sort_ocr_regions

class Detector:
    def __init__(self, config_manager=None):
        """
        初始化文本检测器

        Args:
            config_manager: 配置管理器
        """
        print("Initializing Detector")
        self.config_manager = config_manager
        self.ocr_engine = None
        
        if PADDLE_OCR_AVAILABLE:
            try:
                # 获取模型路径
                det_model_dir = None
                if config_manager:
                    det_model_dir = config_manager.get_setting('det_model_dir')
                
                print(f"Detector det_model_dir: {det_model_dir}")
                
                # 检查模型目录是否存在
                params = {}
                
                # Load common parameters from config
                if config_manager:
                    # use_gpu causing issues with some paddleocr versions, removing for stability
                    # params['use_gpu'] = config_manager.get_setting('use_gpu', True)
                    
                    # Detection specific parameters
                    limit_side_len = config_manager.get_setting('det_limit_side_len')
                    if limit_side_len:
                        params['det_limit_side_len'] = int(limit_side_len)
                        
                    det_db_thresh = config_manager.get_setting('det_db_thresh')
                    if det_db_thresh:
                        params['det_db_thresh'] = float(det_db_thresh)
                        
                    det_db_box_thresh = config_manager.get_setting('det_db_box_thresh')
                    if det_db_box_thresh:
                        params['det_db_box_thresh'] = float(det_db_box_thresh)
                        
                    det_db_unclip_ratio = config_manager.get_setting('det_db_unclip_ratio')
                    if det_db_unclip_ratio:
                        params['det_db_unclip_ratio'] = float(det_db_unclip_ratio)
                
                if det_model_dir and os.path.exists(det_model_dir):
                    print(f"Using local detection model: {det_model_dir}")
                    params['det_model_dir'] = det_model_dir
                else:
                    print("Detection model directory not found, PaddleOCR will use default models")
                
                print(f"Initializing PaddleOCR detector with params: {params}")
                # 初始化PaddleOCR检测器
                self.ocr_engine = PaddleOCR(**params)
                print("PaddleOCR detector initialized successfully")
            except Exception as e:
                print(f"Error initializing PaddleOCR detector: {e}")
                import traceback
                traceback.print_exc()
                self.ocr_engine = None

    def detect_text_regions(self, image):
        """
        检测图像中的文本区域

        Args:
            image: 输入图像

        Returns:
            list: 检测到的文本区域列表，每个区域包含坐标和置信度
        """
        print("Detecting text regions in image")
        try:
            if PADDLE_OCR_AVAILABLE and self.ocr_engine:
                # Convert PIL image to numpy array if needed
                original_image = image
                if hasattr(image, 'convert'):
                    import numpy as np
                    image = np.array(image.convert('RGB'))
                    print(f"Converted image to numpy array, shape: {image.shape}")
                
                # 使用PaddleOCR进行文本检测
                result = self.ocr_engine.predict(image)
                print(f"Detection result: {result}")
                if result and result[0]:
                    # 检查是否有res属性或者直接检查result[0]本身
                    res = result[0].res if hasattr(result[0], 'res') else result[0]
                    print(f"Detection result details: {res}")
                    
                    # 提取识别的文本和置信度
                    recognized_texts = res.get('rec_texts', [])
                    recognized_scores = res.get('rec_scores', [])
                    rec_polys = res.get('rec_polys', [])
                    
                    # 如果rec_polys是数组，需要转换为列表格式
                    if hasattr(rec_polys, 'tolist'):
                        rec_polys = rec_polys.tolist()
                    
                    # 组合检测区域、识别文本和置信度
                    regions = []
                    for i in range(len(rec_polys)):
                        text = recognized_texts[i] if i < len(recognized_texts) else ''
                        score = recognized_scores[i] if i < len(recognized_scores) else 1.0
                        poly = rec_polys[i] if i < len(rec_polys) else []
                        
                        regions.append({
                            'coordinates': poly,
                            'confidence': float(score),
                            'text': text
                        })
                    
                    print(f"Detected {len(regions)} text regions with recognized text")
                    return sort_ocr_regions(regions)
                else:
                    print("No text regions detected (result is empty or invalid)")
                    return []
            else:
                # 模拟检测结果
                print("Error: PaddleOCR not available or failed to initialize.")
                # Return None to indicate failure, triggering proper error handling in main_window
                return None
        except Exception as e:
            print(f"Error detecting text regions: {e}")
            import traceback
            traceback.print_exc()
            return []
