# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：将检测与识别整合为单一 PaddleOCR/PP-Structure 引擎，按预设 (server/mobile/ai_table) 一次性完成推理
# - 核心实现：根据预设与环境装配参数、映射 PaddleX 新参数命名，提供普通 OCR 与 AI 表格两条执行路径并标准化输出
# - 关联关系：由 OcrEngine 作为主识别后端调用；与 ConfigManager/ModelManager 协作选择与定位模型；其输出进一步由 ResultAdapter 排序/规范化
#
# 日志说明：所有日志输出由日志管理器统一接管

"""
统一 OCR 引擎 - 将文本检测和文本识别功能整合为单一引擎
支持 server 和 mobile 两种预设配置，避免模型重复加载造成的资源浪费
"""

import os
import traceback
from app.log.log_bus import get_logger
from app.infrastructure.error_handler import handle_errors, ErrorCode

logger = get_logger()

try:
    import paddleocr
    from paddleocr import PaddleOCR

    PADDLE_OCR_AVAILABLE = True
except ImportError:
    paddleocr = None
    PaddleOCR = None
    PADDLE_OCR_AVAILABLE = False
    logger.error("unified_engine", "import_failed", "PaddleOCR not available, using mock implementation")

from app.utils.ocr_utils import sort_ocr_regions


