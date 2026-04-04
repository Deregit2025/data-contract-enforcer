import json
import uuid
import os
import argparse
import yaml
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOTS_DIR    = "schema_snapshots"
REPORTS_DIR      = "validation_reports"
LINEAGE_PATH     = "outputs/week4/lineage_snapshots.jsonl"

# ─────────────────────────────────────────
# LOAD SNAPSHOTS
# ─────────────────────────────────────────

def load_snapshots(contract_id, since_days=None):
    snapshot_dir = os.path.join(SNAPSHOTS_DIR, contract_id)

    if not os.path.exists(snapshot_dir):
        print(f"  ERROR: no snapshots found for {contract_id}")
        return []

    files = sorted(os.listdir(snapshot_dir))
    files = [f for f in files if f.endswith(".yaml")]

    if not files:
        print(f"  ERROR: no snapshot files in {snapshot_dir}")
        return []

    snapshots = []
    for fname in files:
        path = os.path.join(snapshot_dir, fname)
        with open(path) as f:
            snapshot = yaml.safe_load(f)
            snapshot["_filename"] = fname
            snapshots.append(snapshot)

    print(f"  Found {len(snapshots)} snapshots")
    return snapshots


# ─────────────────────────────────────────
# STEP 1 — DETECT CHANGES
# ─────────────────────────────────────────

def detect_changes(old_schema, new_schema):
    changes = []

    old_fields = old_schema.get("fields", {}) or {}
    new_fields = new_schema.get("fields", {}) or {}

    # handle case where fields might be nested differently
    if not old_fields and "schema" in old_schema:
        old_fields = old_schema.get("schema", {}) or {}
    if not new_fields and "schema" in new_schema:
        new_fields = new_schema.get("schema", {}) or {}

    all_field_names = set(list(old_fields.keys()) + list(new_fields.keys()))

    for field_name in all_field_names:
        old_field = old_fields.get(field_name)
        new_field = new_fields.get(field_name)

        # field removed
        if old_field and not new_field:
            changes.append({
                "field":       field_name,
                "change_type": "FIELD_REMOVED",
                "old_value":   str(old_field),
                "new_value":   None
            })

        # field added
        elif not old_field and new_field:
            changes.append({
                "field":       field_name,
                "change_type": "FIELD_ADDED",
                "old_value":   None,
                "new_value":   str(new_field)
            })

        # field exists in both — check what changed
        elif old_field and new_field:
            if not isinstance(old_field, dict):
                old_field = {}
            if not isinstance(new_field, dict):
                new_field = {}

            # type changed
            if old_field.get("type") != new_field.get("type"):
                changes.append({
                    "field":       field_name,
                    "change_type": "TYPE_CHANGED",
                    "old_value":   old_field.get("type"),
                    "new_value":   new_field.get("type")
                })

            # range changed
            old_min = old_field.get("minimum")
            old_max = old_field.get("maximum")
            new_min = new_field.get("minimum")
            new_max = new_field.get("maximum")

            if old_min != new_min or old_max != new_max:
                changes.append({
                    "field":       field_name,
                    "change_type": "RANGE_CHANGED",
                    "old_value":   f"{old_min}–{old_max}",
                    "new_value":   f"{new_min}–{new_max}"
                })

            # enum changed
            if old_field.get("enum") != new_field.get("enum"):
                changes.append({
                    "field":       field_name,
                    "change_type": "ENUM_CHANGED",
                    "old_value":   old_field.get("enum"),
                    "new_value":   new_field.get("enum")
                })

    return changes


# ─────────────────────────────────────────
# STEP 2 — CLASSIFY CHANGES
# ─────────────────────────────────────────

