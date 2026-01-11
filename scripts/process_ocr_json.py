import sqlite3
import json
import re
import os
import sys

# Configuration
DB_PATH = 'ocr_data.db'

def create_db(db_path):
    """Create the SQLite database and table if not exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Create table with exactly 4 columns as requested + confidence metadata
    # I will use a table without an explicit ID column (using built-in ROWID) and exactly 4 columns.
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS person_info (
            name TEXT,
            profession TEXT,
            id_card TEXT,
            phone_number TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

def clean_name(text):
    """Col 1: String, Chinese only, no punctuation."""
    if not text: return ""
    # Keep only Chinese characters
    return re.sub(r'[^\u4e00-\u9fa5]', '', text)

def clean_profession(text):
    """Col 2: Chinese characters, punctuation allowed."""
    if not text: return ""
    # User allows punctuation. We just trim whitespace.
    return text.strip()

def clean_id(text):
    """Col 3: 18-digit integer type (allowing X)."""
    if not text: return ""
    # Common OCR fix
    text = text.replace('G', '6').replace('g', '9').replace('l', '1').replace('z', '2')
    # Keep digits and X
    match = re.search(r'\d{17}[\dXx]', text)
    if match:
        return match.group(0)
    return re.sub(r'[^0-9Xx]', '', text)

def clean_phone(text):
    """Col 4: 11-digit integer type."""
    if not text: return ""
    # Keep digits
    match = re.search(r'\d{11}', text)
    if match:
        return match.group(0)
    return re.sub(r'[^0-9]', '', text)

def split_region_text(text):
    """
    Check if a text contains merged fields.
    Especially Profession + ID (e.g., '市政610330...')
    """
    # Pattern for ID inside text
    id_pattern = r'(\d{17}[\dXx])'
    match = re.search(id_pattern, text)
    if match:
        id_str = match.group(1)
        # Split logic
        start, end = match.span()
        # If ID is at the end, previous part is profession
        if start > 0:
            profession_part = text[:start]
            return profession_part, id_str
        # If ID is at start? Unlikely for Prof+ID, but possible for Name+ID?
        # If text is just ID, return None, text
    return None

def is_id_card(text):
    """Check if text matches ID card pattern."""
    t = text.replace('G', '6').replace('g', '9').replace('l', '1').replace('z', '2')
    match = re.search(r'\d{17}[\dXx]', t)
    return bool(match)

def is_phone(text):
    """Check if text matches Phone pattern."""
    match = re.search(r'1[3-9]\d{9}', text)
    return bool(match)

def is_profession_likely(text):
    """Check if text is likely a profession based on keywords or length."""
    keywords = ['工程', '专业', '师', '员', '经理', '市政', '建筑', '水利', '土木', '机电', '公用']
    if any(k in text for k in keywords):
        return True
    return len(text) > 4 # Heuristic: Long strings are likely professions if they are not IDs

def process_json_file(json_path, db_path):
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    print(f"Processing {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    regions = data.get('regions', [])
    if not regions:
        print("No regions found.")
        return

    # 1. Calculate centers
    for r in regions:
        coords = r['coordinates']
        ys = [p[1] for p in coords]
        xs = [p[0] for p in coords]
        r['cy'] = sum(ys) / len(ys)
        r['cx'] = sum(xs) / len(xs)

    # 2. Sort by Y to prepare for clustering
    regions.sort(key=lambda x: x['cy'])

    # 3. Cluster into rows
    rows = []
    current_row = []
    last_y = -1
    # Tightening to 10px to separate rows like "陈二远" and "宋泽梅".
    threshold = 10 

    for r in regions:
        if last_y == -1:
            current_row.append(r)
            last_y = r['cy']
        elif abs(r['cy'] - last_y) < threshold:
            current_row.append(r)
        else:
            rows.append(current_row)
            current_row = [r]
            last_y = r['cy']
    if current_row:
        rows.append(current_row)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    count = 0
    for row in rows:
        # Sort by X
        row.sort(key=lambda x: x['cx'])

        # Pre-process for merged fields (keep existing split_region_text logic)
        expanded_candidates = []
        for r in row:
            split_res = split_region_text(r['text'])
            if split_res:
                # Found merged field (Prof + ID)
                prof_text, id_text = split_res
                expanded_candidates.append({'text': prof_text, 'confidence': r['confidence'], 'cx': r['cx'] - 10})
                expanded_candidates.append({'text': id_text, 'confidence': r['confidence'], 'cx': r['cx'] + 10})
            else:
                expanded_candidates.append(r)
        
        candidates = expanded_candidates
        
        # 4 Slots: Name, Profession, ID, Phone
        slots = ["", "", "", ""] 
        
        # Strategy: Find anchors (ID and Phone) first, as they have strict patterns.
        # This prevents "shifting" of integer types into earlier columns.
        
        # 1. Find ID Card
        id_candidate = None
        for item in candidates[:]: # Iterate copy to allow removal
            if is_id_card(item['text']):
                id_candidate = item
                candidates.remove(item)
                break # Assume one ID per row
        
        if id_candidate:
            slots[2] = id_candidate['text']
            
        # 2. Find Phone
        phone_candidate = None
        for item in candidates[:]:
            if is_phone(item['text']):
                phone_candidate = item
                candidates.remove(item)
                break # Assume one Phone per row
        
        if phone_candidate:
            slots[3] = phone_candidate['text']
            
        # 3. Assign remaining items to Name and Profession
        # Re-sort remaining candidates by X
        candidates.sort(key=lambda x: x['cx'])
        
        if len(candidates) == 0:
            pass
        elif len(candidates) == 1:
            # Decide if Name or Profession
            txt = candidates[0]['text']
            # If we already have Name filled (unlikely), assign to Prof
            # But slots[0] is empty.
            # Heuristics:
            if is_profession_likely(txt):
                slots[1] = txt
            else:
                slots[0] = txt # Default to Name if short/unknown
        else:
            # >= 2 items
            # First item is likely Name
            slots[0] = candidates[0]['text']
            # Join the rest as Profession
            slots[1] = "".join([c['text'] for c in candidates[1:]])

        # Data Cleaning
        name = clean_name(slots[0])
        profession = clean_profession(slots[1])
        id_card = clean_id(slots[2])
        phone = clean_phone(slots[3])
        
        # Validation of empty fields
        if not name and not id_card and not phone:
            continue # Empty row
            
        cursor.execute(
            "INSERT INTO person_info (name, profession, id_card, phone_number) VALUES (?, ?, ?, ?)",
            (name, profession, id_card, phone)
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"Successfully processed {count} rows into database.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Default for this task
        json_file = r'f:\workspace\python\ocr_server\output\个人信息\b53c286f549e7fed1869823b7b1bc63e.json'
    
    create_db(DB_PATH)
    process_json_file(json_file, DB_PATH)
