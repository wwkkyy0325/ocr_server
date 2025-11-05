# -*- coding: utf-8 -*-

"""
图像预览与标注组件（显示识别区域）
"""

try:
    from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout
    from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
    from PyQt5.QtCore import Qt, QRect
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class ImageViewer(QWidget):
    def __init__(self):
        """
        初始化图像查看器
        """
        super().__init__()
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.pixmap = None
        self.regions = []
        
        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        self.setLayout(layout)

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
            self.image_label.setPixmap(self.pixmap.scaled(
                self.image_label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            ))
        except Exception as e:
            print(f"Error displaying image: {e}")

    def annotate_region(self, region_coords):
        """
        标注区域

        Args:
            region_coords: 区域坐标 (x1, y1, x2, y2)
        """
        print(f"Annotating region: {region_coords}")
        if len(region_coords) >= 4:
            self.regions.append(region_coords)
            self.update()

    def paintEvent(self, event):
        """
        绘制事件，用于在图像上绘制标注区域
        """
        super().paintEvent(event)
        if not PYQT_AVAILABLE or not self.pixmap:
            return
            
        painter = QPainter(self)
        painter.drawPixmap(self.image_label.geometry(), self.pixmap)
        
        # 绘制标注区域
        pen = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen)
        
        for region in self.regions:
            if len(region) >= 4:
                x1, y1, x2, y2 = region[0], region[1], region[2], region[3]
                rect = QRect(int(x1), int(y1), int(x2-x1), int(y2-y1))
                painter.drawRect(rect)
