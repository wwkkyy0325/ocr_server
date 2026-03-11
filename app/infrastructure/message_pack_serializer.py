# -*- coding: utf-8 -*-
"""
MessagePack 序列化工具
用于高效存储和加载 OCR 结果数据
"""
# 文件说明：
# - 作用：封装 MessagePack 的序列化/反序列化与文件读写，支持 numpy 数据
# - 核心实现：基于 msgpack + msgpack-numpy 提供统一 save/load 接口和便捷函数
# - 关联关系：被 ResultExporter/ProcessingController 等用于高效落盘与加载结果

import msgpack
import msgpack_numpy as mnp
from pathlib import Path
from typing import Any, Dict, List, Union
import traceback
from datetime import datetime
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()

# 激活 msgpack-numpy 支持
mnp.patch()


class MessagePackSerializer:
    """MessagePack 序列化工具类"""

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="MessagePackSerializer")
    def _convert_datetime_to_string(obj):
        """
        递归地将 datetime 对象转换为 ISO 格式字符串
        
        Args:
            obj: 任意对象
            
        Returns:
            转换后的对象
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: MessagePackSerializer._convert_datetime_to_string(value)
                    for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [MessagePackSerializer._convert_datetime_to_string(item)
                    for item in obj]
        else:
            return obj

    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=b'', component="MessagePackSerializer")
    def serialize(data: Union[Dict, List, Any]) -> bytes:
        """
        序列化数据为 MessagePack 二进制
        
        Args:
            data: 要序列化的数据（dict、list 或任意 Python 对象）
            
        Returns:
            bytes: MessagePack 二进制数据
        """
        try:
            # 🔥 预处理：将 datetime 转换为 ISO 字符串（MessagePack 不支持 datetime）
            data = MessagePackSerializer._convert_datetime_to_string(data)

            # msgpack.packb 会自动处理 NumPy 数组
            return msgpack.packb(data, use_bin_type=True)
        except Exception as e:
            error_msg = f"MessagePack serialization error: {e}"
            logger.error("message_pack_serializer", "serialization_failed", error_msg)
            logger.debug("message_pack_serializer", "traceback", traceback.format_exc())
            raise

    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=None, component="MessagePackSerializer")
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
            error_msg = f"MessagePack deserialization error: {e}"
            logger.error("message_pack_serializer", "deserialization_failed", error_msg)
            logger.debug("message_pack_serializer", "traceback", traceback.format_exc())
            raise

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_WRITE_001, fallback_return=None, component="MessagePackSerializer")
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

            file_size_kb = len(packed_data) / 1024
            logger.success("message_pack_serializer", "file_saved",
                           f"Saved MessagePack file: {file_path.name} ({file_size_kb:.2f} KB)")
        except Exception as e:
            error_msg = f"Error saving MessagePack file: {e}"
            logger.error("message_pack_serializer", "save_file_failed", error_msg)
            logger.debug("message_pack_serializer", "traceback", traceback.format_exc())
            raise

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="MessagePackSerializer")
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
            error_msg = f"Error loading MessagePack file: {e}"
            logger.error("message_pack_serializer", "load_file_failed", error_msg)
            logger.debug("message_pack_serializer", "traceback", traceback.format_exc())
            raise

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=0.0, component="MessagePackSerializer")
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
@handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=b'', component="MessagePackSerializer")
def pack(data: Any) -> bytes:
    """快速序列化"""
    return MessagePackSerializer.serialize(data)


@handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=None, component="MessagePackSerializer")
def unpack(data: bytes) -> Any:
    """快速反序列化"""
    return MessagePackSerializer.deserialize(data)


@handle_errors(error_code=ErrorCode.FILE_WRITE_001, fallback_return=None, component="MessagePackSerializer")
def save(data: Any, path: Union[str, Path]) -> None:
    """快速保存到文件"""
    MessagePackSerializer.save_to_file(data, path)


@handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="MessagePackSerializer")
def load(path: Union[str, Path]) -> Any:
    """快速从文件加载"""
    return MessagePackSerializer.load_from_file(path)
