from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from database import get_db
from models import (
    Contract, ValidationReport, ValidationResult,
    Violation, SchemaChange, AiMetric, RegistrySubscription
)
from schemas import (
    ContractOut, ValidationReportOut, ValidationResultOut,
    ViolationOut, SchemaChangeOut, AiMetricOut, SubscriptionOut,
    ContractHealthOut, PlatformHealthOut, InterfaceRiskOut
)

app = FastAPI(title="Contract Enforcer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Health ---------------------------------------------------------------

@app.get("/api/health", response_model=PlatformHealthOut)
def get_platform_health(db: Session = Depends(get_db)):
    row = db.execute(text("SELECT * FROM v_platform_health")).mappings().one()

    total_checks  = row["total_checks"] or 0
    total_passed  = row["total_passed"] or 0
    total_failed  = row["total_failed"] or 0
    raw_pass_rate = float(row["raw_pass_rate"] or 0)

    # severity deductions capped at 50 points
    DEDUCTIONS = {"CRITICAL": 1.5, "HIGH": 0.75, "MEDIUM": 0.25, "LOW": 0.05}
    violations = db.execute(text(
        "SELECT severity FROM violations WHERE injection_note IS NOT TRUE"
    )).mappings().all()
    deduction = min(50.0, sum(DEDUCTIONS.get(v["severity"], 0.05) for v in violations))
    score = round(max(0.0, min(100.0, raw_pass_rate - deduction)), 1)

    if score >= 90:
        narrative = f"Platform is healthy at {score}% - no immediate action required."
    elif score >= 70:
        narrative = f"Platform is degraded at {score}% - review and monitor."
    elif score >= 50:
        narrative = f"Platform is unhealthy at {score}% - investigate and remediate."
    else:
        narrative = f"Platform is critically unhealthy at {score}% - immediate action required."

    return PlatformHealthOut(
        total_checks   = total_checks,
        total_passed   = total_passed,
        total_failed   = total_failed,
        total_warned   = row["total_warned"] or 0,
        raw_pass_rate  = raw_pass_rate,
        contract_count = row["contract_count"] or 0,
        health_score   = score,
        health_narrative = narrative
    )


# -- Contracts ------------------------------------------------------------

@app.get("/api/contracts", response_model=List[ContractOut])
def list_contracts(db: Session = Depends(get_db)):
    return db.query(Contract).order_by(Contract.contract_id).all()


@app.get("/api/contracts/health", response_model=List[ContractHealthOut])
def contract_health(db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT * FROM v_contract_health")).mappings().all()
    return [ContractHealthOut(**dict(r)) for r in rows]


@app.get("/api/contracts/{contract_id}/results", response_model=List[ValidationResultOut])
def contract_results(contract_id: str, db: Session = Depends(get_db)):
    latest = db.execute(text(
        "SELECT report_id FROM v_latest_reports WHERE contract_id = :cid"
    ), {"cid": contract_id}).mappings().first()
    if not latest:
        return []
    return (
        db.query(ValidationResult)
        .filter_by(report_id=latest["report_id"])
        .order_by(ValidationResult.status.desc())
        .all()
    )


# -- Violations -----------------------------------------------------------

@app.get("/api/violations", response_model=List[ViolationOut])
def list_violations(
    severity: Optional[str] = Query(None),
    exclude_injected: bool = Query(True),
    db: Session = Depends(get_db)
):
    q = db.query(Violation)
    if exclude_injected:
        q = q.filter(Violation.injection_note.is_(False))
    if severity:
        q = q.filter(Violation.severity == severity.upper())
    return q.order_by(Violation.detected_at.desc()).all()


@app.get("/api/violations/summary")
def violations_summary(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT severity, COUNT(*) AS count
        FROM violations
        WHERE injection_note IS NOT TRUE
        GROUP BY severity
        ORDER BY CASE severity
            WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM'   THEN 3 ELSE 4 END
    """)).mappings().all()
    return {r["severity"]: r["count"] for r in rows}


# -- Schema Changes -------------------------------------------------------

@app.get("/api/schema-changes", response_model=List[SchemaChangeOut])
def list_schema_changes(db: Session = Depends(get_db)):
    return (
        db.query(SchemaChange)
        .order_by(SchemaChange.compatibility.desc(), SchemaChange.field)
        .all()
    )


# -- AI Metrics -----------------------------------------------------------

@app.get("/api/ai-metrics", response_model=AiMetricOut)
def get_ai_metrics(db: Session = Depends(get_db)):
    return (
        db.query(AiMetric)
        .order_by(AiMetric.run_date.desc())
        .first()
    )


# -- Interfaces -----------------------------------------------------------

@app.get("/api/interfaces", response_model=List[InterfaceRiskOut])
def list_interfaces(db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT * FROM v_interface_risk_scores")).mappings().all()
    return [InterfaceRiskOut(**dict(r)) for r in rows]


@app.get("/api/interfaces/subscriptions", response_model=List[SubscriptionOut])
def list_subscriptions(db: Session = Depends(get_db)):
    return db.query(RegistrySubscription).order_by(RegistrySubscription.contract_id).all()
