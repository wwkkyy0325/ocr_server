# -*- coding: utf-8 -*-
import os
import json
import time
import traceback
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread

from app.core.workers import ProcessingWorker
from app.core.process_manager import ProcessManager
from app.core.record_manager import RecordManager
from app.core.result_manager import ResultManager
from app.core.ocr_subprocess import get_ocr_subprocess_manager
from app.ocr.engine import OcrEngine
from app.utils.file_utils import FileUtils

class ProcessingController(QObject):
    """
    Controller for handling OCR processing tasks (Single Image, Batch Files, Folders).
    Moves logic out of MainWindow.
    """
    # Signals to update UI
    update_status_signal = pyqtSignal(str, str)  # message, status_type
    file_processed_signal = pyqtSignal(str, str)  # filename, full_text
    processing_finished_signal = pyqtSignal(float)  # total_time
    progress_update_signal = pyqtSignal(int, int) # current, total

    def __init__(self, config_manager, file_utils, mask_manager, 
                 detector, recognizer, post_processor, cropper, 
                 performance_monitor, result_manager, output_dir):
        super().__init__()
        self.config_manager = config_manager
        self.file_utils = file_utils
        self.mask_manager = mask_manager
        
        # OCR Components
        self.detector = detector
        self.recognizer = recognizer
        self.post_processor = post_processor
        self.cropper = cropper
        
        self.performance_monitor = performance_monitor
        self.result_manager = result_manager
        self.output_dir = output_dir
        
        self._stop_flag = False
        self.processing_thread = None
        self.ocr_engine = None # Lazy init

    def stop(self):
        """Stop current processing"""
        self._stop_flag = True
        self.update_status_signal.emit("正在停止...", "warning")

    def start_processing(self, files, force_reprocess=False, default_mask_data=None, use_global_selected_mask=True, current_selected_mask=None):
        """
        Start processing a list of files or folders in a background thread.
        """
        self._stop_flag = False
        
        # Create and start worker thread
        self.processing_thread = ProcessingWorker(
            self._process_files_worker,
            files=files,
            force_reprocess=force_reprocess,
            default_mask_data=default_mask_data,
            use_global_selected_mask=use_global_selected_mask,
            current_selected_mask=current_selected_mask
        )
        self.processing_thread.finished_signal.connect(self._on_worker_finished)
        self.processing_thread.error_signal.connect(self._on_worker_error)
        self.processing_thread.start()

    def _on_worker_finished(self):
        pass # Signal already emitted by worker logic if needed, or we can emit here

    def _on_worker_error(self, error_msg):
        self.update_status_signal.emit(f"处理出错: {error_msg}", "error")

    def _process_files_worker(self, files, force_reprocess, default_mask_data, use_global_selected_mask, current_selected_mask):
        """
        Worker function running in separate thread.
        Unified entry point for files and folders.
        """
        start_time = time.perf_counter()
        
        # 1. Identify all files to process
        all_files = []
        for path in files:
            if os.path.isdir(path):
                # It's a folder
                image_files = self.file_utils.get_image_files(path)
                all_files.extend(image_files)
            elif os.path.isfile(path):
                all_files.append(path)
        
        total_files = len(all_files)
        if total_files == 0:
            self.update_status_signal.emit("未找到可处理的图像文件", "warning")
            self.processing_finished_signal.emit(0)
            return

        self.update_status_signal.emit(f"开始处理 {total_files} 个文件...", "working")
        
        # 2. Process Loop
        for i, image_path in enumerate(all_files):
            if self._stop_flag:
                break
                
            self.progress_update_signal.emit(i + 1, total_files)
            self.update_status_signal.emit(f"正在处理 ({i+1}/{total_files}): {os.path.basename(image_path)}", "working")
            
            try:
                self._process_single_file(
                    image_path, 
                    force_reprocess, 
                    default_mask_data, 
                    use_global_selected_mask, 
                    current_selected_mask
                )
            except Exception as e:
                print(f"Error processing file {image_path}: {e}")
                traceback.print_exc()
                self.update_status_signal.emit(f"处理失败: {os.path.basename(image_path)}", "error")

        total_time = time.perf_counter() - start_time
        self.processing_finished_signal.emit(total_time)
        self.update_status_signal.emit("处理完成", "success")

    def _process_single_file(self, image_path, force_reprocess, default_mask_data, use_global_selected_mask, current_selected_mask):
        """
        Process a single file (Image or PDF).
        Handles caching, PDF splitting, and delegation to OCR engine.
        """
        filename = os.path.basename(image_path)
        current_file_dir = os.path.dirname(image_path)
        parent_dir_name = os.path.basename(current_file_dir)
        current_output_dir = os.path.join(self.output_dir, parent_dir_name)
        
        record_mgr = RecordManager.get_instance()
        is_pdf = image_path.lower().endswith('.pdf')
        
        # Check Cache (Skip if processed)
        # Note: For PDF, we check if it's recorded, but we might want to check individual pages.
        # Simplified: if PDF is recorded, we skip it.
        
        # Construct expected JSON output path for checking
        # For PDF, we don't have a single JSON usually, but let's assume standard naming
        safe_filename = filename.replace(':', '_')
        json_output_file = os.path.join(current_output_dir, "json", f"{os.path.splitext(safe_filename)[0]}.json")
        
        is_processed = False
        if not force_reprocess and record_mgr.is_recorded(image_path):
             if is_pdf or os.path.exists(json_output_file):
                 is_processed = True
        
        if is_processed:
            print(f"Skipping processed file (cache): {image_path}")
            # Load result to update UI
            if not is_pdf and os.path.exists(json_output_file):
                try:
                    with open(json_output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.file_processed_signal.emit(filename, data.get('full_text', ''))
                        self.result_manager.store_result(image_path, data.get('full_text', ''))
                except:
                    pass
            return

        # Prepare for processing
        if is_pdf:
            self._process_pdf(image_path, current_output_dir, default_mask_data, use_global_selected_mask, current_selected_mask)
        else:
            self._process_image(image_path, current_output_dir, default_mask_data, use_global_selected_mask, current_selected_mask)
            
        # Mark as recorded
        record_mgr.add_record(image_path, output_path=json_output_file)

    def _process_pdf(self, image_path, output_dir, default_mask_data, use_global_selected_mask, current_selected_mask):
        images = self.file_utils.read_pdf_images(image_path)
        if not images:
            return

        filename = os.path.basename(image_path)
        pdf_full_texts = []
        
        for page_idx, image in enumerate(images):
            if self._stop_flag:
                break
                
            page_base_name = f"{os.path.splitext(filename)[0]}_page_{page_idx+1}"
            
            full_text, _ = self._process_image_data(
                image, 
                image_path, 
                mask_lookup_name=filename, 
                result_base_name=page_base_name,
                output_dir=output_dir,
                default_mask_data=default_mask_data,
                use_global_selected_mask=use_global_selected_mask,
                current_selected_mask=current_selected_mask
            )
            
            if full_text:
                pdf_full_texts.append(f"--- Page {page_idx+1} ---\n{full_text}")

        if pdf_full_texts:
            combined_text = "\n\n".join(pdf_full_texts)
            self.file_processed_signal.emit(filename, combined_text)
            self.result_manager.store_result(image_path, combined_text)

    def _process_image(self, image_path, output_dir, default_mask_data, use_global_selected_mask, current_selected_mask):
        original_image = self.file_utils.read_image(image_path)
        if original_image is None:
            return

        filename = os.path.basename(image_path)
        result_base_name = os.path.splitext(filename)[0]
        
        full_text, _ = self._process_image_data(
            original_image, 
            image_path, 
            mask_lookup_name=filename, 
            result_base_name=result_base_name,
            output_dir=output_dir,
            default_mask_data=default_mask_data,
            use_global_selected_mask=use_global_selected_mask,
            current_selected_mask=current_selected_mask
        )
        
        if full_text is not None:
            self.file_processed_signal.emit(filename, full_text)
            self.result_manager.store_result(image_path, full_text)

    def _process_image_data(self, image, image_path, mask_lookup_name, result_base_name, output_dir, default_mask_data, use_global_selected_mask, current_selected_mask):
        """
        Core logic to process an image object (PIL).
        Determines masks, crops, calls OCR, and saves results.
        """
        # 1. Determine Masks
        masks_to_process = self._determine_masks(
            mask_lookup_name, default_mask_data, use_global_selected_mask, current_selected_mask, image_path
        )
        
        file_recognized_texts = []
        file_detailed_results = []
        file_processing_failed = False
        
        # 2. Iterate Masks
        for mask_info in masks_to_process:
            if self._stop_flag:
                break
                
            rect = mask_info.get('rect')
            
            # Crop Image
            cropped_image, offset_x, offset_y = self._crop_image_with_expansion(image, rect)
            
            # 3. Perform OCR
            # We prefer Subprocess Mode for stability if configured, but logic in MainWindow was mixed.
            # Here we unify: Use Subprocess if configured, else Local.
            
            try:
                use_subprocess = self.config_manager.get_setting('use_ocr_subprocess', True)
                
                process_options = {
                    'skip_preprocessing': True,
                    'ai_table_model': self.config_manager.get_setting('ai_table_model', 'SLANet'),
                    'use_ai_table': self.config_manager.get_setting('use_ai_table', False)
                }
                
                text_regions = None
                
                if use_subprocess:
                    subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
                    if not subprocess_manager.is_running():
                         current_preset = self.config_manager.get_setting('current_ocr_preset', 'mobile')
                         subprocess_manager.start_process(current_preset)
                    
                    result = subprocess_manager.process_image(cropped_image, process_options)
                    text_regions = result.get('regions', [])
                else:
                    # Local Mode
                    if self.ocr_engine is None:
                        self.ocr_engine = OcrEngine(self.config_manager, detector=self.detector, recognizer=self.recognizer)
                    
                    result = self.ocr_engine.process_image(cropped_image, process_options)
                    text_regions = result.get('regions', [])

                if text_regions is None:
                    raise Exception("OCR returned None regions")
                
                # 4. Process Results (Adjust Coordinates)
                part_texts = []
                current_line_texts = []
                current_line_idx = -1
                
                for region in text_regions:
                    text = region.get('text', '')
                    confidence = region.get('confidence', 0.0)
                    line_idx = region.get('line_index', -1)
                    coordinates = region.get('coordinates', [])
                    
                    # Restore coordinates
                    if hasattr(coordinates, 'tolist'):
                        coordinates = coordinates.tolist()
                    
                    if coordinates and (offset_x != 0 or offset_y != 0):
                        new_coords = []
                        for point in coordinates:
                            if isinstance(point, (list, tuple)) and len(point) >= 2:
                                new_coords.append([point[0] + offset_x, point[1] + offset_y])
                        coordinates = new_coords
                        
                    # Line grouping
                    if line_idx != -1:
                        if current_line_idx != -1 and line_idx != current_line_idx:
                            if current_line_texts:
                                part_texts.append(" ".join(current_line_texts))
                                current_line_texts = []
                        current_line_idx = line_idx
                    
                    current_line_texts.append(text)
                    
                    res_item = {
                        'text': text,
                        'confidence': confidence,
                        'coordinates': coordinates,
                        'detection_confidence': confidence,
                        'mask_label': mask_info.get('label', 0),
                        'line_index': line_idx
                    }
                    if 'table_info' in region:
                        res_item['table_info'] = region['table_info']
                        
                    file_detailed_results.append(res_item)
                
                if current_line_texts:
                    part_texts.append(" ".join(current_line_texts))
                
                if part_texts:
                    file_recognized_texts.append("\n".join(part_texts))
                    
            except Exception as e:
                print(f"Error in OCR processing for {image_path}: {e}")
                traceback.print_exc()
                file_processing_failed = True
                break

        if file_processing_failed:
            return None, None
            
        full_text = "\n".join(file_recognized_texts)
        
        # 5. Save Results
        self._save_results(result_base_name, output_dir, image_path, full_text, file_detailed_results)
        
        return full_text, file_detailed_results

    def _determine_masks(self, mask_lookup_name, default_mask_data, use_global_selected_mask, current_selected_mask, image_path=None):
        masks_to_process = []
        try:
            mask_data = None
            
            # 1. Check direct binding (file specific)
            bound_mask = self.mask_manager.get_bound_mask(mask_lookup_name)
            if bound_mask:
                mask_data = self.mask_manager.get_mask(bound_mask)
            
            # 2. Check folder binding (if image_path provided)
            if not mask_data and image_path and hasattr(self, 'folder_mask_map') and self.folder_mask_map:
                folder = os.path.dirname(image_path)
                # Check exact folder match
                if folder in self.folder_mask_map:
                    mask_name = self.folder_mask_map[folder]
                    mask_data = self.mask_manager.get_mask(mask_name)
                # Could also check parent folders if needed, but sticking to flat map for now
            
            # 3. Default or Global
            if not mask_data:
                if default_mask_data is not None:
                    mask_data = default_mask_data
                elif use_global_selected_mask and current_selected_mask:
                    mask_data = current_selected_mask
            
            if mask_data:
                if isinstance(mask_data, list):
                    if len(mask_data) > 0 and isinstance(mask_data[0], (int, float)):
                         masks_to_process = [{'rect': mask_data, 'label': 1}]
                    else:
                        masks_to_process = mask_data
                        # Sort
                        masks_to_process.sort(
                            key=lambda x: (
                                x.get('rect', [0, 0, 0, 0])[1] if x.get('rect') else 0,
                                x.get('rect', [0, 0, 0, 0])[0] if x.get('rect') else 0
                            )
                        )
        except Exception as e:
            print(f"Error determining masks: {e}")
            
        if not masks_to_process:
            masks_to_process = [{'rect': None, 'label': 0}]
            
        return masks_to_process

    def _crop_image_with_expansion(self, image, rect):
        """Crop image with expansion, returning cropped image and offsets."""
        if not rect or len(rect) != 4:
            return image, 0, 0
            
        try:
            w, h = image.size if hasattr(image, 'size') else (None, None)
            if w and h:
                x1 = int(rect[0] * w)
                y1 = int(rect[1] * h)
                x2 = int(rect[2] * w)
                y2 = int(rect[3] * h)
                
                expansion_ratio_w = 0.05
                expansion_ratio_h = 0.02
                
                crop_w = x2 - x1
                crop_h = y2 - y1
                
                expand_w = int(crop_w * expansion_ratio_w)
                expand_h = int(crop_h * expansion_ratio_h)
                
                x1 = max(0, x1 - expand_w)
                y1 = max(0, y1 - expand_h)
                x2 = min(w, x2 + expand_w)
                y2 = min(h, y2 + expand_h)
                
                return self.cropper.crop_text_region(image, [x1, y1, x2, y2]), x1, y1
        except Exception as e:
            print(f"Crop failed: {e}")
            
        return image, 0, 0

    def set_folder_mask_map(self, folder_mask_map):
        """Set the folder mask map for batch processing."""
        self.folder_mask_map = folder_mask_map

    def _save_results(self, result_base_name, output_dir, image_path, full_text, regions):
        txt_output_dir = os.path.join(output_dir, "txt")
        json_output_dir = os.path.join(output_dir, "json")
        os.makedirs(txt_output_dir, exist_ok=True)
        os.makedirs(json_output_dir, exist_ok=True)
        
        # Save TXT
        output_file = os.path.join(txt_output_dir, f"{result_base_name}_result.txt")
        try:
            self.file_utils.write_text_file(output_file, full_text)
        except Exception as e:
            print(f"Failed to write TXT: {e}")
            
        # Save JSON
        json_output_file = os.path.join(json_output_dir, f"{result_base_name}.json")
        try:
            json_result = {
                'image_path': image_path,
                'filename': result_base_name,
                'timestamp': datetime.now().isoformat(),
                'full_text': full_text,
                'regions': regions,
                'status': 'success'
            }
            self.file_utils.write_json_file(json_output_file, json_result)
        except Exception as e:
            print(f"Failed to write JSON: {e}")


