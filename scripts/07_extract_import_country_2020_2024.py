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

HTML_OUTPUT_DIR = OUTPUT_DIR / "html_import_2020_2024"
HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FORM_URL = "https://app3.pertanian.go.id/eksim/impornegaraasal.php"

OUTPUT_RAW_TABLE_PATH = OUTPUT_DIR / "import_country_raw_2020_2024_manual_tables.csv"
OUTPUT_DEBUG_PATH = OUTPUT_DIR / "import_country_scraping_debug_2020_2024.txt"

YEARS = ["2020", "2021", "2022", "2023", "2024"]

# Berdasarkan pola website:
# subsektor value 1 = Tanaman Pangan
SUBSECTOR_VALUE = "1"

# Berdasarkan hasil ekspor kamu:
# klasifik value 0 = Segar,olahan
CLASSIFICATION_VALUE = "0"


def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")

    # Kalau sudah stabil dan mau tanpa buka browser:
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
    rows = []

    trs = table_tag.find_all("tr")

    for tr in trs:
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
        normalized_rows.append(row + [""] * (max_cols - len(row)))

    columns = [f"col_{i + 1}" for i in range(max_cols)]

    df = pd.DataFrame(normalized_rows, columns=columns)
    df.insert(0, "year", year)
    df.insert(1, "table_index", table_index)

    return df


def is_relevant_table(df: pd.DataFrame) -> bool:
    table_text = " ".join(df.astype(str).fillna("").values.flatten()).upper()

    keywords = [
        "BERAS",
        "JAGUNG",
        "KACANG",
        "NEGARA",
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


def select_value_if_available(select_obj: Select, value: str, label: str) -> None:
    available_values = [option.get_attribute("value") for option in select_obj.options]

    print(f"Pilihan tersedia untuk {label}:")
    for option in select_obj.options:
        print("value:", option.get_attribute("value"), "| text:", option.text)

    if value not in available_values:
        raise ValueError(
            f"Value {value} tidak ditemukan untuk {label}. "
            f"Pilihan tersedia: {available_values}"
        )

    select_obj.select_by_value(value)


def scrape_one_year(driver, year: str) -> list[pd.DataFrame]:
    print("\n==============================")
    print(f"Mengambil data impor tahun {year}")
    print("==============================")

    driver.get(FORM_URL)

    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.ID, "prop")))

    print("Form impor berhasil dimuat.")

    Select(driver.find_element(By.ID, "prop")).select_by_value(year)

    subsektor_select = Select(driver.find_element(By.NAME, "subsektor"))
    select_value_if_available(subsektor_select, SUBSECTOR_VALUE, "subsektor")

    time.sleep(2)

    klasifik_select = Select(driver.find_element(By.NAME, "klasifik"))
    select_value_if_available(klasifik_select, CLASSIFICATION_VALUE, "klasifik")

    print("Klasifik dipilih: Segar,olahan")
    print("Klik tombol Tampilkan...")

    submit_button = driver.find_element(By.XPATH, "//input[@type='submit']")
    submit_button.click()

    time.sleep(10)

    html = driver.page_source

    html_path = HTML_OUTPUT_DIR / f"import_country_{year}.html"
    html_path.write_text(html, encoding="utf-8")

    print(f"HTML impor tahun {year} disimpan di:")
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

        print("\nScraping impor 2020–2024 selesai.")
        print("Output raw CSV disimpan di:")
        print(OUTPUT_RAW_TABLE_PATH)
        print(f"Total rows: {len(final_df)}")
        print(f"Total columns: {len(final_df.columns)}")

        if debug_messages:
            OUTPUT_DEBUG_PATH.write_text("\n".join(debug_messages), encoding="utf-8")
            print("\nCatatan debug disimpan di:")
            print(OUTPUT_DEBUG_PATH)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()