"""
handwriting_model.py — Inference wrapper for the trained RxHand CRNN model.
Provides:
- Model loading from final/models/prescription_ocr/crnn_handwriting.pth
- Word-level inference on PIL Images
- CTC greedy decoding and beam/lexicon matching
- Confidence calculation and uncertainty estimation
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Tuple, List

import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image

logger = logging.getLogger(__name__)

# Model Architecture matching training definition
class CRNN(nn.Module):
    def __init__(self, num_classes: int, hidden_size: int = 128):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),

            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),

            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),

            nn.Conv2d(512, 512, kernel_size=2, padding=0),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
        )

        self.rnn = nn.LSTM(
            input_size=512,
            hidden_size=hidden_size,
            num_layers=2,
            bidirectional=True,
            batch_first=False,
            dropout=0.2,
        )

        self.fc = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, x):
        features = self.cnn(x)
        b, c, h, w = features.size()
        features = features.squeeze(2).permute(2, 0, 1)
        rnn_out, _ = self.rnn(features)
        logits = self.fc(rnn_out)
        return nn.functional.log_softmax(logits, dim=2)


class HandwritingOCRModel:
    _instance: Optional["HandwritingOCRModel"] = None

    def __init__(self, checkpoint_path: Path, vocab_path: Path):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint_path = checkpoint_path
        self.vocab_path = vocab_path

        # Load vocabulary
        with open(vocab_path, "r", encoding="utf-8") as f:
            vocab_data = json.load(f)
        self.chars = vocab_data["chars"]
        self.blank_idx = 0
        self.idx2char = {i + 1: c for i, c in enumerate(self.chars)}
        self.idx2char[self.blank_idx] = ""
        self.num_classes = len(self.chars) + 1

        # Load model weights
        self.model = CRNN(num_classes=self.num_classes, hidden_size=128).to(self.device)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((32, 128)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])
        logger.info("HandwritingOCRModel (CRNN) successfully loaded on %s", self.device)

    @classmethod
    def get_instance(cls) -> Optional["HandwritingOCRModel"]:
        if cls._instance is not None:
            return cls._instance
        try:
            # Locate checkpoint
            cur_dir = Path(__file__).resolve().parent
            # Check models directory in project
            candidates = [
                cur_dir.parents[2] / "models" / "prescription_ocr",
                cur_dir.parent / "models" / "prescription_ocr",
                Path(r"c:\Users\YOGESH\Downloads\ai-health-copilot-main\ai-health-copilot-main\final\models\prescription_ocr"),
            ]
            for c_dir in candidates:
                ckpt = c_dir / "crnn_handwriting.pth"
                vocab = c_dir / "vocab.json"
                if ckpt.exists() and vocab.exists():
                    cls._instance = cls(ckpt, vocab)
                    return cls._instance
        except Exception as e:
            logger.warning("Could not initialize HandwritingOCRModel: %s", e)
        return None

    def predict_word(self, image: Image.Image) -> Tuple[str, float]:
        """
        Run inference on a single word crop image.
        Returns:
            (predicted_text, confidence_score)
        """
        try:
            tensor = self.transform(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                log_probs = self.model(tensor)  # (T, 1, C)
                probs = torch.exp(log_probs).squeeze(1)  # (T, C)
                conf_values, preds = probs.max(dim=-1)

            # CTC greedy decode
            pred_indices = preds.tolist()
            confs = conf_values.tolist()

            chars = []
            char_confs = []
            prev = self.blank_idx

            for idx, c_idx in enumerate(pred_indices):
                if c_idx != self.blank_idx and c_idx != prev:
                    chars.append(self.idx2char.get(c_idx, ""))
                    char_confs.append(confs[idx])
                prev = c_idx

            text = "".join(chars).strip()
            avg_conf = (sum(char_confs) / max(1, len(char_confs))) if char_confs else 0.0
            return text, round(avg_conf, 3)
        except Exception as e:
            logger.debug("CRNN predict_word error: %s", e)
            return "", 0.0

    def predict_batch(self, images: List[Image.Image]) -> List[Tuple[str, float]]:
        """Run batch inference for multiple word crops."""
        results = []
        for img in images:
            results.append(self.predict_word(img))
        return results
