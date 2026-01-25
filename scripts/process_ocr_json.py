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

def parse_text_content(content):
    """
    Parse full text content using regex to find records.
    Pattern: [Name+Profession] [ID] [Phone]
    We use ID and Phone as anchors.
    """
    records = []
    
    # Regex explanation:
    # (.*?)          : Group 1 - Name and Profession (non-greedy, matches until the ID)
    # (\d{17}[\dXx]) : Group 2 - ID Card (18 digits, last can be X)
    # \s*            : Optional whitespace
    # (1\d{10})      : Group 3 - Phone Number (11 digits, starts with 1)
    #
    # DOTALL flag is NOT used because we want '.' to match everything except newline?
    # Actually, the content might be single line or multi-line. 
    # The sample shows single line. If multi-line, '.*?' matches within line by default.
    # We should normalize newlines to spaces first just in case.
    
    normalized_content = content.replace('\n', ' ').replace('\r', ' ')
    
    # We use findall to get all non-overlapping matches
    pattern = r'(.*?)\s*(\d{17}[\dXx])\s*(1\d{10})'
    matches = re.findall(pattern, normalized_content)
    
    for match in matches:
        raw_info, raw_id, raw_phone = match
        
        # Process raw_info (Name + Profession)
        raw_info = raw_info.strip()
        
        # Split Name and Profession
        # Logic: Name is usually the first token.
        parts = raw_info.split(maxsplit=1)
        if len(parts) == 2:
            name_candidate, prof_candidate = parts
        elif len(parts) == 1:
            name_candidate = parts[0]
            prof_candidate = ""
        else:
            name_candidate = ""
            prof_candidate = ""
            
        # If the "Name" is too long (e.g. > 4 chars) and contains keywords, it might be just profession?
        # But usually there is a name.
        # Let's trust the split for now, but apply cleaning.
        
        # Further cleanup: raw_info might contain the tail of previous garbage if regex matched too loosely?
        # Since we use findall, it consumes the string.
        # Example: "... 15229918786 宋泽梅 市政..."
        # Previous match ended at 18786. Next match starts at " 宋泽梅...".
        # So raw_info will be "宋泽梅 市政...". Split gives "宋泽梅" and "市政...". Looks correct.
        
        # Special case: The very first match might include file header noise if any.
        # But clean_name will strip non-Chinese.
        
        name = clean_name(name_candidate)
        profession = clean_profession(prof_candidate)
        id_card = clean_id(raw_id)
        phone = clean_phone(raw_phone)
        
        if name or id_card or phone:
            records.append({
                'name': name,
                'profession': profession,
                'id_card': id_card,
                'phone': phone
            })
            
    return records

def save_records_to_db(records, db_path):
    """Save parsed records to database with deduplication."""
    if not records:
        return 0
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    count = 0
    for r in records:
        name = r['name']
        profession = r['profession']
        id_card = r['id_card']
        phone = r['phone']
        
        if not id_card:
            # Without ID, we can't reliably dedup or insert as valid record in this strict mode
            continue
            
        # Deduplication Logic
        cursor.execute("SELECT rowid, name, profession, phone_number FROM person_info WHERE id_card = ?", (id_card,))
        existing = cursor.fetchone()
        
        if existing:
            existing_rowid, existing_name, existing_prof, existing_phone = existing
            
            if existing_phone == phone:
                # Phone matches, check if we need to update info
                if existing_name != name or existing_prof != profession:
                    cursor.execute(
                        "UPDATE person_info SET name = ?, profession = ? WHERE rowid = ?",
                        (name, profession, existing_rowid)
                    )
            # If ID exists (matched), we skip insert regardless of whether phone matches or not
            # (as per previous requirement: "杜绝重复录入")
            continue
        
        # Insert new record
        cursor.execute(
            "INSERT INTO person_info (name, profession, id_card, phone_number) VALUES (?, ?, ?, ?)",
            (name, profession, id_card, phone)
        )
        count += 1
        
    conn.commit()
    conn.close()
    return count

