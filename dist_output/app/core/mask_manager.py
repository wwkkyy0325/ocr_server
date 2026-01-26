# -*- coding: utf-8 -*-

"""
蒙版管理器（管理蒙版列表和图像绑定）
"""

import json
import os
from typing import Dict, List, Optional

class MaskManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self.config_path = os.path.join(project_root, 'masks.json')
        self.masks: Dict[str, List[float]] = {}
        self.image_bindings: Dict[str, str] = {}
        self.load_masks()

    def load_masks(self):
        """加载蒙版配置"""
        if os.path.exists(self.config_path):
            try:
                if os.path.getsize(self.config_path) == 0:
                    self.masks = {}
                    self.image_bindings = {}
                    self.save_masks()
                    return
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.masks = data.get('masks', {})
                    self.image_bindings = data.get('image_bindings', {})
                    for name, value in list(self.masks.items()):
                        if isinstance(value, list) and len(value) == 4 and isinstance(value[0], (int, float)):
                            self.masks[name] = [{'rect': value, 'label': 1, 'color': (255, 0, 0)}]
            except Exception as e:
                print(f"Error loading masks: {e}")
                self.masks = {}
                self.image_bindings = {}
                try:
                    self.save_masks()
                except Exception:
                    pass
        else:
            self.masks = {}
            self.image_bindings = {}
            self.save_masks()

    def save_masks(self):
        """保存蒙版配置"""
        data = {
            'masks': self.masks,
            'image_bindings': self.image_bindings
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving masks: {e}")

    def add_mask(self, name: str, coords: List[float]):
        """添加或更新蒙版"""
        self.masks[name] = coords
        self.save_masks()

    def delete_mask(self, name: str):
        """删除蒙版"""
        if name in self.masks:
            del self.masks[name]
            # 删除相关的绑定
            self.image_bindings = {k: v for k, v in self.image_bindings.items() if v != name}
            self.save_masks()

    def rename_mask(self, old_name: str, new_name: str):
        """重命名蒙版"""
        if old_name in self.masks:
            self.masks[new_name] = self.masks.pop(old_name)
            # 更新绑定
            for img, mask in self.image_bindings.items():
                if mask == old_name:
                    self.image_bindings[img] = new_name
            self.save_masks()

    def get_mask(self, name: str) -> Optional[List]:
        """获取蒙版数据"""
        return self.masks.get(name)

    def get_all_mask_names(self) -> List[str]:
        """获取所有蒙版名称"""
        return list(self.masks.keys())

    def bind_mask_to_image(self, image_name: str, mask_name: str):
        """绑定蒙版到图像"""
        if mask_name in self.masks:
            self.image_bindings[image_name] = mask_name
            self.save_masks()

    def unbind_image(self, image_name: str):
        """解除图像绑定"""
        if image_name in self.image_bindings:
            del self.image_bindings[image_name]
            self.save_masks()

    def get_bound_mask(self, image_name: str) -> Optional[str]:
        """获取图像绑定的蒙版名称"""
        return self.image_bindings.get(image_name)

    def export_masks(self, file_path: str):
        """导出蒙版配置"""
        data = {
            'masks': self.masks,
            'image_bindings': self.image_bindings
        }
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error exporting masks: {e}")

    def import_masks(self, file_path: str):
        """导入蒙版配置"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    new_masks = data.get('masks', {})
                    new_bindings = data.get('image_bindings', {})
                    # 合并或覆盖
                    self.masks.update(new_masks)
                    self.image_bindings.update(new_bindings)
                    self.save_masks()
            except Exception as e:
                print(f"Error importing masks: {e}")
