# AI Health Copilot — Integration Test Plan

## 1. Scope and Objective
Validate that the entire pipeline:
```
Frontend UI (Upload.tsx / api/index.ts)
      │
      ▼ (HTTP multipart/form-data)
FastAPI Backend (routers/records.py -> services/pipeline.py)
      │
      ▼ (ai_engine.extract_record)
AI Engine (validator.py -> extract.py)
```
strictly rejects non-medical uploads, displays the required modal popup in the frontend, prevents database persistence for rejected documents, and preserves valid medical document extraction.

---

## 2. Test Cases

### Suite A: Non-Medical & Negative Upload Tests
| Test ID | Input Document Description | Expected Engine Decision | Expected Backend HTTP Status | Expected Frontend Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **TC-NEG-01** | Cat / Pet Photograph | `REJECTED` (`NON_MEDICAL_DOCUMENT`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |
| **TC-NEG-02** | Selfie / Portrait | `REJECTED` (`NON_MEDICAL_DOCUMENT`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |
| **TC-NEG-03** | Landscape / Wallpaper | `REJECTED` (`NON_MEDICAL_DOCUMENT`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |
| **TC-NEG-04** | Grocery Receipt / Invoice | `REJECTED` (`NON_MEDICAL_DOCUMENT`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |
| **TC-NEG-05** | Solid Blank / White Image | `REJECTED` (`BLANK_OR_EMPTY_PAGE`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |
| **TC-NEG-06** | Corrupted Image / Bad Signature | `REJECTED` (`UNSUPPORTED_OR_CORRUPT_FILE`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |
| **TC-NEG-07** | Empty 0-byte File | `REJECTED` (`EMPTY_FILE`) | `422 Unprocessable Entity` | Modal: "Invalid Medical Document" |

### Suite B: Valid Medical Documents (Positive Tests)
| Test ID | Input Document Description | Expected Engine Decision | Expected Backend HTTP Status | Expected Frontend Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **TC-POS-01** | Blood Lab Report (HbA1c, Glucose) | `ACCEPTED` (`LAB_REPORT`) | `201 Created` | Navigate to `/verify/{id}`, render tests |
| **TC-POS-02** | Doctor Prescription (Rx, Metformin) | `ACCEPTED` (`PRESCRIPTION`) | `201 Created` | Navigate to `/verify/{id}`, render medicines |
| **TC-POS-03** | Hospital Discharge Summary | `ACCEPTED` (`DISCHARGE_SUMMARY`) | `201 Created` | Navigate to `/verify/{id}`, render diagnosis |

### Suite C: Ambiguous & Low-Quality Documents
| Test ID | Input Document Description | Expected Engine Decision | Expected Backend HTTP Status | Expected Frontend Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **TC-AMB-01** | Low contrast scan with few medical words | `NEEDS_REVIEW` | `201 Created` (status: needs_review) | Display Review Required warning banner/modal |

---

## 3. Execution Procedure
1. Execute Unit & Negative Engine tests with `pytest`.
2. Execute Backend Pipeline & Route tests with `pytest`.
3. Execute Frontend Node test suite with `npm test`.
4. Run live HTTP integration tests against running backend (`http://127.0.0.1:8001`).
5. Verify frontend build with `npm run build`.
