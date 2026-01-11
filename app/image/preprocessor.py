# -*- coding: utf-8 -*-

"""
图像预处理（调整分辨率、去噪、倾斜校正）
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import os


class Preprocessor:
    def __init__(self):
        """
        初始化预处理器
        """
        pass

    def add_border_padding(self, image, padding_size=50):
        """
        为图像添加边框padding，防止边缘文字丢失
        
        Args:
            image: 输入图像（PIL Image或numpy array）
            padding_size: 边框大小（像素）
            
        Returns:
            添加边框后的图像
        """
        # 确保输入是numpy数组
        if isinstance(image, Image.Image):
            image = np.array(image)
            
        # 添加白色边框
        padded_image = cv2.copyMakeBorder(
            image, padding_size, padding_size, padding_size, padding_size, 
            cv2.BORDER_CONSTANT, value=[255, 255, 255]  # 白色填充
        )
            
        return padded_image

    def resize_image(self, image, target_width=1280, target_height=720, use_letterbox=True):
        """
        调整图像分辨率

        Args:
            image: 输入图像
            target_width: 目标宽度
            target_height: 目标高度

        Returns:
            调整后的图像
        """
        # 确保输入是PIL Image
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
            
        # 获取原始尺寸
        original_width, original_height = image.size
        
        # 计算缩放比例
        scale_ratio = min(target_width / original_width, target_height / original_height)
        
        # 计算新尺寸
        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)
        
        # 调整图像大小
        resized_image = image.resize((new_width, new_height), Image.LANCZOS)
        
        if not use_letterbox:
            return resized_image
        
        background = Image.new('RGB', (target_width, target_height), (255, 255, 255))
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        background.paste(resized_image, (x_offset, y_offset))
        return background

    def denoise_image(self, image):
        """
        图像去噪

        Args:
            image: 输入图像

        Returns:
            去噪后的图像
        """
        # 确保输入是numpy数组
        if isinstance(image, Image.Image):
            image = np.array(image)
            
        # 使用双边滤波去噪
        denoised = cv2.bilateralFilter(image, 9, 75, 75)
        
        return denoised

    def correct_skew(self, image):
        """
        倾斜校正

        Args:
            image: 输入图像

        Returns:
            校正后的图像
        """
        # 确保输入是numpy数组
        if isinstance(image, Image.Image):
            image = np.array(image)
            
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # 边缘检测
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # 检测直线
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is not None:
            # 计算平均角度
            angles = []
            for rho, theta in lines[:, 0]:
                angles.append(theta)
            
            # 计算中位数角度
            median_angle = np.median(angles) * 180 / np.pi - 90
            
            # 应用旋转校正
            if abs(median_angle) > 0.5:  # 只有当倾斜角度足够大时才校正
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                corrected = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                return corrected
                
        return image

    def enhance_contrast(self, image, factor=1.5):
        """
        增强图像对比度

        Args:
            image: 输入图像
            factor: 对比度增强因子

        Returns:
            增强后的图像
        """
        # 确保输入是PIL Image
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
            
        enhancer = ImageEnhance.Contrast(image)
        enhanced_image = enhancer.enhance(factor)
        
        return enhanced_image

    def comprehensive_preprocess(self, image, output_dir=None, filename=None, use_padding=True):
        """
        综合预处理流程

        Args:
            image: 输入图像
            output_dir: 输出目录（可选，用于保存预处理后的图像）
            filename: 文件名（可选）
            use_padding: 是否启用边框填充

        Returns:
            预处理后的图像
        """
        print("Starting comprehensive preprocessing")
        
        current_image = image

        # 1. 添加边框padding以防止边缘文字丢失 (可选)
        if use_padding:
            current_image = self.add_border_padding(current_image, padding_size=50)
            print("Added border padding to prevent edge text loss")
        else:
            print("Skipped border padding (disabled by user)")
        
        # 2. 调整图像分辨率
        resized_image = self.resize_image(current_image, use_letterbox=use_padding)
        print("Resized image")
        
        # 3. 增强对比度
        enhanced_image = self.enhance_contrast(resized_image, factor=1.2)
        print("Enhanced contrast")
        
        # 4. 去噪
        denoised_image = self.denoise_image(enhanced_image)
        print("Denoised image")
        
        # 5. 跳过倾斜校正（用户要求移除）
        # 直接使用去噪后的图像作为最终结果
        final_image = denoised_image
        print("Skipped skew correction (disabled by user)")
        
        # 如果指定了输出目录，则保存预处理后的图像
        if output_dir and filename:
            os.makedirs(output_dir, exist_ok=True)
            preprocessed_path = os.path.join(output_dir, f"{filename}_preprocessed.jpg")
            
            # 转换为PIL Image并保存
            if isinstance(final_image, np.ndarray):
                preprocessed_image = Image.fromarray(final_image)
            else:
                preprocessed_image = final_image
                
            preprocessed_image.save(preprocessed_path, "JPEG", quality=95)
            print(f"Saved preprocessed image to: {preprocessed_path}")
        
        print("Comprehensive preprocessing completed (without skew correction)")
        return final_image
