# -*- coding: utf-8 -*-
"""
高级插件管理器 - 支持依赖关系、命名空间和加载顺序

作用：实现类似 Minecraft Forge 的插件管理系统，支持：
- 从项目根目录的 plugins 目录加载插件
- 插件依赖关系解析和验证
- 加载顺序控制
- 命名空间隔离
- 版本兼容性检查

插件目录结构：
project_root/
├── plugins/
│   ├── plugin1/
│   │   ├── plugin.json      # 插件元数据
│   │   └── __init__.py      # 插件主模块
│   └── plugin2/
│       ├── plugin.json
│       └── main.py          # 或其他主文件
"""

import os
import sys
import importlib
import importlib.util
import json
from typing import Dict, List, Any, Optional, Type, Set
from pathlib import Path

from app.api.plugin_base import PluginBase
from app.api.plugin_metadata import PluginMetadata
from app.api.plugin_dependency_resolver import PluginDependencyResolver
from app.config.config_manager import ConfigManager
from app.log.log_bus import get_logger
from app.event.event_bus import get_event_bus
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginManager:
    """
    高级插件管理器 - 单例模式
    
    Attributes:
        _instance: 单例实例
        _plugins: 已加载的插件字典 {id: plugin_instance}
        _plugin_metadata: 插件元数据字典 {id: metadata}
        _plugin_modules: 插件模块字典 {id: module}
        _config_manager: 配置管理器
        _plugin_dir: 插件目录路径（项目根目录下的 plugins）
        _initialized: 是否已初始化
        _event_bus: 事件总线
        _dependency_resolver: 依赖解析器
        _plugin_file_timestamps: 插件文件时间戳缓存（用于热重载）
    """
    
    _instance = None
    _lock = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginManager, cls).__new__(cls)
        return cls._instance
        
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        # 插件目录设置为项目根目录下的 plugins
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self._plugin_dir = os.path.join(project_root, 'plugins')
        
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_metadata: Dict[str, PluginMetadata] = {}
        self._plugin_modules: Dict[str, Any] = {}
        self._config_manager = ConfigManager()
        self._event_bus = get_event_bus()
        self._dependency_resolver = PluginDependencyResolver()
        self._initialized = False
        self._plugin_file_timestamps: Dict[str, float] = {}  # 用于热重载
        # 添加主窗口引用
        self._main_window = None
        
        # 创建插件目录（如果不存在）
        os.makedirs(self._plugin_dir, exist_ok=True)
        
        self.logger = get_logger()
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginManager")
    def initialize(self) -> bool:
        """
        初始化插件管理器
        
        Returns:
            bool: 初始化是否成功
        """
        if self._initialized:
            return True
            
        try:
            self.logger.info("plugin_manager", "initializing", "正在初始化高级插件管理器")
            
            # 发现插件并加载元数据
            self.discover_plugins()
            
            # 验证依赖关系
            is_valid, errors = self._dependency_resolver.validate_dependencies(self._plugin_metadata)
            if not is_valid:
                for error in errors:
                    self.logger.error("plugin_manager", "dependency_error", error)
                return False
                
            # 解析加载顺序
            load_order = self._dependency_resolver.resolve_load_order(self._plugin_metadata)
            
            # 按顺序加载插件
            self.load_plugins_in_order(load_order)
            
            # 连接事件总线
            self._connect_event_bus()
            
            self._initialized = True
            self.logger.info("plugin_manager", "initialized", 
                           f"高级插件管理器初始化完成，发现 {len(self._plugin_metadata)} 个插件，加载 {len(self._plugins)} 个插件")
            return True
            
        except Exception as e:
            self.logger.error("plugin_manager", "init_error", f"高级插件管理器初始化失败：{e}")
            import traceback
            traceback.print_exc()
            return False
            
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginManager")
    def discover_plugins(self) -> List[str]:
        """
        发现 plugins 目录中的所有插件
        
        Returns:
            List[str]: 发现的插件 ID 列表
        """
        discovered_plugins = []
        
        if not os.path.exists(self._plugin_dir):
            self.logger.debug("plugin_manager", "no_plugin_dir", "插件目录不存在")
            return discovered_plugins
            
        # 遍历插件目录
        for item in os.listdir(self._plugin_dir):
            plugin_path = os.path.join(self._plugin_dir, item)
            
            # 只处理目录（插件必须是目录）
            if os.path.isdir(plugin_path):
                plugin_id = item
                
                # 检查是否存在 plugin.json
                metadata_file = os.path.join(plugin_path, 'plugin.json')
                if not os.path.exists(metadata_file):
                    self.logger.warning("plugin_manager", "no_metadata", f"插件目录缺少 plugin.json: {plugin_id}")
                    continue
                    
                try:
                    # 加载元数据
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata_dict = json.load(f)
                    
                    # 验证必需字段
                    if 'id' not in metadata_dict or 'version' not in metadata_dict:
                        self.logger.error("plugin_manager", "invalid_metadata", f"插件元数据缺少必需字段：{plugin_id}")
                        continue
                        
                    # 确保元数据中的 ID 与目录名一致
                    if metadata_dict['id'] != plugin_id:
                        self.logger.warning("plugin_manager", "id_mismatch", 
                                          f"插件 ID 不匹配：目录名={plugin_id}, 元数据 ID={metadata_dict['id']}")
                        metadata_dict['id'] = plugin_id
                        
                    metadata = PluginMetadata.from_dict(metadata_dict)
                    self._plugin_metadata[plugin_id] = metadata
                    discovered_plugins.append(plugin_id)
                    
                    self.logger.debug("plugin_manager", "plugin_discovered", 
                                    f"发现插件：{plugin_id} v{metadata.version}")
                    
                except Exception as e:
                    self.logger.error("plugin_manager", "metadata_load_error", 
                                    f"加载插件元数据失败：{plugin_id}, 错误：{e}")
                    
        return discovered_plugins
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginManager")
    def load_plugins_in_order(self, load_order: List[str]) -> List[str]:
        """
        按指定顺序加载插件
        
        Args:
            load_order: 插件 ID 加载顺序列表
            
        Returns:
            List[str]: 成功加载的插件 ID 列表
        """
        loaded_plugins = []
        
        # 获取已启用的插件配置
        enabled_plugins = self._config_manager.get_setting('enabled_plugins', {})
        
        for plugin_id in load_order:
            # 检查插件是否已启用
            if plugin_id not in enabled_plugins or not enabled_plugins[plugin_id].get('enabled', False):
                self.logger.debug("plugin_manager", "plugin_disabled", f"插件已禁用：{plugin_id}")
                continue
                
            if self.load_plugin(plugin_id, enabled_plugins[plugin_id].get('config', {})):
                loaded_plugins.append(plugin_id)
                
        return loaded_plugins
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginManager")
    def load_plugin(self, plugin_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        加载指定插件
        
        Args:
            plugin_id: 插件 ID
            config: 插件配置
            
        Returns:
            bool: 加载是否成功
        """
        if plugin_id in self._plugins:
            self.logger.debug("plugin_manager", "plugin_already_loaded", f"插件已加载：{plugin_id}")
            return True
            
        if plugin_id not in self._plugin_metadata:
            self.logger.error("plugin_manager", "plugin_not_found", f"插件未发现：{plugin_id}")
            return False
            
        metadata = self._plugin_metadata[plugin_id]
        plugin_dir = os.path.join(self._plugin_dir, plugin_id)
        
        try:
            # 加载插件模块
            module = self._load_plugin_module(plugin_id, plugin_dir, metadata)
            if not module:
                return False
                
            self._plugin_modules[plugin_id] = module
            
            # 获取插件类
            plugin_class_name = metadata.main_class or metadata.id.title().replace('_', '') + 'Plugin'
            if not hasattr(module, plugin_class_name):
                self.logger.error("plugin_manager", "main_class_not_found", 
                                f"插件主类未找到：{plugin_id}.{plugin_class_name}")
                return False
                
            plugin_class = getattr(module, plugin_class_name)
            if not issubclass(plugin_class, PluginBase):
                self.logger.error("plugin_manager", "invalid_plugin_class", 
                                f"插件类不是 PluginBase 子类：{plugin_id}.{plugin_class_name}")
                return False
                
            # 创建插件实例
            plugin_instance = plugin_class()
            
            # 初始化插件
            if plugin_instance.initialize(config):
                self._plugins[plugin_id] = plugin_instance
                self.logger.info("plugin_manager", "plugin_loaded", 
                               f"插件加载成功：{plugin_id} v{metadata.version}")
                return True
            else:
                self.logger.error("plugin_manager", "plugin_init_failed", f"插件初始化失败：{plugin_id}")
                return False
                
        except Exception as e:
            self.logger.error("plugin_manager", "plugin_load_error", f"插件加载异常：{plugin_id}, 错误：{e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _load_plugin_module(self, plugin_id: str, plugin_dir: str, metadata: PluginMetadata) -> Optional[Any]:
        """加载插件模块"""
        # 尝试不同的主文件
        main_files = ['__init__.py', 'main.py', f"{plugin_id}.py"]
        
        for main_file in main_files:
            main_path = os.path.join(plugin_dir, main_file)
            if os.path.exists(main_path):
                try:
                    # 将插件目录添加到 sys.path，确保内部导入正常工作
                    if plugin_dir not in sys.path:
                        sys.path.insert(0, plugin_dir)
                    
                    if main_file == '__init__.py':
                        # 包形式加载 - 正确的方式
                        spec = importlib.util.spec_from_file_location(plugin_id, main_path)
                        if spec is None:
                            continue
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[plugin_id] = module
                        spec.loader.exec_module(module)  # type: ignore
                        return module
                    else:
                        # 单文件形式加载
                        spec = importlib.util.spec_from_file_location(plugin_id, main_path)
                        if spec is None:
                            continue
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[plugin_id] = module
                        spec.loader.exec_module(module)  # type: ignore
                        return module
                except Exception as e:
                    self.logger.error("plugin_manager", "module_load_error", 
                                    f"加载插件模块失败：{plugin_id}, 文件：{main_file}, 错误：{e}")
                    continue
                    
        self.logger.error("plugin_manager", "no_main_file", f"插件主文件未找到：{plugin_id}")
        return None
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginManager")
    def unload_plugin(self, plugin_id: str) -> bool:
        """
        卸载指定插件
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            bool: 卸载是否成功
        """
        if plugin_id not in self._plugins:
            self.logger.debug("plugin_manager", "plugin_not_loaded", f"插件未加载：{plugin_id}")
            return False
            
        try:
            # 调用插件的清理方法（如果存在）
            plugin = self._plugins[plugin_id]
            if hasattr(plugin, 'cleanup'):
                plugin.cleanup()
                
            # 清理插件模块
            if plugin_id in sys.modules:
                del sys.modules[plugin_id]
                
            # 从已加载插件中移除
            del self._plugins[plugin_id]
            
            # 如果插件有模块引用，也清理掉
            if plugin_id in self._plugin_modules:
                del self._plugin_modules[plugin_id]
                
            self.logger.info("plugin_manager", "plugin_unloaded", f"插件卸载成功：{plugin_id}")
            return True
            
        except Exception as e:
            self.logger.error("plugin_manager", "plugin_unload_error", f"插件卸载异常：{plugin_id}, 错误：{e}")
            return False
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return={}, component="PluginManager")
    def get_all_plugins(self) -> Dict[str, PluginBase]:
        """获取所有已加载的插件"""
        return self._plugins.copy()
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return={}, component="PluginManager")
    def get_available_plugins(self) -> Dict[str, Dict[str, Any]]:
        """获取所有可用插件的信息"""
        available_plugins = {}
        
        for plugin_id, metadata in self._plugin_metadata.items():
            available_plugins[plugin_id] = {
                'id': metadata.id,
                'name': metadata.name,
                'version': metadata.version,
                'description': metadata.description,
                'author': metadata.author,
                'dependencies': [dep.plugin_id for dep in metadata.dependencies],
                'required_dependencies': metadata.get_required_dependencies(),
                'optional_dependencies': metadata.get_optional_dependencies(),
                'load_order': metadata.load_order,
                'loaded': plugin_id in self._plugins,
                'enabled': self._is_plugin_enabled(plugin_id),
                'compatibility': {
                    'min_ocr_server_version': metadata.min_ocr_server_version,
                    'max_ocr_server_version': metadata.max_ocr_server_version
                }
            }
            
        return available_plugins
        
    def _is_plugin_enabled(self, plugin_id: str) -> bool:
        """检查插件是否已启用"""
        enabled_plugins = self._config_manager.get_setting('enabled_plugins', {})
        return enabled_plugins.get(plugin_id, {}).get('enabled', False)
        
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="PluginManager")
    def enable_plugin(self, plugin_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        启用插件
        
        Args:
            plugin_id: 插件 ID
            config: 插件配置
            
        Returns:
            bool: 启用是否成功
        """
        if plugin_id not in self._plugin_metadata:
            self.logger.error("plugin_manager", "plugin_not_found", f"插件未发现：{plugin_id}")
            return False
            
        # 更新配置
        enabled_plugins = self._config_manager.get_setting('enabled_plugins', {})
        enabled_plugins[plugin_id] = {
            'enabled': True,
            'config': config or {}
        }
        
        self._config_manager.set_setting('enabled_plugins', enabled_plugins)
        self._config_manager.save_config()
        
        # 如果已经初始化，尝试立即加载
        if self._initialized:
            return self.load_plugin(plugin_id, config)
            
        return True
        
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="PluginManager")
    def disable_plugin(self, plugin_id: str) -> bool:
        """
        禁用插件
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            bool: 禁用是否成功
        """
        # 更新配置
        enabled_plugins = self._config_manager.get_setting('enabled_plugins', {})
        if plugin_id in enabled_plugins:
            enabled_plugins[plugin_id]['enabled'] = False
            self._config_manager.set_setting('enabled_plugins', enabled_plugins)
            self._config_manager.save_config()
            
        # 卸载插件（如果已加载）
        return self.unload_plugin(plugin_id)
        
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="PluginManager")
    def update_plugin_config(self, plugin_id: str, new_config: Dict[str, Any]) -> bool:
        """
        更新插件配置
        
        Args:
            plugin_id: 插件 ID
            new_config: 新配置
            
        Returns:
            bool: 更新是否成功
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            self.logger.error("plugin_manager", "plugin_not_loaded", f"插件未加载：{plugin_id}")
            return False
            
        if plugin.update_config(new_config):
            # 保存配置到全局配置
            enabled_plugins = self._config_manager.get_setting('enabled_plugins', {})
            if plugin_id in enabled_plugins:
                enabled_plugins[plugin_id]['config'] = new_config
                self._config_manager.set_setting('enabled_plugins', enabled_plugins)
                self._config_manager.save_config()
                
            return True
        return False
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginManager")
    def _connect_event_bus(self):
        """连接事件总线，将事件分发给插件"""
        try:
            # OCR 结果就绪事件
            self._event_bus.processing.task_completed.connect(
                lambda data: self._dispatch_ocr_result_event(data)
            )
            
            # 批量处理开始事件
            self._event_bus.processing.status_updated.connect(
                lambda msg, status: self._dispatch_batch_start_event(msg, status)
            )
            
            # 批量处理完成事件
            self._event_bus.processing.processing_finished.connect(
                lambda time: self._dispatch_batch_complete_event(time)
            )
            
            # 🔥 处理后结果就绪事件（完整结果数据）
            self._event_bus.processing.processed_result_ready.connect(
                lambda result_data: self._dispatch_processed_result_event(result_data)
            )
            
            self.logger.debug("plugin_manager", "event_bus_connected", "事件总线连接成功")
            
        except Exception as e:
            self.logger.error("plugin_manager", "event_bus_connect_error", f"事件总线连接失败：{e}")
            
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginManager")
    def _dispatch_processed_result_event(self, result_data: Dict[str, Any]):
        """分发处理后结果事件到所有插件"""
        for plugin in self._plugins.values():
            try:
                if hasattr(plugin, 'on_processed_result_ready'):
                    plugin.on_processed_result_ready(result_data)
            except Exception as e:
                self.logger.error("plugin_manager", "plugin_event_error", 
                                f"插件事件处理异常：{plugin.name}, 错误：{e}")
                
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginManager")
    def _dispatch_ocr_result_event(self, result_data: Dict[str, Any]):
        """分发 OCR 结果事件到所有插件"""
        for plugin in self._plugins.values():
            try:
                plugin.on_ocr_result_ready(result_data)
            except Exception as e:
                self.logger.error("plugin_manager", "plugin_event_error", 
                                f"插件事件处理异常：{plugin.name}, 错误：{e}")
                
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginManager")
    def _dispatch_batch_start_event(self, message: str, status: str):
        """分发批量处理开始事件到所有插件"""
        if '批量处理' in message and status == 'working':
            try:
                file_count = 1  # 简化处理
                for plugin in self._plugins.values():
                    try:
                        plugin.on_batch_processing_start(file_count)
                    except Exception as e:
                        self.logger.error("plugin_manager", "plugin_event_error", 
                                        f"插件事件处理异常：{plugin.name}, 错误：{e}")
            except Exception as e:
                self.logger.error("plugin_manager", "batch_start_parse_error", f"批量开始事件解析失败：{e}")
                
    @handle_errors(error_code=ErrorCode.DEPENDENCY, component="PluginManager")
    def _dispatch_batch_complete_event(self, processing_time: float):
        """分发批量处理完成事件到所有插件"""
        success_count = 1
        total_count = 1
        
        for plugin in self._plugins.values():
            try:
                plugin.on_batch_processing_complete(success_count, total_count)
            except Exception as e:
                self.logger.error("plugin_manager", "plugin_event_error", 
                                f"插件事件处理异常：{plugin.name}, 错误：{e}")
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return={}, component="PluginManager")
    def get_plugin_status(self) -> Dict[str, Any]:
        """获取插件系统状态"""
        return {
            'total_discovered': len(self._plugin_metadata),
            'total_loaded': len(self._plugins),
            'plugins': {id: plugin.get_status() for id, plugin in self._plugins.items()},
            'plugin_dir': self._plugin_dir
        }
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=None, component="PluginManager")
    def get_plugin(self, plugin_id: str) -> Optional[PluginBase]:
        """获取指定插件实例"""
        return self._plugins.get(plugin_id)
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginManager")
    def reload_plugin(self, plugin_id: str) -> bool:
        """
        重新加载指定插件（开发模式使用）
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            bool: 重新加载是否成功
        """
        if plugin_id not in self._plugin_metadata:
            self.logger.error("plugin_manager", "plugin_not_found", f"插件未发现：{plugin_id}")
            return False
            
        # 卸载现有插件
        self.unload_plugin(plugin_id)
        
        # 重新加载元数据（可能已更新）
        plugin_dir = os.path.join(self._plugin_dir, plugin_id)
        metadata_file = os.path.join(plugin_dir, 'plugin.json')
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
            self._plugin_metadata[plugin_id] = PluginMetadata.from_dict(metadata_dict)
        except Exception as e:
            self.logger.error("plugin_manager", "metadata_reload_error", 
                            f"重新加载插件元数据失败：{plugin_id}, 错误：{e}")
            return False
            
        # 重新加载插件
        enabled_plugins = self._config_manager.get_setting('enabled_plugins', {})
        config = enabled_plugins.get(plugin_id, {}).get('config', {})
        return self.load_plugin(plugin_id, config)
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginManager")
    def check_and_reload_modified_plugins(self) -> List[str]:
        """
        检查并重新加载已修改的插件（开发模式使用）
        
        Returns:
            List[str]: 重新加载的插件 ID 列表
        """
        if not self._initialized:
            return []
            
        reloaded_plugins = []
        
        for plugin_id in self._plugins.keys():
            plugin_dir = os.path.join(self._plugin_dir, plugin_id)
            
            # 检查主文件是否修改
            main_files = ['__init__.py', 'main.py', f"{plugin_id}.py"]
            modified = False
            
            for main_file in main_files:
                main_path = os.path.join(plugin_dir, main_file)
                if os.path.exists(main_path):
                    current_mtime = os.path.getmtime(main_path)
                    if (plugin_id not in self._plugin_file_timestamps or 
                        current_mtime > self._plugin_file_timestamps[plugin_id]):
                        self._plugin_file_timestamps[plugin_id] = current_mtime
                        modified = True
                        break
                        
            if modified:
                self.logger.info("plugin_manager", "plugin_modified", 
                               f"检测到插件修改，正在重新加载：{plugin_id}")
                if self.reload_plugin(plugin_id):
                    reloaded_plugins.append(plugin_id)
                    self.logger.info("plugin_manager", "plugin_reloaded", 
                                   f"插件重新加载成功：{plugin_id}")
                else:
                    self.logger.error("plugin_manager", "plugin_reload_failed", 
                                    f"插件重新加载失败：{plugin_id}")
                    
        return reloaded_plugins
        
    def set_main_window(self, main_window: Any):
        """
        设置主窗口引用
        
        Args:
            main_window: 主窗口实例
        """
        self._main_window = main_window
        
    def get_main_window(self) -> Optional[Any]:
        """
        获取主窗口引用
        
        Returns:
            MainWindow: 主窗口实例
        """
        return self._main_window