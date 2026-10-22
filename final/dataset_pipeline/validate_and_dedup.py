"""
validate_and_dedup.py — Document Validation & Deduplication Engine.

Validates the raw document records against schema.json.
Performs SHA256 deduplication and text similarity checks.
Emits a formal audit report (validation_report.json) and clean dataset (clean_documents.jsonl).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
RAW_DOCS_FILE = PIPELINE_DIR / "data" / "raw" / "documents.jsonl"
PROCESSED_DIR = PIPELINE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_DOCS_FILE = PROCESSED_DIR / "clean_documents.jsonl"
SCHEMA_FILE = PIPELINE_DIR / "schema.json"
REPORT_FILE = PIPELINE_DIR / "validation_report.json"


def validate_document(doc: dict, schema: dict) -> tuple[bool, list[str]]:
    """Validates document structure against required schema rules."""
    errors = []
    
    # 1. Required Top-Level Keys
    for req in schema.get("required", []):
        if req not in doc:
            errors.append(f"Missing required field '{req}'")

    # 2. Document Type
    valid_types = schema["properties"]["document_type"]["enum"]
    if doc.get("document_type") not in valid_types:
        errors.append(f"Invalid document_type '{doc.get('document_type')}'; must be one of {valid_types}")

    # 3. Provenance
    prov = doc.get("provenance", {})
    if not isinstance(prov, dict):
        errors.append("Field 'provenance' must be a dictionary")
    else:
        for p_req in ["source", "license", "sha256"]:
            if not prov.get(p_req):
                errors.append(f"Provenance missing '{p_req}'")

    # 4. Clinical Entities
    entities = doc.get("clinical_entities", {})
    if not isinstance(entities, dict):
        errors.append("Field 'clinical_entities' must be a dictionary")
    else:
        for e_req in ["medicines", "tests", "diagnoses"]:
            if e_req not in entities or not isinstance(entities[e_req], list):
                errors.append(f"clinical_entities missing array '{e_req}'")

    # 5. Length of OCR text
    text = doc.get("ocr_text", "")
    if not isinstance(text, str) or len(text.strip()) < 10:
        errors.append("ocr_text too short or invalid")

    return (len(errors) == 0, errors)


def run_validation_and_dedup() -> dict[str, Any]:
    logger.info("Starting validation and deduplication on %s...", RAW_DOCS_FILE)

    if not RAW_DOCS_FILE.exists():
        raise FileNotFoundError(f"Raw documents file not found: {RAW_DOCS_FILE}. Run fetch_dataset.py first.")

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema = json.load(f)

    seen_hashes: Set[str] = set()
    seen_texts: Set[str] = set()

    total_records = 0
    valid_records = 0
    duplicate_records = 0
    invalid_records = 0
    error_summary: Dict[str, int] = {}
    clean_documents: List[dict] = []

    with open(RAW_DOCS_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            total_records += 1

            try:
                doc = json.loads(line)
            except Exception as e:
                invalid_records += 1
                error_summary["JSON_PARSE_ERROR"] = error_summary.get("JSON_PARSE_ERROR", 0) + 1
                continue

            # Schema validation
            is_valid, errors = validate_document(doc, schema)
            if not is_valid:
                invalid_records += 1
                for err in errors:
                    err_type = err.split()[0]
                    error_summary[err_type] = error_summary.get(err_type, 0) + 1
                continue

            # SHA256 & Content Deduplication
            doc_hash = doc.get("provenance", {}).get("sha256")
            text_norm = " ".join(doc.get("ocr_text", "").lower().split())

            if doc_hash in seen_hashes or text_norm in seen_texts:
                duplicate_records += 1
                continue

            seen_hashes.add(doc_hash)
            seen_texts.add(text_norm)
            valid_records += 1
            clean_documents.append(doc)

    # Save clean dataset
    with open(CLEAN_DOCS_FILE, "w", encoding="utf-8") as f:
        for doc in clean_documents:
            f.write(json.dumps(doc) + "\n")

    report = {
        "dataset_name": "Healthcare Co-Pilot Unified Medical Benchmark",
        "total_input_records": total_records,
        "valid_deduplicated_records": valid_records,
        "duplicate_records_removed": duplicate_records,
        "schema_invalid_records": invalid_records,
        "pass_rate_percentage": round((valid_records / total_records) * 100, 2) if total_records else 0,
        "class_breakdown": {
            "PRESCRIPTION": sum(1 for d in clean_documents if d["document_type"] == "PRESCRIPTION"),
            "LAB_REPORT": sum(1 for d in clean_documents if d["document_type"] == "LAB_REPORT"),
            "OTHER": sum(1 for d in clean_documents if d["document_type"] not in ("PRESCRIPTION", "LAB_REPORT")),
        },
        "output_file": str(CLEAN_DOCS_FILE),
        "validation_errors": error_summary,
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Validation complete! Valid records: %d / %d (%.2f%%)", valid_records, total_records, report["pass_rate_percentage"])
    logger.info("Saved clean documents to %s", CLEAN_DOCS_FILE)
    logger.info("Validation report written to %s", REPORT_FILE)
    return report


if __name__ == "__main__":
    run_validation_and_dedup()
