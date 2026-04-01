import os
import shutil

DATA_PATH   = "outputs/week3/extractions.jsonl"
BACKUP_PATH = "outputs/week3/extractions_clean.jsonl"

def restore():
    if not os.path.exists(BACKUP_PATH):
        print(f"ERROR: backup not found at {BACKUP_PATH}")
        print("Cannot restore — no backup exists")
        return

    shutil.copy(BACKUP_PATH, DATA_PATH)
    print(f"Clean data restored to {DATA_PATH}")
    print(f"Backup preserved at {BACKUP_PATH}")

if __name__ == "__main__":
    restore()