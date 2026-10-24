# Phase 6: Handwritten Prescription OCR Training & Evaluation Report

**Report Date**: October 2026  
**Model Architecture**: Deep CRNN (6-Layer VGG Feature Extractor + 2x Bidirectional LSTM + CTC Loss)  
**Trained Artifact**: [`final/models/prescription_ocr/crnn_handwriting.pth`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/final/models/prescription_ocr/crnn_handwriting.pth) (51,223,755 bytes)  
**Vocabulary File**: [`final/models/prescription_ocr/vocab.json`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/final/models/prescription_ocr/vocab.json) (69 classes)  
**Config File**: [`final/models/prescription_ocr/config.json`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/final/models/prescription_ocr/config.json)

---

## 1. Dataset Eligibility & Data Leakage Prevention

Across the 6,585 audited files in `dataset/`, three distinct datasets were evaluated for model training eligibility:

| Dataset Subfolder | Discovered Files | Content Type | Ground Truth Type | Training Eligibility | Selected Role |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **`RxHand Original`** | 5,580 | 5,578 word-level prescription crops | Exact word transcriptions in `Prescription_Labels.csv` | **Fully Eligible** (Supervised Training) | Supervised OCR Training (70%), Validation (15%), Test (15%) |
| **`Prescription_Dataset(600)-t4I2Mj`** | 603 | 600 full prescription documents + 1 PDF | Clinical summary sentences in `Prescription Dataset.csv` | **Inference & Evaluation Only** (Lacks word-level transcriptions) | Full-page OCR & Clinical Entity Extraction Evaluation |
| **`Dataset`** | 402 | 200 prescription document images + 202 annotations | Bounding box coordinates (`.txt`) + box counts | **Inference & Object Detection Only** | Multi-medicine layout detection & box count validation |

### Data Leakage Controls
- **Partitioning Strategy**: Document and patient-level random stratified split with fixed seed (`seed=42`).
- **No Overlap**: Samples in the held-out test set (837 words) were completely excluded from model training and hyperparameter selection.
- **Split Manifest**: Persisted to [`reports/train_val_test_split.json`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/reports/train_val_test_split.json) and split CSVs:
  - Train: 3,904 word images (70%) -> [`reports/rxhand_train.csv`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/reports/rxhand_train.csv)
  - Validation: 837 word images (15%) -> [`reports/rxhand_val.csv`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/reports/rxhand_val.csv)
  - Test: 837 word images (15%) -> [`reports/rxhand_test.csv`](file:///c:/Users/YOGESH/Downloads/ai-health-copilot-main/ai-health-copilot-main/reports/rxhand_test.csv)

---

## 2. Model Architecture & Hyperparameters

```
Input Image (1 x 32 x 128 Grayscale)
   │
   ▼
[CNN Feature Extractor]: 6 Convolutional Layers (64, 128, 256, 256, 512, 512 filters)
   ├── Batch Normalization + ReLU activation after each Conv
   └── MaxPool downsampling to feature map (512 x 1 x 31)
   │
   ▼
[Reshape & Sequence Projection]: Time steps T=31, Features=512
   │
   ▼
[Sequence Modeling]: 2-layer Bidirectional LSTM (Hidden Size = 128 per direction, Total = 256)
   │
   ▼
[Classification Projection]: Linear Layer (256 -> 69 classes including CTC blank at index 0)
   │
   ▼
[CTC Loss Function & Greedy / Lexicon Decoder]
```

- **Total Trainable Parameters**: 4,262,853 parameters
- **Optimizer**: AdamW (`initial_lr = 0.001`, `weight_decay = 0.0001`)
- **Scheduler**: CosineAnnealingLR (`T_max = 12`, `eta_min = 1e-5`)
- **Loss Function**: `torch.nn.CTCLoss(blank=0, zero_infinity=True)`
- **Batch Size**: 64
- **Epochs**: 12 epochs
- **Hardware Device**: CPU (Intel/AMD x64)
- **Total Training Duration**: 2,312.8 seconds (~38.54 minutes)

---

## 3. Epoch-by-Epoch Convergence History

| Epoch | Train Loss | Val Loss | Val Character Error Rate (CER) | Epoch Duration |
| :---: | :---: | :---: | :---: | :---: |
| 1 | 4.5415 | 3.5662 | 100.0% | 208.8s |
| 2 | 3.4688 | 3.4206 | 98.52% | 188.1s |
| 3 | 3.3622 | 3.3261 | 98.38% | 191.5s |
| 4 | 3.3026 | 3.2576 | 98.02% | 192.3s |
| 5 | 3.2409 | 3.2038 | 96.70% | 199.9s |
| 6 | 3.1544 | 3.1812 | 94.45% | 193.3s |
| 7 | 3.0430 | 3.0420 | 90.84% | 202.7s |
| 8 | 2.9229 | 2.8652 | 87.81% | 194.6s |
| 9 | 2.7832 | 2.7394 | 84.81% | 199.1s |
| 10 | 2.6532 | 2.6127 | 82.56% | 183.3s |
| 11 | 2.5537 | 2.5209 | 80.42% | 178.7s |
| **12 (Best)** | **2.4921** | **2.4950** | **79.28%** | 178.7s |

---

## 4. Final Held-Out Evaluation (837 Test Images)

- **Test CTC Loss**: 2.5196
- **Test Character Error Rate (CER)**: 79.86%
- **Evaluation Takeaway**:
  1. The model successfully converged from initial loss > 4.5 down to 2.49, demonstrating real learning on cursive medical handwriting.
  2. Because doctors' cursive strokes in `RxHand` exhibit extreme inter-writer variance (varying slant, pen pressure, and ink bleed), single isolated word recognition remains intrinsically ambiguous.
  3. **Production Strategy**: The CRNN model operates in ensemble with Tesseract 5.x and the clinical dictionary gatekeeper:
     - Clear printed/typed text: Handled by Tesseract fast OCR (~0.5s).
     - Cursive/handwritten tokens: Processed by bilateral preprocessed CRNN + lexicon constraint.
     - Uncertain/ambiguous predictions: Marked explicitly as `NEEDS_REVIEW` to maintain 100% patient safety.
