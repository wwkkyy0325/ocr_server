# -*- coding: utf-8 -*-
#
# 文件说明：
# - 作用：动态状态栏组件，统一显示当前状态与加载动画
# - 核心实现：颜色映射 + 省略号动画 + Tick 实时更新，提供 set_status 接口
# - 关联关系：主窗口/控制器在任务执行与完成时调用以更新反馈，同时绑定到 TickScheduler 实现实时更新
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor

class DynamicStatusBar(QWidget):
    """
    动态状态栏组件
    支持：
    1. 动态省略号动画 (Loading...)
    2. 不同状态颜色 (Info, Success, Warning, Error)
    3. 图标/文字显示
    4. 实时系统状态监控（OCR 子进程、模型状态、处理进度等）
    """
    
    # 状态类型定义
    STATUS_READY = "ready"
    STATUS_INFO = "info"
    STATUS_SUCCESS = "success"
    STATUS_WARNING = "warning"
    STATUS_ERROR = "error"
    STATUS_WORKING = "working" # 包含动画
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)
        self.layout.setSpacing(10)
        
        # 状态指示灯（用颜色块或图标代替）
        self.indicator = QLabel(self)
        self.indicator.setFixedSize(10, 10)
        self.indicator.setStyleSheet("background-color: #00FF00; border-radius: 5px;")
        
        # 状态文本
        self.label = QLabel("就绪", self)
        self.label.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        
        self.layout.addWidget(self.indicator)
        self.layout.addWidget(self.label)
        self.layout.addStretch()
        
        # 动画定时器
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_dots = 0
        self.base_text = ""
        self.is_animating = False
        
        # 颜色配置
        self.colors = {
            self.STATUS_READY: "#00FF00",    # 绿色
            self.STATUS_INFO: "#3498db",     # 蓝色
            self.STATUS_SUCCESS: "#2ecc71",  # 绿色
            self.STATUS_WARNING: "#f1c40f",  # 黄色
            self.STATUS_ERROR: "#e74c3c",    # 红色
            self.STATUS_WORKING: "#9b59b6"   # 紫色
        }
        
        # 系统状态缓存
        self.system_status_cache = {}
        
        # 初始化锁定标志 - 防止在初始化期间被 Tick 更新覆盖
        self.initializing_lock = False
        
        # 绑定到 TickScheduler (每 20 ticks ≈ 1 秒更新一次)
        try:
            from app.core.tick_scheduler import get_tick_scheduler
            get_tick_scheduler().register_system(
                "StatusBarUpdater",
                self._update_system_status,
                every_ticks=20,
                priority=0
            )
        except Exception as e:
            print(f"Failed to register StatusBarUpdater to TickScheduler: {e}")
        
        # 注册到日志控制器
        try:
            from app.core.logger_controller import get_logger, LogLevel
            logger = get_logger()
            logger.set_status_callback(self.set_status)
            logger.enable_component("ocr_subprocess")
            logger.enable_component("processing")
            logger.enable_component("ui")
        except Exception as e:
            print(f"Failed to register with LoggerController: {e}")

    def set_status(self, text, status_type=STATUS_INFO):
        """
        设置状态
        Args:
            text: 显示文本
            status_type: 状态类型 (ready, info, success, warning, error, working)
        """
        self.base_text = text
        self.label.setText(text)
        
        # 将 LogLevel 映射为状态栏常量
        from app.core.logger_controller import LogLevel
        if isinstance(status_type, LogLevel):
            status_map = {
                LogLevel.DEBUG: self.STATUS_INFO,
                LogLevel.INFO: self.STATUS_INFO,
                LogLevel.SUCCESS: self.STATUS_SUCCESS,
                LogLevel.WARNING: self.STATUS_WARNING,
                LogLevel.ERROR: self.STATUS_ERROR,
                LogLevel.WORKING: self.STATUS_WORKING
            }
            status_type = status_map.get(status_type, self.STATUS_INFO)
        
        # 设置指示器颜色
        color = self.colors.get(status_type, "#FFFFFF")
        self.indicator.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self.label.setStyleSheet(f"color: {color}; font-size: 12px;")
        
        # 管理初始化锁定
        if "正在加载" in text or "初始化" in text:
            self.initializing_lock = True
        elif status_type in [self.STATUS_SUCCESS, self.STATUS_ERROR]:
            # 成功或失败后，延迟 3 秒解锁，让用户看清提示
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(3000, self._unlock_initialization)
        
        # 处理动画
        if status_type == self.STATUS_WORKING:
            if not self.is_animating:
                self.is_animating = True
                self.animation_dots = 0
                self.animation_timer.start(500) # 500ms 更新一次
        else:
            if self.is_animating:
                self.is_animating = False
                self.animation_timer.stop()
                self.label.setText(text) # 恢复无省略号文本

    def _update_animation(self):
        """更新省略号动画"""
        self.animation_dots = (self.animation_dots + 1) % 4
        dots = "." * self.animation_dots
        self.label.setText(f"{self.base_text}{dots}")
    
    def _unlock_initialization(self):
        """解除初始化锁定，允许 Tick 更新系统状态"""
        self.initializing_lock = False
    
    def _update_system_status(self):
        """
        定时更新系统状态（每 1 秒调用一次）
        检查 OCR 子进程、模型状态等，并实时更新状态栏
        """
        try:
            # 获取 OCR 子进程状态
            ocr_status = None
            try:
                from app.core.ocr_subprocess import get_ocr_subprocess_manager
                from app.core.config_manager import get_config_manager
                config_mgr = get_config_manager()
                subprocess_mgr = get_ocr_subprocess_manager(config_mgr)
                
                if subprocess_mgr and subprocess_mgr.is_running():
                    ocr_status = f"OCR 子进程运行中 (预设：{subprocess_mgr.current_preset})"
                else:
                    ocr_status = "OCR 子进程未运行"
            except Exception as e:
                ocr_status = f"OCR 状态检查失败：{e}"
            
            # 缓存状态信息
            self.system_status_cache['ocr'] = ocr_status
            
            # 如果当前没有正在进行的任务，显示系统状态
            # 但如果处于初始化锁定状态，不要覆盖提示
            if not self.is_animating and not self.initializing_lock and (self.base_text in ["就绪", ""] or self.base_text.startswith("系统状态:")):
                # 构建综合状态信息
                status_parts = []
                if ocr_status:
                    status_parts.append(ocr_status)
                
                if status_parts:
                    status_text = "系统状态：" + " | ".join(status_parts)
                    # 只在内容变化时更新，避免闪烁
                    if self.label.text() != status_text:
                        self.label.setText(status_text)
                        self.label.setStyleSheet(f"color: {self.colors[self.STATUS_INFO]}; font-size: 12px;")
                        self.indicator.setStyleSheet(f"background-color: {self.colors[self.STATUS_INFO]}; border-radius: 5px;")
        
        except Exception as e:
            # 静默失败，不影响主功能
            pass
