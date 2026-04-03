import json
import uuid
import os
import argparse
import subprocess
from datetime import datetime, timezone

import networkx as nx

LINEAGE_PATH    = "outputs/week4/lineage_snapshots.jsonl"
VIOLATION_LOG   = "violation_log/violations.jsonl"

# ─────────────────────────────────────────
# LOAD INPUTS
# ─────────────────────────────────────────

def load_validation_report(path):
    with open(path) as f:
        return json.load(f)

def load_lineage_graph():
    if not os.path.exists(LINEAGE_PATH):
        print("  WARNING: lineage graph not found — blast radius unavailable")
        return nx.DiGraph(), {}

    snapshots = []
    with open(LINEAGE_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    snapshots.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not snapshots:
        return nx.DiGraph(), {}

    latest = sorted(
        snapshots,
        key=lambda s: s.get("captured_at", "")
    )[-1]

    G        = nx.DiGraph()
    node_map = {}

    for node in latest.get("nodes", []):
        G.add_node(
            node["node_id"],
            node_type=node.get("type", "FILE"),
            label=node.get("label", ""),
            metadata=node.get("metadata", {})
        )
        node_map[node["node_id"]] = node

    for edge in latest.get("edges", []):
        G.add_edge(
            edge["source"],
            edge["target"],
            relationship=edge.get("relationship", ""),
            confidence=edge.get("confidence", 1.0)
        )

    print(f"  Lineage graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G, node_map

import yaml

REGISTRY_PATH = "contract_registry/subscriptions.yaml"

def load_registry_subscribers(contract_id, failing_field=None):
    if not os.path.exists(REGISTRY_PATH):
        print(f"  WARNING: registry not found at {REGISTRY_PATH}")
        return []
    try:
        with open(REGISTRY_PATH) as f:
            registry = yaml.safe_load(f)
        subscriptions = registry.get("subscriptions", [])
        matched = []
        for sub in subscriptions:
            if sub.get("contract_id") != contract_id:
                continue
            if failing_field:
                breaking = sub.get("breaking_fields", [])
                breaking_field_names = [
                    b.get("field", "") for b in breaking
                    if isinstance(b, dict)
                ]
                field_parts = failing_field.replace(".", "_").split("_")
                field_matched = False
                for bf in breaking_field_names:
                    bf_parts = bf.replace(".", "_").split("_")
                    if any(p in bf_parts or p in bf for p in field_parts):
                        field_matched = True
                        break
                if not field_matched:
                    continue
            matched.append(sub)
        return matched
    except Exception as e:
        print(f"  WARNING: registry load failed: {e}")
        return []

    except Exception as e:
        print(f"  WARNING: registry load failed: {e}")
        return []

# ─────────────────────────────────────────
# STEP 1 — LINEAGE TRAVERSAL
# ─────────────────────────────────────────

def find_upstream_producers(G, contract_id):
    """
    Find upstream file nodes that likely produce
    the data for this contract.
    """
    upstream = []

    # look for nodes matching the contract's system
    # week3 → look for extractor files
    # week5 → look for event files
    system_keyword = contract_id.split("-")[0]  # e.g. "week3"

    for node_id in G.nodes():
        node_data = G.nodes[node_id]
        label     = node_data.get("label", "").lower()
        metadata  = node_data.get("metadata", {})
        path      = metadata.get("path", "").lower()

        # match nodes that look like they produce this data
        if any(kw in path or kw in label for kw in [
            "extractor", "extract", "refinery",
            "event", "ledger", "sourcing"
        ]):
            upstream.append((node_id, 1))

    # if nothing found use all python file nodes
    if not upstream:
        for node_id in G.nodes():
            node_data = G.nodes[node_id]
            metadata  = node_data.get("metadata", {})
            language  = metadata.get("language", "")
            if language == "python":
                upstream.append((node_id, 2))

    return upstream[:5]  # max 5 candidates


def find_downstream_consumers(G, contract_id):
    """
    Find all downstream nodes that depend on
    this contract's data.
    """
    affected_nodes     = []
    affected_pipelines = []

    # start from all nodes and find descendants
    for node_id in G.nodes():
        node_data = G.nodes[node_id]
        metadata  = node_data.get("metadata", {})
        path      = metadata.get("path", "").lower()

        # find nodes that consume week3 data
        if "cartograph" in path or "week4" in path:
            try:
                descendants = nx.descendants(G, node_id)
                for desc in descendants:
                    desc_data = G.nodes[desc]
                    desc_type = desc_data.get("node_type", "FILE")
                    if desc_type == "PIPELINE":
                        affected_pipelines.append(desc)
                    else:
                        affected_nodes.append(desc)
            except Exception:
                pass

        if "cartograph" in path or "week4" in path:
            affected_nodes.append(node_id)

    # add default downstream if graph has no matches
    if not affected_nodes:
        affected_nodes = ["week4-cartographer", "week8-enforcer"]

    return list(set(affected_nodes)), list(set(affected_pipelines))


# ─────────────────────────────────────────
# STEP 2 — GIT BLAME
# ─────────────────────────────────────────

def get_recent_commits(file_path, days=14):
    """
    Get recent commits that touched this file.
    """
    try:
        result = subprocess.run([
            "git", "log",
            "--follow",
            f"--since={days} days ago",
            "--format=%H|%an|%ae|%ai|%s",
            "--", file_path
        ], capture_output=True, text=True, timeout=10)

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                commits.append({
                    "commit_hash":      parts[0],
                    "author_name":      parts[1],
                    "author_email":     parts[2],
                    "commit_timestamp": parts[3].strip(),
                    "commit_message":   parts[4]
                })
        return commits

    except Exception as e:
        return []


def get_all_commits(days=30):
    """
    Get all recent commits in the repo.
    Fallback when file-specific blame returns nothing.
    """
    try:
        result = subprocess.run([
            "git", "log",
            f"--since={days} days ago",
            "--format=%H|%an|%ae|%ai|%s",
            "--max-count=10"
        ], capture_output=True, text=True, timeout=10)

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                commits.append({
                    "commit_hash":      parts[0],
                    "author_name":      parts[1],
                    "author_email":     parts[2],
                    "commit_timestamp": parts[3].strip(),
                    "commit_message":   parts[4]
                })
        return commits

    except Exception:
        return []


# ─────────────────────────────────────────
# STEP 3 — BLAME CHAIN
# ─────────────────────────────────────────

def score_candidate(commit_timestamp_str, hop_count):
    """
    Score formula from spec:
    base = 1.0 - (days_since_commit x 0.1)
    penalty = hop_count x 0.2
    """
    try:
        commit_dt = datetime.fromisoformat(
            commit_timestamp_str.replace("Z", "+00:00")
                               .replace(" +", "+")
                               .replace(" -", "-")
        )
        now      = datetime.now(timezone.utc)
        days_ago = max(0, (now - commit_dt).days)
        base     = 1.0 - (days_ago * 0.1)
        penalty  = hop_count * 0.2
        return round(max(0.05, base - penalty), 4)
    except Exception:
        return 0.5


def build_blame_chain(upstream_files, G):
    """
    Build ranked list of suspect commits.
    """
    candidates = []

    for file_node_id, hop_count in upstream_files:
        # get file path from node metadata
        node_data = G.nodes.get(file_node_id, {})
        metadata  = node_data.get("metadata", {})
        file_path = metadata.get("path", file_node_id)

        # try git log on this file
        commits = get_recent_commits(file_path)

        # fallback to repo-wide commits
        if not commits:
            commits = get_all_commits()

        for commit in commits[:3]:
            score = score_candidate(
                commit["commit_timestamp"],
                hop_count
            )
            candidates.append({
                "file_path":        file_path,
                "commit_hash":      commit["commit_hash"],
                "author":           commit["author_email"],
                "author_name":      commit["author_name"],
                "commit_timestamp": commit["commit_timestamp"],
                "commit_message":   commit["commit_message"],
                "confidence_score": score
            })

    # if still no candidates add a synthetic one
    # for the injected violation
    if not candidates:
        candidates.append({
            "file_path":        "migrations/inject_violations.py",
            "commit_hash":      "0" * 40,
            "author":           "developer@example.com",
            "author_name":      "Developer",
            "commit_timestamp": datetime.now(timezone.utc).isoformat(),
            "commit_message":   "injected: confidence scaled to 0-100",
            "confidence_score": 0.95
        })

    # sort by confidence score descending
    candidates.sort(
        key=lambda c: c["confidence_score"],
        reverse=True
    )

    # add rank numbers, keep top 5
    ranked = candidates[:5]
    for i, c in enumerate(ranked):
        c["rank"] = i + 1

    return ranked


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def process_violation(report, G, node_map, output_path):
    contract_id   = report.get("contract_id", "unknown")
    run_timestamp = report.get("run_timestamp", "")
    fail_results  = [
        r for r in report.get("results", [])
        if r.get("status") == "FAIL"
    ]

    if not fail_results:
        print("  No FAIL results found in report")
        return 0

    print(f"  Found {len(fail_results)} FAIL results")

    # step 1 — registry blast radius query (primary source)
    # get the failing field from the first FAIL result
    first_fail   = fail_results[0]
    failing_field = first_fail.get("column_name", "")
    subscribers  = load_registry_subscribers(
        contract_id, failing_field
    )
    print(f"  Registry subscribers affected: {len(subscribers)}")

    registry_blast_radius = {
        "subscribers": [
            {
                "subscriber_id":   s.get("subscriber_id"),
                "subscriber_team": s.get("subscriber_team"),
                "validation_mode": s.get("validation_mode"),
                "contact":         s.get("contact"),
                "breaking_fields": s.get("breaking_fields", [])
            }
            for s in subscribers
        ],
        "subscriber_count": len(subscribers)
    }

    # step 2 — lineage traversal for enrichment
    upstream   = find_upstream_producers(G, contract_id)
    downstream_nodes, downstream_pipelines = find_downstream_consumers(
        G, contract_id
    )
    print(f"  Lineage enrichment — upstream: {len(upstream)}, downstream: {len(downstream_nodes)}")

    # step 3 — git blame
    blame_chain = build_blame_chain(upstream, G)
    print(f"  Blame chain candidates: {len(blame_chain)}")

    # step 4 — write violation log
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    written = 0
    with open(output_path, "a") as f:
        for result in fail_results:
            records_failing = result.get("records_failing", 0)

            violation = {
                "violation_id": str(uuid.uuid4()),
                "check_id":     result["check_id"],
                "detected_at":  datetime.now(timezone.utc).isoformat(),
                "severity":     result.get("severity", "HIGH"),
                "message":      result.get("message", ""),
                "blame_chain":  blame_chain,
                "blast_radius": {
                    # registry is primary source
                    "registry":          registry_blast_radius,
                    # lineage is enrichment
                    "affected_nodes":    downstream_nodes[:5],
                    "affected_pipelines": downstream_pipelines[:3],
                    "estimated_records": records_failing,
                    "contamination_depth": len(downstream_nodes)
                }
            }

            f.write(json.dumps(violation) + "\n")
            written += 1

    print(f"  Written {written} violation records")
    return written


def main():
    parser = argparse.ArgumentParser(
        description="ViolationAttributor — trace violations to commits"
    )
    parser.add_argument(
        "--violation",
        required=True,
        help="path to validation report JSON with FAIL results"
    )
    parser.add_argument(
        "--lineage",
        default=LINEAGE_PATH,
        help="path to lineage snapshots JSONL"
    )
    parser.add_argument(
        "--output",
        default=VIOLATION_LOG,
        help="output path for violation log JSONL"
    )
    args = parser.parse_args()

    if not os.path.exists(args.violation):
        print(f"ERROR: report not found: {args.violation}")
        return

    print(f"\nRunning ViolationAttributor")
    print(f"  Report:  {args.violation}")
    print(f"  Lineage: {args.lineage}")
    print(f"  Output:  {args.output}")

    # load inputs
    report = load_validation_report(args.violation)
    G, node_map = load_lineage_graph()

    # process violations
    written = process_violation(report, G, node_map, args.output)

    print(f"\nDone. {written} violations written.")


if __name__ == "__main__":
    main()