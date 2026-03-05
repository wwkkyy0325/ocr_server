# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ConfigItem:
    key: str
    default: Any
    type: type
    description: str
    deprecated: bool = False
    
class ConfigSchema:
    """
    配置项模式定义
    用于校验配置完整性、提供默认值、清理废弃项
    """
    
    # 定义所有合法的配置项
    ITEMS = [
        # --- 基础路径与环境 ---
        ConfigItem('model_path', '', str, '模型根目录 (仅展示用)', deprecated=True),
        ConfigItem('use_gpu', False, bool, '是否使用 GPU (废弃，由环境自动检测)', deprecated=True),
        
        # --- 模型 Key (用于查找) ---
        # 注意：这里的默认值仅作为 fallback，实际加载时应优先询问 ModelManager
        ConfigItem('det_model_key', '', str, '检测模型 Key'),
        ConfigItem('rec_model_key', '', str, '识别模型 Key'),
        ConfigItem('cls_model_key', '', str, '方向分类模型 Key'),
        ConfigItem('doc_ori_model_key', '', str, '文档矫正模型 Key'),
        ConfigItem('unwarp_model_key', '', str, '弯曲矫正模型 Key'),
        ConfigItem('table_model_key', '', str, '表格识别模型 Key'),
        
        # --- 模型绝对路径 (运行时自动生成，但需持久化以便子进程读取) ---
        ConfigItem('det_model_dir', '', str, '检测模型路径 (运行时计算)', deprecated=True),
        ConfigItem('rec_model_dir', '', str, '识别模型路径 (运行时计算)', deprecated=True),
        ConfigItem('cls_model_dir', '', str, '方向分类模型路径 (运行时计算)', deprecated=True),
        ConfigItem('doc_ori_model_dir', '', str, '文档矫正模型路径 (运行时计算)', deprecated=True),
        ConfigItem('unwarp_model_dir', '', str, '弯曲矫正模型路径 (运行时计算)', deprecated=True),
        ConfigItem('table_model_dir', '', str, '表格识别模型路径 (运行时计算)', deprecated=True),
        
        # --- OCR 参数 ---
        ConfigItem('precision', 'fp32', str, '推理精度 (fp32/fp16/int8)'),
        ConfigItem('rec_image_shape', '3, 32, 320', str, '识别图片形状'),
        ConfigItem('use_space_char', True, bool, '是否输出空格'),
        ConfigItem('max_text_length', 25, int, '最大文本长度 (已废弃)', deprecated=True),
        ConfigItem('drop_score', 0.5, float, '丢弃低置信度结果的阈值 (已废弃)', deprecated=True),
        
        # --- 功能开关 ---
        ConfigItem('use_cls_model', False, bool, '启用方向分类'),
        ConfigItem('use_doc_ori_model', False, bool, '启用文档矫正'),
        ConfigItem('use_unwarp_model', False, bool, '启用弯曲矫正'),
        
        # --- 表格识别 ---
        ConfigItem('use_table_split', False, bool, '启用传统表格拆分'),
        ConfigItem('table_split_mode', 'vertical', str, '传统拆分模式 (vertical/horizontal)'),
        ConfigItem('table_split_mode_index', 0, int, '传统拆分模式索引 (兼容旧代码)', deprecated=True),
        ConfigItem('use_ai_table', False, bool, '启用 AI 表格结构识别'),
        
        # --- 蒙版 (Mask) ---
        ConfigItem('use_mask', False, bool, '启用蒙版'),
        ConfigItem('use_adaptive_mask', False, bool, '启用自适应蒙版'),
        ConfigItem('mask_padding', 10, int, '蒙版内缩/外扩像素'),
        
        # --- 性能与多进程 ---
        ConfigItem('cpu_limit', 70, int, 'CPU 使用率限制 (%) (已废弃)', deprecated=True),
        ConfigItem('max_processing_time', 30, int, '单张图片最大处理时间 (秒) (已废弃)', deprecated=True),
        ConfigItem('processing_processes', 1, int, '并发进程数'),
        
        # --- UI 外观 ---
        ConfigItem('theme', 'cyber_neon', str, '界面主题'),
        ConfigItem('glass_background', 'dots', str, '背景风格 (glass/dots/frosted)'),
        
        # --- 杂项/预处理 ---
        ConfigItem('use_preprocessing', True, bool, '启用图像预处理 (已废弃)', deprecated=True),
        ConfigItem('use_skew_correction', True, bool, '启用倾斜校正 (已废弃)', deprecated=True),
        ConfigItem('use_padding', False, bool, '启用图像填充 (已废弃)', deprecated=True),
        
        # --- 废弃项 (将被自动清理) ---
        ConfigItem('ai_table_model', '', str, 'AI 表格模型别名', deprecated=True),
        ConfigItem('enable_advanced_doc', False, bool, '高级文档理解', deprecated=True),
        ConfigItem('interactive_selection', False, bool, '交互式选择', deprecated=True),
        ConfigItem('use_center_priority', False, bool, '中心优先', deprecated=True),
        ConfigItem('default_coordinates', '', str, '默认坐标', deprecated=True),
    ]
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """获取默认配置字典"""
        return {item.key: item.default for item in cls.ITEMS if not item.deprecated}
        
    @classmethod
    def validate_and_clean(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验配置并清理：
        1. 补全缺失的默认值
        2. 移除废弃项 (Deprecated)
        3. 移除未定义项 (Unknown) - 谨慎操作，这里选择保留未知项以防插件扩展，仅清理明确废弃的
        """
        cleaned = config.copy()
        
        # 1. 补全缺失
        for item in cls.ITEMS:
            if not item.deprecated and item.key not in cleaned:
                cleaned[item.key] = item.default
                
        # 2. 清理废弃
        for item in cls.ITEMS:
            if item.deprecated and item.key in cleaned:
                print(f"[Config] Removing deprecated key: {item.key}")
                del cleaned[item.key]
                
        # 3. 类型强制转换 (可选)
        for item in cls.ITEMS:
            if not item.deprecated and item.key in cleaned:
                val = cleaned[item.key]
                if val is not None and not isinstance(val, item.type):
                    try:
                        # 尝试转换类型
                        if item.type == bool:
                            cleaned[item.key] = str(val).lower() in ('true', '1', 'yes')
                        else:
                            cleaned[item.key] = item.type(val)
                    except:
                        print(f"[Config] Type mismatch for {item.key}, using default")
                        cleaned[item.key] = item.default
                        
        return cleaned
