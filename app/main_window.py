# Path: src/app/main_window.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主窗口（集成所有UI组件和交互逻辑）
"""

import os
from datetime import datetime

from app.core.process_manager import ProcessManager

try:
    from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem
    from PyQt5.QtCore import QTimer, Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, using console mode")

from app.core.config_manager import ConfigManager
from app.core.task_manager import TaskManager
from app.core.result_manager import ResultManager
from app.ocr.detector import Detector
from app.ocr.recognizer import Recognizer
from app.ocr.post_processor import PostProcessor
from app.image.converter import Converter
from app.image.preprocessor import Preprocessor
from app.image.cropper import Cropper
from app.utils.file_utils import FileUtils
from app.utils.logger import Logger
from app.utils.performance import PerformanceMonitor


class MainWindow:
    def __init__(self, config_manager=None):
        """
        初始化主窗口

        Args:
            config_manager: 配置管理器（可选）
        """
        print("Initializing MainWindow")
        # 获取项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Project root in MainWindow: {self.project_root}")
        
        # 初始化目录路径
        self.input_dir = "input"
        self.output_dir = "output"
        
        # 初始化配置管理器
        if config_manager:
            self.config_manager = config_manager
        else:
            self.config_manager = ConfigManager(self.project_root)
            self.config_manager.load_config()
        
        self.task_manager = TaskManager()
        self.result_manager = ResultManager()
        self.logger = Logger(os.path.join(self.project_root, "logs", "ocr.log"))
        self.performance_monitor = PerformanceMonitor()
        
        # 初始化OCR组件
        self.detector = Detector(self.config_manager)
        self.recognizer = Recognizer(self.config_manager)
        self.post_processor = PostProcessor()
        
        # 初始化图像处理组件
        self.converter = Converter()
        self.preprocessor = Preprocessor()
        self.cropper = Cropper()
        
        # 初始化文件工具
        self.file_utils = FileUtils()
        
        # 初始化处理管理器
        self.process_manager = None
        
        # 初始化定时器用于更新UI
        self.update_timer = None
        
        # 初始化UI（如果可用）
        self.ui = None
        self.main_window = None
        if PYQT_AVAILABLE:
            try:
                from app.ui.ui_mainwindow import Ui_MainWindow
                self.main_window = QMainWindow()
                self.ui = Ui_MainWindow()
                self.ui.setup_ui(self.main_window)
                self._connect_signals()
                print("UI initialized successfully")
            except Exception as e:
                print(f"Error setting up UI: {e}")
                import traceback
                traceback.print_exc()
                self.ui = None

    def _connect_signals(self):
        """
        连接UI信号
        """
        print("Connecting UI signals")
        if self.ui and self.main_window:
            self.ui.input_button.clicked.connect(self._select_input_directory)
            self.ui.output_button.clicked.connect(self._select_output_directory)
            self.ui.start_button.clicked.connect(self._start_processing)
            self.ui.stop_button.clicked.connect(self._stop_processing)
            self.ui.model_selector.currentIndexChanged.connect(self._on_model_changed)
            print("UI signals connected")

    def _on_model_changed(self, index):
        """
        模型选择改变时的处理
        
        Args:
            index: 选中的索引
        """
        model_names = ["默认模型", "高精度模型", "快速模型"]
        if index >= 0 and index < len(model_names):
            model_name = model_names[index]
            self.logger.info(f"切换到模型: {model_name}")
            # 在这里可以根据选择的模型更新配置
            # 示例: self.config_manager.set_setting('selected_model', model_name)

    def run(self, input_dir, output_dir):
        """
        运行主窗口（命令行模式）

        Args:
            input_dir: 输入目录路径
            output_dir: 输出目录路径
        """
        print(f"MainWindow running with input_dir: {input_dir}, output_dir: {output_dir}")
        
        # 设置输入输出目录
        self.input_dir = input_dir
        self.output_dir = output_dir
        
        # 检查输入目录是否存在
        if not os.path.exists(input_dir):
            self.logger.error(f"Input directory does not exist: {input_dir}")
            return
            
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 直接处理图像（命令行模式）
        self._process_images(input_dir, output_dir)

    def show(self):
        """
        显示主窗口（GUI模式）
        """
        print("Showing main window")
        if self.ui and self.main_window and PYQT_AVAILABLE:
            # 更新UI显示初始目录
            self._update_ui_with_directories()
            
            # 启动定时器定期更新UI
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self._update_ui_status)
            self.update_timer.start(1000)  # 每秒更新一次
            
            self.main_window.show()
            print("Main window shown")
        else:
            print("Cannot show window: UI not available")

    def _update_ui_with_directories(self):
        """
        更新UI显示当前目录信息
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 更新状态栏显示目录信息
        status_text = f"输入目录: {self.input_dir} | 输出目录: {self.output_dir}"
        self.ui.status_label.setText(status_text)
        
        # 更新图像列表
        self._update_image_list()

    def _update_image_list(self):
        """
        更新图像列表显示
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 清空当前列表
        self.ui.image_list.clear()
        
        # 获取图像文件列表并添加到列表中
        if os.path.exists(self.input_dir):
            image_files = self.file_utils.get_image_files(self.input_dir)
            for image_file in image_files:
                self.ui.image_list.addItem(os.path.basename(image_file))

    def _update_ui_status(self):
        """
        定期更新UI状态
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 这里可以添加更多状态更新逻辑
        # 例如: 更新进度条、显示处理状态等
        pass

    def _select_input_directory(self):
        """
        选择输入目录
        """
        print("Selecting input directory")
        if PYQT_AVAILABLE and self.main_window:
            directory = QFileDialog.getExistingDirectory(self.main_window, "选择输入目录", self.input_dir)
            if directory:
                self.input_dir = directory
                print(f"Selected input directory: {directory}")
                self._update_ui_with_directories()

    def _select_output_directory(self):
        """
        选择输出目录
        """
        print("Selecting output directory")
        if PYQT_AVAILABLE and self.main_window:
            directory = QFileDialog.getExistingDirectory(self.main_window, "选择输出目录", self.output_dir)
            if directory:
                self.output_dir = directory
                print(f"Selected output directory: {directory}")
                self._update_ui_with_directories()

    def _open_settings_dialog(self):
        """
        打开设置对话框
        """
        if not PYQT_AVAILABLE:
            return
            
        try:
            from app.ui.dialogs.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self.config_manager, self.main_window)
            dialog.exec_()
            
            # 重新加载配置到相关组件
            self.detector = Detector(self.config_manager)
            self.recognizer = Recognizer(self.config_manager)
        except Exception as e:
            self.logger.error(f"打开设置对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"打开设置对话框失败: {e}")

    def _start_processing(self):
        """
        开始处理
        """
        print("Starting image processing")
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")

        # 检查输入目录是否存在
        if not os.path.exists(self.input_dir):
            self.logger.error(f"Input directory does not exist: {self.input_dir}")
            if PYQT_AVAILABLE and self.main_window:
                QMessageBox.warning(self.main_window, "警告", f"输入目录不存在: {self.input_dir}")
            return

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

        # 更新UI状态
        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(False)
            self.ui.stop_button.setEnabled(True)
            self.ui.status_label.setText("正在处理...")

        try:
            # 使用多进程架构开始处理
            self.process_manager = ProcessManager(self.config_manager)
            self.process_manager.start_processes()
            self.process_manager.add_input_directory(self.input_dir, self.output_dir)
            
            # 启动定时器检查处理进度
            if PYQT_AVAILABLE:
                self.check_progress_timer = QTimer()
                self.check_progress_timer.timeout.connect(self._check_processing_progress)
                self.check_progress_timer.start(1000)  # 每秒检查一次
                
        except Exception as e:
            self.logger.error(f"处理过程中发生错误: {e}")
            if PYQT_AVAILABLE and self.main_window:
                QMessageBox.critical(self.main_window, "错误", f"处理过程中发生错误: {e}")
            
            # 恢复UI状态
            if PYQT_AVAILABLE and self.ui:
                self.ui.start_button.setEnabled(True)
                self.ui.stop_button.setEnabled(False)
                self.ui.status_label.setText("处理失败")

    def _check_processing_progress(self):
        """
        检查处理进度并更新UI
        """
        if not PYQT_AVAILABLE or not self.ui:
            return
            
        # 这里可以添加具体的进度检查逻辑
        # 示例: 通过ProcessManager获取进度信息并更新进度条
        # self.ui.progress_bar.setValue(progress_value)
        
        # 如果处理已完成，则停止定时器并恢复UI状态
        # if processing_finished:
        #     self.check_progress_timer.stop()
        #     self.ui.start_button.setEnabled(True)
        #     self.ui.stop_button.setEnabled(False)
        #     self.ui.status_label.setText("处理完成")

    def _stop_processing(self):
        """
        停止处理
        """
        print("Stopping image processing")
        if hasattr(self, 'process_manager'):
            self.process_manager.stop_processes()
        else:
            self.task_manager.stop_worker()
            
        # 恢复UI状态
        if PYQT_AVAILABLE and self.ui:
            self.ui.start_button.setEnabled(True)
            self.ui.stop_button.setEnabled(False)
            self.ui.status_label.setText("处理已停止")

    def _process_images(self, input_dir, output_dir):
        """
        处理图像

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
        """
        print(f"Processing images from {input_dir} to {output_dir}")
        self.logger.info(f"开始处理目录: {input_dir}")
        self.performance_monitor.start_timer("total_processing")
        
        # 获取图像文件列表
        image_files = self.file_utils.get_image_files(input_dir)
        self.logger.info(f"找到 {len(image_files)} 个图像文件")
        print(f"Found {len(image_files)} image files")
        
        if not image_files:
            self.logger.warning("未找到图像文件")
            return
            
        # 更新进度条范围
        if PYQT_AVAILABLE and self.ui:
            self.ui.progress_bar.setMaximum(len(image_files))
            
        # 处理每个图像文件
        for i, image_path in enumerate(image_files):
            self.logger.info(f"处理图像 ({i+1}/{len(image_files)}): {image_path}")
            print(f"Processing image ({i+1}/{len(image_files)}): {image_path}")
            
            # 更新进度条
            if PYQT_AVAILABLE and self.ui:
                self.ui.progress_bar.setValue(i + 1)
                
            # 读取图像
            image = self.file_utils.read_image(image_path)
            if image is None:
                print(f"Failed to read image: {image_path}")
                continue
                
            # 预处理图像（可选）
            self.performance_monitor.start_timer("preprocessing")
            # 添加一个配置选项来控制是否进行预处理
            use_preprocessing = True  # 默认使用预处理
            if self.config_manager:
                use_preprocessing = self.config_manager.get_setting('use_preprocessing', True)
            
            if use_preprocessing:
                # 使用综合预处理流程并保存预处理后的图像
                preprocessed_filename = os.path.splitext(os.path.basename(image_path))[0]
                image = self.preprocessor.comprehensive_preprocess(image, output_dir, preprocessed_filename)
            else:
                print("Skipping preprocessing as per configuration")
            self.performance_monitor.stop_timer("preprocessing")
            
            # 检测文本区域（同时完成识别）
            self.performance_monitor.start_timer("detection")
            text_regions = self.detector.detect_text_regions(image)
            self.performance_monitor.stop_timer("detection")
            
            # 从检测结果中直接提取已识别的文本
            recognized_texts = []
            detailed_results = []
            
            # 直接使用检测器返回的识别结果
            for j, region in enumerate(text_regions):
                self.performance_monitor.start_timer("recognition")
                try:
                    # 获取识别的文本和置信度
                    text = region.get('text', '')
                    confidence = region.get('confidence', 0.0)
                    coordinates = region.get('coordinates', [])
                    
                    # 后处理
                    corrected_text = self.post_processor.correct_format(text)
                    corrected_text = self.post_processor.semantic_correction(corrected_text)
                    
                    # 保存识别结果
                    recognized_texts.append(corrected_text)
                    detailed_results.append({
                        'text': corrected_text,
                        'confidence': confidence,
                        'coordinates': coordinates,
                        'detection_confidence': confidence
                    })
                except Exception as e:
                    self.logger.error(f"Error processing region {j} in {image_path}: {e}")
                    print(f"Error processing region {j} in {image_path}: {e}")
                finally:
                    self.performance_monitor.stop_timer("recognition")
                
            # 合并所有识别结果
            full_text = "\n".join(recognized_texts)
            print(f"Full recognized text: {full_text}")
            
            # 保存结果到TXT文件
            output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}_result.txt")
            try:
                self.file_utils.write_text_file(output_file, full_text)
            except Exception as e:
                print(f"Warning: Failed to write TXT file {output_file}: {e}")
            
            # 保存详细的JSON结果文件（与源文件同名）
            json_output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}.json")
            try:
                json_result = {
                    'image_path': image_path,
                    'filename': os.path.basename(image_path),
                    'timestamp': datetime.now().isoformat(),
                    'full_text': full_text,
                    'regions': detailed_results
                }
                self.file_utils.write_json_file(json_output_file, json_result)
            except Exception as e:
                print(f"Warning: Failed to write JSON file {json_output_file}: {e}")
            
            # 存储到结果管理器
            self.result_manager.store_result(image_path, full_text)
            
            # 更新结果展示
            if PYQT_AVAILABLE and self.ui:
                self.ui.result_display.append(f"\n--- {os.path.basename(image_path)} ---\n{full_text}")
            
            self.logger.info(f"完成处理: {image_path}")
            print(f"Finished processing: {image_path}")
        
        # 导出所有结果
        export_path = self.result_manager.export_results(output_dir, 'json')
        print(f"Results exported to: {export_path}")
        
        total_time = self.performance_monitor.stop_timer("total_processing")
        self.logger.info(f"处理完成，总耗时: {total_time:.2f}秒")
        print(f"Total processing time: {total_time:.2f} seconds")
        
        # 更新UI状态
        if PYQT_AVAILABLE and self.ui:
            self.ui.status_label.setText(f"处理完成，总耗时: {total_time:.2f}秒")
        
        # 打印性能统计
        stats = self.performance_monitor.get_stats()
        for task, stat in stats.items():
            self.logger.info(f"{task}: 平均{stat['average']:.2f}秒, "
                           f"总计{stat['count']}次, "
                           f"总耗时{stat['total']:.2f}秒")
            print(f"{task}: 平均{stat['average']:.2f}秒, "
                  f"总计{stat['count']}次, "
                  f"总耗时{stat['total']:.2f}秒")

    def close(self):
        """
        关闭主窗口
        """
        print("Closing main window")
        # 停止所有任务
        self.task_manager.stop_worker()
        
        # 停止定时器
        if PYQT_AVAILABLE and hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
            
        if PYQT_AVAILABLE and hasattr(self, 'check_progress_timer') and self.check_progress_timer:
            self.check_progress_timer.stop()
            
        if self.ui and self.main_window and PYQT_AVAILABLE:
            self.main_window.close()
