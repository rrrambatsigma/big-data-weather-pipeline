from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = BASE_DIR / "data" / "raw" / "weather_plan_b" / "by_province"
METADATA_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_coordinates_final.csv"

EXPECTED_HOURLY_ROWS_PER_LOCATION = 43848


def main():
    metadata = pd.read_csv(METADATA_PATH)
    expected_provinces = set(metadata["province"].dropna().unique())

    files = sorted(RAW_DIR.glob("weather_plan_b_*_2020_2024.csv"))

    if not files:
        raise FileNotFoundError(f"Tidak ada file weather final di {RAW_DIR}")

    print(f"Total file weather final ditemukan: {len(files)}")

    found_provinces = set()

    for file_path in files:
        print(f"Validating: {file_path.name}")

        df = pd.read_csv(file_path)

        if df.empty:
            raise ValueError(f"File kosong: {file_path}")

        required_columns = [
            "province",
            "city_regency",
            "time",
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "et0_fao_evapotranspiration",
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(
                f"File {file_path.name} tidak punya kolom wajib: {missing_columns}"
            )

        province = df["province"].dropna().iloc[0]
        found_provinces.add(province)

        city_count = df["city_regency"].nunique()
        expected_rows = city_count * EXPECTED_HOURLY_ROWS_PER_LOCATION
        actual_rows = len(df)

        if actual_rows < expected_rows:
            raise ValueError(
                f"File belum lengkap: {file_path.name}. "
                f"Actual rows={actual_rows}, expected={expected_rows}"
            )

    missing_provinces = sorted(expected_provinces - found_provinces)

    print("\nProvinsi ditemukan:", len(found_provinces))
    print("Provinsi belum tersedia:", len(missing_provinces))

    if missing_provinces:
        print("\nWARNING: Masih ada provinsi yang belum tersedia:")
        for province in missing_provinces:
            print("-", province)

    print("\nValidasi raw weather available selesai.")


if __name__ == "__main__":
    main()