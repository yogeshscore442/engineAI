# AI Health Copilot — Dataset Schema & Annotation Guidelines

## 1. Overview & Provenance
This dataset schema establishes legally compliant, de-identified training and evaluation data requirements for the Local AI Health Copilot.
All data used in training and evaluation is either:
1. Synthetically generated from representative clinical document templates (NABL lab standards, Indian prescription norms, ABDM guidelines).
2. De-identified public clinical records containing zero Protected Health Information (PHI).

## 2. Document Classes

| Class ID | Target Label | Description | Key Indicators |
| :--- | :--- | :--- | :--- |
| **0** | `NON_MEDICAL` | Any file that is not a clinical health record: selfies, pets, landscapes, invoices, grocery receipts, general articles, source code. | High negative vocabulary, absence of clinical units, natural image color variance. |
| **1** | `LAB_REPORT` | Clinical pathology, biochemistry, hematology, microbiology, or urine analysis reports. | Test names, numeric observed values, units (`g/dL`, `mg/dL`, `cells/cumm`), biological reference intervals. |
| **2** | `PRESCRIPTION` | Outpatient prescription (Rx) by an Indian doctor or clinic. | `Rx`, doctor credentials, dosage schedules (`1-0-1`, `OD`, `BD`), brand names, formulation (`Tab`, `Cap`). |
| **3** | `DISCHARGE_SUMMARY` | Hospital inpatient admission and discharge record. | Admission date, discharge date, IP number, hospital course, final diagnosis, discharge medications. |
| **4** | `DIAGNOSTIC_REPORT` | Radiology, imaging, or diagnostic test reports (X-Ray, Ultrasound, CT, MRI, ECG, Echo). | Modality name, clinical indication, findings, and diagnostic impression. |

## 3. Data Schema (JSONL Format)

```json
{
  "source_id": "string (unique anonymous identifier, e.g. syn_rx_001)",
  "split": "train | val | test",
  "document_type": "NON_MEDICAL | LAB_REPORT | PRESCRIPTION | DISCHARGE_SUMMARY | DIAGNOSTIC_REPORT",
  "language": "en | ta | hi | mixed",
  "ocr_text": "string (verbatim OCR transcript without modification)",
  "ground_truth": {
    "doc_date": "YYYY-MM-DD or null",
    "patient_name_present": true | false,
    "medicines": [
      {
        "name_raw": "string (as written)",
        "generic": "string or null",
        "brand_name": "string or null",
        "strength": "string or null",
        "formulation": "tablet | capsule | syrup | injection | ointment | drops | null",
        "schedule_raw": "string or null",
        "schedule_parsed": ["morning", "afternoon", "night"],
        "food_instruction": "before_food | after_food | null",
        "duration_days": "integer or null",
        "verification_state": "present_verified | requires_human_review",
        "source_text": "string",
        "bbox": [0.1, 0.2, 0.4, 0.05]
      }
    ],
    "tests": [
      {
        "name": "string",
        "value": "float or null",
        "value_text": "string or null",
        "unit": "string or null",
        "lab_reference_interval": "string or null",
        "ref_low": "float or null",
        "ref_high": "float or null",
        "flag": "LOW | NORMAL | HIGH | UNKNOWN",
        "source_text": "string",
        "bbox": [0.1, 0.3, 0.8, 0.04]
      }
    ],
    "diagnoses": [
      {
        "text": "string",
        "icd10": "string or null"
      }
    ]
  }
}
```

## 4. De-Identification & Privacy Protocol
Before any document text is added to the training set:
1. Microsoft Presidio and regex sanitization strip all:
   - Patient names (replaced with `[PATIENT]`)
   - Phone numbers (replaced with `[PHONE]`)
   - Email addresses (replaced with `[EMAIL]`)
   - National IDs (Aadhaar, PAN, Voter ID, MRN) (replaced with `[ID_NUM]`)
   - Street and house addresses (replaced with `[LOCATION]`)
2. Clinical measurements, test names, medicine names, and dosages are strictly PRESERVED without masking.

## 5. Train / Validation / Test Splitting Rules
1. **Source Isolation**: All documents originating from the same clinic, hospital, or synthetic generation batch must remain within the same split to avoid data leakage.
2. **Stratified Sampling**: Ensure balanced representation of document types and handwriting styles across all splits.
3. **Purity of Final Test Set**: The test split must remain untouched during hyperparameter tuning and model iteration.
