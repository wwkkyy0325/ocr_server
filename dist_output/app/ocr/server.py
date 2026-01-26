# -*- coding: utf-8 -*-

import sys
import os
import base64
import io
import json
import logging
from flask import Flask, request, jsonify
from PIL import Image

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.ocr.engine import OcrEngine
from app.core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app(config_manager=None):
    app = Flask(__name__)
    
    # Initialize OCR Engine
    logger.info("Initializing OCR Engine...")
    ocr_engine = OcrEngine(config_manager)
    logger.info("OCR Engine initialized")

    @app.route('/', methods=['GET'])
    def index():
        return jsonify({
            "service": "OCR Server",
            "status": "running",
            "endpoints": {
                "health_check": "GET /health",
                "predict": "POST /ocr/predict"
            }
        })

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "ok", "service": "ocr-server"})

    @app.route('/ocr/predict', methods=['POST'])
    def predict():
        try:
            data = request.json
            if not data:
                return jsonify({"error": "No data provided"}), 400

            image = None
            
            # 1. Try Base64
            if 'image_base64' in data and data['image_base64']:
                try:
                    image_data = base64.b64decode(data['image_base64'])
                    image = Image.open(io.BytesIO(image_data))
                except Exception as e:
                    return jsonify({"error": f"Invalid base64 image: {str(e)}"}), 400
            
            # 2. Try Local Path (only if server has access)
            elif 'image_path' in data and data['image_path']:
                image_path = data['image_path']
                if os.path.exists(image_path):
                    try:
                        image = Image.open(image_path)
                    except Exception as e:
                        return jsonify({"error": f"Failed to open image path: {str(e)}"}), 400
                else:
                    return jsonify({"error": "Image path does not exist on server"}), 404
            
            if image is None:
                return jsonify({"error": "No image provided (image_base64 or image_path required)"}), 400

            # Get options
            options = data.get('options', {})
            
            # Process
            result = ocr_engine.process_image(image, options)
            
            return jsonify({
                "status": "success",
                "result": result
            })

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    return app

def run_server(host='0.0.0.0', port=8082):
    config_manager = ConfigManager()
    config_manager.load_config()
    app = create_app(config_manager)
    app.run(host=host, port=port, threaded=True)

if __name__ == '__main__':
    run_server()
