# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import time
import ctypes

# Fix for PaddleOCR/OpenBLAS crash on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

# Define site_packages path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_PACKAGES = os.path.join(BASE_DIR, "site_packages")

# Ensure site_packages is in sys.path
if SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SITE_PACKAGES)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def show_message(msg, title="OCR Server"):
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40 | 0x1)
    except:
        print(f"[{title}] {msg}")

def install_pip():
    print("Checking pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Pip is already installed.")
        return True
    except subprocess.CalledProcessError:
        print("Pip not found. Installing pip...")
        get_pip_script = os.path.join(BASE_DIR, "get-pip.py")
        if not os.path.exists(get_pip_script):
            print("Error: get-pip.py not found!")
            return False
        
        try:
            # Install pip into site_packages
            cmd = [sys.executable, get_pip_script, "--no-warn-script-location", "--target", SITE_PACKAGES]
            subprocess.check_call(cmd)
            print("Pip installed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install pip: {e}")
            return False

def install_requirements():
    flag_path = os.path.join(BASE_DIR, "build_flavor_ai.flag")
    is_ai_build = os.path.exists(flag_path)
    
    candidates = []
    if is_ai_build:
        candidates.append(os.path.join(BASE_DIR, "requirements-gpu.txt"))
    candidates.append(os.path.join(BASE_DIR, "requirements.txt"))
    candidates.append(os.path.join(BASE_DIR, "dist_tools", "requirements.txt"))
    
    req_file = None
    for path in candidates:
        if os.path.exists(path):
            req_file = path
            break
    
    if not req_file:
        print("Error: requirements file not found (requirements-gpu.txt / requirements.txt)!")
        return False

    print(f"Installing dependencies from {req_file}...")
    print(f"Target directory: {SITE_PACKAGES}")
    
    mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
    paddle_cpu_index = "https://www.paddlepaddle.org.cn/packages/stable/cpu/"
    paddle_gpu_index = "https://www.paddlepaddle.org.cn/packages/stable/cu118/"

    normal_lines = []
    paddle_cpu_reqs = []
    paddle_gpu_reqs = []

    try:
        lines = None
        for enc in ("utf-8", "utf-16", "gbk"):
            try:
                with open(req_file, "r", encoding=enc) as f:
                    lines = f.readlines()
                if enc != "utf-8":
                    print(f"Using encoding {enc} to read {req_file}")
                break
            except UnicodeDecodeError:
                lines = None
        if lines is None:
            raise UnicodeDecodeError("requirements", b"", 0, 1, "failed to decode requirements file")
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped or stripped.startswith("#"):
                normal_lines.append(line)
            elif lower.startswith("paddlepaddle-gpu"):
                paddle_gpu_reqs.append(stripped)
            elif lower.startswith("paddlepaddle"):
                paddle_cpu_reqs.append(stripped)
            else:
                normal_lines.append(line)
    except Exception as e:
        print(f"Failed to parse requirements file {req_file}: {e}")
        return False

    if normal_lines:
        tmp_req = os.path.join(BASE_DIR, "requirements_tmp_no_paddle.txt")
        try:
            with open(tmp_req, "w", encoding="utf-8") as f:
                f.writelines(normal_lines)
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                tmp_req,
                "-t",
                SITE_PACKAGES,
                "--no-warn-script-location",
                "-i",
                mirror,
            ]
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install dependencies (general packages): {e}")
            return False
        except Exception as e:
            print(f"Error while installing general dependencies: {e}")
            return False
        finally:
            try:
                if os.path.exists(tmp_req):
                    os.remove(tmp_req)
            except Exception:
                pass

    for req in paddle_cpu_reqs:
        print(f"Installing Paddle CPU package '{req}' from {paddle_cpu_index} ...")
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            req,
            "-t",
            SITE_PACKAGES,
            "--no-warn-script-location",
            "-i",
            paddle_cpu_index,
        ]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Paddle CPU package {req}: {e}")
            return False

    for req in paddle_gpu_reqs:
        print(f"Installing Paddle GPU package '{req}' from {paddle_gpu_index} ...")
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            req,
            "-t",
            SITE_PACKAGES,
            "--no-warn-script-location",
            "-i",
            paddle_gpu_index,
        ]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Paddle GPU package {req}: {e}")
            return False
    
    print("Dependencies installed successfully!")
    return True

def check_ui_dependencies():
    missing = []
    try:
        import PyQt5  # noqa: F401
    except ImportError:
        missing.append("PyQt5")
    try:
        import requests  # noqa: F401
    except ImportError:
        missing.append("requests")
    return missing

