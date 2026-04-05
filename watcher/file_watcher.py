import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT        = Path(__file__).resolve().parents[1]
WATCH_DIR   = ROOT / "outputs"


class EnforcerEventHandler(FileSystemEventHandler):
    """
    Watches outputs/ for .jsonl file creation or modification.
    Logs the event — the Dagster sensor picks up the change
    on its next 30-second poll and submits a pipeline run.
    """

    def _is_relevant(self, path: str) -> bool:
        return path.endswith(".jsonl")

    def on_created(self, event):
        if not event.is_directory and self._is_relevant(event.src_path):
            log.info(f"NEW FILE detected: {event.src_path}")
            log.info("Dagster sensor will pick this up within 30 seconds.")

    def on_modified(self, event):
        if not event.is_directory and self._is_relevant(event.src_path):
            log.info(f"FILE MODIFIED: {event.src_path}")
            log.info("Dagster sensor will pick this up within 30 seconds.")

    def on_deleted(self, event):
        if not event.is_directory and self._is_relevant(event.src_path):
            log.warning(f"FILE DELETED: {event.src_path}")


def start_watcher():
    if not WATCH_DIR.exists():
        log.error(f"Watch directory does not exist: {WATCH_DIR}")
        return

    handler  = EnforcerEventHandler()
    observer = Observer()
    observer.schedule(handler, str(WATCH_DIR), recursive=True)
    observer.start()

    log.info(f"Watching: {WATCH_DIR}")
    log.info("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    start_watcher()