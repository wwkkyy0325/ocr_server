# -*- coding: utf-8 -*-
"""
工具模块

导出内容：
    - PathManager: 统一路径管理器
    - ocr_utils: OCR 相关工具函数

使用示例：
    from app.utils import PathManager
    
    path_mgr = PathManager(project_root)
    output_dir = path_mgr.get_output_dir()
"""

from app.utils.path_manager import PathManager

__all__ = ['PathManager']