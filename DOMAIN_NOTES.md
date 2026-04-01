# DOMAIN_NOTES.md
# Data Contract Enforcer — Domain Notes
# Week 7 — Schema Integrity & Lineage Attribution System

---

## Question 1: What is the difference between a backward-compatible and a breaking schema change? Give three examples of each, drawn from your own week 1–5 output schemas.

A schema change is **backward compatible** when existing consumers
can continue reading data produced by the new schema without
any modification. A **breaking change** is one where existing
consumers will either crash, produce wrong results, or silently
consume incorrect data.

### Backward-Compatible Examples from My Systems

**Example 1 — Adding a nullable field (Week 3)**
The Week 3 extraction record gained an `is_synthetic` boolean
field during development. This field is nullable and optional.
Any downstream consumer that was reading `extracted_facts`,
`entities`, and `confidence` continues to work without change
because it simply ignores the new field it does not know about.
Schema: `outputs/week3/extractions.jsonl` — field `is_synthetic`
added with no required constraint.

**Example 2 — Adding a new enum value (Week 5)**
The Week 5 event sourcing platform introduced a new
`event_type` value `DocumentUploadRequested` alongside the
existing `ApplicationSubmitted`. Consumers that handle known
event types and ignore unknown ones continue to work correctly.
The new value is purely additive.
Schema: `outputs/week5/events.jsonl` — `event_type` enum
extended with new PascalCase value.

**Example 3 — Widening a type (Week 5)**
The `sequence_number` field in Week 5 events could be widened
from a 32-bit integer to a 64-bit integer to support larger
aggregate histories. Any consumer reading it as a number
continues to work because no precision is lost.
Schema: `outputs/week5/events.jsonl` — `sequence_number`
widened from int32 to int64.

### Breaking Examples from My Systems

**Example 1 — Renaming a field (Week 3)**
The Week 3 extractor originally output `timestamp` as the
processing time field. The migration renamed it to
`extracted_at` to match the canonical schema. Any consumer
reading `timestamp` would receive null after this change and
produce silent failures downstream.
Schema: `outputs/week3/extractions.jsonl` — `timestamp`
renamed to `extracted_at`.

**Example 2 — Changing value scale (Week 3)**
The most critical breaking change in this project. The
`confidence` field in `extracted_facts` must be a float
between 0.0 and 1.0. If the extractor changed this to an
integer between 0 and 100, the Week 4 Cartographer would
read confidence values of 87 and treat them as 8700% confident
— completely corrupting downstream lineage metadata. This
change passes structural type checks because the field is
still numeric. Only statistical drift detection catches it.
Schema: `outputs/week3/extractions.jsonl` —
`extracted_facts[*].confidence` scale change.

**Example 3 — Removing a required field (Week 5)**
The Week 5 event schema requires a `metadata` block containing
`correlation_id`, `user_id`, and `source_service`. If the
`source_service` field were removed, the Week 8 enforcement
system would fail to attribute violations to their originating
service, breaking the entire blame chain. This is a hard
failure not a silent one — but it demonstrates why required
field removal is always breaking.
Schema: `outputs/week5/events.jsonl` — `metadata.source_service`
removal would break attribution.

---

## Question 2: The Week 3 Document Refinery's confidence field is float 0.0–1.0. An update changes it to integer 0–100. Trace the failure this causes in the Week 4 Cartographer. Write the data contract clause that would catch this change before it propagates, in Bitol YAML format.

### The Failure Chain

The Week 3 Document Refinery extracts facts from documents and
assigns each fact a confidence score between 0.0 and 1.0.
For example: `{"fact_id": "abc", "confidence": 0.87}`.

The Week 4 Brownfield Cartographer ingests these extraction
records and uses the `confidence` value to weight edges in
the lineage graph. A fact with confidence 0.87 means the
cartographer is 87% sure this fact came from this source.

Now imagine a developer changes the extractor to output
confidence as an integer percentage: `{"confidence": 87}`.

The failure propagates as follows:

**Step 1** — The extractor writes `confidence: 87` instead
of `confidence: 0.87`. Structurally the field is still
numeric. No type error is raised.

**Step 2** — The ValidationRunner runs its range check:
`minimum: 0.0, maximum: 1.0`. It detects `max=98, mean=84.3`
and immediately raises a CRITICAL FAIL on the range check
`week3.extracted_facts.confidence.range`.

**Step 3** — Without the contract check, the Cartographer
reads `confidence: 87` and treats it as a weight. All
lineage edges now have confidence weights between 70 and 100
instead of 0.7 and 1.0. The graph traversal logic that
filters edges below a threshold of 0.5 now keeps everything
because all values are above 70. The lineage graph becomes
meaningless — every fact appears to be maximally certain.

