# -*- coding: utf-8 -*-
import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QProgressBar, QMessageBox, QPushButton)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Add current directory to path to find dependency_manager
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from dependency_manager import DependencyManager

class Worker(QThread):
    progress = pyqtSignal(str, int, int) # task_name, current, total
    finished = pyqtSignal(bool, str) # success, message
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        
    def run(self):
        try:
            # 1. Check Packages
            missing_pkgs = self.manager.check_missing_packages()
            total_tasks = len(missing_pkgs) + len(self.manager.check_missing_models())
            current_task = 0
            
            # Install Packages
            for pkg_name in missing_pkgs:
                info = self.manager.config['packages'][pkg_name]
                desc = info.get('description', pkg_name)
                
                # Check if we have URL for direct download (e.g. Paddle)
                url = info.get('url')
                if url:
                    self.progress.emit(f"正在下载 {desc}...", 0, 100)
                    filename = os.path.basename(url)
                    target_path = os.path.join(self.manager.temp_dir, filename)
                    
                    def dl_callback(curr, total):
                        pct = int(curr / total * 100)
                        self.progress.emit(f"正在下载 {desc} ({pct}%)", pct, 100)
                        
                    if not self.manager.download_file(url, target_path, dl_callback):
                        self.finished.emit(False, f"下载 {desc} 失败")
                        return
                        
                    self.progress.emit(f"正在安装 {desc}...", 100, 100)
                    if not self.manager.install_local_whl(target_path):
                        self.finished.emit(False, f"安装 {desc} 失败")
                        return
                else:
                    # Pip install
                    self.progress.emit(f"正在安装 {desc}...", 50, 100)
                    if not self.manager.install_package(info.get('pypi_name', pkg_name)):
                        self.finished.emit(False, f"安装 {desc} 失败")
                        return
                
                current_task += 1
            
            # 2. Check Models
            missing_models = self.manager.check_missing_models()
            for model_name in missing_models:
                info = self.manager.config['models'][model_name]
                url = info['url']
                target_rel_path = info['path']
                
                self.progress.emit(f"正在下载模型 {model_name}...", 0, 100)
                
                filename = os.path.basename(url)
                archive_path = os.path.join(self.manager.temp_dir, filename)
                
                def dl_callback(curr, total):
                    pct = int(curr / total * 100)
                    self.progress.emit(f"正在下载模型 {model_name} ({pct}%)", pct, 100)

                if not self.manager.download_file(url, archive_path, dl_callback):
                    self.finished.emit(False, f"下载模型 {model_name} 失败")
                    return
                
                self.progress.emit(f"正在解压模型 {model_name}...", 100, 100)
                # Extract to parent dir of target path
                target_full_path = os.path.join(self.manager.dist_dir, target_rel_path)
                extract_root = os.path.dirname(target_full_path)
                if not os.path.exists(extract_root):
                    os.makedirs(extract_root)
                    
                if not self.manager.extract_model(archive_path, extract_root):
                    self.finished.emit(False, f"解压模型 {model_name} 失败")
                    return
                
                # Clean up
                try:
                    os.remove(archive_path)
                except:
                    pass
                    
            self.finished.emit(True, "所有依赖安装完成")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, str(e))

class InstallerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR环境初始化向导")
        self.resize(500, 200)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        self.lbl_status = QLabel("正在检查运行环境...")
        layout.addWidget(self.lbl_status)
        
        self.pbar = QProgressBar()
        layout.addWidget(self.pbar)
        
        self.btn_retry = QPushButton("重试")
        self.btn_retry.clicked.connect(self.start_install)
        self.btn_retry.hide()
        layout.addWidget(self.btn_retry)
        
        self.manager = DependencyManager()
        self.start_install()
        
    def start_install(self):
        self.btn_retry.hide()
        self.worker = Worker(self.manager)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        
    def on_progress(self, msg, curr, total):
        self.lbl_status.setText(msg)
        self.pbar.setValue(curr)
        
    def on_finished(self, success, msg):
        if success:
            self.lbl_status.setText("安装完成，正在启动...")
            self.pbar.setValue(100)
            # Give user a moment to see success
            QApplication.processEvents()
            import time
            time.sleep(1)
            self.close()
        else:
            self.lbl_status.setText(f"错误: {msg}")
            self.btn_retry.show()
            QMessageBox.critical(self, "安装失败", f"环境初始化失败:\n{msg}\n请检查网络连接后重试。")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = InstallerUI()
    ui.show()
    sys.exit(app.exec_())
