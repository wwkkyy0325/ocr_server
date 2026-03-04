# -*- coding: utf-8 -*-
"""
Result Adapter Middleware (result_adapter.py)

全权负责将各种 OCR 引擎的输出结果转换为前端 UI 可用的标准格式。
支持多种 OCR 输出格式的自动识别和适配，包括：
- PaddleOCR 标准格式
- PP-Structure 表格识别格式
- 自定义 OCR 引擎格式
- 表格拆分后的单元格结果

标准前端数据项结构：
{
    'text': str,                # 识别的文本内容
    'confidence': float,        # 置信度 (0.0 - 1.0)
    'box': [x1, y1, x2, y2],    # 边界框（图像坐标系）
    'polygon': [[x,y], ...],    # 精确多边形坐标（可选）
    'table_info': {             # 表格结构信息（可选）
        'row': int,             # 行索引
        'col': int,             # 列索引
        'rowspan': int,         # 跨行数
        'colspan': int,         # 跨列数
        'is_header': bool,      # 是否表头
        'cell_box': [x, y, w, h] # 单元格相对位置（可选）
    },
    'source': str,              # 数据来源标记 ('ocr', 'table_ai', 'table_split')
    'original': dict            # 原始数据引用（用于调试）
}
"""

import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field


@dataclass
class OcrResultItem:
    """OCR 结果项的标准数据类"""
    text: str = ""
    confidence: float = 0.0
    box: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    polygon: List[List[int]] = field(default_factory=list)
    table_info: Optional[Dict[str, Any]] = None
    source: str = "ocr"
    original: Optional[Dict] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'text': self.text,
            'confidence': self.confidence,
            'box': self.box,
            'polygon': self.polygon,
            'table_info': self.table_info,
            'source': self.source
        }
        if self.original is not None:
            result['original'] = self.original
        return result


class ResultAdapterError(Exception):
    """Result Adapter 异常类"""
    pass


