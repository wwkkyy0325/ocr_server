# -*- coding: utf-8 -*-
"""
结果格式化器 - 将 OCR 结果转换为不同文本格式

职责：
    - 将结果转换为 TXT/CSV/JSON 等文本格式
    - 只负责格式化，不负责文件 IO
    
使用示例：
    formatter = ResultFormatter()
    txt_content = formatter.to_txt(results)
    csv_content = formatter.to_csv(results)
"""

import json
import csv
import io
from typing import Dict, Any
from app.infrastructure.error_handler import handle_errors, ErrorCode


class ResultFormatter:
    """
    结果格式化器
    
    将 OCR 结果字典转换为各种文本格式
    """
    
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return="", component="ResultFormatter")
    def to_txt(self, results: Dict[str, Any]) -> str:
        """
        转换为 TXT 格式
        
        Args:
            results: 结果字典 {image_path: data}
            
        Returns:
            格式化后的文本字符串
        """
        output = []
        
        for image_path, data in results.items():
            output.append(f"Image: {image_path}")
            output.append(f"Filename: {data.get('filename', 'unknown')}")
            output.append(f"Result: {data.get('result', '')}")
            output.append(f"Timestamp: {data.get('timestamp', '')}")
            output.append("-" * 50)
        
        return "\n".join(output)
    
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return="{}", component="ResultFormatter")
    def to_json(self, results: Dict[str, Any], indent: int = 2) -> str:
        """
        转换为 JSON 格式
        
        Args:
            results: 结果字典
            indent: JSON 缩进空格数
            
        Returns:
            JSON 字符串
        """
        return json.dumps(results, ensure_ascii=False, indent=indent)
    
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return="", component="ResultFormatter")
    def to_csv(self, results: Dict[str, Any]) -> str:
        """
        转换为 CSV 格式
        
        Args:
            results: 结果字典
            
        Returns:
            CSV 字符串（UTF-8 编码）
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow(['Image Path', 'Filename', 'Result', 'Timestamp'])
        
        # 写入数据行
        for image_path, data in results.items():
            writer.writerow([
                image_path,
                data.get('filename', ''),
                data.get('result', ''),
                data.get('timestamp', '')
            ])
        
        return output.getvalue()
    
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return="", component="ResultFormatter")
    def to_markdown(self, results: Dict[str, Any]) -> str:
        """
        转换为 Markdown 表格格式
        
        Args:
            results: 结果字典
            
        Returns:
            Markdown 表格字符串
        """
        lines = []
        
        # 表头
        lines.append("| Image | Filename | Result | Timestamp |")
        lines.append("|-------|----------|--------|-----------|")
        
        # 数据行
        for image_path, data in results.items():
            filename = data.get('filename', '')
            result = data.get('result', '').replace('\n', ' ')[:100]  # 截断长文本
            timestamp = data.get('timestamp', '')
            
            lines.append(f"| {image_path} | {filename} | {result} | {timestamp} |")
        
        return "\n".join(lines)
