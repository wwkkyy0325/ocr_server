# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：提供面向任务队列的异步 OCR 调度与状态管理，支持优先级、输出与控制通道
# - 核心实现：以 PriorityQueue/Queue 组合实现生产者 - 消费者模型，集中提交/执行任务并与 OcrEngine 协同处理
# - 关联关系：由上层控制器调用以批量提交任务，与 ConfigManager 协作读取配置与缓存，最终产出交由 ResultManager/前端消费

"""
进程管理器（重构版）
负责管理 OCR 处理任务，使用 PriorityQueue 进行任务调度，支持多线程处理。
"""

import os
import time
import queue
import json
import threading
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.config.config_manager import ConfigManager
from app.infrastructure.file_utils import FileUtils
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

# Try importing OcrEngine, handle potential import errors gracefully if needed
try:
    from app.core.ocr.engine import OcrEngine
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

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessManager")
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

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessManager")
    def submit_tasks(self, files: List[str], options: Dict[str, Any], priority: int = 10):
        """
        提交任务到处理队列

        Args:
            files: 图片文件路径列表
            options: 处理选项，必须包含 'output_dir'
            priority: 优先级 (默认 10，越小优先级越高)
        """
        logger = get_logger()
        
        if not files:
            logger.debug("process_manager", "no_files", "未提供文件列表")
            return

        output_dir = options.get('output_dir')
        if not output_dir:
            logger.warning("process_manager", "no_output_dir", "未指定输出目录，使用默认值 'outputs'")
            output_dir = 'outputs'
            options['output_dir'] = output_dir  # Update options

        count = 0
        for file_path in files:
            if not os.path.exists(file_path):
                continue

            self.submit_task(file_path, options, priority)
            count += 1

        logger.info("process_manager", "tasks_submitted", f"已提交 {count} 个任务，优先级 {priority}")

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessManager")
    def submit_task(self, file_path: str, options: Dict[str, Any], priority: int = 10):
        """
        提交单个任务到处理队列
        """
        logger = get_logger()
        
        # Check existence, handling virtual paths like "path/to/pdf|page=1"
        check_path = file_path
        if "|page=" in file_path:
            check_path = file_path.split("|page=")[0]

        if not os.path.exists(check_path):
            logger.warning("process_manager", "file_not_found", f"文件不存在：{check_path}")
            return

        output_dir = options.get('output_dir', 'outputs')

        # Construct task
        task = {
            'image_path': file_path,
            'options': options,
            'output_dir': output_dir,  # Ensure output_dir is accessible
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
        logger = get_logger()
        logger.debug("process_manager", "queue_cleared", "处理队列已清空")

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessManager")
    def process_directory(self, input_dir: str, output_dir: str, options: Dict[str, Any] = None, priority: int = 10):
        """
        扫描目录并提交任务 (Wrapper around submit_tasks)
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            options: 其他选项
            priority: 优先级
        """
        logger = get_logger()
        
        if options is None:
            options = {}

        # Ensure output_dir is in options
        options['output_dir'] = output_dir

        # Scan for images
        try:
            image_files = FileUtils.get_image_files(input_dir)
            logger.info("process_manager", "directory_scanned", f"扫描目录 {input_dir}: 找到 {len(image_files)} 张图片")

            # Submit tasks
            self.submit_tasks(image_files, options, priority)

        except Exception as e:
            logger.error("process_manager", "directory_error", f"处理目录 {input_dir} 时出错：{e}")
            traceback.print_exc()

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="ProcessManager")
    def start_processes(self):
        """
        启动所有工作线程
        """
        logger = get_logger()
        
        if self.running:
            logger.debug("process_manager", "already_running", "Processes already running")
            return

        logger.info("process_manager", "starting_workers", "Starting ProcessManager workers...")
        self.running = True

        # Start Output Worker
        self._start_output_worker()

        # Start Processing Workers
        # User Request: Use single thread structure to save memory
        # Force num_workers to 1 regardless of config (Config 'processing_processes' is deprecated)
        num_workers = 1

        for i in range(num_workers):
            self._start_processing_worker(i)

        logger.info("process_manager", "workers_started", f"Started {num_workers} processing worker (Single-Thread Mode) and 1 output worker")

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="ProcessManager")
    def stop_processes(self):
        """
        停止所有工作线程
        """
        logger = get_logger()
        
        logger.info("process_manager", "stopping_workers", "Stopping ProcessManager workers...")
        self.running = False

        # Send STOP signal to control queue (enough for all workers)
        # Note: Workers check self.running first, but control queue helps wake them up if blocked
        for _ in range(len(self.processes) * 2):
            self.queues['control'].put('STOP')

        # Wait for threads to finish
        for name, thread in self.processes.items():
            if thread.is_alive():
                logger.debug("process_manager", "waiting_thread", f"Waiting for {name} to stop...")
                thread.join(timeout=2.0)

        self.processes.clear()

        # Update status
        with self._status_lock:
            for key in self._service_status:
                self._service_status[key]['status'] = 'stopped'

        logger.info("process_manager", "workers_stopped", "All workers stopped")

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

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ProcessManager")
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

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={}, component="ProcessManager")
    def get_service_status(self):
        with self._status_lock:
            return json.loads(json.dumps(self._service_status))

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessManager")
    def _processing_worker(self, index):
        """
        Worker thread that processes OCR tasks
        """
        logger = get_logger()
        name = f"ProcessingWorker-{index}"
        logger.info("process_manager", "worker_started", f"{name} started")

        # OCR 引擎完全移至子进程 - 主进程不初始化任何 OCR 组件
        logger.debug("process_manager", "subprocess_only", f"{name}: OCR processing delegated to subprocess only")

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

                    # Use context manager to ensure file is closed Note: FileUtils.read_image returns an open PIL
                    # Image object which supports context manager protocol
                    with image:
                        logger.debug("process_manager", "subprocess_mode", "[DEBUG] 🔒 FORCING SUBPROCESS MODE - Main process OCR DISABLED")
                        # 完全移除主进程 OCR 引擎 - 所有处理都在子进程中进行
                        try:
                            from app.core.process.subprocess.ocr_subprocess import get_ocr_subprocess_manager
                            subprocess_manager = get_ocr_subprocess_manager(self.config_manager)

                            # 确保子进程在运行
                            if not subprocess_manager.is_running():
                                current_preset = self.config_manager.get_setting('current_ocr_preset', 'mobile')
                                logger.info("process_manager", "starting_subprocess", f"{name}: 🚀 Starting OCR subprocess with preset: {current_preset}")
                                success = subprocess_manager.start_process(current_preset)
                                if not success:
                                    raise RuntimeError("Failed to start OCR subprocess")
                                logger.info("process_manager", "subprocess_started", f"{name}: ✅ OCR subprocess started successfully")
                            else:
                                logger.debug("process_manager", "subprocess_running", f"{name}: ✅ OCR subprocess already running")

                            # 在子进程中处理图像
                            logger.debug("process_manager", "processing_image", f"{name}: 🔄 Sending image to OCR subprocess for processing...")
                            ocr_result = subprocess_manager.process_image(image, options)
                            logger.info("process_manager", "image_processed", f"{name}: ✅ Image processed successfully in OCR subprocess")

                        except Exception as e:
                            logger.error("process_manager", "subprocess_failed", f"{name}: ❌ OCR subprocess processing failed: {e}")
                            logger.error("process_manager", "no_fallback", f"{name}: ⛔ Main process OCR is COMPLETELY DISABLED - NO FALLBACK")
                            raise RuntimeError(f"OCR 子进程处理失败，主进程 OCR 已完全禁用：{e}")

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
                    logger.error("process_manager", "processing_error", f"{name}: Error processing {image_path}: {e}")
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
                logger.error("process_manager", "worker_loop_error", f"{name} loop error: {e}")
                traceback.print_exc()
                self._update_status(name, 'error', str(e))
                time.sleep(1)  # Prevent tight loop on repeated errors

        logger.info("process_manager", "worker_stopped", f"{name} stopped")
        self._update_status(name, 'stopped')

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="ProcessManager")
    def _output_worker(self):
        """
        Worker thread that handles output (saving files, callbacks)
        """
        logger = get_logger()
        name = "OutputWorker"
        logger.info("process_manager", "worker_started", f"{name} started")

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
                    logger.error("process_manager", "result_handling_error", f"{name}: Error handling result: {e}")
                    traceback.print_exc()
                    self._update_status(name, 'running', str(e))

            except Exception as e:
                logger.error("process_manager", "worker_loop_error", f"{name} loop error: {e}")
                self._update_status(name, 'error', str(e))
                time.sleep(1)

        logger.info("process_manager", "worker_stopped", f"{name} stopped")
        self._update_status(name, 'stopped')

    @handle_errors(error_code=ErrorCode.RESULT_EXPORT_001, fallback_return=None, component="ProcessManager")
    @staticmethod
    def _handle_result(result: Dict[str, Any]):
        """
        Save results and handle callbacks
        """
        logger = get_logger()
        
        status = result.get('status')
        image_path = result.get('image_path')
        filename = result.get('filename')
        output_dir = result.get('output_dir')

        if not output_dir:
            return

        # Handle successful processing
        if status == 'success':

            # Determine subdirectories
            # If the image was in a subdirectory of the input root, we might want to mirror that structure.
            # For now, we follow the simple logic: output_dir/parent_dir_name/

            parent_dir_name = os.path.basename(os.path.dirname(image_path))
            target_dir = os.path.join(output_dir, parent_dir_name)

            msgpack_dir = os.path.join(target_dir, "msgpack")

            os.makedirs(msgpack_dir, exist_ok=True)

            # Save MessagePack
            msgpack_filename = f"{os.path.splitext(filename)[0]}.msgpack"
            msgpack_path = os.path.join(msgpack_dir, msgpack_filename)
            from app.infrastructure.message_pack_serializer import MessagePackSerializer
            MessagePackSerializer.save_to_file(result, msgpack_path)

            # Execute Callbacks (if any in options)
            options = result.get('options', {})
            callback = options.get('callback')
            if callback and callable(callback):
                try:
                    callback(result)
                except Exception as e:
                    logger.error("process_manager", "callback_failed", f"Callback failed for {filename}: {e}")

        else:
            # Handle Error
            error_msg = result.get('error_message', 'Unknown error')
            logger.error("process_manager", "processing_failed", f"Processing failed for {filename}: {error_msg}")

            # Optionally save error log
            # ...

    @staticmethod
    def should_use_subprocess():
        """
        🔒 强制使用 OCR 子进程模式 - 完全移除主进程 OCR 处理
        
        这是系统的核心架构原则：所有 OCR 模型注册和调用都必须在独立的子进程中进行，
        主进程绝不直接处理 OCR 任务，确保资源隔离和稳定性。
        
        Returns:
            bool: 总是返回 True，强制使用子进程模式
        """
        logger = get_logger()
        logger.debug("process_manager", "subprocess_enforced", f"[DEBUG] 🔒 ARCHITECTURE ENFORCED: SUBPROCESS MODE ONLY")
        logger.debug("process_manager", "main_disabled", f"[DEBUG] 🚫 Main process OCR processing is COMPLETELY DISABLED")
        logger.debug("process_manager", "subprocess_required", f"[DEBUG] ✅ All OCR operations MUST go through subprocess")
        return True

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={}, component="ProcessManager")
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
