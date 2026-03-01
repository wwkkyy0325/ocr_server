# -*- coding: utf-8 -*-
try:
    from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QStyle
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from app.core.clipboard_watcher import ClipboardWatcher
from app.ui.widgets.floating_result_widget import FloatingResultWidget

class ScreenshotController:
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
        # Screenshot Mode Init
        self.clipboard_watcher = ClipboardWatcher()
        self.clipboard_watcher.image_captured.connect(self.process_clipboard_image)
        
        self.floating_widget = FloatingResultWidget()
        self.floating_widget.restore_requested.connect(self.restore_from_tray)
        
        # Connect main window signal
        if hasattr(self.main_window, 'ocr_result_ready_signal'):
            self.main_window.ocr_result_ready_signal.connect(self.on_ocr_result_ready)
        
        # Tray Icon
        self.tray_icon = QSystemTrayIcon(self.main_window.main_window)
        
        # Try to get window icon, fallback to system icon
        icon = self.main_window.main_window.windowIcon()
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        self.tray_menu = QMenu()
        self.act_restore = QAction("显示主界面 (Show Main Window)", self.main_window.main_window)
        self.act_restore.triggered.connect(self.restore_from_tray)
        
        self.act_stop_screenshot_mode = QAction("停止自动截屏 (Stop Auto-OCR)", self.main_window.main_window)
        self.act_stop_screenshot_mode.triggered.connect(self.stop_screenshot_mode_action)
        # Initially hidden or disabled
        self.act_stop_screenshot_mode.setVisible(False)
        
        self.act_quit = QAction("退出程序 (Quit)", self.main_window.main_window)
        self.act_quit.triggered.connect(self.main_window.quit_application)
        
        self.tray_menu.addAction(self.act_restore)
        self.tray_menu.addAction(self.act_stop_screenshot_mode)
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
                
            self.act_stop_screenshot_mode.setVisible(True)
        else:
            self.clipboard_watcher.stop()
            self.logger.info("Screenshot Auto-OCR Mode Disabled")
            if self.main_window.main_window:
                self.main_window.main_window.showNormal()
                self.main_window.main_window.activateWindow()
                self.tray_icon.hide()
                if hasattr(self.main_window.main_window, 'statusBar'):
                    self.main_window.main_window.statusBar().showMessage("自动截屏识别模式已关闭")
                
            self.act_stop_screenshot_mode.setVisible(False)

    def stop_screenshot_mode_action(self):
        """Action for tray menu to stop screenshot mode"""
        # Call main window's toggle method to ensure UI consistency if needed
        # Or check the action in main window if it exists
        if hasattr(self.main_window, 'act_screenshot_mode') and self.main_window.act_screenshot_mode.isChecked():
            self.main_window.act_screenshot_mode.setChecked(False)
        else:
            self.toggle_screenshot_mode(False)

    def restore_from_tray(self):
        """Restore main window from tray"""
        if hasattr(self.main_window, 'act_screenshot_mode') and self.main_window.act_screenshot_mode.isChecked():
             self.main_window.act_screenshot_mode.setChecked(False)
        else:
             self.toggle_screenshot_mode(False)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_from_tray()

    def process_clipboard_image(self, qimage):
        """Process captured clipboard image"""
        self.logger.info(f"Processing clipboard image")
        
        # Save QImage to temp file
        import os
        import tempfile
        
        # Use project temp dir
        temp_dir = os.path.join(self.main_window.project_root, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"clipboard_{int(import_time.time())}.png")
        
        qimage.save(temp_path, "PNG")
        
        # Show floating widget
        if self.floating_widget:
            self.floating_widget.show_loading()
        
        # Use main window's processing logic (single file)
        self.main_window._process_single_image_task(temp_path, is_clipboard=True)

    def on_ocr_result_ready(self, result_text):
        if self.floating_widget:
            self.floating_widget.show_result(result_text)

import time as import_time
