# -*- coding: utf-8 -*-
"""
插件元数据 - 定义插件的依赖关系、版本兼容性等信息

作用：为插件提供标准化的元数据描述，支持依赖解析和版本检查

元数据格式（在插件目录下的 plugin.json 文件中定义）：
{
    "id": "example_plugin",
    "name": "Example Plugin", 
    "version": "1.0.0",
    "description": "A example plugin",
    "author": "Author Name",
    "dependencies": {
        "required": {
            "core_plugin": "^1.0.0"
        },
        "optional": {
            "another_plugin": "~2.0.0"
        }
    },
    "main_class": "ExamplePlugin",
    "load_order": 100,
    "compatibility": {
        "min_ocr_server_version": "1.0.0",
        "max_ocr_server_version": "2.0.0"
    }
}
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
import re
from app.infrastructure.error_handler import handle_errors, ErrorCode


@dataclass
class PluginDependency:
    """插件依赖信息"""
    plugin_id: str
    version_range: str  # 语义化版本范围，如 "^1.0.0", "~2.0.0", ">=1.0.0 <2.0.0"
    required: bool = True
    
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginDependency")
    def matches_version(self, version: str) -> bool:
        """检查版本是否匹配范围"""
        if not self.version_range:
            return True
            
        # 简化的版本匹配逻辑
        if self.version_range.startswith('^'):
            # 兼容版本（主版本相同）
            base_version = self.version_range[1:]
            base_parts = base_version.split('.')
            check_parts = version.split('.')
            
            if len(base_parts) >= 1 and len(check_parts) >= 1:
                return base_parts[0] == check_parts[0]
            return False
            
        elif self.version_range.startswith('~'):
            # 补丁版本兼容（主次版本相同）
            base_version = self.version_range[1:]
            base_parts = base_version.split('.')
            check_parts = version.split('.')
            
            if len(base_parts) >= 2 and len(check_parts) >= 2:
                return base_parts[0] == check_parts[0] and base_parts[1] == check_parts[1]
            return False
            
        else:
            # 精确版本匹配或其他情况
            return version == self.version_range


@dataclass
class PluginMetadata:
    """插件元数据"""
    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[PluginDependency] = field(default_factory=list)
    main_class: str = ""
    load_order: int = 1000  # 数字越小越早加载
    min_ocr_server_version: str = "0.0.0"
    max_ocr_server_version: str = "999.999.999"
    
    @classmethod
    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return=None, component="PluginMetadata")
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginMetadata':
        """从字典创建元数据对象"""
        metadata = cls(
            id=data['id'],
            name=data.get('name', data['id']),
            version=data['version'],
            description=data.get('description', ''),
            author=data.get('author', ''),
            main_class=data.get('main_class', ''),
            load_order=data.get('load_order', 1000),
            min_ocr_server_version=data.get('compatibility', {}).get('min_ocr_server_version', '0.0.0'),
            max_ocr_server_version=data.get('compatibility', {}).get('max_ocr_server_version', '999.999.999')
        )
        
        # 解析依赖
        deps_data = data.get('dependencies', {})
        if isinstance(deps_data, dict):
            # 处理 required 依赖
            required_deps = deps_data.get('required', {})
            if isinstance(required_deps, dict):
                for dep_id, version_range in required_deps.items():
                    metadata.dependencies.append(PluginDependency(dep_id, version_range, True))
            
            # 处理 optional 依赖
            optional_deps = deps_data.get('optional', {})
            if isinstance(optional_deps, dict):
                for dep_id, version_range in optional_deps.items():
                    metadata.dependencies.append(PluginDependency(dep_id, version_range, False))
            
        return metadata
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginMetadata")
    def get_required_dependencies(self) -> List[str]:
        """获取必需的依赖插件 ID 列表"""
        return [dep.plugin_id for dep in self.dependencies if dep.required]
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginMetadata")
    def get_optional_dependencies(self) -> List[str]:
        """获取可选的依赖插件 ID 列表"""
        return [dep.plugin_id for dep in self.dependencies if not dep.required]
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginMetadata")
    def get_all_dependencies(self) -> List[str]:
        """获取所有依赖插件 ID 列表"""
        return [dep.plugin_id for dep in self.dependencies]