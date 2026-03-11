# -*- coding: utf-8 -*-
"""
OCR Server API 模块

提供插件管理和扩展功能的统一接口
"""

from .plugin_base import PluginBase
from .plugin_manager import PluginManager
from .plugin_config import PluginConfigManager
from .plugin_api import PluginAPI
from .plugin_event_bus import PluginEventBus

__all__ = [
    'PluginBase',
    'PluginManager', 
    'PluginConfigManager',
    'PluginAPI',
    'PluginEventBus'
]