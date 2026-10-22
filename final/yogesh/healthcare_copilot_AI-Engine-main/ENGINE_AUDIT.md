# AI Health Copilot Engine — Comprehensive Audit Report (ENGINE_AUDIT.md)

**Audit Date:** 2026-10-20  
**Auditor:** Senior AI Engineer, Python Backend Engineer, Medical Processing & AI Safety Specialist  
**Target Repository:** `final/yogesh/healthcare_copilot_AI-Engine-main` (Core AI Engine) & integration surfaces with `final/praveen/backend`  
**Execution Environment:** Windows, Python 3.10.11, PyMuPDF 1.27.2, Pillow 10.4.0, Pydantic 2.12.5, Pytest 8.4.2  

---

## 1. Executive Summary & Audit Baseline

The AI Health Copilot Engine is designed as a clinical-safety-first document processing pipeline to ingest medical records (laboratory reports, prescriptions, discharge summaries, and diagnostic/radiology reports), extract structured healthcare records, flag abnormal clinical lab values deterministically against LOINC reference intervals, parse prescription dosages, identify drug-drug interactions (DDI), and convert records into ABDM-ready FHIR R4 bundles.

While the existing codebase demonstrates thoughtful initial design (deterministic flagging separated from LLM inference, PII masking regexes, frozen disclaimer text, and structured Pydantic models), **a rigorous, evidence-based audit reveals critical architectural vulnerabilities, hallucination vectors, and silent failure modes**:

1. **Non-Medical Document False Acceptance:** Any non-medical image (photographs of animals, scenery, blank images, arbitrary documents) is forced by prompt and schema constraints to be categorized as a medical document (`lab_report` or `prescription`).
2. **Plausible Default & Mock Leaks:** When processing fails or mock mode is toggled, static mock records (`mock_lab_report.json`, `mock_prescription.json`) are injected into production or test pathways, giving an illusion of 100% extraction success.
3. **Regex-Based Fallback Hallucinations on Noise:** The fallback text parser matches any dictionary alias with any nearby integer or float, extracting numbers from page headers, timestamps, room numbers, or invoice numbers as laboratory values.
4. **Synthetic FHIR & Identity Data:** FHIR generation manufactures synthetic ABHA identifiers (`ABHA-{record_id[:8]}`) and substitutes hardcoded LOINC codes (`30745-4`) for unmatched tests.
5. **Superficial Unit Test Passing:** 167 unit tests pass, but core integration tests (`test_never_raises.py`) patched `USE_MOCK_AI="true"`, bypassing real image validation and error handling entirely.

---

## 2. Inventory of Python Modules & Actual Responsibilities

