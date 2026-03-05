# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：卡片式字段排布与拖拽组件，用于将识别文本块映射到结构化字段
# - 核心实现：可拖拽标签、卡槽与上下文菜单，支持拆分/合并/插入空项
# - 关联关系：嵌入 FieldBindingDialog 等对话框，辅助结构化结果整理
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QFrame, QGridLayout, QApplication, QMenu, QAction,
                             QDialog, QPlainTextEdit, QPushButton, QShortcut,
                             QLayout, QSizePolicy, QStyle)
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QColor, QFontMetrics, QCursor

class DraggableLabel(QLabel):
    """
    可拖拽的标签
    """
    def __init__(self, text, parent=None, original_index=-1):
        super().__init__(text, parent)
        self.original_index = original_index
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLabel:hover {
                background-color: #4d4d4d;
                border-color: #777;
            }
        """)
        self.setAttribute(Qt.WA_DeleteOnClose)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        
        # 传递数据：文本内容和原始索引
        mime_data.setText(self.text())
        mime_data.setData("application/x-original-index", str(self.original_index).encode('utf-8'))
        
        drag.setMimeData(mime_data)

        # 创建拖拽时的视觉反馈
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        # 执行拖拽
        drop_action = drag.exec_(Qt.MoveAction | Qt.CopyAction)
        
        # 如果是移动操作且被接受，可以在这里做一些清理工作（如果是从源列表拖出的）
        # 但实际上我们在 dropEvent 中处理数据移动

class CardSlot(QFrame):
    """
    卡片插槽（接收拖拽）
    """
    content_changed = pyqtSignal() # 当插槽内容变化时触发
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Sunken | QFrame.StyledPanel)
        self.setAcceptDrops(True)
        self.setMinimumHeight(40)
        self.setStyleSheet("""
            CardSlot {
                background-color: #2d2d2d;
                border: 1px dashed #555;
                border-radius: 4px;
            }
            CardSlot[drag_hover="true"] {
                background-color: #3d3d4d;
                border-color: #88aaff;
            }
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        
        # 内部数据
        self.items = [] # list of dict: {'text': str, 'original_index': int}

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setProperty("drag_hover", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("drag_hover", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("drag_hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        
        text = event.mimeData().text()
        original_index = -1
        if event.mimeData().hasFormat("application/x-original-index"):
            try:
                original_index = int(event.mimeData().data("application/x-original-index").data().decode('utf-8'))
            except:
                pass
                
        # 添加到插槽
        self.add_item(text, original_index)
        event.acceptProposedAction()
        
        # 通知源可能需要移除（如果是移动操作）
        # 这里简化处理：通常源列表是只读的或者是“待选池”，如果是从另一个插槽移过来的，需要处理
        # 实际逻辑由 CardSortWidget 统一协调

    def add_item(self, text, original_index=-1):
        self.items.append({'text': text, 'original_index': original_index})
        self._refresh_ui()
        self.content_changed.emit()

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._refresh_ui()
            self.content_changed.emit()
            
    def clear_items(self):
        self.items = []
        self._refresh_ui()
        self.content_changed.emit()

    def get_text(self):
        return "".join([item['text'] for item in self.items])

    def _refresh_ui(self):
        # 清除现有控件
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 重新添加标签
        for i, item_data in enumerate(self.items):
            lbl = DraggableLabel(item_data['text'], self, item_data['original_index'])
            # 允许从插槽中再次拖出（或者右键删除）
            lbl.setContextMenuPolicy(Qt.CustomContextMenu)
            lbl.customContextMenuRequested.connect(lambda pos, idx=i: self._show_context_menu(pos, idx))
            self.layout.addWidget(lbl)
            
        self.layout.addStretch()

    def _show_context_menu(self, pos, index):
        menu = QMenu(self)
        delete_action = QAction("移除", self)
        delete_action.triggered.connect(lambda: self.remove_item(index))
        menu.addAction(delete_action)
        menu.exec_(self.mapToGlobal(pos))

class CardSortWidget(QWidget):
    """
    卡片排序与字段绑定组件
    """
    def __init__(self, text_blocks, field_names=None, parent=None):
        super().__init__(parent)
        self.text_blocks = text_blocks # list of str
        self.field_names = field_names or []
        
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        
        # 左侧：待选文本池
        source_frame = QFrame()
        source_layout = QVBoxLayout(source_frame)
        source_layout.addWidget(QLabel("待选文本 (拖拽到右侧)"))
        
        self.source_area = QScrollArea()
        self.source_area.setWidgetResizable(True)
        self.source_content = QWidget()
        self.source_grid = QGridLayout(self.source_content)
        self.source_grid.setAlignment(Qt.AlignTop)
        
        # 填充待选文本
        for i, text in enumerate(self.text_blocks):
            lbl = DraggableLabel(text, original_index=i)
            row = i // 2
            col = i % 2
            self.source_grid.addWidget(lbl, row, col)
            
        self.source_area.setWidget(self.source_content)
        source_layout.addWidget(self.source_area)
        
        # 右侧：字段插槽
        target_frame = QFrame()
        target_layout = QVBoxLayout(target_frame)
        target_layout.addWidget(QLabel("字段映射"))
        
        self.target_area = QScrollArea()
        self.target_area.setWidgetResizable(True)
        self.target_content = QWidget()
        self.target_form = QGridLayout(self.target_content)
        self.target_form.setAlignment(Qt.AlignTop)
        
        self.slots = {} # field_name -> CardSlot
        
        for i, field in enumerate(self.field_names):
            lbl = QLabel(f"{field}:")
            slot = CardSlot()
            self.slots[field] = slot
            
            self.target_form.addWidget(lbl, i, 0)
            self.target_form.addWidget(slot, i, 1)
            
        self.target_area.setWidget(self.target_content)
        target_layout.addWidget(self.target_area)
        
        # 布局
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(source_frame)
        splitter.addWidget(target_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)

    def get_result(self):
        """
        获取当前绑定结果
        Returns: dict {field: text}
        """
        result = {}
        for field, slot in self.slots.items():
            result[field] = slot.get_text()
        return result
