"""
test_prescription.py — Test uploading and extracting a prescription document
against the live running backend (http://127.0.0.1:8000).

Usage:
    python test_prescription.py <path_to_prescription_file> [language: en|ta]
Example:
    python test_prescription.py my_rx.jpg ta
"""
import sys
import os
import mimetypes
import json
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8001/api")

def upload_and_view(file_path: str, lang: str = "en"):
    path = os.path.abspath(file_path)
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        return

    filename = os.path.basename(path)
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "application/pdf"

    print(f"\n=======================================================")
    print(f"  AI Health Copilot - Prescription Extraction Test")
    print(f"=======================================================")
    print(f"Target Server : {API_BASE}")
    print(f"File Name     : {filename}")
    print(f"MIME Type     : {mime_type}")
    print(f"Language Hint : {lang}")
    print(f"File Size     : {os.path.getsize(path)} bytes")
    print("Uploading to backend & processing with AI engine...\n")

    # Read bytes
    with open(path, "rb") as f:
        file_bytes = f.read()

    # Build multipart/form-data
    boundary = "----WebKitFormBoundaryHealthCopilot12345"
    body = bytearray()

    # Part: lang
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="lang"\r\n\r\n')
    body.extend(f"{lang}\r\n".encode())

    # Part: file
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())

    url = f"{API_BASE}/profiles/default/records"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status_code = resp.getcode()
            raw_data = resp.read().decode("utf-8")
            data = json.loads(raw_data)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[FAILED] HTTP {e.code}: {err_msg}")
        return
    except Exception as e:
        print(f"[FAILED] Connection error: {e}")
        print("Make sure backend is running on http://127.0.0.1:8000")
        return

    record = data.get("record", {})
    record_json = record.get("record_json", {}) or record
    record_id = data.get("record_id")

    print(f"[SUCCESS] Record Created! Status: {status_code} ({data.get('status')})")
    print(f"Record ID    : {record_id}")
    print(f"Document Type: {record.get('doc_type')}")
    print(f"Document Date: {record.get('doc_date') or 'Not specified'}")
    print(f"Source       : {record.get('source')} (AI Mode)")

    # Print Medicines
    medicines = record_json.get("medicines") or record.get("medicines") or []
    print(f"\n--- EXTRACTED MEDICINES ({len(medicines)}) ---")
    if medicines:
        for idx, m in enumerate(medicines, 1):
            name = m.get("name_raw") or "Unknown"
            generic = m.get("generic") or "-"
            strength = m.get("strength") or "-"
            sched = m.get("schedule_raw") or str(m.get("schedule_parsed") or "-")
            food = m.get("food_instruction") or "-"
            dur = f"{m.get('duration_days')} days" if m.get("duration_days") else "-"
            conf = f"{int(m.get('confidence', 0) * 100)}%" if m.get("confidence") is not None else "-"
            print(f"  {idx}. {name}")
            print(f"     Generic: {generic} | Strength: {strength} | Dosage: {sched}")
            print(f"     Food: {food} | Duration: {dur} | Confidence: {conf}")
    else:
        print("  No medicines detected.")

    # Print Diagnoses
    diagnoses = record_json.get("diagnoses") or []
    if diagnoses:
        print(f"\n--- DIAGNOSES ({len(diagnoses)}) ---")
        for d in diagnoses:
            print(f"  - {d.get('text')} (Confidence: {int(d.get('confidence', 0)*100)}%)")

    # Print Summaries
    print("\n--- SUMMARY ---")
    summary_en = record_json.get("summary_en")
    summary_ta = record_json.get("summary_ta")
    if summary_en:
        print(f"English: {summary_en}")
    if summary_ta:
        print(f"\nTamil  : {summary_ta}")

    # Review Needed
    needs_review = record_json.get("needs_review") or []
    if needs_review:
        print(f"\nNeeds Review Fields: {needs_review}")

    print("\n--- MEDICAL DISCLAIMER ---")
    print(record_json.get("disclaimer") or record.get("disclaimer"))
    print("\n=======================================================\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_arg = sys.argv[1]
        lang_arg = sys.argv[2] if len(sys.argv) > 2 else "en"
        upload_and_view(file_arg, lang_arg)
    else:
        # Check for default sample
        sample_path = "yogesh/healthcare_copilot_AI-Engine-main/samples/prescription1.jpg"
        print(f"No file path provided. Testing with default sample: {sample_path}")
        print("To test your own file: python test_prescription.py <your_file.jpg> [en|ta]\n")
        upload_and_view(sample_path, "en")
