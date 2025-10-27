# Path: src/app/main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse

# 添加项目路径到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 检查关键依赖
missing_deps = []

# 检查PIL
try:
    from PIL import Image
except ImportError:
    missing_deps.append("Pillow")

# 检查PaddleOCR
try:
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    PADDLE_OCR_AVAILABLE = False
    missing_deps.append("paddleocr")

# PyQt相关导入
try:
    from PyQt5.QtWidgets import QApplication
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not available, using console mode")

# 如果缺少关键依赖，给出提示
if missing_deps:
    print("警告：缺少以下依赖库:")
    for dep in missing_deps:
        print(f"  - {dep}")
    print("请安装这些依赖以获得完整功能:")
    print("  pip install " + " ".join(missing_deps))
    print()

from app.main_window import MainWindow
from app.core.config_manager import ConfigManager


def setup_cpu_limit():
    """
    设置CPU使用限制
    """
    try:
        # 使用配置管理器获取配置
        config_manager = ConfigManager()
        config_manager.load_config()
        PERFORMANCE = {
            'cpu_limit': config_manager.get_setting('cpu_limit', 70),
            'max_processing_time': config_manager.get_setting('max_processing_time', 30)
        }
        
        cpu_limit = PERFORMANCE.get('cpu_limit', 70)

        # 检查是否有通过环境变量设置的CPU限制（来自GUI）
        if 'GUI_CPU_LIMIT' in os.environ:
            gui_cpu_limit = int(os.environ.get('GUI_CPU_LIMIT'))
            cpu_limit = max(10, min(100, gui_cpu_limit))  # 确保在合理范围内
            print(f"使用GUI设置的CPU限制: {cpu_limit}%")

        # 设置环境变量限制CPU使用率
        thread_count = max(1, int(cpu_limit / 10))

        # 为了避免PaddlePaddle的警告，我们只在必要时设置OMP_NUM_THREADS
        if thread_count > 1:
            os.environ['OMP_NUM_THREADS'] = str(thread_count)
        else:
            os.environ['OMP_NUM_THREADS'] = '1'

        os.environ['MKL_NUM_THREADS'] = str(thread_count)

        print(f"CPU使用率限制: {cpu_limit}%")
        print(f"实际设置的线程数: {thread_count}")

        # 尝试使用psutil限制CPU使用率（如果可用）
        try:
            import psutil
            p = psutil.Process(os.getpid())
            # 根据CPU限制设置CPU亲和性
            cpu_count = psutil.cpu_count()
            # 只使用部分CPU核心
            cores_to_use = max(1, int(cpu_count * cpu_limit / 100))
            p.cpu_affinity(list(range(cores_to_use)))
            print(f"CPU核心限制: 使用 {cores_to_use}/{cpu_count} 个核心")
        except ImportError:
            pass

        return cpu_limit
    except Exception as e:
        print(f"设置CPU限制时出错: {e}")
        return 70


def main():
    """
    主函数 - 演示基于蒙版定位的日期识别流程
    """
    # 检查是否是GUI模式
    is_gui_mode = '--gui' in sys.argv

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='OCR日期识别系统')
    parser.add_argument('--input', '-i', type=str, help='输入目录路径')
    parser.add_argument('--output', '-o', type=str, help='输出目录路径')
    parser.add_argument('--gui', action='store_true', help='使用GUI界面选择目录')
    args = parser.parse_args()

    # 确定输入和输出目录
    input_dir = "input"
    output_dir = "output"

    if args.gui:
        # 在GUI模式下，不立即选择目录，而是在GUI中选择
        print("GUI mode: Directories will be selected in the GUI")
        input_dir = args.input or "input"
        output_dir = args.output or "output"
    elif args.input or args.output:
        # 使用命令行参数
        input_dir = args.input or "input"
        output_dir = args.output or "output"
    else:
        # 使用默认目录
        input_dir = "input"
        output_dir = "output"

    # 显示当前配置
    try:
        # 使用配置管理器获取配置
        config_manager = ConfigManager()
        config_manager.load_config()
        
        MASK_SETTINGS = {
            'use_mask': config_manager.get_setting('use_mask', False),
            'use_adaptive_mask': config_manager.get_setting('use_adaptive_mask', False),
            'mask_padding': config_manager.get_setting('mask_padding', 10),
            'interactive_selection': config_manager.get_setting('interactive_selection', False),
            'use_center_priority': config_manager.get_setting('use_center_priority', False),
            'default_coordinates': config_manager.get_setting('default_coordinates', '')
        }
        
        PERFORMANCE = {
            'max_processing_time': config_manager.get_setting('max_processing_time', 30)
        }
        
        print(f"当前配置:")
        print(f"  输入目录: {input_dir}")
        print(f"  输出目录: {output_dir}")
        print(f"  蒙版功能: {'启用' if MASK_SETTINGS['use_mask'] else '禁用'}")
        if MASK_SETTINGS['use_mask']:
            print(f"  蒙版类型: {'自适应' if MASK_SETTINGS['use_adaptive_mask'] else '默认'}")
            print(f"  蒙版填充: {MASK_SETTINGS['mask_padding']} 像素")
            print(f"  交互式选择: {'启用' if MASK_SETTINGS.get('interactive_selection', False) else '禁用'}")
            print(f"  中心优先算法: {'启用' if MASK_SETTINGS.get('use_center_priority', False) else '禁用'}")
            print(f"  默认坐标: {MASK_SETTINGS.get('default_coordinates', '未设置')}")
        print(f"  性能限制: {PERFORMANCE.get('max_processing_time', 30)}秒")
    except ImportError:
        print("配置文件导入失败")

    # 初始化主窗口
    app = None
    if is_gui_mode and PYQT_AVAILABLE:
        app = QApplication.instance()  # 获取现有的QApplication实例
        if app is None:  # 如果没有现有的实例，则创建新的
            app = QApplication(sys.argv)
    
    # 只初始化一次ConfigManager并传递给MainWindow
    config_manager = ConfigManager()
    config_manager.load_config()
    main_window = MainWindow(config_manager)
    
    # 在GUI模式下，只显示窗口，不自动运行处理
    if is_gui_mode:
        main_window.show()
    else:
        # 在命令行模式下，运行处理流程
        main_window.run(input_dir, output_dir)
    
    # 运行Qt事件循环（如果在GUI模式下）
    if is_gui_mode and PYQT_AVAILABLE and app:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
