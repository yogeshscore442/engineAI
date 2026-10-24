"""
train_handwriting_ocr.py — Train CRNN + CTC Model on RxHand Handwritten Prescription Word Dataset.
Includes:
- Data Augmentation (affine rotation, shear, contrast)
- ResNet/VGG-style CNN feature extractor + BiLSTM temporal sequence encoder
- CTC Loss (Connectionist Temporal Classification)
- Greedy CTC Decoder + CER/WER validation tracker
- Best checkpoint saving and training metrics logging
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import pandas as pd

# ── Vocabulary & Label Encoder ────────────────────────────────────────────────
class LabelEncoder:
    def __init__(self, chars: List[str]):
        self.blank_idx = 0
        self.chars = sorted(list(set(chars)))
        self.char2idx = {c: i + 1 for i, c in enumerate(self.chars)}
        self.idx2char = {i + 1: c for i, c in enumerate(self.chars)}
        self.idx2char[self.blank_idx] = ""

    def encode(self, text: str) -> List[int]:
        return [self.char2idx[c] for c in text if c in self.char2idx]

    def decode(self, indices: List[int]) -> str:
        # CTC collapse: remove consecutive repeats and blanks
        result = []
        prev = self.blank_idx
        for idx in indices:
            if idx != self.blank_idx and idx != prev:
                result.append(self.idx2char.get(idx, ""))
            prev = idx
        return "".join(result)

    def num_classes(self) -> int:
        return len(self.chars) + 1  # +1 for blank


# ── Dataset Definition ────────────────────────────────────────────────────────
class RxHandDataset(Dataset):
    def __init__(self, df: pd.DataFrame, img_dir: Path, encoder: LabelEncoder, is_training: bool = True):
        self.df = df.reset_index(drop=True)
        self.img_dir = img_dir
        self.encoder = encoder
        self.is_training = is_training

        # Preprocessing: convert to grayscale, resize to standard height 32, width 128
        self.base_transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((32, 128)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])

        # Mild augmentation for handwriting robustness
        self.train_augment = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.RandomRotation(degrees=4, fill=255),
            transforms.ColorJitter(brightness=0.15, contrast=0.15),
            transforms.Resize((32, 128)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = self.img_dir / str(row['Images'])
        text = str(row['Text']).strip()

        try:
            with Image.open(img_path) as im:
                img = im.convert("RGB")
        except Exception:
            # Fallback blank image on read failure
            img = Image.new("RGB", (128, 128), (255, 255, 255))

        if self.is_training:
            tensor = self.train_augment(img)
        else:
            tensor = self.base_transform(img)

        encoded = self.encoder.encode(text)
        return tensor, torch.tensor(encoded, dtype=torch.long), text


def collate_fn(batch):
    images, targets, texts = zip(*batch)
    images = torch.stack(images, dim=0)

    target_lengths = torch.tensor([len(t) for t in targets], dtype=torch.long)
    max_len = max(1, target_lengths.max().item())
    padded_targets = torch.zeros((len(targets), max_len), dtype=torch.long)
    for i, t in enumerate(targets):
        if len(t) > 0:
            padded_targets[i, :len(t)] = t

    return images, padded_targets, target_lengths, texts


# ── CRNN Model Architecture ───────────────────────────────────────────────────
class CRNN(nn.Module):
    """
    CRNN architecture for handwritten prescription text recognition:
    CNN: extracts 2D feature maps from (1, 32, 128) image
    BiLSTM: 2-layer bidirectional LSTM models sequence transitions
    Linear: projects to vocabulary size
    """
    def __init__(self, num_classes: int, hidden_size: int = 128):
        super().__init__()
        # CNN: (1, 32, 128) -> (512, 1, 32) -> (T=32, B, 512)
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # (64, 16, 64)

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # (128, 8, 32)

            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),

            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),  # (256, 4, 32)

            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),  # (512, 2, 32)

            nn.Conv2d(512, 512, kernel_size=2, padding=0),  # (512, 1, 31)
            nn.BatchNorm2d(512),
            nn.ReLU(True),
        )

        # RNN: 2-layer BiLSTM
        self.rnn = nn.LSTM(
            input_size=512,
            hidden_size=hidden_size,
            num_layers=2,
            bidirectional=True,
            batch_first=False,
            dropout=0.2,
        )

        # Classifier
        self.fc = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, x):
        # x: (B, 1, 32, 128)
        features = self.cnn(x)  # (B, 512, 1, W_seq)
        b, c, h, w = features.size()
        features = features.squeeze(2)  # (B, 512, W_seq)
        features = features.permute(2, 0, 1)  # (W_seq, B, 512)

        rnn_out, _ = self.rnn(features)  # (W_seq, B, hidden*2)
        logits = self.fc(rnn_out)  # (W_seq, B, num_classes)
        log_probs = nn.functional.log_softmax(logits, dim=2)
        return log_probs


# ── Levenshtein Distance & Error Metrics ───────────────────────────────────────
def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def evaluate_model(model, dataloader, encoder, device) -> Tuple[float, float, float]:
    """Compute (mean_loss, CER, WER, ExactMatchRate)."""
    model.eval()
    criterion = nn.CTCLoss(blank=encoder.blank_idx, zero_infinity=True)

    total_loss = 0.0
    total_chars = 0
    total_char_errs = 0
    total_words = 0
    total_word_errs = 0
    exact_matches = 0

    with torch.no_grad():
        for images, targets, target_lengths, texts in dataloader:
            images = images.to(device)
            targets = targets.to(device)
            target_lengths = target_lengths.to(device)

            log_probs = model(images)  # (T, B, C)
            T, B, _ = log_probs.size()
            input_lengths = torch.full((B,), T, dtype=torch.long, device=device)

            loss = criterion(log_probs, targets, input_lengths, target_lengths)
            total_loss += loss.item() * B

            # Greedy CTC decode
            preds = log_probs.argmax(dim=2)  # (T, B)
            for b in range(B):
                pred_indices = preds[:, b].tolist()
                pred_text = encoder.decode(pred_indices).strip()
                gt_text = texts[b].strip()

                char_dist = levenshtein_distance(gt_text, pred_text)
                total_char_errs += char_dist
                total_chars += max(1, len(gt_text))

                total_words += 1
                if pred_text.lower() == gt_text.lower():
                    exact_matches += 1
                else:
                    total_word_errs += 1

    mean_loss = total_loss / max(1, total_words)
    cer = total_char_errs / max(1, total_chars)
    wer = total_word_errs / max(1, total_words)
    exact_match = exact_matches / max(1, total_words)
    return mean_loss, cer, wer, exact_match


# ── Training Script Main ──────────────────────────────────────────────────────
def train_crnn(epochs: int = 15, batch_size: int = 64, lr: float = 1e-3):
    workspace_root = Path(__file__).resolve().parent.parent
    reports_dir = workspace_root / "reports"
    models_dir = workspace_root / "final" / "models" / "prescription_ocr"
    models_dir.mkdir(parents=True, exist_ok=True)
    img_dir = workspace_root / "dataset" / "RxHand Original" / "RxHand-Handwritten Prescription Word Image Dataset"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device for training: {device}")

    # Load splits
    train_df = pd.read_csv(reports_dir / "rxhand_train.csv")
    val_df = pd.read_csv(reports_dir / "rxhand_val.csv")
    test_df = pd.read_csv(reports_dir / "rxhand_test.csv")

    # Build vocabulary from training set
    all_train_text = "".join(train_df['Text'].astype(str).tolist())
    vocab_chars = sorted(list(set(all_train_text)))
    encoder = LabelEncoder(vocab_chars)

    # Save vocab
    vocab_file = models_dir / "vocab.json"
    with open(vocab_file, "w", encoding="utf-8") as f:
        json.dump({"chars": encoder.chars, "num_classes": encoder.num_classes()}, f, indent=2)
    print(f"Vocabulary saved with {encoder.num_classes()} classes (including CTC blank).")

    # Datasets and Loaders
    train_dataset = RxHandDataset(train_df, img_dir, encoder, is_training=True)
    val_dataset = RxHandDataset(val_df, img_dir, encoder, is_training=False)
    test_dataset = RxHandDataset(test_df, img_dir, encoder, is_training=False)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_fn, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn, num_workers=0)

    # Initialize CRNN
    model = CRNN(num_classes=encoder.num_classes(), hidden_size=128).to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Initialized CRNN with {total_params:,} trainable parameters.")

    criterion = nn.CTCLoss(blank=encoder.blank_idx, zero_infinity=True)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    best_val_cer = 1.0
    checkpoint_path = models_dir / "crnn_handwriting.pth"
    history = []

    print(f"\n--- Starting Training for {epochs} Epochs ---")
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        t0 = time.time()

        for images, targets, target_lengths, texts in train_loader:
            images = images.to(device)
            targets = targets.to(device)
            target_lengths = target_lengths.to(device)

            optimizer.zero_grad()
            log_probs = model(images)  # (T, B, C)
            T, B, _ = log_probs.size()
            input_lengths = torch.full((B,), T, dtype=torch.long, device=device)

            loss = criterion(log_probs, targets, input_lengths, target_lengths)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()

            train_loss += loss.item() * B

        scheduler.step()
        epoch_train_loss = train_loss / len(train_dataset)

        # Validation
        val_loss, val_cer, val_wer, val_acc = evaluate_model(model, val_loader, encoder, device)
        epoch_time = time.time() - t0

        print(f"Epoch {epoch:02d}/{epochs:02d} [{epoch_time:.1f}s] - Train Loss: {epoch_train_loss:.4f} | Val Loss: {val_loss:.4f} | Val CER: {val_cer*100:.2f}% | Val ExactMatch: {val_acc*100:.2f}%")

        history.append({
            "epoch": epoch,
            "train_loss": round(epoch_train_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_cer": round(val_cer, 4),
            "val_wer": round(val_wer, 4),
            "val_exact_match": round(val_acc, 4),
            "duration_sec": round(epoch_time, 2),
        })

        if val_cer < best_val_cer:
            best_val_cer = val_cer
            torch.save({
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "epoch": epoch,
                "best_val_cer": best_val_cer,
                "vocab": encoder.chars,
                "num_classes": encoder.num_classes(),
                "hidden_size": 128,
            }, checkpoint_path)
            print(f"  --> Saved new best checkpoint to {checkpoint_path} (Val CER: {val_cer*100:.2f}%)")

    total_duration = time.time() - start_time
    print(f"\nTraining completed in {total_duration/60:.2f} minutes.")

    # Load best checkpoint for final held-out test evaluation
    print(f"Loading best checkpoint for final evaluation on withheld test set (837 samples)...")
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])

    test_loss, test_cer, test_wer, test_acc = evaluate_model(model, test_loader, encoder, device)
    print(f"\n=======================================================")
    print(f"  HELD-OUT TEST EVALUATION RESULTS (837 samples)")
    print(f"=======================================================")
    print(f"  Test Loss:        {test_loss:.4f}")
    print(f"  Character Error Rate (CER): {test_cer*100:.2f}%")
    print(f"  Word Error Rate (WER):      {test_wer*100:.2f}%")
    print(f"  Exact Word Match Rate:      {test_acc*100:.2f}%")
    print(f"=======================================================\n")

    # Save training configuration and final test metrics
    config = {
        "model_architecture": "CRNN_2xBiLSTM_CTC",
        "cnn_backbone": "Custom_6_Layer_VGG_BatchNorm",
        "hidden_size": 128,
        "bidirectional": True,
        "input_dimensions": [1, 32, 128],
        "vocabulary_size": encoder.num_classes(),
        "total_trainable_parameters": total_params,
        "optimizer": "AdamW",
        "initial_learning_rate": lr,
        "weight_decay": 1e-4,
        "scheduler": "CosineAnnealingLR",
        "epochs": epochs,
        "batch_size": batch_size,
        "total_training_duration_seconds": round(total_duration, 2),
        "device": str(device),
        "dataset_split": {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
        "final_held_out_metrics": {
            "test_loss": round(test_loss, 4),
            "test_cer_percent": round(test_cer * 100, 2),
            "test_wer_percent": round(test_wer * 100, 2),
            "exact_match_percent": round(test_acc * 100, 2),
        },
        "checkpoint_file": str(checkpoint_path),
        "vocab_file": str(vocab_file),
    }

    with open(models_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    with open(reports_dir / "training_metrics.json", "w", encoding="utf-8") as f:
        json.dump({"config": config, "epoch_history": history}, f, indent=2)

    print("Saved models/prescription_ocr/config.json and reports/training_metrics.json")


if __name__ == "__main__":
    train_crnn(epochs=12, batch_size=64, lr=1e-3)
