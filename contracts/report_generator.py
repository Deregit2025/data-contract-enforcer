import json
import uuid
import os
import glob
import argparse
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

VALIDATION_REPORTS_DIR = "validation_reports"
VIOLATION_LOG          = "violation_log/violations.jsonl"
AI_METRICS_PATH        = "validation_reports/ai_metrics.json"
ENFORCER_REPORT_DIR    = "enforcer_report"


# ─────────────────────────────────────────
# DATA COLLECTION
# ─────────────────────────────────────────

def load_validation_reports():
    """
    Load all validation report JSON files.
    Skip schema evolution and ai_metrics files.
    """
    latest: dict = {}   # contract_id → most recent report
    pattern = os.path.join(VALIDATION_REPORTS_DIR, "*.json")
    for path in glob.glob(pattern):
        fname = os.path.basename(path)
        if any(x in fname for x in ["schema_evolution", "ai_metrics", "migration_impact"]):
            continue
        try:
            with open(path) as f:
                report = json.load(f)
            if "total_checks" not in report:
                continue
            cid = report.get("contract_id", fname)
            ts  = report.get("run_timestamp", "")
            if cid not in latest or ts > latest[cid].get("run_timestamp", ""):
                latest[cid] = report
        except Exception:
            continue
    return list(latest.values())