def classify_change(change):
    ct = change["change_type"]

    if ct == "FIELD_ADDED":
        old_val = change.get("new_value", "") or ""
        if "required: True" in str(old_val) or "required: true" in str(old_val):
            return "BREAKING", "New required field — all producers must update"
        return "SAFE", "New optional field — consumers can ignore it"

    elif ct == "FIELD_REMOVED":
        return "BREAKING", "Field removed — consumers reading it will break"

    elif ct == "TYPE_CHANGED":
        old_t = str(change.get("old_value", ""))
        new_t = str(change.get("new_value", ""))
        widening_pairs = [
            ("integer", "number"),
            ("int",     "float"),
            ("float32", "float64")
        ]
        for old_w, new_w in widening_pairs:
            if old_w in old_t and new_w in new_t:
                return "SAFE", f"Type widened {old_t} → {new_t} — no precision loss"
        return "BREAKING", f"Type changed {old_t} → {new_t} — consumers will misread values"

    elif ct == "RANGE_CHANGED":
        old_val = str(change.get("old_value", ""))
        new_val = str(change.get("new_value", ""))

        # detect semantic narrowing: proportional scale change (e.g. 0–1 → 0–100)
        # consumers reading values in the old range will silently misinterpret all data
        try:
            old_parts = [
                float(x) for x in old_val.split("\u2013")
                if x.strip() not in ("", "None")
            ]
            new_parts = [
                float(x) for x in new_val.split("\u2013")
                if x.strip() not in ("", "None")
            ]
            if len(old_parts) == 2 and len(new_parts) == 2:
                old_span = old_parts[1] - old_parts[0]
                new_span = new_parts[1] - new_parts[0]
                if old_span > 0 and (new_span / old_span) >= 50:
                    return "CRITICAL", (
                        f"Semantic narrowing detected: scale changed {old_val} → {new_val}. "
                        f"Consumers expecting the {old_val} range will silently misread every "
                        f"value — all downstream thresholds and statistical baselines are invalid."
                    )
        except (ValueError, ZeroDivisionError):
            pass

        # confidence field is always a scale concern even without span ratio
        if "confidence" in change["field"].lower():
            return "CRITICAL", (
                f"Confidence range changed {old_val} → {new_val}. "
                f"This is the canonical scale violation — "
                f"downstream baselines are now invalid."
            )
        return "BREAKING", f"Range changed {old_val} → {new_val} — statistical baselines invalid"

    elif ct == "ENUM_CHANGED":
        old_vals = set(change.get("old_value") or [])
        new_vals  = set(change.get("new_value") or [])
        removed   = old_vals - new_vals
        if removed:
            return "BREAKING", f"Enum values removed: {removed}"
        return "SAFE", f"Enum values added only — additive change"

    return "UNKNOWN", "Could not classify change"


# ─────────────────────────────────────────
# STEP 3 — BLAST RADIUS
# ─────────────────────────────────────────

