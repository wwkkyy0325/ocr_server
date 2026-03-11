# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：应用入口，负责初始化 GUI 模式，构建主窗口实例
# - 核心实现：初始化 ConfigManager，以 GUI 模式启动 MainWindow
# - 关联关系：作为 run/launcher 的逻辑入口之一；MainWindow 负责界面与交互，核心处理流程由 ProcessingController 等组件承载

import os
import sys
from app.log.log_bus import get_logger

logger = get_logger()

# 添加项目路径到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 注意：环境变量配置已在 run.py 中统一处理，此处不再重复调用

# PyQt 相关导入
try:
    from PyQt5.QtWidgets import QApplication

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logger.error("main", "pyqt5_not_available", "PyQt5 not available, using console mode")

from app.ui.main_window import MainWindow
from app.config.config_manager import ConfigManager


def main():
    config_manager = ConfigManager()
    config_manager.load_config()
    app = None
    if PYQT_AVAILABLE:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        try:
            # 中文路径检查逻辑已移除
            pass
        except Exception:
            pass
    try:
        main_window = MainWindow(config_manager)
        main_window.show()
        # 运行 Qt 事件循环
        if PYQT_AVAILABLE and app:
            sys.exit(app.exec_())
    except Exception as e:
        import traceback
        error_msg = f"程序启动失败/Program Crash:\n{str(e)}\n\n{traceback.format_exc()}"
        logger.error("main", "program_crash", error_msg)
        if PYQT_AVAILABLE:
            try:
                from PyQt5.QtWidgets import QMessageBox
                if QApplication.instance() is None:
                    _ = QApplication(sys.argv)
                QMessageBox.critical(None, "致命错误 / Fatal Error", error_msg)
            except:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
