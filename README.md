## `README.md`

```markdown
# sentinel-contracts
## Data Contract Enforcer — Schema Integrity & Lineage Attribution System

A deployable data contract enforcement platform for AI-powered pipelines.
Automatically validates inter-system data contracts, traces violations to
their source commit, and generates plain-English health reports across
five interconnected systems.

---

## What This System Does

This platform turns every data dependency between five AI systems into a
machine-checked contract. When a contract is broken — by a schema change,
a type drift, or a statistical shift — the enforcer catches it, traces it
to the commit that caused it, and produces a blast radius report showing
every downstream system affected.

The five systems monitored:
- **Week 1** — Intent Code Correlator
- **Week 2** — Digital Courtroom
- **Week 3** — Document Refinery
- **Week 4** — Brownfield Cartographer
- **Week 5** — Event Sourcing Platform

---

## Repository Structure

```
contract-enforcer/
├── contracts/                  ← core enforcement scripts
│   ├── generator.py            ← auto-generates contracts from data
│   ├── runner.py               ← validates data against contracts
│   ├── attributor.py           ← traces violations to git commits
│   ├── schema_analyzer.py      ← detects and classifies schema changes
│   ├── ai_extensions.py        ← AI-specific contract checks
│   └── report_generator.py     ← generates stakeholder PDF report
├── generated_contracts/        ← auto-generated YAML + dbt contracts
├── validation_reports/         ← structured validation report JSON
├── violation_log/              ← violation records JSONL
├── schema_snapshots/           ← timestamped schema snapshots
├── enforcer_report/            ← PDF + JSON enforcer report
├── outputs/                    ← migrated data from all 5 systems
│   ├── week1/intent_records.jsonl
│   ├── week2/verdicts.jsonl
│   ├── week3/extractions.jsonl
│   ├── week4/lineage_snapshots.jsonl
│   ├── week5/events.jsonl
│   └── traces/runs.jsonl
├── migrations/                 ← data migration scripts
├── tests/                      ← unit tests
├── DOMAIN_NOTES.md             ← Phase 0 domain knowledge
└── README.md                   ← this file
```

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/sentinel-contracts.git
cd sentinel-contracts
```

### 2. Create and activate virtual environment

```bash
# create
python -m venv venv

# activate — windows
venv\Scripts\Activate.ps1

# activate — mac/linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
# copy the example file
cp .env.example .env

# open .env and add your keys
OPENROUTER_API_KEY=your_key_here
```

### 5. Run migrations to prepare data

```bash
python migrations/migrate_all.py
```

---

## Running Each Script

### Step 1 — ContractGenerator

Reads JSONL data files, profiles them statistically, and writes
Bitol-compatible YAML contracts plus dbt schema.yml files.

```bash
# generate contract for week 3
python contracts/generator.py \
  --source outputs/week3/extractions.jsonl \
  --output generated_contracts/

# generate contract for week 5
python contracts/generator.py \
  --source outputs/week5/events.jsonl \
  --output generated_contracts/
```

**Expected output:**
```
Processing: outputs/week3/extractions.jsonl
  Contract ID: week3-document-refinery-extractions
  Loaded 100 records
  Structural profile: 18 columns
  Statistical profile: 6 numeric columns
  Downstream consumers: 1
  LLM annotations: 8 columns
  Contract written: generated_contracts/week3_document_refinery_extractions.yaml
  dbt schema written: generated_contracts/week3_document_refinery_extractions_dbt.yml
  Snapshot saved: schema_snapshots/week3-.../2025-01-15T14-23-00.yaml
Done.
```

---

### Step 2 — ValidationRunner

Executes every clause in a contract against a data snapshot.
Produces a structured JSON report with PASS/FAIL/WARN/ERROR
per check.

```bash
# validate week 3
python contracts/runner.py \
  --contract generated_contracts/week3_extractions.yaml \
  --data outputs/week3/extractions.jsonl

# validate week 5
python contracts/runner.py \
  --contract generated_contracts/week5_events.yaml \
  --data outputs/week5/events.jsonl
```

**Expected output:**
```
Running validation: week3-document-refinery-extractions
  Records: 100
  Results:
    PASS:  22
    FAIL:  0
    WARN:  0
    ERROR: 0
    TOTAL: 22
  Report written: validation_reports/week3_20250115_1423.json
```

---

### Step 3 — ViolationAttributor

When a FAIL result is found, traces the violation back to the
upstream git commit that caused it. Produces a ranked blame
chain with confidence scores and a blast radius report.

```bash
python contracts/attributor.py \
  --violation validation_reports/week3_20250115_1423.json \
  --lineage outputs/week4/lineage_snapshots.jsonl \
  --output violation_log/violations.jsonl
```

**Expected output:**
```
Loading violation report...
  Found 1 FAIL result
Loading lineage graph...
  Nodes: 47  Edges: 83
Running upstream traversal...
  Upstream files found: 3
Running git blame...
  Blame chain: 2 candidates
Blast radius:
  Affected nodes: 2
  Affected pipelines: 1
  Estimated records: 847
Violation written to violation_log/violations.jsonl
```

---

### Step 4 — SchemaEvolutionAnalyzer

Diffs consecutive schema snapshots, classifies every detected
change as breaking or safe, and generates a migration impact
report.

```bash
python contracts/schema_analyzer.py \
  --contract-id week3-document-refinery-extractions \
  --since "7 days ago" \
  --output validation_reports/schema_evolution_week3.json
```

