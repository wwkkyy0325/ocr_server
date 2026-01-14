# -*- coding: utf-8 -*-

"""
表格拆分器（用于识别表格边缘线条并拆分图像）
"""

import cv2
import numpy as np
from PIL import Image

class TableSplitter:
    def __init__(self):
        """
        初始化表格拆分器
        """
        pass

    def split(self, image, mode='horizontal'):
        """
        根据模式拆分图像
        
        Args:
            image: 输入图像 (PIL Image or numpy array)
            mode: 拆分模式 ('horizontal', 'vertical', 'cell')
            
        Returns:
            list: 拆分后的结果列表 [{'image': PIL Image, 'box': (x, y, w, h), 'row': int, 'col': int}, ...]
        """
        # 确保输入是numpy数组
        if isinstance(image, Image.Image):
            cv_image = np.array(image)
            # PIL是RGB，OpenCV通常需要BGR，但这里我们只做灰度处理，或者保持RGB
            # 为了兼容性，如果是RGB，转换为BGR
            if cv_image.ndim == 3:
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
        else:
            cv_image = image

        # 转换为灰度图
        if cv_image.ndim == 3:
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv_image

        # 二值化
        # 使用自适应阈值处理光照不均
        binary = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2)
        
        rows, cols = binary.shape
        scale = 20 # 经验值
        
        # 识别横线
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cols // scale, 1))
        horizontal_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
        
        # 识别竖线
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, rows // scale))
        vertical_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
        
        # 根据模式处理
        results = []
        
        if mode == 'horizontal':
            # 仅横向拆分
            crops_info = self._split_by_lines(cv_image, horizontal_mask, is_horizontal=True)
            for i, info in enumerate(crops_info):
                info['row'] = i
                info['col'] = 0
                results.append(info)
            
        elif mode == 'vertical':
            # 仅纵向拆分
            crops_info = self._split_by_lines(cv_image, vertical_mask, is_horizontal=False)
            for i, info in enumerate(crops_info):
                info['row'] = 0
                info['col'] = i
                results.append(info)
            
        elif mode == 'cell':
            # 单元格拆分
            h_lines = self._get_line_positions(horizontal_mask, is_horizontal=True)
            v_lines = self._get_line_positions(vertical_mask, is_horizontal=False)
            
            # 补充图像边缘
            h_lines = [0] + h_lines + [rows]
            v_lines = [0] + v_lines + [cols]
            
            h_lines.sort()
            v_lines.sort()
            
            # 去重和合并相近线条
            h_lines = self._merge_close_lines(h_lines)
            v_lines = self._merge_close_lines(v_lines)
            
            for i in range(len(h_lines) - 1):
                y1, y2 = h_lines[i], h_lines[i+1]
                if y2 - y1 < 10: continue
                
                for j in range(len(v_lines) - 1):
                    x1, x2 = v_lines[j], v_lines[j+1]
                    if x2 - x1 < 10: continue
                    
                    crop = cv_image[y1:y2, x1:x2]
                    results.append({
                        'image': crop,
                        'box': (int(x1), int(y1), int(x2-x1), int(y2-y1)),
                        'row': i,
                        'col': j
                    })
                    
        else:
            results = [{
                'image': cv_image,
                'box': (0, 0, cols, rows),
                'row': 0,
                'col': 0
            }]
            
        # 转换回PIL Image
        final_results = []
        for res in results:
            crop = res['image']
            if crop.size == 0: continue
            
            if crop.ndim == 3:
                crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            
            res['image'] = Image.fromarray(crop)
            final_results.append(res)
            
        return final_results

    def _split_by_lines(self, image, mask, is_horizontal=True):
        """根据线条掩码拆分图像，返回图像和位置信息"""
        positions = self._get_line_positions(mask, is_horizontal)
        
        # 补充图像边缘
        limit = image.shape[0] if is_horizontal else image.shape[1]
        positions = [0] + positions + [limit]
        positions.sort()
        positions = self._merge_close_lines(positions)
        
        results = []
        for i in range(len(positions) - 1):
            p1, p2 = positions[i], positions[i+1]
            if p2 - p1 < 10: continue
            
            if is_horizontal:
                crop = image[p1:p2, :]
                # x, y, w, h
                box = (0, int(p1), image.shape[1], int(p2-p1))
            else:
                crop = image[:, p1:p2]
                box = (int(p1), 0, int(p2-p1), image.shape[0])
                
            results.append({
                'image': crop,
                'box': box
            })
            
        return results

    def _get_line_positions(self, mask, is_horizontal=True):
        """从掩码中提取线条位置"""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        positions = []
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if is_horizontal:
                # 横线取中心Y
                pos = y + h // 2
            else:
                # 竖线取中心X
                pos = x + w // 2
            positions.append(pos)
            
        return positions

    def _merge_close_lines(self, lines, threshold=10):
        """合并相近的线条位置"""
        if not lines: return []
        
        merged = [lines[0]]
        for line in lines[1:]:
            if line - merged[-1] > threshold:
                merged.append(line)
            else:
                # 取平均值更新
                merged[-1] = (merged[-1] + line) // 2
        return merged
