import os

files = [
    "data/raw/produksi_padi_2020_2024.csv",
    "data/raw/produksi_jagung_2020_2024.csv",
    "data/raw/produksi_kedelai_2020_2024.csv",
    "data/raw/produksi_kacanghijau_2020_2024.csv",
    "data/raw/produksi_kacangtanah_2020_2024.csv",
]

for file in files:
    if not os.path.exists(file):
        raise FileNotFoundError(f"File tidak ditemukan: {file}")

print("[OK] Semua file raw tersedia")