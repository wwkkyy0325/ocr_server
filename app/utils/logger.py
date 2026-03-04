# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：轻量级日志记录器，统一输出到控制台并可选写入文件
# - 核心实现：提供 info/error/warning/debug 四级方法，自动附加时间戳
# - 关联关系：由 MainWindow/控制层/工具类按需记录运行与错误信息
"""
日志记录（识别过程、错误信息）
"""

import os
from datetime import datetime


class Logger:
    def __init__(self, log_file=None):
        """
        初始化日志记录器

        Args:
            log_file: 日志文件路径
        """
        self.log_file = log_file
        if log_file:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

    def info(self, message):
        """
        记录信息日志

        Args:
            message: 日志消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [INFO] {message}"
        print(log_message)
        if self.log_file:
            self._write_to_file(log_message)

    def error(self, message):
        """
        记录错误日志

        Args:
            message: 错误消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [ERROR] {message}"
        print(log_message)
        if self.log_file:
            self._write_to_file(log_message)

    def warning(self, message):
        """
        记录警告日志

        Args:
            message: 警告消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [WARNING] {message}"
        print(log_message)
        if self.log_file:
            self._write_to_file(log_message)

    def debug(self, message):
        """
        记录调试日志

        Args:
            message: 调试消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [DEBUG] {message}"
        print(log_message)
        if self.log_file:
            self._write_to_file(log_message)

    def _write_to_file(self, message):
        """
        写入日志到文件

        Args:
            message: 日志消息
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(message + '\n')
        except Exception as e:
            print(f"Error writing to log file: {e}")
