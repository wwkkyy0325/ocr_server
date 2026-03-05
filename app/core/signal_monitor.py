# -*- coding: utf-8 -*-
import time
from collections import defaultdict
from typing import Dict, List, Tuple

from PyQt5.QtCore import QObject


class SignalMonitor(QObject):
    """
    信号监控系统 - 用于监控和报告系统事件频率
    
    功能：
    1. 自动记录所有通过 logger 的事件
    2. 每秒报告一次事件频率
    3. 支持自定义事件源
    """
    """
    轻量级信号监控器
    统计每秒信号触发频率 (Event/Sec)
    """
    
    def __init__(self):
        super().__init__()
        self._counts: Dict[str, int] = defaultdict(int)
        self._last_report_time = time.time()
        self._history: List[Tuple[str, int]] = []
        
    def record_emit(self, signal_name: str):
        """记录一次信号发射"""
        self._counts[signal_name] += 1
        
    def get_and_reset_counts(self) -> Dict[str, int]:
        """获取当前统计并重置"""
        if not self._counts:
            return {}
        current_counts = dict(self._counts)
        self._counts.clear()
        self._last_report_time = time.time()
        return current_counts
        
    def report(self):
        """生成报告（供 TickScheduler 调用）"""
        counts = self.get_and_reset_counts()
        if not counts:
            return
            
        # 找出 Top 3 活跃信号
        top_signals = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # 简单打印，或者发送到日志
        # 实际项目中可以连接到 Debug HUD
        msg = "[SignalMonitor] Events/s: " + ", ".join([f"{k}={v}" for k, v in top_signals])
        print(msg)
        
        # 如果某个信号频率极高 (>50/s)，发出警告
        for name, count in top_signals:
            if count > 50:
                print(f"⚠️ [WARNING] High frequency signal detected: {name} ({count}/s)")

_global_monitor = None

def get_signal_monitor():
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SignalMonitor()
    return _global_monitor
