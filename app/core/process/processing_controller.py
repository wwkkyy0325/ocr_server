# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：统一调度单图/批量/PDF 的 OCR 处理工作流（线程后台执行），负责子进程调用与结果保存
# - 核心实现：组织 _process_files_worker/_process_image/_process_pdf 等步骤，适配表格/文本模式并序列化结果为 MessagePack
# - 关联关系：与 OCRPipeline、ResultManager、FileUtils 协同工作，通过信号与 UI 同步进度
import os
import time
import traceback
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from app.log.log_bus import get_logger
from app.infrastructure.threading.workers import ProcessingWorker
from app.infrastructure.message_pack_serializer import MessagePackSerializer
# 🔥 引入 OCRPipeline
from app.core.process.pipeline import OCRPipeline
from app.infrastructure.error_handler import handle_errors, ErrorCode


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
    structured_result_ready_signal = pyqtSignal(object)  # detailed_results (list of dicts)
    processed_result_ready_signal = pyqtSignal(dict)  # complete_result_data

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessingController")
    def __init__(self, config_manager, file_utils,
                 performance_monitor, result_manager, output_dir):
        super().__init__()
        self.config_manager = config_manager
        self.file_utils = file_utils
        
        self.performance_monitor = performance_monitor
        self.result_manager = result_manager
        self.output_dir = output_dir
        
        self._stop_flag = False
        self.processing_thread = None
        # 🔥 使用 OCRPipeline 替代直接的 OCR 引擎
        self.ocr_pipeline = OCRPipeline(config_manager)
        
        # 🔥 性能优化：内存缓存索引 + MessagePack 二进制索引表
        # 格式：{msgpack_path: metadata_dict} 快速查找已处理的文件
        self._processed_cache_index = {}
        
        # 📋 索引表文件路径（MessagePack 二进制格式，高性能）
        self._index_file_path = os.path.join(output_dir, "msgpack_index.msgpack")
        
        # 📖 启动时加载索引表到内存
        self._load_index_table()

    def stop(self):
        """Stop current processing"""
        logger = get_logger()
        self._stop_flag = True
        self.update_status_signal.emit("正在停止...", "warning")  # type: ignore[attr-defined]
        
        # 💾 停止时立即保存索引表到磁盘
        self._save_index_table()
        logger.debug("processing_controller", "stopping", "Processing controller stopping")
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ProcessingController")
    def _maybe_save_index_table(self, force=False, interval=10):
        """
        💾 定期保存索引表（避免频繁 IO）
        
        Args:
            force: 是否强制保存
            interval: 每处理多少个文件保存一次（默认 10）
        """
        if not hasattr(self, '_last_save_count'):
            self._last_save_count = 0
        
        current_count = len(self._processed_cache_index)
        
        # 强制保存或达到间隔阈值时保存
        if force or (current_count - self._last_save_count >= interval):
            self._save_index_table()
            self._last_save_count = current_count
            
            logger = get_logger()
            logger.debug("processing_controller", "index_auto_saved", 
                        f"自动保存索引表（当前 {current_count} 个文件）")
    
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="ProcessingController")
    def _load_index_table(self):
        """
        📖 从 MessagePack 文件加载索引表到内存
        启动时调用一次，避免程序重启后重新扫描所有文件
        
        使用 MessagePack 而非 JSON 的原因：
        - 读取速度快 3-5 倍（二进制格式）
        - 文件体积小 30-50%
        - 与项目现有 MessagePack 体系完美兼容
        """
        try:
            if os.path.exists(self._index_file_path):
                data = MessagePackSerializer.load_from_file(self._index_file_path)
                self._processed_cache_index = data.get('files', {})
                logger = get_logger()
                logger.info("processing_controller", "index_loaded", 
                           f"已加载索引表：{len(self._processed_cache_index)} 个文件")
            else:
                self._processed_cache_index = {}
                logger = get_logger()
                logger.debug("processing_controller", "no_index_found", 
                            "索引表不存在，将使用空索引启动")
        except Exception as e:
            logger = get_logger()
            logger.error("processing_controller", "load_index_failed", 
                        f"加载索引表失败：{e}")
            self._processed_cache_index = {}
    
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="ProcessingController")
    def _save_index_table(self):
        """
        💾 保存内存索引到 MessagePack 文件
        在程序退出或定期调用，持久化缓存状态
        
        使用 MessagePack 而非 JSON 的原因：
        - 写入速度快 2-3 倍（二进制格式）
        - 文件体积小 30-50%，节省磁盘空间
        - 自动处理 datetime 等复杂类型
        """
        try:
            index_dir = os.path.dirname(self._index_file_path)
            os.makedirs(index_dir, exist_ok=True)
            
            data = {
                'version': '1.0',
                'last_updated': datetime.now(),
                'output_dir': self.output_dir,
                'files': self._processed_cache_index
            }
            
            MessagePackSerializer.save_to_file(data, self._index_file_path)
            
            logger = get_logger()
            logger.info("processing_controller", "index_saved", 
                       f"已保存索引表：{len(self._processed_cache_index)} 个文件")
        except Exception as e:
            logger = get_logger()
            logger.error("processing_controller", "save_index_failed", 
                        f"保存索引表失败：{e}")

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessingController")
    def start_processing(self, files, force_reprocess=False):
        """
        Start processing a list of files or folders in a background thread.
        """
        logger = get_logger()
        self._stop_flag = False
        
        # Create and start worker thread
        self.processing_thread = ProcessingWorker(
            self._process_files_worker,
            files=files,
            force_reprocess=force_reprocess
        )
        self.processing_thread.finished_signal.connect(self._on_worker_finished)
        self.processing_thread.error_signal.connect(self._on_worker_error)
        self.processing_thread.start()
        
        logger.debug("processing_controller", "processing_started", f"Starting processing {len(files)} files")

    def _on_worker_finished(self):
        pass # Signal already emitted by worker logic if needed, or we can emit here
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ProcessingController")
    def clear_cache_index(self):
        """
        🗑️ 清空所有缓存索引（内存 + 磁盘）
        用于设置页面的"清除所有缓存"功能
        """
        logger = get_logger()
        self._processed_cache_index.clear()
        
        # 删除索引文件
        try:
            if os.path.exists(self._index_file_path):
                os.remove(self._index_file_path)
                logger.info("processing_controller", "cache_cleared", 
                           "已清空所有缓存索引")
        except Exception as e:
            logger.error("processing_controller", "clear_cache_failed", 
                        f"删除索引文件失败：{e}")

    def _on_worker_error(self, error_msg):
        self.update_status_signal.emit(f"处理出错：{error_msg}", "error")  # type: ignore[attr-defined]

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessingController")
    def _process_files_worker(self, files, force_reprocess):
        """
        Worker function running in separate thread.
        Unified entry point for files and folders.
        """
        logger = get_logger()
        start_time = time.perf_counter()
        
        logger.debug("processing_controller", "worker_started", 
                    f"Processing worker started with {len(files)} paths")
        
        # 1. Identify all files to process
        all_files = []
        for path in files:
            if os.path.isdir(path):
                # It's a folder
                image_files = self.file_utils.get_image_files(path)
                logger.debug("processing_controller", "folder_scanned", 
                           f"Folder {path}: found {len(image_files)} images")
                all_files.extend(image_files)
            elif os.path.isfile(path):
                logger.debug("processing_controller", "file_added", f"Direct file: {path}")
                all_files.append(path)
        
        total_files = len(all_files)
        logger.info("processing_controller", "files_identified", 
                   f"Total files identified for processing: {total_files}")
        
        if total_files == 0:
            logger.warning("processing_controller", "no_files_found", "未找到可处理的图像文件")
            self.update_status_signal.emit("未找到可处理的图像文件", "warning")  # type: ignore[attr-defined]
            self.processing_finished_signal.emit(0)  # type: ignore[attr-defined]
            return

        logger.info("processing_controller", "batch_start", f"开始处理 {total_files} 个文件")
        self.update_status_signal.emit(f"开始处理 {total_files} 个文件...", "working")  # type: ignore[attr-defined]
        
        # 2. Process Loop
        processed_count = 0
        failed_count = 0
        for i, image_path in enumerate(all_files):
            if self._stop_flag:
                logger.info("processing_controller", "processing_stopped", "Processing stopped by user")
                break
                
            self.progress_update_signal.emit(i + 1, total_files)  # type: ignore[attr-defined]
            self.update_status_signal.emit(f"正在处理 ({i+1}/{total_files}): {os.path.basename(image_path)}", "working")  # type: ignore[attr-defined]
            
            try:
                self._process_single_file(
                    image_path, 
                    force_reprocess
                )
                processed_count += 1
            except Exception as e:
                logger.error("processing_controller", "file_processing_error", 
                           f"处理文件 {image_path} 时出错：{e}")
                traceback.print_exc()
                failed_count += 1
                self.update_status_signal.emit(f"处理失败：{os.path.basename(image_path)}", "error")  # type: ignore[attr-defined]

        total_time = time.perf_counter() - start_time
        
        # 💾 批量处理完成后，强制保存索引表
        self._maybe_save_index_table(force=True)
        
        logger.info("processing_controller", "batch_complete", 
                   f"批量处理完成：成功={processed_count}, 失败={failed_count}, 总耗时 {total_time:.2f}s")
        self.processing_finished_signal.emit(total_time)  # type: ignore[attr-defined]
        self.update_status_signal.emit("处理完成", "success")  # type: ignore[attr-defined]

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessingController")
    def _process_single_file(self, image_path, force_reprocess):
        """
        Process a single file (Image or PDF).
        Handles caching and delegation to OCR engine.
        """
        logger = get_logger()
        filename = os.path.basename(image_path)
        current_file_dir = os.path.dirname(image_path)
        parent_dir_name = os.path.basename(current_file_dir)
        current_output_dir = os.path.join(self.output_dir, parent_dir_name)
        
        is_pdf = image_path.lower().endswith('.pdf')
        
        # Construct expected MessagePack output path for checking cache
        safe_filename = filename.replace(':', '_')
        msgpack_output_file = os.path.join(current_output_dir, "msgpack", f"{os.path.splitext(safe_filename)[0]}.msgpack")
        
        # Check Cache (Skip if processed)
        # 🔥 性能优化：优先检查内存索引（已从 JSON 加载），避免磁盘 IO
        is_processed = False
        if not force_reprocess:
            # 1. 先检查内存索引（最快，无 IO）- O(1) 查找
            if msgpack_output_file in self._processed_cache_index:
                is_processed = True
            # 2. 内存索引未命中，再检查磁盘（仅在必要时发生 IO）
            elif os.path.exists(msgpack_output_file):
                is_processed = True
                # 加入内存索引，下次访问更快
                self._processed_cache_index[msgpack_output_file] = {
                    'file_path': image_path,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'success'
                }
        
        if is_processed:
            logger.debug("processing_controller", "skipping_cached", f"跳过已处理的文件（缓存）: {image_path}")
            # Load result to update UI
            try:
                data = MessagePackSerializer.load_from_file(msgpack_output_file)
                if 'full_text' in data:
                    self.file_processed_signal.emit(filename, data['full_text'])  # type: ignore[attr-defined]
                    # Update ResultManager cache so clicking the item shows results
                    self.result_manager.store_result(image_path, data['full_text'])
            except Exception as e:
                logger.error("processing_controller", "load_cache_error", f"加载缓存结果时出错：{e}")
            
            return
            
        # If force_reprocess is True, we proceed to process the file
        if force_reprocess:
            logger.info("processing_controller", "force_reprocessing", f"强制重新处理：{image_path}")
            # Clear any existing result in ResultManager to ensure UI updates
            self.result_manager.clear_result(image_path)
            # 从内存索引中移除
            self._processed_cache_index.pop(msgpack_output_file, None)


        # Prepare for processing
        if is_pdf:
            self._process_pdf(image_path, current_output_dir)
        else:
            self._process_image(image_path, current_output_dir)

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessingController")
    def _process_pdf(self, image_path, output_dir):
        logger = get_logger()
        images = self.file_utils.read_pdf_images(image_path)
        if not images:
            logger.warning("processing_controller", "pdf_read_failed", f"无法读取 PDF 文件：{image_path}")
            return

        filename = os.path.basename(image_path)
        pdf_full_texts = []
        
        for page_idx, image in enumerate(images):
            if self._stop_flag:
                break
                
            page_base_name = f"{os.path.splitext(filename)[0]}_page_{page_idx+1}"
            
            # 🔥 使用 OCRPipeline 处理 PDF 页面
            options = {
                'save_result': False,  # 我们自己处理保存
                'skip_preprocessing': True,  # 跳过预处理以避免 preprocessor 错误
                'image_path': f"{image_path}|page={page_idx+1}",
                'output_dir': output_dir,
                'result_base_name': page_base_name
            }
            
            result = self.ocr_pipeline.process(image, options)
            full_text = result.get('full_text', '')
            
            if full_text:
                pdf_full_texts.append(f"--- Page {page_idx+1} ---\n{full_text}")
                
                # 保存单页结果
                self._save_results(page_base_name, output_dir, f"{image_path}|page={page_idx+1}", full_text, result.get('regions', []))

        if pdf_full_texts:
            combined_text = "\n\n".join(pdf_full_texts)
            self.file_processed_signal.emit(filename, combined_text)  # type: ignore[attr-defined]
            self.result_manager.store_result(image_path, combined_text)
            
            # 🔥 发射处理后结果就绪事件（完整结果数据）
            # 在结果处理完成后、UI 渲染前触发，供插件和其他组件使用
            processed_result_data = {
                'filename': filename,
                'image_path': image_path,
                'full_text': combined_text,
                'regions': [],  # PDF 处理暂不包含详细区域信息
                'metadata': {
                    'processing_time': 0,  # PDF 处理时间未单独记录
                    'engine_version': 'unknown',
                    'preset': 'mobile',
                    'timestamp': datetime.now().isoformat(),
                    'is_pdf': True,
                    'page_count': len(pdf_full_texts)
                }
            }
            self.processed_result_ready_signal.emit(processed_result_data)

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessingController")
    def _process_image(self, image_path, output_dir):
        logger = get_logger()
        original_image = self.file_utils.read_image(image_path)
        if original_image is None:
            logger.warning("processing_controller", "image_read_failed", f"无法读取图像文件：{image_path}")
            return

        filename = os.path.basename(image_path)
        result_base_name = os.path.splitext(filename)[0]
        
        # 🔥 使用 OCRPipeline 处理图像
        options = {
            'save_result': False,  # 我们自己处理保存
            'skip_preprocessing': True,  # 跳过预处理以避免 preprocessor 错误
            'image_path': image_path,
            'output_dir': output_dir,
            'result_base_name': result_base_name
        }
        
        result = self.ocr_pipeline.process(original_image, options)
        full_text = result.get('full_text', '')
        detailed_results = result.get('regions', [])
        
        if full_text:
            # 🔥 发射普通文本信号（兼容旧代码）
            self.file_processed_signal.emit(filename, full_text)  # type: ignore[attr-defined]
            
            # 🔥 同时发射结构化数据信号（供悬浮窗使用）
            if hasattr(self, 'structured_result_ready_signal'):
                try:
                    logger.debug("processing_controller", "emitting_structured", f"发射结构化结果信号，包含 {len(detailed_results) if detailed_results else 0} 项")
                    self.structured_result_ready_signal.emit(detailed_results or [])  # type: ignore[attr-defined]
                except Exception as e:
                    logger.error("processing_controller", "emit_structured_failed", f"发射结构化信号失败：{e}")
            
            self.result_manager.store_result(image_path, full_text)
            
            # 🔥 发射处理后结果就绪事件（完整结果数据）
            # 在结果处理完成后、UI 渲染前触发，供插件和其他组件使用
            processed_result_data = {
                'filename': filename,
                'image_path': image_path,
                'full_text': full_text,
                'regions': detailed_results or [],
                'metadata': {
                    'processing_time': result.get('processing_time', 0),
                    'engine_version': result.get('engine_version', 'unknown'),
                    'preset': result.get('preset', 'mobile'),
                    'timestamp': datetime.now().isoformat()
                }
            }
            self.processed_result_ready_signal.emit(processed_result_data)
            
            # 保存结果
            self._save_results(result_base_name, output_dir, image_path, full_text, detailed_results)

    def _process_image_data(self, image, image_path, result_base_name, output_dir):
        """
        Core logic to process an image object (PIL).
        Calls OCR and saves results.
        """
        # 始终处理全图
        cropped_image, offset_x, offset_y = self._crop_image_with_expansion(image, None)
        
        file_recognized_texts = []
        file_detailed_results = []
        file_processing_failed = False
        
        # 强制使用子进程模式
        use_subprocess = True
        
        text_regions = None

    def _determine_masks(self, image_path=None):
        """已移除蒙版功能，始终返回全图"""
        return [{'rect': None, 'label': 0}]

    def _crop_image_with_expansion(self, image, rect=None):
        """Crop image with expansion, returning cropped image and offsets."""
        logger = get_logger()
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
                
                return self._crop_image_manual(image), 0, 0
        except Exception as e:
            logger.error("processing_controller", "crop_error", f"裁切图像失败：{e}")
            
        return image, 0, 0

    @handle_errors(error_code=ErrorCode.RESULT_EXPORT_001, fallback_return=None, component="ProcessingController")
    def _save_results(self, result_base_name, output_dir, image_path, full_text, regions):
        logger = get_logger()
        msgpack_output_dir = os.path.join(output_dir, "msgpack")
        os.makedirs(msgpack_output_dir, exist_ok=True)
        
        # Save MessagePack
        msgpack_output_file = os.path.join(msgpack_output_dir, f"{result_base_name}.msgpack")
        try:
            # 使用 ResultAdapter 转换 regions 为标准格式
            logger.debug("processing_controller", "adapting_regions", f"正在适配 {len(regions)} 个区域...")
            from app.core.result.result_adapter import ResultAdapter
            adapted_regions = ResultAdapter.adapt(regions)
            logger.debug("processing_controller", "regions_adapted", f"已适配到 {len(adapted_regions)} 项")
            if adapted_regions:
                logger.debug("processing_controller", "first_item_keys", f"首个适配项的键：{list(adapted_regions[0].keys())}")
                logger.debug("processing_controller", "has_box", f"包含 box 字段：{'box' in adapted_regions[0]}")
                logger.debug("processing_controller", "has_polygon", f"包含 polygon 字段：{'polygon' in adapted_regions[0]}")
                logger.debug("processing_controller", "has_table_info", f"包含 table_info 字段：{'table_info' in adapted_regions[0]}")
            
            msgpack_result = {
                'image_path': image_path,
                'filename': result_base_name,
                'timestamp': datetime.now().isoformat(),
                'full_text': full_text,
                'regions': adapted_regions,  # 保存适配后的数据
                'status': 'success'
            }
            MessagePackSerializer.save_to_file(msgpack_result, msgpack_output_file)
            
            # 🔥 性能优化：保存到内存索引 + JSON 索引表，下次检查无需磁盘 IO
            self._processed_cache_index[msgpack_output_file] = {
                'file_path': image_path,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }
        except Exception as e:
            logger.error("processing_controller", "save_msgpack_failed", f"保存 MessagePack 失败：{e}")
            import traceback
            traceback.print_exc()
