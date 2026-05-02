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

HTML_OUTPUT_DIR = OUTPUT_DIR / "html_export_2020_2024"
HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FORM_URL = "https://app3.pertanian.go.id/eksim/eksporProvAsal.php"

OUTPUT_RAW_TABLE_PATH = OUTPUT_DIR / "export_province_raw_2020_2024_manual_tables.csv"
OUTPUT_DEBUG_PATH = OUTPUT_DIR / "export_province_scraping_debug_2020_2024.txt"

YEARS = ["2020", "2021", "2022", "2023", "2024"]

# Dari hasil test kamu:
# subsektor value 1 = Tanaman Pangan
SUBSECTOR_VALUE = "1"

# Dari hasil test kamu:
# klasifik value 0 = Segar,olahan
CLASSIFICATION_VALUE = "0"


def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")

    # Kalau nanti sudah stabil dan mau browser tidak tampil, aktifkan ini:
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


def extract_table_manually(table_tag, table_index: int, year: str) -> pd.DataFrame:
    """
    Ekstrak tabel HTML lama secara manual.
    Tidak memakai pandas.read_html karena struktur tabel Kementan/BPS tidak selalu rapi.
    """
    rows = []

    trs = table_tag.find_all("tr")

    for row_index, tr in enumerate(trs):
        cells = tr.find_all(["th", "td"])
        row_values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]

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
    df.insert(0, "year", year)
    df.insert(1, "table_index", table_index)

    return df


def is_relevant_table(df: pd.DataFrame) -> bool:
    """
    Filter awal agar tabel menu/layout yang tidak penting tidak ikut disimpan.
    """
    table_text = " ".join(df.astype(str).fillna("").values.flatten()).upper()

    keywords = [
        "BERAS",
        "JAGUNG",
        "KACANG",
        "PROVINSI",
        "PROPINSI",
        "VOLUME",
        "NILAI",
        "TOTAL",
        "JANUARI",
        "FEBRUARI",
        "MARET",
        "APRIL",
        "MEI",
        "JUNI",
        "JULI",
        "AGUSTUS",
        "SEPTEMBER",
        "OKTOBER",
        "NOVEMBER",
        "DESEMBER",
    ]

    return any(keyword in table_text for keyword in keywords)


def scrape_one_year(driver, year: str) -> list[pd.DataFrame]:
    print(f"\n==============================")
    print(f"Mengambil data ekspor tahun {year}")
    print(f"==============================")

    driver.get(FORM_URL)

    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.ID, "prop")))

    print("Form berhasil dimuat.")

    Select(driver.find_element(By.ID, "prop")).select_by_value(year)

    Select(driver.find_element(By.NAME, "subsektor")).select_by_value(SUBSECTOR_VALUE)

    time.sleep(2)

    klasifik_select = Select(driver.find_element(By.NAME, "klasifik"))

    print("Pilihan klasifik tersedia:")
    for option in klasifik_select.options:
        print("value:", option.get_attribute("value"), "| text:", option.text)

    klasifik_select.select_by_value(CLASSIFICATION_VALUE)

    print("Klasifik dipilih: Segar,olahan")
    print("Klik tombol Tampilkan...")

    submit_button = driver.find_element(By.XPATH, "//input[@type='submit']")
    submit_button.click()

    time.sleep(10)

    html = driver.page_source

    html_path = HTML_OUTPUT_DIR / f"export_province_{year}.html"
    html_path.write_text(html, encoding="utf-8")

    print(f"HTML tahun {year} disimpan di:")
    print(html_path)

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    print(f"Jumlah tag <table> ditemukan tahun {year}: {len(tables)}")

    year_tables = []

    for table_index, table_tag in enumerate(tables):
        df = extract_table_manually(table_tag, table_index, year)

        if df.empty:
            continue

        if is_relevant_table(df):
            print(f"Tabel relevan ditemukan | tahun {year} | table_index {table_index}")
            print(df.head(5))
            year_tables.append(df)
        else:
            print(f"Tabel tidak relevan dilewati | tahun {year} | table_index {table_index}")

    return year_tables


def main():
    driver = setup_driver()

    all_tables = []
    debug_messages = []

    try:
        for year in YEARS:
            try:
                year_tables = scrape_one_year(driver, year)

                if not year_tables:
                    message = f"Tahun {year}: tidak ada tabel relevan yang berhasil diekstrak."
                    print(message)
                    debug_messages.append(message)
                    continue

                all_tables.extend(year_tables)

                print(f"Tahun {year}: total tabel relevan = {len(year_tables)}")

                time.sleep(3)

            except Exception as error:
                message = f"Tahun {year}: gagal scraping. Error: {error}"
                print(message)
                debug_messages.append(message)

        if not all_tables:
            OUTPUT_DEBUG_PATH.write_text(
                "\n".join(debug_messages) if debug_messages else "Tidak ada data berhasil diekstrak.",
                encoding="utf-8",
            )
            raise RuntimeError("Tidak ada tabel yang berhasil diekstrak untuk semua tahun.")

        final_df = pd.concat(all_tables, ignore_index=True)

        final_df.to_csv(
            OUTPUT_RAW_TABLE_PATH,
            index=False,
            encoding="utf-8-sig",
        )

        print("\nScraping ekspor 2020–2024 selesai.")
        print(f"Output raw CSV disimpan di:")
        print(OUTPUT_RAW_TABLE_PATH)
        print(f"Total rows: {len(final_df)}")
        print(f"Total columns: {len(final_df.columns)}")

        if debug_messages:
            OUTPUT_DEBUG_PATH.write_text("\n".join(debug_messages), encoding="utf-8")
            print(f"\nCatatan debug disimpan di:")
            print(OUTPUT_DEBUG_PATH)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()