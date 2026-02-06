# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import time
import ctypes

# 修复 Windows 上 PIR 转换错误 (关键修复)
os.environ['FLAGS_enable_pir_api'] = '0'
# 优化显存分配策略，防止闪退
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'

# Fix for PaddleOCR/OpenBLAS crash on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
site_packages = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_packages")
if site_packages not in sys.path:
    sys.path.insert(0, site_packages)

def check_python_dependencies():
    """
    Check if critical python packages are available.
    """
    try:
        # Debug: Print where we are looking for packages
        # print(f"DEBUG: sys.path[0] = {sys.path[0]}")
        
        import paddle
        import paddleocr
        import cv2
        import shapely
        import pyclipper
        import PyQt5
        import requests
        import openpyxl
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False
    except OSError as e:
        print("="*50)
        print(f"CRITICAL ERROR: Operating System Error detected.")
        print(f"Error details: {e}")
        print("-" * 20)
        print("This usually indicates a missing system DLL (like VC++ Redistributable)")
        print("or a conflict with the Python environment.")
        print("Re-installing Python packages will NOT fix this.")
        print("="*50)
        # We must exit here to prevent infinite download loops
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during dependency check: {e}")
        sys.exit(1)

def show_message_box(title, message):
    """
    Show a Windows Message Box (works without PyQt5)
    """
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x1) # MB_ICONINFORMATION | MB_OKCANCEL
    except:
        print(f"[{title}] {message}")

def install_gui_dependencies():
    """
    Install only PyQt5 and requests first, to enable the Installer UI.
    """
    print("="*50)
    print("Initializing Installer Environment...")
    print("="*50)
    
    # Set console title
    os.system("title OCR Server - Initializing...")
    
    # Show message box
    show_message_box("OCR Server Setup", 
                     "First time setup detected.\n\nThe application needs to download necessary components (PyQt5, PaddleOCR, Models).\n\nClick OK to start the installation process.")

    packages = ["PyQt5", "requests"]
    
    try:
        cmd = [
            sys.executable, "-m", "pip", "install", 
            "--no-warn-script-location",
            "-t", site_packages,
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
        ] + packages
        
        # Use a new console window for the installation process so the user can see progress
        # CREATE_NEW_CONSOLE = 0x00000010
        subprocess.check_call(cmd, creationflags=0x00000010)
        
        print("Installer environment ready.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install GUI dependencies: {e}")
        return False

def run_installer_ui():
    """
    Run the GUI Installer (installer_ui.py) to handle the rest.
    """
    print("Launching Installer UI...")
    installer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist_tools", "installer_ui.py")
    
    if not os.path.exists(installer_path):
        print("Installer UI not found. Falling back to CLI installation.")
        return False
        
    try:
        # We need to run it as a subprocess to ensure clean environment or just import it?
        # Subprocess is safer to avoid pollution, but we want to share the site_packages
        # Since we added site_packages to sys.path, we can run it.
        subprocess.check_call([sys.executable, installer_path])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Installer UI failed: {e}")
        return False

def install_dependencies_cli():
    """
    Fallback: Install dependencies from requirements.txt via CLI.
    """
    print("Installing dependencies via CLI...")
    dist_tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist_tools")
    requirements_path = os.path.join(dist_tools_dir, "requirements.txt")
    
    if not os.path.exists(requirements_path):
        print(f"Error: requirements.txt not found at {requirements_path}")
        return False

    # 1. Check/Install pip
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("pip not found. Installing pip...")
        get_pip_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get-pip.py")
        if os.path.exists(get_pip_path):
            try:
                subprocess.check_call([sys.executable, get_pip_path, "--no-warn-script-location"])
            except subprocess.CalledProcessError:
                return False

    # 2. Install requirements
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "-r", requirements_path, 
            "-t", site_packages,
            "--no-warn-script-location",
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
        ])
        return True
    except subprocess.CalledProcessError:
        return False

def check_and_download_models():
    """
    Check and download OCR models using app's ModelManager.
    """
    print("Checking OCR models...")
    try:
        # Import here to avoid ImportError before dependencies are installed
        from app.core.model_manager import ModelManager
        mm = ModelManager()
        mm.check_and_download_defaults()
        return True
    except Exception as e:
        print(f"Warning: Model check failed: {e}")
        return False

def launch_main_app():
    """Launch the main application"""
    print("Starting Application...")
    try:
        if "--gui" not in sys.argv:
            sys.argv.append("--gui")
            
        import app.main as main_app
        if hasattr(main_app, 'main'):
            main_app.main()
            return
            
        import main
        if hasattr(main, 'main'):
            main.main()
        elif hasattr(main, 'run'):
            main.run()
    except Exception as e:
        print(f"Failed to launch app: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == "__main__":
    # 1. Check Python Packages
    if not check_python_dependencies():
        # Try to import PyQt5 to see if we can launch GUI installer
        try:
            import PyQt5
            has_pyqt = True
        except ImportError:
            has_pyqt = False
            
        if not has_pyqt:
            if install_gui_dependencies():
                # Restart script to load PyQt5
                print("Restarting to launch installer...")
                subprocess.call([sys.executable] + sys.argv)
                sys.exit(0)
            else:
                print("Failed to setup GUI environment. Trying CLI fallback...")
                if not install_dependencies_cli():
                    input("Installation failed. Press Enter to exit...")
                    sys.exit(1)
        
        # If we are here, we have PyQt5 (either existed or just installed)
        # But check_python_dependencies returned False, so other deps are missing.
        # Launch GUI Installer
        if run_installer_ui():
             # Installer UI finished successfully (hopefully)
             # Restart one last time to load all new packages
             subprocess.call([sys.executable] + sys.argv)
             sys.exit(0)
        else:
             print("Installer UI failed or closed. Exiting.")
             sys.exit(1)
            
    # 2. Check & Download Models (Now that env is ready)
    # Note: Installer UI might have handled this, but double check doesn't hurt
    check_and_download_models()
    
    # 3. Launch App
    launch_main_app()
