# -*- coding: utf-8 -*-
"""
OCR 处理管线 - 极简封装

作用：封装 OCR 子进程调用和结果处理，提供单一接口

使用示例：
    pipeline = OCRPipeline(config_manager)
    result = pipeline.process(image_path)
    
优势：
    - 单一接口：调用方无需了解内部复杂结构
    - 减少耦合：各层组件只在管线内部引用
    - 易于测试：可以 Mock 整个管线或单独测试某层
"""

from typing import Optional, Dict, Any, List, Union, Callable
from PIL import Image
import os
import time  # 🔥 添加 time 导入用于事件时间戳

from app.core.process.subprocess.ocr_subprocess import get_ocr_subprocess_manager
from app.core.result.result_manager import ResultManager
from app.core.result.result_adapter import ResultAdapter
from app.log.log_bus import get_logger

# 🔥 引入事件总线支持
from app.event.event_bus import get_event_bus
from app.infrastructure.error_handler import handle_errors, ErrorCode


class OCRPipeline:
    """
    OCR 处理管线（极简版）
    
    封装了：OCR 子进程调用 + 结果适配 + 结果保存
    
    Attributes:
        config_manager: 配置管理器
        subprocess_manager: OCR 子进程管理器（单例）
        result_manager: 结果管理器
        event_bus: 事件总线（用于发射处理事件）
    """

    def __init__(self, config_manager):
        """
        初始化 OCR 管线
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.logger = get_logger()

        # 获取 OCR 子进程管理器（单例模式）
        self._subprocess_manager = None

        # 结果管理器
        self.result_manager = ResultManager()

        # 🔥 初始化事件总线
        self.event_bus = get_event_bus()

        # 降低日志级别，只在调试时显示初始化信息
        self.logger.debug("ocr_pipeline", "initialized", "OCR 处理管线初始化完成")

    @property
    def subprocess_manager(self):
        """延迟获取子进程管理器（单例模式）"""
        if self._subprocess_manager is None:
            self._subprocess_manager = get_ocr_subprocess_manager(self.config_manager)
        return self._subprocess_manager

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return={'error': 'OCR processing failed', 'full_text': '', 'regions': [], 'metadata': {}}, component="OCRPipeline")
    def process(
            self,
            image: Union[str, Image.Image],
            options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理单张图像
        
        Args:
            image: PIL Image 对象或文件路径
            options: 处理选项，可包含：
                - skip_preprocessing: 跳过预处理 (bool)
                - save_result: 是否保存结果 (bool)
                - image_path: 图像路径（用于结果索引）
                - output_dir: 输出目录
                - result_base_name: 结果文件名基础
                
        Returns:
            包含识别结果的字典：
                {
                    'full_text': str,           # 完整文本
                    'regions': List[Dict],      # 适配后的区域数据
                    'metadata': Dict,           # 元数据信息
                }
        """
        try:
            # 🔥 发射处理开始事件
            image_path_for_event = image if isinstance(image, str) else options.get('image_path', '<Image>')
            self.event_bus.processing.task_submitted.emit({
                'task_id': f"ocr_task_{hash(str(image))}",
                'image_path': image_path_for_event,
                'timestamp': time.time()
            })

            # 降低日志级别，只在调试时显示处理开始信息
            self.logger.debug("ocr_pipeline", "processing_start",
                              f"开始处理图像：{image if isinstance(image, str) else '<Image>'}")

            # ========== Step 1: 确保图像是 PIL Image ==========
            if isinstance(image, str):
                image = Image.open(image)

            # ========== Step 2: 调用 OCR 子进程 ==========
            ocr_result = self._execute_ocr(image, options or {})

            # ========== Step 3: 结果处理和保存 ==========
            final_result = self._finalize_result(ocr_result, image, options or {})

            # 🔥 发射处理完成事件
            self.event_bus.processing.task_completed.emit({
                'task_id': f"ocr_task_{hash(str(image))}",
                'image_path': image_path_for_event,
                'processing_time': time.time(),  # 这里应该是实际处理时间，简化处理
                'regions_count': len(final_result['regions']),
                'success': True
            })

            # 降低日志级别，只在调试时显示处理完成信息
            self.logger.debug("ocr_pipeline", "processing_complete",
                              f"处理完成，识别到 {len(final_result['regions'])} 个区域")

            return final_result

        except Exception as e:
            # 🔥 发射处理失败事件
            image_path_for_event = image if isinstance(image, str) else options.get('image_path', '<Image>')
            self.event_bus.processing.task_failed.emit({
                'task_id': f"ocr_task_{hash(str(image))}",
                'image_path': image_path_for_event,
                'error': str(e),
                'timestamp': time.time()
            })

            # 错误日志保持 info 级别，因为这是重要信息
            self.logger.error("ocr_pipeline", "processing_error",
                              f"处理失败：{e}")
            import traceback
            traceback.print_exc()

            return {
                'error': str(e),
                'full_text': '',
                'regions': [],
                'metadata': {}
            }

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return={'regions': [], 'metadata': {}}, component="OCRPipeline")
    def _execute_ocr(
            self,
            image: Image.Image,
            options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        OCR 层：执行文字识别
        
        通过子进程管理器调用 OCR 引擎
        """
        # 确保子进程已启动
        if not self.subprocess_manager.is_running():
            preset = self.config_manager.get_setting('current_ocr_preset', 'mobile')
            # 降低日志级别，只在调试时显示子进程启动信息
            self.logger.debug("ocr_pipeline", "starting_subprocess",
                             f"启动 OCR 子进程，预设：{preset}")
            self.subprocess_manager.start_process(preset)

        # 执行 OCR 识别
        # 降低日志级别，只在调试时显示 OCR 执行信息
        self.logger.debug("ocr_pipeline", "executing_ocr", "执行 OCR 识别")
        result = self.subprocess_manager.process_image(image, options)

        return result

    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return={'full_text': '', 'regions': [], 'metadata': {}}, component="OCRPipeline")
    def _finalize_result(
            self,
            ocr_result: Dict[str, Any],
            original_image: Image.Image,
            options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Result 层：结果适配和导出
        
        将 OCR 结果转换为标准格式并保存
        """
        # 1. 适配为标准格式
        regions = ocr_result.get('regions', [])
        adapted_regions = ResultAdapter.adapt(regions)

        # 降低日志级别，只在调试时显示结果适配信息
        self.logger.debug("ocr_pipeline", "adapting_result",
                          f"适配结果：{len(regions)} → {len(adapted_regions)} 项")

        # 2. 提取纯文本
        full_text = '\n'.join([r['text'] for r in adapted_regions if 'text' in r])

        # 3. 可选：保存结果
        if options.get('save_result', True):
            # 确定图像路径（用于结果索引）
            image_path = options.get('image_path', '')
            if not image_path and hasattr(original_image, 'filename'):
                image_path = original_image.filename

            if image_path:
                # 降低日志级别，只在调试时显示结果保存信息
                self.logger.debug("ocr_pipeline", "saving_result",
                                  f"保存结果到索引：{image_path}")
                self.result_manager.store_result(image_path, full_text)

        # 4. 组装最终结果
        return {
            'full_text': full_text,
            'regions': adapted_regions,
            'metadata': ocr_result.get('metadata', {})
        }

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=[], component="OCRPipeline")
    def batch_process(
            self,
            images: List[Union[str, Image.Image]],
            options: Optional[Dict[str, Any]] = None,
            progress_callback: Optional[Callable[[int, int], None]] = None,
            status_callback: Optional[Callable[[str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        批量处理图像（支持进度回调）
        
        Args:
            images: 图像列表（路径或 PIL Image 对象）
            options: 处理选项（应用到所有图像）
            progress_callback: 进度回调函数 (current, total) -> None
            status_callback: 状态更新回调函数 (message) -> None
            
        Returns:
            结果列表，每个元素包含：
                - success: bool, 是否成功
                - result: Dict, 成功时的结果
                - error: str, 失败时的错误信息
                - index: int, 图像索引
        """
        # 🔥 发射批量处理开始事件
        self.event_bus.processing.status_updated.emit(
            f"开始批量处理，共 {len(images)} 张图像", "working"
        )

        # 降低日志级别，只在调试时显示批量处理开始信息
        self.logger.debug("ocr_pipeline", "batch_start",
                         f"开始批量处理，共 {len(images)} 张图像")

        results = []
        base_options = options or {}
        total = len(images)

        for i, image in enumerate(images):
            try:
                # 为每张图像创建独立选项
                img_options = base_options.copy()
                img_options['image_path'] = image if isinstance(image, str) else f'image_{i}'

                # 更新状态（如果提供了回调）
                if status_callback:
                    filename = os.path.basename(image) if isinstance(image, str) else f'Image {i + 1}'
                    status_callback(f"正在处理 ({i + 1}/{total}): {filename}")

                # 处理图像
                result = self.process(image, img_options)

                results.append({
                    'success': 'error' not in result,
                    'result': result,
                    'index': i
                })

                # 更新进度（如果提供了回调）
                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                # 🔥 单个任务失败事件已经在 process 方法中处理
                # 降低日志级别，只在调试时显示批量处理中的错误
                self.logger.debug("ocr_pipeline", "batch_item_error",
                                  f"批量处理中第 {i} 张图像失败：{e}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'index': i
                })

                # 即使出错也要更新进度
                if progress_callback:
                    progress_callback(i + 1, total)

        success_count = sum(1 for r in results if r.get('success', False))
        
        # 🔥 发射批量处理完成事件
        self.event_bus.processing.processing_finished.emit(
            time.time()  # 这里应该是实际总耗时，简化处理
        )
        self.event_bus.processing.status_updated.emit(
            f"批量处理完成：{success_count}/{len(images)} 成功", "success"
        )

        # 降低日志级别，只在调试时显示批量处理完成信息
        self.logger.debug("ocr_pipeline", "batch_complete",
                         f"批量处理完成：{success_count}/{len(images)} 成功")

        return results

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="OCRPipeline")
    def cleanup(self):
        """
        清理资源
        
        停止子进程并释放资源
        """
        # 降低日志级别，只在调试时显示清理信息
        self.logger.debug("ocr_pipeline", "cleanup_start", "开始清理管线资源")

        if self._subprocess_manager and self._subprocess_manager.is_running():
            # 降低日志级别，只在调试时显示子进程停止信息
            self.logger.debug("ocr_pipeline", "stopping_subprocess", "停止 OCR 子进程")
            self._subprocess_manager.stop_process()

        # 降低日志级别，只在调试时显示清理完成信息
        self.logger.debug("ocr_pipeline", "cleanup_complete", "管线资源清理完成")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口 - 自动清理资源"""
        self.cleanup()
