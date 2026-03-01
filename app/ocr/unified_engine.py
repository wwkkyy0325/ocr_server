# -*- coding: utf-8 -*-

"""
统一OCR引擎 - 将文本检测和文本识别功能整合为单一引擎
支持server和mobile两种预设配置，避免模型重复加载造成的资源浪费
"""

import os
try:
    import paddleocr
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    PADDLE_OCR_AVAILABLE = False
    print("PaddleOCR not available, using mock implementation")

from app.utils.ocr_utils import sort_ocr_regions


class UnifiedOCREngine:
    """
    统一OCR引擎，整合文本检测和识别功能
    支持预设配置：server（高精度）和mobile（轻量级）
    """
    
    # 预设配置
    PRESETS = {
        'server': {
            'name': 'GPU 高精度模式 (Server Models)',
            'det_model_key': 'PP-OCRv5_server_det',
            'rec_model_key': 'PP-OCRv5_server_rec',
            'description': '适用于GPU环境，高精度但资源消耗较大'
        },
        'mobile': {
            'name': 'CPU 均衡模式 (Mobile Models)', 
            'det_model_key': 'PP-OCRv5_mobile_det',
            'rec_model_key': 'PP-OCRv5_mobile_rec',
            'description': '适用于CPU环境，轻量级且内存友好'
        }
    }
    
    def __init__(self, config_manager=None, preset='mobile'):
        """
        初始化统一OCR引擎
        
        Args:
            config_manager: 配置管理器
            preset: 预设配置 ('server' 或 'mobile')
        """
        print(f"Initializing Unified OCR Engine with preset: {preset}")
        self.config_manager = config_manager
        self.current_preset = preset
        self.ocr_engine = None
        self._initialize_engine()
    
    def _get_model_name_from_dir(self, dir_path):
        """
        从inference.yml或目录名提取模型名称
        """
        if not dir_path: 
            return None
        # 尝试读取inference.yml
        yml_path = os.path.join(dir_path, 'inference.yml')
        if os.path.exists(yml_path):
            try:
                with open(yml_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if 'model_name:' in line:
                            return line.split('model_name:')[1].strip()
            except:
                pass
        # 回退到目录名
        name = os.path.basename(dir_path)
        if name.endswith('_infer'):
            name = name[:-6]
        return name
    
    def _initialize_engine(self):
        """
        根据当前预设初始化OCR引擎
        """
        if not PADDLE_OCR_AVAILABLE:
            print("PaddleOCR not available, using mock implementation")
            return
            
        try:
            preset_config = self.PRESETS[self.current_preset]
            print(f"Loading unified OCR engine with {preset_config['name']}")
            
            # 获取模型路径和配置
            params = self._prepare_params(preset_config)
            
            print(f"Initializing unified PaddleOCR engine with params: {params}")
            
            # 初始化统一的PaddleOCR引擎
            try:
                self.ocr_engine = PaddleOCR(**params)
                print("Unified PaddleOCR engine initialized successfully")
            except Exception as e:
                print(f"Error initializing unified PaddleOCR engine with GPU: {e}")
                if params.get('device') == 'gpu':
                    print("Attempting fallback to CPU mode...")
                    params['device'] = 'cpu'
                    if 'use_gpu' in params:
                        del params['use_gpu']
                    self.ocr_engine = PaddleOCR(**params)
                    print("Unified PaddleOCR engine initialized successfully (Fallback to CPU)")
                else:
                    raise e
                    
        except Exception as e:
            print(f"Error initializing unified OCR engine: {e}")
            import traceback
            traceback.print_exc()
            self.ocr_engine = None
    
    def _prepare_params(self, preset_config):
        """
        准备PaddleOCR参数
        """
        params = {}
        
        # 设备检测
        try:
            import paddle
            is_gpu_available = paddle.is_compiled_with_cuda()
            print(f"PaddlePaddle compiled with CUDA: {is_gpu_available}")
        except Exception:
            is_gpu_available = False
            print("Could not determine if PaddlePaddle is compiled with CUDA, assuming False")

        # 自动检测GPU使用（用户策略：GPU可用则使用，否则使用CPU）
        use_gpu = is_gpu_available
        params['device'] = 'gpu' if use_gpu else 'cpu'
        print(f"PaddleOCR device set to: {params['device']} (Auto-detected)")
        
        # 应用预设配置
        if self.config_manager:
            # 检测相关参数
            limit_side_len = self.config_manager.get_setting('det_limit_side_len')
            if limit_side_len:
                val = int(limit_side_len)
                # CPU模式优化：防止大图像导致OOM/崩溃
                if not use_gpu and val > 960:
                    print(f"Warning: Downgrading det_limit_side_len from {val} to 960 for CPU mode stability")
                    val = 960
                params['det_limit_side_len'] = val
                params['det_limit_type'] = 'max'
                
            det_db_thresh = self.config_manager.get_setting('det_db_thresh')
            if det_db_thresh:
                params['det_db_thresh'] = float(det_db_thresh)
                
            det_db_box_thresh = self.config_manager.get_setting('det_db_box_thresh')
            if det_db_box_thresh:
                params['det_db_box_thresh'] = float(det_db_box_thresh)
                
            det_db_unclip_ratio = self.config_manager.get_setting('det_db_unclip_ratio')
            if det_db_unclip_ratio:
                params['det_db_unclip_ratio'] = float(det_db_unclip_ratio)
            
            # 分类相关参数
            use_angle_cls = self.config_manager.get_setting('use_angle_cls')
            if use_angle_cls is not None:
                params['use_angle_cls'] = use_angle_cls
                
            cls_model_dir = self.config_manager.get_setting('cls_model_dir')
            if cls_model_dir and os.path.exists(cls_model_dir):
                print(f"Using local classification model: {cls_model_dir}")
                params['cls_model_dir'] = cls_model_dir
            
            # 确保角度分类启用（如果有CLS模型）
            if cls_model_dir:
                params['use_angle_cls'] = True
            
            # 语言设置（对默认模型必需）
            params['lang'] = 'ch'
            
            # 精度设置
            precision = self.config_manager.get_setting('precision')
            if precision:
                params['precision'] = precision
            
            # 获取模型目录 - 关键修复点
            det_model_dir = self.config_manager.get_setting('det_model_dir')
            rec_model_dir = self.config_manager.get_setting('rec_model_dir')
            
            if det_model_dir and os.path.exists(det_model_dir):
                print(f"Using local detection model: {det_model_dir}")
                params['det_model_dir'] = det_model_dir
                
            if rec_model_dir and os.path.exists(rec_model_dir):
                print(f"Using local recognition model: {rec_model_dir}")
                params['rec_model_dir'] = rec_model_dir
        
        # 应用预设的模型键
        if self.config_manager:
            print(f"Setting det_model_key = {preset_config['det_model_key']}")
            print(f"Setting rec_model_key = {preset_config['rec_model_key']}")
            self.config_manager.set_setting('det_model_key', preset_config['det_model_key'])
            self.config_manager.set_setting('rec_model_key', preset_config['rec_model_key'])
            
            # 确保模型目录也同步更新
            det_model_dir = self.config_manager.model_manager.get_model_dir('det', preset_config['det_model_key'])
            rec_model_dir = self.config_manager.model_manager.get_model_dir('rec', preset_config['rec_model_key'])
            
            if det_model_dir:
                print(f"Det model directory: {det_model_dir}")
                self.config_manager.set_setting('det_model_dir', det_model_dir)
                params['det_model_dir'] = det_model_dir
                # 同时设置对应的模型名称
                params['det_model_name'] = preset_config['det_model_key']
                
            if rec_model_dir:
                print(f"Rec model directory: {rec_model_dir}")
                self.config_manager.set_setting('rec_model_dir', rec_model_dir)
                params['rec_model_dir'] = rec_model_dir
                # 同时设置对应的模型名称
                params['rec_model_name'] = preset_config['rec_model_key']
        
        # 兼容性处理（PaddleOCR 3.4.0+）
        if PADDLE_OCR_AVAILABLE and hasattr(paddleocr, '__version__'):
            is_v3 = paddleocr.__version__.startswith('3.') or paddleocr.__version__.startswith('4.')
            if is_v3:
                print(f"Adapting params for PaddleOCR v{paddleocr.__version__}")
                # 移除不支持的参数
                params.pop('use_gpu', None)
                params.pop('show_log', None)
                params.pop('enable_mkldnn', None)
                
                # 显式禁用文档方向分类和去扭曲以避免默认模型下载/检查
                params['use_doc_orientation_classify'] = False
                params['use_doc_unwarping'] = False
                
                # 映射模型键
                if 'use_angle_cls' in params:
                    params['use_textline_orientation'] = params.pop('use_angle_cls')
                
                # 映射模型目录和名称（PaddleX格式）
                if 'det_model_dir' in params:
                    params['text_detection_model_dir'] = params.pop('det_model_dir')
                    if 'det_model_name' in params:
                        params['text_detection_model_name'] = params.pop('det_model_name')
                    else:
                        params['text_detection_model_name'] = preset_config['det_model_key']
                        
                if 'rec_model_dir' in params:
                    params['text_recognition_model_dir'] = params.pop('rec_model_dir')
                    if 'rec_model_name' in params:
                        params['text_recognition_model_name'] = params.pop('rec_model_name')
                    else:
                        params['text_recognition_model_name'] = preset_config['rec_model_key']
                        
                if 'cls_model_dir' in params:
                    cls_dir = params.pop('cls_model_dir')
                    # 当前只支持 0/180 的文本行方向管线，如果用户选的是 doc_ori 四分类模型，这里忽略自定义模型，使用内置的两方向模型
                    cls_key = self.config_manager.get_setting('cls_model_key') if self.config_manager else None
                    if cls_key and 'doc_ori' in str(cls_key):
                        print(f"Warning: Detected doc orientation model '{cls_key}' for Unified Engine; using built-in 2-class textline orientation instead.")
                    else:
                        params['textline_orientation_model_dir'] = cls_dir
                        params['textline_orientation_model_name'] = self._get_model_name_from_dir(cls_dir)
        
        return params
    
    def switch_preset(self, preset):
        """
        切换预设配置
        
        Args:
            preset: 预设名称 ('server' 或 'mobile')
        """
        if preset not in self.PRESETS:
            raise ValueError(f"Invalid preset: {preset}. Available presets: {list(self.PRESETS.keys())}")
        
        if preset == self.current_preset:
            print(f"Already using preset: {preset}")
            return
            
        print(f"Switching from {self.current_preset} to {preset} preset")
        self.current_preset = preset
        self._initialize_engine()
    
    def get_current_preset(self):
        """
        获取当前预设配置
        
        Returns:
            str: 当前预设名称
        """
        return self.current_preset
    
    def get_preset_info(self):
        """
        获取当前预设的详细信息
        
        Returns:
            dict: 预设信息
        """
        return self.PRESETS[self.current_preset]
    
    def process_image(self, image):
        """
        处理图像：检测并识别文本
        
        Args:
            image: 输入图像（PIL Image或numpy array）
            
        Returns:
            dict: 处理结果，包含文本区域和识别文本
        """
        print("Processing image with unified OCR engine")
        try:
            if PADDLE_OCR_AVAILABLE and self.ocr_engine:
                # 转换PIL图像为numpy数组（如果需要）
                if hasattr(image, 'convert'):
                    import numpy as np
                    image = np.array(image.convert('RGB'))
                    print(f"Converted image to numpy array, shape: {image.shape}")
                
                print("Starting unified PaddleOCR prediction...")
                # 使用统一的OCR引擎进行检测和识别
                if hasattr(self.ocr_engine, 'ocr'):
                    # 标准PaddleOCR用法
                    result = self.ocr_engine.ocr(image)
                    print("Unified PaddleOCR prediction completed.")
                    
                    # 处理标准PaddleOCR输出格式
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
                        print(f"Processed {len(regions)} text regions with unified engine")
                        return sort_ocr_regions(regions)
                
                # 回退到predict方法（PaddleX格式）
                result = self.ocr_engine.predict(image)
                print(f"Detection result: {result}")
                
                if result and result[0]:
                    # 检查res属性或直接检查result[0]
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
                    
                    print(f"Processed {len(regions)} text regions with unified engine")
                    return sort_ocr_regions(regions)
                else:
                    print("No text regions detected")
                    return []
            else:
                # 模拟结果
                print("Using mock recognition (PaddleOCR not available)")
                return [{
                    'text': '示例文本',
                    'confidence': 0.95,
                    'coordinates': [[0, 0], [100, 0], [100, 30], [0, 30]]
                }]
        except Exception as e:
            print(f"Error processing image with unified OCR engine: {e}")
            import traceback
            traceback.print_exc()
            return []
