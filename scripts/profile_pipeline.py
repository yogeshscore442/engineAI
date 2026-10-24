import time
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(r"c:\Users\YOGESH\Downloads\ai-health-copilot-main\ai-health-copilot-main")
AI_ENGINE_ROOT = WORKSPACE_ROOT / "final" / "yogesh" / "healthcare_copilot_AI-Engine-main"
sys.path.insert(0, str(AI_ENGINE_ROOT))

def log(msg):
    print(f"[{time.strftime('%X')}] {msg}", flush=True)

log("Starting profile...")

t0 = time.time()
from ai_engine.ocr import load_document, _load_image, _run_ocr_pipeline, _DOCTR_OK, _TESSERACT_OK
log(f"Imports done in {time.time() - t0:.2f}s. docTR_OK={_DOCTR_OK}, Tesseract_OK={_TESSERACT_OK}")

test_img = WORKSPACE_ROOT / "dataset" / "Dataset" / "Dataset" / "images" / "11.jpg"
log(f"Test image: {test_img} (exists={test_img.exists()})")

# Test 1: Image loading
t1 = time.time()
from PIL import Image
im = Image.open(test_img)
log(f"Image open done in {time.time() - t1:.2f}s, size={im.size}")

# Test 2: OCR pipeline
t2 = time.time()
log("Running load_document...")
doc = load_document(str(test_img), "image/jpeg")
log(f"load_document done in {time.time() - t2:.2f}s. Engine={doc.get('ocr_engine')}, chars={len(doc.get('fallback_text', ''))}, tokens={len(doc.get('tokens', []))}")

# Test 3: Validation
t3 = time.time()
from ai_engine.validator import validate_medical_document
val = validate_medical_document(str(test_img), doc.get("pages", []), doc.get("fallback_text", ""), "image/jpeg")
log(f"Validation done in {time.time() - t3:.2f}s. Decision={val.decision}, type={val.document_type}")

# Test 4: Extraction
t4 = time.time()
from ai_engine.extract import extract_from_file
rec = extract_from_file(str(test_img), "image/jpeg")
log(f"extract_from_file done in {time.time() - t4:.2f}s. Status={rec.get('status')}, doc_type={rec.get('doc_type')}, meds={len(rec.get('medicines', []))}")

# Test 5: Summaries
t5 = time.time()
from ai_engine.summarize import build_summaries
sums = build_summaries(rec)
log(f"build_summaries done in {time.time() - t5:.2f}s.")

# Test 6: Full extract_record
t6 = time.time()
from ai_engine import extract_record
final_rec = extract_record(str(test_img), "image/jpeg")
log(f"Full extract_record done in {time.time() - t6:.2f}s.")
log(f"TOTAL TIME: {time.time() - t0:.2f}s")
