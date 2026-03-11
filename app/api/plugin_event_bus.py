# -*- coding: utf-8 -*-
"""
插件间事件总线 - 支持插件发布和订阅自定义事件

作用：为插件提供独立的事件系统，支持插件间的松耦合通信

使用示例：
    # 在插件A 中发布事件
    from app.api.plugin_event_bus import PluginEventBus
    event_bus = PluginEventBus.get_instance()
    event_bus.publish('my_custom_event', {'data': 'value'})
    
    # 在插件 B 中订阅事件
    def handle_custom_event(data):
        print(f"收到事件数据：{data}")
    
    event_bus.subscribe('my_custom_event', handle_custom_event)
"""

from typing import Dict, List, Callable, Any
from threading import Lock
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginEventBus:
    """
    插件间事件总线 - 单例模式
    
    Attributes:
        _instance: 单例实例
        _subscribers: 事件订阅者字典 {event_name: [callback_functions]}
        _lock: 线程锁
        _logger: 日志记录器
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PluginEventBus, cls).__new__(cls)
        return cls._instance
        
    def __init__(self):
        """初始化插件事件总线"""
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._subscribers: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = True
        from app.log.log_bus import get_logger
        self.logger = get_logger()
        
    @classmethod
    def get_instance(cls) -> 'PluginEventBus':
        """获取插件事件总线单例实例"""
        return cls()
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginEventBus")
    def subscribe(self, plugin_id: str, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        订阅事件
        
        Args:
            plugin_id: 插件 ID
            event_name: 事件名称
            callback: 回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        if not callable(callback):
            self.logger.error("plugin_event_bus", "invalid_callback", f"无效的回调函数：{plugin_id}.{event_name}")
            return False
            
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
            
        # 检查是否已订阅
        for subscriber in self._subscribers[event_name]:
            if subscriber['plugin_id'] == plugin_id and subscriber['callback'] == callback:
                self.logger.debug("plugin_event_bus", "already_subscribed", 
                                f"插件已订阅事件：{plugin_id}.{event_name}")
                return True
                
        self._subscribers[event_name].append({
            'plugin_id': plugin_id,
            'callback': callback
        })
        
        self.logger.info("plugin_event_bus", "subscribed", 
                        f"插件订阅事件：{plugin_id}.{event_name}")
        return True
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginEventBus")
    def unsubscribe(self, plugin_id: str, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        取消订阅事件
        
        Args:
            plugin_id: 插件 ID
            event_name: 事件名称
            callback: 要取消的回调函数
            
        Returns:
            bool: 是否成功取消订阅
        """
        if event_name not in self._subscribers:
            return False
            
        try:
            self._subscribers[event_name].remove({
                'plugin_id': plugin_id,
                'callback': callback
            })
            self.logger.info("plugin_event_bus", "unsubscribed", 
                             f"插件取消订阅事件：{plugin_id}.{event_name}")
            return True
        except ValueError:
            return False
            
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=0, component="PluginEventBus")
    def publish(self, event_name: str, data: Dict[str, Any] = None) -> int:
        """
        发布事件
        
        Args:
            event_name: 事件名称
            data: 事件数据
            
        Returns:
            int: 成功调用的订阅者数量
        """
        if event_name not in self._subscribers:
            self.logger.debug("plugin_event_bus", "no_subscribers", 
                              f"事件无订阅者：{event_name}")
            return 0
            
        success_count = 0
        failed_callbacks = []
        
        for subscriber in self._subscribers[event_name]:
            try:
                subscriber['callback'](data)
                success_count += 1
            except Exception as e:
                self.logger.error("plugin_event_bus", "callback_error", 
                                 f"事件回调执行失败：{event_name}, 错误：{e}")
                failed_callbacks.append(subscriber)
                
        # 清理失败的回调（可选）
        # for failed_callback in failed_callbacks:
        #     self._subscribers[event_name].remove(failed_callback)
            
        self.logger.debug("plugin_event_bus", "published", 
                          f"事件发布完成：{event_name}, 订阅者数量：{len(self._subscribers[event_name])}, 成功：{success_count}")
        return success_count
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=0, component="PluginEventBus")
    def get_subscriber_count(self, event_name: str) -> int:
        """
        获取事件的订阅者数量
        
        Args:
            event_name: 事件名称
            
        Returns:
            int: 订阅者数量
        """
        return len(self._subscribers.get(event_name, []))
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginEventBus")
    def clear_event(self, event_name: str) -> None:
        """
        清除指定事件的所有订阅者
        
        Args:
            event_name: 事件名称
        """
        if event_name in self._subscribers:
            del self._subscribers[event_name]
            self.logger.debug("plugin_event_bus", "cleared", 
                              f"事件订阅者已清除：{event_name}")
            
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginEventBus")
    def clear_all(self) -> None:
        """清除所有事件订阅者"""
        self._subscribers.clear()
        self.logger.info("plugin_event_bus", "cleared_all", "所有事件订阅者已清除")