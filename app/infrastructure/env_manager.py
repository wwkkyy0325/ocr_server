# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：统一配置 Paddle/PaddleOCR/PP-Structure 运行环境变量与依赖安装指引，处理 CPU/GPU 差异与目录迁移
# - 核心实现：根据平台与 CPU 厂商配置 OneDNN/MKLDNN、PADDLEX_HOME/PADDLEOCR_HOME 等变量，并提供环境探测与安装/卸载命令生成
# - 关联关系：在应用启动与模型初始化前由上层入口调用（如 launcher/run），为 ModelManager/UnifiedOCREngine 等组件提供稳定运行环境
import os
import sys
import subprocess
import platform
import re
import importlib.metadata
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class EnvManager:
    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=False, component="EnvManager")
    def is_ai_build():
        """
        判断是否为 AI 版本构建
        Returns: True/False
        """
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            flag_path = os.path.join(base_dir, "build_flavor_ai.flag")
            if os.path.exists(flag_path):
                return True
            value = os.environ.get("OCR_BUILD_FLAVOR", "")
            if value and value.lower() == "ai":
                return True
        except Exception as e:
            # 静默处理，返回默认值 False
            # 注意：这里不记录日志，避免在多次调用时产生噪音
            pass
        return False

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return="normal", component="EnvManager")
    def get_build_flavor():
        if EnvManager.is_ai_build():
            return "ai"
        return "normal"

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return="Unknown", component="EnvManager")
    def get_cpu_vendor(log_result=False):
        """
        获取 CPU 厂商信息 (Intel/AMD)
        Args:
            log_result: 是否记录日志（避免重复输出）
        Returns: 'Intel', 'AMD', or 'Unknown'
        """
        vendor = "Unknown"
        try:
            if platform.system() == "Windows":
                # Use wmic for accurate vendor info
                cmd = "wmic cpu get name"
                output = subprocess.check_output(cmd, shell=True, text=True, timeout=5)
                if "Intel" in output:
                    vendor = "Intel"
                elif "AMD" in output:
                    vendor = "AMD"
            else:
                # Linux/Mac fallback
                processor = platform.processor()
                if "Intel" in processor:
                    vendor = "Intel"
                elif "AMD" in processor or "x86_64" in processor:
                    # On Linux x86_64 could be either, check /proc/cpuinfo
                    pass

                if os.path.exists("/proc/cpuinfo"):
                    with open("/proc/cpuinfo", "r") as f:
                        content = f.read()
                        if "GenuineIntel" in content:
                            vendor = "Intel"
                        elif "AuthenticAMD" in content:
                            vendor = "AMD"
        except subprocess.TimeoutExpired:
            # 命令执行超时
            if log_result:
                logger = get_logger()
                logger.warning("env_manager", "cpu_vendor_timeout", "获取 CPU 厂商信息超时")
        except Exception as e:
            # 记录具体错误信息，便于调试
            if log_result:
                logger = get_logger()
                logger.warning("env_manager", "cpu_vendor_error", f"获取 CPU 厂商信息失败：{e}")
            # 不抛出异常，返回默认值

        # 只在明确要求时才记录日志，避免重复输出
        if log_result:
            logger = get_logger()
            logger.info("env_manager", "cpu_detected", f"CPU 厂商：{vendor}")

        return vendor

    @staticmethod
    @handle_errors(error_code=ErrorCode.PROCESS_START_001, fallback_return=None, component="EnvManager")
    def configure_paddle_env():
        """
        Configure environment variables for PaddlePaddle based on CPU vendor.
        Must be called before importing paddle.
        """
        logger = get_logger()

        try:
            libs_dir = None
            if platform.system() == "Windows":
                os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
                # User requested automatic CPU management (removed hard limit of 1)
                # os.environ["OMP_NUM_THREADS"] = "1"
                # os.environ["MKL_NUM_THREADS"] = "1"
                # os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
                # os.environ["NUMEXPR_NUM_THREADS"] = "1"

                try:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

                    # 强制重定向到应用目录下的 paddlex_home，不再检测中文路径
                    # 这样可以避免各种用户目录权限、中文路径编码等问题，统一管理
                    chosen = os.path.join(base_dir, "paddlex_home")
                    try:
                        os.makedirs(chosen, exist_ok=True)
                    except Exception as e:
                        logger.error("env_manager", "create_paddlex_home_failed", f"创建 paddlex_home 失败：{e}")
                        # Fallback to temp if local write failed
                        import tempfile
                        chosen = os.path.join(tempfile.gettempdir(), "ocr_server_paddlex_home")
                        os.makedirs(chosen, exist_ok=True)

                    # 尝试从默认用户目录迁移旧数据 (如果存在且新目录为空)
                    # 仅在首次运行时执行此操作
                    try:
                        import shutil
                        default_home = os.path.join(os.path.expanduser("~"), ".paddlex")
                        if os.path.exists(default_home) and os.path.isdir(default_home):
                            # 检查目标目录是否为空（除了可能的空文件夹）
                            has_content = False
                            for root, dirs, files in os.walk(chosen):
                                if files:
                                    has_content = True
                                    break

                            if not has_content:
                                logger.info("env_manager", "migrating_models",
                                            f"正在从 {default_home} 迁移模型到 {chosen}...")
                                # 复制内容
                                try:
                                    # 遍历源目录复制，避免权限问题
                                    for item in os.listdir(default_home):
                                        s = os.path.join(default_home, item)
                                        d = os.path.join(chosen, item)
                                        if os.path.isdir(s):
                                            shutil.copytree(s, d, dirs_exist_ok=True)
                                        else:
                                            shutil.copy2(s, d)
                                    logger.info("env_manager", "migration_completed", "模型迁移完成")
                                except Exception as e:
                                    logger.error("env_manager", "migration_failed", f"模型迁移失败：{e}")

                        # 清理旧目录逻辑：如果新目录已有内容（说明迁移完成或已有新数据），则删除旧目录并标记
                        cleanup_marker = os.path.join(chosen, ".legacy_cleanup_done")
                        if not os.path.exists(cleanup_marker):
                            # 再次确认新目录是否非空
                            has_content = False
                            for root, dirs, files in os.walk(chosen):
                                if files:
                                    has_content = True
                                    break

                            # 只有在真正执行清理时才记录日志
                            if has_content and os.path.exists(default_home) and os.path.isdir(default_home):
                                logger.info("env_manager", "cleaning_legacy", f"正在清理旧版模型目录：{default_home}")
                                try:
                                    shutil.rmtree(default_home, ignore_errors=True)
                                    logger.info("env_manager", "legacy_cleanup_done", "旧版目录清理完成")
                                except Exception as e:
                                    logger.error("env_manager", "cleanup_failed", f"清理旧版目录失败：{e}")

                            # 创建标记文件，避免下次再次检查和记录日志
                            try:
                                with open(cleanup_marker, 'w') as f:
                                    f.write("1")
                            except Exception:
                                pass

                    except Exception as e:
                        logger.warning("env_manager", "migration_check_failed", f"迁移检查失败：{e}")

                    os.environ["PADDLEX_HOME"] = chosen
                    os.environ["PADDLE_PDX_CACHE_HOME"] = chosen
                    # 同时设置 PaddleOCR 的缓存目录，防止它乱跑
                    os.environ["PADDLEOCR_HOME"] = chosen

                    logger.debug("env_manager", "paddlex_home_set", f"设置 PADDLEX_HOME: {chosen}")
                    logger.debug("env_manager", "paddle_pdx_cache_set", f"设置 PADDLE_PDX_CACHE_HOME: {chosen}")

                    libs_dir = os.path.join(base_dir, "libs")
                    if os.path.isdir(libs_dir):
                        current_path = os.environ.get("PATH", "")
                        if libs_dir not in current_path:
                            os.environ["PATH"] = libs_dir + os.pathsep + current_path
                            logger.debug("env_manager", "libs_added_to_path", f"已将 libs 添加到 PATH: {libs_dir}")
                except Exception:
                    libs_dir = None

            # Disable PaddleX model source check globally
            os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

            # CPU Vendor Check（只在 configure_paddle_env 中记录一次日志）
            cpu_vendor = EnvManager.get_cpu_vendor(log_result=True)

            if cpu_vendor == "AMD":
                logger.warning("env_manager", "amd_cpu_mkldnn_disabled", "检测到 AMD CPU，已禁用 MKLDNN 以防止崩溃")
                os.environ['FLAGS_use_mkldnn'] = '0'
                os.environ['FLAGS_enable_mkldnn'] = '0'
                os.environ['DN_ENABLE_ONEDNN'] = '0'
            elif cpu_vendor == "Intel":
                logger.debug("env_manager", "intel_cpu_mkldnn_enabled", "检测到 Intel CPU，保持 MKLDNN 启用")
            else:
                logger.warning("env_manager", "unknown_cpu_mkldnn_disabled", "未知 CPU 厂商，为安全起见禁用 MKLDNN")
                os.environ['FLAGS_use_mkldnn'] = '0'
                os.environ['FLAGS_enable_mkldnn'] = '0'
                os.environ['DN_ENABLE_ONEDNN'] = '0'

            if platform.system() == "Windows":
                try:
                    import ctypes

                    def _log_cuda_dll_from_path(path):
                        try:
                            dll = ctypes.WinDLL(path)
                        except OSError:
                            return False
                        buf = ctypes.create_unicode_buffer(1024)
                        ctypes.windll.kernel32.GetModuleFileNameW(ctypes.c_void_p(dll._handle), buf, 1024)
                        dll_path = buf.value
                        source = "libs" if (libs_dir and dll_path.lower().startswith(
                            os.path.abspath(libs_dir).lower())) else "system"
                        logger.debug("env_manager", "cuda_dll_loaded", f"CUDA DLL 加载自：{dll_path} (来源={source})")
                        return True

                    logged = False
                    if libs_dir and os.path.isdir(libs_dir):
                        for name in os.listdir(libs_dir):
                            lower = name.lower()
                            if lower.startswith("cudart") and lower.endswith(".dll"):
                                candidate_path = os.path.join(libs_dir, name)
                                if _log_cuda_dll_from_path(candidate_path):
                                    logged = True
                                    break
                    if not logged:
                        logger.debug("env_manager", "no_cuda_dll_found",
                                     "未找到 CUDA DLL（可能没有 libs 目录或 cudart*.dll）")
                except Exception:
                    pass

        except Exception as e:
            logger.error("env_manager", "configure_env_error", f"配置环境变量失败：{e}")

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={}, component="EnvManager")
    def get_system_info():
        """获取系统基本信息"""
        info = {
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "gpu_name": "N/A",
            "driver_version": "N/A",
            "cuda_version": "N/A",
            "cpu_vendor": EnvManager.get_cpu_vendor()
        }

        # 尝试获取 GPU 信息
        try:
            cmd = "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader"
            output = subprocess.check_output(cmd, shell=True, text=True).strip()
            if output:
                name, driver = output.split(',')
                info['gpu_name'] = name.strip()
                info['driver_version'] = driver.strip()

            # 获取 CUDA 版本
            cmd_cuda = "nvcc --version"
            output_cuda = subprocess.check_output(cmd_cuda, shell=True, text=True)
            match = re.search(r"release (\d+\.\d+)", output_cuda)
            if match:
                info['cuda_version'] = match.group(1)
            else:
                # 尝试从 nvidia-smi 获取 (虽然这通常显示的是 Driver 支持的最高版本)
                cmd_smi_cuda = "nvidia-smi"
                output_smi = subprocess.check_output(cmd_smi_cuda, shell=True, text=True)
                match_smi = re.search(r"CUDA Version: (\d+\.\d+)", output_smi)
                if match_smi:
                    info['cuda_version'] = match_smi.group(1)

        except Exception:
            pass

        return info

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return={"installed": False}, component="EnvManager")
    def get_paddle_status():
        """获取 PaddlePaddle 安装状态"""
        status = {
            "installed": False,
            "version": "未安装",
            "gpu_support": False,
            "location": "N/A",
            "paddleocr_version": "N/A",
            "paddlex_version": "N/A"
        }

        try:
            # 使用 importlib.metadata 避免直接 import paddle 导致锁定
            dist = importlib.metadata.distribution("paddlepaddle-gpu")
            status["installed"] = True
            status["version"] = dist.version
            status["gpu_support"] = True
            status["location"] = str(dist.locate_file(''))
        except importlib.metadata.PackageNotFoundError:
            try:
                dist = importlib.metadata.distribution("paddlepaddle")
                status["installed"] = True
                status["version"] = dist.version
                status["gpu_support"] = False
                status["location"] = str(dist.locate_file(''))
            except importlib.metadata.PackageNotFoundError:
                pass

        # Check dependencies
        try:
            status["paddleocr_version"] = importlib.metadata.version("paddleocr")
        except importlib.metadata.PackageNotFoundError:
            pass

        try:
            status["paddlex_version"] = importlib.metadata.version("paddlex")
        except importlib.metadata.PackageNotFoundError:
            pass

        return status

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=[], component="EnvManager")
    def get_install_command(target_type, cuda_version=None):
        """
        生成安装命令
        target_type: 'cpu_3_2_0' | 'gpu_nightly'
        cuda_version: '11.8' | '12.6' | '12.9' (only for gpu_nightly)
        """
        cmds = []
        python_exec = sys.executable

        # Base install command
        install_cmd = [python_exec, "-m", "pip", "install"]

        if target_type == 'cpu_3_2_0':
            # CPU Stable
            cmds.append(
                install_cmd + ["paddlepaddle==3.0.0b2", "-i", "https://www.paddlepaddle.org.cn/packages/stable/cpu/"])
            cmds.append(install_cmd + ["paddleocr>=2.9.1"])
            cmds.append(install_cmd + ["paddlex==3.0.0b2"])

        elif target_type == 'gpu_nightly':
            # GPU Nightly
            if not cuda_version:
                return []

            # Map cuda version to url
            # Reference: https://www.paddlepaddle.org.cn/
            # Note: 3.0.0b2 is current next-gen

            # Nightly builds often use different URLs
            # For 11.8: paddlepaddle-gpu==3.0.0b2 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
            # But we need Windows

            # Simplified for Windows (Using official pip index if possible or paddle whl)
            # Actually, let's use the specific wheels or index-url provided by Paddle

            if cuda_version == '11.8':
                cmds.append(install_cmd + ["paddlepaddle-gpu==3.0.0b2", "-i",
                                           "https://www.paddlepaddle.org.cn/packages/stable/cu118/"])
            elif cuda_version == '12.3' or cuda_version == '12.6' or cuda_version == '12.9':
                # Assuming 12.x compatible
                cmds.append(install_cmd + ["paddlepaddle-gpu==3.0.0b2", "-i",
                                           "https://www.paddlepaddle.org.cn/packages/stable/cu123/"])
            else:
                return []

            cmds.append(install_cmd + ["paddleocr>=2.9.1"])
            cmds.append(install_cmd + ["paddlex==3.0.0b2"])

        return cmds

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=[], component="EnvManager")
    def uninstall_paddle():
        """Generate uninstall command"""
        return [sys.executable, "-m", "pip", "uninstall", "-y", "paddlepaddle", "paddlepaddle-gpu", "paddleocr",
                "paddlex"]
