# -*- coding: utf-8 -*-
import sys
import os
import subprocess
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QComboBox, QTextEdit, QMessageBox, 
                             QProgressBar, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.core.env_manager import EnvManager

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, commands):
        super().__init__()
        self.commands = commands

    def run(self):
        try:
            for cmd in self.commands:
                cmd_str = " ".join(cmd)
                self.log_signal.emit(f"Executing: {cmd_str}")
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    encoding='utf-8',
                    errors='replace' # Handle encoding errors gracefully
                )
                
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        self.log_signal.emit(line.strip())
                
                if process.returncode != 0:
                    self.log_signal.emit(f"Command failed with return code {process.returncode}")
                    self.finished_signal.emit(False)
                    return

            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False)

class LauncherDialog(QDialog):
    def __init__(self, auto_launch=True):
        super().__init__()
        self.setWindowTitle("OCR Server Launcher & Environment Manager")
        self.resize(600, 500)
        self.auto_launch = auto_launch
        self.init_ui()
        
        # Check environment on startup
        self.check_environment()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Status Section
        status_group = QGroupBox("当前环境状态")
        status_layout = QFormLayout()
        self.lbl_python = QLabel("Checking...")
        self.lbl_cuda = QLabel("Checking...")
        self.lbl_paddle = QLabel("Checking...")
        self.lbl_gpu_support = QLabel("Checking...")
        
        status_layout.addRow("Python:", self.lbl_python)
        status_layout.addRow("CUDA:", self.lbl_cuda)
        status_layout.addRow("PaddlePaddle:", self.lbl_paddle)
        status_layout.addRow("GPU Support:", self.lbl_gpu_support)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Management Section
        mgmt_group = QGroupBox("环境管理 / 修复")
        mgmt_layout = QVBoxLayout()
        
        hbox = QHBoxLayout()
        self.combo_version = QComboBox()
        # Items will be populated in check_environment based on CUDA detection
        
        self.btn_apply = QPushButton("应用更改 (全量重装)")
        self.btn_apply.clicked.connect(self.apply_changes)
        
        hbox.addWidget(QLabel("选择版本:"))
        hbox.addWidget(self.combo_version)
        hbox.addWidget(self.btn_apply)
        
        mgmt_layout.addLayout(hbox)
        mgmt_group.setLayout(mgmt_layout)
        layout.addWidget(mgmt_group)
        
        # Log Section
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False) # Hide initially
        layout.addWidget(self.progress_bar)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        
        # Launch Button
        self.btn_launch = QPushButton("启动 OCR 服务器")
        self.btn_launch.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #4CAF50; color: white; padding: 10px;")
        self.btn_launch.clicked.connect(self.launch_main_app)
        self.btn_launch.setVisible(False) # Hidden by default, shown if env OK
        
        self.btn_exit = QPushButton("退出")
        self.btn_exit.clicked.connect(self.close)
        
        btn_layout.addWidget(self.btn_launch)
        btn_layout.addWidget(self.btn_exit)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def check_environment(self):
        sys_info = EnvManager.get_system_info()
        paddle_status = EnvManager.get_paddle_status()
        
        self.lbl_python.setText(sys_info['python'])
        self.lbl_cuda.setText(sys_info['cuda_version'] if sys_info['cuda_version'] != 'N/A' else "Not Found")
        
        env_ok = False
        if paddle_status['installed']:
            self.lbl_paddle.setText(f"{paddle_status['version']} (OCR: {paddle_status['paddleocr_version']})")
            
            # Clarify "No" GPU support
            gpu_text = "Yes" if paddle_status['gpu_support'] else "No (当前安装为 CPU 版)"
            self.lbl_gpu_support.setText(gpu_text)
            
            self.lbl_paddle.setStyleSheet("color: green")
            
            # Run dynamic GPU diagnosis
            self.run_gpu_diagnosis()
            env_ok = True
        else:
            self.lbl_paddle.setText("未安装")
            self.lbl_gpu_support.setText("-")
            self.lbl_paddle.setStyleSheet("color: red")
            self.auto_launch = False # Cancel auto launch if missing env

        # Populate combo box based on CUDA version (Strict Mode)
        current_selection = self.combo_version.currentData()
        self.combo_version.clear()
        
        # Always allow CPU restore
        self.combo_version.addItem("恢复至 CPU 稳定版 (3.2.0)", "cpu_3_2_0")
        
        cuda_ver = sys_info['cuda_version']
        if cuda_ver != 'N/A':
            # Extract major.minor
            try:
                major, minor = map(int, cuda_ver.split('.'))
                
                # Logic to match available Nightly builds
                # 11.8 compatible
                if major == 11 and minor >= 8:
                    self.combo_version.addItem("升级至 GPU Nightly (CUDA 11.8)", "gpu_nightly_11.8")
                # 12.x compatible
                if major == 12:
                    # Paddle usually provides specific builds, e.g. 12.3 for 12.x
                    # But user requested 12.6 / 12.9 specific support
                    # We add them if they match or are compatible
                    self.combo_version.addItem(f"升级至 GPU Nightly (CUDA {cuda_ver}) [Auto-Match]", f"gpu_nightly_{cuda_ver}")
                    
                    if minor == 6:
                        self.combo_version.addItem("升级至 GPU Nightly (CUDA 12.6)", "gpu_nightly_12.6")
                    elif minor == 9:
                        self.combo_version.addItem("升级至 GPU Nightly (CUDA 12.9)", "gpu_nightly_12.9")
                    else:
                        pass

            except ValueError:
                pass
        
        # Restore previous selection if possible
        if current_selection:
            index = self.combo_version.findData(current_selection)
            if index >= 0:
                self.combo_version.setCurrentIndex(index)

        # Update UI based on status
        if env_ok:
            self.btn_launch.setVisible(True)
            self.log("环境检查通过。")
            
            # Auto launch logic
            if self.auto_launch:
                self.log("正在自动启动主程序...")
                # Delay slightly to show UI then launch
                QApplication.processEvents()
                self.launch_main_app()

    def launch_main_app(self):
        """Launch the main OCR application"""
        try:
            cmd = [sys.executable, "run.py", "--launched-by-launcher", "--gui"]
            
            # On Windows, try to detach process
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_CONSOLE
                
            subprocess.Popen(cmd, cwd=project_root, creationflags=creation_flags)
            
            # Close launcher
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动主程序: {e}")



    def run_gpu_diagnosis(self):
        """Runs a subprocess to check actual Paddle runtime device"""
        try:
            self.lbl_gpu_support.setText(self.lbl_gpu_support.text() + " (Diagnosing...)")
            QApplication.processEvents()
            
            cmd = [
                sys.executable, "-c", 
                "import paddle; print(f'DEVICE:{paddle.device.get_device()}'); print(f'CUDNN:{paddle.is_compiled_with_cudnn()}')"
            ]
            
            # Run with timeout to avoid hanging
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
            )
            stdout, stderr = process.communicate(timeout=10)
            
            device = "Unknown"
            if "DEVICE:" in stdout:
                for line in stdout.splitlines():
                    if line.startswith("DEVICE:"):
                        device = line.split(":", 1)[1].strip()
            
            current_text = self.lbl_gpu_support.text().split(" (Diagnosing...)")[0]
            
            if "gpu" in device.lower():
                self.lbl_gpu_support.setText(f"Yes (Active: {device})")
                self.lbl_gpu_support.setStyleSheet("color: green; font-weight: bold")
            else:
                self.lbl_gpu_support.setText(f"{current_text} | Runtime: {device}")
                if "No" in current_text:
                    self.lbl_gpu_support.setStyleSheet("color: red")
                else:
                    self.lbl_gpu_support.setStyleSheet("color: orange") # Installed but not using GPU?
                    
        except Exception as e:
            print(f"Diagnosis failed: {e}")
            self.lbl_gpu_support.setText(self.lbl_gpu_support.text().replace(" (Diagnosing...)", " (Diag Failed)"))

    def apply_changes(self):
        target = self.combo_version.currentData()
        if not target:
            return
            
        # Parse target
        cuda_version = None
        target_type = target
        if target.startswith("gpu_nightly_"):
            parts = target.split("_")
            cuda_version = parts[-1] # 11.8, 12.6, 12.9
            target_type = "gpu_nightly"
            
        cmds = EnvManager.get_install_command(target_type, cuda_version)
        if not cmds:
            QMessageBox.warning(self, "不支持", f"未找到适合该版本的安装配置: {target}")
            return
            
        # Add uninstall command at the beginning
        uninstall_cmd = EnvManager.uninstall_paddle()
        full_cmds = [uninstall_cmd] + cmds
        
        # Confirm
        msg = f"即将执行全量重装：\n1. 卸载现有 PaddlePaddle/OCR/PaddleX\n2. 安装 {self.combo_version.currentText()}\n\n此过程可能需要几分钟，请保持网络连接。"
        if QMessageBox.question(self, "确认重装", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
            
        self.btn_apply.setEnabled(False)
        self.combo_version.setEnabled(False)
        self.log_text.clear()
        
        # Show busy progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate mode
        
        self.thread = WorkerThread(full_cmds)
        self.thread.log_signal.connect(self.log)
        self.thread.finished_signal.connect(self.on_install_finished)
        self.thread.start()

    def log(self, msg):
        self.log_text.append(msg)
        # Scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)

    def on_install_finished(self, success):
        self.btn_apply.setEnabled(True)
        self.combo_version.setEnabled(True)
        
        # Stop progress animation
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        
        if success:
            QMessageBox.information(self, "成功", "环境更新成功！")
            self.check_environment() # Refresh status
        else:
            QMessageBox.critical(self, "错误", "环境更新失败，请查看日志。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Check args
    auto_launch = True
    if "--manage" in sys.argv:
        auto_launch = False
        
    dlg = LauncherDialog(auto_launch)
    dlg.show()
    sys.exit(app.exec_())
