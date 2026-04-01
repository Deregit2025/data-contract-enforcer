import subprocess
import sys

scripts = [
    "migrations/migrate_week1.py",
    "migrations/migrate_week2.py",
    "migrations/migrate_week3.py",
    "migrations/migrate_week4.py",
    "migrations/migrate_week5.py",
]

for script in scripts:
    print(f"\n{'='*50}")
    print(f"Running {script}")
    print('='*50)
    result = subprocess.run(
        [sys.executable, script],
        capture_output=False
    )
    if result.returncode != 0:
        print(f"ERROR: {script} failed")
        sys.exit(1)

print("\nAll migrations completed successfully")