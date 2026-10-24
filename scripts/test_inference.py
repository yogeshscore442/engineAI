import sys
sys.path.insert(0, r"c:\Users\YOGESH\Downloads\ai-health-copilot-main\ai-health-copilot-main\final\yogesh\healthcare_copilot_AI-Engine-main")
from ai_engine.handwriting_model import HandwritingOCRModel
from PIL import Image
from pathlib import Path

hw = HandwritingOCRModel.get_instance()
print("HandwritingOCRModel loaded:", hw is not None)
if hw:
    img_p = Path(r"dataset/RxHand Original/RxHand-Handwritten Prescription Word Image Dataset/P0001.jpg")
    if img_p.exists():
        im = Image.open(img_p)
        text, conf = hw.predict_word(im)
        print(f"Prediction for P0001.jpg: text='{text}', conf={conf}")
