# -*- coding: utf-8 -*-
"""
下载事件（Download Events）

文件说明：
- 作用：定义模型下载相关的事件
- 核心实现：基于 DomainSignals 基类，提供类型安全的信号定义
- 关联关系：被 event_bus.py 引用，用于模型下载进度的状态同步

主要事件：
- model_download_progress: 模型下载进度
- model_download_finished: 模型下载完成
"""
from PyQt5.QtCore import pyqtSignal
from app.event.event import DomainSignals


class DownloadSignals(DomainSignals):
    """模型下载进度信号"""
    
    def __init__(self):
        super().__init__("download")
    
    # 模型下载进度信号 (当前值，最大值)
    model_download_progress = pyqtSignal(int, int)
    
    # 模型下载完成信号 (是否成功，消息文本)
    model_download_finished = pyqtSignal(bool, str)
