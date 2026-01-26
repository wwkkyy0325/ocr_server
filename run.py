# -*- coding: utf-8 -*-

import sys
import os

# Fix for PaddleOCR/OpenBLAS crash on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
# Disable mkldnn to prevent crash
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['DN_ENABLE_ONEDNN'] = '0'

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    from app.main import main as ocr_main
    ocr_main()


if __name__ == "__main__":
    main()
