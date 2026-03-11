# -*- coding: utf-8 -*-
#
# 文件说明：
# - 作用：以 MessagePack 格式集中保存 OCR 识别结果
# - 核心实现：统一输出目录结构（.../msgpack/），保存元数据
# - 关联关系：由 ProcessingController/主流程在完成识别后调用；读取由 ResultManager/前端使用
#              文本格式化功能由 ResultFormatter 负责
"""
结果导出器 - 使用 MessagePack 格式存储 OCR 结果
只保存一个 .msgpack 文件，替代原来的 JSON + TXT 双文件模式
"""

import os
from datetime import datetime
from typing import Optional, Union
from pathlib import Path

from app.log.log_bus import get_logger
from app.infrastructure.message_pack_serializer import MessagePackSerializer
from app.core.result.result_formatter import ResultFormatter
from app.utils.path_manager import PathManager
from app.infrastructure.error_handler import handle_errors, ErrorCode


class ResultExporter:
    """
    结果导出器
    
    职责：
        - 将 OCR 结果保存到 MessagePack 文件（二进制格式）
        - 从 MessagePack 文件加载结果
        - 不负责文本格式化（由 ResultFormatter 负责）
    """
    
    def __init__(self, output_dir_base):
        """
        初始化 ResultExporter
        
        Args:
            output_dir_base: 输出目录基础路径 (data/outputs)
        """
        self.output_dir_base = output_dir_base
        self.formatter = ResultFormatter()

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ResultExporter")
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

    @staticmethod
    @handle_errors(error_code=ErrorCode.DIR_CREATE_001, fallback_return=None, component="ResultExporter")
    def _ensure_output_dirs(current_output_dir):
        """
        📁 确保输出目录存在（内部使用）
        
        Args:
            current_output_dir: 当前输出目录路径
        """
        msgpack_output_dir = os.path.join(current_output_dir, "msgpack")
        os.makedirs(msgpack_output_dir, exist_ok=True)

    @handle_errors(error_code=ErrorCode.RESULT_EXPORT_001, fallback_return=None, component="ResultExporter")
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
        logger = get_logger()
        current_output_dir, msgpack_path = self.get_output_path(image_path, filename)
        self._ensure_output_dirs(current_output_dir)
        
        try:
            # 确保 result_data 是字典
            if isinstance(result_data, list):
                result_data = {'regions': result_data}
            
            # 补充元数据
            final_data = result_data.copy() if result_data else {}
            final_data.update({
                'full_text': full_text,
                'image_path': image_path,
                'filename': Path(image_path.split("|page=")[0]).name if "|page=" in str(image_path) else Path(image_path).name,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            })
            
            # 使用 MessagePack 保存（二进制格式，高效存储）
            MessagePackSerializer.save_to_file(final_data, msgpack_path)
            
            logger.debug("result_exporter", "saved", f"已保存结果到：{msgpack_path}")
            return final_data
            
        except Exception as e:
            logger.error("result_exporter", "save_error", f"保存 MessagePack 结果失败：{e}")
            import traceback
            traceback.print_exc()
            return None
    
    @handle_errors(error_code=ErrorCode.FILE_IO_001, fallback_return=None, component="ResultExporter")
    def load_result(self, image_path, filename=None):
        """
        从 MessagePack 文件加载结果
        
        Args:
            image_path: 原始图像路径
            filename: 可选的文件名
            
        Returns:
            dict: 加载的数据，如果文件不存在则返回 None
        """
        logger = get_logger()
        try:
            current_output_dir, msgpack_path = self.get_output_path(image_path, filename)
            
            if os.path.exists(msgpack_path):
                return MessagePackSerializer.load_from_file(msgpack_path)
            else:
                logger.warning("result_exporter", "not_found", f"结果文件不存在：{msgpack_path}")
                return None
                
        except Exception as e:
            logger.error("result_exporter", "load_error", f"加载 MessagePack 结果失败：{e}")
            import traceback
            traceback.print_exc()
            return None
    
    @handle_errors(error_code=ErrorCode.RESULT_EXPORT_001, fallback_return="", component="ResultExporter")
    def export_to_text(self, results, output_path: str, format: str = 'txt') -> str:
        """
        导出结果为文本格式（TXT/CSV/JSON/Markdown）
        
        Args:
            results: OCR 结果字典
            output_path: 输出文件路径
            format: 导出格式 ('txt', 'csv', 'json', 'markdown')
            
        Returns:
            导出的文件路径
        """
        logger = get_logger()
        try:
            # 使用 formatter 格式化
            if format == 'txt':
                content = self.formatter.to_txt(results)
            elif format == 'csv':
                content = self.formatter.to_csv(results)
            elif format == 'json':
                content = self.formatter.to_json(results)
            elif format == 'markdown':
                content = self.formatter.to_markdown(results)
            else:
                raise ValueError(f"不支持的导出格式：{format}")
            
            # 确保目录存在
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("result_exporter", "export_complete", f"已导出 {format.upper()} 到：{output_path}")
            return output_path
            
        except Exception as e:
            logger.error("result_exporter", "export_error", f"导出文本结果失败：{e}")
            import traceback
            traceback.print_exc()
            return ""
