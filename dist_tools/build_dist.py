# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import sys

import compileall

def compile_and_cleanup(directory):
    """
    编译指定目录下的所有 .py 文件为 .pyc，并删除源文件。
    使用 legacy=True 确保 .pyc 生成在源文件同级目录。
    """
    if not os.path.exists(directory):
        return

    print(f"正在编译并加密代码: {directory} ...")
    
    # 编译代码，legacy=True 会将 .pyc 生成在原位而不是 __pycache__
    # quiet=1 减少输出
    compileall.compile_dir(directory, force=True, legacy=True, quiet=1)
    
    # 删除 .py 源文件和 __pycache__ 目录
    cleaned_count = 0
    for root, dirs, files in os.walk(directory):
        # 删除 .py 文件
        for file in files:
            if file.endswith('.py'):
                os.remove(os.path.join(root, file))
                cleaned_count += 1
        
        # 删除 __pycache__ 目录
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))
            dirs.remove('__pycache__')
            
    print(f"  - 已处理 {cleaned_count} 个 Python 源文件")

def build_distribution():
    print("开始构建轻量级分发包...")
    
    # 1. 定义路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_output = os.path.join(project_root, "dist_output")
    
    if not os.path.exists(dist_output):
        os.makedirs(dist_output)
    else:
        # Clean up code folders but preserve environments and data
        for item in ["app", "dist_tools", "boot.py", "main.py", "OCR_Server.bat"]:
            path = os.path.join(dist_output, item)
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
    
    print(f"输出目录: {dist_output}")
    
    # 2. 复制核心代码
    # 这里我们只复制必要的应用代码，排除 venv, .git, __pycache__ 等
    ignore_patterns = shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.git", ".idea", ".vscode", "venv", "dist", "build", "dist_output", "logs", "temp_downloads"
    )
    
    # 复制 app 目录
    shutil.copytree(os.path.join(project_root, "app"), os.path.join(dist_output, "app"), ignore=ignore_patterns)
    
    # 复制 dist_tools (作为安装器组件)
    # 我们直接把 dist_tools 里的内容平铺到 dist_output/dist_tools 下，或者直接放在根目录？
    # 为了保持引用简单，我们还是保持 dist_tools 结构，但在 installer_ui 里加 path 修正
    shutil.copytree(os.path.join(project_root, "dist_tools"), os.path.join(dist_output, "dist_tools"), ignore=ignore_patterns)
    
    # 4. 编译并加密源代码 (App 目录)
    # 注意：boot.py 和 main.py 保持原样作为入口，dist_tools 也可以保持原样（主要是安装脚本）
    # 但 app 目录包含核心逻辑，需要加密
    compile_and_cleanup(os.path.join(dist_output, "app"))
    
    # 确保 requirements_lock.json 存在，如果不存在则从 requirements.txt 生成简单的版本
    lock_file = os.path.join(dist_output, "dist_tools", "requirements_lock.json")
    if not os.path.exists(lock_file):
        # 创建一个基本的 lock 文件，用于 dependency_manager.py
        import json
        basic_lock = {
            "packages": {
                "paddlepaddle": {"pypi_name": "paddlepaddle"},
                "paddleocr": {"pypi_name": "paddleocr"},
                "shapely": {"pypi_name": "shapely"},
                "pyclipper": {"pypi_name": "pyclipper"},
                "PyQt5": {"pypi_name": "PyQt5"},
                "requests": {"pypi_name": "requests"},
                "openpyxl": {"pypi_name": "openpyxl"}
            },
            "models": {} # 模型列表后续动态检测或预定义
        }
        with open(lock_file, 'w', encoding='utf-8') as f:
            json.dump(basic_lock, f, indent=4)
    
    # 复制入口脚本
    shutil.copy2(os.path.join(project_root, "boot.py"), os.path.join(dist_output, "boot.py"))
    
    # 复制 get-pip.py (确保环境缺失pip时可安装)
    get_pip_src = os.path.join(project_root, "get-pip.py")
    if os.path.exists(get_pip_src):
        shutil.copy2(get_pip_src, os.path.join(dist_output, "get-pip.py"))
    
    # 如果有 main.py 也复制
    if os.path.exists(os.path.join(project_root, "main.py")):
        shutil.copy2(os.path.join(project_root, "main.py"), os.path.join(dist_output, "main.py"))

    # 创建目录结构
    os.makedirs(os.path.join(dist_output, "base_env"), exist_ok=True)
    # site_packages 目录保留但不预填充，由 boot.py 自动安装
    os.makedirs(os.path.join(dist_output, "site_packages"), exist_ok=True)
    os.makedirs(os.path.join(dist_output, "temp"), exist_ok=True)
    os.makedirs(os.path.join(dist_output, "databases"), exist_ok=True)

    # 创建启动脚本 (保留 BAT 作为备用)
    with open(os.path.join(dist_output, "OCR_Server_Debug.bat"), "w", encoding="utf-8") as f:
        f.write('@echo off\n')
        f.write('cd /d "%~dp0"\n')
        f.write('set PYTHONPATH=%CD%\\site_packages;%CD%\n')
        f.write('if exist "base_env\\python.exe" (\n')
        f.write('    "base_env\\python.exe" boot.py\n')
        f.write(') else (\n')
        f.write('    echo Error: Python base environment not found.\n')
        f.write('    pause\n')
        f.write(')\n')
        f.write('pause\n')

    # 编译 EXE 启动器
    compile_launcher(project_root, dist_output)
    
    # 3. 提示后续步骤 (嵌入式 Python)
    print("\n" + "="*50)
    print("构建完成！")
    print("已生成 OCR_Server.exe (无控制台启动器) 和 OCR_Server_Debug.bat (调试用)")
    print("注意：site_packages 已从分发包中排除（仅创建空目录），将在首次运行时自动安装。")
    print("请按照以下步骤配置环境：")
    print("1. 将 Python Embeddable Package (python-3.9.x-embed-amd64) 的所有文件")
    print("   移动到 dist_output/base_env 文件夹中")
    print("2. 修改 base_env/python39._pth 文件:")
    print("   取消 'import site' 的注释")
    print("3. 双击 OCR_Server.exe 启动")
    print("   (程序会自动检测并安装缺失的依赖库和模型)")
    print("="*50)


