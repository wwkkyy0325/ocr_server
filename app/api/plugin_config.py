# -*- coding: utf-8 -*-
"""
插件配置管理器 - 处理插件的配置存储、验证和加载

作用：提供插件配置的统一管理接口，支持配置模式验证、默认值设置等

核心功能：
- 配置模式定义和验证
- 默认配置生成
- 配置合并和更新
- 配置持久化
"""

from typing import Dict, Any, Optional
import json
import os

from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginConfigManager:
    """
    插件配置管理器
    
    Attributes:
        _config_dir: 配置目录路径
        _logger: 日志记录器
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        self._config_dir = config_dir or os.path.join(os.path.dirname(__file__), 'plugin_configs')
        self._logger = get_logger()
        os.makedirs(self._config_dir, exist_ok=True)
        
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return=True, component="PluginConfigManager")
    def validate_config(self, config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """
        验证配置是否符合模式
        
        Args:
            config: 待验证的配置
            schema: 配置模式字典（简化版，不使用 JSON Schema）
            
        Returns:
            bool: 配置是否有效
        """
        if not schema:
            return True
            
        try:
            # 检查必需字段
            for required_key in schema.get('required', []):
                if required_key not in config:
                    self._logger.error("plugin_config", "missing_required", 
                                     f"缺少必需的配置项：{required_key}")
                    return False
                    
            # 类型和枚举验证
            type_map = {
                'string': str,
                'number': (int, float),
                'integer': int,
                'boolean': bool,
                'array': list,
                'object': dict
            }
            
            for prop_name, prop_schema in schema.get('properties', {}).items():
                if prop_name not in config:
                    continue
                    
                prop_value = config[prop_name]
                prop_type = prop_schema.get('type')
                
                # 类型验证
                if prop_type and prop_type in type_map:
                    if not isinstance(prop_value, type_map[prop_type]):
                        self._logger.error("plugin_config", "type_mismatch", 
                                         f"配置项 {prop_name} 类型错误，期望 {prop_type}")
                        return False
                        
                # 枚举验证
                if 'enum' in prop_schema and prop_value not in prop_schema['enum']:
                    self._logger.error("plugin_config", "enum_invalid", 
                                     f"配置项 {prop_name} 值不在允许范围内")
                    return False
                    
            return True
            
        except Exception as e:
            self._logger.error("plugin_config", "validation_exception", f"配置验证异常：{e}")
            return False
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return={}, component="PluginConfigManager")
    def generate_default_config(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据模式生成默认配置
        
        Args:
            schema: JSON Schema 模式
            
        Returns:
            Dict: 默认配置
        """
        if not schema:
            return {}
            
        default_config = {}
        
        # 处理 properties
        if 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                if 'default' in prop_schema:
                    default_config[prop_name] = prop_schema['default']
                elif 'type' in prop_schema:
                    # 根据类型设置默认值
                    type_mapping = {
                        'string': '',
                        'number': 0,
                        'integer': 0,
                        'boolean': False,
                        'array': [],
                        'object': {}
                    }
                    default_config[prop_name] = type_mapping.get(prop_schema['type'], None)
                    
        return default_config
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="PluginConfigManager")
    def merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并两个配置字典（深合并）
        
        Args:
            base_config: 基础配置
            override_config: 覆盖配置
            
        Returns:
            Dict: 合并后的配置
        """
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if (key in merged and 
                isinstance(merged[key], dict) and 
                isinstance(value, dict)):
                merged[key] = self.merge_configs(merged[key], value)
            else:
                merged[key] = value
                
        return merged
        
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="PluginConfigManager")
    def save_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        保存插件配置到文件
        
        Args:
            plugin_name: 插件名称
            config: 配置字典
            
        Returns:
            bool: 保存是否成功
        """
        try:
            config_file = os.path.join(self._config_dir, f"{plugin_name}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self._logger.debug("plugin_config", "config_saved", f"插件配置已保存：{plugin_name}")
            return True
        except Exception as e:
            self._logger.error("plugin_config", "save_error", f"保存插件配置失败：{plugin_name}, 错误：{e}")
            return False
            
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="PluginConfigManager")
    def load_plugin_config(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        从文件加载插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Dict: 配置字典，如果文件不存在返回 None
        """
        config_file = os.path.join(self._config_dir, f"{plugin_name}.json")
        
        if not os.path.exists(config_file):
            return None
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self._logger.debug("plugin_config", "config_loaded", f"插件配置已加载：{plugin_name}")
            return config
        except Exception as e:
            self._logger.error("plugin_config", "load_error", f"加载插件配置失败：{plugin_name}, 错误：{e}")
            return None
            
    @handle_errors(error_code=ErrorCode.FILE_DELETE_001, fallback_return=False, component="PluginConfigManager")
    def delete_plugin_config(self, plugin_name: str) -> bool:
        """
        删除插件配置文件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 删除是否成功
        """
        config_file = os.path.join(self._config_dir, f"{plugin_name}.json")
        
        if not os.path.exists(config_file):
            return True
            
        try:
            os.remove(config_file)
            self._logger.debug("plugin_config", "config_deleted", f"插件配置已删除：{plugin_name}")
            return True
        except Exception as e:
            self._logger.error("plugin_config", "delete_error", f"删除插件配置失败：{plugin_name}, 错误：{e}")
            return False