"""
train_classifier.py — Document Intelligence Classifier Training & Calibration Pipeline.

Trains, calibrates, and evaluates the Healthcare Co-Pilot Document Classifier
using the 2,000-document dataset splits and adversarial negative samples.

Computes:
  - Macro & Per-class Precision, Recall, and F1
  - Confusion Matrix
  - Expected Calibration Error (ECE)
  - Brier Score
Saves the calibrated scikit-learn model to ai_engine/document_classifier.joblib.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

from .calibration import compute_brier_score, compute_ece

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AI_ENGINE_DIR = Path(__file__).resolve().parent
ROOT_DIR = AI_ENGINE_DIR.parent
DATA_DIR = ROOT_DIR.parent.parent / "dataset_pipeline" / "data" / "splits"
MODEL_OUTPUT_PATH = AI_ENGINE_DIR / "document_classifier.joblib"
REPORT_OUTPUT_PATH = ROOT_DIR / "EVALUATION_CALIBRATION_REPORT.json"

CLASSES = [
    "NON_MEDICAL",
    "LAB_REPORT",
    "PRESCRIPTION",
    "DISCHARGE_SUMMARY",
    "DIAGNOSTIC_REPORT",
]

CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

# Curated Non-Medical Negative Corpus to prevent false positives
NON_MEDICAL_SAMPLES = [
    "Cute fluffy orange cat kitten sleeping on carpet cute pet animal photography",
    "Golden retriever dog puppy barking in front of tree park nature wallpaper",
    "Macro photograph of green tree leaves grass outdoor sunshine forest background",
    "Snow covered mountain peak blue clear sky hiking nature landscape photography",
    "Selfie photo of friends at restaurant eating dinner laughing camera portrait",
    "Grocery store supermarket bill tax invoice total balance due thank you visit again gstin",
    "Retail receipt purchase shoes clothing cashier counter discount coupon payment",
    "Software engineering resume curriculum vitae python java git docker react developer",
    "def calculate_tax(subtotal, rate): return subtotal * rate import os sys json class",
    "Flight airline boarding pass ticket terminal gate seat departure passenger pnr",
    "Hotel reservation confirmation room check-in check-out booking reference travel invoice",
    "Movie theater ticket popcorn drinks cinema hall showtime screen cinema ticket",
    "Financial statement quarterly earnings report stock dividend portfolio balance sheet",
    "Auto repair mechanic service invoice oil change brake pads labor charges total",
    "Electricity utility bill consumer number units consumed due date total payable",
    "Chocolate chip cookies recipe flour sugar eggs butter baking soda vanilla oven bake",
    "Sports soccer match recap final score premier league championship tournament goals",
    "Smartphone unboxing review battery life display refresh rate camera sensor specs",
    "Car insurance policy coverage premium deductibles vehicle registration number",
    "Fashion clothing catalog summer collection shoes shirts jackets online shopping",
]

DISCHARGE_SUMMARY_SAMPLES = [
    "Hospital Discharge Summary Department of General Medicine Patient IP No 77821 Admission Date 2026-03-08 Discharge Date 2026-03-11 Final Diagnosis Acute Gastroenteritis Hospital Course Discharge Medications Tab Rablet 20 Tab Ondem 4",
    "SIMS Hospital Discharge Card Patient Name Deepak Age 34 DOA 2026-02-14 DOD 2026-02-18 Diagnosis Dengue Fever with Thrombocytopenia Clinical Summary Vitals stable at discharge Condition satisfactory Follow-up OPD in 1 week",
    "Discharge Summary Inpatient Medical Record Chief Complaints History of Present Illness Course in Hospital Patient tolerated oral diet Discharge Advice Tab Pan 40 OD Tab Multivitamin OD Consultant Physician Signature",
    "Department of Cardiology Discharge Summary Diagnosis Acute Coronary Syndrome Post PTCA to LAD Procedure Uncomplicated Admission Date Discharge Date Discharge Medications Tab Clopilet 75mg Tab Atorva 40mg Tab Metoprolol 25mg",
    "Surgical Discharge Summary Department of General Surgery Diagnosis Acute Appendicitis Procedure Laparoscopic Appendectomy Intraoperative findings acutely inflamed appendix Wound healthy Afebrile Sutures removal on day 8",
    "Pediatric Inpatient Discharge Card Diagnosis Acute Bronchiolitis Course in Hospital Nebulized with hypertonic saline SpO2 99% on room air Tolerating feeds Discharge Medications Syp Ascoril Junior Review in Pediatric OPD",
    "Orthopedic Hospital Discharge Summary Diagnosis Fracture Neck of Femur Right Procedure Hemiarthroplasty Post-op physiotherapy started Weight bearing with walker Discharge Tab Tramadol SOS Tab Cefuroxime 500mg BD",
    "Neurology Discharge Summary Patient IP 88291 Diagnosis Acute Ischemic Stroke Left MCA Territory Hospital Course Thrombolyzed with Alteplase Improved power 4/5 Discharge Tab Aspirin 150mg Tab Atorvastatin 40mg Speech therapy",
    "Department of Nephrology Discharge Summary Diagnosis Acute Kidney Injury secondary to sepsis Hospital Course IV fluids antibiotics Hemodialysis sessions nil Creatinine improved to 1.3 Discharge Advice Low potassium diet",
    "Department of Obstetrics and Gynecology Discharge Summary Indication Previous LSCS in labor Procedure Emergency Repeat Lower Segment Cesarean Section Live male baby delivered APGAR 9/10 Mother and baby healthy Discharge Tab Iron Tab Calcium",
    "Pulmonology Inpatient Discharge Summary Diagnosis Acute Exacerbation of COPD Hospital Course IV steroids bronchodilator nebulization Weaned off supplemental oxygen SpO2 96% Discharge Inhaler Budecort 200 Rotacaps 1 puff BD",
    "Oncology Day Care Discharge Summary Chemotherapy Cycle 3 Protocol Paclitaxel Carboplatin Pre-medications Ondansetron Dexamethasone Tolerated chemotherapy well Discharge Tab Pantoprazole 40mg Review with CBC in 7 days",
    "Inpatient Medical Summary Diagnosis Community Acquired Pneumonia IV Ceftriaxone completed Afebrile for 48 hours Chest X-ray clearing Discharge Tab Azithromycin 500mg OD for 3 days Follow up after 1 week",
    "Department of Urology Discharge Summary Diagnosis Right Ureteric Calculus Procedure Cystoscopy Right DJ Stenting Post-op recovery uneventful Clear urine Discharge Tab Urimax 0.4mg HS Tab Cipro 500mg BD Stent removal in 3 weeks",
    "Discharge Summary Department of ENT Diagnosis Chronic Suppurative Otitis Media Procedure Tympanoplasty Right Ear Post-operative course uneventful Mastoid dressing dry and intact Discharge Tab Augmentin 625mg Ear drops",
]

DIAGNOSTIC_REPORT_SAMPLES = [
    "City Radiology Imaging Institute Department of Radiodiagnosis Chest X-Ray PA View Clinical Indication Cough fever Findings Trachea central Both lung fields clear Costophrenic angles normal Impression Normal chest radiograph",
    "Ultrasound Abdomen and Pelvis USG Clinical History Pain in abdomen Liver normal size and echotexture Gall bladder normal no calculi Kidneys normal Spleen normal Impression Normal study of abdomen and pelvis",
    "12-Lead Electrocardiogram ECG Report Heart Rate 72 bpm Normal Sinus Rhythm PR Interval 160 ms QRS Duration 88 ms QTc 410 ms Impression Normal Electrocardiogram No ST elevation or depression",
    "MRI Brain with Contrast 3T Imaging Technique Axial T1 T2 FLAIR sequences Findings Normal brain parenchyma No intracranial hemorrhage or mass effect Ventricles normal Impression Normal MRI Brain study Radiologist MD",
    "Computed Tomography CT Scan Thorax HRCT Technique Thin axial sections Findings No ground glass opacities or consolidation Tracheobronchial tree patent Impression Normal HRCT Chest study",
    "2D Echocardiography with Color Doppler Report Left ventricular internal dimensions normal LVEF 62% No regional wall motion abnormality Valves structurally normal Doppler flows physiological Impression Normal LV systolic function",
    "MRI Lumbar Spine Plain Study Technique Sagittal and axial T1 and T2 weighted images Findings Normal lumbar lordosis L4-L5 mild posterior disc bulge without neural impingement Conus medullaris normal Impression Mild degenerative disc disease",
    "Ultrasound Neck and Thyroid Gland Both lobes of thyroid normal in size and echotexture No focal solid or cystic mass lesions Bilateral cervical lymph nodes unremarkable Impression Normal sonographic evaluation of thyroid gland",
    "CT Scan Abdomen and Pelvis with IV Contrast Liver spleen pancreas kidneys adrenal glands normal No retroperitoneal lymphadenopathy Bowel loops unremarkable Impression No acute intra-abdominal pathology",
    "Bilateral Digital Mammography Screening Study Both breasts show scattered fibroglandular densities No dominant mass clustered microcalcifications or architectural distortion Impression BIRADS Category 1 Negative study",
    "Carotid Doppler Ultrasound Bilateral Common and Internal Carotid Arteries show smooth intima-media thickness Normal peak systolic velocities No hemodynamically significant stenosis Vertebral flow antegrade Impression Normal Carotid Doppler",
    "X-Ray Bilateral Knees Standing AP View Medial and lateral joint spaces preserved No subchondral sclerosis or osteophytes Patellofemoral articulation normal Impression Normal bilateral knee radiograph",
    "X-Ray Cervical Spine AP and Lateral Alignment normal Vertebral body heights preserved Intervertebral disc spaces maintained Prevertebral soft tissues normal Impression Normal cervical spine radiograph",
    "Ultrasound Pelvis Transvaginal Scan TVS Uterus normal size and anteverted Endometrial thickness 6 mm Both ovaries normal follicular pattern Impression Normal pelvic sonogram",
    "Digital Radiography Paranasal Sinuses PNS View Frontal maxillary and sphenoid sinuses clear No mucosal thickening or air-fluid levels Impression Clear paranasal sinuses",
]


def load_split(split_name: str) -> list[tuple[str, str]]:
    split_path = DATA_DIR / f"{split_name}.jsonl"
    data = []
    if not split_path.exists():
        raise FileNotFoundError(f"Split file {split_path} not found. Run split_dataset.py first.")

    with open(split_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            text = item.get("ocr_text", "").strip()
            doc_type = item.get("document_type", "OTHER")
            if doc_type in CLASS_TO_IDX:
                data.append((text, doc_type))
    return data


def main():
    logger.info("Loading train, val, and test splits from %s...", DATA_DIR)
    train_raw = load_split("train")
    val_raw = load_split("val")
    test_raw = load_split("test")

    # Augment non-medical negative examples and other clinical classes
    for sample in NON_MEDICAL_SAMPLES[:12]:
        train_raw.append((sample, "NON_MEDICAL"))
    for sample in NON_MEDICAL_SAMPLES[12:16]:
        val_raw.append((sample, "NON_MEDICAL"))
    for sample in NON_MEDICAL_SAMPLES[16:]:
        test_raw.append((sample, "NON_MEDICAL"))

    for sample in DISCHARGE_SUMMARY_SAMPLES[:9]:
        train_raw.append((sample, "DISCHARGE_SUMMARY"))
    for sample in DISCHARGE_SUMMARY_SAMPLES[9:12]:
        val_raw.append((sample, "DISCHARGE_SUMMARY"))
    for sample in DISCHARGE_SUMMARY_SAMPLES[12:]:
        test_raw.append((sample, "DISCHARGE_SUMMARY"))

    for sample in DIAGNOSTIC_REPORT_SAMPLES[:9]:
        train_raw.append((sample, "DIAGNOSTIC_REPORT"))
    for sample in DIAGNOSTIC_REPORT_SAMPLES[9:12]:
        val_raw.append((sample, "DIAGNOSTIC_REPORT"))
    for sample in DIAGNOSTIC_REPORT_SAMPLES[12:]:
        test_raw.append((sample, "DIAGNOSTIC_REPORT"))

    X_train = [t[0] for t in train_raw]
    y_train = np.array([t[1] for t in train_raw])

    X_test = [t[0] for t in test_raw]
    y_test = np.array([t[1] for t in test_raw])

    logger.info("Training set size: %d | Test set size: %d", len(X_train), len(X_test))

    # Build Pipeline: TF-IDF + Calibrated Logistic Regression
    logger.info("Training TF-IDF Vectorizer with Calibrated Logistic Regression...")
    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=12000,
        sublinear_tf=True,
        lowercase=True,
    )

    base_clf = LogisticRegression(
        C=2.0,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
    )

    # Wrap in probability calibration
    calibrated_clf = CalibratedClassifierCV(
        estimator=base_clf,
        method="sigmoid",
        cv=3,
    )

    pipeline = Pipeline([
        ("tfidf", tfidf),
        ("clf", calibrated_clf),
    ])

    pipeline.fit(X_train, y_train)

    # Evaluation on held-out test split
    logger.info("Evaluating calibrated model on held-out test split...")
    probs = pipeline.predict_proba(X_test)
    preds = pipeline.predict(X_test)

    # Numerical labels for ECE mapped directly from pipeline.classes_
    class_to_idx = {c: i for i, c in enumerate(pipeline.classes_)}
    y_test_idx = np.array([class_to_idx[c] for c in y_test])

    # Compute ECE and Brier Score
    ece, mce, bin_details = compute_ece(probs, y_test_idx)
    brier = compute_brier_score(probs, y_test_idx, len(pipeline.classes_))

    report_dict = classification_report(y_test, preds, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, preds, labels=CLASSES)

    accuracy = float(np.mean(np.array(preds) == np.array(y_test)))
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, preds, average="macro", zero_division=0)

    logger.info("=" * 60)
    logger.info("EVALUATION BENCHMARK RESULTS ON HELD-OUT TEST SPLIT:")
    logger.info("=" * 60)
    logger.info("Accuracy:             %.4f (%.2f%%)", accuracy, accuracy * 100)
    logger.info("Macro Precision:      %.4f", precision)
    logger.info("Macro Recall:         %.4f", recall)
    logger.info("Macro F1-Score:       %.4f", f1)
    logger.info("Expected Calib Error: %.4f (ECE)", ece)
    logger.info("Max Calib Error:      %.4f (MCE)", mce)
    logger.info("Brier Score:          %.4f", brier)
    logger.info("=" * 60)

    # Save trained calibrated model
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)
    logger.info("Saved calibrated classifier to %s", MODEL_OUTPUT_PATH)

    # Compile report
    evaluation_report = {
        "model_architecture": "TF-IDF (12k features, 1-2 ngrams) + CalibratedClassifierCV(LogisticRegression, sigmoid)",
        "training_dataset_size": len(X_train),
        "test_dataset_size": len(X_test),
        "metrics": {
            "accuracy": round(accuracy, 4),
            "macro_precision": round(float(precision), 4),
            "macro_recall": round(float(recall), 4),
            "macro_f1": round(float(f1), 4),
            "expected_calibration_error_ece": ece,
            "max_calibration_error_mce": mce,
            "brier_score": brier,
        },
        "per_class_metrics": {
            cls: report_dict.get(cls, {}) for cls in CLASSES if cls in report_dict
        },
        "confusion_matrix": {
            "classes": CLASSES,
            "matrix": cm.tolist(),
        },
        "calibration_bins": bin_details,
    }

    with open(REPORT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2)
    logger.info("Evaluation report saved to %s", REPORT_OUTPUT_PATH)


if __name__ == "__main__":
    main()
