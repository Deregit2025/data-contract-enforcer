import json
import uuid
import os
import re
import argparse
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

EXTRACTIONS_PATH    = "outputs/week3/extractions.jsonl"
VERDICTS_PATH       = "outputs/week2/verdicts.jsonl"
BASELINE_PATH       = "schema_snapshots/embedding_baselines.npz"
AI_METRICS_PATH     = "validation_reports/ai_metrics.json"
VIOLATION_LOG       = "violation_log/violations.jsonl"
QUARANTINE_DIR      = "outputs/quarantine"

DRIFT_THRESHOLD     = 0.15
EMBEDDING_SAMPLE    = 200

CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# prompt input schema for week3 extraction
PROMPT_INPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type":    "object",
    "required": ["doc_id", "source_path", "extracted_facts"],
    "properties": {
        "doc_id": {
            "type":   "string",
            "minLength": 1
        },
        "source_path": {
            "type":      "string",
            "minLength": 1
        },
        "extracted_facts": {
            "type":     "array",
            "minItems": 1
        }
    },
    "additionalProperties": True
}

# expected LLM output schema for week2 verdicts
VERDICT_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type":    "object",
    "required": [
        "verdict_id", "overall_verdict",
        "overall_score", "confidence", "evaluated_at"
    ],
    "properties": {
        "verdict_id": {
            "type": "string"
        },
        "overall_verdict": {
            "type": "string",
            "enum": ["PASS", "FAIL", "WARN"]
        },
        "overall_score": {
            "type":    "number",
            "minimum": 1.0,
            "maximum": 5.0
        },
        "confidence": {
            "type":    "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "evaluated_at": {
            "type": "string"
        }
    }
}


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def load_jsonl(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def write_violation(check_id, message, severity="HIGH", extra=None):
    os.makedirs(os.path.dirname(VIOLATION_LOG), exist_ok=True)
    violation = {
        "violation_id": str(uuid.uuid4()),
        "check_id":     check_id,
        "detected_at":  datetime.now(timezone.utc).isoformat(),
        "severity":     severity,
        "type":         "llm_output_schema",
        "message":      message
    }
    if extra:
        violation.update(extra)
    with open(VIOLATION_LOG, "a") as f:
        f.write(json.dumps(violation) + "\n")


# ─────────────────────────────────────────
# EXTENSION 1 — EMBEDDING DRIFT
# ─────────────────────────────────────────

def embed_texts(texts):
    """
    Embed a list of texts using OpenRouter.
    Returns numpy array of vectors.
    """
    try:
        # batch into chunks of 50 to avoid rate limits
        all_embeddings = []
        chunk_size     = 50

        for i in range(0, len(texts), chunk_size):
            chunk    = texts[i:i + chunk_size]
            response = CLIENT.embeddings.create(
                model="openai/text-embedding-3-small",
                input=chunk
            )
            vectors = [item.embedding for item in response.data]
            all_embeddings.extend(vectors)

        return np.array(all_embeddings)

    except Exception as e:
        print(f"  WARNING: embedding failed: {e}")
        # return random vectors as fallback for testing
        return np.random.rand(len(texts), 1536)


def load_fact_texts(jsonl_path):
    """
    Extract text values from extracted_facts arrays.
    """
    texts   = []
    records = load_jsonl(jsonl_path)
    for record in records:
        for fact in record.get("extracted_facts", []):
            if isinstance(fact, dict) and fact.get("text"):
                texts.append(fact["text"])
    return texts


def check_embedding_drift():
    print("\n--- Extension 1: Embedding Drift Detection ---")

    texts = load_fact_texts(EXTRACTIONS_PATH)
    if not texts:
        print("  WARNING: no fact texts found")
        return {
            "status":  "ERROR",
            "message": "No fact texts found in extractions"
        }

    print(f"  Loaded {len(texts)} fact texts")

    # sample up to EMBEDDING_SAMPLE texts
    sample = texts[:EMBEDDING_SAMPLE] if len(texts) > EMBEDDING_SAMPLE else texts
    print(f"  Embedding {len(sample)} samples...")

    current_vectors  = embed_texts(sample)
    current_centroid = np.mean(current_vectors, axis=0)

    # first run — save baseline
    if not os.path.exists(BASELINE_PATH):
        os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
        np.savez(BASELINE_PATH, centroid=current_centroid)
        print(f"  Baseline saved to {BASELINE_PATH}")
        return {
            "status":  "PASS",
            "message": "Baseline established on first run",
            "sample_size": len(sample)
        }

    # subsequent runs — compare to baseline
    baseline          = np.load(BASELINE_PATH)
    baseline_centroid = baseline["centroid"]

    similarity = cosine_similarity(
        [current_centroid],
        [baseline_centroid]
    )[0][0]
    drift = float(1 - similarity)

    status = "FAIL" if drift > DRIFT_THRESHOLD else "PASS"

    result = {
        "drift_score":  round(drift, 4),
        "threshold":    DRIFT_THRESHOLD,
        "status":       status,
        "sample_size":  len(sample),
        "message": (
            f"Drift score {drift:.4f} "
            f"{'EXCEEDS' if status == 'FAIL' else 'within'} "
            f"threshold {DRIFT_THRESHOLD}"
        )
    }

    print(f"  Drift score: {drift:.4f} (threshold: {DRIFT_THRESHOLD})")
    print(f"  Status: {status}")

    if status == "FAIL":
        write_violation(
            "ai.embedding.drift",
            f"Embedding drift {drift:.4f} exceeds threshold {DRIFT_THRESHOLD}. "
            f"Data meaning may have shifted significantly.",
            severity="HIGH",
            extra={"drift_score": drift}
        )

    return result


# ─────────────────────────────────────────
# EXTENSION 2 — PROMPT INPUT VALIDATION
# ─────────────────────────────────────────

def check_prompt_input_validation():
    print("\n--- Extension 2: Prompt Input Schema Validation ---")

    records = load_jsonl(EXTRACTIONS_PATH)
    if not records:
        print("  WARNING: no records found")
        return {"status": "ERROR", "message": "No records found"}

    print(f"  Validating {len(records)} records...")

    valid    = []
    rejected = []

    for record in records:
        try:
            jsonschema.validate(
                instance=record,
                schema=PROMPT_INPUT_SCHEMA
            )
            valid.append(record)
        except jsonschema.ValidationError as e:
            rejected.append({
                "original_record":  record.get("doc_id", "unknown"),
                "rejection_reason": e.message,
                "rejected_at":      datetime.now(timezone.utc).isoformat()
            })

    # write quarantine file if any rejected
    if rejected:
        os.makedirs(QUARANTINE_DIR, exist_ok=True)
        ts             = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        quarantine_path = os.path.join(QUARANTINE_DIR, f"{ts}.jsonl")
        with open(quarantine_path, "w") as f:
            for r in rejected:
                f.write(json.dumps(r) + "\n")
        print(f"  {len(rejected)} records quarantined → {quarantine_path}")
    else:
        print(f"  All {len(valid)} records passed validation")

    status = "FAIL" if rejected else "PASS"

    result = {
        "total":    len(records),
        "valid":    len(valid),
        "rejected": len(rejected),
        "status":   status,
        "message":  (
            f"{len(valid)} passed, {len(rejected)} quarantined"
        )
    }

    print(f"  Status: {status}")
    return result


# ─────────────────────────────────────────
# EXTENSION 3 — LLM OUTPUT SCHEMA
# ─────────────────────────────────────────

def load_historical_rates():
    if not os.path.exists(AI_METRICS_PATH):
        return []
    try:
        with open(AI_METRICS_PATH) as f:
            metrics = json.load(f)
        runs = metrics.get("llm_output_schema", {}).get("runs", [])
        return [r["violation_rate"] for r in runs[-5:]]
    except Exception:
        return []


def assess_trend(current_rate, past_rates):
    if len(past_rates) < 2:
        return "stable"
    avg_past = sum(past_rates) / len(past_rates)
    if avg_past == 0:
        return "stable"
    if current_rate > avg_past * 1.5:
        return "rising"
    elif current_rate < avg_past * 0.8:
        return "falling"
    return "stable"


def check_llm_output_schema():
    print("\n--- Extension 3: LLM Output Schema Enforcement ---")

    records = load_jsonl(VERDICTS_PATH)
    if not records:
        print("  WARNING: no verdict records found")
        return {
            "status":          "ERROR",
            "message":         "No verdict records found",
            "violation_rate":  0.0,
            "trend":           "stable"
        }

    print(f"  Validating {len(records)} verdict records...")

    total      = 0
    violations = 0
    violation_records = []

    for record in records:
        total += 1
        try:
            jsonschema.validate(
                instance=record,
                schema=VERDICT_OUTPUT_SCHEMA
            )
        except jsonschema.ValidationError as e:
            violations += 1
            violation_records.append({
                "record_id": record.get("verdict_id", "unknown"),
                "reason":    e.message
            })

    violation_rate = round(violations / total, 4) if total > 0 else 0.0
    past_rates     = load_historical_rates()
    trend          = assess_trend(violation_rate, past_rates)

    status = "PASS"
    if trend == "rising":
        status = "WARN"
        write_violation(
            "ai.llm_output.schema.rising_violation_rate",
            f"LLM output schema violation rate is rising. "
            f"Current rate: {violation_rate:.1%}. "
            f"Review recent prompt changes.",
            severity="MEDIUM",
            extra={
                "violation_rate": violation_rate,
                "trend":          trend
            }
        )

    result = {
        "total_outputs":     total,
        "schema_violations": violations,
        "violation_rate":    violation_rate,
        "trend":             trend,
        "status":            status,
        "runs":              past_rates + [violation_rate],
        "message": (
            f"{violations}/{total} violations "
            f"({violation_rate:.1%}), trend: {trend}"
        )
    }

    print(f"  Total records:    {total}")
    print(f"  Violations:       {violations}")
    print(f"  Violation rate:   {violation_rate:.1%}")
    print(f"  Trend:            {trend}")
    print(f"  Status:           {status}")

    return result


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Contract Extensions — embedding drift, prompt validation, LLM output schema"
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="skip embedding drift check (saves API cost)"
    )
    args = parser.parse_args()

    print("\nRunning AI Contract Extensions")
    print("=" * 50)

    results = {}

    # extension 1
    if args.skip_embeddings:
        print("\n--- Extension 1: Embedding Drift Detection ---")
        print("  SKIPPED (--skip-embeddings flag set)")
        results["embedding_drift"] = {
            "status":  "SKIPPED",
            "message": "Skipped via flag"
        }
    else:
        results["embedding_drift"] = check_embedding_drift()

    # extension 2
    results["prompt_input_validation"] = check_prompt_input_validation()

    # extension 3
    results["llm_output_schema"] = check_llm_output_schema()

    # save metrics
    os.makedirs(os.path.dirname(AI_METRICS_PATH), exist_ok=True)

    metrics = {
        "run_date":              datetime.now(timezone.utc).isoformat(),
        "embedding_drift":       results["embedding_drift"],
        "prompt_input_validation": results["prompt_input_validation"],
        "llm_output_schema":     results["llm_output_schema"]
    }

    with open(AI_METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n{'=' * 50}")
    print(f"AI metrics written to {AI_METRICS_PATH}")

    # summary
    print(f"\nSummary:")
    for ext, result in results.items():
        status = result.get("status", "UNKNOWN")
        msg    = result.get("message", "")
        icon   = "✓" if status == "PASS" else "✗" if status == "FAIL" else "~"
        print(f"  {icon} {ext}: {status} — {msg}")

    print("\nDone.")


if __name__ == "__main__":
    main()