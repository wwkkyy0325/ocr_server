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
    def get_system_info():
        """获取系统基本信息"""
        info = {
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "gpu_name": "N/A",
            "driver_version": "N/A",
            "cuda_version": "N/A"
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
        
        # 基础依赖修复命令 (防止 packaging 等库版本冲突)
        fix_cmd = [sys.executable, "-m", "pip", "install", "--ignore-installed", "packaging", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        
        if target_type == 'cpu_3_2_0':
            # CPU 模式：严格按照用户当前环境版本恢复
            deps_stable = ["paddleocr==3.2.0", "paddlex==3.2.1"]
            cmd = [sys.executable, "-m", "pip", "install", "paddlepaddle==3.2.0"] + deps_stable + \
                  ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "--force-reinstall", "--no-cache-dir"]
            return [fix_cmd, cmd]
            
        elif target_type == 'gpu_nightly':
            if not cuda_version:
                return None
                
            cuda_map = {
                '11.8': 'cu118',
                '12.6': 'cu126',
                '12.9': 'cu129'
            }
            tag = cuda_map.get(cuda_version)
            if not tag:
                return None
                
            url = f"https://www.paddlepaddle.org.cn/packages/nightly/{tag}/"
            
            # GPU Nightly 模式：安装 gpu 版本的 paddlepaddle
            # 同时安装最新版的 paddleocr 和 paddlex，以保证与新核心的兼容性
            deps_latest = ["paddleocr", "paddlex"]
            cmd = [sys.executable, "-m", "pip", "install", "--pre", "paddlepaddle-gpu"] + deps_latest + \
                  ["-i", url, "--extra-index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--force-reinstall", "--no-cache-dir"]
            return [fix_cmd, cmd]
            
        return None

    @staticmethod
    def uninstall_paddle():
        """生成卸载命令"""
        return [sys.executable, "-m", "pip", "uninstall", "-y", "paddlepaddle", "paddlepaddle-gpu", "paddleocr", "paddlex"]

    @staticmethod
    def backup_environment(backup_dir="backup"):
        """备份环境"""
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(backup_dir, f"requirements_backup_{timestamp}.txt")
        
        with open(filename, "w") as f:
            subprocess.run([sys.executable, "-m", "pip", "freeze"], stdout=f)
        return filename