**Step 4** — The statistical drift check also fires. The
baseline mean for confidence was 0.857. The new mean is 84.3.
The deviation is over 1000 standard deviations. This is
caught even if the range check somehow missed it.

### The Contract Clause in Bitol YAML

```yaml
schema:
  extracted_facts:
    type: array
    items:
      confidence:
        type: number
        minimum: 0.0
        maximum: 1.0
        required: true
        description: >
          Extraction confidence score. MUST be a float between
          0.0 and 1.0. A value of 0.87 means 87% confident.
          BREAKING CHANGE if scale is changed to 0-100 integer.
        business_rule: >
          value >= 0.0 AND value <= 1.0. Any mean above 1.0
          indicates a scale violation. Trigger CRITICAL alert
          and block downstream Cartographer pipeline.

quality:
  type: SodaChecks
  specification:
    checks for extractions:
      - min(extracted_facts_confidence_min) >= 0.0
      - max(extracted_facts_confidence_max) <= 1.0
```

---

## Question 3: The Cartographer (Week 4) produced a lineage graph. Explain, step by step, how the Data Contract Enforcer uses that graph to produce a blame chain when a contract violation is detected. Include the specific graph traversal logic.

When the ValidationRunner detects a FAIL on
`week3.extracted_facts.confidence.range`, the
ViolationAttributor takes over. Here is the step-by-step
process using the Week 4 lineage graph.

**Step 1 — Load the lineage graph**
The ViolationAttributor opens
`outputs/week4/lineage_snapshots.jsonl` and loads the most
recent snapshot. It builds a directed graph using networkx
where nodes are files, tables, services, and models, and
edges represent relationships like IMPORTS, CALLS, READS,
WRITES, PRODUCES, CONSUMES.

**Step 2 — Identify the failing node**
The check ID `week3.extracted_facts.confidence.range` maps
to the Week 3 extraction output file. The attributor finds
the node `file::outputs/week3/extractions.jsonl` in the
graph as the starting point.

**Step 3 — Traverse upstream using BFS**
The graph is reversed so edges point backwards — from
consumer to producer. Breadth-first search starts from the
failing node and walks upstream stopping at FILE type nodes.
Each hop away from the failing node increases the distance
counter. The traversal stops at external boundaries or
file system roots.

For example:
```
outputs/week3/extractions.jsonl
    ← produced by: src/week3/extractor.py        (hop 1)
    ← which imports: src/week3/confidence_scorer.py  (hop 2)
    ← which imports: src/utils/scoring.py            (hop 3)
```

**Step 4 — Run git blame on each upstream file**
For each file found at hop 1 and hop 2, the attributor runs:
```
git log --follow --since="14 days ago" \
  --format="%H|%an|%ae|%ai|%s" -- src/week3/extractor.py
```
This returns all commits that touched the file in the last
14 days. For each commit it computes a confidence score:
`score = 1.0 - (days_since_commit × 0.1) - (hop_count × 0.2)`

**Step 5 — Rank candidates and output blame chain**
Candidates are sorted by confidence score descending. The
top 5 are written to `violation_log/violations.jsonl` with
the commit hash, author, timestamp, and commit message.

**Step 6 — Compute blast radius**
The attributor then traverses downstream from the failing
node. Every node that transitively depends on
`extractions.jsonl` is in the blast radius. In our platform
this includes the Week 4 Cartographer and the Week 8
Enforcer itself.

---

## Question 4: Write a data contract for the LangSmith trace_record schema. Include at least one structural clause, one statistical clause, and one AI-specific clause. Show it in Bitol-compatible YAML.

