# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QAction, QSystemTrayIcon, QStyle
from PyQt5.QtCore import Qt, QEvent

from app.ui.styles.glass_components import FramelessBorderWindow
from app.ui.dialogs.glass_dialogs import GlassMessageDialog

class CustomMainWindow(FramelessBorderWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._current_theme = None

    def closeEvent(self, event):
        if getattr(self.controller, '_is_quitting', False):
            self.controller.cleanup()
            event.accept()
            return
        
        dlg = GlassMessageDialog(
            self,
            title="退出确认",
            text="您想要如何操作？",
            buttons=[
                ("minimize", "最小化到托盘"),
                ("quit", "直接退出"),
                ("cancel", "取消"),
            ],
        )
        dlg.exec_()

        result = dlg.result_key()
        if result == "cancel" or result is None:
            event.ignore()
            return

        if result == "minimize":
            event.ignore()
            self.hide()
            self.controller.tray_icon.show()
        elif result == "quit":
            self.controller.cleanup()
            event.accept()

    def apply_theme(self, theme_name, theme_def):
        self._current_theme = theme_name
        app = QApplication.instance()
        if not app or not theme_def:
            return
        base_rgba = theme_def.get('window_rgba', '15,20,35,230')
        palette_bg = theme_def.get('panel_rgba', '10,15,30,220')
        try:
            bg_style = self.controller.config_manager.get_setting('glass_background', 'glass')
        except Exception:
            bg_style = 'glass'
        if bg_style in ('dots', 'frosted'):
            parts = [p.strip() for p in str(palette_bg).split(',')]
            if len(parts) == 4:
                parts[-1] = '140'
                palette_bg = ','.join(parts)
        accent = theme_def.get('accent_color', '#00FF9C')
        accent_soft = theme_def.get('accent_soft', '#00CC88')
        text_primary = theme_def.get('text_primary', '#E8F7FF')
        text_secondary = theme_def.get('text_secondary', '#8899AA')
        danger = theme_def.get('danger_color', '#FF4B81')
        success = theme_def.get('success_color', '#2DF3A3')
        border = theme_def.get('border_color', '#1E2940')
        highlight = theme_def.get('selection_color', '#1E9FFF')
        style = f"""
            QMainWindow {{
                background-color: rgba({base_rgba});
                border: none;
            }}
            QWidget {{
                background-color: rgba({palette_bg});
                color: {text_primary};
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 13px;
            }}
            QMenuBar, QMenu {{
                background-color: rgba({palette_bg});
                color: {text_primary};
                border: 2px solid {accent};
            }}
            QMenuBar {{
                border-radius: 8px;
                padding: 2px 8px;
            }}
            QMenuBar::item:selected {{
                background-color: rgba(255,255,255,26);
                color: {accent};
            }}
            QMenu::item:selected {{
                background-color: rgba(255,255,255,26);
                color: {accent};
            }}
            QToolBar {{
                background-color: rgba({palette_bg});
                border-bottom: 1px solid {border};
            }}
            QStatusBar {{
                background-color: rgba({palette_bg});
                color: {text_secondary};
                border-top: 1px solid {border};
            }}
            QGroupBox {{
                border: 2px solid {accent};
                border-radius: 10px;
                margin-top: 18px;
                background-color: rgba(255,255,255,8);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: {accent};
            }}
            QLabel#modelLabel {{
                color: {accent};
                font-weight: 600;
            }}
            QListWidget, QTreeView {{
                background-color: rgba(8,12,26,230);
                border: 2px solid {accent};
                border-radius: 8px;
                selection-background-color: {highlight};
                selection-color: {text_primary};
            }}
            QTextEdit, QPlainTextEdit {{
                background-color: rgba(6,10,22,120);
                border: 1px solid {border};
                selection-background-color: {highlight};
                selection-color: {text_primary};
            }}
            QTableView, QTableWidget {{
                background-color: rgba(18,24,40,150);
                alternate-background-color: rgba(10,16,30,130);
                gridline-color: {border};
                color: {text_primary};
                selection-background-color: {highlight};
                selection-color: {text_primary};
                border: 2px solid {accent};
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: rgba(12,20,40,240);
                color: {text_secondary};
                padding: 4px 6px;
                border: 0px;
                border-bottom: 1px solid {border};
                border-right: 1px solid {border};
            }}
            QPushButton {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 rgba(255,245,210,95),
                                                 stop:0.22 rgba(255,245,210,26),
                                                 stop:0.55 rgba(255,255,255,8),
                                                 stop:1 rgba(255,255,255,42));
                color: {text_primary};
                border-radius: 10px;
                padding: 7px 20px;
                border: 1px solid {accent};
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 rgba(255,248,220,150),
                                                 stop:0.22 rgba(255,245,210,60),
                                                 stop:0.55 rgba(255,255,255,26),
                                                 stop:1 rgba(255,255,255,100));
                border: 2px solid {accent};
            }}
            QPushButton:focus {{
                border: 1px solid {accent};
            }}
            QPushButton:pressed {{
                background-color: rgba(0,0,0,170);
                border-color: {accent};
                color: {accent};
            }}
            QPushButton:disabled {{
                background-color: rgba(60,60,70,200);
                color: #888888;
                border-color: #444444;
            }}
            QPushButton#dangerButton {{
                background-color: {danger};
                border-color: {danger};
            }}
            QLabel#titleLabel {{
                color: {accent};
                font-size: 16px;
                font-weight: 600;
                letter-spacing: 2px;
            }}
            QWidget#titleBar {{
                background-color: rgba({base_rgba});
                border-bottom: none;
            }}
            QPushButton#titleMinButton,
            QPushButton#titleMaxButton,
            QPushButton#titleCloseButton {{
                background-color: transparent;
                border: none;
                color: {text_secondary};
                padding: 0;
                margin: 0;
            }}
            QPushButton#titleMinButton:hover,
            QPushButton#titleMaxButton:hover {{
                background-color: rgba(255,255,255,40);
            }}
            QPushButton#titleCloseButton:hover {{
                background-color: {danger};
                color: #050810;
            }}
            QPushButton#primaryStartButton {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 rgba(255,248,220,135),
                                                 stop:0.2 rgba(255,245,210,40),
                                                 stop:0.55 rgba(255,255,255,14),
                                                 stop:1 rgba(255,255,255,80));
                color: {accent};
                font-size: 14px;
                font-weight: 700;
                padding: 9px 34px;
                border-radius: 10px;
                border: 1px solid rgba(255,245,210,180);
                letter-spacing: 2px;
            }}
            QPushButton#primaryStartButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 rgba(255,251,230,165),
                                                 stop:0.22 rgba(255,248,220,60),
                                                 stop:0.6 rgba(255,255,255,22),
                                                 stop:1 rgba(255,255,255,105));
                border-color: {accent};
            }}
            QPushButton#primaryStopButton {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 rgba(255,248,220,135),
                                                 stop:0.2 rgba(255,245,210,40),
                                                 stop:0.55 rgba(255,255,255,14),
                                                 stop:1 rgba(255,255,255,80));
                color: {danger};
                font-size: 14px;
                font-weight: 700;
                padding: 9px 34px;
                border-radius: 10px;
                border: 1px solid rgba(255,245,210,180);
                letter-spacing: 2px;
            }}
            QPushButton#primaryStopButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                 stop:0 rgba(255,251,230,165),
                                                 stop:0.22 rgba(255,248,220,60),
                                                 stop:0.6 rgba(255,255,255,22),
                                                 stop:1 rgba(255,255,255,105));
                border-color: #ff85a1;
            }}
            QCheckBox, QRadioButton, QLabel {{
                color: {text_primary};
            }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                background-color: qradialgradient(cx:0.5, cy:0.3, radius:0.8,
                                                  fx:0.5, fy:0.2,
                                                  stop:0 rgba(255,255,255,80),
                                                  stop:0.4 rgba(180,180,190,200),
                                                  stop:1 rgba(10,12,24,230));
                border: 1px solid rgba(255,245,210,120);
                margin-right: 6px;
            }}
            QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
                border: 1px solid {accent};
            }}
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                background-color: qradialgradient(cx:0.5, cy:0.3, radius:0.8,
                                                  fx:0.5, fy:0.2,
                                                  stop:0 rgba(255,255,255,230),
                                                  stop:0.4 {accent},
                                                  stop:1 rgba(5,8,20,230));
                border: 1px solid {accent};
            }}
            QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
                background-color: rgba(40,40,50,180);
                border: 1px solid rgba(80,80,90,180);
            }}
            QDockWidget {{
                background-color: rgba({palette_bg});
                border: 2px solid {accent};
            }}
            QDockWidget::title {{
                background-color: rgba(10,10,25,240);
                color: {text_secondary};
                padding-left: 8px;
                border-bottom: 2px solid {accent};
            }}
            ImageViewer, #imageViewerPanel {{
                border: 2px solid {accent};
                border-radius: 10px;
                background-color: transparent;
            }}
            TextBlockListWidget, #textResultList {{
                border: 2px solid {accent};
                border-radius: 8px;
                background-color: rgba(8,12,26,130);
            }}
            #rawTextResult {{
                border: 2px solid {accent};
                border-radius: 8px;
                background-color: rgba(6,10,22,110);
            }}
            QSplitter::handle {{
                background-color: #111624;
            }}
            QScrollBar:vertical {{
                background: #050814;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar:horizontal {{
                background: #050814;
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {accent_soft};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {accent_soft};
                min-width: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: transparent;
                border: none;
            }}
            QTabWidget::pane {{
                border: 1px solid {border};
                border-radius: 8px;
                top: 1px;
                background-color: rgba({palette_bg});
            }}
            QTabBar::tab {{
                background-color: rgba(8,12,26,220);
                color: {text_secondary};
                padding: 6px 14px;
                border: 1px solid {border};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: rgba(12,20,40,235);
                color: {text_primary};
                border-bottom-color: {accent};
            }}
            QTabBar::tab:hover {{
                color: {accent};
            }}
            AnnouncementBanner QLabel#announcementPrefix {{
                color: {accent};
                font-weight: 600;
                letter-spacing: 2px;
            }}
            AnnouncementBanner QLabel#announcementText {{
                color: {text_secondary};
            }}
        """
        app.setStyleSheet(style)
