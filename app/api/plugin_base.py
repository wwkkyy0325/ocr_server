# -*- coding: utf-8 -*-
"""
插件基类 - 定义标准插件接口

作用：为所有插件提供统一的接口规范，确保插件系统的松耦合性

插件必须实现的核心方法：
- initialize(): 插件初始化
- get_name(): 返回插件名称  
- get_version(): 返回插件版本
- get_description(): 返回插件描述

可选实现的方法：
- on_ocr_result_ready(): OCR 结果就绪时调用
- on_batch_processing_start(): 批量处理开始时调用
- on_batch_processing_complete(): 批量处理完成时调用
- get_config_schema(): 返回插件配置模式
- validate_config(): 验证插件配置
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from app.log.log_bus import get_logger
from app.api.plugin_event_bus import PluginEventBus
from app.ui.ui_extension_manager import UIComponentType, UIComponentConfig
from app.config.config_schema import ConfigItem
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginBase(ABC):
    """
    插件基类 - 所有插件必须继承此类
    
    Attributes:
        name: 插件名称
        version: 插件版本
        description: 插件描述
        config: 插件配置字典
        logger: 插件专用日志记录器
        _event_bus: 插件间事件总线
    """
    
    def __init__(self):
        self.name = self.get_name()
        self.version = self.get_version()
        self.description = self.get_description()
        self.config: Dict[str, Any] = {}
        self.logger = get_logger()
        self._event_bus = PluginEventBus.get_instance()
        
    @abstractmethod
    def get_name(self) -> str:
        """返回插件名称"""
        
    @abstractmethod
    def get_version(self) -> str:
        """返回插件版本"""
        
    @abstractmethod
    def get_description(self) -> str:
        """返回插件描述"""
        
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=False, component="PluginBase")
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        插件初始化
        
        Args:
            config: 插件配置字典
            
        Returns:
            bool: 初始化是否成功
        """
        if config is not None:
            self.config = config
            
        self.logger.info("plugin", "initializing", f"正在初始化插件：{self.name} v{self.version}")
        success = self._initialize_impl()
        if success:
            self.logger.info("plugin", "initialized", f"插件初始化成功：{self.name}")
        else:
            self.logger.error("plugin", "init_failed", f"插件初始化失败：{self.name}")
        return success
        
    def _initialize_impl(self) -> bool:
        """
        插件初始化的具体实现（子类可重写）
        默认实现返回 True
        """
        return True
        
    def on_ocr_result_ready(self, result_data: Dict[str, Any]) -> None:
        """
        OCR 结果就绪事件回调
        
        Args:
            result_data: OCR 结果数据
        """
        pass
        
    def on_batch_processing_start(self, file_count: int) -> None:
        """
        批量处理开始事件回调
        
        Args:
            file_count: 文件数量
        """
        pass
        
    def on_batch_processing_complete(self, success_count: int, total_count: int) -> None:
        """
        批量处理完成事件回调
        
        Args:
            success_count: 成功处理的数量
            total_count: 总处理数量
        """
        pass
        
    def on_processed_result_ready(self, result_data: Dict[str, Any]) -> None:
        """
        处理后结果就绪事件回调
        
        在 OCR 结果处理完成后、UI 渲染前触发，包含完整的处理结果数据
        
        Args:
            result_data: 完整的处理结果数据，包含以下字段：
                - filename: 文件名
                - image_path: 图像路径  
                - full_text: 完整文本
                - regions: 详细区域信息列表
                - metadata: 元数据信息
        """
        pass
        
    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取插件配置模式（子类可重写）
        返回 JSON Schema 格式的配置模式
        """
        return {}
        
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证插件配置（子类可重写）
        
        Args:
            config: 待验证的配置
            
        Returns:
            bool: 配置是否有效
        """
        return True
        
    @handle_errors(error_code=ErrorCode.CONFIG_SAVE_001, fallback_return=False, component="PluginBase")
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新插件配置
        
        Args:
            new_config: 新的配置字典
            
        Returns:
            bool: 更新是否成功
        """
        if self.validate_config(new_config):
            old_config = self.config.copy()
            self.config.update(new_config)
            
            # 调用配置更新钩子
            self.on_config_updated(old_config, new_config)
            self.logger.debug("plugin", "config_updated", f"插件配置已更新：{self.name}")
            return True
        else:
            self.logger.warning("plugin", "config_invalid", f"插件配置无效：{self.name}")
            return False
            
    def on_config_updated(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> None:
        """
        配置更新后的回调（子类可重写）
        
        Args:
            old_config: 旧配置
            new_config: 新配置
        """
        pass
        
    def get_status(self) -> Dict[str, Any]:
        """
        获取插件状态信息
        
        Returns:
            Dict: 插件状态信息
        """
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'enabled': True,
            'initialized': hasattr(self, '_initialized') and self._initialized
        }
        
    # ========== 插件间事件系统接口 ==========
    
    def publish_event(self, event_name: str, event_data: Dict[str, Any]) -> int:
        """
        发布插件间事件
        
        Args:
            event_name: 事件名称
            event_data: 事件数据
            
        Returns:
            int: 订阅者数量
        """
        return PluginEventBus.get_instance().publish(event_name, event_data)
        
    def subscribe_event(self, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        订阅插件间事件
        
        Args:
            event_name: 事件名称
            callback: 回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        return PluginEventBus.get_instance().subscribe(self.name, event_name, callback)
    
    # 🔥 添加 UI 扩展方法
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=False, component="PluginBase")
    def register_ui_component(
        self, 
        component_type: UIComponentType,
        component_id: str,
        label: str,
        callback: Optional[Callable] = None,
        **kwargs
    ) -> bool:
        """
        注册 UI组件到主窗口
        
        Args:
            component_type: 组件类型
            component_id: 组件 ID（插件内唯一）
            label: 显示标签
            callback: 点击回调函数
            **kwargs: 其他配置参数（icon_path, tooltip, position, priority, widget 等）
            
        Returns:
            bool: 注册是否成功
        """
        from app.api.plugin_api import PluginAPI
        api = PluginAPI.get_instance()
        
        # 获取主窗口
        main_window = api.get_main_window()
        if not main_window:
            return False
            
        # 创建组件配置
        config = UIComponentConfig(
            component_type=component_type,
            plugin_id=self.name,
            component_id=component_id,
            label=label,
            **kwargs
        )
        
        # 单独设置 callback，因为 UIComponentConfig 没有 callback 字段作为构造参数
        config.callback = callback
        
        return main_window.ui_extension_manager.register_ui_component(config)
        
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=False, component="PluginBase")
    def unregister_ui_component(self, component_id: str) -> bool:
        """
        注销 UI组件
        
        Args:
            component_id: 组件 ID
            
        Returns:
            bool: 注销是否成功
        """
        from app.api.plugin_api import PluginAPI
        api = PluginAPI.get_instance()
        
        main_window = api.get_main_window()
        if not main_window:
            return False
            
        return main_window.ui_extension_manager.unregister_ui_component(self.name, component_id)
        
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="PluginBase")
    def get_main_window(self):
        """
        获取主窗口实例
        
        Returns:
            MainWindow: 主窗口实例
        """
        from app.api.plugin_api import PluginAPI
        api = PluginAPI.get_instance()
        return api.get_main_window()
        
    # 🔥 添加便捷的 UI组件创建方法
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=False, component="PluginBase")
    def create_button(
        self,
        component_id: str,
        label: str,
        callback: Optional[Callable] = None,
        **kwargs
    ) -> bool:
        """
        创建并注册按钮组件
        
        Args:
            component_id: 组件 ID
            label: 按钮标签
            callback: 点击回调
            **kwargs: 其他参数（icon_path, tooltip, position, priority 等）
            
        Returns:
            bool: 注册是否成功
        """
        from app.ui.ui_component_factory import UIComponentFactory
        from app.ui.ui_extension_manager import UIComponentType
        
        # 创建按钮 widget
        widget = UIComponentFactory.create_button(label, callback, **kwargs)
        if not widget:
            return False
            
        # 注册到 UI 扩展管理器
        return self.register_ui_component(
            UIComponentType.MAIN_WINDOW_BUTTON,
            component_id,
            label,
            callback,
            widget=widget,
            **kwargs
        )
        
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=False, component="PluginBase")
    def create_menu_action(
        self,
        component_id: str,
        label: str,
        callback: Optional[Callable] = None,
        **kwargs
    ) -> bool:
        """
        创建并注册菜单动作
        
        Args:
            component_id: 组件 ID
            label: 菜单标签
            callback: 触发回调
            **kwargs: 其他参数（icon_path, shortcut, tooltip, position 等）
            
        Returns:
            bool: 注册是否成功
        """
        from app.ui.ui_component_factory import UIComponentFactory
        from app.ui.ui_extension_manager import UIComponentType
        
        # 创建菜单动作
        widget = UIComponentFactory.create_menu_action(label, callback, **kwargs)
        if not widget:
            return False
            
        # 注册到 UI 扩展管理器
        return self.register_ui_component(
            UIComponentType.MENU_ACTION,
            component_id,
            label,
            callback,
            widget=widget,
            **kwargs
        )
        
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=False, component="PluginBase")
    def create_status_widget(
        self,
        component_id: str,
        text: str,
        **kwargs
    ) -> bool:
        """
        创建并注册状态栏组件
        
        Args:
            component_id: 组件 ID
            text: 显示文本
            **kwargs: 其他参数（tooltip 等）
            
        Returns:
            bool: 注册是否成功
        """
        from app.ui.ui_component_factory import UIComponentFactory
        from app.ui.ui_extension_manager import UIComponentType
        
        # 创建状态标签
        widget = UIComponentFactory.create_status_label(text, **kwargs)
        if not widget:
            return False
            
        # 注册到 UI 扩展管理器
        return self.register_ui_component(
            UIComponentType.STATUS_BAR_WIDGET,
            component_id,
            text,
            widget=widget,
            **kwargs
        )
        
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return=False, component="PluginBase")
    def register_config_item(self, key: str, default: Any, type_: type, 
                           description: str, category: str = "plugin", 
                           **kwargs) -> bool:
        """
        注册插件配置项到主配置系统
        
        Args:
            key: 配置项键名（必须全局唯一）
            default: 默认值
            type_: 配置项类型
            description: 配置项描述
            category: 配置分类（默认为"plugin"）
            **kwargs: 其他配置项参数（valid_values, min_value, max_value, restart_required 等）
            
        Returns:
            bool: 注册是否成功
        """
        try:
            # 创建配置项
            config_item = ConfigItem(
                key=key,
                default=default,
                type=type_,
                description=description,
                category=category,
                **kwargs
            )
            
            # 获取配置管理器并注册
            from app.config.config_manager import ConfigManager
            config_manager = ConfigManager()
            plugin_id = self.get_plugin_id() if hasattr(self, 'get_plugin_id') else self.name
            
            success = config_manager.register_plugin_config_item(plugin_id, config_item)
            
            if success:
                self.logger.debug("plugin_base", "config_registered", 
                                f"插件 {plugin_id} 成功注册配置项：{key}")
            else:
                self.logger.error("plugin_base", "config_register_failed", 
                                f"插件 {plugin_id} 注册配置项失败：{key}")
                
            return success
            
        except Exception as e:
            self.logger.error("plugin_base", "config_register_error", 
                            f"插件 {self.name} 注册配置项异常：{e}")
            return False
    
    def get_plugin_id(self) -> str:
        """
        获取插件 ID（用于配置注册）
        子类可以重写此方法以提供自定义插件 ID
        """
        return self.name