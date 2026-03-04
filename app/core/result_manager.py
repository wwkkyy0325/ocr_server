# -*- coding: utf-8 -*-

"""
结果管理（存储、查询、导出）
"""

import json
import csv
import os
from datetime import datetime


class ResultManager:
    def __init__(self):
        """
        初始化结果管理器
        """
        self.results = {}

    def store_result(self, image_path, result):
        """
        存储结果

        Args:
            image_path: 图像路径
            result: OCR识别结果
        """
        print(f"Storing result for {image_path}")
        self.results[image_path] = {
            'result': result,
            'timestamp': datetime.now().isoformat(),
            'filename': os.path.basename(image_path)
        }

    def get_result(self, image_path):
        """
        获取结果

        Args:
            image_path: 图像路径

        Returns:
            OCR识别结果
        """
        print(f"Retrieving result for {image_path}")
        result_data = self.results.get(image_path, None)
        return result_data['result'] if result_data else None

    def get_all_results(self):
        """
        获取所有结果

        Returns:
            所有结果的字典
        """
        return self.results

    def export_results(self, output_path, format='txt'):
        """
        导出结果

        Args:
            output_path: 输出路径
            format: 导出格式 ('txt', 'json', 'csv')

        Returns:
            导出的文件路径
        """
        print(f"Exporting results in {format} format")
        
        # 确保输出目录存在
        if output_path:
            os.makedirs(output_path, exist_ok=True)
        else:
             # 如果没有提供输出路径，默认不导出或抛出异常
             # 为了兼容旧逻辑，这里可以返回空字符串
             return ""
        
        if format == 'json':
            file_path = os.path.join(output_path, f'ocr_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            return file_path
            
        elif format == 'csv':
            file_path = os.path.join(output_path, f'ocr_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Image Path', 'Filename', 'Result', 'Timestamp'])
                for image_path, data in self.results.items():
                    writer.writerow([image_path, data['filename'], data['result'], data['timestamp']])
            return file_path
            
        else:  # txt format
            file_path = os.path.join(output_path, f'ocr_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
            with open(file_path, 'w', encoding='utf-8') as f:
                for image_path, data in self.results.items():
                    f.write(f"Image: {image_path}\n")
                    f.write(f"Filename: {data['filename']}\n")
                    f.write(f"Result: {data['result']}\n")
                    f.write(f"Timestamp: {data['timestamp']}\n")
                    f.write("-" * 50 + "\n")
            return file_path

    def clear_result(self, image_path):
        """
        清除特定图像的结果缓存
        
        Args:
            image_path: 图像路径
        """
        if image_path in self.results:
            print(f"Clearing cached result for {image_path}")
            del self.results[image_path]

    def clear_all(self):
        """
        清除所有结果缓存
        """
        self.results.clear()
