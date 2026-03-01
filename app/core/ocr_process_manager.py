# -*- coding: utf-8 -*-
"""
OCR子进程管理器
负责管理独立的OCR处理进程，实现模型的隔离加载和生命周期控制
"""

import multiprocessing
import queue
import time
import traceback
import json
import base64
import pickle
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image
import io

from app.core.config_manager import ConfigManager
from app.utils.logger import Logger

logger = Logger()

class OCRWorkerProcess(multiprocessing.Process):
    """
    OCR工作进程类
    在独立进程中运行OCR引擎，避免与主进程的资源冲突
    """
    
    def __init__(self, task_queue, result_queue, config_data, preset):
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.config_data = config_data
        self.preset = preset
        self.ocr_engine = None
        self.running = True
        
    def run(self):
        """
        进程主循环
        """
        try:
            logger.info(f"OCR Worker Process started with preset: {self.preset}")
            
            # 初始化配置管理器
            config_manager = ConfigManager()
            config_manager.load_from_dict(self.config_data)
            
            # 初始化OCR引擎（只初始化一次）
            from app.ocr.engine import OcrEngine
            self.ocr_engine = OcrEngine(
                config_manager=config_manager,
                detector=None,
                recognizer=None,
                preset=self.preset
            )
            
            logger.info("OCR Engine initialized in worker process")
            
            # 处理任务循环
            while self.running:
                try:
                    # 设置超时以允许检查running状态
                    task_data = self.task_queue.get(timeout=1.0)
                    
                    if task_data is None:  # 停止信号
                        logger.info("Received stop signal, shutting down worker process")
                        break
                        
                    task_id = task_data.get('task_id')
                    image_data = task_data.get('image_data')
                    options = task_data.get('options', {})
                    
                    logger.debug(f"Processing task {task_id} in worker process")
                    
                    # 反序列化图像数据
                    image = self._deserialize_image(image_data)
                    
                    # 执行OCR处理
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
                    logger.debug(f"Task {task_id} completed in {processing_time:.2f}s")
                    
                except queue.Empty:
                    # 超时继续循环，检查running状态
                    continue
                except Exception as e:
                    logger.error(f"Error processing task in worker: {e}")
                    traceback.print_exc()
                    
                    # 发送错误结果
                    if 'task_id' in locals():
                        error_result = {
                            'task_id': task_id,
                            'result': None,
                            'error': str(e),
                            'status': 'error'
                        }
                        self.result_queue.put(error_result)
                        
        except Exception as e:
            logger.error(f"Fatal error in OCR worker process: {e}")
            traceback.print_exc()
        finally:
            logger.info("OCR Worker Process shutting down")
    
    def _deserialize_image(self, image_data):
        """
        反序列化图像数据
        支持多种格式：base64编码、numpy数组pickle序列化等
        """
        try:
            if isinstance(image_data, str):
                # base64编码的图像
                image_bytes = base64.b64decode(image_data)
                return Image.open(io.BytesIO(image_bytes))
            elif isinstance(image_data, bytes):
                # 直接的字节数据
                return Image.open(io.BytesIO(image_data))
            elif isinstance(image_data, dict) and 'array' in image_data:
                # numpy数组序列化
                array_data = pickle.loads(image_data['array'])
                return Image.fromarray(array_data)
            else:
                raise ValueError(f"Unsupported image data format: {type(image_data)}")
        except Exception as e:
            logger.error(f"Failed to deserialize image: {e}")
            raise

