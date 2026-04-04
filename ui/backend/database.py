import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/contract_enforcer"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_views(db):
    views = [
        """
        CREATE OR REPLACE VIEW v_latest_reports AS
        SELECT DISTINCT ON (contract_id)
            report_id, contract_id, run_timestamp,
            total_checks, passed, failed, warned, errored,
            enforcement_mode
        FROM validation_reports
        ORDER BY contract_id, run_timestamp DESC
        """,

        """
        CREATE OR REPLACE VIEW v_contract_health AS
        SELECT
            contract_id,
            total_checks,
            passed,
            failed,
            warned,
            ROUND(passed::numeric / NULLIF(total_checks, 0) * 100, 1) AS pass_rate,
            CASE
                WHEN failed > 0 THEN 'CRITICAL'
                WHEN warned > 0 THEN 'WARNING'
                ELSE 'HEALTHY'
            END AS status
        FROM v_latest_reports
        """,

        """
        CREATE OR REPLACE VIEW v_platform_health AS
        SELECT
            SUM(total_checks)  AS total_checks,
            SUM(passed)        AS total_passed,
            SUM(failed)        AS total_failed,
            SUM(warned)        AS total_warned,
            ROUND(SUM(passed)::numeric / NULLIF(SUM(total_checks), 0) * 100, 1) AS raw_pass_rate,
            COUNT(*)           AS contract_count
        FROM v_latest_reports
        """,

        """
        CREATE OR REPLACE VIEW v_active_violations AS
        SELECT
            v.violation_id,
            v.check_id,
            split_part(v.check_id, '.', 1) AS contract_id,
            v.severity,
            v.message,
            v.detected_at,
            v.blast_radius,
            v.blame_chain,
            v.injection_note
        FROM violations v
        ORDER BY
            CASE v.severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH'     THEN 2
                WHEN 'MEDIUM'   THEN 3
                ELSE 4
            END,
            v.detected_at DESC
        """,

        """
        CREATE OR REPLACE VIEW v_interface_risk_scores AS
        SELECT
            rs.contract_id,
            rs.subscriber_id,
            rs.validation_mode,
            rs.contact,
            jsonb_array_length(rs.breaking_fields)   AS breaking_field_count,
            jsonb_array_length(rs.fields_consumed)   AS fields_consumed_count,
            CASE rs.validation_mode
                WHEN 'ENFORCE' THEN 3
                WHEN 'WARN'    THEN 2
                ELSE 1
            END AS mode_score,
            COALESCE(vc.critical_count, 0) AS active_critical,
            COALESCE(vc.high_count, 0)     AS active_high,
            (
                CASE rs.validation_mode WHEN 'ENFORCE' THEN 3 WHEN 'WARN' THEN 2 ELSE 1 END
                + jsonb_array_length(rs.breaking_fields) * 2
                + COALESCE(vc.critical_count, 0) * 3
                + COALESCE(vc.high_count, 0) * 2
            ) AS risk_score
        FROM registry_subscriptions rs
        LEFT JOIN (
            SELECT
                split_part(check_id, '.', 1) AS contract_id,
                COUNT(*) FILTER (WHERE severity = 'CRITICAL') AS critical_count,
                COUNT(*) FILTER (WHERE severity = 'HIGH')     AS high_count
            FROM violations
            WHERE injection_note IS NOT TRUE
            GROUP BY split_part(check_id, '.', 1)
        ) vc ON vc.contract_id = rs.contract_id
        ORDER BY risk_score DESC
        """
    ]
    for view_sql in views:
        db.execute(text(view_sql))
    db.commit()
