# -*- coding: utf-8 -*-

import os
import traceback
import numpy as np
from PIL import Image
from app.image.preprocessor import Preprocessor
from app.ocr.detector import Detector
from app.ocr.recognizer import Recognizer
from app.ocr.unified_engine import UnifiedOCREngine
from app.ocr.post_processor import PostProcessor
from app.image.cropper import Cropper
from app.image.table_splitter import TableSplitter
from app.ocr.unwarper import Unwarper
from app.core.config_manager import ConfigManager

class OcrEngine:
    _instance = None
    _lock = None

    @classmethod
    def get_instance(cls, config_manager=None, detector=None, recognizer=None, preset='mobile'):
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()
            
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    print(f"Creating global OCR engine instance with preset: {preset}")
                    cls._instance = cls(config_manager, detector, recognizer, preset=preset)
        return cls._instance

    def __init__(self, config_manager=None, detector=None, recognizer=None, preset='mobile'):
        """
        Initialize OCR Engine with necessary components
        """
        self.config_manager = config_manager or ConfigManager()
        if not config_manager:
            self.config_manager.load_config()
            
        print(f"OcrEngine initializing with detector={detector is not None}, recognizer={recognizer is not None}")
            
        self.preprocessor = Preprocessor()
        self.unwarper = Unwarper(self.config_manager)
        
        # 初始化统一OCR引擎作为主引擎（使用传入的预设配置）
        self.unified_engine = UnifiedOCREngine(self.config_manager, preset=preset)
        
        # 统一引擎作为主OCR处理器，detector和recognizer仅在需要时按需创建
        # 避免重复加载模型造成资源浪费
        self.detector = detector
        self.recognizer = recognizer
        
        print("Unified OCR Engine initialized as primary OCR processor")
        print(f"Detector instance provided: {detector is not None}")
        print(f"Recognizer instance provided: {recognizer is not None}")
        
        self.post_processor = PostProcessor()
        self.cropper = Cropper()
        self.table_splitter = TableSplitter()

    def add_padding(self, image, padding_size):
        """
        Add white padding around the image.
        
        Args:
            image: PIL Image
            padding_size: int, size of padding in pixels
            
        Returns:
            tuple: (padded_image, (pad_left, pad_top))
        """
        if padding_size <= 0:
            return image, (0, 0)
            
        width, height = image.size
        new_width = width + 2 * padding_size
        new_height = height + 2 * padding_size
        
        # Create new white image
        padded_image = Image.new("RGB", (new_width, new_height), (255, 255, 255))
        
        # Paste original image in center
        padded_image.paste(image, (padding_size, padding_size))
        
        return padded_image, (padding_size, padding_size)

    def process_image(self, image, options=None):
        """
        Process an image: Preprocess -> Table Split -> Detect -> PostProcess
        
        Args:
            image: PIL Image object
            options: Dictionary of processing options (overrides config)
            
        Returns:
            dict: Processing result
        """
        options = options or {}
        
        # 0. Handle Masks (New Step)
        masks = options.get('masks')
        if masks:
            full_text_parts = []
            all_regions = []
            
            width, height = image.size
            
            for i, mask_info in enumerate(masks):
                rect = mask_info.get('rect') # [x1, y1, x2, y2] normalized
                label = mask_info.get('label', 0)
                
                cropped_image = image
                x1, y1 = 0, 0
                
                if rect:
                    # Calculate crop coordinates with expansion
                    try:
                        x1 = int(rect[0] * width)
                        y1 = int(rect[1] * height)
                        x2 = int(rect[2] * width)
                        y2 = int(rect[3] * height)
                        
                        # Expansion logic from ProcessingController
                        expansion_ratio_w = 0.05
                        expansion_ratio_h = 0.02
                        crop_w = x2 - x1
                        crop_h = y2 - y1
                        expand_w = int(crop_w * expansion_ratio_w)
                        expand_h = int(crop_h * expansion_ratio_h)
                        
                        x1 = max(0, x1 - expand_w)
                        y1 = max(0, y1 - expand_h)
                        x2 = min(width, x2 + expand_w)
                        y2 = min(height, y2 + expand_h)
                        
                        # Crop
                        crop_box = (x1, y1, x2, y2)
                        cropped_image = image.crop(crop_box)
                    except Exception as e:
                        print(f"Error cropping mask {i}: {e}")
                        traceback.print_exc()
                        continue
                
                # Recursive call
                # We remove 'masks' to prevent infinite recursion
                # We also inherit other options
                sub_options = options.copy()
                sub_options.pop('masks', None)
                
                sub_result = self.process_image(cropped_image, sub_options)
                
                # Adjust coordinates
                sub_text = sub_result.get('full_text', '')
                sub_regions = sub_result.get('regions', [])
                
                if sub_text:
                    full_text_parts.append(sub_text)
                    
                for region in sub_regions:
                    # Adjust coordinates
                    coords = region.get('coordinates', [])
                    new_coords = []
                    if isinstance(coords, list):
                        for point in coords:
                            if isinstance(point, (list, tuple)) and len(point) >= 2:
                                new_coords.append([point[0] + x1, point[1] + y1])
                    
                    region['coordinates'] = new_coords
                    region['mask_label'] = label
                    all_regions.append(region)

            return {
                'full_text': "\n".join(full_text_parts),
                'regions': all_regions,
                'status': 'success'
            }

        # Initialize padding offset
        padding_offset = (0, 0)
        
        # 1. Preprocess
        try:
            # Check if preprocessing should be skipped (e.g. if already done by caller)
            if options.get('skip_preprocessing', False):
                # Ensure image is PIL Image even if skipped
                if isinstance(image, np.ndarray):
                    image = Image.fromarray(image)
            else:
                # We don't save temp files here
                image = self.preprocessor.comprehensive_preprocess(image, None, "temp")
                
                # Ensure image is PIL Image for subsequent steps (TableSplitter returns PIL, but we need PIL here too for .size)
                if isinstance(image, np.ndarray):
                    image = Image.fromarray(image)

                # 1.1 Unwarp（方向/几何矫正默认启用）
                try:
                    image = self.unwarper.unwarp_image(image)
                except Exception as _:
                    pass
                
                # 1.2 Padding (New Step)
                use_padding = options.get('use_padding', 
                                        self.config_manager.get_setting('use_padding', False))
                if use_padding:
                    # 如果启用了 Padding，记录偏移量，后续需要还原坐标
                    padding_size = options.get('padding_size', 
                                             self.config_manager.get_setting('padding_size', 50))
                    image, padding_offset = self.add_padding(image, padding_size)
                    print(f"DEBUG: Added padding size={padding_size}, offset={padding_offset}")
            
        except Exception as e:
            print(f"Error in preprocessing: {e}")
            # Continue with original image if preprocessing fails

            
        # 2. Table Split & Detection
        text_regions = []
        try:
            # 🔥 关键修复：优先使用 options 中的配置，因为它来自 processing_controller
            # processing_controller 会根据 current_preset 自动推断 use_ai_table
            use_ai_table = options.get('use_ai_table', False)
            
            # 🔥 关键修复：确保 use_table_split 在所有路径下都有定义
            use_table_split = options.get(
                'use_table_split',
                self.config_manager.get_setting('use_table_split', False)
            )
            
            # 调试日志：显示当前使用的配置来源
            print(
                "DEBUG: OcrEngine.process_image use_ai_table="
                f"{use_ai_table} (from options), use_table_split="
                f"{use_table_split}"
            )

            # 🔥 关键修复：AI 表格模式和传统表格拆分模式是互斥的！
            # AI 表格模式由 PP-Structure 完整处理，不应该再执行传统表格拆分
            if use_ai_table:
                print("DEBUG: AI Table mode enabled - skipping traditional table split")
                # AI 表格模式下，整个图像由 PP-Structure 统一处理
                # 在 unified_engine.process_image() 中会根据 preset='ai_table' 调用 PP-Structure
                width, height = image.size
                split_results = [{'image': image, 'box': (0, 0, width, height), 'row': 0, 'col': 0}]
            else:
                # 只有非 AI 表格模式才使用传统表格拆分
                split_results = []

                if use_table_split:
                    table_split_mode = options.get(
                        'table_split_mode',
                        self.config_manager.get_setting('table_split_mode', 'horizontal')
                    )
                    
                    # 🔥 修复：TableSplitter 的方法是 split() 而不是 split_table()
                    split_results = self.table_splitter.split(
                        image, 
                        mode=table_split_mode
                    )
                    print(f"Table splitting resulted in {len(split_results)} regions")
                else:
                    # No table splitting, treat whole image as one region
                    width, height = image.size
                    split_results = [{'image': image, 'box': (0, 0, width, height), 'row': 0, 'col': 0}]

            # Detect in each split region
            # Fixed indentation for basedpyright
            try:
                text_regions = []  # Initialize text_regions
                for split_item in split_results:
                    sub_image = split_item['image']
                    cell_box = split_item['box']
                    cell_x, cell_y = cell_box[0], cell_box[1]
                    row_idx = split_item.get('row', 0)
                    col_idx = split_item.get('col', 0)
                    
                    try:
                        # 优先使用统一OCR引擎（推荐方式，避免重复加载模型）
                        sub_regions = self.unified_engine.process_image(sub_image)
                        print("Using unified OCR engine for detection and recognition (primary method)")
                        
                        # Critical Fix: Check for None return which indicates detection failure (e.g. model missing)
                        if sub_regions is None:
                            raise RuntimeError(
                                f"Detection failed for region (row={row_idx}, col={col_idx}). "
                                "Check OCR engine status."
                            )
                        
                        # 对检测到的区域进行单独识别（如果需要）
                        recognized_regions = []
                        for region in sub_regions:
                            # 这里可以添加额外的识别逻辑
                            recognized_regions.append(region)
                        sub_regions = recognized_regions
                        
                        for region in sub_regions:
                            # Adjust coordinates to original image
                            coords = region.get('coordinates', [])
                            new_coords = []
                            if isinstance(coords, list):
                                for point in coords:
                                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                                        # Adjust for cell offset and padding offset
                                        x = point[0] + cell_x - padding_offset[0]
                                        y = point[1] + cell_y - padding_offset[1]
                                        new_coords.append([x, y])
                            
                            if new_coords:
                                region['coordinates'] = new_coords
                                
                            # 🔥 关键修复：只有传统表格拆分才需要添加 table_info
                            # AI 表格模式下，PP-Structure 会自己处理表格结构信息
                            if use_table_split and not use_ai_table:
                                region['table_info'] = {
                                    'row': row_idx,
                                    'col': col_idx,
                                    'cell_box': cell_box
                                }
                            text_regions.append(region)
                    except Exception as e:
                        print(f"Error detecting in split region: {e}")
                        
            except Exception as e:
                print(f"Error in detection phase: {e}")
                traceback.print_exc()

        except Exception as e:
            print(f"Error in detection phase: {e}")
            traceback.print_exc()

        # 3. Post-process & Format Results
        detailed_results = []
        recognized_texts = []
        
        for region in text_regions:
            try:
                text = region.get('text', '')
                confidence = region.get('confidence', 0.0)
                coordinates = region.get('coordinates', [])
                
                # Ensure JSON serializable
                if hasattr(coordinates, 'tolist'):
                    coordinates = coordinates.tolist()
                
                # Post-process
                corrected_text = self.post_processor.correct_format(text)
                corrected_text = self.post_processor.semantic_correction(corrected_text)
                
                recognized_texts.append(corrected_text)
                
                # 如果有 Padding，需要还原坐标
                if padding_offset != (0, 0):
                    px, py = padding_offset
                    if coordinates:
                        new_coords = []
                        for point in coordinates:
                            if isinstance(point, (list, tuple)) and len(point) >= 2:
                                new_coords.append([point[0] - px, point[1] - py])
                        coordinates = new_coords
                        # print(f"DEBUG: Restored coords from padding offset {padding_offset}")

                result_item = {
                    'text': corrected_text,
                    'confidence': float(confidence),
                    'coordinates': coordinates,
                    'detection_confidence': float(confidence)
                }
                
                # Preserve other keys (like line_index, table_info, etc.)
                for k, v in region.items():
                    if k not in result_item and k != 'coordinates':
                         result_item[k] = v
                    
                detailed_results.append(result_item)
            except Exception as e:
                print(f"Error processing region result: {e}")

        return {
            'full_text': "\n".join(recognized_texts),
            'regions': detailed_results
        }