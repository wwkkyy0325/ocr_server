# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QCheckBox, QSpinBox, QComboBox, QButtonGroup, QWidget
from PyQt5.QtCore import QObject

# Import logger and error handler
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()


class ConfigBinder(QObject):
    """
    配置绑定器：实现 UI 控件与 ConfigManager 的双向绑定
    
    功能：
    1. UI -> Config: 控件值改变时自动更新配置
    2. Config -> UI: 配置改变时自动刷新控件状态
    3. Dependency: 支持基于配置值的控件启用/禁用联动
    """

    @handle_errors(error_code=ErrorCode.UI_INIT_001, fallback_return=None, component="ConfigBinder")
    def __init__(self, config_manager):
        super().__init__()
        self.cm = config_manager
        self._bindings = {}  # key -> list of widgets
        self._dependencies = {}  # key -> list of (widget, condition_func)
        logger.debug("config_binder", "initialized", "ConfigBinder initialized")

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def bind_checkbox(self, widget: QCheckBox, key: str, invert: bool = False):
        """绑定 QCheckBox"""
        try:
            # Init value
            val = self.cm.get_setting(key, False)
            widget.setChecked(not val if invert else val)

            # Connect signal
            def on_toggled(checked):
                final_val = not checked if invert else checked
                self.cm.set_setting(key, final_val)

            widget.toggled.connect(on_toggled)
            self._register_binding(key, widget, lambda w, v: w.setChecked(not v if invert else v))
        except Exception as e:
            logger.error("config_binder", "bind_checkbox_failed", f"绑定复选框失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def bind_spinbox(self, widget: QSpinBox, key: str, default=0):
        """绑定 QSpinBox"""
        try:
            val = self.cm.get_setting(key, default)
            widget.setValue(val)

            widget.valueChanged.connect(lambda v: self.cm.set_setting(key, v))
            self._register_binding(key, widget, lambda w, v: w.setValue(v))
        except Exception as e:
            logger.error("config_binder", "bind_spinbox_failed", f"绑定数值输入框失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def bind_combobox(self, widget: QComboBox, key: str, default_index=0):
        """绑定 QComboBox (基于 Index)"""
        try:
            # 当前仅支持 Index 绑定
            val = self.cm.get_setting(key, default_index)
            if isinstance(val, int):
                widget.setCurrentIndex(val)

            widget.currentIndexChanged.connect(lambda v: self.cm.set_setting(key, v))
            self._register_binding(key, widget, lambda w, v: w.setCurrentIndex(v) if isinstance(v, int) else None)
        except Exception as e:
            logger.error("config_binder", "bind_combobox_failed", f"绑定下拉框失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def bind_radio_group(self, group: QButtonGroup, key: str, value_map: dict, default=None):
        """
        绑定 RadioGroup
        value_map: {radioButtonWidget: "value_in_config"}
        """
        try:
            # Init state
            current_val = self.cm.get_setting(key, default)
            for radio_btn, config_val in value_map.items():
                if config_val == current_val:
                    radio_btn.setChecked(True)
                    break

            # Connect signal (using buttonClicked which sends the button)
            def on_button_clicked(clicked_btn):
                if clicked_btn in value_map:
                    self.cm.set_setting(key, value_map[clicked_btn])

            group.buttonClicked.connect(on_button_clicked)

            # Update logic
            def update_group(v):
                # v is the new value
                # We need to find which button corresponds to v
                for radio_btn, config_val in value_map.items():
                    if config_val == v:
                        radio_btn.setChecked(True)
                        return

            self._register_binding(key, group, update_group)
        except Exception as e:
            logger.error("config_binder", "bind_radio_group_failed", f"绑定单选组失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def bind_enabled(self, widget: QWidget, dependency_key: str, condition=lambda x: bool(x)):
        """
        绑定控件的启用状态 (Enabled/Disabled)
        condition: 函数，接收配置值，返回 True(Enable) 或 False(Disable)
        """
        try:
            # Init state
            val = self.cm.get_setting(dependency_key)
            widget.setEnabled(condition(val))

            # Register
            if dependency_key not in self._dependencies:
                self._dependencies[dependency_key] = []
            self._dependencies[dependency_key].append((widget, condition))
        except Exception as e:
            logger.error("config_binder", "bind_enabled_failed", f"绑定启用状态失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def bind_visible(self, widget: QWidget, dependency_key: str, condition=lambda x: bool(x)):
        """
        绑定控件的可见性
        注意：此方法仅设置初始状态，暂不支持动态更新
        """
        try:
            val = self.cm.get_setting(dependency_key)
            widget.setVisible(condition(val))
        except Exception as e:
            logger.error("config_binder", "bind_visible_failed", f"绑定可见性失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def _register_binding(self, key, widget, update_func):
        try:
            if key not in self._bindings:
                self._bindings[key] = []
            self._bindings[key].append((widget, update_func))
        except Exception as e:
            logger.error("config_binder", "register_binding_failed", f"注册绑定失败：{e}", exc_info=True)

    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=None, component="ConfigBinder")
    def _on_setting_changed(self, key, value):
        try:
            # 1. Update bound widgets
            if key in self._bindings:
                for widget, update_func in self._bindings[key]:
                    try:
                        # Block signals to prevent infinite loop (UI -> Config -> UI -> Config...)
                        if hasattr(widget, 'blockSignals'):
                            widget.blockSignals(True)
                            update_func(widget, value)
                            widget.blockSignals(False)
                    except Exception as e:
                        logger.error("config_binder", "widget_update_error", f"更新控件失败：{e}", exc_info=True)

            # 2. Update dependencies (Enabled/Disabled)
            if key in self._dependencies:
                for widget, condition in self._dependencies[key]:
                    try:
                        widget.setEnabled(condition(value))
                    except Exception as e:
                        logger.error("config_binder", "dependency_update_error", f"更新依赖状态失败：{e}", exc_info=True)
        except Exception as e:
            logger.error("config_binder", "setting_changed_handler_failed", f"配置变更处理器执行失败：{e}", exc_info=True)
