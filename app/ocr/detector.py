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

    def _sort_regions(self, regions):
        """
        Sort text regions from top to bottom, left to right.
        Uses a row clustering approach to handle slight misalignments.
        """
        if not regions:
            return []

        # Helper to get center y of a region
        def get_center_y(region):
            poly = region.get('coordinates', [])
            # Fix: Use len() check to avoid numpy array truth value ambiguity
            if poly is None or len(poly) == 0:
                return 0
            ys = [p[1] for p in poly]
            return sum(ys) / len(ys)

        # First, sort by Y coordinate of the center
        regions.sort(key=get_center_y)

        # Group into lines
        lines = []
        current_line = []
        last_y = -1
        
        # Threshold for line grouping (e.g., 10 pixels or relative to height)
        # Using a dynamic threshold based on average box height would be better,
        # but a fixed reasonable threshold often works for standard documents.
        # Let's try to estimate box height.
        avg_height = 20
        if regions:
            heights = []
            for r in regions:
                poly = r.get('coordinates', [])
                # Fix: Use len() check to avoid numpy array truth value ambiguity
                if poly is not None and len(poly) > 0:
                    ys = [p[1] for p in poly]
                    heights.append(max(ys) - min(ys))
            if heights:
                avg_height = sum(heights) / len(heights)
        
        y_threshold = avg_height * 0.5  # Half of average height as threshold

        for region in regions:
            cy = get_center_y(region)
            if last_y == -1 or abs(cy - last_y) <= y_threshold:
                current_line.append(region)
                # Update last_y to average of current line to keep it stable
                # or just keep the first one's Y. 
                # Updating it might cause drift. Let's stick to the first one for the group
                # or better: don't update last_y, but use the first element of the line as reference.
                if last_y == -1:
                    last_y = cy
            else:
                lines.append(current_line)
                current_line = [region]
                last_y = cy
        
        if current_line:
            lines.append(current_line)

        # Sort each line by X coordinate
        sorted_regions = []
        
        def get_min_x(r):
            poly = r.get('coordinates', [])
            # Fix: Use len() check to avoid numpy array truth value ambiguity
            if poly is not None and len(poly) > 0:
                return min([p[0] for p in poly])
            return 0
            
        for line in lines:
            # Sort by min X (left edge)
            line.sort(key=get_min_x)
            sorted_regions.extend(line)

        return sorted_regions

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
                    return self._sort_regions(regions)
                else:
                    print("No text regions detected (result is empty or invalid)")
                    return []
            else:
                # 模拟检测结果
                print("Using mock detection (PaddleOCR not available)")
                # 返回一些模拟的文本区域坐标
                return [
                    {
                        'coordinates': [[10, 10], [100, 10], [100, 30], [10, 30]],  # 简单的矩形区域
                        'confidence': 0.9
                    },
                    {
                        'coordinates': [[10, 50], [150, 50], [150, 70], [10, 70]],
                        'confidence': 0.85
                    }
                ]
        except Exception as e:
            print(f"Error detecting text regions: {e}")
            import traceback
            traceback.print_exc()
            return []
