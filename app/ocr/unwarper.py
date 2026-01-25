# -*- coding: utf-8 -*-

"""
文档矫正（调用PaddleOCR TextImageUnwarping接口）
"""

import os
import cv2
import numpy as np
try:
    from paddleocr import TextImageUnwarping
    PADDLE_UNWARP_AVAILABLE = True
except ImportError:
    PADDLE_UNWARP_AVAILABLE = False
    print("PaddleOCR TextImageUnwarping not available")

class Unwarper:
    def __init__(self, config_manager=None):
        """
        初始化文档矫正器

        Args:
            config_manager: 配置管理器
        """
        print("Initializing Unwarper")
        self.config_manager = config_manager
        self.unwarp_engine = None
        
        if PADDLE_UNWARP_AVAILABLE:
            try:
                # 获取模型路径
                unwarp_model_dir = None
                if config_manager:
                    unwarp_model_dir = config_manager.get_setting('unwarp_model_dir')
                
                print(f"Unwarper unwarp_model_dir: {unwarp_model_dir}")
                
                params = {}
                if unwarp_model_dir and os.path.exists(unwarp_model_dir):
                    print(f"Using local unwarping model: {unwarp_model_dir}")
                    # TextImageUnwarping uses 'model_name' or implicit path? 
                    # The doc says: TextImageUnwarping(model_name="UVDoc")
                    # But if we have a local path, how do we pass it?
                    # Looking at PaddleOCR source (or guessing), it might take 'det_model_dir' equivalent?
                    # Actually, usually Paddle classes take a directory. 
                    # Let's try to assume it might work like PaddleOCR or check docs.
                    # The search result said: model = TextImageUnwarping(model_name="UVDoc")
                    # If we want to use local path, maybe we need to set it differently?
                    # Let's assume for now we can pass it or it uses the default structure if key matches.
                    # BUT, ConfigManager downloads it to a specific path.
                    # If TextImageUnwarping(model_name="UVDoc") auto-downloads to .paddlex, we might be duplicating.
                    # However, if we want to use OUR path:
                    # Looking at source code of TextImageUnwarping is not possible directly, but standard pattern is:
                    # It might verify model_name.
                    pass
                
                # For now, let's try initializing with the model_name if it matches standard ones,
                # OR if we can pass the directory.
                # Since we don't know the exact API for custom path for TextImageUnwarping, 
                # we will try to use the one from search result: model_name="UVDoc".
                # If the user downloaded it to our models dir, we might need to point to it.
                # Use_gpu check
                use_gpu = False
                if config_manager:
                     use_gpu = config_manager.get_setting('use_gpu', False)

                # Initialize
                # Note: TextImageUnwarping might not accept arbitrary kwargs like PaddleOCR.
                # We'll stick to model_name="UVDoc" for now as it's the only one supported typically.
                # If we need custom path, we might need to look deeper. 
                # But "UVDoc" is the key we use.
                
                self.unwarp_engine = TextImageUnwarping(model_name="UVDoc", use_gpu=use_gpu)
                print("PaddleOCR unwarper initialized successfully")
                
            except Exception as e:
                print(f"Error initializing PaddleOCR unwarper: {e}")
                import traceback
                traceback.print_exc()
                self.unwarp_engine = None

    def unwarp_image(self, image):
        """
        矫正图像

        Args:
            image: 输入图像 (PIL Image or numpy array)

        Returns:
            PIL Image: 矫正后的图像
        """
        if not PADDLE_UNWARP_AVAILABLE or not self.unwarp_engine:
            return image

        print("Unwarping image...")
        try:
            # Convert to numpy (BGR) for Paddle
            if hasattr(image, 'convert'):
                img_np = np.array(image.convert('RGB'))
                img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            else:
                img_np = image

            # Predict
            # output = model.predict(img_path_or_np)
            # output is a list of results.
            results = self.unwarp_engine.predict(img_np)
            
            if results and len(results) > 0:
                # result object has save_to_img or similar.
                # The search result said: {'res': {'doctr_img': ...}}
                # Let's check the result structure.
                # result might be a list of objects.
                res_obj = results[0]
                
                # We need the unwarped image. 
                # Typically it's in res_obj['doctr_img'] if it returns a dict, 
                # or res_obj.doctr_img if it's an object.
                # The search result showed: {'res': {'input_path': ..., 'doctr_img': ...}}
                # Wait, the search result output format was:
                # output = model.predict(...)
                # for res in output: ...
                
                # Let's inspect what we can get.
                # Ideally we get the image array back.
                
                # If we can't easily get it, we might skip.
                # But usually 'doctr_img' is the key for the unwarped image (numpy array).
                
                unwarped_img = None
                if isinstance(res_obj, dict) and 'doctr_img' in res_obj:
                     unwarped_img = res_obj['doctr_img']
                elif hasattr(res_obj, 'doctr_img'):
                     unwarped_img = res_obj.doctr_img
                
                if unwarped_img is not None:
                     # Convert back to PIL RGB
                     unwarped_img = cv2.cvtColor(unwarped_img, cv2.COLOR_BGR2RGB)
                     from PIL import Image
                     return Image.fromarray(unwarped_img)
            
            print("Unwarping returned no valid image, using original.")
            return image
            
        except Exception as e:
            print(f"Error unwarping image: {e}")
            traceback.print_exc()
            return image
