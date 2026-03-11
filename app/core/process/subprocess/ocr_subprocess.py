# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：以独立子进程承载 OCR 模型，隔离主进程并提升稳定性；提供跨进程通信接口
# - 核心实现：multiprocessing 队列请求/响应、延迟加载 OcrEngine，支持预设切换与状态查询
# - 关联关系：由 ProcessingController/OcrEngine 通过 get_ocr_subprocess_manager 获取实例进行处理调用

import multiprocessing
import pickle
import io
import traceback
import time
import queue
import numpy as np
from PIL import Image
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

# 全局子进程管理器实例
_subprocess_manager = None


class OCRSubprocessManager:
    """OCR 子进程管理器 - 负责模型的生命周期管理和进程间通信"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.process = None
        self.input_queue = None
        self.output_queue = None
        self.error_queue = None
        self.current_preset = None
        self.is_initialized = False

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=False, component="OCRSubprocessManager")
    def start_process(self, preset='mobile'):
        """启动 OCR 子进程"""
        logger = get_logger()
        
        if self.is_running():
            self.stop_process()

        try:
            # 创建进程间通信队列
            self.input_queue = multiprocessing.Queue()
            self.output_queue = multiprocessing.Queue()
            self.error_queue = multiprocessing.Queue()

            # 启动子进程
            self.process = multiprocessing.Process(
                target=self._ocr_worker,
                args=(self.input_queue, self.output_queue, self.error_queue,
                      self.config_manager.serialize(), preset),
                daemon=True
            )
            self.process.start()

            self.current_preset = preset
            self.is_initialized = True

            # 等待初始化完成
            timeout = 30  # 30 秒超时
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    if not self.error_queue.empty():
                        error_msg = self.error_queue.get_nowait()
                        raise RuntimeError(f"子进程初始化失败：{error_msg}")

                    if not self.output_queue.empty():
                        response = self.output_queue.get_nowait()
                        if response.get('type') == 'initialized':
                            logger.info("ocr_subprocess", "initialized", f"OCR 子进程初始化成功，预设：{preset}")
                            return True
                except queue.Empty:
                    pass

                time.sleep(0.1)

            raise TimeoutError("子进程初始化超时")

        except Exception as e:
            logger.error("ocr_subprocess", "start_failed", f"启动 OCR 子进程失败：{e}")
            self.cleanup()
            return False

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="OCRSubprocessManager")
    def stop_process(self):
        """停止 OCR 子进程"""
        logger = get_logger()

        if self.is_running():
            logger.info("ocr_subprocess", "stopping", f"开始停止子进程 PID: {self.process.pid}")
            try:
                # 发送停止信号
                if self.input_queue:
                    self.input_queue.put({'command': 'stop'})

                # 等待正常退出
                self.process.join(timeout=3)

                if self.process.is_alive():
                    logger.debug("ocr_subprocess", "sending_terminate", "子进程未正常退出，发送终止信号")
                    self.process.terminate()
                    self.process.join(timeout=2)

                if self.process.is_alive():
                    logger.warning("ocr_subprocess", "killing_process", "子进程仍未退出，强制杀死")
                    self.process.kill()
                    self.process.join(timeout=1)

                logger.info("ocr_subprocess", "stopped", f"子进程停止完成 PID: {self.process.pid}")
            except Exception as e:
                logger.error("ocr_subprocess", "stop_error", f"停止子进程时出错：{e}")
                import traceback
                traceback.print_exc()
            finally:
                self.cleanup()
        else:
            logger.debug("ocr_subprocess", "not_running", "子进程未运行，直接清理资源")
            self.cleanup()

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="OCRSubprocessManager")
    def cleanup(self):
        """清理资源"""
        logger = get_logger()

        logger.debug("ocr_subprocess", "cleaning_up", "开始清理子进程资源")
        try:
            # 清理队列
            queues_to_close = [
                ('input_queue', self.input_queue),
                ('output_queue', self.output_queue),
                ('error_queue', self.error_queue)
            ]

            for queue_name, queue_obj in queues_to_close:
                if queue_obj:
                    try:
                        queue_obj.close()
                        logger.debug("ocr_subprocess", "queue_closed", f"已关闭 {queue_name}")
                    except Exception as e:
                        logger.warning("ocr_subprocess", "queue_close_error", f"关闭 {queue_name} 时出错：{e}")
                setattr(self, queue_name, None)

            # 清理进程引用
            if self.process:
                pid = self.process.pid
                self.process = None
                logger.debug("ocr_subprocess", "process_ref_cleaned", f"已清理进程引用 PID: {pid}")

            # 重置状态
            self.is_initialized = False
            self.current_preset = None
            logger.info("ocr_subprocess", "cleanup_complete", "子进程资源清理完成")
        except Exception as e:
            logger.error("ocr_subprocess", "cleanup_error", f"清理资源时出错：{e}")
            import traceback
            traceback.print_exc()

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=False, component="OCRSubprocessManager")
    def is_running(self):
        """检查子进程是否正在运行"""
        return (self.process is not None and
                self.process.is_alive() and
                self.is_initialized)

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="OCRSubprocessManager")
    def process_image(self, image_data, options=None):
        """在子进程中处理图像"""
        if not self.is_running():
            raise RuntimeError("OCR 子进程未运行")

        try:
            options = options or {}

            # 将图像转换为可序列化的格式
            if isinstance(image_data, np.ndarray):
                image_bytes = self._numpy_to_bytes(image_data)
                image_type = 'numpy'
            elif isinstance(image_data, Image.Image):
                image_bytes = self._pil_to_bytes(image_data)
                image_type = 'pil'
            else:
                raise ValueError("不支持的图像类型")

            # 发送处理请求
            request = {
                'command': 'process',
                'image_data': image_bytes,
                'image_type': image_type,
                'options': options
            }

            self.input_queue.put(request)

            # 等待结果
            timeout = 60  # 60 秒超时
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    if not self.error_queue.empty():
                        error_msg = self.error_queue.get_nowait()
                        raise RuntimeError(f"OCR 处理出错：{error_msg}")

                    if not self.output_queue.empty():
                        response = self.output_queue.get_nowait()
                        if response.get('type') == 'result':
                            return response.get('data')
                        elif response.get('type') == 'error':
                            raise RuntimeError(response.get('message', '未知错误'))
                except queue.Empty:
                    pass

                time.sleep(0.01)

            raise TimeoutError("OCR 处理超时")

        except Exception as e:
            logger = get_logger()
            logger.error("ocr_subprocess", "process_failed", f"图像处理失败：{e}")
            raise

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=False, component="OCRSubprocessManager")
    def switch_preset(self, new_preset):
        """切换预设配置"""
        logger = get_logger()

        logger.info("ocr_subprocess", "switching_preset", f"开始切换预设：{self.current_preset} -> {new_preset}")

        if not self.is_running():
            logger.debug("ocr_subprocess", "not_running_start_new", "子进程未运行，直接启动新预设")
            return self.start_process(new_preset)

        if self.current_preset == new_preset:
            logger.debug("ocr_subprocess", "already_in_target", f"当前已在目标预设 {new_preset}，无需切换")
            return True

        try:
            logger.info("ocr_subprocess", "stopping_process", f"正在停止当前子进程 (PID: {self.process.pid if self.process else 'None'})")
            # 强制停止当前进程
            self.stop_process()

            # 确保完全清理资源
            time.sleep(0.5)  # 等待资源释放

            logger.info("ocr_subprocess", "starting_new_preset", f"正在启动新预设子进程：{new_preset}")
            # 启动新进程
            success = self.start_process(new_preset)
            if success:
                logger.success("ocr_subprocess", "preset_switched", f"预设切换成功：{new_preset}")
            else:
                logger.error("ocr_subprocess", "preset_switch_failed", f"预设切换失败：{new_preset}")
            return success
        except Exception as e:
            logger.error("ocr_subprocess", "switch_exception", f"切换预设时发生异常：{e}")
            import traceback
            traceback.print_exc()
            # 尝试清理残留资源
            try:
                self.cleanup()
            except:
                pass
            return False

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={'running': False, 'preset': None, 'pid': None}, component="OCRSubprocessManager")
    def get_status(self):
        """获取子进程状态"""
        return {
            'running': self.is_running(),
            'preset': self.current_preset,
            'pid': self.process.pid if self.process else None
        }

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="OCRSubprocessManager")
    def _numpy_to_bytes(array):
        """将 numpy 数组转换为字节"""
        buffer = io.BytesIO()
        np.save(buffer, array)
        return buffer.getvalue()

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="OCRSubprocessManager")
    def _bytes_to_numpy(bytes_data):
        """将字节转换为 numpy 数组"""
        buffer = io.BytesIO(bytes_data)
        return np.load(buffer)

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="OCRSubprocessManager")
    def _pil_to_bytes(image):
        """将 PIL 图像转换为字节"""
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="OCRSubprocessManager")
    def _bytes_to_pil(bytes_data):
        """将字节转换为 PIL 图像"""
        buffer = io.BytesIO(bytes_data)
        return Image.open(buffer)

    @staticmethod
    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="OCRSubprocessManager")
    def _ocr_worker(input_queue, output_queue, error_queue, config_data, preset):
        """OCR 工作进程函数"""
        try:
            # 反序列化配置管理器
            from app.config.config_manager import ConfigManager
            config_manager = ConfigManager.deserialize(config_data)
            
            # 🔒 关键修复：在子进程中重新从配置文件加载最新配置
            # 这样可以确保用户在设置界面的修改能够生效，而不是使用启动时的配置快照
            config_manager.load_config()

            # 延迟初始化 OCR 引擎 - 只在首次处理任务时初始化
            ocr_engine = None

            # 注意：子进程中不使用全局 logger，避免与主进程冲突
            # 使用临时创建的 logger
            from app.log.log_bus import get_logger
            logger = get_logger()

            logger.info("ocr_subprocess", "worker_started",
                        f"OCR 子进程启动完成，预设：{preset} - OCR 引擎将在首次任务时初始化")
            
            # 🔒 记录当前配置状态（用于调试）
            logger.debug("ocr_subprocess", "config_snapshot", 
                        f"矫正模型配置 - use_cls_model: {config_manager.get_setting('use_cls_model')}, "
                        f"use_doc_ori_model: {config_manager.get_setting('use_doc_ori_model')}, "
                        f"use_unwarp_model: {config_manager.get_setting('use_unwarp_model')}")
            
            # 💡 说明：子进程中使用独立的 OCR 引擎实例，与主进程完全隔离
            # 模型加载信息中的 "Creating model" 日志可能在初始化和处理阶段各出现一次
            # 这是 PaddleOCR 的缓存检查机制，不是重复加载，不影响性能

            # 通知主进程初始化完成
            output_queue.put({'type': 'initialized', 'preset': preset})

            # 处理循环
            while True:
                try:
                    # 设置非阻塞超时
                    request = input_queue.get(timeout=1.0)

                    if request.get('command') == 'stop':
                        break

                    elif request.get('command') == 'process':
                        try:
                            # 🔒 延迟初始化 OCR 引擎 - 只在首次处理时初始化
                            # 这确保了模型加载只在子进程中进行，符合架构设计
                            if ocr_engine is None:
                                try:
                                    logger.info("ocr_subprocess", "initializing_engine",
                                                f"🔄 开始在子进程中初始化 OCR 引擎，预设：{preset}")
                                    # 通知主进程开始加载模型
                                    output_queue.put({
                                        'type': 'initializing',
                                        'message': f'正在加载模型到内存 (第一次运行耗时较长，请耐心等待...)'
                                    })
                                    from app.core.ocr.engine import OcrEngine
                                    ocr_engine = OcrEngine.get_instance(
                                        config_manager=config_manager,
                                        preset=preset
                                    )
                                    logger.info("ocr_subprocess", "engine_initialized",
                                                f"✅ OCR 引擎在子进程中初始化完成，预设：{preset}")
                                    logger.info("ocr_subprocess", "models_loaded",
                                                f"✅ 模型已加载到子进程内存，主进程保持纯净")
                                    # 通知主进程模型加载完成
                                    output_queue.put({
                                        'type': 'initialized',
                                        'preset': preset,
                                        'message': '模型加载完成'
                                    })
                                except Exception as e:
                                    error_msg = f"OCR 引擎初始化失败：{str(e)}\n{traceback.format_exc()}"
                                    error_queue.put(error_msg)
                                    logger.error("ocr_subprocess", "init_error", f"OCR 引擎初始化失败 - {str(e)}")
                                    output_queue.put({
                                        'type': 'error',
                                        'message': str(e)
                                    })
                                    continue

                            # 解析图像数据
                            image_type = request.get('image_type')
                            image_bytes = request.get('image_data')
                            options = request.get('options', {})

                            if image_type == 'numpy':
                                image = pickle.loads(image_bytes)
                            elif image_type == 'pil':
                                image = OCRSubprocessManager._bytes_to_pil(image_bytes)
                            else:
                                raise ValueError(f"Unknown image type: {image_type}")

                            # 处理图像
                            result = ocr_engine.process_image(image, options)

                            # 发送结果
                            output_queue.put({
                                'type': 'result',
                                'data': result
                            })

                        except Exception as e:
                            error_msg = f"处理图像时出错：{str(e)}\n{traceback.format_exc()}"
                            error_queue.put(error_msg)
                            output_queue.put({
                                'type': 'error',
                                'message': str(e)
                            })
                except queue.Empty:
                    continue
                except Exception as e:
                    error_msg = f"子进程循环出错：{str(e)}\n{traceback.format_exc()}"
                    error_queue.put(error_msg)

        except Exception as e:
            error_msg = f"工作进程初始化失败：{str(e)}\n{traceback.format_exc()}"
            error_queue.put(error_msg)
        finally:
            # 清理资源
            try:
                if input_queue:
                    input_queue.close()
                if output_queue:
                    output_queue.close()
                if error_queue:
                    error_queue.close()
            except:
                pass


def get_ocr_subprocess_manager(config_manager):
    """获取全局 OCR 子进程管理器实例"""
    global _subprocess_manager
    if _subprocess_manager is None:
        _subprocess_manager = OCRSubprocessManager(config_manager)
    return _subprocess_manager
