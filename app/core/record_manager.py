# -*- coding: utf-8 -*-

"""
记录管理器（防止重复处理）
"""

import os
import json
import threading
from datetime import datetime

class RecordManager:
    _instances = {}
    _global_lock = threading.Lock()

    @classmethod
    def get_instance(cls, directory):
        """
        获取指定目录的RecordManager实例（单例模式）
        """
        with cls._global_lock:
            # 规范化路径
            norm_dir = os.path.normpath(os.path.abspath(directory))
            if norm_dir not in cls._instances:
                cls._instances[norm_dir] = cls(norm_dir)
            return cls._instances[norm_dir]

    def __init__(self, directory):
        self.directory = directory
        self.record_file = os.path.join(directory, "processed_records.json")
        self.lock = threading.Lock()
        self.records = {}
        self.load_records()

    def load_records(self):
        """
        加载记录
        """
        if os.path.exists(self.record_file):
            try:
                with open(self.record_file, 'r', encoding='utf-8') as f:
                    self.records = json.load(f)
            except Exception as e:
                print(f"Error loading records from {self.record_file}: {e}")
                self.records = {}
        else:
            self.records = {}

    def is_recorded(self, filename):
        """
        检查文件是否已记录
        """
        with self.lock:
            return filename in self.records

    def add_record(self, filename):
        """
        添加处理记录
        """
        with self.lock:
            self.records[filename] = {
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }
            self._save()

    def _save(self):
        """
        保存记录到文件
        """
        try:
            if not os.path.exists(self.directory):
                os.makedirs(self.directory, exist_ok=True)
            with open(self.record_file, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving records to {self.record_file}: {e}")
