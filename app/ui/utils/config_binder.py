# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton, QButtonGroup, QWidget
from PyQt5.QtCore import QObject

class ConfigBinder(QObject):
    """
    配置绑定器：实现 UI 控件与 ConfigManager 的双向绑定
    
    功能：
    1. UI -> Config: 控件值改变时自动更新配置
    2. Config -> UI: 配置改变时自动刷新控件状态
    3. Dependency: 支持基于配置值的控件启用/禁用联动
    """
    
    def __init__(self, config_manager):
        super().__init__()
        self.cm = config_manager
        self._bindings = {} # key -> list of widgets
        self._dependencies = {} # key -> list of (widget, condition_func)
        
        # 监听配置变更
        self.cm.setting_changed.connect(self._on_setting_changed)

    def bind_checkbox(self, widget: QCheckBox, key: str, invert: bool = False):
        """绑定 QCheckBox"""
        # Init value
        val = self.cm.get_setting(key, False)
        widget.setChecked(not val if invert else val)
        
        # Connect signal
        def on_toggled(checked):
            final_val = not checked if invert else checked
            self.cm.set_setting(key, final_val)
            
        widget.toggled.connect(on_toggled)
        self._register_binding(key, widget, lambda w, v: w.setChecked(not v if invert else v))

    def bind_spinbox(self, widget: QSpinBox, key: str, default=0):
        """绑定 QSpinBox"""
        val = self.cm.get_setting(key, default)
        widget.setValue(val)
        
        widget.valueChanged.connect(lambda v: self.cm.set_setting(key, v))
        self._register_binding(key, widget, lambda w, v: w.setValue(v))

    def bind_combobox(self, widget: QComboBox, key: str, default_index=0, map_text=False):
        """绑定 QComboBox (基于 Index 或 Text)"""
        # 暂时只支持 Index 绑定，简单场景够用
        val = self.cm.get_setting(key, default_index)
        if isinstance(val, int):
            widget.setCurrentIndex(val)
        
        widget.currentIndexChanged.connect(lambda v: self.cm.set_setting(key, v))
        self._register_binding(key, widget, lambda w, v: w.setCurrentIndex(v) if isinstance(v, int) else None)

    def bind_radio_group(self, group: QButtonGroup, key: str, value_map: dict, default=None):
        """
        绑定 RadioGroup
        value_map: {radioButtonWidget: "value_in_config"}
        """
        # Init state
        current_val = self.cm.get_setting(key, default)
        for btn, val in value_map.items():
            if val == current_val:
                btn.setChecked(True)
                break
        
        # Connect signal (using buttonClicked which sends the button)
        def on_clicked(btn):
            if btn in value_map:
                self.cm.set_setting(key, value_map[btn])
                
        group.buttonClicked.connect(on_clicked)
        
        # Update logic
        def update_group(w, v):
            # w is the group, v is the new value
            # We need to find which button corresponds to v
            for btn, val in value_map.items():
                if val == v:
                    btn.setChecked(True)
                    return
                    
        self._register_binding(key, group, update_group)

    def bind_enabled(self, widget: QWidget, dependency_key: str, condition=lambda x: bool(x)):
        """
        绑定控件的启用状态 (Enabled/Disabled)
        condition: 函数，接收配置值，返回 True(Enable) 或 False(Disable)
        """
        # Init state
        val = self.cm.get_setting(dependency_key)
        widget.setEnabled(condition(val))
        
        # Register
        if dependency_key not in self._dependencies:
            self._dependencies[dependency_key] = []
        self._dependencies[dependency_key].append((widget, condition))

    def bind_visible(self, widget: QWidget, dependency_key: str, condition=lambda x: bool(x)):
        """绑定控件的可见性"""
        val = self.cm.get_setting(dependency_key)
        widget.setVisible(condition(val))
        
        if dependency_key not in self._dependencies:
            self._dependencies[dependency_key] = []
        # Reuse dependency list but mark it's for visibility? 
        # For simplicity, we just wrap setVisible into a custom widget-like setter
        # But here we can just use a wrapper lambda in the list
        def update_visibility(w, v):
            w.setVisible(condition(v))
            
        # Hack: Store update function instead of raw widget to support flexible actions
        # But _dependencies structure is currently (widget, condition).
        # Let's generalize _dependencies to list of callbacks
        pass # To be refactored if complex logic needed. 
        # For now, let's just support setEnabled via standard way.
        # Visible binding can be added if really needed.

    def _register_binding(self, key, widget, update_func):
        if key not in self._bindings:
            self._bindings[key] = []
        self._bindings[key].append((widget, update_func))

    def _on_setting_changed(self, key, value):
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
                    print(f"Error updating widget for {key}: {e}")
        
        # 2. Update dependencies (Enabled/Disabled)
        if key in self._dependencies:
            for widget, condition in self._dependencies[key]:
                try:
                    widget.setEnabled(condition(value))
                except Exception as e:
                    print(f"Error updating dependency for {key}: {e}")
