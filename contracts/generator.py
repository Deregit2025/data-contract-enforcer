
from dotenv import load_dotenv
load_dotenv()

import json
import uuid
import os
import re
import hashlib
import argparse
import yaml
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np
from ydata_profiling import ProfileReport
from openai import OpenAI

ANTHROPIC_CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

LINEAGE_PATH     = "outputs/week4/lineage_snapshots.jsonl"
SNAPSHOTS_DIR    = "schema_snapshots"
CONTRACTS_DIR    = "generated_contracts"
BASELINES_PATH   = "schema_snapshots/baselines.json"


LINEAGE_CONSUMERS = {
    "week3-document-refinery-extractions": [
        {
            "id":          "week4-cartographer",
            "description": "Cartographer ingests doc_id and extracted_facts as node metadata",
            "fields_consumed":     ["doc_id", "extracted_facts", "extraction_model"],
            "breaking_if_changed": ["extracted_facts.confidence", "doc_id"]
        }
    ],
    "week5-event-sourcing-platform": [
        {
            "id":          "week8-contract-enforcer",
            "description": "Enforcer validates event payloads against registered schemas",
            "fields_consumed":     ["event_type", "payload", "sequence_number"],
            "breaking_if_changed": ["event_type", "sequence_number"]
        }
    ]
}


# ─────────────────────────────────────────
# NUMPY SAFE CONVERTER
# ─────────────────────────────────────────

