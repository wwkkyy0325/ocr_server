"""
日志控制器 - 统一的日志管理和状态显示系统

功能：
1. 统一日志格式：[组件名] 操作：详细信息
2. 日志分级：INFO, SUCCESS, WARNING, ERROR, WORKING
3. 状态栏集成：选择性显示重要状态
4. 性能监控：自动记录性能指标
5. 信号统计：集成 SignalMonitor
"""

import time
from enum import Enum
from typing import Optional, Callable, Dict
from datetime import datetime
from app.infrastructure.error_handler import handle_errors, ErrorCode


class LogLevel(Enum):
    """日志级别"""
    DEBUG = 0
    INFO = 1
    SUCCESS = 2
    WARNING = 3
    ERROR = 4
    WORKING = 5  # 带省略号动画的工作状态


class LogEntry:
    """日志条目"""

    def __init__(self, component: str, action: str, message: str = "",
                 level: LogLevel = LogLevel.INFO, data: Optional[Dict] = None):
        self.timestamp = datetime.now()
        self.component = component
        self.action = action
        self.message = message
        self.level = level
        self.data = data or {}

    def format(self) -> str:
        """格式化日志条目"""
        base = f"[{self.component}] {self.action}"
        if self.message:
            base += f": {self.message}"
        return base

    def to_signal_format(self) -> str:
        """转换为 SignalMonitor 格式"""
        key = f"{self.component}.{self.action}"
        return key


