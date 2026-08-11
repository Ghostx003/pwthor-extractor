import json
import os

def flush_files():
    # File paths (relative to the root directory where the script is executed)
    download_mapping = "download_mapping.json"
    link_saver = "link_saver.json"
    
    print("========================================")
    print("           FLUSHING JSON FILES          ")
    print("========================================")
    
    # Flush download_mapping.json
    try:
        with open(download_mapping, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
        print(f"[OK] Flushed {download_mapping}")
    except Exception as e:
        print(f"[ERROR] Failed to flush {download_mapping}: {e}")
        
    # Flush link_saver.json
    try:
        with open(link_saver, "w", encoding="utf-8") as f:
            json.dump({"videos": []}, f, indent=4)
        print(f"[OK] Flushed {link_saver}")
    except Exception as e:
        print(f"[ERROR] Failed to flush {link_saver}: {e}")
        
    print("========================================")
    print("          FLUSH COMPLETE                ")
    print("========================================")

if __name__ == "__main__":
    flush_files()
