# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QListWidget, QListWidgetItem, 
                             QGroupBox, QSplitter, QWidget, QMenu, QInputDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
                             QTabWidget, QLineEdit, QFormLayout, QCheckBox, QRadioButton, QButtonGroup,
                             QStackedWidget, QProgressDialog, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QCoreApplication, QEvent
from PyQt5.QtGui import QColor, QBrush, QIcon
from app.main_window import FramelessBorderDialog, GlassTitleBar, GlassMessageDialog
from app.ui.widgets.image_viewer import ImageViewer
from app.ui.widgets.card_sort_widget import CardSortWidget
from app.ui.dialogs.dictionary_manager_dialog import DictionaryManagerDialog
from app.utils.ocr_utils import sort_ocr_regions
from app.utils.file_utils import FileUtils
from app.ocr.engine import OcrEngine
from PIL import Image
import json
import os
import sqlite3
import shutil


class TemplateManagerDialog(FramelessBorderDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模板管理")
        self.resize(400, 300)
        self.template_path = os.path.join(os.getcwd(), "field_templates.json")
        self.selected_template = None
        self.templates = {}
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = GlassTitleBar("模板管理", self)
        main_layout.addWidget(title_bar)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)
        main_layout.addLayout(layout)
        
        self.list_widget = QListWidget()
        self.list_widget.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("加载")
        self.btn_load.clicked.connect(self.accept_selection)
        self.btn_delete = QPushButton("删除")
        self.btn_delete.clicked.connect(self.delete_template)
        self.btn_cancel = QPushButton("关闭")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.load_data()
        
    def load_data(self):
        self.list_widget.clear()
        self.templates = {}
        if os.path.exists(self.template_path):
            try:
                with open(self.template_path, 'r', encoding='utf-8') as f:
                    self.templates = json.load(f)
            except Exception:
                pass
        
        for name in self.templates.keys():
            self.list_widget.addItem(name)
            
    def delete_template(self):
        item = self.list_widget.currentItem()
        if not item: return
        name = item.text()
        
        dlg = GlassMessageDialog(
            self,
            title="确认删除",
            text=f"确定要删除模板 '{name}' 吗？",
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg.exec_()
        if dlg.result_key() == "yes":
            if name in self.templates:
                del self.templates[name]
                self._save_file()
                self.load_data()
                
    def _save_file(self):
        try:
            with open(self.template_path, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            dlg_err = GlassMessageDialog(
                self,
                title="错误",
                text=f"保存失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err.exec_()
            
    def accept_selection(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_template = self.templates.get(item.text())
            self.accept()
        else:
            if self.sender() == self.btn_load:
                dlg_warn = GlassMessageDialog(
                    self,
                    title="提示",
                    text="请选择一个模板",
                    buttons=[("ok", "确定")],
                )
                dlg_warn.exec_()


class TemplateNameDialog(FramelessBorderDialog):
    def __init__(self, parent=None, title="输入", label_text="请输入名称:"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(360, 160)
        self._text = ""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = GlassTitleBar(title, self)
        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(8)

        label = QLabel(label_text)
        self.edit = QLineEdit()

        content_layout.addWidget(label)
        content_layout.addWidget(self.edit)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        content_layout.addLayout(btn_layout)
        main_layout.addWidget(content_widget)

    def _on_ok(self):
        text = self.edit.text().strip()
        if not text:
            dlg_warn = GlassMessageDialog(
                self,
                title="提示",
                text="名称不能为空",
                buttons=[("ok", "确定")],
            )
            dlg_warn.exec_()
            return
        self._text = text
        self.accept()

    def get_text(self):
        return self._text


class FieldBindingDialog(FramelessBorderDialog):
    """
    可视化字段绑定工作台
    集成图片管理、双视图预览、数据库配置与字段绑定功能
    """
    
    # 信号：当配置保存时触发，传递配置字典
    config_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.setWindowTitle("可视化字段绑定工作台")
        self.resize(1600, 1000)
        
        self.config_manager = config_manager
        
        # State
        self.image_dir = ""
        self.image_files = []
        self.current_image_index = -1
        self.ocr_results = []
        self.modified_ocr_data = {} # filename -> list of items (cache for edited data)
        
        self.db_path = ""
        self.table_name = "ocr_records"
        self.current_bindings = {} 
        self.current_target_field = None
        self.known_field_mappings = {} # Cache for auto-fill
        
        # Default Fields (can be overridden by DB config)
        self.available_fields = []
        
        # State variables for robustness against widget deletion
        self.is_auto_pk_selected = True 
        
        self._init_ui()

        # File utils for PDF page counting if available
        try:
            from app.utils.file_utils import FileUtils as _FU
            self._file_utils = _FU()
        except Exception:
            self._file_utils = None
        
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = GlassTitleBar("可视化字段绑定工作台", self)
        main_layout.addWidget(title_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(8)
        
        # Splitter for 3 panes: File List | Viewers | Controls
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # --- 1. Left Panel: File Manager ---
        file_panel = QWidget()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        file_group = QGroupBox("图片列表")
        file_group_layout = QVBoxLayout(file_group)
        
        self.btn_open_dir = QPushButton("打开文件夹")
        self.btn_open_dir.clicked.connect(self.open_directory)
        
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.on_file_list_context_menu)
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        # 让文件列表支持拖拽导入图片 / 文件夹
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragEnabled(False)
        self.file_list.setDropIndicatorShown(True)
        self.file_list.installEventFilter(self)
        
        file_group_layout.addWidget(self.btn_open_dir)
        file_group_layout.addWidget(self.file_list)
        file_layout.addWidget(file_group)
        
        # --- 2. Center Panel: Dual Viewers ---
        view_panel = QWidget()
        view_layout = QVBoxLayout(view_panel)
        view_layout.setContentsMargins(0, 0, 0, 0)
        
        view_group = QGroupBox("双视图预览 (左:原图 / 右:识别文字)")
        view_group_layout = QVBoxLayout(view_group)
        
        self.viewer_splitter = QSplitter(Qt.Horizontal)
        
        # Viewer 1: Original Image
        self.image_viewer_orig = ImageViewer()
        self.image_viewer_orig.set_interaction_mode('select')
        self.image_viewer_orig.selection_callback = lambda idx: self.on_region_selected(idx, 'orig')
        self.image_viewer_orig.show_ocr_text = False # Only image
        self.image_viewer_orig.show_image = True
        
        # Viewer 2: Text List (Expanded view) or Card Sort View
        self.view_stack = QStackedWidget()
        
        # View 0: List
        self.ocr_list_widget = QListWidget()
        self.ocr_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.ocr_list_widget.itemSelectionChanged.connect(self.on_list_selection_changed)
        self.view_stack.addWidget(self.ocr_list_widget)
        
        # View 1: Card Sort
        self.card_sort_widget = CardSortWidget()
        self.card_sort_widget.data_changed.connect(self.on_ocr_data_changed)
        self.view_stack.addWidget(self.card_sort_widget)
        
        self.viewer_splitter.addWidget(self.image_viewer_orig)
        self.viewer_splitter.addWidget(self.view_stack)
        self.viewer_splitter.setStretchFactor(0, 1)
        self.viewer_splitter.setStretchFactor(1, 1)
        
        view_group_layout.addWidget(self.viewer_splitter)
        view_layout.addWidget(view_group)
        
        # --- 3. Right Panel: Controls & Settings ---
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        # Tab 1: Database & Schema
        self.tab_db = QWidget()
        self._init_db_tab(self.tab_db)
        self.tabs.addTab(self.tab_db, "数据库配置")
        
        # Tab 2: Binding
        self.tab_binding = QWidget()
        self._init_binding_tab(self.tab_binding)
        self.tabs.addTab(self.tab_binding, "字段绑定")
        
        control_layout.addWidget(self.tabs)
        
        # Bottom Actions
        action_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存配置模板")
        self.save_btn.clicked.connect(self.save_config)
        
        self.run_import_btn = QPushButton("开始批量导入数据库")
        self.run_import_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.run_import_btn.clicked.connect(self.run_batch_import)
        
        self.cancel_btn = QPushButton("关闭")
        self.cancel_btn.clicked.connect(self.reject)
        
        action_layout.addWidget(self.save_btn)
        action_layout.addWidget(self.run_import_btn)
        action_layout.addWidget(self.cancel_btn)
        
        control_layout.addLayout(action_layout)
        
        # Add to main splitter
        self.main_splitter.addWidget(file_panel)
        self.main_splitter.addWidget(view_panel)
        self.main_splitter.addWidget(control_panel)
        
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 6)
        self.main_splitter.setStretchFactor(2, 3)
        
        content_layout.addWidget(self.main_splitter)
        main_layout.addLayout(content_layout)

    def _init_db_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Database File
        db_group = QGroupBox("数据库连接")
        db_layout = QFormLayout(db_group)
        
        self.edit_db_path = QLineEdit()
        self.edit_db_path.setPlaceholderText("选择或创建 .db 文件")
        btn_browse_db = QPushButton("浏览...")
        btn_browse_db.clicked.connect(self.browse_database)
        
        db_row = QHBoxLayout()
        db_row.addWidget(self.edit_db_path)
        db_row.addWidget(btn_browse_db)
        
        self.combo_table_name = QComboBox()
        self.combo_table_name.setEditable(True)
        self.combo_table_name.setInsertPolicy(QComboBox.NoInsert)
        self.combo_table_name.activated.connect(self.on_table_selected)
        
        # Data Mode
        mode_layout = QHBoxLayout()
        self.radio_single = QRadioButton("单条模式 (一图一记录)")
        self.radio_single.setChecked(True)
        self.radio_single.toggled.connect(self.on_mode_changed)
        
        self.radio_table = QRadioButton("表格模式 (一图多记录)")
        self.radio_table.toggled.connect(self.on_mode_changed)
        self.bg_mode = QButtonGroup()
        self.bg_mode.addButton(self.radio_single)
        self.bg_mode.addButton(self.radio_table)
        mode_layout.addWidget(self.radio_single)
        mode_layout.addWidget(self.radio_table)
        mode_layout.addStretch()
        
        db_layout.addRow("数据库文件:", db_row)
        db_layout.addRow("数据表名:", self.combo_table_name)

        # PK Strategy
        pk_group = QGroupBox("主键策略 (必选)")
        pk_layout = QHBoxLayout(pk_group)
        self.radio_pk_auto = QRadioButton("系统自动生成 (Auto ID)")
        self.radio_pk_custom = QRadioButton("指定业务字段 (Business PK)")
        self.radio_pk_auto.setChecked(True) # Default
        self.radio_pk_auto.toggled.connect(self._update_schema_ui_state)
        self.radio_pk_custom.toggled.connect(self._update_schema_ui_state)
        
        self.bg_pk = QButtonGroup()
        self.bg_pk.addButton(self.radio_pk_auto)
        self.bg_pk.addButton(self.radio_pk_custom)
        
        pk_layout.addWidget(self.radio_pk_auto)
        pk_layout.addWidget(self.radio_pk_custom)
        
        db_layout.addRow("主键策略:", pk_layout)
        
        db_layout.addRow("录入模式:", mode_layout)
        
        layout.addWidget(db_group)
        
        # Field Schema
        schema_group = QGroupBox("字段定义")
        schema_layout = QVBoxLayout(schema_group)
        
        self.schema_table = QTableWidget()
        self.schema_table.setColumnCount(4)
        self.schema_table.setHorizontalHeaderLabels(["字段Key", "字段名称", "类型", "唯一/主键"])
        self.schema_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.schema_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.schema_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.schema_table.setSelectionMode(QTableWidget.SingleSelection)
        self.schema_table.itemChanged.connect(self.on_schema_item_changed)
        
        # Add/Remove Field Buttons
        btn_layout = QHBoxLayout()
        self.btn_add_field = QPushButton("添加字段")
        self.btn_add_field.clicked.connect(self.add_schema_field)
        self.btn_remove_field = QPushButton("删除字段")
        self.btn_remove_field.clicked.connect(self.remove_schema_field)
        
        # Template Buttons
        self.btn_save_tpl = QPushButton("保存模板")
        self.btn_save_tpl.clicked.connect(self.save_field_template)
        self.btn_load_tpl = QPushButton("加载/管理模板")
        self.btn_load_tpl.clicked.connect(self.load_field_template)
        
        # Move Up/Down Buttons
        self.btn_move_up = QPushButton("上移")
        self.btn_move_up.clicked.connect(self.move_field_up)
        self.btn_move_down = QPushButton("下移")
        self.btn_move_down.clicked.connect(self.move_field_down)

        self.btn_apply_schema = QPushButton("应用字段定义")
        self.btn_apply_schema.clicked.connect(self.apply_schema)
        self.btn_apply_schema.setStyleSheet("font-weight: bold; color: #2196F3;")
        
        self.btn_manage_dict = QPushButton("字典映射管理")
        self.btn_manage_dict.clicked.connect(self.open_dict_manager)

        btn_layout.addWidget(self.btn_add_field)
        btn_layout.addWidget(self.btn_remove_field)
        btn_layout.addWidget(self.btn_save_tpl)
        btn_layout.addWidget(self.btn_load_tpl)
        btn_layout.addWidget(self.btn_manage_dict)
        btn_layout.addWidget(self.btn_move_up)
        btn_layout.addWidget(self.btn_move_down)
        btn_layout.addWidget(self.btn_apply_schema)
        
        schema_layout.addWidget(self.schema_table)
        schema_layout.addLayout(btn_layout)
        
        layout.addWidget(schema_group)
        
        # Initial Schema Data
        self._populate_schema_table([])

    def move_field_up(self):
        row = self.schema_table.currentRow()
        if row > 0:
            self._swap_schema_rows(row, row - 1)
            self.schema_table.setCurrentCell(row - 1, 0)

    def move_field_down(self):
        row = self.schema_table.currentRow()
        if row >= 0 and row < self.schema_table.rowCount() - 1:
            self._swap_schema_rows(row, row + 1)
            self.schema_table.setCurrentCell(row + 1, 0)

    def _swap_schema_rows(self, row1, row2):
        # Capture data from row1
        key1 = self.schema_table.item(row1, 0).text() if self.schema_table.item(row1, 0) else ""
        name1 = self.schema_table.item(row1, 1).text() if self.schema_table.item(row1, 1) else ""
        type_combo1 = self.schema_table.cellWidget(row1, 2)
        type1 = type_combo1.currentText() if type_combo1 else "TEXT"
        widget1 = self.schema_table.cellWidget(row1, 3)
        pk1 = False
        if widget1:
            ck1 = widget1.findChild(QCheckBox)
            if ck1: pk1 = ck1.isChecked()
        
        # Capture data from row2
        key2 = self.schema_table.item(row2, 0).text() if self.schema_table.item(row2, 0) else ""
        name2 = self.schema_table.item(row2, 1).text() if self.schema_table.item(row2, 1) else ""
        type_combo2 = self.schema_table.cellWidget(row2, 2)
        type2 = type_combo2.currentText() if type_combo2 else "TEXT"
        widget2 = self.schema_table.cellWidget(row2, 3)
        pk2 = False
        if widget2:
            ck2 = widget2.findChild(QCheckBox)
            if ck2: pk2 = ck2.isChecked()
        
        # Set data to row1 (using row2's data)
        self.schema_table.setItem(row1, 0, QTableWidgetItem(key2))
        self.schema_table.setItem(row1, 1, QTableWidgetItem(name2))
        self.schema_table.setCellWidget(row1, 2, self._create_type_combo(type2))
        
        ck_new1 = QCheckBox()
        ck_new1.setChecked(pk2)
        ck_new1.toggled.connect(lambda checked, r=row1: self._on_pk_checkbox_toggled(r, checked))
        w_new1 = QWidget()
        h_new1 = QHBoxLayout(w_new1)
        h_new1.setAlignment(Qt.AlignCenter)
        h_new1.setContentsMargins(0,0,0,0)
        h_new1.addWidget(ck_new1)
        self.schema_table.setCellWidget(row1, 3, w_new1)
        
        # Set data to row2 (using row1's data)
        self.schema_table.setItem(row2, 0, QTableWidgetItem(key1))
        self.schema_table.setItem(row2, 1, QTableWidgetItem(name1))
        self.schema_table.setCellWidget(row2, 2, self._create_type_combo(type1))
        
        ck_new2 = QCheckBox()
        ck_new2.setChecked(pk1)
        ck_new2.toggled.connect(lambda checked, r=row2: self._on_pk_checkbox_toggled(r, checked))
        w_new2 = QWidget()
        h_new2 = QHBoxLayout(w_new2)
        h_new2.setAlignment(Qt.AlignCenter)
        h_new2.setContentsMargins(0,0,0,0)
        h_new2.addWidget(ck_new2)
        self.schema_table.setCellWidget(row2, 3, w_new2)

    def _init_binding_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Binding Table
        self.binding_table = QTableWidget()
        self.binding_table.setColumnCount(3)
        self.binding_table.setHorizontalHeaderLabels(["字段名称", "绑定值预览", "操作"])
        self.binding_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.binding_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.binding_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.binding_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.binding_table.setSelectionMode(QTableWidget.SingleSelection)
        self.binding_table.cellClicked.connect(self.on_binding_table_clicked)
        
        layout.addWidget(self.binding_table)
        
        # Tools
        tools_group = QGroupBox("辅助工具")
        tools_layout = QHBoxLayout(tools_group)
        
        self.btn_batch_col = QPushButton("选择同列")
        self.btn_batch_col.clicked.connect(lambda: self.select_aligned('vertical'))
        self.btn_batch_row = QPushButton("选择同行")
        self.btn_batch_row.clicked.connect(lambda: self.select_aligned('horizontal'))
        self.btn_clear_bind = QPushButton("清除绑定")
        self.btn_clear_bind.clicked.connect(self.clear_current_binding)
        
        tools_layout.addWidget(self.btn_batch_col)
        tools_layout.addWidget(self.btn_batch_row)
        tools_layout.addWidget(self.btn_clear_bind)
        
        layout.addWidget(tools_group)

    # --- File Handling ---
    
    def open_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if dir_path:
            self.image_dir = dir_path
            self.load_file_list()
            
    def load_file_list(self):
        self.file_list.clear()
        self.image_files = []
        
        valid_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.pdf']
        for f in os.listdir(self.image_dir):
            if os.path.splitext(f)[1].lower() in valid_exts:
                self.image_files.append(f)
                self.file_list.addItem(f)
                
        if self.image_files:
            self.file_list.setCurrentRow(0)

    def eventFilter(self, obj, event):
        # 让文件列表支持像主程序一样拖入文件 / 文件夹
        try:
            if obj == self.file_list:
                if event.type() == QEvent.DragEnter:
                    if event.mimeData().hasUrls():
                        event.acceptProposedAction()
                        return True
                if event.type() == QEvent.Drop:
                    urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
                    dropped_paths = []
                    for url in urls:
                        local_path = url.toLocalFile()
                        if local_path:
                            dropped_paths.append(local_path)

                    if not dropped_paths:
                        return False

                    # 规则：
                    # 1) 如果拖入的是目录，则以目录为 image_dir，列出其中所有合法图片 / PDF
                    # 2) 如果拖入的是多个文件，则以这些文件所在目录为 image_dir，只加载这些文件
                    first_path = dropped_paths[0]
                    if os.path.isdir(first_path):
                        self.image_dir = first_path
                        self._load_files_from_directory(first_path)
                    else:
                        base_dir = os.path.dirname(first_path)
                        self.image_dir = base_dir
                        self._load_files_from_explicit_list(dropped_paths)

                    event.acceptProposedAction()
                    return True
        except Exception:
            pass

        return super().eventFilter(obj, event)

    def _load_files_from_directory(self, dir_path):
        self.image_files = []
        self.file_list.clear()
        valid_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.pdf']
        for f in os.listdir(dir_path):
            full = os.path.join(dir_path, f)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(f)[1].lower() not in valid_exts:
                continue
            self.image_files.append(f)
            self.file_list.addItem(f)

        if self.image_files:
            self.file_list.setCurrentRow(0)

    def _load_files_from_explicit_list(self, paths):
        self.image_files = []
        self.file_list.clear()
        valid_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.pdf']

        for p in paths:
            if os.path.isdir(p):
                # 如果混合拖入目录，这里可以递归或忽略；按简单策略：忽略目录
                continue
            if not os.path.isfile(p):
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext not in valid_exts:
                continue

            name = os.path.basename(p)
            # 保证 image_dir 作为基准：只记录文件名，路径由 image_dir + 文件名组合
            self.image_files.append(name)
            self.file_list.addItem(name)

        if self.image_files:
            self.file_list.setCurrentRow(0)

    def on_file_selected(self, row):
        if row < 0 or row >= len(self.image_files):
            return
            
        filename = self.image_files[row]
        file_path = os.path.join(self.image_dir, filename)
        self.current_image_path = file_path
        
        # Load Image
        self.image_viewer_orig.display_image(file_path)
        # self.image_viewer_text.display_image(file_path) # Removed
        
        # Load OCR Result
        self.load_ocr_result(filename)

    def _get_ocr_data_for_file(self, filename):
        if filename in self.modified_ocr_data:
            return self.modified_ocr_data[filename]

        base_name = os.path.splitext(filename)[0]
        json_names = [base_name + ".json"]
        
        # Support PDF page 1
        if filename.lower().endswith('.pdf'):
            json_names.insert(0, base_name + "_page_1.json")

        possible_paths = []
        for jn in json_names:
            possible_paths.extend([
                os.path.join(self.image_dir, "output", "json", jn),
                os.path.join(self.image_dir, "output", jn),
                os.path.join("output", "json", jn),
                os.path.join("output", jn)
            ])
        
        ocr_data = []
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            ocr_data = data
                        elif isinstance(data, dict):
                            ocr_data = data.get('regions', []) or data.get('words', [])
                    break
                except Exception:
                    pass
        
        # Normalize
        for item in ocr_data:
            if 'box' not in item:
                if 'coordinates' in item:
                    coords = item['coordinates']
                    if coords:
                        xs = [p[0] for p in coords]
                        ys = [p[1] for p in coords]
                        item['box'] = [min(xs), min(ys), max(xs), max(ys)]
                    else:
                         item['box'] = [0, 0, 0, 0]
                else:
                    item['box'] = [0, 0, 0, 0]
        
        # Sort using the intelligent sorting logic
        ocr_data = sort_ocr_regions(ocr_data)
        
        return ocr_data

    def on_file_list_context_menu(self, position):
        menu = QMenu()
        reprocess_action = menu.addAction("强制重新OCR处理")
        action = menu.exec_(self.file_list.mapToGlobal(position))
        
        if action == reprocess_action:
            self.reprocess_selected_files()

    def reprocess_selected_files(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
            
        filenames = [item.text() for item in selected_items]
        
        dlg = GlassMessageDialog(
            self,
            title="确认",
            text=f"确定要重新处理选中的 {len(filenames)} 张图片吗？\n这将覆盖现有的识别结果。",
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg.exec_()
        if dlg.result_key() != "yes":
            return
            
        # Progress Dialog
        progress = QProgressDialog("正在初始化OCR引擎...", "取消", 0, len(filenames), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QCoreApplication.processEvents()
        
        try:
            # Init Engine (Lazy load)
            # Use shared config manager to ensure we use the latest settings (e.g. table split)
            ocr_engine = OcrEngine(config_manager=self.config_manager) 
            
            output_dir = os.path.join(self.image_dir, "output", "json")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            for i, filename in enumerate(filenames):
                if progress.wasCanceled():
                    break
                    
                progress.setLabelText(f"正在处理 ({i+1}/{len(filenames)}): {filename}")
                progress.setValue(i)
                QCoreApplication.processEvents() # Keep UI responsive
                
                image_path = os.path.join(self.image_dir, filename)
                try:
                    image = FileUtils.read_image(image_path)
                    if image is None:
                        print(f"Failed to read image: {image_path}")
                        continue
                    
                    # Run OCR
                    result = ocr_engine.process_image(image)
                    
                    # Save JSON
                    json_name = os.path.splitext(filename)[0] + ".json"
                    json_path = os.path.join(output_dir, json_name)
                    
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=4, ensure_ascii=False)
                        
                    # Clear cache if any
                    if filename in self.modified_ocr_data:
                        del self.modified_ocr_data[filename]
                        
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    # Continue to next
            
            progress.setValue(len(filenames))
            
            # Reload current if it was in the list
            current_row = self.file_list.currentRow()
            if current_row >= 0:
                current_filename = self.image_files[current_row]
                if current_filename in filenames:
                    self.load_ocr_result(current_filename)
                    
            dlg_done = GlassMessageDialog(
                self,
                title="完成",
                text="重新处理完成",
                buttons=[("ok", "确定")],
            )
            dlg_done.exec_()
            
        except Exception as e:
            dlg_err = GlassMessageDialog(
                self,
                title="错误",
                text=f"处理过程中发生错误: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err.exec_()
            import traceback
            traceback.print_exc()
        finally:
            progress.close()

    def on_ocr_data_changed(self, new_data):
        if not self.image_files: return
        
        current_row = self.file_list.currentRow()
        if current_row < 0: return
        
        filename = self.image_files[current_row]
        self.modified_ocr_data[filename] = new_data
        self.ocr_results = new_data
        
        # Refresh List View
        self.ocr_list_widget.blockSignals(True)
        self.ocr_list_widget.clear()
        for i, item in enumerate(self.ocr_results):
            text = item.get('text', '')
            if item.get('is_empty'): text = "<空>"
            list_item = QListWidgetItem(f"{i+1}. {text}")
            list_item.setData(Qt.UserRole, i)
            if item.get('is_empty'):
                list_item.setForeground(QBrush(QColor("gray")))
            self.ocr_list_widget.addItem(list_item)
        self.ocr_list_widget.blockSignals(False)
        
        # Update Image Viewer
        self.image_viewer_orig.set_ocr_results(self.ocr_results)

    def load_ocr_result(self, filename):
        self.ocr_results = self._get_ocr_data_for_file(filename)
        self.image_viewer_orig.set_ocr_results(self.ocr_results)
        
        # Populate List
        self.ocr_list_widget.clear()
        for i, item in enumerate(self.ocr_results):
            text = item.get('text', '')
            if item.get('is_empty'): text = "<空>"
            list_item = QListWidgetItem(f"{i+1}. {text}")
            list_item.setData(Qt.UserRole, i) # Store index
            if item.get('is_empty'):
                list_item.setForeground(QBrush(QColor("gray")))
            self.ocr_list_widget.addItem(list_item)
            
        # Update Card Sort Widget if in Table Mode (or just always update data)
        self.card_sort_widget.setup(self.available_fields, self.ocr_results)
        
        # Restore bindings if saved? (Not implemented yet, just clear for new image)
        # In a real app, we might check if this image was already bound.
        # For now, clear visual highlights
        self.image_viewer_orig.highlight_regions([])
        self._refresh_binding_table_status()

    def on_list_selection_changed(self):
        selected_items = self.ocr_list_widget.selectedItems()
        indices = [item.data(Qt.UserRole) for item in selected_items]
        
        # Highlight in Image
        self.image_viewer_orig.highlight_regions(indices)
        
        # Trigger binding update
        # We simulate "on_region_selected" from "list" source
        self.on_region_selected(indices, 'list')

    def _sync_schema_from_ui(self):
        """Sync self.available_fields from schema_table UI"""
        new_fields = []
        for row in range(self.schema_table.rowCount()):
            key = self.schema_table.item(row, 0).text()
            name = self.schema_table.item(row, 1).text()
            
            type_combo = self.schema_table.cellWidget(row, 2)
            ftype = type_combo.currentText() if type_combo else "TEXT"
            
            widget = self.schema_table.cellWidget(row, 3)
            is_pk = False
            if widget:
                ck = widget.findChild(QCheckBox)
                if ck: is_pk = ck.isChecked()
            
            new_fields.append((key, name, ftype, is_pk))
        
        self.available_fields = new_fields

    def run_batch_import(self):
        """Run batch import with strict schema control and sidecar tables"""
        if not self.db_path:
            dlg_db = GlassMessageDialog(
                self,
                title="错误",
                text="请先选择数据库文件",
                buttons=[("ok", "确定")],
            )
            dlg_db.exec_()
            return
            
        # 0. Sync Schema from UI (Critical Fix)
        self._sync_schema_from_ui()
            
        if not self.available_fields:
            dlg_fields = GlassMessageDialog(
                self,
                title="错误",
                text="请先定义字段",
                buttons=[("ok", "确定")],
            )
            dlg_fields.exec_()
            return
        
        # 1. Validate PK Strategy
        # Force re-check from UI widgets if alive
        try:
            if hasattr(self, 'radio_pk_custom') and self.radio_pk_custom is not None:
                if self.radio_pk_custom.isChecked():
                    self.is_auto_pk_selected = False
                elif hasattr(self, 'radio_pk_auto') and self.radio_pk_auto is not None:
                    if self.radio_pk_auto.isChecked():
                        self.is_auto_pk_selected = True
        except RuntimeError:
            pass # Trust existing state variable

        use_auto_pk = self.is_auto_pk_selected
        
        pk_fields = [f[0] for f in self.available_fields if len(f) > 3 and f[3]]
        
        # Smart Correction: If user checked PK fields but "Auto PK" is logically selected,
        # prioritize the explicit field selection.
        if use_auto_pk and pk_fields:
            print(f"[WARN] Conflict detected: Auto PK selected but fields {pk_fields} are marked as PK. Switching to Business PK.")
            use_auto_pk = False

        # Smart Type Correction: INTEGER PK -> TEXT
        # Explicitly notify user and update UI to prevent "datatype mismatch" (e.g. ID with 'X')
        converted_pks = []
        if not use_auto_pk:
            new_fields_list = []
            for row_idx, field in enumerate(self.available_fields):
                # field structure: (key, name, ftype, is_pk)
                key = field[0]
                ftype = field[2]
                is_pk = field[3] if len(field) > 3 else False
                
                if is_pk and ftype.upper() == "INTEGER":
                    # Convert logic
                    print(f"[INFO] Auto-converting PK '{key}' from INTEGER to TEXT")
                    new_fields_list.append((key, field[1], "TEXT", is_pk))
                    converted_pks.append(key)
                    
                    # Update UI Widget
                    try:
                        if hasattr(self, 'schema_table') and row_idx < self.schema_table.rowCount():
                            type_combo = self.schema_table.cellWidget(row_idx, 2)
                            if type_combo:
                                idx = type_combo.findText("TEXT") 
                                if idx >= 0:
                                    type_combo.setCurrentIndex(idx)
                    except Exception as e:
                        print(f"Error updating UI for {key}: {e}")
                else:
                    new_fields_list.append(field)
            
            if converted_pks:
                self.available_fields = new_fields_list
                dlg_type = GlassMessageDialog(
                    self,
                    title="类型自动修正",
                    text="检测到主键字段 {0} 的类型为 INTEGER。\n\n为了支持身份证号（包含'X'）及避免类型不匹配错误，\n系统已自动将其类型修正为 TEXT (文本)。".format(
                        ", ".join(converted_pks)
                    ),
                    buttons=[("ok", "确定")],
                )
                dlg_type.exec_()

        if not use_auto_pk and not pk_fields:
            dlg_pk = GlassMessageDialog(
                self,
                title="错误",
                text="选择了'指定业务字段'作为主键，但未勾选任何主键字段。\n请在字段列表中勾选唯一/主键。",
                buttons=[("ok", "确定")],
            )
            dlg_pk.exec_()
            return
            
        # Confirm
        mode_str = "表格模式 (一图多记录)" if self.radio_table.isChecked() else "单条模式 (一图一记录)"
        pk_str = "系统自增ID" if use_auto_pk else f"业务字段 ({', '.join(pk_fields)})"

        # Check for field name conflicts with System Auto ID
        if use_auto_pk:
             for f in self.available_fields:
                 if f[0].lower() == 'id':
                     dlg_conflict = GlassMessageDialog(
                         self,
                         title="错误",
                         text="字段名称冲突: 'id' 是系统自增主键的保留名称。\n请重命名您的字段 (例如 'custom_id', 'user_id') 或选择 '指定业务字段' 作为主键策略。",
                         buttons=[("ok", "确定")],
                     )
                     dlg_conflict.exec_()
                     return
        
        dlg_confirm = GlassMessageDialog(
            self,
            title="确认导入",
            text="即将批量导入 {0} 张图片。\n\n模式: {1}\n主键策略: {2}\n注意: 主表将只包含用户定义的字段，\n来源信息将存储在独立的附表中。".format(
                len(self.image_files), mode_str, pk_str
            ),
            buttons=[("yes", "确定"), ("no", "取消")],
        )
        dlg_confirm.exec_()
        if dlg_confirm.result_key() != "yes":
            return
        
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            table_name = self.combo_table_name.currentText().strip()
            if not table_name: table_name = "ocr_records"
            
            # --- 2. Check Existing Table ---
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            row = cursor.fetchone()
            if row:
                msg = (
                    "数据表 '{0}' 已存在。\n\n【追加数据】: 保留旧表，尝试插入数据（如果结构不一致可能会失败）。\n【重建表】: 删除旧表，应用新字段结构（推荐，可确保主键策略生效）。".format(
                        table_name
                    )
                )
                dlg_table = GlassMessageDialog(
                    self,
                    title="表已存在",
                    text=msg,
                    buttons=[("append", "追加数据"), ("recreate", "重建表")],
                )
                dlg_table.exec_()
                
                if dlg_table.result_key() == "recreate":
                    # Drop
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}_import_sources")
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}_source_map")
            
            # --- 3. Schema Generation ---
            
            # User Fields
            user_cols_def = []
            for field in self.available_fields:
                key = field[0]
                ftype = field[2] if len(field) > 2 else "TEXT"
                
                user_cols_def.append(f"{key} {ftype}")
            
            if use_auto_pk:
                # Auto ID PK
                create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(user_cols_def)})"
            else:
                # Custom PK
                pk_clause = f", PRIMARY KEY ({', '.join(pk_fields)})"
                create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(user_cols_def)}{pk_clause})"
            
            print(f"[DEBUG] Create Table SQL: {create_sql}") # Debug
            cursor.execute(create_sql)
            
            # --- 4. Sidecar Tables ---
            
            # Source Table: Stores file info
            source_table = f"{table_name}_import_sources"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {source_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Map Table: Links Source -> Record (via rowid)
            map_table = f"{table_name}_source_map"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {map_table} (
                    source_id INTEGER,
                    record_rowid INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Index for performance
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{map_table}_source ON {map_table}(source_id)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{map_table}_record ON {map_table}(record_rowid)")

            # --- 5. Prepare Data & Insert ---
            
            field_keys = [f[0] for f in self.available_fields]
            placeholders = ",".join(["?" for _ in field_keys])
            
            # We use INSERT OR REPLACE to handle conflicts (updates)
            # We use RETURNING rowid to get the ID for mapping
            insert_sql = f"INSERT OR REPLACE INTO {table_name} ({','.join(field_keys)}) VALUES ({placeholders}) RETURNING rowid"
            
            is_table_mode = self.radio_table.isChecked()
            total_inserted = 0
            
            from PyQt5.QtGui import QImageReader
            
            for filename in self.image_files:
                # 5.1 Register Source
                cursor.execute(f"INSERT OR IGNORE INTO {source_table} (filename) VALUES (?)", (filename,))
                # Get source_id
                cursor.execute(f"SELECT id FROM {source_table} WHERE filename=?", (filename,))
                source_row = cursor.fetchone()
                if not source_row: continue
                source_id = source_row[0]
                
                # 5.2 Prepare Records
                ocr_data = self._get_ocr_data_for_file(filename)
                records_data = [] # List of tuples
                
                if is_table_mode:
                    num_fields = len(field_keys)
                    if num_fields == 0: continue
                    
                    # Chunking logic
                    items = ocr_data
                    num_records = (len(items) + num_fields - 1) // num_fields
                    
                    for i in range(num_records):
                        start_idx = i * num_fields
                        current_chunk = items[start_idx : start_idx + num_fields]
                        
                        row_values = []
                        for j, key in enumerate(field_keys):
                            val = current_chunk[j].get('text', '') if j < len(current_chunk) else ""
                            row_values.append(val)
                        records_data.append(tuple(row_values))
                else:
                    # Single Mode
                    image_path = os.path.join(self.image_dir, filename)
                    reader = QImageReader(image_path)
                    size = reader.size()
                    w, h = size.width(), size.height()
                    
                    row_values = []
                    for key in field_keys:
                        binding = self.current_bindings.get(key)
                        val = ""
                        if binding and binding.get('bbox') and w > 0:
                            rx1, ry1, rx2, ry2 = binding['bbox']
                            ax1, ay1, ax2, ay2 = rx1*w, ry1*h, rx2*w, ry2*h
                            
                            items = [item for item in ocr_data if item.get('box')]
                            items = [item for item in items if ax1 <= (item['box'][0]+item['box'][2])/2 <= ax2 and ay1 <= (item['box'][1]+item['box'][3])/2 <= ay2]
                            items.sort(key=lambda x: (x['box'][1], x['box'][0]))
                            val = " ".join([item.get('text', '') for item in items])
                        row_values.append(val)
                    records_data.append(tuple(row_values))
                
                if not records_data: continue
                
                # 5.3 Insert Records & Map
                pk_indices = []
                if not use_auto_pk:
                    pk_indices = [i for i, k in enumerate(field_keys) if k in pk_fields]

                for record_tuple in records_data:
                    # Validation: Check if PKs are empty
                    if not use_auto_pk:
                        missing_pk = False
                        for idx in pk_indices:
                            val = record_tuple[idx]
                            if val is None or str(val).strip() == "":
                                missing_pk = True
                                break
                        if missing_pk:
                            print(f"[WARN] Skipping row in {filename}: Primary Key field is empty/invalid.")
                            continue

                    try:
                        cursor.execute(insert_sql, record_tuple)
                        row_id_row = cursor.fetchone()
                        if row_id_row:
                            row_id = row_id_row[0]
                            cursor.execute(f"INSERT INTO {map_table} (source_id, record_rowid) VALUES (?, ?)", (source_id, row_id))
                    except sqlite3.IntegrityError as e_int:
                        print(f"Integrity Error (Duplicate?): {e_int}")
                        # If INSERT OR REPLACE failed, it might be a strict constraint.
                        pass
                    except Exception as e_row:
                        print(f"Error inserting row for {filename}: {e_row}")
                        pass
                
                total_inserted += len(records_data)

            # --- 6. Save Dictionary Mappings ---
            self._save_current_schema_mappings_to_db(cursor)

            conn.commit()
            
            # Verify total rows to prove deduplication
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_rows = cursor.fetchone()[0]
            
            conn.close()
            
            dlg_done = GlassMessageDialog(
                self,
                title="导入完成",
                text="本次处理: {0} 条记录 (含更新/新增)\n当前库中总记录数: {1} 条\n\n说明: 如果'总记录数'未随导入成倍增加，说明去重(覆盖)逻辑已生效。\n数据已存入主表 '{2}'，来源信息存入 '{3}'。".format(
                    total_inserted, total_rows, table_name, source_table
                ),
                buttons=[("ok", "确定")],
            )
            dlg_done.exec_()
            
        except Exception as e:
            if conn: conn.close()
            import traceback
            traceback.print_exc()
            dlg_err = GlassMessageDialog(
                self,
                title="错误",
                text=f"导入失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err.exec_()
            print(f"Import error: {e}")

    # --- Database & Schema ---
    
    def open_dict_manager(self):
        """打开字典管理器"""
        if not self.db_path:
            dlg_db = GlassMessageDialog(
                self,
                title="提示",
                text="请先选择数据库文件",
                buttons=[("ok", "确定")],
            )
            dlg_db.exec_()
            return
            
        dialog = DictionaryManagerDialog(self.db_path, parent=self)
        dialog.exec_()
        
        # 刷新 Schema 表格中的显示名称
        self._refresh_schema_names_from_dict()

    def _load_dictionary_mappings(self):
        """Load mappings from DB to memory cache"""
        self.known_field_mappings = {}
        if not self.db_path or not os.path.exists(self.db_path): return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # Check if table exists first
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_sys_meta_dict'")
                if cursor.fetchone():
                    cursor.execute("SELECT key, value FROM _sys_meta_dict WHERE type='field'")
                    for k, v in cursor.fetchall():
                        self.known_field_mappings[k] = v
            except Exception:
                pass
            conn.close()
        except Exception as e:
            print(f"Error loading dictionary: {e}")

    def _save_current_schema_mappings_to_db(self, cursor=None):
        """Save current available_fields to DB dictionary"""
        if not self.db_path: return
        
        should_close = False
        if cursor is None:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                should_close = True
            except Exception as e:
                print(f"Error connecting to DB: {e}")
                return

        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS _sys_meta_dict (type TEXT, key TEXT, value TEXT, PRIMARY KEY(type, key))")
            
            updated_any = False
            for field in self.available_fields:
                key = field[0]
                name = field[1]
                if key and name and key != name:
                        cursor.execute("INSERT OR REPLACE INTO _sys_meta_dict (type, key, value) VALUES ('field', ?, ?)", (key, name))
                        self.known_field_mappings[key] = name
                        updated_any = True
            
            if should_close:
                conn.commit()
                conn.close()
            
            if updated_any:
                print("Dictionary mappings updated.")
                
        except Exception as e:
            print(f"Error saving dictionary mappings: {e}")
            if should_close and conn:
                conn.close()

    def on_schema_item_changed(self, item):
        # Auto-fill name if key changes
        if item.column() == 0: # Key column
            key = item.text().strip()
            if key in self.known_field_mappings:
                name = self.known_field_mappings[key]
                row = item.row()
                
                # Check if we should update name
                # If name is empty or same as key (default), update it.
                # If user already typed a custom name, maybe keep it? 
                # But usually mapping implies enforcement. Let's update it.
                self.schema_table.blockSignals(True)
                self.schema_table.setItem(row, 1, QTableWidgetItem(name))
                self.schema_table.blockSignals(False)

    def _refresh_schema_names_from_dict(self):
        self._load_dictionary_mappings()
        
        # Update Schema Table
        self.schema_table.blockSignals(True)
        for row in range(self.schema_table.rowCount()):
            key_item = self.schema_table.item(row, 0)
            if key_item:
                key = key_item.text()
                if key in self.known_field_mappings:
                    self.schema_table.setItem(row, 1, QTableWidgetItem(self.known_field_mappings[key]))
        self.schema_table.blockSignals(False)

    def browse_database(self):
        # Default to 'databases' directory in project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        db_dir = os.path.join(project_root, "databases")
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        options = QFileDialog.Options()
        options |= QFileDialog.DontConfirmOverwrite
        path, _ = QFileDialog.getSaveFileName(self, "选择数据库文件", db_dir, "SQLite Database (*.db)", options=options)
        if path:
            self.edit_db_path.setText(path)
            self.db_path = path
            
            # List tables if exists
            if os.path.exists(path):
                self._load_tables_from_db(path)

    def _load_tables_from_db(self, db_path):
        self.combo_table_name.clear()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if tables:
                self.combo_table_name.addItems(tables)
                # If ocr_records is in tables, select it, otherwise select first
                index = self.combo_table_name.findText("ocr_records")
                if index >= 0:
                    self.combo_table_name.setCurrentIndex(index)
                else:
                    self.combo_table_name.setCurrentIndex(0)
                
                # Try load schema for current
                self._try_load_schema_from_db(db_path)
            else:
                self.combo_table_name.setEditText("ocr_records")
        except Exception as e:
            print(f"Error listing tables: {e}")
            self.combo_table_name.setEditText("ocr_records")

    def on_table_selected(self):
        if not self.db_path or not os.path.exists(self.db_path):
            return
        self._try_load_schema_from_db(self.db_path)

    def _try_load_schema_from_db(self, db_path):
        table_name = self.combo_table_name.currentText().strip()
        if not table_name: return
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                conn.close()
                return # Table doesn't exist, nothing to load
            
            # Get schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # Load Mappings
            mappings = {}
            try:
                cursor.execute("SELECT key, value FROM _sys_meta_dict WHERE type='field'")
                for k, v in cursor.fetchall():
                    mappings[k] = v
            except:
                pass

            conn.close()
            
            if not columns:
                return

            new_fields = []
            system_fields = ['id', 'filename', 'created_at']
            
            found_fields = False
            for col in columns:
                # col: (cid, name, type, notnull, dflt_value, pk)
                name = col[1]
                ftype = col[2]
                pk = col[5]
                
                if name in system_fields:
                    continue
                    
                # Map DB type to UI type
                ui_type = "TEXT"
                if "INT" in ftype.upper(): ui_type = "INTEGER"
                elif "REAL" in ftype.upper() or "FLOAT" in ftype.upper(): ui_type = "REAL"
                elif "BLOB" in ftype.upper(): ui_type = "BLOB"
                
                is_pk = (pk > 0)
                
                # Use mapping if available, otherwise use key
                display_name = mappings.get(name, name)
                
                new_fields.append((name, display_name, ui_type, is_pk))
                found_fields = True
            
            if found_fields:
                self._populate_schema_table(new_fields)
                # Automatically loaded without prompt

        except Exception as e:
            print(f"Error loading schema: {e}")
            # Non-critical, just ignore or log

    def _create_type_combo(self, current_text):
        combo = QComboBox()
        combo.addItems(["TEXT", "INTEGER", "REAL", "BLOB"])
        index = combo.findText(current_text)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(0) # Default to TEXT
        return combo

    def _update_schema_ui_state(self):
        # Fix: Check if widget exists before access
        if not hasattr(self, 'radio_pk_custom') or self.radio_pk_custom is None:
            return
        try:
            is_custom_pk = self.radio_pk_custom.isChecked()
            # Update state variable for robustness
            self.is_auto_pk_selected = not is_custom_pk
        except RuntimeError:
            return

        for row in range(self.schema_table.rowCount()):
            widget = self.schema_table.cellWidget(row, 3)
            if widget:
                ck = widget.findChild(QCheckBox)
                if ck:
                    ck.setEnabled(is_custom_pk)
                    if not is_custom_pk:
                        ck.setChecked(False)

    def _on_pk_checkbox_toggled(self, row, checked):
        """
        保证“唯一/主键”列在业务主键模式下始终只有一行被选中
        """
        try:
            if not checked:
                return

            # 无论当前主键策略如何，都强制保证整表只有一个勾选
            for r in range(self.schema_table.rowCount()):
                if r == row:
                    continue
                widget = self.schema_table.cellWidget(r, 3)
                if not widget:
                    continue
                other_ck = widget.findChild(QCheckBox)
                if other_ck and other_ck.isChecked():
                    other_ck.blockSignals(True)
                    other_ck.setChecked(False)
                    other_ck.blockSignals(False)
        except RuntimeError:
            # 对话框销毁后 Qt 对象可能已经被删除，直接忽略迟到的信号
            return

    def _populate_schema_table(self, fields):
        # 1. Determine PK strategy from fields to prevent UI inconsistency
        has_pk = any(len(f) > 3 and f[3] for f in fields)
        
        # Update Radio Button (if exists) to match data
        # This prevents _update_schema_ui_state from wiping PK checks if Auto was default
        if hasattr(self, 'radio_pk_custom') and self.radio_pk_custom:
            try:
                self.bg_pk.blockSignals(True) # Block group signals
                if has_pk:
                    self.radio_pk_custom.setChecked(True)
                else:
                    self.radio_pk_auto.setChecked(True)
                self.bg_pk.blockSignals(False)
            except RuntimeError:
                pass

        self.schema_table.setRowCount(0)
        for field in fields:
            # Handle 2-tuple, 3-tuple, 4-tuple
            key = field[0]
            name = field[1]
            ftype = field[2] if len(field) > 2 else "TEXT"
            is_pk = field[3] if len(field) > 3 else False
            
            row = self.schema_table.rowCount()
            self.schema_table.insertRow(row)
            self.schema_table.setItem(row, 0, QTableWidgetItem(key))
            self.schema_table.setItem(row, 1, QTableWidgetItem(name))
            self.schema_table.setCellWidget(row, 2, self._create_type_combo(ftype))
            
            # PK Checkbox
            ck = QCheckBox()
            ck.setChecked(is_pk)
            ck.toggled.connect(lambda checked, r=row: self._on_pk_checkbox_toggled(r, checked))
            # Center align checkbox
            widget = QWidget()
            h = QHBoxLayout(widget)
            h.setAlignment(Qt.AlignCenter)
            h.setContentsMargins(0,0,0,0)
            h.addWidget(ck)
            self.schema_table.setCellWidget(row, 3, widget)
        
        self._update_schema_ui_state()

    def add_schema_field(self):
        row = self.schema_table.rowCount()
        self.schema_table.insertRow(row)
        self.schema_table.setItem(row, 0, QTableWidgetItem("new_field"))
        self.schema_table.setItem(row, 1, QTableWidgetItem("新字段"))
        self.schema_table.setCellWidget(row, 2, self._create_type_combo("TEXT"))
        
        ck = QCheckBox()
        ck.toggled.connect(lambda checked, r=row: self._on_pk_checkbox_toggled(r, checked))
        widget = QWidget()
        h = QHBoxLayout(widget)
        h.setAlignment(Qt.AlignCenter)
        h.setContentsMargins(0,0,0,0)
        h.addWidget(ck)
        self.schema_table.setCellWidget(row, 3, widget)
        
        self._update_schema_ui_state()

    def remove_schema_field(self):
        row = self.schema_table.currentRow()
        if row >= 0:
            self.schema_table.removeRow(row)

    def save_field_template(self):
        dlg_name = TemplateNameDialog(self, title="保存模板", label_text="请输入模板名称:")
        if dlg_name.exec_() != QDialog.Accepted:
            return
        name = dlg_name.get_text()
            
        template_path = os.path.join(os.getcwd(), "field_templates.json")
        
        # Load existing
        templates = {}
        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    templates = json.load(f)
            except Exception:
                pass # Overwrite if corrupt
        
        # Save
        templates[name.strip()] = self._get_schema_from_table()
        
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(templates, f, indent=2, ensure_ascii=False)
            dlg_ok = GlassMessageDialog(
                self,
                title="成功",
                text=f"模板 '{name}' 已保存",
                buttons=[("ok", "确定")],
            )
            dlg_ok.exec_()
        except Exception as e:
            dlg_err = GlassMessageDialog(
                self,
                title="错误",
                text=f"保存模板失败: {e}",
                buttons=[("ok", "确定")],
            )
            dlg_err.exec_()

    def load_field_template(self):
        dialog = TemplateManagerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            fields = dialog.selected_template
            if fields:
                self._populate_schema_table(fields)
                dlg_loaded = GlassMessageDialog(
                    self,
                    title="成功",
                    text="模板已加载，请点击“应用字段定义”生效",
                    buttons=[("ok", "确定")],
                )
                dlg_loaded.exec_()

    def apply_schema(self):
        # Read table and update available_fields
        new_fields = self._get_schema_from_table()
            
        self.available_fields = new_fields
        self._rebuild_binding_table()
        
        # Update Card View if active
        if self.radio_table.isChecked():
             self.card_sort_widget.setup(self.available_fields, self.ocr_results)
             
        self.tabs.setCurrentIndex(1) # Switch to binding tab
        dlg_schema = GlassMessageDialog(
            self,
            title="提示",
            text="字段定义已更新",
            buttons=[("ok", "确定")],
        )
        dlg_schema.exec_()

    def _get_schema_from_table(self):
        fields = []
        for row in range(self.schema_table.rowCount()):
            key_item = self.schema_table.item(row, 0)
            name_item = self.schema_table.item(row, 1)
            
            if not key_item or not name_item: continue
            
            key = key_item.text()
            name = name_item.text()
            
            # Type
            type_combo = self.schema_table.cellWidget(row, 2)
            ftype = "TEXT"
            if type_combo and isinstance(type_combo, QComboBox):
                ftype = type_combo.currentText()
            else:
                item = self.schema_table.item(row, 2)
                if item: ftype = item.text()
            
            # PK
            widget = self.schema_table.cellWidget(row, 3)
            is_pk = False
            if widget:
                ck = widget.findChild(QCheckBox)
                if ck: is_pk = ck.isChecked()
            
            fields.append((key, name, ftype, is_pk))
        return fields


    def on_mode_changed(self):
        if self.radio_table.isChecked():
            self.view_stack.setCurrentIndex(1)
            self.card_sort_widget.setup(self.available_fields, self.ocr_results)
        else:
            self.view_stack.setCurrentIndex(0)

    # --- Binding Logic ---

    def _rebuild_binding_table(self):
        self.binding_table.setRowCount(0)
        self.binding_table.setRowCount(len(self.available_fields))
        
        for i, field in enumerate(self.available_fields):
            key, name = field[0], field[1]
            # Name
            item_name = QTableWidgetItem(f"{name} ({key})")
            item_name.setData(Qt.UserRole, key)
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
            self.binding_table.setItem(i, 0, item_name)
            
            # Value
            val_text = "未绑定"
            if key in self.current_bindings:
                val_text = self.current_bindings[key].get('preview', '已绑定')
            item_val = QTableWidgetItem(val_text)
            if key not in self.current_bindings:
                # 未绑定时使用略浅前景色区分状态，背景交给系统主题
                item_val.setForeground(QBrush(QColor(150, 150, 150)))
            
            item_val.setFlags(item_val.flags() & ~Qt.ItemIsEditable)
            self.binding_table.setItem(i, 1, item_val)

    def on_binding_table_clicked(self, row, col):
        item = self.binding_table.item(row, 0)
        if not item: return
        
        field_key = item.data(Qt.UserRole)
        self.current_target_field = field_key
        
        # Highlight existing binding
        binding = self.current_bindings.get(field_key)
        indices = binding.get('indices', []) if binding else []
        self.image_viewer_orig.highlight_regions(indices)
        
        # Sync List Selection
        self.ocr_list_widget.blockSignals(True)
        self.ocr_list_widget.clearSelection()
        for i in range(self.ocr_list_widget.count()):
            list_item = self.ocr_list_widget.item(i)
            if list_item.data(Qt.UserRole) in indices:
                list_item.setSelected(True)
        self.ocr_list_widget.blockSignals(False)

    def on_region_selected(self, indices, source):
        """
        source: 'orig' or 'list'
        """
        if not self.current_target_field:
            return
        
        # Sync highlight
        if source == 'orig':
            # Image -> List
            self.ocr_list_widget.blockSignals(True)
            self.ocr_list_widget.clearSelection()
            for i in range(self.ocr_list_widget.count()):
                list_item = self.ocr_list_widget.item(i)
                if list_item.data(Qt.UserRole) in indices:
                    list_item.setSelected(True)
                    self.ocr_list_widget.scrollToItem(list_item)
            self.ocr_list_widget.blockSignals(False)
        else:
            # List -> Image
            # Already handled in on_list_selection_changed which calls this
            self.image_viewer_orig.highlight_regions(indices)
            
        if not indices: return
        
        # Logic to save binding (Same as before)
        field_key = self.current_target_field
        
        # Get Texts & Compute BBox
        texts = []
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        has_valid_box = False
        
        for idx in indices:
            if 0 <= idx < len(self.ocr_results):
                item = self.ocr_results[idx]
                texts.append(item.get('text', ''))
                
                box = item.get('box')
                if box:
                    has_valid_box = True
                    min_x = min(min_x, box[0])
                    min_y = min(min_y, box[1])
                    max_x = max(max_x, box[2])
                    max_y = max(max_y, box[3])
                    
        display_text = " ".join(texts)
        
        # Compute BBox (Relative)
        bbox = None
        if has_valid_box and self.image_viewer_orig.image_size:
            w, h = self.image_viewer_orig.image_size
            if w > 0 and h > 0:
                bbox = [min_x / w, min_y / h, max_x / w, max_y / h]
        
        self.current_bindings[field_key] = {
            "indices": indices,
            "preview": display_text,
            "bbox": bbox
        }
        
        self._update_binding_row(field_key, display_text)
        self._update_viewer_bound_state()
        
        # Only auto-advance if selection is done (this logic might be tricky with multi-select)
        # Maybe we don't auto-advance on every click, but it's fine for now.
        # Actually, let's NOT auto-advance in list mode immediately, because user might select multiple lines.
        # But for 'orig' (box selection), it's usually one action.
        # Let's keep auto-advance for now but maybe we need a "Confirm" or just let user click next.
        # The user didn't complain about auto-advance.
        if source == 'orig': 
             self._auto_advance_row()

    def _update_binding_row(self, field_key, text):
        for row in range(self.binding_table.rowCount()):
            item = self.binding_table.item(row, 0)
            if item.data(Qt.UserRole) == field_key:
                val_item = self.binding_table.item(row, 1)
                val_item.setText(text)
                # 使用系统配色，不再强制黑字/浅绿底
                break

    def _update_viewer_bound_state(self):
        all_bound = set()
        for k, v in self.current_bindings.items():
            all_bound.update(v.get('indices', []))
        self.image_viewer_orig.bound_indices = all_bound
        self.image_viewer_orig.update()
        # Update List colors?
        # Could colorize list items that are bound.
        for i in range(self.ocr_list_widget.count()):
            item = self.ocr_list_widget.item(i)
            idx = item.data(Qt.UserRole)
            if idx in all_bound:
                # 轻微高亮已绑定项目，这里仍使用浅色以便在深色背景下保持对比
                item.setBackground(QColor(230, 255, 230))
            else:
                # 交给系统主题控制未绑定项背景
                item.setBackground(QColor())

    def _auto_advance_row(self):
        current = self.binding_table.currentRow()
        if current < self.binding_table.rowCount() - 1:
            next_row = current + 1
            self.binding_table.selectRow(next_row)
            self.on_binding_table_clicked(next_row, 0)

    def clear_current_binding(self):
        if not self.current_target_field: return
        if self.current_target_field in self.current_bindings:
            del self.current_bindings[self.current_target_field]
            self._rebuild_binding_table() # Brute force refresh
            self._update_viewer_bound_state()
            self.image_viewer_orig.highlight_regions([])
            self.ocr_list_widget.clearSelection()

    def _refresh_binding_table_status(self):
        # Refresh UI based on current_bindings (which is per image, but here we reset it usually)
        # Ideally, we should save bindings per image.
        # For now, just reset bindings when image changes as per simple workflow
        self.current_bindings = {}
        self._rebuild_binding_table()

    def select_aligned(self, direction):
        # Trigger on active viewer? 
        # Default to orig viewer for calculation
        if not self.current_target_field: return
        binding = self.current_bindings.get(self.current_target_field)
        if not binding or not binding['indices']:
             dlg_ref = GlassMessageDialog(
                 self,
                 title="提示",
                 text="请先选择一个参考框",
                 buttons=[("ok", "确定")],
             )
             dlg_ref.exec_()
             return
        
        ref_idx = binding['indices'][0]
        # Calculate on orig viewer
        new_indices = self.image_viewer_orig.select_aligned_regions(ref_idx, direction)
        
        # Sync to list
        self.ocr_list_widget.blockSignals(True)
        self.ocr_list_widget.clearSelection()
        for i in range(self.ocr_list_widget.count()):
            list_item = self.ocr_list_widget.item(i)
            if list_item.data(Qt.UserRole) in new_indices:
                list_item.setSelected(True)
        self.ocr_list_widget.blockSignals(False)
        
        # Trigger update
        self.on_region_selected(new_indices, 'orig')
        # Yes, lines 104-105 in ImageViewer calls selection_callback.

    def save_config(self):
        # Save Template
        name, ok = QInputDialog.getText(self, "保存配置", "请输入配置名称:")
        if ok and name:
            config = {
                "name": name,
                "db_path": self.db_path,
                "table_name": self.table_name,
                "fields": self.available_fields,
                "mode": "table" if self.radio_table.isChecked() else "single",
                "bindings": self.current_bindings # Note: This is only for ONE image currently. 
                # Template usually saves the "Rules" or "Relative Positions".
                # But here we are just saving the schema and maybe the binding definition?
                # For "Visual Binding", we usually define "Zones".
                # Since we are using OCR indices, it's specific to this image.
                # However, the user asked for "Import Database".
                # So this button should probably be "Start Import" or "Save Template".
                # Let's assume it returns the Schema and Binding Logic.
            }
            self.config_saved.emit(config)
            dlg_saved = GlassMessageDialog(
                self,
                title="成功",
                text="配置已保存",
                buttons=[("ok", "确定")],
            )
            dlg_saved.exec_()
            self.accept()
