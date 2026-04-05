import json
from pathlib import Path
from dagster import sensor, RunRequest, SensorEvaluationContext, DefaultSensorStatus

ROOT        = Path(__file__).resolve().parents[2]
CURSOR_FILE = ROOT / ".dagster_storage" / "watchdog_cursor.json"
FLAG_FILE   = ROOT / ".dagster_storage" / "force_run.flag"


def _load_cursor() -> dict:
    if CURSOR_FILE.exists():
        try:
            return json.loads(CURSOR_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_cursor(cursor: dict):
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_FILE.write_text(json.dumps(cursor))


@sensor(
    job_name="enforcement_pipeline_job",
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=30,
    description="Watches outputs/ for new or modified JSONL files and triggers the pipeline.",
)
def output_file_sensor(context: SensorEvaluationContext):
    # ── Priority 1: direct trigger from file_watcher.py ──────────────────────
    if FLAG_FILE.exists():
        reason = FLAG_FILE.read_text().strip()
        FLAG_FILE.unlink()  # consume the flag
        context.log.info(f"Force trigger from watcher: {reason}")
        yield RunRequest(
            run_key=f"watcher_trigger_{int(FLAG_FILE.stat().st_mtime) if False else hash(reason) & 0xFFFFFF}",
            run_config={},
            tags={"trigger": "file_watcher", "reason": reason[:80]},
        )
        return

    # ── Priority 2: mtime polling fallback ────────────────────────────────────
    outputs_dir = ROOT / "outputs"
    if not outputs_dir.exists():
        return

    cursor    = _load_cursor()
    new_cursor = {}
    changed_files = []

    for jsonl_file in outputs_dir.rglob("*.jsonl"):
        mtime = str(jsonl_file.stat().st_mtime)
        new_cursor[str(jsonl_file)] = mtime
        # Only flag as changed if cursor already knew about this file
        # (skip on first boot — avoids triggering on all existing files)
        if str(jsonl_file) in cursor and cursor[str(jsonl_file)] != mtime:
            changed_files.append(jsonl_file.name)

    _save_cursor(new_cursor)

    if changed_files:
        context.log.info(f"Changed files detected: {changed_files}")
        yield RunRequest(
            run_key=f"file_change_{'_'.join(sorted(changed_files)[:3])}_{new_cursor.get(str(list(outputs_dir.rglob('*.jsonl'))[0]),'')}",
            run_config={},
            tags={"trigger": "mtime_sensor", "changed_files": ", ".join(changed_files)},
        )
