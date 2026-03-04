# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：简单的服务注册表，提供组件间按名称共享/检索实例的机制
# - 核心实现：类级字典维护服务对象，支持注册/获取/注销/列举
# - 关联关系：主窗口与控制层可通过此处共享如 ResultManager/TaskManager 等服务实例
from typing import Dict, Any


class ServiceRegistry:
    _services: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, service: Any) -> None:
        cls._services[name] = service

    @classmethod
    def get(cls, name: str) -> Any:
        return cls._services.get(name)

    @classmethod
    def unregister(cls, name: str) -> None:
        cls._services.pop(name, None)

    @classmethod
    def all(cls) -> Dict[str, Any]:
        return dict(cls._services)
