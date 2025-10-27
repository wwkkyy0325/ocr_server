# Path: src/app/core/config_manager.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理（保存模型路径、识别参数）
"""

import json
import os


class ConfigManager:
    def __init__(self, project_root=None):
        """
        初始化配置管理器

        Args:
            project_root: 项目根目录路径
        """
        print("Initializing ConfigManager")
        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        print(f"Project root: {self.project_root}")
        self.models_dir = os.path.join(self.project_root, 'models', 'paddle_ocr')
        print(f"Models directory: {self.models_dir}")
        
        # 确保模型目录存在
        os.makedirs(self.models_dir, exist_ok=True)
        print(f"Ensured models directory exists: {os.path.exists(self.models_dir)}")
        
        # 查找实际的模型路径
        det_model_dir = self._find_model_dir('det')
        print(f"Detected det_model_dir: {det_model_dir}")
        rec_model_dir = self._find_model_dir('rec')
        print(f"Detected rec_model_dir: {rec_model_dir}")
        cls_model_dir = self._find_model_dir('cls')
        print(f"Detected cls_model_dir: {cls_model_dir}")
        
        self.default_config = {
            'model_path': self.models_dir,
            'use_gpu': False,
            'det_model_dir': det_model_dir,
            'rec_model_dir': rec_model_dir,
            'cls_model_dir': cls_model_dir,
            'precision': 'fp32',
            'max_text_length': 25,
            'rec_image_shape': '3, 32, 320',
            'use_space_char': True,
            'drop_score': 0.5,
            # 添加蒙版相关配置
            'use_mask': False,
            'use_adaptive_mask': False,
            'mask_padding': 10,
            'interactive_selection': False,
            'use_center_priority': False,
            'default_coordinates': '',
            # 添加性能相关配置
            'cpu_limit': 70,
            'max_processing_time': 30,
            # 添加多进程相关配置
            'processing_processes': 2,
            'use_preprocessing': True,
            'use_skew_correction': False
        }
        print("ConfigManager initialized")

    def _find_model_dir(self, model_type):
        """
        查找指定类型的模型目录

        Args:
            model_type: 模型类型 ('det', 'rec', 'cls')

        Returns:
            模型目录路径
        """
        print(f"Finding model directory for type: {model_type}")
        
        # 首先检查是否存在直接的模型类型目录
        type_dir = os.path.join(self.models_dir, model_type)
        print(f"Checking type directory: {type_dir}")
        print(f"Type directory exists: {os.path.exists(type_dir)}")
        
        if os.path.exists(type_dir):
            # 查找目录中的模型
            try:
                items = os.listdir(type_dir)
                print(f"Items in type directory: {items}")
                if items:
                    # 返回第一个模型目录
                    model_path = os.path.join(type_dir, items[0])
                    print(f"Checking model path: {model_path}")
                    print(f"Model path is directory: {os.path.isdir(model_path)}")
                    if os.path.isdir(model_path):
                        print(f"Found {model_type} model in type dir: {model_path}")
                        return model_path
            except Exception as e:
                print(f"Error reading {type_dir}: {e}")
        
        # 如果没有对应类型目录，直接在models/paddle_ocr目录下查找
        print(f"Checking main models directory: {self.models_dir}")
        print(f"Main models directory exists: {os.path.exists(self.models_dir)}")
        
        if os.path.exists(self.models_dir):
            # 根据模型类型定义特定模型名称优先级
            priority_models = {
                'det': ['PP-OCRv5_server_det'],
                'rec': ['PP-OCRv5_server_rec'],
                'cls': ['PP-LCNet_x1_0_textline_ori', 'PP-LCNet_x1_0_doc_ori', 'UVDoc']
            }
            
            # 优先查找特定模型
            model_list = priority_models.get(model_type, [])
            print(f"Priority models for {model_type}: {model_list}")
            
            for model_name in model_list:
                model_path = os.path.join(self.models_dir, model_name)
                print(f"Checking priority model path: {model_path}")
                print(f"Priority model path exists: {os.path.exists(model_path)}")
                
                if os.path.exists(model_path):
                    # 检查目录中是否有模型文件（至少要有一个模型文件）
                    model_files = ['inference.pdmodel', 'inference.pdiparams']
                    has_any_model_file = any(os.path.exists(os.path.join(model_path, f)) for f in model_files)
                    print(f"Has any model file: {has_any_model_file}")
                    
                    if has_any_model_file:
                        print(f"Found priority {model_type} model: {model_path}")
                        return model_path
                    else:
                        print(f"Priority model {model_path} missing model files")
            
            # 如果没有找到特定模型，则根据关键词查找
            keywords = {
                'det': ['det', 'detection'],
                'rec': ['rec', 'recognition'],
                'cls': ['cls', 'classification', 'ori', 'orientation', 'unwarping']
            }
            
            type_keywords = keywords.get(model_type, [model_type])
            print(f"Keywords for {model_type}: {type_keywords}")
            
            items = os.listdir(self.models_dir)
            print(f"Items in models directory: {items}")
            
            for item in items:
                item_path = os.path.join(self.models_dir, item)
                print(f"Checking item: {item_path}")
                # 检查目录名是否包含模型类型关键词
                if os.path.isdir(item_path):
                    item_lower = item.lower()
                    print(f"Item name (lowercase): {item_lower}")
                    matched_keywords = [keyword for keyword in type_keywords if keyword in item_lower]
                    print(f"Matched keywords: {matched_keywords}")
                    
                    if any(keyword in item_lower for keyword in type_keywords):
                        # 检查目录中是否有模型文件（至少要有一个模型文件）
                        model_files = ['inference.pdmodel', 'inference.pdiparams']
                        has_any_model_file = any(os.path.exists(os.path.join(item_path, f)) for f in model_files)
                        print(f"Has any model file: {has_any_model_file}")
                        
                        if has_any_model_file:
                            print(f"Found {model_type} model by keyword: {item_path}")
                            return item_path
                        else:
                            print(f"Model {item_path} missing model files")
                else:
                    print(f"Item {item_path} is not a directory")
                        
        # 如果还是没找到，返回默认路径
        default_path = os.path.join(self.models_dir, model_type)
        print(f"Using default path for {model_type} model: {default_path}")
        return default_path

    def load_config(self, config_path=None):
        """
        加载配置

        Args:
            config_path: 配置文件路径
        """
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.json')
            
        print(f"Loading configuration from: {config_path}")
        print(f"Config file exists: {os.path.exists(config_path)}")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print("Configuration loaded successfully")
                print(f"Loaded config keys: {list(self.config.keys())}")
            except Exception as e:
                print(f"Error loading config: {e}")
                print("Using default configuration")
                self.config = self.default_config.copy()
        else:
            print("Config file not found, using default config")
            self.config = self.default_config.copy()
            # 保存默认配置
            print("Saving default configuration")
            self.save_config(config_path)

    def save_config(self, config_path=None):
        """
        保存配置

        Args:
            config_path: 配置文件路径
        """
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.json')
            
        print(f"Saving configuration to: {config_path}")
        try:
            # 确保配置目录存在
            config_dir = os.path.dirname(config_path)
            print(f"Ensuring config directory exists: {config_dir}")
            os.makedirs(config_dir, exist_ok=True)
            print(f"Config directory exists: {os.path.exists(config_dir)}")
            
            # 确保self.config存在
            if not hasattr(self, 'config'):
                print("Config not initialized, using default config")
                self.config = self.default_config.copy()
                
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            print("Configuration saved successfully")
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_setting(self, key, default=None):
        """
        获取配置项

        Args:
            key: 配置项键名
            default: 默认值

        Returns:
            配置项值
        """
        print(f"Getting setting: {key}")
        if key in self.config:
            value = self.config[key]
            print(f"Found in config: {value}")
            return value
        elif key in self.default_config:
            value = self.default_config[key]
            print(f"Found in default config: {value}")
            return value
        else:
            print(f"Not found, using default: {default}")
            return default

    def set_setting(self, key, value):
        """
        设置配置项

        Args:
            key: 配置项键名
            value: 配置项值
        """
        print(f"Setting {key} = {value}")
        self.config[key] = value

    def get_default_settings(self):
        """
        获取默认设置

        Returns:
            dict: 默认设置
        """
        return {
            'language': 'zh',
            'theme': 'default',
            'performance_monitoring': True,
            'det_model_dir': self._find_model_dir('det'),
            'rec_model_dir': self._find_model_dir('rec'),
            'cls_model_dir': self._find_model_dir('cls'),
            'use_preprocessing': True,
            'processing_processes': 2,
            'use_skew_correction': False,
            'model_path': self.models_dir,
            'use_gpu': False,
            'precision': 'fp32',
            'max_text_length': 25,
            'rec_image_shape': '3, 32, 320',
            'use_space_char': True,
            'drop_score': 0.5,
            'use_mask': False,
            'use_adaptive_mask': False,
            'mask_padding': 10,
            'interactive_selection': False,
            'use_center_priority': False,
            'default_coordinates': '',
            'cpu_limit': 70,
            'max_processing_time': 30
        }
