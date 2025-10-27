# Path: src/app/core/task_manager.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务调度（单张/批量识别任务队列）
"""

import queue
import threading
import time


class TaskManager:
    def __init__(self):
        """
        初始化任务管理器
        """
        self.task_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.tasks = {}  # 存储任务ID和任务的映射
        self.task_counter = 0  # 任务计数器

    def add_task(self, task):
        """
        添加任务到队列

        Args:
            task: 任务对象

        Returns:
            任务ID
        """
        self.task_counter += 1
        task_id = self.task_counter
        self.tasks[task_id] = task
        print(f"Adding task {task_id} to queue")
        self.task_queue.put((task_id, task))
        return task_id

    def process_tasks(self):
        """
        处理任务队列
        """
        print("Processing task queue")
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
                print(f"Error processing task: {e}")

    def start_worker(self):
        """
        启动后台工作线程
        """
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            print("Worker thread started")

    def stop_worker(self):
        """
        停止后台工作线程
        """
        print("Stopping worker thread")
        self.running = False
        # 等待所有任务完成
        self.task_queue.join()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)  # 最多等待5秒
            if self.worker_thread.is_alive():
                print("Warning: Worker thread did not stop gracefully")

    def _worker(self):
        """
        工作线程函数
        """
        print("Worker thread running")
        while self.running:
            try:
                task_id, task = self.task_queue.get(timeout=1)
                if task and self.running:
                    # 执行任务
                    if callable(task):
                        try:
                            task()
                        except Exception as e:
                            print(f"Error executing task {task_id}: {e}")
                    self.task_queue.task_done()
                    # 从任务字典中移除已完成的任务
                    if task_id in self.tasks:
                        del self.tasks[task_id]
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in worker thread: {e}")
        print("Worker thread stopped")

    def cancel_task(self, task_id):
        """
        取消任务

        Args:
            task_id: 任务ID
        """
        print(f"Cancelling task: {task_id}")
        # 从任务字典中移除任务
        if task_id in self.tasks:
            del self.tasks[task_id]
            print(f"Task {task_id} cancelled")
        else:
            print(f"Task {task_id} not found or already completed")
