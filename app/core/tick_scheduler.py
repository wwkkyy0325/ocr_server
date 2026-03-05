# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from PyQt5.QtCore import QObject, QTimer


@dataclass
class _SystemEntry:
    name: str
    callback: Callable[[], None]
    every_ticks: int
    priority: int
    enabled: bool = True
    last_tick: int = 0


class TickScheduler(QObject):
    def __init__(self, tick_ms: int = 50, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._tick_ms = max(1, int(tick_ms))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._tick = 0
        self._systems: Dict[str, _SystemEntry] = {}

    @property
    def tick(self) -> int:
        return self._tick

    def start(self):
        if not self._timer.isActive():
            self._timer.start(self._tick_ms)

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()

    def register_system(self, name: str, callback: Callable[[], None], every_ticks: int = 1, priority: int = 0):
        every = max(1, int(every_ticks))
        self._systems[name] = _SystemEntry(
            name=name,
            callback=callback,
            every_ticks=every,
            priority=int(priority),
            enabled=True,
            last_tick=self._tick,
        )

    def unregister_system(self, name: str):
        self._systems.pop(name, None)

    def set_enabled(self, name: str, enabled: bool):
        entry = self._systems.get(name)
        if entry:
            entry.enabled = bool(enabled)

    def _on_tick(self):
        self._tick += 1
        entries = [e for e in self._systems.values() if e.enabled]
        entries.sort(key=lambda e: e.priority, reverse=True)
        for entry in entries:
            if (self._tick - entry.last_tick) < entry.every_ticks:
                continue
            entry.last_tick = self._tick
            try:
                entry.callback()
            except Exception:
                continue


_global_scheduler = None


def get_tick_scheduler():
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = TickScheduler()
        try:
            from app.core.service_registry import ServiceRegistry
            ServiceRegistry.register("tick_scheduler", _global_scheduler)
        except Exception:
            pass
    return _global_scheduler

