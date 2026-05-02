import pandas as pd

file_2020 = "produksi_padi_2020.csv"
file_2021_2024 = "produksi_padi_2021_2024.csv"

df2020 = pd.read_csv(file_2020, sep=";")
df_lanjut = pd.read_csv(file_2021_2024, sep=",")

df2020.columns = df2020.columns.str.strip()
df_lanjut.columns = df_lanjut.columns.str.strip()

df2020 = df2020.rename(columns={
    "Produksi (ton)": "2020",
    "Produksi_(ton)": "2020"
})

df2020 = df2020[["Provinsi", "2020"]]
df_lanjut = df_lanjut[["Provinsi", "2021", "2022", "2023", "2024"]]

# Samakan format nama provinsi
df2020["Provinsi"] = df2020["Provinsi"].str.strip().str.upper()
df_lanjut["Provinsi"] = df_lanjut["Provinsi"].str.strip().str.upper()

# Samakan nama provinsi yang beda versi
mapping = {
    "DI YOGYAKARTA": "DAERAH ISTIMEWA YOGYAKARTA",
    "DKI JAKARTA": "DAERAH KHUSUS IBUKOTA JAKARTA",
    "KEP. BANGKA BELITUNG": "KEPULAUAN BANGKA BELITUNG",
    "KEP. RIAU": "KEPULAUAN RIAU"
}

df2020["Provinsi"] = df2020["Provinsi"].replace(mapping)
df_lanjut["Provinsi"] = df_lanjut["Provinsi"].replace(mapping)

# Gabungkan data
df_final = pd.merge(df2020, df_lanjut, on="Provinsi", how="outer")

# Urutkan
df_final = df_final.sort_values("Provinsi").reset_index(drop=True)

# Simpan
df_final.to_csv("produksi_padi_2020_2024.csv", index=False, encoding="utf-8-sig")

print(df_final)
print("\n[OK] File berhasil dibuat: produksi_padi_2020_2024.csv")