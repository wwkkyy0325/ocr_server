# -*- coding: utf-8 -*-
"""
Tick 调度器 - 周期性任务调度系统

文件说明:
- 作用：提供基于定时器的周期性任务调度，支持优先级和频率控制
- 核心实现：QTimer 驱动 tick 循环，按优先级和频率调度回调
- 关联关系：被 EventMonitor 等组件用于周期性报告统计
"""
from dataclasses import dataclass
from typing import Callable, Dict, Optional
from PyQt5.QtCore import QObject, QTimer
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


@dataclass
class _SystemEntry:
    name: str
    callback: Callable[[], None]
    every_ticks: int
    priority: int
    enabled: bool = True
    last_tick: int = 0


class TickScheduler(QObject):
    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="TickScheduler")
    def __init__(self, tick_ms: int = 50, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._tick_ms = max(1, int(tick_ms))
        self._timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self._timer.timeout.connect(self._on_tick)
        self._tick = 0
        self._systems: Dict[str, _SystemEntry] = {}
        logger = get_logger()
        logger.debug("tick_scheduler", "initialized", f"TickScheduler initialized with {tick_ms}ms interval")

    @property
    def tick(self) -> int:
        return self._tick

    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="TickScheduler")
    def start(self):
        """启动调度器"""
        if not self._timer.isActive():
            self._timer.start(self._tick_ms)
            logger = get_logger()
            logger.info("tick_scheduler", "started", f"TickScheduler started with {self._tick_ms}ms interval")

    @handle_errors(error_code=ErrorCode.PROCESS_TIMEOUT_001, fallback_return=None, component="TickScheduler")
    def stop(self):
        """停止调度器"""
        if self._timer.isActive():
            self._timer.stop()
            logger = get_logger()
            logger.info("tick_scheduler", "stopped", "TickScheduler stopped")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="TickScheduler")
    def register_system(self, name: str, callback: Callable[[], None], every_ticks: int = 1, priority: int = 0):
        """注册定时任务"""
        every = max(1, int(every_ticks))
        self._systems[name] = _SystemEntry(
            name=name,
            callback=callback,
            every_ticks=every,
            priority=int(priority),
            enabled=True,
            last_tick=self._tick,
        )
        logger = get_logger()
        logger.debug("tick_scheduler", "system_registered", f"Registered system: {name} (every={every}, priority={priority})")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="TickScheduler")
    def unregister_system(self, name: str):
        """注销定时任务"""
        if name in self._systems:
            self._systems.pop(name, None)
            logger = get_logger()
            logger.debug("tick_scheduler", "system_unregistered", f"Unregistered system: {name}")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="TickScheduler")
    def set_enabled(self, name: str, enabled: bool):
        """启用/禁用定时任务"""
        entry = self._systems.get(name)
        if entry:
            entry.enabled = bool(enabled)
            logger = get_logger()
            logger.debug("tick_scheduler", "system_toggled", f"System {name} {'enabled' if enabled else 'disabled'}")

    @handle_errors(error_code=ErrorCode.PROCESS_CRASH_001, fallback_return=None, component="TickScheduler")
    def _on_tick(self):
        """Tick 回调 - 调度所有到期的任务"""
        self._tick += 1
        entries = [e for e in self._systems.values() if e.enabled]
        entries.sort(key=lambda e: e.priority, reverse=True)
        
        executed_count = 0
        for entry in entries:
            if (self._tick - entry.last_tick) < entry.every_ticks:
                continue
            entry.last_tick = self._tick
            try:
                entry.callback()
                executed_count += 1
            except Exception as e:
                # 记录异常但不影响其他任务
                logger = get_logger()
                logger.error("tick_scheduler", "callback_error", f"Error executing callback for {entry.name}: {e}")
                continue
        
        # 定期记录调试信息（每 100 个 tick）
        if self._tick % 100 == 0:
            logger = get_logger()
            logger.debug("tick_scheduler", "tick_report", f"Tick {self._tick}: executed {executed_count}/{len(entries)} systems")

    def get_stats(self) -> Dict[str, dict]:
        """获取调度统计信息"""
        stats = {}
        for name, entry in self._systems.items():
            stats[name] = {
                'enabled': entry.enabled,
                'every_ticks': entry.every_ticks,
                'priority': entry.priority,
                'last_tick': entry.last_tick,
                'ticks_since_last': self._tick - entry.last_tick
            }
        return stats


_global_scheduler = None


@handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="TickScheduler")
def get_tick_scheduler():
    """获取全局 TickScheduler 单例"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = TickScheduler()
        try:
            from app.infrastructure.service_registry import ServiceRegistry
            ServiceRegistry.register("tick_scheduler", _global_scheduler)
            logger = get_logger()
            logger.info("tick_scheduler", "singleton_created", "Global TickScheduler singleton created")
        except Exception as e:
            logger = get_logger()
            logger.warning("tick_scheduler", "registry_failed", f"Failed to register TickScheduler: {e}")
    return _global_scheduler
