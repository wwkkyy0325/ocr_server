# -*- coding: utf-8 -*-

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

