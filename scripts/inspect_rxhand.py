import pandas as pd
from pathlib import Path
from PIL import Image

rx_csv = Path('dataset/RxHand Original/Prescription_Labels.csv')
df = pd.read_csv(rx_csv)
print('CSV columns:', df.columns.tolist())
df = df[['Images', 'Text']].dropna()
print('Valid pairs:', len(df))
print('Sample entries:')
for idx, row in df.sample(8, random_state=42).iterrows():
    print(f"  {row['Images']} -> '{row['Text']}'")

texts = df['Text'].astype(str).tolist()
chars = sorted(list(set(''.join(texts))))
print(f'Total unique characters ({len(chars)}):', repr(''.join(chars)))
lengths = [len(t) for t in texts]
print(f'Min len: {min(lengths)}, Max len: {max(lengths)}, Mean len: {sum(lengths)/len(lengths):.1f}')

img_dir = Path('dataset/RxHand Original/RxHand-Handwritten Prescription Word Image Dataset')
sizes = []
for idx, r in df.head(100).iterrows():
    p = img_dir / r['Images']
    if p.exists():
        with Image.open(p) as im:
            sizes.append(im.size)
ws = [s[0] for s in sizes]
hs = [s[1] for s in sizes]
print(f'Sample widths: min={min(ws)}, max={max(ws)}, mean={sum(ws)/len(ws):.1f}')
print(f'Sample heights: min={min(hs)}, max={max(hs)}, mean={sum(hs)/len(hs):.1f}')
