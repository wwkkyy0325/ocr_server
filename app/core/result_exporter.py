import os
import json
from datetime import datetime
from app.utils.file_utils import FileUtils
from app.core.record_manager import RecordManager

class ResultExporter:
    """
    负责将 OCR 识别结果导出到文件并更新处理记录
    """
    def __init__(self, output_dir_base, file_utils=None, record_manager=None):
        self.output_dir_base = output_dir_base
        self.file_utils = file_utils or FileUtils()
        self.record_manager = record_manager or RecordManager.get_instance()

    def get_output_paths(self, image_path, filename=None):
        """
        计算输出路径
        Args:
            image_path: 原始图像路径
            filename: 可选，指定文件名（不含扩展名），若不提供则使用 image_path 的文件名
        Returns:
            (parent_output_dir, txt_path, json_path)
        """
        if filename is None:
            filename = os.path.basename(image_path)
            
        # 处理 PDF 页面等虚拟路径 (假设已在调用前处理好，这里仅作为安全检查)
        # 如果是 "xxx.pdf::page_1"，这里需要外部处理好 filename 为 "xxx_page_1.jpg" 或类似安全格式
        safe_filename = filename.replace(':', '_')
        base_name = os.path.splitext(safe_filename)[0]

        # 集中化目录逻辑：data/outputs/<parent_dir_name>/
        parent_dir_name = os.path.basename(os.path.dirname(image_path))
        current_output_dir = os.path.join(self.output_dir_base, parent_dir_name)
        
        json_output_dir = os.path.join(current_output_dir, "json")
        txt_output_dir = os.path.join(current_output_dir, "txt")
        
        json_path = os.path.join(json_output_dir, f"{base_name}.json")
        txt_path = os.path.join(txt_output_dir, f"{base_name}_result.txt")
        
        return current_output_dir, txt_path, json_path

    def ensure_output_dirs(self, current_output_dir):
        """确保输出目录存在"""
        os.makedirs(os.path.join(current_output_dir, "json"), exist_ok=True)
        os.makedirs(os.path.join(current_output_dir, "txt"), exist_ok=True)

    def save_result(self, image_path, full_text, result_data, filename=None):
        """
        保存结果到文件并更新记录
        """
        current_output_dir, txt_path, json_path = self.get_output_paths(image_path, filename)
        self.ensure_output_dirs(current_output_dir)
        
        # 1. 保存 TXT
        try:
            self.file_utils.write_text_file(txt_path, full_text)
        except Exception as e:
            print(f"Error writing TXT file: {e}")
            
        # 2. 保存 JSON
        try:
            # 确保 result_data 是字典
            if isinstance(result_data, list):
                result_data = {'regions': result_data}
            
            # 补充元数据
            final_data = result_data.copy() if result_data else {}
            final_data.update({
                'full_text': full_text,
                'image_path': image_path,
                'filename': os.path.basename(image_path),
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            })
            
            self.file_utils.write_json_file(json_path, final_data)
            
            # 3. 更新数据库记录
            self.record_manager.add_record(image_path, output_path=json_path)
            
            return final_data
            
        except Exception as e:
            print(f"Error saving JSON result: {e}")
            return None
