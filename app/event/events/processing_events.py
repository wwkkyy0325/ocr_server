# -*- coding: utf-8 -*-
"""
处理流程事件（Processing Events）

文件说明：
- 作用：定义 OCR 处理流程中的所有事件
- 核心实现：基于 DomainSignals 基类，提供类型安全的信号定义
- 关联关系：被 event_bus.py 引用，用于 OCR 处理流程的状态同步

主要事件：
- status_updated: 状态更新
- file_processed: 文件处理完成
- processing_finished: 批处理完成
- progress_updated: 进度更新
- ocr_result_ready: OCR 结果就绪
"""
from PyQt5.QtCore import pyqtSignal
from app.event.event import DomainSignals


class ProcessingSignals(DomainSignals):
    """OCR 处理流程信号"""
    
    def __init__(self):
        super().__init__("processing")
    
    # 状态更新信号 (状态文本，状态类型)
    status_updated = pyqtSignal(str, str)
    
    # 文件处理完成信号 (文件名，结果文本)
    file_processed = pyqtSignal(str, str)
    
    # 批处理完成信号 (总耗时)
    processing_finished = pyqtSignal(float)
    
    # 进度更新信号 (当前值，最大值)
    progress_updated = pyqtSignal(int, int)
    
    # OCR 结果就绪信号 (结果文本)
    ocr_result_ready = pyqtSignal(str)
    
    # 🔥 OCR 进程管理相关信号
    # 工作进程生命周期事件
    worker_started = pyqtSignal(dict)  # {preset: str, pid: int}
    worker_stopped = pyqtSignal(dict)  # {reason: str, preset: str}
    worker_start_failed = pyqtSignal(dict)  # {error: str, preset: str}
    
    # 任务处理事件
    task_submitted = pyqtSignal(dict)  # {task_id: str, image_path: str}
    task_completed = pyqtSignal(dict)  # {task_id: str, processing_time: float}
    task_failed = pyqtSignal(dict)  # {task_id: str, error: str}
    
    # 配置切换事件
    preset_switched = pyqtSignal(dict)  # {old_preset: str, new_preset: str}
    preset_switch_failed = pyqtSignal(dict)  # {error: str, old_preset: str, new_preset: str}
    
    # 🔥 新增：处理后结果就绪信号（完整结果数据）
    # 在结果处理完成后、UI渲染前触发，包含完整的处理结果数据
    processed_result_ready = pyqtSignal(dict)  # {filename: str, image_path: str, full_text: str, regions: list, metadata: dict}