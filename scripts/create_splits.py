"""
create_splits.py — Partition RxHand dataset into Train, Val, and Test splits.
Guarantees:
- Fixed deterministic random seed (seed=42)
- Separate evaluation set (test) withheld from training and tuning
- Stratified sampling across word frequency tiers
- Saved manifest at reports/train_val_test_split.json
"""
import json
import random
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

def create_splits(seed: int = 42):
    workspace_root = Path(__file__).resolve().parent.parent
    rx_csv = workspace_root / "dataset" / "RxHand Original" / "Prescription_Labels.csv"
    reports_dir = workspace_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(rx_csv)[['Images', 'Text']].dropna()
    df['Text'] = df['Text'].astype(str).str.strip()
    df['clean_word'] = df['Text'].str.lower()

    # Stratify by frequency tier to ensure balanced word complexity across splits
    counts = df['clean_word'].value_counts()
    def get_tier(w):
        c = counts.get(w, 1)
        if c >= 50: return "high_freq"
        if c >= 10: return "med_freq"
        if c >= 3: return "low_freq"
        return "singleton"
    df['freq_tier'] = df['clean_word'].apply(get_tier)

    # 70% Train, 15% Val, 15% Test
    train_df, temp_df = train_test_split(
        df, test_size=0.30, random_state=seed, stratify=df['freq_tier']
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, random_state=seed, stratify=temp_df['freq_tier']
    )

    print(f"Total samples: {len(df)}")
    print(f"Train samples: {len(train_df)} ({len(train_df)/len(df)*100:.1f}%)")
    print(f"Val samples:   {len(val_df)} ({len(val_df)/len(df)*100:.1f}%)")
    print(f"Test samples:  {len(test_df)} ({len(test_df)/len(df)*100:.1f}%)")

    # Build split manifest
    manifest = {
        "random_seed": seed,
        "split_ratio": {"train": 0.70, "val": 0.15, "test": 0.15},
        "total_samples": len(df),
        "train_count": len(train_df),
        "val_count": len(val_df),
        "test_count": len(test_df),
        "train_images": sorted(train_df['Images'].tolist()),
        "val_images": sorted(val_df['Images'].tolist()),
        "test_images": sorted(test_df['Images'].tolist()),
    }

    out_file = reports_dir / "train_val_test_split.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved split manifest to: {out_file}")

    # Also save CSV versions for easy dataset loading
    train_df[['Images', 'Text']].to_csv(reports_dir / "rxhand_train.csv", index=False)
    val_df[['Images', 'Text']].to_csv(reports_dir / "rxhand_val.csv", index=False)
    test_df[['Images', 'Text']].to_csv(reports_dir / "rxhand_test.csv", index=False)
    print("Saved rxhand_train.csv, rxhand_val.csv, rxhand_test.csv")

if __name__ == "__main__":
    create_splits(42)
