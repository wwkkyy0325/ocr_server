# -*- coding: utf-8 -*-

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                               QLabel, QAbstractItemView, QMenu, QAction, QApplication)
    from PyQt5.QtCore import pyqtSignal, Qt
    from PyQt5.QtGui import QColor, QBrush, QFont
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

class TextBlockListWidget(QWidget):
    """
    Widget to display list of text blocks.
    Supports single/multi-selection and hover effects.
    """
    # Signal emitted when a block is clicked (single selection)
    block_selected = pyqtSignal(int)
    # Signal emitted when a block is hovered
    block_hovered = pyqtSignal(int)
    # Signal emitted when selection changes (multi-selection)
    selection_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (Optional)
        # self.header = QLabel("Text Blocks")
        # self.layout.addWidget(self.header)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection) # Enable Multi-Selection
        self.list_widget.setMouseTracking(True) # Enable hover events
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connections
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemEntered.connect(self._on_item_entered)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        
        self.layout.addWidget(self.list_widget)
        
        self._last_hovered_item = None
        self._ignore_selection_change = False # Flag to prevent feedback loops

    def _show_context_menu(self, pos):
        """Show context menu"""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
            
        menu = QMenu(self)
        
        # Action: Copy Text
        action_copy = QAction(f"复制选中 ({len(selected_items)} 项)", self)
        action_copy.triggered.connect(self._copy_selected_text)
        menu.addAction(action_copy)
        
        menu.exec_(self.list_widget.mapToGlobal(pos))
        
    def _copy_selected_text(self):
        """Copy text of selected items to clipboard"""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
            
        # Sort by row index to ensure order
        selected_items.sort(key=lambda item: self.list_widget.row(item))
        
        texts = []
        for item in selected_items:
            # Extract text from item label or tooltip
            # Label format: "[1] text..."
            full_text = item.toolTip()
            if full_text:
                texts.append(full_text)
            else:
                # Fallback to parsing label if tooltip missing (shouldn't happen)
                label = item.text()
                # Remove [n] prefix
                if ']' in label:
                    texts.append(label.split(']', 1)[1].strip())
                else:
                    texts.append(label)
                    
        if texts:
            QApplication.clipboard().setText("\n".join(texts))

    def set_blocks(self, blocks):
        """
        Populate the list with text blocks.
        blocks: list of dicts [{'text': str, 'id': int, ...}]
        """
        self.list_widget.clear()
        self._last_hovered_item = None  # Reset hovered item reference as all items are deleted
        if not blocks:
            return
            
        for i, block in enumerate(blocks):
            text = block.get('text', '').strip()
            table_info = block.get('table_info')
            
            prefix = f"[{i+1}]"
            if table_info:
                row = table_info.get('row', 0)
                col = table_info.get('col', 0)
                is_header = table_info.get('is_header', False)
                header_mark = " [H]" if is_header else ""
                prefix = f"[{i+1}][R{row},C{col}]{header_mark}"
            
            display_text = f"{prefix} {text}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, i) # Store index
            item.setToolTip(text) # Full text in tooltip
            
            # Style
            font = item.font()
            font.setPointSize(10)
            item.setFont(font)
            
            if table_info:
                if table_info.get('is_header', False):
                    item.setBackground(QBrush(QColor(220, 235, 255))) # Light Blue for Header
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setBackground(QBrush(QColor(245, 245, 245))) # Light Gray for Cell
            
            self.list_widget.addItem(item)

    def select_block(self, index):
        """
        Select a single block by index (Programmatic selection).
        """
        self._ignore_selection_change = True
        self.list_widget.clearSelection()
        if 0 <= index < self.list_widget.count():
            item = self.list_widget.item(index)
            item.setSelected(True)
            self.list_widget.scrollToItem(item)
        self._ignore_selection_change = False

    def select_blocks(self, indices):
        """
        Select multiple blocks by indices (Programmatic selection).
        """
        self._ignore_selection_change = True
        self.list_widget.clearSelection()
        
        if not indices:
            self._ignore_selection_change = False
            return
            
        first_item = None
        for index in indices:
            if 0 <= index < self.list_widget.count():
                item = self.list_widget.item(index)
                item.setSelected(True)
                if not first_item:
                    first_item = item
                    
        if first_item:
            self.list_widget.scrollToItem(first_item)
            
        self._ignore_selection_change = False

    def set_hovered_block(self, index):
        """
        Highlight the item corresponding to the block index (without selecting).
        """
        # Reset previous hover style
        if self._last_hovered_item:
            try:
                # If item is selected, we shouldn't change its background to white.
                if not self._last_hovered_item.isSelected():
                    self._last_hovered_item.setBackground(QBrush(Qt.NoBrush)) # Reset
            except RuntimeError:
                # Item might be deleted
                self._last_hovered_item = None
            
            self._last_hovered_item = None
            
        if 0 <= index < self.list_widget.count():
            item = self.list_widget.item(index)
            
            if not item.isSelected():
                item.setBackground(QBrush(QColor(224, 247, 250))) # Light Cyan
            
            self.list_widget.scrollToItem(item)
            self._last_hovered_item = item

    def _on_item_clicked(self, item):
        # Single click logic is handled by selection change usually, but we might want explicit click
        index = item.data(Qt.UserRole)
        self.block_selected.emit(index)

    def _on_selection_changed(self):
        if self._ignore_selection_change:
            return
            
        selected_items = self.list_widget.selectedItems()
        indices = [item.data(Qt.UserRole) for item in selected_items]
        self.selection_changed.emit(indices)
        
    def _on_item_entered(self, item):
        index = item.data(Qt.UserRole)
        self.block_hovered.emit(index)
