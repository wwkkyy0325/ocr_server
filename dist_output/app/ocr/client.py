# -*- coding: utf-8 -*-

import requests
import base64
import os
import json
import logging

logger = logging.getLogger(__name__)

class OcrClient:
    def __init__(self, base_url, timeout=30):
        """
        Initialize OCR Client
        
        Args:
            base_url: Base URL of the OCR server (e.g. http://localhost:8082)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
    def health_check(self):
        """Check server health"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def predict(self, image_path, options=None):
        """
        Send image to OCR server for processing
        
        Args:
            image_path: Path to the image file
            options: Processing options
            
        Returns:
            dict: Processing result
        """
        url = f"{self.base_url}/ocr/predict"
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
                b64_data = base64.b64encode(img_bytes).decode('utf-8')
                
            payload = {
                "image_base64": b64_data,
                "options": options or {}
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            resp_json = response.json()
            if resp_json.get('status') == 'success':
                return resp_json.get('result')
            else:
                raise RuntimeError(f"Server error: {resp_json.get('error')}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"OCR Request failed: {e}")
            raise RuntimeError(f"OCR Network Error: {e}")