def get_blast_radius(contract_id):
    """
    Load lineage graph and find downstream consumers.
    """
    if not os.path.exists(LINEAGE_PATH):
        return ["week4-cartographer", "week8-enforcer"]

    try:
        import networkx as nx
        snapshots = []
        with open(LINEAGE_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    snapshots.append(json.loads(line))

        if not snapshots:
            return []

        latest = sorted(
            snapshots,
            key=lambda s: s.get("captured_at", "")
        )[-1]

        G = nx.DiGraph()
        for node in latest.get("nodes", []):
            G.add_node(node["node_id"])
        for edge in latest.get("edges", []):
            G.add_edge(edge["source"], edge["target"])

        affected = []
        for node_id in G.nodes():
            if "knowledge_graph" in node_id or "archivist" in node_id:
                for desc in nx.descendants(G, node_id):
                    affected.append(desc)
                affected.append(node_id)

        return list(set(affected))[:5] if affected else [
            "file::src/agents/archivist.py",
            "file::src/graph/knowledge_graph.py"
        ]

    except Exception:
        return ["week4-cartographer", "week8-enforcer"]


# ─────────────────────────────────────────
# STEP 4 — MIGRATION IMPACT REPORT
# ─────────────────────────────────────────

def generate_migration_report(
    contract_id,
    changes_with_class,
    blast_radius,
    old_snapshot_name,
    new_snapshot_name
):
    breaking = [c for c in changes_with_class if c["compatibility"] in ("BREAKING", "CRITICAL")]
    safe     = [c for c in changes_with_class if c["compatibility"] == "SAFE"]
    critical = [c for c in breaking if c["compatibility"] == "CRITICAL"]
    critical_fields = {c["field"] for c in critical}

    # ── per-consumer failure mode analysis ──
    # load registry to get subscriber details
    consumer_analysis = []
    try:
        if os.path.exists("contract_registry/subscriptions.yaml"):
            with open("contract_registry/subscriptions.yaml") as f:
                registry = yaml.safe_load(f)
            subscriptions = registry.get("subscriptions", [])

            for sub in subscriptions:
                if sub.get("contract_id") != contract_id:
                    continue

                subscriber_id   = sub.get("subscriber_id", "unknown")
                validation_mode = sub.get("validation_mode", "AUDIT")
                breaking_fields = sub.get("breaking_fields", [])
                fields_consumed = sub.get("fields_consumed", [])

                # find which breaking changes affect this consumer
                affected_changes = []
                for change in breaking:
                    field = change["field"]
                    # check if this consumer cares about this field
                    consumer_breaking = [
                        b for b in breaking_fields
                        if isinstance(b, dict) and (
                            b.get("field", "") in field or
                            field in b.get("field", "")
                        )
                    ]
                    if consumer_breaking or any(
                        fc in field or field in fc
                        for fc in fields_consumed
                    ):
                        affected_changes.append({
                            "field":          field,
                            "change_type":    change["change_type"],
                            "failure_mode":   (
                                consumer_breaking[0].get("reason", "")
                                if consumer_breaking
                                else f"Consumer reads {field} which changed"
                            ),
                            "severity": (
                                "CRITICAL"
                                if validation_mode == "ENFORCE"
                                else "HIGH"
                                if validation_mode == "WARN"
                                else "MEDIUM"
                            )
                        })

                if affected_changes:
                    # consumer is HIGH_RISK if any of its affected fields
                    # experienced a CRITICAL (semantic narrowing) change
                    hits_critical = any(
                        ac["field"] in critical_fields
                        for ac in affected_changes
                    )
                    risk_level = "HIGH_RISK" if hits_critical else "AT_RISK"
                    consumer_analysis.append({
                        "subscriber_id":   subscriber_id,
                        "validation_mode": validation_mode,
                        "contact":         sub.get("contact", ""),
                        "risk_level":      risk_level,
                        "affected_changes": affected_changes,
                        "recommended_action": (
                            f"{'⚠ HIGH_RISK — ' if hits_critical else ''}"
                            f"Notify {subscriber_id} immediately. "
                            f"Validation mode is {validation_mode} — "
                            + (
                                "pipeline will be BLOCKED on next run."
                                if validation_mode == "ENFORCE"
                                else "violations will be logged but pipeline will continue."
                                if validation_mode == "AUDIT"
                                else "CRITICAL violations will block pipeline."
                            )
                        )
                    })
    except Exception as e:
        print(f"  WARNING: consumer analysis failed: {e}")

    # ── migration checklist ──
    checklist = []
    step = 1
    for change in breaking:
        field   = change["field"]
        old_val = change["old_value"]
        new_val = change["new_value"]
        checklist.append(
            f"{step}. Notify all registry subscribers of breaking "
            f"change in '{field}' — see consumer_analysis section"
        )
        step += 1
        checklist.append(
            f"{step}. Revert '{field}' from {new_val} back to "
            f"{old_val} in producer"
        )
        step += 1
        checklist.append(
            f"{step}. Re-run ValidationRunner with --mode AUDIT "
            f"on all consumer datasets to confirm fix"
        )
        step += 1
        checklist.append(
            f"{step}. Re-establish statistical baseline for "
            f"'{field}' by deleting entry from "
            f"schema_snapshots/baselines.json and re-running generator"
        )
        step += 1

    if not checklist:
        checklist = ["No breaking changes — no migration required"]

    rollback = (
        f"Revert producer to state before snapshot {new_snapshot_name}. "
        f"Re-run ContractGenerator to re-establish baselines. "
        f"Re-run ValidationRunner on all consumer datasets. "
        f"Notify registry subscribers that rollback is complete."
    ) if breaking else "No rollback required — all changes are safe."

    high_risk_consumers = [
        c for c in consumer_analysis if c.get("risk_level") == "HIGH_RISK"
    ]

    return {
        "report_id":    str(uuid.uuid4()),
        "contract_id":  contract_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "compared_snapshots": {
            "old": old_snapshot_name,
            "new": new_snapshot_name
        },
        "summary": {
            "total_changes":      len(changes_with_class),
            "critical_changes":   len(critical),
            "breaking_changes":   len(breaking),
            "safe_changes":       len(safe),
            "consumers_affected": len(consumer_analysis),
            "high_risk_consumers": len(high_risk_consumers)
        },
        "critical_changes":     critical,
        "changes_detected":     changes_with_class,
        "high_risk_consumers":  high_risk_consumers,
        "consumer_analysis":    consumer_analysis,
        "blast_radius":         blast_radius,
        "migration_checklist":  checklist,
        "rollback_plan":        rollback
    }


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SchemaEvolutionAnalyzer — detect and classify schema changes"
    )
    parser.add_argument(
        "--contract-id",
        required=True,
        help="contract ID to analyze e.g. week3-document-refinery-extractions"
    )
    parser.add_argument(
        "--since",
        default="7 days ago",
        help="time window e.g. '7 days ago'"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="output path for evolution report JSON"
    )
    args = parser.parse_args()

    contract_id = args.contract_id
    print(f"\nRunning SchemaEvolutionAnalyzer")
    print(f"  Contract: {contract_id}")

    # load snapshots
    snapshots = load_snapshots(contract_id)
    if len(snapshots) < 2:
        print(f"  ERROR: need at least 2 snapshots, found {len(snapshots)}")
        print(f"  Run generator.py twice — once on clean data, once on modified data")
        return

    # compare the two most recent snapshots
    old_snapshot  = snapshots[-2]
    new_snapshot  = snapshots[-1]
    old_name      = old_snapshot["_filename"]
    new_name      = new_snapshot["_filename"]

    print(f"  Old snapshot: {old_name}")
    print(f"  New snapshot: {new_name}")

    # detect changes
    changes = detect_changes(old_snapshot, new_snapshot)
    print(f"  Changes detected: {len(changes)}")

    if not changes:
        print("  No schema changes detected between snapshots")

    # classify each change
    changes_with_class = []
    for change in changes:
        compat, reason = classify_change(change)
        change["compatibility"] = compat
        change["reason"]        = reason
        changes_with_class.append(change)
        status_icon = "BREAKING" if compat == "BREAKING" else "safe"
        print(f"    [{status_icon}] {change['field']}: {change['change_type']} — {reason[:60]}")

    breaking_count = sum(
        1 for c in changes_with_class
        if c["compatibility"] in ("BREAKING", "CRITICAL")
    )
    critical_count = sum(
        1 for c in changes_with_class
        if c["compatibility"] == "CRITICAL"
    )
    print(f"  Critical changes: {critical_count}")
    print(f"  Breaking changes: {breaking_count}")
    print(f"  Safe changes:     {len(changes) - breaking_count}")

    # get blast radius
    blast_radius = get_blast_radius(contract_id)

    # generate migration impact report
    report = generate_migration_report(
        contract_id,
        changes_with_class,
        blast_radius,
        old_name,
        new_name
    )

    # write output
    os.makedirs(REPORTS_DIR, exist_ok=True)
    if args.output:
        output_path = args.output
    else:
        timestamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        output_path = os.path.join(
            REPORTS_DIR,
        f"migration_impact_{contract_id}_{timestamp}.json"
    )

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Migration impact report: {output_path}")
    if critical_count > 0:
        print(f"  CRITICAL: {critical_count} semantic narrowing(s) — high-risk consumers: {len(report['high_risk_consumers'])}")
    if breaking_count > 0:
        print(f"  ACTION REQUIRED: {breaking_count} breaking change(s) detected")
        print(f"  Migration checklist has {len(report['migration_checklist'])} steps")
    else:
        print(f"  All changes are safe — no migration required")

    print(f"\nDone.")


if __name__ == "__main__":
    main()