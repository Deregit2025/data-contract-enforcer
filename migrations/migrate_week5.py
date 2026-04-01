import json
import uuid
import os

INPUT_PATH  = os.path.expanduser(
    "~/Desktop/Intensive/ledger/data/seed_events.jsonl"
)
OUTPUT_PATH = "outputs/week5/events.jsonl"

SEQUENCE_COUNTERS = {}

def get_next_sequence(aggregate_id):
    if aggregate_id not in SEQUENCE_COUNTERS:
        SEQUENCE_COUNTERS[aggregate_id] = 0
    SEQUENCE_COUNTERS[aggregate_id] += 1
    return SEQUENCE_COUNTERS[aggregate_id]

def stream_id_to_uuid(stream_id):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, stream_id))

def migrate_record(record):
    stream_id = record.pop("stream_id")

    return {
        "event_id":        str(uuid.uuid4()),
        "event_type":      record["event_type"],
        "aggregate_id":    stream_id_to_uuid(stream_id),
        "aggregate_type":  "LoanApplication",
        "sequence_number": get_next_sequence(
                               stream_id_to_uuid(stream_id)
                           ),
        "payload":         record["payload"],
        "metadata": {
            "causation_id":   None,
            "correlation_id": str(uuid.uuid4()),
            "user_id":        record["payload"].get(
                                  "applicant_id", "system"
                              ),
            "source_service": "week5-event-sourcing-platform"
        },
        "schema_version":  str(record.get("event_version", "1.0")),
        "occurred_at":     record["recorded_at"],
        "recorded_at":     record["recorded_at"],
        "stream_id":       stream_id
    }

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

    os.makedirs("outputs/week5", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for record in records:
            f.write(json.dumps(migrate_record(record)) + "\n")

    print(f"Written to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()