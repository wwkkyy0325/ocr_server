# -*- coding: utf-8 -*-
"""
按钮工厂 - 提供便捷的按钮注册和连接接口

职责：
- 提供高层便捷 API
- 简化批量注册流程
- 支持多种注册模式
"""

from typing import Dict, Callable
from PyQt5.QtWidgets import QPushButton
from app.log.log_bus import get_logger
from app.ui.button_system.enums import WindowButtonId
from app.ui.button_system.registry import ButtonRegistry

logger = get_logger()


def get_button_registry() -> ButtonRegistry:
    """获取全局按钮注册表实例"""
    return ButtonRegistry.get_instance()


def register_window_buttons(
    ui_buttons: Dict[WindowButtonId, QPushButton], 
    actions: Dict[WindowButtonId, Callable]
) -> int:
    """
    便捷函数：一次性注册并连接所有窗口按钮
    
    Args:
        ui_buttons: UI 按钮字典 {WindowButtonId: QPushButton}
        actions: 执行动作字典 {WindowButtonId: Callable}
        
    Returns:
        成功连接的按钮数量
    """
    registry = get_button_registry()
    
    # 1. 注册 UI组件
    ui_count = 0
    for button_id, button in ui_buttons.items():
        if registry.register_ui_button(button_id, button):
            ui_count += 1
    
    logger.debug(
        "button_factory",
        "ui_buttons_registered",
        f"已注册 {ui_count}/{len(ui_buttons)} 个 UI 按钮"
    )
    
    # 2. 注册动作
    action_count = 0
    for button_id, action in actions.items():
        if registry.register_action(button_id, action):
            action_count += 1
    
    logger.debug(
        "button_factory",
        "actions_registered",
        f"已注册 {action_count}/{len(actions)} 个执行动作"
    )
    
    # 3. 统一连接
    connected_count = registry.connect_all_buttons()
    
    # 4. 验证完整性
    if ui_count != len(ui_buttons):
        logger.warning(
            "button_factory",
            "incomplete_ui_registration",
            f"部分 UI 按钮未注册成功：{ui_count}/{len(ui_buttons)}"
        )
    
    if action_count != len(actions):
        logger.warning(
            "button_factory",
            "incomplete_action_registration",
            f"部分动作未注册成功：{action_count}/{len(actions)}"
        )
    
    return connected_count


class ButtonBuilderFactory:
    """按钮注册构建器 - 支持链式调用"""
    
    def __init__(self):
        self._registry = get_button_registry()
        self._ui_buttons: Dict[WindowButtonId, QPushButton] = {}
        self._actions: Dict[WindowButtonId, Callable] = {}
    
    def add_button(self, button_id: WindowButtonId, button: QPushButton) -> 'ButtonBuilderFactory':
        """添加 UI 按钮"""
        self._ui_buttons[button_id] = button
        return self
    
    def add_action(self, button_id: WindowButtonId, action: Callable) -> 'ButtonBuilderFactory':
        """添加执行动作"""
        self._actions[button_id] = action
        return self
    
    def add_window_buttons(
        self,
        minimize_btn: QPushButton,
        maximize_btn: QPushButton,
        close_btn: QPushButton,
        minimize_action: Callable,
        maximize_action: Callable,
        close_action: Callable
    ) -> 'ButtonBuilderFactory':
        """批量添加窗口控制按钮和动作"""
        self._ui_buttons.update({
            WindowButtonId.WINDOW_MINIMIZE: minimize_btn,
            WindowButtonId.WINDOW_MAXIMIZE: maximize_btn,
            WindowButtonId.WINDOW_CLOSE: close_btn,
        })
        
        self._actions.update({
            WindowButtonId.WINDOW_MINIMIZE: minimize_action,
            WindowButtonId.WINDOW_MAXIMIZE: maximize_action,
            WindowButtonId.WINDOW_CLOSE: close_action,
        })
        
        return self
    
    def build_and_connect(self) -> int:
        """构建并连接所有按钮"""
        return register_window_buttons(self._ui_buttons, self._actions)
    
    def reset(self) -> 'ButtonBuilderFactory':
        """重置构建器"""
        self._ui_buttons.clear()
        self._actions.clear()
        return self
