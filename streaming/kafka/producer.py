import json
import logging
from pathlib import Path
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

log = logging.getLogger(__name__)

ROOT            = Path(__file__).resolve().parents[2]
VIOLATIONS_PATH = ROOT / "violation_log" / "violations.jsonl"
KAFKA_BROKER    = "localhost:9092"
TOPIC           = "violations"


def get_producer() -> KafkaProducer | None:
    """Create and return a KafkaProducer. Returns None if broker unavailable."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=3,
        )
        return producer
    except NoBrokersAvailable:
        log.error("Kafka broker not available at %s", KAFKA_BROKER)
        return None


def load_critical_violations() -> list[dict]:
    """
    Read violations.jsonl and return only CRITICAL severity records.
    Skips injected violations (injection_note: true).
    """
    if not VIOLATIONS_PATH.exists():
        log.warning("violations.jsonl not found at %s", VIOLATIONS_PATH)
        return []

    violations = []
    for line in VIOLATIONS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            record = json.loads(line)
            if (
                record.get("severity") == "CRITICAL"
                and not record.get("injection_note", False)
            ):
                violations.append(record)
        except json.JSONDecodeError:
            continue
    return violations


def format_message(violation: dict) -> dict:
    """
    Flatten a violation record into a clean Kafka message payload.
    Extracts the most useful fields for the Slack consumer.
    """
    # Extract top blame chain entry
    blame = violation.get("blame_chain", [])
    top_blame = blame[0] if blame else {}

    # Extract blast radius
    blast = violation.get("blast_radius", {})
    affected = (
        blast.get("affected_nodes", [])
        or blast.get("registry_subscribers", [])
    )

    return {
        "violation_id":   violation.get("violation_id", "unknown"),
        "check_id":       violation.get("check_id", "unknown"),
        "severity":       violation.get("severity", "UNKNOWN"),
        "message":        violation.get("message", ""),
        "detected_at":    violation.get("detected_at", ""),
        "contract_id":    violation.get("contract_id", ""),
        "blame_commit":   top_blame.get("commit_hash", "unknown")[:8],
        "blame_author":   top_blame.get("author", "unknown"),
        "blame_message":  top_blame.get("commit_message", ""),
        "blame_score":    top_blame.get("confidence_score", 0.0),
        "blast_radius":   affected,
        "records_failing": violation.get("records_failing", 0),
    }


def publish_violations() -> dict:
    """
    Main entry point — called by the Dagster kafka_publish asset.
    Reads CRITICAL violations and publishes each to the Kafka topic.
    Returns a summary dict for Dagster metadata.
    """
    violations = load_critical_violations()

    if not violations:
        log.info("No CRITICAL violations to publish.")
        return {"published": 0, "status": "no_violations"}

    producer = get_producer()
    if producer is None:
        return {"published": 0, "status": "broker_unavailable"}

    published = 0
    failed    = 0

    # Deduplicate by violation_id before publishing
    seen = set()
    for v in violations:
        vid = v.get("violation_id", "")
        if vid in seen:
            continue
        seen.add(vid)

        try:
            msg = format_message(v)
            producer.send(TOPIC, value=msg)
            log.info("Published violation: %s", msg["check_id"])
            published += 1
        except Exception as e:
            log.error("Failed to publish violation %s: %s", vid, e)
            failed += 1

    producer.flush()
    producer.close()

    log.info("Kafka publish complete — %d published, %d failed", published, failed)
    return {
        "published": published,
        "failed":    failed,
        "status":    "complete",
        "topic":     TOPIC,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = publish_violations()
    print(result)