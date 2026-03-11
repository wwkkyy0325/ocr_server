# -*- coding: utf-8 -*-
"""
事件总线 (Event Bus)

文件说明:
- 作用：集中管理和分发应用全局的事件，实现模块间解耦通信
- 核心实现：基于 event.py 中定义的信号类，通过 EventBus 统一转发和监控
- 关联关系：被 MainWindow、ProcessingController、ImageCropper 等模块引用
- 集成监控：内置 EventMonitor 统计每秒事件触发频率，用于性能分析和调试

使用示例:
    event_bus = get_event_bus()
    event_bus.processing.status_updated.connect(callback)
    event_bus.ui.text_blocks_generated.connect(handler)
"""
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from PyQt5.QtCore import QObject, pyqtSignal
from app.log.log_bus import get_logger
from app.event.events import (
    ProcessingSignals,
    UISignals,
    DownloadSignals
)
from app.infrastructure.error_handler import handle_errors, ErrorCode


class EventMonitor:
    """
    轻量级事件监控器 - 统计每秒事件触发频率 (Event/Sec)
    
    功能:
    1. 记录所有通过 EventBus 的事件发射事件
    2. 每秒报告一次事件频率 (由 TickScheduler 调用)
    3. 识别高频事件，帮助发现潜在性能问题
    """

    def __init__(self):
        self._counts: Dict[str, int] = defaultdict(int)
        self._last_report_time = time.time()
        self._history: List[Tuple[str, int]] = []

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="EventMonitor")
    def record_emit(self, signal_name: str):
        """记录一次事件发射"""
        self._counts[signal_name] += 1

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={}, component="EventMonitor")
    def get_and_reset_counts(self) -> Dict[str, int]:
        """获取当前统计并重置"""
        if not self._counts:
            return {}
        current_counts = dict(self._counts)
        self._counts.clear()
        self._last_report_time = time.time()
        return current_counts

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="EventMonitor")
    def report(self):
        """生成报告 (供 TickScheduler 调用)"""
        logger = get_logger()
        counts = self.get_and_reset_counts()
        if not counts:
            return

        # 找出 Top 3 活跃事件
        top_signals = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]

        # 生成报告消息
        msg = "Events/s: " + ", ".join([f"{k}={v}" for k, v in top_signals])
        logger.debug("signal_monitor", "report", msg)

        # 如果某个事件频率极高 (>50/s),发出警告
        for name, count in top_signals:
            if count > 50:
                logger.warning("signal_monitor", "high_frequency",
                               f"⚠️ 高频事件:{name} ({count}/s)")


_global_monitor = None


def get_event_monitor():
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = EventMonitor()
    return _global_monitor


class EventBus(QObject):
    status_updated = pyqtSignal(str, str)
    file_processed = pyqtSignal(str, str)
    processing_finished = pyqtSignal(float)
    progress_updated = pyqtSignal(int, int)
    ocr_result_ready = pyqtSignal(str)
    image_captured = pyqtSignal(object)
    text_blocks_generated = pyqtSignal(list)
    text_block_selected = pyqtSignal(int, object)
    text_blocks_selected = pyqtSignal(list)
    text_block_hovered = pyqtSignal(int)
    model_download_progress = pyqtSignal(int, int)
    model_download_finished = pyqtSignal(bool, str)
    processed_result_ready = pyqtSignal(dict)

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="EventBus")
    def __init__(self):
        super().__init__()
        logger = get_logger()
        
        self.processing = ProcessingSignals()
        self.ui = UISignals()
        self.download = DownloadSignals()

        # 集成监控
        try:
            self.monitor = get_event_monitor()
            self._connect_monitor()
            logger.debug("event_bus", "monitor_initialized", "Event monitor initialized")
        except Exception as e:
            logger.error("event_bus", "monitor_init_failed", f"初始化事件监控器失败:{e}")

        # 连接处理信号
        self.processing.status_updated.connect(self.status_updated.emit)
        self.processing.file_processed.connect(self.file_processed.emit)
        self.processing.processing_finished.connect(self.processing_finished.emit)
        self.processing.progress_updated.connect(self.progress_updated.emit)
        self.processing.ocr_result_ready.connect(self.ocr_result_ready.emit)
        self.processing.processed_result_ready.connect(self.processed_result_ready.emit)

        # 连接 UI 信号
        self.ui.text_blocks_generated.connect(self.text_blocks_generated.emit)
        self.ui.text_block_selected.connect(self.text_block_selected.emit)
        self.ui.text_blocks_selected.connect(self.text_blocks_selected.emit)
        self.ui.text_block_hovered.connect(self.text_block_hovered.emit)

        # 连接下载信号
        self.download.model_download_progress.connect(self.model_download_progress.emit)
        self.download.model_download_finished.connect(self.model_download_finished.emit)
        
        logger.info("event_bus", "initialized", "Event bus initialized successfully")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="EventBus")
    def _connect_monitor(self):
        """将所有信号连接到监控器"""
        logger = get_logger()
        if not hasattr(self, 'monitor'): 
            logger.debug("event_bus", "monitor_not_found", "Monitor not found, skipping connection")
            return
    
        connected_count = 0
        for domain_name in ['processing', 'ui', 'download']:
            domain_obj = getattr(self, domain_name)
            for attr_name in dir(domain_obj):
                if attr_name.startswith('_'): 
                    continue
                signal = getattr(domain_obj, attr_name)
                if hasattr(signal, 'connect'):
                    signal.connect(lambda *args, n=f"{domain_name}.{attr_name}": self.monitor.record_emit(n))
                    connected_count += 1
        
        logger.debug("event_bus", "monitor_connected", f"Connected {connected_count} signals to monitor")


_global_bus = None


def get_event_bus():
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
        try:
            from app.infrastructure.service_registry import ServiceRegistry
            ServiceRegistry.register("event_bus", _global_bus)
        except Exception:
            pass
    return _global_bus
