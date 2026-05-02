import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_DIR = BASE_DIR / "data" / "raw" / "trade"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FORM_URL = "https://app3.pertanian.go.id/eksim/eksporProvAsal.php"

OUTPUT_HTML_PATH = OUTPUT_DIR / "test_export_selenium_2020.html"
OUTPUT_RAW_TABLE_PATH = OUTPUT_DIR / "test_export_selenium_2020_manual_tables.csv"
OUTPUT_DEBUG_PATH = OUTPUT_DIR / "test_export_debug.txt"


def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")

    # Kalau nanti sudah stabil dan mau tanpa buka browser, aktifkan ini:
    # options.add_argument("--headless=new")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    return driver


def clean_text(value: str) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .replace("\xa0", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
        .strip()
    )


def extract_table_manually(table_tag, table_index: int) -> pd.DataFrame:
    """
    Ekstrak tabel HTML lama secara manual.
    Tidak memakai pandas.read_html karena struktur tabel Kementan/BPS kadang tidak rapi.
    """
    rows = []

    trs = table_tag.find_all("tr")

    for row_index, tr in enumerate(trs):
        cells = tr.find_all(["th", "td"])

        row_values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]

        # buang row yang benar-benar kosong
        if not any(row_values):
            continue

        rows.append(row_values)

    if not rows:
        return pd.DataFrame()

    max_cols = max(len(row) for row in rows)

    normalized_rows = []

    for row in rows:
        padded_row = row + [""] * (max_cols - len(row))
        normalized_rows.append(padded_row)

    columns = [f"col_{i + 1}" for i in range(max_cols)]

    df = pd.DataFrame(normalized_rows, columns=columns)
    df.insert(0, "table_index", table_index)

    return df


def main():
    driver = setup_driver()

    try:
        print("Membuka halaman form...")
        driver.get(FORM_URL)

        wait = WebDriverWait(driver, 40)
        wait.until(EC.presence_of_element_located((By.ID, "prop")))

        print("Form berhasil dimuat.")

        # Tahun 2020
        Select(driver.find_element(By.ID, "prop")).select_by_value("2020")

        # 1 = Tanaman Pangan
        Select(driver.find_element(By.NAME, "subsektor")).select_by_value("1")

        time.sleep(2)

        klasifik_select = Select(driver.find_element(By.NAME, "klasifik"))

        print("Daftar pilihan klasifik:")
        for option in klasifik_select.options:
            print("value:", option.get_attribute("value"), "| text:", option.text)

        # 0 = Segar,olahan
        klasifik_select.select_by_value("0")

        print("Klik tombol Tampilkan...")

        submit_button = driver.find_element(By.XPATH, "//input[@type='submit']")
        submit_button.click()

        # Tunggu halaman hasil muncul
        time.sleep(10)

        html = driver.page_source
        OUTPUT_HTML_PATH.write_text(html, encoding="utf-8")

        print("HTML hasil tersimpan:")
        print(OUTPUT_HTML_PATH)

        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        print(f"Jumlah tag <table> ditemukan: {len(tables)}")

        if not tables:
            OUTPUT_DEBUG_PATH.write_text(
                "Tidak ada tag <table> ditemukan di halaman hasil.",
                encoding="utf-8",
            )
            print("Tidak ada tag <table> ditemukan.")
            return

        all_tables = []

        for table_index, table_tag in enumerate(tables):
            df = extract_table_manually(table_tag, table_index)

            if df.empty:
                print(f"Tabel {table_index} kosong, dilewati.")
                continue

            # Simpan hanya tabel yang kemungkinan punya data ekspor
            table_text = " ".join(df.astype(str).fillna("").values.flatten()).upper()

            is_relevant = any(
                keyword in table_text
                for keyword in [
                    "BERAS",
                    "JAGUNG",
                    "KACANG",
                    "PROVINSI",
                    "VOLUME",
                    "NILAI",
                    "TOTAL",
                ]
            )

            if is_relevant:
                print(f"\n=== TABEL RELEVAN {table_index} ===")
                print(df.head(10))
                all_tables.append(df)
            else:
                print(f"Tabel {table_index} tidak relevan, dilewati.")

        if not all_tables:
            OUTPUT_DEBUG_PATH.write_text(
                "Tag <table> ditemukan, tapi tidak ada tabel yang mengandung keyword data ekspor.",
                encoding="utf-8",
            )
            print("Tidak ada tabel relevan yang berhasil diekstrak.")
            return

        final_df = pd.concat(all_tables, ignore_index=True)
        final_df.to_csv(OUTPUT_RAW_TABLE_PATH, index=False, encoding="utf-8-sig")

        print("\nCSV manual hasil test tersimpan:")
        print(OUTPUT_RAW_TABLE_PATH)
        print(f"Total rows: {len(final_df)}")
        print(f"Total columns: {len(final_df.columns)}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()