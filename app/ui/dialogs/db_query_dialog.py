# -*- coding: utf-8 -*-

import sqlite3
import os
import re
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog, QGroupBox, QWidget, 
                             QApplication, QCheckBox, QComboBox, QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

try:
    from app.ui.dialogs.automation_dialog import AutomationDialog
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    print("Automation module not available")

from app.ui.dialogs.dictionary_manager_dialog import DictionaryManagerDialog

class DbQueryDialog(QDialog):
    # 默认映射 (作为兜底)
    DEFAULT_FIELD_MAPPING = {
        'name': '姓名',
        'profession': '职业',
        'id_card': '身份证号',
        'phone_number': '手机号',
        'phone': '手机号',
        'company_name': '单位名称',
        'certificates_json': '证书JSON',
        'level': '等级',
        'registration_number': '注册编号',
        'b_cert_status': 'B证状态',
        'b_cert_issue_date': 'B证发证日期',
        'b_cert_expiry_date': 'B证有效期',
        'result_count': '结果数',
        'verification_time': '验证时间',
        'expiry_date': '有效期',
        'person_id_card': '关联身份证',
        'rowid': '系统ID',
        'id': '编号',
        'gender': '性别',
        'nation': '民族',
        'birthday': '出生日期',
        'address': '地址',
        'authority': '签发机关',
        'valid_period': '有效期限',
        'issue_date': '发证日期',
        'category': '类别',
        'timestamp': '时间戳',
        'created_at': '创建时间',
        'updated_at': '更新时间'
    }

    DEFAULT_TABLE_MAPPING = {
        'person_info': '人员信息',
        'certificates': '证书列表',
        'ocr_records': '识别记录',
        'sqlite_sequence': '序列',
        'users': '用户',
        'config': '配置'
    }

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        
        # 运行时映射字典
        self.field_mapping = self.DEFAULT_FIELD_MAPPING.copy()
        self.table_mapping = self.DEFAULT_TABLE_MAPPING.copy()
        
        self.setWindowTitle("数据库查询")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(1200, 800)
        
        self._load_custom_mappings()
        
        self.layout = QVBoxLayout(self)
        self.search_inputs = {} # 存储动态生成的搜索输入框 {col_name: widget}
        self.current_columns = [] # 当前表的列名列表
        
        # 1. 顶部控制区
        top_group = QGroupBox("查询控制")
        top_layout = QVBoxLayout(top_group)
        
        # 表选择行
        table_select_layout = QHBoxLayout()
        table_select_layout.addWidget(QLabel("选择数据表:"))
        self.table_selector = QComboBox()
        self.table_selector.currentIndexChanged.connect(self.load_table_schema)
        table_select_layout.addWidget(self.table_selector)
        
        # 字典管理按钮
        self.dict_btn = QPushButton("字典管理")
        self.dict_btn.setFixedWidth(100)
        self.dict_btn.clicked.connect(self.open_dict_manager)
        table_select_layout.addWidget(self.dict_btn)
        
        table_select_layout.addStretch()
        top_layout.addLayout(table_select_layout)
        
        # 动态搜索条件区域 (使用ScrollArea以适应多字段)
        self.search_scroll = QScrollArea()
        self.search_scroll.setWidgetResizable(True)
        self.search_scroll.setMaximumHeight(200) # 限制高度
        self.search_widget = QWidget()
        self.search_grid = QGridLayout(self.search_widget)
        self.search_scroll.setWidget(self.search_widget)
        top_layout.addWidget(self.search_scroll)
        
        # 操作按钮行
        action_layout = QHBoxLayout()
        
        self.fuzzy_checkbox = QCheckBox("模糊匹配 (Python高级评分)")
        self.fuzzy_checkbox.setToolTip("选中后使用Python算法进行相似度评分和排序，否则使用SQL精确匹配(LIKE)")
        self.fuzzy_checkbox.setChecked(False)
        self.fuzzy_checkbox.stateChanged.connect(self.perform_search)
        
        self.edit_mode_checkbox = QCheckBox("编辑模式")
        self.edit_mode_checkbox.setChecked(False)
        self.edit_mode_checkbox.stateChanged.connect(self.toggle_edit_mode)
        
        self.search_btn = QPushButton("查询")
        self.search_btn.clicked.connect(self.perform_search)
        
        action_layout.addWidget(self.fuzzy_checkbox)
        action_layout.addWidget(self.edit_mode_checkbox)
        action_layout.addStretch()
        action_layout.addWidget(self.search_btn)
        top_layout.addLayout(action_layout)
        
        self.layout.addWidget(top_group)
        
        # 2. 结果展示区域
        self.result_table = QTableWidget()
        self.result_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.result_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.installEventFilter(self)
        self.result_table.cellChanged.connect(self.on_cell_changed)
        
        self.layout.addWidget(self.result_table)
        
        # 3. 底部操作区域
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        
        # 仅当表包含身份证列时才启用的按钮
        self.verify_btn = QPushButton("在线验证 (仅person_info)")
        self.verify_btn.clicked.connect(self.open_verification_dialog)
        self.verify_btn.setEnabled(False)
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.verify_btn)
        bottom_layout.addWidget(self.export_btn)
        
        self.layout.addLayout(bottom_layout)
        
        # 初始化
        self.table_relations = {} # parent -> [{child, child_col, parent_col}]
        self.column_metadata = [] # list of {name, table, origin_col, type, is_pk}
        self.load_tables()

    def _load_custom_mappings(self):
        """从数据库加载自定义字典"""
        if not os.path.exists(self.db_path): return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_sys_meta_dict'")
            if cursor.fetchone():
                cursor.execute("SELECT type, key, value FROM _sys_meta_dict")
                rows = cursor.fetchall()
                for r_type, key, val in rows:
                    if r_type == 'field':
                        self.field_mapping[key] = val
                    elif r_type == 'table':
                        self.table_mapping[key] = val
            conn.close()
        except Exception as e:
            print(f"Error loading dictionary: {e}")

    def open_dict_manager(self):
        """打开字典管理器"""
        dialog = DictionaryManagerDialog(self.db_path, 
                                         self.DEFAULT_FIELD_MAPPING,
                                         self.DEFAULT_TABLE_MAPPING,
                                         self)
        dialog.exec_()
        # 关闭后重新加载映射并刷新界面
        self.field_mapping = self.DEFAULT_FIELD_MAPPING.copy()
        self.table_mapping = self.DEFAULT_TABLE_MAPPING.copy()
        self._load_custom_mappings()
        self.load_tables() # 刷新表列表
        self.load_table_schema() # 刷新字段列表

    def _analyze_db_structure(self):
        """分析数据库表结构，识别主子表关系"""
        self.table_relations = {}
        if not os.path.exists(self.db_path):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for child_table in tables:
                # 检查外键
                cursor.execute(f"PRAGMA foreign_key_list({child_table})")
                # (id, seq, table, from, to, on_update, on_delete, match)
                fks = cursor.fetchall()
                for fk in fks:
                    parent_table = fk[2]
                    child_col = fk[3]
                    parent_col = fk[4]
                    
                    if parent_table not in self.table_relations:
                        self.table_relations[parent_table] = []
                    
                    self.table_relations[parent_table].append({
                        'child_table': child_table,
                        'child_col': child_col,
                        'parent_col': parent_col
                    })
            conn.close()
        except Exception as e:
            print(f"Error analyzing DB structure: {e}")

    def load_tables(self):
        """加载所有表名"""
        if not os.path.exists(self.db_path):
            QMessageBox.warning(self, "错误", "数据库文件不存在")
            return
            
        try:
            self._analyze_db_structure()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            self.table_selector.blockSignals(True)
            self.table_selector.clear()
            
            # 标记主表 (含有子表的表)
            display_items = []
            for t in tables:
                if t in self.table_relations:
                    display_items.append(f"{t} [主表]")
                else:
                    display_items.append(t)
            
            self.table_selector.addItems(tables) # 存储真实表名作为 data? QComboBox itemData is better but simpler to just use text for now
            # 为了简单，还是显示原始表名，但在逻辑里处理
            # 或者我们可以自定义显示文本
            
            self.table_selector.clear()
            for t in tables:
                # 使用中文表名 + 原始表名
                t_cn = self.table_mapping.get(t, t)
                label = f"{t_cn} ({t})"
                
                if t in self.table_relations:
                    label = f"{label} [主表 +{len(self.table_relations[t])}子表]"
                
                self.table_selector.addItem(label, t) # user_data = real table name

            self.table_selector.blockSignals(False)
            
            # 默认选中 person_info
            index = self.table_selector.findData("person_info")
            if index >= 0:
                self.table_selector.setCurrentIndex(index)
            elif self.table_selector.count() > 0:
                self.table_selector.setCurrentIndex(0)
            
            self.load_table_schema()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载表列表失败: {e}")

    def load_table_schema(self):
        """根据选择的表加载字段并生成搜索框 (支持主子表合并)"""
        table_name = self.table_selector.currentData()
        if not table_name:
            return
            
        # 清空旧搜索框
        for i in reversed(range(self.search_grid.count())): 
            self.search_grid.itemAt(i).widget().setParent(None)
        self.search_inputs = {}
        self.column_metadata = [] # 重置列元数据
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 获取主表字段
            cursor.execute(f"PRAGMA table_info({table_name})")
            # (cid, name, type, notnull, dflt_value, pk)
            main_cols = cursor.fetchall()
            
            for col in main_cols:
                origin_name = col[1]
                display_name = self.field_mapping.get(origin_name, origin_name)
                
                # 如果没有映射，尝试简单的格式化
                if display_name == origin_name:
                    display_name = display_name.replace('_', ' ').title()
                
                self.column_metadata.append({
                    'name': origin_name,
                    'table': table_name,
                    'origin_col': origin_name,
                    'type': col[2],
                    'is_pk': col[5] > 0,
                    'display_name': display_name
                })
                
            # 2. 获取子表字段 (如果存在)
            children = self.table_relations.get(table_name, [])
            for child in children:
                child_name = child['child_table']
                cursor.execute(f"PRAGMA table_info({child_name})")
                child_cols = cursor.fetchall()
                
                for col in child_cols:
                    # 避免重复显示外键列 (可选，这里先全部显示，加上前缀区分)
                    # 只有当列名冲突时才加前缀，或者总是加前缀？
                    # 为了用户体验，如果有冲突，加表名前缀
                    
                    origin_col = col[1]
                    display_col = origin_col
                    
                    # 检查是否与主表字段重名
                    if any(c['name'] == origin_col for c in self.column_metadata):
                        display_col = f"{child_name}.{origin_col}"
                        
                    # 字段名映射也要尝试匹配
                    mapped_name = self.field_mapping.get(origin_col, display_col)
                    
                    # 获取表中文名
                    child_name_cn = self.table_mapping.get(child_name, child_name)
                    
                    if mapped_name == display_col and "." in display_col:
                         # 如果没有直接映射，尝试组合映射
                         base_map = self.field_mapping.get(origin_col, origin_col)
                         # 如果 base_map 依然是英文，尝试格式化一下
                         if base_map == origin_col:
                             base_map = base_map.replace('_', ' ').title()
                             
                         mapped_name = f"{base_map} ({child_name_cn})"
                    elif mapped_name != display_col:
                        # 如果有映射，但也需要区分来源
                        mapped_name = f"{mapped_name} ({child_name_cn})"
                    else:
                        # 既没有映射，也没有重名 (origin_col == mapped_name)
                        # 但如果是子表字段，可能还是想区分一下？或者不需要
                        # 如果是未映射的英文名，格式化一下
                        if mapped_name == origin_col:
                            mapped_name = mapped_name.replace('_', ' ').title()

                    self.column_metadata.append({
                        'name': display_col, # 唯一标识名 (用于搜索inputs key)
                        'table': child_name,
                        'origin_col': origin_col,
                        'type': col[2],
                        'is_pk': col[5] > 0,
                        'display_name': mapped_name
                    })

            conn.close()
            
            # 3. 生成搜索框
            cols_per_row = 4
            for idx, meta in enumerate(self.column_metadata):
                display_name = meta['display_name']
                col_key = meta['name']
                
                label = QLabel(f"{display_name}:")
                line_edit = QLineEdit()
                line_edit.setPlaceholderText(f"搜索 {display_name}")
                line_edit.returnPressed.connect(self.perform_search)
                
                self.search_inputs[col_key] = line_edit
                
                row = idx // cols_per_row
                col_idx = (idx % cols_per_row) * 2
                
                self.search_grid.addWidget(label, row, col_idx)
                self.search_grid.addWidget(line_edit, row, col_idx + 1)
                
            # 4. 更新结果表头
            header_labels = [m['display_name'] for m in self.column_metadata]
            self.result_table.setColumnCount(len(header_labels))
            self.result_table.setHorizontalHeaderLabels(header_labels)
            
            # 表格自适应宽度逻辑
            header = self.result_table.horizontalHeader()
            if len(header_labels) <= 7:
                # 字段少时，平分宽度填满
                header.setSectionResizeMode(QHeaderView.Stretch)
            else:
                # 字段多时，按内容自适应，但最后那一列拉伸填满剩余空间
                header.setSectionResizeMode(QHeaderView.ResizeToContents)
                header.setStretchLastSection(True)
            
            # 启用/禁用特定按钮
            # 只要包含 id_card 且属于 person_info 即可
            has_id_card = any(m['table'] == 'person_info' and m['origin_col'] == 'id_card' for m in self.column_metadata)
            self.verify_btn.setEnabled(has_id_card)
            
            # 调整搜索框区域高度 (自适应内容，带上限)
            # 计算行数: (count + 3) // 4
            row_count = (len(self.column_metadata) + 3) // 4
            if row_count == 0: row_count = 1
            
            # 每行高度估算 (行高 + 间距)
            row_height = 40 
            # 基础高度 (padding)
            base_height = 20 
            
            target_height = base_height + (row_count * row_height)
            max_height = 220 # 上限
            
            final_height = min(target_height, max_height)
            self.search_scroll.setFixedHeight(final_height)
            
            # 自动触发查询
            self.perform_search()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"加载表结构失败: {e}")

    def perform_search(self):
        """执行动态查询 (支持 JOIN)"""
        table_name = self.table_selector.currentData()
        if not table_name:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. 构建查询字段和 JOIN
            # 我们需要获取所有相关表的 rowid 以便后续编辑
            # SELECT T0.rowid as _rowid_T0, T1.rowid as _rowid_T1, T0.col1, T1.col2 ...
            
            select_parts = [f"{table_name}.rowid as _rowid_{table_name}"]
            join_parts = []
            
            children = self.table_relations.get(table_name, [])
            for child in children:
                child_name = child['child_table']
                select_parts.append(f"{child_name}.rowid as _rowid_{child_name}")
                
                # LEFT JOIN child ON child.fk = parent.pk
                # 注意：这里假设是简单的 1层 JOIN。如果是多层，逻辑会更复杂，目前只处理 1层。
                join_parts.append(f"LEFT JOIN {child_name} ON {child_name}.{child['child_col']} = {table_name}.{child['parent_col']}")

            # 添加数据列
            for meta in self.column_metadata:
                # 使用 table.col 格式
                select_parts.append(f"{meta['table']}.{meta['origin_col']}")

            base_sql = f"SELECT {', '.join(select_parts)} FROM {table_name} {' '.join(join_parts)}"
            
            # 2. 收集搜索条件
            conditions = []
            params = []
            active_filters = {} 
            
            for col_key, widget in self.search_inputs.items():
                val = widget.text().strip()
                if val:
                    # 找到对应的 meta
                    meta = next((m for m in self.column_metadata if m['name'] == col_key), None)
                    if not meta: continue
                    
                    active_filters[col_key] = val
                    
                    if not self.fuzzy_checkbox.isChecked():
                        # SQL LIKE search
                        conditions.append(f"{meta['table']}.{meta['origin_col']} LIKE ?")
                        params.append(f"%{val}%")

            if not self.fuzzy_checkbox.isChecked() and conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
                sql = base_sql + where_clause
            else:
                sql = base_sql
                params = []
            
            cursor.execute(sql, params)
            rows = cursor.fetchall() # list of Row objects
            conn.close()
            
            # 3. 模糊匹配后处理 (如果需要)
            final_rows = []
            if self.fuzzy_checkbox.isChecked() and active_filters:
                scored_rows = []
                for row in rows:
                    total_score = 0
                    match_all = True
                    
                    # row 是 sqlite3.Row，我们需要通过 index 访问，因为列名可能有重复
                    # select_parts 顺序：rowids... , data_cols...
                    # 数据列的起始索引 = 1 (master rowid) + len(children)
                    data_start_idx = 1 + len(children)
                    
                    for idx, meta in enumerate(self.column_metadata):
                        col_key = meta['name']
                        if col_key in active_filters:
                            keyword = active_filters[col_key]
                            # 获取值
                            val_idx = data_start_idx + idx
                            cell_value = str(row[val_idx]) if row[val_idx] is not None else ""
                            
                            score, _ = self._calculate_match_score(cell_value, keyword)
                            if score == 0:
                                match_all = False
                                break
                            total_score += score
                    
                    if match_all:
                        scored_rows.append({'row': row, 'score': total_score})
                
                scored_rows.sort(key=lambda x: x['score'], reverse=True)
                final_rows = [x['row'] for x in scored_rows]
            else:
                final_rows = rows
                
            self._update_table(final_rows, table_name, children)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "查询错误", str(e))

    def _update_table(self, rows, master_table, children):
        """更新结果表格"""
        self.result_table.blockSignals(True)
        self.result_table.setRowCount(0)
        
        display_limit = 500
        data_start_idx = 1 + len(children)
        
        for row_idx, row_data in enumerate(rows[:display_limit]):
            self.result_table.insertRow(row_idx)
            
            # 提取 rowids
            # master rowid is at 0
            # child rowids follow
            rowids = {}
            rowids[master_table] = row_data[0]
            for i, child in enumerate(children):
                rowids[child['child_table']] = row_data[1 + i]
            
            for col_idx, meta in enumerate(self.column_metadata):
                val_idx = data_start_idx + col_idx
                val = row_data[val_idx]
                item = QTableWidgetItem(str(val) if val is not None else "")
                
                # 将 rowids 存入每一格 (或者只存第一格，但为了编辑方便，存每一格)
                # 实际上我们需要知道这一格属于哪个表，以及那个表的 rowid
                target_table = meta['table']
                target_rowid = rowids.get(target_table)
                
                item.setData(Qt.UserRole, {
                    'table': target_table,
                    'rowid': target_rowid,
                    'col': meta['origin_col']
                })
                
                self.result_table.setItem(row_idx, col_idx, item)
        
        self.result_table.blockSignals(False)
        self.status_label.setText(f"显示 {len(rows[:display_limit])} 条记录 (共 {len(rows)} 条)")

    def _calculate_match_score(self, text, keyword):
        """计算匹配分数 (复用原有逻辑)"""
        if not text or not keyword:
            return 0, []
            
        text_lower = text.lower()
        kw_lower = keyword.lower()
        
        if text_lower == kw_lower:
            return 100, [(0, len(text))]
        
        if kw_lower in text_lower:
            start = text_lower.find(kw_lower)
            return 80, [(start, start + len(keyword))]
            
        matches = []
        current_pos = 0
        matched_indices = []
        
        for char in kw_lower:
            pos = text_lower.find(char, current_pos)
            if pos == -1:
                return 0, []
            matched_indices.append(pos)
            current_pos = pos + 1
            
        span = matched_indices[-1] - matched_indices[0] + 1
        compactness = len(keyword) / span
        score = 40 + (compactness * 20)
        
        ranges = [(i, i+1) for i in matched_indices]
        return score, ranges

    def on_cell_changed(self, row, column):
        """处理单元格修改"""
        if not self.edit_mode_checkbox.isChecked():
            return
            
        try:
            item = self.result_table.item(row, column)
            if not item: return
            new_value = item.text().strip()
            
            # 获取元数据 (存储在每一格)
            data = item.data(Qt.UserRole)
            if not data or not isinstance(data, dict):
                return
            
            rowid = data.get('rowid')
            if not rowid:
                return
                
            table_name = data.get('table')
            col_name = data.get('col')
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            sql = f"UPDATE {table_name} SET {col_name} = ? WHERE rowid = ?"
            cursor.execute(sql, (new_value, rowid))
            conn.commit()
            conn.close()
            
            self.status_label.setText(f"已更新: {table_name}.{col_name} -> {new_value}")
            
        except Exception as e:
            # 避免弹出过多错误框，只在状态栏显示
            self.status_label.setText(f"更新错误: {e}")
            print(f"Update error: {e}")

    def toggle_edit_mode(self, state):
        if state == Qt.Checked:
            self.result_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
            self.status_label.setText("编辑模式已开启 (双击单元格修改)")
        else:
            self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.status_label.setText("编辑模式已关闭")

    def open_verification_dialog(self):
        """打开在线验证对话框 (仅支持 person_info 表)"""
        if not AUTOMATION_AVAILABLE:
            QMessageBox.warning(self, "错误", "自动化模块未加载")
            return
            
        # 查找 id_card 列索引
        id_col_index = -1
        for idx, meta in enumerate(self.column_metadata):
            if meta['table'] == 'person_info' and meta['origin_col'] == 'id_card':
                id_col_index = idx
                break
                
        if id_col_index == -1:
            QMessageBox.warning(self, "错误", "未找到身份证号列 (person_info.id_card)")
            return

        selected_items = self.result_table.selectedItems()
        id_cards = set()
        
        # 1. 优先使用选中的行
        if selected_items:
            rows = set(item.row() for item in selected_items)
            for row in rows:
                id_item = self.result_table.item(row, id_col_index)
                if id_item and id_item.text().strip():
                    id_cards.add(id_item.text().strip())
        
        # 2. 如果没有选中，询问是否处理全部
        if not id_cards:
            count = self.result_table.rowCount()
            if count == 0:
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
        self.perform_search()

    def eventFilter(self, source, event):
        if (source == self.result_table and event.type() == event.KeyPress and 
            event.matches(QKeySequence.Copy)):
            self.copy_selection()
            return True
        return super().eventFilter(source, event)

    def copy_selection(self):
        selection = self.result_table.selectedItems()
        if not selection:
            return
        selection.sort(key=lambda x: (x.row(), x.column()))
        text = " ".join([item.text() for item in selection])
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def export_results(self):
        if self.result_table.rowCount() == 0:
            QMessageBox.information(self, "提示", "没有数据可导出")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "Excel Files (*.xlsx)")
        if not save_path:
            return
            
        try:
            headers = [self.result_table.horizontalHeaderItem(i).text() for i in range(self.result_table.columnCount())]
            data = []
            for row in range(self.result_table.rowCount()):
                row_data = []
                for col in range(self.result_table.columnCount()):
                    item = self.result_table.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            df = pd.DataFrame(data, columns=headers)
            df.to_excel(save_path, index=False)
            QMessageBox.information(self, "成功", "导出成功")
        except Exception as e:
            QMessageBox.critical(self, "导出错误", str(e))
