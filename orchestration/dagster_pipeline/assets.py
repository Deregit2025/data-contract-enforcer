import subprocess
import json
import yaml
from pathlib import Path
from dagster import asset, AssetExecutionContext, MetadataValue
from streaming.kafka.producer import publish_violations

ROOT = Path(__file__).resolve().parents[2]

CONTRACTS = [
    "week1_intent_code_correlator",
    "week2_digital_courtroom",
    "week3_document_refinery_extractions",
    "week4_brownfield_cartographer",
    "week5_event_sourcing_platform",
]

DATA_SOURCES = {
    "week1_intent_code_correlator":        "outputs/week1/intent_records.jsonl",
    "week2_digital_courtroom":             "outputs/week2/verdicts.jsonl",
    "week3_document_refinery_extractions": "outputs/week3/extractions.jsonl",
    "week4_brownfield_cartographer":       "outputs/week4/lineage_snapshots.jsonl",
    "week5_event_sourcing_platform":       "outputs/week5/events.jsonl",
}


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _count_clauses(yaml_path: Path) -> int:
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8", errors="replace"))
        spec = data.get("quality", {}).get("specification", {})
        for v in spec.values():
            if isinstance(v, list):
                return len(v)
    except Exception:
        pass
    return 0


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _load_jsonl(path: Path) -> list:
    lines = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return lines


# ─────────────────────────────────────────
# ASSET 1 — Contract Generation
# ─────────────────────────────────────────

