# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：引导与展示模型下载进度的对话框
# - 核心实现：后台线程执行 ModelManager.download_model，通过进度/完成信号更新 UI
# - 关联关系：由主窗口或设置面板在缺失模型时弹出，保障识别流程依赖完整
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar,
                             QPushButton)
from PyQt5.QtCore import QThread, pyqtSignal
from app.ui.dialogs.glass_dialogs import GlassMessageDialog
from app.event.event_bus import get_signal_bus
from app.infrastructure.error_handler import handle_errors, ErrorCode, NetworkError


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)  # downloaded, total
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, model_manager, model_type, model_key):
        super().__init__()
        self.model_manager = model_manager
        self.model_type = model_type
        self.model_key = model_key

    @handle_errors(
        error_code=ErrorCode.DOWNLOAD_FAILED_001,
        fallback_return=False,
        component="DownloadWorker",
        operation="download_model"
    )
    def _download_model_with_error_handling(self):
        """带错误处理的下载方法"""
        return self.model_manager.download_model(
            self.model_type,
            self.model_key,
            self.report_progress
        )

    def run(self):
        try:
            success = self._download_model_with_error_handling()
            if success:
                self.finished.emit(True, "加载完成")    # type: ignore
            else:
                self.finished.emit(False, "下载失败，请检查网络连接")   # type: ignore
        except NetworkError as e:
            # 网络错误，提供友好提示
            error_msg = f"网络错误：{str(e)}" if str(e) else "无法连接到下载服务器，请检查网络连接"
            self.finished.emit(False, error_msg)   # type: ignore
        except Exception as e:
            # 其他错误，记录详细日志
            self.finished.emit(False, f"下载失败：{str(e)}")   # type: ignore

    def report_progress(self, downloaded, total):
        self.progress.emit(downloaded, total)   # type: ignore


class ModelDownloadDialog(QDialog):
    def __init__(self, model_manager, missing_models, parent=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.missing_models = missing_models  # List of (type, key, name)
        self.current_index = 0
        self._bus = get_signal_bus()
        self.worker = None  # Initialize worker attribute

        self.setWindowTitle("加载模型")
        self.setFixedSize(400, 200)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.status_label = QLabel("正在加载模型资源...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.info_label = QLabel("模型较大，首次加载时间可能略长，请稍候。")
        layout.addWidget(self.info_label)

        layout.addStretch()

        self.cancel_btn = QPushButton("取消加载")
        self.cancel_btn.clicked.connect(self.reject)    # type: ignore
        layout.addWidget(self.cancel_btn)

        self._bus.download.model_download_progress.connect(self.update_progress)    # type: ignore
        self._bus.download.model_download_finished.connect(self.on_download_finished)    # type: ignore

        # Start download automatically
        self.start_next_download()

    def start_next_download(self):
        if self.current_index >= len(self.missing_models):
            self.accept()
            return

        m_type, m_key, m_desc = self.missing_models[self.current_index]
        self.status_label.setText(f"正在加载 {m_desc} ({self.current_index + 1}/{len(self.missing_models)})...")
        self.progress_bar.setValue(0)
        self.info_label.setText("准备中...")

        self.worker = DownloadWorker(self.model_manager, m_type, m_key)
        self.worker.progress.connect(self._bus.download.model_download_progress)    # type: ignore
        self.worker.finished.connect(self._bus.download.model_download_finished)    # type: ignore
        self.worker.start()

    def update_progress(self, downloaded, total):
        if total > 0:
            percent = int(downloaded * 100 / total)
            self.progress_bar.setValue(percent)
            self.info_label.setText(f"{downloaded / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB")

    def on_download_finished(self, success, message):
        if success:
            self.current_index += 1
            self.start_next_download()
        else:
            dlg = GlassMessageDialog(
                self,
                title="加载失败",
                text=f"模型加载失败: {message}",
                buttons=[("ok", "确定")],
            )
            dlg.exec_()  # type: ignore
            self.reject()

    def reject(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
        super().reject()
