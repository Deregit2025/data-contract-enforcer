import subprocess
import json
from pathlib import Path
from dagster import asset, AssetExecutionContext, MetadataValue

ROOT = Path(__file__).resolve().parents[2]  # contract-enforcer/

CONTRACTS = [
    "week1_intent_code_correlator",
    "week2_digital_courtroom",
    "week3_document_refinery_extractions",
    "week4_brownfield_cartographer",
    "week5_event_sourcing_platform",
]

DATA_SOURCES = {
    "week1_intent_code_correlator":        "outputs/week1/intent_records.jsonl",
    "week2_digital_courtroom":             "outputs/week2/verdicts.jsonl",
    "week3_document_refinery_extractions": "outputs/week3/extractions.jsonl",
    "week4_brownfield_cartographer":       "outputs/week4/lineage_snapshots.jsonl",
    "week5_event_sourcing_platform":       "outputs/week5/events.jsonl",
}


# ─────────────────────────────────────────
# ASSET 1 — Contract Generation
# ─────────────────────────────────────────

@asset(
    description="Generate YAML contracts for all 5 pipeline outputs.",
    group_name="enforcement_pipeline",
)
def generated_contracts(context: AssetExecutionContext):
    """Run contracts/generator.py for each data source."""
    results = {}
    for contract_id, data_path in DATA_SOURCES.items():
        full_data_path = ROOT / data_path
        if not full_data_path.exists():
            context.log.warning(f"Data file not found, skipping: {full_data_path}")
            results[contract_id] = "skipped"
            continue

        output_dir = ROOT / "generated_contracts"
        output_dir.mkdir(exist_ok=True)

        result = subprocess.run(
            ["python", str(ROOT / "contracts" / "generator.py"),
             "--source", str(full_data_path),
             "--output", str(output_dir)],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            context.log.error(f"Generator failed for {contract_id}: {result.stderr}")
            results[contract_id] = "failed"
        else:
            context.log.info(f"Contract generated: {contract_id}")
            results[contract_id] = "generated"

    context.add_output_metadata({
        "contracts_generated": MetadataValue.int(
            sum(1 for v in results.values() if v == "generated")
        ),
        "contracts_skipped": MetadataValue.int(
            sum(1 for v in results.values() if v == "skipped")
        ),
    })
    return results


# ─────────────────────────────────────────
# ASSET 2 — Validation Run
# ─────────────────────────────────────────

@asset(
    deps=[generated_contracts],
    description="Run ValidationRunner on all 5 contracts.",
    group_name="enforcement_pipeline",
)
def validation_reports(context: AssetExecutionContext):
    """Run contracts/runner.py for each contract in ENFORCE mode."""
    results = {}
    for contract_id, data_path in DATA_SOURCES.items():
        full_data_path  = ROOT / data_path
        contract_file   = ROOT / "generated_contracts" / f"{contract_id}.yaml"

        if not full_data_path.exists() or not contract_file.exists():
            context.log.warning(f"Skipping {contract_id} — missing data or contract")
            results[contract_id] = "skipped"
            continue

        result = subprocess.run(
            ["python", str(ROOT / "contracts" / "runner.py"),
             "--data",     str(full_data_path),
             "--contract", str(contract_file),
             "--mode",     "ENFORCE"],
            capture_output=True, text=True, cwd=ROOT
        )
        status = "passed" if result.returncode == 0 else "failed"
        context.log.info(f"Validation {status}: {contract_id}")
        if result.returncode != 0:
            context.log.warning(f"ENFORCE block on {contract_id}:\n{result.stdout}")
        results[contract_id] = status

    failed = [k for k, v in results.items() if v == "failed"]
    context.add_output_metadata({
        "contracts_passed":  MetadataValue.int(len([v for v in results.values() if v == "passed"])),
        "contracts_failed":  MetadataValue.int(len(failed)),
        "failed_contracts":  MetadataValue.text(", ".join(failed) if failed else "none"),
    })
    return results


# ─────────────────────────────────────────
# ASSET 3 — Schema Evolution Analysis
# ─────────────────────────────────────────

@asset(
    deps=[validation_reports],
    description="Run SchemaEvolutionAnalyzer on Week 3 snapshots.",
    group_name="enforcement_pipeline",
)
def schema_evolution_report(context: AssetExecutionContext):
    """Run contracts/schema_analyzer.py."""
    result = subprocess.run(
        ["python", str(ROOT / "contracts" / "schema_analyzer.py")],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        context.log.error(f"Schema analyzer failed: {result.stderr}")
        return {"status": "failed"}

    context.log.info("Schema evolution analysis complete")

    # Count breaking changes from output report if it exists
    reports = list((ROOT / "validation_reports").glob("schema_evolution_*.json"))
    breaking = 0
    if reports:
        latest = max(reports, key=lambda p: p.stat().st_mtime)
        try:
            data = json.loads(latest.read_text())
            breaking = sum(
                1 for c in data.get("changes", [])
                if c.get("verdict") == "BREAKING"
            )
        except Exception:
            pass

    context.add_output_metadata({
        "breaking_changes": MetadataValue.int(breaking),
        "report_file": MetadataValue.text(str(reports[-1]) if reports else "none"),
    })
    return {"status": "complete", "breaking_changes": breaking}


# ─────────────────────────────────────────
# ASSET 4 — AI Contract Extensions
# ─────────────────────────────────────────

@asset(
    deps=[validation_reports],
    description="Run AI extensions: embedding drift, prompt validation, LLM output schema.",
    group_name="enforcement_pipeline",
)
def ai_metrics(context: AssetExecutionContext):
    """Run contracts/ai_extensions.py."""
    result = subprocess.run(
        ["python", str(ROOT / "contracts" / "ai_extensions.py")],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        context.log.error(f"AI extensions failed: {result.stderr}")
        return {"status": "failed"}

    metrics_path = ROOT / "validation_reports" / "ai_metrics.json"
    if metrics_path.exists():
        try:
            data = json.loads(metrics_path.read_text())
            drift  = data.get("embedding_drift", {}).get("drift_score", "n/a")
            prompt = data.get("prompt_input_validation", {}).get("status", "n/a")
            llm    = data.get("llm_output_schema", {}).get("status", "n/a")
            context.add_output_metadata({
                "embedding_drift_score":       MetadataValue.float(float(drift) if drift != "n/a" else 0.0),
                "prompt_input_validation":     MetadataValue.text(prompt),
                "llm_output_schema_status":    MetadataValue.text(llm),
            })
            return data
        except Exception as e:
            context.log.warning(f"Could not parse ai_metrics.json: {e}")

    return {"status": "complete"}


# ─────────────────────────────────────────
# ASSET 5 — Violation Attribution
# ─────────────────────────────────────────

@asset(
    deps=[validation_reports],
    description="Run ViolationAttributor — blame chain and blast radius for all FAILs.",
    group_name="enforcement_pipeline",
)
def violation_attribution(context: AssetExecutionContext):
    """Run contracts/attributor.py on latest validation reports."""
    reports_dir = ROOT / "validation_reports"
    report_files = list(reports_dir.glob("*.json"))
    report_files = [r for r in report_files
                    if not r.name.startswith(("schema_evolution", "ai_metrics", "migration"))]

    total_violations = 0
    critical_count   = 0

    for report_file in report_files:
        result = subprocess.run(
            ["python", str(ROOT / "contracts" / "attributor.py"),
             "--report", str(report_file)],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            context.log.warning(f"Attributor issue on {report_file.name}: {result.stderr}")

    # Count violations written
    violations_path = ROOT / "violation_log" / "violations.jsonl"
    if violations_path.exists():
        lines = [l for l in violations_path.read_text().splitlines() if l.strip()]
        for line in lines:
            try:
                v = json.loads(line)
                total_violations += 1
                if v.get("severity") == "CRITICAL":
                    critical_count += 1
            except Exception:
                pass

    context.add_output_metadata({
        "total_violations":    MetadataValue.int(total_violations),
        "critical_violations": MetadataValue.int(critical_count),
    })
    return {
        "total_violations":    total_violations,
        "critical_violations": critical_count,
    }


# ─────────────────────────────────────────
# ASSET 6 — Enforcer Report
# ─────────────────────────────────────────

@asset(
    deps=[schema_evolution_report, ai_metrics, violation_attribution],
    description="Generate the final enforcer report — JSON + PDF.",
    group_name="enforcement_pipeline",
)
def enforcer_report(context: AssetExecutionContext):
    """Run contracts/report_generator.py to produce report_data.json and PDF."""
    result = subprocess.run(
        ["python", str(ROOT / "contracts" / "report_generator.py")],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        context.log.error(f"Report generator failed: {result.stderr}")
        return {"status": "failed"}

    report_json = ROOT / "enforcer_report" / "report_data.json"
    if report_json.exists():
        try:
            data = json.loads(report_json.read_text())
            context.add_output_metadata({
                "health_score":      MetadataValue.float(data.get("health_score", 0.0)),
                "health_narrative":  MetadataValue.text(data.get("health_narrative", "")),
                "report_id":         MetadataValue.text(data.get("report_id", "")),
                "total_violations":  MetadataValue.int(
                    data.get("summary", {}).get("total_violations", 0)
                ),
            })
            return data
        except Exception as e:
            context.log.warning(f"Could not parse report_data.json: {e}")

    return {"status": "complete"}