import json
import os
import shutil

DATA_PATH   = "outputs/week3/extractions.jsonl"
BACKUP_PATH = "outputs/week3/extractions_clean.jsonl"

# these texts are deliberately from a completely different
# domain than your financial/legal documents
# this forces the embedding centroid to drift significantly
DRIFT_TEXTS = [
    "The quantum entanglement of photon pairs demonstrates non-local correlation effects.",
    "Neural network backpropagation updates weights using gradient descent optimization.",
    "The mitochondria produces ATP through oxidative phosphorylation in the inner membrane.",
    "Kubernetes orchestrates containerized workloads across distributed cluster nodes.",
    "The Fourier transform decomposes signals into frequency domain representations.",
    "CRISPR-Cas9 enables precise genomic editing through guide RNA targeting mechanisms.",
    "Blockchain consensus mechanisms ensure distributed ledger integrity without central authority.",
    "Photosynthesis converts carbon dioxide and water into glucose using solar energy.",
    "The TCP/IP protocol stack manages reliable data transmission across network layers.",
    "Eigenvalue decomposition reveals the principal components of high-dimensional data.",
    "The Riemann hypothesis concerns the distribution of prime numbers in complex analysis.",
    "Machine learning models overfit when training loss diverges from validation loss.",
    "The second law of thermodynamics states entropy in isolated systems always increases.",
    "RNA polymerase transcribes DNA sequences into messenger RNA during gene expression.",
    "Convolutional neural networks extract spatial features through shared weight filters.",
    "The Navier-Stokes equations describe fluid dynamics in viscous flow conditions.",
    "Docker containers isolate application dependencies in lightweight virtual environments.",
    "The central limit theorem states sample means converge to normal distribution.",
    "Synaptic plasticity underlies long-term potentiation in hippocampal memory formation.",
    "GraphQL queries allow clients to request exactly the data structure they need.",
]

def inject():
    if not os.path.exists(DATA_PATH):
        print(f"ERROR: {DATA_PATH} not found")
        return

    # backup if not already done
    if not os.path.exists(BACKUP_PATH):
        shutil.copy(DATA_PATH, BACKUP_PATH)
        print(f"Clean backup saved to {BACKUP_PATH}")
    else:
        print(f"Backup already exists at {BACKUP_PATH}")

    records = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Loaded {len(records)} records")

    # replace fact texts with drift texts
    import random
    replaced = 0
    for record in records:
        for fact in record.get("extracted_facts", []):
            if isinstance(fact, dict) and "text" in fact:
                fact["text"]           = random.choice(DRIFT_TEXTS)
                fact["source_excerpt"] = fact["text"][:80]
                replaced              += 1

    with open(DATA_PATH, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Replaced {replaced} fact texts with out-of-domain content")
    print(f"Run ai_extensions.py to detect the drift")
    print(f"Run restore_violation.py to undo")

if __name__ == "__main__":
    inject()