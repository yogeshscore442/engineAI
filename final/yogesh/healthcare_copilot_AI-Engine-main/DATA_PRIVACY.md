# Data Privacy, De-Identification & Confidentiality Policy
**AI Health Copilot Engine**  
**Component:** Yogesh (Core AI Engine)  
**Version:** 2.1.0  
**Effective Date:** 2026-10-20  
**Legal Frameworks:** India Digital Personal Data Protection Act (DPDP) 2023, HIPAA Privacy & Security Rules (45 CFR Part 160/164), ABDM Health Data Management Policy.

---

## 1. Overview and Privacy Philosophy

The AI Health Copilot Engine processes sensitive personal data (SPD), protected health information (PHI), and digital medical documents.

Our privacy architecture follows the principle of **Data Minimization and Zero Unnecessary Retention**:
1. Only the minimum data required to parse clinical facts is processed.
2. Direct personal identifiers are masked prior to external model transit.
3. No medical images or document buffers are permanently stored by the AI engine.
4. Ephemeral temporary files are purged immediately upon processing completion.

---

## 2. Personal Identifiable Information (PII) Redaction Engine

De-identification is executed in `ai_engine/privacy.py` before any document text or summaries are passed to third-party model providers or external network endpoints.

### 2.1 Masking Specification

| Data Category | Target Identifier Pattern | Mask Replacement Token | Regex Rule / Mechanism |
| :--- | :--- | :--- | :--- |
| **Phone Number** | 10-digit Indian mobile, `+91` prefix, `0` prefix, hyphenated | `[PHONE_MASKED]` | `(?:\+91[\s\-]?)?(?:0)?[6-9]\d{9}` |
| **Aadhaar ID** | 12-digit Indian national UIDAI number | `[AADHAAR_MASKED]` | `\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b` |
| **Email Address** | Standard RFC 5322 email addresses | `[EMAIL_MASKED]` | `\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b` |
| **Medical Record Numbers** | UHID, MRN, PID, Patient ID alphanumeric patterns | `[ID_MASKED]` | `\b(?:UHID\|MRN\|PID\|Patient\s*ID)[:\s\-]+[A-Za-z0-9\-_/]+` |
| **Patient Name Labels** | Document header lines: `Patient:`, `Pt Name:`, `Name:` | `[NAME_MASKED]` | Lookbehind extraction of name tokens following clinical headers |

### 2.2 Preservation of Clinical Data
The privacy engine employs negative-lookahead assertions to guarantee that clinical values and units are **NEVER** accidentally masked:
- `10 mg`, `500 mg`, `120/80 mmHg`, `5.6 mmol/L` are preserved verbatim.
- Doctor names (e.g. `Dr. Rajesh Kannan`) are preserved for prescription traceability unless explicitly redacted.
- Diagnostic dates (`2024-03-15`) are preserved for clinical timeline sequencing.

### 2.3 Idempotency Guarantee
The masking engine is strictly idempotent:
$$\text{mask\_text}(\text{mask\_text}(x)) == \text{mask\_text}(x)$$
Applying the masking filter multiple times produces identical tokens without recursive corruption.

---

## 3. Boundary Protection: Local vs. External Cloud

```
+---------------------------------------------------------------------------------+
|                                 TRUST BOUNDARY                                  |
|                                                                                 |
|  [Uploaded File]                                                                |
|         │                                                                       |
|         ▼                                                                       |
|  [Magic Bytes & Integrity] ─── (Local Validator: validator.py)                  |
|         │                                                                       |
|         ▼                                                                       |
|  [Image Preprocessing & OCR] ─ (Local In-Memory: PyMuPDF / Tesseract)           |
|         │                                                                       |
|         ▼                                                                       |
|  [PII Sanitization] ────────── (Local Regex Engine: privacy.py)                 |
|         │                                                                       |
|         ├──────────────────────────────────────────────────────┐                |
|         ▼                                                      ▼                |
|  [Local Fallback Parser]                           [Cloud Vision / LLM API]    |
|   - LOINC Catalog Match                             - TLS 1.3 Encrypted Transit |
|   - NLEM Brand Lookup                               - Zero Data Retention (ZDR) |
|   - 100% On-Premises                                - PII Masked Text Only      |
|         │                                                      │                |
|         └──────────────────────┬───────────────────────────────┘                |
|                                │                                                |
|                                ▼                                                |
|                   [Contract Output & Scrubbing]                                 |
|                    - Status & Quality Assessment                                |
|                    - Provenance Attached                                        |
|                    - Ephemeral Temp Cleanup                                     |
+---------------------------------------------------------------------------------+
```

### 3.1 Third-Party Cloud Transits
When external LLM providers (Google Gemini, OpenAI, Anthropic) are utilized:
1. **Network Security:** Strict TLS 1.3 with pinned certificates.
2. **Data Retention Policy:** Provider API contracts must specify zero-data retention (data not used for model training or retained beyond request execution).
3. **Transmission Content:** Only the sanitized image or masked OCR text is transmitted. Raw patient names, phone numbers, and Aadhaar identifiers are redacted before transit.

### 3.2 Offline / Local Execution Capability
If internet connectivity is lost or strict on-premises data isolation is required:
- The engine operates 100% locally using PyMuPDF direct text extraction, local Tesseract OCR, and deterministic rule engines (`ai_engine/flags.py`, `ai_engine/brands.py`, `ai_engine/interactions.py`).
- No external network packets are emitted in offline fallback mode.

---

## 4. Temporary File Lifecycle & Retention

1. **Storage Location:** Temporary files are created strictly within the application's allocated scratch directory (`tempfile.mkdtemp()`).
2. **File Permissions:** Created with POSIX `0600` / Windows explicit user ACLs (readable only by the backend service account).
3. **Deterministic Teardown:** Python `try ... finally` contexts and explicit `shutil.rmtree()` / `os.unlink()` handlers guarantee deletion immediately after document feature extraction.
4. **Crash Cleanup:** Background garbage collector sweeps temporary directories on service startup to eliminate stale buffers from unexpected termination.

---

## 5. Security & Secret Management

1. **Zero Secret Hardcoding:**
   - API keys (`GOOGLE_API_KEY`, `LLM_API_KEY`) are loaded from environment variables (`.env`).
   - If keys are missing, the engine gracefully transitions to offline/mock mode rather than crashing or revealing credentials in tracebacks.
2. **Error Scrubbing:**
   - Exception handlers in `ai_engine/models.py` sanitize traceback messages before returning error dictionaries to consumers, preventing stack traces, internal file paths, or credentials from leaking to end users.

---

## 6. Regulatory Limitations and Disclaimers

> **IMPORTANT:** Automated regular-expression masking significantly reduces the risk of accidental PII disclosure, but does **NOT** guarantee mathematical 100% de-identification or true legal anonymity under HIPAA Safe Harbor / Expert Determination standards. Unusual handwriting, embedded watermarks, or handwritten signatures may evade automated pattern recognition. Clinical organizations deploying this engine in production must establish institutional Data Protection Agreements (DPAs) and appropriate administrative safeguards.
