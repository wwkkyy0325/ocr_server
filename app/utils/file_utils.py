# -*- coding: utf-8 -*-

"""
文件操作（图像/PDF读写、结果导出为TXT）
"""

import os
import glob
from PIL import Image
import json


class FileUtils:
    def __init__(self):
        """
        初始化文件工具类
        """
        pass

    @staticmethod
    def read_image(image_path):
        """
        读取图像文件

        Args:
            image_path: 图像文件路径

        Returns:
            图像数据
        """
        print(f"Reading image: {image_path}")
        try:
            if os.path.exists(image_path):
                image = Image.open(image_path)
                return image
            else:
                print(f"Image file not found: {image_path}")
                return None
        except Exception as e:
            print(f"Error reading image {image_path}: {e}")
            return None

    @staticmethod
    def write_text_file(file_path, content):
        """
        写入文本文件

        Args:
            file_path: 文件路径
            content: 文件内容
        """
        print(f"Writing text file: {file_path}")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 先写入临时文件，再重命名为目标文件，确保原子性
            temp_file_path = file_path + ".tmp"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 原子性地重命名文件
            os.replace(temp_file_path, file_path)
        except Exception as e:
            print(f"Error writing text file {file_path}: {e}")
            # 尝试删除临时文件（如果存在）
            try:
                if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass

    @staticmethod
    def get_image_files(directory, recursive=False):
        """
        获取目录中的所有图像文件
        
        Args:
            directory: 目录路径或单个文件路径
            recursive: 是否递归搜索子目录
            
        Returns:
            图像文件路径列表
        """
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
        image_files = []
        
        # 如果传入的是文件，直接检查扩展名并返回
        if os.path.isfile(directory):
            ext = os.path.splitext(directory)[1].lower()
            if ext in image_extensions:
                return [directory]
            return []
            
        # 如果是目录，则搜索
        if recursive:
            for root, _, _ in os.walk(directory):
                for extension in image_extensions:
                    # glob pattern need *
                    pattern = f"*{extension}"
                    image_files.extend(glob.glob(os.path.join(root, pattern), recursive=False))
        else:
            for extension in image_extensions:
                pattern = f"*{extension}"
                image_files.extend(glob.glob(os.path.join(directory, pattern), recursive=False))
                
        return sorted(image_files)

    @staticmethod
    def write_json_file(file_path, data):
        """
        写入JSON文件

        Args:
            file_path: 文件路径
            data: 要写入的数据
        """
        print(f"Writing JSON file: {file_path}")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 确保所有numpy数据类型都转换为Python原生类型
            def convert_numpy_types(obj):
                if isinstance(obj, dict):
                    return {key: convert_numpy_types(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
                elif hasattr(obj, 'tolist'):  # numpy数组
                    return obj.tolist()
                elif hasattr(obj, 'item'):  # numpy标量类型
                    return obj.item()
                else:
                    return obj
            
            # 转换数据
            converted_data = convert_numpy_types(data)
            
            # 先写入临时文件，再重命名为目标文件，确保原子性
            temp_file_path = file_path + ".tmp"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(converted_data, f, ensure_ascii=False, indent=2)
            
            # 原子性地重命名文件
            os.replace(temp_file_path, file_path)
            print(f"Successfully wrote JSON file: {file_path}")
        except Exception as e:
            print(f"Error writing JSON file {file_path}: {e}")
            # 尝试删除临时文件（如果存在）
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass
            raise  # 重新抛出异常，让调用者知道写入失败
