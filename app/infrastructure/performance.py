# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：提供耗时与文本相似度等性能指标的收集与汇总
# - 核心实现：基于时间戳记录与 difflib 计算相似度，支持平均/最小/最大统计
# - 关联关系：由主流程在关键阶段打点测量，配合日志与 UI 展示
"""
性能统计（识别耗时、准确率计算）
"""

import time
import difflib
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()


class PerformanceMonitor:
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="PerformanceMonitor")
    def __init__(self):
        """
        初始化性能监控器
        """
        self.timers = {}
        self.metrics = {}

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="PerformanceMonitor")
    def reset(self):
        """
        重置所有统计数据
        """
        self.timers = {}
        self.metrics = {}
        logger.debug("performance", "metrics_reset", "Performance monitor metrics reset")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="PerformanceMonitor")
    def start_timer(self, task_name):
        """
        开始计时

        Args:
            task_name: 任务名称
        """
        logger.debug("performance", "timer_started", f"Starting timer for: {task_name}")
        self.timers[task_name] = time.time()

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=0.0, component="PerformanceMonitor")
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
            logger.debug("performance", "timer_stopped", 
                        f"Stopping timer for: {task_name}, elapsed: {elapsed_time:.2f}s")
            del self.timers[task_name]
            
            # 记录指标
            if task_name not in self.metrics:
                self.metrics[task_name] = []
            self.metrics[task_name].append(elapsed_time)
            
            return elapsed_time
        else:
            logger.warning("performance", "timer_not_found", f"Timer for {task_name} not found")
            return 0.0

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=0.0, component="PerformanceMonitor")
    def calculate_accuracy(self, predicted, actual):
        """
        计算准确率

        Args:
            predicted: 预测结果
            actual: 实际结果

        Returns:
            准确率
        """
        logger.debug("performance", "calculating_accuracy", "Calculating accuracy")
        if not actual:
            return 1.0 if not predicted else 0.0
            
        if not predicted:
            return 0.0
            
        # 使用序列匹配器计算相似度
        similarity = difflib.SequenceMatcher(None, predicted, actual).ratio()
        return similarity

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=0.0, component="PerformanceMonitor")
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

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={}, component="PerformanceMonitor")
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
