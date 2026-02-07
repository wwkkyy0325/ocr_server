# -*- coding: utf-8 -*-

"""
文本识别（调用PaddleOCR识别接口）
"""

import os
try:
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    PADDLE_OCR_AVAILABLE = False
    print("PaddleOCR not available, using mock implementation")


class Recognizer:
    def __init__(self, config_manager=None):
        """
        初始化文本识别器

        Args:
            config_manager: 配置管理器
        """
        print("Initializing Recognizer")
        self.config_manager = config_manager
        self.ocr_engine = None
        
        if PADDLE_OCR_AVAILABLE:
            try:
                # 获取模型路径
                rec_model_dir = None
                cls_model_dir = None
                if config_manager:
                    rec_model_dir = config_manager.get_setting('rec_model_dir')
                    cls_model_dir = config_manager.get_setting('cls_model_dir')
                
                print(f"Recognizer rec_model_dir: {rec_model_dir}")
                print(f"Recognizer cls_model_dir: {cls_model_dir}")
                
                # 检查模型目录是否存在
                params = {}
                
                # Load common parameters from config
                # Check if PaddlePaddle is compiled with CUDA
                try:
                    import paddle
                    is_gpu_available = paddle.is_compiled_with_cuda()
                    print(f"PaddlePaddle compiled with CUDA: {is_gpu_available}")
                except Exception:
                    is_gpu_available = False
                    print("Could not determine if PaddlePaddle is compiled with CUDA, assuming False")

                # Auto-detect GPU usage (User policy: GPU if available, else CPU)
                use_gpu = is_gpu_available
                
                # PaddleOCR 3.2.0 uses 'device' instead of 'use_gpu'
                params['device'] = 'gpu' if use_gpu else 'cpu'
                # Remove use_gpu as it causes Unknown argument error in newer PaddleOCR versions
                # params['use_gpu'] = use_gpu
                print(f"PaddleOCR device set to: {params['device']} (Auto-detected)")

                if config_manager:
                    # PaddleOCR 3.2.0 uses 'device' instead of 'use_gpu'
                    # params['device'] = 'gpu' if use_gpu else 'cpu'
                    # Recognizer doesn't strictly need 'device' if not passed, but good to have if we updated logic
                    # Keeping existing logic but printing warning
                    
                    # use_gpu causing issues with some paddleocr versions
                    # params['use_gpu'] = config_manager.get_setting('use_gpu', True)
                    params['use_angle_cls'] = config_manager.get_setting('use_skew_correction', False)
                    
                    # rec_image_shape causing issues with some paddleocr versions
                    # rec_image_shape = config_manager.get_setting('rec_image_shape')
                    # if rec_image_shape:
                    #     params['rec_image_shape'] = rec_image_shape
                        
                    # Precision
                    precision = config_manager.get_setting('precision')
                    if precision:
                        params['precision'] = precision
                
                if rec_model_dir and os.path.exists(rec_model_dir):
                    print(f"Using local recognition model: {rec_model_dir}")
                    params['rec_model_dir'] = rec_model_dir
                    
                if cls_model_dir and os.path.exists(cls_model_dir):
                    print(f"Using local classification model: {cls_model_dir}")
                    params['cls_model_dir'] = cls_model_dir
                
                # 禁用 mkldnn 以解决兼容性问题
                params['enable_mkldnn'] = False

                print(f"Initializing PaddleOCR recognizer with params: {params}")
                # 初始化PaddleOCR识别器
                try:
                    self.ocr_engine = PaddleOCR(**params)
                    print("PaddleOCR recognizer initialized successfully")
                except Exception as e:
                    print(f"Error initializing PaddleOCR recognizer with GPU: {e}")
                    if params.get('device') == 'gpu':
                        print("Attempting fallback to CPU mode...")
                        params['device'] = 'cpu'
                        if 'use_gpu' in params:
                            del params['use_gpu']
                        self.ocr_engine = PaddleOCR(**params)
                        print("PaddleOCR recognizer initialized successfully (Fallback to CPU)")
                    else:
                        raise e
            except Exception as e:
                print(f"Error initializing PaddleOCR recognizer: {e}")
                import traceback
                traceback.print_exc()
                self.ocr_engine = None

    def recognize_text(self, image):
        """
        识别图像中的文本

        Args:
            image: 输入图像或图像路径

        Returns:
            dict: 识别结果，包括文本和置信度
        """
        print("Recognizing text in image")
        try:
            if PADDLE_OCR_AVAILABLE and self.ocr_engine:
                # Convert PIL image to numpy array if needed
                if hasattr(image, 'convert'):
                    import numpy as np
                    image = np.array(image.convert('RGB'))
                
                # 使用PaddleOCR进行文本识别
                result = self.ocr_engine.predict(image)
                print(f"Recognition result: {result}")
                if result and result[0]:
                    # 检查是否有res属性或者直接检查result[0]本身
                    res = result[0].res if hasattr(result[0], 'res') else result[0]
                    print(f"Recognition result details: {res}")
                    
                    # 检查rec_text或者rec_texts
                    if res.get('rec_text') is not None:
                        text = res['rec_text']
                        score = res.get('rec_score', 1.0)
                        
                        return {
                            'text': text,
                            'confidence': float(score)
                        }
                    elif res.get('rec_texts') is not None:
                        # 如果返回的是文本列表，获取第一个文本
                        texts = res['rec_texts']
                        scores = res.get('rec_scores', [1.0] * len(texts)) if res.get('rec_scores') is not None else [1.0] * len(texts)
                        
                        # 过滤掉空文本，返回第一个非空文本
                        for i, text in enumerate(texts):
                            if text and text.strip():
                                return {
                                    'text': text,
                                    'confidence': float(scores[i]) if i < len(scores) else 1.0
                                }
                        
                        # 如果没有非空文本，返回置信度最高的文本
                        if texts and scores:
                            max_score_index = scores.index(max(scores))
                            return {
                                'text': texts[max_score_index],
                                'confidence': float(scores[max_score_index])
                            }
                        
                        # 如果没有文本，返回空结果
                        return {
                            'text': '',
                            'confidence': 0.0
                        }
                    else:
                        print("No text recognized")
                        return {
                            'text': '',
                            'confidence': 0.0
                        }
                else:
                    print("No text recognized")
                    return {
                        'text': '',
                        'confidence': 0.0
                    }
            else:
                # 模拟识别结果
                print("Using mock recognition (PaddleOCR not available)")
                return {
                    'text': '示例文本',
                    'confidence': 0.95
                }
        except Exception as e:
            print(f"Error recognizing text: {e}")
            import traceback
            traceback.print_exc()
            return {
                'text': '',
                'confidence': 0.0
            }
