# -*- coding: utf-8 -*-
"""
结果处理工具 - 提供 OCR 结果的合并、过滤、排序等辅助功能

职责：
    - 合并多个 OCR 结果
    - 过滤空文本项
    - 按位置排序
    
与 ResultAdapter 的区别：
    - ResultAdapter: 负责格式转换（原始数据 → 标准格式）
    - ResultProcessor: 负责业务处理（合并/过滤/排序）
"""

from typing import List, Dict
from app.infrastructure.error_handler import handle_errors, ErrorCode


class ResultProcessor:
    """
    OCR 结果处理器
    
    提供常用的结果处理工具方法
    """
    
    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=[], component="ResultProcessor")
    def merge_results(results: List[List[Dict]]) -> List[Dict]:
        """
        合并多个 OCR 结果
        
        Args:
            results: 结果列表的列表
            
        Returns:
            合并后的扁平化结果列表
        """
        merged = []
        for result_list in results:
            if isinstance(result_list, list):
                merged.extend(result_list)
        return merged
    
    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=[], component="ResultProcessor")
    def filter_empty(items: List[Dict]) -> List[Dict]:
        """
        过滤空文本项
        
        Args:
            items: OCR 结果项列表
            
        Returns:
            过滤后的结果列表
        """
        return [item for item in items if item.get('text', '').strip()]
    
    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=[], component="ResultProcessor")
    def sort_by_position(items: List[Dict], reading_order: str = 'lr-tb') -> List[Dict]:
        """
        按位置排序 OCR 结果
        
        Args:
            items: OCR 结果项列表
            reading_order: 阅读顺序
                - 'lr-tb': 从左到右，从上到下（默认）
                - 'tb-lr': 从上到下，从左到右
                
        Returns:
            排序后的结果列表
        """
        if not items:
            return items
        
        try:
            if reading_order == 'tb-lr':
                # 先按 Y 排序，再按 X 排序
                return sorted(items, key=lambda x: (x['box'][1], x['box'][0]))
            else:
                # 默认：先按 X 排序，再按 Y 排序  
                return sorted(items, key=lambda x: (x['box'][0], x['box'][1]))
        except Exception:
            return items
    
    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=[], component="ResultProcessor")
    def group_by_lines(items: List[Dict], y_threshold: int = 10) -> List[List[Dict]]:
        """
        按行分组 OCR 结果
        
        Args:
            items: OCR 结果项列表
            y_threshold: Y 坐标差值阈值（像素），小于此值视为同一行
            
        Returns:
            分行后的结果 [[line1_items], [line2_items], ...]
        """
        if not items:
            return []
        
        # 按 Y 坐标排序
        sorted_items = sorted(items, key=lambda x: x['box'][1])
        
        lines = []
        current_line = [sorted_items[0]]
        current_y = sorted_items[0]['box'][1]
        
        for item in sorted_items[1:]:
            y = item['box'][1]
            
            # 如果 Y 坐标差值小于阈值，视为同一行
            if abs(y - current_y) <= y_threshold:
                current_line.append(item)
            else:
                # 否则开始新行
                lines.append(current_line)
                current_line = [item]
                current_y = y
        
        # 添加最后一行
        if current_line:
            lines.append(current_line)
        
        return lines
    
    @staticmethod
    @handle_errors(error_code=ErrorCode.RESULT_FORMAT_001, fallback_return=[], component="ResultProcessor")
    def merge_line_texts(lines: List[List[Dict]], separator: str = ' ') -> List[str]:
        """
        将每行的 OCR 结果合并为文本
        
        Args:
            lines: 分行后的结果 [[line1_items], [line2_items], ...]
            separator: 项之间的分隔符
            
        Returns:
            每行的文本列表
        """
        line_texts = []
        
        for line in lines:
            # 按 X 坐标排序（从左到右）
            sorted_line = sorted(line, key=lambda x: x['box'][0])
            
            # 合并文本
            text = separator.join([item['text'] for item in sorted_line])
            line_texts.append(text)
        
        return line_texts
