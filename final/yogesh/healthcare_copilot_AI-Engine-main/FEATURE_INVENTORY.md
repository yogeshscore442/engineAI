# AI Health Copilot Engine — Feature Inventory (FEATURE_INVENTORY.md)

**Document Date:** 2026-10-20  
**Repository:** `final/yogesh/healthcare_copilot_AI-Engine-main`  
**Classification Standards:**
- **Working and verified:** Implemented, covered by rigorous tests, assertions verified against ground truth or deterministic logic.
- **Implemented but insufficiently tested:** Code exists and functions, but test coverage is narrow, relies on mocks, or misses critical edge cases.
- **Partially implemented:** Feature is incomplete, covers only happy paths, or lacks essential medical validation stages.
- **Incorrect or unreliable:** Implementation introduces errors, false positives, hallucinations, synthetic IDs, or silent data corruptions.
- **Missing:** Required by enterprise medical specification but absent from codebase.
- **Not applicable:** Not relevant to the core AI engine scope.

---

## 1. Feature Status Matrix

| ID | Feature / Component | Module(s) | Status | Detailed Findings & Evidence |
| :---: | :--- | :--- | :--- | :--- |
| **F-01** | **Strict Document Type & Magic Validation** | `ocr.py`, `extract.py` | **Incorrect or unreliable** | Checks only filename/MIME string; lacks magic byte checks. Rejects corrupt files, but treats non-medical images as medical. |
| **F-02** | **Image Quality & Blank Detection** | `ocr.py` | **Missing** | No check for blank/solid white/black images, extreme blur, severe low resolution, or zero textual content. |
| **F-03** | **Multi-Signal Medical Document Classification** | `extract.py` | **Incorrect or unreliable** | LLM prompt forces choice between 4 medical types (`prescription`, `lab_report`, etc.). Lacks `NON_MEDICAL` category. Heuristic classifier falls back to default. |
| **F-04** | **Medical Evidence Gatekeeper** | `extract.py` | **Missing** | No gatekeeper to reject images containing zero verifiable medical evidence (no tests, no medicines, no clinical structure). |
| **F-05** | **Field-Level Provenance Tracking** | `models.py`, `extract.py` | **Partially implemented** | Bounding box fields exist on models, but are almost always populated with `None`. No trace of page number, raw matched text, or normalization stage. |
| **F-06** | **Deterministic Abnormal Lab Value Flagging** | `flags.py` | **Working and verified** | Computes `LOW`, `NORMAL`, `HIGH`, `UNKNOWN` deterministically using LOINC intervals. Document-stated ranges take precedence over catalog. |
| **F-07** | **LOINC Catalog Mapping & Alias Resolution** | `flags.py`, `aliases.json` | **Working and verified** | Resolves test names to LOINC codes via 60+ aliases. Rejects unknown units and reversed intervals. |
| **F-08** | **Clinical Unit Conversion** | `units.py` | **Working and verified** | Validated conversion factors for glucose (`18.0182`), cholesterol (`38.67`), triglycerides (`88.57`), creatinine (`88.4`), hemoglobin (`10.0`). Rejects unlisted conversions. |
| **F-09** | **Indian Brand Name to Generic Normalizer** | `brands.py`, `brands.csv` | **Working and verified** | Maps 360+ Indian commercial brand names to generic names and strengths. Prefix stripping (`Tab`, `Cap`). Returns `None` for unknown brands. |
| **F-10** | **Prescription Dosage & Schedule Parser** | `dosage.py` | **Working and verified** | Accurately parses `1-0-1`, `0-0-1`, `OD`, `BD`, `TDS`, `AC`, `PC`, and duration strings (`5 days`). |
| **F-11** | **Ambiguous Dosage Flagging** | `dosage.py` | **Implemented but insufficiently tested** | Unrecognized patterns return empty parsed slots, but do not explicitly flag an ambiguity warning to the reviewer. |
| **F-12** | **Clinical Drug-Drug Interaction (DDI) Guard** | `interactions.py`, `ddi_rules.json` | **Partially implemented** | Identifies 12 documented severe/moderate drug interaction pairs. Lacks dataset versioning, polypharmacy rules, and notice of incomplete medication list. |
| **F-13** | **Food Timing & Drug Administration Advisories** | `interactions.py` | **Working and verified** | Provides evidence-based advice (Levothyroxine on empty stomach, Metformin with meals, Statins at bedtime). |
| **F-14** | **Jan Aushadhi Generic Savings Calculator** | `affordability.py` | **Working and verified** | Calculates potential patient savings comparing branded prescriptions with PMBJP generic pricing. |
| **F-15** | **ICD-10 Condition Terminology Mapping** | `diagnoses.py`, `icd10.json` | **Implemented but insufficiently tested** | 130+ conditions mapped. Substring matching is prone to over-matching on common English words. |
| **F-16** | **PII Masking & Patient De-Identification** | `privacy.py` | **Implemented but insufficiently tested** | Masks phone, Aadhaar, MRN, UHID, email, and labeled patient names. Regex-based; unlabelled patient names in unstructured text may slip through. |
| **F-17** | **Safe Plain-Language English Summary** | `summarize.py` | **Working and verified** | Scanner blocks forbidden diagnosis/treatment phrases. Grounding check verifies summary numbers against extracted record. Fixed disclaimer appended. |
| **F-18** | **Safe Tamil Plain-Language Summary** | `summarize.py` | **Working and verified** | Verified Tamil patient summary generator and deterministic fallback with disclaimer. |
| **F-19** | **Safe Hindi Plain-Language Summary** | `summarize.py` | **Working and verified** | Verified Hindi patient summary generator with deterministic template and disclaimer. |
| **F-20** | **Text-to-Speech (TTS) Voice Copilot** | `voice.py` | **Partially implemented** | Browser HTML5 Web Speech synthesis functions properly. Native Piper TTS integration is a mock/placeholder. |
| **F-21** | **ABDM HL7 FHIR R4 Bundle Export** | `fhir.py` | **Incorrect or unreliable** | Generates valid JSON syntax for FHIR Bundle, but synthesizes fake ABHA identifiers (`ABHA-...`) and substitutes hardcoded LOINC `30745-4` when missing. |
| **F-22** | **OCR Preprocessing & Deskew** | `ocr.py` | **Working and verified** | Auto-orient, LANCZOS 2x resize, contrast boost, unsharp filter, and project-profile deskew operate safely and independently. |
| **F-23** | **Multi-Model LLM Failover** | `extract.py` | **Partially implemented** | Candidate models list exists, but catches generic exceptions without logging structured telemetry or fallback provenance. |
| **F-24** | **Rule-Based Fallback Text Extraction** | `extract.py` | **Incorrect or unreliable** | Matches dictionary aliases with any adjacent digits on a line. Fabricates clinical tests on non-medical documents containing numbers. |
| **F-25** | **Cross-Check Verification against OCR** | `crosscheck.py` | **Implemented but insufficiently tested** | Verifies numbers and medicine tokens against raw OCR. Skips Tamil documents entirely. |
| **F-26** | **SHA-256 File Caching** | `cache.py` | **Working and verified** | Computes SHA-256 hash of file content; caches JSON for 24h in user cache directory. |
| **F-27** | **Never-Raise Top-Level Interface** | `ai_engine/__init__.py` | **Working and verified** | Top-level try/except wraps `extract_record` and always returns a dictionary with contract keys (`record_id`, `disclaimer`, `error`). |
| **F-28** | **Negative Testing on Non-Medical Inputs** | `tests/` | **Missing** | Test suite contained zero tests for non-medical images (cats, landscapes, blank pages, receipts). |
| **F-29** | **Calibrated Confidence Scoring** | `models.py`, `eval.py` | **Partially implemented** | Confidence fields exist in schemas, but values are largely hardcoded heuristics (`0.80`, `0.85`, `0.95`) rather than statistically calibrated probabilities. |
| **F-30** | **Mock Mode Segregation** | `ai_engine/__init__.py` | **Incorrect or unreliable** | Mock mode returns static files regardless of what file path is provided, creating a false impression of live extraction in testing. |

---

## 2. Summary by Feature Status

- **Working and verified:** 11 features (37%)
- **Implemented but insufficiently tested:** 5 features (17%)
- **Partially implemented:** 5 features (17%)
- **Incorrect or unreliable:** 5 features (17%)
- **Missing:** 4 features (13%)
- **Not applicable:** 0 features (0%)

**Conclusion:** Over 47% of engine features require immediate correction, enhancement, or rigorous negative testing before the engine can be considered clinically safe and reliable.
