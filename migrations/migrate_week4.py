import json
import os

INPUT_PATH  = r"C:\Users\derej\Desktop\Intensive\cartographer\.cartography\lineage_snapshots.jsonl"
OUTPUT_PATH = "outputs/week4/lineage_snapshots.jsonl"

def migrate():
    snapshots = []
    with open(INPUT_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    snapshots.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Skipping malformed line")

    print(f"Read {len(snapshots)} snapshots")

    os.makedirs("outputs/week4", exist_ok=True)

    with open(OUTPUT_PATH, "w") as f:
        for snapshot in snapshots:
            # collect valid node_ids for this snapshot
            valid_node_ids = {
                node["node_id"]
                for node in snapshot.get("nodes", [])
            }

            # filter broken edges
            original  = snapshot.get("edges", [])
            clean     = [
                e for e in original
                if e["source"] in valid_node_ids
                and e["target"] in valid_node_ids
            ]
            removed   = len(original) - len(clean)
            snapshot["edges"] = clean

            print(f"  Snapshot {snapshot['snapshot_id'][:8]}...")
            print(f"    Nodes: {len(valid_node_ids)}")
            print(f"    Edges: {len(original)} → {len(clean)} ({removed} removed)")

            f.write(json.dumps(snapshot) + "\n")

    print(f"Written to {OUTPUT_PATH}")

if __name__ == "__main__":
    migrate()