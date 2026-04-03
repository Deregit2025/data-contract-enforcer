"""
migrate_traces.py — Transform extractor_ai real execution data into LangSmith trace format.

Source:  ../extractor_ai/.refinery/extractions.jsonl   (real LLM calls with token counts)
         ../extractor_ai/.refinery/extraction_ledger.jsonl (real pipeline runs)
Output:  outputs/traces/runs.jsonl

The extractor_ai project calls OpenRouter directly (no LangSmith SDK).
These records are derived from actual API calls — token counts, timestamps,
and model names are real. The format is mapped to the LangSmith trace_record schema.

LangSmith trace_record schema:
  id, name, run_type, inputs, outputs, error, start_time, end_time,
  total_tokens, prompt_tokens, completion_tokens, total_cost,
  tags, parent_run_id, session_id
"""

import json
import uuid
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).parent
REPO_ROOT    = SCRIPT_DIR.parent
EXTRACTOR_AI = REPO_ROOT.parent / "extractor_ai"

EXTRACTIONS_SRC = EXTRACTOR_AI / ".refinery" / "extractions.jsonl"
LEDGER_SRC      = EXTRACTOR_AI / ".refinery" / "extraction_ledger.jsonl"
OUTPUT_PATH     = REPO_ROOT / "outputs" / "traces" / "runs.jsonl"

# ---------------------------------------------------------------------------
# OpenRouter pricing (USD per token) — used to compute total_cost
# ---------------------------------------------------------------------------
PRICING = {
    "openai/gpt-4o-2024-08-06": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "openai/gpt-4o-mini":       {"input": 0.15 / 1_000_000, "output":  0.60 / 1_000_000},
    "anthropic/claude-3-5-sonnet": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
}
DEFAULT_PRICING = {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000}


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICING.get(model, DEFAULT_PRICING)
    return round(p["input"] * prompt_tokens + p["output"] * completion_tokens, 6)