```yaml
kind: DataContract
apiVersion: v3.0.0
id: langsmith-trace-records
info:
  title: LangSmith Trace Records
  version: 1.0.0
  owner: week7-enforcer
  description: >
    One record per LangSmith run. Covers LLM calls, chain
    executions, tool invocations, and retriever calls made
    across all five platform systems.

servers:
  local:
    type: local
    path: outputs/traces/runs.jsonl
    format: jsonl

schema:
  id:
    type: string
    format: uuid
    required: true
    unique: true
    description: Unique run identifier from LangSmith.

  run_type:
    type: string
    required: true
    enum: [llm, chain, tool, retriever, embedding]
    description: >
      Structural clause — run_type must be exactly one of
      five registered values. Any other value indicates an
      unregistered run type that must be added to the schema
      registry before use.

  total_tokens:
    type: integer
    required: true
    minimum: 0
    description: >
      Total tokens consumed. Must equal prompt_tokens plus
      completion_tokens. Validated by cross-field check.

  total_cost:
    type: number
    required: true
    minimum: 0.0
    description: Cost in USD. Must be non-negative.

  start_time:
    type: string
    format: date-time
    required: true

  end_time:
    type: string
    format: date-time
    required: true
    description: Must be strictly greater than start_time.

quality:
  type: SodaChecks
  specification:
    checks for traces:
      # structural clause
      - missing_count(id) = 0
      - duplicate_count(id) = 0
      - invalid_count(run_type) = 0
      # statistical clause
      - avg(total_tokens) between 500 and 10000
      - max(total_cost) < 1.0
      - min(total_cost) >= 0.0
      # AI-specific clause
      - avg(total_tokens) < avg(prompt_tokens) * 3

ai_extensions:
  embedding_drift:
    applies_to: inputs
    baseline_path: schema_snapshots/embedding_baselines.npz
    threshold: 0.15
    description: >
      AI-specific clause — if the semantic centroid of LLM
      inputs drifts more than 0.15 cosine distance from the
      baseline, the system is processing a different category
      of content than it was designed for. Trigger WARN and
      notify the platform team.

  token_anomaly:
    description: >
      Statistical clause — if mean total_tokens deviates
      more than 3 standard deviations from the baseline mean,
      emit FAIL. This catches prompt injection attacks that
      dramatically increase token consumption, and also
      catches accidental context window overflow.
```

---

## Question 5: What is the most common failure mode of contract enforcement systems in production? Why do contracts get stale? How does your architecture prevent this?

### The Most Common Failure Mode — Staleness

The most common failure mode of contract enforcement systems
in production is not a technical failure but an organisational
one: **contracts get written once and never updated**. Within
three months of deployment, the majority of production data
contracts no longer accurately describe the data they govern.

This happens for three reasons.

**Reason 1 — Contracts are written by the consumer not the
producer.** The downstream team writes the contract to
describe what they expect. The upstream team that produces
the data was never involved and feels no ownership. When the
producer makes a change they do not update the contract
because they did not write it and may not even know it exists.

**Reason 2 — Contract enforcement is manual.** If running
the contract checks requires a human to remember to do it,
it will not get done. Teams move fast. Manual steps get
skipped. A contract that is not enforced on every data
update is a document, not a contract.

**Reason 3 — There is no feedback loop.** When a contract
fails, the failure must reach the person who can fix it
within minutes not days. If violations are written to a
log file that nobody reads, the contract is effectively
dead even if technically active.

### Concrete Evidence from My Own Platform

In my Week 3 system, the `extraction_ledger.jsonl` file
produced by the original extractor bore no resemblance to
the canonical extraction record schema. Fields were named
differently, the `extracted_facts` array was entirely absent,
and `doc_id` was a plain string instead of a UUID. This is
exactly what contract staleness looks like in practice —
the system evolved but the expected schema did not.

### How My Architecture Prevents This

**Prevention 1 — Auto-generation not manual authoring.**
The `ContractGenerator` reads the actual data and generates
contracts from observation. The contract always reflects
what the data currently looks like. A human never writes
a contract clause — the system infers it. This eliminates
the gap between documented expectation and actual behavior.

**Prevention 2 — Schema snapshots on every run.**
Every time the `ContractGenerator` runs it saves a
timestamped snapshot of the inferred schema. The
`SchemaEvolutionAnalyzer` diffs consecutive snapshots
automatically. If the schema changes between runs, the
change is detected, classified as breaking or safe, and
a migration impact report is generated immediately. The
contract updates itself.

**Prevention 3 — Statistical baselines.**
The first run establishes a statistical baseline for every
numeric column. Every subsequent run compares the live
distribution against the baseline. The confidence scale
change from 0.0–1.0 to 0–100 would produce a mean shift
of over 1000 standard deviations. This is caught even if
the structural type check passes because the field is still
numeric.

**Prevention 4 — Violation log as first-class data.**
Every violation is written to `violation_log/violations.jsonl`
in a format that the Week 8 Sentinel can ingest without
modification. Violations are not buried in log files — they
are structured data that feeds downstream alerting,
reporting, and attribution systems automatically.

**Prevention 5 — Blast radius makes cost visible.**
When a contract violation is detected, the blast radius
report shows exactly how many downstream systems and records
are affected. This makes the cost of ignoring a contract
violation concrete and visible to the team lead. A violation
that affects 847 records across 3 downstream systems is
harder to ignore than an entry in a log file.

---


