# -*- coding: utf-8 -*-

"""
数据库导入器
基于 scripts/process_ocr_json.py 逻辑，支持差量更新
"""

import sqlite3
import os
import re
import json
from datetime import datetime

class DatabaseImporter:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建人员信息表 (保持与脚本一致的结构)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS person_info (
                name TEXT,
                profession TEXT,
                id_card TEXT,
                phone_number TEXT
            )
        ''')
        
        # 创建已处理文件记录表 (用于差量更新)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS imported_files (
                filename TEXT PRIMARY KEY,
                import_time TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def _clean_name(self, text):
        """清洗姓名: 仅保留中文"""
        if not text: return ""
        return re.sub(r'[^\u4e00-\u9fa5]', '', text)

    def _clean_profession(self, text):
        """清洗职业: 去除首尾空白"""
        if not text: return ""
        return text.strip()

    def _clean_id(self, text):
        """清洗身份证号: 18位，允许X"""
        if not text: return ""
        # 常见OCR错误修正
        text = text.replace('G', '6').replace('g', '9').replace('l', '1').replace('z', '2')
        match = re.search(r'\d{17}[\dXx]', text)
        if match:
            return match.group(0)
        return re.sub(r'[^0-9Xx]', '', text)

    def _clean_phone(self, text):
        """清洗手机号: 11位数字"""
        if not text: return ""
        match = re.search(r'\d{11}', text)
        if match:
            return match.group(0)
        return re.sub(r'[^0-9]', '', text)

    def _parse_text_content(self, content):
        """
        解析文本内容
        模式: [Name+Profession] [ID] [Phone]
        """
        records = []
        normalized_content = content.replace('\n', ' ').replace('\r', ' ')
        
        # 使用正则表达式提取
        pattern = r'(.*?)\s*(\d{17}[\dXx])\s*(1\d{10})'
        matches = re.findall(pattern, normalized_content)
        
        for match in matches:
            raw_info, raw_id, raw_phone = match
            raw_info = raw_info.strip()
            
            # 分割姓名和职业
            parts = raw_info.split(maxsplit=1)
            if len(parts) == 2:
                name_candidate, prof_candidate = parts
            elif len(parts) == 1:
                name_candidate = parts[0]
                prof_candidate = ""
            else:
                name_candidate = ""
                prof_candidate = ""
                
            name = self._clean_name(name_candidate)
            profession = self._clean_profession(prof_candidate)
            id_card = self._clean_id(raw_id)
            phone = self._clean_phone(raw_phone)
            
            if name or id_card or phone:
                records.append({
                    'name': name,
                    'profession': profession,
                    'id_card': id_card,
                    'phone': phone
                })
        return records

    def _save_records(self, conn, records):
        """保存记录到数据库 (带记录级去重)"""
        if not records:
            return 0
            
        cursor = conn.cursor()
        count = 0
        
        for r in records:
            name = r['name']
            profession = r['profession']
            id_card = r['id_card']
            phone = r['phone']
            
            if not id_card:
                continue
                
            # 记录级去重逻辑
            cursor.execute("SELECT rowid, name, profession, phone_number FROM person_info WHERE id_card = ?", (id_card,))
            existing = cursor.fetchone()
            
            if existing:
                existing_rowid, existing_name, existing_prof, existing_phone = existing
                if existing_phone == phone:
                    if existing_name != name or existing_prof != profession:
                        cursor.execute(
                            "UPDATE person_info SET name = ?, profession = ? WHERE rowid = ?",
                            (name, profession, existing_rowid)
                        )
                continue
            
            # 插入新记录
            cursor.execute(
                "INSERT INTO person_info (name, profession, id_card, phone_number) VALUES (?, ?, ?, ?)",
                (name, profession, id_card, phone)
            )
            count += 1
            
        return count

    def import_from_directory(self, source_dir, progress_callback=None):
        """
        从指定目录导入数据
        
        Args:
            source_dir: 源目录 (程序会自动查找其下的 txt 子目录)
            progress_callback: 进度回调函数 (processed_count, total_count, current_file)
        
        Returns:
            tuple: (processed_files_count, added_records_count)
        """
        txt_dir = os.path.join(source_dir, 'txt')
        if not os.path.exists(txt_dir):
            print(f"Warning: 'txt' subdirectory not found in {source_dir}")
            return 0, 0
            
        files = [f for f in os.listdir(txt_dir) if f.lower().endswith('.txt')]
        total_files = len(files)
        
        conn = sqlite3.connect(self.db_path)
        processed_files_count = 0
        total_added_records = 0
        
        try:
            for idx, filename in enumerate(files):
                # 差量更新检查：检查文件是否已导入
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM imported_files WHERE filename = ?", (filename,))
                if cursor.fetchone():
                    # 如果已导入，跳过
                    if progress_callback:
                        progress_callback(idx + 1, total_files, f"Skipping {filename}")
                    continue
                
                file_path = os.path.join(txt_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    records = self._parse_text_content(content)
                    added_count = self._save_records(conn, records)
                    total_added_records += added_count
                    
                    # 标记文件为已导入
                    cursor.execute(
                        "INSERT INTO imported_files (filename, import_time) VALUES (?, ?)",
                        (filename, datetime.now().isoformat())
                    )
                    conn.commit()
                    processed_files_count += 1
                    
                    if progress_callback:
                        progress_callback(idx + 1, total_files, f"Importing {filename}")
                        
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    
        finally:
            conn.close()
            
        return processed_files_count, total_added_records
