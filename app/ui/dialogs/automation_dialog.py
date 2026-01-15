# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QProgressBar, QCheckBox,
                             QSpinBox, QGroupBox, QDoubleSpinBox, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from app.automation.task_manager import AutomationService
from app.core.database_importer import DatabaseImporter

class AutomationSignal(QObject):
    update = pyqtSignal(dict)
    finished = pyqtSignal(list)

class AutomationDialog(QDialog):
    def __init__(self, id_cards, db_path=None, parent=None):
        super().__init__(parent)
        self.id_cards = id_cards
        self.db_path = db_path # 接收数据库路径
        
        # 确保数据库结构是最新的
        if self.db_path:
            try:
                importer = DatabaseImporter(self.db_path)
                # DatabaseImporter 的初始化会自动检查并添加缺失的列
            except Exception as e:
                print(f"Database schema update failed: {e}")

        self.automation_service = AutomationService()
        self.signals = AutomationSignal()
        
        self.setWindowTitle("在线验证自动化")
        self.resize(800, 600)
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 配置区域
        config_group = QGroupBox("任务配置")
        config_layout = QHBoxLayout(config_group)
        
        # 线程数
        config_layout.addWidget(QLabel("线程数:"))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 10)
        self.thread_spin.setValue(1)
        config_layout.addWidget(self.thread_spin)
        
        # 延迟设置
        config_layout.addWidget(QLabel("最小延迟(s):"))
        self.min_delay_spin = QDoubleSpinBox()
        self.min_delay_spin.setValue(2.0)
        config_layout.addWidget(self.min_delay_spin)
        
        config_layout.addWidget(QLabel("最大延迟(s):"))
        self.max_delay_spin = QDoubleSpinBox()
        self.max_delay_spin.setValue(5.0)
        config_layout.addWidget(self.max_delay_spin)
        
        # 无头模式
        self.headless_chk = QCheckBox("无头模式 (后台运行)")
        self.headless_chk.setChecked(False) # 默认为有头模式，方便人工验证
        self.headless_chk.setToolTip("选中后浏览器将在后台运行，不显示界面")
        config_layout.addWidget(self.headless_chk)
        
        config_layout.addStretch()
        layout.addWidget(config_group)
        
        # 2. 代理设置
        proxy_group = QGroupBox("代理设置 (每行一个 ip:port)")
        proxy_layout = QVBoxLayout(proxy_group)
        self.proxy_edit = QTextEdit()
        self.proxy_edit.setPlaceholderText("例如:\n127.0.0.1:8080\nuser:pass@192.168.1.1:8888")
        self.proxy_edit.setMaximumHeight(80)
        proxy_layout.addWidget(self.proxy_edit)
        layout.addWidget(proxy_group)
        
        # 3. 进度与控制
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始验证")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.progress_bar = QProgressBar()
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.progress_bar)
        layout.addLayout(control_layout)
        
        # 4. 日志输出
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        layout.addWidget(log_group)
        
        # 初始状态
        self.log(f"已加载 {len(self.id_cards)} 个待验证身份证号")
        self.progress_bar.setMaximum(len(self.id_cards))
        self.progress_bar.setValue(0)
        
    def setup_connections(self):
        self.start_btn.clicked.connect(self.start_task)
        self.stop_btn.clicked.connect(self.stop_task)
        self.signals.update.connect(self.on_update)
        self.signals.finished.connect(self.on_finished)
        
    def log(self, message):
        self.log_display.append(message)
        
    def start_task(self):
        proxies = [p.strip() for p in self.proxy_edit.toPlainText().split('\n') if p.strip()]

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.thread_spin.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log("任务开始...")

        config = {
            "headless": self.headless_chk.isChecked(),
            "num_threads": self.thread_spin.value(),
            "proxies": proxies,
            "delay_range": (self.min_delay_spin.value(), self.max_delay_spin.value()),
        }

        self.automation_service.run_async(
            self.id_cards,
            config,
            update_callback=self.signals.update.emit,
            finish_callback=self.signals.finished.emit,
        )
        
    def stop_task(self):
        self.automation_service.stop()
        self.log("正在停止任务...")
        self.stop_btn.setEnabled(False)
        
    def on_update(self, result):
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.log(f"[{result['status']}] {result['id_card']}: {result.get('extra_info', '')}")
        
        # 实时更新数据库
        if result['status'] == 'Success' and self.db_path and 'data' in result:
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                data = result['data']
                id_card = result['id_card']
                
                # 准备更新字段
                # 注意：我们使用身份证号作为 key
                
                # 使用字典来收集要更新的字段，避免重复添加
                updates = {}

                if 'name' in data and data['name']:
                    updates["name"] = data['name']
                    
                if 'company' in data:
                    updates["company_name"] = data['company']
                    
                if 'certificates_json' in data:
                    updates["certificates_json"] = data['certificates_json']
                    
                if 'level' in data:
                    updates["level"] = data['level']
                    
                if 'cert_number' in data:
                    updates["certificate_number"] = data['cert_number']
                    
                if 'reg_number' in data:
                    updates["registration_number"] = data['reg_number']

                if 'b_cert_status' in data:
                    updates["b_cert_status"] = data['b_cert_status']
                    
                if 'b_cert_issue_date' in data:
                    updates["b_cert_issue_date"] = data['b_cert_issue_date']
                    
                if 'b_cert_expiry_date' in data:
                    updates["b_cert_expiry_date"] = data['b_cert_expiry_date']

                # 处理动态字段 (profession_X, expiry_X)
                # 获取当前所有列名
                cursor.execute("PRAGMA table_info(person_info)")
                # columns list is tuple (cid, name, type, notnull, dflt_value, pk)
                # existing_columns names are at index 1
                existing_columns = [info[1] for info in cursor.fetchall()]

                # 确保动态字段被添加
                for key, value in data.items():
                    if key.startswith('profession_') or key.startswith('expiry_'):
                        if key not in existing_columns:
                            try:
                                # 再次检查 (防止多线程竞态条件，虽然后面是单线程更新)
                                cursor.execute("PRAGMA table_info(person_info)")
                                current_cols = [info[1] for info in cursor.fetchall()]
                                if key not in current_cols:
                                    self.log(f" -> 尝试添加新列: {key}")
                                    cursor.execute(f"ALTER TABLE person_info ADD COLUMN {key} TEXT")
                                    # 注意：SQLite ALTER TABLE 可能会自动提交事务，但显式提交更安全
                                    # 某些旧版 SQLite 可能不支持在事务中 ALTER TABLE
                                    # 这里先不 commit，依赖最后的 commit
                                    existing_columns.append(key)
                            except Exception as e:
                                self.log(f" -> 添加列 {key} 失败: {e}")
                
                # 提交结构变更 (如果有)
                conn.commit()

                # 重新获取列名以确保万无一失
                cursor.execute("PRAGMA table_info(person_info)")
                final_columns = [info[1] for info in cursor.fetchall()]
                
                if 'certificates' in data and isinstance(data['certificates'], list) and len(data['certificates']) == 0:
                    # 清空主表中的旧职业字段
                    updates["profession"] = ""
                    # 先把数据库里已有的所有 profession_*/expiry_* 列都设为空
                    # 这样可以覆盖那些 data 里没有返回但数据库里存在的旧字段
                    for col in final_columns:
                        if col.startswith('profession_') or col.startswith('expiry_'):
                            updates[col] = ""

                # 2. 用 data 中的具体值覆盖（如果 data 里有 profession_1=""，这里会再次确认）
                for key, value in data.items():
                     if (key.startswith('profession_') or key.startswith('expiry_')) and key in final_columns:
                         updates[key] = value

                # 构建 SQL
                if updates:
                    update_fields = []
                    params = []
                    for col, val in updates.items():
                        update_fields.append(f"{col} = ?")
                        params.append(val)
                    
                    sql = f"UPDATE person_info SET {', '.join(update_fields)} WHERE id_card = ?"
                    params.append(id_card)
                    
                    cursor.execute(sql, params)
                    conn.commit()
                    self.log(f" -> 主表已更新: {id_card}")
                
                # 更新证书子表
                # 1. 先删除该身份证号下的旧证书数据 (全量覆盖策略)
                cursor.execute("DELETE FROM certificates WHERE person_id_card = ?", (id_card,))
                
                # 2. 解析 certificates 列表并插入新数据
                # 优先处理结构化的 certificates 列表
                if 'certificates' in data and isinstance(data['certificates'], list):
                    total_inserted = 0
                    for cert in data['certificates']:
                        # 每个证书块可能有自己的 level 和 reg_number
                        cert_level = cert.get('level', data.get('level', ''))
                        cert_reg_num = cert.get('reg_number', data.get('reg_number', ''))
                        # cert_number 已弃用
                        
                        if 'details' in cert and isinstance(cert['details'], list):
                            for detail in cert['details']:
                                prof = detail.get('profession', '')
                                expiry = detail.get('expiry', '')
                                
                                cursor.execute('''
                                    INSERT INTO certificates (person_id_card, profession, expiry_date, level, registration_number)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (id_card, prof, expiry, cert_level, cert_reg_num))
                                total_inserted += 1
                                
                    conn.commit()
                    self.log(f" -> 证书子表已更新: {total_inserted} 条记录")
                
                # Fallback: 如果 data 中直接有 details 列表 (旧逻辑兼容)
                elif 'details' in data and isinstance(data['details'], list):
                    cert_details = data['details']
                    for detail in cert_details:
                        prof = detail.get('profession', '')
                        expiry = detail.get('expiry', '')
                        # level, cert_number, reg_number 通常是整个人的属性，或者每个证书也有？
                        # 根据之前的 scraper 逻辑，level, reg_number 是从 header 提取的，属于“人”或“主证书”级别
                        # 但用户提到“一个证书对应一个有效期”，所以 profession 和 expiry 是成对的
                        # 我们把主表中的 level, reg_number 也冗余存一份到子表，或者子表只存 profession/expiry
                        # 用户需求： "一个人可能有多个证书，一个证书对应一个有效期"
                        # 建议：子表存储 profession, expiry, 以及继承自 info 的 level, reg_number (如果适用)
                        
                        # 使用主表中的 level 和 reg_number (如果 data 中有)
                        level = data.get('level', '')
                        reg_num = data.get('reg_number', '')
                        
                        cursor.execute('''
                            INSERT INTO certificates (person_id_card, profession, expiry_date, level, registration_number)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (id_card, prof, expiry, level, reg_num))
                    
                    conn.commit()
                    self.log(f" -> 证书子表已更新: {len(cert_details)} 条记录")

                conn.close()
            except Exception as e:
                self.log(f" -> 数据库更新失败: {e}")
        
    def on_finished(self, results):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.thread_spin.setEnabled(True)
        self.log(f"任务完成，共处理 {len(results)} 条记录")
        QMessageBox.information(self, "完成", "验证任务已完成")
        
    def closeEvent(self, event):
        is_running = False
        try:
            tm = getattr(self.automation_service, "task_manager", None)
            if tm is not None and getattr(tm, "is_running", False):
                is_running = True
        except Exception:
            is_running = False
        if is_running:
            reply = QMessageBox.question(self, '确认退出',
                                       "任务正在运行，确定要停止并退出吗？",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.automation_service.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
