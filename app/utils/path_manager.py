# -*- coding: utf-8 -*-
"""
路径管理器 - 统一管理项目中的所有路径规则

职责：
    - 计算和规范化项目内的各种路径
    - 确保目录存在
    - 提供安全的路径检查
    - 封装 pathlib 操作，避免直接使用 os.path

使用示例：
    path_mgr = PathManager(project_root)
    
    # 获取输出目录
    output_dir = path_mgr.get_output_dir()
    
    # 计算 MessagePack 文件路径
    msgpack_path = path_mgr.get_msgpack_path(image_path)
    
    # 确保目录存在
    path_mgr.ensure_dir_exists(output_dir)
"""

from pathlib import Path
from typing import Optional, Union


class PathManager:
    """
    路径管理器
    
    统一管理项目路径规则，避免路径逻辑散落在各处
    """
    
    def __init__(self, project_root: str):
        """
        初始化路径管理器
        
        Args:
            project_root: 项目根目录路径
        """
        self.project_root = Path(project_root).resolve()
        
        # 核心目录配置
        self.output_base_dir = self.project_root / "data" / "outputs"
        self.msgpack_subdir = "msgpack"  # MessagePack 子目录名
        self.index_filename = "msgpack_index.msgpack"  # 索引文件名
        
        # 其他常用目录
        self.logs_dir = self.project_root / "logs"
        self.temp_dir = self.project_root / "temp"
        self.models_dir = self.project_root / "models"
        self.libs_dir = self.project_root / "libs"
    
    def get_output_dir(self, image_path: Optional[str] = None) -> Path:
        """
        获取输出目录
        
        Args:
            image_path: 原始图像路径（可选），如果提供则返回对应的子目录
            
        Returns:
            输出目录路径
            
        示例：
            # 基础输出目录
            >>> path_mgr.get_output_dir()
            Path('/project/data/outputs')
            
            # 带图像路径的输出目录
            >>> path_mgr.get_output_dir("/path/to/folder/image.jpg")
            Path('/project/data/outputs/folder')
        """
        if image_path is None:
            return self.output_base_dir
        
        # 提取图像所在文件夹名称作为子目录
        image_path_obj = Path(image_path)
        parent_name = image_path_obj.parent.name
        
        # 如果是虚拟路径（如 PDF 页），提取真实路径
        if "|page=" in str(image_path):
            real_path = image_path.split("|page=")[0]
            parent_name = Path(real_path).parent.name
        
        return self.output_base_dir / parent_name
    
    def get_msgpack_dir(self, image_path: Optional[str] = None) -> Path:
        """
        获取 MessagePack 文件存储目录
        
        Args:
            image_path: 原始图像路径（可选）
            
        Returns:
            MessagePack 目录路径
        """
        output_dir = self.get_output_dir(image_path)
        return output_dir / self.msgpack_subdir
    
    def get_msgpack_path(self, image_path: str, filename: Optional[str] = None) -> Path:
        """
        计算 MessagePack 文件的完整路径
        
        Args:
            image_path: 原始图像路径
            filename: 可选的文件名（不含扩展名）
            
        Returns:
            MessagePack 文件路径
            
        示例：
            >>> path_mgr.get_msgpack_path("/path/to/folder/image.jpg")
            Path('/project/data/outputs/folder/msgpack/image.msgpack')
        """
        msgpack_dir = self.get_msgpack_dir(image_path)
        
        # 确定文件名
        if filename is None:
            # 处理虚拟路径
            real_path = image_path.split("|page=")[0] if "|page=" in str(image_path) else image_path
            filename = Path(real_path).stem  # 不含扩展名的文件名
        
        # 清理文件名中的特殊字符
        safe_filename = filename.replace(':', '_')
        
        return msgpack_dir / f"{safe_filename}.msgpack"
    
    def get_index_path(self) -> Path:
        """
        获取索引文件路径
        
        Returns:
            索引文件路径
        """
        return self.output_base_dir / self.index_filename
    
    def ensure_dir_exists(self, path: Union[Path, str]) -> None:
        """
        确保目录存在，如果不存在则创建
        
        Args:
            path: 目录路径
        """
        path_obj = Path(path) if isinstance(path, str) else path
        path_obj.mkdir(parents=True, exist_ok=True)
    
    def ensure_output_dirs_exist(self, image_path: Optional[str] = None) -> None:
        """
        确保输出目录结构存在
        
        Args:
            image_path: 原始图像路径（可选）
        """
        output_dir = self.get_output_dir(image_path)
        msgpack_dir = self.get_msgpack_dir(image_path)
        
        self.ensure_dir_exists(output_dir)
        self.ensure_dir_exists(msgpack_dir)
    
    def is_safe_path(self, path: Union[Path, str], base_path: Optional[Union[Path, str]] = None) -> bool:
        """
        检查路径是否安全（防止目录穿越攻击）
        
        Args:
            path: 要检查的路径
            base_path: 基准路径（默认为项目根目录）
            
        Returns:
            True 如果路径安全（在基准路径内）
        """
        path_obj = Path(path).resolve()
        base_obj = Path(base_path).resolve() if base_path else self.project_root
        
        try:
            # 检查 path 是否在 base 内部
            path_obj.relative_to(base_obj)
            return True
        except ValueError:
            return False
    
    def get_relative_path(self, path: Union[Path, str], base_path: Optional[Union[Path, str]] = None) -> str:
        """
        获取相对于基准路径的相对路径
        
        Args:
            path: 目标路径
            base_path: 基准路径（默认为项目根目录）
            
        Returns:
            相对路径字符串
        """
        path_obj = Path(path).resolve()
        base_obj = Path(base_path).resolve() if base_path else self.project_root
        
        try:
            return str(path_obj.relative_to(base_obj))
        except ValueError:
            # 如果不在同一分区，返回绝对路径
            return str(path_obj)
    
    def normalize_path(self, path: str) -> str:
        """
        规范化路径字符串
        
        Args:
            path: 原始路径字符串
            
        Returns:
            规范化后的路径字符串
        """
        return str(Path(path).resolve())
    
    def join_paths(self, *paths: str) -> str:
        """
        连接多个路径
        
        Args:
            *paths: 路径片段
            
        Returns:
            连接后的路径字符串
        """
        result = Path(paths[0])
        for p in paths[1:]:
            result = result / p
        return str(result)
    
    def get_temp_path(self, subpath: str = "") -> Path:
        """
        获取临时目录下的路径
        
        Args:
            subpath: 子路径
            
        Returns:
            临时文件/目录路径
        """
        self.ensure_dir_exists(self.temp_dir)
        return self.temp_dir / subpath if subpath else self.temp_dir
    
    def get_log_path(self, filename: str = "ocr.log") -> Path:
        """
        获取日志文件路径
        
        Args:
            filename: 日志文件名
            
        Returns:
            日志文件路径
        """
        self.ensure_dir_exists(self.logs_dir)
        return self.logs_dir / filename
    
    def get_model_path(self, model_name: str) -> Path:
        """
        获取模型文件路径
        
        Args:
            model_name: 模型文件名
            
        Returns:
            模型文件路径
        """
        return self.models_dir / model_name
    
    def cleanup_temp(self) -> None:
        """
        清理临时目录
        """
        import shutil
        
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                from app.log.log_bus import get_logger
                logger = get_logger()
                logger.warning("path_manager", "cleanup_temp_failed", f"清理临时目录失败：{e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"PathManager(project_root={self.project_root})"
