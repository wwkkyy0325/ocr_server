# -*- coding: utf-8 -*-

"""
统一OCR引擎 - 将文本检测和文本识别功能整合为单一引擎
支持server和mobile两种预设配置，避免模型重复加载造成的资源浪费
"""

import os
try:
    import paddleocr
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    PADDLE_OCR_AVAILABLE = False
    print("PaddleOCR not available, using mock implementation")

from app.utils.ocr_utils import sort_ocr_regions


class UnifiedOCREngine:
    """
    统一OCR引擎，整合文本检测和识别功能
    支持预设配置：server（高精度）和mobile（轻量级）
    """
    
    # 预设配置
    PRESETS = {
        'server': {
            'name': 'GPU 高精度模式 (Server Models)',
            'det_model_key': 'PP-OCRv5_server_det',
            'rec_model_key': 'PP-OCRv5_server_rec',
            'description': '适用于 GPU 环境，高精度但资源消耗较大'
        },
        'mobile': {
            'name': 'CPU 均衡模式 (Mobile Models)', 
            'det_model_key': 'PP-OCRv5_mobile_det',
            'rec_model_key': 'PP-OCRv5_mobile_rec',
            'description': '适用于 CPU 环境，轻量级且内存友好'
        },
        # 🔥 新增：AI 表格识别专用预设（不加载 det/rec 模型，由 PP-Structure 自己处理）
        'ai_table': {
            'name': 'AI 表格结构识别 (PP-Structure)',
            'det_model_key': None,  # 不需要，PP-Structure 有自己的检测模型
            'rec_model_key': None,  # 不需要，PP-Structure 有自己的识别模型
            'description': '基于 PP-Structure 的完整表格识别系统，包含结构分析和 OCR'
        }
    }
    
    # AI 表格识别专用模式（独立完整的 OCR 系统）
    AI_TABLE_MODE = True
    
    def __init__(self, config_manager=None, preset='mobile'):
        """
        初始化统一OCR引擎
        
        Args:
            config_manager: 配置管理器
            preset: 预设配置 ('server' 或 'mobile')
        """
        print(f"Initializing Unified OCR Engine with preset: {preset}")
        self.config_manager = config_manager
        self.current_preset = preset
        self.ocr_engine = None
        self._initialize_engine()
    
    def _get_model_name_from_dir(self, dir_path):
        """
        从inference.yml或目录名提取模型名称
        """
        if not dir_path: 
            return None
        # 尝试读取inference.yml
        yml_path = os.path.join(dir_path, 'inference.yml')
        if os.path.exists(yml_path):
            try:
                with open(yml_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if 'model_name:' in line:
                            return line.split('model_name:')[1].strip()
            except:
                pass
        # 回退到目录名
        name = os.path.basename(dir_path)
        if name.endswith('_infer'):
            name = name[:-6]
        return name
    
    def _initialize_engine(self):
        """
        根据当前预设初始化 OCR 引擎
        """
        if not PADDLE_OCR_AVAILABLE:
            print("PaddleOCR not available, using mock implementation")
            return
                    
        try:
            # AI 表格识别模式：使用独立的完整 OCR 系统
            if self.current_preset == 'ai_table':
                print("Initializing AI Table Recognition (PP-Structure) - Complete OCR System")
                self._initialize_ai_table_mode()
            else:
                # 常规 OCR 模式（mobile/server）
                if self.current_preset not in self.PRESETS:
                    raise ValueError(f"Unknown preset: {self.current_preset}")
                preset_config = self.PRESETS[self.current_preset]
                print(f"Loading unified OCR engine with {preset_config['name']}")
                        
                # 获取模型路径和配置
                params = self._prepare_params(preset_config)
                        
                print(f"Initializing unified PaddleOCR engine with params: {params}")
                        
                # 初始化统一的 PaddleOCR 引擎
                try:
                    self.ocr_engine = PaddleOCR(**params)
                    print("Unified PaddleOCR engine initialized successfully")
                except Exception as e:
                    print(f"Error initializing unified PaddleOCR engine with GPU: {e}")
                    if params.get('device') == 'gpu':
                        print("Attempting fallback to CPU mode...")
                        params['device'] = 'cpu'
                        if 'use_gpu' in params:
                            del params['use_gpu']
                        self.ocr_engine = PaddleOCR(**params)
                        print("Unified PaddleOCR engine initialized successfully (Fallback to CPU)")
                    else:
                        raise e
                                
        except Exception as e:
            print(f"Error initializing unified OCR engine: {e}")
            import traceback
            traceback.print_exc()
            self.ocr_engine = None
    
    def _initialize_ai_table_mode(self):
        """
        初始化 AI 表格识别模式（PP-Structure）
        这是一个完整的 OCR 系统，包含检测、识别、表格结构分析等所有组件
        
        ⚠️ 注意：PP-StructureV3 会自动加载以下模型用于表格识别：
        - PP-DocLayout_plus-L: 文档布局分析
        - PP-OCRv5_server_det/rec: 表格内文字识别（PP-Structure 内部依赖）
        - SLANeXt/SLANet_plus: 表格结构识别
        - RT-DETR-L_*_table_cell_det: 表格单元格检测
        - PP-Chart2Table: 图表转表格
        - PP-LCNet_x1_0_doc_ori/textline_ori: 文档方向矫正（PP-Structure 内部使用）
        
        这些模型的加载是 PP-Structure 的正常工作流程，不是重复加载或错误配置。
        """
        try:
            print("\n" + "="*70)
            print("🔍 正在初始化 AI 表格识别 (PP-StructureV3) - 完整 OCR 系统")
            print("="*70)
            
            # 尝试导入 PPStructure（专门用于表格识别）
            try:
                from paddleocr import PPStructureV3 as PPStructure
                print("✅ 使用 PPStructureV3")
            except ImportError:
                try:
                    from paddleocr import PPStructure
                    print("✅ 使用 PPStructure")
                except ImportError:
                    raise ImportError("PPStructure 不可用，回退到 PaddleOCR")
                
            # 设备检测
            try:
                import paddle
                is_gpu_available = paddle.is_compiled_with_cuda()
                print(f"✅ PaddlePaddle 已编译 CUDA 支持：{is_gpu_available}")
            except Exception:
                is_gpu_available = False
                print("⚠️ 无法确定 PaddlePaddle 是否支持 CUDA，假设不支持")
                
            # GPU 可用则使用 GPU
            device = 'gpu' if is_gpu_available else 'cpu'
            print(f"🚀 AI 表格识别使用 {device.upper()} 模式")
            print("\n📦 即将加载的模型清单（PP-Structure 自动管理）：")
            print("   - PP-DocLayout_plus-L: 文档布局分析")
            print("   - PP-OCRv5_server_det/rec: 表格内文字识别 (PP-Structure 内部依赖)")
            print("   - PP-LCNet_x1_0_table_cls: 表格分类")
            print("   - SLANeXt_wired / SLANet_plus: 表格结构识别")
            print("   - RT-DETR-L_*_table_cell_det: 表格单元格检测")
            print("   - PP-Chart2Table: 图表转表格")
            print("   - PP-LCNet_x1_0_doc_ori/textline_ori: 文档方向矫正 (PP-Structure 内部使用)")
            print("\n⚠️ 重要提示：")
            print("   1. 以上模型由 PP-StructureV3 自动加载和管理，非重复加载或错误配置")
            print("   2. 部分模型可能会被多次引用（如 server det/rec），这是 PP-Structure 的内部设计")
            print("   3. 所有模型只会从磁盘加载一次，后续会使用缓存，不影响性能")
            print("="*70 + "\n")
                
            # 初始化 PP-Structure 引擎（专门用于表格识别）
            # 关键参数：use_table_recognition=True
            self.ocr_engine = PPStructure(
                device=device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_seal_recognition=False,
                use_table_recognition=True,      # 关键：启用表格识别
                use_formula_recognition=False,
                use_chart_recognition=False,
                use_region_detection=False,
            )
                
            print("\n✅ AI 表格识别 (PP-Structure) 初始化成功")
            print("💡 提示：PP-Structure 将自动管理所有相关模型的加载和使用\n")
                
        except Exception as e:
            print(f"❌ 初始化 AI 表格识别失败：{e}")
            print("↩️ 回退到 PaddleOCR（可能无法正确识别表格）")
            # 回退到普通 PaddleOCR
            try:
                from paddleocr import PaddleOCR
                params = {
                    'use_angle_cls': True,
                    'lang': 'ch',
                    'device': 'gpu' if is_gpu_available else 'cpu',
                }
                self.ocr_engine = PaddleOCR(**params)
                print("✅ 已回退到 PaddleOCR")
            except Exception as e2:
                print(f"❌ 回退也失败了：{e2}")
                import traceback
                traceback.print_exc()
                self.ocr_engine = None
        
    def _process_with_ai_table(self, image):
        """
        使用 AI 表格识别模式处理图像
            
        Args:
            image: numpy array 格式的图像
                
        Returns:
            list: 包含表格结构信息的 OCR 结果
        """
        print("DEBUG [_process_with_ai_table] Starting AI table recognition...")
        try:
            # 调用 PP-Structure 的 predict 方法，它会返回包含表格结构的结果
            result = self.ocr_engine.predict(image)
            print(f"DEBUG [_process_with_ai_table] Raw result type: {type(result)}, len: {len(result) if hasattr(result, '__len__') else 'N/A'}")
                
            regions = []
                
            if result and len(result) > 0:
                # PP-Structure 的输出格式：result[0] 包含所有识别结果
                res_obj = result[0]
                res = res_obj.res if hasattr(res_obj, 'res') else res_obj
                    
                print(f"DEBUG [_process_with_ai_table] Result keys: {list(res.keys()) if isinstance(res, dict) else 'Not a dict'}")
                                
                # 打印所有可能的表格相关字段
                possible_table_keys = ['table_res_list', 'table_cells', 'tables', 'table_result', 'structure_res', 'merged_res']
                for key in possible_table_keys:
                    if key in res:
                        val = res[key]
                        print(f"DEBUG [_process_with_ai_table] Found table key '{key}': type={type(val)}, len={len(val) if hasattr(val, '__len__') else 'N/A'}")
                        if val and len(val) > 0:
                            print(f"DEBUG [_process_with_ai_table] First item: {val[0] if isinstance(val, list) else val}")
                
                # 提取文本识别结果
                rec_texts = res.get('rec_texts', [])
                rec_scores = res.get('rec_scores', [])
                rec_polys = res.get('rec_polys', [])
                
                # 🔍 关键补充：检查 overall_ocr_res 字段（PP-Structure 的整体 OCR 结果）
                if not rec_texts or len(rec_texts) == 0:
                    overall_ocr_res = res.get('overall_ocr_res', None)
                    if overall_ocr_res:
                        print(f"DEBUG [_process_with_ai_table] Found overall_ocr_res, checking for OCR texts...")
                        # overall_ocr_res 可能是一个列表或字典
                        if isinstance(overall_ocr_res, list):
                            # 如果是列表，尝试从中提取文本
                            for item in overall_ocr_res:
                                if isinstance(item, dict):
                                    text = item.get('text', '') or item.get('recognized_text', '') or item.get('content', '')
                                    if text:
                                        rec_texts.append(text)
                                    # 提取坐标
                                    poly = item.get('poly', []) or item.get('points', []) or item.get('bbox', [])
                                    if poly:
                                        rec_polys.append(poly)
                                    # 提取置信度
                                    score = item.get('score', 1.0) or item.get('confidence', 1.0)
                                    rec_scores.append(score)
                            print(f"DEBUG [_process_with_ai_table] Extracted {len(rec_texts)} texts from overall_ocr_res")
                        elif isinstance(overall_ocr_res, dict):
                            # 如果是字典，尝试直接获取字段
                            rec_texts = overall_ocr_res.get('rec_texts', rec_texts)
                            rec_scores = overall_ocr_res.get('rec_scores', rec_scores)
                            rec_polys = overall_ocr_res.get('rec_polys', rec_polys)
                            print(f"DEBUG [_process_with_ai_table] Got texts from overall_ocr_res dict: {len(rec_texts)} items")
                    
                # 提取表格结构信息（如果有）
                table_res_list = res.get('table_res_list', [])
                
                # 检查其他可能的表格字段
                if not table_res_list:
                    # 尝试 merged_res (PP-Structure v2.x)
                    merged_res = res.get('merged_res', [])
                    if merged_res:
                        print(f"DEBUG [_process_with_ai_table] Found merged_res with {len(merged_res)} items")
                        # merged_res 可能包含表格单元格信息
                        table_res_list = []
                        for item in merged_res:
                            if isinstance(item, dict):
                                # 检查是否有表格相关信息
                                if 'row' in item or 'col' in item or 'bbox' in item:
                                    table_res_list.append(item)
                        print(f"DEBUG [_process_with_ai_table] Extracted {len(table_res_list)} table cells from merged_res")
                    
                # 检查是否有单独的表格识别结果
                if not table_res_list:
                    table_res = res.get('table', None)
                    if table_res:
                        print(f"DEBUG [_process_with_ai_table] Found separate table result: {type(table_res)}")
                        # PP-Structure 有时会返回单独的 table 字段
                        if hasattr(table_res, 'res'):
                            table_data = table_res.res
                            if isinstance(table_data, dict):
                                table_res_list = table_data.get('cells', [])
                                print(f"DEBUG [_process_with_ai_table] Extracted {len(table_res_list)} cells from table.res.cells")
                    
                print(f"DEBUG [_process_with_ai_table] rec_texts: {len(rec_texts)}, table_res_list: {len(table_res_list)}")
                    
                # 🔥 关键修复：优先使用表格识别结果，但如果表格为空且有 OCR 结果，则使用 OCR 结果
                has_table = bool(table_res_list)
                has_ocr = bool(rec_texts) and len(rec_texts) > 0
                
                print(f"DEBUG [_process_with_ai_table] has_table={has_table}, has_ocr={has_ocr}")
                    
                # 优先使用表格识别结果
                if has_table:
                    print(f"DEBUG [_process_with_ai_table] Processing {len(table_res_list)} table regions...")
                    for idx, table_region in enumerate(table_res_list):
                        if isinstance(table_region, dict):
                            # PP-Structure V3 格式
                            cell_box_list = table_region.get('cell_box_list', [])
                            # 关键修复：使用 pred_html 而不是 html
                            html_content = table_region.get('pred_html', '')
                            
                            # 打印所有可能的字段
                            print(f"DEBUG [_process_with_ai_table] Table region[{idx}] keys: {list(table_region.keys())}")
                            print(f"DEBUG [_process_with_ai_table] Table region[{idx}]: cell_box_list len={len(cell_box_list)}, has_pred_html={bool(html_content)}")
                            
                            # 检查是否有其他包含文本的字段
                            ocr_res = table_region.get('table_ocr_pred', {})
                            rec_texts = ocr_res.get('rec_texts', []) if isinstance(ocr_res, dict) else []
                            rec_polys = ocr_res.get('rec_polys', []) if isinstance(ocr_res, dict) else []
                            rec_scores = ocr_res.get('rec_scores', []) if isinstance(ocr_res, dict) else []
                            
                            if rec_texts:
                                print(f"DEBUG [_process_with_ai_table] Found OCR texts in table_ocr_pred: {len(rec_texts)} items")
                            
                            # 如果有 HTML，尝试解析 HTML 获取表格结构
                            if html_content and cell_box_list:
                                print(f"DEBUG [_process_with_ai_table] Attempting to parse HTML with {len(cell_box_list)} cells")
                                try:
                                    # 使用 Python 内置的 html.parser 解析 HTML（无需额外依赖）
                                    from html.parser import HTMLParser
                                    
                                    class TableParser(HTMLParser):
                                        def __init__(self):
                                            super().__init__()
                                            self.rows = []
                                            self.current_row = []
                                            self.current_cell = None
                                            self.in_td = False
                                            self.in_th = False
                                            self.cell_text = ''
                                            
                                        def handle_starttag(self, tag, attrs):
                                            attrs_dict = dict(attrs)
                                            if tag == 'tr':
                                                self.current_row = []
                                            elif tag in ['td', 'th']:
                                                self.in_td = (tag == 'td')
                                                self.in_th = (tag == 'th')
                                                self.cell_text = ''
                                                self.current_cell = {
                                                    'rowspan': int(attrs_dict.get('rowspan', 1)),
                                                    'colspan': int(attrs_dict.get('colspan', 1))
                                                }
                                        
                                        def handle_endtag(self, tag):
                                            if tag == 'tr':
                                                self.rows.append(self.current_row)
                                            elif tag in ['td', 'th']:
                                                if self.current_cell:
                                                    self.current_cell['text'] = self.cell_text.strip()
                                                    self.current_row.append(self.current_cell)
                                                self.in_td = False
                                                self.in_th = False
                                                self.current_cell = None
                                        
                                        def handle_data(self, data):
                                            if self.in_td or self.in_th:
                                                self.cell_text += data
                                    
                                    parser = TableParser()
                                    parser.feed(html_content)
                                    
                                    print(f"DEBUG [_process_with_ai_table] Parsed HTML: {len(parser.rows)} rows")
                                    for r_idx, row in enumerate(parser.rows):
                                        cells_text = [c.get('text', '')[:10] for c in row]
                                        print(f"DEBUG [_process_with_ai_table] Row[{r_idx}]: {cells_text}, cols={len(row)}")
                                    
                                    print(f"DEBUG [_process_with_ai_table] cell_box_list length: {len(cell_box_list)}")
                                    # 打印前几个 bbox 用于对比
                                    for i in range(min(5, len(cell_box_list))):
                                        box = cell_box_list[i]
                                        if hasattr(box, 'tolist'):
                                            box = box.tolist()
                                        print(f"DEBUG [_process_with_ai_table] cell_box_list[{i}]: {box}")
                                    
                                    # 提取单元格信息
                                    cell_idx = 0
                                    for row_idx, row in enumerate(parser.rows):
                                        for col_idx, cell in enumerate(row):
                                            text = cell.get('text', '')
                                            rowspan = cell.get('rowspan', 1)
                                            colspan = cell.get('colspan', 1)
                                            
                                            # 获取对应的 bbox
                                            bbox = None
                                            if cell_idx < len(cell_box_list):
                                                box_arr = cell_box_list[cell_idx]
                                                if hasattr(box_arr, 'tolist'):
                                                    box_arr = box_arr.tolist()
                                                # 转换为 [x1, y1, x2, y2] 格式
                                                if len(box_arr) >= 4:
                                                    bbox = [int(box_arr[0]), int(box_arr[1]), int(box_arr[2]), int(box_arr[3])]
                                                                                            
                                            # 将 bbox 转换为多边形格式 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                                            coordinates = None
                                            if bbox and len(bbox) == 4:
                                                coordinates = [
                                                    [bbox[0], bbox[1]],  # 左上
                                                    [bbox[2], bbox[1]],  # 右上
                                                    [bbox[2], bbox[3]],  # 右下
                                                    [bbox[0], bbox[3]]   # 左下
                                                ]
                                                                                            
                                            region = {
                                                'text': text,
                                                'confidence': 1.0,
                                                'coordinates': coordinates,  # 多边形格式
                                                'box': bbox,  # bbox 格式
                                                'table_info': {
                                                    'row': row_idx,
                                                    'col': col_idx,
                                                    'rowspan': rowspan,
                                                    'colspan': colspan
                                                }
                                            }
                                            regions.append(region)
                                            print(f"DEBUG [_process_with_ai_table] Cell[{row_idx},{col_idx}]: text='{text[:20]}...', bbox={bbox}")
                                            cell_idx += 1
                                            
                                except Exception as e:
                                    print(f"Error parsing HTML table: {e}")
                                    import traceback
                                    traceback.print_exc()
                            elif cell_box_list:
                                # 没有 HTML，只有 bbox 列表，无法确定行列和文本
                                print(f"DEBUG [_process_with_ai_table] Only cell_box_list available ({len(cell_box_list)} cells), cannot parse without HTML or text")
                                # 至少返回 bbox 信息
                                for cell_idx, box_arr in enumerate(cell_box_list):
                                    if hasattr(box_arr, 'tolist'):
                                        box_arr = box_arr.tolist()
                                    bbox = None
                                    if len(box_arr) >= 4:
                                        bbox = [int(box_arr[0]), int(box_arr[1]), int(box_arr[2]), int(box_arr[3])]
                                    
                                    # 将 bbox 转换为多边形格式
                                    coordinates = None
                                    if bbox and len(bbox) == 4:
                                        coordinates = [
                                            [bbox[0], bbox[1]],
                                            [bbox[2], bbox[1]],
                                            [bbox[2], bbox[3]],
                                            [bbox[0], bbox[3]]
                                        ]
                                    
                                    region = {
                                        'text': f'[Cell {cell_idx}]',
                                        'confidence': 1.0,
                                        'coordinates': coordinates,
                                        'box': bbox
                                    }
                                    regions.append(region)
                    
                # 🔥 关键修复：如果没有表格结果，使用普通 OCR 结果
                elif has_ocr:
                    print(f"DEBUG [_process_with_ai_table] No table detected, processing {len(rec_texts)} OCR regions...")
                    print(f"DEBUG [_process_with_ai_table] Processing {len(rec_texts)} OCR regions...")
                    if hasattr(rec_polys, 'tolist'):
                        rec_polys = rec_polys.tolist()
                    
                    # 🔍 关键调试：打印原始 OCR 结果的详细信息
                    print(f"DEBUG [_process_with_ai_table] rec_texts type: {type(rec_texts)}, len: {len(rec_texts) if hasattr(rec_texts, '__len__') else 'N/A'}")
                    print(f"DEBUG [_process_with_ai_table] rec_polys type: {type(rec_polys)}, len: {len(rec_polys) if hasattr(rec_polys, '__len__') else 'N/A'}")
                    print(f"DEBUG [_process_with_ai_table] rec_scores type: {type(rec_scores)}, len: {len(rec_scores) if hasattr(rec_scores, '__len__') else 'N/A'}")
                    
                    # 打印前 5 个结果的详细信息
                    for i in range(min(5, len(rec_texts))):
                        text = rec_texts[i] if i < len(rec_texts) else ''
                        score = rec_scores[i] if i < len(rec_scores) else 1.0
                        poly = rec_polys[i] if i < len(rec_polys) else []
                        
                        # 🔧 修复 numpy 数组判断：使用 len() 而不是直接 if poly
                        has_poly = (poly is not None) and (len(poly) > 0 if hasattr(poly, '__len__') else bool(poly))
                        poly_preview = poly[:2] if has_poly else None
                        
                        print(f"DEBUG [_process_with_ai_table] Region[{i}]: text='{text[:50]}...', score={score}, poly={poly_preview}...")
                        
                    if hasattr(rec_polys, 'tolist'):
                        rec_polys = rec_polys.tolist()
                        
                    for i in range(len(rec_texts)):
                        text = rec_texts[i] if i < len(rec_texts) else ''
                        score = rec_scores[i] if i < len(rec_scores) else 1.0
                        poly = rec_polys[i] if i < len(rec_polys) else []
                            
                        if hasattr(poly, 'tolist'):
                            poly = poly.tolist()
                        
                        # 🔧 修复 numpy 数组判断：先检查是否为 None，再检查长度
                        has_valid_poly = (poly is not None) and (len(poly) > 0 if hasattr(poly, '__len__') else bool(poly))
                        box = None
                        if has_valid_poly and len(poly) == 4:
                            box = [
                                int(min(p[0] for p in poly)),
                                int(min(p[1] for p in poly)),
                                int(max(p[0] for p in poly)),
                                int(max(p[1] for p in poly))
                            ]
                            
                        region = {
                            'text': text,
                            'confidence': float(score),
                            'coordinates': poly,
                            'box': box
                        }
                        regions.append(region)
                
                # 🔍 最终检查：如果两个分支都没进入，但有原始 OCR 数据，尝试直接使用
                if not regions and has_ocr and not has_table:
                    print(f"WARNING [_process_with_ai_table] Both table and OCR branches skipped, but has_ocr=True. Forcing OCR processing...")
                    # 这可能是逻辑 bug，强制处理 OCR 结果
                    if hasattr(rec_polys, 'tolist'):
                        rec_polys = rec_polys.tolist()
                    
                    for i in range(len(rec_texts)):
                        text = rec_texts[i] if i < len(rec_texts) else ''
                        score = rec_scores[i] if i < len(rec_scores) else 1.0
                        poly = rec_polys[i] if i < len(rec_polys) else []
                        
                        if hasattr(poly, 'tolist'):
                            poly = poly.tolist()
                        
                        # 🔧 修复 numpy 数组判断
                        has_valid_poly = (poly is not None) and (len(poly) > 0 if hasattr(poly, '__len__') else bool(poly))
                        box = None
                        if has_valid_poly and len(poly) == 4:
                            box = [
                                int(min(p[0] for p in poly)),
                                int(min(p[1] for p in poly)),
                                int(max(p[0] for p in poly)),
                                int(max(p[1] for p in poly))
                            ]
                        
                        region = {
                            'text': text,
                            'confidence': float(score),
                            'coordinates': poly,
                            'box': box
                        }
                        regions.append(region)
                    
                    print(f"WARNING [_process_with_ai_table] Forced processing returned {len(regions)} regions")
                
            print(f"DEBUG [_process_with_ai_table] Returning {len(regions)} regions")
            return sort_ocr_regions(regions)
                
        except Exception as e:
            print(f"Error in _process_with_ai_table: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _prepare_params(self, preset_config):
        """
        准备PaddleOCR参数
        """
        params = {}
        
        # 设备检测
        try:
            import paddle
            is_gpu_available = paddle.is_compiled_with_cuda()
            print(f"PaddlePaddle compiled with CUDA: {is_gpu_available}")
        except Exception:
            is_gpu_available = False
            print("Could not determine if PaddlePaddle is compiled with CUDA, assuming False")

        # 自动检测GPU使用（用户策略：GPU可用则使用，否则使用CPU）
        use_gpu = is_gpu_available
        params['device'] = 'gpu' if use_gpu else 'cpu'
        print(f"PaddleOCR device set to: {params['device']} (Auto-detected)")
        
        # 应用预设配置
        if self.config_manager:
            # 检测相关参数
            limit_side_len = self.config_manager.get_setting('det_limit_side_len')
            if limit_side_len:
                val = int(limit_side_len)
                # CPU模式优化：防止大图像导致OOM/崩溃
                if not use_gpu and val > 960:
                    print(f"Warning: Downgrading det_limit_side_len from {val} to 960 for CPU mode stability")
                    val = 960
                params['det_limit_side_len'] = val
                params['det_limit_type'] = 'max'
                
            det_db_thresh = self.config_manager.get_setting('det_db_thresh')
            if det_db_thresh:
                params['det_db_thresh'] = float(det_db_thresh)
                
            det_db_box_thresh = self.config_manager.get_setting('det_db_box_thresh')
            if det_db_box_thresh:
                params['det_db_box_thresh'] = float(det_db_box_thresh)
                
            det_db_unclip_ratio = self.config_manager.get_setting('det_db_unclip_ratio')
            if det_db_unclip_ratio:
                params['det_db_unclip_ratio'] = float(det_db_unclip_ratio)
            
            # 分类相关参数
            use_angle_cls = self.config_manager.get_setting('use_angle_cls')
            if use_angle_cls is not None:
                params['use_angle_cls'] = use_angle_cls
                
            cls_model_dir = self.config_manager.get_setting('cls_model_dir')
            if cls_model_dir and os.path.exists(cls_model_dir):
                print(f"Using local classification model: {cls_model_dir}")
                params['cls_model_dir'] = cls_model_dir
            
            # 确保角度分类启用（如果有CLS模型）
            if cls_model_dir:
                params['use_angle_cls'] = True
            
            # 语言设置（对默认模型必需）
            params['lang'] = 'ch'
            
            # 精度设置
            precision = self.config_manager.get_setting('precision')
            if precision:
                params['precision'] = precision
            
            # 获取模型目录 - 关键修复点
            det_model_dir = self.config_manager.get_setting('det_model_dir')
            rec_model_dir = self.config_manager.get_setting('rec_model_dir')
            
            if det_model_dir and os.path.exists(det_model_dir):
                print(f"Using local detection model: {det_model_dir}")
                params['det_model_dir'] = det_model_dir
                
            if rec_model_dir and os.path.exists(rec_model_dir):
                print(f"Using local recognition model: {rec_model_dir}")
                params['rec_model_dir'] = rec_model_dir
        
        # 应用预设的模型键
        if self.config_manager:
            print(f"Setting det_model_key = {preset_config['det_model_key']}")
            print(f"Setting rec_model_key = {preset_config['rec_model_key']}")
            self.config_manager.set_setting('det_model_key', preset_config['det_model_key'])
            self.config_manager.set_setting('rec_model_key', preset_config['rec_model_key'])
            
            # 确保模型目录也同步更新
            det_model_dir = self.config_manager.model_manager.get_model_dir('det', preset_config['det_model_key'])
            rec_model_dir = self.config_manager.model_manager.get_model_dir('rec', preset_config['rec_model_key'])
            
            if det_model_dir:
                print(f"Det model directory: {det_model_dir}")
                self.config_manager.set_setting('det_model_dir', det_model_dir)
                params['det_model_dir'] = det_model_dir
                # 同时设置对应的模型名称
                params['det_model_name'] = preset_config['det_model_key']
                
            if rec_model_dir:
                print(f"Rec model directory: {rec_model_dir}")
                self.config_manager.set_setting('rec_model_dir', rec_model_dir)
                params['rec_model_dir'] = rec_model_dir
                # 同时设置对应的模型名称
                params['rec_model_name'] = preset_config['rec_model_key']
        
        # 兼容性处理（PaddleOCR 3.4.0+）
        if PADDLE_OCR_AVAILABLE and hasattr(paddleocr, '__version__'):
            is_v3 = paddleocr.__version__.startswith('3.') or paddleocr.__version__.startswith('4.')
            if is_v3:
                print(f"Adapting params for PaddleOCR v{paddleocr.__version__}")
                # 移除不支持的参数
                params.pop('use_gpu', None)
                params.pop('show_log', None)
                params.pop('enable_mkldnn', None)
                
                # 检查是否配置了文档矫正模型
                unwarp_model_dir = self.config_manager.get_setting('unwarp_model_dir')
                use_unwarp = self.config_manager.get_setting('use_unwarp_model', False)
                
                if use_unwarp and unwarp_model_dir and os.path.exists(unwarp_model_dir):
                    print(f"Using local unwarping model: {unwarp_model_dir}")
                    params['use_doc_unwarping'] = True
                    params['doc_unwarping_model_dir'] = unwarp_model_dir
                    params['doc_unwarping_model_name'] = self._get_model_name_from_dir(unwarp_model_dir)
                else:
                    params['use_doc_unwarping'] = False
                
                # 检查是否配置了文档方向分类模型
                doc_ori_model_dir = self.config_manager.get_setting('doc_ori_model_dir')
                doc_ori_key = self.config_manager.get_setting('doc_ori_model_key')
                
                # 兼容旧配置：cls_model_dir
                cls_model_dir = self.config_manager.get_setting('cls_model_dir')
                cls_key = self.config_manager.get_setting('cls_model_key')

                use_doc_ori = self.config_manager.get_setting('use_doc_ori_model', False)
                
                # 优先使用专门的 doc_ori 配置
                if use_doc_ori and doc_ori_model_dir and os.path.exists(doc_ori_model_dir):
                    print(f"Using local document orientation model: {doc_ori_model_dir}")
                    params['use_doc_orientation_classify'] = True
                    params['doc_orientation_classify_model_dir'] = doc_ori_model_dir
                    params['doc_orientation_classify_model_name'] = self._get_model_name_from_dir(doc_ori_model_dir)
                # 兼容旧配置：如果 cls 配置中包含 doc_ori
                elif use_doc_ori and cls_model_dir and os.path.exists(cls_model_dir) and cls_key and 'doc_ori' in str(cls_key):
                    print(f"Using local document orientation model (from cls config): {cls_model_dir}")
                    params['use_doc_orientation_classify'] = True
                    params['doc_orientation_classify_model_dir'] = cls_model_dir
                    params['doc_orientation_classify_model_name'] = self._get_model_name_from_dir(cls_model_dir)
                else:
                    params['use_doc_orientation_classify'] = False
                
                # 映射模型键
                use_cls = self.config_manager.get_setting('use_cls_model', True)
                
                # 移除旧的 use_angle_cls，统一使用 use_textline_orientation
                if 'use_angle_cls' in params:
                    del params['use_angle_cls']
                
                # Double check
                if 'use_angle_cls' in params:
                    params.pop('use_angle_cls', None)
                
                if not use_cls:
                    params['use_textline_orientation'] = False
                else:
                    # 如果启用了 cls，则根据之前的逻辑（如果有cls模型则启用）
                    # 之前的逻辑可能已经设置了 use_angle_cls 或 use_textline_orientation
                    # 但我们已经pop了 use_angle_cls
                    
                    # 检查是否有 cls_model_dir (textline orientation)
                    # 之前的代码段已经处理了:
                    # if 'cls_model_dir' in params: ... params['textline_orientation_model_dir'] = ...
                    
                    # 只要有模型路径，我们就认为应该启用（除非被显式禁用）
                    # 但 params['use_textline_orientation'] 此时可能还没设置
                    
                    # 默认启用，除非没有模型?
                    # PaddleOCR pipeline 默认行为：如果提供了 textline_orientation_model_dir，则启用。
                    # 但我们需要显式控制。
                    
                    params['use_textline_orientation'] = True
                
                # 映射模型目录和名称（PaddleX格式）
                if 'det_model_dir' in params:
                    params['text_detection_model_dir'] = params.pop('det_model_dir')
                    if 'det_model_name' in params:
                        params['text_detection_model_name'] = params.pop('det_model_name')
                    else:
                        params['text_detection_model_name'] = preset_config['det_model_key']
                        
                if 'rec_model_dir' in params:
                    params['text_recognition_model_dir'] = params.pop('rec_model_dir')
                    if 'rec_model_name' in params:
                        params['text_recognition_model_name'] = params.pop('rec_model_name')
                    else:
                        params['text_recognition_model_name'] = preset_config['rec_model_key']
                        
                if 'cls_model_dir' in params:
                    cls_dir = params.pop('cls_model_dir')
                    # 当前只支持 0/180 的文本行方向管线，如果用户选的是 doc_ori 四分类模型，这里忽略自定义模型，使用内置的两方向模型
                    # 但上面的逻辑已经处理了 doc_ori 模型，这里仅处理文本行方向分类模型
                    cls_key = self.config_manager.get_setting('cls_model_key') if self.config_manager else None
                    if cls_key and 'doc_ori' in str(cls_key):
                        # 如果配置的是文档方向模型，不要将其作为文本行方向模型
                        # print(f"Skipping doc orientation model '{cls_key}' for textline orientation.")
                        pass
                    else:
                        print(f"Using local textline orientation model: {cls_dir}")
                        params['textline_orientation_model_dir'] = cls_dir
                        params['textline_orientation_model_name'] = self._get_model_name_from_dir(cls_dir)
                
                # 检查是否同时启用了两个方向模型
                if params.get('use_doc_orientation_classify') and params.get('use_textline_orientation'):
                    print("Both doc orientation and textline orientation are enabled.")
        
        return params
    
    def switch_preset(self, preset):
        """
        切换预设配置
        
        Args:
            preset: 预设名称 ('server' 或 'mobile')
        """
        if preset not in self.PRESETS:
            raise ValueError(f"Invalid preset: {preset}. Available presets: {list(self.PRESETS.keys())}")
        
        if preset == self.current_preset:
            print(f"Already using preset: {preset}")
            return
            
        print(f"Switching from {self.current_preset} to {preset} preset")
        self.current_preset = preset
        self._initialize_engine()
    
    def get_current_preset(self):
        """
        获取当前预设配置
        
        Returns:
            str: 当前预设名称
        """
        return self.current_preset
    
    def get_preset_info(self):
        """
        获取当前预设的详细信息
        
        Returns:
            dict: 预设信息
        """
        return self.PRESETS[self.current_preset]
    
    def process_image(self, image):
        """
        处理图像：检测并识别文本
            
        Args:
            image: 输入图像（PIL Image 或 numpy array）
                
        Returns:
            dict: 处理结果，包含文本区域和识别文本
        """
        print("Processing image with unified OCR engine")
        try:
            if PADDLE_OCR_AVAILABLE and self.ocr_engine:
                # 转换 PIL 图像为 numpy 数组（如果需要）
                if hasattr(image, 'convert'):
                    import numpy as np
                    image = np.array(image.convert('RGB'))
                    print(f"Converted image to numpy array, shape: {image.shape}")
                    
                # AI 表格识别模式：使用 PP-Structure 的表格识别功能
                if self.current_preset == 'ai_table':
                    print("DEBUG: Processing with AI Table Recognition mode")
                    return self._process_with_ai_table(image)
                    
                # 常规 OCR 模式
                print("Starting unified PaddleOCR prediction...")
                # 使用统一的 OCR 引擎进行检测和识别
                if hasattr(self.ocr_engine, 'ocr'):
                    # 标准 PaddleOCR 用法
                    result = self.ocr_engine.ocr(image)
                    print("✓ Unified PaddleOCR prediction completed.")
                        
                    # 处理标准 PaddleOCR 输出格式
                    if result and isinstance(result[0], list):
                        regions = []
                        for line in result[0]:
                            # line: [box, (text, score)]
                            box = line[0]
                            text_obj = line[1]
                            text = text_obj[0]
                            score = text_obj[1]
                                
                            # Ensure box is a Python list (convert from numpy array if needed)
                            if hasattr(box, 'tolist'):
                                try:
                                    box = box.tolist()
                                except:
                                    box = []
                                
                            regions.append({
                                'coordinates': box,
                                'confidence': float(score),
                                'text': text,
                                # Ensure box is also available for ResultAdapter fallback
                                'box': [
                                    int(min(p[0] for p in box)),
                                    int(min(p[1] for p in box)),
                                    int(max(p[0] for p in box)),
                                    int(max(p[1] for p in box))
                                ] if box and len(box) == 4 else None
                            })
                        print(f"✓ Processed {len(regions)} text regions with unified engine")
                        return sort_ocr_regions(regions)
                    
                # 回退到 predict 方法（PaddleX 格式）
                result = self.ocr_engine.predict(image)
                                    
                if result and result[0]:
                    # 检查 res 属性或直接检查 result[0]
                    res = result[0].res if hasattr(result[0], 'res') else result[0]
                                        
                    # 提取识别的文本和置信度
                    recognized_texts = res.get('rec_texts', [])
                    recognized_scores = res.get('rec_scores', [])
                    rec_polys = res.get('rec_polys', [])
                        
                    # 如果 rec_polys 是数组，需要转换为列表格式
                    if hasattr(rec_polys, 'tolist'):
                        rec_polys = rec_polys.tolist()
                        
                    # 组合检测区域、识别文本和置信度
                    regions = []
                    for i in range(len(rec_polys)):
                        text = recognized_texts[i] if i < len(recognized_texts) else ''
                        score = recognized_scores[i] if i < len(recognized_scores) else 1.0
                        poly = rec_polys[i] if i < len(rec_polys) else []
                            
                        print(f"DEBUG [unified_engine] Region {i}: text='{text[:20]}...', poly_type={type(poly)}, poly_len={len(poly) if hasattr(poly, '__len__') else 'N/A'}")
                            
                        # Ensure poly is a Python list FIRST (not numpy array)
                        if hasattr(poly, 'tolist'):
                            try:
                                poly = poly.tolist()
                            except:
                                poly = []
                            
                        # Check if poly is empty (after conversion to list)
                        poly_is_empty = len(poly) == 0 if hasattr(poly, '__len__') else True
                            
                        # Convert polygon to box if possible
                        box = None
                        if not poly_is_empty and len(poly) == 4:
                            try:
                                box = [
                                    int(min(p[0] for p in poly)),
                                    int(min(p[1] for p in poly)),
                                    int(max(p[0] for p in poly)),
                                    int(max(p[1] for p in poly))
                                ]
                            except Exception as e:
                                pass
                            
                        print(f"DEBUG [unified_engine] After convert: poly={poly[:2] if poly else None}..., box={box}")
                            
                        regions.append({
                            'coordinates': poly,
                            'confidence': float(score),
                            'text': text,
                            'box': box
                        })
                        
                    print(f"✓ Processed {len(regions)} text regions with unified engine")
                    return sort_ocr_regions(regions)
                else:
                    print("No text regions detected")
                    return []
            else:
                # 模拟结果
                print("Using mock recognition (PaddleOCR not available)")
                return [{
                    'text': '示例文本',
                    'confidence': 0.95,
                    'coordinates': [[0, 0], [100, 0], [100, 30], [0, 30]]
                }]
        except Exception as e:
            print(f"Error processing image with unified OCR engine: {e}")
            import traceback
            traceback.print_exc()
            return []
