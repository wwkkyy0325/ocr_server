
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

try:
    print("Initializing Detector...")
    from app.ocr.detector import Detector
    
    # Mock config manager
    class MockConfig:
        def get_setting(self, key, default=None):
            # Mock return values for keys
            if key == 'use_gpu':
                # If checking config, return None so it uses the default provided in get_setting call
                return default
            return default
            
    detector = Detector(config_manager=MockConfig())
    print("Detector initialized successfully.")
    
    # Verify use_gpu
    if detector.ocr_engine:
        print(f"OCR Engine use_gpu: {getattr(detector.ocr_engine, 'use_gpu', 'Unknown')}")
    
except Exception as e:
    print(f"Error initializing detector: {e}")
    import traceback
    traceback.print_exc()