def numpy_safe(obj):
    """
    Recursively convert numpy types to plain Python types
    so yaml.dump does not write numpy-specific tags.
    """
    if isinstance(obj, dict):
        return {k: numpy_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [numpy_safe(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj


# ─────────────────────────────────────────
# STEP 1 — STRUCTURAL PROFILING
# ─────────────────────────────────────────

def load_jsonl(path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def flatten_records(records):
    flat = []
    for r in records:
        row = {}
        for key, value in r.items():
            if isinstance(value, list):
                row[f"{key}_count"] = len(value)
                if value and isinstance(value[0], dict):
                    for sub_key in value[0].keys():
                        vals = [
                            item[sub_key]
                            for item in value
                            if isinstance(item, dict)
                            and sub_key in item
                            and isinstance(item[sub_key], (int, float))
                        ]
                        if vals:
                            row[f"{key}_{sub_key}_mean"] = np.mean(vals)
                            row[f"{key}_{sub_key}_min"]  = np.min(vals)
                            row[f"{key}_{sub_key}_max"]  = np.max(vals)
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, (int, float, str, bool)):
                        row[f"{key}_{sub_key}"] = sub_val
            else:
                row[key] = value
        flat.append(row)
    return pd.DataFrame(flat)


def structural_profile(df):
    profile = {}
    for col in df.columns:
        col_data  = df[col].dropna()
        samples   = col_data.head(5).tolist()
        null_frac = round(float(df[col].isnull().mean()), 4)
        cardin    = int(df[col].nunique())

        pattern = None
        if df[col].dtype == object:
            uuid_pattern = re.compile(
                r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            )
            sha_pattern  = re.compile(r'^[0-9a-f]{64}$')
            iso_pattern  = re.compile(r'^\d{4}-\d{2}-\d{2}T')

            str_samples = col_data.astype(str).head(20).tolist()
            if all(uuid_pattern.match(s) for s in str_samples):
                pattern = "uuid-v4"
            elif all(sha_pattern.match(s) for s in str_samples):
                pattern = "sha256"
            elif all(iso_pattern.match(s) for s in str_samples):
                pattern = "iso8601"

        profile[col] = {
            "dtype":         str(df[col].dtype),
            "null_fraction": null_frac,
            "cardinality":   cardin,
            "samples":       [numpy_safe(s) for s in samples],
            "pattern":       pattern
        }
    return profile


# ─────────────────────────────────────────
# STEP 2 — STATISTICAL PROFILING
# ─────────────────────────────────────────

def statistical_profile(df):
    stats        = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) == 0:
            continue

        col_stats = {
            "min":    round(float(col_data.min()),  4),
            "max":    round(float(col_data.max()),  4),
            "mean":   round(float(col_data.mean()), 4),
            "stddev": round(float(col_data.std()),  4),
            "p25":    round(float(col_data.quantile(0.25)), 4),
            "p50":    round(float(col_data.quantile(0.50)), 4),
            "p75":    round(float(col_data.quantile(0.75)), 4),
            "p95":    round(float(col_data.quantile(0.95)), 4),
            "p99":    round(float(col_data.quantile(0.99)), 4),
        }

        if "confidence" in col.lower():
            if col_stats["max"] > 1.0:
                col_stats["flag"] = "POSSIBLE_SCALE_VIOLATION — max > 1.0"
            elif col_stats["mean"] > 0.99:
                col_stats["flag"] = "POSSIBLE_CLAMPED — mean > 0.99"
            elif col_stats["mean"] < 0.01:
                col_stats["flag"] = "POSSIBLE_BROKEN — mean < 0.01"
            else:
                col_stats["flag"] = "OK"

        stats[col] = col_stats

    return stats


# ─────────────────────────────────────────
# STEP 3 — LINEAGE CONTEXT INJECTION
# ─────────────────────────────────────────

def load_lineage_consumers(contract_id):
    if os.path.exists(LINEAGE_PATH):
        try:
            import networkx as nx
            snapshots = []
            with open(LINEAGE_PATH) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        snapshots.append(json.loads(line))

            if snapshots:
                latest = sorted(
                    snapshots,
                    key=lambda s: s.get("captured_at", "")
                )[-1]

                G = nx.DiGraph()
                for node in latest.get("nodes", []):
                    G.add_node(node["node_id"], **node.get("metadata", {}))
                for edge in latest.get("edges", []):
                    G.add_edge(
                        edge["source"],
                        edge["target"],
                        relationship=edge.get("relationship", "")
                    )

                downstream = []
                for node_id in G.nodes():
                    if contract_id.split("-")[0] in node_id.lower():
                        for descendant in nx.descendants(G, node_id):
                            downstream.append({
                                "id":                  descendant,
                                "description":         "downstream consumer from lineage graph",
                                "fields_consumed":     [],
                                "breaking_if_changed": []
                            })
                if downstream:
                    return downstream
        except Exception as e:
            print(f"Lineage graph load failed: {e} — using defaults")

    return LINEAGE_CONSUMERS.get(contract_id, [])


# ─────────────────────────────────────────
# STEP 4 — LLM ANNOTATION
# ─────────────────────────────────────────

def llm_annotate_column(col_name, table_name, samples, adjacent_cols):
    try:
        prompt = f"""You are a data contract expert.
Given this column information, provide annotations.

Column name: {col_name}
Table: {table_name}
Sample values: {samples}
Adjacent columns: {adjacent_cols}

Respond with ONLY a JSON object — no explanation, no markdown:
{{
  "description": "plain English meaning of this column",
  "business_rule": "a validation expression e.g. value must be positive integer",
  "cross_column_relationship": "any dependency on other columns or null"
}}"""

        response = ANTHROPIC_CLIENT.chat.completions.create(
            model="anthropic/claude-sonnet-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)

    except Exception as e:
        return {
            "description":               f"Column {col_name} in {table_name}",
            "business_rule":             "no rule inferred",
            "cross_column_relationship": None
        }


def should_annotate(col_name, profile):
    obvious_patterns = ["uuid", "sha256", "iso8601"]
    obvious_names    = [
        "doc_id", "fact_id", "entity_id", "event_id",
        "extracted_at", "recorded_at", "occurred_at",
        "processing_time_ms", "source_path", "source_hash"
    ]
    if col_name in obvious_names:
        return False
    if profile.get("pattern") in obvious_patterns:
        return False
    return True


# ─────────────────────────────────────────
# STEP 5 — WRITE YAML + DBT OUTPUT
# ─────────────────────────────────────────

def build_contract(
    contract_id, title, source_path,
    struct_profile, stat_profile,
    downstream_consumers, llm_annotations, records
):
    schema = {}
    for col, info in struct_profile.items():
        field = {
            "description": llm_annotations.get(col, {}).get(
                "description", f"Column {col}"
            )
        }

        dtype = info["dtype"]
        if "int" in dtype:
            field["type"] = "integer"
        elif "float" in dtype:
            field["type"] = "number"
        elif "bool" in dtype:
            field["type"] = "boolean"
        else:
            field["type"] = "string"

        # doc_id is not globally unique — same doc can be processed multiple times
        NON_UNIQUE_UUID_FIELDS = ["doc_id", "aggregate_id"]
        if info.get("pattern") == "uuid-v4" and col not in NON_UNIQUE_UUID_FIELDS:
            field["format"] = "uuid"
        elif info.get("pattern") == "sha256":
            field["pattern"] = "^[a-f0-9]{64}$"
        elif info.get("pattern") == "iso8601":
            field["format"] = "date-time"

        field["required"] = bool(info["null_fraction"] == 0.0)

        if col in stat_profile:
            s = stat_profile[col]
            if "confidence" in col.lower():
                field["minimum"] = 0.0
                field["maximum"] = 1.0
            else:
                field["minimum"] = float(s["min"])
                field["maximum"] = float(s["max"])

        rule = llm_annotations.get(col, {}).get("business_rule")
        if rule and rule != "no rule inferred":
            field["business_rule"] = rule

        schema[col] = field

    checks = ["row_count >= 1"]
    for col, info in struct_profile.items():
        if info["null_fraction"] == 0.0:
            checks.append(f"missing_count({col}) = 0")
        if info.get("pattern") == "uuid-v4":
            checks.append(f"duplicate_count({col}) = 0")
    if "extracted_facts_confidence_min" in struct_profile:
        checks.append("min(extracted_facts_confidence_min) >= 0.0")
        checks.append("max(extracted_facts_confidence_max) <= 1.0")

    contract = {
        "kind":       "DataContract",
        "apiVersion": "v3.0.0",
        "id":         contract_id,
        "info": {
            "title":       title,
            "version":     "1.0.0",
            "owner":       contract_id.split("-")[0],
            "description": (
                f"Auto-generated contract for {title}. "
                f"Generated at {datetime.now(timezone.utc).isoformat()}."
            )
        },
        "servers": {
            "local": {
                "type":   "local",
                "path":   source_path,
                "format": "jsonl"
            }
        },
        "terms": {
            "usage":       "Internal inter-system data contract.",
            "limitations": "Do not modify field types without updating downstream consumers."
        },
        "schema":  schema,
        "quality": {
            "type": "SodaChecks",
            "specification": {
                f"checks for {contract_id}": checks
            }
        },
        "lineage": {
            "upstream":   [],
            "downstream": downstream_consumers
        }
    }

    if stat_profile:
        contract["statistics"] = stat_profile

    if llm_annotations:
        contract["llm_annotations"] = llm_annotations

    return contract


def build_dbt_schema(contract_id, title, struct_profile, stat_profile):
    columns = []
    for col, info in struct_profile.items():
        tests     = []
        col_entry = {"name": col, "tests": tests}

        if info["null_fraction"] == 0.0:
            tests.append("not_null")

        if info.get("pattern") == "uuid-v4":
            tests.append("unique")

        if col == "overall_verdict":
            tests.append({
                "accepted_values": {
                    "values": ["PASS", "FAIL", "WARN"]
                }
            })

        if col in ("type", "entity_type"):
            tests.append({
                "accepted_values": {
                    "values": [
                        "PERSON", "ORG", "LOCATION",
                        "DATE", "AMOUNT", "OTHER"
                    ]
                }
            })

        if "confidence" in col.lower() and col in stat_profile:
            tests.append({
                "dbt_utils.accepted_range": {
                    "min_value": 0.0,
                    "max_value": 1.0
                }
            })

        columns.append(col_entry)

    return {
        "version": 2,
        "models": [
            {
                "name":        contract_id.replace("-", "_"),
                "description": title,
                "columns":     columns
            }
        ]
    }


def save_schema_snapshot(contract_id, schema):
    snapshot_dir  = os.path.join(SNAPSHOTS_DIR, contract_id)
    os.makedirs(snapshot_dir, exist_ok=True)

    timestamp     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    snapshot_path = os.path.join(snapshot_dir, f"{timestamp}.yaml")

    snapshot = {
        "snapshot_id": contract_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "fields":      numpy_safe(schema)
    }

    with open(snapshot_path, "w") as f:
        yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True)

    print(f"  Snapshot saved: {snapshot_path}")


def save_baselines(contract_id, stat_profile):
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

    baselines = {}
    if os.path.exists(BASELINES_PATH):
        with open(BASELINES_PATH) as f:
            baselines = json.load(f)

    if contract_id not in baselines:
        baselines[contract_id] = {}

    for col, stats in stat_profile.items():
        if col not in baselines[contract_id]:
            baselines[contract_id][col] = {
                "mean":   float(stats["mean"]),
                "stddev": float(stats["stddev"]),
                "min":    float(stats["min"]),
                "max":    float(stats["max"])
            }
            print(f"  Baseline saved for {col}")

    with open(BASELINES_PATH, "w") as f:
        json.dump(baselines, f, indent=2)


# ─────────────────────────────────────────
# CONTRACT CONFIGS
# ─────────────────────────────────────────

CONTRACT_CONFIGS = {
    "outputs/week3/extractions.jsonl": {
        "contract_id": "week3-document-refinery-extractions",
        "title":       "Week 3 Document Refinery — Extraction Records"
    },
    "outputs/week5/events.jsonl": {
        "contract_id": "week5-event-sourcing-platform",
        "title":       "Week 5 Event Sourcing Platform — Event Records"
    },
    "outputs/week1/intent_records.jsonl": {
        "contract_id": "week1-intent-code-correlator",
        "title":       "Week 1 Intent Code Correlator — Intent Records"
    },
    "outputs/week2/verdicts.jsonl": {
        "contract_id": "week2-digital-courtroom",
        "title":       "Week 2 Digital Courtroom — Verdict Records"
    },
    "outputs/week4/lineage_snapshots.jsonl": {
        "contract_id": "week4-brownfield-cartographer",
        "title":       "Week 4 Brownfield Cartographer — Lineage Snapshots"
    },
    "outputs/traces/runs.jsonl": {
        "contract_id": "langsmith-traces",
        "title":       "LangSmith Trace Records — Week 3 Extraction Runs"
    },
}


def process_source(source_path, output_dir):
    if source_path not in CONTRACT_CONFIGS:
        stem        = Path(source_path).stem
        contract_id = stem.replace("_", "-")
        title       = stem.replace("_", " ").title()
    else:
        contract_id = CONTRACT_CONFIGS[source_path]["contract_id"]
        title       = CONTRACT_CONFIGS[source_path]["title"]

    print(f"\nProcessing: {source_path}")
    print(f"  Contract ID: {contract_id}")

    records = load_jsonl(source_path)
    if not records:
        print(f"  ERROR: no records found in {source_path}")
        return

    print(f"  Loaded {len(records)} records")

    df             = flatten_records(records)
    struct_profile = structural_profile(df)
    print(f"  Structural profile: {len(struct_profile)} columns")

    stat_profile = statistical_profile(df)
    print(f"  Statistical profile: {len(stat_profile)} numeric columns")

    downstream = load_lineage_consumers(contract_id)
    print(f"  Downstream consumers: {len(downstream)}")

    cols        = list(struct_profile.keys())
    annotations = {}
    for i, col in enumerate(cols):
        if should_annotate(col, struct_profile[col]):
            adjacent = cols[max(0, i-2): i] + cols[i+1: i+3]
            print(f"  Annotating column: {col}")
            annotations[col] = llm_annotate_column(
                col, title,
                struct_profile[col]["samples"],
                adjacent
            )
    print(f"  LLM annotations: {len(annotations)} columns")

    contract = build_contract(
        contract_id, title, source_path,
        struct_profile, stat_profile,
        downstream, annotations, records
    )

    os.makedirs(output_dir, exist_ok=True)

    contract_filename = contract_id.replace("-", "_") + ".yaml"
    contract_path     = os.path.join(output_dir, contract_filename)

    with open(contract_path, "w") as f:
        yaml.dump(
            numpy_safe(contract),
            f,
            default_flow_style=False,
            allow_unicode=True
        )
    print(f"  Contract written: {contract_path}")

    dbt_schema   = build_dbt_schema(
        contract_id, title, struct_profile, stat_profile
    )
    dbt_filename = contract_id.replace("-", "_") + "_dbt.yml"
    dbt_path     = os.path.join(output_dir, dbt_filename)

    with open(dbt_path, "w") as f:
        yaml.dump(
            numpy_safe(dbt_schema),
            f,
            default_flow_style=False,
            allow_unicode=True
        )
    print(f"  dbt schema written: {dbt_path}")

    save_schema_snapshot(contract_id, contract["schema"])
    save_baselines(contract_id, stat_profile)

    return contract_path


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ContractGenerator — auto-generate data contracts"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="path to input JSONL file"
    )
    parser.add_argument(
        "--output",
        default=CONTRACTS_DIR,
        help="output directory for contracts"
    )
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"ERROR: source file not found: {args.source}")
        return

    process_source(args.source, args.output)
    print("\nDone.")


if __name__ == "__main__":
    main()