# -*- coding: utf-8 -*-

"""
图像预览与标注组件（显示识别区域）
"""

try:
    from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout, QPushButton
    from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
    from PyQt5.QtCore import Qt, QRect, QPoint
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class ImageViewer(QWidget):
    def __init__(self):
        """
        初始化图像查看器
        """
        super().__init__()
        self.pixmap = None
        self.mask_enabled = False
        self.dragging = False
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.image_size = None
        self.scaled_rect = None
        self.current_mask_ratios = None  # 兼容旧代码，暂保留
        self.mask_list = []  # 新增：存储多蒙版 [{'rect': [x1,y1,x2,y2], 'label': 1, 'color': (r,g,b)}]
        self.setMouseTracking(True)
        
        # New: OCR Result Interaction
        self.ocr_results = []  # [{'text': 'foo', 'box': [x1,y1,x2,y2], 'id': 0}, ...]
        self.highlighted_indices = set()  # Set of indices to highlight
        self.bound_indices = set() # NEW: Set of indices that are already bound
        self.show_ocr_text = True # NEW: Toggle for showing text
        self.show_image = True # NEW: Toggle for showing image
        self.interaction_mode = 'mask'  # 'mask' or 'select'
        self.selection_callback = None  # Function to call when region selected: cb(indices)
        
        # Zoom support
        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0) # (x, y) offset in pixels
        self.is_panning = False
        self.pan_start_pos = QPoint()
        
        # Reset Button
        self.btn_reset = QPushButton("复原", self)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 100);
                color: white;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 150);
            }
        """)
        self.btn_reset.clicked.connect(self.reset_view)
        self.btn_reset.hide() # Initially hidden, shown when image loaded? Or always shown? User said "click to reset". Let's show it.
        self.btn_reset.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'btn_reset'):
            btn_w = 80
            btn_h = 30
            self.btn_reset.resize(btn_w, btn_h)
            # Center horizontally, 20px from bottom
            x = (self.width() - btn_w) // 2
            y = self.height() - btn_h - 20
            self.btn_reset.move(x, y)

    def reset_view(self):
        """Reset zoom and pan"""
        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self.update()

    def set_interaction_mode(self, mode):
        """Set interaction mode: 'mask' or 'select'"""
        self.interaction_mode = mode
        self.update()

    def clear_masks(self):
        """Clear all masks"""
        self.mask_list = []
        self.current_mask_ratios = None
        self.update()

    def set_ocr_results(self, results):
        """
        Set OCR results for interaction
        results: list of dicts with 'text' and 'coordinates' (list of [x,y])
        """
        self.ocr_results = []
        for i, res in enumerate(results):
            coords = res.get('coordinates', [])
            box = res.get('box')
            
            # Allow items with no coords (e.g. inserted empty values)
            valid_box = False
            x1, y1, x2, y2 = 0, 0, 0, 0
            
            if box:
                x1, y1, x2, y2 = box
                valid_box = True
            elif coords:
                # Convert polygon to bounding box
                xs = [p[0] for p in coords]
                ys = [p[1] for p in coords]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                valid_box = True
            
            self.ocr_results.append({
                'id': i,
                'text': res.get('text', ''),
                'box': [x1, y1, x2, y2] if valid_box else None,
                'original': res
            })
        self.update()

    def highlight_regions(self, indices):
        """Highlight specific regions by index"""
        self.highlighted_indices = set(indices)
        self.update()

    def select_aligned_regions(self, reference_index, direction='vertical'):
        """Select regions aligned with the reference region"""
        if reference_index < 0 or reference_index >= len(self.ocr_results):
            return []
            
        ref_box = self.ocr_results[reference_index]['box']
        ref_cx = (ref_box[0] + ref_box[2]) / 2
        ref_cy = (ref_box[1] + ref_box[3]) / 2
        
        selected_indices = [reference_index]
        
        for i, item in enumerate(self.ocr_results):
            if i == reference_index: continue
            
            box = item['box']
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            
            if direction == 'vertical':
                # Aligned vertically (similar X center)
                if abs(cx - ref_cx) < 20: # Tolerance
                    selected_indices.append(i)
            elif direction == 'horizontal':
                # Aligned horizontally (similar Y center)
                if abs(cy - ref_cy) < 20: # Tolerance
                    selected_indices.append(i)
                    
        self.highlight_regions(selected_indices)
        if self.selection_callback:
            self.selection_callback(selected_indices)
        return selected_indices

    def clear_masks(self):
        self.mask_list = []
        self.current_mask_ratios = None
        self.update()

    def undo_last_mask(self):
        if self.mask_list:
            self.mask_list.pop()
            self.update()

    def display_image(self, image_path):
        """
        显示图像

        Args:
            image_path: 图像路径
        """
        print(f"Displaying image: {image_path}")
        if not PYQT_AVAILABLE:
            print("Cannot display image: PyQt5 not available")
            return
            
        try:
            self.pixmap = QPixmap(image_path)
            self.image_size = self.pixmap.size() # Keep QSize object
            self.zoom_factor = 1.0  # Reset zoom when loading new image
            self.pan_offset = QPoint(0, 0)
            self.update()
        except Exception as e:
            print(f"Error displaying image: {e}")

    def start_mask_mode(self, enabled=True):
        self.mask_enabled = enabled
        self.interaction_mode = 'mask' if enabled else 'select' # Sync with new mode system
        self.update()

    def mousePressEvent(self, event):
        if not PYQT_AVAILABLE or not self.pixmap:
            return

        # Handle Panning (Right Mouse Button)
        if event.button() == Qt.RightButton or event.button() == Qt.MiddleButton:
            self.is_panning = True
            self.pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
            
        # Handle Selection Mode
        if self.interaction_mode == 'select' and event.button() == Qt.LeftButton:
            # Check if clicked on any OCR region
            pos = self._map_to_image(event.pos())
            if not pos: return
            
            # Use QSize for width/height
            w, h = self.image_size.width(), self.image_size.height()
            
            # pos is QPoint in image coords
            cx, cy = pos.x(), pos.y()
            
            clicked_index = -1
            for i, item in enumerate(self.ocr_results):
                if not item or 'box' not in item or not item['box']:
                    continue
                x1, y1, x2, y2 = item['box']
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    clicked_index = i
                    break
            
            if clicked_index != -1:
                self.highlight_regions([clicked_index])
                if self.selection_callback:
                    self.selection_callback([clicked_index])
            return

        if self.mask_enabled and event.button() == Qt.LeftButton:
            self.dragging = True
            self.start_pos = self._map_to_image(event.pos()) # Store in image coords
            self.end_pos = self.start_pos
            self.update()

    def mouseMoveEvent(self, event):
        if not PYQT_AVAILABLE or not self.pixmap:
            return

        if self.is_panning:
            delta = event.pos() - self.pan_start_pos
            self.pan_offset += delta
            self.pan_start_pos = event.pos()
            self.update()
            return

        if self.dragging and self.mask_enabled:
            self.end_pos = self._map_to_image(event.pos()) # Store in image coords
            self.update()

    def mouseReleaseEvent(self, event):
        if not PYQT_AVAILABLE or not self.pixmap:
            return
        
        if self.is_panning and (event.button() == Qt.RightButton or event.button() == Qt.MiddleButton):
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)
            return

        if self.dragging and self.mask_enabled and event.button() == Qt.LeftButton:
            self.end_pos = self._map_to_image(event.pos()) # Store in image coords
            self.dragging = False

            try:
                ratios = self.get_mask_coordinates_ratios()
                if ratios and len(ratios) == 4:
                    self.current_mask_ratios = ratios
                    # 添加到多蒙版列表
                    label = len(self.mask_list) + 1
                    # 生成颜色
                    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
                    color = colors[(label - 1) % len(colors)]
                    self.mask_list.append({
                        'rect': ratios,
                        'label': label,
                        'color': color
                    })
            except Exception:
                pass
            self.update()

    def wheelEvent(self, event):
        """
        Handle mouse wheel event for zooming
        """
        if not PYQT_AVAILABLE or not self.pixmap:
            return

        if event.modifiers() & Qt.ControlModifier:
            # Zoom
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_factor *= 1.1
            else:
                self.zoom_factor /= 1.1
            
            # Clamp zoom factor
            self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))
            self.update()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Reset view on double click"""
        if event.button() == Qt.RightButton or event.button() == Qt.LeftButton:
            self.reset_view()

    def _compute_scaled_rect(self):
        if not self.pixmap:
            return None
        w = self.width()
        h = self.height()
        pw = self.pixmap.width()
        ph = self.pixmap.height()
        if pw == 0 or ph == 0 or w == 0 or h == 0:
            return QRect(0, 0, 0, 0)
        scale = min(w / pw, h / ph) * self.zoom_factor
        sw = int(pw * scale)
        sh = int(ph * scale)
        ox = (w - sw) // 2 + self.pan_offset.x()
        oy = (h - sh) // 2 + self.pan_offset.y()
        self.scaled_rect = QRect(ox, oy, sw, sh)
        return self.scaled_rect

    def _map_to_image(self, pos):
        """Map widget coordinates to image coordinates considering zoom and pan"""
        if not self.scaled_rect:
            return QPoint(0, 0)
        
        # Relative to scaled rect top-left
        rel_x = pos.x() - self.scaled_rect.x()
        rel_y = pos.y() - self.scaled_rect.y()
        
        # Scale back to original image
        img_w = self.image_size.width() if self.image_size else 0
        scale = self.scaled_rect.width() / img_w if img_w > 0 else 1.0
        
        orig_x = int(rel_x / scale)
        orig_y = int(rel_y / scale)
        
        return QPoint(orig_x, orig_y)

    # Legacy helper for compatibility, now delegates to _map_to_image
    def _map_widget_to_image(self, pos):
        p = self._map_to_image(pos)
        # Return normalized coordinates (0-1) as tuple
        if self.image_size and self.image_size.width() > 0:
            return (p.x() / self.image_size.width(), p.y() / self.image_size.height())
        return (0, 0)

    def get_mask_coordinates_ratios(self):
        """
        获取当前蒙版的坐标比例 (x1, y1, x2, y2)
        """
        if not self.start_pos or not self.end_pos or not self.image_size:
            return None
            
        # self.start_pos and self.end_pos are already in image coordinates
        p1 = self.start_pos
        p2 = self.end_pos
        
        x1, x2 = min(p1.x(), p2.x()), max(p1.x(), p2.x())
        y1, y2 = min(p1.y(), p2.y()), max(p1.y(), p2.y())
        
        w, h = self.image_size.width(), self.image_size.height()
        if w == 0 or h == 0: return None
        
        return [x1/w, y1/h, x2/w, y2/h]

    def get_mask_data(self):
        """获取当前蒙版数据（支持多区域）"""
        if self.mask_list:
            return self.mask_list
        if self.current_mask_ratios:
            # 兼容单蒙版
            return [{'rect': self.current_mask_ratios, 'label': 1, 'color': (255, 0, 0)}]
        return []

    def set_mask_data(self, data):
        """设置蒙版数据"""
        self.mask_list = []
        self.current_mask_ratios = None
        if not data:
            self.update()
            return
            
        if isinstance(data, list):
            # 判断是旧格式(坐标列表)还是新格式(字典列表)
            if len(data) == 4 and isinstance(data[0], (int, float)):
                # 旧格式
                self.current_mask_ratios = data
                self.mask_list.append({
                    'rect': data,
                    'label': 1,
                    'color': (255, 0, 0)
                })
            else:
                # 新格式
                self.mask_list = data
                # 更新 current_mask_ratios 为第一个（为了兼容）
                if self.mask_list and 'rect' in self.mask_list[0]:
                    self.current_mask_ratios = self.mask_list[0]['rect']
        self.update()

    def set_mask_coordinates_ratios(self, ratios):
        # 兼容旧接口
        self.set_mask_data(ratios)

    def has_mask(self):
        return len(self.mask_list) > 0 or (self.current_mask_ratios is not None)

    def paintEvent(self, event):
        """
        绘制事件，用于在图像上绘制标注区域
        """
        super().paintEvent(event)
        if not PYQT_AVAILABLE:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        if not self.pixmap:
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "无图像")
            return

        rect = self._compute_scaled_rect()
        if rect:
            if self.show_image:
                painter.drawPixmap(rect, self.pixmap)
            else:
                # Fill with white if image is hidden
                painter.fillRect(rect, Qt.white)
                painter.setPen(Qt.black)
                painter.drawRect(rect)
        
        # Draw OCR Results (Boxes)
        if self.ocr_results:
            scale_x = rect.width() / self.image_size.width()
            scale_y = rect.height() / self.image_size.height()
            
            for i, item in enumerate(self.ocr_results):
                if not item['box']: continue # Skip items with no box
                
                x1, y1, x2, y2 = item['box']
                # Map to widget coordinates
                rx = int(rect.x() + x1 * scale_x)
                ry = int(rect.y() + y1 * scale_y)
                rw = int((x2 - x1) * scale_x)
                rh = int((y2 - y1) * scale_y)
                r = QRect(rx, ry, rw, rh)
                
                if i in self.highlighted_indices:
                    # Highlighted: Filled Yellow with Red Border
                    painter.fillRect(r, QColor(255, 255, 0, 100)) # Semi-transparent yellow
                    painter.setPen(QPen(QColor(255, 0, 0), 2))
                elif i in self.bound_indices:
                    # Bound: Filled Green with Green Border
                    painter.fillRect(r, QColor(0, 255, 0, 80)) # Semi-transparent green
                    painter.setPen(QPen(QColor(0, 255, 0), 2))
                else:
                    # Normal: Thin Blue Border
                    painter.setPen(QPen(QColor(0, 0, 255), 1))
                
                painter.drawRect(r)
                
                # Draw Text
                if self.show_ocr_text:
                    text = item.get('text', '')
                    if text:
                        # Draw background for text
                        # Use a slightly larger/bold font for visibility
                        font = painter.font()
                        font.setBold(True)
                        # Ensure minimum readable size if possible, though painter scales with widget?
                        # Actually QPainter on widget uses widget pixels. 
                        # If the image is large but widget is small, text might be crowded.
                        # But 'r' is in widget coordinates.
                        
                        painter.setFont(font)
                        fm = painter.fontMetrics()
                        tw = fm.width(text)
                        th = fm.height()
                        
                        # Position above the box
                        tx, ty = r.x(), r.y() - 5
                        if ty < th: ty = r.y() + r.height() + th # Flip to bottom if too close to top
                        
                        # Ensure text stays within widget bounds horizontally
                        if tx + tw > rect.right():
                            tx = rect.right() - tw
                        if tx < rect.left():
                            tx = rect.left()
                            
                        painter.fillRect(tx, ty - th + 2, tw + 4, th + 2, QColor(255, 255, 255, 230))
                        painter.setPen(QColor(0, 0, 0))
                        painter.drawText(tx + 2, ty, text)

        # 绘制蒙版区域
        if self.mask_enabled or self.mask_list:
            # 如果正在拖拽，绘制当前拖拽框
            if self.dragging and (self.start_pos and self.end_pos) and self.mask_enabled and rect and self.image_size and self.image_size.width() > 0:
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                
                # Image coords to Widget coords mapping
                mx1_img = min(self.start_pos.x(), self.end_pos.x())
                my1_img = min(self.start_pos.y(), self.end_pos.y())
                mx2_img = max(self.start_pos.x(), self.end_pos.x())
                my2_img = max(self.start_pos.y(), self.end_pos.y())
                
                scale_x = rect.width() / self.image_size.width()
                scale_y = rect.height() / self.image_size.height()
                
                wx1 = int(rect.x() + mx1_img * scale_x)
                wy1 = int(rect.y() + my1_img * scale_y)
                wx2 = int(rect.x() + mx2_img * scale_x)
                wy2 = int(rect.y() + my2_img * scale_y)
                
                r = QRect(wx1, wy1, wx2 - wx1, wy2 - wy1)
                painter.drawRect(r)
            
            # 绘制已保存的蒙版列表
            if self.mask_list and rect:
                for item in self.mask_list:
                    ratios = item.get('rect')
                    label = item.get('label', 1)
                    color_tuple = item.get('color', (255, 0, 0))
                    color = QColor(*color_tuple)
                    
                    if ratios:
                        x1 = int(rect.x() + ratios[0] * rect.width())
                        y1 = int(rect.y() + ratios[1] * rect.height())
                        x2 = int(rect.x() + ratios[2] * rect.width())
                        y2 = int(rect.y() + ratios[3] * rect.height())
                        r = QRect(x1, y1, x2 - x1, y2 - y1)
                        
                        # 绘制矩形
                        pen = QPen(color, 2)
                        painter.setPen(pen)
                        painter.drawRect(r)
                        
                        # 绘制标签
                        painter.setPen(color)
                        font = painter.font()
                        font.setBold(True)
                        font.setPointSize(12)
                        painter.setFont(font)
                        painter.drawText(x1, y1 - 5, f"#{label}")
