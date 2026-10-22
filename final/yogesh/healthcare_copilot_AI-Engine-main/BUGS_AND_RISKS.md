# AI Health Copilot Engine — Bugs & Clinical Risk Assessment (BUGS_AND_RISKS.md)

**Document Date:** 2026-10-20  
**Target System:** `healthcare_copilot_AI-Engine-main` & Backend Integration  

---

## 1. Confirmed Software Defects & Root Cause Analysis

### BUG-01: False Medical Classification of Arbitrary Non-Medical Images
- **Severity:** Critical (Safety & Reliability Violation)
- **Root Cause:**
  1. The LLM extraction system prompt in `ai_engine/extract.py` specifies:
     ```text
     9. doc_type must be one of: prescription, lab_report, discharge_summary, diagnostic_report.
     ```
     The prompt provides no option to report non-medical images, drawings, photographs, or unrelated text.
  2. The Pydantic model `HealthRecord` in `ai_engine/models.py` restricts `doc_type`:
     ```python
     DocType = Literal["prescription", "lab_report", "discharge_summary", "diagnostic_report"]
     ```
     Returning `"non_medical"` or `"rejected"` causes a validation exception, which triggers fallback to mock or synthetic errors.
  3. The heuristic classifier `_classify_doc_type_from_text` defaults to `"unknown"` when zero signals match, but `_get_typed_system_prompt("unknown")` provides the standard medical extraction prompt without rejection logic.
- **Clinical Impact:** A patient or user uploading a cat photograph, receipt, or random landscape receives an output structured as a medical record. If the LLM generates any hallucinations, the user may be led to believe health data was discovered.

---

### BUG-02: Rule-Based Fallback Text Matcher Fabricates Lab Values from General Numbers
- **Severity:** High (Data Fabrication Vector)
- **Location:** `ai_engine/extract.py` (`_fallback_extract_from_text`)
- **Root Cause:**
  ```python
  for test_key, entry in ranges.items():
      for alias in entry.get("aliases", []):
          if re.search(r"\b" + re.escape(alias) + r"\b", line_lower):
              match = re.search(r"\b(\d+(?:\.\d+)?)\b", line_clean)
              if match:
                  val = float(match.group(1))
  ```
  This code loops over all lines in raw OCR text. If any word on a line matches a common word in `aliases.json` (for example, "time", "date", "sample", "urea", "rbc"), the **first number on the entire line** is extracted as a measured laboratory value with an ungrounded confidence score of `0.80`.
- **Clinical Impact:** Dates (e.g. `2024-10-15` -> `2024`), line numbers, page numbers, invoice values, or phone numbers are extracted as blood glucose or creatinine levels.

---

### BUG-03: Synthetic Patient Identifier (ABHA) Generation in FHIR Converter
- **Severity:** High (Identity & Regulatory Integrity Violation)
- **Location:** `ai_engine/fhir.py` (`record_to_fhir_bundle`)
- **Root Cause:**
  ```python
  patient: Dict[str, Any] = {
      ...
      "identifier": [
          {
              "system": "https://healthid.ndhm.gov.in",
              "value": f"ABHA-{record_id[:8].upper()}",
          }
      ],
  }
  ```
  When no ABHA identifier exists on the source document, the engine invents a synthetic ABHA identifier formatted as `ABHA-XXXXXX`.
- **Clinical Impact:** Corrupts downstream electronic health record (EHR) linkages. A fabricated ABHA number could falsely associate one patient's record with another citizen's national health identity in ABDM repositories.

---

### BUG-04: Hardcoded Default LOINC Code for Unmatched Laboratory Tests
- **Severity:** High (Diagnostic Inaccuracy)
- **Location:** `ai_engine/fhir.py` (`record_to_fhir_bundle`)
- **Root Cause:**
  ```python
  loinc = test.get("loinc") or "30745-4"
  ```
  If an extracted test cannot be matched to a LOINC code in `reference_ranges.json`, the converter automatically assigns `30745-4` (Chest X-ray single projection view).
- **Clinical Impact:** A blood test, biopsy finding, or urine analysis without an identified LOINC is represented in FHIR as a Chest X-ray.

