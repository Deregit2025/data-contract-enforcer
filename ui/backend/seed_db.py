"""
seed_db.py — Load all existing JSON/JSONL/YAML data into PostgreSQL.
Run once: py -3.11 seed_db.py
"""
import sys
import os
import json
import glob
import yaml

# resolve paths relative to project root (two levels up from ui/backend/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal, create_views
from models import (
    Base, Contract, ValidationReport, ValidationResult,
    Violation, SchemaChange, AiMetric, RegistrySubscription
)


# ── helpers ──────────────────────────────────────────────────────────────

def load_jsonl(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def p(path):
    return os.path.join(ROOT, path)


# ── seed functions ────────────────────────────────────────────────────────

def seed_contracts(db):
    print("Seeding contracts...")
    contract_dir = p("generated_contracts")
    seen = set()
    for yaml_path in glob.glob(os.path.join(contract_dir, "*.yaml")):
        fname = os.path.basename(yaml_path)
        if fname.endswith("_dbt.yml") or "dbt" in fname:
            continue
        try:
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except UnicodeDecodeError:
                with open(yaml_path, encoding="cp1252") as f:
                    data = yaml.safe_load(f)
            if not data:
                continue
            cid = data.get("contract_id") or fname.replace(".yaml", "").replace("_", "-")
            if cid in seen:
                continue
            seen.add(cid)
            title = data.get("title") or data.get("name") or cid
            exists = db.query(Contract).filter_by(contract_id=cid).first()
            if not exists:
                db.add(Contract(
                    contract_id=cid,
                    title=title,
                    source_file=fname
                ))
        except Exception as e:
            print(f"  WARN contract {fname}: {e}")
    db.commit()
    print(f"  Done — {len(seen)} contracts")


def seed_validation_reports(db):
    print("Seeding validation reports...")
    count = 0
    for json_path in glob.glob(p("validation_reports/week*.json")):
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            rid = data.get("report_id")
            if not rid:
                continue
            exists = db.query(ValidationReport).filter_by(report_id=rid).first()
            if exists:
                continue
            db.add(ValidationReport(
                report_id        = rid,
                contract_id      = data.get("contract_id", "unknown"),
                snapshot_id      = data.get("snapshot_id"),
                run_timestamp    = data.get("run_timestamp"),
                total_checks     = data.get("total_checks", 0),
                passed           = data.get("passed", 0),
                failed           = data.get("failed", 0),
                warned           = data.get("warned", 0),
                errored          = data.get("errored", 0),
                enforcement_mode = data.get("enforcement_mode")
            ))
            # seed per-check results
            for result in data.get("results", []):
                db.add(ValidationResult(
                    report_id       = rid,
                    contract_id     = data.get("contract_id", "unknown"),
                    check_id        = result.get("check_id", ""),
                    column_name     = result.get("column_name"),
                    check_type      = result.get("check_type"),
                    status          = result.get("status", "UNKNOWN"),
                    severity        = result.get("severity"),
                    actual_value    = result.get("actual_value"),
                    expected        = result.get("expected"),
                    records_failing = result.get("records_failing", 0),
                    message         = result.get("message")
                ))
            count += 1
        except Exception as e:
            print(f"  WARN {json_path}: {e}")
    db.commit()
    print(f"  Done — {count} reports")


def seed_violations(db):
    print("Seeding violations...")
    records = load_jsonl(p("violation_log/violations.jsonl"))
    count = 0
    for v in records:
        vid = v.get("violation_id")
        if not vid:
            continue
        exists = db.query(Violation).filter_by(violation_id=vid).first()
        if exists:
            continue
        db.add(Violation(
            violation_id   = vid,
            check_id       = v.get("check_id", ""),
            detected_at    = v.get("detected_at"),
            severity       = v.get("severity", "LOW"),
            message        = v.get("message"),
            blame_chain    = v.get("blame_chain"),
            blast_radius   = v.get("blast_radius"),
            injection_note = v.get("injection_note", False),
            injection_type = v.get("injection_type")
        ))
        count += 1
    db.commit()
    print(f"  Done — {count} violations")


def seed_schema_changes(db):
    print("Seeding schema changes...")
    count = 0
    pattern = p("validation_reports/migration_impact_*.json")
    for json_path in glob.glob(pattern):
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            cid     = data.get("contract_id", "unknown")
            rid     = data.get("report_id", "")
            gen_at  = data.get("generated_at")
            for change in data.get("changes_detected", []):
                db.add(SchemaChange(
                    report_id     = rid,
                    contract_id   = cid,
                    field         = change.get("field", ""),
                    change_type   = change.get("change_type"),
                    old_value     = str(change.get("old_value", "")) if change.get("old_value") is not None else None,
                    new_value     = str(change.get("new_value", "")) if change.get("new_value") is not None else None,
                    compatibility = change.get("compatibility"),
                    reason        = change.get("reason"),
                    generated_at  = gen_at
                ))
                count += 1
        except Exception as e:
            print(f"  WARN {json_path}: {e}")
    db.commit()
    print(f"  Done — {count} schema changes")


def seed_ai_metrics(db):
    print("Seeding AI metrics...")
    path = p("validation_reports/ai_metrics.json")
    if not os.path.exists(path):
        print("  SKIP — ai_metrics.json not found")
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    run_date = data.get("run_date", "")
    exists = db.query(AiMetric).filter_by(run_date=run_date).first()
    if exists:
        print("  SKIP — already seeded")
        return
    ed = data.get("embedding_drift", {})
    pv = data.get("prompt_input_validation", {})
    lo = data.get("llm_output_schema", {})
    db.add(AiMetric(
        run_date               = run_date,
        embedding_drift_score  = ed.get("drift_score"),
        embedding_drift_status = ed.get("status"),
        embedding_sample_size  = ed.get("sample_size"),
        prompt_total           = pv.get("total"),
        prompt_valid           = pv.get("valid"),
        prompt_rejected        = pv.get("rejected"),
        prompt_status          = pv.get("status"),
        llm_total_outputs      = lo.get("total_outputs"),
        llm_violations         = lo.get("schema_violations"),
        llm_violation_rate     = lo.get("violation_rate"),
        llm_trend              = lo.get("trend"),
        llm_status             = lo.get("status")
    ))
    db.commit()
    print("  Done — 1 AI metrics record")


def seed_registry(db):
    print("Seeding registry subscriptions...")
    path = p("contract_registry/subscriptions.yaml")
    if not os.path.exists(path):
        print("  SKIP — subscriptions.yaml not found")
        return
    with open(path, encoding="utf-8") as f:
        registry = yaml.safe_load(f)
    count = 0
    for sub in registry.get("subscriptions", []):
        exists = db.query(RegistrySubscription).filter_by(
            contract_id=sub.get("contract_id"),
            subscriber_id=sub.get("subscriber_id")
        ).first()
        if exists:
            continue
        db.add(RegistrySubscription(
            contract_id     = sub.get("contract_id", ""),
            subscriber_id   = sub.get("subscriber_id", ""),
            subscriber_team = sub.get("subscriber_team"),
            validation_mode = sub.get("validation_mode"),
            fields_consumed = sub.get("fields_consumed"),
            breaking_fields = sub.get("breaking_fields"),
            contact         = sub.get("contact"),
            registered_at   = sub.get("registered_at")
        ))
        count += 1
    db.commit()
    print(f"  Done — {count} subscriptions")


# ── main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_contracts(db)
        seed_validation_reports(db)
        seed_violations(db)
        seed_schema_changes(db)
        seed_ai_metrics(db)
        seed_registry(db)
        print("\nCreating views...")
        create_views(db)
        print("\nSeed complete.")
    finally:
        db.close()
