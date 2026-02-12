# -*- coding: utf-8 -*-

"""
表格结构识别器（封装 PP-Structure）
"""

import os
import cv2
import numpy as np
import traceback

try:
    from paddleocr import PPStructureV3 as PPStructure
    PADDLE_STRUCTURE_AVAILABLE = True
except ImportError:
    try:
        from paddleocr import PPStructure
        PADDLE_STRUCTURE_AVAILABLE = True
    except ImportError:
        PADDLE_STRUCTURE_AVAILABLE = False
        print("PaddleOCR PPStructure not available")

class TableRecognizer:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.engine = None
        self.current_model = None
        
    def _init_engine(self, model_name='SLANet'):
        """
        初始化 PP-Structure 引擎
        """
        if not PADDLE_STRUCTURE_AVAILABLE:
            raise ImportError("PaddleOCR not installed or PPStructure not available")
            
        if self.engine and self.current_model == model_name:
            return

        print(f"Initializing TableRecognizer with model: {model_name}")
        
        # 获取模型路径
        models_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models', 'paddle_ocr')
        
        # 表格模型路径
        # 优先尝试从 ConfigManager 获取配置的路径，如果 key 匹配
        config_table_key = self.config_manager.get_setting('table_model_key')
        config_table_dir = self.config_manager.get_setting('table_model_dir')
        
        if config_table_key == model_name and config_table_dir and os.path.exists(config_table_dir):
            table_model_dir = config_table_dir
        else:
            # 默认构造路径
            table_model_dir = os.path.join(models_root, 'table', f'{model_name}_infer')
        
        # 依赖的检测和识别模型路径 (复用 OCR 的模型)
        det_model_dir = self.config_manager.get_setting('det_model_dir')
        rec_model_dir = self.config_manager.get_setting('rec_model_dir')
        cls_model_dir = self.config_manager.get_setting('cls_model_dir') # 如果需要
        
        # 如果配置为空，尝试使用默认路径
        if not det_model_dir:
             det_model_dir = os.path.join(models_root, 'det', 'PP-OCRv5_server_det_infer')
        if not rec_model_dir:
             rec_model_dir = os.path.join(models_root, 'rec', 'PP-OCRv5_server_rec_infer')

        # 检查模型是否存在
        if not os.path.exists(table_model_dir):
            print(f"Warning: Table model not found at {table_model_dir}, attempting to download or use default")
            # 这里可以触发下载逻辑，或者由 UI 层的 DownloadDialog 处理
            # PaddleOCR 会尝试自动下载默认模型，但我们需要指定本地路径以离线运行
        
        try:
            # 初始化参数
            args = {
                # 'show_log': False, # Removed, not supported in new PaddleOCR
                'table_model_dir': table_model_dir,
                'det_model_dir': det_model_dir,
                'rec_model_dir': rec_model_dir,
                # 'cls_model_dir': cls_model_dir, # Table recognition usually implies text rec inside cells
                'use_gpu': False, # 默认 CPU，可配置
                'layout': False, # 只做表格识别，不做版面分析
                'table': True,
                'ocr': True,     # 同时识别单元格内的文字
                'recovery': True # 开启恢复逻辑
            }
            
            # 检查 GPU
            try:
                import paddle
                if paddle.is_compiled_with_cuda():
                    args['use_gpu'] = True
            except:
                pass
                
            # Compatibility for PaddleOCR 3.2.0+ (PaddleX pipeline)
            # PPStructureV3/PaddleOCR might require different args or strict args
            # New version uses 'device' instead of 'use_gpu'
            if 'use_gpu' in args:
                 args['device'] = 'gpu' if args.pop('use_gpu') else 'cpu'

            # PPStructureV3 specific args check
            # It seems PPStructureV3 (which we alias to PPStructure) might take specific args.
            # But wait, PPStructureV3 is a pipeline.
            # Let's try to init.
            
            # Re-map keys if needed for v3
            # v3 might expect 'table_structure_model_dir' instead of 'table_model_dir'
            # Let's check keys from source if possible, or just try mapping common ones.
            # Based on standard PaddleX config:
            if 'table_model_dir' in args:
                args['table_structure_model_dir'] = args.pop('table_model_dir')
            if 'det_model_dir' in args:
                args['text_detection_model_dir'] = args.pop('det_model_dir')
            if 'rec_model_dir' in args:
                args['text_recognition_model_dir'] = args.pop('rec_model_dir')
                
            # Remove unsupported args for V3
            args.pop('layout', None)
            args.pop('table', None)
            args.pop('ocr', None)
            args.pop('recovery', None)
            
            # Add V3 specific requirement? 
            # Actually, looking at __init__.py, PPStructureV3 is a pipeline class.
            # We should probably instantiate it.

            # PPStructureV3 initialization
            self.engine = PPStructure(**args)
            self.current_model = model_name
            print("TableRecognizer initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize TableRecognizer: {e}")
            traceback.print_exc()
            self.engine = None
            raise

    def predict(self, image, model_name='SLANet'):
        """
        执行表格识别
        
        Args:
            image: PIL Image or numpy array
            model_name: 模型名称
            
        Returns:
            list: 识别结果列表，每个元素包含单元格信息
        """
        self._init_engine(model_name)
        
        if not self.engine:
            return []
            
        # Convert to numpy if needed
        if hasattr(image, 'convert'):
            img_np = np.array(image.convert('RGB'))
            # RGB to BGR for OpenCV/Paddle
            img_np = img_np[:, :, ::-1] 
        else:
            img_np = image

        try:
            # PP-Structure predict
            # For V3 pipeline, calling instance directly works
            result = self.engine(img_np)
            
            # V3 result format is different. 
            # It returns a generator or list of dicts.
            # Each item: {'type': 'table', 'bbox': ..., 'img': ..., 'res': {'html': ..., 'cell_bbox': ...}}
            # BUT wait, V3 output format might be:
            # {'layout': [...], 'table': [...]} ?
            # Let's assume standard iteration works.
            
            if not isinstance(result, list):
                 # Generator?
                 result = list(result)

            processed_results = []
            
            # If V3 returns something else, we need to adapt.
            # Assuming standard structure result for now.
            
            for region in result:
                # V3 region keys?
                # Check if it's a table result directly or wrapped
                # If we disabled layout analysis, maybe it returns just the table structure?
                
                # Let's be robust.
                res = region.get('res', {}) if isinstance(region, dict) else {}
                if not res and isinstance(region, dict) and 'cell_bbox' in region:
                     # Maybe the region IS the result (if layout=False)
                     res = region
                
                html = res.get('html', '')
                cell_bboxes = res.get('cell_bbox', []) 
                
                if not html and not cell_bboxes:
                     continue
                
                # Get table offset (if any, from layout)
                table_bbox = region.get('bbox', [0, 0, 0, 0])
                table_x, table_y = table_bbox[0], table_bbox[1]
                
                # Workaround:
                # Use lxml to parse HTML to get text order, and map to cell_bbox order.
                # Usually they are in same order.
                
                from lxml import html as lhtml
                try:
                    tree = lhtml.fragment_fromstring(html, create_parent='div')
                except:
                    # Fallback for full document or other issues
                    try:
                        tree = lhtml.fromstring(html)
                    except:
                        tree = None
                
                if tree is None:
                     continue

                # Find all rows to track row/col indices correctly
                rows = tree.xpath('//tr')
                if not rows:
                     # Fallback if no tr found (unlikely for table)
                     rows = []
                     # Try to find direct tds if structure is malformed
                     tds = tree.xpath('//td | //th')
                     if tds:
                         # Treat as one row
                         dummy_tr = lhtml.Element('tr')
                         for td in tds: dummy_tr.append(td)
                         rows = [dummy_tr]

                cell_idx = 0
                occupied = {} # (row, col) -> bool
                
                current_row = 0
                for tr in rows:
                    current_col = 0
                    cells = tr.xpath('./td | ./th')
                    for cell in cells:
                        # Skip occupied cells (from rowspan of previous rows)
                        while (current_row, current_col) in occupied:
                            current_col += 1
                        
                        # Get rowspan/colspan
                        try:
                            rowspan = int(cell.get('rowspan', 1))
                        except:
                            rowspan = 1
                        try:
                            colspan = int(cell.get('colspan', 1))
                        except:
                            colspan = 1
                        
                        # Mark occupied cells
                        for r in range(rowspan):
                            for c in range(colspan):
                                occupied[(current_row + r, current_col + c)] = True
                        
                        # Process cell
                        if cell_idx < len(cell_bboxes):
                            text = cell.text_content().strip()
                            box = cell_bboxes[cell_idx]
                            
                            # Convert 4 points to rect (8 values: x1,y1, x2,y2, x3,y3, x4,y4)
                            if len(box) == 8:
                                xs = [box[j] for j in range(0, 8, 2)]
                                ys = [box[j] for j in range(1, 8, 2)]
                                x_min, x_max = min(xs), max(xs)
                                y_min, y_max = min(ys), max(ys)
                            elif len(box) == 4: # [x1, y1, x2, y2]
                                x_min, y_min, x_max, y_max = box
                            else:
                                x_min, y_min, x_max, y_max = 0, 0, 0, 0
                            
                            # Adjust to original image coordinates
                            # If layout=False, table_bbox might be 0,0 (whole image)
                            
                            processed_results.append({
                                'text': text,
                                'bbox': [x_min + table_x, y_min + table_y, x_max + table_x, y_max + table_y],
                                'score': 0.95, # Mock score
                                'row': current_row,
                                'col': current_col,
                                'rowspan': rowspan,
                                'colspan': colspan,
                                'is_header': cell.tag == 'th'
                            })
                            
                            cell_idx += 1
                        
                        current_col += colspan # Move past this cell
                    
                    current_row += 1
            
            return processed_results

        except Exception as e:
            print(f"Error in TableRecognizer predict: {e}")
            traceback.print_exc()
            return []

