import pandas as pd

files = [
    ("data/raw/produksi_padi_2020_2024.csv", "Padi"),
    ("data/raw/produksi_jagung_2020_2024.csv", "Jagung"),
    ("data/raw/produksi_kedelai_2020_2024.csv", "Kedelai"),
    ("data/raw/produksi_kacanghijau_2020_2024.csv", "Kacang Hijau"),
    ("data/raw/produksi_kacangtanah_2020_2024.csv", "Kacang Tanah"),
]

all_data = []

for file, komoditas in files:
    print(f"Processing {file}...")

    df = pd.read_csv(file)
    df.columns = df.columns.str.strip()

    drop_cols = [col for col in df.columns if "No" in col or "Pertumbuhan" in col]
    df = df.drop(columns=drop_cols, errors="ignore")

    df["Provinsi"] = df["Provinsi"].astype(str).str.strip().str.upper()
    df = df[df["Provinsi"] != "INDONESIA"]

    df_long = df.melt(
        id_vars=["Provinsi"],
        var_name="Tahun",
        value_name="Produksi"
    )

    df_long = df_long[df_long["Tahun"].astype(str).str.match(r"20\d{2}")]
    df_long["Produksi"] = pd.to_numeric(df_long["Produksi"], errors="coerce")
    df_long = df_long.dropna(subset=["Produksi"])
    df_long["Komoditas"] = komoditas

    all_data.append(df_long)

df_final = pd.concat(all_data, ignore_index=True)
df_final = df_final.sort_values(["Provinsi", "Komoditas", "Tahun"])

df_final.to_csv(
    "data/processed/produksi_komoditas_clean_long.csv",
    index=False,
    encoding="utf-8-sig"
)

df_sum = df_final.groupby(
    ["Provinsi", "Komoditas"],
    as_index=False
)["Produksi"].sum()

df_sum = df_sum.sort_values(["Provinsi", "Komoditas"])

df_sum.to_csv(
    "data/processed/produksi_komoditas_total_2020_2024.csv",
    index=False,
    encoding="utf-8-sig"
)

print("[OK] Transform selesai")