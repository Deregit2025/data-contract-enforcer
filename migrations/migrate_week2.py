import json
import uuid
import hashlib
import random
import os
from datetime import datetime, timezone, timedelta

INPUT_PATH = r"C:\Users\derej\Desktop\Intensive\langgraph-auditor\audit\verdicts.jsonl"
OUTPUT_PATH = "outputs/week2/verdicts.jsonl"

CRITERION_NAMES = [
    "Git Forensic Analysis",
    "State Management Rigor",
    "Graph Orchestration Architecture",
    "Safe Tool Engineering",
    "Structured Output Enforcement",
    "Judicial Nuance and Dialectics",
    "Chief Justice Synthesis Engine",
    "Theoretical Depth (Documentation)",
    "Report Accuracy (Cross-Reference)",
    "Architectural Diagram Analysis"
]

VERDICTS   = ["PASS", "FAIL", "WARN"]
TARGET_REFS = [
    "local/repository",
    "src/graph.py",
    "src/nodes/judges.py",
    "src/state.py",
    "src/tools/git_tools.py",
    "src/nodes/justice.py",
    "notebooks/example_exploration.ipynb",
    "tests/test_graph.py",
    "README.md",
    "src/orchestrator.py"
]

def fix_rubric_id(rubric_id):
    # ensure exactly 64 hex characters
    if len(rubric_id) < 64:
        rubric_id = rubric_id + "0" * (64 - len(rubric_id))
    return rubric_id[:64]

def generate_scores():
    scores = {}
    total  = 0
    for criterion in CRITERION_NAMES:
        score = random.randint(1, 5)
        total += score
        scores[criterion] = {
            "score":    score,
            "evidence": [
                f"Evidence item 1 for {criterion}",
                f"Evidence item 2 for {criterion}"
            ],
            "notes": f"Synthetic evaluation note for {criterion}."
        }
    weighted_avg = round(total / len(CRITERION_NAMES), 2)
    return scores, weighted_avg

def generate_verdict_record():
    scores, overall_score = generate_scores()
    days_ago   = random.randint(0, 60)
    evaluated  = datetime.now(timezone.utc) - timedelta(days=days_ago)

    if overall_score >= 3.5:
        verdict = "PASS"
    elif overall_score >= 2.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "verdict_id":      str(uuid.uuid4()),
        "target_ref":      random.choice(TARGET_REFS),
        "rubric_id":       hashlib.sha256(
                               str(uuid.uuid4()).encode()
                           ).hexdigest(),
        "rubric_version":  "3.0.0",
        "scores":          scores,
        "overall_verdict": verdict,
        "overall_score":   overall_score,
        "confidence":      round(random.uniform(0.60, 0.95), 2),
        "evaluated_at":    evaluated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_synthetic":    True
    }

def migrate_record(record):
    # fix rubric_id length
    record["rubric_id"] = fix_rubric_id(record["rubric_id"])
    return record

def main():
    # load real records
    real_records = []
    try:
        with open(INPUT_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        real_records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        print(f"Loaded {len(real_records)} real records")
    except FileNotFoundError:
        print("Real file not found — generating synthetic only")

    # fix real records
    fixed_real = [migrate_record(r) for r in real_records]

    # generate synthetic to reach 20 total
    target    = 20
    needed    = max(0, target - len(fixed_real))
    synthetic = [generate_verdict_record() for _ in range(needed)]
    print(f"Generated {needed} synthetic records")

    all_records = fixed_real + synthetic

    os.makedirs("outputs/week2", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    print(f"Written {len(all_records)} records to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()