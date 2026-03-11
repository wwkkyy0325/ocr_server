# -*- coding: utf-8 -*-
"""
事件优先级枚举 (Event Priority)

文件说明:
- 作用：定义应用全局事件的优先级枚举值，统一管理事件处理的优先顺序
- 核心实现：基于 Enum 实现类型安全的优先级常量
- 关联关系：被 event_bus.py 等模块引用，用于控制事件处理顺序

使用示例:
    from app.event.event_priority import EventPriority
    
    # 注册高优先级事件
    event_bus.register_handler(event_type, handler, priority=EventPriority.CRITICAL)
    
    # 比较优先级
    if priority > EventPriority.NORMAL:
        print("这是一个重要事件")
"""
from enum import IntEnum


class EventPriority(IntEnum):
    """
    事件优先级枚举
    
    数值越小，优先级越高（越先被处理）
    
    级别说明:
    - CRITICAL (0): 关键事件，需要立即处理，如系统错误、安全相关
    - HIGH (10): 高优先级事件，重要业务逻辑，如用户交互响应
    - NORMAL (20): 普通事件，常规业务处理，如数据更新
    - LOW (30): 低优先级事件，可延迟处理，如日志记录、统计上报
    - BACKGROUND (40): 后台事件，空闲时处理，如缓存清理、预加载
    
    使用示例:
        # 注册事件处理器
        event_bus.register('user.login', handler, priority=EventPriority.HIGH)
        
        # 获取优先级值
        priority_value = EventPriority.NORMAL.value  # 20
        
        # 优先级比较
        if EventPriority.CRITICAL < EventPriority.NORMAL:
            print("关键事件优先处理")
    """
    
    CRITICAL = 0      # 关键优先级：系统级事件，必须立即处理
    HIGH = 10         # 高优先级：重要业务事件，快速响应
    NORMAL = 20       # 普通优先级：常规事件，标准处理
    LOW = 30          # 低优先级：可延迟事件，空闲时处理
    BACKGROUND = 40   # 后台优先级：后台任务，不影响主业务流程
    
    @classmethod
    def get_priority_name(cls, priority_value: int) -> str:
        """
        根据优先级值获取名称
        
        Args:
            priority_value: 优先级值
            
        Returns:
            str: 优先级名称
        """
        try:
            return cls(priority_value).name
        except ValueError:
            return f"UNKNOWN_{priority_value}"
    
    @classmethod
    def is_critical(cls, priority_value: int) -> bool:
        """
        判断是否为关键优先级
        
        Args:
            priority_value: 优先级值
            
        Returns:
            bool: 是否为关键优先级
        """
        return priority_value == cls.CRITICAL
    
    @classmethod
    def is_high(cls, priority_value: int) -> bool:
        """
        判断是否为高优先级
        
        Args:
            priority_value: 优先级值
            
        Returns:
            bool: 是否为高优先级
        """
        return priority_value <= cls.HIGH
    
    @classmethod
    def is_background(cls, priority_value: int) -> bool:
        """
        判断是否为背景优先级
        
        Args:
            priority_value: 优先级值
            
        Returns:
            bool: 是否为背景优先级
        """
        return priority_value >= cls.BACKGROUND
