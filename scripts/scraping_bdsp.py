from selenium import webdriver
from selenium.webdriver.common.by import By
from io import StringIO
import pandas as pd
import time
import re

URL = "https://bdsp2.pertanian.go.id/bdsp/id/home.html"

output_file = input("Nama file output: ").strip()
if not output_file:
    output_file = "hasil_scraping.csv"

driver = webdriver.Chrome()

try:
    driver.get(URL)

    print("Atur filter dulu di browser:")
    print("- Subsektor")
    print("- Komoditas")
    print("- Indikator")
    print("- Tahun Awal / Tahun Akhir")
    print("- Klik Cari")
    input("\nKalau tabel sudah muncul, tekan Enter di terminal...")

    time.sleep(2)

    table_element = driver.find_element(By.ID, "isitabel")
    table_html = table_element.get_attribute("outerHTML")

    df = pd.read_html(StringIO(table_html))[0]

    # rapikan nama kolom
    raw_cols = [str(c).strip() for c in df.columns]
    df.columns = raw_cols

    print("\nKolom asli:")
    print(df.columns.tolist())

    # buat nama kolom lebih aman
    cleaned_cols = []
    for col in df.columns:
        c = str(col).strip()
        c = re.sub(r"\s+", "_", c)
        c = c.replace("(", "").replace(")", "")
        c = c.replace("%", "pct")
        c = c.replace("/", "_")
        c = c.replace("-", "_")
        cleaned_cols.append(c)

    df.columns = cleaned_cols

    print("\nKolom setelah dirapikan:")
    print(df.columns.tolist())

    # hapus baris kosong
    df = df.dropna(how="all")

    # cari kolom angka tahunan otomatis
    year_cols = [col for col in df.columns if re.fullmatch(r"20\d{2}", str(col))]
    print("\nKolom tahun:", year_cols)

    # cari kolom pertumbuhan kalau ada
    growth_cols = [col for col in df.columns if "Pertumbuhan" in col or "pertumbuhan" in col]
    print("Kolom pertumbuhan:", growth_cols)

    # bersihkan kolom tahun
    for col in year_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.extract(r"(-?\d+\.?\d*)")[0]
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # bersihkan kolom pertumbuhan kalau ada
    for col in growth_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.replace("\u2212", "-", regex=False)
            .str.extract(r"(-?\d+\.?\d*)")[0]
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    print("\nPreview data bersih:")
    print(df.head(10))

    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n[OK] File berhasil disimpan: {output_file}")

finally:
    driver.quit()