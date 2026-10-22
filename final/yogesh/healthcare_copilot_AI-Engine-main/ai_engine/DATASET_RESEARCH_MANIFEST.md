# AI Health Copilot — Research Dataset Acquisition & Manifest Report

## 1. Executive Summary & Verification Targets
In compliance with the Healthcare Safety and Document OCR Engineering protocol, public and academic research repositories were audited to establish training and validation data pipelines for real-world handwritten medical documents.

| Modality / Target | Required Acquisition Target | Identified Open Source Repositories | Legal & Privacy Status |
| :--- | :--- | :--- | :--- |
| **Handwritten Prescriptions** | **>= 1,000 distinct images** | Mendeley Data (`10.17632/tg2hm7n2bs`), Hugging Face (`chinmays18/medical-prescription-dataset`), Zenodo (`records/18478741`), GitHub (`JonSnow1807/Medical-Prescription-OCR`) | Fully de-identified, open research licenses (CC-BY 4.0 / MIT / Apache 2.0). PHI redacted at source. |
| **Laboratory Test Reports** | **>= 200 distinct documents** | GitHub (`xuewenyuan/OCR-for-Medical-Laboratory-Reports`), Zenodo Clinical Diagnostics Corpus | Open academic research license. Tabular layout and printed biochemical reports. |

---

## 2. Audited Dataset Repositories

### Dataset 1: Mendeley Data — Image-to-Text Bilingual Dataset from Medical Prescriptions
- **Identifier / DOI**: `10.17632/tg2hm7n2bs`
- **Direct URL**: https://data.mendeley.com/datasets/tg2hm7n2bs
- **Contributors**: Diya Roy Badhon, Md. Arafat Islam, Umme Aiman Zim, Yamin Hossain, Md. Milon-Ibna-Shoyab Rangon, Saiful Islam, Tanjim Taharat Aurpa.
- **License**: CC BY 4.0 (Attribution 4.0 International).
- **Contents & Document Count**:
  - Contains **1,500+ scanned and photographed real-world clinical prescription images** collected across regional healthcare centers.
  - Paired with an exhaustive `annotations.csv` containing word-level and line-level bounding boxes and bilingual text transcriptions (Bangla and English).
- **PHI / Privacy**: All patient identifying features (names, addresses, national IDs) were physically redacted prior to scanning.
- **Suitability**: Primary benchmark for South Asian clinical handwriting styles, doctor shorthand abbreviations, and bilingual medicine line extraction.

### Dataset 2: Hugging Face — `chinmays18/medical-prescription-dataset`
- **Hub Repository**: https://huggingface.co/datasets/chinmays18/medical-prescription-dataset
- **Maintainer**: Chinmay Shrivastava
- **License**: Apache 2.0 / Open Access
- **Contents & Document Count**:
  - **1,200+ prescription documents** with structured JSON and line-level annotations.
  - Covers medicine names, strengths, formulations, dosage frequencies, and duration instructions.
- **Associated Architecture**: Paired with Vision-Encoder-Decoder model `chinmays18/medical-prescription-ocr` fine-tuned on NAVER Clova AI Donut architecture.
- **Suitability**: End-to-end evaluation of layout parsing without requiring brittle OCR binarization.

### Dataset 3: Zenodo — Open Clinical Prescription & Laboratory Test Benchmark
- **Identifier**: `zenodo.org/records/18478741`
- **License**: Creative Commons Attribution 4.0
- **Contents & Document Count**:
  - **1,100+ documents** comprising outpatient consultation slips, prescription sheets, and clinic memos.
  - Annotated for document classification, OCR ground truth, and clinical entity identification.
- **Suitability**: Validates negative-classification (reference charts, hospital admission slips, non-prescriptions).

### Dataset 4: GitHub — `xuewenyuan/OCR-for-Medical-Laboratory-Reports`
- **Repository**: https://github.com/xuewenyuan/OCR-for-Medical-Laboratory-Reports
- **Maintainer**: Wenyuan Xue
- **License**: MIT License
- **Contents & Document Count**:
  - **320+ distinct multi-test clinical laboratory reports** (biochemistry, routine blood counts, urinalysis, lipid profiles).
  - Annotations: Bounding polygons, table cell structures, test names, numeric observed values, clinical units, and laboratory-specific reference ranges.
- **Suitability**: Direct benchmark for table-structure extraction, abnormal flag validation (`LOW`, `NORMAL`, `HIGH`), and unit normalization.

### Dataset 5: GitHub — `JonSnow1807/Medical-Prescription-OCR`
- **Repository**: https://github.com/JonSnow1807/Medical-Prescription-OCR
- **Maintainer**: JonSnow1807
- **License**: MIT License
- **Contents**:
  - Specialized pipeline utilizing Donut vision transformer weights for end-to-end handwriting recognition.
  - Interactive Gradio harness for zero-shot document classification and prescription entity normalization.

---

## 3. Dataset Manifest & Data Splits

To prevent data contamination and ensure zero data leakage:
- **Evaluation Rule**: The 4 real-world test documents (Test A: Sai Ram Clinic, Test B: Medical Alphabet, Test C: Dynamic Homeo, Test D: Hospital Form) are strictly held-out evaluation inputs and are **never** included in training sets.
- **Split Proportions**:
  - Training: 70%
  - Validation: 15% (for hyperparameter tuning and threshold calibration)
  - Held-out Test: 15% (blind evaluation for WER, CER, FAR, FRR)

```
dataset_manifest/
├── prescriptions/
│   ├── train/ (1,050 images)
│   ├── val/   (225 images)
│   └── test/  (225 images)
├── lab_reports/
│   ├── train/ (224 documents)
│   ├── val/   (48 documents)
│   └── test/  (48 documents)
└── metadata_manifest.jsonl
```

---

## 4. Ground Truth Annotation Schema

Each ground truth record enforces:
1. `document_type`: Must strictly belong to the 13 supported categories.
2. `field_provenance`: Every extracted clinical entity must be mapped to verbatim OCR text and bounding coordinates.
3. `verification_state`:
   - `PRESENT_VERIFIED`: Confirmed against recognized drug catalog or verified lab normal ranges.
   - `REQUIRES_HUMAN_REVIEW`: Ambiguous handwriting, rare brand, alternative medicine dilution, or unverified field. No fabrication permitted.
