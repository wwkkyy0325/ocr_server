# -*- coding: utf-8 -*-
from typing import List, Callable, Dict, Any
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QObject

# Import logger and error handler
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()


class UIConstraintManager(QObject):
    """
    UI 约束管理器 (UI Constraint Manager)
    
    作用：
    - 集中管理 UI组件之间的互斥、依赖和状态约束逻辑。
    - 解决"当 A 开启时，B 必须关闭且禁用"这类复杂的业务逻辑。
    - 配合 ConfigManager 和 ConfigBinder 使用，处理比简单的"启用/禁用"更复杂的场景。
    
    核心概念：
    - Rule (规则): 一个函数，接收当前的 Context (配置/状态)，返回一组 Action。
    - Action (动作): 对某个 UI组件的具体操作（如 setEnabled, setChecked, setVisible）。
    """

    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="UIConstraintManager")
    def __init__(self, config_manager):
        super().__init__()
        self.cm = config_manager
        self._rules: List[Callable[[Dict[str, Any]], None]] = []
        logger.debug("ui_constraint_manager", "initialized", "UIConstraintManager initialized")

        # 监听配置变更，触发规则评估
        self.cm.setting_changed.connect(self._evaluate_rules)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="UIConstraintManager")
    def add_rule(self, rule_func: Callable[[Dict[str, Any]], None]):
        """
        添加一条约束规则
        
        rule_func: 接收 config 字典，直接执行副作用（修改 UI 状态）
        建议：虽然可以直接修改 UI，但为了解耦，最好通过闭包持有 UI 引用。
        """
        try:
            self._rules.append(rule_func)
            # 立即评估一次
            self._evaluate_rules()
        except Exception as e:
            logger.error("ui_constraint_manager", "add_rule_failed", f"添加约束规则失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="UIConstraintManager")
    def _evaluate_rules(self, *_):
        """评估所有规则"""
        try:
            # 获取当前配置快照
            # 注意：这里直接访问 self.cm.config 可能有线程安全问题，但在主线程 UI 逻辑中通常是安全的
            current_config = self.cm.config

            for rule in self._rules:
                try:
                    rule(current_config)
                except Exception as e:
                    logger.error("ui_constraint_manager", "rule_evaluation_error",
                                 f"评估 UI 约束规则失败：{e}", exc_info=True)
        except Exception as e:
            logger.error("ui_constraint_manager", "evaluate_rules_failed", f"评估所有规则失败：{e}", exc_info=True)

    # --- 预定义的常见约束模式 ---

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="UIConstraintManager")
    def add_mutex_constraint(self,
                             trigger_key: str,
                             trigger_value: Any,
                             target_widgets: List[QWidget],
                             target_keys: List[str] = None):
        """
        添加互斥约束：
        当 config[trigger_key] == trigger_value 时：
        1. 禁用 (Disable) 所有 target_widgets
        2. (可选) 将 target_keys 对应的配置设为 False/默认值
        
        场景：开启"AI 表格"模式时，必须强制关闭并禁用"文档矫正"和"方向分类"。
        """
        try:
            def mutex_rule(config):
                is_triggered = config.get(trigger_key) == trigger_value

                for widget in target_widgets:
                    if not widget: continue
                    # 如果触发了互斥，控件被禁用；否则恢复启用
                    # 注意：这里假设控件原本应该是启用的。如果控件还有其他依赖，可能需要更复杂的逻辑（如 && 运算）
                    # 简单起见，这里直接 setEnabled(!is_triggered)
                    # 更好的做法是：ConfigBinder 处理基础依赖，Constraint 处理强制覆盖
                    widget.setEnabled(not is_triggered)

                if is_triggered and target_keys:
                    for t_key in target_keys:
                        # 如果当前是 True，强制设为 False
                        if config.get(t_key):
                            logger.info("ui_constraint_manager", "mutex_constraint_triggered",
                                        f"[UIConstraint] Mutex triggered: {trigger_key}={trigger_value} -> Force disabling {t_key}")
                            self.cm.set_setting(t_key, False)

            self.add_rule(mutex_rule)
        except Exception as e:
            logger.error("ui_constraint_manager", "add_mutex_constraint_failed", f"添加互斥约束失败：{e}", exc_info=True)
