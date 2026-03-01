try:
    from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QBrush
    from PyQt5.QtCore import Qt, QPoint, QPointF
except ImportError:
    pass

class BackgroundPainter:
    def __init__(self, config_manager=None):
        self.config_manager = config_manager

    def _get_glass_background_style(self):
        style = 'glass'
        if self.config_manager:
            try:
                style = self.config_manager.get_setting('glass_background', 'glass')
            except Exception:
                style = 'glass'
        if style not in ('glass', 'dots', 'frosted'):
            style = 'glass'
        return style

    def paint_background(self, painter, path, rect, is_main=False):
        """Public method to paint background"""
        style = self._get_glass_background_style()
        if style == 'glass':
            self._paint_plain_glass_background(painter, path, is_main=is_main)
        elif style == 'frosted':
            self._paint_frosted_background(painter, path, rect, is_main=is_main)
        else:
            self._paint_dots_background(painter, path, rect, is_main=is_main)

    def _paint_plain_glass_background(self, painter, path, is_main=False):
        painter.save()
        
        # Check current theme for minimalist override
        theme = 'classic'
        if self.config_manager:
            theme = self.config_manager.get_setting('theme', 'classic')
            
        if theme == 'minimalist':
            # Solid background for minimalist theme (High opacity)
            alpha = 255
            base_color = QColor(18, 18, 18, alpha)
        else:
            alpha = 190 if is_main else 220
            base_color = QColor(8, 12, 26, alpha)
            
        painter.fillPath(path, base_color)
        painter.restore()

    def _paint_dots_background(self, painter, path, rect, is_main=False):
        painter.save()
        self._paint_plain_glass_background(painter, path, is_main=is_main)

        painter.setPen(Qt.NoPen)
        left = rect.left()
        top = rect.top()
        right = rect.right()
        bottom = rect.bottom()
        offset = 7
        if is_main:
            # 顶部标题带：点更亮更密
            band_height = min(bottom - top, int((bottom - top) * 0.16))
            band_bottom = top + band_height
            y = top + offset
            while y < band_bottom:
                x = left + offset
                painter.setBrush(QColor(255, 255, 255, 64))
                radius = 1.5
                step_x = 12
                while x < right:
                    painter.drawEllipse(QPointF(x, y), radius, radius)
                    x += step_x
                y += 14

            # 中部区域：点明显可见，接近弹窗强度
            y = band_bottom + offset
            while y < bottom:
                x = left + offset
                painter.setBrush(QColor(255, 255, 255, 46))
                radius = 1.3
                step_x = 14
                while x < right:
                    painter.drawEllipse(QPointF(x, y), radius, radius)
                    x += step_x
                y += 18

            # 主界面聚合波点强度接近弹窗
            cluster_alpha = 82
            cluster_radius = max(rect.width(), rect.height()) * 0.24
            centers = [
                QPointF(rect.x() + rect.width() * 0.28, rect.y() + rect.height() * 0.28),
                QPointF(rect.x() + rect.width() * 0.7, rect.y() + rect.height() * 0.6),
            ]
            for c in centers:
                grad = QRadialGradient(c, cluster_radius)
                grad.setColorAt(0.0, QColor(255, 255, 255, cluster_alpha))
                grad.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setBrush(grad)
                painter.drawEllipse(c, cluster_radius, cluster_radius)
        else:
            dot_color = QColor(255, 255, 255, 40)
            painter.setBrush(dot_color)
            radius = 1.2
            step = 14
            y = top + offset
            while y < bottom:
                x = left + offset
                while x < right:
                    painter.drawEllipse(QPointF(x, y), radius, radius)
                    x += step
                y += step

            cluster_alpha = 90
            cluster_radius = max(rect.width(), rect.height()) * 0.18
            centers = [
                QPointF(rect.x() + rect.width() * 0.25, rect.y() + rect.height() * 0.3),
                QPointF(rect.x() + rect.width() * 0.6, rect.y() + rect.height() * 0.2),
                QPointF(rect.x() + rect.width() * 0.7, rect.y() + rect.height() * 0.65),
            ]
            for c in centers:
                grad = QRadialGradient(c, cluster_radius)
                grad.setColorAt(0.0, QColor(255, 255, 255, cluster_alpha))
                grad.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setBrush(grad)
                painter.drawEllipse(c, cluster_radius, cluster_radius)

        painter.restore()

    def _paint_frosted_background(self, painter, path, rect, is_main=False):
        painter.save()
        self._paint_plain_glass_background(painter, path, is_main=is_main)

        center = QPointF(rect.x() + rect.width() * 0.5, rect.y() + rect.height() * 0.35)
        glow_radius = max(rect.width(), rect.height()) * (0.6 if is_main else 0.7)
        glow = QRadialGradient(center, glow_radius)
        if is_main:
            glow.setColorAt(0.0, QColor(255, 255, 255, 42))
            glow.setColorAt(0.4, QColor(255, 255, 255, 24))
        else:
            glow.setColorAt(0.0, QColor(255, 255, 255, 38))
            glow.setColorAt(0.4, QColor(255, 255, 255, 22))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)

        painter.restore()
