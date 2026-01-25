# -*- coding: utf-8 -*-

import os
import tarfile
import zipfile
import requests
import shutil


class ModelManager:
    # 官方模型下载链接配置
    MODELS = {
        "det": {
            "PP-OCRv5_server_det": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_det_infer.tar",
                "dir_name": "PP-OCRv5_server_det_infer",
                "description": "PP-OCRv5 服务器端检测模型 (高精度)"
            },
            "ch_PP-OCRv4_det": {
                "url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar",
                "dir_name": "ch_PP-OCRv4_det_infer",
                "description": "PP-OCRv4 中文检测模型"
            },
            "ch_PP-OCRv4_server_det": {
                "url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_server_det_infer.tar",
                "dir_name": "ch_PP-OCRv4_server_det_infer",
                "description": "PP-OCRv4 服务器端检测模型"
            },
            "ch_PP-OCRv3_det": {
                "url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/chinese/ch_PP-OCRv3_det_infer.tar",
                "dir_name": "ch_PP-OCRv3_det_infer",
                "description": "PP-OCRv3 中文检测模型"
            }
        },
        "rec": {
            "PP-OCRv5_server_rec": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_rec_infer.tar",
                "dir_name": "PP-OCRv5_server_rec_infer",
                "description": "PP-OCRv5 服务器端识别模型 (高精度)"
            },
            "ch_PP-OCRv4_rec": {
                "url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar",
                "dir_name": "ch_PP-OCRv4_rec_infer",
                "description": "PP-OCRv4 中文识别模型"
            },
            "ch_PP-OCRv4_server_rec": {
                "url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_server_rec_infer.tar",
                "dir_name": "ch_PP-OCRv4_server_rec_infer",
                "description": "PP-OCRv4 服务器端识别模型"
            },
            "ch_PP-OCRv3_rec": {
                "url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/chinese/ch_PP-OCRv3_rec_infer.tar",
                "dir_name": "ch_PP-OCRv3_rec_infer",
                "description": "PP-OCRv3 中文识别模型"
            }
        },
        "cls": {
            "PP-LCNet_x1_0_textline_ori": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_textline_ori_infer.tar",
                "dir_name": "PP-LCNet_x1_0_textline_ori_infer",
                "description": "PP-LCNet 文本行方向分类模型"
            },
             "PP-LCNet_x1_0_doc_ori": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_doc_ori_infer.tar",
                "dir_name": "PP-LCNet_x1_0_doc_ori_infer",
                "description": "PP-LCNet 文档方向分类模型"
            },
            "ch_ppocr_mobile_v2.0_cls": {
                "url": "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar",
                "dir_name": "ch_ppocr_mobile_v2.0_cls_infer",
                "description": "通用方向分类模型 V2.0"
            }
        },
        "unwarp": {
            "UVDoc": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/UVDoc_infer.tar",
                "dir_name": "UVDoc_infer",
                "description": "UVDoc 文档矫正模型"
            }
        }
    }

    def __init__(self, models_root=None):
        """
        初始化模型管理器
        Args:
            models_root: 模型存放根目录，默认为项目根目录下的 models/paddle_ocr
        """
        if models_root:
            self.models_root = models_root
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.models_root = os.path.join(project_root, 'models', 'paddle_ocr')
        
        self._ensure_root_exists()

    def _ensure_root_exists(self):
        os.makedirs(self.models_root, exist_ok=True)
        for model_type in ['det', 'rec', 'cls', 'unwarp']:
            os.makedirs(os.path.join(self.models_root, model_type), exist_ok=True)

    def get_available_models(self, model_type):
        """
        获取指定类型的所有可用模型列表
        Returns:
            list: [(key, description, is_downloaded), ...]
        """
        if model_type not in self.MODELS:
            return []
            
        result = []
        for key, config in self.MODELS[model_type].items():
            model_path = os.path.join(self.models_root, model_type, config['dir_name'])
            is_downloaded = self._is_model_valid(model_path)
            result.append((key, config['description'], is_downloaded))
            
        return result

    def get_model_dir(self, model_type, model_key=None):
        """
        获取指定模型的目录路径
        Args:
            model_type: 模型类型 'det', 'rec', 'cls'
            model_key: 模型标识，如果为None则返回该类型下的第一个可用模型
        """
        type_dir = os.path.join(self.models_root, model_type)
        
        # 如果指定了 key，直接构造路径
        if model_key and model_key in self.MODELS.get(model_type, {}):
            config = self.MODELS[model_type][model_key]
            model_path = os.path.join(type_dir, config['dir_name'])
            if self._is_model_valid(model_path):
                return model_path
            return None # 指定的模型不存在或无效

        # 如果没指定 key，查找该目录下存在的任意有效模型
        if os.path.exists(type_dir):
            for item in os.listdir(type_dir):
                path = os.path.join(type_dir, item)
                if os.path.isdir(path) and self._is_model_valid(path):
                    return path
        
        return None

    def _is_model_valid(self, model_path):
        """检查模型目录是否包含必要文件"""
        if not os.path.exists(model_path):
            return False
        # PaddleOCR inference model 通常包含 inference.pdmodel 和 inference.pdiparams
        # Paddle 3.0+ 可能使用 inference.json 代替 inference.pdmodel
        
        has_params = os.path.exists(os.path.join(model_path, 'inference.pdiparams'))
        
        has_pdmodel = os.path.exists(os.path.join(model_path, 'inference.pdmodel'))
        has_json = os.path.exists(os.path.join(model_path, 'inference.json'))
        
        return has_params and (has_pdmodel or has_json)

    def download_model(self, model_type, model_key, progress_callback=None):
        """
        下载并解压指定模型
        Args:
            model_type: 模型类型
            model_key: 模型Key
            progress_callback: 进度回调 func(downloaded_bytes, total_bytes)
        """
        if model_type not in self.MODELS or model_key not in self.MODELS[model_type]:
            raise ValueError(f"Unknown model: {model_type}/{model_key}")

        config = self.MODELS[model_type][model_key]
        url = config['url']
        dir_name = config['dir_name']
        target_dir = os.path.join(self.models_root, model_type)
        
        # 临时文件路径
        filename = url.split('/')[-1]
        temp_path = os.path.join(target_dir, filename)

        print(f"Downloading {url} to {temp_path}...")
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            print("Download complete. Extracting...")
            
            # 解压
            if filename.endswith('.tar') or filename.endswith('.tar.gz'):
                with tarfile.open(temp_path, 'r:*') as tar:
                    tar.extractall(path=target_dir)
            elif filename.endswith('.zip'):
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
            
            # 清理压缩包
            os.remove(temp_path)
            print(f"Model {model_key} installed successfully to {os.path.join(target_dir, dir_name)}")
            return True

        except Exception as e:
            print(f"Failed to download/install model {model_key}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    def check_and_download_defaults(self, progress_callback=None):
        """
        检查默认模型是否存在，不存在则下载
        """
        defaults = [
            ('det', 'ch_PP-OCRv4_det'),
            ('rec', 'ch_PP-OCRv4_rec'),
            ('cls', 'ch_ppocr_mobile_v2.0_cls')
        ]
        
        results = {}
        for m_type, m_key in defaults:
            current_path = self.get_model_dir(m_type, m_key)
            if not current_path:
                print(f"Default model {m_type}/{m_key} not found. Downloading...")
                success = self.download_model(m_type, m_key, progress_callback)
                results[f"{m_type}_{m_key}"] = success
            else:
                print(f"Default model {m_type}/{m_key} exists at {current_path}")
                results[f"{m_type}_{m_key}"] = True
                
        return results
