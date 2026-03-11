# -*- coding: utf-8 -*-
"""
事件基类 (Event Base)

文件说明:
- 作用：定义应用全局事件的基类，为事件系统提供统一的抽象层
- 核心实现：基于 PyQt5 的 QObject 实现事件的基础行为
- 关联关系：被 events 目录下的具体事件类继承，作为整个事件系统的基石

主要类:
- Event: 事件基类，所有自定义事件应继承此类
- DomainSignals: 域信号基类，用于分组管理相关信号

使用示例:
    # 定义自定义事件
    class MyEvent(Event):
        data_ready = pyqtSignal(object)
    
    event = MyEvent()
    print(f"事件名称：{event.name}")
    event.enable()  # 启用事件
"""
from PyQt5.QtCore import QObject
from app.infrastructure.error_handler import handle_errors, ErrorCode


class Event(QObject):
    """
    事件基类
    
    所有自定义事件应继承此类，提供统一的事件行为和接口。
    继承自 QObject，支持 PyQt5 的信号槽机制。
    
    特性:
    1. 自动注册到 Qt 对象树 (如果提供父对象)
    2. 支持信号槽连接
    3. 可扩展自定义属性和方法
    4. 提供事件启用/禁用控制
    
    使用示例:
        class FileProcessEvent(Event):
            file_loaded = pyqtSignal(str)
            file_processed = pyqtSignal(str, str)
            
        event = FileProcessEvent()
        event.file_loaded.connect(on_file_loaded)
        
        # 检查事件状态
        if event.enabled:
            print("事件已启用")
        
        # 检查信号连接
        if event.is_signal_connected('file_loaded'):
            print("file_loaded 信号已连接")
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self._name = self.__class__.__name__
    
    @property
    def name(self):
        """获取事件名称"""
        return self._name
    
    @property
    def enabled(self):
        """获取事件启用状态"""
        return self._enabled
    
    def enable(self):
        """启用事件"""
        self._enabled = True
    
    def disable(self):
        """禁用事件"""
        self._enabled = False
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=False, component="Event")
    def is_signal_connected(self, signal_name: str) -> bool:
        """
        检查指定信号是否有连接
        
        Args:
            signal_name: 信号名称
            
        Returns:
            bool: 是否有连接
        """
        try:
            signal = getattr(self, signal_name, None)
            if signal is None:
                return False
            return signal.receivers() > 0
        except Exception:
            return False


class DomainSignals(QObject):
    """
    域信号基类
    
    用于分组管理相关的信号，提供命名空间隔离。
    每个功能域应创建一个域信号类继承此类。
    
    特性:
    1. 自动信号注册
    2. 域隔离，避免命名冲突
    3. 支持批量操作
    4. 提供域名称标识
    
    使用示例:
        class ProcessingDomainSignals(DomainSignals):
            status_updated = pyqtSignal(str, str)
            progress_updated = pyqtSignal(int, int)
        
        signals = ProcessingDomainSignals("processing")
        print(f"域名称：{signals.domain_name}")
        
        # 获取所有信号
        signal_names = signals.get_signals()
        print(f"信号列表：{signal_names}")
    """
    
    def __init__(self, domain_name: str = "unknown"):
        super().__init__()
        self._domain_name = domain_name
    
    @property
    def domain_name(self):
        """获取域名称"""
        return self._domain_name
    
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=[], component="DomainSignals")
    def get_signals(self):
        """获取所有信号名称列表"""
        signals = []
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if hasattr(attr, 'connect'):
                signals.append(attr_name)
        return signals