def check_critical_dependencies():
    missing = []
    for name, import_name in [
        ("lxml", "lxml"),
        ("Pillow", "PIL"),
        ("paddleocr", "paddleocr"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(name)
    return missing

def install_ui_dependencies():
    missing = check_ui_dependencies()
    if not missing:
        print("UI dependencies already installed.")
        return True
    print("Installing UI dependencies:", ", ".join(missing))
    mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
    for pkg in missing:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            pkg,
            "-t",
            SITE_PACKAGES,
            "--no-warn-script-location",
            "-i",
            mirror,
        ]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install UI dependency {pkg}: {e}")
            return False
    return True

def run_gui_installer():
    try:
        from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QProgressBar, QTextEdit
        from PyQt5.QtCore import Qt, QThread, pyqtSignal
    except Exception as e:
        print(f"Failed to import PyQt5 for GUI installer: {e}")
        return

    class InstallerWorker(QThread):
        progress = pyqtSignal(str, str, float)
        finished = pyqtSignal()

        def run(self):
            try:
                from dist_tools.dependency_manager import DependencyManager
                manager = DependencyManager(dist_dir=BASE_DIR)
                def callback(item_name, step_desc, progress_float):
                    self.progress.emit(item_name, step_desc, progress_float)
                manager.install_missing_items(progress_callback=callback)
            except Exception as exc:
                self.progress.emit("error", f"Installer error: {exc}", 1.0)
            self.finished.emit()

    class InstallerDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("OCR Server 安装")
            self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
            layout = QVBoxLayout(self)
            self.label = QLabel("正在准备安装环境...", self)
            self.progress_bar = QProgressBar(self)
            self.progress_bar.setRange(0, 100)
            self.log_view = QTextEdit(self)
            self.log_view.setReadOnly(True)
            layout.addWidget(self.label)
            layout.addWidget(self.progress_bar)
            layout.addWidget(self.log_view)
            self.lines = []
            self.worker = InstallerWorker(self)
            self.worker.progress.connect(self.on_progress)
            self.worker.finished.connect(self.accept)
            self.worker.start()

        def on_progress(self, item_name, step_desc, progress_float):
            self.label.setText(step_desc)
            value = int(progress_float * 100)
            if value < 0:
                value = 0
            if value > 100:
                value = 100
            self.progress_bar.setValue(value)
            if step_desc:
                self.lines.append(step_desc)
                if len(self.lines) > 3:
                    self.lines = self.lines[-3:]
                self.log_view.setPlainText("\n".join(self.lines))
                self.log_view.moveCursor(self.log_view.textCursor().End)

    app = QApplication(sys.argv)
    dialog = InstallerDialog()
    dialog.exec_()

def main():
    flag_path = os.path.join(BASE_DIR, "build_flavor_ai.flag")
    is_ai_build = os.path.exists(flag_path)
    # Set console title
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("OCR Server Environment Setup")
        except:
            pass

    setup_mode = os.environ.get("OCR_SETUP_MODE") == "1"
    
    # Check for installation lock file
    install_lock_file = os.path.join(SITE_PACKAGES, "install.lock")
    is_installed = os.path.exists(install_lock_file)

    if is_installed:
        missing_core = check_critical_dependencies()
        if missing_core:
            print("Critical dependencies missing: " + ", ".join(missing_core) + ". Re-running setup...")
            is_installed = False

    if is_installed:
        # Dependencies assumed OK. Directly launch run.py (Main App)
        run_script = os.path.join(BASE_DIR, "run.py")
        if os.path.exists(run_script):
             # Normal launch
             # Inherit the python interpreter type (python.exe or pythonw.exe)
             # This ensures that if we are in Debug mode (python.exe), the child process also shows output.
             python_cmd = sys.executable
             
             # If we are in pythonw (no console), we can just launch run.py directly
             subprocess.Popen([python_cmd, run_script, "--gui"])
        else:
            if setup_mode:
                print("Error: run.py not found!")
                time.sleep(5)
            else:
                # If no console, we can't print error easily, but we can try logging or message box if critical
                pass
        return

    # 2. If dependencies missing (lock file not found)
    if not is_installed:
        if not setup_mode:
            # We need to show a console for installation
            # Use same python executable but open a new console
            # subprocess.CREATE_NEW_CONSOLE = 0x00000010
            
            # Re-launch self in setup mode
            env = os.environ.copy()
            env["OCR_SETUP_MODE"] = "1"
            
            python_exe = sys.executable
            # If currently using pythonw, try to use python.exe for console output
            if "pythonw.exe" in python_exe:
                python_console = python_exe.replace("pythonw.exe", "python.exe")
                if os.path.exists(python_console):
                    python_exe = python_console
            
            subprocess.Popen([python_exe, __file__], env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
            sys.exit(0)
        else:
            # We are in setup mode (visible console)
            print("="*50)
            print("OCR Server - First Run Setup")
            print("="*50)
            
            print("Diagnosing dependency issues...")
            try:
                import PyQt5  # noqa: F401
                import requests  # noqa: F401
            except Exception as e:
                print(f"UI dependency check: {e}")
            print("-" * 50)

            if not install_pip():
                input("Press Enter to exit...")
                sys.exit(1)

            if not install_ui_dependencies():
                print("Failed to install UI dependencies.")
                input("Press Enter to exit...")
                sys.exit(1)

            run_gui_installer()

            missing_after_gui = check_critical_dependencies()
            if missing_after_gui:
                print("Still missing dependencies after GUI installer: " + ", ".join(missing_after_gui))
                print("Installing remaining dependencies via requirements.txt ...")
                if not install_requirements():
                    print("Failed to install remaining dependencies.")
                    input("Press Enter to exit...")
                    sys.exit(1)

            try:
                if not os.path.exists(SITE_PACKAGES):
                    os.makedirs(SITE_PACKAGES)
                with open(install_lock_file, "w") as f:
                    f.write("Installation completed successfully.")
                print(f"Created lock file: {install_lock_file}")
            except Exception as e:
                print(f"Warning: Could not create lock file: {e}")

            print("\nSetup complete.")
            print("Launching application...")
            time.sleep(2)

            run_script = os.path.join(BASE_DIR, "run.py")
            if os.path.exists(run_script):
                pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.exists(pythonw):
                    pythonw = sys.executable
                subprocess.Popen([pythonw, run_script])
            else:
                print("Error: run.py not found!")
                input("Press Enter to exit...")

            sys.exit(0)

if __name__ == "__main__":
    main()
