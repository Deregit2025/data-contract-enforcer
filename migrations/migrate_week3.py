import json
import uuid
import os

# read from your old repo directly
INPUT_PATH  = os.path.expanduser(
    "~/Desktop/Intensive/extractor_ai/.refinery/extractions.jsonl"
)

# write to your new repo
OUTPUT_PATH = "outputs/week3/extractions.jsonl"

DOC_ID_MAP = {}

def get_stable_uuid(doc_name):
    if doc_name not in DOC_ID_MAP:
        DOC_ID_MAP[doc_name] = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_name))
    return DOC_ID_MAP[doc_name]

def fix_extraction_model(model_str):
    if "/" in model_str:
        return model_str.split("/")[-1]
    return model_str

def migrate_record(record):
    original_doc_name      = record["doc_id"]
    record["doc_id"]       = get_stable_uuid(original_doc_name)
    record["doc_name"]     = original_doc_name
    record["extraction_model"] = fix_extraction_model(
        record["extraction_model"]
    )
    return record

def main():
    records = []
    with open(INPUT_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Skipping malformed line: {line[:50]}")

    print(f"Read {len(records)} records")

    os.makedirs("outputs/week3", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for record in migrate_record_list(records):
            f.write(json.dumps(record) + "\n")

    print(f"Written to {OUTPUT_PATH}")

def migrate_record_list(records):
    return [migrate_record(r) for r in records]

if __name__ == "__main__":
    main()