import yaml
import os

SNAPSHOTS_DIR = "schema_snapshots/week3-document-refinery-extractions"

# ─────────────────────────────────────────
# WHAT THIS SCRIPT DOES
# ─────────────────────────────────────────
# Modifies the OLDEST snapshot to simulate
# what the schema looked like BEFORE several
# changes were made. The NEWEST snapshot
# represents the current state.
#
# The analyzer diffs old vs new and detects:
#
# BREAKING changes:
#   1. processing_time_ms — FIELD_REMOVED
#      (was in old, missing in new)
#   2. extraction_model   — TYPE_CHANGED
#      (was integer in old, string in new)
#   3. source_hash        — RANGE_CHANGED
#      (had min/max constraints that changed)
#
# SAFE changes:
#   4. is_synthetic       — FIELD_ADDED optional
#      (missing in old, added in new)
#   5. doc_name           — FIELD_ADDED optional
#      (missing in old, added in new)
# ─────────────────────────────────────────

def inject():
    files = sorted([
        f for f in os.listdir(SNAPSHOTS_DIR)
        if f.endswith(".yaml")
    ])

    if len(files) < 2:
        print("ERROR: need at least 2 snapshots")
        print("Run generator.py twice to create two snapshots")
        return

    old_path = os.path.join(SNAPSHOTS_DIR, files[0])
    new_path = os.path.join(SNAPSHOTS_DIR, files[1])

    print(f"Old snapshot: {files[0]}")
    print(f"New snapshot: {files[1]}")

    with open(old_path) as f:
        old_snapshot = yaml.safe_load(f)

    fields = old_snapshot.get("fields", {})
    if not fields:
        print("ERROR: no fields found in old snapshot")
        return

    changes_made = []

    # ── BREAKING CHANGE 1 ──
    # Remove processing_time_ms from old snapshot
    # New snapshot has it as required=True
    # Analyzer will see FIELD_ADDED required → BREAKING
    if "processing_time_ms" in fields:
        del fields["processing_time_ms"]
        changes_made.append(
            "BREAKING — removed processing_time_ms "
            "(required field added in new snapshot)"
        )

    # ── BREAKING CHANGE 2 ──
    # Change extraction_model type from string to integer
    # in the old snapshot so analyzer sees TYPE_CHANGED
    if "extraction_model" in fields:
        if isinstance(fields["extraction_model"], dict):
            fields["extraction_model"]["type"] = "integer"
            changes_made.append(
                "BREAKING — extraction_model type changed "
                "integer → string (narrowing)"
            )

    # ── BREAKING CHANGE 3 ──
    # Change token_count_input range in old snapshot
    # to simulate a range constraint change
    if "token_count_input" in fields:
        if isinstance(fields["token_count_input"], dict):
            fields["token_count_input"]["minimum"] = 0.0
            fields["token_count_input"]["maximum"] = 1000.0
            changes_made.append(
                "BREAKING — token_count_input range changed "
                "0-1000 → wider range (consumers had tight validation)"
            )

    # ── SAFE CHANGE 1 ──
    # Remove is_synthetic from old snapshot
    # New snapshot has it as optional
    # Analyzer will see FIELD_ADDED optional → SAFE
    if "is_synthetic" in fields:
        del fields["is_synthetic"]
        changes_made.append(
            "SAFE — removed is_synthetic from old "
            "(optional field added in new snapshot)"
        )

    # ── SAFE CHANGE 2 ──
    # Remove doc_name from old snapshot
    # New snapshot has it as optional
    if "doc_name" in fields:
        del fields["doc_name"]
        changes_made.append(
            "SAFE — removed doc_name from old "
            "(optional field added in new snapshot)"
        )

    old_snapshot["fields"] = fields

    with open(old_path, "w") as f:
        yaml.dump(
            old_snapshot, f,
            default_flow_style=False,
            allow_unicode=True
        )

    print(f"\nInjected {len(changes_made)} schema changes into {files[0]}:")
    for i, change in enumerate(changes_made, 1):
        print(f"  {i}. {change}")

    print(f"\nRun schema_analyzer.py to detect them")
    print(f"Run restore_schema_change.py to undo")


if __name__ == "__main__":
    inject()