| Module | Declared Responsibility | Actual Implemented Reality |
| :--- | :--- | :--- |
| `ai_engine/__init__.py` | Public interface (`extract_record`), cache lookup, summary & advisory orchestration | Orchestrates extraction, but bypasses real processing if `USE_MOCK_AI=true`. Swallows unexpected errors and returns `make_error_record`. |
| `ai_engine/models.py` | Pydantic contract models (`HealthRecord`, `MedicineRecord`, `TestRecord`, etc.) | Strictly validates field types, but schema `DocType` only allows `prescription`, `lab_report`, `discharge_summary`, `diagnostic_report`. Lacks `NON_MEDICAL` or rejection status. Bounding box validation requires 4 floats, but confidence is uncalibrated. |
| `ai_engine/extract.py` | Ingestion, LLM extraction dispatch, JSON parsing, prompt management, and fallback text parsing | LLM prompt forces classification into one of 4 medical document types. Text-based fallback matches dictionary words to any number on the line, fabricating lab values on non-medical text. |
| `ai_engine/ocr.py` | Document ingestion (PDF to images via pdf2image/fitz), image preprocessing, Tesseract OCR | Image preprocessing includes EXIF transpose, 2x LANCZOS resize, contrast enhance, unsharp mask, and deskew. However, `Tesseract` binary is frequently missing on Windows PATH, causing silent fallback to empty OCR text without error propagation. |
| `ai_engine/flags.py` | Deterministic abnormal flag computation (`LOW`, `NORMAL`, `HIGH`, `UNKNOWN`) against LOINC reference ranges | Correctly computes flags without LLM influence. Properly requires matching units or handles `mmol/L` conversion. Rejects non-finite values and reversed ranges. However, lacks provenance records. |
| `ai_engine/brands.py` | Maps Indian pharmaceutical brand names to generic names and strengths via `brands.csv` | Performs normalized lookup and prefix stripping (`Tab`, `Cap`, `Syp`). Returns `(None, None)` for unknown brands (does not hallucinate). |
| `ai_engine/dosage.py` | Parses prescription schedule shorthand (`1-0-1`, `OD`, `BD`, `TDS`, `before_food`) | Regex parsing for standard Indian dosage patterns. Does not flag ambiguous formats (e.g. `1-0-1-1` or unlisted frequencies) for human review. |
| `ai_engine/interactions.py`| Detects drug-drug interactions (DDI) and clinical advisories via `ddi_rules.json` | Cross-references extracted medicine tokens against static list of 12 interaction rules. Lacks dataset versioning, cannot evaluate polypharmacy beyond paired rules, and does not report dataset incompleteness. |
| `ai_engine/fhir.py` | ABDM HL7 FHIR Release 4 document bundle generation | Builds valid JSON structure for `Bundle`, `Composition`, `Patient`, `Observation`, `MedicationRequest`. Fabricates placeholder ABHA identifiers (`ABHA-...`) and falls back to hardcoded LOINC `30745-4` if missing. |
| `ai_engine/summarize.py` | Safe bilingual patient summaries in English, Tamil, and Hindi | Implements regex forbidden-word scanner and number grounding check against extracted data. Falls back to deterministic templates. However, if extraction returns empty tests/meds on non-medical documents, it still outputs a reassuring medical disclaimer. |
| `ai_engine/voice.py` | Speech generation HTML and Piper TTS integration | Generates HTML5 Web Speech API snippet for browser-side speech synthesis; returns placeholder path when Piper offline. |
| `ai_engine/privacy.py` | De-identification and PII masking | Masks phone numbers, emails, Aadhaar patterns, MRN/UHID/ABHA, and labeled patient names. Regex-based only; does not guarantee complete anonymization. |
| `ai_engine/units.py` | Unit conversion constants and validation | Defines standard conversion factors (glucose, cholesterol, triglycerides, creatinine, hemoglobin). Rejects conversions outside documented categories. |
| `ai_engine/diagnoses.py` | ICD-10 terminology mapping via `icd10.json` | Exact and substring match against 130+ clinical conditions. Substring matching is prone to false positives on short words. |
| `ai_engine/affordability.py`| Jan Aushadhi generic pricing and savings calculation | Calculates cost differences between branded drugs and PMBJP Jan Aushadhi generic equivalents via `jan_aushadhi.csv`. |
| `ai_engine/crosscheck.py` | Cross-checks LLM extracted entities against local OCR text | Checks if numeric test values and medicine tokens exist in OCR text; adjusts confidence and appends to `needs_review`. Skips Tamil text entirely. |
| `ai_engine/cache.py` | SHA-256 disk cache for extraction results in `~/.health_copilot_cache` | Caches results for 24h by file content hash. |
| `ai_engine/cli.py` | Command-line testing interface | Invocable via `python -m ai_engine.cli <path>`. Prints JSON output. |
| `app.py` | Interactive CLI launcher menu | Provides 1-click batch runs, demo samples, and pytest runner. |
| `eval.py` | Evaluation harness comparing against 12 synthetic ground-truth files | Evaluates field-level accuracy, but crashes or loops if API key is not configured and Tesseract is missing. |

---

## 3. Public Functions, Classes, and Entry Points

