# -*- coding: utf-8 -*-
"""
OCR 子进程管理器
负责管理独立的 OCR 处理进程，实现模型的隔离加载和生命周期控制
"""

import multiprocessing
import queue
import time
import traceback
import base64
import pickle
from typing import Dict, Any
import numpy as np
from PIL import Image
import io
from app.config.config_manager import ConfigManager
from app.log.log_bus import get_logger
from app.event.event_bus import get_event_bus
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()


class OCRWorkerProcess(multiprocessing.Process):
    """
    OCR 工作进程类
    在独立进程中运行 OCR 引擎，避免与主进程的资源冲突
    """

    def __init__(self, task_queue, result_queue, config_data, preset):
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.config_data = config_data
        self.preset = preset
        self.ocr_engine = None
        self.running = True

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="OCRWorkerProcess")
    def run(self):
        """
        进程主循环
        """
        try:
            logger.info("ocr_process_manager", "worker_started", f"OCR Worker Process started with preset: {self.preset}")
    
            # 初始化配置管理器（使用 deserialize 方法从序列化的数据恢复）
            config_manager = ConfigManager.deserialize(self.config_data)
    
            # 初始化 OCR 引擎（只初始化一次）
            from app.core.ocr.engine import OcrEngine
            self.ocr_engine = OcrEngine(
                config_manager=config_manager,
                preset=self.preset
            )
    
            logger.info("ocr_process_manager", "engine_initialized", "OCR Engine initialized in worker process")

            # 处理任务循环
            while self.running:
                task_id = None  # 初始化 task_id，避免未定义错误
                try:
                    # 设置超时以允许检查 running 状态
                    task_data = self.task_queue.get(timeout=1.0)
            
                    if task_data is None:  # 停止信号
                        logger.info("ocr_process_manager", "stop_signal_received", "Received stop signal, shutting down worker process")
                        break
            
                    task_id = task_data.get('task_id')
                    image_data = task_data.get('image_data')
                    options = task_data.get('options', {})
            
                    logger.debug("ocr_process_manager", "processing_task", f"Processing task {task_id} in worker process")
            
                    # 反序列化图像数据
                    image = self._deserialize_image(image_data)
            
                    # 执行 OCR 处理
                    start_time = time.time()
                    result = self.ocr_engine.process_image(image, options)
                    processing_time = time.time() - start_time
            
                    # 发送结果回主进程
                    result_data = {
                        'task_id': task_id,
                        'result': result,
                        'processing_time': processing_time,
                        'status': 'success'
                    }
            
                    self.result_queue.put(result_data)
                    logger.debug("ocr_process_manager", "task_completed", f"Task {task_id} completed in {processing_time:.2f}s")
            
                except queue.Empty:
                    # 超时继续循环，检查 running 状态
                    continue
                except Exception as e:
                    logger.error("ocr_process_manager", "task_error", f"Error processing task in worker: {e}")
                    traceback.print_exc()
            
                    # 发送错误结果（如果有 task_id）
                    if task_id is not None:
                        error_result = {
                            'task_id': task_id,
                            'result': None,
                            'error': str(e),
                            'status': 'error'
                        }
                        self.result_queue.put(error_result)

        except Exception as e:
            logger.error("ocr_process_manager", "fatal_error", f"Fatal error in OCR worker process: {e}")
            traceback.print_exc()
        finally:
            logger.info("ocr_process_manager", "worker_shutdown", "OCR Worker Process shutting down")

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="OCRWorkerProcess")
    def _deserialize_image(image_data):
        """
        反序列化图像数据
        支持多种格式：base64 编码、numpy 数组 pickle 序列化等
        """
        try:
            if isinstance(image_data, str):
                # base64 编码的图像
                image_bytes = base64.b64decode(image_data)
                return Image.open(io.BytesIO(image_bytes))
            elif isinstance(image_data, bytes):
                # 直接的字节数据
                return Image.open(io.BytesIO(image_data))
            elif isinstance(image_data, dict) and 'array' in image_data:
                # numpy 数组序列化
                array_data = pickle.loads(image_data['array'])
                return Image.fromarray(array_data)
            else:
                raise ValueError(f"Unsupported image data format: {type(image_data)}")
        except Exception as e:
            logger.error("ocr_process_manager", "deserialize_image_failed", f"Failed to deserialize image: {e}")
            raise


