# -*- coding: utf-8 -*-

import sqlite3
import os
import re
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog, QGroupBox, QWidget, QApplication, QCheckBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

try:
    from app.ui.dialogs.automation_dialog import AutomationDialog
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    print("Automation module not available")

class DbQueryDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("数据库查询")
        self.resize(1000, 700)
        
        self.layout = QVBoxLayout(self)
        
        # 1. 搜索条件区域
        search_group = QGroupBox("搜索条件")
        search_layout = QHBoxLayout(search_group)
        
        # 恢复分字段搜索
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("姓名")
        self.name_input.returnPressed.connect(self.perform_search)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("身份证号")
        self.id_input.returnPressed.connect(self.perform_search)
        
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("手机号")
        self.phone_input.returnPressed.connect(self.perform_search)
        
        # 有效期筛选：纯文本输入，格式为 yyyymmdd，可留空
        self.start_date_input = QLineEdit()
        self.start_date_input.setPlaceholderText("有效期起(yyyymmdd，可空)")
        self.start_date_input.returnPressed.connect(self.perform_search)
        
        self.end_date_input = QLineEdit()
        self.end_date_input.setPlaceholderText("有效期止(yyyymmdd，可空)")
        self.end_date_input.returnPressed.connect(self.perform_search)
        
        # 新增关键字搜索，匹配姓名/公司/等级/注册号/证书等所有文本
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("关键字（姓名/公司/等级/注册号/证书等）")
        self.keyword_input.returnPressed.connect(self.perform_search)
        
        self.search_btn = QPushButton("查询")
        self.search_btn.clicked.connect(self.perform_search)
        
        # 添加模糊匹配复选框
        self.fuzzy_checkbox = QCheckBox("模糊匹配")
        self.fuzzy_checkbox.setChecked(False) # 默认关闭，即精确匹配
        self.fuzzy_checkbox.stateChanged.connect(self.perform_search)
        
        # 添加编辑模式复选框
        self.edit_mode_checkbox = QCheckBox("编辑模式")
        self.edit_mode_checkbox.setChecked(False)
        self.edit_mode_checkbox.stateChanged.connect(self.toggle_edit_mode)

        search_layout.addWidget(QLabel("姓名:"))
        search_layout.addWidget(self.name_input)
        search_layout.addWidget(QLabel("身份证:"))
        search_layout.addWidget(self.id_input)
        search_layout.addWidget(QLabel("手机号:"))
        search_layout.addWidget(self.phone_input)
        search_layout.addWidget(QLabel("有效期:"))
        search_layout.addWidget(self.start_date_input)
        search_layout.addWidget(QLabel("至"))
        search_layout.addWidget(self.end_date_input)
        search_layout.addWidget(QLabel("关键字:"))
        search_layout.addWidget(self.keyword_input)
        search_layout.addWidget(self.fuzzy_checkbox)
        search_layout.addWidget(self.edit_mode_checkbox)
        search_layout.addWidget(self.search_btn)
        
        self.layout.addWidget(search_group)
        
        # 2. 结果展示区域
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels(["姓名", "职业", "身份证号", "手机号", "等级", "单位名称", "证书编号", "注册编号"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 改为单元格选择模式，方便复制具体内容
        self.result_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.result_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers) # 禁止编辑
        self.result_table.installEventFilter(self) # 安装事件过滤器以处理复制
        self.result_table.cellChanged.connect(self.on_cell_changed) # 连接单元格修改信号
        
        self.layout.addWidget(self.result_table)
        
        # 3. 底部操作区域
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        
        self.verify_btn = QPushButton("在线验证")
        self.verify_btn.clicked.connect(self.open_verification_dialog)
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.verify_btn)
        bottom_layout.addWidget(self.export_btn)
        
        self.layout.addLayout(bottom_layout)
        
        # 初始加载数据
        self.perform_search()

    def open_verification_dialog(self):
        """打开在线验证对话框"""
        if not AUTOMATION_AVAILABLE:
            QMessageBox.warning(self, "错误", "自动化模块未加载")
            return
            
        selected_items = self.result_table.selectedItems()
        id_cards = set()
        
        # 动态查找身份证号所在的列索引
        id_col_index = -1
        for i in range(self.result_table.columnCount()):
            header_item = self.result_table.horizontalHeaderItem(i)
            if header_item and header_item.text() == "身份证号":
                id_col_index = i
                break
        
        if id_col_index == -1:
            # Fallback to index 1 (based on current layout: Name, ID, Phone...)
            id_col_index = 1

        # 1. 优先使用选中的行
        if selected_items:
            # 获取选中的行号
            rows = set(item.row() for item in selected_items)
            for row in rows:
                id_item = self.result_table.item(row, id_col_index)
                if id_item and id_item.text().strip():
                    id_cards.add(id_item.text().strip())
        
        # 2. 如果没有选中，询问是否处理当前表格所有数据
        if not id_cards:
            count = self.result_table.rowCount()
            if count == 0:
                QMessageBox.information(self, "提示", "没有数据可验证")
                return
                
            reply = QMessageBox.question(self, "验证确认", 
                                       f"未选中任何行，是否验证当前列表显示的全部 {count} 条记录？",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                for row in range(count):
                    id_item = self.result_table.item(row, id_col_index)
                    if id_item and id_item.text().strip():
                        id_cards.add(id_item.text().strip())
            else:
                return

        if not id_cards:
            QMessageBox.warning(self, "提示", "未找到有效的身份证号")
            return
            
        dialog = AutomationDialog(list(id_cards), db_path=self.db_path, parent=self)
        dialog.exec_()
        
        # 自动刷新表格
        self.perform_search()

    def eventFilter(self, source, event):
        if (source == self.result_table and event.type() == event.KeyPress and 
            event.matches(QKeySequence.Copy)):
            self.copy_selection()
            return True
        return super().eventFilter(source, event)

    def toggle_edit_mode(self, state):
        """切换编辑模式"""
        if state == Qt.Checked:
            self.result_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
            self.status_label.setText("编辑模式已开启，双击单元格修改")
        else:
            self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.status_label.setText("编辑模式已关闭")

    def on_cell_changed(self, row, column):
        """处理单元格修改"""
        # 如果不是编辑模式，忽略（可能是代码加载数据触发的）
        if not self.edit_mode_checkbox.isChecked():
            return
            
        try:
            item = self.result_table.item(row, column)
            new_value = item.text().strip()
            
            rowid = item.data(Qt.UserRole)
            if not rowid:
                QMessageBox.warning(self, "警告", "无法获取记录ID，修改失败")
                return

            # Updated column mapping based on new layout
            # 0: Name, 1: ID, 2: Phone, 3: Level, 4: Company, 5: RegNum, 6: B-Status, 7: B-Issue, 8: B-Expiry
            fixed_cols = {
                0: "name",
                1: "id_card",
                2: "phone_number",
                3: "level",
                4: "company_name",
                5: "registration_number",
                6: "b_cert_status",
                7: "b_cert_issue_date",
                8: "b_cert_expiry_date"
            }
            
            if column in fixed_cols:
                field_name = fixed_cols[column]
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                sql = f"UPDATE person_info SET {field_name} = ? WHERE rowid = ?"
                cursor.execute(sql, (new_value, rowid))
                conn.commit()
                conn.close()
                self.status_label.setText(f"记录已更新: {field_name} -> {new_value}")
            else:
                # Dynamic columns (Certificates) editing is not yet supported via this simple view
                self.status_label.setText("提示: 暂不支持直接编辑证书详情列，请通过重新导入或自动化更新")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "更新错误", str(e))

    def copy_selection(self):
        selection = self.result_table.selectedItems()
        if not selection:
            return
            
        # 按行号和列号排序
        selection.sort(key=lambda x: (x.row(), x.column()))
        
        # 提取文本并用空格连接
        text = " ".join([item.text() for item in selection])
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def perform_search(self):
        """执行数据库查询 (支持高级匹配和排序)"""
        name_query = self.name_input.text().strip()
        id_query = self.id_input.text().strip()
        phone_query = self.phone_input.text().strip()
        start_date_str = self.start_date_input.text().strip()
        end_date_str = self.end_date_input.text().strip()
        
        start_date = self._parse_user_date(start_date_str) if start_date_str else None
        end_date = self._parse_user_date(end_date_str) if end_date_str else None
        keyword_query = self.keyword_input.text().strip()
        
        if not os.path.exists(self.db_path):
            QMessageBox.warning(self, "错误", "数据库文件不存在")
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 获取所有数据 (分两步获取并合并)
            # Step A: 获取主表数据
            # 0:rowid, 1:name, 2:profession(legacy), 3:id_card, 4:phone, 
            # 5:level(legacy), 6:company, 7:reg_num(legacy)
            try:
                sql_main = """
                    SELECT rowid,
                           name,
                           profession,
                           id_card,
                           phone_number,
                           level,
                           company_name,
                           registration_number,
                           b_cert_status,
                           b_cert_issue_date,
                           b_cert_expiry_date,
                           result_count,
                           verification_time
                    FROM person_info
                """
                cursor.execute(sql_main)
                person_rows = cursor.fetchall()
            except Exception as e:
                try:
                    sql_main = """
                        SELECT rowid, name, profession, id_card, phone_number, level, company_name, registration_number
                        FROM person_info
                    """
                    cursor.execute(sql_main)
                    person_rows = cursor.fetchall()
                except:
                    sql_main = "SELECT rowid, name, profession, id_card, phone_number FROM person_info"
                    cursor.execute(sql_main)
                    person_rows = cursor.fetchall()

            # Step B: 获取证书子表数据
            cert_map = {} # id_card -> list of cert dicts
            try:
                sql_cert = """
                    SELECT person_id_card, profession, expiry_date, level, registration_number 
                    FROM certificates
                """
                cursor.execute(sql_cert)
                cert_rows = cursor.fetchall()
                
                for c_row in cert_rows:
                    pid, prof, expiry, lvl, reg = c_row
                    if pid not in cert_map:
                        cert_map[pid] = []
                    cert_map[pid].append({
                        'profession': prof, 
                        'expiry': expiry, 
                        'level': lvl, 
                        'reg_number': reg
                    })
            except:
                # 证书表可能不存在
                pass

            conn.close()
            
            # 2. 合并数据 (One person per row)
            merged_data = []
            for p_row in person_rows:
                # Parse person info
                rowid = p_row[0]
                name = p_row[1]
                p_prof = p_row[2]
                id_card = p_row[3]
                phone = p_row[4]
                
                # Extended fields if available
                p_level = p_row[5] if len(p_row) > 5 else ""
                company = p_row[6] if len(p_row) > 6 else ""
                p_reg = p_row[7] if len(p_row) > 7 else ""
                
                raw_b_status = p_row[8] if len(p_row) > 8 else ""
                raw_b_issue = p_row[9] if len(p_row) > 9 else ""
                raw_b_expiry = p_row[10] if len(p_row) > 10 else ""
                result_count = p_row[11] if len(p_row) > 11 else 0
                verification_time = p_row[12] if len(p_row) > 12 else ""
                
                b_status = raw_b_status
                b_issue = self._normalize_date_string(raw_b_issue)
                b_expiry = self._normalize_date_string(raw_b_expiry)
                v_time = self._normalize_date_string(verification_time) if verification_time else ""
                
                # Get certs for this person
                certs = cert_map.get(id_card, [])
                
                # Construct display data
                # Fixed columns: Name, ID, Phone, Company, Level, RegNum
                # Dynamic columns: Prof1, Exp1, Prof2, Exp2...
                
                # Determine display Level and RegNum
                # Strategy: Use certs if available, else legacy person_info fields
                # Join unique values if multiple certs have different levels/regs
                
                display_levels = set()
                display_regs = set()
                
                if p_level: display_levels.add(p_level)
                if p_reg: display_regs.add(p_reg)
                
                for c in certs:
                    if c['level']: display_levels.add(c['level'])
                    if c['reg_number']: display_regs.add(c['reg_number'])
                    
                final_level = ", ".join(sorted(list(display_levels)))
                final_reg = ", ".join(sorted(list(display_regs)))
                
                # Construct Cert Pairs
                # If no certs in subtable, use legacy profession (no expiry)
                cert_pairs = []
                if certs:
                    for c in certs:
                        cert_pairs.append((c['profession'], self._normalize_date_string(c['expiry'])))
                elif p_prof:
                    cert_pairs.append((p_prof, ""))
                    
                # Create merged object for scoring and display
                # We store cert_pairs in a special way to be expanded later
                merged_entry = {
                    'rowid': rowid,
                    'name': name,
                    'id_card': id_card,
                    'phone': phone,
                    'company': company,
                    'level': final_level,
                    'reg_num': final_reg,
                    'b_status': b_status,
                    'b_issue': b_issue,
                    'b_expiry': b_expiry,
                    'result_count': result_count if result_count is not None else 0,
                    'verification_time': v_time,
                    'cert_pairs': cert_pairs,
                    'search_text': f"{name} {id_card} {phone} {company} {final_level} {final_reg} {b_status} {' '.join([f'{p} {e}' for p, e in cert_pairs])}"
                }
                merged_data.append(merged_entry)

            # 3. 过滤和评分
            scored_results = []
            
            for entry in merged_data:
                total_score = 0
                match_name = True
                match_id = True
                match_phone = True
                match_date = True
                match_keyword = True
                
                if name_query:
                    score, _ = self._calculate_match_score(entry['name'], name_query)
                    if score == 0:
                        match_name = False
                    else:
                        total_score += score
                        
                if id_query:
                    score, _ = self._calculate_match_score(entry['id_card'], id_query)
                    if score == 0:
                        match_id = False
                    else:
                        total_score += score
                        
                if phone_query:
                    score, _ = self._calculate_match_score(entry['phone'], phone_query)
                    if score == 0:
                        match_phone = False
                    else:
                        total_score += score
                        
                # 关键字在合并后的 search_text 上匹配，覆盖公司/等级/注册号/证书等字段
                if keyword_query:
                    score, _ = self._calculate_match_score(entry['search_text'], keyword_query)
                    if score == 0:
                        match_keyword = False
                    else:
                        total_score += score
                
                if start_date or end_date:
                    candidate_dates = []
                    
                    exp_b = self._parse_date(entry.get('b_expiry'))
                    if exp_b:
                        candidate_dates.append(exp_b)
                    
                    for _, cert_exp in entry.get('cert_pairs', []):
                        d = self._parse_date(cert_exp)
                        if d:
                            candidate_dates.append(d)
                    
                    if not candidate_dates:
                        match_date = False
                    else:
                        in_range = False
                        for d in candidate_dates:
                            if start_date and d < start_date:
                                continue
                            if end_date and d > end_date:
                                continue
                            in_range = True
                            break
                        match_date = in_range
                
                if match_name and match_id and match_phone and match_keyword and match_date:
                    scored_results.append({
                        'data': entry,
                        'score': total_score
                    })
            
            scored_results.sort(
                key=lambda x: (
                    x['data'].get('result_count') if x['data'].get('result_count') is not None else 0,
                    x['score']
                ),
                reverse=True
            )
            
            # 5. 更新表格
            final_data = [item['data'] for item in scored_results]
            self._update_table_merged(final_data)
            self.status_label.setText(f"找到 {len(scored_results)} 条匹配记录")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "查询错误", str(e))
            
    def _update_table_merged(self, data):
        """更新表格显示 (合并模式：一行一人，动态扩展证书列)"""
        # 1. 计算最大证书数量以确定列数
        max_certs = 0
        for entry in data:
            max_certs = max(max_certs, len(entry['cert_pairs']))
            
        headers = ["姓名", "身份证号", "手机号", "等级", "单位名称", "注册编号", "B证状态", "发证日期", "有效期结束", "结果数", "验证日期"]
        # 动态列
        for i in range(max_certs):
            headers.append(f"职业{i+1}")
            headers.append(f"有效期{i+1}")
            
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        
        self.result_table.setRowCount(0)
        self.result_table.blockSignals(True)
        
        display_limit = 500
        for row_idx, entry in enumerate(data[:display_limit]):
            self.result_table.insertRow(row_idx)
            
            fixed_values = [
                entry['name'],
                entry['id_card'],
                entry['phone'],
                entry['level'],
                entry['company'],
                entry['reg_num'],
                entry.get('b_status', ''),
                entry.get('b_issue', ''),
                entry.get('b_expiry', ''),
                entry.get('result_count', ''),
                entry.get('verification_time', '')
            ]
            
            col_cursor = 0
            # 填充固定列
            for val in fixed_values:
                item = QTableWidgetItem(str(val) if val is not None else "")
                if col_cursor == 0:
                     item.setData(Qt.UserRole, entry['rowid'])
                self.result_table.setItem(row_idx, col_cursor, item)
                col_cursor += 1
                
            # 填充动态证书列
            for prof, expiry in entry['cert_pairs']:
                # Profession
                self.result_table.setItem(row_idx, col_cursor, QTableWidgetItem(str(prof) if prof else ""))
                col_cursor += 1
                # Expiry
                self.result_table.setItem(row_idx, col_cursor, QTableWidgetItem(str(expiry) if expiry else ""))
                col_cursor += 1
                
        self.result_table.blockSignals(False)
        if len(data) > display_limit:
            self.status_label.setText(f"显示前 {display_limit} 条记录 (共 {len(data)} 条)")
    
    def _parse_date(self, s):
        if not s:
            return None
        text = str(s).strip()
        if not text:
            return None
        text = text.replace("年", "-").replace("月", "-").replace("日", "")
        text = text.replace("/", "-").replace(".", "-")
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except Exception:
            return None
    
    def _normalize_date_string(self, s):
        d = self._parse_date(s)
        if not d:
            return s
        return d.strftime("%Y-%m-%d")
    
    def _parse_user_date(self, s):
        if not s:
            return None
        text = str(s).strip()
        if not text:
            return None
        # 用户输入期望为 yyyymmdd，但容错允许带分隔符
        digits = re.sub(r'\D', '', text)
        if len(digits) == 8:
            try:
                return datetime.strptime(digits, "%Y%m%d").date()
            except Exception:
                pass
        # 回退到通用解析（支持 2028-01-22、2028年01月22日 等）
        return self._parse_date(s)

    def _calculate_match_score(self, text, keyword):
        """
        计算文本与关键词的匹配分数和匹配范围
        返回: (score, list_of_ranges)
        ranges = [(start, end), ...] 左闭右开
        """
        if not text or not keyword:
            return 0, []
            
        text_lower = text.lower()
        kw_lower = keyword.lower()
        
        # 1. 精确匹配 (始终优先)
        if text_lower == kw_lower:
            return 100, [(0, len(text))]
        
        # 如果未开启模糊匹配，且不是精确匹配，则返回0分
        if not self.fuzzy_checkbox.isChecked():
            return 0, []
            
        # 2. 包含匹配 (连续)
        if kw_lower in text_lower:
            start = text_lower.find(kw_lower)
            return 80, [(start, start + len(keyword))]
            
        # 3. 间隔匹配 (顺序字符匹配)
        matches = []
        current_pos = 0
        matched_indices = []
        
        for char in kw_lower:
            pos = text_lower.find(char, current_pos)
            if pos == -1:
                return 0, []
            matched_indices.append(pos)
            current_pos = pos + 1
            
        # 计算间隔匹配的分数
        span = matched_indices[-1] - matched_indices[0] + 1
        compactness = len(keyword) / span
        score = 40 + (compactness * 20)
        
        ranges = [(i, i+1) for i in matched_indices]
        return score, ranges

    def _update_table(self, data):
        """普通更新表格"""
        self.result_table.blockSignals(True) # 暂时阻止信号，防止在填充时触发cellChanged
        self.result_table.setRowCount(0)
        display_limit = 500
        for row_idx, row_data in enumerate(data[:display_limit]):
            self.result_table.insertRow(row_idx)
            
            # row_data 长度可能不同，取决于数据库结构版本
            row_id = row_data[0]
            display_data = list(row_data[1:])
            
            # 如果是旧数据结构 (只有5列: id, name, prof, id_card, phone)，补齐剩余列
            # 目标是8列展示: 姓名, 职业, 身份证号, 手机号, 等级, 单位, 证书编号, 注册编号
            # 当前 display_data 已包含前4项
            
            current_cols = len(display_data)
            target_cols = 8
            
            if current_cols < target_cols:
                display_data.extend([""] * (target_cols - current_cols))
            
            for col_idx, item_text in enumerate(display_data):
                item = QTableWidgetItem(str(item_text) if item_text is not None else "")
                # 将数据库ID存储在item的data中，用于后续修改定位
                item.setData(Qt.UserRole, row_id)
                self.result_table.setItem(row_idx, col_idx, item)
                # 确保清理之前的CellWidget
                self.result_table.removeCellWidget(row_idx, col_idx)
        
        self.result_table.blockSignals(False) # 恢复信号
        
        if len(data) > display_limit:
            self.status_label.setText(f"显示前 {display_limit} 条记录 (共 {len(data)} 条)")

    def export_results(self):
        """导出当前结果到Excel"""
        if self.result_table.rowCount() == 0:
            QMessageBox.information(self, "提示", "没有数据可导出")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "Excel Files (*.xlsx)")
        if not save_path:
            return
            
        try:
            # 收集数据
            headers = [self.result_table.horizontalHeaderItem(i).text() for i in range(self.result_table.columnCount())]
            data = []
            
            for row in range(self.result_table.rowCount()):
                row_data = []
                for col in range(self.result_table.columnCount()):
                    item = self.result_table.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            # 使用pandas导出
            df = pd.DataFrame(data, columns=headers)
            df.to_excel(save_path, index=False)
                    
            QMessageBox.information(self, "成功", "导出成功")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "导出错误", str(e))
