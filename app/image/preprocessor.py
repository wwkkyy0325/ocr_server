# Path: src/app/image/preprocessor.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图像预处理（去噪、增强、倾斜校正）
"""

from PIL import Image, ImageEnhance, ImageFilter
import math

# 尝试导入OpenCV
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("OpenCV not available. Some preprocessing features will be disabled.")


class Preprocessor:
    def __init__(self):
        """
        初始化图像预处理器
        """
        # 定义标准分辨率
        self.target_dpi = 300
        self.min_size = 600
        self.max_size = 3000

    def denoise(self, image):
        """
        图像去噪

        Args:
            image: 输入图像

        Returns:
            处理后的图像
        """
        print("Denoising image")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                if isinstance(image, Image.Image):
                    open_cv_image = np.array(image)
                    # 转换RGB到BGR（如果图像是彩色的）
                    if len(open_cv_image.shape) == 3:
                        open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
                else:
                    open_cv_image = image
                
                # 应用去噪
                denoised = cv2.fastNlMeansDenoisingColored(open_cv_image, None, 10, 10, 7, 21)
                
                # 转换回PIL图像
                if len(denoised.shape) == 3:
                    denoised = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(denoised)
                return pil_image
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error denoising image: {e}")
            return image

    def enhance(self, image):
        """
        图像增强

        Args:
            image: 输入图像

        Returns:
            增强后的图像
        """
        print("Enhancing image")
        try:
            # 增强对比度
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # 增强锐度
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # 增强亮度
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.2)
            
            return image
        except Exception as e:
            print(f"Error enhancing image: {e}")
            return image

    def correct_skew(self, image):
        """
        倾斜校正 - 针对OCR优化的版本

        Args:
            image: 输入图像

        Returns:
            校正后的图像
        """
        print("Correcting image skew (OCR optimized)")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                open_cv_image = np.array(image)
                if len(open_cv_image.shape) == 3:
                    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                else:
                    gray = open_cv_image
                
                # 应用阈值处理
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # 通过形态学操作减少干扰线的影响
                # 使用较小的结构元素清理噪点
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
                
                # 检测轮廓
                contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 过滤轮廓，只保留可能是文本行的区域
                text_contours = []
                for contour in contours:
                    x, y, w, h = cv2.boundingRect(contour)
                    area = cv2.contourArea(contour)
                    
                    # 过滤条件：
                    # 1. 面积不能太小
                    # 2. 宽度要大于高度（文本行通常是水平的，宽度大于高度）
                    # 3. 宽高比要合理
                    if area > 100 and w > h and w/h > 2:
                        text_contours.append(contour)
                
                # 如果找到了可能是文本的轮廓
                if text_contours:
                    # 计算所有文本轮廓的角度
                    angles = []
                    for contour in text_contours:
                        # 获取最小外接矩形
                        rect = cv2.minAreaRect(contour)
                        angle = rect[-1]
                        
                        # 标准化角度
                        if angle < -45:
                            angle = 90 + angle
                        
                        # 只考虑较小的角度
                        if abs(angle) < 30:
                            angles.append(angle)
                    
                    # 如果有足够多的角度样本
                    if len(angles) > 2:
                        # 使用中位数作为最终角度，减少异常值影响
                        median_angle = np.median(angles)
                        print(f"Detected skew angle from {len(angles)} text regions: {median_angle}")
                        
                        # 如果角度足够大，则进行校正
                        if abs(median_angle) > 0.3:  # 降低阈值
                            rotated = self._rotate_image(open_cv_image, median_angle)
                            # 转换回PIL图像
                            if len(rotated.shape) == 3:
                                rotated = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
                            return Image.fromarray(rotated)
                
                return image
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error correcting skew: {e}")
            return image
    
    def correct_skew_old(self, image):
        """
        旧版倾斜校正（保留以备参考）

        Args:
            image: 输入图像

        Returns:
            校正后的图像
        """
        print("Correcting image skew (old method)")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                open_cv_image = np.array(image)
                if len(open_cv_image.shape) == 3:
                    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                else:
                    gray = open_cv_image
                
                # 应用阈值处理
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # 检测轮廓
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 计算最大轮廓的角度
                if contours:
                    # 选择面积适中的轮廓，而非最大轮廓
                    contour_areas = [(cv2.contourArea(c), c) for c in contours]
                    contour_areas = sorted(contour_areas, key=lambda x: x[0], reverse=True)
                    
                    # 选择前几个较大轮廓中的一个进行角度计算
                    if contour_areas:
                        selected_contour = contour_areas[0][1]  # 使用最大轮廓
                        angle = self._get_skew_angle(selected_contour)
                        print(f"Detected skew angle: {angle}")
                        
                        # 如果角度不为0，则进行校正
                        if abs(angle) > 0.5:
                            rotated = self._rotate_image(open_cv_image, angle)
                            # 转换回PIL图像
                            if len(rotated.shape) == 3:
                                rotated = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
                            return Image.fromarray(rotated)
                
                return image
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error correcting skew: {e}")
            return image

    def adjust_resolution(self, image):
        """
        调整图像分辨率：高分辨率降采样，低分辨率超分辨率

        Args:
            image: 输入图像

        Returns:
            调整分辨率后的图像
        """
        print("Adjusting image resolution")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                if isinstance(image, Image.Image):
                    open_cv_image = np.array(image)
                    if len(open_cv_image.shape) == 3:
                        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                    else:
                        gray = open_cv_image
                else:
                    if len(image.shape) == 3:
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    else:
                        gray = image
                
                height, width = gray.shape
                max_dimension = max(height, width)
                
                # 如果图像过大，进行降采样
                if max_dimension > self.max_size:
                    print(f"Downsampling image from {width}x{height}")
                    scale_factor = self.max_size / max_dimension
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)
                    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    # 转换回PIL图像
                    if len(resized.shape) == 3:
                        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    return Image.fromarray(resized) if isinstance(image, Image.Image) else resized
                
                # 如果图像过小，进行超分辨率
                elif max_dimension < self.min_size:
                    print(f"Upsampling image from {width}x{height}")
                    scale_factor = self.min_size / max_dimension
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)
                    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                    # 转换回PIL图像
                    if len(resized.shape) == 3:
                        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    return Image.fromarray(resized) if isinstance(image, Image.Image) else resized
                
                # 图像尺寸适中，无需调整
                return image
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error adjusting resolution: {e}")
            return image

    def binarize(self, image):
        """
        图像二值化

        Args:
            image: 输入图像

        Returns:
            二值化后的图像
        """
        print("Binarizing image")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                if isinstance(image, Image.Image):
                    open_cv_image = np.array(image)
                    if len(open_cv_image.shape) == 3:
                        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                    else:
                        gray = open_cv_image
                else:
                    if len(image.shape) == 3:
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    else:
                        gray = image
                
                # 应用自适应阈值处理
                binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                
                # 转换回PIL图像
                return Image.fromarray(binary)
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error binarizing image: {e}")
            return image

    def detect_edges(self, image):
        """
        边缘检测

        Args:
            image: 输入图像

        Returns:
            边缘检测后的图像
        """
        print("Detecting edges")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                if isinstance(image, Image.Image):
                    open_cv_image = np.array(image)
                    if len(open_cv_image.shape) == 3:
                        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                    else:
                        gray = open_cv_image
                else:
                    if len(image.shape) == 3:
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    else:
                        gray = image
                
                # 应用Canny边缘检测
                edges = cv2.Canny(gray, 50, 150, apertureSize=3)
                
                # 转换回PIL图像
                return Image.fromarray(edges)
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error detecting edges: {e}")
            return image

    def morphological_processing(self, image):
        """
        形态学处理

        Args:
            image: 输入图像

        Returns:
            形态学处理后的图像
        """
        print("Applying morphological processing")
        try:
            if OPENCV_AVAILABLE:
                # 将PIL图像转换为OpenCV格式
                if isinstance(image, Image.Image):
                    open_cv_image = np.array(image)
                    if len(open_cv_image.shape) == 3:
                        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
                    else:
                        gray = open_cv_image
                else:
                    if len(image.shape) == 3:
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    else:
                        gray = image
                
                # 定义结构元素
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                
                # 形态学操作：先腐蚀后膨胀
                morphed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
                
                # 转换回PIL图像
                return Image.fromarray(morphed)
            else:
                print("OpenCV not available, returning original image")
                return image
        except Exception as e:
            print(f"Error applying morphological processing: {e}")
            return image

    def comprehensive_preprocess(self, image, output_dir=None, filename=None):
        """
        综合预处理流程

        Args:
            image: 输入图像
            output_dir: 输出目录（可选）
            filename: 文件名（可选）

        Returns:
            预处理后的图像
        """
        print("Starting comprehensive preprocessing")
        original_image = image
        
        # 1. 调整分辨率
        image = self.adjust_resolution(image)
        
        # 2. 去噪（仅对大图像进行，避免小图像处理过度）
        if isinstance(image, Image.Image):
            width, height = image.size
        else:
            height, width = image.shape[:2]
            
        if max(width, height) > 1000:
            image = self.denoise(image)
        
        # 3. 倾斜校正（通过配置控制是否启用）
        use_skew_correction = False  # 默认禁用
        # 在实际应用中，这个值应该从配置管理器获取
        # 例如: use_skew_correction = config_manager.get_setting('use_skew_correction', False)
        
        if use_skew_correction:
            image = self.correct_skew(image)
        else:
            print("Skew correction disabled")
        
        # 4. 适度增强（降低增强参数）
        image = self.enhance_light(image)
        
        # 5. 如果图像尺寸过大，进行压缩
        image = self.optimize_size(image)
        
        # 如果指定了输出目录和文件名，则保存预处理后的图像
        if output_dir and filename:
            try:
                import os
                # 标准化路径分隔符
                output_dir = os.path.normpath(output_dir)
                # 确保输出目录存在
                os.makedirs(output_dir, exist_ok=True)
                # 保存预处理后的图像（使用JPEG格式以减小文件大小）
                output_path = os.path.join(output_dir, f"{filename}_preprocessed.jpg")
                if isinstance(image, Image.Image):
                    image.save(output_path, 'JPEG', quality=85, optimize=True)
                else:
                    # 如果是numpy数组，转换为PIL图像再保存
                    pil_image = Image.fromarray(image)
                    if len(image.shape) == 3 and image.shape[2] == 3:
                        pil_image = pil_image.convert('RGB')
                    pil_image.save(output_path, 'JPEG', quality=85, optimize=True)
                print(f"Preprocessed image saved to: {output_path}")
            except Exception as e:
                print(f"Error saving preprocessed image: {e}")
        
        print("Comprehensive preprocessing completed")
        return image
    
    def enhance_light(self, image):
        """
        轻度图像增强

        Args:
            image: 输入图像

        Returns:
            增强后的图像
        """
        print("Lightly enhancing image")
        try:
            # 轻度增强对比度
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # 轻度增强锐度
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)
            
            # 轻度增强亮度
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.1)
            
            return image
        except Exception as e:
            print(f"Error lightly enhancing image: {e}")
            return image
    
    def _get_skew_angle(self, contour):
        """
        计算轮廓的倾斜角度

        Args:
            contour: 轮廓点

        Returns:
            倾斜角度
        """
        if not OPENCV_AVAILABLE:
            return 0
            
        coords = cv2.minAreaRect(contour)
        angle = coords[-1]
        if angle < -45:
            angle = 90 + angle
        return angle
    
    def _rotate_image(self, image, angle):
        """
        旋转图像

        Args:
            image: 输入图像
            angle: 旋转角度

        Returns:
            旋转后的图像
        """
        if not OPENCV_AVAILABLE:
            return image
            
        # 获取图像中心
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        
        # 计算旋转矩阵
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # 执行旋转
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    
    def optimize_size(self, image):
        """
        优化图像尺寸以减小文件大小

        Args:
            image: 输入图像

        Returns:
            优化后的图像
        """
        try:
            # 获取图像尺寸
            if isinstance(image, Image.Image):
                width, height = image.size
            else:
                height, width = image.shape[:2]
            
            # 如果图像过大，进行适度缩小
            max_dimension = max(width, height)
            if max_dimension > 2000:  # 设置一个合理的最大尺寸
                scale_factor = 2000 / max_dimension
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                
                print(f"Optimizing image size from {width}x{height} to {new_width}x{new_height}")
                
                if isinstance(image, Image.Image):
                    image = image.resize((new_width, new_height), Image.LANCZOS)
                else:
                    import cv2
                    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            return image
        except Exception as e:
            print(f"Error optimizing image size: {e}")
            return image
