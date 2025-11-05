# -*- coding: utf-8 -*-

import sys
import os
import argparse

# 添加项目目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='OCR日期识别系统')
    parser.add_argument('--gui', action='store_true', help='使用GUI界面选择输入输出目录')
    parser.add_argument('--input', '-i', type=str, help='输入目录路径')
    parser.add_argument('--output', '-o', type=str, help='输出目录路径')
    args = parser.parse_args()

    # 如果使用GUI模式，直接调用main函数处理GUI参数
    if args.gui:
        from app.main import main as ocr_main
        # 传递GUI参数
        sys.argv = [sys.argv[0], '--gui']
        ocr_main()
    else:
        # 否则传递命令行参数
        from app.main import main as ocr_main
        ocr_main()


if __name__ == "__main__":
    main()
