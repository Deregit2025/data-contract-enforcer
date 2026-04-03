import json
import uuid
import hashlib
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml
import pandas as pd
import numpy as np

BASELINES_PATH = "schema_snapshots/baselines.json"
REPORTS_DIR    = "validation_reports"


# ─────────────────────────────────────────
# HELPERS
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


def load_contract(path):
    with open(path) as f:
        return yaml.safe_load(f)


def snapshot_id(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_baselines(contract_id):
    if not os.path.exists(BASELINES_PATH):
        return {}
    with open(BASELINES_PATH) as f:
        all_baselines = json.load(f)
    return all_baselines.get(contract_id, {})


def make_result(check_id, column_name, check_type,
                status, severity, actual,
                expected, records_failing=0,
                sample_failing=None, message=""):
    return {
        "check_id":        check_id,
        "column_name":     column_name,
        "check_type":      check_type,
        "status":          status,
        "actual_value":    str(actual),
        "expected":        str(expected),
        "severity":        severity,
        "records_failing": records_failing,
        "sample_failing":  sample_failing or [],
        "message":         message
    }


# ─────────────────────────────────────────
# CHECK FUNCTIONS
# ─────────────────────────────────────────

def check_not_null(df, col, check_id):
    try:
        failing = int(df[col].isnull().sum())
        status  = "FAIL" if failing > 0 else "PASS"
        return make_result(
            check_id, col, "not_null",
            status, "CRITICAL" if failing > 0 else None,
            actual=f"{failing} nulls",
            expected="0 nulls",
            records_failing=failing,
            message=f"{failing} null values found in required field {col}"
        )
    except KeyError:
        return make_result(
            check_id, col, "not_null",
            "ERROR", None,
            actual="column missing",
            expected="column present",
            message=f"Column {col} not found in dataset"
        )


def check_unique(df, col, check_id):
    try:
        total    = len(df)
        unique   = df[col].nunique()
        failing  = int(total - unique)
        status   = "FAIL" if failing > 0 else "PASS"
        dupes    = df[df[col].duplicated()][col].head(2).tolist()
        return make_result(
            check_id, col, "unique",
            status, "CRITICAL" if failing > 0 else None,
            actual=f"{unique} unique of {total}",
            expected="all unique",
            records_failing=failing,
            sample_failing=dupes,
            message=f"{failing} duplicate values found in {col}"
        )
    except KeyError:
        return make_result(
            check_id, col, "unique",
            "ERROR", None,
            actual="column missing",
            expected="column present",
            message=f"Column {col} not found in dataset"
        )


def check_range(df, col, minimum, maximum, check_id):
    try:
        col_data = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(col_data) == 0:
            return make_result(
                check_id, col, "range",
                "ERROR", None,
                actual="no numeric values",
                expected=f">={minimum}, <={maximum}",
                message=f"No numeric values found in {col}"
            )
        failing_mask = (col_data < minimum) | (col_data > maximum)
        failing      = int(failing_mask.sum())
        status       = "FAIL" if failing > 0 else "PASS"
        sample       = col_data[failing_mask].head(2).tolist()
        return make_result(
            check_id, col, "range",
            status, "CRITICAL" if failing > 0 else None,
            actual=f"min={col_data.min():.4f}, max={col_data.max():.4f}, mean={col_data.mean():.4f}",
            expected=f">={minimum}, <={maximum}",
            records_failing=failing,
            sample_failing=sample,
            message=f"{failing} values outside range [{minimum}, {maximum}]"
        )
    except KeyError:
        return make_result(
            check_id, col, "range",
            "ERROR", None,
            actual="column missing",
            expected=f">={minimum}, <={maximum}",
            message=f"Column {col} not found in dataset"
        )


def check_accepted_values(df, col, allowed, check_id):
    try:
        failing_mask = ~df[col].isin(allowed)
        failing      = int(failing_mask.sum())
        sample       = df[failing_mask][col].head(2).tolist()
        status       = "FAIL" if failing > 0 else "PASS"
        return make_result(
            check_id, col, "accepted_values",
            status, "CRITICAL" if failing > 0 else None,
            actual=str(df[col].unique().tolist()[:5]),
            expected=str(allowed),
            records_failing=failing,
            sample_failing=sample,
            message=f"{failing} values not in allowed set {allowed}"
        )
    except KeyError:
        return make_result(
            check_id, col, "accepted_values",
            "ERROR", None,
            actual="column missing",
            expected=str(allowed),
            message=f"Column {col} not found in dataset"
        )


def check_row_count(df, minimum, check_id):
    count  = len(df)
    status = "FAIL" if count < minimum else "PASS"
    return make_result(
        check_id, "row_count", "row_count",
        status, "HIGH" if count < minimum else None,
        actual=f"{count} rows",
        expected=f">={minimum} rows",
        records_failing=0 if count >= minimum else minimum - count,
        message=f"Dataset has {count} rows, minimum is {minimum}"
    )


def check_statistical_drift(df, col, contract_id, check_id):
    """
    Compare current mean against saved baseline.
    WARN if deviation > 2 stddev.
    FAIL if deviation > 3 stddev.
    """
    try:
        col_data = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(col_data) == 0:
            return make_result(
                check_id, col, "statistical_drift",
                "ERROR", None,
                actual="no numeric values",
                expected="numeric values present",
                message=f"No numeric values in {col}"
            )

        current_mean = float(col_data.mean())
        current_std  = float(col_data.std())
        baselines    = load_baselines(contract_id)

        if col not in baselines:
            return make_result(
                check_id, col, "statistical_drift",
                "PASS", None,
                actual=f"mean={current_mean:.4f}",
                expected="baseline not yet established",
                message="First run — baseline will be saved by generator"
            )

        base_mean = baselines[col]["mean"]
        base_std  = baselines[col]["stddev"]

        if base_std == 0:
            deviation = 0
        else:
            deviation = abs(current_mean - base_mean) / base_std

        if deviation > 3:
            status   = "FAIL"
            severity = "HIGH"
            msg      = (f"Mean shifted {deviation:.1f} stddev from baseline "
                       f"({base_mean:.4f} → {current_mean:.4f}). "
                       f"Possible scale change.")
        elif deviation > 2:
            status   = "WARN"
            severity = "MEDIUM"
            msg      = (f"Mean shifted {deviation:.1f} stddev from baseline "
                       f"({base_mean:.4f} → {current_mean:.4f}).")
        else:
            status   = "PASS"
            severity = None
            msg      = (f"Mean within baseline range "
                       f"(deviation={deviation:.2f} stddev).")

        return make_result(
            check_id, col, "statistical_drift",
            status, severity,
            actual=f"mean={current_mean:.4f}, stddev={current_std:.4f}",
            expected=f"baseline mean={base_mean:.4f} ±2 stddev",
            message=msg
        )

    except KeyError:
        return make_result(
            check_id, col, "statistical_drift",
            "ERROR", None,
            actual="column missing",
            expected="column present",
            message=f"Column {col} not found"
        )


def check_referential_integrity(records, check_id):
    """
    For week3 — every entity_ref inside extracted_facts
    must exist in the entities[] of the same record.
    """
    failing      = 0
    sample_fails = []

    for record in records:
        entity_ids = {
            e["entity_id"]
            for e in record.get("entities", [])
            if isinstance(e, dict)
        }
        for fact in record.get("extracted_facts", []):
            if not isinstance(fact, dict):
                continue
            for ref in fact.get("entity_refs", []):
                if ref not in entity_ids:
                    failing += 1
                    if len(sample_fails) < 2:
                        sample_fails.append(
                            fact.get("fact_id", "unknown")
                        )

    status = "FAIL" if failing > 0 else "PASS"
    return make_result(
        check_id,
        "extracted_facts[*].entity_refs",
        "referential_integrity",
        status,
        "CRITICAL" if failing > 0 else None,
        actual=f"{failing} broken references",
        expected="all entity_refs exist in entities[]",
        records_failing=failing,
        sample_failing=sample_fails,
        message=f"{failing} entity_refs point to non-existent entity_ids"
    )


def check_sequence_numbers(records, check_id):
    """
    For week5 — sequence_number must be monotonically
    increasing per aggregate_id with no gaps or duplicates.
    """
    from collections import defaultdict
    agg_sequences = defaultdict(list)

    for record in records:
        agg_id = record.get("aggregate_id")
        seq    = record.get("sequence_number")
        if agg_id and seq is not None:
            agg_sequences[agg_id].append(seq)

    failing      = 0
    sample_fails = []

    for agg_id, seqs in agg_sequences.items():
        sorted_seqs   = sorted(seqs)
        expected_seqs = list(range(1, len(sorted_seqs) + 1))
        if sorted_seqs != expected_seqs:
            failing += 1
            if len(sample_fails) < 2:
                sample_fails.append(agg_id)

    status = "FAIL" if failing > 0 else "PASS"
    return make_result(
        check_id,
        "sequence_number",
        "sequence_integrity",
        status,
        "CRITICAL" if failing > 0 else None,
        actual=f"{failing} aggregates with broken sequences",
        expected="monotonically increasing from 1 per aggregate",
        records_failing=failing,
        sample_failing=sample_fails,
        message=f"{failing} aggregates have gaps or duplicates in sequence_number"
    )


def check_timestamp_order(records, earlier_field,
                           later_field, check_id):
    """
    Check that later_field >= earlier_field for every record.
    e.g. recorded_at >= occurred_at
    """
    failing      = 0
    sample_fails = []

    for record in records:
        t1 = record.get(earlier_field)
        t2 = record.get(later_field)
        if t1 and t2:
            if t2 < t1:
                failing += 1
                if len(sample_fails) < 2:
                    sample_fails.append(
                        record.get("event_id",
                        record.get("doc_id", "unknown"))
                    )

    status = "FAIL" if failing > 0 else "PASS"
    return make_result(
        check_id,
        f"{later_field} >= {earlier_field}",
        "timestamp_order",
        status,
        "CRITICAL" if failing > 0 else None,
        actual=f"{failing} violations",
        expected=f"{later_field} >= {earlier_field}",
        records_failing=failing,
        sample_failing=sample_fails,
        message=f"{failing} records where {later_field} < {earlier_field}"
    )


# ─────────────────────────────────────────
# FLATTEN FOR PANDAS
# ─────────────────────────────────────────

def flatten_for_runner(records, contract_id):
    """
    Extract flat columns needed for checks.
    """
    flat = []
    for r in records:
        row = {k: v for k, v in r.items()
               if not isinstance(v, (list, dict))}

        # week3 specific — flatten confidence values
        if "extracted_facts" in r:
            confs = [
                f["confidence"]
                for f in r.get("extracted_facts", [])
                if isinstance(f, dict) and "confidence" in f
            ]
            if confs:
                row["extracted_facts_confidence_mean"] = np.mean(confs)
                row["extracted_facts_confidence_min"]  = np.min(confs)
                row["extracted_facts_confidence_max"]  = np.max(confs)

        flat.append(row)

    return pd.DataFrame(flat)

# -------------------------------
# week 1 and week 2 checks
#----------------------------

def check_cross_system_w1_w2(intent_records_path, verdict_records_path, check_id):
    """
    Week 1 → Week 2 cross-system check.
    Every verdict.target_ref must match a file in
    some intent_record.code_refs[*].file.
    """
    try:
        intent_files = set()
        if os.path.exists(intent_records_path):
            with open(intent_records_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        for ref in record.get("code_refs", []):
                            if ref.get("file"):
                                intent_files.add(ref["file"])

        if not intent_files:
            return make_result(
                check_id,
                "verdict.target_ref",
                "cross_system_referential",
                "ERROR", None,
                actual="no intent files loaded",
                expected="intent_records present",
                message="Week 1 intent_records.jsonl not found or empty"
            )

        verdict_records = load_jsonl(verdict_records_path)
        failing      = 0
        sample_fails = []

        for record in verdict_records:
            target_ref = record.get("target_ref", "")
            if target_ref and not any(
                target_ref in f or f in target_ref
                for f in intent_files
            ):
                failing += 1
                if len(sample_fails) < 2:
                    sample_fails.append(target_ref)

        status = "WARN" if failing > 0 else "PASS"
        return make_result(
            check_id,
            "verdict.target_ref → intent.code_refs[*].file",
            "cross_system_referential",
            status,
            "MEDIUM" if failing > 0 else None,
            actual=f"{failing} target_refs not found in intent code_refs",
            expected="all target_refs match an intent code_refs file",
            records_failing=failing,
            sample_failing=sample_fails,
            message=(
                f"{failing} verdict target_refs do not match "
                f"any intent code_refs file path"
            )
        )
    except Exception as e:
        return make_result(
            check_id,
            "verdict.target_ref",
            "cross_system_referential",
            "ERROR", None,
            actual=str(e),
            expected="cross-system check executed",
            message=f"Cross-system check failed: {e}"
        )


def check_cross_system_w3_w4(extractions_path, lineage_path, check_id):
    """
    Week 3 → Week 4 cross-system check.
    doc_id values from extraction_records should
    appear as nodes in the lineage_snapshot.
    """
    try:
        # load extraction doc_ids
        doc_ids = set()
        if os.path.exists(extractions_path):
            with open(extractions_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        if record.get("doc_id"):
                            doc_ids.add(record["doc_id"])

        if not doc_ids:
            return make_result(
                check_id,
                "lineage_snapshot.nodes → extraction.doc_id",
                "cross_system_referential",
                "ERROR", None,
                actual="no doc_ids loaded",
                expected="extraction records present",
                message="Week 3 extractions not found or empty"
            )

        # load lineage node ids
        node_ids = set()
        if os.path.exists(lineage_path):
            with open(lineage_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        snapshot = json.loads(line)
                        for node in snapshot.get("nodes", []):
                            node_ids.add(node.get("node_id", ""))

        # check how many doc_ids appear in lineage
        matched  = sum(
            1 for d in doc_ids
            if any(d in n for n in node_ids)
        )
        coverage = round(matched / len(doc_ids), 2) if doc_ids else 0

        # warn if less than 50% of docs appear in lineage
        status = "PASS" if coverage >= 0.5 else "WARN"

        return make_result(
            check_id,
            "lineage_snapshot.nodes → extraction.doc_id",
            "cross_system_referential",
            status,
            "MEDIUM" if status == "WARN" else None,
            actual=f"{matched}/{len(doc_ids)} doc_ids found in lineage",
            expected="doc_ids from extractions appear as lineage nodes",
            records_failing=len(doc_ids) - matched,
            message=(
                f"{matched} of {len(doc_ids)} extraction doc_ids "
                f"found in lineage graph ({coverage:.0%} coverage)"
            )
        )
    except Exception as e:
        return make_result(
            check_id,
            "lineage_snapshot.nodes → extraction.doc_id",
            "cross_system_referential",
            "ERROR", None,
            actual=str(e),
            expected="cross-system check executed",
            message=f"Cross-system check failed: {e}"
        )


# ─────────────────────────────────────────
# RUN ALL CHECKS
# ─────────────────────────────────────────

def run_checks(contract, records, contract_id, data_path=""):
    df      = flatten_for_runner(records, contract_id)
    results = []
    schema  = contract.get("schema", {})

    # ── row count ──
    results.append(
        check_row_count(df, 1, f"{contract_id}.row_count")
    )

    # ── per field checks from contract schema ──
    for col, field_def in schema.items():
        if not isinstance(field_def, dict):
            continue

        prefix = f"{contract_id}.{col}"

        # not null
        if field_def.get("required") is True:
            if col in df.columns:
                results.append(
                    check_not_null(df, col, f"{prefix}.not_null")
                )

        # unique
        if field_def.get("format") == "uuid":
            if col in df.columns:
                results.append(
                    check_unique(df, col, f"{prefix}.unique")
                )

        # range check
        if "minimum" in field_def and "maximum" in field_def:
            if col in df.columns:
                results.append(
                    check_range(
                        df, col,
                        field_def["minimum"],
                        field_def["maximum"],
                        f"{prefix}.range"
                    )
                )

    # ── confidence range check (nested) ──
    if "extracted_facts_confidence_min" in df.columns:
        results.append(
            check_range(
                df,
                "extracted_facts_confidence_min",
                0.0, 1.0,
                f"{contract_id}.extracted_facts.confidence.range"
            )
        )
        results.append(
            check_range(
                df,
                "extracted_facts_confidence_max",
                0.0, 1.0,
                f"{contract_id}.extracted_facts.confidence.max_range"
            )
        )

    # ── statistical drift ──
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        results.append(
            check_statistical_drift(
                df, col, contract_id,
                f"{contract_id}.{col}.drift"
            )
        )

    # ── week3 specific ──
    if "week3" in contract_id:
        results.append(
            check_referential_integrity(
                records,
                f"{contract_id}.entity_refs.integrity"
            )
        )
        # cross-system week3 → week4
        results.append(
            check_cross_system_w3_w4(
                data_path,
                "outputs/week4/lineage_snapshots.jsonl",
                f"{contract_id}.doc_id.cross_system_w4"
            )
        )

    # ── week5 specific ──
    if "week5" in contract_id:
        results.append(
            check_sequence_numbers(
                records,
                f"{contract_id}.sequence_number.monotonic"
            )
        )
        results.append(
            check_timestamp_order(
                records,
                "occurred_at", "recorded_at",
                f"{contract_id}.timestamps.order"
            )
        )

    # ── cross-system week1 → week2 ──
    if "week2" in contract_id:
        results.append(
            check_cross_system_w1_w2(
                "outputs/week1/intent_records.jsonl",
                data_path,
                f"{contract_id}.target_ref.cross_system_w1"
            )
        )

    return results


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ValidationRunner — execute contract checks"
    )
    parser.add_argument(
        "--mode",
        default="AUDIT",
        choices=["AUDIT", "WARN", "ENFORCE"],
        help=(
            "Enforcement mode. "
            "AUDIT: log all violations, never block. "
            "WARN: block on CRITICAL only. "
            "ENFORCE: block on CRITICAL or HIGH."
        )
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="path to contract YAML file"
    )
    parser.add_argument(
        "--data",
        required=True,
        help="path to data JSONL file"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="output path for report JSON"
    )
    args = parser.parse_args()

    # load inputs
    contract    = load_contract(args.contract)
    contract_id = contract.get("id", Path(args.contract).stem)
    records     = load_jsonl(args.data)

    if not records:
        print(f"ERROR: no records found in {args.data}")
        return

    print(f"\nRunning validation: {contract_id}")
    print(f"  Records: {len(records)}")
    print(f"  Contract: {args.contract}")

    # run all checks
    results = run_checks(contract, records, contract_id, args.data)

    # tally results
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    warned  = sum(1 for r in results if r["status"] == "WARN")
    errored = sum(1 for r in results if r["status"] == "ERROR")

    # ── enforcement mode logic ──
    should_block = False
    block_reason = ""

    if args.mode == "WARN":
        critical_fails = [
            r for r in results
            if r["status"] == "FAIL"
            and r.get("severity") == "CRITICAL"
        ]
        if critical_fails:
            should_block = True
            block_reason = (
                f"WARN mode: {len(critical_fails)} CRITICAL "
                f"violation(s) detected — pipeline blocked"
            )

    elif args.mode == "ENFORCE":
        blocking_fails = [
            r for r in results
            if r["status"] == "FAIL"
            and r.get("severity") in ("CRITICAL", "HIGH")
        ]
        if blocking_fails:
            should_block = True
            block_reason = (
                f"ENFORCE mode: {len(blocking_fails)} CRITICAL/HIGH "
                f"violation(s) detected — pipeline blocked"
            )

    # ── build report ──
    report = {
        "report_id":        str(uuid.uuid4()),
        "contract_id":      contract_id,
        "snapshot_id":      snapshot_id(args.data),
        "run_timestamp":    datetime.now(timezone.utc).isoformat(),
        "enforcement_mode": args.mode,
        "pipeline_blocked": should_block,
        "block_reason":     block_reason,
        "total_checks":     len(results),
        "passed":           passed,
        "failed":           failed,
        "warned":           warned,
        "errored":          errored,
        "results":          results
    }

    # ── print summary ──
    print(f"\n  Results:")
    print(f"    Mode:  {args.mode}")
    print(f"    PASS:  {passed}")
    print(f"    FAIL:  {failed}")
    print(f"    WARN:  {warned}")
    print(f"    ERROR: {errored}")
    print(f"    TOTAL: {len(results)}")

    if failed > 0:
        print(f"\n  Failed checks:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    - {r['check_id']}: {r['message']}")

    # ── mode status ──
    print(f"\n  Mode: {args.mode}")
    if should_block:
        print(f"  BLOCKED: {block_reason}")
    elif args.mode != "AUDIT":
        print(f"  Pipeline allowed to proceed")
    else:
        print(f"  AUDIT mode — violations logged, pipeline not blocked")

    # ── write report ──
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if args.output:
        output_path = args.output
    else:
        timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        short_id    = contract_id.split("-")[0]
        output_path = os.path.join(
            REPORTS_DIR,
            f"{short_id}_{timestamp}.json"
        )

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Report written: {output_path}")


if __name__ == "__main__":
    main()