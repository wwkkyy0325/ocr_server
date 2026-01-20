# -*- coding: utf-8 -*-

import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    from app.main import main as ocr_main
    ocr_main()


if __name__ == "__main__":
    main()
