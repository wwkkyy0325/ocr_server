# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：应用标准启动入口，负责注入项目路径与环境初始化后委托到 app.main
# - 核心实现：调用 EnvManager.configure_paddle_env 配置运行环境，随后执行 app.main.main
# - 关联关系：与 launcher/boot 共同作为不同打包/运行形态的入口脚本

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
