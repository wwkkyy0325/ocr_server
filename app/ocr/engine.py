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
from app.core.config_manager import ConfigManager

class OcrEngine:
    def __init__(self, config_manager=None):
        """
        Initialize OCR Engine with necessary components
        """
        self.config_manager = config_manager or ConfigManager()
        if not config_manager:
            self.config_manager.load_config()
            
        self.preprocessor = Preprocessor()
        self.unwarper = Unwarper(self.config_manager)
        self.detector = Detector(self.config_manager)
        self.recognizer = Recognizer(self.config_manager) # Kept for compatibility, though Detector does most work
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
            # We don't save temp files here
            image = self.preprocessor.comprehensive_preprocess(image, None, "temp")
            
            # Ensure image is PIL Image for subsequent steps (TableSplitter returns PIL, but we need PIL here too for .size)
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)

            # 1.1 Unwarp (if enabled)
            use_unwarp = self.config_manager.get_setting('use_unwarp_model', False)
            if use_unwarp:
                 image = self.unwarper.unwarp_image(image)
            
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
            # Check options first, then config
            use_table_split = options.get('use_table_split', 
                                        self.config_manager.get_setting('use_table_split', False))
            
            split_results = []
            if use_table_split:
                table_split_mode = options.get('table_split_mode', 
                                             self.config_manager.get_setting('table_split_mode', 'horizontal'))
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
                        raise RuntimeError(f"Detection failed for region (row={row_idx}, col={col_idx}). Check OCR engine status.")
                    
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
                
                if 'table_info' in region:
                    result_item['table_info'] = region['table_info']
                    
                detailed_results.append(result_item)
            except Exception as e:
                print(f"Error processing region result: {e}")

        return {
            'full_text': "\n".join(recognized_texts),
            'regions': detailed_results
        }
