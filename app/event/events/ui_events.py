# -*- coding: utf-8 -*-
"""
UI 交互事件（UI Events）

文件说明：
- 作用：定义 UI 交互相关的所有事件
- 核心实现：基于 DomainSignals 基类，提供类型安全的信号定义
- 关联关系：被 event_bus.py 引用，用于 UI 组件间的状态同步

主要事件：
- text_blocks_generated: 文本块生成
- text_block_selected: 文本块选中
- text_blocks_selected: 多个文本块选中
- text_block_hovered: 文本块悬停
"""
from PyQt5.QtCore import pyqtSignal
from app.event.event import DomainSignals


class UISignals(DomainSignals):
    """UI 交互信号"""
    
    def __init__(self):
        super().__init__("ui")
    
    # 文本块生成信号 (文本块列表)
    text_blocks_generated = pyqtSignal(list)
    
    # 文本块选中信号 (索引，数据对象)
    text_block_selected = pyqtSignal(int, object)
    
    # 多个文本块选中信号 (选中的文本块列表)
    text_blocks_selected = pyqtSignal(list)
    
    # 文本块悬停信号 (索引)
    text_block_hovered = pyqtSignal(int)