class OCRProcessManager:
    """
    OCR进程管理器
    负责创建、管理和销毁OCR工作进程
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.worker_process = None
        self.task_queue = None
        self.result_queue = None
        self.current_preset = None
        self.task_counter = 0
        
    def start_worker(self, preset: str = 'mobile') -> bool:
        """
        启动OCR工作进程
        
        Args:
            preset: 预设配置 ('mobile' 或 'server')
            
        Returns:
            bool: 启动是否成功
        """
        try:
            # 如果已有进程在运行，先停止
            if self.worker_process and self.worker_process.is_alive():
                self.stop_worker()
            
            logger.info(f"Starting OCR worker process with preset: {preset}")
            
            # 创建队列
            self.task_queue = multiprocessing.Queue()
            self.result_queue = multiprocessing.Queue()
            
            # 获取配置数据
            config_data = self.config_manager.to_dict()
            
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
                logger.info("OCR worker process started successfully")
                return True
            else:
                logger.error("OCR worker process failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start OCR worker process: {e}")
            traceback.print_exc()
            return False
    
    def stop_worker(self):
        """
        停止OCR工作进程
        """
        try:
            if self.worker_process:
                logger.info("Stopping OCR worker process")
                
                # 发送停止信号
                if self.task_queue:
                    self.task_queue.put(None)
                
                # 等待进程结束
                self.worker_process.join(timeout=10)
                
                # 如果进程仍未结束，强制终止
                if self.worker_process.is_alive():
                    logger.warning("Force terminating OCR worker process")
                    self.worker_process.terminate()
                    self.worker_process.join(timeout=5)
                
                self.worker_process = None
                self.current_preset = None
                logger.info("OCR worker process stopped")
                
        except Exception as e:
            logger.error(f"Error stopping OCR worker process: {e}")
            traceback.print_exc()
    
    def switch_preset(self, preset: str) -> bool:
        """
        切换OCR预设配置
        通过重启工作进程实现
        
        Args:
            preset: 新的预设配置
            
        Returns:
            bool: 切换是否成功
        """
        if preset == self.current_preset:
            logger.info(f"Already using preset: {preset}")
            return True
            
        logger.info(f"Switching OCR preset from {self.current_preset} to {preset}")
        
        # 停止当前进程
        self.stop_worker()
        
        # 启动新进程
        return self.start_worker(preset)
    
    def process_image(self, image, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理图像（通过子进程）
        
        Args:
            image: PIL Image对象或numpy数组
            options: 处理选项
            
        Returns:
            Dict: 处理结果
        """
        try:
            # 确保工作进程在运行
            if not self.worker_process or not self.worker_process.is_alive():
                logger.warning("Worker process not running, starting with default preset")
                if not self.start_worker():
                    raise RuntimeError("Failed to start OCR worker process")
            
            # 生成任务ID
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
            logger.debug(f"Sent task {task_id} to worker process")
            
            # 等待结果（带超时）
            try:
                result_data = self.result_queue.get(timeout=30)  # 30秒超时
                
                if result_data.get('task_id') == task_id:
                    if result_data.get('status') == 'success':
                        logger.debug(f"Received successful result for task {task_id}")
                        return result_data['result']
                    else:
                        error_msg = result_data.get('error', 'Unknown error')
                        raise RuntimeError(f"OCR processing failed: {error_msg}")
                else:
                    raise RuntimeError("Task ID mismatch in result")
                    
            except queue.Empty:
                raise TimeoutError("OCR processing timed out")
                
        except Exception as e:
            logger.error(f"Error processing image through subprocess: {e}")
            raise
    
    def _serialize_image(self, image):
        """
        序列化图像数据用于进程间传输
        """
        try:
            if isinstance(image, Image.Image):
                # 转换为numpy数组再序列化
                img_array = np.array(image)
                return {'array': pickle.dumps(img_array)}
            elif isinstance(image, np.ndarray):
                return {'array': pickle.dumps(image)}
            else:
                raise ValueError(f"Unsupported image type: {type(image)}")
        except Exception as e:
            logger.error(f"Failed to serialize image: {e}")
            raise
    
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
    
    def cleanup(self):
        """
        清理资源
        """
        self.stop_worker()
        if self.task_queue:
            self.task_queue.close()
        if self.result_queue:
            self.result_queue.close()
