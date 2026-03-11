# -*- coding: utf-8 -*-

"""
配置管理（保存模型路径、识别参数）
受 Minecraft Forge 配置系统启发的现代化配置管理器
"""

import json
import os
import re
from datetime import datetime
from typing import List
from PyQt5.QtCore import QObject, pyqtSignal

from app.infrastructure.error_handler import handle_errors, ErrorCode


class ConfigManager(QObject):
    # 配置变更信号 (key, value)
    setting_changed = pyqtSignal(str, object)
    # 配置重载信号
    config_reloaded = pyqtSignal()
    # 需要重启信号
    restart_required = pyqtSignal()
    
    def __init__(self, project_root=None):
        """
        初始化配置管理器

        Args:
            project_root: 项目根目录路径
        """
        super().__init__()
        from app.log.log_bus import get_logger
        logger = get_logger()

        logger.info("config_manager", "initializing", "正在初始化配置管理器")
        
        # 使用路径管理器接管路径处理
        from app.utils.path_manager import PathManager
        if project_root is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.path_manager = PathManager(project_root)
        self.project_root = str(self.path_manager.project_root)
        logger.debug("config_manager", "project_root", f"项目根目录：{self.project_root}")

        # 获取 PaddleX 模型目录（从环境变量读取，由 env_manager 设置）
        # 这样可以防止用户系统名有中文导致的问题
        self.models_dir = os.environ.get("PADDLEX_HOME", os.path.join(os.path.expanduser("~"), ".paddlex"))
        logger.debug("config_manager", "models_dir", f"PaddleX 模型目录：{self.models_dir}")

        # 初始化默认配置
        from app.config.config_schema import ConfigSchema
        self.default_config = ConfigSchema.get_default_config()
        logger.info("config_manager", "initialized", "配置管理器初始化完成")

        # Load config immediately
        self.load_config()

    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, component="ConfigManager")
    def load_config(self, config_path=None):
        """
        加载配置
        
        Args:
            config_path: 配置文件路径
        """
        from app.log.log_bus import get_logger
        logger = get_logger()

        if config_path is None:
            config_path = self.path_manager.join_paths(self.project_root, 'config.json')

        logger.debug("config_manager", "loading", f"正在从 {config_path} 加载配置")

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info("config_manager", "loaded", "配置文件加载成功")

                # 使用 schema 清理和验证配置
                from app.config.config_schema import ConfigSchema
                old_config = self.config.copy() if hasattr(self, 'config') else {}
                self.config = ConfigSchema.validate_and_clean(self.config)
                logger.debug("config_manager", "cleaned", "已清理废弃配置项")

                # 检查是否有需要重启的配置项发生变化
                restart_needed = False
                for key, new_value in self.config.items():
                    old_value = old_config.get(key)
                    if old_value != new_value:
                        item_def = ConfigSchema.get_item_by_key(key)
                        if item_def and item_def.restart_required:
                            restart_needed = True
                            break
                
                if restart_needed:
                    self.restart_required.emit()

            except Exception as e:
                logger.error("config_manager", "load_error", f"加载配置文件失败：{e}")
                logger.warning("config_manager", "using_default", "使用默认配置")
                self.config = self.default_config.copy()
        else:
            logger.info("config_manager", "not_found", "配置文件不存在，使用默认配置")
            self.config = self.default_config.copy()
            # 保存默认配置
            self.save_config(config_path)

        # 发射重载信号
        self.config_reloaded.emit()

    def set_model(self, model_type, model_key):
        """
        设置使用的模型
        
        Args:
            model_type: 模型类型 (det/rec/cls/doc_ori/unwarp)
            model_key: 模型 Key
        """
        from app.log.log_bus import get_logger
        logger = get_logger()

        key_name = f"{model_type}_model_key"
        self.set_setting(key_name, model_key)

    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, component="ConfigManager")
    def save_config(self, config_path=None):
        """
        保存配置（不带注释）

        Args:
            config_path: 配置文件路径
        """
        from app.log.log_bus import get_logger
        logger = get_logger()

        if config_path is None:
            config_path = self.path_manager.join_paths(self.project_root, 'config.json')

        logger.debug("config_manager", "saving", f"正在保存配置到：{config_path}")
        try:
            # 确保配置目录存在
            config_dir = os.path.dirname(config_path)
            self.path_manager.ensure_dir_exists(config_dir)

            # 确保 self.config 存在
            if not hasattr(self, 'config'):
                logger.warning("config_manager", "no_config", "配置未初始化，使用默认配置")
                self.config = self.default_config.copy()

            # 使用 schema 过滤废弃项后再保存
            from app.config.config_schema import ConfigSchema
            config_to_save = ConfigSchema.validate_and_clean(self.config.copy())

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=4)
            logger.info("config_manager", "saved", "配置保存成功")
        except Exception as e:
            logger.error("config_manager", "save_error", f"保存配置失败：{e}")


    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="ConfigManager")
    def get_setting(self, key, default=None):
        """
        获取配置项
        
        Args:
            key: 配置项键名
            default: 默认值
        
        Returns:
            配置项值
        """
        if key in self.config:
            return self.config[key]
        if key in self.default_config:
            return self.default_config[key]
        return default

    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="ConfigManager")
    def set_setting(self, key, value):
        """
        设置配置项

        Args:
            key: 配置项键名
            value: 配置项值
        """
        from app.log.log_bus import get_logger
        logger = get_logger()
        
        logger.debug("config_manager", "set_setting", f"设置 {key} = {value}")
        
        # 验证值的有效性
        from app.config.config_schema import ConfigSchema
        item_def = ConfigSchema.get_item_by_key(key)
        if item_def:
            if not item_def.is_valid(value):
                logger.warning("config_manager", "invalid_value", f"配置项 {key} 值 {value} 无效，使用默认值 {item_def.default}")
                value = item_def.default
        
        old_value = self.config.get(key)
        self.config[key] = value
        
        # 如果值发生变化，发射信号
        if old_value != value:
            self.setting_changed.emit(key, value)
            
            # 检查是否需要重启
            if item_def and item_def.restart_required:
                self.restart_required.emit()

    @staticmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigManager")
    def get_available_models(model_type):
        """
        获取指定类型的可用模型列表
        
        Args:
            model_type: 模型类型 (cls/doc_ori/unwarp)
            
        Returns:
            list: [(model_key, description, is_downloaded, size), ...]
        """
        # 定义各类型可用的模型
        models = {
            'cls': [
                ('PP-LCNet_x1_0_textline_ori', '文本行方向分类模型', True, '2.1MB'),
            ],
            'doc_ori': [
                ('PP-LCNet_x1_0_doc_ori', '文档方向分类模型', True, '2.1MB'),
            ],
            'unwarp': [
                ('UVDoc', '文档弯曲矫正模型', True, '85.3MB'),
            ],
        }
        
        return models.get(model_type, [])

    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return={}, component="ConfigManager")
    def serialize(self):
        """
        序列化配置管理器用于进程间传输
        
        Returns:
            dict: 可序列化的配置数据
        """
        # 创建配置副本，转换为可序列化的格式
        serializable_config = {
            'project_root': self.project_root,
            'config': self.config.copy() if hasattr(self, 'config') else self.default_config.copy(),
            'default_config': self.default_config.copy()
        }

        return serializable_config

    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="ConfigManager")
    def deserialize(cls, serialized_data):
        """
        反序列化配置管理器
        
        Args:
            serialized_data: 序列化的配置数据
            
        Returns:
            ConfigManager: 配置管理器实例
        """
        project_root = serialized_data.get('project_root')
        config_manager = cls(project_root)

        # 恢复配置
        if 'config' in serialized_data:
            config_manager.config = serialized_data['config'].copy()

        return config_manager
        
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, component="ConfigManager")
    def reload_config(self):
        """重新加载配置（热重载）"""
        from app.log.log_bus import get_logger
        logger = get_logger()
        logger.info("config_manager", "reload_requested", "请求重新加载配置")
        self.load_config()
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigManager")
    def get_config_categories(self):
        """获取配置分类列表"""
        from app.config.config_schema import ConfigSchema
        return ConfigSchema.get_categories()
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigManager")
    def get_config_items_by_category(self, category):
        """根据分类获取配置项"""
        from app.config.config_schema import ConfigSchema
        return ConfigSchema.get_items_by_category(category)
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="ConfigManager")
    def get_config_item_definition(self, key):
        """获取配置项定义"""
        from app.config.config_schema import ConfigSchema
        return ConfigSchema.get_item_by_key(key)
            
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="ConfigManager")
    def register_plugin_config_item(self, plugin_id: str, config_item: 'ConfigItem') -> bool:
        """
        注册插件配置项（供插件系统调用）
            
        Args:
            plugin_id: 插件 ID
            config_item: 配置项定义
                
        Returns:
            bool: 注册是否成功
        """
        from app.config.plugin_config_registry import PluginConfigRegistry
            
        registry = PluginConfigRegistry.get_instance()
        success = registry.register_config_item(plugin_id, config_item)
            
        if success:
            # 重新加载配置以包含新的配置项
            self.reload_config()
                
        return success
            
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="ConfigManager")
    def unregister_plugin_configs(self, plugin_id: str) -> bool:
        """
        注销插件配置项（插件卸载时调用）
            
        Args:
            plugin_id: 插件 ID
                
        Returns:
            bool: 注销是否成功
        """
        from app.config.plugin_config_registry import PluginConfigRegistry
            
        registry = PluginConfigRegistry.get_instance()
        success = registry.unregister_plugin_configs(plugin_id)
            
        if success:
            # 重新加载配置以移除插件配置项
            self.reload_config()
                
        return success
            
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigManager")
    def get_plugin_config_items(self, plugin_id: str) -> List['ConfigItem']:
        """
        获取插件注册的配置项
            
        Args:
            plugin_id: 插件 ID
                
        Returns:
            List[ConfigItem]: 配置项列表
        """
        from app.config.plugin_config_registry import PluginConfigRegistry
            
        registry = PluginConfigRegistry.get_instance()
        return registry.get_plugin_config_items(plugin_id)