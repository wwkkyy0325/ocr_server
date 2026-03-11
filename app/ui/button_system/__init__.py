# -*- coding: utf-8 -*-
"""
按钮系统包 - 实现 UI 按钮三层架构解耦

架构分层：
1. UI 层：仅负责按钮视觉渲染（QPushButton）
2. 按钮映射层：定义按钮标识与 UI组件的映射
3. 绑定逻辑层：定义按钮标识与执行函数的映射
4. 执行操作层：纯业务逻辑实现
"""

from app.ui.button_system.enums import WindowButtonId, ButtonCategory
from app.ui.button_system.registry import ButtonRegistry
from app.ui.button_system.factory import get_button_registry, register_window_buttons, ButtonBuilderFactory
from app.ui.button_system.actions import WindowActionProvider, create_window_actions, get_standard_window_actions

__all__ = [
    # 枚举
    'WindowButtonId',
    'ButtonCategory',
    
    # 注册表
    'ButtonRegistry',
    
    # 工厂
    'get_button_registry',
    'register_window_buttons',
    'ButtonBuilderFactory',
    
    # 动作提供者
    'WindowActionProvider',
    'create_window_actions',
    'get_standard_window_actions',
]
