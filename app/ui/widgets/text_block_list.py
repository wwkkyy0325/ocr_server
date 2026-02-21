# -*- coding: utf-8 -*-

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                               QLabel, QAbstractItemView, QMenu, QAction, QApplication)
    from PyQt5.QtCore import pyqtSignal, Qt
    from PyQt5.QtGui import QColor, QBrush, QFont
    from app.ui.widgets.result_table_widget import ResultTableWidget
    from PyQt5.QtWidgets import QTableWidgetItem
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
        
        self.table_widget = ResultTableWidget(self)
        self.list_widget = self.table_widget.table
        base_font = self.list_widget.font()
        base_font.setPointSize(10)
        self.list_widget.setFont(base_font)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemEntered.connect(self._on_item_entered)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        
        self.layout.addWidget(self.table_widget)
        
        self._last_hovered_item = None
        self._ignore_selection_change = False # Flag to prevent feedback loops
        self._block_index_to_cell = {}

    def set_export_basename(self, basename: str):
        """
        透传导出基础文件名到内部的 ResultTableWidget
        """
        if hasattr(self.table_widget, "set_export_basename"):
            self.table_widget.set_export_basename(basename)

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
        self.list_widget.clearContents()
        self.list_widget.setRowCount(0)
        self._last_hovered_item = None
        self._block_index_to_cell = {}
        if not blocks:
            return

        has_table_info = any(block.get('table_info') for block in blocks)
        if has_table_info:
            self._set_blocks_with_table_info(blocks)
            try:
                self.table_widget._auto_fit_all(resize_splitter=True, remember=True)
            except Exception:
                pass
            return

        block_items = []
        for i, block in enumerate(blocks):
            rect = block.get('rect')
            if rect is None:
                continue
            try:
                x1 = rect.left()
                y1 = rect.top()
                x2 = rect.right()
                y2 = rect.bottom()
            except Exception:
                continue
            w = max(1, x2 - x1)
            h = max(1, y2 - y1)
            cx = (x1 + x2) / 2.0
            block_items.append({
                'block_index': i,
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'cx': cx,
                'w': float(w),
                'h': float(h)
            })

        if not block_items:
            return

        all_block_items = sorted(block_items, key=lambda it: it['cx'])
        avg_w = sum(it['w'] for it in all_block_items) / len(all_block_items) if all_block_items else 1.0
        col_threshold = max(avg_w * 0.8, 20.0)

        columns = []
        block_to_col = {}
        for it in all_block_items:
            cx = it['cx']
            if not columns:
                columns.append({'center': cx})
                col_idx = 0
            else:
                dists = [abs(cx - c['center']) for c in columns]
                min_idx = min(range(len(dists)), key=lambda k: dists[k])
                if dists[min_idx] <= col_threshold:
                    col_idx = min_idx
                    columns[col_idx]['center'] = (columns[col_idx]['center'] + cx) / 2.0
                else:
                    col_idx = len(columns)
                    columns.append({'center': cx})
            block_to_col[it['block_index']] = col_idx

        line_cells = []
        for it in block_items:
            block_index = it['block_index']
            block = blocks[block_index]
            text = block.get('text', '')
            if not text:
                continue
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if not lines:
                continue

            h_total = it['h']
            y1 = it['y1']
            line_h = max(1.0, h_total / float(len(lines)))

            for line_idx, line_text in enumerate(lines):
                cy = y1 + (line_idx + 0.5) * line_h
                line_cells.append({
                    'block_index': block_index,
                    'line_index': line_idx,
                    'text': line_text,
                    'cy': cy,
                    'h': line_h,
                    'col_idx': block_to_col.get(block_index, 0)
                })

        if not line_cells:
            return

        line_cells.sort(key=lambda c: c['cy'])
        avg_line_h = sum(c['h'] for c in line_cells) / len(line_cells) if line_cells else 1.0
        row_threshold = max(avg_line_h * 0.6, 5.0)

        line_rows = []
        current_row = [line_cells[0]]
        current_cy = line_cells[0]['cy']
        for cell in line_cells[1:]:
            if abs(cell['cy'] - current_cy) <= row_threshold:
                current_row.append(cell)
                current_cy = (current_cy + cell['cy']) / 2.0
            else:
                line_rows.append(current_row)
                current_row = [cell]
                current_cy = cell['cy']
        if current_row:
            line_rows.append(current_row)

        row_count = len(line_rows)
        column_count = max(len(columns), 1)
        self.list_widget.setRowCount(row_count)
        self.list_widget.setColumnCount(column_count)

        for row_idx, row_cells in enumerate(line_rows):
            for cell in sorted(row_cells, key=lambda c: c['col_idx']):
                block_index = cell['block_index']
                col_idx = cell['col_idx']
                text = cell['text']

                table_info = blocks[block_index].get('table_info')

                item = self.list_widget.item(row_idx, col_idx)
                if item:
                    base_text = item.text().strip()
                    new_text = text if not base_text else base_text + " " + text
                    item.setText(new_text)
                    tooltip = item.toolTip()
                    if tooltip:
                        item.setToolTip(tooltip + "\n" + text)
                    else:
                        item.setToolTip(new_text)
                    if item.data(Qt.UserRole) is None:
                        item.setData(Qt.UserRole, block_index)
                else:
                    item = QTableWidgetItem(text)
                    item.setData(Qt.UserRole, block_index)
                    item.setToolTip(text)

                    if table_info:
                        bg = None
                        if table_info.get('is_header', False):
                            bg = QBrush(QColor(220, 235, 255))
                        else:
                            bg = QBrush(QColor(245, 245, 245))
                        if bg is not None:
                            item.setBackground(bg)

                    self.list_widget.setItem(row_idx, col_idx, item)

                cells = self._block_index_to_cell.get(block_index)
                if cells is None:
                    self._block_index_to_cell[block_index] = [(row_idx, col_idx)]
                else:
                    if (row_idx, col_idx) not in cells:
                        cells.append((row_idx, col_idx))

        try:
            self.table_widget._auto_fit_all(resize_splitter=True, remember=True)
        except Exception:
            pass

    def _set_blocks_with_table_info(self, blocks):
        rows_map = {}
        for i, block in enumerate(blocks):
            table_info = block.get('table_info')
            rect = block.get('rect')
            text = block.get('text', '')
            if not table_info or rect is None:
                continue
            text = text.strip()
            if not text:
                continue
            row_idx = table_info.get('row', 0)
            col_idx = table_info.get('col', 0)
            is_header = table_info.get('is_header', False)
            row = rows_map.get(row_idx)
            if row is None:
                row = {}
                rows_map[row_idx] = row
            cell_list = row.get(col_idx)
            if cell_list is None:
                cell_list = []
                row[col_idx] = cell_list
            cell_list.append((i, text, is_header))

        if not rows_map:
            return

        sorted_row_indices = sorted(rows_map.keys())
        all_cols = set()
        for row in rows_map.values():
            all_cols.update(row.keys())
        if not all_cols:
            return

        max_col_idx = max(all_cols)
        column_count = max(max_col_idx + 1, 1)
        row_count = len(sorted_row_indices)

        self.list_widget.setRowCount(row_count)
        self.list_widget.setColumnCount(column_count)

        for visual_row_idx, row_idx in enumerate(sorted_row_indices):
            row = rows_map[row_idx]
            for col_idx in sorted(row.keys()):
                cell_items = row[col_idx]
                merged_text_parts = [t for _, t, _ in cell_items if t]
                if not merged_text_parts:
                    continue
                merged_text = " ".join(merged_text_parts)

                item = self.list_widget.item(visual_row_idx, col_idx)
                if item:
                    base_text = item.text().strip()
                    new_text = merged_text if not base_text else base_text + " " + merged_text
                    item.setText(new_text)
                    tooltip = item.toolTip()
                    if tooltip:
                        item.setToolTip(tooltip + "\n" + merged_text)
                    else:
                        item.setToolTip(new_text)
                else:
                    first_block_index, _, is_header = cell_items[0]
                    item = QTableWidgetItem(merged_text)
                    item.setData(Qt.UserRole, first_block_index)
                    item.setToolTip(merged_text)
                    bg = None
                    if is_header:
                        bg = QBrush(QColor(220, 235, 255))
                    else:
                        bg = QBrush(QColor(245, 245, 245))
                    if bg is not None:
                        item.setBackground(bg)
                    self.list_widget.setItem(visual_row_idx, col_idx, item)

                for block_index, _, _ in cell_items:
                    cells = self._block_index_to_cell.get(block_index)
                    if cells is None:
                        self._block_index_to_cell[block_index] = [(visual_row_idx, col_idx)]
                    else:
                        if (visual_row_idx, col_idx) not in cells:
                            cells.append((visual_row_idx, col_idx))

    def select_block(self, index):
        """
        Select a single block by index (Programmatic selection).
        """
        self._ignore_selection_change = True
        self.list_widget.clearSelection()
        cells = self._block_index_to_cell.get(index, [])
        first_item = None
        for row_idx, col_idx in cells:
            item = self.list_widget.item(row_idx, col_idx)
            if item:
                item.setSelected(True)
                if first_item is None:
                    first_item = item
        if first_item:
            self.list_widget.scrollToItem(first_item)
            self.list_widget.setFocus()
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
            cells = self._block_index_to_cell.get(index, [])
            for row_idx, col_idx in cells:
                item = self.list_widget.item(row_idx, col_idx)
                if item:
                    item.setSelected(True)
                    if first_item is None:
                        first_item = item
        
        if first_item:
            self.list_widget.scrollToItem(first_item)
            self.list_widget.setFocus()
            
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
            
        cells = self._block_index_to_cell.get(index, [])
        if cells:
            row_idx, col_idx = cells[0]
            item = self.list_widget.item(row_idx, col_idx)
            if item:
                if not item.isSelected():
                    item.setBackground(QBrush(QColor(224, 247, 250)))
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
        index_set = []
        seen = set()
        for item in selected_items:
            idx = item.data(Qt.UserRole)
            if idx is None:
                continue
            if idx not in seen:
                seen.add(idx)
                index_set.append(idx)
        self.selection_changed.emit(index_set)
        
    def _on_item_entered(self, item):
        index = item.data(Qt.UserRole)
        self.block_hovered.emit(index)
