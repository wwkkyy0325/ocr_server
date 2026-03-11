# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：提供 OCR 相关的通用算法与工具函数（如结果排序/分行重建）
# - 核心实现：严格的 Center-Y 线聚类与行内左右排序，输出带 line_index 的有序区域
# - 关联关系：由 UnifiedOCREngine/OcrEngine 产出的区域在交给 ResultAdapter/前端组件前进行排序以保证阅读顺序

def sort_ocr_regions(regions):

    if not regions:
        return []

    # 1. Preprocess: Compute bounding boxes and vertical centers
    items = []
    for r in regions:
        poly = r.get('coordinates', [])

        # Fallback to 'box' if coordinates are missing
        if (poly is None or len(poly) == 0) and 'box' in r:
            box = r['box']  # Expecting [x1, y1, x2, y2]
        elif poly is not None and len(poly) > 0:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            if not xs or not ys:
                continue
            box = [min(xs), min(ys), max(xs), max(ys)]
        else:
            continue

        y1, y2 = box[1], box[3]
        cy = (y1 + y2) / 2
        height = y2 - y1
        items.append({'data': r, 'box': box, 'cy': cy, 'h': height})

    if not items:
        return []

    # 2. Initial Sort by Top Y (helps in greedy clustering)
    items.sort(key=lambda x: x['box'][1])

    # 3. Cluster into Lines (Strict Mode)
    lines = []

    for item in items:
        matched = False

        # Try to match with existing lines
        # We check the last added line first (most likely candidate for sorted input)
        # But we should check all 'active' lines if we want to be robust against y-jitter

        best_line_idx = -1
        min_dist = float('inf')

        for i, line in enumerate(lines):
            # Calculate line statistics
            # We use the average Center Y of the line to represent it
            line_cy = sum(x['cy'] for x in line) / len(line)
            line_h = sum(x['h'] for x in line) / len(line)

            # Check if item belongs to this line
            # User Requirement: Cancel merging of upper and lower lines.
            # Stricter Criterion:
            # 1. Vertical Center Distance must be very small relative to height.
            # 2. Significant Vertical Overlap.

            # Distance Check: Stricter threshold (e.g., 0.3 * height)
            # This ensures distinct lines are kept separate.
            dist = abs(item['cy'] - line_cy)
            threshold = min(item['h'], line_h) * 0.3

            # Overlap Check:
            # y_top = max(item_top, line_top_avg) ... simplified to cy check usually works,
            # but let's be robust.

            if dist < threshold:
                # Found a candidate. Is it the best?
                if dist < min_dist:
                    min_dist = dist
                    best_line_idx = i

        if best_line_idx != -1:
            lines[best_line_idx].append(item)
            matched = True

        if not matched:
            # Start a new line
            lines.append([item])

    # 4. Sort Lines by Vertical Position (Average Center Y)
    # This ensures that even if a line started with a slightly lower item, 
    # the overall line position determines the order.
    lines.sort(key=lambda line: sum(x['cy'] for x in line) / len(line))

    # 5. Sort Regions within Lines by Left X and Tag Line Index
    sorted_regions = []
    for line_idx, line in enumerate(lines):
        line.sort(key=lambda x: x['box'][0])
        for item in line:
            # Tag the region with its line index
            # This allows downstream consumers (like MainWindow) to reconstruct line breaks
            item['data']['line_index'] = line_idx
            sorted_regions.append(item['data'])

    return sorted_regions
