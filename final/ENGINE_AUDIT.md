# AI Health Copilot — Core AI Engine Audit (Yogesh Component)

## 1. Executive Summary
- **Module Path**: `yogesh/healthcare_copilot_AI-Engine-main/ai_engine`
- **Core Functionality**: Document OCR ingestion, multimodal Vision LLM extraction, deterministic clinical validation, drug-drug interaction detection, NLEM brand normalization, FHIR bundle conversion, and bilingual summary generation.
- **Audit Date**: 2026-10-20
- **Status**: Critical validation defects identified and remediated.

---

## 2. Component Architecture & Workflow
```
Uploaded File (Image/PDF)
       │
       ▼
[ai_engine.ocr.load_document] ──────────► EXIF auto-orient, RGB, Lancaster resize, Unsharp mask
       │
       ▼
[ai_engine.validator.validate_medical_document]
  ├── Stage 1: File Signature & Magic Bytes (PDF, JPEG, PNG, WEBP, TIFF)
  ├── Stage 2: Quality & Blank Assessment (Std Dev, pixel contrast, resolution)
  ├── Stage 3: Multi-Signal Classification (Lab, Prescription, Discharge, Diagnostic)
  ├── Stage 4: Medical Evidence Gatekeeper (clinical tokens, measurement patterns, dosage)
  └── Stage 5: Decision Gate (ACCEPTED, NEEDS_REVIEW, REJECTED)
       │
       ├─────────────────────────► If REJECTED: Returns make_rejected_record immediately
       ▼ If ACCEPTED / NEEDS_REVIEW:
[ai_engine.extract.extract_from_file]
  ├── Multimodal Vision LLM (Google / OpenAI / Anthropic)
  ├── Fallback Deterministic OCR Parser (Regex with LOINC/Brand catalog)
  ├── Deterministic Enrichment (compute_flag, normalize_brand, parse_schedule)
  └── Safety Verification: Zero clinical findings -> NEEDS_REVIEW
       │
       ▼
[ai_engine.summarize.build_summaries] & [interactions.check_drug_interactions]
```

---

## 3. Discovered Defects & Vulnerabilities

| Defect ID | Severity | File & Location | Description & Root Cause |
| :--- | :--- | :--- | :--- |
| **ENG-01** | **CRITICAL** | `ai_engine/__init__.py:167-189` (`_load_mock`) | In `USE_MOCK_AI=true`, non-medical images (e.g. `IMG_9999.jpg`, phone camera photos) were accepted as `lab_report` with 5 fabricated tests because only a small hardcoded substring blacklist was checked. |
| **ENG-02** | **HIGH** | `ai_engine/validator.py:223-228` | Synthetic 1x1 test fixture check blindly accepted files without checking medical context, risking bypass during testing. |
| **ENG-03** | **HIGH** | `ai_engine/extract.py:674-685` | Documents with 0 clinical findings were previously allowed to be marked `ACCEPTED` if the LLM outputted empty arrays instead of explicitly rejecting non-medical files. |
| **ENG-04** | **MEDIUM** | `ai_engine/ocr.py:100-109` | When Tesseract is not installed or not in PATH, `fallback_text` became empty `""`, requiring image quality and signature checks to be ultra-robust. |

---

## 4. Remediation Plan
1. Refactor `_load_mock` in `ai_engine/__init__.py` to execute `validate_medical_document`. If the input is non-medical (photos, solid backgrounds, low text/evidence), it MUST return `make_rejected_record(reason_codes=["NON_MEDICAL_DOCUMENT"])`.
2. Ensure `NON_MEDICAL` is an explicit, supported status across all engines and prompts.
3. Guarantee that missing clinical values remain null, and zero-evidence documents are routed to `REJECTED` or `NEEDS_REVIEW`.
4. Prevent any downstream summary generation, interaction checking, or FHIR generation when status is `REJECTED`.
