# Path: src/app/ocr/model_manager.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模型加载、切换、版本管理
"""

import os


class ModelManager:
    def __init__(self, project_root=None):
        """
        初始化模型管理器

        Args:
            project_root: 项目根目录
        """
        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.models_dir = os.path.join(self.project_root, 'models', 'paddle_ocr')
        
        self.current_model = None
        self.available_models = []
        self.model_paths = {}
        
        # 查找可用模型
        self._find_available_models()

    def load_model(self, model_path):
        """
        加载模型

        Args:
            model_path: 模型路径
        """
        print(f"Loading model from: {model_path}")
        if os.path.exists(model_path):
            try:
                # 实际的模型加载逻辑应该在这里实现
                # 例如使用PaddleOCR加载模型
                self.current_model = model_path
                print(f"Model loaded successfully: {model_path}")
            except Exception as e:
                print(f"Error loading model: {e}")
        else:
            print(f"Model path does not exist: {model_path}")

    def switch_model(self, model_name):
        """
        切换模型

        Args:
            model_name: 模型名称
        """
        print(f"Switching to model: {model_name}")
        if model_name in self.model_paths:
            self.load_model(self.model_paths[model_name])
        else:
            print(f"Model {model_name} not found")

    def list_available_models(self):
        """
        列出可用模型

        Returns:
            list: 可用模型列表
        """
        print("Listing available models")
        return self.available_models
        
    def _find_available_models(self):
        """
        查找可用模型
        """
        # 检查默认模型目录
        if os.path.exists(self.models_dir):
            print(f"Found models directory: {self.models_dir}")
            for model_type in ['det', 'rec', 'cls']:
                type_dir = os.path.join(self.models_dir, model_type)
                if os.path.exists(type_dir):
                    print(f"Found {model_type} models in: {type_dir}")
                    for model_name in os.listdir(type_dir):
                        model_path = os.path.join(type_dir, model_name)
                        if os.path.isdir(model_path):
                            # 检查模型目录是否包含inference.pdmodel文件
                            model_file = os.path.join(model_path, 'inference.pdmodel')
                            if os.path.exists(model_file):
                                full_name = f"{model_type}_{model_name}"
                                self.available_models.append(full_name)
                                self.model_paths[full_name] = model_path
                                print(f"Found model: {full_name} at {model_path}")
                            else:
                                print(f"Model directory {model_path} does not contain inference.pdmodel")
                else:
                    print(f"Model type directory not found: {type_dir}")
        else:
            print(f"Models directory not found: {self.models_dir}")
            # 如果没有找到模型，添加一些默认值
            self.available_models = ['det_default', 'rec_default', 'cls_default']
            self.model_paths = {
                'det_default': os.path.join(self.models_dir, 'det', 'default'),
                'rec_default': os.path.join(self.models_dir, 'rec', 'default'),
                'cls_default': os.path.join(self.models_dir, 'cls', 'default')
            }
