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
        
        # 启动输入进程
        self._start_input_process()
        
        # 启动处理进程（可以有多个）
        num_processing_processes = self.config_manager.get_setting('processing_processes', 2) if self.config_manager else 2
        for i in range(num_processing_processes):
            self._start_processing_process(i)
        
        # 启动输出进程
        self._start_output_process()
        
        print("All processes started")

    def stop_processes(self):
        """
        停止所有线程
        """
        print("Stopping all threads")
        self.running = False
        
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
        self.processes[f'processing-{index}'] = thread
        print(f"Processing thread {index} started")

    def _start_output_process(self):
        """
        启动输出线程
        """
        thread = threading.Thread(target=self._output_worker, name="OutputThread")
        thread.daemon = True  # 设置为守护线程
        thread.start()
        self.processes['output'] = thread
        print("Output thread started")

    def _input_worker(self):
        """
        输入线程工作函数
        负责扫描输入目录并添加图像文件到处理队列
        """
        print("Input worker started")
        from app.utils.file_utils import FileUtils
        
        while self.running:
            try:
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
                            processing_task = {
                                'image_path': image_path,
                                'output_dir': output_dir,
                                'input_dir': input_dir
                            }
                            self.queues['processing'].put(processing_task)
                            print(f"Added to processing queue: {image_path}")
                except queue.Empty:
                    # 没有任务时短暂休眠，避免过度占用CPU
                    time.sleep(0.1)
                except Exception as e:
                    if self.running:  # 只在仍在运行时打印错误
                        print(f"Error in input worker task processing: {e}")
                
            except Exception as e:
                if self.running:  # 只在仍在运行时打印错误
                    print(f"Error in input worker: {e}")
        
        print("Input worker stopped")

    def _processing_worker(self, index):
        """
        处理线程工作函数
        负责执行OCR处理

        Args:
            index: 线程索引
        """
        print(f"Processing worker {index} started")
        
        # 导入必要的模块
        try:
            from app.image.preprocessor import Preprocessor
            from app.ocr.detector import Detector
            from app.ocr.recognizer import Recognizer
            from app.ocr.post_processor import PostProcessor
            from app.image.cropper import Cropper
            from app.core.config_manager import ConfigManager
            import numpy as np
        except Exception as e:
            if self.running:
                print(f"Error importing modules in processing worker {index}: {e}")
            return
        
        # 为每个线程创建独立的配置管理器和处理组件
        try:
            config_manager = ConfigManager()
            config_manager.load_config()
            
            preprocessor = Preprocessor()
            detector = Detector(config_manager)
            recognizer = Recognizer(config_manager)
            post_processor = PostProcessor()
            cropper = Cropper()
        except Exception as e:
            if self.running:
                print(f"Error initializing components in processing worker {index}: {e}")
                print(traceback.format_exc())
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
                
                # 检查处理任务
                try:
                    task = self.queues['processing'].get(timeout=0.1)
                    image_path = task['image_path']
                    output_dir = task['output_dir']
                    
                    print(f"Processing worker {index} processing: {image_path}")
                    
                    # 读取图像
                    try:
                        image = Image.open(image_path)
                    except Exception as e:
                        if self.running:
                            print(f"Error reading image {image_path}: {e}")
                        continue
                    
                    # 预处理
                    try:
                        filename = os.path.splitext(os.path.basename(image_path))[0]
                        image = preprocessor.comprehensive_preprocess(image, output_dir, filename)
                    except Exception as e:
                        if self.running:
                            print(f"Error preprocessing image {image_path}: {e}")
                    
                    # 检测文本区域
                    try:
                        text_regions = detector.detect_text_regions(image)
                    except Exception as e:
                        if self.running:
                            print(f"Error detecting text regions in {image_path}: {e}")
                            print(traceback.format_exc())
                        text_regions = []
                    
                    # 识别每个文本区域
                    recognized_texts = []
                    detailed_results = []
                    for j, region in enumerate(text_regions):
                        if not self.running:  # 检查是否应该停止
                            break
                        try:
                            # 获取识别的文本和置信度
                            text = region.get('text', '')
                            confidence = region.get('confidence', 0.0)
                            coordinates = region.get('coordinates', [])
                            
                            # 将numpy数组转换为列表，确保可以JSON序列化
                            if hasattr(coordinates, 'tolist'):
                                coordinates = coordinates.tolist()
                            
                            # 后处理
                            corrected_text = post_processor.correct_format(text)
                            corrected_text = post_processor.semantic_correction(corrected_text)
                            
                            # 保存识别结果
                            recognized_texts.append(corrected_text)
                            detailed_results.append({
                                'text': corrected_text,
                                'confidence': float(confidence),  # 确保是Python原生类型
                                'coordinates': coordinates,
                                'detection_confidence': float(confidence)  # 确保是Python原生类型
                            })
                        except Exception as e:
                            if self.running:
                                print(f"Error processing region {j} in {image_path}: {e}")
                    
                    # 合并所有识别结果
                    full_text = "\n".join(recognized_texts)
                    
                    # 创建结果
                    result = {
                        'image_path': image_path,
                        'filename': os.path.basename(image_path),
                        'timestamp': datetime.now().isoformat(),
                        'full_text': full_text,
                        'regions': detailed_results,
                        'output_dir': output_dir
                    }
                    
                    # 确保所有numpy数据类型都转换为Python原生类型
                    def convert_numpy_types(obj):
                        if isinstance(obj, dict):
                            return {key: convert_numpy_types(value) for key, value in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_numpy_types(item) for item in obj]
                        elif hasattr(obj, 'item'):  # numpy标量类型
                            return obj.item()
                        else:
                            return obj
                    
                    result = convert_numpy_types(result)
                    
                    # 添加到输出队列
                    if self.running:
                        self.queues['output'].put(result)
                    print(f"Processing worker {index} finished: {image_path}")
                    
                except queue.Empty:
                    # 没有任务时短暂休眠，避免过度占用CPU
                    time.sleep(0.01)
                except Exception as e:
                    if self.running:
                        print(f"Error processing task in worker {index}: {e}")
                        print(traceback.format_exc())
                        
            except Exception as e:
                if self.running:
                    print(f"Error in processing worker {index}: {e}")
                    print(traceback.format_exc())
        
        print(f"Processing worker {index} stopped")

    def _output_worker(self):
        """
        输出线程工作函数
        负责保存处理结果
        """
        print("Output worker started")
        from app.utils.file_utils import FileUtils
        
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
                    
                    print(f"Output worker saving results for: {filename}")
                    
                    # 保存结果到TXT文件
                    try:
                        output_file = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_result.txt")
                        FileUtils.write_text_file(output_file, full_text)
                    except Exception as e:
                        if self.running:
                            print(f"Error writing TXT file for {filename}: {e}")
                    
                    # 保存详细的JSON结果文件
                    try:
                        json_output_file = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
                        FileUtils.write_json_file(json_output_file, result)
                    except Exception as e:
                        if self.running:
                            print(f"Error writing JSON file for {filename}: {e}")
                            
                except queue.Empty:
                    # 没有任务时短暂休眠，避免过度占用CPU
                    time.sleep(0.01)
                except Exception as e:
                    if self.running:
                        print(f"Error in output worker task processing: {e}")
                    
            except Exception as e:
                if self.running:
                    print(f"Error in output worker: {e}")
        
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
