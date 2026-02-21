# -*- coding: utf-8 -*-

import sys
import os
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# CPU Vendor Check & MKLDNN Configuration
try:
    from app.core.env_manager import EnvManager
    EnvManager.configure_paddle_env()
except Exception as e:
    print(f"[Init] Error configuring env: {e}")

def main():
    from app.main import main as ocr_main
    ocr_main()


if __name__ == "__main__":
    main()
