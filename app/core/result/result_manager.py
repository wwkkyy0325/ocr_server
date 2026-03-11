# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：在内存中暂存 OCR 结果，提供增删查接口
# - 核心实现：以字典管理每个文件的结果与时间戳
# - 关联关系：由 ProcessingController/MainWindow 调用保存/获取结果
#              导出功能由 ResultExporter/ResultFormatter 负责
"""
结果管理（仅存储和查询）
"""

import os
from datetime import datetime
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class ResultManager:
    """
    结果管理器 - 仅负责内存中的结果存储和查询
    
    职责：
        - 存储 OCR 识别结果到内存
        - 提供查询、删除接口
        - 不负责文件导出（由 ResultExporter 负责）
    """
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ResultManager")
    def __init__(self):
        """
        初始化结果管理器
        """
        self.results = {}

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ResultManager")
    def store_result(self, image_path, result):
        """
        存储结果
    
        Args:
            image_path: 图像路径
            result: OCR 识别结果
        """
        logger = get_logger()
        logger.debug("result_manager", "store", f"存储结果：{os.path.basename(image_path)}")
        self.results[image_path] = {
            'result': result,
            'timestamp': datetime.now().isoformat(),
            'filename': os.path.basename(image_path)
        }

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ResultManager")
    def get_result(self, image_path):
        """
        获取结果
    
        Args:
            image_path: 图像路径
    
        Returns:
            OCR 识别结果
        """
        logger = get_logger()
        logger.debug("result_manager", "get", f"获取结果：{os.path.basename(image_path)}")
        result_data = self.results.get(image_path, None)
        return result_data['result'] if result_data else None

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={}, component="ResultManager")
    def get_all_results(self):
        """
        获取所有结果

        Returns:
            所有结果的字典
        """
        return self.results

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ResultManager")
    def clear_result(self, image_path):
        """
        清除特定图像的结果缓存
        
        Args:
            image_path: 图像路径
        """
        logger = get_logger()
        if image_path in self.results:
            logger.debug("result_manager", "clear", f"清除缓存结果：{os.path.basename(image_path)}")
            del self.results[image_path]

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ResultManager")
    def clear_all(self):
        """
        清除所有结果缓存
        """
        self.results.clear()
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=0, component="ResultManager")
    def get_count(self) -> int:
        """
        获取结果数量
        
        Returns:
            已存储的结果数量
        """
        return len(self.results)
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=False, component="ResultManager")
    def has_result(self, image_path: str) -> bool:
        """
        检查是否存在指定结果
        
        Args:
            image_path: 图像路径
            
        Returns:
            True 如果存在该结果
        """
        return image_path in self.results