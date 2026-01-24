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

try:
    from PyQt5.QtGui import QImageReader
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

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
                phone_number TEXT,
                company_name TEXT,
                certificates_json TEXT,
                level TEXT,
                registration_number TEXT,
                b_cert_status TEXT,
                b_cert_issue_date TEXT,
                b_cert_expiry_date TEXT,
                result_count INTEGER,
                verification_time TEXT
            )
        ''')
        
        # 检查并添加新列 (如果表已存在)
        cursor.execute("PRAGMA table_info(person_info)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'company_name' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN company_name TEXT")
            
        if 'certificates_json' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN certificates_json TEXT")

        if 'level' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN level TEXT")

        if 'registration_number' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN registration_number TEXT")
            
        if 'b_cert_status' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN b_cert_status TEXT")
            
        if 'b_cert_issue_date' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN b_cert_issue_date TEXT")
            
        if 'b_cert_expiry_date' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN b_cert_expiry_date TEXT")

        if 'result_count' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN result_count INTEGER")

        if 'verification_time' not in columns:
            cursor.execute("ALTER TABLE person_info ADD COLUMN verification_time TEXT")
        
        # 创建证书表 (子表)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id_card TEXT,
                profession TEXT,
                expiry_date TEXT,
                level TEXT,
                registration_number TEXT,
                FOREIGN KEY (person_id_card) REFERENCES person_info(id_card)
            )
        ''')

        # 创建索引以加速查询
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cert_person_id ON certificates(person_id_card)")

        conn.commit()
        conn.close()

    def _clean_name(self, text):
        """清洗姓名: 仅保留中文"""
        if not text: return ""
        return re.sub(r'[^\u4e00-\u9fa5]', '', text)

    def _clean_profession(self, text):
        """清洗职业: 去除首尾空白，移除包含长数字的异常片段"""
        if not text: return ""
        # 移除包含6位以上数字的片段（防止ID/Phone残留）
        parts = text.split()
        clean_parts = []
        for p in parts:
            if not re.search(r'\d{6,}', p):
                clean_parts.append(p)
        return " ".join(clean_parts).strip()

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
        # 优化正则：允许ID和手机号之间存在少量干扰字符（非贪婪匹配，防止跨行错误）
        # 之前的正则: r'(.*?)\s*(\d{17}[\dXx])\s*(1\d{10})'
        pattern = r'(.*?)\s*(\d{17}[\dXx])\s*(?:.{0,30}?)\s*(1\d{10})'
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
                
                # 强绑定逻辑：ID存在时，以当前导入的手机号为准（确保绑定正确）
                # 姓名和职业：仅当新数据有效时更新，或者为了保证ID-Phone绑定而更新
                
                new_phone = phone
                new_name = name if name else existing_name
                new_prof = profession if profession else existing_prof
                
                # 只要有任何字段不一致，就执行更新
                if (new_phone != existing_phone) or (new_name != existing_name) or (new_prof != existing_prof):
                    cursor.execute(
                        "UPDATE person_info SET name = ?, profession = ?, phone_number = ? WHERE rowid = ?",
                        (new_name, new_prof, new_phone, existing_rowid)
                    )
                continue
            
            # 插入新记录
            cursor.execute(
                "INSERT INTO person_info (name, profession, id_card, phone_number) VALUES (?, ?, ?, ?)",
                (name, profession, id_card, phone)
            )
            count += 1
            
        return count

    def _extract_content(self, file_path):
        """读取文件内容 (支持 .txt 和 .json)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.lower().endswith('.txt'):
                    return f.read()
                elif file_path.lower().endswith('.json'):
                    data = json.load(f)
                    # 优先使用 full_text
                    if 'full_text' in data and data['full_text']:
                        # 检查是否有表格结构信息，如果有，我们可以重建更准确的行结构
                        # 因为 full_text 只是简单的拼接，可能丢失了表格的行结构信息（取决于拼接方式）
                        # 但 ProcessManager 生成的 full_text 通常是按区域顺序拼接的
                        # 如果是表格模式，ProcessManager 也是按行/列顺序处理的，所以 full_text 应该大致可用
                        # 但为了最稳健的解析，我们尝试利用 table_info 重建结构化文本
                        if 'regions' in data and any('table_info' in r for r in data['regions']):
                            pass # Fall through to table_info processing
                        else:
                            return data['full_text']
                            
                    # 其次从 regions 构建
                    if 'regions' in data:
                        regions = data['regions']
                        if not regions:
                            return ""

                        # 0. 检查是否有表格结构信息 (table_info)
                        has_table_info = any('table_info' in r for r in regions)
                        
                        if has_table_info:
                            # 基于表格信息重建文本
                            # 按行号分组
                            rows_map = {}
                            for r in regions:
                                if 'table_info' in r:
                                    row_idx = r['table_info'].get('row', 0)
                                    col_idx = r['table_info'].get('col', 0)
                                    if row_idx not in rows_map:
                                        rows_map[row_idx] = []
                                    rows_map[row_idx].append((col_idx, r.get('text', '')))
                            
                            # 按行号排序
                            sorted_row_indices = sorted(rows_map.keys())
                            text_parts = []
                            for row_idx in sorted_row_indices:
                                # 按列号排序
                                cols = rows_map[row_idx]
                                cols.sort(key=lambda x: x[0])
                                # 连接同一行的文本
                                row_text = " ".join([item[1] for item in cols])
                                text_parts.append(row_text)
                                
                            return "\n".join(text_parts)

                        # 1. 计算所有区域的几何中心和高度
                        for r in regions:
                            coords = r.get('coordinates', [])
                            if coords:
                                ys = [p[1] for p in coords]
                                xs = [p[0] for p in coords]
                                r['cy'] = sum(ys) / len(ys)
                                r['cx'] = sum(xs) / len(xs)
                                r['h'] = max(ys) - min(ys)
                            else:
                                r['cy'] = 0
                                r['cx'] = 0
                                r['h'] = 0
                        
                        # 2. 计算平均行高 (用于行聚类)
                        heights = [r['h'] for r in regions if r['h'] > 0]
                        avg_height = sum(heights) / len(heights) if heights else 20
                        
                        # 3. 行聚类算法
                        # 先按垂直中心 cy 排序
                        regions.sort(key=lambda x: x['cy'])
                        
                        rows = []
                        current_row = []
                        
                        for r in regions:
                            if not current_row:
                                current_row.append(r)
                            else:
                                # 计算当前行的平均 cy
                                row_cy = sum(item['cy'] for item in current_row) / len(current_row)
                                # 如果当前元素 cy 与行平均 cy 差距小于半行高，视为同一行
                                if abs(r['cy'] - row_cy) < avg_height / 2:
                                    current_row.append(r)
                                else:
                                    # 结束当前行，开始新行
                                    rows.append(current_row)
                                    current_row = [r]
                        if current_row:
                            rows.append(current_row)
                        
                        # 4. 行内按水平中心 cx 排序并拼接
                        text_parts = []
                        for row in rows:
                            row.sort(key=lambda x: x['cx'])
                            row_text = " ".join([r.get('text', '') for r in row])
                            text_parts.append(row_text)
                            
                        # 用换行符连接各行
                        return "\n".join(text_parts)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        return ""

    def import_records_with_template(self, ocr_results_map, template_config):
        """
        基于可视化模板导入记录
        ocr_results_map: { "image_path": ocr_results_list }
        template_config: { "bindings": { "field": { "indices": [0,1], "bbox": [x1,y1,x2,y2] } } }
        """
        records = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            bindings = template_config.get('bindings', {})
            
            for image_path, ocr_results in ocr_results_map.items():
                record = {}
                
                # 获取图片尺寸以支持基于位置的匹配
                img_w, img_h = 0, 0
                if PYQT_AVAILABLE and os.path.exists(image_path):
                    try:
                        reader = QImageReader(image_path)
                        size = reader.size()
                        img_w, img_h = size.width(), size.height()
                    except Exception as e:
                        print(f"Failed to read image size for {image_path}: {e}")

                for field_key, binding in bindings.items():
                    texts = []
                    bbox = binding.get('bbox')
                    
                    # 优先使用空间位置匹配 (Spatial Matching)
                    if bbox and img_w > 0 and img_h > 0:
                        bx1, by1, bx2, by2 = bbox
                        candidates = []
                        
                        for item in ocr_results:
                            # 获取 item 的包围盒
                            ibox = None
                            if 'box' in item: # Format: [x1, y1, x2, y2]
                                ibox = item['box']
                            elif 'coordinates' in item: # Format: [[x,y], ...]
                                xs = [p[0] for p in item['coordinates']]
                                ys = [p[1] for p in item['coordinates']]
                                ibox = [min(xs), min(ys), max(xs), max(ys)]
                                
                            if ibox:
                                # 计算中心点归一化坐标
                                cx = (ibox[0] + ibox[2]) / 2 / img_w
                                cy = (ibox[1] + ibox[3]) / 2 / img_h
                                
                                # 检查中心点是否在模板定义的区域内
                                # 稍微放宽一点边界容差可能更好，但这里先严格匹配
                                if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                                    # 为了排序，保存原始 y 和 x
                                    candidates.append((ibox[1], ibox[0], item.get('text', '')))
                        
                        # 按 y (行) 然后 x (列) 排序
                        candidates.sort(key=lambda x: (x[0], x[1]))
                        texts = [c[2] for c in candidates]
                        
                    # 如果空间匹配没有结果（或者没有bbox/image size），回退到索引匹配
                    if not texts:
                        indices = binding.get('indices', [])
                        for idx in indices:
                            if 0 <= idx < len(ocr_results):
                                texts.append(ocr_results[idx].get('text', ''))
                        
                    if texts:
                        record[field_key] = " ".join(texts)
                
                if record:
                    self._save_single_record(cursor, record)
                    records.append(record)
            
            conn.commit()
            return len(records), []
            
        except Exception as e:
            conn.rollback()
            print(f"Template import failed: {e}")
            raise e
        finally:
            conn.close()

    def _save_single_record(self, cursor, record):
        """保存单条记录，支持更新逻辑"""
        id_card = record.get('id_card', '')
        if not id_card:
            # 如果没有身份证号，暂时无法去重/更新，或者生成临时ID
            # 这里简单跳过无ID数据，或者你可以定义策略
            return

        # 检查是否存在
        cursor.execute("SELECT rowid, * FROM person_info WHERE id_card = ?", (id_card,))
        existing = cursor.fetchone()
        
        if existing:
            # 更新逻辑
            update_fields = []
            update_values = []
            for k, v in record.items():
                if k != 'id_card': # ID不可变
                    update_fields.append(f"{k} = ?")
                    update_values.append(v)
            
            if update_fields:
                update_values.append(id_card)
                sql = f"UPDATE person_info SET {', '.join(update_fields)} WHERE id_card = ?"
                cursor.execute(sql, update_values)
        else:
            # 插入逻辑
            cols = list(record.keys())
            vals = list(record.values())
            placeholders = ', '.join(['?' for _ in cols])
            sql = f"INSERT INTO person_info ({', '.join(cols)}) VALUES ({placeholders})"
            cursor.execute(sql, vals)

    def import_from_directory(self, source_dir, progress_callback=None):
        """
        递归从指定目录导入数据 (支持 .txt 和 .json)
        
        Args:
            source_dir: 源目录 (递归查找所有 .txt/.json 文件)
            progress_callback: 进度回调函数
        
        Returns:
            tuple: (processed_files_count, added_records_count)
        """
        if not os.path.exists(source_dir):
            print(f"Directory not found: {source_dir}")
            return 0, 0
            
        # 1. 递归扫描所有文件
        files_to_process = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith(('.json', '.txt')):
                    files_to_process.append(os.path.join(root, file))
        
        total_files = len(files_to_process)
        if total_files == 0:
            return 0, 0
        
        conn = sqlite3.connect(self.db_path)
        processed_files_count = 0
        total_added_records = 0
        
        try:
            for idx, file_path in enumerate(files_to_process):
                try:
                    content = self._extract_content(file_path)
                    
                    if content:
                        records = self._parse_text_content(content)
                        added_count = self._save_records(conn, records)
                        total_added_records += added_count
                        processed_files_count += 1
                    
                    if progress_callback:
                        filename = os.path.basename(file_path)
                        progress_callback(idx + 1, total_files, f"Importing {filename}")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
            
            # 提交事务
            conn.commit()
                    
        finally:
            conn.close()
            
        return processed_files_count, total_added_records
