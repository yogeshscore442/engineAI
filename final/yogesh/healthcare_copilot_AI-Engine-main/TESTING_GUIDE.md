# Testing Guide & Quality Assurance Architecture
**AI Health Copilot Engine**  
**Component:** Yogesh (Core AI Engine Test Suite)  
**Version:** 2.1.0  
**Test Framework:** Pytest 8.x with Coverage, Typeguard, AnyIO  

---

## 1. Quality Assurance Architecture

The test architecture ensures zero clinical hallucinations, verified deterministic rules, rigorous privacy masking, and bulletproof negative-case rejection.

```
+───────────────────────────────────────────────────────────────────────────────+
|                           TEST SUITE ARCHITECTURE                            |
|                                                                               |
|  [Unit Tests]            [Negative & Edge]        [Integration & Flows]       |
|  - test_models.py        - test_negative_cases.py - test_processing.py        |
|  - test_brands.py        - test_never_raises.py   - praveen/test_integration  |
|  - test_flags.py         (Cats, Landscapes,       (Upload -> OCR -> Extract   |
|  - test_dosage.py         Selfies, Blank, Blur)    -> Rules -> FHIR -> Bundle)|
|  - test_privacy.py                                                            |
|  - test_scanner.py                                                            |
|                                                                               |
|  [Regression Suite]      [Clinical Guardrails]    [Contract Validation]       |
|  - test_regressions.py   - Forbidden phrases      - FHIR R4 schema checks     |
|  - Unit-range mismatch   - Number grounding       - Reason codes verification |
+───────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Test Execution Commands

### 2.1 Running the Core AI Engine Test Suite
Run from `healthcare_copilot_AI-Engine-main`:

```bash
# Run all 179 core engine tests with verbose output
python -m pytest tests/ -v

# Run the strict mandatory negative case test suite
python -m pytest tests/test_negative_cases.py -v

# Run the never-raises error contract suite
python -m pytest tests/test_never_raises.py -v

# Run privacy & de-identification unit tests
python -m pytest tests/test_privacy.py -v

# Run deterministic clinical rules (flags, brands, dosage)
python -m pytest tests/test_flags.py tests/test_brands.py tests/test_dosage.py -v

# Run guardrail scanner & grounding tests
python -m pytest tests/test_scanner.py -v
```

### 2.2 Running Backend Integration Tests (Praveen's Module)
Run from `final/praveen/backend`:

```bash
# Run all 84 backend integration, upload, and API tests
python -m pytest tests/ -v

# Run end-to-end full module flow integration tests
python -m pytest tests/test_integration.py -v
```

---

## 3. Test Suites & Categorical Coverage

### Category A: Unit Tests
- **`tests/test_flags.py` (38 tests):**
  - Evaluates normal, low, high, and critical ranges for glucose, creatinine, hemoglobin, HbA1c, platelets, etc.
  - Verifies that unmapped tests receive `flag: "UNKNOWN"` and never fabricate normal ranges.
- **`tests/test_dosage.py` (22 tests):**
  - Tests prescription shorthand parsing: `1-0-1`, `TID`, `BD`, `OD`, `QDS`, `SOS`.
  - Verifies food instructions (`before_food`, `after_food`) and duration day calculations.
- **`tests/test_brands.py` (19 tests):**
  - Validates brand-to-generic mappings against NLEM 2022 (e.g. `Dolo 650` $\rightarrow$ `paracetamol 650 mg`, `Augmentin 625` $\rightarrow$ `amoxicillin + clavulanic acid 625 mg`).
- **`tests/test_privacy.py` (16 tests):**
  - Confirms masking of 10-digit phones, Aadhaar, email, UHID, and patient names.
  - Verifies that clinical values, doctor names, and test units are **never** accidentally masked.
  - Confirms masking idempotency.
- **`tests/test_scanner.py` (26 tests):**
  - Verifies rejection of forbidden diagnostic statements (`"you are diagnosed with"`, `"you should take"`, `"increase dose"`).
  - Verifies rejection of ungrounded hallucinated numbers in summaries.
- **`tests/test_models.py` (15 tests):**
  - Tests Pydantic schemas, ISO-8601 date validators, `HealthRecord`, and `make_rejected_record`.

---

### Category B: Mandatory Negative Test Cases (`tests/test_negative_cases.py`)

Every negative input must produce `status: "REJECTED"` or `"NEEDS_REVIEW"` with `accepted: false` and `NON_MEDICAL_DOCUMENT` reason code, with **zero clinical records**:

| Test Case | Input Characteristics | Expected Behavior |
| :--- | :--- | :--- |
| `test_blank_white_image` | Completely white 800x600 image (0 text) | Status `REJECTED`, code `BLANK_OR_UNREADABLE_DOCUMENT` |
| `test_cat_photo_rejected` | Pet photograph with high texture | Status `REJECTED`, code `NON_MEDICAL_DOCUMENT` |
| `test_landscape_photo_rejected` | Natural landscape scenery | Status `REJECTED`, code `NON_MEDICAL_DOCUMENT` |
| `test_random_selfie_rejected` | Photo of a human face | Status `REJECTED`, code `NON_MEDICAL_DOCUMENT` |
| `test_ordinary_paragraphs_text` | Non-medical text paragraphs (story, code) | Status `REJECTED`, code `NON_MEDICAL_DOCUMENT` |
| `test_random_numbers_invoice` | Supermarket grocery receipt with prices | Status `REJECTED`, code `NON_MEDICAL_DOCUMENT` |
| `test_corrupted_file` | Truncated byte header / noise | Status `REJECTED`, code `CORRUPTED_OR_UNREADABLE_FILE` |
| `test_unsupported_file_extension` | Executable `.exe` / `.sh` / `.zip` | Status `REJECTED`, code `UNSUPPORTED_FILE_TYPE` |
| `test_illegible_blur_image` | Image with extreme Gaussian blur | Status `REJECTED` or `NEEDS_REVIEW` with warning |

---

### Category C: Positive & Edge Case Tests

- **`test_legitimate_lab_report_unusual_layout`:**
  - Validates lab report with header, tabular data, non-standard layout. Correctly accepted with parsed tests.
- **`test_legitimate_prescription_incomplete_optional`:**
  - Tests real-world prescription with missing clinic header and omitted durations. Handled without crashing or fabricating duration.
- **`test_mixed_english_tamil_document`:**
  - Tests bilingual Tamil/English clinical text. Correctly accepted and parsed without character corruption.

---

### Category D: Contract Invariant & Never-Raises Suite (`tests/test_never_raises.py`)

Guarantees that `extract_record()`:
1. Never raises an uncaught exception on nonexistent files (`FILE_NOT_FOUND`).
2. Never raises on zero-byte files (`EMPTY_FILE`).
3. Never raises on corrupted binary data.
4. Always includes the mandatory clinical disclaimer in all paths.
5. In mock mode (`USE_MOCK_AI=true`), returns contract-compliant mock records for genuine sample names while still rejecting non-medical tokens.

---

## 4. Continuous Integration (CI) Guidelines

In corporate CI/CD pipelines (GitHub Actions, GitLab CI):
```yaml
name: AI Engine Quality Gate
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run Engine Tests
        run: |
          pytest tests/ -v --maxfail=1
      - name: Run Backend Integration Tests
        run: |
          cd ../../praveen/backend
          pip install -r requirements.txt
          pytest tests/ -v --maxfail=1
```