class OCRProcessManager:
    """
    OCR 进程管理器
    负责创建、管理和销毁 OCR 工作进程
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.worker_process = None
        self.task_queue = None
        self.result_queue = None
        self.current_preset = None
        self.task_counter = 0
        
        # 🔥 接入事件总线
        self.event_bus = get_event_bus()

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=False, component="OCRProcessManager")
    def start_worker(self, preset: str = 'mobile') -> bool:
        """
        启动 OCR 工作进程
        
        Args:
            preset: 预设配置 ('mobile' 或 'server')
            
        Returns:
            bool: 启动是否成功
        """
        try:
            # 如果已有进程在运行，先停止
            if self.worker_process and self.worker_process.is_alive():
                self.stop_worker()

            logger.info("ocr_process_manager", "starting_worker", f"Starting OCR worker process with preset: {preset}")

            # 创建队列
            self.task_queue = multiprocessing.Queue()
            self.result_queue = multiprocessing.Queue()

            # 获取配置数据（使用 serialize 方法）
            config_data = self.config_manager.serialize()

            # 创建并启动工作进程
            self.worker_process = OCRWorkerProcess(
                task_queue=self.task_queue,
                result_queue=self.result_queue,
                config_data=config_data,
                preset=preset
            )

            self.worker_process.start()
            self.current_preset = preset

            # 等待进程启动完成
            time.sleep(2)

            if self.worker_process.is_alive():
                logger.info("ocr_process_manager", "worker_started", "OCR worker process started successfully")
                
                # 🔥 发射事件：工作进程启动（高优先级）
                self.event_bus.processing.worker_started.emit({
                    'preset': preset,
                    'pid': self.worker_process.pid
                })
                
                return True
            else:
                logger.error("ocr_process_manager", "start_failed", "OCR worker process failed to start")
                return False

        except Exception as e:
            logger.error("ocr_process_manager", "start_error", f"Failed to start OCR worker process: {e}")
            traceback.print_exc()
            
            # 🔥 发射事件：工作进程启动失败（关键优先级）
            self.event_bus.processing.worker_start_failed.emit({
                'error': str(e),
                'preset': preset
            })
            
            return False

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="OCRProcessManager")
    def stop_worker(self):
        """
        停止 OCR 工作进程
        """
        try:
            if self.worker_process:
                logger.info("ocr_process_manager", "stopping_worker", "Stopping OCR worker process")

                # 发送停止信号
                if self.task_queue:
                    self.task_queue.put(None)

                # 等待进程结束
                self.worker_process.join(timeout=10)

                # 如果进程仍未结束，强制终止
                if self.worker_process.is_alive():
                    logger.warning("ocr_process_manager", "force_terminate", "Force terminating OCR worker process")
                    self.worker_process.terminate()
                    self.worker_process.join(timeout=5)

                self.worker_process = None
                self.current_preset = None
                logger.info("ocr_process_manager", "worker_stopped", "OCR worker process stopped")
                
                # 🔥 发射事件：工作进程停止（高优先级）
                self.event_bus.processing.worker_stopped.emit({
                    'reason': 'normal_shutdown',
                    'preset': preset_name if (preset_name := locals().get('preset_name')) else self.current_preset
                })

        except Exception as e:
            logger.error("ocr_process_manager", "stop_error", f"Error stopping OCR worker process: {e}")
            traceback.print_exc()

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=False, component="OCRProcessManager")
    def switch_preset(self, preset: str) -> bool:
        """
        切换 OCR 预设配置
        通过重启工作进程实现
        
        Args:
            preset: 新的预设配置
            
        Returns:
            bool: 切换是否成功
        """
        if preset == self.current_preset:
            logger.info("ocr_process_manager", "preset_unchanged", f"Already using preset: {preset}")
            return True

        logger.info("ocr_process_manager", "switching_preset", f"Switching OCR preset from {self.current_preset} to {preset}")
        
        old_preset = self.current_preset

        # 停止当前进程
        self.stop_worker()

        # 启动新进程
        success = self.start_worker(preset)
        
        if success:
            # 🔥 发射事件：预设切换成功（高优先级）
            self.event_bus.processing.preset_switched.emit({
                'old_preset': old_preset,
                'new_preset': preset
            })
        else:
            # 🔥 发射事件：预设切换失败（关键优先级）
            self.event_bus.processing.preset_switch_failed.emit({
                'error': 'Failed to start worker with new preset',
                'old_preset': old_preset,
                'new_preset': preset
            })
        
        return success

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return={'result': None, 'error': 'Subprocess processing failed', 'status': 'error'}, component="OCRProcessManager")
    def process_image(self, image, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理图像（通过子进程）
        
        Args:
            image: PIL Image 对象或 numpy 数组
            options: 处理选项
            
        Returns:
            Dict: 处理结果
        """
        try:
            # 确保工作进程在运行
            if not self.worker_process or not self.worker_process.is_alive():
                logger.warning("ocr_process_manager", "worker_not_running", "Worker process not running, starting with default preset")
                if not self.start_worker():
                    raise RuntimeError("Failed to start OCR worker process")

            # 生成任务 ID
            self.task_counter += 1
            task_id = f"task_{self.task_counter}_{int(time.time())}"

            # 序列化图像数据
            image_data = self._serialize_image(image)

            # 发送任务到工作进程
            task_data = {
                'task_id': task_id,
                'image_data': image_data,
                'options': options or {}
            }

            self.task_queue.put(task_data)
            logger.debug("ocr_process_manager", "task_sent", f"Sent task {task_id} to worker process")
            
            # 🔥 发射事件：任务提交（普通优先级）
            self.event_bus.processing.task_submitted.emit({
                'task_id': task_id,
                'image_path': getattr(image, 'filename', 'unknown') if hasattr(image, 'filename') else task_id
            })

            # 等待结果（带超时）
            try:
                result_data = self.result_queue.get(timeout=30)  # 30 秒超时

                if result_data.get('task_id') == task_id:
                    if result_data.get('status') == 'success':
                        logger.debug("ocr_process_manager", "result_received", f"Received successful result for task {task_id}")
                        
                        # 🔥 发射事件：任务完成（普通优先级）
                        self.event_bus.processing.task_completed.emit({
                            'task_id': task_id,
                            'processing_time': result_data.get('processing_time', 0)
                        })
                        
                        return result_data['result']
                    else:
                        error_msg = result_data.get('error', 'Unknown error')
                        
                        # 🔥 发射事件：任务失败（高优先级）
                        self.event_bus.processing.task_failed.emit({
                            'task_id': task_id,
                            'error': error_msg
                        })
                        
                        raise RuntimeError(f"OCR processing failed: {error_msg}")
                else:
                    raise RuntimeError("Task ID mismatch in result")

            except queue.Empty:
                raise TimeoutError("OCR processing timed out")

        except Exception as e:
            logger.error("ocr_process_manager", "process_image_error", f"Error processing image through subprocess: {e}")
            
            # 🔥 发射事件：任务处理异常（关键优先级）
            self.event_bus.processing.task_failed.emit({
                'task_id': task_id if 'task_id' in locals() else 'unknown',
                'error': str(e)
            })
            
            raise

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="OCRProcessManager")
    def _serialize_image(image):
        """
        序列化图像数据用于进程间传输
        """
        try:
            if isinstance(image, Image.Image):
                # 转换为 numpy 数组再序列化
                img_array = np.array(image)
                return {'array': pickle.dumps(img_array)}
            elif isinstance(image, np.ndarray):
                return {'array': pickle.dumps(image)}
            else:
                raise ValueError(f"Unsupported image type: {type(image)}")
        except Exception as e:
            logger.error("ocr_process_manager", "serialize_image_failed", f"Failed to serialize image: {e}")
            raise

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={'worker_running': False, 'current_preset': None, 'pid': None, 'queue_sizes': {'task_queue': 0, 'result_queue': 0}}, component="OCRProcessManager")
    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态信息
        """
        return {
            'worker_running': self.worker_process is not None and self.worker_process.is_alive(),
            'current_preset': self.current_preset,
            'pid': self.worker_process.pid if self.worker_process else None,
            'queue_sizes': {
                'task_queue': self.task_queue.qsize() if self.task_queue else 0,
                'result_queue': self.result_queue.qsize() if self.result_queue else 0
            }
        }

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="OCRProcessManager")
    def cleanup(self):
        """
        清理资源
        """
        self.stop_worker()
        if self.task_queue:
            self.task_queue.close()
        if self.result_queue:
            self.result_queue.close()
