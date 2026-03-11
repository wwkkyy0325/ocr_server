# -*- coding: utf-8 -*-
"""
UI组件工厂 - 提供标准UI组件的创建方法

这个模块提供了一些便捷方法，帮助插件快速创建常见的UI组件，
而不需要直接操作PyQt5的复杂API。
"""

from typing import Optional, Callable, Any
from pathlib import Path

if __name__ == "__main__":
    # Mock PyQt5 for testing
    class MockQtWidgets:
        class QPushButton: 
            def __init__(self, text): self.text = text
        class QAction:
            def __init__(self, text): self.text = text
        class QLabel:
            def __init__(self, text): self.text = text
            
    QtWidgets = MockQtWidgets()
else:
    try:
        from PyQt5 import QtWidgets, QtGui, QtCore
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False


class UIComponentFactory:
    """UI组件工厂类"""
    
    @staticmethod
    def create_button(
        label: str, 
        callback: Optional[Callable] = None,
        icon_path: Optional[str] = None,
        tooltip: Optional[str] = None,
        enabled: bool = True,
        **kwargs
    ) -> Any:
        """
        创建按钮组件
        
        Args:
            label: 按钮文本
            callback: 点击回调函数
            icon_path: 图标路径
            tooltip: 工具提示
            enabled: 是否启用
            **kwargs: 其他参数（会被忽略）
            
        Returns:
            QPushButton: 创建的按钮
        """
        if not PYQT_AVAILABLE:
            return None
            
        button = QtWidgets.QPushButton(label)
        button.setEnabled(enabled)
        
        if tooltip:
            button.setToolTip(tooltip)
            
        if icon_path and Path(icon_path).exists():
            icon = QtGui.QIcon(icon_path)
            button.setIcon(icon)
            
        if callback:
            button.clicked.connect(callback)
            
        return button
        
    @staticmethod
    def create_menu_action(
        label: str,
        callback: Optional[Callable] = None,
        icon_path: Optional[str] = None,
        shortcut: Optional[str] = None,
        tooltip: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        创建菜单动作
        
        Args:
            label: 动作文本
            callback: 触发回调函数
            icon_path: 图标路径
            shortcut: 快捷键
            tooltip: 工具提示
            **kwargs: 其他参数（会被忽略）
            
        Returns:
            QAction: 创建的菜单动作
        """
        if not PYQT_AVAILABLE:
            return None
            
        action = QtWidgets.QAction(label)
        
        if tooltip:
            action.setToolTip(tooltip)
            
        if icon_path and Path(icon_path).exists():
            icon = QtGui.QIcon(icon_path)
            action.setIcon(icon)
            
        if shortcut:
            action.setShortcut(shortcut)
            
        if callback:
            action.triggered.connect(callback)
            
        return action
        
    @staticmethod
    def create_status_label(
        text: str,
        tooltip: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        创建状态栏标签
        
        Args:
            text: 标签文本
            tooltip: 工具提示
            **kwargs: 其他参数（会被忽略）
            
        Returns:
            QLabel: 创建的标签
        """
        if not PYQT_AVAILABLE:
            return None
            
        label = QtWidgets.QLabel(text)
        label.setContentsMargins(5, 0, 5, 0)
        
        if tooltip:
            label.setToolTip(tooltip)
            
        return label