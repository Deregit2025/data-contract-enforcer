from dagster import (
    Definitions,
    define_asset_job,
    AssetSelection,
    ScheduleDefinition,
)

from orchestration.dagster_pipeline.assets import (
    generated_contracts,
    validation_reports,
    schema_evolution_report,
    ai_metrics,
    violation_attribution,
    enforcer_report,
)
from orchestration.dagster_pipeline.sensors import output_file_sensor

# ── All assets in pipeline order ──────────────────────────────────────────────
all_assets = [
    generated_contracts,
    validation_reports,
    schema_evolution_report,
    ai_metrics,
    violation_attribution,
    enforcer_report,
]

# ── Job: run the full pipeline ─────────────────────────────────────────────────
enforcement_pipeline_job = define_asset_job(
    name="enforcement_pipeline_job",
    selection=AssetSelection.all(),
    description="Full sentinel-contracts enforcement pipeline — "
                "contract generation → validation → schema evolution → "
                "AI extensions → attribution → report.",
)

# ── Optional schedule: run every night at midnight ────────────────────────────
nightly_schedule = ScheduleDefinition(
    job=enforcement_pipeline_job,
    cron_schedule="0 0 * * *",
    name="nightly_enforcement_schedule",
)

# ── Dagster entry point ────────────────────────────────────────────────────────
defs = Definitions(
    assets=all_assets,
    jobs=[enforcement_pipeline_job],
    sensors=[output_file_sensor],
    schedules=[nightly_schedule],
)