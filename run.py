# -*- coding: utf-8 -*-

import sys
import os
import subprocess

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# CPU Vendor Check & MKLDNN Configuration
try:
    from app.core.env_manager import EnvManager
    EnvManager.configure_paddle_env()
except Exception as e:
    print(f"[Init] Error configuring env: {e}")

def main():
    # Check if launched by launcher
    if "--launched-by-launcher" in sys.argv:
        # Remove the flag so argparse in app.main doesn't crash
        sys.argv.remove("--launched-by-launcher")
        from app.main import main as ocr_main
        ocr_main()
    else:
        # Redirect to Launcher
        # This ensures the Launcher is the default entry point
        cmd = [sys.executable, "launcher.py"]
        # Pass through arguments if any, but filter out script name
        cmd.extend(sys.argv[1:])
        subprocess.Popen(cmd, cwd=project_root)
        sys.exit(0)


if __name__ == "__main__":
    main()
