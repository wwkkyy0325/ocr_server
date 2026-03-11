# -*- coding: utf-8 -*-
"""
插件依赖解析器 - 解析插件依赖关系并确定加载顺序

作用：分析插件间的依赖关系，检测循环依赖，并生成正确的加载顺序
"""

from typing import Dict, List, Set, Tuple
from app.api.plugin_metadata import PluginMetadata
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode


class PluginDependencyResolver:
    """插件依赖解析器"""
    
    def __init__(self):
        self.logger = get_logger()
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginDependencyResolver")
    def resolve_load_order(self, plugins: Dict[str, PluginMetadata]) -> List[str]:
        """
        解析插件加载顺序
        
        Args:
            plugins: 插件元数据字典 {plugin_id: metadata}
            
        Returns:
            List[str]: 按加载顺序排列的插件 ID 列表
            
        Raises:
            ValueError: 存在循环依赖或缺失依赖
        """
        # 构建依赖图
        dependency_graph = {}
        all_plugins = set(plugins.keys())
        
        for plugin_id, metadata in plugins.items():
            dependencies = metadata.get_required_dependencies()
            # 过滤掉不存在的依赖（可选依赖可以不存在）
            valid_dependencies = [dep for dep in dependencies if dep in all_plugins]
            dependency_graph[plugin_id] = valid_dependencies
            
        # 检测循环依赖
        if self._has_cycle(dependency_graph):
            raise ValueError("检测到插件循环依赖")
            
        # 拓扑排序确定加载顺序
        load_order = self._topological_sort(dependency_graph)
        
        # 根据 load_order 字段进行微调
        load_order = self._adjust_by_load_order(load_order, plugins)
        
        return load_order
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=False, component="PluginDependencyResolver")
    def _has_cycle(self, graph: Dict[str, List[str]]) -> bool:
        """检测依赖图中是否存在循环依赖"""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
                
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if dfs(neighbor):
                    return True
                    
            rec_stack.remove(node)
            return False
            
        for node in graph:
            if dfs(node):
                return True
        return False
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=[], component="PluginDependencyResolver")
    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """拓扑排序算法"""
        # 计算入度
        in_degree = {}
        all_nodes = set(graph.keys())
        for deps in graph.values():
            all_nodes.update(deps)
            
        for node in all_nodes:
            in_degree[node] = 0
            
        for deps in graph.values():
            for dep in deps:
                in_degree[dep] += 1
                
        # Kahn 算法
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        if len(result) != len(all_nodes):
            raise ValueError("依赖图中存在循环依赖")
            
        return result
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=None, component="PluginDependencyResolver")
    def _adjust_by_load_order(self, base_order: List[str], plugins: Dict[str, PluginMetadata]) -> List[str]:
        """根据 load_order 字段对基础顺序进行微调"""
        # 创建 (load_order, original_index, plugin_id) 的元组列表
        ordered_plugins = []
        for i, plugin_id in enumerate(base_order):
            if plugin_id in plugins:
                load_order_val = plugins[plugin_id].load_order
            else:
                load_order_val = 1000
            ordered_plugins.append((load_order_val, i, plugin_id))
            
        # 按 load_order 排序，如果相同则保持原有顺序
        ordered_plugins.sort(key=lambda x: (x[0], x[1]))
        
        return [plugin_id for _, _, plugin_id in ordered_plugins]
        
    @handle_errors(error_code=ErrorCode.DEPENDENCY, fallback_return=(False, []), component="PluginDependencyResolver")
    def validate_dependencies(self, plugins: Dict[str, PluginMetadata]) -> Tuple[bool, List[str]]:
        """
        验证插件依赖是否满足
        
        Args:
            plugins: 插件元数据字典
            
        Returns:
            Tuple[bool, List[str]]: (是否有效，错误信息列表)
        """
        errors = []
        all_plugin_ids = set(plugins.keys())
        
        for plugin_id, metadata in plugins.items():
            # 检查必需依赖
            required_deps = metadata.get_required_dependencies()
            missing_deps = [dep for dep in required_deps if dep not in all_plugin_ids]
            if missing_deps:
                errors.append(f"插件 {plugin_id} 缺少必需依赖：{', '.join(missing_deps)}")
                
            # 检查版本兼容性（简化处理）
            # TODO: 实现完整的语义化版本检查
            
        return len(errors) == 0, errors