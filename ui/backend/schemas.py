from pydantic import BaseModel
from typing import Optional, List, Any


class ContractOut(BaseModel):
    contract_id: str
    title: str
    source_file: Optional[str]

    class Config:
        from_attributes = True


class ValidationReportOut(BaseModel):
    report_id: str
    contract_id: str
    run_timestamp: Optional[str]
    total_checks: int
    passed: int
    failed: int
    warned: int
    errored: int
    enforcement_mode: Optional[str]

    class Config:
        from_attributes = True


class ValidationResultOut(BaseModel):
    check_id: str
    column_name: Optional[str]
    check_type: Optional[str]
    status: str
    severity: Optional[str]
    actual_value: Optional[str]
    expected: Optional[str]
    records_failing: int
    message: Optional[str]

    class Config:
        from_attributes = True


class ViolationOut(BaseModel):
    violation_id: str
    check_id: str
    detected_at: Optional[str]
    severity: str
    message: Optional[str]
    blame_chain: Optional[Any]
    blast_radius: Optional[Any]
    injection_note: Optional[bool]

    class Config:
        from_attributes = True


class SchemaChangeOut(BaseModel):
    contract_id: str
    field: str
    change_type: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    compatibility: Optional[str]
    reason: Optional[str]
    generated_at: Optional[str]

    class Config:
        from_attributes = True


class AiMetricOut(BaseModel):
    run_date: str
    embedding_drift_score: Optional[float]
    embedding_drift_status: Optional[str]
    embedding_sample_size: Optional[int]
    prompt_total: Optional[int]
    prompt_valid: Optional[int]
    prompt_rejected: Optional[int]
    prompt_status: Optional[str]
    llm_total_outputs: Optional[int]
    llm_violations: Optional[int]
    llm_violation_rate: Optional[float]
    llm_trend: Optional[str]
    llm_status: Optional[str]

    class Config:
        from_attributes = True


class SubscriptionOut(BaseModel):
    contract_id: str
    subscriber_id: str
    subscriber_team: Optional[str]
    validation_mode: Optional[str]
    fields_consumed: Optional[Any]
    breaking_fields: Optional[Any]
    contact: Optional[str]

    class Config:
        from_attributes = True


class ContractHealthOut(BaseModel):
    contract_id: str
    total_checks: int
    passed: int
    failed: int
    warned: int
    pass_rate: Optional[float]
    status: str


class PlatformHealthOut(BaseModel):
    total_checks: int
    total_passed: int
    total_failed: int
    total_warned: int
    raw_pass_rate: Optional[float]
    contract_count: int
    health_score: float
    health_narrative: str


class InterfaceRiskOut(BaseModel):
    contract_id: str
    subscriber_id: str
    validation_mode: str
    breaking_field_count: int
    active_critical: int
    active_high: int
    risk_score: int
    contact: Optional[str]
