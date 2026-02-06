# -*- coding: utf-8 -*-

import sys
import os
import subprocess

# Fix for PaddleOCR/OpenBLAS crash on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
# Disable mkldnn to prevent crash
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['DN_ENABLE_ONEDNN'] = '0'
# Disable PaddleX model source check
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


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