**Expected output:**
```
Loading snapshots for week3-document-refinery-extractions...
  Found 2 snapshots
  Old: 2025-01-01T09-00-00.yaml
  New: 2025-01-15T09-00-00.yaml
Comparing snapshots...
  Changes detected: 1
  - confidence: RANGE_CHANGED (0.0-1.0 → 0-100) — BREAKING
Migration impact report written.
```

---

### Step 5 — AI Contract Extensions

Runs three AI-specific contract checks:
1. Embedding drift detection on extracted fact text
2. Prompt input schema validation
3. LLM output schema enforcement and violation rate tracking

```bash
python contracts/ai_extensions.py
```

**Expected output:**
```
Running AI Contract Extensions...
  Embedding drift: score=0.042 — PASS
  Prompt input validation: 100 checked, 0 quarantined — PASS
  LLM output schema: violation_rate=0.0142, trend=stable — PASS
AI metrics written to validation_reports/ai_metrics.json
```

---

### Step 6 — ReportGenerator

Reads all validation data and generates the Enforcer Report —
a plain-English PDF readable by non-engineers, with a data
health score, violation summaries, schema change descriptions,
AI risk assessment, and recommended actions.

```bash
python contracts/report_generator.py
```

**Expected output:**
```
Generating Enforcer Report...
  Health score: 87.0 / 100
  Violations this week: 0 CRITICAL, 0 HIGH, 0 MEDIUM
  Schema changes: 0
  AI risk: stable
Report written to enforcer_report/report_2025-01-15.pdf
Data written to enforcer_report/report_data.json
```

---

## Injecting a Test Violation

To demonstrate violation detection, inject a controlled
violation and re-run the pipeline:

```bash
# inject — changes confidence from 0.0-1.0 to 0-100 scale
python migrations/inject_violation.py

# run validation — should detect FAIL
python contracts/runner.py \
  --contract generated_contracts/week3_extractions.yaml \
  --data outputs/week3/extractions.jsonl

# restore clean data
python migrations/restore_violation.py
```

---

## Running Tests

```bash
pytest tests/
```

---

## Data Sources

Each week's data was migrated from the original system output
to the canonical schema using scripts in `migrations/`.

| Week | Original file | Migration script |
|------|--------------|-----------------|
| Week 1 | Roo-Code/.orchestration/agent_trace.jsonl | migrate_week1.py |
| Week 2 | langgraph-auditor/audit/langsmith_logs/ | migrate_week2.py |
| Week 3 | extractor_ai/.refinery/fact_table.jsonl | migrate_week3.py |
| Week 4 | cartographer/.cartography/lineage_graph.json | migrate_week4.py |
| Week 5 | ledger/data/seed_events.jsonl | migrate_week5.py |

Week 3 extractions were supplemented with 87 synthetic records
generated by `migrations/generate_synthetic_week3.py` to reach
the required minimum of 50 records. Synthetic records are
flagged with `"is_synthetic": true`.

---

## Contract Coverage

| Interface | Contract written | Type |
|-----------|-----------------|------|
| Week 3 → Week 4 | Yes | Bitol YAML + dbt |
| Week 5 → Week 8 | Yes | Bitol YAML + dbt |
| Week 1 → Week 2 | Partial | Bitol YAML |
| Week 2 → Week 8 | Partial | Bitol YAML |
| Week 4 → Week 8 | Yes | Bitol YAML |

---

## Tech Stack

### Core
- `pandas` — data loading and transformation
- `numpy` — statistical computations
- `ydata-profiling` — automated column profiling
- `pyyaml` — contract YAML read/write
- `jsonschema` — payload and prompt input validation
- `gitpython` — git blame and log integration
- `networkx` — lineage graph traversal
- `openai` — embeddings via OpenRouter
- `scikit-learn` — cosine similarity for drift detection
- `reportlab` — PDF report generation
- `python-dotenv` — environment variable management

### Production Additions
- `dagster` — asset-aware pipeline orchestration
- `kafka-python` — real-time data streaming
- `psycopg2-binary` — PostgreSQL storage
- `slack-sdk` — violation alerts
- `dbt-postgres` — SQL contract enforcement
- `watchdog` — local file change detection

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| OPENROUTER_API_KEY | Yes | For LLM annotation in ContractGenerator |
| POSTGRES_URL | No | For PostgreSQL storage layer |
| SLACK_WEBHOOK_URL | No | For violation alerts |
| KAFKA_BROKER | No | For real-time streaming |

---

## Violation Log Format

Every violation written to `violation_log/violations.jsonl`
follows this schema and is ingestible by the Week 8 Sentinel
pipeline without modification:

```json
{
  "violation_id":  "uuid-v4",
  "check_id":      "week3.extracted_facts.confidence.range",
  "detected_at":   "ISO 8601",
  "blame_chain": [
    {
      "rank":             1,
      "file_path":        "src/week3/extractor.py",
      "commit_hash":      "abc123...",
      "author":           "jane.doe@example.com",
      "commit_timestamp": "ISO 8601",
      "commit_message":   "feat: change confidence to percentage scale",
      "confidence_score": 0.94
    }
  ],
  "blast_radius": {
    "affected_nodes":     ["file::src/week4/cartographer.py"],
    "affected_pipelines": ["week4-lineage-generation"],
    "estimated_records":  847
  }
}
```


