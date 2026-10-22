# AI Health Copilot — Backend API Audit (Praveen Component)

## 1. Executive Summary
- **Module Path**: `praveen/backend/app`
- **Framework**: FastAPI (Python 3.10+), SQLAlchemy with SQLite WAL mode, Uvicorn.
- **Audit Date**: 2026-10-20
- **Status**: Critical upload status propagation and error handling defects identified and remediated.

---

## 2. API Endpoints & Contract
- `POST /api/profiles/{profile_id}/records`: Primary file upload endpoint (Multipart form-data: `file`, `lang`).
- `GET /api/records/{record_id}`: Fetch record with clinical items and summary.
- `PUT /api/records/{record_id}`: Human-in-the-loop review and confirmation.
- `GET /api/health`: Health status endpoint.
- `GET /api/profiles/{profile_id}/timeline`: Chronological medical events.

---

## 3. Discovered Defects & Root Causes

| Defect ID | Severity | File & Location | Description & Root Cause |
| :--- | :--- | :--- | :--- |
| **BACK-01** | **CRITICAL** | `app/services/pipeline.py:85-104` | When the AI Engine rejected a file (`status: "REJECTED"` or `doc_type: "non_medical"`), the backend caught it as a generic error and created a `status: "draft"` record in the SQLite database, returning `HTTP 201 Created` instead of `HTTP 422 Unprocessable Entity`. |
| **BACK-02** | **HIGH** | `app/services/pipeline.py:59` | Uploaded non-medical files were permanently saved to disk under `UPLOAD_DIR` and not cleaned up upon rejection. |
| **BACK-03** | **HIGH** | `app/routers/records.py:60-99` | The upload route did not inspect `record.status == "REJECTED"` or raise HTTP 422 with a structured error contract. |
| **BACK-04** | **MEDIUM** | `app/services/files.py:30-45` | Magic bytes check allowed any `.jpg` / `.png` through even if the file was completely non-medical. |

---

## 4. Remediation Plan
1. Update `app/services/pipeline.py`:
   - Inspect `ai_result.get("status")` and `ai_result.get("accepted")`.
   - If `status == "REJECTED"` or `accepted is False` or `doc_type == "non_medical"`:
     - Immediately delete the temporary stored file.
     - Do NOT persist a record in the database.
     - Raise an explicit `MedicalDocumentRejectionException` or return structured rejection data.
2. Update `app/routers/records.py`:
   - Catch `MedicalDocumentRejectionException` and return `HTTP 422 Unprocessable Entity` with:
     ```json
     {
       "error": {
         "code": "NON_MEDICAL_DOCUMENT",
         "message": "The uploaded file does not appear to be a supported medical document. Please upload a valid laboratory report, prescription, or diagnostic report.",
         "reason_codes": ["NON_MEDICAL_DOCUMENT"],
         "status": "REJECTED"
       }
     }
     ```
3. Support `NEEDS_REVIEW` propagation properly without presenting uncertain fields as verified facts.
