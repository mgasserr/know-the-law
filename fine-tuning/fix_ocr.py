import os
import json
import re

def fix_ocr_cache():
    ocr_dir = os.path.join("data", "ocr")
    if not os.path.exists(ocr_dir):
        print(f"Directory {ocr_dir} not found.")
        return

    for file in os.listdir(ocr_dir):
        if not file.endswith(".jsonl"): 
            continue
            
        path = os.path.join(ocr_dir, file)
        fixed_lines = []
        
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                fixed_text = []
                
                for p_line in record.get("raw_text", "").split('\n'):
                    # 1. Reverse the entire line (restores Arabic RTL reading order)
                    rev = p_line[::-1]
                    # 2. Flip brackets back to their correct orientation
                    rev = rev.translate(str.maketrans('()[]{}<>', ')(][}{><'))
                    # 3. Re-reverse numbers and English words so they read LTR properly
                    rev = re.sub(r'[a-zA-Z0-9]+', lambda m: m.group(0)[::-1], rev)
                    
                    fixed_text.append(rev)
                
                record["raw_text"] = '\n'.join(fixed_text)
                fixed_lines.append(json.dumps(record, ensure_ascii=False))
                
        # Overwrite the cache file with the corrected text
        with open(path, "w", encoding="utf-8") as f:
            f.write('\n'.join(fixed_lines) + '\n')
            
    print("OCR text successfully un-reversed and fixed!")

if __name__ == "__main__":
    fix_ocr_cache()