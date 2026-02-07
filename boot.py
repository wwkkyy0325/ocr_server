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
    req_file = os.path.join(BASE_DIR, "requirements.txt")
    if not os.path.exists(req_file):
        # Try to look in dist_tools
        req_file = os.path.join(BASE_DIR, "dist_tools", "requirements.txt")
        
    if not os.path.exists(req_file):
        print("Error: requirements.txt not found!")
        return False

    print(f"Installing dependencies from {req_file}...")
    print(f"Target directory: {SITE_PACKAGES}")
    
    mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
    cmd = [
        sys.executable, "-m", "pip", "install", 
        "-r", req_file,
        "-t", SITE_PACKAGES,
        "--no-warn-script-location",
        "-i", mirror
    ]
    
    try:
        subprocess.check_call(cmd)
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        return False

def main():
    # Set console title
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("OCR Server Environment Setup")
        except:
            pass

    setup_mode = os.environ.get("OCR_SETUP_MODE") == "1"

    # 1. Check critical dependencies
    missing_deps = False
    try:
        import PyQt5
        import paddle
        import requests
        import cv2
    except ImportError:
        missing_deps = True

    if not missing_deps:
        # Dependencies OK. Directly launch run.py (Main App) to skip Launcher
        run_script = os.path.join(BASE_DIR, "run.py")
        if os.path.exists(run_script):
            if setup_mode:
                 # If just installed, maybe show launcher first? No, direct launch is fine.
                 print("Launching application...")
                 subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), run_script, "--launched-by-launcher"])
            else:
                 # Normal launch
                 # Inherit the python interpreter type (python.exe or pythonw.exe)
                 # This ensures that if we are in Debug mode (python.exe), the child process also shows output.
                 python_cmd = sys.executable
                 
                 subprocess.Popen([python_cmd, run_script, "--launched-by-launcher", "--gui"])
        else:
            print("Error: run.py not found!")
            time.sleep(5)
        return

    # 2. If dependencies missing
    if missing_deps:
        if not setup_mode:
            # We need to show a console for installation
            show_message("Initial setup required. The application will now download and install necessary components.\nA console window will appear.", "Setup Required")
            
            env = os.environ.copy()
            env["OCR_SETUP_MODE"] = "1"
            
            # Use python.exe to ensure console is visible
            python_exe = sys.executable
            if "pythonw.exe" in python_exe.lower():
                python_exe = python_exe.replace("pythonw.exe", "python.exe")
            
            # Create new console
            subprocess.Popen([python_exe, __file__], env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
            sys.exit(0)
        else:
            # We are in setup mode (visible console)
            print("="*50)
            print("OCR Server - First Run Setup")
            print("="*50)
            print("Checking environment...")
            print(f"Base Env: {sys.prefix}")
            print(f"Site Packages: {SITE_PACKAGES}")

            if not install_pip():
                input("Press Enter to exit...")
                sys.exit(1)
            
            if not install_requirements():
                print("Retrying with global options or check internet connection...")
                input("Press Enter to exit...")
                sys.exit(1)

            print("\nSetup complete.")
            print("Launching application...")
            time.sleep(2)
            
            # Launch launcher.py
            # But since environment is ready, we can launch run.py directly now too
            run_script = os.path.join(BASE_DIR, "run.py")
            if os.path.exists(run_script):
                # Try to find pythonw.exe for GUI launch
                pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.exists(pythonw):
                    pythonw = sys.executable
                
                subprocess.Popen([pythonw, run_script, "--launched-by-launcher"])
            else:
                print("Error: run.py not found!")
                input("Press Enter to exit...")
            
            sys.exit(0)

if __name__ == "__main__":
    main()