---

### BUG-05: Test Suite Masking Real Failures with `USE_MOCK_AI=true`
- **Severity:** High (Testing Integrity Failure)
- **Location:** `tests/test_never_raises.py`
- **Root Cause:**
  ```python
  with patch.dict(os.environ, {"USE_MOCK_AI": "true"}):
      from ai_engine import extract_record
      return extract_record(file_path, mime)
  ```
  Tests intended to verify graceful handling of corrupted images, invalid binary bytes, and missing files patched mock mode on. Consequently, the tests never executed image parsing or validation; they simply read `contract/mock_lab_report.json` and passed.
- **Clinical Impact:** Production code bugs in image validation remained invisible despite a 100% green test suite.

---

### BUG-06: Permissive Summary on Empty Document Extractions
- **Severity:** Medium (False Reassurance Risk)
- **Location:** `ai_engine/summarize.py` (`_deterministic_summary_en`)
- **Root Cause:**
  ```python
  if not parts:
      parts.append("Please review this record with your doctor.")
  return " ".join(parts) + " " + DISCLAIMER
  ```
  When extraction returns zero tests, zero medicines, and zero diagnoses, the engine still outputs an English, Tamil, and Hindi summary advising the user to "review this record with your doctor", rather than informing them that the document is not a valid or readable medical record.
- **Clinical Impact:** Misleads users into assuming their unreadable or corrupted document was processed and contains no abnormal findings.

---

### BUG-07: Silent Replacement of Failed AI Extractions in Backend Integration
- **Severity:** Medium (Silent Error Masking)
- **Location:** `final/praveen/backend/app/services/ai_client.py`
- **Root Cause:**
  ```python
  if res.get("error") and settings.allow_mock_fallback:
      logger.warning("AI extraction returned error, falling back to mock: %s", res.get("error"))
      return await MockAIClient().extract(file_bytes, filename_hint, lang)
  ```
  If `allow_mock_fallback` is enabled in backend settings, any document that fails extraction is silently replaced with a mock medical report containing synthetic patient laboratory data.

---

### BUG-08: Absence of Magic Byte File Signature Verification
- **Severity:** Medium (Security & Ingestion Integrity)
- **Location:** `ai_engine/ocr.py` (`load_document`)
- **Root Cause:**
  The function branches purely on the string `mime` parameter (`"pdf" in mime_lc`). If a malicious or non-PDF binary is provided with `mime="application/pdf"`, `fitz` or `pdf2image` crashes or logs warnings without pre-validating `%PDF-` file headers.

---

## 2. Clinical Risk Analysis Matrix

| Risk Domain | Potential Hazard | Existing Mitigation | Residual Risk | Required Action |
| :--- | :--- | :--- | :--- | :--- |
| **Diagnostic Hallucination** | Non-medical image generates phantom clinical flags | None (Prompt forces 1 of 4 medical types) | **CRITICAL** | Implement 5-stage document classification pipeline; reject non-medical inputs with code `NON_MEDICAL_DOCUMENT`. |
| **False Reassurance** | Critical test omitted or unreadable, interpreted as normal | Deterministic flagging does not assume unread tests are normal | **HIGH** | Explicitly report `NEEDS_REVIEW` and unreadable fields; distinguish missing data from normal data. |
| **Identity Corruption** | Synthetic ABHA assigned to patient record in FHIR | Fixed prefix `ABHA-` | **HIGH** | Never invent ABHA IDs; use source ABHA or omit identifier when absent. |
| **Dosage Ambiguity** | Ambiguous schedule coerced into standard frequency | Regex parser handles common patterns | **MEDIUM** | Flag ambiguous schedules (`needs_review`) and preserve verbatim text. |
| **Drug Interactions** | Incomplete medication list assumed to have zero interactions | Warnings in advisories | **MEDIUM** | Include disclaimer that absence of detected interaction does not guarantee safety when medication list is partial. |
| **Data Leakage (PII)** | Patient phone, address, or Aadhaar logged or passed to external LLM | Regex masking in `privacy.py` | **LOW-MEDIUM** | Ensure all logging strips PII; evaluate multi-lingual PII regexes. |

---
