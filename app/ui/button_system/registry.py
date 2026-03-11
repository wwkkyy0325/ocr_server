# -*- coding: utf-8 -*-
"""
按钮注册表 - 管理 UI组件与执行动作的映射关系

职责：
- 维护按钮 ID 到 UI组件的映射（第一层映射）
- 维护按钮 ID 到执行函数的映射（第二层映射）
- 提供统一的连接/断开管理
- 支持动态注册和热更新
"""

from typing import Dict, Callable, Optional
from PyQt5.QtWidgets import QPushButton
from app.log.log_bus import get_logger
from app.ui.button_system.enums import WindowButtonId

logger = get_logger()


class ButtonRegistry:
    """按钮注册表 - 单例模式，统一管理所有按钮映射"""
    
    _instance = None
    
    def __init__(self):
        self._ui_mapping: Dict[WindowButtonId, QPushButton] = {}  # 标识 -> UI组件
        self._action_mapping: Dict[WindowButtonId, Callable] = {}  # 标识 -> 执行函数
        self._initialized = False
        self._connection_count = 0
    
    @classmethod
    def get_instance(cls) -> 'ButtonRegistry':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def reset(self):
        """重置注册表（用于重新初始化或热更新）"""
        old_count = len(self._ui_mapping)
        self._ui_mapping.clear()
        self._action_mapping.clear()
        self._initialized = False
        self._connection_count = 0
        logger.debug("button_registry", "reset", f"已重置注册表（原{old_count}个按钮）")
    
    # ========== 第一层映射：UI组件注册 ==========
    
    def register_ui_button(self, button_id: WindowButtonId, button: QPushButton) -> bool:
        """
        注册 UI 按钮组件
        
        Args:
            button_id: 按钮唯一标识
            button: UI 按钮组件
            
        Returns:
            是否注册成功
        """
        if not button:
            logger.warning(
                "button_registry",
                "null_button",
                f"尝试注册空按钮：{button_id.name}"
            )
            return False
        
        if button_id in self._ui_mapping:
            logger.warning(
                "button_registry", 
                "duplicate_ui_registration",
                f"按钮 {button_id.name} 已注册，忽略重复注册"
            )
            return False
        
        self._ui_mapping[button_id] = button
        logger.debug(
            "button_registry", 
            "ui_button_registered",
            f"UI 按钮已注册：{button_id.name}"
        )
        return True
    
    def get_ui_button(self, button_id: WindowButtonId) -> Optional[QPushButton]:
        """获取 UI 按钮组件"""
        button = self._ui_mapping.get(button_id)
        if not button:
            logger.debug(
                "button_registry",
                "button_not_found",
                f"未找到按钮：{button_id.name}"
            )
        return button
    
    def get_all_ui_buttons(self) -> Dict[WindowButtonId, QPushButton]:
        """获取所有已注册的 UI 按钮"""
        return self._ui_mapping.copy()
    
    # ========== 第二层映射：行为绑定 ==========
    
    def register_action(self, button_id: WindowButtonId, action: Callable) -> bool:
        """
        注册按钮执行动作
        
        Args:
            button_id: 按钮唯一标识
            action: 执行的函数
            
        Returns:
            是否注册成功
        """
        if not action or not callable(action):
            logger.error(
                "button_registry",
                "invalid_action",
                f"尝试注册无效动作：{button_id.name}"
            )
            return False
        
        if button_id in self._action_mapping:
            logger.warning(
                "button_registry",
                "duplicate_action_registration",
                f"动作 {button_id.name} 已注册，忽略重复注册"
            )
            return False
        
        self._action_mapping[button_id] = action
        logger.debug(
            "button_registry",
            "action_registered",
            f"执行动作已注册：{button_id.name}"
        )
        return True
    
    def get_action(self, button_id: WindowButtonId) -> Optional[Callable]:
        """获取按钮执行动作"""
        return self._action_mapping.get(button_id)
    
    def get_all_actions(self) -> Dict[WindowButtonId, Callable]:
        """获取所有已注册的动作"""
        return self._action_mapping.copy()
    
    # ========== 连接管理 ==========
    
    def connect_all_buttons(self) -> int:
        """
        连接所有已注册的按钮到对应的动作
        
        Returns:
            成功连接的按钮数量
        """
        count = 0
        for button_id, button in self._ui_mapping.items():
            action = self._action_mapping.get(button_id)
            
            if not action:
                logger.warning(
                    "button_registry",
                    "missing_action",
                    f"按钮 {button_id.name} 没有关联的动作"
                )
                continue
            
            if not button:
                continue
            
            try:
                # 直接连接，不检查（避免误判）
                button.clicked.connect(action)
                count += 1
                logger.debug(
                    "button_registry",
                    "button_connected",
                    f"按钮已连接：{button_id.name}"
                )
            except Exception as e:
                logger.error(
                    "button_registry",
                    "connection_failed",
                    f"连接按钮 {button_id.name} 失败：{e}",
                    exc_info=True
                )
        
        self._initialized = True
        self._connection_count = count
        
        logger.info(
            "button_registry",
            "all_buttons_connected",
            f"已连接 {count}/{len(self._ui_mapping)} 个窗口控制按钮"
        )
        return count
    
    def disconnect_all_buttons(self):
        """断开所有按钮连接（用于清理或重新连接）"""
        disconnected_count = 0
        
        for button_id, button in self._ui_mapping.items():
            action = self._action_mapping.get(button_id)
            
            if action and button:
                try:
                    # 检查是否已连接
                    if not self._is_connected(button, action):
                        continue
                    
                    button.clicked.disconnect(action)
                    disconnected_count += 1
                except (TypeError, RuntimeError):
                    pass  # 忽略未连接的错误
        
        self._initialized = False
        self._connection_count = 0
        
        logger.debug(
            "button_registry", 
            "disconnected",
            f"已断开 {disconnected_count} 个按钮连接"
        )
    
    def _is_connected(self, button: QPushButton, action: Callable) -> bool:
        """
        检查按钮是否已连接到指定动作
        
        Args:
            button: 按钮组件
            action: 动作函数
            
        Returns:
            是否已连接
        """
        try:
            # PyQt5 没有直接的 isConnected 方法，通过信号接收者判断
            return button.receivers(button.clicked) > 0
        except Exception:
            return False
    
    def is_initialized(self) -> bool:
        """检查注册表是否已初始化"""
        return self._initialized
    
    def get_connection_count(self) -> int:
        """获取当前连接的按钮数量"""
        return self._connection_count
    
    def get_statistics(self) -> dict:
        """获取注册表统计信息"""
        return {
            'ui_buttons': len(self._ui_mapping),
            'actions': len(self._action_mapping),
            'connections': self._connection_count,
            'initialized': self._initialized
        }
