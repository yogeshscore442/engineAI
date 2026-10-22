# AI Health Copilot Engine — API & Data Contract Specification
**Component:** Yogesh (Core AI Engine Interface)  
**Consumer Modules:** Praveen (Backend Service / Fastify & Flask API), Naveen (Frontend Web Client)  
**Contract Version:** 2.1.0  
**Schema Standard:** JSON Schema Draft 7 / Pydantic v2  

---

## 1. Engine Public Entry Point

```python
from ai_engine import extract_record

result: dict = extract_record(
    file_path="samples/lab1.jpg",
    mime="image/jpeg",
    lang_hint="auto"  # "auto" | "en" | "ta"
)
```

### 1.1 Invariant Execution Guarantee
`extract_record()` **NEVER raises an uncaught exception**.
All execution branches (success, invalid input, rejection, timeout, or unexpected error) return a strictly validated JSON-serializable dictionary adhering to this contract.

---

## 2. Response Status Lifecycle

Every response dictionary includes an explicit processing outcome in `status` and `accepted`:

```
                    +───────────────────────────+
                    |  Document Ingestion Flow  |
                    +─────────────┬─────────────+
                                  │
                                  ▼
                    +───────────────────────────+
                    |    Validator Pipeline     |
                    +─────────────┬─────────────+
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
+─────────────────+      +─────────────────+      +─────────────────+
| status:ACCEPTED |      | status:NEEDS_   |      | status:REJECTED |
| accepted: true  |      |        REVIEW   |      | accepted: false |
|                 |      | accepted: true  |      |                 |
| Clear clinical  |      | Low resolution, |      | Cat/landscape,  |
| evidence, valid |      | missing ranges, |      | blank image,    |
| tests/medicines |      | unconfirmed rx  |      | corrupted file  |
+─────────────────+      +─────────────────+      +─────────────────+
```

---

## 3. Comprehensive Output JSON Schema

### 3.1 Accepted / Needs-Review Medical Response

```json
{
  "record_id": "c4b1e5a2-9721-4f10-b918-a3f282470e91",
  "status": "ACCEPTED",
  "document_type": "LAB_REPORT",
  "accepted": true,
  "reason_codes": [],
  "warnings": [],
  "ruleset_version": "2.1.0",
  "model_metadata": {
    "provider": "google",
    "model": "gemini-3.5-flash",
    "pipeline": "multimodal_vision_v2"
  },
  "quality_assessment": {
    "is_blank": false,
    "std_dev": 78.4,
    "contrast_range": 242,
    "quality_status": "EXCELLENT"
  },
  "field_provenance": {
    "extraction_engine": "llm_vision",
    "ocr_engine": "pymupdf_tesseract"
  },
  "doc_type": "lab_report",
  "doc_date": "2024-03-15",
  "collection_date": "2024-03-15",
  "follow_up_date": null,
  "language": "en",
  "patient_name_present": true,
  "allergies": [],
  "tests": [
    {
      "name": "Hemoglobin",
      "loinc": "718-7",
      "value": 14.2,
      "value_text": null,
      "unit": "g/dL",
      "ref_low": 13.0,
      "ref_high": 17.0,
      "flag": "NORMAL",
      "explanation_en": "Hemoglobin (14.2 g/dL) is within normal reference limits (13.0 - 17.0 g/dL).",
      "explanation_ta": "ஹீமோகுளோபின் (14.2 g/dL) இயல்பான வரம்பிற்குள் உள்ளது (13.0 - 17.0 g/dL).",
      "confidence": 0.98,
      "bbox": [0.12, 0.35, 0.78, 0.04],
      "provenance": {
        "source_text": "Hemoglobin: 14.2 g/dL (Ref: 13.0 - 17.0)",
        "method": "llm_vision"
      }
    }
  ],
  "medicines": [],
  "diagnoses": [],
  "safety_alerts": [],
  "drug_advisories": [],
  "cost_savings": null,
  "summary_en": "Your laboratory test for Hemoglobin is within the normal reference range.",
  "summary_ta": "உங்கள் ஹீமோகுளோபின் பரிசோதனை முடிவு இயல்பான வரம்பிற்குள் உள்ளது.",
  "summary_hi": "आपका हीमोग्लोबिन परीक्षण सामान्य सीमा के भीतर है।",
  "needs_review": [],
  "disclaimer": "This AI-generated analysis is for informational and educational purposes only. It does not constitute medical advice, diagnosis, or treatment recommendations. Always consult a qualified healthcare provider.",
  "error": null
}
```

