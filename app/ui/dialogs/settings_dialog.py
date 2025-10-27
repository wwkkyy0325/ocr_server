# Path: src/app/ui/dialogs/settings_dialog.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模型选择、识别参数设置对话框
"""

import tkinter as tk
from tkinter import filedialog
import os


class SettingsDialog:
    def __init__(self):
        """
        初始化设置对话框
        """
        pass

    @staticmethod
    def select_directories():
        """
        选择输入和输出目录

        Returns:
            tuple: (input_dir, output_dir)
        """
        try:
            # 创建根窗口但不显示
            root = tk.Tk()
            root.withdraw()  # 隐藏根窗口
            root.lift()  # 将窗口提升到顶层
            root.attributes('-topmost', True)  # 确保窗口在最前面
            
            # 显示目录选择对话框
            print("请选择输入目录...")
            input_dir = filedialog.askdirectory(title="选择输入目录")
            if not input_dir:
                input_dir = "input"  # 如果未选择，则使用默认值
                
            print("请选择输出目录...")
            output_dir = filedialog.askdirectory(title="选择输出目录")
            if not output_dir:
                output_dir = "output"  # 如果未选择，则使用默认值
                
            # 销毁根窗口
            root.destroy()
            
            print(f"已选择输入目录: {input_dir}")
            print(f"已选择输出目录: {output_dir}")
            return input_dir, output_dir
        except Exception as e:
            print(f"Error in directory selection: {e}")
            return "input", "output"
