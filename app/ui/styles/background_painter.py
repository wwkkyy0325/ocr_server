# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：绘制玻璃/波点/磨砂背景效果，统一 UI 视觉风格
# - 核心实现：根据 ConfigManager 的主题与背景设置选择不同绘制方案
# - 关联关系：由主窗口与对话框在绘制阶段调用，配合 glass_components 使用
try:
    from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QBrush
    from PyQt5.QtCore import Qt, QPoint, QPointF
except ImportError:
    # 定义占位符，避免 NameError
    QPainter = None
    QColor = None
    QRadialGradient = None
    QBrush = None
    Qt = None
    QPoint = None
    QPointF = None

from app.infrastructure.error_handler import handle_errors, ErrorCode
from app.log.log_bus import get_logger

logger = get_logger()


class BackgroundPainter:
    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="BackgroundPainter")
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        logger.debug("background_painter", "initialized", "BackgroundPainter initialized")

    def _get_glass_background_style(self):
        """获取玻璃背景样式配置"""
        # 默认样式
        style = 'glass'
        if self.config_manager:
            try:
                # 安全获取配置
                style = self.config_manager.get_setting('glass_background', 'glass')
            except Exception as e:
                logger.warning("background_painter", "config_read_failed", f"读取背景样式配置失败：{e}")
                style = 'glass'
        # 确保样式有效
        if style not in ('glass', 'dots', 'frosted'):
            logger.debug("background_painter", "invalid_style_fallback", f"无效的背景样式 '{style}'，回退到默认值")
            style = 'glass'
        return style

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="BackgroundPainter")
    def paint_background(self, painter, path, rect, is_main=False):
        """Public method to paint background"""
        try:
            style = self._get_glass_background_style()
            if style == 'glass':
                self._paint_plain_glass_background(painter, path, is_main=is_main)
            elif style == 'frosted':
                self._paint_frosted_background(painter, path, rect, is_main=is_main)
            else:
                self._paint_dots_background(painter, path, rect, is_main=is_main)
        except Exception as e:
            logger.error("background_painter", "paint_failed", f"背景绘制失败：{e}", exc_info=True)
            # 降级处理：绘制纯色背景
            if painter and path:
                painter.fillPath(path, QColor(0, 0, 0))

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="BackgroundPainter")
    def _paint_plain_glass_background(self, painter, path, is_main=False):
        """绘制纯色玻璃背景"""
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

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="BackgroundPainter")
    def _paint_dots_background(self, painter, path, rect, is_main=False):
        """绘制波点玻璃背景"""
        painter.save()
        try:
            # 先绘制底色
            self._paint_plain_glass_background(painter, path, is_main=is_main)

            painter.setPen(Qt.NoPen)
            left = rect.left()
            top = rect.top()
            right = rect.right()
            bottom = rect.bottom()
            offset = 7

            # 只有在主界面才绘制复杂的波点带
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
                    painter.setBrush(QBrush(grad))
                    painter.drawEllipse(c, cluster_radius, cluster_radius)
            else:
                # 弹窗/对话框：简单的波点
                y = top + offset
                while y < bottom:
                    x = left + offset
                    painter.setBrush(QColor(255, 255, 255, 46))
                    radius = 1.3
                    step_x = 14
                    while x < right:
                        painter.drawEllipse(QPointF(x, y), radius, radius)
                        x += step_x
                    y += 18
        except Exception as e:
            logger.error("background_painter", "dots_paint_failed", f"波点背景绘制失败：{e}", exc_info=True)
            # 降级处理：只绘制底色
            self._paint_plain_glass_background(painter, path, is_main=is_main)
        finally:
            painter.restore()

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="BackgroundPainter")
    def _paint_frosted_background(self, painter, path, rect, is_main=False):
        """绘制磨砂玻璃背景效果"""
        painter.save()
        try:
            # 底色
            painter.fillPath(path, QColor(20, 25, 40, 210))

            # 简单的光晕效果模拟磨砂感
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
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, glow_radius, glow_radius)
        except Exception as e:
            logger.error("background_painter", "frosted_paint_failed", f"磨砂背景绘制失败：{e}", exc_info=True)
            # 降级处理：只绘制底色
            painter.fillPath(path, QColor(20, 25, 40, 210))
        finally:
            painter.restore()
