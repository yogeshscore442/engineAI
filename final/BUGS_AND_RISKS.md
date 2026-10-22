# AI Health Copilot — Bugs, Clinical Risks & Security Analysis

## 1. Clinical Risks of Non-Medical Document Acceptance
Accepting a non-medical photograph (such as a selfie, cat photo, landscape, or grocery receipt) as a medical document carries extreme clinical risks:
1. **Hallucination of Disease & Diagnoses**: Generating fabricated blood sugar, HbA1c, or kidney function values on a healthy user could cause panic or improper self-medication.
2. **Fabricated Medication Schedules**: Generating prescriptions for potent drugs (e.g. Metformin, Atorvastatin) could lead to dangerous drug-drug interactions or wrongful dispensing.
3. **Pollution of Longitudinal Health Records**: Creating false records corrupts patient trends and historical clinical timelines.
4. **Breach of Trust & Compliance**: Violates WHO, FDA, and ABDM guidance on Responsible AI in clinical decision support.

---

## 2. Risk Matrix

| Risk ID | Hazard | Severity | Likelihood Before Fix | Mitigation | Post-Mitigation Likelihood |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | Cat / Landscape / Selfie accepted as Lab Report | Critical | High | 5-Stage validation + Mock validation check + Backend 422 Rejection | Negligible |
| **RSK-02** | Zero-evidence document generates fake medical data | Critical | High | Minimum clinical token requirement + Evidence Gatekeeper | Negligible |
| **RSK-03** | Frontend intercepts upload with synthetic mock data | High | High | Enforce real backend dispatch on all file uploads | Zero |
| **RSK-04** | Rejected file remains in database as draft | High | High | Backend rejects with HTTP 422 before database commit | Zero |
| **RSK-05** | Ambiguous scans treated as verified normal results | Medium | Medium | Explicit `NEEDS_REVIEW` workflow with warning popup | Low |
| **RSK-06** | Disk exhaustion from rejected file clutter | Medium | Medium | Immediate atomic unlink of rejected upload files | Zero |

---

## 3. Security & Privacy Safeguards
- **MIME & Magic Bytes**: Inspect actual file headers (`%PDF-`, `\xff\xd8\xff`, `\x89PNG`, `RIFF/WEBP`, `II*/MM*`), preventing polyglot attacks.
- **Path Traversal Protection**: Reject null bytes and path manipulation.
- **Log Sanitization**: PII redaction (profile IDs and document text are scrubbed from log files).
- **Safe Error Responses**: Errors return stable reason codes without leaking system filepaths or stack traces.
