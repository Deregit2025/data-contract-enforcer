from sqlalchemy import Column, String, Integer, Float, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id          = Column(Integer, primary_key=True, index=True)
    contract_id = Column(String, unique=True, index=True, nullable=False)
    title       = Column(String, nullable=False)
    source_file = Column(String)
    created_at  = Column(String)


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id               = Column(Integer, primary_key=True, index=True)
    report_id        = Column(String, unique=True, index=True, nullable=False)
    contract_id      = Column(String, index=True, nullable=False)
    snapshot_id      = Column(String)
    run_timestamp    = Column(String, index=True)
    total_checks     = Column(Integer, default=0)
    passed           = Column(Integer, default=0)
    failed           = Column(Integer, default=0)
    warned           = Column(Integer, default=0)
    errored          = Column(Integer, default=0)
    enforcement_mode = Column(String)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id              = Column(Integer, primary_key=True, index=True)
    report_id       = Column(String, index=True, nullable=False)
    contract_id     = Column(String, index=True, nullable=False)
    check_id        = Column(String, nullable=False)
    column_name     = Column(String)
    check_type      = Column(String)
    status          = Column(String)
    severity        = Column(String)
    actual_value    = Column(Text)
    expected        = Column(Text)
    records_failing = Column(Integer, default=0)
    message         = Column(Text)


class Violation(Base):
    __tablename__ = "violations"

    id             = Column(Integer, primary_key=True, index=True)
    violation_id   = Column(String, unique=True, index=True, nullable=False)
    check_id       = Column(String, index=True, nullable=False)
    detected_at    = Column(String, index=True)
    severity       = Column(String, index=True)
    message        = Column(Text)
    blame_chain    = Column(JSONB)
    blast_radius   = Column(JSONB)
    injection_note = Column(Boolean, default=False)
    injection_type = Column(String)


class SchemaChange(Base):
    __tablename__ = "schema_changes"

    id            = Column(Integer, primary_key=True, index=True)
    report_id     = Column(String, index=True)
    contract_id   = Column(String, index=True, nullable=False)
    field         = Column(String, nullable=False)
    change_type   = Column(String)
    old_value     = Column(Text)
    new_value     = Column(Text)
    compatibility = Column(String)
    reason        = Column(Text)
    generated_at  = Column(String)


class AiMetric(Base):
    __tablename__ = "ai_metrics"

    id                     = Column(Integer, primary_key=True, index=True)
    run_date               = Column(String, index=True)
    embedding_drift_score  = Column(Float)
    embedding_drift_status = Column(String)
    embedding_sample_size  = Column(Integer)
    prompt_total           = Column(Integer)
    prompt_valid           = Column(Integer)
    prompt_rejected        = Column(Integer)
    prompt_status          = Column(String)
    llm_total_outputs      = Column(Integer)
    llm_violations         = Column(Integer)
    llm_violation_rate     = Column(Float)
    llm_trend              = Column(String)
    llm_status             = Column(String)


class RegistrySubscription(Base):
    __tablename__ = "registry_subscriptions"

    id              = Column(Integer, primary_key=True, index=True)
    contract_id     = Column(String, index=True, nullable=False)
    subscriber_id   = Column(String, nullable=False)
    subscriber_team = Column(String)
    validation_mode = Column(String)
    fields_consumed = Column(JSONB)
    breaking_fields = Column(JSONB)
    contact         = Column(String)
    registered_at   = Column(String)