### 3.1 Core Public API (`ai_engine`)
- `extract_record(file_path: str, mime: str, lang_hint: str = "auto") -> dict`: Public entry point. Guaranteed never to raise; returns contract-compliant dict with `record_id`, `disclaimer`, `error`.
- `calculate_prescription_savings(medicines: list) -> dict`: Returns price comparison and savings breakdown.
- `record_to_fhir_bundle(record: dict) -> dict`: Converts extracted record to FHIR R4 Bundle.
- `export_fhir_json(record: dict, output_path: str) -> str`: Serializes FHIR Bundle to disk.
- `check_drug_interactions(medicines: list) -> list`: Evaluates DDI rules on medicine list.
- `get_drug_advisories(medicines: list) -> list`: Retrieves administration advice (food timing, precautions).
- `generate_audio(text: str, lang: str = "en") -> str`: Synthesizes audio or returns fallback path.
- `get_browser_speech_html(text_en: str, text_ta: str, text_hi: str) -> str`: Generates HTML5 audio player.

### 3.2 Backend Service Integration (`final/praveen/backend`)
- `RealAIClient.extract(file_bytes: bytes, filename_hint: str, lang: str) -> dict`: Wraps `extract_record` in threadpool executor (`run_in_executor`). Writes `file_bytes` to temporary file and calls `extract_record`.
- `MockAIClient.extract(...) -> dict`: Reads static `mock_*.json` from `contract/` directory.

---

## 4. Dependencies & Version Constraints

From `requirements.txt` and verified in active Python 3.10 environment:
- `pydantic>=2.9.0`: Used for data models and contract validation.
- `pillow>=10.4.0`: Core image loading, resizing, enhancing.
- `pymupdf>=1.24.0` (`fitz`): High-speed PDF rendering to pixmaps.
- `pdf2image>=1.17.0`: Fallback PDF rendering (requires external Poppler).
- `pytesseract>=0.3.10`: OCR wrapper (requires external Tesseract binary).
- `google-generativeai>=0.8.0`: Legacy Google Gemini SDK (deprecated upstream in favor of `google-genai`).
- `openai>=1.40.0`: OpenAI API client.
- `anthropic>=0.34.0`: Anthropic API client.
- `python-dotenv>=1.0.1`: Environment file loading.
- `pytest>=8.2.0`, `pytest-cov>=5.0.0`: Testing framework.

---

## 5. Medical Rules, Reference Data, and Provenance

1. **`reference_ranges.json`**:
   - Contains 70+ laboratory tests (LOINC codes, canonical units, reference intervals for male/female/unsexed, unit aliases, `mmol_factor`).
   - Sourced from LOINC and standard clinical chemistry reference intervals (e.g. Tietz).
2. **`brands.csv`**:
   - Contains 360+ Indian commercial brand names mapped to generic formulations and standard strengths.
   - Sourced from National List of Essential Medicines (NLEM) and Jan Aushadhi database.
3. **`jan_aushadhi.csv`**:
   - Official NPPA / PMBJP price list for Jan Aushadhi generic medicines compared to average market branded prices.
4. **`ddi_rules.json`**:
   - Contains 12 drug-drug interaction pairs and 10 single-drug clinical food/timing advisories.
   - Sourced from clinical pharmacopeia guidelines (e.g. Aspirin + Clopidogrel bleeding alert, Sildenafil + Nitrates hypotension alert).
5. **`icd10.json`**:
   - 130+ clinical condition names mapped to ICD-10-CM codes and formal display descriptions.
6. **`aliases.json`**:
   - 60+ variations and common OCR misspellings mapped to canonical laboratory test names.

---

## 6. Analysis of Existing Test Suite Assertions

