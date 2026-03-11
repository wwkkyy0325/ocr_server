# -*- coding: utf-8 -*-
"""
按钮动作预设 - 提供常用的窗口控制动作实现

职责：
- 封装标准窗口操作逻辑
- 提供可复用的动作模板
- 支持自定义动作扩展
"""

from typing import Optional, Any
from PyQt5.QtWidgets import QMainWindow
from app.log.log_bus import get_logger

logger = get_logger()


class WindowActionProvider:
    """窗口动作提供者 - 封装所有窗口控制相关的业务逻辑"""
    
    def __init__(self, main_window: Optional[QMainWindow] = None):
        """
        Args:
            main_window: 主窗口实例
        """
        self._main_window = main_window
    
    def set_main_window(self, main_window: QMainWindow):
        """设置主窗口引用"""
        self._main_window = main_window
        logger.debug(
            "action_provider",
            "window_set",
            f"已设置主窗口：{type(main_window).__name__}"
        )
    
    @property
    def main_window(self) -> Optional[QMainWindow]:
        """获取主窗口引用"""
        return self._main_window
    
    # ========== 标准窗口控制动作 ==========
    
    def on_minimize(self):
        """最小化窗口"""
        if not self._main_window:
            logger.error(
                "action_provider",
                "no_window",
                "无法最小化：主窗口未设置"
            )
            return
        
        try:
            self._main_window.showMinimized()
            logger.debug(
                "action_provider",
                "minimized",
                "窗口已最小化"
            )
        except Exception as e:
            logger.error(
                "action_provider",
                "minimize_failed",
                f"最小化窗口失败：{e}",
                exc_info=True
            )
    
    def on_maximize_toggle(self):
        """最大化/还原切换"""
        if not self._main_window:
            logger.error(
                "action_provider",
                "no_window",
                "无法切换最大化：主窗口未设置"
            )
            return
        
        try:
            if self._main_window.isMaximized():
                self._main_window.showNormal()
                logger.debug("action_provider", "restored", "窗口已还原")
            else:
                self._main_window.showMaximized()
                logger.debug("action_provider", "maximized", "窗口已最大化")
        except Exception as e:
            logger.error(
                "action_provider",
                "toggle_failed",
                f"切换窗口状态失败：{e}",
                exc_info=True
            )
    
    def on_close(self):
        """关闭窗口（触发标准 closeEvent）"""
        if not self._main_window:
            logger.error(
                "action_provider",
                "no_window",
                "无法关闭：主窗口未设置"
            )
            return
        
        try:
            self._main_window.close()
            logger.debug("action_provider", "closing", "正在关闭窗口")
        except Exception as e:
            logger.error(
                "action_provider",
                "close_failed",
                f"关闭窗口失败：{e}",
                exc_info=True
            )
    
    def on_hide(self):
        """隐藏窗口（不退出）"""
        if not self._main_window:
            logger.error(
                "action_provider",
                "no_window",
                "无法隐藏：主窗口未设置"
            )
            return
        
        try:
            self._main_window.hide()
            logger.debug("action_provider", "hidden", "窗口已隐藏")
        except Exception as e:
            logger.error(
                "action_provider",
                "hide_failed",
                f"隐藏窗口失败：{e}",
                exc_info=True
            )
    
    def on_show_normal(self):
        """还原窗口到正常状态"""
        if not self._main_window:
            return
        
        try:
            self._main_window.showNormal()
            logger.debug("action_provider", "show_normal", "窗口已显示为正常状态")
        except Exception as e:
            logger.error(
                "action_provider",
                "show_normal_failed",
                f"还原窗口失败：{e}",
                exc_info=True
            )
    
    def on_show_maximized(self):
        """最大化显示窗口"""
        if not self._main_window:
            return
        
        try:
            self._main_window.showMaximized()
            logger.debug("action_provider", "show_maximized", "窗口已最大化显示")
        except Exception as e:
            logger.error(
                "action_provider",
                "show_maximized_failed",
                f"最大化窗口失败：{e}",
                exc_info=True
            )
    
    # ========== 工具方法 ==========
    
    def is_maximized(self) -> bool:
        """检查窗口是否已最大化"""
        if not self._main_window:
            return False
        
        try:
            return self._main_window.isMaximized()
        except Exception:
            return False
    
    def is_minimized(self) -> bool:
        """检查窗口是否已最小化"""
        if not self._main_window:
            return False
        
        try:
            # Qt 没有直接的 isMinimized 方法，通过 windowState 判断
            from PyQt5.QtCore import Qt
            return bool(self._main_window.windowState() & Qt.WindowMinimized)
        except Exception:
            return False


# ========== 便捷函数 ==========

def create_window_actions(main_window: QMainWindow) -> WindowActionProvider:
    """
    创建窗口动作提供者
    
    Args:
        main_window: 主窗口实例
        
    Returns:
        配置好的动作提供者
    """
    provider = WindowActionProvider(main_window)
    return provider


def get_standard_window_actions(main_window: QMainWindow) -> dict:
    """
    获取标准窗口控制动作字典
    
    Args:
        main_window: 主窗口实例
        
    Returns:
        动作字典 {WindowButtonId: Callable}
    """
    from app.ui.button_system.enums import WindowButtonId
    
    provider = create_window_actions(main_window)
    
    return {
        WindowButtonId.WINDOW_MINIMIZE: provider.on_minimize,
        WindowButtonId.WINDOW_MAXIMIZE: provider.on_maximize_toggle,
        WindowButtonId.WINDOW_CLOSE: provider.on_close,
    }
