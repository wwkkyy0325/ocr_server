# -*- coding: utf-8 -*-
"""
UI扩展管理器 - 允许插件在主页面上添加UI组件

这个模块提供了一个中间件，让插件可以：
- 在主窗口的指定位置添加按钮、菜单、工具栏等UI组件
- 注册自定义的事件处理函数
- 访问主窗口的现有组件和功能
"""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum

if __name__ == "__main__":
    # Mock PyQt5 for testing
    class MockQtWidgets:
        class QWidget: pass
        class QPushButton: pass
        class QMenu: pass
        class QAction: pass
        class QToolBar: pass
        
    class MockQtCore:
        class QObject: pass
        
    QtWidgets = MockQtWidgets()
    QtCore = MockQtCore()
else:
    try:
        from PyQt5 import QtWidgets, QtCore
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False


class UIComponentType(Enum):
    """UI组件类型枚举"""
    TOOLBAR_BUTTON = "toolbar_button"
    MENU_ACTION = "menu_action" 
    STATUS_BAR_WIDGET = "status_bar_widget"
    MAIN_WINDOW_BUTTON = "main_window_button"
    CUSTOM_WIDGET = "custom_widget"


@dataclass
class UIComponentConfig:
    """UI组件配置"""
    component_type: UIComponentType
    plugin_id: str
    component_id: str  # 插件内唯一标识
    label: str
    icon_path: Optional[str] = None
    tooltip: Optional[str] = None
    enabled: bool = True
    visible: bool = True
    position: Optional[str] = None  # 位置标识，如 "left_toolbar", "right_toolbar", "file_menu" 等
    priority: int = 0  # 优先级，数字越大越靠前
    callback: Optional[Callable] = None
    widget: Optional[Any] = None  # 对于自定义widget


class UIExtensionManager:
    """
    UI扩展管理器
    
    负责管理所有插件注册的UI组件，并提供统一的接口给主窗口
    """
    
    def __init__(self, main_window: Any):
        """
        初始化UI扩展管理器
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self._components: Dict[str, UIComponentConfig] = {}  # {plugin_id.component_id: config}
        self._component_groups: Dict[str, List[UIComponentConfig]] = {}  # {position: [components]}
        
    def register_ui_component(self, config: UIComponentConfig) -> bool:
        """
        注册UI组件
        
        Args:
            config: UI组件配置
            
        Returns:
            bool: 注册是否成功
        """
        if not PYQT_AVAILABLE:
            return False
            
        component_key = f"{config.plugin_id}.{config.component_id}"
        if component_key in self._components:
            print(f"Warning: UI component {component_key} already registered")
            return False
            
        self._components[component_key] = config
        
        # 按位置分组
        position = config.position or "default"
        if position not in self._component_groups:
            self._component_groups[position] = []
        self._component_groups[position].append(config)
        
        # 按优先级排序
        self._component_groups[position].sort(key=lambda x: x.priority, reverse=True)
        
        return True
        
    def unregister_ui_component(self, plugin_id: str, component_id: str) -> bool:
        """
        注销UI组件
        
        Args:
            plugin_id: 插件ID
            component_id: 组件ID
            
        Returns:
            bool: 注销是否成功
        """
        component_key = f"{plugin_id}.{component_id}"
        if component_key not in self._components:
            return False
            
        config = self._components[component_key]
        del self._components[component_key]
        
        # 从分组中移除
        position = config.position or "default"
        if position in self._component_groups:
            self._component_groups[position] = [
                comp for comp in self._component_groups[position] 
                if f"{comp.plugin_id}.{comp.component_id}" != component_key
            ]
            
        return True
        
    def get_components_by_position(self, position: str) -> List[UIComponentConfig]:
        """
        获取指定位置的所有UI组件
        
        Args:
            position: 位置标识
            
        Returns:
            List[UIComponentConfig]: 组件配置列表
        """
        return self._component_groups.get(position, [])
        
    def get_all_components(self) -> List[UIComponentConfig]:
        """
        获取所有UI组件
        
        Returns:
            List[UIComponentConfig]: 所有组件配置列表
        """
        return list(self._components.values())
        
    def clear_plugin_components(self, plugin_id: str):
        """
        清除指定插件的所有UI组件
        
        Args:
            plugin_id: 插件ID
        """
        # 找到该插件的所有组件
        plugin_components = [
            key for key in self._components.keys() 
            if key.startswith(f"{plugin_id}.")
        ]
        
        # 逐个注销
        for component_key in plugin_components:
            plugin_id_part, component_id = component_key.split('.', 1)
            self.unregister_ui_component(plugin_id_part, component_id)