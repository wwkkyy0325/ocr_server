# -*- coding: utf-8 -*-
"""
按钮标识符枚举 - 定义所有窗口控制按钮的唯一标识

职责：
- 提供强类型的按钮 ID 定义
- 确保按钮命名规范统一
- 支持扩展其他按钮类型
"""

from enum import Enum, auto


class WindowButtonId(Enum):
    """窗口控制按钮唯一标识符"""
    
    # 基本窗口控制
    WINDOW_MINIMIZE = auto()      # 最小化按钮
    WINDOW_MAXIMIZE = auto()      # 最大化/还原按钮
    WINDOW_CLOSE = auto()         # 关闭按钮
    
    # 可扩展其他按钮类型
    # WINDOW_HELP = auto()        # 帮助按钮（未来扩展）
    # WINDOW_SETTINGS = auto()    # 设置按钮（未来扩展）


class ButtonCategory(Enum):
    """按钮分类（用于分组管理）"""
    
    WINDOW_CONTROL = "window_control"  # 窗口控制类
    ACTION = "action"                  # 操作按钮类
    NAVIGATION = "navigation"          # 导航按钮类
    
    @classmethod
    def get_category(cls, button_id: WindowButtonId) -> 'ButtonCategory':
        """根据按钮 ID 获取所属分类"""
        return cls.WINDOW_CONTROL
