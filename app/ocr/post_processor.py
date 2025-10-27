# Path: src/app/ocr/post_processor.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
结果后处理（如格式校正、语义纠错）
"""

import re
from datetime import datetime


class PostProcessor:
    def __init__(self):
        """
        初始化后处理器
        """
        # 定义常见的日期格式模式
        self.date_patterns = [
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY-MM-DD or YYYY/MM/DD
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # MM/DD/YYYY or MM-DD-YYYY
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',     # YYYY年MM月DD日
        ]

    def correct_format(self, ocr_result):
        """
        格式校正

        Args:
            ocr_result: OCR识别结果

        Returns:
            str: 格式校正后的结果
        """
        print(f"Correcting format for: {ocr_result}")
        if not ocr_result:
            return ocr_result
            
        # 清理常见的OCR错误
        corrected = ocr_result
        
        # 替换常见的字符错误
        corrections = {
            'O': '0',
            'l': '1',
            'I': '1',
            'Z': '2',
            'S': '5',
            'B': '8'
        }
        
        for wrong, correct in corrections.items():
            corrected = corrected.replace(wrong, correct)
            
        return corrected

    def semantic_correction(self, text):
        """
        语义纠错

        Args:
            text: 输入文本

        Returns:
            str: 纠错后的文本
        """
        print(f"Performing semantic correction for: {text}")
        if not text:
            return text
            
        # 尝试识别并格式化日期
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    # 尝试解析日期
                    if '年' in pattern:
                        # 中文日期格式
                        year, month, day = match.groups()
                        date_obj = datetime(int(year), int(month), int(day))
                        formatted_date = f"{date_obj.year}年{date_obj.month}月{date_obj.day}日"
                        text = re.sub(pattern, formatted_date, text)
                    else:
                        # 数字日期格式
                        groups = match.groups()
                        if len(groups[0]) == 4:  # YYYY-MM-DD 格式
                            year, month, day = groups
                        else:  # MM-DD-YYYY 格式
                            month, day, year = groups
                        date_obj = datetime(int(year), int(month), int(day))
                        formatted_date = f"{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}"
                        text = re.sub(pattern, formatted_date, text)
                except ValueError:
                    # 日期无效，跳过
                    pass
                    
        return text
        
    def extract_dates(self, text):
        """
        从文本中提取日期

        Args:
            text: 输入文本

        Returns:
            list: 提取到的日期列表
        """
        dates = []
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    if '年' in pattern:
                        year, month, day = match
                        date_obj = datetime(int(year), int(month), int(day))
                    else:
                        groups = match
                        if len(groups[0]) == 4:  # YYYY-MM-DD 格式
                            year, month, day = groups
                        else:  # MM-DD-YYYY 格式
                            month, day, year = groups
                        date_obj = datetime(int(year), int(month), int(day))
                    dates.append(date_obj.strftime('%Y-%m-%d'))
                except ValueError:
                    # 日期无效，跳过
                    pass
        return dates