def process_file_content(content, file_path, db_path):
    """Process string content and save to DB."""
    records = parse_text_content(content)
    added = save_records_to_db(records, db_path)
    print(f"Processed {file_path}: Found {len(records)} items, Added {added} new records.")
    return added

def process_txt_file(txt_path, db_path):
    """Process a single TXT file."""
    if not os.path.exists(txt_path):
        print(f"File not found: {txt_path}")
        return

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        process_file_content(content, txt_path, db_path)
    except Exception as e:
        print(f"Error processing {txt_path}: {e}")

def process_json_file(json_path, db_path):
    """Process a single JSON file (converts to text first)."""
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        content = ""
        # Priority 1: Use 'full_text' if available
        if 'full_text' in data and data['full_text']:
            content = data['full_text']
        # Priority 2: Construct from regions
        elif 'regions' in data:
            # Sort using intelligent line grouping logic
            regions = data['regions']
            regions = sort_ocr_regions(regions)
            content = " ".join([r.get('text', '') for r in regions])
            
        if content:
            process_file_content(content, json_path, db_path)
        else:
            print(f"No text content found in {json_path}")
            
    except Exception as e:
        print(f"Error processing {json_path}: {e}")

def process_directory(directory_path, db_path):
    """Batch process all JSON and TXT files in directory."""
    if not os.path.exists(directory_path):
        print(f"Directory not found: {directory_path}")
        return
    
    print(f"Scanning directory: {directory_path}")
    files_to_process = []
    
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(('.json', '.txt')):
                files_to_process.append(os.path.join(root, file))
    
    if not files_to_process:
        print("No JSON or TXT files found.")
        return
    
    print(f"Found {len(files_to_process)} files.")
    
    total_added = 0
    for i, file_path in enumerate(files_to_process, 1):
        print(f"\n--- Processing {i}/{len(files_to_process)}: {file_path}")
        if file_path.lower().endswith('.json'):
            # Check db count before/after is handled inside process function? 
            # No, process_file_content returns added count.
            pass
        
        if file_path.lower().endswith('.txt'):
            process_txt_file(file_path, db_path)
        elif file_path.lower().endswith('.json'):
            process_json_file(file_path, db_path)
            
    print(f"\n=== Batch Processing Complete ===")

if __name__ == "__main__":
    # Initialize DB
    create_db(DB_PATH)
    
    # Check arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        
        if os.path.isdir(input_path):
            process_directory(input_path, DB_PATH)
        elif os.path.isfile(input_path):
            if input_path.lower().endswith('.txt'):
                process_txt_file(input_path, DB_PATH)
            elif input_path.lower().endswith('.json'):
                process_json_file(input_path, DB_PATH)
            else:
                print("Unsupported file type. Please provide .json or .txt")
    else:
        # Interactive mode
        print("\n=== OCR Data Processor ===")
        print("Supports JSON and TXT files.")
        print("1. Process single file")
        print("2. Process directory")
        print("3. Exit")
        
        choice = input("\nSelect option (1/2/3): ").strip()
        
        if choice == "1":
            file_path = input("\nEnter file path: ").strip().strip('"').strip("'")
            if os.path.isfile(file_path):
                if file_path.lower().endswith('.txt'):
                    process_txt_file(file_path, DB_PATH)
                elif file_path.lower().endswith('.json'):
                    process_json_file(file_path, DB_PATH)
                else:
                    print("Unsupported file type.")
            else:
                print("File not found.")
                
        elif choice == "2":
            dir_path = input("\nEnter directory path: ").strip().strip('"').strip("'")
            if os.path.isdir(dir_path):
                process_directory(dir_path, DB_PATH)
            else:
                print("Directory not found.")
                
        elif choice == "3":
            print("Exiting.")
        else:
            print("Invalid choice.")
