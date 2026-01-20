# -*- coding: utf-8 -*-

import sqlite3
import os
import re
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog, QGroupBox, QWidget, QApplication, QCheckBox, QSpinBox, QComboBox)
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
        # 移除标题栏上的问号按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(1000, 700)
        
        self.layout = QVBoxLayout(self)
        
        # 1. 搜索条件区域
        search_group = QGroupBox("搜索条件")
        search_main_layout = QVBoxLayout(search_group)
        
        row1_layout = QHBoxLayout()
        row2_layout = QHBoxLayout()
        
        # 恢复分字段搜索
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("姓名")
        self.name_input.returnPressed.connect(self.perform_search)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("身份证号")
        self.id_input.returnPressed.connect(self.perform_search)
        
        # B证状态筛选 (下拉框)
        self.b_status_combo = QComboBox()
        self.b_status_combo.addItem("全部")
        self.b_status_combo.currentIndexChanged.connect(self.perform_search)
        
        # 有效期筛选：年/月/日 下拉框
        self.year_combo = QComboBox()
        self.year_combo.addItem("年份")
        self.year_combo.currentIndexChanged.connect(self.perform_search)
        
        self.month_combo = QComboBox()
        self.month_combo.addItem("月份")
        for i in range(1, 13):
            self.month_combo.addItem(f"{i:02d}")
        self.month_combo.currentIndexChanged.connect(self.perform_search)
        
        self.day_combo = QComboBox()
        self.day_combo.addItem("日期")
        for i in range(1, 32):
            self.day_combo.addItem(f"{i:02d}")
        self.day_combo.currentIndexChanged.connect(self.perform_search)
        
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

        # 验证区间筛选
        self.verification_filter_cb = QCheckBox("验证区间筛选")
        self.verification_filter_cb.setChecked(False)
        self.verification_filter_cb.stateChanged.connect(self.perform_search)
        
        self.min_days_spin = QSpinBox()
        self.min_days_spin.setRange(0, 9999)
        self.min_days_spin.setValue(0)
        self.min_days_spin.setSuffix(" 天")
        self.min_days_spin.valueChanged.connect(self.perform_search)
        
        self.max_days_spin = QSpinBox()
        self.max_days_spin.setRange(0, 9999)
        self.max_days_spin.setValue(30)
        self.max_days_spin.setSuffix(" 天")
        self.max_days_spin.valueChanged.connect(self.perform_search)

        row1_layout.addWidget(QLabel("姓名:"))
        row1_layout.addWidget(self.name_input)
        row1_layout.addWidget(QLabel("身份证:"))
        row1_layout.addWidget(self.id_input)
        row1_layout.addWidget(QLabel("B证状态:"))
        row1_layout.addWidget(self.b_status_combo)
        row1_layout.addWidget(QLabel("有效期:"))
        row1_layout.addWidget(self.year_combo)
        row1_layout.addWidget(QLabel("年"))
        row1_layout.addWidget(self.month_combo)
        row1_layout.addWidget(QLabel("月"))
        row1_layout.addWidget(self.day_combo)
        row1_layout.addWidget(QLabel("日"))
        
        row2_layout.addWidget(QLabel("关键字:"))
        row2_layout.addWidget(self.keyword_input)
        
        # Add Verification Filter widgets
        row2_layout.addWidget(self.verification_filter_cb)
        row2_layout.addWidget(QLabel("最小:"))
        row2_layout.addWidget(self.min_days_spin)
        row2_layout.addWidget(QLabel("最大:"))
        row2_layout.addWidget(self.max_days_spin)
        
        row2_layout.addWidget(self.fuzzy_checkbox)
        row2_layout.addWidget(self.edit_mode_checkbox)
        row2_layout.addWidget(self.search_btn)
        
        search_main_layout.addLayout(row1_layout)
        search_main_layout.addLayout(row2_layout)
        
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
        self._load_b_status_options()
        self._load_year_options()
        self.perform_search()

    def _load_year_options(self):
        """加载年份选项"""
        columns = self._get_db_columns()
        years = set()
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 从 person_info 中获取年份
            if 'b_cert_expiry_date' in columns:
                cursor.execute("SELECT b_cert_expiry_date FROM person_info WHERE b_cert_expiry_date IS NOT NULL")
                for row in cursor.fetchall():
                    d = self._parse_date(row[0])
                    if d:
                        years.add(d.year)
            
            # 从 certificates 中获取年份
            try:
                cursor.execute("SELECT expiry_date FROM certificates WHERE expiry_date IS NOT NULL")
                for row in cursor.fetchall():
                    d = self._parse_date(row[0])
                    if d:
                        years.add(d.year)
            except:
                pass
                
            conn.close()
            
            if years:
                sorted_years = sorted(list(years))
                self.year_combo.blockSignals(True)
                self.year_combo.clear()
                self.year_combo.addItem("年份")
                for y in sorted_years:
                    self.year_combo.addItem(str(y))
                self.year_combo.blockSignals(False)
                
        except Exception as e:
            print(f"Failed to load years: {e}")


    def _get_db_columns(self):
        if hasattr(self, 'db_columns') and self.db_columns:
            return self.db_columns
        
        if not os.path.exists(self.db_path):
            return []
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(person_info)")
            columns = [info[1] for info in cursor.fetchall()]
            conn.close()
            self.db_columns = columns
            return columns
        except:
            return []

    def _load_b_status_options(self):
        """加载B证状态选项"""
        columns = self._get_db_columns()
        
        if 'b_cert_status' in columns:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT b_cert_status FROM person_info WHERE b_cert_status IS NOT NULL AND b_cert_status != ''")
                rows = cursor.fetchall()
                options = sorted([row[0] for row in rows])
                
                self.b_status_combo.blockSignals(True)
                self.b_status_combo.clear()
                self.b_status_combo.addItem("全部")
                self.b_status_combo.addItems(options)
                self.b_status_combo.blockSignals(False)
                conn.close()
            except Exception as e:
                print(f"Failed to load B status options: {e}")

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
        b_status_query = self.b_status_combo.currentText()
        if b_status_query == "全部":
            b_status_query = ""
            
        # 构造日期筛选区间
        start_date = None
        end_date = None
        
        sel_year = self.year_combo.currentText()
        sel_month = self.month_combo.currentText()
        sel_day = self.day_combo.currentText()
        
        # 必须选择年份才生效，或者如果用户只选了月份/日期但没选年份，逻辑上无法确定区间，这里假设必须选年份
        # 如果 "年份" 没选，则忽略日期筛选
        if sel_year != "年份":
            try:
                y = int(sel_year)
                
                if sel_month != "月份":
                    m = int(sel_month)
                    
                    if sel_day != "日期":
                        # 精确到日
                        d = int(sel_day)
                        try:
                            start_date = datetime(y, m, d).date()
                            end_date = datetime(y, m, d).date()
                        except ValueError:
                            # 日期无效（如2月30日），则忽略筛选或提示
                            pass
                    else:
                        # 指定年月，闭区间 [yyyy-mm-01, yyyy-mm-last_day]
                        import calendar
                        _, last_day = calendar.monthrange(y, m)
                        start_date = datetime(y, m, 1).date()
                        end_date = datetime(y, m, last_day).date()
                else:
                    # 只指定年，闭区间 [yyyy-01-01, yyyy-12-31]
                    start_date = datetime(y, 1, 1).date()
                    end_date = datetime(y, 12, 31).date()
            except:
                pass

        keyword_query = self.keyword_input.text().strip()
        
        if not os.path.exists(self.db_path):
            QMessageBox.warning(self, "错误", "数据库文件不存在")
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. 获取所有数据 (动态构建查询，适配不同版本的数据库结构)
            columns = self._get_db_columns()
            
            # 基础字段
            query_cols = ["rowid"]
            
            # 可能存在的字段
            possible_fields = [
                'name', 'profession', 'id_card', 'phone_number', 
                'level', 'company_name', 'registration_number',
                'b_cert_status', 'b_cert_issue_date', 'b_cert_expiry_date',
                'result_count', 'verification_time'
            ]
            
            for field in possible_fields:
                if field in columns:
                    query_cols.append(field)
            
            sql_main = f"SELECT {', '.join(query_cols)} FROM person_info"
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
                    # 使用列名访问，更安全
                    try:
                        pid = c_row['person_id_card']
                        prof = c_row['profession']
                        expiry = c_row['expiry_date']
                        lvl = c_row['level']
                        reg = c_row['registration_number']
                        
                        if pid not in cert_map:
                            cert_map[pid] = []
                        cert_map[pid].append({
                            'profession': prof, 
                            'expiry': expiry, 
                            'level': lvl, 
                            'reg_number': reg
                        })
                    except (IndexError, KeyError) as e:
                        print(f"Error processing certificate row: {e}")
                        continue
            except Exception as e:
                # 证书表可能不存在或查询出错
                print(f"Failed to load certificates: {e}")
                pass

            conn.close()
            
            # 2. 合并数据 (One person per row)
            merged_data = []
            for p_row in person_rows:
                # Helper to safely get field
                def get_val(key, default=""):
                    try:
                        val = p_row[key]
                        return val if val is not None else default
                    except (IndexError, KeyError):
                        return default
                
                rowid = p_row['rowid']
                name = get_val('name')
                p_prof = get_val('profession')
                id_card = get_val('id_card')
                phone = get_val('phone_number')
                
                p_level = get_val('level')
                company = get_val('company_name')
                p_reg = get_val('registration_number')
                
                raw_b_status = get_val('b_cert_status')
                raw_b_issue = get_val('b_cert_issue_date')
                raw_b_expiry = get_val('b_cert_expiry_date')
                
                res_cnt_val = p_row['result_count'] if 'result_count' in p_row.keys() else 0
                result_count = res_cnt_val if res_cnt_val is not None else 0
                
                verification_time = get_val('verification_time')
                
                b_status = raw_b_status if raw_b_status else ""
                b_issue = self._normalize_date_string(raw_b_issue)
                b_expiry = self._normalize_date_string(raw_b_expiry)
                v_time = self._normalize_date_string(verification_time) if verification_time else ""
                
                # Get certs for this person
                certs = cert_map.get(id_card, [])
                
                display_levels = set()
                display_regs = set()
                
                if p_level: display_levels.add(p_level)
                if p_reg: display_regs.add(p_reg)
                
                for c in certs:
                    if c['level']: display_levels.add(c['level'])
                    if c['reg_number']: display_regs.add(c['reg_number'])
                    
                final_level = ", ".join(sorted(list(display_levels)))
                final_reg = ", ".join(sorted(list(display_regs)))
                
                cert_pairs = []
                if certs:
                    for c in certs:
                        cert_pairs.append((c['profession'], self._normalize_date_string(c['expiry'])))
                elif p_prof:
                    cert_pairs.append((p_prof, ""))
                    
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
                    'result_count': result_count,
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
                match_b_status = True
                match_date = True
                match_keyword = True
                match_verification_interval = True
                
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
                        
                if b_status_query:
                    # 精确匹配 B证状态
                    if entry.get('b_status') != b_status_query:
                        match_b_status = False
                    # B证状态匹配不加分，或者是必须条件
                        
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
                
                if self.verification_filter_cb.isChecked():
                    v_time_str = entry.get('verification_time')
                    if not v_time_str:
                        match_verification_interval = False
                    else:
                        try:
                            v_date = datetime.strptime(v_time_str, "%Y-%m-%d").date()
                            today = datetime.now().date()
                            delta_days = (today - v_date).days
                            
                            min_days = self.min_days_spin.value()
                            max_days = self.max_days_spin.value()
                            
                            if not (min_days <= delta_days <= max_days):
                                match_verification_interval = False
                        except Exception:
                            match_verification_interval = False

                if match_name and match_id and match_b_status and match_keyword and match_date and match_verification_interval:
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
            # 尝试纯数字格式 20250101
            if len(text) == 8 and text.isdigit():
                try:
                    return datetime.strptime(text, "%Y%m%d").date()
                except:
                    pass
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
