# -*- coding: utf-8 -*-

"""
图像预览与标注组件（显示识别区域）
"""

try:
    from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout, QPushButton
    from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QPainterPath
    from PyQt5.QtCore import Qt, QRect, QPoint, QRectF
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from app.utils.file_utils import FileUtils
from PIL import Image
import io


class VisualMapper:
    """
    中间层：负责将逻辑OCR结果坐标映射到可视化视图坐标
    处理坐标偏移、缩放和转换关系
    """
    def __init__(self):
        # 矫正参数 (Correction parameters)
        # 用于处理 "输出位置与真实位置有出入" 的情况
        self.offset_x = 0
        self.offset_y = 0
        self.scale_x = 1.0
        self.scale_y = 1.0

    def map_to_visual(self, logical_box, image_size, display_rect):
        """
        将逻辑坐标 [x1, y1, x2, y2] 映射到组件可视区域的 QRect
        Args:
            logical_box: [x1, y1, x2, y2] 原始OCR结果坐标
            image_size: QSize 原始图像尺寸
            display_rect: QRect 图像在组件中的显示区域（已缩放/偏移）
        Returns:
            QRect: 组件坐标系下的矩形
        """
        if not logical_box or not image_size or not display_rect:
            return QRect()
            
        x1, y1, x2, y2 = logical_box
        
        # 1. 应用逻辑层面的矫正 (Logic Correction)
        # 假设 logical_box 是基于原始图像的，但可能存在系统性偏差
        cx1 = x1 * self.scale_x + self.offset_x
        cy1 = y1 * self.scale_y + self.offset_y
        cx2 = x2 * self.scale_x + self.offset_x
        cy2 = y2 * self.scale_y + self.offset_y
        
        # Debug Log for first item or specific check
        # print(f"DEBUG: Map logical {logical_box} -> Corrected [{cx1}, {cy1}, {cx2}, {cy2}]")

        # 2. 映射到视图坐标 (View Mapping)
        img_w = image_size.width()
        img_h = image_size.height()
        
        if img_w == 0 or img_h == 0:
            return QRect()
            
        # 计算图像到视图的缩放比例
        view_scale_x = display_rect.width() / img_w
        view_scale_y = display_rect.height() / img_h
        
        # 转换到组件坐标系
        vx1 = display_rect.x() + cx1 * view_scale_x
        vy1 = display_rect.y() + cy1 * view_scale_y
        vw = (cx2 - cx1) * view_scale_x
        vh = (cy2 - cy1) * view_scale_y
        
        return QRect(int(vx1), int(vy1), int(vw), int(vh))


