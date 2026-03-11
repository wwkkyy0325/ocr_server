# -*- coding: utf-8 -*-
"""
插件API接口 - 提供统一的插件管理 API

作用：为其他组件提供简单易用的插件管理接口，隐藏内部实现细节

使用示例：
    from app.api.plugin_api import PluginAPI
    
    # 获取插件API 实例
    plugin_api = PluginAPI.get_instance()
    
    # 获取所有可用插件
    plugins = plugin_api.get_available_plugins()
    
    # 启用插件
    plugin_api.enable_plugin('my_plugin', {'setting': 'value'})
    
    # 调用插件方法
    result = plugin_api.call_plugin_method('my_plugin', 'custom_method', arg1, arg2)
"""

from typing import Dict, Any, Optional, List
from app.api.plugin_manager import PluginManager
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginAPI:
    """
    插件API接口 - 单例模式
    
    提供统一的插件管理接口
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginAPI, cls).__new__(cls)
        return cls._instance
        
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._plugin_manager = PluginManager()
        self._logger = get_logger()
        self._initialized = False
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=False, component="PluginAPI")
    def initialize(self) -> bool:
        """
        初始化插件API
        
        Returns:
            bool: 初始化是否成功
        """
        if self._initialized:
            return True
            
        success = self._plugin_manager.initialize()
        self._initialized = success
        return success
        
    @classmethod
    def get_instance(cls) -> 'PluginAPI':
        """获取插件API 单例实例"""
        return cls()
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return={}, component="PluginAPI")
    def get_available_plugins(self) -> Dict[str, Dict[str, Any]]:
        """获取所有可用插件的信息"""
        return self._plugin_manager.get_available_plugins()
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return={}, component="PluginAPI")
    def get_loaded_plugins(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已加载插件的状态信息"""
        return self._plugin_manager.get_plugin_status()
        
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return=False, component="PluginAPI")
    def enable_plugin(self, plugin_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        启用插件
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            
        Returns:
            bool: 启用是否成功
        """
        return self._plugin_manager.enable_plugin(plugin_name, config)
        
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return=False, component="PluginAPI")
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 禁用是否成功
        """
        return self._plugin_manager.disable_plugin(plugin_name)
        
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="PluginAPI")
    def update_plugin_config(self, plugin_name: str, new_config: Dict[str, Any]) -> bool:
        """
        更新插件配置
        
        Args:
            plugin_name: 插件名称
            new_config: 新配置
            
        Returns:
            bool: 更新是否成功
        """
        return self._plugin_manager.update_plugin_config(plugin_name, new_config)
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=None, component="PluginAPI")
    def call_plugin_method(self, plugin_name: str, method_name: str, *args, **kwargs) -> Any:
        """
        调用插件的自定义方法
        
        Args:
            plugin_name: 插件名称
            method_name: 方法名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Any: 方法返回值
            
        Raises:
            ValueError: 插件未找到或方法不存在
        """
        plugin = self._plugin_manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"插件未找到或未加载：{plugin_name}")
            
        if not hasattr(plugin, method_name):
            raise ValueError(f"插件方法不存在：{plugin_name}.{method_name}")
            
        method = getattr(plugin, method_name)
        if not callable(method):
            raise ValueError(f"插件属性不是可调用方法：{plugin_name}.{method_name}")
            
        return method(*args, **kwargs)
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=None, component="PluginAPI")
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定插件的状态信息
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Dict: 插件状态信息，如果插件不存在返回 None
        """
        plugin = self._plugin_manager.get_plugin(plugin_name)
        if plugin:
            return plugin.get_status()
        return None
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginAPI")
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        检查插件是否已启用
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 插件是否已启用
        """
        available_plugins = self.get_available_plugins()
        return available_plugins.get(plugin_name, {}).get('enabled', False)
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=None, component="PluginAPI")
    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        """
        获取插件实例
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Any: 插件实例，如果未找到返回 None
        """
        return self._plugin_manager.get_plugin(plugin_name)
        
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="PluginAPI")
    def get_main_window(self) -> Optional[Any]:
        """
        获取主窗口实例
        
        Returns:
            MainWindow: 主窗口实例，如果未初始化返回 None
        """
        if hasattr(self._plugin_manager, '_main_window'):
            return self._plugin_manager._main_window
        return None
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginAPI")
    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """
        检查插件是否已加载
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 插件是否已加载
        """
        return self._plugin_manager.is_plugin_loaded(plugin_name)