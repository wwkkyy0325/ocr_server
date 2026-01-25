from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QFrame, QGridLayout, QApplication, QMenu, QAction,
                             QDialog, QPlainTextEdit, QPushButton, QMessageBox, QShortcut,
                             QLayout, QSizePolicy, QStyle)
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QColor, QBrush, QPen, QKeySequence
import copy

class SplitEditDialog(QDialog):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("拆分/编辑结果")
        self.resize(400, 300)
        self.layout = QVBoxLayout(self)
        
        self.label = QLabel("编辑文本 (每一行将拆分为一个独立结果):")
        self.layout.addWidget(self.label)
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(text)
        self.layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)
        
    def get_lines(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return []
        return [line.strip() for line in text.split('\n') if line.strip()]

class DraggableLabel(QLabel):
    def __init__(self, text, index, parent=None):
        super().__init__(text, parent)
        self.index = index  # Index in the display list
        self.setStyleSheet("background-color: #e6f3ff; border: 1px solid #99ccff; border-radius: 4px; padding: 4px;")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWordWrap(True)

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
        mime_data.setText(self.text())
        mime_data.setData("application/x-ocr-item-index", str(self.index).encode('utf-8'))
        
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        self.setVisible(False)
        drop_action = drag.exec_(Qt.MoveAction)
        
        try:
            if drop_action != Qt.MoveAction:
                self.setVisible(True)
        except RuntimeError:
            pass # Widget deleted during drag (e.g. dropped and re-rendered)

class CardSlot(QFrame):
    itemDropped = pyqtSignal(int, object) # source_index, target_slot
    insertEmptyRequested = pyqtSignal(object) # target_slot
    deleteItemRequested = pyqtSignal(object) # target_slot
    splitItemRequested = pyqtSignal(object) # target_slot
    mergeNextRequested = pyqtSignal(object) # target_slot

    def __init__(self, field_key, field_name, parent=None):
        super().__init__(parent)
        self.field_key = field_key
        self.field_name = field_name
        self.current_item = None
        
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: #f9f9f9; border: 1px dashed #cccccc; border-radius: 4px;")
        self.setMinimumHeight(40)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        
        # Field Label (Tiny)
        self.lbl_name = QLabel(field_name)
        self.lbl_name.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent;")
        self.layout.addWidget(self.lbl_name)

    def set_item(self, item_widget):
        if self.current_item:
            self.layout.removeWidget(self.current_item)
            self.current_item.deleteLater()
            self.current_item = None
            
        if item_widget:
            self.current_item = item_widget
            self.layout.addWidget(item_widget)
            item_widget.setVisible(True)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                color: #000000;
                border: 1px solid transparent;
            }
            QMenu::item:selected {
                background-color: #e6f3ff;
                border: 1px solid #0078d7;
                border-radius: 4px;
                color: #000000;
            }
        """)
        
        action_insert = QAction("在此处插入空值", self)
        action_insert.triggered.connect(lambda: self.insertEmptyRequested.emit(self))
        menu.addAction(action_insert)
        
        if self.current_item:
            menu.addSeparator()
            
            action_split = QAction("拆分/编辑结果...", self)
            action_split.triggered.connect(lambda: self.splitItemRequested.emit(self))
            menu.addAction(action_split)
            
            action_merge = QAction("向下合并 (与后一项合并)", self)
            action_merge.triggered.connect(lambda: self.mergeNextRequested.emit(self))
            menu.addAction(action_merge)
            
            menu.addSeparator()
            
            action_delete = QAction("删除该项并前移后续内容", self)
            action_delete.triggered.connect(lambda: self.deleteItemRequested.emit(self))
            menu.addAction(action_delete)
            
        menu.exec_(event.globalPos())

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-ocr-item-index"):
            event.accept()
            self.setStyleSheet("background-color: #e0e0e0; border: 2px solid #666666; border-radius: 4px;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: #f9f9f9; border: 1px dashed #cccccc; border-radius: 4px;")

    def dropEvent(self, event):
        self.setStyleSheet("background-color: #f9f9f9; border: 1px dashed #cccccc; border-radius: 4px;")
        if event.mimeData().hasFormat("application/x-ocr-item-index"):
            index_bytes = event.mimeData().data("application/x-ocr-item-index")
            source_index = int(index_bytes.data().decode('utf-8'))
            self.itemDropped.emit(source_index, self)
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hSpacing=-1, vSpacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._item_list = []
        self._h_spacing = hSpacing
        self._v_spacing = vSpacing

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def horizontalSpacing(self):
        if self._h_spacing >= 0:
            return self._h_spacing
        else:
            return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._v_spacing >= 0:
            return self._v_spacing
        else:
            return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.horizontalSpacing()

        for item in self._item_list:
            wid = item.widget()
            space_x = spacing
            space_y = self.verticalSpacing()
            if wid:
                style = wid.style()
                layout_spacing_x = style.layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
                layout_spacing_y = style.layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
                if space_x == -1: space_x = layout_spacing_x
                if space_y == -1: space_y = layout_spacing_y
            
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()
        
    def smartSpacing(self, pm):
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()

class RecordCard(QFrame):
    def __init__(self, record_index, fields, parent=None):
        super().__init__(parent)
        self.record_index = record_index
        self.fields = fields
        self.slots = {} # key -> CardSlot
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setFixedWidth(180) # Fixed width instead of adaptive
        self.setStyleSheet("""
            RecordCard {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        header = QLabel(f"Record {record_index + 1}")
        header.setStyleSheet("font-weight: bold; color: #2c3e50; border: none;")
        layout.addWidget(header)
        
        for field in fields:
            key, name = field[0], field[1]
            slot = CardSlot(key, name)
            layout.addWidget(slot)
            self.slots[key] = slot

class CardSortWidget(QWidget):
    data_changed = pyqtSignal(list) # Emits new list of items
    
    def __init__(self, parent=None, cols=3):
        super().__init__(parent)
        # self.cols = cols # Deprecated in favor of FlowLayout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #f0f0f0;")
        
        self.container = QWidget()
        self.flow_layout = FlowLayout(self.container, margin=10, hSpacing=10, vSpacing=10)
        # self.flow_layout.setAlignment(Qt.AlignTop) # FlowLayout handles this
        
        self.scroll_area.setWidget(self.container)
        self.layout.addWidget(self.scroll_area)
        
        self.cards = [] 
        self.items = [] # Working list of dicts
        self.fields = []
        
        # Undo/Redo Stacks
        self.undo_stack = []
        self.redo_stack = []
        
        # Shortcuts
        self.undo_shortcut = QShortcut(QKeySequence.Undo, self)
        self.undo_shortcut.activated.connect(self.undo)
        
        self.redo_shortcut = QShortcut(QKeySequence.Redo, self)
        self.redo_shortcut.activated.connect(self.redo)

    def _save_state(self):
        """Save current state to undo stack"""
        self.undo_stack.append(copy.deepcopy(self.items))
        self.redo_stack.clear() # Clear redo stack on new action

    def undo(self):
        """Undo last action"""
        if not self.undo_stack:
            return
            
        # Save current state to redo stack
        self.redo_stack.append(copy.deepcopy(self.items))
        
        # Restore state
        self.items = self.undo_stack.pop()
        self._render_cards()
        self.data_changed.emit(self.items)
        
    def redo(self):
        """Redo last undone action"""
        if not self.redo_stack:
            return
            
        # Save current state to undo stack
        self.undo_stack.append(copy.deepcopy(self.items))
        
        # Restore state
        self.items = self.redo_stack.pop()
        self._render_cards()
        self.data_changed.emit(self.items)

    def setup(self, fields, ocr_data):
        self.fields = fields
        # Create a working copy
        self.items = list(ocr_data)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._render_cards()

    def set_columns(self, cols):
        """Set number of columns and re-render"""
        # FlowLayout handles columns adaptively, so this is now ignored or forces re-layout
        # if cols != self.cols:
        #    self.cols = cols
        self._render_cards()

    def _render_cards(self):
        # Clear existing
        for i in reversed(range(self.flow_layout.count())): 
            widget = self.flow_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
        self.cards = []
        
        if not self.fields:
            return

        field_count = len(self.fields)
        # Calculate needed records based on current items
        num_records = (len(self.items) + field_count - 1) // field_count
        if num_records == 0: num_records = 1
        
        # cols = self.cols # Unused in FlowLayout
        
        for i in range(num_records):
            card = RecordCard(i, self.fields)
            # row = i // cols
            # col = i % cols
            # self.flow_layout.addWidget(card, row, col)
            self.flow_layout.addWidget(card)
            self.cards.append(card)
            
            # Populate Slots
            start_idx = i * field_count
            for j, field in enumerate(self.fields):
                idx = start_idx + j
                key = field[0]
                slot = card.slots[key]
                
                # Connect signals
                slot.itemDropped.connect(self.handle_drop)
                slot.insertEmptyRequested.connect(self.handle_insert_empty)
                slot.deleteItemRequested.connect(self.handle_delete_item)
                slot.splitItemRequested.connect(self.handle_split_item)
                slot.mergeNextRequested.connect(self.handle_merge_next)
                
                if idx < len(self.items):
                    item = self.items[idx]
                    text = item.get('text', '')
                    if item.get('is_empty'):
                        text = "<空>"
                        
                    lbl = DraggableLabel(text, idx)
                    if item.get('is_empty'):
                        lbl.setStyleSheet("background-color: #ffe6e6; border: 1px dashed #ff9999; border-radius: 4px; padding: 4px; color: #888;")
                    
                    slot.set_item(lbl)

    def _find_slot_index(self, target_slot):
        for i, card in enumerate(self.cards):
            for key, slot in card.slots.items():
                if slot == target_slot:
                    field_idx = 0
                    for f_idx, f in enumerate(self.fields):
                        if f[0] == key:
                            field_idx = f_idx
                            break
                    return i * len(self.fields) + field_idx
        return -1

    def handle_delete_item(self, target_slot):
        target_idx = self._find_slot_index(target_slot)
        if target_idx != -1 and target_idx < len(self.items):
            self._save_state()
            self.items.pop(target_idx)
            self._render_cards()
            self.data_changed.emit(self.items)

    def handle_insert_empty(self, target_slot):
        # Determine index based on slot position
        target_idx = self._find_slot_index(target_slot)
            
        if target_idx != -1:
            self._save_state()
            # Insert Empty at this index
            empty_item = {'text': '', 'is_empty': True, 'box': None}
            self.items.insert(target_idx, empty_item)
            
            self._render_cards()
            self.data_changed.emit(self.items)

    def handle_split_item(self, target_slot):
        target_idx = self._find_slot_index(target_slot)
        if target_idx == -1 or target_idx >= len(self.items):
            return
            
        item = self.items[target_idx]
        text = item.get('text', '')
        
        dialog = SplitEditDialog(text, self)
        if dialog.exec_() == QDialog.Accepted:
            new_lines = dialog.get_lines()
            if not new_lines:
                return 
            
            self._save_state()
                
            # Calculate new boxes
            original_box = item.get('box')
            
            new_items = []
            
            # Simple length-based box splitting
            total_len = sum(len(line) for line in new_lines)
            if total_len == 0: total_len = 1 
            
            if original_box:
                x1, y1, x2, y2 = original_box
                total_width = x2 - x1
                current_x = x1
                
                for line in new_lines:
                    ratio = len(line) / total_len
                    width = total_width * ratio
                    new_box = [int(current_x), y1, int(current_x + width), y2]
                    current_x += width
                    
                    new_items.append({
                        'text': line,
                        'box': new_box,
                        'is_empty': False
                    })
            else:
                for line in new_lines:
                    new_items.append({
                        'text': line,
                        'box': None,
                        'is_empty': False
                    })
            
            # Replace the original item with new items
            self.items[target_idx:target_idx+1] = new_items
            self._render_cards()
            self.data_changed.emit(self.items)

    def handle_merge_next(self, target_slot):
        target_idx = self._find_slot_index(target_slot)
        if target_idx == -1 or target_idx >= len(self.items) - 1:
            QMessageBox.information(self, "提示", "没有后一项可以合并")
            return
            
        self._save_state()
        
        curr_item = self.items[target_idx]
        next_item = self.items[target_idx + 1]
        
        # Merge Text
        text1 = curr_item.get('text', '')
        text2 = next_item.get('text', '')
        new_text = text1 + text2
        
        # Merge Box
        box1 = curr_item.get('box')
        box2 = next_item.get('box')
        
        new_box = None
        if box1 and box2:
            new_box = [
                min(box1[0], box2[0]),
                min(box1[1], box2[1]),
                max(box1[2], box2[2]),
                max(box1[3], box2[3])
            ]
        elif box1:
            new_box = box1
        elif box2:
            new_box = box2
            
        new_item = {
            'text': new_text,
            'box': new_box,
            'is_empty': False
        }
        
        # Replace 2 items with 1
        self.items[target_idx:target_idx+2] = [new_item]
        self._render_cards()
        self.data_changed.emit(self.items)

    def handle_drop(self, source_index, target_slot):
        # Find target index
        target_index = self._find_slot_index(target_slot)
            
        if target_index == -1: return
        if source_index == target_index: return
        
        # Perform Move (Insert)
        if 0 <= source_index < len(self.items) and 0 <= target_index < len(self.items):
            self._save_state()
            item = self.items.pop(source_index)
            self.items.insert(target_index, item)
            self._render_cards()
            self.data_changed.emit(self.items)

    def get_ordered_items(self):
        return self.items

    def get_grouped_results(self):
        results = []
        if not self.fields: return results
        
        num_fields = len(self.fields)
        num_records = (len(self.items) + num_fields - 1) // num_fields
        
        for i in range(num_records):
            record = {}
            base_idx = i * num_fields
            for j in range(num_fields):
                if base_idx + j < len(self.items):
                    item = self.items[base_idx + j]
                    key = self.fields[j][0]
                    record[key] = {
                        "text": item.get('text', ''),
                        "box": item.get('box'),
                        "index": base_idx + j
                    }
            results.append(record)
        return results
