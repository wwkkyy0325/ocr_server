# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
import re
from app.infrastructure.error_handler import handle_errors, ErrorCode


@dataclass
class ConfigItem:
    """配置项定义 - 受 Minecraft Forge 启发"""
    key: str
    default: Any
    type: type
    description: str
    category: str = "general"  # 配置分类
    comment: str = ""  # 详细注释说明
    valid_values: Optional[List[Any]] = None  # 有效值列表（枚举）
    min_value: Optional[Union[int, float]] = None  # 最小值（数值类型）
    max_value: Optional[Union[int, float]] = None  # 最大值（数值类型）
    validator: Optional[Callable[[Any], bool]] = None  # 自定义验证函数
    restart_required: bool = False  # 是否需要重启生效
    deprecated: bool = False  # 是否已废弃
    hidden: bool = False  # 是否在 UI 中隐藏
    plugin_id: Optional[str] = None  # 插件 ID（如果是插件注册的配置项）
    
    def __post_init__(self):
        """初始化后处理"""
        if self.comment == "":
            self.comment = self.description
            
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return=False, component="ConfigItem")
    def is_valid(self, value: Any) -> bool:
        """验证值是否有效"""
        # 类型检查
        if not isinstance(value, self.type):
            return False
            
        # 枚举值检查
        if self.valid_values is not None and value not in self.valid_values:
            return False
            
        # 数值范围检查
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
            
        # 自定义验证
        if self.validator is not None and not self.validator(value):
            return False
            
        return True


