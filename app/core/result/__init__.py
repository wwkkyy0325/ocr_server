# -*- coding: utf-8 -*-
"""
结果处理模块

导出内容：
    - ResultManager: 内存结果管理（存储/查询）
    - ResultAdapter: OCR 数据格式适配
    - ResultExporter: MessagePack 文件导出
    - ResultFormatter: 文本格式转换（TXT/CSV/JSON）
    - ResultProcessor: 结果处理工具（合并/过滤/排序）

使用示例：
    from app.core.result import ResultManager, ResultExporter, ResultAdapter
    
    # 存储结果
    manager = ResultManager()
    manager.store_result(image_path, text)
    
    # 导出为 MessagePack
    exporter = ResultExporter(output_dir)
    exporter.save_result(image_path, text, regions)
    
    # 导出为 TXT
    exporter.export_to_text(manager.get_all_results(), output_path, format='txt')
"""

from app.core.result.result_manager import ResultManager
from app.core.result.result_adapter import ResultAdapter
from app.core.result.result_exporter import ResultExporter
from app.core.result.result_formatter import ResultFormatter
from app.core.result.result_processor import ResultProcessor

__all__ = [
    'ResultManager',
    'ResultAdapter',
    'ResultExporter',
    'ResultFormatter',
    'ResultProcessor',
]