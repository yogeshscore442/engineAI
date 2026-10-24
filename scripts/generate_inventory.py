"""
generate_inventory.py — Generate comprehensive dataset inventory.
Inventories all 6,585 files in the dataset folder, detects file types, verifies decodability,
computes SHA-256 hashes to identify duplicates, records page counts, and produces:
- reports/dataset_inventory.csv
- reports/dataset_inventory_summary.json
"""
import os
import sys
import json
import hashlib
import mimetypes
import zipfile
from pathlib import Path
import pandas as pd
from PIL import Image

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def test_decodable(filepath: Path, ext: str) -> tuple[bool, int, str]:
    """Test if file can be decoded; return (can_decode, page_count, error_str)."""
    try:
        ext_lower = ext.lower()
        if ext_lower in (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"):
            with Image.open(filepath) as img:
                img.verify()
            # Reopen to get page count if multi-frame
            with Image.open(filepath) as img:
                pages = getattr(img, "n_frames", 1)
                return True, pages, ""
        elif ext_lower == ".pdf":
            import fitz
            doc = fitz.open(filepath)
            pages = len(doc)
            doc.close()
            return True, pages, ""
        elif ext_lower in (".txt", ".csv"):
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                f.read(1024)
            return True, 1, ""
        elif ext_lower == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True)
            wb.close()
            return True, 1, ""
        elif ext_lower == ".zip":
            is_valid = zipfile.is_zipfile(filepath)
            if is_valid:
                with zipfile.ZipFile(filepath, "r") as zf:
                    test = zf.testzip()
                    if test is not None:
                        return False, 0, f"Corrupted zip entry: {test}"
                return True, 1, ""
            return False, 0, "Not a valid zip archive"
        else:
            with open(filepath, "rb") as f:
                f.read(512)
            return True, 1, ""
    except Exception as e:
        return False, 0, str(e)

