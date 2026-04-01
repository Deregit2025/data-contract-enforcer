import json
import os
import shutil
from datetime import datetime, timezone

DATA_PATH   = "outputs/week3/extractions.jsonl"
BACKUP_PATH = "outputs/week3/extractions_clean.jsonl"

# document the injection at the top of the violation log
INJECTION_NOTE = (
    "# INJECTED VIOLATION: confidence values in extracted_facts "
    "scaled from 0.0-1.0 to 0-100 to simulate a breaking change. "
    "Injected to demonstrate statistical drift detection and range "
    "check failure. Original clean data preserved in "
    "outputs/week3/extractions_clean.jsonl"
)

def inject():
    if not os.path.exists(DATA_PATH):
        print(f"ERROR: {DATA_PATH} not found")
        return

    # step 1 — backup clean file
    shutil.copy(DATA_PATH, BACKUP_PATH)
    print(f"Clean backup saved to {BACKUP_PATH}")

    # step 2 — load records
    records = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Loaded {len(records)} records")

    # step 3 — corrupt confidence values
    corrupted_facts = 0
    for record in records:
        for fact in record.get("extracted_facts", []):
            if isinstance(fact, dict) and "confidence" in fact:
                # scale from 0.0-1.0 to 0-100
                fact["confidence"] = round(
                    fact["confidence"] * 100, 1
                )
                corrupted_facts += 1

    print(f"Corrupted {corrupted_facts} confidence values")
    print(f"Example: 0.87 → 87.0, 0.92 → 92.0")

    # step 4 — write corrupted file
    with open(DATA_PATH, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Violation injected into {DATA_PATH}")
    print(f"Run runner.py to detect it")
    print(f"Run restore_violation.py to undo")

if __name__ == "__main__":
    inject()