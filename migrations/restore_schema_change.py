import yaml
import os

SNAPSHOTS_DIR = "schema_snapshots/week3-document-refinery-extractions"

def restore():
    files = sorted([
        f for f in os.listdir(SNAPSHOTS_DIR)
        if f.endswith(".yaml")
    ])

    if not files:
        print("ERROR: no snapshots found")
        return

    old_path = os.path.join(SNAPSHOTS_DIR, files[0])

    with open(old_path) as f:
        snapshot = yaml.safe_load(f)

    fields = snapshot.get("fields", {})
    restored = []

    # restore processing_time_ms
    if "processing_time_ms" not in fields:
        fields["processing_time_ms"] = {
            "type":        "integer",
            "required":    True,
            "minimum":     1000.0,
            "maximum":     300000.0,
            "description": "Time in milliseconds to process the document"
        }
        restored.append("processing_time_ms")

    # restore extraction_model type
    if "extraction_model" in fields:
        if isinstance(fields["extraction_model"], dict):
            fields["extraction_model"]["type"] = "string"
            restored.append("extraction_model type → string")

    # restore token_count_input range
    if "token_count_input" in fields:
        if isinstance(fields["token_count_input"], dict):
            fields["token_count_input"]["minimum"] = 3000.0
            fields["token_count_input"]["maximum"] = 8000.0
            restored.append("token_count_input range restored")

    # restore is_synthetic
    if "is_synthetic" not in fields:
        fields["is_synthetic"] = {
            "type":        "boolean",
            "required":    False,
            "description": "Flag indicating record was synthetically generated"
        }
        restored.append("is_synthetic")

    # restore doc_name
    if "doc_name" not in fields:
        fields["doc_name"] = {
            "type":        "string",
            "required":    False,
            "description": "Original document name before uuid conversion"
        }
        restored.append("doc_name")

    snapshot["fields"] = fields

    with open(old_path, "w") as f:
        yaml.dump(
            snapshot, f,
            default_flow_style=False,
            allow_unicode=True
        )

    if restored:
        print(f"Restored {len(restored)} fields in {files[0]}:")
        for r in restored:
            print(f"  - {r}")
    else:
        print("Nothing to restore — snapshot already clean")


if __name__ == "__main__":
    restore()