class LoggerController:
    """日志控制器"""

    def __init__(self):
        self.logs = []  # 历史日志
        self.current_status = None  # 当前状态
        self.status_callback = None  # 状态栏回调函数
        self.max_logs = 1000  # 最大保存日志数
        self.enabled_components = set()  # 启用的组件（空集表示全部启用）
        self.log_handlers = []  # 日志处理器列表

        # 性能统计
        self.perf_stats = {}  # {component.action: [耗时列表]}

        # 信号统计 (集成 SignalMonitor)
        self.signal_stats = {}  # {key: count}

        # 日志级别过滤（可配置最小级别）
        self.min_log_level = LogLevel.DEBUG  # 默认输出所有级别

    def set_status_callback(self, callback: Callable[[str, LogLevel], None]):
        """设置状态栏更新回调"""
        self.status_callback = callback

    def enable_component(self, component: str):
        """启用组件日志"""
        self.enabled_components.add(component)

    def disable_component(self, component: str):
        """禁用组件日志"""
        self.enabled_components.discard(component)

    def log(self, component: str, action: str, message: str = "",
            level: LogLevel = LogLevel.INFO, data: Optional[Dict] = None,
            show_in_status: bool = False):
        """
        记录日志
        
        Args:
            component: 组件名 (如：ocr_subprocess, processing, ui)
            action: 操作名 (如：initialized, file_processed, loading_model)
            message: 详细信息
            level: 日志级别
            data: 附加数据
            show_in_status: 是否在状态栏显示
        """
        # 检查日志级别过滤
        if level.value < self.min_log_level.value:
            return

        # 检查组件是否被禁用（如果 enabled_components 非空，则只允许列表中的组件）
        if self.enabled_components and component not in self.enabled_components:
            return

        entry = LogEntry(component, action, message, level, data)

        # 添加到历史日志
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

        # 更新信号统计
        signal_key = entry.to_signal_format()
        self.signal_stats[signal_key] = self.signal_stats.get(signal_key, 0) + 1

        # 调用日志处理器
        for handler in self.log_handlers:
            try:
                handler(entry)
            except Exception as e:
                print(f"Log handler error: {e}")

        # 更新状态栏
        if show_in_status and self.status_callback:
            status_text = entry.format()
            self.status_callback(status_text, level)

        # 打印到控制台 (统一格式)
        print(f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.format()}")

    def info(self, component: str, action: str, message: str = "",
             show_in_status: bool = False, **kwargs):
        """记录 INFO 级别日志"""
        self.log(component, action, message, LogLevel.INFO, kwargs, show_in_status)

    def success(self, component: str, action: str, message: str = "",
                show_in_status: bool = True, **kwargs):
        """记录 SUCCESS 级别日志"""
        self.log(component, action, message, LogLevel.SUCCESS, kwargs, show_in_status)

    def warning(self, component: str, action: str, message: str = "",
                show_in_status: bool = True, **kwargs):
        """记录 WARNING 级别日志"""
        self.log(component, action, message, LogLevel.WARNING, kwargs, show_in_status)

    def error(self, component: str, action: str, message: str = "",
              show_in_status: bool = True, **kwargs):
        """记录 ERROR 级别日志"""
        self.log(component, action, message, LogLevel.ERROR, kwargs, show_in_status)

    def working(self, component: str, action: str, message: str = "",
                show_in_status: bool = True, **kwargs):
        """记录 WORKING 级别日志 (带省略号动画)"""
        self.log(component, action, message, LogLevel.WORKING, kwargs, show_in_status)

    def debug(self, component: str, action: str, message: str = "", **kwargs):
        """记录 DEBUG 级别日志"""
        if LogLevel.DEBUG.value >= 0:  # 始终允许 DEBUG
            self.log(component, action, message, LogLevel.DEBUG, kwargs, False)

    def perf_start(self, component: str, action: str):
        """开始性能计时"""
        key = f"{component}.{action}"
        self.perf_stats[key] = self.perf_stats.get(key, []) + [time.time()]

    def perf_end(self, component: str, action: str, show_in_status: bool = False):
        """结束性能计时并记录"""
        key = f"{component}.{action}"
        if key in self.perf_stats and len(self.perf_stats[key]) > 0:
            start_time = self.perf_stats[key].pop()
            elapsed = (time.time() - start_time) * 1000  # 毫秒
            self.info(component, f"{action}_perf", f"{elapsed:.1f}ms",
                      show_in_status=show_in_status, elapsed_ms=elapsed)
            return elapsed
        return None

    def get_signal_stats(self) -> Dict[str, int]:
        """获取信号统计"""
        return self.signal_stats.copy()

    def reset_signal_stats(self):
        """重置信号统计"""
        self.signal_stats.clear()

    def get_recent_logs(self, count: int = 10) -> list:
        """获取最近的日志"""
        return self.logs[-count:]

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="LoggerController")
    def add_handler(self, handler: Callable[[LogEntry], None]):
        """添加日志处理器"""
        self.log_handlers.append(handler)

    def set_log_level(self, level: LogLevel):
        """
        设置全局日志级别过滤
        
        Args:
            level: 最小日志级别（低于此级别的日志将被忽略）
        """
        self.min_log_level = level

    @handle_errors(error_code=ErrorCode.FILE_WRITE_001, fallback_return=None, component="LoggerController")
    def enable_file_logging(self, log_file: str):
        """
        启用文件日志记录
        
        Args:
            log_file: 日志文件路径
        """
        import os
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        def file_handler(entry: LogEntry):
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    timestamp = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    level_str = entry.level.name
                    formatted = f"[{timestamp}] [{level_str}] [{entry.component}] {entry.action}"
                    if entry.message:
                        formatted += f": {entry.message}"
                    f.write(formatted + '\n')
            except Exception as e:
                print(f"Error writing to log file: {e}")
        
        self.add_handler(file_handler)

    def enable_all_components(self):
        """启用所有组件的日志输出"""
        self.enabled_components.clear()

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="LoggerController")
    def restrict_to_components(self, components: list):
        """
        限制只允许指定组件输出日志
        
        Args:
            components: 组件名列表，如 ['ocr_subprocess', 'processing']
        """
        self.enabled_components = set(components)

    def is_component_enabled(self, component: str) -> bool:
        """
        检查组件是否可以输出日志
        
        Args:
            component: 组件名
            
        Returns:
            bool: True 表示可以输出，False 表示被禁用
        """
        # 空集表示全部启用
        if not self.enabled_components:
            return True
        return component in self.enabled_components


# 全局日志控制器实例
_global_logger = None


def get_logger() -> LoggerController:
    """获取全局日志控制器实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = LoggerController()
    return _global_logger


def init_logger():
    """初始化日志控制器"""
    global _global_logger
    _global_logger = LoggerController()
    return _global_logger
