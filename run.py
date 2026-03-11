# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：应用标准启动入口，负责注入项目路径与环境初始化后委托到 app.main
# - 核心实现：调用 EnvManager.configure_paddle_env 配置运行环境，随后执行 app.main.main
# - 关联关系：与 boot 共同作为不同打包/运行形态的入口脚本

import sys
import os
import multiprocessing
from app.log.log_bus import get_logger

logger = get_logger()

# Windows 下必须设置 spawn 启动方式
if sys.platform.startswith('win'):
    multiprocessing.set_start_method('spawn', force=True)

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# CPU Vendor Check & MKLDNN Configuration
try:
    from app.infrastructure.env_manager import EnvManager
    EnvManager.configure_paddle_env()
except Exception as e:
    logger.error("run", "env_config_failed", f"[Init] Error configuring env: {e}")

def main():
    from app.main import main as ocr_main
    ocr_main()


if __name__ == "__main__":
    main()