class ResultAdapter:
    """
    OCR 结果适配器 - 统一处理所有 OCR 输出格式到前端格式的转换
    """
    
    # 支持的输入格式标记
    FORMAT_OCR_STANDARD = 'ocr_standard'  # {'regions': [...]}
    FORMAT_OCR_LIST = 'ocr_list'          # [...]
    FORMAT_TABLE_AI = 'table_ai'          # PP-Structure AI 表格结果
    FORMAT_TABLE_SPLIT = 'table_split'    # 表格拆分后的单元格结果
    
    @classmethod
    def adapt(cls, raw_data: Any, source_type: str = "auto") -> List[Dict[str, Any]]:
        """
        将原始 OCR 数据适配为标准前端格式
        
        Args:
            raw_data: 原始数据（可以是 dict、list 或其他格式）
            source_type: 数据来源类型提示，支持：
                - 'auto': 自动检测
                - 'ocr': 普通 OCR 结果
                - 'table_ai': AI 表格识别结果
                - 'table_split': 表格拆分结果
                
        Returns:
            list: 标准化后的结果列表
            
        Raises:
            ResultAdapterError: 当数据格式无法解析时
        """
        if raw_data is None:
            return []
        
        try:
            print(f"\nDEBUG [ResultAdapter.adapt] Starting adaptation...")
            print(f"  Input type: {type(raw_data).__name__}")
            if isinstance(raw_data, (dict, list)) and len(raw_data) > 0:
                if isinstance(raw_data, dict):
                    print(f"  Input keys: {list(raw_data.keys())[:10]}")
                if isinstance(raw_data, list):
                    print(f"  Input length: {len(raw_data)} items")
                    if raw_data and isinstance(raw_data[0], dict):
                        print(f"  First item keys: {list(raw_data[0].keys())[:10]}")
            
            # 自动检测格式
            if source_type == "auto":
                detected_format, regions = cls._detect_and_extract(raw_data)
            else:
                detected_format = source_type
                regions = cls._extract_regions(raw_data, detected_format)
            
            print(f"  Detected format: {detected_format}")
            print(f"  Extracted regions count: {len(regions) if regions else 0}")
            
            if regions is None:
                return []
            
            # 处理每个区域
            adapted_items = []
            for idx, region in enumerate(regions):
                try:
                    item = cls._adapt_single_region(region, detected_format)
                    if item and item.text:  # 只保留有文本内容的项
                        adapted_items.append(item.to_dict())
                except Exception as e:
                    print(f"Warning: Failed to adapt region {idx}: {e}")
                    continue
            
            print(f"  Adapted to {len(adapted_items)} items")
            if adapted_items:
                print(f"  First adapted item keys: {list(adapted_items[0].keys())}")
                print(f"  First item has box: {'box' in adapted_items[0]}")
                print(f"  First item has polygon: {'polygon' in adapted_items[0]}")
                print(f"  First item has table_info: {'table_info' in adapted_items[0]}")
                if 'box' in adapted_items[0]:
                    print(f"  First box value: {adapted_items[0]['box']}")
            print()
            
            return adapted_items
            
        except Exception as e:
            print(f"Error in ResultAdapter.adapt: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @classmethod
    def _detect_and_extract(cls, raw_data: Any) -> Tuple[str, Optional[List]]:
        """
        自动检测数据格式并提取区域列表
        
        Returns:
            tuple: (格式类型，区域列表)
        """
        # Case 1: 字典格式
        if isinstance(raw_data, dict):
            # PP-Structure AI 表格结果
            if 'html' in raw_data or 'cell_bboxes' in raw_data or 'pred_html' in raw_data:
                return cls.FORMAT_TABLE_AI, [raw_data]
            
            # 标准 OCR 格式
            if 'regions' in raw_data:
                return cls.FORMAT_OCR_STANDARD, raw_data['regions']
            
            # Paddle 格式
            if 'res' in raw_data:
                res = raw_data['res']
                if isinstance(res, list):
                    return cls.FORMAT_OCR_LIST, res
            
            # 包含 bbox 的单个区域
            if 'bbox' in raw_data or 'box' in raw_data or 'coordinates' in raw_data:
                return cls.FORMAT_OCR_LIST, [raw_data]
            
            # 未知字典格式
            return cls.FORMAT_OCR_LIST, []
        
        # Case 2: 列表格式
        elif isinstance(raw_data, list):
            # 检查是否是 AI 表格识别结果（每个元素都有 table_info）
            if raw_data and len(raw_data) > 0:
                first_item = raw_data[0]
                if isinstance(first_item, dict) and ('table_info' in first_item or 
                    any(k in first_item for k in ['row', 'col', 'rowspan', 'colspan'])):
                    # 这是一个包含多个单元格的 AI 表格结果
                    return cls.FORMAT_TABLE_AI, raw_data
            
            return cls.FORMAT_OCR_LIST, raw_data
        
        # Case 3: 其他格式
        else:
            print(f"Warning: Unknown data format: {type(raw_data)}")
            return cls.FORMAT_OCR_LIST, []
    
    @classmethod
    def _extract_regions(cls, raw_data: Any, format_type: str) -> Optional[List]:
        """根据指定格式提取区域列表"""
        if not isinstance(raw_data, (dict, list)):
            return None
        
        if format_type == cls.FORMAT_OCR_STANDARD:
            return raw_data.get('regions', [])
        elif format_type == cls.FORMAT_TABLE_AI:
            return [raw_data] if isinstance(raw_data, dict) else []
        else:
            return raw_data if isinstance(raw_data, list) else []
    
    @classmethod
    def _adapt_single_region(cls, region: Any, format_type: str) -> Optional[OcrResultItem]:
        """
        适配单个区域
        
        Args:
            region: 单个区域数据
            format_type: 格式类型
            
        Returns:
            OcrResultItem 或 None
        """
        if not isinstance(region, dict):
            return None
        
        # 根据格式类型选择适配策略
        if format_type == cls.FORMAT_TABLE_AI:
            return cls._adapt_table_ai(region)
        else:
            return cls._adapt_ocr_region(region)
    
    @classmethod
    def _adapt_ocr_region(cls, region: Dict) -> Optional[OcrResultItem]:
        """适配普通 OCR 区域"""
        item = OcrResultItem()
        item.original = region
        item.source = "ocr"
        
        # 提取文本
        item.text = cls._extract_text(region)
        
        # 提取置信度
        item.confidence = cls._extract_confidence(region)
        
        # 提取坐标
        box, polygon = cls._extract_coordinates(region)
        item.box = box
        item.polygon = polygon
        
        # 提取表格信息（如果有）
        item.table_info = cls._extract_table_info(region)
        if item.table_info:
            item.source = "table_split"
        
        return item if item.text else None
    
    @classmethod
    def _adapt_table_ai(cls, region: Dict) -> Optional[OcrResultItem]:
        """适配 AI 表格识别结果"""
        item = OcrResultItem()
        item.original = region
        item.source = "table_ai"
        
        # 提取文本
        item.text = cls._extract_text(region)
        
        # 提取置信度
        item.confidence = cls._extract_confidence(region, default=0.95)
        
        # 提取坐标
        box, polygon = cls._extract_coordinates(region)
        item.box = box
        item.polygon = polygon
        
        # 提取表格信息
        item.table_info = cls._extract_table_info(region, is_ai_result=True)
        
        return item if item.text else None
    
    @staticmethod
    def _extract_text(region: Dict) -> str:
        """从区域中提取文本"""
        # 尝试多个可能的键
        for key in ['text', 'rec_text', 'recognized_text', 'content']:
            if key in region:
                val = region[key]
                if val is not None:
                    text = str(val).strip()
                    if text:
                        return text
        
        # 如果是表格结果，尝试从 HTML 提取
        html = region.get('html') or region.get('pred_html')
        if html:
            try:
                from lxml import html as lhtml
                tree = lhtml.fragment_fromstring(html, create_parent="div")
                text = tree.text_content().strip()
                if text:
                    return text
            except:
                pass
        
        return ""
    
    @staticmethod
    def _extract_confidence(region: Dict, default: float = 0.0) -> float:
        """从区域中提取置信度"""
        for key in ['confidence', 'score', 'prob', 'rec_score']:
            if key in region:
                val = region[key]
                try:
                    conf = float(val)
                    return max(0.0, min(1.0, conf))
                except (ValueError, TypeError):
                    pass
        return default
    
    @classmethod
    def _extract_coordinates(cls, region: Dict) -> Tuple[List[int], List[List[int]]]:
        """
        从区域中提取坐标
        
        Returns:
            tuple: (box [x1,y1,x2,y2], polygon [[x1,y1],...])
        """
        box = [0, 0, 0, 0]
        polygon = []
        
        # 优先使用已经计算好的 box 字段（边界框格式 [x1,y1,x2,y2]）
        if 'box' in region:
            coords = region['box']
            # 如果是 [x1, y1, x2, y2] 格式
            if isinstance(coords, list) and len(coords) == 4:
                try:
                    box = [int(v) for v in coords]
                    x1, y1, x2, y2 = box
                    polygon = [
                        [x1, y1], [x2, y1],
                        [x2, y2], [x1, y2]
                    ]
                    return box, polygon
                except (ValueError, TypeError):
                    pass
        
        # 其次尝试 coordinates/poly/points/bbox 等字段
        coords = None
        for key in ['coordinates', 'points', 'poly', 'bbox']:
            val = region.get(key)
            if val is not None:
                coords = val
                break
        
        # 处理 numpy 数组或类数组对象
        if hasattr(coords, 'tolist'):
            # NumPy array 或其他有 tolist() 方法的对象
            try:
                coords = coords.tolist()
            except:
                coords = []
        elif isinstance(coords, list) and len(coords) > 0:
            # 检查是否是嵌套的 numpy 数组列表
            # 不要直接清空，而是尝试转换每个元素
            new_coords = []
            for item in coords:
                if hasattr(item, 'tolist'):
                    # numpy array 元素，转换为 Python 类型
                    try:
                        new_coords.append(item.tolist())
                    except:
                        new_coords.append(item)
                else:
                    new_coords.append(item)
            coords = new_coords
        
        if not coords:
            return box, polygon
        
        # Case A: 多边形 [[x1,y1], [x2,y2], ...]
        if isinstance(coords, list) and len(coords) > 0:
            first_elem = coords[0]
            if isinstance(first_elem, (list, tuple)):
                # 检查是 4 点矩形还是任意多边形
                if len(coords) == 4:
                    # 4 点矩形
                    try:
                        xs = [float(p[0]) for p in coords]
                        ys = [float(p[1]) for p in coords]
                        if xs and ys:
                            box = [
                                int(min(xs)), int(min(ys)),
                                int(max(xs)), int(max(ys))
                            ]
                            polygon = [[int(x), int(y)] for x, y in coords]
                    except:
                        pass
                else:
                    # 任意多边形
                    polygon = [[int(p[0]), int(p[1])] for p in coords if len(p) >= 2]
                    if polygon:
                        xs = [p[0] for p in polygon]
                        ys = [p[1] for p in polygon]
                        box = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
            
            # Case B: 边界框 [x1, y1, x2, y2]
            elif len(coords) == 4 and all(isinstance(v, (int, float)) for v in coords):
                try:
                    box = [int(v) for v in coords]
                    x1, y1, x2, y2 = box
                    polygon = [
                        [x1, y1], [x2, y1],
                        [x2, y2], [x1, y2]
                    ]
                except:
                    pass
        
        return box, polygon
    
    @staticmethod
    def _extract_table_info(region: Dict, is_ai_result: bool = False) -> Optional[Dict[str, Any]]:
        """提取表格信息"""
        table_info = None
        
        # 尝试从 table_info 键提取
        raw_info = region.get('table_info')
        if raw_info and isinstance(raw_info, dict):
            table_info = {
                'row': int(raw_info.get('row', 0)),
                'col': int(raw_info.get('col', 0)),
                'rowspan': int(raw_info.get('rowspan', 1)),
                'colspan': int(raw_info.get('colspan', 1)),
                'is_header': bool(raw_info.get('is_header', False))
            }
            if 'cell_box' in raw_info:
                table_info['cell_box'] = raw_info['cell_box']
        
        # 如果是 AI 结果或直接在根级别有表格字段
        if not table_info:
            has_table_fields = any(k in region for k in ['row', 'col', 'rowspan', 'colspan'])
            if has_table_fields:
                table_info = {
                    'row': int(region.get('row', 0)),
                    'col': int(region.get('col', 0)),
                    'rowspan': int(region.get('rowspan', 1)),
                    'colspan': int(region.get('colspan', 1)),
                    'is_header': bool(region.get('is_header', False))
                }
                
                # 如果有 bbox，计算 cell_box
                bbox = region.get('bbox') or region.get('box')
                if bbox and isinstance(bbox, list) and len(bbox) == 4:
                    try:
                        x1, y1, x2, y2 = [int(v) for v in bbox]
                        table_info['cell_box'] = [x1, y1, x2 - x1, y2 - y1]
                    except:
                        pass
        
        return table_info
    
    @staticmethod
    def merge_results(results: List[List[Dict]]) -> List[Dict]:
        """
        合并多个 OCR 结果
        
        Args:
            results: 结果列表的列表
            
        Returns:
            list: 合并后的结果
        """
        merged = []
        for result_list in results:
            if isinstance(result_list, list):
                merged.extend(result_list)
        return merged
    
    @staticmethod
    def filter_empty(items: List[Dict]) -> List[Dict]:
        """过滤空文本项"""
        return [item for item in items if item.get('text', '').strip()]
    
    @staticmethod
    def sort_by_position(items: List[Dict], reading_order: str = 'lr-tb') -> List[Dict]:
        """
        按位置排序结果
        
        Args:
            items: 结果列表
            reading_order: 阅读顺序
                - 'lr-tb': 从左到右，从上到下（默认）
                - 'tb-lr': 从上到下，从左到右
                
        Returns:
            list: 排序后的结果
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
        except:
            return items