---

### 3.2 Rejected Non-Medical Response (Cat, Landscape, Selfie, Invoice, Code)

```json
{
  "record_id": "7fa4d3b1-8b2a-4318-b2ef-349c4f1c9d81",
  "status": "REJECTED",
  "document_type": "NON_MEDICAL",
  "accepted": false,
  "reason_codes": [
    "NON_MEDICAL_DOCUMENT"
  ],
  "warnings": [
    "Document does not contain recognizable clinical tests or prescriptions."
  ],
  "ruleset_version": "2.1.0",
  "model_metadata": {
    "provider": "validator_gatekeeper"
  },
  "quality_assessment": {
    "is_blank": false,
    "quality_status": "REJECTED_NON_MEDICAL"
  },
  "field_provenance": null,
  "extracted_data": null,
  "doc_type": "non_medical",
  "doc_date": null,
  "collection_date": null,
  "follow_up_date": null,
  "language": "en",
  "patient_name_present": false,
  "allergies": [],
  "tests": [],
  "medicines": [],
  "diagnoses": [],
  "safety_alerts": [],
  "drug_advisories": [],
  "cost_savings": null,
  "summary_en": null,
  "summary_ta": null,
  "summary_hi": null,
  "needs_review": [
    "DOCUMENT_REJECTED"
  ],
  "disclaimer": "This AI-generated analysis is for informational and educational purposes only. It does not constitute medical advice, diagnosis, or treatment recommendations. Always consult a qualified healthcare provider.",
  "error": {
    "code": "DOCUMENT_REJECTED",
    "message": "Document rejected: Not a recognizable medical document."
  }
}
```

---

## 4. Reason Codes Reference Catalog

| Reason Code | Category | Meaning & Recommended UI Action |
| :--- | :--- | :--- |
| `NON_MEDICAL_DOCUMENT` | Rejection | Input is an ordinary photo (pet, selfie, scenery, receipt, meme). **UI:** Display rejection badge: *"Please upload a valid medical report or prescription."* |
| `BLANK_OR_UNREADABLE_DOCUMENT` | Rejection | Document image is completely blank, monochrome, or unreadable. **UI:** Prompt user to retake photo with proper lighting. |
| `CORRUPTED_OR_UNREADABLE_FILE` | Rejection | File signature failed or file buffer is truncated/corrupt. **UI:** Advise re-uploading file. |
| `UNSUPPORTED_FILE_TYPE` | Rejection | Extension or MIME type not in allowed set (PDF, JPEG, PNG, WEBP). |
| `FILE_SIZE_LIMIT_EXCEEDED` | Rejection | File exceeds configured 20 MB size boundary. |
| `INSUFFICIENT_MEDICAL_EVIDENCE` | Review/Rejection | Document text detected, but zero clinical tests or medications were found. |
| `MISSING_REFERENCE_RANGE` | Warning | Test value extracted, but laboratory provided no reference interval. Evaluated as `UNKNOWN`. |
| `AMBIGUOUS_DOSAGE_SCHEDULE` | Warning | Prescription dosing instruction cannot be uniquely parsed into `M-A-N`. Marked for human confirmation. |

---

## 5. Backward Compatibility Guarantee

To ensure **zero disruption** to Praveen's backend (`app.py`, `routes/`, `database.py`) and Naveen's frontend components:
1. **Existing Keys Retained:** `record_id`, `doc_type`, `doc_date`, `tests`, `medicines`, `allergies`, `diagnoses`, `safety_alerts`, `disclaimer`, and `error` remain in their original positions and types.
2. **Safe Fallbacks:** When a document is rejected, `tests` and `medicines` are returned as empty lists `[]` rather than throwing missing-key errors in legacy loops.
3. **HTTP Status Code Mapping:**
   - `status == "ACCEPTED"` $\rightarrow$ HTTP 200 OK
   - `status == "NEEDS_REVIEW"` $\rightarrow$ HTTP 200 OK (with warning headers / review payload)
   - `status == "REJECTED"` $\rightarrow$ HTTP 422 Unprocessable Entity
   - `error["code"] == "FILE_NOT_FOUND"` $\rightarrow$ HTTP 404 Not Found
