# -*- coding: utf-8 -*-
"""
MessagePack 序列化工具
用于高效存储和加载 OCR 结果数据
"""

import msgpack
import msgpack_numpy as mnp
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Union
import traceback

# 激活 msgpack-numpy 支持
mnp.patch()


class MessagePackSerializer:
    """MessagePack 序列化工具类"""
    
    @staticmethod
    def serialize(data: Union[Dict, List, Any]) -> bytes:
        """
        序列化数据为 MessagePack 二进制
        
        Args:
            data: 要序列化的数据（dict、list 或任意 Python 对象）
            
        Returns:
            bytes: MessagePack 二进制数据
        """
        try:
            # msgpack.packb 会自动处理 NumPy 数组
            return msgpack.packb(data, use_bin_type=True)
        except Exception as e:
            print(f"MessagePack serialization error: {e}")
            traceback.print_exc()
            raise
    
    @staticmethod
    def deserialize(data: bytes) -> Any:
        """
        反序列化 MessagePack 二进制数据
        
        Args:
            data: MessagePack 二进制数据
            
        Returns:
            Any: 反序列化后的 Python 对象
        """
        try:
            return msgpack.unpackb(data, raw=False)
        except Exception as e:
            print(f"MessagePack deserialization error: {e}")
            traceback.print_exc()
            raise
    
    @staticmethod
    def save_to_file(data: Union[Dict, List, Any], file_path: Union[str, Path]) -> None:
        """
        保存数据到 MessagePack 文件
        
        Args:
            data: 要保存的数据
            file_path: 输出文件路径 (.msgpack 或 .mpk)
        """
        try:
            file_path = Path(file_path)
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 序列化并保存
            packed_data = MessagePackSerializer.serialize(data)
            with open(file_path, 'wb') as f:
                f.write(packed_data)
                
            print(f"✓ Saved MessagePack file: {file_path.name} ({len(packed_data) / 1024:.2f} KB)")
        except Exception as e:
            print(f"Error saving MessagePack file: {e}")
            traceback.print_exc()
            raise
    
    @staticmethod
    def load_from_file(file_path: Union[str, Path]) -> Any:
        """
        从 MessagePack 文件加载数据
        
        Args:
            file_path: 输入文件路径 (.msgpack 或 .mpk)
            
        Returns:
            Any: 反序列化后的数据
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"MessagePack file not found: {file_path}")
            
            with open(file_path, 'rb') as f:
                packed_data = f.read()
            
            return MessagePackSerializer.deserialize(packed_data)
        except Exception as e:
            print(f"Error loading MessagePack file: {e}")
            traceback.print_exc()
            raise
    
    @staticmethod
    def get_compression_ratio(original_size: int, packed_size: int) -> float:
        """
        计算压缩率
        
        Args:
            original_size: 原始数据大小（字节）
            packed_size: MessagePack 后的大小（字节）
            
        Returns:
            float: 压缩率（0-1 之间，越小越好）
        """
        if original_size == 0:
            return 0
        return packed_size / original_size


# 便捷函数
def pack(data: Any) -> bytes:
    """快速序列化"""
    return MessagePackSerializer.serialize(data)


def unpack(data: bytes) -> Any:
    """快速反序列化"""
    return MessagePackSerializer.deserialize(data)


def save(data: Any, path: Union[str, Path]) -> None:
    """快速保存到文件"""
    MessagePackSerializer.save_to_file(data, path)


def load(path: Union[str, Path]) -> Any:
    """快速从文件加载"""
    return MessagePackSerializer.load_from_file(path)