def load_violations():
    if not os.path.exists(VIOLATION_LOG):
        return []
    violations = []
    with open(VIOLATION_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    violations.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return violations


def load_schema_changes():
    changes = []
    pattern = os.path.join(
        VALIDATION_REPORTS_DIR, "schema_evolution_*.json"
    )
    for path in glob.glob(pattern):
        try:
            with open(path) as f:
                report = json.load(f)
            for change in report.get("changes_detected", []):
                changes.append(change)
        except Exception:
            continue
    return changes


def load_ai_metrics():
    if not os.path.exists(AI_METRICS_PATH):
        return {}
    try:
        with open(AI_METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


# ─────────────────────────────────────────
# SECTION 1 — HEALTH SCORE
# ─────────────────────────────────────────

def compute_health_score(reports, violations):
    if not reports:
        return 0.0, "No validation reports found."

    total_checks = sum(r.get("total_checks", 0) for r in reports)
    total_passed = sum(r.get("passed", 0) for r in reports)

    if total_checks == 0:
        return 0.0, "No checks were run."

    # Severity deductions drawn from current report results (not historical log)
    DEDUCTIONS = {"CRITICAL": 20, "HIGH": 10, "MEDIUM": 5, "LOW": 1}
    current_fails = [
        result
        for rep in reports
        for result in rep.get("results", [])
        if result.get("status") in ("FAIL", "ERROR")
    ]
    critical_count = sum(1 for f in current_fails if f.get("severity") == "CRITICAL")

    raw_score = (total_passed / total_checks) * 100
    deduction = sum(DEDUCTIONS.get(f.get("severity", "LOW"), 1) for f in current_fails)
    score     = round(max(0.0, min(100.0, raw_score - deduction)), 1)

    if score >= 90:
        narrative = (
            f"Your data platform is {score}% healthy — "
            f"no critical issues detected."
        )
    elif score >= 70:
        narrative = (
            f"Your data platform is {score}% healthy — "
            f"{critical_count} critical violation(s) require attention."
        )
    elif score >= 50:
        narrative = (
            f"Your data platform is {score}% healthy — "
            f"data quality issues are affecting downstream systems."
        )
    else:
        narrative = (
            f"Your data platform is critically unhealthy at {score}% — "
            f"immediate action required."
        )

    return score, narrative


# ─────────────────────────────────────────
# SECTION 2 — VIOLATIONS SUMMARY
# ─────────────────────────────────────────

def summarise_violations(violations):
    counts = {
        "CRITICAL": 0, "HIGH": 0,
        "MEDIUM":   0, "LOW":  0, "WARNING": 0
    }
    for v in violations:
        sev = v.get("severity", "LOW")
        counts[sev] = counts.get(sev, 0) + 1

    severity_weight = {
        "CRITICAL": 5, "HIGH": 4,
        "MEDIUM":   3, "LOW":  2, "WARNING": 1
    }
    sorted_v = sorted(
        violations,
        key=lambda v: severity_weight.get(v.get("severity", "LOW"), 0),
        reverse=True
    )

    top3 = []
    for v in sorted_v[:3]:
        check_id = v.get("check_id", "")
        parts    = check_id.split(".")
        system   = parts[0] if parts else "unknown"
        field    = ".".join(parts[1:-1]) if len(parts) > 2 else "unknown"
        blast    = v.get("blast_radius", {})
        records  = blast.get("estimated_records", 0)
        affected = len(blast.get("affected_nodes", []))
        blame    = v.get("blame_chain", [{}])
        msg      = blame[0].get("commit_message", "unknown change") if blame else "unknown"

        top3.append(
            f"The {system} system's '{field}' field failed validation. "
            f"This affects {records} records and {affected} downstream "
            f"system(s). Most likely caused by: '{msg}'."
        )

    return counts, top3


# ─────────────────────────────────────────
# SECTION 3 — SCHEMA CHANGES
# ─────────────────────────────────────────

def summarise_schema_changes(changes):
    summaries = []
    for change in changes:
        field   = change.get("field", "unknown")
        ct      = change.get("change_type", "UNKNOWN")
        compat  = change.get("compatibility", "UNKNOWN")
        old_val = change.get("old_value", "unknown")
        new_val = change.get("new_value", "unknown")
        reason  = change.get("reason", "")

        if compat == "BREAKING":
            action = "ACTION REQUIRED — downstream teams must update before deploying."
        else:
            action = "No immediate action required."

        summaries.append({
            "field":   field,
            "summary": (
                f"Field '{field}' changed from {old_val} to {new_val} "
                f"({ct.replace('_', ' ').lower()})."
            ),
            "verdict": compat,
            "reason":  reason,
            "action":  action
        })
    return summaries


# ─────────────────────────────────────────
# SECTION 4 — AI RISK
# ─────────────────────────────────────────

def summarise_ai_risk(ai_metrics):
    if not ai_metrics:
        return "AI metrics not available — run ai_extensions.py first."

    drift   = ai_metrics.get("embedding_drift", {})
    llm     = ai_metrics.get("llm_output_schema", {})
    prompt  = ai_metrics.get("prompt_input_validation", {})

    drift_score    = drift.get("drift_score", 0)
    drift_status   = drift.get("status", "PASS")
    violation_rate = llm.get("violation_rate", 0)
    trend          = llm.get("trend", "stable")
    rejected       = prompt.get("rejected", 0)

    lines = []

    if drift_status == "FAIL":
        lines.append(
            f"ALERT: Text data meaning has drifted significantly "
            f"(drift score {drift_score}, threshold 0.15). "
            f"The AI system may be processing a different type of "
            f"content than it was designed for."
        )
    elif drift_status == "PASS":
        lines.append(
            f"Text data meaning is stable "
            f"(drift score {drift_score}). "
            f"AI embeddings are within acceptable bounds."
        )
    else:
        lines.append("Embedding drift check was not run.")

    if trend == "rising":
        lines.append(
            f"WARNING: LLM output schema violations are rising "
            f"(current rate {violation_rate:.1%}). "
            f"The AI model may have changed behavior — "
            f"review prompt templates."
        )
    else:
        lines.append(
            f"LLM output schema violation rate is "
            f"{violation_rate:.1%} and {trend}. "
            f"No action required."
        )

    if rejected > 0:
        lines.append(
            f"{rejected} prompt input record(s) failed validation "
            f"and were quarantined. "
            f"Check outputs/quarantine/ for details."
        )
    else:
        lines.append(
            "All prompt input records passed schema validation."
        )

    return " ".join(lines)


# ─────────────────────────────────────────
# SECTION 5 — RECOMMENDED ACTIONS
# ─────────────────────────────────────────

def generate_actions(health_score, violation_counts,
                     top3_violations, schema_changes,
                     ai_summary):
    actions = []

    # action 1 — most critical violation
    if top3_violations:
        actions.append({
            "priority": 1,
            "risk":     "CRITICAL" if violation_counts.get("CRITICAL", 0) > 0 else "HIGH",
            "action":   top3_violations[0]
        })

    # action 2 — breaking schema change
    breaking = [c for c in schema_changes if c.get("verdict") == "BREAKING"]
    if breaking:
        change = breaking[0]
        actions.append({
            "priority": 2,
            "risk":     "HIGH",
            "action": (
                f"Breaking schema change on field '{change['field']}'. "
                f"{change['action']} "
                f"Review migration checklist in validation_reports/."
            )
        })

    # action 3 — AI risk
    if "ALERT" in ai_summary or "WARNING" in ai_summary:
        actions.append({
            "priority": 3,
            "risk":     "MEDIUM",
            "action": (
                "AI system risk detected. "
                "Review ai_metrics.json and check recent data sources "
                "and prompt template changes."
            )
        })

    # pad to 3 actions
    while len(actions) < 3:
        actions.append({
            "priority": len(actions) + 1,
            "risk":     "LOW",
            "action": (
                "Run contracts/generator.py on all output directories "
                "to refresh contracts and update statistical baselines. "
                "Ensure all downstream consumers are notified of any "
                "schema changes detected this week."
            )
        })

    return actions[:3]


# ─────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────

def generate_pdf(report_data, output_path):
    doc    = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    story  = []

    # custom styles
    title_style = ParagraphStyle(
        "title",
        parent=styles["Heading1"],
        fontSize=22,
        spaceAfter=6,
        textColor=colors.HexColor("#2C2C2A")
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=16,
        textColor=colors.HexColor("#5F5E5A")
    )
    heading_style = ParagraphStyle(
        "heading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#2C2C2A")
    )
    body_style = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=6,
        leading=16
    )
    score_style = ParagraphStyle(
        "score",
        parent=styles["Normal"],
        fontSize=48,
        spaceAfter=4,
        textColor=colors.HexColor("#1D9E75")
    )
    score_label_style = ParagraphStyle(
        "score_label",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=8,
        textColor=colors.HexColor("#5F5E5A")
    )
    bullet_style = ParagraphStyle(
        "bullet",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=6,
        leading=16,
        leftIndent=20
    )
    action_style = ParagraphStyle(
        "action",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=10,
        leading=16,
        leftIndent=10,
        borderPad=8,
        borderColor=colors.HexColor("#D3D1C7"),
        borderWidth=0.5,
        borderRadius=4
    )

    # ── header ──
    story.append(Paragraph(
        "Data Contract Enforcer Report",
        title_style
    ))
    story.append(Paragraph(
        f"Auto-generated — {report_data['generated_at'][:10]}   |   "
        f"Platform: sentinel-contracts",
        subtitle_style
    ))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#D3D1C7"),
        spaceAfter=16
    ))

    # ── section 1 — health score ──
    story.append(Paragraph("1. Data Health Score", heading_style))
    story.append(Paragraph(
        f"{report_data['health_score']} / 100",
        score_style
    ))
    story.append(Paragraph(
        report_data["health_narrative"],
        score_label_style
    ))

    # stats table
    reports    = load_validation_reports()
    total_chk  = sum(r.get("total_checks", 0) for r in reports)
    total_pass = sum(r.get("passed", 0) for r in reports)
    total_fail = sum(r.get("failed", 0) for r in reports)
    total_warn = sum(r.get("warned", 0) for r in reports)

    table_data = [
        ["Total checks", "Passed", "Failed", "Warned"],
        [
            str(total_chk),
            str(total_pass),
            str(total_fail),
            str(total_warn)
        ]
    ]
    table = Table(table_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.HexColor("#2C2C2A")),
        ("FONTSIZE",    (0, 0), (-1, -1), 11),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D1C7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F1EFE8")]),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*cm))

    # ── section 2 — violations ──
    story.append(Paragraph("2. Violations This Week", heading_style))
    counts   = report_data["violation_counts"]
    top3     = report_data["top3_violations"]
    count_parts = []
    for sev, count in counts.items():
        if count > 0:
            count_parts.append(f"{sev}: {count}")
    story.append(Paragraph(
        "  |  ".join(count_parts) if count_parts else "No violations detected.",
        body_style
    ))
    if top3:
        for v in top3:
            story.append(Paragraph(f"• {v}", bullet_style))
    else:
        story.append(Paragraph(
            "No violations detected this week.", body_style
        ))
    story.append(Spacer(1, 0.2*cm))

    # ── section 3 — schema changes ──
    story.append(Paragraph("3. Schema Changes Detected", heading_style))
    schema_changes = report_data["schema_changes"]
    if schema_changes:
        for change in schema_changes:
            verdict = change.get("verdict", "UNKNOWN")
            color   = (
                "#A32D2D" if verdict == "BREAKING"
                else "#0F6E56"
            )
            story.append(Paragraph(
                f"<font color='{color}'><b>[{verdict}]</b></font> "
                f"{change['summary']} {change['action']}",
                body_style
            ))
    else:
        story.append(Paragraph(
            "No schema changes detected this week.", body_style
        ))
    story.append(Spacer(1, 0.2*cm))

    # ── section 4 — AI risk ──
    story.append(Paragraph("4. AI System Risk Assessment", heading_style))
    story.append(Paragraph(report_data["ai_risk_summary"], body_style))

    # AI metrics table
    ai = report_data.get("ai_metrics_raw", {})
    drift_score    = ai.get("embedding_drift", {}).get("drift_score", "N/A")
    violation_rate = ai.get("llm_output_schema", {}).get("violation_rate", "N/A")
    trend          = ai.get("llm_output_schema", {}).get("trend", "N/A")
    rejected       = ai.get("prompt_input_validation", {}).get("rejected", 0)

    ai_table_data = [
        ["Metric", "Value", "Status"],
        ["Embedding drift score",
         str(drift_score),
         "PASS" if float(drift_score or 0) <= 0.15 else "FAIL"],
        ["LLM output violation rate",
         f"{float(violation_rate or 0):.1%}",
         "PASS" if trend != "rising" else "WARN"],
        ["Prompt inputs quarantined",
         str(rejected),
         "PASS" if rejected == 0 else "WARN"],
    ]
    ai_table = Table(
        ai_table_data,
        colWidths=[8*cm, 4*cm, 4*cm]
    )
    ai_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
        ("FONTSIZE",    (0, 0), (-1, -1), 11),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D1C7")),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(Spacer(1, 0.3*cm))
    story.append(ai_table)
    story.append(Spacer(1, 0.3*cm))

    # ── section 5 — recommended actions ──
    story.append(Paragraph("5. Recommended Actions", heading_style))
    for action in report_data["recommended_actions"]:
        risk  = action["risk"]
        color = (
            "#A32D2D" if risk == "CRITICAL"
            else "#854F0B" if risk == "HIGH"
            else "#185FA5" if risk == "MEDIUM"
            else "#3B6D11"
        )
        story.append(Paragraph(
            f"<font color='{color}'><b>#{action['priority']} [{risk}]</b></font> "
            f"{action['action']}",
            action_style
        ))

    # ── footer ──
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#D3D1C7"),
        spaceAfter=8
    ))
    story.append(Paragraph(
        f"Auto-generated by sentinel-contracts/contracts/report_generator.py — "
        f"not hand-written. "
        f"Report ID: {report_data['report_id']}",
        ParagraphStyle(
            "footer",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#888780")
        )
    ))

    doc.build(story)
    print(f"  PDF written: {output_path}")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ReportGenerator — auto-generate enforcer report"
    )
    parser.add_argument(
        "--output-dir",
        default=ENFORCER_REPORT_DIR,
        help="output directory for report files"
    )
    args = parser.parse_args()

    print("\nGenerating Enforcer Report...")
    print("=" * 50)

    # collect all data
    reports        = load_validation_reports()
    violations     = load_violations()
    schema_changes_raw = load_schema_changes()
    ai_metrics     = load_ai_metrics()

    print(f"  Validation reports: {len(reports)}")
    print(f"  Violations:         {len(violations)}")
    print(f"  Schema changes:     {len(schema_changes_raw)}")

    # compute each section
    health_score, health_narrative = compute_health_score(
        reports, violations
    )
    violation_counts, top3 = summarise_violations(violations)
    schema_changes         = summarise_schema_changes(schema_changes_raw)
    ai_risk                = summarise_ai_risk(ai_metrics)
    actions                = generate_actions(
        health_score, violation_counts,
        top3, schema_changes, ai_risk
    )

    print(f"\n  Health score:       {health_score} / 100")
    print(f"  Critical violations: {violation_counts.get('CRITICAL', 0)}")
    print(f"  Breaking changes:    {sum(1 for c in schema_changes if c.get('verdict') == 'BREAKING')}")

    # assemble report_data.json
    today       = datetime.now(timezone.utc).date().isoformat()
    report_data = {
        "report_id":          str(uuid.uuid4()),
        "generated_at":       datetime.now(timezone.utc).isoformat(),
        "data_health_score":  health_score,
        "health_score":       health_score,
        "health_narrative":   health_narrative,
        "violation_counts":   violation_counts,
        "top3_violations":    top3,
        "schema_changes":     schema_changes,
        "ai_risk_summary":    ai_risk,
        "ai_metrics_raw":     ai_metrics,
        "recommended_actions": actions,
        "summary": {
            "total_reports":         len(reports),
            "total_violations":      len(violations),
            "total_schema_changes":  len(schema_changes_raw),
            "breaking_changes":      sum(
                1 for c in schema_changes
                if c.get("verdict") == "BREAKING"
            )
        }
    }

    # write report_data.json
    os.makedirs(args.output_dir, exist_ok=True)
    data_path = os.path.join(args.output_dir, "report_data.json")
    with open(data_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n  report_data.json written: {data_path}")

    # generate PDF
    pdf_path = os.path.join(
        args.output_dir, f"report_{today}.pdf"
    )
    generate_pdf(report_data, pdf_path)

    print(f"\n{'=' * 50}")
    print(f"Enforcer Report complete.")
    print(f"  Health score: {health_score} / 100")
    print(f"  report_data.json: {data_path}")
    print(f"  PDF: {pdf_path}")
    print(f"\nDone.")


if __name__ == "__main__":
    main()