| Test File | Total Tests | What It Actually Asserts | Blind Spots & Flaws |
| :--- | :---: | :--- | :--- |
| `test_models.py` | 27 | Pydantic model constraints: valid dates, date regex, bbox element length == 4, positive duration days, disclaimer constancy. | Does not validate uncalibrated confidence score semantics or non-medical document flags. |
| `test_flags.py` | 21 | Document-specified ranges take priority; unit conversion (mmol/L to mg/dL); sex-specific ranges; UNKNOWN on missing range or unknown unit. | Does not test non-numeric tests with ambiguous qualitative ranges. |
| `test_never_raises.py` | 10 | That `extract_record` never raises an unhandled exception on corrupt/empty/missing files. | **CRITICAL FLAW:** Sets `os.environ["USE_MOCK_AI"] = "true"`, thus testing `_load_mock` rather than real image processing and validation pipelines. |
| `test_processing.py` | 13 | Documented unit conversion factors; summary preserves values and disclaimers; unknown summary does not declare normal. | Relies on synthetic record dictionaries. |
| `test_dosage.py` | 17 | Regex parsing for `1-0-1`, `BD`, `TDS`, `AC`, `PC`, `x 5 days`. | Does not test ambiguous or conflicting prescriptions (e.g. `1-0-1-1`, `PRN with food`). |
| `test_interactions.py` | 4 | Known pairs in `ddi_rules.json` trigger alerts; non-interacting pairs trigger no alerts. | Does not test polypharmacy, spelling variants, or unknown generic names. |
| `test_privacy.py` | 14 | Phone numbers, Aadhaar, MRN, UHID, and patient name prefix masking. | Does not test unstructured text where patient name is not prefixed by "Patient:". |
| `test_scanner.py` | 23 | Forbidden diagnosis phrases ("you have", "diagnosed with") and grounding check for numbers in summaries. | Safe incidental numbers (`0`, `1`, `2`, `100`) can mask ungrounded values if not strictly scoped. |
| `test_fhir.py` | 2 | FHIR Bundle structure contains expected resource types (`Composition`, `Patient`, etc.). | Does not validate against FHIR R4 schema or ABDM profile specifications. Accepts synthetic ABHA IDs. |
| `test_affordability.py`| 3 | Brand-to-Jan-Aushadhi savings calculation. | Only tests listed catalog brands. |
| `test_accuracy_regressions.py`| 6 | Non-finite values (`nan`, `inf`), unit mismatch, reversed bounds return `UNKNOWN`. | Solid assertions, but limited scope. |
| `test_voice.py` | 1 | HTML audio tag generation. | Minimal coverage. |

---

## 7. External AI Models, OCR, and Runtime Services

1. **Google Gemini Vision (`google.generativeai` / `gemini-3.5-flash`):**
   - Receives Base64-encoded JPEG image and system prompt.
   - Temperature set to `0.0`, `max_output_tokens=4096`.
   - Uses deprecated `google.generativeai` SDK.
2. **OpenAI (`gpt-4o` / `gpt-4o-mini`):**
   - Configured via `_call_openai` in `extract.py`.
3. **Anthropic (`claude-3-5-sonnet`):**
   - Configured via `_call_anthropic` in `extract.py`.
4. **Tesseract OCR:**
   - Invocable via `pytesseract.image_to_string(img, lang="eng+tam")`.
   - External binary dependency. When missing, fails with `TesseractNotFoundError` which is caught, resulting in empty OCR text.
5. **PyMuPDF (`fitz`):**
   - Python-native C-extension for PDF rasterization. Highly reliable and available in active environment.

---

## 8. Environment Variables and External Configuration

| Variable | Default Value | Purpose | Audit Observation |
| :--- | :--- | :--- | :--- |
| `LLM_PROVIDER` | `google` | Selects LLM backend (`google`, `openai`, `anthropic`) | Validated at dispatch time. |
| `LLM_API_KEY` | None | Primary API credential | Falls back to `GOOGLE_API_KEY`. Never hardcoded. |
| `GOOGLE_API_KEY` | None | Fallback Google API key | Checked if `LLM_API_KEY` is absent. |
| `LLM_MODEL` | `gemini-3.5-flash` | Model identifier | Throws error if blank when live extraction called. |
| `USE_MOCK_AI` | `false` | Enables static contract mock responses | If `true`, returns mock data regardless of input file validity. |
| `DISABLE_CACHE` | `false` | Bypasses SHA-256 disk cache | Evaluated in `cache.py`. |

