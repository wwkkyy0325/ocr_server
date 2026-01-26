# -*- coding: utf-8 -*-

"""
格式转换（如PDF转图片、灰度化）
"""

import os
from PIL import Image
import io

# 尝试导入PyMuPDF (fitz)
try:
    import fitz  # PyMuPDF
    PymuPDF_AVAILABLE = True
except ImportError:
    PymuPDF_AVAILABLE = False
    print("PyMuPDF (fitz) not available. PDF conversion will be disabled.")


class Converter:
    def __init__(self):
        """
        初始化格式转换器
        """
        pass

    def pdf_to_image(self, pdf_path, dpi=200):
        """
        PDF转图片

        Args:
            pdf_path: PDF文件路径
            dpi: 转换分辨率

        Returns:
            转换后的图像列表
        """
        print(f"Converting PDF to images: {pdf_path}")
        images = []
        
        if not PymuPDF_AVAILABLE:
            print("PDF conversion is disabled because PyMuPDF is not available.")
            return images
            
        try:
            # 打开PDF文件
            pdf_document = fitz.open(pdf_path)
            
            # 遍历每一页
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # 设置缩放因子
                zoom = dpi / 72  # 72是默认DPI
                mat = fitz.Matrix(zoom, zoom)
                
                # 渲染页面为图像
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为PIL图像
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
                
            pdf_document.close()
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
            
        return images

    def to_grayscale(self, image):
        """
        转换为灰度图

        Args:
            image: 彩色图像

        Returns:
            灰度图像
        """
        print("Converting image to grayscale")
        try:
            if image.mode != 'L':
                return image.convert('L')
            return image
        except Exception as e:
            print(f"Error converting to grayscale: {e}")
            return image
            
    def resize_image(self, image, max_size=(1920, 1080)):
        """
        调整图像大小

        Args:
            image: 输入图像
            max_size: 最大尺寸 (width, height)

        Returns:
            调整后的图像
        """
        print(f"Resizing image to max size: {max_size}")
        try:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            return image
        except Exception as e:
            print(f"Error resizing image: {e}")
            return image
