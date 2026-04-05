import json
from pathlib import Path
from dagster import sensor, RunRequest, SensorEvaluationContext, DefaultSensorStatus

ROOT       = Path(__file__).resolve().parents[2]
CURSOR_FILE = ROOT / ".dagster_storage" / "watchdog_cursor.json"


def _load_cursor() -> dict:
    """Load the last-seen file modification times."""
    if CURSOR_FILE.exists():
        try:
            return json.loads(CURSOR_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_cursor(cursor: dict):
    """Save current file modification times."""
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_FILE.write_text(json.dumps(cursor))


@sensor(
    job_name="enforcement_pipeline_job",
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=30,
    description="Watches outputs/ for new or modified JSONL files and triggers the pipeline.",
)
def output_file_sensor(context: SensorEvaluationContext):
    """
    Polls the outputs/ directory every 30 seconds.
    If any .jsonl file has been created or modified since the last check,
    submits a new Dagster run for the full enforcement pipeline.
    """
    outputs_dir = ROOT / "outputs"
    if not outputs_dir.exists():
        context.log.warning(f"outputs/ directory not found at {outputs_dir}")
        return

    cursor = _load_cursor()
    new_cursor = {}
    changed_files = []

    # Walk all subdirectories and collect .jsonl files
    for jsonl_file in outputs_dir.rglob("*.jsonl"):
        mtime = str(jsonl_file.stat().st_mtime)
        new_cursor[str(jsonl_file)] = mtime

        last_mtime = cursor.get(str(jsonl_file))
        if last_mtime != mtime:
            changed_files.append(jsonl_file.name)

    _save_cursor(new_cursor)

    if changed_files:
        context.log.info(f"Changed files detected: {changed_files}")
        yield RunRequest(
            run_key=f"file_change_{'_'.join(changed_files[:3])}",
            run_config={},
            tags={
                "trigger":       "watchdog_sensor",
                "changed_files": ", ".join(changed_files),
            },
        )
    else:
        context.log.debug("No file changes detected.")