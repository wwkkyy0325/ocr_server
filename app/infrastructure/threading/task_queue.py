# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：简易任务队列与后台工作线程，用于串行调度耗时任务
# - 核心实现：Queue + 守护线程处理可调用任务，支持启动/停止/取消
# - 关联关系：可被主窗口或控制层用于封装批处理/导出等非实时任务
"""
任务调度（单张/批量识别任务队列）
"""

import queue
import threading
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class TaskManager:
    def __init__(self):
        """
        初始化任务管理器
        """
        self.task_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.tasks = {}  # 存储任务 ID 和任务的映射
        self.task_counter = 0  # 任务计数器

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=0, component="TaskManager")
    def add_task(self, task):
        """
        添加任务到队列
    
        Args:
            task: 任务对象
    
        Returns:
            任务 ID
        """
        logger = get_logger()
        self.task_counter += 1
        task_id = self.task_counter
        self.tasks[task_id] = task
        logger.debug("task_manager", "add_task", f"添加任务 {task_id} 到队列")
        self.task_queue.put((task_id, task))
        return task_id

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="TaskManager")
    def process_tasks(self):
        """
        处理任务队列
        """
        logger = get_logger()
        logger.info("task_manager", "process_start", "开始处理任务队列")
        self.running = True
        while self.running and not self.task_queue.empty():
            try:
                task_id, task = self.task_queue.get(timeout=1)
                # 执行任务
                if callable(task):
                    task()
                self.task_queue.task_done()
                # 从任务字典中移除已完成的任务
                if task_id in self.tasks:
                    del self.tasks[task_id]
            except queue.Empty:
                break
            except Exception as e:
                logger.error("task_manager", "process_error", f"处理任务时出错：{e}")

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="TaskManager")
    def start_worker(self):
        """
        启动后台工作线程
        """
        logger = get_logger()
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            logger.info("task_manager", "worker_started", "工作线程已启动")

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="TaskManager")
    def stop_worker(self):
        """
        停止后台工作线程
        """
        logger = get_logger()
        logger.info("task_manager", "worker_stopping", "正在停止工作线程")
        self.running = False
        # 等待所有任务完成
        self.task_queue.join()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)  # 最多等待 5 秒
            if self.worker_thread.is_alive():
                logger.warning("task_manager", "worker_stop_timeout", "工作线程未能正常停止")

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="TaskManager")
    def _worker(self):
        """
        工作线程函数
        """
        logger = get_logger()
        logger.debug("task_manager", "worker_running", "工作线程运行中")
        while self.running:
            try:
                task_id, task = self.task_queue.get(timeout=1)
                if task and self.running:
                    # 执行任务
                    if callable(task):
                        try:
                            task()
                        except Exception as e:
                            logger.error("task_manager", "task_error",
                                         f"执行任务 {task_id} 时出错：{e}")
                    self.task_queue.task_done()
                    # 从任务字典中移除已完成的任务
                    if task_id in self.tasks:
                        del self.tasks[task_id]
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("task_manager", "worker_error", f"工作线程错误：{e}")
        logger.info("task_manager", "worker_stopped", "工作线程已停止")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="TaskManager")
    def cancel_task(self, task_id):
        """
        取消任务
    
        Args:
            task_id: 任务 ID
        """
        logger = get_logger()
        logger.info("task_manager", "cancel_task", f"正在取消任务：{task_id}")
        # 从任务字典中移除任务
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info("task_manager", "task_cancelled", f"任务 {task_id} 已取消")
        else:
            logger.warning("task_manager", "task_not_found",
                           f"任务 {task_id} 不存在或已完成")
