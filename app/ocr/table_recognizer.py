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

        # 优先使用 Paddle 默认模型路径，仅在配置中明确指定且路径存在时才传入自定义目录
        table_model_dir = None
        det_model_dir = None
        rec_model_dir = None

        # 表格模型路径（可选，当前不主动注入到 PPStructure，交由管线自行管理）
        config_table_key = self.config_manager.get_setting('table_model_key')
        config_table_dir = self.config_manager.get_setting('table_model_dir')
        if config_table_key == model_name and config_table_dir and os.path.exists(config_table_dir):
            table_model_dir = config_table_dir

        try:
            # 初始化参数：默认只传 device，依赖 Paddle 自己的模型下载与路径管理
            args = {}

            # 检查 GPU，设置 device
            try:
                import paddle
                use_gpu = paddle.is_compiled_with_cuda()
            except Exception:
                use_gpu = False

            args['device'] = 'gpu' if use_gpu else 'cpu'

            # 仅设置 device，其余模型选择和路径交由 PPStructure 管线内部管理
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
            enable_advanced = False
            if self.config_manager:
                enable_advanced = bool(self.config_manager.get_setting('enable_advanced_doc', False))

            result = self.engine.predict(
                input=img_np,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_seal_recognition=False,
                use_table_recognition=True,
                use_formula_recognition=enable_advanced,
                use_chart_recognition=enable_advanced,
                use_region_detection=enable_advanced
            )

            if not isinstance(result, list):
                result = list(result)

            print(f"DEBUG: TableRecognizer.raw_result_len={len(result)}")

            processed_results = []

            for idx, item in enumerate(result):
                region_dict = item if isinstance(item, dict) else None

                if region_dict is None:
                    region_dict = getattr(item, "res", None)

                if not isinstance(region_dict, dict):
                    print(f"DEBUG: TableRecognizer item[{idx}] is not dict, type={type(item)}")
                    continue

                # Debug keys of top-level region_dict (avoid huge arrays)
                if idx == 0:
                    safe_keys = [k for k in region_dict.keys() if k not in ("input_img", "dt_polys", "rec_text")]
                    print(f"DEBUG: TableRecognizer region_dict keys: {safe_keys}")

                table_entries = []

                # Case 1: PPStructure 新格式：table_res_list 是表格结果列表
                if "table_res_list" in region_dict and isinstance(region_dict["table_res_list"], list):
                    table_entries = region_dict["table_res_list"]

                # Case 2: 旧格式：region_dict["table_res"] 是列表
                elif "table_res" in region_dict and isinstance(region_dict["table_res"], list):
                    table_entries = region_dict["table_res"]

                # Case 3: region_dict["res"] is a list of elements, some of which are tables
                elif isinstance(region_dict.get("res"), list):
                    for sub in region_dict["res"]:
                        sub_res = sub.get("res", sub) if isinstance(sub, dict) else {}
                        if isinstance(sub_res, dict) and ("html" in sub_res or "cell_bbox" in sub_res):
                            table_entries.append(sub)

                # Case 4: region_dict["res"] itself是一个包含 html/cell_bbox 的 dict
                elif isinstance(region_dict.get("res"), dict):
                    sub_res = region_dict["res"]
                    if "html" in sub_res or "cell_bbox" in sub_res:
                        table_entries.append(region_dict)

                # Case 5: 直接用 region_dict（旧格式兜底）
                else:
                    table_entries = [region_dict]

                if idx == 0 and table_entries:
                    first_region = table_entries[0]
                    if isinstance(first_region, dict):
                        print(
                            "DEBUG: TableRecognizer first table entry keys:",
                            [k for k in first_region.keys() if k not in ("dt_polys", "rec_text", "input_img")],
                        )
                        inner_res = first_region.get("res", first_region)
                        if isinstance(inner_res, dict):
                            print(
                                "DEBUG: TableRecognizer first table entry res keys:",
                                [k for k in inner_res.keys() if k not in ("dt_polys", "rec_text", "input_img")],
                            )

                for region in table_entries:
                    res = region.get("res", region) if isinstance(region, dict) else {}

                    # 兼容新旧字段命名：
                    # - 旧版：html + cell_bbox
                    # - 新版：pred_html + cell_box_list
                    html = res.get("html") or res.get("pred_html", "")
                    cell_bboxes = res.get("cell_bbox") or res.get("cell_box_list", [])

                    if not html and not cell_bboxes:
                        continue

                    table_bbox = region.get("bbox", [0, 0, 0, 0])
                    table_x, table_y = table_bbox[0], table_bbox[1]

                    from lxml import html as lhtml
                    try:
                        tree = lhtml.fragment_fromstring(html, create_parent="div")
                    except Exception:
                        try:
                            tree = lhtml.fromstring(html)
                        except Exception:
                            tree = None

                    if tree is None:
                        continue

                    rows = tree.xpath("//tr")
                    if not rows:
                        rows = []
                        tds = tree.xpath("//td | //th")
                        if tds:
                            dummy_tr = lhtml.Element("tr")
                            for td in tds:
                                dummy_tr.append(td)
                            rows = [dummy_tr]

                    cell_idx = 0
                    occupied = {}

                    current_row = 0
                    for tr in rows:
                        current_col = 0
                        cells = tr.xpath("./td | ./th")
                        for cell in cells:
                            while (current_row, current_col) in occupied:
                                current_col += 1

                            try:
                                rowspan = int(cell.get("rowspan", 1))
                            except Exception:
                                rowspan = 1
                            try:
                                colspan = int(cell.get("colspan", 1))
                            except Exception:
                                colspan = 1

                            for r in range(rowspan):
                                for c in range(colspan):
                                    occupied[(current_row + r, current_col + c)] = True

                            if cell_idx < len(cell_bboxes):
                                text = cell.text_content().strip()
                                box = cell_bboxes[cell_idx]

                                if len(box) == 8:
                                    xs = [box[j] for j in range(0, 8, 2)]
                                    ys = [box[j] for j in range(1, 8, 2)]
                                    x_min, x_max = min(xs), max(xs)
                                    y_min, y_max = min(ys), max(ys)
                                elif len(box) == 4:
                                    x_min, y_min, x_max, y_max = box
                                else:
                                    x_min, y_min, x_max, y_max = 0, 0, 0, 0

                                processed_results.append({
                                    "text": text,
                                    "bbox": [
                                        x_min + table_x,
                                        y_min + table_y,
                                        x_max + table_x,
                                        y_max + table_y,
                                    ],
                                    "score": 0.95,
                                    "row": current_row,
                                    "col": current_col,
                                    "rowspan": rowspan,
                                    "colspan": colspan,
                                    "is_header": cell.tag == "th",
                                })

                                cell_idx += 1

                            current_col += colspan

                        current_row += 1

            print(f"DEBUG: TableRecognizer.processed_cells={len(processed_results)}")
            return processed_results

        except Exception as e:
            print(f"Error in TableRecognizer predict: {e}")
            traceback.print_exc()
            return []
