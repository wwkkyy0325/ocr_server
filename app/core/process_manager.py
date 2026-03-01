# -*- coding: utf-8 -*-

"""
进程管理器（重构版）
负责管理OCR处理任务，使用PriorityQueue进行任务调度，支持多线程处理。
"""

import os
import time
import queue
import json
import threading
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from PIL import Image
import numpy as np

from app.core.config_manager import ConfigManager
from app.utils.file_utils import FileUtils
from app.core.record_manager import RecordManager

# Try importing OcrEngine, handle potential import errors gracefully if needed
try:
    from app.ocr.engine import OcrEngine
except ImportError:
    OcrEngine = None


class ProcessManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(ProcessManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        初始化进程管理器
        """
        # 防止重复初始化
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        self.config_manager = config_manager or ConfigManager()
        if not self.config_manager.config:
            self.config_manager.load_config()

        self.processes = {}
        self.queues = {}
        self.running = False
        
        # Service status with lock for thread safety
        self._service_status = {}
        self._status_lock = threading.Lock()
        
        self._create_queues()
        self.initialized = True

    @classmethod
    def get_instance(cls, config_manager=None):
        if cls._instance is None:
            cls._instance = cls(config_manager)
        return cls._instance

    def _create_queues(self):
        """
        创建队列
        """
        # Processing queue: stores (priority, task_dict)
        # Priority: Lower number = Higher priority
        self.queues['processing'] = queue.PriorityQueue()
        
        # Output queue: stores result_dict
        self.queues['output'] = queue.Queue()
        
        # Control queue: stores command strings
        self.queues['control'] = queue.Queue()

    def submit_tasks(self, files: List[str], options: Dict[str, Any], priority: int = 10):
        """
        提交任务到处理队列

        Args:
            files: 图片文件路径列表
            options: 处理选项，必须包含 'output_dir'
            priority: 优先级 (默认10，越小优先级越高)
        """
        if not files:
            return

        output_dir = options.get('output_dir')
        if not output_dir:
            print("Warning: No output_dir specified in options. Using default 'outputs'.")
            output_dir = 'outputs'
            options['output_dir'] = output_dir # Update options

        count = 0
        for file_path in files:
            if not os.path.exists(file_path):
                continue
            
            self.submit_task(file_path, options, priority)
            count += 1
            
        print(f"Submitted {count} tasks with priority {priority}")

    def submit_task(self, file_path: str, options: Dict[str, Any], priority: int = 10):
        """
        提交单个任务到处理队列
        """
        # Check existence, handling virtual paths like "path/to/pdf|page=1"
        check_path = file_path
        if "|page=" in file_path:
            check_path = file_path.split("|page=")[0]
            
        if not os.path.exists(check_path):
            print(f"Warning: File not found: {check_path}")
            return

        output_dir = options.get('output_dir', 'outputs')
        
        # Construct task
        task = {
            'image_path': file_path,
            'options': options,
            'output_dir': output_dir, # Ensure output_dir is accessible
            'timestamp': datetime.now().isoformat(),
            'task_id': f"{os.path.basename(file_path)}_{time.time()}"
        }
        
        # Add to PriorityQueue
        # Python's PriorityQueue retrieves lowest values first
        self.queues['processing'].put((priority, task))

    def clear_queue(self):
        """
        清空处理队列
        """
        q = self.queues.get('processing')
        if q:
            try:
                while not q.empty():
                    q.get_nowait()
            except queue.Empty:
                pass
        print("Processing queue cleared")

    def process_directory(self, input_dir: str, output_dir: str, options: Dict[str, Any] = None, priority: int = 10):
        """
        扫描目录并提交任务 (Wrapper around submit_tasks)
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            options: 其他选项
            priority: 优先级
        """
        if options is None:
            options = {}
        
        # Ensure output_dir is in options
        options['output_dir'] = output_dir
        
        # Scan for images
        try:
            image_files = FileUtils.get_image_files(input_dir)
            print(f"Scanning directory {input_dir}: Found {len(image_files)} images")
            
            # Submit tasks
            self.submit_tasks(image_files, options, priority)
            
        except Exception as e:
            print(f"Error processing directory {input_dir}: {e}")
            traceback.print_exc()

    def start_processes(self):
        """
        启动所有工作线程
        """
        if self.running:
            print("Processes already running")
            return

        print("Starting ProcessManager workers...")
        self.running = True
        
        # Start Output Worker
        self._start_output_worker()
        
        # Start Processing Workers
        # User Request: Use single thread structure to save memory
        # Force num_workers to 1 regardless of config
        num_workers = 1 
        # num_workers = self.config_manager.get_setting('processing_processes', 2)
        
        for i in range(num_workers):
            self._start_processing_worker(i)
            
        print(f"Started {num_workers} processing worker (Single-Thread Mode) and 1 output worker")

    def stop_processes(self):
        """
        停止所有工作线程
        """
        print("Stopping ProcessManager workers...")
        self.running = False
        
        # Send STOP signal to control queue (enough for all workers)
        # Note: Workers check self.running first, but control queue helps wake them up if blocked
        for _ in range(len(self.processes) * 2):
            self.queues['control'].put('STOP')
            
        # Wait for threads to finish
        for name, thread in self.processes.items():
            if thread.is_alive():
                print(f"Waiting for {name} to stop...")
                thread.join(timeout=2.0)
                
        self.processes.clear()
        
        # Update status
        with self._status_lock:
            for key in self._service_status:
                self._service_status[key]['status'] = 'stopped'
                
        print("All workers stopped")

    def _start_processing_worker(self, index):
        thread_name = f"ProcessingWorker-{index}"
        thread = threading.Thread(
            target=self._processing_worker,
            args=(index,),
            name=thread_name,
            daemon=True
        )
        thread.start()
        self.processes[thread_name] = thread
        self._update_status(thread_name, 'running')

    def _start_output_worker(self):
        thread_name = "OutputWorker"
        thread = threading.Thread(
            target=self._output_worker,
            name=thread_name,
            daemon=True
        )
        thread.start()
        self.processes[thread_name] = thread
        self._update_status(thread_name, 'running')

    def _update_status(self, name: str, status: str, error: str = None):
        """
        Thread-safe status update
        """
        with self._status_lock:
            if name not in self._service_status:
                self._service_status[name] = {
                    'processed': 0,
                    'start_time': time.time()
                }
            
            self._service_status[name].update({
                'status': status,
                'last_heartbeat': time.time()
            })
            
            if error:
                self._service_status[name]['last_error'] = error

    def _increment_processed_count(self, name: str):
        with self._status_lock:
            if name in self._service_status:
                self._service_status[name]['processed'] += 1

    def get_service_status(self):
        with self._status_lock:
            return json.loads(json.dumps(self._service_status))

    def _processing_worker(self, index):
        """
        Worker thread that processes OCR tasks
        """
        name = f"ProcessingWorker-{index}"
        print(f"{name} started")
        
        # OCR引擎完全移至子进程 - 主进程不初始化任何OCR组件
        print(f"{name}: OCR processing delegated to subprocess only")

        while self.running:
            try:
                # 1. Check control queue (non-blocking or short timeout)
                try:
                    command = self.queues['control'].get(timeout=0.01)
                    if command == 'STOP':
                        break
                except queue.Empty:
                    pass

                # 2. Get task from processing queue
                try:
                    # Block with timeout to allow checking self.running periodically
                    priority, task = self.queues['processing'].get(timeout=0.5)
                except queue.Empty:
                    self._update_status(name, 'idle')
                    continue

                self._update_status(name, 'processing')
                
                image_path = task['image_path']
                options = task.get('options', {})
                output_dir = task.get('output_dir')
                
                # Merge global options if needed, but task options take precedence
                # processing_options = options.copy()
                
                # Process image
                try:
                    check_path = image_path
                    if "|page=" in image_path:
                        check_path = image_path.split("|page=")[0]
                        
                    if not os.path.exists(check_path):
                        raise FileNotFoundError(f"Image not found: {check_path}")

                    # Use FileUtils to handle virtual paths and PDFs
                    image = FileUtils.read_image(image_path)
                    if image is None:
                         raise ValueError(f"Failed to read image: {image_path}")
                         
                    # Use context manager to ensure file is closed
                    # Note: FileUtils.read_image returns an open PIL Image object which supports context manager protocol
                    with image:
                        print("[DEBUG] 🔒 FORCING SUBPROCESS MODE - Main process OCR DISABLED")
                        # 完全移除主进程OCR引擎 - 所有处理都在子进程中进行
                        try:
                            from app.core.ocr_subprocess import get_ocr_subprocess_manager
                            subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
                            
                            # 确保子进程在运行
                            if not subprocess_manager.is_running():
                                current_preset = self.config_manager.get_setting('current_ocr_preset', 'mobile')
                                print(f"{name}: 🚀 Starting OCR subprocess with preset: {current_preset}")
                                success = subprocess_manager.start_process(current_preset)
                                if not success:
                                    raise RuntimeError("Failed to start OCR subprocess")
                                print(f"{name}: ✅ OCR subprocess started successfully")
                            else:
                                print(f"{name}: ✅ OCR subprocess already running")
                            
                            # 在子进程中处理图像
                            print(f"{name}: 🔄 Sending image to OCR subprocess for processing...")
                            ocr_result = subprocess_manager.process_image(image, options)
                            print(f"{name}: ✅ Image processed successfully in OCR subprocess")
                            
                        except Exception as e:
                            print(f"{name}: ❌ OCR subprocess processing failed: {e}")
                            print(f"{name}: ⛔ Main process OCR is COMPLETELY DISABLED - NO FALLBACK")
                            raise RuntimeError(f"OCR子进程处理失败，主进程OCR已完全禁用: {e}")
                    
                    # Prepare result for output worker
                    result = {
                        'image_path': image_path,
                        'filename': os.path.basename(image_path),
                        'output_dir': output_dir,
                        'full_text': ocr_result.get('full_text', ''),
                        'regions': ocr_result.get('regions', []),
                        'status': ocr_result.get('status', 'success'),
                        'error_message': ocr_result.get('error_message', ''),
                        'timestamp': datetime.now().isoformat(),
                        'options': options  # Pass options through in case needed
                    }
                    
                    # Convert numpy types to native types
                    result = self._convert_numpy_types(result)
                    
                    self.queues['output'].put(result)
                    self._increment_processed_count(name)
                    
                except Exception as e:
                    print(f"{name}: Error processing {image_path}: {e}")
                    # Send error result to output queue so it can be logged/recorded
                    error_result = {
                        'image_path': image_path,
                        'filename': os.path.basename(image_path),
                        'output_dir': output_dir,
                        'status': 'error',
                        'error_message': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    self.queues['output'].put(error_result)
                    self._update_status(name, 'running', str(e))

            except Exception as e:
                print(f"{name} loop error: {e}")
                traceback.print_exc()
                self._update_status(name, 'error', str(e))
                time.sleep(1) # Prevent tight loop on repeated errors

        print(f"{name} stopped")
        self._update_status(name, 'stopped')

    def _output_worker(self):
        """
        Worker thread that handles output (saving files, callbacks)
        """
        name = "OutputWorker"
        print(f"{name} started")
        
        while self.running:
            try:
                # 1. Check control queue
                try:
                    command = self.queues['control'].get(timeout=0.01)
                    if command == 'STOP':
                        break
                except queue.Empty:
                    pass

                # 2. Get result from output queue
                try:
                    result = self.queues['output'].get(timeout=0.5)
                except queue.Empty:
                    self._update_status(name, 'idle')
                    continue

                self._update_status(name, 'processing')
                
                # Handle Result
                try:
                    self._handle_result(result)
                    self._increment_processed_count(name)
                except Exception as e:
                    print(f"{name}: Error handling result: {e}")
                    traceback.print_exc()
                    self._update_status(name, 'running', str(e))

            except Exception as e:
                print(f"{name} loop error: {e}")
                self._update_status(name, 'error', str(e))
                time.sleep(1)

        print(f"{name} stopped")
        self._update_status(name, 'stopped')

    def _handle_result(self, result: Dict[str, Any]):
        """
        Save results and handle callbacks
        """
        status = result.get('status')
        image_path = result.get('image_path')
        filename = result.get('filename')
        output_dir = result.get('output_dir')
        
        if not output_dir:
            return

        # Handle successful processing
        if status == 'success':
            full_text = result.get('full_text', '')
            
            # Determine subdirectories
            # If the image was in a subdirectory of the input root, we might want to mirror that structure.
            # For now, we follow the simple logic: output_dir/parent_dir_name/
            
            parent_dir_name = os.path.basename(os.path.dirname(image_path))
            target_dir = os.path.join(output_dir, parent_dir_name)
            
            txt_dir = os.path.join(target_dir, "txt")
            json_dir = os.path.join(target_dir, "json")
            
            os.makedirs(txt_dir, exist_ok=True)
            os.makedirs(json_dir, exist_ok=True)
            
            # Save TXT
            txt_filename = f"{os.path.splitext(filename)[0]}_result.txt"
            txt_path = os.path.join(txt_dir, txt_filename)
            FileUtils.write_text_file(txt_path, full_text)
            
            # Save JSON
            json_filename = f"{os.path.splitext(filename)[0]}.json"
            json_path = os.path.join(json_dir, json_filename)
            FileUtils.write_json_file(json_path, result)
            
            # Update Records
            try:
                record_mgr = RecordManager.get_instance()
                record_mgr.add_record(image_path, output_path=json_path)
            except Exception as e:
                print(f"Failed to update record for {filename}: {e}")
                
            # Execute Callbacks (if any in options)
            options = result.get('options', {})
            callback = options.get('callback')
            if callback and callable(callback):
                try:
                    callback(result)
                except Exception as e:
                    print(f"Callback failed for {filename}: {e}")
                    
        else:
            # Handle Error
            error_msg = result.get('error_message', 'Unknown error')
            print(f"Processing failed for {filename}: {error_msg}")
            
            # Optionally save error log
            # ...

    def should_use_subprocess(self):
        """
        🔒 强制使用OCR子进程模式 - 完全移除主进程OCR处理
        
        这是系统的核心架构原则：所有OCR模型注册和调用都必须在独立的子进程中进行，
        主进程绝不直接处理OCR任务，确保资源隔离和稳定性。
        
        Returns:
            bool: 总是返回True，强制使用子进程模式
        """
        print(f"[DEBUG] 🔒 ARCHITECTURE ENFORCED: SUBPROCESS MODE ONLY")
        print(f"[DEBUG] 🚫 Main process OCR processing is COMPLETELY DISABLED")
        print(f"[DEBUG] ✅ All OCR operations MUST go through subprocess")
        return True
    
    def _convert_numpy_types(self, obj):
        """
        Recursively convert numpy types to Python native types for JSON serialization
        """
        if isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif hasattr(obj, 'item'):  # Numpy scalars
            return obj.item()
        elif hasattr(obj, 'tolist'):  # Numpy arrays
            return obj.tolist()
        else:
            return obj
