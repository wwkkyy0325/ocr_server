# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import platform
import re
import importlib.metadata
import json
from datetime import datetime

class EnvManager:
    @staticmethod
    def get_cpu_vendor():
        """
        获取 CPU 厂商信息 (Intel/AMD)
        Returns: 'Intel', 'AMD', or 'Unknown'
        """
        vendor = "Unknown"
        try:
            if platform.system() == "Windows":
                # Use wmic for accurate vendor info
                cmd = "wmic cpu get name"
                output = subprocess.check_output(cmd, shell=True, text=True)
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
        except Exception:
            pass
            
        return vendor

    @staticmethod
    def configure_paddle_env():
        """
        Configure environment variables for PaddlePaddle based on CPU vendor.
        Must be called before importing paddle.
        """
        try:
            # Common fixes for Windows
            if platform.system() == "Windows":
                os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
                os.environ["OMP_NUM_THREADS"] = "1"
                os.environ["MKL_NUM_THREADS"] = "1"
                os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
                os.environ["NUMEXPR_NUM_THREADS"] = "1"

            # Disable PaddleX model source check globally
            os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

            # CPU Vendor Check
            cpu_vendor = EnvManager.get_cpu_vendor()
            print(f"[EnvManager] CPU Vendor detected: {cpu_vendor}")
            
            if cpu_vendor == "AMD":
                print("[EnvManager] AMD CPU detected. Disabling MKLDNN to prevent 'invalid vector subscript' crashes.")
                os.environ['FLAGS_use_mkldnn'] = '0'
                os.environ['FLAGS_enable_mkldnn'] = '0'
                os.environ['DN_ENABLE_ONEDNN'] = '0'
            elif cpu_vendor == "Intel":
                print("[EnvManager] Intel CPU detected. Keeping MKLDNN enabled (default).")
            else:
                print("[EnvManager] Unknown CPU vendor. Disabling MKLDNN for safety.")
                os.environ['FLAGS_use_mkldnn'] = '0'
                os.environ['FLAGS_enable_mkldnn'] = '0'
                os.environ['DN_ENABLE_ONEDNN'] = '0'
                
        except Exception as e:
            print(f"[EnvManager] Error configuring env: {e}")

    @staticmethod
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
                # 尝试从 nvidia-smi 获取 (虽然这通常显示的是Driver支持的最高版本)
                cmd_smi_cuda = "nvidia-smi"
                output_smi = subprocess.check_output(cmd_smi_cuda, shell=True, text=True)
                match_smi = re.search(r"CUDA Version: (\d+\.\d+)", output_smi)
                if match_smi:
                    info['cuda_version'] = match_smi.group(1)
                    
        except Exception:
            pass
            
        return info

    @staticmethod
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
            cmds.append(install_cmd + ["paddlepaddle==3.0.0b2", "-i", "https://www.paddlepaddle.org.cn/packages/stable/cpu/"])
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
                 cmds.append(install_cmd + ["paddlepaddle-gpu==3.0.0b2", "-i", "https://www.paddlepaddle.org.cn/packages/stable/cu118/"])
            elif cuda_version == '12.3' or cuda_version == '12.6' or cuda_version == '12.9':
                 # Assuming 12.x compatible
                 cmds.append(install_cmd + ["paddlepaddle-gpu==3.0.0b2", "-i", "https://www.paddlepaddle.org.cn/packages/stable/cu123/"])
            else:
                 return []

            cmds.append(install_cmd + ["paddleocr>=2.9.1"])
            cmds.append(install_cmd + ["paddlex==3.0.0b2"])

        return cmds

    @staticmethod
    def uninstall_paddle():
        """Generate uninstall command"""
        return [sys.executable, "-m", "pip", "uninstall", "-y", "paddlepaddle", "paddlepaddle-gpu", "paddleocr", "paddlex"]
