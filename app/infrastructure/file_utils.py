# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：封装文件系统相关操作（图像/PDF 读取、目录遍历、文本导出等）
# - 核心实现：支持"path|page=N"虚拟路径读取 PDF 指定页；统一返回 PIL Image 对象
# - 关联关系：ProcessingController/OcrEngine 在处理前通过本工具读取输入；与 ResultExporter/导出功能协同

"""
文件操作（图像/PDF 读写、结果导出为 TXT）
"""

import os
import glob
from PIL import Image
import json
import io
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()


class FileUtils:
    def __init__(self):
        """
        初始化文件工具类
        """
        pass

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_READ_001, fallback_return=0, component="FileUtils")
    def get_pdf_page_count(pdf_path):
        """
        Get number of pages in a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            int: Number of pages, or 0 if failed
        """
        try:
            if not os.path.exists(pdf_path):
                return 0
            import fitz
            doc = fitz.open(pdf_path)
            return len(doc)
        except ImportError:
            logger.error("file_utils", "pymupdf_not_installed", "PyMuPDF not installed")
            return 0
        except Exception as e:
            logger.error("file_utils", "get_pdf_page_count_error", f"Error getting PDF page count {pdf_path}: {e}")
            return 0

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_READ_001, fallback_return=None, component="FileUtils")
    def read_image(image_path):
        """
        读取图像文件 (Support virtual path "path|page=N")
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            图像数据 (PIL Image)
        """
        page_index = 0
        real_path = image_path

        # Handle virtual path
        if "|page=" in image_path:
            parts = image_path.split("|page=")
            if len(parts) == 2:
                real_path = parts[0]
                try:
                    page_index = int(parts[1]) - 1  # Convert 1-based to 0-based
                except ValueError:
                    page_index = 0

        logger.debug("file_utils", "read_image", f"Reading image: {real_path} (Page {page_index})")
        try:
            if os.path.exists(real_path):
                # Check if it is a PDF
                if real_path.lower().endswith('.pdf'):
                    try:
                        import fitz
                        doc = fitz.open(real_path)
                        if len(doc) > page_index:
                            page = doc[page_index]
                            pix = page.get_pixmap()
                            img_data = pix.tobytes("ppm")
                            image = Image.open(io.BytesIO(img_data))
                            return image
                        else:
                            logger.error("file_utils", "page_out_of_range", f"Page {page_index} out of range for {real_path} (Total: {len(doc)})")
                            return None
                    except ImportError:
                        logger.error("file_utils", "pymupdf_not_installed", "PyMuPDF not installed, cannot read PDF")
                        return None
                    except Exception as e:
                        logger.error("file_utils", "read_pdf_error", f"Error reading PDF {real_path}: {e}")
                        import traceback
                        logger.debug("file_utils", "traceback", traceback.format_exc())
                        return None

                image = Image.open(real_path)
                return image
            else:
                logger.error("file_utils", "image_not_found", f"Image file not found: {real_path}")
                return None
        except Exception as e:
            logger.error("file_utils", "read_image_error", f"Error reading image {real_path}: {e}")
            return None

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_READ_001, fallback_return=[], component="FileUtils")
    def read_pdf_images(pdf_path):
        """
        Read all pages from a PDF file as images.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of PIL Image objects
        """
        images = []
        try:
            if not os.path.exists(pdf_path):
                return []

            import fitz
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap()
                img_data = pix.tobytes("ppm")
                image = Image.open(io.BytesIO(img_data))
                images.append(image)
            return images
        except ImportError:
            logger.error("file_utils", "pymupdf_not_installed", "PyMuPDF not installed")
            return []
        except Exception as e:
            logger.error("file_utils", "read_pdf_error", f"Error reading PDF {pdf_path}: {e}")
            return []

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_WRITE_001, fallback_return=None, component="FileUtils")
    def write_text_file(file_path, content):
        """
        写入文本文件

        Args:
            file_path: 文件路径
            content: 文件内容
        """
        logger.debug("file_utils", "write_text_file", f"Writing text file: {file_path}")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 先写入临时文件，再重命名为目标文件，确保原子性
            temp_file_path = file_path + ".tmp"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # 原子性地重命名文件
            os.replace(temp_file_path, file_path)
        except Exception as e:
            logger.error("file_utils", "write_text_file_error", f"Error writing text file {file_path}: {e}")
            # 尝试删除临时文件（如果存在）
            try:
                if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass

    @staticmethod
    @handle_errors(error_code=ErrorCode.UNKNOWN_001, fallback_return=[], component="FileUtils")
    def get_image_files(directory, recursive=False):
        """
        获取目录中的所有图像文件
        
        Args:
            directory: 目录路径或单个文件路径
            recursive: 是否递归搜索子目录
            
        Returns:
            图像文件路径列表
        """
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']
        image_files = []

        # 如果传入的是文件，直接检查扩展名并返回
        if os.path.isfile(directory):
            ext = os.path.splitext(directory)[1].lower()
            if ext in image_extensions:
                return [directory]
            return []

        # 如果是目录，则搜索
        if recursive:
            for root, _, _ in os.walk(directory):
                for extension in image_extensions:
                    # glob pattern need *
                    pattern = f"*{extension}"
                    image_files.extend(glob.glob(os.path.join(root, pattern), recursive=False))
        else:
            for extension in image_extensions:
                pattern = f"*{extension}"
                image_files.extend(glob.glob(os.path.join(directory, pattern), recursive=False))

        return sorted(image_files)

    @staticmethod
    @handle_errors(error_code=ErrorCode.FILE_WRITE_001, fallback_return=None, component="FileUtils")
    def write_json_file(file_path, data):
        """
        写入 JSON 文件

        Args:
            file_path: 文件路径
            data: 要写入的数据
        """
        logger.debug("file_utils", "write_json_file", f"Writing JSON file: {file_path}")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
            # 确保所有 numpy 数据类型都转换为 Python 原生类型
            def convert_numpy_types(obj):
                if isinstance(obj, dict):
                    return {key: convert_numpy_types(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
                elif hasattr(obj, 'tolist'):  # numpy 数组
                    return obj.tolist()
                elif hasattr(obj, 'item'):  # numpy 标量类型
                    return obj.item()
                else:
                    return obj
        
            # 转换数据
            converted_data = convert_numpy_types(data)
        
            # 先写入临时文件，再重命名为目标文件，确保原子性
            temp_file_path = file_path + ".tmp"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(converted_data, f, ensure_ascii=False, indent=2)
        
            # 原子性地重命名文件
            os.replace(temp_file_path, file_path)
            logger.success("file_utils", "json_file_written", f"Successfully wrote JSON file: {file_path}")
        except Exception as e:
            logger.error("file_utils", "write_json_file_error", f"Error writing JSON file {file_path}: {e}")
            # 尝试删除临时文件（如果存在）
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass
            raise  # 重新抛出异常，让调用者知道写入失败
