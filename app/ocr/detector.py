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

                # Add Recognition and Classification models
                rec_model_dir = config_manager.get_setting('rec_model_dir')
                if rec_model_dir and os.path.exists(rec_model_dir):
                    print(f"Using local recognition model: {rec_model_dir}")
                    params['rec_model_dir'] = rec_model_dir
                
                cls_model_dir = config_manager.get_setting('cls_model_dir')
                if cls_model_dir and os.path.exists(cls_model_dir):
                    print(f"Using local classification model: {cls_model_dir}")
                    params['cls_model_dir'] = cls_model_dir
                
                # Ensure angle classification is enabled if we have a CLS model or mandatory
                # User policy: Det, Rec, Cls are mandatory.
                if cls_model_dir or True: # Force enable
                    params['use_angle_cls'] = True
                    # Also ensure Det and Rec are enabled implicitly by not disabling them
                    # params['det'] = True # PaddleOCR init usually takes 'det_model_dir' etc, not 'det' flag directly?
                    # Actually 'det' param in init might be 'det_model_dir' presence or defaults.

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
                # Pass explicit flags to control pipeline
                # Note: predict() might not accept kwargs in all versions, but ocr() does.
                # Assuming self.ocr_engine is a PaddleOCR instance.
                if hasattr(self.ocr_engine, 'ocr'):
                    # Standard PaddleOCR usage
                    # Note: Calling ocr() with kwargs (det=True, etc.) caused TypeError: predict() got an unexpected keyword argument 'det'
                    # in some environments/versions.
                    # Since Det, Rec, Cls are mandatory and configured via __init__ (use_angle_cls=True),
                    # we call ocr() without arguments to rely on configured defaults.
                    # This avoids passing unsupported kwargs to the underlying predict method.
                    try:
                        result = self.ocr_engine.ocr(image, det=True, rec=True, cls=True)
                    except TypeError:
                        print("PaddleOCR.ocr() threw TypeError with kwargs, retrying without kwargs...")
                        result = self.ocr_engine.ocr(image)
                    
                    # Standard PaddleOCR returns a list of results (one per image)
                    # Structure: [[[[x1,y1],..], (text, score)], ...]
                    # We need to adapt this to the existing 'res' structure expectation if possible,
                    # OR adapt the parsing logic below.
                    
                    # The existing code expects 'result[0].res' (PaddleX style) or 'result[0]' (PaddleOCR style?)
                    # If we use .ocr(), result[0] is the list of line results for the first image.
                    
                    # Let's try to adapt the parsing logic to support standard PaddleOCR output too.
                    # If result[0] is a list, it's likely standard output.
                    if result and isinstance(result[0], list):
                         regions = []
                         for line in result[0]:
                             # line: [box, (text, score)]
                             box = line[0]
                             text_obj = line[1]
                             text = text_obj[0]
                             score = text_obj[1]
                             regions.append({
                                 'coordinates': box,
                                 'confidence': float(score),
                                 'text': text
                             })
                         print(f"Detected {len(regions)} text regions with recognized text (Standard Format)")
                         return sort_ocr_regions(regions)
                
                # Fallback or original method if .ocr not preferred or for PaddleX
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