class TextBlockGenerator:
    """
    文字块生成器：负责生成文字区域的描边路径和聚类
    """
    def __init__(self, visual_mapper):
        self.visual_mapper = visual_mapper
        self.dilation_x = 5   # 基础横向膨胀
        self.dilation_y = 5   # 基础纵向膨胀
        self.bridge_gap_x = 40 # 横向连接阈值
        self.bridge_gap_y = 20 # 纵向连接阈值
        self.visual_offset_x = -10 # 视觉水平矫正：负值左移 (加大力度)
        self.visual_offset_y = -15 # 视觉垂直矫正：负值上移 (加大力度)
        
    def _pre_merge_rects(self, rects):
        """
        Deprecated: Logic moved to clustering in generate_text_blocks
        """
        return rects
        
    def _are_rects_connected_raw(self, r1, r2, threshold_x, threshold_y):
        """
        判断两个矩形是否应该被视为同一块 (使用动态阈值)
        Args:
            r1, r2: QRect (原始坐标系)
            threshold_x: 水平连接阈值
            threshold_y: 垂直连接阈值
        """
        # 1. 垂直重叠检查 (Vertical Overlap)
        y_overlap = max(0, min(r1.bottom(), r2.bottom()) - max(r1.top(), r2.top()))
        h_min = min(r1.height(), r2.height())
        
        # 2. 水平重叠检查 (Horizontal Overlap)
        x_overlap = max(0, min(r1.right(), r2.right()) - max(r1.left(), r2.left()))
        w_min = min(r1.width(), r2.width())
        
        # 3. 距离检查
        dist_x = max(0, max(r1.left(), r2.left()) - min(r1.right(), r2.right()))
        dist_y = max(0, max(r1.top(), r2.top()) - min(r1.bottom(), r2.bottom()))
        
        # Case A: 同一行 (Vertical Overlap + Small X Gap)
        # 要求重叠高度至少是较小矩形的 50%
        if h_min > 0 and y_overlap > 0.5 * h_min: 
            if dist_x < threshold_x:
                return True
                
        # Case B: 同一段落 (Horizontal Overlap + Small Y Gap)
        # 注意：这里要求有水平重叠，避免把不相关的左右分栏连在一起
        if w_min > 0 and x_overlap > 0.5 * w_min:
            if dist_y < threshold_y:
                return True
                
        return False

    def _cluster_rects_raw(self, rects):
        """
        使用连通分量算法对原始矩形进行聚类 (Scale Invariant)
        Args:
            rects: list of QRect (原始坐标)
        Returns: 
            list of QRect (merged raw bounding boxes)
        """
        if not rects:
            return []
            
        n = len(rects)
        if n == 0:
            return []
            
        # 计算平均高度，用于动态设定阈值
        total_h = sum(r.height() for r in rects)
        avg_h = total_h / n if n > 0 else 20
        
        # 动态阈值：
        # 水平间距：允许 1.5 倍字高 (处理字间距)
        # 垂直间距：允许 0.8 倍字高 (处理行间距)
        threshold_x = 1.5 * avg_h
        threshold_y = 0.8 * avg_h
        
        parent = list(range(n))
        
        def find(i):
            if parent[i] != i:
                parent[i] = find(parent[i])
            return parent[i]
            
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j
                
        # O(N^2) pairwise comparison
        for i in range(n):
            for j in range(i + 1, n):
                if self._are_rects_connected_raw(rects[i], rects[j], threshold_x, threshold_y):
                    union(i, j)
                    
        # Group by root
        clusters = {}
        for i in range(n):
            root = find(i)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(rects[i])
            
        # Compute bounding box for each cluster
        merged_rects = []
        for root in clusters:
            group = clusters[root]
            if not group: continue
            
            # Union all rects in the group to get the bounding box
            bounding_box = group[0]
            for k in range(1, len(group)):
                bounding_box = bounding_box.united(group[k])
            merged_rects.append(bounding_box)
            
        return merged_rects

    def generate_text_blocks(self, ocr_results, image_size, display_rect):
        """
        生成文字块的 QPainterPath
        Args:
            ocr_results: OCR结果列表
            image_size: 原始图像尺寸
            display_rect: 显示区域
        Returns:
            QPainterPath: 融合后的文字块路径
        """
        path = QPainterPath()
        if not ocr_results or not image_size or not display_rect:
            return path
            
        # 1. 收集原始坐标 (Raw Coordinates)
        raw_rects = []
        for item in ocr_results:
            if not item or 'box' not in item or not item['box']:
                continue
            
            # 获取原始坐标
            b = item['box']
            # 确保是整数 QRect
            r = QRect(int(b[0]), int(b[1]), int(b[2]-b[0]), int(b[3]-b[1]))
            if r.isValid():
                raw_rects.append(r)

        if not raw_rects:
            return path
            
        # 2. 在原始坐标系下进行聚类 (Clustering in Raw Space)
        # 这样聚类结果只与图像内容有关，与视图缩放无关
        clustered_raw_rects = self._cluster_rects_raw(raw_rects)
        
        # 3. 将聚类后的矩形映射到视图坐标 (Map to Visual)
        visual_rects = []
        for raw_r in clustered_raw_rects:
             # 将 QRect 转换回 [x1, y1, x2, y2] 格式供 map_to_visual 使用
             box = [raw_r.left(), raw_r.top(), raw_r.right(), raw_r.bottom()]
             v_rect = self.visual_mapper.map_to_visual(box, image_size, display_rect)
             if v_rect.isValid():
                 visual_rects.append(v_rect)
        
        # 4. 生成路径 (Generate Path)
        for r in visual_rects:
            # 应用视觉位置矫正 (整体上移+左移)
            if self.visual_offset_x != 0 or self.visual_offset_y != 0:
                r.translate(self.visual_offset_x, self.visual_offset_y)
                
            expanded_rect = r.adjusted(
                -self.dilation_x, 
                -self.dilation_y, 
                self.dilation_x, 
                self.dilation_y
            )
            # 最小尺寸保护
            if expanded_rect.width() < 1: expanded_rect.setWidth(1)
            if expanded_rect.height() < 1: expanded_rect.setHeight(1)
            
            p = QPainterPath()
            p.addRoundedRect(QRectF(expanded_rect), 5, 5)
            path = path.united(p)
            
        # 5. 简化路径
        path = path.simplified()
        
        # 6. 填充内部空洞 (Hole Filling)
        filled_path = QPainterPath()
        for polygon in path.toSubpathPolygons():
            filled_path.addPolygon(polygon)
            
        path = filled_path.simplified()
        
        return path


