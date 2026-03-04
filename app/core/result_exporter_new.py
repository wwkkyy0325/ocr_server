# -*- coding: utf-8 -*-
"""
结果导出器 - 使用 MessagePack 格式存储 OCR 结果
只保存一个 .msgpack 文件，替代原来的 JSON + TXT 双文件模式
"""

import os
from datetime import datetime
from app.core.record_manager import RecordManager
from app.utils.message_pack_serializer import MessagePackSerializer


class ResultExporter:
    """
    负责将 OCR 识别结果导出到 MessagePack 文件并更新处理记录
    """
    
    def __init__(self, output_dir_base, record_manager=None):
        """
        初始化 ResultExporter
        
        Args:
            output_dir_base: 输出目录基础路径 (data/outputs)
            record_manager: 记录管理器实例
        """
        self.output_dir_base = output_dir_base
        self.record_manager = record_manager or RecordManager.get_instance()

    def get_output_path(self, image_path, filename=None):
        """
        计算输出路径（只返回 MessagePack 文件路径）
        
        Args:
            image_path: 原始图像路径
            filename: 可选，指定文件名（不含扩展名），若不提供则使用 image_path 的文件名
            
        Returns:
            tuple: (parent_output_dir, msgpack_path)
        """
        if filename is None:
            filename = os.path.basename(image_path)
            
        # 处理 PDF 页面等虚拟路径
        safe_filename = filename.replace(':', '_')
        base_name = os.path.splitext(safe_filename)[0]

        # 集中化目录逻辑：data/outputs/<parent_dir_name>/msgpack/
        parent_dir_name = os.path.basename(os.path.dirname(image_path))
        current_output_dir = os.path.join(self.output_dir_base, parent_dir_name)
        msgpack_output_dir = os.path.join(current_output_dir, "msgpack")
        
        msgpack_path = os.path.join(msgpack_output_dir, f"{base_name}.msgpack")
        
        return current_output_dir, msgpack_path

    def ensure_output_dirs(self, current_output_dir):
        """确保输出目录存在"""
        msgpack_output_dir = os.path.join(current_output_dir, "msgpack")
        os.makedirs(msgpack_output_dir, exist_ok=True)

    def save_result(self, image_path, full_text, result_data, filename=None):
        """
        保存结果到 MessagePack 文件并更新记录
        
        Args:
            image_path: 原始图像路径
            full_text: 完整文本内容
            result_data: OCR 结果数据（dict 或 list）
            filename: 可选的文件名
            
        Returns:
            dict: 最终保存的数据结构，包含所有元数据
        """
        current_output_dir, msgpack_path = self.get_output_path(image_path, filename)
        self.ensure_output_dirs(current_output_dir)
        
        try:
            # 确保 result_data 是字典
            if isinstance(result_data, list):
                result_data = {'regions': result_data}
            
            # 补充元数据
            final_data = result_data.copy() if result_data else {}
            final_data.update({
                'full_text': full_text,
                'image_path': image_path,
                'filename': os.path.basename(image_path),
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            })
            
            # 使用 MessagePack 保存（二进制格式，高效存储）
            MessagePackSerializer.save_to_file(final_data, msgpack_path)
            
            # 更新数据库记录
            self.record_manager.add_record(image_path, output_path=msgpack_path)
            
            print(f"✓ Saved result to: {msgpack_path}")
            return final_data
            
        except Exception as e:
            print(f"Error saving MessagePack result: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def load_result(self, image_path, filename=None):
        """
        从 MessagePack 文件加载结果
        
        Args:
            image_path: 原始图像路径
            filename: 可选的文件名
            
        Returns:
            dict: 加载的数据，如果文件不存在则返回 None
        """
        try:
            current_output_dir, msgpack_path = self.get_output_path(image_path, filename)
            
            if os.path.exists(msgpack_path):
                return MessagePackSerializer.load_from_file(msgpack_path)
            else:
                print(f"Result file not found: {msgpack_path}")
                return None
                
        except Exception as e:
            print(f"Error loading MessagePack result: {e}")
            import traceback
            traceback.print_exc()
            return None
