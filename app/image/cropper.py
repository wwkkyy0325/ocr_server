# -*- coding: utf-8 -*-

"""
图像裁剪（根据检测框提取文本区域）
"""

from PIL import Image


class Cropper:
    def __init__(self):
        """
        初始化图像裁剪器
        """
        pass

    def crop_text_region(self, image, coordinates):
        """
        裁剪文本区域

        Args:
            image: 输入图像
            coordinates: 区域坐标 [x1, y1, x2, y2]

        Returns:
            裁剪后的图像
        """
        print(f"Cropping text region: {coordinates}")
        try:
            # 确保坐标是整数
            x1, y1, x2, y2 = map(int, coordinates)
            
            # 确保坐标顺序正确（左上到右下）
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)
            
            # 检查坐标是否有效
            if left < 0 or top < 0 or right <= left or bottom <= top:
                raise ValueError("Invalid coordinates: Coordinate 'lower' is less than 'upper'")
            
            # 如果图像是PIL图像
            if isinstance(image, Image.Image):
                # 确保坐标不超出图像边界
                width, height = image.size
                left = max(0, left)
                top = max(0, top)
                right = min(width, right)
                bottom = min(height, bottom)
                
                # 检查裁剪区域是否有效
                if right <= left or bottom <= top:
                    raise ValueError("Invalid crop region")
                
                # 裁剪图像
                cropped = image.crop((left, top, right, bottom))
                return cropped
            else:
                # 如果图像是numpy数组
                import numpy as np
                if isinstance(image, np.ndarray):
                    # 确保坐标不超出图像边界
                    height, width = image.shape[:2]
                    left = max(0, left)
                    top = max(0, top)
                    right = min(width, right)
                    bottom = min(height, bottom)
                    
                    # 检查裁剪区域是否有效
                    if right <= left or bottom <= top:
                        raise ValueError("Invalid crop region")
                    
                    # 裁剪图像
                    cropped = image[top:bottom, left:right]
                    return cropped
                else:
                    raise ValueError("Unsupported image type")
        except Exception as e:
            print(f"Error cropping image: {e}")
            # 返回原始图像或抛出异常
            raise

    def crop_multiple_regions(self, image, regions):
        """
        裁剪多个文本区域

        Args:
            image: 输入图像
            regions: 区域坐标列表 [(x1, y1, x2, y2), ...]

        Returns:
            裁剪后的图像区域列表
        """
        cropped_images = []
        for region in regions:
            cropped_img = self.crop_text_region(image, region)
            cropped_images.append(cropped_img)
        return cropped_images