class ConfigSchema:
    """
    配置项模式定义
    受 Minecraft Forge 配置系统启发，提供更强大的配置管理能力
    """

    # 定义所有合法的配置项 - 按类别组织
    ITEMS = [
        # --- 模型配置 (models) ---
        ConfigItem(
            'det_model_key', 
            'PP-OCRv5_mobile_det', 
            str, 
            '检测模型 Key',
            category='models',
            comment='用于文本检测的模型标识符。不同的模型适用于不同的场景和精度要求。',
            restart_required=True
        ),
        ConfigItem(
            'rec_model_key', 
            'PP-OCRv5_mobile_rec', 
            str, 
            '识别模型 Key',
            category='models',
            comment='用于文本识别的模型标识符。选择合适的识别模型可以提高准确率。',
            restart_required=True
        ),
        ConfigItem(
            'cls_model_key', 
            'PP-LCNet_x1_0_textline_ori', 
            str, 
            '方向分类模型 Key',
            category='models',
            comment='用于文本行方向分类的模型标识符。',
            restart_required=True
        ),
        ConfigItem(
            'doc_ori_model_key', 
            'PP-LCNet_x1_0_doc_ori', 
            str, 
            '文档矫正模型 Key',
            category='models',
            comment='用于文档方向矫正的模型标识符。',
            restart_required=True
        ),
        ConfigItem(
            'unwarp_model_key', 
            'UVDoc', 
            str, 
            '弯曲矫正模型 Key',
            category='models',
            comment='用于文档弯曲矫正的模型标识符。',
            restart_required=True
        ),

        # --- OCR 参数 (ocr) ---
        ConfigItem(
            'precision', 
            'fp32', 
            str, 
            '推理精度',
            category='ocr',
            comment='模型推理精度设置，影响性能和准确性。',
            valid_values=['fp32', 'fp16', 'int8'],
            restart_required=True
        ),
        ConfigItem(
            'batch_size', 
            1, 
            int, 
            '批处理大小',
            category='ocr',
            comment='每次推理处理的图像数量。增加批处理大小可以提高吞吐量，但会增加内存使用。',
            min_value=1,
            max_value=32
        ),
        ConfigItem(
            'gpu_memory_fraction', 
            0.8, 
            float, 
            'GPU 内存占用比例',
            category='ocr',
            comment='PaddlePaddle 使用的 GPU 内存比例（0.0-1.0）。调整此值可以平衡 OCR 和其他 GPU 应用的内存使用。',
            min_value=0.1,
            max_value=1.0
        ),

        # --- 功能开关 (features) ---
        ConfigItem(
            'use_cls_model', 
            False, 
            bool, 
            '启用方向分类',
            category='features',
            comment='启用文本行方向分类功能。对于包含旋转文本的文档很有用。'
        ),
        ConfigItem(
            'use_doc_ori_model', 
            False, 
            bool, 
            '启用文档矫正',
            category='features',
            comment='启用文档整体方向矫正功能。自动检测并矫正文档的方向。'
        ),
        ConfigItem(
            'use_unwarp_model', 
            False, 
            bool, 
            '启用弯曲矫正',
            category='features',
            comment='启用文档弯曲矫正功能。对于扫描的弯曲文档特别有用。'
        ),
        ConfigItem(
            'use_ai_table', 
            False, 
            bool, 
            '启用 AI 表格结构识别',
            category='features',
            comment='启用 AI 驱动的表格结构识别功能。可以更准确地识别复杂表格。'
        ),

        # --- UI 外观 (ui) ---
        ConfigItem(
            'theme', 
            'cyber_neon', 
            str, 
            '界面主题',
            category='ui',
            comment='应用程序的视觉主题。不同的主题提供不同的颜色方案和外观。',
            valid_values=['classic', 'cyber_neon', 'dark_mode', 'light_mode']
        ),
        ConfigItem(
            'glass_background', 
            'dots', 
            str, 
            '背景风格',
            category='ui',
            comment='主窗口的背景效果风格。',
            valid_values=['glass', 'dots', 'frosted', 'none']
        ),
        ConfigItem(
            'auto_save_interval', 
            300, 
            int, 
            '自动保存间隔（秒）',
            category='ui',
            comment='自动保存配置的时间间隔（秒）。设置为 0 禁用自动保存。',
            min_value=0,
            max_value=3600
        ),

        # --- 性能与子进程 (performance) ---
        ConfigItem(
            'use_ocr_subprocess', 
            True, 
            bool, 
            '启用 OCR 子进程模式',
            category='performance',
            comment='在独立的子进程中运行 OCR 任务，避免阻塞主 UI 线程。推荐保持启用。',
            restart_required=True
        ),
        ConfigItem(
            'max_workers', 
            4, 
            int, 
            '最大工作线程数',
            category='performance',
            comment='用于处理 OCR 任务的最大并发工作线程数。根据 CPU 核心数调整。',
            min_value=1,
            max_value=16
        ),
        ConfigItem(
            'current_ocr_preset', 
            'mobile', 
            str, 
            '当前 OCR 预设',
            category='performance',
            comment='OCR 预设配置，影响模型选择和性能权衡。',
            valid_values=['mobile', 'server', 'ai_table', 'high_accuracy']
        ),

        # --- 文件与路径 (paths) ---
        ConfigItem(
            'output_directory', 
            '', 
            str, 
            '默认输出目录',
            category='paths',
            comment='OCR 结果的默认保存目录。留空则使用输入文件所在目录。'
        ),
        ConfigItem(
            'temp_directory', 
            '', 
            str, 
            '临时文件目录',
            category='paths',
            comment='处理过程中的临时文件存储目录。留空则使用系统临时目录。'
        ),
        
        # --- 网络与 API (network) ---
        ConfigItem(
            'api_enabled', 
            False, 
            bool, 
            '启用 HTTP API 服务',
            category='network',
            comment='启用内置的 HTTP API 服务，允许外部程序调用 OCR 功能。',
            restart_required=True
        ),
        ConfigItem(
            'api_port', 
            8080, 
            int, 
            'API 服务端口',
            category='network',
            comment='HTTP API 服务监听的端口号。',
            min_value=1024,
            max_value=65535,
            restart_required=True
        ),
    ]

    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return={}, component="ConfigSchema")
    def get_default_config(cls) -> Dict[str, Any]:
        """获取默认配置字典"""
        return {item.key: item.default for item in cls.ITEMS if not item.deprecated}

    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_INVALID_001, fallback_return={}, component="ConfigSchema")
    def validate_and_clean(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验配置并清理：
        1. 补全缺失的默认值
        2. 类型强制转换
        3. 验证值的有效性
        """
        cleaned = config.copy()

        # 获取所有配置项（包括插件注册的）
        all_items = cls.get_all_config_items()
        
        # 1. 补全缺失
        for item in all_items:
            if item.key not in cleaned:
                cleaned[item.key] = item.default

        # 2. 类型强制转换和验证
        for item in all_items:
            if item.key in cleaned:
                val = cleaned[item.key]
                if val is not None and not isinstance(val, item.type):
                    try:
                        # 尝试转换类型
                        if item.type == bool:
                            cleaned[item.key] = str(val).lower() in ('true', '1', 'yes', 'on')
                        elif item.type == int:
                            cleaned[item.key] = int(float(val))  # 先转 float 再转 int，处理字符串数字
                        elif item.type == float:
                            cleaned[item.key] = float(val)
                        else:
                            cleaned[item.key] = item.type(val)
                    except Exception as e:
                        from app.log.log_bus import get_logger
                        logger = get_logger()
                        logger.warning("config_schema", "type_mismatch", f"配置项 {item.key} 类型不匹配，使用默认值：{e}")
                        cleaned[item.key] = item.default
                
                # 3. 验证值的有效性
                if not item.is_valid(cleaned[item.key]):
                    from app.log.log_bus import get_logger
                    logger = get_logger()
                    logger.warning("config_schema", "validation_failed", f"配置项 {item.key} 值无效，使用默认值")
                    cleaned[item.key] = item.default

        return cleaned
        
    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigSchema")
    def get_categories(cls) -> List[str]:
        """获取所有配置分类"""
        categories = set()
        all_items = cls.get_all_config_items()
        for item in all_items:
            if not item.deprecated and not item.hidden:
                categories.add(item.category)
        return sorted(list(categories))
        
    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigSchema")
    def get_items_by_category(cls, category: str) -> List[ConfigItem]:
        """根据分类获取配置项"""
        all_items = cls.get_all_config_items()
        return [item for item in all_items if item.category == category and not item.deprecated and not item.hidden]
        
    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="ConfigSchema")
    def get_item_by_key(cls, key: str) -> Optional[ConfigItem]:
        """根据键名获取配置项定义"""
        all_items = cls.get_all_config_items()
        for item in all_items:
            if item.key == key:
                return item
        return None
        
    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=[], component="ConfigSchema")
    def get_all_config_items(cls) -> List[ConfigItem]:
        """获取所有配置项（包括核心和插件注册的）"""
        from app.config.plugin_config_registry import PluginConfigRegistry
        
        # 获取核心配置项
        core_items = cls.ITEMS.copy()
        
        # 获取插件配置项
        plugin_registry = PluginConfigRegistry.get_instance()
        plugin_items = plugin_registry.get_all_config_items()
        
        # 合并并检查冲突
        all_items = core_items + plugin_items
        
        # 检查键名冲突
        seen_keys = set()
        unique_items = []
        for item in all_items:
            if item.key not in seen_keys:
                seen_keys.add(item.key)
                unique_items.append(item)
            else:
                from app.log.log_bus import get_logger
                logger = get_logger()
                logger.error("config_schema", "key_conflict", f"配置项键名冲突：{item.key}")
        
        return unique_items
        
    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return="", component="ConfigSchema")
    def generate_documentation(cls) -> str:
        """生成配置文档（类似 Forge 的配置文档）"""
        from datetime import datetime
        
        content = f"""# OCR Server Configuration Documentation
Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This documentation describes all available configuration options.

## Configuration Structure

The configuration is organized into the following categories:
"""
        
        # 按分类组织配置项
        categories = cls.get_categories()
        for category in categories:
            items = cls.get_items_by_category(category)
            if not items:
                continue
                
            content += f"\n### {category.title()} Configuration\n"
            
            for item in items:
                content += f"\n#### `{item.key}`\n"
                content += f"- **Type**: `{item.type.__name__}`\n"
                content += f"- **Default**: `{json.dumps(item.default)}`\n"
                content += f"- **Description**: {item.description}\n"
                
                if item.comment and item.comment != item.description:
                    content += f"- **Details**: {item.comment}\n"
                
                if item.valid_values:
                    content += f"- **Valid Values**: {item.valid_values}\n"
                elif item.min_value is not None or item.max_value is not None:
                    range_info = []
                    if item.min_value is not None:
                        range_info.append(f"min: {item.min_value}")
                    if item.max_value is not None:
                        range_info.append(f"max: {item.max_value}")
                    if range_info:
                        content += f"- **Range**: {' | '.join(range_info)}\n"
                
                if item.restart_required:
                    content += "- **Restart Required**: Yes\n"
                else:
                    content += "- **Restart Required**: No\n"
                
                if item.plugin_id:
                    content += f"- **Plugin**: `{item.plugin_id}`\n"
        
        return content