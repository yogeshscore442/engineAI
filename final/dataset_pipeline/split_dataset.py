"""
split_dataset.py — Stratified Dataset Splitter (70% Train, 15% Val, 15% Test).

Performs deterministic, class-balanced, stratified splitting of clean medical documents.
Ensures zero data leakage between splits.
Outputs train.jsonl, val.jsonl, test.jsonl, and split_manifest.json.
"""
from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
CLEAN_DOCS_FILE = PIPELINE_DIR / "data" / "processed" / "clean_documents.jsonl"
SPLITS_DIR = PIPELINE_DIR / "data" / "splits"
SPLITS_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_FILE = SPLITS_DIR / "train.jsonl"
VAL_FILE = SPLITS_DIR / "val.jsonl"
TEST_FILE = SPLITS_DIR / "test.jsonl"
MANIFEST_FILE = SPLITS_DIR / "split_manifest.json"

SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


def stratified_split(documents: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Splits documents preserving stratum balance (document_type x is_synthetic)."""
    random.seed(SEED)
    
    # Group by stratum
    strata: dict[tuple[str, bool], list[dict]] = defaultdict(list)
    for doc in documents:
        key = (doc.get("document_type", "OTHER"), bool(doc.get("is_synthetic")))
        strata[key].append(doc)

    train_set, val_set, test_set = [], [], []

    for key, group in strata.items():
        random.shuffle(group)
        n = len(group)
        n_train = int(n * TRAIN_RATIO)
        n_val = int(n * VAL_RATIO)
        
        # Ensure at least 1 item in train/test if group has >= 2 items
        if n >= 2 and n_train == 0:
            n_train = 1
        
        train_set.extend(group[:n_train])
        val_set.extend(group[n_train:n_train + n_val])
        test_set.extend(group[n_train + n_val:])

    # Final shuffle
    random.shuffle(train_set)
    random.shuffle(val_set)
    random.shuffle(test_set)

    return train_set, val_set, test_set


def save_jsonl(path: Path, docs: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")


def summarize_split(docs: list[dict]) -> dict[str, Any]:
    rx_count = sum(1 for d in docs if d["document_type"] == "PRESCRIPTION")
    lab_count = sum(1 for d in docs if d["document_type"] == "LAB_REPORT")
    synth_count = sum(1 for d in docs if d.get("is_synthetic"))
    real_count = len(docs) - synth_count
    return {
        "count": len(docs),
        "prescriptions": rx_count,
        "lab_reports": lab_count,
        "real": real_count,
        "synthetic": synth_count,
    }


def main():
    logger.info("Reading clean documents from %s...", CLEAN_DOCS_FILE)
    if not CLEAN_DOCS_FILE.exists():
        raise FileNotFoundError(f"Clean documents not found at {CLEAN_DOCS_FILE}. Run validate_and_dedup.py first.")

    documents = []
    with open(CLEAN_DOCS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))

    logger.info("Loaded %d documents. Performing stratified 70/15/15 split...", len(documents))
    train_docs, val_docs, test_docs = stratified_split(documents)

    save_jsonl(TRAIN_FILE, train_docs)
    save_jsonl(VAL_FILE, val_docs)
    save_jsonl(TEST_FILE, test_docs)

    manifest = {
        "random_seed": SEED,
        "ratios": {"train": TRAIN_RATIO, "val": VAL_RATIO, "test": TEST_RATIO},
        "total_documents": len(documents),
        "splits": {
            "train": summarize_split(train_docs),
            "val": summarize_split(val_docs),
            "test": summarize_split(test_docs),
        },
        "files": {
            "train": str(TRAIN_FILE),
            "val": str(VAL_FILE),
            "test": str(TEST_FILE),
        },
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Split complete!")
    logger.info("Train: %d documents (Prescriptions: %d, Labs: %d)", len(train_docs), manifest["splits"]["train"]["prescriptions"], manifest["splits"]["train"]["lab_reports"])
    logger.info("Val:   %d documents (Prescriptions: %d, Labs: %d)", len(val_docs), manifest["splits"]["val"]["prescriptions"], manifest["splits"]["val"]["lab_reports"])
    logger.info("Test:  %d documents (Prescriptions: %d, Labs: %d)", len(test_docs), manifest["splits"]["test"]["prescriptions"], manifest["splits"]["test"]["lab_reports"])
    logger.info("Manifest saved to %s", MANIFEST_FILE)


if __name__ == "__main__":
    main()
