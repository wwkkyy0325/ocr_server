# -*- coding: utf-8 -*-

import os
import traceback
import numpy as np
from PIL import Image
from app.image.preprocessor import Preprocessor
from app.ocr.detector import Detector
from app.ocr.recognizer import Recognizer
from app.ocr.post_processor import PostProcessor
from app.image.cropper import Cropper
from app.image.table_splitter import TableSplitter
from app.ocr.unwarper import Unwarper
from app.core.config_manager import ConfigManager

class OcrEngine:
    def __init__(self, config_manager=None, detector=None, recognizer=None):
        """
        Initialize OCR Engine with necessary components
        """
        self.config_manager = config_manager or ConfigManager()
        if not config_manager:
            self.config_manager.load_config()
            
        self.preprocessor = Preprocessor()
        self.unwarper = Unwarper(self.config_manager)
        self.detector = detector or Detector(self.config_manager)
        self.recognizer = recognizer or Recognizer(self.config_manager) # Kept for compatibility
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
                    padding_size = options.get('padding_size', 
                                             self.config_manager.get_setting('padding_size', 50))
                    image, padding_offset = self.add_padding(image, padding_size)
            
        except Exception as e:
            print(f"Error in preprocessing: {e}")
            # Continue with original image if preprocessing fails
            
        # 2. Table Split & Detection
        text_regions = []
        try:
            use_ai_table = options.get(
                'use_ai_table',
                self.config_manager.get_setting('use_ai_table', False)
            )

            print(
                "DEBUG: OcrEngine.process_image use_ai_table="
                f"{use_ai_table}, config_use_ai_table="
                f"{self.config_manager.get_setting('use_ai_table', False)}"
            )

            if use_ai_table:
                try:
                    from app.ocr.table_recognizer import TableRecognizer
                    if not hasattr(self, 'table_recognizer'):
                        self.table_recognizer = TableRecognizer(self.config_manager)
                    
                    table_model = options.get(
                        'ai_table_model',
                        self.config_manager.get_setting('ai_table_model', 'SLANet')
                    )
                    
                    structure_results = self.table_recognizer.predict(image, model_name=table_model)

                    print(f"DEBUG: AI Table Recognition produced {len(structure_results)} cells")
                    
                    for res in structure_results:
                        bbox = res.get('bbox', [0, 0, 0, 0])
                        x1, y1, x2, y2 = bbox
                        
                        region = {
                            'text': res.get('text', ''),
                            'confidence': res.get('score', 0.9),
                            'coordinates': [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
                            'table_info': {
                                'row': res.get('row', 0),
                                'col': res.get('col', 0),
                                'rowspan': res.get('rowspan', 1),
                                'colspan': res.get('colspan', 1),
                                'cell_box': (x1, y1, x2 - x1, y2 - y1),
                                'is_header': res.get('is_header', False)
                            }
                        }
                        
                        new_coords = []
                        for point in region['coordinates']:
                            new_coords.append([point[0] - padding_offset[0], point[1] - padding_offset[1]])
                        region['coordinates'] = new_coords
                        
                        text_regions.append(region)
                except Exception as e:
                    print(f"Error in AI Table Recognition: {e}")
                    traceback.print_exc()

            use_table_split = options.get(
                'use_table_split',
                self.config_manager.get_setting('use_table_split', False)
            )
            
            split_results = []

            if use_table_split:
                table_split_mode = options.get(
                    'table_split_mode',
                    self.config_manager.get_setting('table_split_mode', 'horizontal')
                )
                try:
                    split_results = self.table_splitter.split(image, table_split_mode)
                except Exception as e:
                    print(f"Error splitting table: {e}")
                    width, height = image.size
                    split_results = [{'image': image, 'box': (0, 0, width, height), 'row': 0, 'col': 0}]
            else:
                width, height = image.size
                split_results = [{'image': image, 'box': (0, 0, width, height), 'row': 0, 'col': 0}]

            # Detect in each split region
            # Fixed indentation for basedpyright
            for split_item in split_results:
                sub_image = split_item['image']
                cell_box = split_item['box']
                cell_x, cell_y = cell_box[0], cell_box[1]
                row_idx = split_item.get('row', 0)
                col_idx = split_item.get('col', 0)
                
                try:
                    sub_regions = self.detector.detect_text_regions(sub_image)
                    
                    # Critical Fix: Check for None return which indicates detection failure (e.g. model missing)
                    if sub_regions is None:
                        raise RuntimeError(
                            f"Detection failed for region (row={row_idx}, col={col_idx}). "
                            "Check OCR engine status."
                        )
                    
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
                            
                        # Only add table_info if we are actually using table features (split or AI)
                        if use_table_split:
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
