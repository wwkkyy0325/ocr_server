# -*- coding: utf-8 -*-

"""
文本识别（调用PaddleOCR识别接口）
"""

import os
try:
    import paddleocr
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    PADDLE_OCR_AVAILABLE = False
    print("PaddleOCR not available, using mock implementation")


class Recognizer:
    def _get_model_name_from_dir(self, dir_path):
        """
        Extract model name from inference.yml or directory name
        """
        if not dir_path: return None
        # Try reading inference.yml
        yml_path = os.path.join(dir_path, 'inference.yml')
        if os.path.exists(yml_path):
            try:
                with open(yml_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if 'model_name:' in line:
                            return line.split('model_name:')[1].strip()
            except:
                pass
        # Fallback to directory name
        name = os.path.basename(dir_path)
        if name.endswith('_infer'):
            name = name[:-6]
        return name

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

                # Load det model path (to prevent default model loading/downloading in PaddleOCR pipeline)
                det_model_dir = config_manager.get_setting('det_model_dir') if config_manager else None
                if det_model_dir and os.path.exists(det_model_dir):
                    print(f"Using local detection model: {det_model_dir}")
                    params['det_model_dir'] = det_model_dir
                    
                if cls_model_dir and os.path.exists(cls_model_dir):
                    print(f"Using local classification model: {cls_model_dir}")
                    params['cls_model_dir'] = cls_model_dir
                
                # 禁用 mkldnn 以解决兼容性问题
                # Use environment variable to ensure it's disabled globally for Paddle
                if params.get('device') == 'cpu':
                    os.environ['FLAGS_use_mkldnn'] = '0'
                    os.environ['FLAGS_enable_mkldnn'] = '0'
                    print("Disabled MKLDNN for CPU mode via environment variables")

                # Compatibility for PaddleOCR 3.4.0+ (PaddleX pipeline)
                if PADDLE_OCR_AVAILABLE and hasattr(paddleocr, '__version__'):
                     # Check if we are using new structure (v3)
                     is_v3 = paddleocr.__version__.startswith('3.') or paddleocr.__version__.startswith('4.')
                     
                     if is_v3:
                         print(f"Adapting params for PaddleOCR v{paddleocr.__version__}")
                         # Map keys
                         if 'rec_model_dir' in params:
                             params['text_recognition_model_dir'] = params.pop('rec_model_dir')
                             params['text_recognition_model_name'] = self._get_model_name_from_dir(params['text_recognition_model_dir'])
                             
                         if 'det_model_dir' in params:
                             params['text_detection_model_dir'] = params.pop('det_model_dir')
                             params['text_detection_model_name'] = self._get_model_name_from_dir(params['text_detection_model_dir'])
                             
                         if 'cls_model_dir' in params:
                             params['textline_orientation_model_dir'] = params.pop('cls_model_dir')
                             params['textline_orientation_model_name'] = self._get_model_name_from_dir(params['textline_orientation_model_dir'])
                         
                         if 'use_angle_cls' in params:
                             params['use_textline_orientation'] = params.pop('use_angle_cls')
                             
                         # Remove unsupported
                         params.pop('use_gpu', None)
                         params.pop('show_log', None)
                         params.pop('enable_mkldnn', None)
                         
                         # Explicitly disable document orientation and unwarping to avoid default model download/check
                         params['use_doc_orientation_classify'] = False
                         params['use_doc_unwarping'] = False

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
