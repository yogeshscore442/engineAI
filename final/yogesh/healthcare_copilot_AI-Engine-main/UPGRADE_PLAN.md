# AI Health Copilot Engine — Systematic Upgrade Plan (UPGRADE_PLAN.md)

**Document Date:** 2026-10-20  
**Target:** Robust, Evidence-Grounded, Responsible Medical Document Engine  
**Execution Strategy:** Non-destructive, incremental, backward-compatible upgrades with test-driven verification at every stage.

---

## 1. Architectural Upgrade Overview

To resolve false extractions, synthetic data fabrication, and lack of provenance, the engine will be refactored into a **Strict 5-Stage Evidence-Based Processing Pipeline**:

```
[Uploaded Document File]
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: File & Signature Validation                   │
│ - Path traversal protection                            │
│ - Magic byte inspection (PDF, JPEG, PNG, TIFF, WebP)   │
│ - File size and dimension constraints                  │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Quality & Readability Assessment              │
│ - Blank page & solid color detection                   │
│ - Contrast, sharpness, and resolution assessment       │
│ - Textual content & density check                      │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: Multi-Signal Medical Classification           │
│ - Multimodal classification (OCR + Visual features)    │
│ - Terminology, header, and tabular layout scoring      │
│ - Distinct classes: LAB_REPORT, PRESCRIPTION,          │
│   DISCHARGE_SUMMARY, DIAGNOSTIC_REPORT, NON_MEDICAL    │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 4: Evidence-Grounded Extraction & Provenance     │
│ - Field provenance: original text, bbox, method        │
│ - Strict grounding (no hallucinations or outside facts)│
│ - Zero fallback fabrication on noisy numbers           │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 5: Decision, Medical Rules, Privacy & Validation │
│ - Deterministic LOINC flagging (LOW/NORMAL/HIGH/UNK)   │
│ - No synthetic ABHA or fabricated LOINC in FHIR        │
│ - Outcome Decision: ACCEPTED / NEEDS_REVIEW / REJECTED │
│ - Output Schema Validation & Disclaimer Enforcement    │
└────────────────────────────────────────────────────────┘
```

---

## 2. Execution Phases & Action Items

### Phase 1: Repository Discovery & Baseline Testing (Completed)
- Audited all 24 source files, schemas, and configurations.
- Executed unit test suites in both Yogesh and Praveen workspaces.
- Documented baseline test passing rates and blind spots.

### Phase 2: Feature Inventory & Bug Identification (Completed)
- Created `ENGINE_AUDIT.md`, `FEATURE_INVENTORY.md`, `BUGS_AND_RISKS.md`, and `UPGRADE_PLAN.md`.
- Identified 8 critical bugs and mapped root causes.

### Phase 3: Reproduce Non-Medical Acceptance Bug
- Build automated reproduction tests proving that random non-medical images (cat picture, blank canvas, random prose) previously failed to reject properly.
- Verify exact error trajectories.

### Phase 4: Implement Strict Input Validation & Document Classifier
- Implement `ai_engine/validator.py` with:
  - Magic byte verification (`%PDF`, `\xFF\xD8\xFF`, `\x89PNG`).
  - Blank and solid color image detection (variance and histogram analysis).
  - Multi-signal medical classification scoring (clinical keywords, laboratory headers, prescription tokens, diagnostic headers).
  - Medical evidence threshold: Requires recognizable clinical evidence before acceptance.
  - Decision outcome: `ACCEPTED`, `NEEDS_REVIEW`, `REJECTED`.
  - Machine-readable reason codes (`NON_MEDICAL_DOCUMENT`, `CORRUPT_FILE`, `IMAGE_TOO_BLURRY`, `EMPTY_DOCUMENT`, `UNSUPPORTED_TYPE`).

### Phase 5: Field-Level Provenance & Safe Evidence Extraction
- Update `models.py` to support:
  - `status: Literal["ACCEPTED", "NEEDS_REVIEW", "REJECTED"]`
  - `document_type: str` (supporting `NON_MEDICAL`, `LAB_REPORT`, `PRESCRIPTION`, `DISCHARGE_SUMMARY`, `DIAGNOSTIC_REPORT`)
  - `accepted: bool`
  - `reason_codes: list[str]`
  - `warnings: list[str]`
  - `quality_assessment: dict`
  - `field_provenance: dict`
- Update `extract.py`:
  - Upgrade LLM system prompt to permit `NON_MEDICAL` detection and honest rejection.
  - Eliminate noisy number fallback matcher that turned dates/room numbers into lab tests.
  - Ensure missing fields remain `None` / `null` without synthetic substitution.

### Phase 6: Clinical Rules, Reference Intervals & Dosage Parsing
- Review and refine `flags.py` to retain source laboratory ranges where printed.
- Enhance `dosage.py` to flag ambiguous abbreviations and unlisted frequencies for reviewer attention.
- Preserve verbatim prescription wording in `schedule_raw`.

### Phase 7: Medicine Normalization & Drug Interaction Guard
- Maintain brand catalog integrity (`brands.csv` and `jan_aushadhi.csv`).
- Enhance `interactions.py` with explicit advisory indicating that absence of detected interactions on incomplete lists does not guarantee clinical safety.

### Phase 8: Responsible AI, Privacy & Uncertainty Handling
- Produce `RESPONSIBLE_AI.md`, `DATA_PRIVACY.md`, and `MODEL_CARD.md`.
- Ensure multi-lingual de-identification preserves clinical units and numbers while masking personal identifiers.
- Ensure all processing errors and rejections avoid leaking sensitive patient information.

### Phase 9: FHIR & Output Contract Integrity
- Correct `fhir.py`:
  - Never fabricate synthetic ABHA numbers; use source ABHA if present, or omit patient identifier cleanly.
  - Never default unknown LOINC codes to `30745-4`; use code `unknown` with source text display or omit LOINC coding cleanly.
- Ensure complete backward compatibility for Praveen's backend consumers.

### Phase 10: Expanded Automated Testing & Negative Test Suite
- Produce `TESTING_GUIDE.md`.
- Create exhaustive negative test suite (`tests/test_negative_cases.py`):
  - Cat photo, landscape, selfie, blank image, random prose, random numbers, fake lab with gibberish names, prescription with no medicines, corrupted file, unsupported file extension.
- Create regression tests for all identified bugs.
- Remove misleading `USE_MOCK_AI=true` patch from real error handling tests.

### Phase 11: Objective Evaluation Harness
- Upgrade `eval.py` to evaluate both positive and negative cases.
- Measure False Acceptance Rate (FAR) for non-medical images (target: 0.0%).
- Produce reproducible `EVALUATION_REPORT.md`.

### Phase 12: Backend Integration & Deployment Verification
- Verify integration with Praveen's backend (`final/praveen/backend`).
- Verify that `RealAIClient` correctly receives rejection codes (`NON_MEDICAL_DOCUMENT`) without falling back to mock files.
- Produce `API_CONTRACT.md`.

### Phase 13: Final Engineering Report
- Compile comprehensive engineering audit and refactoring report matching all Section 24 requirements.

---