class ImageViewer(QWidget):
    def __init__(self):
        """
        初始化图像查看器
        """
        super().__init__()
        self.visual_mapper = VisualMapper()  # 初始化中间层映射器
        self.text_block_generator = TextBlockGenerator(self.visual_mapper) # 初始化文字块生成器
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

    @property
    def mapper(self):
        if not hasattr(self, 'visual_mapper'):
            self.visual_mapper = VisualMapper()
        return self.visual_mapper
        
    @property
    def generator(self):
        if not hasattr(self, 'text_block_generator'):
             # Hot-fix: if mapper is not init, init it
            self.text_block_generator = TextBlockGenerator(self.mapper)
        return self.text_block_generator

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
        设置OCR结果并触发重绘
        Args:
            results: OCR结果列表
        """
        if not results:
            print("DEBUG: set_ocr_results called with empty results")
            self.ocr_results = []
            self.update()
            return

        print(f"DEBUG: set_ocr_results called with {len(results)} items")
        
        self.ocr_results = []
        max_x = 0
        max_y = 0
        
        for res in results:
            valid_box = False
            x1, y1, x2, y2 = 0, 0, 0, 0
            
            # 1. Try 'box' field (format: [x1, y1, x2, y2])
            if 'box' in res and res['box']:
                b = res['box']
                if len(b) == 4:
                    x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
                    valid_box = True
            
            # 2. Try 'coordinates' field (format: [[x,y], ...])
            elif 'coordinates' in res and res['coordinates']:
                coords = res['coordinates']
                if coords:
                    xs = [p[0] for p in coords]
                    ys = [p[1] for p in coords]
                    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                    valid_box = True
            
            if valid_box:
                # Update max dimensions for auto-scaling check
                max_x = max(max_x, x2)
                max_y = max(max_y, y2)
                
                # Store normalized structure
                self.ocr_results.append({
                    'box': [x1, y1, x2, y2],
                    'text': res.get('text', ''),
                    'original': res # Keep original data
                })
        
        # Auto-Normalization Check
        # If coordinates are normalized (0-1) but image size is large, we need to handle it.
        # However, VisualMapper expects pixel coordinates relative to image size.
        # If max_x <= 1.0 and image width > 100, it's likely normalized.
        
        is_normalized = False
        if self.image_size and self.image_size.width() > 100:
             if max_x <= 1.5: # Threshold slightly > 1.0 to account for float noise
                 is_normalized = True
                 print("DEBUG: Detected NORMALIZED coordinates (0-1). Converting to pixels...")
        
        if is_normalized and self.image_size:
            w = self.image_size.width()
            h = self.image_size.height()
            for item in self.ocr_results:
                b = item['box']
                item['box'] = [b[0]*w, b[1]*h, b[2]*w, b[3]*h]
        
        print(f"DEBUG: Processed {len(self.ocr_results)} valid OCR items. Max X: {max_x}, Max Y: {max_y}")
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
            # Handle PDF files or virtual paths
            if image_path.lower().endswith('.pdf') or '|page=' in image_path.lower():
                print(f"ImageViewer: Loading PDF/Virtual path: {image_path}")
                pil_image = FileUtils.read_image(image_path)
                if pil_image:
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    data = pil_image.tobytes("raw", "RGB")
                    qim = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGB888)
                    self.pixmap = QPixmap.fromImage(qim)
                    print(f"ImageViewer: Successfully loaded pixmap for {image_path}")
                else:
                    print(f"ImageViewer: Failed to read image for {image_path}")
                    self.pixmap = None
            else:
                self.pixmap = QPixmap(image_path)
                
            if self.pixmap and not self.pixmap.isNull():
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
            # Check if clicked on any OCR region using VisualMapper for accurate hit testing
            click_pos = event.pos()
            display_rect = self._compute_scaled_rect()
            
            clicked_index = -1
            # Iterate in reverse order to select top-most if overlapping (optional, but good practice)
            # But usually index order matches reading order. Let's stick to forward or reverse? 
            # Forward means checking first match. 
            for i, item in enumerate(self.ocr_results):
                if not item or 'box' not in item or not item['box']:
                    continue
                
                # Use VisualMapper to get the exact rect rendered on screen
                visual_rect = self.mapper.map_to_visual(item['box'], self.image_size, display_rect)
                
                if visual_rect.contains(click_pos):
                    clicked_index = i
                    break # Found the first match
            
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

    def get_merged_text_path(self, visual_rects, padding=5):
        # Deprecated: use TextBlockGenerator instead
        return self.generator.generate_text_blocks(self.ocr_results, self.image_size, self._compute_scaled_rect())

    def paintEvent(self, event):
        """
        绘制事件，用于在图像上绘制标注区域
        """
        super().paintEvent(event)
        
        # Hot-fix for missing attributes due to hot-reloading __init__ bypass
        if not hasattr(self, 'ocr_results'): self.ocr_results = []
        if not hasattr(self, 'highlighted_indices'): self.highlighted_indices = set()
        if not hasattr(self, 'bound_indices'): self.bound_indices = set()
        if not hasattr(self, 'show_ocr_text'): self.show_ocr_text = True
        if not hasattr(self, 'show_image'): self.show_image = True
        if not hasattr(self, 'mask_enabled'): self.mask_enabled = False
        if not hasattr(self, 'mask_list'): self.mask_list = []
        if not hasattr(self, 'dragging'): self.dragging = False
        if not hasattr(self, 'start_pos'): self.start_pos = QPoint()
        if not hasattr(self, 'end_pos'): self.end_pos = QPoint()
        if not hasattr(self, 'image_size'): 
            self.image_size = self.pixmap.size() if getattr(self, 'pixmap', None) else None
        if not hasattr(self, 'interaction_mode'): self.interaction_mode = 'mask'
        if not hasattr(self, 'selection_callback'): self.selection_callback = None
        if not hasattr(self, 'zoom_factor'): self.zoom_factor = 1.0
        if not hasattr(self, 'pan_offset'): self.pan_offset = QPoint(0, 0)
        if not hasattr(self, 'is_panning'): self.is_panning = False
        if not hasattr(self, 'pan_start_pos'): self.pan_start_pos = QPoint()

        if not PYQT_AVAILABLE:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Background
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        if not self.pixmap:
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "无图像")
            # print("DEBUG: paintEvent - No pixmap")
            return

        rect = self._compute_scaled_rect()
        if not rect:
            print("DEBUG: paintEvent - Failed to compute scaled rect")
            return
        
        # print(f"DEBUG: paintEvent - Image Rect: {rect}, OCR Results: {len(self.ocr_results)}")

        # 1. Draw Original Image
        if getattr(self, 'show_image', True):
            painter.drawPixmap(rect, self.pixmap)
        else:
            painter.fillRect(rect, Qt.white)
            painter.setPen(Qt.black)
            painter.drawRect(rect)
        
        # 2. Draw Dimmed Background with Holes (Text Blocks)
        if self.ocr_results and rect:
            # 使用 TextBlockGenerator 生成路径
            merged_path = self.generator.generate_text_blocks(self.ocr_results, self.image_size, rect)
            
            if not merged_path.isEmpty():
                # Create the Dim Overlay Path
                # Full rect path - Merged text path
                overlay_path = QPainterPath()
                overlay_path.addRect(QRectF(rect))
                
                # Subtract text path to create holes
                dim_mask_path = overlay_path.subtracted(merged_path)
                
                # Draw Dim Overlay (Semi-transparent black)
                painter.fillPath(dim_mask_path, QColor(0, 0, 0, 150))
                
                # 3. Draw Highlights (Bold White Outline)
                # Draw the outline of the merged path
                pen = QPen(Qt.white, 2)
                # pen.setJoinStyle(Qt.RoundJoin) # Optional: smoother corners
                painter.setPen(pen)
                painter.drawPath(merged_path)
            else:
                # Fallback or empty (maybe no valid boxes)
                pass
            
            # 4. Draw Specific Selection Highlights (Yellow/Green overlays)
            # These should probably be drawn ON TOP of the dim layer to be visible
            for i, item in enumerate(self.ocr_results):
                if i in self.highlighted_indices or i in self.bound_indices:
                    if not item['box']: continue
                    r = self.mapper.map_to_visual(item['box'], self.image_size, rect)
                    
                    if i in self.highlighted_indices:
                        painter.fillRect(r, QColor(255, 255, 0, 100)) # Yellow
                        painter.setPen(QPen(QColor(255, 0, 0), 2))
                        painter.drawRect(r)
                    elif i in self.bound_indices:
                        painter.fillRect(r, QColor(0, 255, 0, 80)) # Green
                        painter.setPen(QPen(QColor(0, 255, 0), 2))
                        painter.drawRect(r)
            
            # 5. Draw Text (Optional, if enabled)
            if self.show_ocr_text:
                for i, item in enumerate(self.ocr_results):
                    if not item['box']: continue
                    text = item.get('text', '')
                    if not text: continue
                    
                    r = self.mapper.map_to_visual(item['box'], self.image_size, rect)
                    
                    # Draw background for text
                    font = painter.font()
                    font.setBold(True)
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

        # Draw Dragging Selection Rect (if any)
        if self.mask_enabled and self.dragging:
             pass # Logic handled below in "mask_enabled or mask_list" block

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
