# -*- coding: utf-8 -*-

"""
性能统计（识别耗时、准确率计算）
"""

import time
from datetime import datetime
import difflib


class PerformanceMonitor:
    def __init__(self):
        """
        初始化性能监控器
        """
        self.timers = {}
        self.metrics = {}

    def start_timer(self, task_name):
        """
        开始计时

        Args:
            task_name: 任务名称
        """
        print(f"Starting timer for: {task_name}")
        self.timers[task_name] = time.time()

    def stop_timer(self, task_name):
        """
        停止计时

        Args:
            task_name: 任务名称

        Returns:
            执行时间（秒）
        """
        if task_name in self.timers:
            elapsed_time = time.time() - self.timers[task_name]
            print(f"Stopping timer for: {task_name}, elapsed: {elapsed_time:.2f}s")
            del self.timers[task_name]
            
            # 记录指标
            if task_name not in self.metrics:
                self.metrics[task_name] = []
            self.metrics[task_name].append(elapsed_time)
            
            return elapsed_time
        else:
            print(f"Timer for {task_name} not found")
            return 0.0

    def calculate_accuracy(self, predicted, actual):
        """
        计算准确率

        Args:
            predicted: 预测结果
            actual: 实际结果

        Returns:
            准确率
        """
        print("Calculating accuracy")
        if not actual:
            return 1.0 if not predicted else 0.0
            
        if not predicted:
            return 0.0
            
        # 使用序列匹配器计算相似度
        similarity = difflib.SequenceMatcher(None, predicted, actual).ratio()
        return similarity

    def get_average_time(self, task_name):
        """
        获取任务平均执行时间

        Args:
            task_name: 任务名称

        Returns:
            平均执行时间
        """
        if task_name in self.metrics and self.metrics[task_name]:
            times = self.metrics[task_name]
            return sum(times) / len(times)
        return 0.0

    def get_stats(self):
        """
        获取性能统计信息

        Returns:
            性能统计字典
        """
        stats = {}
        for task_name, times in self.metrics.items():
            if times:
                stats[task_name] = {
                    'count': len(times),
                    'total': sum(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times)
                }
        return stats
