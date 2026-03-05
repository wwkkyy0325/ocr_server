# -*- coding: utf-8 -*-
#
# 文件说明：
# - 作用：自动截屏识别控制器，基于剪贴板监听实现"截屏即识别"
# - 核心实现：托盘图标与菜单控制、ClipboardWatcher 监听、悬浮结果窗口显示
# - 关联关系：由 MainWindow 管理其启停，使用 FloatingResultWidget 独立显示结果

try:
    from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QStyle
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from app.core.clipboard_watcher import ClipboardWatcher
from app.ui.widgets.floating_result_widget import FloatingResultWidget
from app.core.signal_bus import get_signal_bus

class ScreenshotController:
    """
    截屏识别控制器 - 使用独立悬浮窗口显示结果
    
    核心理念：
    1. 使用 FloatingResultWidget 独立显示识别结果
    2. 主窗口保持后台运行，不主动显示
    3. 用户可通过悬浮窗快速查看和复制结果
    
    主要方法：
    - process_clipboard_image(): 处理剪贴板图像并显示到悬浮窗
    - on_ocr_result_ready(): 接收识别结果并更新悬浮窗
    - toggle_screenshot_mode(): 启用/禁用自动截屏模式
    """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = main_window.logger
        self.config_manager = main_window.config_manager
        
        self.clipboard_watcher = None
        self.floating_widget = None
        self.tray_icon = None
        self.tray_menu = None
        
        if PYQT_AVAILABLE:
            self._init_components()

    def _init_components(self):
        # 初始化剪贴板监听器
        self.clipboard_watcher = ClipboardWatcher()
        bus = get_signal_bus()
        self.clipboard_watcher.image_captured.connect(bus.capture.image_captured)
        bus.capture.image_captured.connect(self.process_clipboard_image)
        
        # 初始化悬浮结果窗口
        self.floating_widget = FloatingResultWidget()
        self.floating_widget.restore_requested.connect(self.exit_screenshot_mode)
        
        # 连接主窗口信号（用于接收识别完成通知）
        if hasattr(self.main_window, 'ocr_result_ready_signal'):
            self.main_window.ocr_result_ready_signal.connect(get_signal_bus().processing.ocr_result_ready)
            get_signal_bus().processing.ocr_result_ready.connect(self.on_ocr_result_ready)
        
        # 初始化托盘图标
        self.tray_icon = QSystemTrayIcon(self.main_window.main_window)
        
        # 获取窗口图标
        icon = self.main_window.main_window.windowIcon()
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        # 创建托盘菜单
        self.tray_menu = QMenu()
        
        # 退出自动截屏模式按钮（同时负责恢复主窗口）
        self.act_exit_screenshot_mode = QAction("退出自动截屏模式 (Exit Auto-OCR)", self.main_window.main_window)
        self.act_exit_screenshot_mode.triggered.connect(self.exit_screenshot_mode)
        self.act_exit_screenshot_mode.setVisible(False)  # 初始隐藏，只在自动截屏模式开启时显示
        
        self.act_quit = QAction("退出程序 (Quit)", self.main_window.main_window)
        self.act_quit.triggered.connect(self.main_window.quit_application)
        
        self.tray_menu.addAction(self.act_exit_screenshot_mode)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.act_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def toggle_screenshot_mode(self, enabled):
        """Toggle Screenshot Auto-OCR Mode"""
        if not self.clipboard_watcher:
            return
            
        if enabled:
            self.clipboard_watcher.start()
            self.logger.info("Screenshot Auto-OCR Mode Enabled")
            
            # Hide main window and show tray
            if self.main_window.main_window:
                self.tray_icon.show()
                self.tray_icon.showMessage("自动截屏识别已开启", "软件已隐藏到后台，监测到截屏时将自动识别。\n双击托盘图标可恢复主界面。", QSystemTrayIcon.Information, 3000)
                self.main_window.main_window.hide()
                
            # 显示退出自动截屏模式按钮
            self.act_exit_screenshot_mode.setVisible(True)
        else:
            self.clipboard_watcher.stop()
            self.logger.info("Screenshot Auto-OCR Mode Disabled")
            if self.main_window.main_window:
                self.main_window.main_window.showNormal()
                self.main_window.main_window.activateWindow()
                self.tray_icon.hide()
                if hasattr(self.main_window.main_window, 'statusBar'):
                    self.main_window.main_window.statusBar().showMessage("自动截屏识别模式已关闭")
                
            # 隐藏退出自动截屏模式按钮
            self.act_exit_screenshot_mode.setVisible(False)

    def exit_screenshot_mode(self):
        """
        退出自动截屏模式并恢复主窗口
        
        流程说明：
        1. 停止自动截屏模式
        2. 显示并激活主窗口
        3. 隐藏悬浮窗和托盘图标
        4. 清理相关状态
        """
        # 1. 停止自动截屏模式
        if hasattr(self.main_window, 'act_screenshot_mode') and self.main_window.act_screenshot_mode.isChecked():
            self.main_window.act_screenshot_mode.setChecked(False)
        else:
            self.toggle_screenshot_mode(False)
        
        # 2. 显示并激活主窗口
        if self.main_window.main_window:
            self.main_window.main_window.showNormal()
            self.main_window.main_window.activateWindow()
            self.main_window.main_window.raise_()
            
            # 显示状态提示
            if hasattr(self.main_window.main_window, 'statusBar'):
                self.main_window.main_window.statusBar().showMessage("已从自动截屏模式恢复主界面", 3000)
        
        # 3. 隐藏悬浮窗
        if self.floating_widget:
            self.floating_widget.hide()
        
        # 4. 隐藏托盘图标
        if self.tray_icon:
            self.tray_icon.hide()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.exit_screenshot_mode()

    def process_clipboard_image(self, qimage):
        """
        处理剪贴板图像 - 复用主窗口处理流程
            
        流程说明：
        1. 保存 QImage 到临时文件
        2. 显示悬浮窗（加载中状态）并显示图片
        3. 调用主窗口的 _process_single_file 方法（走批处理流程）
        4. 识别完成后，ProcessingController 会发射 structured_result_ready_signal
        5. 截图控制器接收信号并更新悬浮窗的所有组件
            
        Args:
            qimage: 从剪贴板获取的 QImage 对象
        """
        self.logger.info(f"Processing clipboard image")
            
        import os
        import time
            
        # 保存到项目临时目录
        temp_dir = os.path.join(self.main_window.project_root, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"clipboard_{int(time.time())}.png")
            
        # 保存图像
        qimage.save(temp_path, "PNG")
            
        # 🔥 显示悬浮窗（加载状态 + 图片预览）
        if self.floating_widget:
            self.floating_widget.show_loading()
            # 立即显示图片到预览框
            self.floating_widget.display_image(temp_path)
            
        # 🔥 关键修改：不再直接调用 OCR 引擎，而是调用主窗口的处理方法
        # 这样就能复用 ProcessingController 的所有信号和逻辑
        # 注意：这里使用 _start_processing_files 会触发完整的批处理流程
        # 包括发射 structured_result_ready_signal 信号
        self.main_window._start_processing_files([temp_path])
            
        # 用户会看到：
        # - 屏幕右上角出现悬浮窗，显示截屏图片和"正在识别..."
        # - 识别完成后，悬浮窗自动更新：
        #   - 图片上显示白色轮廓标注
        #   - 文本结果栏显示识别的文字
        #   - 表格结果栏显示结构化数据（如果有表格）

    def on_ocr_result_ready(self, result_text):
        """
        接收识别完成结果 - 悬浮窗方案
        
        流程说明：
        1. 主窗口处理完成后发射 ocr_result_ready_signal 信号
        2. 此方法接收信号并更新悬浮窗显示结果
        3. 用户可以立即查看和复制识别结果
        
        Args:
            result_text: 识别结果文本
        """
        # 🔥 更新悬浮窗显示结果
        if self.floating_widget:
            self.floating_widget.show_result(result_text)
            self.logger.debug(f"OCR result displayed in floating widget")
    
    def on_structured_result_ready(self, items):
        """
        接收结构化 OCR 结果（包含 box、polygon、table_info 等）
        
        流程说明：
        1. 主窗口处理完成后调用此方法传递结构化数据
        2. 使用这些数据更新悬浮窗的所有组件（图片标注 + 表格 + 文本）
        
        Args:
            items: 标准化的 OCR 结果列表，每项包含 text/box/polygon/table_info
        """
        print(f"DEBUG [ScreenshotController] on_structured_result_ready called with {len(items)} items")
        # 🔥 更新悬浮窗的所有组件
        if self.floating_widget and hasattr(self.floating_widget, 'set_ocr_results'):
            try:
                print(f"DEBUG [ScreenshotController] Calling floating_widget.set_ocr_results")
                self.floating_widget.set_ocr_results(items)
                print(f"DEBUG [ScreenshotController] Structured OCR results displayed: {len(items)} items")
            except Exception as e:
                print(f"ERROR [ScreenshotController] Failed to set structured results: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"ERROR [ScreenshotController] floating_widget not available or missing set_ocr_results method")

# 文件末尾添加 time 导入
import time
