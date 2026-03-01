# -*- coding: utf-8 -*-

"""
记录管理器（防止重复处理）
"""

import os
import json
import threading
import sqlite3
from datetime import datetime

class RecordManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    @classmethod
    def get_instance(cls, project_root=None):
        """
        获取全局唯一的 RecordManager 实例
        """
        with cls._lock:
            if cls._instance is None:
                if project_root is None:
                    # 尝试推断项目根目录，如果未提供
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
                data_dir = os.path.join(project_root, "data")
                os.makedirs(data_dir, exist_ok=True)
                db_path = os.path.join(data_dir, "processed_records.db")
                cls._instance = cls(db_path)
            return cls._instance

    def _init_db(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS processed_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT UNIQUE,
                        filename TEXT,
                        timestamp TEXT,
                        status TEXT,
                        output_path TEXT
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON processed_files (file_path)')
                conn.commit()
        except Exception as e:
            print(f"Error initializing database: {e}")

    def is_recorded(self, file_path):
        """
        检查文件是否已记录 (使用完整路径)
        """
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM processed_files WHERE file_path = ? AND status = "success"', (file_path,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking record for {file_path}: {e}")
            return False

    def add_record(self, file_path, status='success', output_path=''):
        """
        添加处理记录
        """
        try:
            filename = os.path.basename(file_path)
            timestamp = datetime.now().isoformat()
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO processed_files (file_path, filename, timestamp, status, output_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (file_path, filename, timestamp, status, output_path))
                conn.commit()
        except Exception as e:
            print(f"Error adding record for {file_path}: {e}")

    def clear_all_records(self):
        """
        清空所有记录
        """
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM processed_files')
                # 重置自增 ID
                cursor.execute('DELETE FROM sqlite_sequence WHERE name="processed_files"')
                conn.commit()
            print("All records cleared from database.")
            return True
        except Exception as e:
            print(f"Error clearing records: {e}")
            return False

    # 兼容旧接口的方法（如果还有其他地方调用且只传了 filename）
    # 但建议修改调用处传入完整路径
    def is_recorded_filename(self, filename):
        # 这是一个不精确的检查，仅供参考，应避免使用
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM processed_files WHERE filename = ?', (filename,))
                return cursor.fetchone() is not None
        except Exception:
            return False
