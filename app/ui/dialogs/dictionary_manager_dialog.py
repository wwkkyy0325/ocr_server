# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
                             QHeaderView, QMessageBox, QWidget, QTreeWidgetItemIterator)
from PyQt5.QtCore import Qt
import sqlite3

class DictionaryManagerDialog(QDialog):
    def __init__(self, db_path, default_field_mapping=None, default_table_mapping=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.default_field_mapping = default_field_mapping or {}
        self.default_table_mapping = default_table_mapping or {}
        
        # 内部状态 (未保存的更改)
        self.custom_field_map = {}
        self.custom_table_map = {}
        
        self.setWindowTitle("字典映射管理")
        self.resize(900, 700)
        
        self.layout = QVBoxLayout(self)
        
        # 说明
        self.layout.addWidget(QLabel("提示: 双击“显示名称”列即可编辑。修改字段名称会影响所有表中的同名字段。\n注意：修改后请点击“应用修改”保存，直接关闭窗口将丢弃更改。"))
        
        # 树形视图
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["原始名称 (英文)", "显示名称 (中文) - 可编辑", "来源"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemChanged.connect(self.on_item_changed)
        
        self.layout.addWidget(self.tree)
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_apply = QPushButton("应用修改 (Save)")
        self.btn_apply.clicked.connect(self.save_changes)
        
        self.btn_close = QPushButton("关闭 (Close)")
        self.btn_close.clicked.connect(self.close)
        
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)
        
        self.layout.addLayout(btn_layout)
        
        # 加载数据
        self._fetch_full_schema()
        self._init_db_meta()
        self.load_data()

    def _fetch_full_schema(self):
        """获取完整的表结构 schema: {table_name: [field_names]}"""
        self.schema = {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' AND name NOT LIKE '_sys_%'")
            tables = sorted([row[0] for row in cursor.fetchall()])
            
            for table in tables:
                self.schema[table] = []
                try:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = cursor.fetchall()
                    for col in cols:
                        self.schema[table].append(col[1]) # name
                except:
                    pass
            
            conn.close()
        except Exception as e:
            print(f"Error fetching schema: {e}")

    def _init_db_meta(self):
        """初始化元数据表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS _sys_meta_dict (
                    type TEXT,  -- 'field' or 'table'
                    key TEXT,   -- original name (e.g., 'person_info')
                    value TEXT, -- display name (e.g., '人员信息')
                    PRIMARY KEY (type, key)
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化字典表失败: {e}")

    def load_data(self):
        """加载数据并构建树"""
        try:
            # 1. 获取自定义映射
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT type, key, value FROM _sys_meta_dict")
            db_rows = cursor.fetchall()
            conn.close()
            
            # 重置内部状态
            self.custom_field_map = {}
            self.custom_table_map = {}
            for r_type, key, val in db_rows:
                if r_type == 'field':
                    self.custom_field_map[key] = val
                else:
                    self.custom_table_map[key] = val
            
            self.tree.blockSignals(True)
            self.tree.clear()
            
            # 2. 构建树
            # 遍历所有表
            for table_name in sorted(self.schema.keys()):
                # --- 表节点 ---
                table_item = QTreeWidgetItem(self.tree)
                self._setup_item(table_item, table_name, 'table', 
                                 self.default_table_mapping, self.custom_table_map)
                table_item.setExpanded(True)
                
                # 遍历该表的所有字段
                fields = self.schema[table_name]
                for field_name in sorted(fields):
                    # --- 字段节点 ---
                    field_item = QTreeWidgetItem(table_item)
                    self._setup_item(field_item, field_name, 'field',
                                     self.default_field_mapping, self.custom_field_map)
            
            self.tree.blockSignals(False)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败: {e}")

    def _setup_item(self, item, key, map_type, default_map, custom_map):
        """配置树节点显示"""
        is_custom = key in custom_map
        has_default = key in default_map
        
        val = ""
        source = "未绑定"
        color = Qt.red 
        
        if is_custom:
            val = custom_map[key]
            if has_default:
                source = "自定义 (覆盖)"
                color = Qt.blue
            else:
                source = "自定义"
                color = Qt.darkGreen
        elif has_default:
            val = default_map[key]
            source = "系统默认"
            color = Qt.gray
        else:
            val = ""
            source = "未绑定"
            color = Qt.red
            
        item.setText(0, key)
        item.setText(1, val)
        item.setText(2, source)
        
        # 只有第1列(Value)可编辑
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        item.setForeground(2, color)
        
        # 存储元数据以便识别
        item.setData(0, Qt.UserRole, map_type) # 'table' or 'field'
        item.setData(1, Qt.UserRole, key)      # original key

    def on_item_changed(self, item, column):
        """当树节点内容变化时 (只更新内存，不保存数据库)"""
        if column != 1: return
        
        map_type = item.data(0, Qt.UserRole)
        key = item.data(1, Qt.UserRole)
        
        if not map_type or not key: return
        
        new_val = item.text(1).strip()
        
        self.tree.blockSignals(True)
        try:
            # 更新内存状态
            target_map = self.custom_field_map if map_type == 'field' else self.custom_table_map
            
            if not new_val:
                if key in target_map:
                    del target_map[key]
            else:
                target_map[key] = new_val
            
            # 更新当前节点状态
            default_map = self.default_field_mapping if map_type == 'field' else self.default_table_mapping
            
            self._update_item_visuals(item, key, default_map, target_map)
            
            # 如果是字段类型，需要同步更新树中所有相同字段名的节点
            if map_type == 'field':
                self._sync_all_fields(key, default_map, target_map)
            
        except Exception as e:
            print(f"Update error: {e}")
            QMessageBox.critical(self, "错误", f"更新失败: {e}")
        finally:
            self.tree.blockSignals(False)

    def save_changes(self):
        """保存更改到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 开启事务
            cursor.execute("BEGIN TRANSACTION")
            
            # 1. 清除旧数据 (只清除 field 和 table 类型)
            cursor.execute("DELETE FROM _sys_meta_dict WHERE type IN ('field', 'table')")
            
            # 2. 插入新数据
            data_to_insert = []
            for key, val in self.custom_table_map.items():
                data_to_insert.append(('table', key, val))
            
            for key, val in self.custom_field_map.items():
                data_to_insert.append(('field', key, val))
                
            if data_to_insert:
                cursor.executemany("INSERT INTO _sys_meta_dict (type, key, value) VALUES (?, ?, ?)", data_to_insert)
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "成功", "更改已保存")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存数据库失败: {e}")

    def _update_item_visuals(self, item, key, default_map, custom_map):
        """更新单个节点的视觉状态"""
        is_custom = key in custom_map
        has_default = key in default_map
        val = custom_map.get(key, "")
        
        if not is_custom and has_default:
            val = default_map[key]
            
        source = ""
        color = Qt.black
        
        if is_custom:
            if has_default:
                source = "自定义 (覆盖)"
                color = Qt.blue
            else:
                source = "自定义"
                color = Qt.darkGreen
        elif has_default:
            source = "系统默认"
            color = Qt.gray
        else:
            source = "未绑定"
            color = Qt.red
            
        item.setText(1, val)
        item.setText(2, source)
        item.setForeground(2, color)

    def _sync_all_fields(self, field_name, default_map, custom_map):
        """同步更新所有同名字段节点"""
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            it = iterator.value()
            if it.data(0, Qt.UserRole) == 'field' and it.data(1, Qt.UserRole) == field_name:
                self._update_item_visuals(it, field_name, default_map, custom_map)
            iterator += 1

