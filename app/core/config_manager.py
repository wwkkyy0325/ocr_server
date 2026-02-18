# -*- coding: utf-8 -*-

"""
配置管理（保存模型路径、识别参数）
"""

import json
import os


from app.core.model_manager import ModelManager
from app.core.env_manager import EnvManager

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
        
        # 初始化模型管理器（使用 PaddleX 默认模型目录，而不是项目本地 models 目录）
        self.model_manager = ModelManager()
        print(f"ModelManager initialized with root: {self.model_manager.models_root}")
        
        # models_dir 仅作为配置中的展示路径，保持与模型管理器一致
        self.models_dir = self.model_manager.models_root
        
        # 检查环境并设置默认值
        paddle_status = EnvManager.get_paddle_status()
        is_gpu_supported = paddle_status.get('gpu_support', False)
        print(f"Environment GPU Support: {is_gpu_supported}")
        
        default_det_key = 'PP-OCRv5_mobile_det'
        default_rec_key = 'PP-OCRv5_mobile_rec'
        print("Selected Mobile models as default")
            
        default_cls_key = 'PP-LCNet_x1_0_textline_ori'
        default_unwarp_key = 'UVDoc'
        default_table_key = 'SLANet'
        
        # 查找实际的模型路径 (使用默认Key)
        det_model_dir = self.model_manager.get_model_dir('det', default_det_key)
        rec_model_dir = self.model_manager.get_model_dir('rec', default_rec_key)
        cls_model_dir = self.model_manager.get_model_dir('cls', default_cls_key)
        unwarp_model_dir = self.model_manager.get_model_dir('unwarp', default_unwarp_key)
        table_model_dir = self.model_manager.get_model_dir('table', default_table_key)
        
        self.default_config = {
            'model_path': self.models_dir,
            'use_gpu': is_gpu_supported,
            'det_model_dir': det_model_dir,
            'rec_model_dir': rec_model_dir,
            'cls_model_dir': cls_model_dir,
            'unwarp_model_dir': unwarp_model_dir,
            'table_model_dir': table_model_dir,
            'det_model_key': default_det_key,
            'rec_model_key': default_rec_key,
            'cls_model_key': default_cls_key,
            'unwarp_model_key': default_unwarp_key,
            'table_model_key': default_table_key,
            'ai_table_model': default_table_key, # Alias for consistency
            # Model enable switches
            'use_det_model': True,
            'use_rec_model': True,
            'use_cls_model': False,
            'use_unwarp_model': False,
            'use_table_model': False, # AI表格结构模型开关 (PP-Structure)
            'precision': 'fp32',
            'max_text_length': 25,
            'rec_image_shape': '3, 32, 320',
            'use_space_char': True,
            'drop_score': 0.5,
            'enable_advanced_doc': False,
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
            'use_skew_correction': True,
            'use_padding': False,
            'padding_size': 50,
            # OCR服务配置
            'ocr_server_url': ''
        }
        print("ConfigManager initialized")
        
        # Load config immediately
        self.load_config()

    def _to_absolute_path(self, path):
        """Convert relative path to absolute path based on project root"""
        if path and isinstance(path, str) and not os.path.isabs(path):
            return os.path.normpath(os.path.join(self.project_root, path))
        return path

    def _to_relative_path(self, path):
        """Convert absolute path to relative path based on project root"""
        if path and isinstance(path, str) and os.path.isabs(path):
            try:
                rel_path = os.path.relpath(path, self.project_root)
                # Ensure we don't go up too many levels if on different drives (Windows)
                # or if path is outside project root
                if not rel_path.startswith('..') or '..' not in rel_path: 
                     # Allow .. but usually we want paths inside project
                     return rel_path
            except ValueError:
                # Can happen on Windows if paths are on different drives
                pass
        return path

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
                
                # Convert relative paths to absolute
                path_keys = ['model_path', 'det_model_dir', 'rec_model_dir', 'cls_model_dir', 'unwarp_model_dir', 'table_model_dir']
                for key in path_keys:
                    if key in self.config:
                        self.config[key] = self._to_absolute_path(self.config[key])
                
                # Re-evaluate model dirs based on loaded keys
                det_key = self.config.get('det_model_key')
                rec_key = self.config.get('rec_model_key')
                cls_key = self.config.get('cls_model_key')
                unwarp_key = self.config.get('unwarp_model_key')
                table_key = self.config.get('table_model_key')
                
                if det_key:
                    self.config['det_model_dir'] = self.model_manager.get_model_dir('det', det_key)
                if rec_key:
                    self.config['rec_model_dir'] = self.model_manager.get_model_dir('rec', rec_key)
                if cls_key:
                    self.config['cls_model_dir'] = self.model_manager.get_model_dir('cls', cls_key)
                if unwarp_key:
                    self.config['unwarp_model_dir'] = self.model_manager.get_model_dir('unwarp', unwarp_key)
                if table_key:
                    self.config['table_model_dir'] = self.model_manager.get_model_dir('table', table_key)
                    # Sync alias
                    self.config['ai_table_model'] = table_key
                    
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

    def set_model(self, model_type, model_key):
        """
        设置使用的模型
        """
        key_name = f"{model_type}_model_key"
        self.config[key_name] = model_key
        
        # Update directory immediately
        dir_name = f"{model_type}_model_dir"
        self.config[dir_name] = self.model_manager.get_model_dir(model_type, model_key)
        
        self.save_config()

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
            
            # Create a copy to save relative paths
            config_to_save = self.config.copy()
            path_keys = ['model_path', 'det_model_dir', 'rec_model_dir', 'cls_model_dir', 'unwarp_model_dir', 'table_model_dir']
            for key in path_keys:
                if key in config_to_save:
                    config_to_save[key] = self._to_relative_path(config_to_save[key])

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=4)
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
        if key in self.config:
            return self.config[key]
        if key in self.default_config:
            return self.default_config[key]
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

    def _get_optimal_process_count(self):
        """
        获取最优处理进程数（CPU核心数的一半）
        
        Returns:
            int: 最优处理进程数
        """
        try:
            import os
            cpu_count = os.cpu_count()
            # 使用CPU核心数的一半，但至少为1个，最多不超过8个
            optimal_count = max(1, min(cpu_count // 2, 8)) if cpu_count else 2
            print(f"检测到CPU核心数: {cpu_count}, 设置处理进程数: {optimal_count}")
            return optimal_count
        except Exception as e:
            print(f"获取CPU核心数时出错: {e}, 使用默认值2")
            return 2

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
            'processing_processes': self._get_optimal_process_count(),
            'use_skew_correction': True,
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
