# -*- coding: utf-8 -*-
"""
插件配置注册器 - 允许插件向主配置系统注册配置项

作用：提供插件配置项的注册、管理和集成接口
"""

import json
from typing import Dict, List, Optional, Any
from app.config.config_schema import ConfigItem
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginConfigRegistry:
    """
    插件配置注册器 - 单例模式
    
    Attributes:
        _instance: 单例实例
        _plugin_config_items: 插件注册的配置项 {plugin_id: [ConfigItem]}
        _logger: 日志记录器
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._plugin_config_items: Dict[str, List[ConfigItem]] = {}
            self._logger = get_logger()
            self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'PluginConfigRegistry':
        """获取单例实例"""
        return cls()
    
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return=False, component="PluginConfigRegistry")
    def register_config_item(self, plugin_id: str, config_item: ConfigItem) -> bool:
        """
        注册插件配置项
        
        Args:
            plugin_id: 插件 ID
            config_item: 配置项定义
            
        Returns:
            bool: 注册是否成功
        """
        # 设置插件 ID
        config_item.plugin_id = plugin_id
        
        # 检查配置项键名是否已存在
        existing_items = self.get_all_config_items()
        for item in existing_items:
            if item.key == config_item.key and item.plugin_id != plugin_id:
                self._logger.error("plugin_config_registry", "duplicate_key", 
                                 f"配置项键名冲突：{config_item.key} 已被插件 {item.plugin_id} 使用")
                return False
        
        # 添加到插件配置项列表
        if plugin_id not in self._plugin_config_items:
            self._plugin_config_items[plugin_id] = []
        
        self._plugin_config_items[plugin_id].append(config_item)
        self._logger.debug("plugin_config_registry", "registered", 
                         f"插件 {plugin_id} 注册配置项：{config_item.key}")
        return True
    
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=False, component="PluginConfigRegistry")
    def unregister_plugin_configs(self, plugin_id: str) -> bool:
        """
        注销插件的所有配置项（插件卸载时调用）
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            bool: 注销是否成功
        """
        if plugin_id in self._plugin_config_items:
            removed_count = len(self._plugin_config_items[plugin_id])
            del self._plugin_config_items[plugin_id]
            self._logger.debug("plugin_config_registry", "unregistered", 
                             f"插件 {plugin_id} 的 {removed_count} 个配置项已注销")
            return True
        return False
    
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="PluginConfigRegistry")
    def get_plugin_config_items(self, plugin_id: str) -> List[ConfigItem]:
        """
        获取插件注册的配置项
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            List[ConfigItem]: 配置项列表
        """
        return self._plugin_config_items.get(plugin_id, [])
    
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="PluginConfigRegistry")
    def get_all_config_items(self) -> List[ConfigItem]:
        """
        获取所有插件注册的配置项
        
        Returns:
            List[ConfigItem]: 所有配置项列表
        """
        all_items = []
        for items in self._plugin_config_items.values():
            all_items.extend(items)
        return all_items
    
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="PluginConfigRegistry")
    def get_config_items_by_category(self, category: str) -> List[ConfigItem]:
        """
        根据分类获取插件配置项
        
        Args:
            category: 配置分类
            
        Returns:
            List[ConfigItem]: 配置项列表
        """
        all_items = self.get_all_config_items()
        return [item for item in all_items if item.category == category]
    
    @handle_errors(error_code=ErrorCode.CONFIG_PARSE_001, fallback_return=[], component="PluginConfigRegistry")
    def merge_with_core_config(self, core_config_items: List[ConfigItem]) -> List[ConfigItem]:
        """
        将插件配置项与核心配置项合并
        
        Args:
            core_config_items: 核心配置项列表
            
        Returns:
            List[ConfigItem]: 合并后的配置项列表
        """
        # 检查键名冲突
        core_keys = {item.key for item in core_config_items}
        plugin_items = self.get_all_config_items()
        plugin_keys = {item.key for item in plugin_items}
        
        conflicts = core_keys & plugin_keys
        if conflicts:
            self._logger.error("plugin_config_registry", "merge_conflict", 
                             f"核心配置与插件配置键名冲突：{conflicts}")
            # 移除冲突的插件配置项
            plugin_items = [item for item in plugin_items if item.key not in conflicts]
        
        return core_config_items + plugin_items
    
    @handle_errors(error_code=ErrorCode.FILE_WRITE_001, fallback_return="", component="PluginConfigRegistry")
    def generate_plugin_documentation(self) -> str:
        """
        生成插件配置文档
        
        Returns:
            str: Markdown 格式的文档内容
        """
        from datetime import datetime
        
        if not self._plugin_config_items:
            return "# 插件配置文档\n\n暂无插件注册配置项。\n"
        
        content = f"""# 插件配置文档
Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

本文件描述了所有插件注册的配置选项。

## 已注册插件

"""
        
        for plugin_id, items in self._plugin_config_items.items():
            if not items:
                continue
                
            content += f"\n### 插件：`{plugin_id}`\n"
            
            for item in items:
                content += f"\n#### `{item.key}`\n"
                content += f"- **类型**: `{item.type.__name__}`\n"
                content += f"- **默认值**: `{json.dumps(item.default, ensure_ascii=False)}`\n"
                content += f"- **描述**: {item.description}\n"
                
                if item.comment and item.comment != item.description:
                    content += f"- **详情**: {item.comment}\n"
                
                if item.valid_values:
                    content += f"- **有效值**: {item.valid_values}\n"
                elif item.min_value is not None or item.max_value is not None:
                    range_info = []
                    if item.min_value is not None:
                        range_info.append(f"最小值：{item.min_value}")
                    if item.max_value is not None:
                        range_info.append(f"最大值：{item.max_value}")
                    if range_info:
                        content += f"- **范围**: {' | '.join(range_info)}\n"
                
                if item.restart_required:
                    content += "- **需要重启**: 是\n"
                else:
                    content += "- **需要重启**: 否\n"
        
        return content
