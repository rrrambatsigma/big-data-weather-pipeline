import os
import pandas as pd

os.makedirs("data/staging", exist_ok=True)

df = pd.read_csv("data/processed/produksi_komoditas_total_2020_2024.csv")
df.to_csv("data/staging/produksi_staging.csv", index=False, encoding="utf-8-sig")

print("[OK] Data berhasil masuk staging")