@asset(
    description="Generate Bitol YAML contracts for all 5 pipeline outputs using ContractGenerator.",
    group_name="enforcement_pipeline",
)
def generated_contracts(context: AssetExecutionContext):
    results = {}
    for contract_id, data_path in DATA_SOURCES.items():
        full_data_path = ROOT / data_path
        if not full_data_path.exists():
            context.log.warning(f"Data file not found, skipping: {full_data_path}")
            results[contract_id] = "skipped"
            continue

        output_dir = ROOT / "generated_contracts"
        output_dir.mkdir(exist_ok=True)

        result = subprocess.run(
            ["python", str(ROOT / "contracts" / "generator.py"),
             "--source", str(full_data_path),
             "--output", str(output_dir)],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            context.log.error(f"Generator failed for {contract_id}: {result.stderr}")
            results[contract_id] = "failed"
        else:
            context.log.info(f"Contract generated: {contract_id}")
            results[contract_id] = "generated"

    # ── Rich metadata ──────────────────────────────────────────────────────────
    contracts_dir = ROOT / "generated_contracts"
    rows = []
    total_clauses = 0
    for contract_id in DATA_SOURCES:
        yaml_path = contracts_dir / f"{contract_id}.yaml"
        if yaml_path.exists():
            clauses = _count_clauses(yaml_path)
            total_clauses += clauses
            status = results.get(contract_id, "existing")
            rows.append(f"| `{contract_id}` | {clauses} | {status} |")
        else:
            rows.append(f"| `{contract_id}` | — | {results.get(contract_id, 'missing')} |")

    md = "## Generated Contracts\n\n"
    md += "| Contract | Clauses | Status |\n"
    md += "|----------|---------|--------|\n"
    md += "\n".join(rows)
    md += f"\n\n**Total quality clauses:** {total_clauses}  \n"
    md += "**Format:** Bitol YAML v3.0.0 + companion dbt schema.yml  \n"
    md += "**Key clause:** `max(extracted_facts_confidence_max) <= 1.0` — catches the 0→100 scale change"

    context.add_output_metadata({
        "contracts_generated": MetadataValue.int(sum(1 for v in results.values() if v == "generated")),
        "contracts_skipped":   MetadataValue.int(sum(1 for v in results.values() if v == "skipped")),
        "total_clauses":       MetadataValue.int(total_clauses),
        "contract_summary":    MetadataValue.md(md),
    })
    return results


# ─────────────────────────────────────────
# ASSET 2 — Validation Run
# ─────────────────────────────────────────

@asset(
    deps=[generated_contracts],
    description="Run ValidationRunner on all 5 contracts in ENFORCE mode. Catches structural, statistical, temporal, and AI violations.",
    group_name="enforcement_pipeline",
)
def validation_reports(context: AssetExecutionContext):
    results = {}
    for contract_id, data_path in DATA_SOURCES.items():
        full_data_path = ROOT / data_path
        contract_file  = ROOT / "generated_contracts" / f"{contract_id}.yaml"

        if not full_data_path.exists() or not contract_file.exists():
            context.log.warning(f"Skipping {contract_id} — missing data or contract")
            results[contract_id] = "skipped"
            continue

        result = subprocess.run(
            ["python", str(ROOT / "contracts" / "runner.py"),
             "--data",     str(full_data_path),
             "--contract", str(contract_file),
             "--mode",     "ENFORCE"],
            capture_output=True, text=True, cwd=ROOT
        )
        status = "passed" if result.returncode == 0 else "violated"
        context.log.info(f"Validation {status}: {contract_id}")
        results[contract_id] = status

    # ── Rich metadata: per-contract table + failing checks ────────────────────
    reports_dir = ROOT / "validation_reports"
    all_fails   = []
    summary_rows = []
    total_checks = total_passed = total_failed = 0

    for contract_id in DATA_SOURCES:
        report_files = sorted(reports_dir.glob(f"{contract_id.replace('_', '')[:6]}*.json"))
        # try broader match
        if not report_files:
            prefix = contract_id.split("_")[0]  # week1, week2, etc.
            report_files = sorted(reports_dir.glob(f"{prefix}*.json"))
            report_files = [r for r in report_files
                            if not r.name.startswith(("schema_", "ai_", "migration_"))]

        if report_files:
            data = _load_json(report_files[-1])
            tc = data.get("total_checks", 0)
            tp = data.get("passed", 0)
            tf = data.get("failed", 0)
            total_checks += tc
            total_passed += tp
            total_failed += tf
            status_icon = "FAIL" if tf > 0 else "PASS"
            summary_rows.append(f"| `{contract_id}` | {tc} | {tp} | {tf} | **{status_icon}** |")
            for r in data.get("results", []):
                if r.get("status") == "FAIL":
                    all_fails.append({
                        "contract": contract_id,
                        "check":    r.get("check_id", ""),
                        "severity": r.get("severity", ""),
                        "records":  r.get("records_failing", "?"),
                        "message":  r.get("message", ""),
                    })
        else:
            summary_rows.append(f"| `{contract_id}` | — | — | — | no report |")

    fail_rows = [
        f"| `{f['check'].split('.')[-1]}` | `{f['contract']}` | {f['severity']} | {f['records']} | {f['message'][:60]} |"
        for f in sorted(all_fails, key=lambda x: x["severity"])
    ]

    md  = "## Validation Summary\n\n"
    md += "| Contract | Checks | Passed | Failed | Result |\n"
    md += "|----------|--------|--------|--------|--------|\n"
    md += "\n".join(summary_rows)
    md += f"\n\n**Platform pass rate:** {round(total_passed/total_checks*100,1) if total_checks else 0}%\n\n"

    if fail_rows:
        md += "### Failing Checks\n\n"
        md += "| Check | Contract | Severity | Records | Message |\n"
        md += "|-------|----------|----------|---------|--|\n"
        md += "\n".join(fail_rows[:15])

    context.add_output_metadata({
        "total_checks":   MetadataValue.int(total_checks),
        "total_passed":   MetadataValue.int(total_passed),
        "total_failed":   MetadataValue.int(total_failed),
        "pass_rate_pct":  MetadataValue.float(round(total_passed/total_checks*100, 1) if total_checks else 0),
        "validation_detail": MetadataValue.md(md),
    })
    return results


# ─────────────────────────────────────────
# ASSET 3 — Schema Evolution Analysis
# ─────────────────────────────────────────

@asset(
    deps=[validation_reports],
    description="SchemaEvolutionAnalyzer: diff consecutive schema snapshots, classify BREAKING vs SAFE changes, generate migration impact report.",
    group_name="enforcement_pipeline",
)
def schema_evolution_report(context: AssetExecutionContext):
    result = subprocess.run(
        ["python", str(ROOT / "contracts" / "schema_analyzer.py"),
         "--contract-id", "week3-document-refinery-extractions",
         "--output", str(ROOT / "validation_reports" / "schema_evolution_latest.json")],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        context.log.error(f"Schema analyzer failed: {result.stderr}")
        return {"status": "failed"}

    context.log.info(result.stdout)

    # ── Load the evolution report ─────────────────────────────────────────────
    evo_path = ROOT / "validation_reports" / "schema_evolution_latest.json"
    evo_data = _load_json(evo_path) if evo_path.exists() else {}
    changes  = evo_data.get("changes", [])

    # ── Load the latest migration impact report ───────────────────────────────
    impact_files = sorted((ROOT / "validation_reports").glob("migration_impact_*.json"))
    impact_data  = _load_json(impact_files[-1]) if impact_files else {}

    breaking = [c for c in changes if c.get("compatibility") == "BREAKING"]
    safe     = [c for c in changes if c.get("compatibility") != "BREAKING"]

    change_rows = [
        f"| `{c['field']}` | {c['change_type']} | **{c['compatibility']}** | {c.get('reason','')[:60]} |"
        for c in changes
    ]

    # Migration impact rows
    impact_rows = []
    for c in impact_data.get("changes_detected", []):
        compat = c.get("compatibility", "")
        impact_rows.append(
            f"| `{c['field']}` | {c['change_type']} | **{compat}** | {c.get('reason','')[:55]} |"
        )

    checklist = impact_data.get("migration_checklist", [])

    md  = "## Schema Evolution Analysis\n\n"
    md += f"**Contract:** week3-document-refinery-extractions  \n"
    if changes:
        md += f"**Changes detected:** {len(changes)} ({len(breaking)} BREAKING, {len(safe)} safe)\n\n"
        md += "| Field | Change Type | Compatibility | Reason |\n"
        md += "|-------|-------------|---------------|--------|\n"
        md += "\n".join(change_rows)
    else:
        md += "No changes detected in latest snapshot pair.\n"

    if impact_rows:
        md += "\n\n### Migration Impact Report\n\n"
        md += "| Field | Change Type | Compatibility | Reason |\n"
        md += "|-------|-------------|---------------|--------|\n"
        md += "\n".join(impact_rows)

    if checklist:
        md += "\n\n### Migration Checklist\n\n"
        md += "\n".join(f"- {step}" for step in checklist[:6])

    consumers = impact_data.get("consumer_analysis", [])
    if consumers:
        md += "\n\n### Affected Consumers\n\n"
        for c in consumers:
            md += f"- **{c['subscriber_id']}** (mode: `{c['validation_mode']}`) — {c.get('recommended_action','')}\n"

    context.add_output_metadata({
        "breaking_changes":    MetadataValue.int(len(breaking) or len([c for c in impact_data.get("changes_detected",[]) if c.get("compatibility")=="BREAKING"])),
        "safe_changes":        MetadataValue.int(len(safe)),
        "schema_evolution":    MetadataValue.md(md),
    })
    return {"status": "complete", "breaking_changes": len(breaking), "changes": changes}


# ─────────────────────────────────────────
# ASSET 4 — AI Contract Extensions
# ─────────────────────────────────────────

@asset(
    deps=[validation_reports],
    description="AI-specific contract checks: embedding drift (cosine distance), prompt input JSON schema validation, LLM output schema enforcement.",
    group_name="enforcement_pipeline",
)
def ai_metrics(context: AssetExecutionContext):
    result = subprocess.run(
        ["python", str(ROOT / "contracts" / "ai_extensions.py"), "--skip-embeddings"],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        context.log.error(f"AI extensions failed: {result.stderr}")
        return {"status": "failed"}

    metrics_path = ROOT / "validation_reports" / "ai_metrics.json"
    data = _load_json(metrics_path) if metrics_path.exists() else {}

    drift   = data.get("embedding_drift", {})
    prompt  = data.get("prompt_input_validation", {})
    llm_out = data.get("llm_output_schema", {})

    drift_score  = drift.get("drift_score", 0.0)
    drift_status = drift.get("status", "n/a")
    prompt_valid = prompt.get("valid", 0)
    prompt_total = prompt.get("total", 0)
    llm_viol     = llm_out.get("violation_rate", 0.0)
    llm_status   = llm_out.get("status", "n/a")

    drift_icon  = "FAIL" if drift_status == "FAIL" else "PASS"
    prompt_icon = "PASS" if prompt.get("rejected", 1) == 0 else "FAIL"
    llm_icon    = "PASS" if llm_status == "PASS" else "FAIL"

    md  = "## AI Contract Extensions\n\n"
    md += "Standard data contracts cover tabular data. These three checks are AI-specific.\n\n"
    md += "| Check | Result | Detail |\n"
    md += "|-------|--------|--------|\n"
    md += f"| Embedding Drift | **{drift_icon}** | Score: `{drift_score}` (threshold: `{drift.get('threshold', 0.15)}`) — {drift.get('message', '')} |\n"
    md += f"| Prompt Input Schema | **{prompt_icon}** | {prompt_valid}/{prompt_total} records passed JSON schema validation |\n"
    md += f"| LLM Output Schema | **{llm_icon}** | Violation rate: `{llm_viol*100:.1f}%` — {llm_out.get('message', '')} |\n"
    md += "\n\n**What embedding drift means:** cosine distance between weekly embedding batches. "
    md += "Above 0.15 means the model's representation space has shifted — downstream similarity search is silently using a different geometry.\n\n"
    md += "**No existing tool covers all three.** Confluent Schema Registry is schema-only. dbt cannot enforce AI semantics."

    context.add_output_metadata({
        "embedding_drift_score":    MetadataValue.float(float(drift_score)),
        "embedding_drift_status":   MetadataValue.text(drift_status),
        "prompt_validation_status": MetadataValue.text(prompt_icon),
        "llm_output_violation_pct": MetadataValue.float(float(llm_viol) * 100),
        "ai_checks_detail":         MetadataValue.md(md),
    })
    return data


# ─────────────────────────────────────────
# ASSET 5 — Violation Attribution
# ─────────────────────────────────────────

@asset(
    deps=[validation_reports],
    description="ViolationAttributor: BFS traversal on Week 4 lineage graph + git blame to identify the commit that caused each violation. Computes blast radius via registry + lineage.",
    group_name="enforcement_pipeline",
)
def violation_attribution(context: AssetExecutionContext):
    reports_dir  = ROOT / "validation_reports"
    report_files = [
        r for r in reports_dir.glob("*.json")
        if not r.name.startswith(("schema_", "ai_", "migration_", "schema_evolution"))
    ]

    for report_file in sorted(report_files):
        result = subprocess.run(
            ["python", str(ROOT / "contracts" / "attributor.py"),
             "--violation", str(report_file),
             "--lineage",   str(ROOT / "outputs" / "week4" / "lineage_snapshots.jsonl")],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            context.log.warning(f"Attributor issue on {report_file.name}: {result.stderr[:200]}")

    # ── Read violation log ─────────────────────────────────────────────────────
    violations_path = ROOT / "violation_log" / "violations.jsonl"
    violations      = _load_jsonl(violations_path)

    total_violations = len(violations)
    critical_count   = sum(1 for v in violations if v.get("severity") == "CRITICAL")

    # ── Build blame chain summary ─────────────────────────────────────────────
    blame_rows = []
    blast_rows = []
    for v in violations[:10]:  # show top 10
        check_id = v.get("check_id", "")
        chain    = v.get("blame_chain", [])
        if chain:
            top = chain[0]
            blame_rows.append(
                f"| `{check_id.split('.')[-1]}` | `{top.get('file_path','')}` "
                f"| {top.get('author_name', top.get('author',''))} "
                f"| `{top.get('commit_hash','')[:10]}` "
                f"| {top.get('commit_message','')[:40]} "
                f"| `{top.get('confidence_score', 0):.2f}` |"
            )

        br = v.get("blast_radius", {})
        registry = br.get("registry", {})
        subscribers = registry.get("subscribers", []) if isinstance(registry, dict) else []
        affected_nodes = br.get("affected_nodes", [])
        if subscribers or affected_nodes:
            blast_rows.append(
                f"| `{check_id.split('.')[-1]}` "
                f"| {', '.join(s.get('subscriber_id','') for s in subscribers)} "
                f"| {len(affected_nodes)} nodes "
                f"| {br.get('estimated_records', '?')} records |"
            )

    md  = "## Violation Attribution\n\n"
    md += f"**Total violations:** {total_violations}  \n"
    md += f"**Critical:** {critical_count}  \n\n"

    if blame_rows:
        md += "### Blame Chain (top entries)\n\n"
        md += "| Check | File | Author | Commit | Message | Confidence |\n"
        md += "|-------|------|--------|--------|---------|------------|\n"
        md += "\n".join(blame_rows)
        md += "\n\n**Confidence score formula:** `max(0.05, 1.0 - (days × 0.1) - (hop_count × 0.2))`\n"

    if blast_rows:
        md += "\n\n### Blast Radius\n\n"
        md += "| Check | Registry Subscribers | Lineage Nodes | Est. Records |\n"
        md += "|-------|---------------------|---------------|---------------|\n"
        md += "\n".join(blast_rows)

    # Registry subscriber detail
    for v in violations[:3]:
        br  = v.get("blast_radius", {})
        reg = br.get("registry", {})
        subs = reg.get("subscribers", []) if isinstance(reg, dict) else []
        if subs:
            md += f"\n\n#### Subscribers for `{v.get('check_id','').split('.')[-1]}`\n\n"
            for s in subs:
                md += f"- **{s['subscriber_id']}** (mode: `{s.get('validation_mode','')}`) — contact: {s.get('contact','')}\n"
                for bf in s.get("breaking_fields", [])[:2]:
                    md += f"  - `{bf['field']}`: {bf.get('reason','')[:80]}\n"

    context.add_output_metadata({
        "total_violations":    MetadataValue.int(total_violations),
        "critical_violations": MetadataValue.int(critical_count),
        "blame_blast_detail":  MetadataValue.md(md),
    })
    return {"total_violations": total_violations, "critical_violations": critical_count}


# ─────────────────────────────────────────
# ASSET 6 — Enforcer Report
# ─────────────────────────────────────────

@asset(
    deps=[schema_evolution_report, ai_metrics, violation_attribution],
    description="ReportGenerator: compile all validation data into health score, plain-language top violations, recommended actions, and stakeholder PDF.",
    group_name="enforcement_pipeline",
)
def enforcer_report(context: AssetExecutionContext):
    result = subprocess.run(
        ["python", str(ROOT / "contracts" / "report_generator.py"),
         "--output-dir", str(ROOT / "enforcer_report")],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        context.log.error(f"Report generator failed: {result.stderr}")
        return {"status": "failed"}

    report_json = ROOT / "enforcer_report" / "report_data.json"
    data = _load_json(report_json) if report_json.exists() else {}

    health_score  = data.get("health_score", 0.0)
    narrative     = data.get("health_narrative", "")
    top3          = data.get("top3_violations", [])
    actions       = data.get("recommended_actions", [])
    schema_chgs   = data.get("schema_changes", [])
    ai_risk       = data.get("ai_risk_summary", "")
    vcounts       = data.get("violation_counts", {})
    summary       = data.get("summary", {})

    # Health bar
    filled  = int(health_score / 5)
    bar     = "█" * filled + "░" * (20 - filled)
    health_color = "CRITICAL" if health_score < 50 else ("WARNING" if health_score < 75 else "HEALTHY")

    md  = "## Enforcer Report\n\n"
    md += f"### Platform Health: `{health_score}/100` [{health_color}]\n\n"
    md += f"`[{bar}]`\n\n"
    md += f"{narrative}\n\n"

    md += "### Violation Counts\n\n"
    md += "| Severity | Count |\n|----------|-------|\n"
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = vcounts.get(sev, 0)
        if count:
            md += f"| **{sev}** | {count} |\n"

    if top3:
        md += "\n### Top Violations (plain language)\n\n"
        for i, v in enumerate(top3, 1):
            md += f"{i}. {v}\n"

    if actions:
        md += "\n### Recommended Actions\n\n"
        for a in actions[:5]:
            md += f"- **[{a['risk']}]** {a['action']}\n"

    breaking_schema = [c for c in schema_chgs if c.get("verdict") == "BREAKING"]
    if breaking_schema:
        md += "\n### Breaking Schema Changes\n\n"
        for c in breaking_schema:
            md += f"- **{c['field']}** — {c['summary']} → _{c['action']}_\n"

    if ai_risk:
        md += f"\n### AI Risk Summary\n\n{ai_risk}\n"

    # PDF link
    pdf_files = sorted((ROOT / "enforcer_report").glob("*.pdf"))
    if pdf_files:
        md += f"\n### Report PDF\n\n`{pdf_files[-1].name}` — open from `enforcer_report/` directory\n"

    context.add_output_metadata({
        "health_score":       MetadataValue.float(float(health_score)),
        "health_status":      MetadataValue.text(health_color),
        "critical_count":     MetadataValue.int(vcounts.get("CRITICAL", 0)),
        "high_count":         MetadataValue.int(vcounts.get("HIGH", 0)),
        "total_violations":   MetadataValue.int(summary.get("total_violations", 0)),
        "breaking_schema":    MetadataValue.int(summary.get("breaking_changes", 0)),
        "enforcer_report":    MetadataValue.md(md),
    })
    return data

@asset(
    deps=[enforcer_report],
    description="Publish CRITICAL violations to Kafka violations topic → triggers Slack alerts.",
    group_name="enforcement_pipeline",
)
def kafka_publish(context: AssetExecutionContext):
    """
    Reads violation_log/violations.jsonl after the enforcer report is complete.
    Publishes every CRITICAL violation to the Kafka 'violations' topic.
    The Kafka consumer picks these up and posts to Slack automatically.
    """
    result = publish_violations()

    context.add_output_metadata({
        "violations_published": MetadataValue.int(result.get("published", 0)),
        "violations_failed":    MetadataValue.int(result.get("failed", 0)),
        "kafka_topic":          MetadataValue.text(result.get("topic", "violations")),
        "status":               MetadataValue.text(result.get("status", "unknown")),
    })

    if result.get("status") == "broker_unavailable":
        context.log.warning(
            "Kafka broker unavailable — violations not published. "
            "Is Docker running? Run: docker-compose up -d "
            "from streaming/kafka/"
        )
    elif result.get("published", 0) > 0:
        context.log.info(
            "%d CRITICAL violations published to Kafka topic 'violations'",
            result["published"],
        )
    else:
        context.log.info("No CRITICAL violations to publish.")

    return result