---

## 9. File I/O, Caching, and Data Retention

- **Disk Cache (`~/.health_copilot_cache`):**
  - Files named by SHA-256 hash of document bytes: `<hash>.json`.
  - TTL: 24 hours (86,400 seconds).
  - Contains full extraction dictionary (including masked clinical values and summaries).
  - Risk: If two different users upload identical documents or test files, they share cached results (safe for identical content, but requires multi-tenant isolation in shared deployments).
- **Temporary Files:**
  - `RealAIClient` in backend creates `tempfile.TemporaryDirectory(prefix="health-extract-")` and deletes it after extraction.
  - Yogesh's `extract_from_file` reads from the given path without creating orphaned temporary files.

---

## 10. Silent Failures, Swallowed Exceptions, and Dangerous Fallbacks

The following 8 critical flaws were pinpointed during code tracing:

1. **Prompt-Forced Hallucination (`extract.py` L57):**
   ```python
   # Line 57: doc_type must be one of: prescription, lab_report, discharge_summary, diagnostic_report.
   ```
   *Impact:* An ordinary photo of a pet or landscape has NO way to be classified as non-medical. The LLM must hallucinate one of the four types.
2. **Fallback Text Matcher Leaks (`extract.py` L441-484):**
   ```python
   for test_key, entry in ranges.items():
       for alias in entry.get("aliases", []):
           if re.search(r"\b" + re.escape(alias) + r"\b", line_lower):
               match = re.search(r"\b(\d+(?:\.\d+)?)\b", line_clean)
   ```
   *Impact:* If any word on a page matches a test alias (e.g. "time", "date", "rbc", "urea"), any number on that line is extracted as a verified lab test with 0.80 confidence.
3. **Hardcoded Synthetic LOINC in FHIR (`fhir.py` L133):**
   ```python
   loinc = test.get("loinc") or "30745-4"
   ```
   *Impact:* Any test without a LOINC code is stamped with `30745-4` (Chest X-ray), violating clinical data integrity.
4. **Synthetic ABHA Patient Identifier (`fhir.py` L111):**
   ```python
   "value": f"ABHA-{record_id[:8].upper()}"
   ```
   *Impact:* Synthesizes a plausible-looking government health identifier where none exists.
5. **Reassuring Summary for Non-Medical/Empty Documents (`summarize.py` L274):**
   ```python
   if not parts:
       parts.append("Please review this record with your doctor.")
   ```
   *Impact:* When an empty or non-medical document produces 0 tests and 0 meds, the engine issues a clinical advisory rather than rejecting the input.
6. **Mock Mode Hijacks Test Coverage (`test_never_raises.py` L22):**
   ```python
   with patch.dict(os.environ, {"USE_MOCK_AI": "true"}):
   ```
   *Impact:* `TestNeverRaises` never tested real document error paths, giving false confidence in error handling.
7. **Backend Fallback Swallows AI Errors (`ai_client.py` L180-184):**
   ```python
   if res.get("error") and settings.allow_mock_fallback:
       return await MockAIClient().extract(file_bytes, filename_hint, lang)
   ```
   *Impact:* When the engine correctly returns an error, the backend quietly replaces it with a valid mock medical report if `allow_mock_fallback` is on.
8. **Lack of File Magic Signature Checking (`ocr.py` L86-90):**
   ```python
   if "pdf" in mime_lc:
       images = _load_pdf(path)
   else:
       images = _load_image(path)
   ```
   *Impact:* Trusts user-provided MIME string without inspecting header bytes (`%PDF`, `\xFF\xD8\xFF`, `\x89PNG`).

---