def parse_ts(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp, adding UTC if missing."""
    ts_str = ts_str.rstrip("Z")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Step 1: Load real ledger data — keyed by (doc_id, timestamp-minute)
# for joining to extractions
# ---------------------------------------------------------------------------
def load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        print(f"[WARN] Ledger not found: {path}")
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def strategy_to_run_type(strategy: str) -> str:
    """Map extractor_ai strategy names to LangSmith run_type enum."""
    s = strategy.lower()
    if "vision" in s:
        return "llm"
    if "fasttext" in s:
        return "chain"
    if "layout" in s:
        return "tool"
    return "llm"


# ---------------------------------------------------------------------------
# Step 2: Transform extraction records → LangSmith llm-type trace records
# ---------------------------------------------------------------------------
def transform_extraction(rec: dict, session_map: dict, ledger_map: dict) -> dict:
    """
    One extraction record = one LLM call trace.
    Token counts, timestamps, and model are real values from actual API calls.
    """
    doc_id   = rec["doc_id"]
    model    = rec.get("extraction_model", "openai/gpt-4o-2024-08-06")
    tc       = rec.get("token_count", {})
    prompt_t = tc.get("input", 0)
    compl_t  = tc.get("output", 0)
    total_t  = prompt_t + compl_t
    cost     = compute_cost(model, prompt_t, compl_t)
    proc_ms  = rec.get("processing_time_ms", 2000)

    start_dt = parse_ts(rec["extracted_at"])
    end_dt   = start_dt + timedelta(milliseconds=proc_ms)

    # session_id: stable UUID per doc_id (so all runs for same doc share session)
    if doc_id not in session_map:
        session_map[doc_id] = str(uuid.uuid4())
    session_id = session_map[doc_id]

    # parent_run_id: the chain-level run for this doc (set later when we build chains)
    parent_run_id = ledger_map.get(doc_id)

    # Inputs: what the LLM received (source info — not the raw prompt bytes)
    inputs = {
        "doc_id":      doc_id,
        "source_path": rec.get("source_path", ""),
        "source_hash": rec.get("source_hash", ""),
    }

    # Outputs: what the LLM returned
    facts = rec.get("extracted_facts", [])
    outputs = {
        "facts_extracted":  len(facts),
        "confidence_mean":  round(
            sum(f.get("confidence", 0) for f in facts) / len(facts), 4
        ) if facts else 0.0,
        "entities_extracted": len(rec.get("entities", [])),
    }

    return {
        "id":                str(uuid.uuid4()),
        "name":              f"{doc_id}::extraction",
        "run_type":          "llm",
        "inputs":            inputs,
        "outputs":           outputs,
        "error":             None,
        "start_time":        fmt_ts(start_dt),
        "end_time":          fmt_ts(end_dt),
        "total_tokens":      total_t,
        "prompt_tokens":     prompt_t,
        "completion_tokens": compl_t,
        "total_cost":        cost,
        "tags":              ["week3", "extraction"],
        "parent_run_id":     parent_run_id,
        "session_id":        session_id,
    }


# ---------------------------------------------------------------------------
# Step 3: Transform ledger records → LangSmith chain-type trace records
# (pipeline-level parent runs)
# ---------------------------------------------------------------------------
def transform_ledger_entry(rec: dict, session_map: dict) -> tuple[str, dict]:
    """
    One ledger entry = one pipeline chain run (parent of the LLM extraction call).
    Returns (run_id, trace_record).
    """
    doc_id   = rec["doc_id"]
    strategy = rec.get("strategy_used", "unknown")
    run_type = strategy_to_run_type(strategy)

    start_dt = parse_ts(rec["timestamp"])
    # Ledger has no end_time — estimate from facts_extracted count
    approx_ms = rec.get("facts_extracted", 5) * 3000 + 10000
    end_dt    = start_dt + timedelta(milliseconds=approx_ms)

    if doc_id not in session_map:
        session_map[doc_id] = str(uuid.uuid4())
    session_id = session_map[doc_id]

    run_id = str(uuid.uuid4())

    trace = {
        "id":                run_id,
        "name":              f"{doc_id}::pipeline",
        "run_type":          run_type,
        "inputs":            {
            "doc_id":          doc_id,
            "strategy":        strategy,
            "origin_type":     rec.get("origin_type", "unknown"),
            "layout_complexity": rec.get("layout_complexity", "unknown"),
        },
        "outputs":           {
            "status":          rec.get("status", "SUCCESS"),
            "chunks":          rec.get("chunks", 0),
            "facts_extracted": rec.get("facts_extracted", 0),
        },
        "error":             None if rec.get("status") == "SUCCESS" else rec.get("status"),
        "start_time":        fmt_ts(start_dt),
        "end_time":          fmt_ts(end_dt),
        "total_tokens":      0,   # chain-level: token roll-up not available
        "prompt_tokens":     0,
        "completion_tokens": 0,
        "total_cost":        0.0,
        "tags":              ["week3", "pipeline"],
        "parent_run_id":     None,
        "session_id":        session_id,
    }
    return run_id, trace


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def migrate():
    print(f"Source extractions : {EXTRACTIONS_SRC}")
    print(f"Source ledger      : {LEDGER_SRC}")
    print(f"Output             : {OUTPUT_PATH}")

    if not EXTRACTIONS_SRC.exists():
        print(f"[ERROR] extractions.jsonl not found at {EXTRACTIONS_SRC}")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    session_map: dict[str, str] = {}   # doc_id → session_id UUID
    ledger_map:  dict[str, str] = {}   # doc_id → latest chain run_id

    all_traces = []

    # --- Pass 1: Build chain-level parent runs from ledger ---
    ledger_records = load_ledger(LEDGER_SRC)
    for rec in ledger_records:
        run_id, trace = transform_ledger_entry(rec, session_map)
        # Keep the latest chain run per doc_id (for parent_run_id linking)
        ledger_map[rec["doc_id"]] = run_id
        all_traces.append(trace)

    print(f"  Ledger entries    : {len(ledger_records)} chain traces")

    # --- Pass 2: Transform LLM-level extraction records ---
    extraction_records = []
    with open(EXTRACTIONS_SRC, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                extraction_records.append(json.loads(line))

    llm_traces = []
    for rec in extraction_records:
        trace = transform_extraction(rec, session_map, ledger_map)
        llm_traces.append(trace)

    all_traces.extend(llm_traces)
    print(f"  Extraction traces : {len(llm_traces)} llm traces")

    # --- Write output ---
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for trace in all_traces:
            f.write(json.dumps(trace) + "\n")

    print(f"\n  Total traces written : {len(all_traces)}")
    print(f"  Output path          : {OUTPUT_PATH}")

    # --- Summary ---
    total_tokens = sum(t["total_tokens"] for t in all_traces)
    total_cost   = sum(t["total_cost"]   for t in all_traces)
    print(f"  Total tokens         : {total_tokens:,}")
    print(f"  Total cost (USD)     : ${total_cost:.4f}")
    unique_docs  = len(session_map)
    print(f"  Unique documents     : {unique_docs}")
    print("\nDone.")


if __name__ == "__main__":
    migrate()
