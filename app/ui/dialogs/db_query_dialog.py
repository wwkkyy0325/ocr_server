# -*- coding: utf-8 -*-

import sqlite3
import os
import re
import pandas as pd
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog, QGroupBox, QWidget, QApplication, QCheckBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

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
        
        self.search_btn = QPushButton("查询")
        self.search_btn.clicked.connect(self.perform_search)
        
        # 添加模糊匹配复选框
        self.fuzzy_checkbox = QCheckBox("模糊匹配")
        self.fuzzy_checkbox.setChecked(False) # 默认关闭，即精确匹配
        self.fuzzy_checkbox.stateChanged.connect(self.perform_search)

        search_layout.addWidget(QLabel("姓名:"))
        search_layout.addWidget(self.name_input)
        search_layout.addWidget(QLabel("身份证:"))
        search_layout.addWidget(self.id_input)
        search_layout.addWidget(QLabel("手机号:"))
        search_layout.addWidget(self.phone_input)
        search_layout.addWidget(self.fuzzy_checkbox)
        search_layout.addWidget(self.search_btn)
        
        self.layout.addWidget(search_group)
        
        # 2. 结果展示区域
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["姓名", "职业", "身份证号", "手机号"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 改为单元格选择模式，方便复制具体内容
        self.result_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.result_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers) # 禁止编辑
        self.result_table.installEventFilter(self) # 安装事件过滤器以处理复制
        
        self.layout.addWidget(self.result_table)
        
        # 3. 底部操作区域
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.export_btn)
        
        self.layout.addLayout(bottom_layout)
        
        # 初始加载数据
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
        
        if not os.path.exists(self.db_path):
            QMessageBox.warning(self, "错误", "数据库文件不存在")
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 获取所有数据 (为了进行Python端的高级匹配和排序)
            # 如果数据量巨大，这里需要优化为分批加载或后端搜索，但考虑到是单机工具，先全量加载
            sql = "SELECT name, profession, id_card, phone_number FROM person_info"
            cursor.execute(sql)
            all_data = cursor.fetchall()
            conn.close()
            
            # 2. 过滤和评分
            if not name_query and not id_query and not phone_query:
                # 无查询条件，显示所有（或前N条）
                self._update_table(all_data)
                self.status_label.setText(f"显示所有记录: {len(all_data)} 条")
                return
            
            scored_results = []
            
            for row in all_data:
                name, profession, id_card, phone = row
                
                # 计算总分
                total_score = 0
                
                # 必须满足所有有输入的条件
                match_name = True
                match_id = True
                match_phone = True
                
                if name_query:
                    score, _ = self._calculate_match_score(str(name) if name else "", name_query)
                    if score == 0:
                        match_name = False
                    else:
                        total_score += score
                        
                if id_query:
                    score, _ = self._calculate_match_score(str(id_card) if id_card else "", id_query)
                    if score == 0:
                        match_id = False
                    else:
                        total_score += score
                        
                if phone_query:
                    score, _ = self._calculate_match_score(str(phone) if phone else "", phone_query)
                    if score == 0:
                        match_phone = False
                    else:
                        total_score += score
                
                if match_name and match_id and match_phone:
                    scored_results.append({
                        'data': row,
                        'score': total_score
                    })
            
            # 3. 排序 (按分数降序)
            scored_results.sort(key=lambda x: x['score'], reverse=True)
            
            # 4. 更新表格 (仅显示数据，移除高亮逻辑)
            # 提取排序后的原始数据
            sorted_data = [item['data'] for item in scored_results]
            self._update_table(sorted_data)
            self.status_label.setText(f"找到 {len(scored_results)} 条匹配记录")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "查询错误", str(e))

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
        self.result_table.setRowCount(0)
        display_limit = 500
        for row_idx, row_data in enumerate(data[:display_limit]):
            self.result_table.insertRow(row_idx)
            for col_idx, item in enumerate(row_data):
                self.result_table.setItem(row_idx, col_idx, QTableWidgetItem(str(item)))
                # 确保清理之前的CellWidget
                self.result_table.removeCellWidget(row_idx, col_idx)
        
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
