# -*- coding: utf-8 -*-

"""
进程管理器（管理GUI、输入、处理、输出等独立进程）
"""

import multiprocessing
import os
import time
import queue
from datetime import datetime
import json
from PIL import Image
import traceback
import threading


class ProcessManager:
    def __init__(self, config_manager=None):
        """
        初始化进程管理器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.processes = {}
        self.queues = {}
        self.running = False
        self.service_status = {}
        
        # 创建进程间通信队列
        self._create_queues()

    def _create_queues(self):
        """
        创建进程间通信队列
        """
        # 输入队列（文件路径）
        self.queues['input'] = queue.Queue()
        
        # 处理队列（图像数据和元数据）
        self.queues['processing'] = queue.Queue()
        
        # 输出队列（处理结果）
        self.queues['output'] = queue.Queue()
        
        # 控制队列（开始、停止等控制命令）
        self.queues['control'] = queue.Queue()

    def start_processes(self):
        """
        启动所有进程
        """
        print("Starting multi-process architecture")
        self.running = True
        
        self._start_input_process()
        
        num_processing_processes = self.config_manager.get_setting('processing_processes', 2) if self.config_manager else 2
        for i in range(num_processing_processes):
            self._start_processing_process(i)
        
        self._start_output_process()
        
        print("All processes started")

    def stop_processes(self):
        """
        停止所有线程
        """
        print("Stopping all threads")
        self.running = False
        for name in list(self.service_status.keys()):
            self.service_status[name]['status'] = 'stopped'
        
        # 向所有线程发送停止信号
        try:
            for _ in range(len(self.processes) + 5):  # 发送足够多的停止信号
                try:
                    self.queues['control'].put('STOP', block=False)
                except:
                    pass
        except:
            pass
        
        # 等待所有线程结束（设置超时）
        for name, thread in self.processes.items():
            if thread.is_alive():
                print(f"Waiting for {name} to finish...")
                try:
                    thread.join(timeout=2)  # 减少等待时间
                except:
                    pass
                
        self.processes.clear()
        print("All threads stopped")

    def _start_input_process(self):
        """
        启动输入线程
        """
        thread = threading.Thread(target=self._input_worker, name="InputThread")
        thread.daemon = True  # 设置为守护线程
        thread.start()
        self.processes['input'] = thread
        self.service_status['input'] = {
            'status': 'running',
            'last_heartbeat': time.time(),
            'last_error': None,
            'processed': 0
        }
        print("Input thread started")

    def _start_processing_process(self, index):
        """
        启动处理线程（使用线程而非进程避免pickle问题）

        Args:
            index: 线程索引
        """
        # 使用线程而不是进程，避免pickle问题
        thread = threading.Thread(
            target=self._processing_worker, 
            args=(index,), 
            name=f"ProcessingThread-{index}"
        )
        thread.daemon = True  # 设置为守护线程
        thread.start()
        name = f'processing-{index}'
        self.processes[name] = thread
        self.service_status[name] = {
            'status': 'running',
            'last_heartbeat': time.time(),
            'last_error': None,
            'processed': 0
        }
        print(f"Processing thread {index} started")

    def _start_output_process(self):
        """
        启动输出线程
        """
        thread = threading.Thread(target=self._output_worker, name="OutputThread")
        thread.daemon = True  # 设置为守护线程
        thread.start()
        self.processes['output'] = thread
        self.service_status['output'] = {
            'status': 'running',
            'last_heartbeat': time.time(),
            'last_error': None,
            'processed': 0
        }
        print("Output thread started")

    def get_service_status(self):
        return json.loads(json.dumps(self.service_status))

    def _input_worker(self):
        """
        输入线程工作函数
        负责扫描输入目录并添加图像文件到处理队列
        """
        print("Input worker started")
        from app.utils.file_utils import FileUtils
        from app.core.record_manager import RecordManager
        
        while self.running:
            try:
                status = self.service_status.get('input')
                if status is not None:
                    status['last_heartbeat'] = time.time()
                # 检查是否有处理任务
                try:
                    task = self.queues['input'].get(timeout=0.5)
                    if task.get('type') == 'STOP':
                        print("Input worker received STOP command")
                        break
                    elif task.get('type') == 'process_directory':
                        input_dir = task['input_dir']
                        output_dir = task['output_dir']
                        
                        print(f"Processing directory: {input_dir}")
                        # 获取图像文件列表
                        image_files = FileUtils.get_image_files(input_dir)
                        print(f"Found {len(image_files)} image files")
                        
                        # 将每个文件添加到处理队列
                        for image_path in image_files:
                            if not self.running:  # 检查是否应该停止
                                break
                            
                            # 根据用户需求，输出目录生成到对应输入文件夹的下级中
                            current_file_dir = os.path.dirname(image_path)
                            current_output_dir = os.path.join(current_file_dir, "output")
                            
                            # 检查是否已处理
                            filename = os.path.basename(image_path)
                            input_record_mgr = RecordManager.get_instance(current_file_dir)
                            output_record_mgr = RecordManager.get_instance(current_output_dir)
                            
                            # Check if processing is needed
                            # Need to check json status for error
                            json_path = os.path.join(current_output_dir, "json", f"{os.path.splitext(filename)[0]}.json")
                            is_processed_successfully = False
                            
                            if os.path.exists(json_path):
                                try:
                                    with open(json_path, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                        if data.get('status') == 'success':
                                            is_processed_successfully = True
                                        else:
                                            # If status is error, we should reprocess
                                            print(f"File {filename} was processed with error, reprocessing...")
                                except:
                                    # If file is corrupted, reprocess
                                    pass
                            
                            if is_processed_successfully:
                                print(f"Skipping already processed file: {filename}")
                                if status is not None:
                                    status['processed'] += 1
                                continue
                            
                            # Add to queue
                            task = {
                                'image_path': image_path,
                                'output_dir': current_output_dir
                            }
                            
                            self.queues['processing'].put(task)
                            print(f"Added to processing queue: {filename}")
                            
                        # Signal end of batch for this directory
                        # But since we are processing continuously, we don't really end unless stopped
                        
                except queue.Empty:
                    # 没有任务时短暂休眠，避免过度占用CPU
                    time.sleep(0.1)
                except Exception as e:
                    if self.running:  # 只在仍在运行时打印错误
                        print(f"Error in input worker task processing: {e}")
                
            except Exception as e:
                if self.running:  # 只在仍在运行时打印错误
                    print(f"Error in input worker: {e}")
        
        status = self.service_status.get('input')
        if status is not None:
            status['status'] = 'stopped'
        print("Input worker stopped")

    def _processing_worker(self, index):
        """
        处理线程工作函数
        负责执行OCR处理

        Args:
            index: 线程索引
        """
        print(f"Processing worker {index} started")
        name = f'processing-{index}'
        status = self.service_status.get(name)
        
        # 导入必要的模块
        try:
            from app.core.config_manager import ConfigManager
            from app.ocr.engine import OcrEngine
            import numpy as np
        except Exception as e:
            if self.running:
                print(f"Error importing modules in processing worker {index}: {e}")
                if status is not None:
                    status['last_error'] = str(e)
                    status['status'] = 'error'
            return
        
        # 为每个线程创建独立的配置管理器和处理组件
        try:
            config_manager = ConfigManager()
            config_manager.load_config()
            ocr_client = None
            ocr_engine = OcrEngine(config_manager)
            print(f"Worker {index}: Using Local OCR Engine")

        except Exception as e:
            if self.running:
                print(f"Error initializing components in processing worker {index}: {e}")
                print(traceback.format_exc())
                if status is not None:
                    status['last_error'] = str(e)
                    status['status'] = 'error'
            return
        
        while self.running:
            try:
                # 检查控制命令
                try:
                    command = self.queues['control'].get(timeout=0.1)
                    if command == 'STOP':
                        print(f"Processing worker {index} received STOP command")
                        break
                except queue.Empty:
                    pass
                if status is not None:
                    status['last_heartbeat'] = time.time()
                
                # 检查处理任务
                try:
                    task = self.queues['processing'].get(timeout=0.1)
                    image_path = task['image_path']
                    output_dir = task['output_dir']
                    
                    print(f"Processing worker {index} processing: {image_path}")
                    
                    ocr_result = {}
                    
                    # Prepare options
                    options = {
                        'use_table_split': config_manager.get_setting('use_table_split', False),
                        'table_split_mode': config_manager.get_setting('table_split_mode', 'horizontal'),
                        'use_ai_table': config_manager.get_setting('use_ai_table', False),
                        'ai_table_model': config_manager.get_setting('ai_table_model', 'SLANet'),
                    }
                    
                    try:
                        if use_network_ocr and ocr_client:
                            # Use Client
                            ocr_result = ocr_client.predict(image_path, options)
                        else:
                            # Use Local Engine
                            image = Image.open(image_path)
                            ocr_result = ocr_engine.process_image(image, options)
                    except Exception as e:
                        print(f"OCR processing failed for {image_path}: {e}")
                        # print(traceback.format_exc()) # Reduce noise
                        if status is not None:
                            status['last_error'] = str(e)
                        
                        # Create error result
                        ocr_result = {
                            'full_text': '',
                            'regions': [],
                            'status': 'error',
                            'error_message': str(e)
                        }
                        
                    # Process Result
                    full_text = ocr_result.get('full_text', '')
                    regions = ocr_result.get('regions', [])
                    status_code = ocr_result.get('status', 'success')
                    error_message = ocr_result.get('error_message', '')
                    
                    # Create result structure expected by Output Thread
                    result = {
                        'image_path': image_path,
                        'filename': os.path.basename(image_path),
                        'timestamp': datetime.now().isoformat(),
                        'full_text': full_text,
                        'regions': regions,
                        'output_dir': output_dir,
                        'status': status_code,
                        'error_message': error_message
                    }
                    
                    # Ensure numpy types are converted
                    def convert_numpy_types(obj):
                        if isinstance(obj, dict):
                            return {key: convert_numpy_types(value) for key, value in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_numpy_types(item) for item in obj]
                        elif hasattr(obj, 'item'):
                            return obj.item()
                        else:
                            return obj
                    
                    result = convert_numpy_types(result)
                    
                    # 添加到输出队列
                    if self.running:
                        self.queues['output'].put(result)
                    print(f"Processing worker {index} finished: {image_path}")
                    if status is not None:
                        status['processed'] += 1
                    
                except queue.Empty:
                    # 没有任务时短暂休眠，避免过度占用CPU
                    time.sleep(0.01)
                except Exception as e:
                    if self.running:
                        print(f"Error processing task in worker {index}: {e}")
                        print(traceback.format_exc())
                        if status is not None:
                            status['last_error'] = str(e)
                        
            except Exception as e:
                if self.running:
                    print(f"Error in processing worker {index}: {e}")
                    print(traceback.format_exc())
                    if status is not None:
                        status['last_error'] = str(e)
        if status is not None:
            status['status'] = 'stopped'
        print(f"Processing worker {index} stopped")

    def _output_worker(self):
        """
        输出线程工作函数
        负责保存处理结果
        """
        print("Output worker started")
        from app.utils.file_utils import FileUtils
        from app.core.record_manager import RecordManager
        status = self.service_status.get('output')
        
        while self.running:
            try:
                # 检查控制命令
                try:
                    command = self.queues['control'].get(timeout=0.1)
                    if command == 'STOP':
                        print("Output worker received STOP command")
                        break
                except queue.Empty:
                    pass
                
                # 检查输出任务
                try:
                    result = self.queues['output'].get(timeout=0.1)
                    
                    image_path = result['image_path']
                    output_dir = result['output_dir']
                    full_text = result['full_text']
                    filename = result['filename']
                    
                    # 根据用户需求，输出目录生成到对应输入文件夹的下级中
                    # current_output_dir = os.path.join(os.path.dirname(image_path), "output")
                    # 但这里我们保持接口一致性，output_dir由调用方决定
                    # 如果需要强制每个文件都在其父目录的output下，可以在这里修改
                    # 鉴于_input_worker也会修改，这里我们先使用传入的output_dir
                    # 但是为了保持一致性，我们在这里处理txt/json子目录
                    
                    print(f"Output worker saving results for: {filename}")
                    
                    # 创建txt和json子目录
                    txt_output_dir = os.path.join(output_dir, "txt")
                    json_output_dir = os.path.join(output_dir, "json")
                    
                    os.makedirs(txt_output_dir, exist_ok=True)
                    os.makedirs(json_output_dir, exist_ok=True)
                    
                    # 保存结果到TXT文件
                    try:
                        output_file = os.path.join(txt_output_dir, f"{os.path.splitext(filename)[0]}_result.txt")
                        FileUtils.write_text_file(output_file, full_text)
                    except Exception as e:
                        if self.running:
                            print(f"Error writing TXT file for {filename}: {e}")
                    
                    # 保存详细的JSON结果文件
                    try:
                        json_output_file = os.path.join(json_output_dir, f"{os.path.splitext(filename)[0]}.json")
                        FileUtils.write_json_file(json_output_file, result)
                    except Exception as e:
                        if self.running:
                            print(f"Error writing JSON file for {filename}: {e}")
                    
                    # 记录已处理
                    try:
                        current_file_dir = os.path.dirname(image_path)
                        input_record_mgr = RecordManager.get_instance(current_file_dir)
                        output_record_mgr = RecordManager.get_instance(output_dir)
                        
                        input_record_mgr.add_record(filename)
                        output_record_mgr.add_record(filename)
                    except Exception as e:
                        if self.running:
                            print(f"Error updating records for {filename}: {e}")
                            
                    if status is not None:
                        status['processed'] += 1
                except queue.Empty:
                    # 没有任务时短暂休眠，避免过度占用CPU
                    time.sleep(0.01)
                except Exception as e:
                    if self.running:
                        print(f"Error in output worker task processing: {e}")
                        if status is not None:
                            status['last_error'] = str(e)
                    
            except Exception as e:
                if self.running:
                    print(f"Error in output worker: {e}")
                    if status is not None:
                        status['last_error'] = str(e)
        if status is not None:
            status['status'] = 'stopped'
        print("Output worker stopped")

    def add_input_directory(self, input_dir, output_dir):
        """
        添加输入目录进行处理

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
        """
        try:
            # 发送处理任务到输入队列
            task = {
                'type': 'process_directory',
                'input_dir': input_dir,
                'output_dir': output_dir,
                'timestamp': datetime.now().isoformat()
            }
            self.queues['input'].put(task)
            print(f"Added directory task: {input_dir} -> {output_dir}")
        except Exception as e:
            print(f"Error adding input directory: {e}")

    def process_directory(self, input_dir: str, output_dir: str, result_manager=None) -> str:
        """
        同步处理指定目录中的图像并保存结果
        """
        from app.utils.file_utils import FileUtils
        from app.core.record_manager import RecordManager
        try:
            from app.image.preprocessor import Preprocessor
            from app.ocr.detector import Detector
            from app.ocr.recognizer import Recognizer
            from app.ocr.post_processor import PostProcessor
            from app.image.table_splitter import TableSplitter
            from app.core.config_manager import ConfigManager
            from datetime import datetime
            import os
        except Exception as e:
            print(f"Error importing modules in process_directory: {e}")
            return ""

        try:
            os.makedirs(output_dir, exist_ok=True)
            image_files = FileUtils.get_image_files(input_dir)
        except Exception as e:
            print(f"Error preparing directories or listing images: {e}")
            return ""

        try:
            config_manager = self.config_manager or ConfigManager()
            if not self.config_manager:
                config_manager.load_config()
            preprocessor = Preprocessor()
            detector = Detector(config_manager)
            recognizer = Recognizer(config_manager)
            post_processor = PostProcessor()
            table_splitter = TableSplitter()
        except Exception as e:
            print(f"Error initializing components in process_directory: {e}")
            return ""

        for image_path in image_files:
            try:
                image = FileUtils.read_image(image_path)
                if image is None:
                    continue
                    
                # 根据用户需求，输出目录生成到对应输入文件夹的下级中
                current_file_dir = os.path.dirname(image_path)
                current_output_dir = os.path.join(current_file_dir, "output")
                
                # 检查是否已处理
                filename = os.path.basename(image_path)
                input_record_mgr = RecordManager.get_instance(current_file_dir)
                output_record_mgr = RecordManager.get_instance(current_output_dir)
                
                is_processed = False
                json_output_file = os.path.join(current_output_dir, "json", f"{os.path.splitext(filename)[0]}.json")
                
                if input_record_mgr.is_recorded(filename) and output_record_mgr.is_recorded(filename):
                    if os.path.exists(json_output_file):
                        is_processed = True
                
                if is_processed:
                    print(f"Skipping processed file (loading cache): {image_path}")
                    try:
                        with open(json_output_file, 'r', encoding='utf-8') as f:
                            cached_result = json.load(f)
                        full_text = cached_result.get('full_text', '')
                        if result_manager:
                            result_manager.store_result(image_path, full_text)
                    except Exception as e:
                        print(f"Error loading cached result for {image_path}: {e}")
                        pass
                    else:
                        continue
                
                txt_output_dir = os.path.join(current_output_dir, "txt")
                json_output_dir = os.path.join(current_output_dir, "json")
                
                os.makedirs(txt_output_dir, exist_ok=True)
                os.makedirs(json_output_dir, exist_ok=True)
                
                filename = os.path.splitext(os.path.basename(image_path))[0]
                image = preprocessor.comprehensive_preprocess(image, None, filename)
                
                # Table Split Logic
                use_table_split = config_manager.get_setting('use_table_split', False)
                split_results = []
                if use_table_split:
                    table_split_mode = config_manager.get_setting('table_split_mode', 'horizontal')
                    try:
                        split_results = table_splitter.split(image, table_split_mode)
                    except Exception as e:
                        print(f"Error splitting table: {e}")
                        width, height = image.size
                        split_results = [{'image': image, 'box': (0, 0, width, height), 'row': 0, 'col': 0}]
                else:
                    width, height = image.size
                    split_results = [{'image': image, 'box': (0, 0, width, height), 'row': 0, 'col': 0}]
                
                text_regions = []
                for split_item in split_results:
                    sub_image = split_item['image']
                    cell_box = split_item['box']
                    cell_x, cell_y = cell_box[0], cell_box[1]
                    row_idx = split_item.get('row', 0)
                    col_idx = split_item.get('col', 0)
                    
                    sub_regions = detector.detect_text_regions(sub_image)
                    for region in sub_regions:
                        coords = region.get('coordinates', [])
                        new_coords = []
                        if isinstance(coords, list):
                            for point in coords:
                                if isinstance(point, (list, tuple)) and len(point) >= 2:
                                    new_coords.append([point[0] + cell_x, point[1] + cell_y])
                        if new_coords:
                            region['coordinates'] = new_coords
                        region['table_info'] = {'row': row_idx, 'col': col_idx, 'cell_box': cell_box}
                        text_regions.append(region)
                        
                recognized_texts = []
                detailed_results = []
                for region in text_regions:
                    text = region.get('text', '')
                    confidence = region.get('confidence', 0.0)
                    coordinates = region.get('coordinates', [])
                    corrected_text = post_processor.correct_format(text)
                    corrected_text = post_processor.semantic_correction(corrected_text)
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
                full_text = " ".join(recognized_texts)
                txt_path = os.path.join(txt_output_dir, f"{filename}_result.txt")
                FileUtils.write_text_file(txt_path, full_text)
                json_result = {
                    'image_path': image_path,
                    'filename': os.path.basename(image_path),
                    'timestamp': datetime.now().isoformat(),
                    'full_text': full_text,
                    'regions': detailed_results
                }
                json_path = os.path.join(json_output_dir, f"{filename}.json")
                FileUtils.write_json_file(json_path, json_result)
                if result_manager:
                    result_manager.store_result(image_path, full_text)
                    
                # 记录已处理
                input_record_mgr.add_record(filename)
                output_record_mgr.add_record(filename)
            except Exception as e:
                print(f"Error processing image {image_path}: {e}")
                continue

        export_path = ""
        try:
            if result_manager:
                export_path = result_manager.export_results(output_dir, 'json')
        except Exception as e:
            print(f"Error exporting aggregated results: {e}")
        return export_path