def compile_launcher(project_root, dist_output):
    print("正在编译启动器 EXE...")
    launcher_src = os.path.join(project_root, "dist_tools", "launcher.c")
    output_exe = os.path.join(dist_output, "OCR_Server.exe")
    
    # 尝试使用 gcc
    try:
        # -mwindows 标志用于创建 GUI 应用程序（不显示控制台窗口）
        cmd = ["gcc", launcher_src, "-o", output_exe, "-mwindows"]
        subprocess.check_call(cmd)
        print(f"成功编译启动器: {output_exe}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("警告: 未找到 gcc 或编译失败，无法生成 EXE 启动器。")
        print("将仅保留 BAT 启动脚本。")
        # 如果编译失败，回退到生成原来的 BAT 并命名为 OCR_Server.bat
        bat_path = os.path.join(dist_output, "OCR_Server.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write('@echo off\n')
            f.write('cd /d "%~dp0"\n')
            f.write('set PYTHONPATH=%CD%\\site_packages;%CD%\n')
            f.write('if exist "base_env\\python.exe" (\n')
            f.write('    start "" "base_env\\pythonw.exe" boot.py\n')
            f.write(') else (\n')
            f.write('    echo Error: Python base environment not found.\n')
            f.write('    pause\n')
            f.write(')\n')
        return False


def build_installer():
    """
    一键：重建 dist_output 并调用 Inno Setup 生成安装包（如果已安装 ISCC.exe）
    """
    # 先重建 dist_output
    build_distribution()

    # 再尝试调用 Inno Setup 命令行编译器
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_tools_dir = os.path.join(project_root, "dist_tools")
    iss_path = os.path.join(dist_tools_dir, "setup.iss")

    if not os.path.exists(iss_path):
        print("未找到 setup.iss，跳过安装包编译。")
        return

    # 默认 Inno Setup 6 的安装路径（64 位 Windows 常见路径）
    default_iscc = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

    # 允许通过环境变量覆盖 ISCC 路径
    iscc_path = os.environ.get("INNO_SETUP_ISCC", default_iscc)

    if not os.path.exists(iscc_path):
        print("=" * 50)
        print("未找到 Inno Setup 命令行编译器 ISCC.exe，无法自动生成安装包。")
        print("请确认已安装 Inno Setup 6，并执行以下任一操作：")
        print("1. 手动在 Inno Setup IDE 中打开 dist_tools\\setup.iss，点击编译")
        print("2. 或者在系统中安装 Inno Setup 后，将 ISCC.exe 的完整路径写入环境变量：")
        print("   INNO_SETUP_ISCC")
        print("   然后重新运行：python dist_tools\\build_dist.py installer")
        print("=" * 50)
        return

    print("开始调用 Inno Setup 编译器生成安装包...")
    try:
        # 在 dist_tools 目录下调用，避免路径问题
        subprocess.check_call([iscc_path, iss_path], cwd=dist_tools_dir)
        print("安装包编译完成，输出目录为 dist_output_installer。")
    except subprocess.CalledProcessError as e:
        print(f"Inno Setup 编译失败，返回码: {e.returncode}")


if __name__ == "__main__":
    # 支持两种用法：
    #   python dist_tools/build_dist.py        -> 只重建 dist_output
    #   python dist_tools/build_dist.py installer  -> 重建并编译安装包
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("installer", "install", "setup"):
        build_installer()
    else:
        build_distribution()
