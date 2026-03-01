# -*- coding: utf-8 -*-
import os
import json
try:
    from PyQt5.QtWidgets import QFileDialog, QInputDialog, QDialog, QApplication, QProgressDialog
    from PyQt5.QtCore import Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from app.core.database_importer import DatabaseImporter
from app.ui.dialogs.db_manager_dialog import DbManagerDialog
from app.ui.dialogs.glass_dialogs import GlassMessageDialog
from app.ui.dialogs.db_selection_dialog import DbSelectionDialog
from app.ui.dialogs.db_query_dialog import DbQueryDialog
from app.ui.dialogs.field_binding_dialog import FieldBindingDialog

class DatabaseController:
    def __init__(self, main_window):
        self.main_window = main_window
        self.config_manager = main_window.config_manager
        self.project_root = main_window.project_root

    def open_db_manager_dialog(self):
        """打开数据库管理对话框"""
        if not PYQT_AVAILABLE:
            return
            
        db_dir = os.path.join(self.project_root, "databases")
        dialog = DbManagerDialog(db_dir, self.main_window.main_window)
        dialog.exec_()

    def open_db_import_dialog(self):
        """打开数据库导入对话框"""
        if not PYQT_AVAILABLE:
            return
            
        # 选择导入模式
        items = ["从TXT/JSON数据文件导入", "导入现有数据库文件(.db)"]
        item, ok = QInputDialog.getItem(self.main_window.main_window, "选择导入方式", "请选择导入类型:", items, 0, False)
        if not ok or not item:
            return
            
        if item == "导入现有数据库文件(.db)":
            self.import_existing_db()
        else:
            self.import_from_data_files()
            
    def import_existing_db(self):
        """导入现有数据库文件"""
        source_db, _ = QFileDialog.getOpenFileName(
            self.main_window.main_window,
            "选择现有数据库文件",
            "",
            "SQLite Database (*.db);;All Files (*)"
        )
        if not source_db:
            return
            
        import shutil
        
        # 目标目录
        db_dir = os.path.join(self.project_root, "databases")
        os.makedirs(db_dir, exist_ok=True)
        
        # 目标文件名 (保持原名，如果有重名则询问)
        base_name = os.path.basename(source_db)
        target_path = os.path.join(db_dir, base_name)
        
        if os.path.exists(target_path):
             # 询问是否覆盖或重命名
             dlg = GlassMessageDialog(
                 self.main_window.main_window,
                 title="文件已存在",
                 text=f"数据库 '{base_name}' 已存在。\n是否覆盖？\n(选择“否”则取消导入)",
                 buttons=[("yes", "是"), ("no", "否")],
             )
             dlg.exec_()
             if dlg.result_key() != "yes":
                 return
                 
        try:
            shutil.copy2(source_db, target_path)
            dlg_ok = GlassMessageDialog(
                self.main_window.main_window,
                title="成功",
                text=f"数据库已成功导入到:\n{target_path}",
                buttons=[("ok", "确定")],
            )
            dlg_ok.exec_()
        except Exception as e:
            dlg_err = GlassMessageDialog(
                self.main_window.main_window,
                title="错误",
                text=f"导入数据库失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err.exec_()

    def import_from_data_files(self):
        """从数据文件导入"""
        # 1. 选择源目录
        input_dir = QFileDialog.getExistingDirectory(
            self.main_window.main_window, 
            "选择源目录 (将递归查找 .txt/.json)",
            self.project_root
        )
        if not input_dir:
            return
            
        # 2. 选择目标数据库
        items = ["新建数据库", "选择现有数据库"]
        item, ok = QInputDialog.getItem(self.main_window.main_window, "选择目标数据库", "请选择:", items, 0, False)
        if not ok or not item:
            return

        db_path = ""
        if item == "新建数据库":
             db_name, ok = QInputDialog.getText(self.main_window.main_window, "新建数据库", "请输入数据库名称 (无需后缀):")
             if not ok or not db_name:
                 return
             db_dir = os.path.join(self.project_root, "databases")
             os.makedirs(db_dir, exist_ok=True)
             db_path = os.path.join(db_dir, f"{db_name}.db")
             if os.path.exists(db_path):
                 dlg2 = GlassMessageDialog(
                     self.main_window.main_window,
                     title="确认",
                     text="数据库已存在，是否覆盖？",
                     buttons=[("yes", "确定"), ("no", "取消")],
                 )
                 dlg2.exec_()
                 if dlg2.result_key() != "yes":
                     return
        else: # 选择现有数据库
             db_dir = os.path.join(self.project_root, "databases")
             selection_dialog = DbSelectionDialog(db_dir, self.main_window.main_window)
             if selection_dialog.exec_() == QDialog.Accepted:
                 db_path = selection_dialog.selected_db_path
             else:
                 return
        
        if not db_path:
             return
            
        # 3. 执行导入 (使用进度条)
        try:
            # 创建进度对话框 (初始范围未知)
            progress = QProgressDialog("正在扫描文件...", "取消", 0, 0, self.main_window.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            
            importer = DatabaseImporter(db_path)
            
            def progress_callback(current, total, filename):
                if progress.wasCanceled():
                    return
                if progress.maximum() != total:
                    progress.setMaximum(total)
                progress.setValue(current)
                progress.setLabelText(f"正在处理 ({current}/{total}): {filename}")
                QApplication.processEvents()
                
            processed_count, added_records = importer.import_from_directory(input_dir, progress_callback)
            
            progress.setValue(progress.maximum())
            
            if progress.wasCanceled():
                dlg_cancel = GlassMessageDialog(
                    self.main_window.main_window,
                    title="已取消",
                    text="导入过程已取消",
                    buttons=[("ok", "确定")],
                )
                dlg_cancel.exec_()
            else:
                dlg_done = GlassMessageDialog(
                    self.main_window.main_window,
                    title="导入完成",
                    text=f"数据库: {os.path.basename(db_path)}\n处理文件数: {processed_count}\n新增记录数: {added_records}",
                    buttons=[("ok", "确定")],
                )
                dlg_done.exec_()
            
        except Exception as e:
            # self.main_window.logger.error(f"数据库导入失败: {e}") # Logger might not be available or public
            print(f"数据库导入失败: {e}")
            dlg_err2 = GlassMessageDialog(
                self.main_window.main_window,
                title="错误",
                text=f"数据库导入失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err2.exec_()

    def open_field_binding_dialog(self):
        """打开可视化字段绑定工作台"""
        if not PYQT_AVAILABLE:
            return
            
        # 直接打开对话框，不依赖主窗口选图
        dialog = FieldBindingDialog(self.main_window.main_window, config_manager=self.config_manager)
        dialog.config_saved.connect(self.on_binding_config_saved)
        dialog.exec_()
        
        # Clear cache and refresh current view after dialog closes
        self.main_window.results_json_by_filename.clear()
        self.main_window.results_by_filename.clear()
        
        if self.main_window.ui and hasattr(self.main_window.ui, 'image_list'):
            current_item = self.main_window.ui.image_list.currentItem()
            if current_item:
                self.main_window._display_result_for_item(current_item)

    def on_binding_config_saved(self, config):
        """处理保存的绑定配置"""
        print(f"Binding config saved: {config}")
        # 保存到本地配置或数据库
        # 这里我们可以将其保存为一种特殊的"导入模板"
        template_name = config.get('template_name')
        if template_name:
            # Save to templates directory
            templates_dir = os.path.join(os.getcwd(), 'templates')
            os.makedirs(templates_dir, exist_ok=True)
            save_path = os.path.join(templates_dir, f"{template_name}.json")
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            dlg_saved = GlassMessageDialog(
                self.main_window.main_window,
                title="成功",
                text=f"模板 '{template_name}' 已保存",
                buttons=[("ok", "确定")],
            )
            dlg_saved.exec_()

    def open_db_query_dialog(self):
        """打开数据库查询对话框"""
        if not PYQT_AVAILABLE:
            return
            
        # 数据库目录
        db_dir = os.path.join(self.project_root, "databases")
        
        # 使用自定义选择对话框
        selection_dialog = DbSelectionDialog(db_dir, self.main_window.main_window)
        if selection_dialog.exec_() == QDialog.Accepted:
            db_path = selection_dialog.selected_db_path
            if db_path and os.path.exists(db_path):
                dialog = DbQueryDialog(db_path, self.main_window.main_window)
                dialog.exec_()
            else:
                dlg_missing = GlassMessageDialog(
                    self.main_window.main_window,
                    title="提示",
                    text="所选数据库文件不存在",
                    buttons=[("ok", "确定")],
                )
                dlg_missing.exec_()
