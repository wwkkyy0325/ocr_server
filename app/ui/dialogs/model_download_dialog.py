# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar, 
                             QPushButton, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class DownloadWorker(QThread):
    progress = pyqtSignal(int, int) # downloaded, total
    finished = pyqtSignal(bool, str) # success, message
    
    def __init__(self, model_manager, model_type, model_key):
        super().__init__()
        self.model_manager = model_manager
        self.model_type = model_type
        self.model_key = model_key
        
    def run(self):
        try:
            success = self.model_manager.download_model(
                self.model_type, 
                self.model_key, 
                self.report_progress
            )
            if success:
                self.finished.emit(True, "下载完成")
            else:
                self.finished.emit(False, "下载失败")
        except Exception as e:
            self.finished.emit(False, str(e))
            
    def report_progress(self, downloaded, total):
        self.progress.emit(downloaded, total)

class ModelDownloadDialog(QDialog):
    def __init__(self, model_manager, missing_models, parent=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.missing_models = missing_models # List of (type, key, name)
        self.current_index = 0
        
        self.setWindowTitle("下载模型")
        self.setFixedSize(400, 200)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("正在检查模型...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.info_label = QLabel("")
        layout.addWidget(self.info_label)
        
        layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)
        
        # Start download automatically
        self.start_next_download()
        
    def start_next_download(self):
        if self.current_index >= len(self.missing_models):
            self.accept()
            return
            
        m_type, m_key, m_desc = self.missing_models[self.current_index]
        self.status_label.setText(f"正在下载 {m_desc} ({self.current_index + 1}/{len(self.missing_models)})...")
        self.progress_bar.setValue(0)
        self.info_label.setText("准备中...")
        
        self.worker = DownloadWorker(self.model_manager, m_type, m_key)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.start()
        
    def update_progress(self, downloaded, total):
        if total > 0:
            percent = int(downloaded * 100 / total)
            self.progress_bar.setValue(percent)
            self.info_label.setText(f"{downloaded/1024/1024:.1f} MB / {total/1024/1024:.1f} MB")
            
    def on_download_finished(self, success, message):
        if success:
            self.current_index += 1
            self.start_next_download()
        else:
            QMessageBox.warning(self, "下载失败", f"模型下载失败: {message}")
            self.reject()
            
    def reject(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
        super().reject()
