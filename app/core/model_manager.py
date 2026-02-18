# -*- coding: utf-8 -*-

import os
import tarfile
import zipfile
import requests
import shutil


from app.core.env_manager import EnvManager

class ModelManager:
    # 官方模型下载链接配置
    MODELS = {
        "det": {
            "PP-OCRv5_server_det": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_det_infer.tar",
                "dir_name": "PP-OCRv5_server_det_infer",
                "description": "PP-OCRv5 服务器端检测模型 (高精度)",
                "size": "84.3 MB"
            },
            "PP-OCRv5_mobile_det": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_mobile_det_infer.tar",
                "dir_name": "PP-OCRv5_mobile_det_infer",
                "description": "PP-OCRv5 移动端检测模型 (超轻量)",
                "size": "4.7 MB"
            }
        },
        "rec": {
            "PP-OCRv5_server_rec": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_rec_infer.tar",
                "dir_name": "PP-OCRv5_server_rec_infer",
                "description": "PP-OCRv5 服务器端识别模型 (高精度)",
                "size": "214.2 MB"
            },
            "PP-OCRv5_mobile_rec": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_mobile_rec_infer.tar",
                "dir_name": "PP-OCRv5_mobile_rec_infer",
                "description": "PP-OCRv5 移动端识别模型 (超轻量)",
                "size": "16.1 MB"
            }
        },
        "cls": {
            "PP-LCNet_x1_0_textline_ori": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_textline_ori_infer.tar",
                "dir_name": "PP-LCNet_x1_0_textline_ori_infer",
                "description": "PP-LCNet 文本行方向分类模型",
                "size": "7.3 MB"
            },
             "PP-LCNet_x1_0_doc_ori": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_doc_ori_infer.tar",
                "dir_name": "PP-LCNet_x1_0_doc_ori_infer",
                "description": "PP-LCNet 文档方向分类模型",
                "size": "7.3 MB"
            }
        },
        "unwarp": {
            "UVDoc": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/UVDoc_infer.tar",
                "dir_name": "UVDoc_infer",
                "description": "UVDoc 文档矫正模型",
                "size": "30.4 MB"
            }
        },
        "table": {
            "SLANet": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/SLANet_infer.tar",
                "dir_name": "SLANet_infer",
                "description": "SLANet 表格结构识别模型 (中文)",
                "size": "9.6 MB"
            },
            "SLANet_en": {
                "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/SLANet_en_infer.tar",
                "dir_name": "SLANet_en_infer",
                "description": "SLANet 表格结构识别模型 (英文)",
                "size": "9.6 MB"
            }
        }
    }

    def __init__(self, models_root=None):
        if models_root:
            self.models_root = models_root
            self.paddlex_official_root = models_root
        else:
            paddlex_home = os.environ.get("PADDLEX_HOME")
            if paddlex_home:
                base_dir = paddlex_home
            else:
                home_dir = os.path.expanduser("~")
                base_dir = os.path.join(home_dir, ".paddlex")
            self.paddlex_official_root = os.path.join(base_dir, "official_models")
            self.models_root = self.paddlex_official_root

        self._ensure_root_exists()

    def _ensure_root_exists(self):
        os.makedirs(self.models_root, exist_ok=True)
        for model_type in ['det', 'rec', 'cls', 'unwarp', 'table']:
            os.makedirs(os.path.join(self.models_root, model_type), exist_ok=True)

    def get_available_models(self, model_type):
        """
        获取指定类型的所有可用模型列表
        Returns:
            list: [(key, description, is_downloaded, size), ...]
        """
        if model_type not in self.MODELS:
            return []
            
        result = []
        for key, config in self.MODELS[model_type].items():
            dir_name = config['dir_name']

            candidates = []
            candidates.append(os.path.join(self.models_root, model_type, dir_name))
            candidates.append(os.path.join(self.models_root, dir_name))
            candidates.append(os.path.join(self.paddlex_official_root, dir_name))
            candidates.append(os.path.join(self.paddlex_official_root, key))

            is_downloaded = any(self._is_model_valid(p) for p in candidates)
            size = config.get('size', 'Unknown')
            result.append((key, config['description'], is_downloaded, size))

        return result

    def get_model_dir(self, model_type, model_key=None):
        """
        获取指定模型的目录路径
        Args:
            model_type: 模型类型 'det', 'rec', 'cls'
            model_key: 模型标识，如果为None则返回该类型下的第一个可用模型
        """
        type_dir = os.path.join(self.models_root, model_type)

        def resolve_path_for_key(m_key):
            if m_key not in self.MODELS.get(model_type, {}):
                return None
            cfg = self.MODELS[model_type][m_key]
            dir_name = cfg['dir_name']

            candidates = []
            candidates.append(os.path.join(self.models_root, model_type, dir_name))
            candidates.append(os.path.join(self.models_root, dir_name))
            candidates.append(os.path.join(self.paddlex_official_root, dir_name))
            candidates.append(os.path.join(self.paddlex_official_root, m_key))

            for p in candidates:
                if self._is_model_valid(p):
                    return p
            return None

        if model_key:
            return resolve_path_for_key(model_key)

        if os.path.exists(type_dir):
            for item in os.listdir(type_dir):
                path = os.path.join(type_dir, item)
                if os.path.isdir(path) and self._is_model_valid(path):
                    return path

        for m_key in self.MODELS.get(model_type, {}).keys():
            p = resolve_path_for_key(m_key)
            if p:
                return p

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

        existing_dir = os.path.join(target_dir, dir_name)
        if self._is_model_valid(existing_dir):
            print(f"Model {model_key} already exists at {existing_dir}, skip downloading.")
            return True
        
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
        根据环境自动选择模型 (GPU -> Server, CPU -> Mobile)
        """
        # Check environment
        paddle_status = EnvManager.get_paddle_status()
        is_gpu = paddle_status.get('gpu_support', False)
        
        if is_gpu:
            det_key = 'PP-OCRv5_server_det'
            rec_key = 'PP-OCRv5_server_rec'
            print("Auto-selecting Server models for default download (GPU detected)")
        else:
            det_key = 'PP-OCRv5_mobile_det'
            rec_key = 'PP-OCRv5_mobile_rec'
            print("Auto-selecting Mobile models for default download (CPU detected)")

        defaults = [
            ('det', det_key),
            ('rec', rec_key),
            ('cls', 'PP-LCNet_x1_0_textline_ori')
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
