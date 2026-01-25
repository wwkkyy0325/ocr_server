# -*- coding: utf-8 -*-

def sort_ocr_regions(regions):
    """
    Sort text regions from top to bottom, left to right.
    Uses a robust visual line grouping approach.
    
    Args:
        regions: List of dicts, each containing 'coordinates' (polygon points) 
                 and optionally 'text', 'confidence', etc.
                 
    Returns:
        List of sorted regions.
    """
    if not regions:
        return []

    # 1. Compute bounding boxes for all regions
    items = []
    for r in regions:
        poly = r.get('coordinates', [])
        
        # If no coordinates, try 'box' [x1, y1, x2, y2]
        is_poly_empty = poly is None or len(poly) == 0
        if is_poly_empty and 'box' in r:
            box = r['box']
            if box is not None and len(box) > 0:
                # Convert box to poly for consistency if needed, or just use box
                items.append({'box': box, 'data': r})
            continue
            
        if poly is None or len(poly) == 0:
            continue
        
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        if not xs or not ys:
            continue
            
        box = [min(xs), min(ys), max(xs), max(ys)]
        items.append({'box': box, 'data': r})

    if not items:
        return []

    # 2. Sort by Top Y primarily
    items.sort(key=lambda x: x['box'][1])

    # 3. Group into lines
    lines = []
    current_line = []

    for item in items:
        if not current_line:
            current_line.append(item)
            continue

        # Anchor is the first item in the current line (sorted by Top Y)
        anchor = current_line[0]
        box_anchor = anchor['box']
        box_item = item['box']

        # Calculate vertical overlap to determine if items are on the same line
        y1_anchor, y2_anchor = box_anchor[1], box_anchor[3]
        y1_item, y2_item = box_item[1], box_item[3]
        
        overlap = max(0, min(y2_anchor, y2_item) - max(y1_anchor, y1_item))
        h_anchor = y2_anchor - y1_anchor
        h_item = y2_item - y1_item
        
        # Use the smaller height to handle different font sizes on the same line
        # (e.g. Title and Chapter Number). 
        # Requirement: Significant vertical overlap (> 40% of the smaller item).
        min_h = min(h_anchor, h_item)
        if min_h > 0 and overlap > min_h * 0.4:
            current_line.append(item)
        else:
            lines.append(current_line)
            current_line = [item]

    if current_line:
        lines.append(current_line)

    # 4. Sort each line by Left X and flatten
    sorted_regions = []
    for line in lines:
        line.sort(key=lambda x: x['box'][0])
        for item in line:
            sorted_regions.append(item['data'])

    return sorted_regions