class UnifiedOCREngine:
    """
    统一 OCR 引擎，整合文本检测和识别功能
    支持预设配置：server（高精度）和 mobile（轻量级）
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
        初始化统一 OCR 引擎
        
        Args:
            config_manager: 配置管理器
            preset: 预设配置 ('server' 或 'mobile')
        """
        logger.debug("unified_engine", "initializing", f"Initializing Unified OCR Engine with preset: {preset}")
        self.config_manager = config_manager
        self.current_preset = preset
        self.ocr_engine = None
        self._initialize_engine()

    @staticmethod
    def _get_model_name_from_dir(dir_path):
        """
        从 inference.yml 或目录名提取模型名称
        """
        if not dir_path:
            return None
        # 尝试读取 inference.yml
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

    @handle_errors(error_code=ErrorCode.OCR_ENGINE_001, fallback_return=None, component="UnifiedOCREngine")
    def _initialize_engine(self):
        """
        根据当前预设初始化 OCR 引擎
        """
        if not PADDLE_OCR_AVAILABLE:
            logger.error("unified_engine", "not_available", "PaddleOCR not available, using mock implementation")
            return

        try:
            # AI 表格识别模式：使用独立的完整 OCR 系统
            if self.current_preset == 'ai_table':
                logger.debug("unified_engine", "init_ai_table",
                            "Initializing AI Table Recognition (PP-Structure) - Complete OCR System")
                self._initialize_ai_table_mode()
            else:
                # 常规 OCR 模式（mobile/server）
                if self.current_preset not in self.PRESETS:
                    raise ValueError(f"Unknown preset: {self.current_preset}")
                preset_config = self.PRESETS[self.current_preset]
                logger.debug("unified_engine", "loading_preset",
                            f"Loading unified OCR engine with {preset_config['name']}")

                # 获取模型路径和配置
                params = self._prepare_params(preset_config)

                logger.debug("unified_engine", "init_with_params",
                            f"Initializing unified PaddleOCR engine with params")

                # 初始化统一的 PaddleOCR 引擎
                try:
                    self.ocr_engine = PaddleOCR(**params)
                    logger.success("unified_engine", "init_success",
                                   "Unified PaddleOCR engine initialized successfully")
                except Exception as e:
                    error_msg = f"Error initializing unified PaddleOCR engine with GPU: {e}"
                    logger.error("unified_engine", "init_gpu_failed", error_msg)
                    if params.get('device') == 'gpu':
                        logger.debug("unified_engine", "fallback_cpu", "Attempting fallback to CPU mode...")
                        params['device'] = 'cpu'
                        if 'use_gpu' in params:
                            del params['use_gpu']
                        self.ocr_engine = PaddleOCR(**params)
                        logger.success("unified_engine", "init_cpu_success",
                                       "Unified PaddleOCR engine initialized successfully (Fallback to CPU)")
                    else:
                        raise e

        except Exception as e:
            error_msg = f"Error initializing unified OCR engine: {e}"
            logger.error("unified_engine", "init_failed", error_msg)
            traceback.print_exc()
            self.ocr_engine = None

    @handle_errors(error_code=ErrorCode.OCR_ENGINE_001, fallback_return=None, component="UnifiedOCREngine")
    def _initialize_ai_table_mode(self):
        """
        初始化 AI 表格识别模式（PP-Structure）
        这是一个完整的 OCR 系统，包含检测、识别、表格结构分析等所有组件
        
        ⚠️ 重要说明：
        PP-StructureV3 会自动加载以下模型用于表格识别：
        - PP-DocLayout_plus-L: 文档布局分析
        - PP-OCRv5_server_det/rec: 表格内文字识别（PP-Structure 内部依赖）
        - SLANeXt/SLANet_plus: 表格结构识别
        - RT-DETR-L_*_table_cell_det: 表格单元格检测
        - PP-Chart2Table: 图表转表格
        - PP-LCNet_x1_0_doc_ori/textline_ori: 文档方向矫正（PP-Structure 内部使用）
        
        💡 关于日志中"Creating model"重复出现的说明：
        - 第一次出现（初始化阶段）：真正的模型加载到内存
        - 后续出现（处理阶段）：PaddleOCR 的缓存检查日志，并非真正重新加载
        - 所有模型只会加载一次，后续都会使用磁盘缓存，不影响性能
        - 这是 PP-StructureV3 的正常工作机制，不是错误或重复加载
        """
        try:
            # 简化日志输出，只保留关键信息
            logger.info("unified_engine", "init_ai_table_start", "Initializing AI Table Recognition (PP-Structure)")

            # 尝试导入 PPStructure（专门用于表格识别）
            try:
                from paddleocr import PPStructureV3 as PPStructure
                logger.debug("unified_engine", "use_ppstructurev3", "Using PPStructureV3")
            except ImportError:
                try:
                    from paddleocr import PPStructure  # type: ignore[attr-defined]
                    logger.debug("unified_engine", "use_ppstructure", "Using PPStructure")
                except ImportError:
                    PPStructure = None
                    raise ImportError("PPStructure 不可用，回退到 PaddleOCR")

            # 设备检测
            try:
                import paddle
                is_gpu_available = paddle.is_compiled_with_cuda()
                device = 'gpu' if is_gpu_available else 'cpu'
                logger.debug("unified_engine", "ai_table_device", f"AI 表格识别使用 {device.upper()} 模式")
            except Exception:
                device = 'cpu'
                logger.warning("unified_engine", "cuda_unknown", "无法确定 CUDA 支持，使用 CPU 模式")

            # 初始化 PP-Structure 引擎（专门用于表格识别）
            self.ocr_engine = PPStructure(
                device=device,
                use_doc_orientation_classify=False,  # AI 表格模式不使用外部纠正模型
                use_doc_unwarping=False,  # AI 表格模式不使用外部纠正模型
                use_textline_orientation=False,  # AI 表格模式不使用外部纠正模型
                use_seal_recognition=False,
                use_table_recognition=True,  # 关键：启用表格识别
                use_formula_recognition=False,
                use_chart_recognition=False,
                use_region_detection=False,
            )

            logger.success("unified_engine", "ai_table_init_success", "AI 表格识别 (PP-Structure) 初始化成功")

        except Exception as e:
            error_msg = f"初始化 AI 表格识别失败：{e}"
            logger.error("unified_engine", "ai_table_init_failed", error_msg)
            logger.info("unified_engine", "fallback_ppstructure", "回退到 PaddleOCR")
            is_gpu_available = False
            try:
                from paddleocr import PaddleOCR
                params = {
                    'use_angle_cls': True,
                    'lang': 'ch',
                    'device': 'gpu' if is_gpu_available else 'cpu',
                }
                self.ocr_engine = PaddleOCR(**params)
                logger.success("unified_engine", "ai_table_fallback_success", "已成功回退到 PaddleOCR")
            except Exception as e2:
                error_msg = f"回退也失败了：{e2}"
                logger.error("unified_engine", "ai_table_fallback_failed", error_msg)
                traceback.print_exc()
                self.ocr_engine = None

    @handle_errors(error_code=ErrorCode.OCR_ENGINE_002, fallback_return=[], component="UnifiedOCREngine")
    def _process_with_ai_table(self, image):
        """
        使用 AI 表格识别模式处理图像
            
        Args:
            image: numpy array 格式的图像
                
        Returns:
            list: 包含表格结构信息的 OCR 结果
        """
        logger.debug("unified_engine", "ai_table_process_start", "Starting AI table recognition...")
        try:
            # 调用 PP-Structure 的 predict 方法，它会返回包含表格结构的结果
            result = self.ocr_engine.predict(image)

            regions = []

            if result and len(result) > 0:
                # PP-Structure 的输出格式：result[0] 包含所有识别结果
                res_obj = result[0]
                res = res_obj.res if hasattr(res_obj, 'res') else res_obj

                # 提取文本识别结果
                rec_texts = res.get('rec_texts', [])
                rec_scores = res.get('rec_scores', [])
                rec_polys = res.get('rec_polys', [])

                # 🔍 关键补充：检查 overall_ocr_res 字段（PP-Structure 的整体 OCR 结果）
                if not rec_texts or len(rec_texts) == 0:
                    overall_ocr_res = res.get('overall_ocr_res', None)
                    if overall_ocr_res:
                        # overall_ocr_res 可能是一个列表或字典
                        if isinstance(overall_ocr_res, list):
                            # 如果是列表，尝试从中提取文本
                            for item in overall_ocr_res:
                                if isinstance(item, dict):
                                    text = item.get('text', '') or item.get('recognized_text', '') or item.get(
                                        'content', '')
                                    if text:
                                        rec_texts.append(text)
                                    # 提取坐标
                                    poly = item.get('poly', []) or item.get('points', []) or item.get('bbox', [])
                                    if poly:
                                        rec_polys.append(poly)
                                    # 提取置信度
                                    score = item.get('score', 1.0) or item.get('confidence', 1.0)
                                    rec_scores.append(score)
                        elif isinstance(overall_ocr_res, dict):
                            # 如果是字典，尝试直接获取字段
                            rec_texts = overall_ocr_res.get('rec_texts', rec_texts)
                            rec_scores = overall_ocr_res.get('rec_scores', rec_scores)
                            rec_polys = overall_ocr_res.get('rec_polys', rec_polys)

                # 提取表格结构信息（如果有）
                table_res_list = res.get('table_res_list', [])

                # 检查其他可能的表格字段
                if not table_res_list:
                    # 尝试 merged_res (PP-Structure v2.x)
                    merged_res = res.get('merged_res', [])
                    if merged_res:
                        # merged_res 可能包含表格单元格信息
                        table_res_list = []
                        for item in merged_res:
                            if isinstance(item, dict):
                                # 检查是否有表格相关信息
                                if 'row' in item or 'col' in item or 'bbox' in item:
                                    table_res_list.append(item)

                # 检查是否有单独的表格识别结果
                if not table_res_list:
                    table_res = res.get('table', None)
                    if table_res:
                        # PP-Structure 有时会返回单独的 table 字段
                        if hasattr(table_res, 'res'):
                            table_data = table_res.res
                            if isinstance(table_data, dict):
                                table_res_list = table_data.get('cells', [])

                has_table = bool(table_res_list)
                has_ocr = bool(rec_texts) and len(rec_texts) > 0

                # 优先使用表格识别结果
                if has_table:
                    for idx, table_region in enumerate(table_res_list):
                        if isinstance(table_region, dict):
                            # PP-Structure V3 格式
                            cell_box_list = table_region.get('cell_box_list', [])
                            # 关键修复：使用 pred_html 而不是 html
                            html_content = table_region.get('pred_html', '')

                            # 检查是否有其他包含文本的字段
                            ocr_res = table_region.get('table_ocr_pred', {})
                            rec_texts = ocr_res.get('rec_texts', []) if isinstance(ocr_res, dict) else []
                            rec_polys = ocr_res.get('rec_polys', []) if isinstance(ocr_res, dict) else []
                            rec_scores = ocr_res.get('rec_scores', []) if isinstance(ocr_res, dict) else []

                            if html_content and cell_box_list:
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
                                                    bbox = [int(box_arr[0]), int(box_arr[1]), int(box_arr[2]),
                                                            int(box_arr[3])]

                                            # 将 bbox 转换为多边形格式 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                                            coordinates = None
                                            if bbox and len(bbox) == 4:
                                                coordinates = [
                                                    [bbox[0], bbox[1]],  # 左上
                                                    [bbox[2], bbox[1]],  # 右上
                                                    [bbox[2], bbox[3]],  # 右下
                                                    [bbox[0], bbox[3]]  # 左下
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
                                            cell_idx += 1

                                except Exception as e:
                                    error_msg = f"Error parsing HTML table: {e}"
                                    logger.error("unified_engine", "ai_table_html_parse_error", error_msg)
                                    traceback.print_exc()
                            elif cell_box_list:
                                # 没有 HTML，只有 bbox 列表，无法确定行列和文本
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
                    if hasattr(rec_polys, 'tolist'):
                        rec_polys = rec_polys.tolist()

                    for i in range(len(rec_texts)):
                        text = rec_texts[i] if i < len(rec_texts) else ''
                        score = rec_scores[i] if i < len(rec_scores) else 1.0
                        poly = rec_polys[i] if i < len(rec_polys) else []

                        if hasattr(poly, 'tolist'):
                            poly = poly.tolist()

                        # 🔧 修复 numpy 数组判断：先检查是否为 None，再检查长度
                        has_valid_poly = (poly is not None) and (
                            len(poly) > 0 if hasattr(poly, '__len__') else bool(poly))
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
                        has_valid_poly = (poly is not None) and (
                            len(poly) > 0 if hasattr(poly, '__len__') else bool(poly))
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

            return sort_ocr_regions(regions)

        except Exception as e:
            error_msg = f"Error in _process_with_ai_table: {e}"
            logger.error("unified_engine", "ai_table_process_error", error_msg)
            traceback.print_exc()
            return []

    @handle_errors(error_code=ErrorCode.OCR_ENGINE_002, fallback_return=[], component="UnifiedOCREngine")
    def process_image(self, image):
        """
        处理图像：检测并识别文本
            
        Args:
            image: 输入图像（PIL Image 或 numpy array）
                
        Returns:
            dict: 处理结果，包含文本区域和识别文本
        """
        logger.debug("unified_engine", "process_start", "Processing image with unified OCR engine")
        try:
            if PADDLE_OCR_AVAILABLE and self.ocr_engine:
                # 转换 PIL 图像为 numpy 数组（如果需要）
                if hasattr(image, 'convert'):
                    import numpy as np
                    image = np.array(image.convert('RGB'))
                    logger.debug("unified_engine", "image_converted",
                                 f"Converted image to numpy array")

                # AI 表格识别模式：使用 PP-Structure 的表格识别功能
                if self.current_preset == 'ai_table':
                    logger.debug("unified_engine", "ai_table_mode_enter", "Processing with AI Table Recognition mode")
                    return self._process_with_ai_table(image)

                # 常规 OCR 模式
                logger.debug("unified_engine", "predict_start", "Starting unified PaddleOCR prediction...")
                # 使用统一的 OCR 引擎进行检测和识别
                if hasattr(self.ocr_engine, 'ocr'):
                    # 标准 PaddleOCR 用法
                    result = self.ocr_engine.ocr(image)
                    logger.debug("unified_engine", "predict_success", "Unified PaddleOCR prediction completed.")

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
                        logger.debug("unified_engine", "regions_processed", f"Processed {len(regions)} text "
                                                                              f"regions with unified engine")
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

                        regions.append({
                            'coordinates': poly,
                            'confidence': float(score),
                            'text': text,
                            'box': box
                        })

                    logger.debug("unified_engine", "regions_processed", f"Processed {len(regions)} text regions "
                                                                          f"with unified engine")
                    return sort_ocr_regions(regions)
                else:
                    logger.debug("unified_engine", "no_regions_detected", "No text regions detected")
                    return []
            else:
                # 模拟结果
                logger.debug("unified_engine", "mock_mode", "Using mock recognition (PaddleOCR not available)")
                return [{
                    'text': '示例文本',
                    'confidence': 0.95,
                    'coordinates': [[0, 0], [100, 0], [100, 30], [0, 30]]
                }]
        except Exception as e:
            error_msg = f"Error processing image with unified OCR engine: {e}"
            logger.error("unified_engine", "process_failed", error_msg)
            traceback.print_exc()
            return []

    @handle_errors(error_code=ErrorCode.CONFIG_LOAD_001, fallback_return={}, component="UnifiedOCREngine")
    def _prepare_params(self, preset_config):
        """
        准备 PaddleOCR 参数
        """
        params = {}

        # 设备检测
        try:
            import paddle
            is_gpu_available = paddle.is_compiled_with_cuda()
            logger.debug("unified_engine", "cuda_support", f"PaddlePaddle CUDA 支持：{is_gpu_available}")
        except Exception:
            is_gpu_available = False
            logger.debug("unified_engine", "cuda_unknown", "无法确定 PaddlePaddle CUDA 支持")

        # 自动检测 GPU 使用（用户策略：GPU 可用则使用，否则使用 CPU）
        use_gpu = is_gpu_available
        params['device'] = 'gpu' if use_gpu else 'cpu'
        logger.debug("unified_engine", "device_set", f"PaddleOCR device: {params['device']}")

        # 应用预设配置
        if self.config_manager:
            # 检测相关参数
            limit_side_len = self.config_manager.get_setting('det_limit_side_len')
            if limit_side_len:
                val = int(limit_side_len)
                # CPU 模式优化：防止大图像导致 OOM/崩溃
                if not use_gpu and val > 960:
                    logger.debug("unified_engine", "det_limit_downgrade",
                                   f"Downgrading det_limit_side_len from {val} to 960 for CPU mode")
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
                logger.debug("unified_engine", "cls_model_loaded", f"Using local classification model")
                params['cls_model_dir'] = cls_model_dir

            # 确保角度分类启用（如果有 CLS 模型）
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
                logger.debug("unified_engine", "det_model_loaded", f"Using local detection model")
                params['det_model_dir'] = det_model_dir

            if rec_model_dir and os.path.exists(rec_model_dir):
                logger.debug("unified_engine", "rec_model_loaded", f"Using local recognition model")
                params['rec_model_dir'] = rec_model_dir

        # 应用预设的模型键
        if self.config_manager:
            logger.debug("unified_engine", "set_model_keys",
                         f"Setting det_model_key and rec_model_key")
            self.config_manager.set_setting('det_model_key', preset_config['det_model_key'])
            self.config_manager.set_setting('rec_model_key', preset_config['rec_model_key'])

            # 确保模型目录也同步更新
            # PaddleOCR v3.x+ 使用模型名称自动管理，不需要手动指定目录
            # 直接使用模型 Key 作为模型名称传递给 PaddleOCR
            if preset_config['det_model_key']:
                params['text_detection_model_name'] = preset_config['det_model_key']
                logger.debug("unified_engine", "det_model_set", f"Using det model")

            if preset_config['rec_model_key']:
                params['text_recognition_model_name'] = preset_config['rec_model_key']
                logger.debug("unified_engine", "rec_model_set", f"Using rec model")

        # 兼容性处理（PaddleOCR 3.4.0+）
        if PADDLE_OCR_AVAILABLE and hasattr(paddleocr, '__version__'):
            is_v3 = paddleocr.__version__.startswith('3.') or paddleocr.__version__.startswith('4.')
            if is_v3:
                logger.debug("unified_engine", "paddleocr_version_adapt",
                             f"Adapting params for PaddleOCR v{paddleocr.__version__}")
                # 移除不支持的参数
                params.pop('use_gpu', None)
                params.pop('show_log', None)
                params.pop('enable_mkldnn', None)

                unwarp_model_dir = self.config_manager.get_setting('unwarp_model_dir')
                use_unwarp = self.config_manager.get_setting('use_unwarp_model', False)
                unwarp_model_key = self.config_manager.get_setting('unwarp_model_key')

                logger.debug("unified_engine", "unwarp_config_check",
                             f"use_unwarp_model={use_unwarp}, unwarp_model_dir={unwarp_model_dir}, unwarp_model_key={unwarp_model_key}")

                if use_unwarp and unwarp_model_dir and os.path.exists(unwarp_model_dir):
                    logger.debug("unified_engine", "unwarp_model_loaded",
                                f"Using local unwarping model")
                    params['use_doc_unwarping'] = True
                    params['doc_unwarping_model_dir'] = unwarp_model_dir
                    params['doc_unwarping_model_name'] = self._get_model_name_from_dir(unwarp_model_dir)
                elif use_unwarp and unwarp_model_key:
                    # 没有指定目录，但有模型 Key，使用 PaddleOCR 自动下载和管理
                    logger.debug("unified_engine", "unwarp_use_builtin",
                                f"Using built-in unwarping model")
                    params['use_doc_unwarping'] = True
                    params['doc_unwarping_model_name'] = unwarp_model_key
                else:
                    params['use_doc_unwarping'] = False

                doc_ori_model_dir = self.config_manager.get_setting('doc_ori_model_dir')
                doc_ori_model_key = self.config_manager.get_setting('doc_ori_model_key')

                # 兼容旧配置：cls_model_dir
                cls_model_dir = self.config_manager.get_setting('cls_model_dir')
                cls_key = self.config_manager.get_setting('cls_model_key')

                use_doc_ori = self.config_manager.get_setting('use_doc_ori_model', False)

                if use_doc_ori and doc_ori_model_dir and os.path.exists(doc_ori_model_dir):
                    logger.debug("unified_engine", "doc_ori_model_loaded",
                                f"Using local document orientation model")
                    params['use_doc_orientation_classify'] = True
                    params['doc_orientation_classify_model_dir'] = doc_ori_model_dir
                    params['doc_orientation_classify_model_name'] = self._get_model_name_from_dir(doc_ori_model_dir)
                elif use_doc_ori and doc_ori_model_key:
                    # 没有指定目录，但有模型 Key，使用 PaddleOCR 自动下载和管理
                    logger.debug("unified_engine", "doc_ori_use_builtin",
                                f"Using built-in document orientation model")
                    params['use_doc_orientation_classify'] = True
                    params['doc_orientation_classify_model_name'] = doc_ori_model_key
                elif use_doc_ori and cls_model_dir and os.path.exists(cls_model_dir) and cls_key and 'doc_ori' in str(
                        cls_key):
                    logger.debug("unified_engine", "doc_ori_from_cls", f"Using local document orientation model (from "
                                                                      f"cls config)")
                    params['use_doc_orientation_classify'] = True
                    params['doc_orientation_classify_model_dir'] = cls_model_dir
                    params['doc_orientation_classify_model_name'] = self._get_model_name_from_dir(cls_model_dir)
                else:
                    params['use_doc_orientation_classify'] = False

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
                    # 如果启用了 cls，则根据之前的逻辑（如果有 cls 模型则启用）
                    # 之前的逻辑可能已经设置了 use_angle_cls 或 use_textline_orientation
                    # 但我们已经 pop 了 use_angle_cls

                    # 检查是否有 cls_model_dir (textline orientation)
                    # 之前的代码段已经处理了:
                    # if 'cls_model_dir' in params: ... params['textline_orientation_model_dir'] = ...

                    # 只要有模型路径，我们就认为应该启用（除非被显式禁用）
                    # 但 params['use_textline_orientation'] 此时可能还没设置

                    # 默认启用，除非没有模型？
                    # PaddleOCR pipeline 默认行为：如果提供了 textline_orientation_model_dir，则启用。
                    # 但我们需要显式控制。

                    params['use_textline_orientation'] = True

                # 映射模型目录和名称（PaddleX 格式）
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
                    if cls_key and 'doc_ori' in str(cls_key):
                        logger.debug("unified_engine", "skip_doc_ori_for_textline",
                                     f"Skipping doc orientation model for textline orientation.")
                        pass
                    else:
                        logger.debug("unified_engine", "textline_model_loaded", f"Using local textline orientation "
                                                                               f"model")
                        params['textline_orientation_model_dir'] = cls_dir
                        params['textline_orientation_model_name'] = self._get_model_name_from_dir(cls_dir)

                if params.get('use_doc_orientation_classify') and params.get('use_textline_orientation'):
                    logger.debug("unified_engine", "dual_orientation_enabled", "Both doc orientation and textline "
                                                                              "orientation are enabled.")

        return params