def run_inventory():
    workspace_root = Path(__file__).resolve().parent.parent
    ds_root = workspace_root / "dataset"
    reports_dir = workspace_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting inventory on: {ds_root}")
    all_files = sorted(list(ds_root.rglob("*")))
    files = [f for f in all_files if f.is_file()]
    print(f"Found {len(files)} files to audit.")

    records = []
    sha_map = {}

    for idx, f in enumerate(files):
        rel_path = f.relative_to(workspace_root).as_posix()
        rel_to_ds = f.relative_to(ds_root).as_posix()
        top_subfolder = rel_to_ds.split("/")[0]

        ext = f.suffix.lower()
        size_bytes = f.stat().st_size
        sha = compute_sha256(f)

        if sha in sha_map:
            dup_status = f"duplicate_of:{sha_map[sha]}"
        else:
            dup_status = "unique"
            sha_map[sha] = rel_path

        can_decode, page_count, err_str = test_decodable(f, ext)

        # Content role & intended use
        content_role = "unknown"
        intended_use = "unknown"
        proc_status = "unprocessed"

        if ext in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
            content_role = "image"
            if top_subfolder == "RxHand Original":
                intended_use = "training_and_evaluation"
                proc_status = "eligible_for_ocr_processing"
            elif top_subfolder == "Prescription_Dataset(600)-t4I2Mj":
                intended_use = "ocr_evaluation_and_testing"
                proc_status = "eligible_for_ocr_processing"
            elif top_subfolder == "Dataset":
                intended_use = "ocr_evaluation_and_testing"
                proc_status = "eligible_for_ocr_processing"
        elif ext == ".pdf":
            content_role = "documentation"
            intended_use = "documentation_and_metadata"
            proc_status = "eligible_for_ocr_processing"
        elif ext == ".txt":
            content_role = "annotation"
            intended_use = "bounding_box_annotation"
            proc_status = "annotation_metadata"
        elif ext in (".csv", ".xlsx"):
            content_role = "ground_truth" if "label" in f.name.lower() or "dataset" in f.name.lower() else "metadata"
            intended_use = "ground_truth_transcription" if "label" in f.name.lower() or "dataset" in f.name.lower() else "box_count_metadata"
            proc_status = "annotation_metadata"
        elif ext == ".zip":
            content_role = "archive"
            intended_use = "archive_source"
            proc_status = "archive_extracted"

        mime_type = mimetypes.guess_type(f.name)[0] or f"application/octet-stream ({ext})"

        records.append({
            "relative_file_path": rel_path,
            "dataset_subfolder": top_subfolder,
            "file_name": f.name,
            "file_extension": ext,
            "detected_file_type": mime_type,
            "file_size_bytes": size_bytes,
            "can_decode": can_decode,
            "page_count": page_count if page_count > 0 else 1,
            "content_role": content_role,
            "duplicate_status": dup_status,
            "sha256": sha,
            "corruption_error": err_str or "none",
            "intended_use": intended_use,
            "processing_status": proc_status,
        })

        if (idx + 1) % 1000 == 0 or (idx + 1) == len(files):
            print(f"Audited {idx+1}/{len(files)} files...")

    df = pd.DataFrame(records)
    inv_csv = reports_dir / "dataset_inventory.csv"
    df.to_csv(inv_csv, index=False, encoding="utf-8")
    print(f"Wrote inventory CSV to: {inv_csv}")

    # Build summary JSON
    subfolders = sorted(list(set(r["dataset_subfolder"] for r in records)))
    summary = {
        "total_discovered_files": len(records),
        "supported_image_files": sum(1 for r in records if r["content_role"] == "image"),
        "supported_pdf_files": sum(1 for r in records if r["content_role"] == "documentation" and r["file_extension"] == ".pdf"),
        "annotation_and_metadata_files": sum(1 for r in records if r["content_role"] in ("annotation", "ground_truth", "metadata")),
        "archive_files": sum(1 for r in records if r["content_role"] == "archive"),
        "files_successfully_decoded": sum(1 for r in records if r["can_decode"]),
        "unreadable_or_corrupted_files": sum(1 for r in records if not r["can_decode"]),
        "duplicate_files_count": sum(1 for r in records if r["duplicate_status"] != "unique"),
        "eligible_for_training": sum(1 for r in records if r["intended_use"] == "training_and_evaluation"),
        "by_subfolder": {}
    }

    for sf in subfolders:
        sf_records = [r for r in records if r["dataset_subfolder"] == sf]
        summary["by_subfolder"][sf] = {
            "total_files": len(sf_records),
            "image_files": sum(1 for r in sf_records if r["content_role"] == "image"),
            "pdf_files": sum(1 for r in sf_records if r["file_extension"] == ".pdf"),
            "annotation_and_metadata_files": sum(1 for r in sf_records if r["content_role"] in ("annotation", "ground_truth", "metadata")),
            "archive_files": sum(1 for r in sf_records if r["content_role"] == "archive"),
            "decoded_ok": sum(1 for r in sf_records if r["can_decode"]),
            "corrupted": sum(1 for r in sf_records if not r["can_decode"]),
            "duplicates": sum(1 for r in sf_records if r["duplicate_status"] != "unique"),
            "ground_truth_samples": sum(1 for r in sf_records if r["content_role"] == "ground_truth"),
        }

    inv_json = reports_dir / "dataset_inventory_summary.json"
    with open(inv_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote inventory summary JSON to: {inv_json}")

    # Build dataset_issues.csv
    issues = []
    for r in records:
        issue_type = None
        issue_desc = None
        if not r["can_decode"]:
            issue_type = "CORRUPT_OR_UNREADABLE"
            issue_desc = r["corruption_error"]
        elif r["duplicate_status"] != "unique":
            issue_type = "DUPLICATE_FILE"
            issue_desc = r["duplicate_status"]
        elif r["content_role"] == "archive":
            issue_type = "ARCHIVE_FILE"
            issue_desc = "Zip archive present alongside uncompressed images"
        elif r["content_role"] == "image" and r["intended_use"] != "training_and_evaluation" and r["dataset_subfolder"] == "Dataset":
            issue_type = "NO_FULL_TEXT_GROUND_TRUTH"
            issue_desc = "Image has box-level coordinates but lacks word/transcription text labels"

        if issue_type:
            issues.append({
                "relative_file_path": r["relative_file_path"],
                "dataset_subfolder": r["dataset_subfolder"],
                "file_name": r["file_name"],
                "issue_type": issue_type,
                "issue_description": issue_desc,
                "can_decode": r["can_decode"],
                "remedy_or_action": "Use for bounding box count evaluation only" if issue_type == "NO_FULL_TEXT_GROUND_TRUTH" else ("Decompressed source exists" if issue_type == "ARCHIVE_FILE" else "Exclude from training")
            })

    issues_df = pd.DataFrame(issues)
    issues_csv = reports_dir / "dataset_issues.csv"
    issues_df.to_csv(issues_csv, index=False, encoding="utf-8")
    print(f"Wrote dataset issues CSV to: {issues_csv} ({len(issues)} issues logged)")

    print("\nSummary Summary:")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    run_inventory()

