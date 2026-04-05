import json
import logging
import os
from pathlib import Path
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from slack_sdk.webhook import WebhookClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSUMER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

KAFKA_BROKER      = "localhost:9092"
TOPIC             = "violations"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def format_slack_message(msg: dict) -> list:
    """
    Build a rich Slack Block Kit message from a violation payload.
    Returns a list of blocks for the Slack API.
    """
    blast = msg.get("blast_radius", [])
    blast_str = ", ".join(blast) if blast else "none identified"

    blame_text = (
        f"`{msg['blame_commit']}` by *{msg['blame_author']}*"
        f" — \"{msg['blame_message']}\""
        if msg.get("blame_commit") != "unknown"
        else "No blame chain available"
    )

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 CRITICAL DATA VIOLATION DETECTED",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Contract:*\n`{msg.get('contract_id', 'unknown')}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Severity:*\n🔴 {msg.get('severity', 'UNKNOWN')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Check:*\n`{msg.get('check_id', 'unknown')}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Records Failing:*\n{msg.get('records_failing', 0)} of 100",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Violation Message:*\n{msg.get('message', '')}",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Blamed Commit:*\n{blame_text}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Blast Radius:*\n{blast_str}",
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Detected: {msg.get('detected_at', '')}  |  "
                        f"Violation ID: `{msg.get('violation_id', '')[:8]}...`  |  "
                        f"sentinel-contracts platform"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]


def post_to_slack(msg: dict):
    """Post a formatted violation message to Slack."""
    if not SLACK_WEBHOOK_URL:
        log.error("SLACK_WEBHOOK_URL not set in .env")
        return

    client = WebhookClient(SLACK_WEBHOOK_URL)
    blocks = format_slack_message(msg)

    response = client.send(
        text=f"🚨 CRITICAL violation: {msg.get('check_id', 'unknown')}",
        blocks=blocks,
    )

    if response.status_code == 200:
        log.info("Slack alert sent for: %s", msg.get("check_id"))
    else:
        log.error(
            "Slack post failed — status %s: %s",
            response.status_code,
            response.body,
        )


def start_consumer():
    """
    Run the Kafka consumer loop.
    Listens to the violations topic and posts each message to Slack.
    """
    log.info("Starting Kafka consumer on topic: %s", TOPIC)

    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",   # read from beginning on first run
            enable_auto_commit=True,
            group_id="slack-alert-consumer",
        )
    except NoBrokersAvailable:
        log.error("Kafka broker not available at %s — is Docker running?", KAFKA_BROKER)
        return

    log.info("Consumer ready. Waiting for violations...")

    try:
        for kafka_msg in consumer:
            msg = kafka_msg.value
            log.info(
                "Received violation: %s [%s]",
                msg.get("check_id"),
                msg.get("severity"),
            )
            post_to_slack(msg)
    except KeyboardInterrupt:
        log.info("Consumer stopped by user.")
    finally:
        consumer.close()


if __name__ == "__main__":
    start_consumer()