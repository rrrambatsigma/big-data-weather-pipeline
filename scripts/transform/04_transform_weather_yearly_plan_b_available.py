from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_DIR = BASE_DIR / "data" / "raw" / "weather_plan_b" / "by_province"

OUTPUT_DIR = BASE_DIR / "data" / "staging" / "weather_plan_b"
OUTPUT_CITY_PATH = OUTPUT_DIR / "weather_yearly_city_plan_b_available_2020_2024.csv"
OUTPUT_PROVINCE_PATH = OUTPUT_DIR / "weather_yearly_province_plan_b_available_2020_2024.csv"
OUTPUT_SUMMARY_PATH = OUTPUT_DIR / "weather_plan_b_available_transform_summary.csv"

START_YEAR = 2020
END_YEAR = 2024
EXPECTED_YEARS = list(range(START_YEAR, END_YEAR + 1))
EXPECTED_HOURLY_ROWS_PER_LOCATION = 43848

MAIN_WEATHER_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "et0_fao_evapotranspiration",
]

SOIL_MOISTURE_VARIABLES = [
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
]

NUMERIC_COLUMNS = MAIN_WEATHER_VARIABLES + SOIL_MOISTURE_VARIABLES

REQUIRED_COLUMNS = [
    "province",
    "city_regency",
    "time",
    "latitude",
    "longitude",
    "timezone",
    *NUMERIC_COLUMNS,
]

# DKI Jakarta boleh punya missing soil moisture karena wilayah urban/pesisir/kepulauan.
# Data weather utama tetap dipakai, tetapi nanti saat modeling bisa diputuskan:
# dipakai dengan imputasi, atau DKI dikeluarkan.
SOIL_OPTIONAL_PROVINCES = ["DKI Jakarta", "Sulawesi Utara"]


def get_weather_files() -> list[Path]:
    files = sorted(INPUT_DIR.glob("weather_plan_b_*_2020_2024.csv"))

    valid_files = []

    for file_path in files:
        name = file_path.name

        # Abaikan file temporary atau backup incomplete.
        if ".tmp." in name:
            continue

        if ".incomplete_" in name:
            continue

        valid_files.append(file_path)

    return valid_files


def validate_columns(df: pd.DataFrame, file_path: Path) -> None:
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"File {file_path.name} tidak punya kolom wajib: {missing_columns}"
        )


def clean_weather_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df["year"] = df["time"].dt.year

    df = df[df["year"].isin(EXPECTED_YEARS)]

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def validate_missing_by_province(df: pd.DataFrame, province: str) -> None:
    missing = df[NUMERIC_COLUMNS].isna().sum()
    missing = missing[missing > 0]

    if missing.empty:
        return

    print(f"\nWARNING missing value ditemukan di provinsi {province}:")
    print(missing.to_string())

    only_soil_missing = all(col in SOIL_MOISTURE_VARIABLES for col in missing.index)

    if province in SOIL_OPTIONAL_PROVINCES and only_soil_missing:
        print(
            f"INFO: Missing hanya soil moisture dan diizinkan untuk {province}. "
            "Transform tetap lanjut."
        )
        return

    print(
        "INFO: Transform tetap lanjut karena ini output available, "
        "tetapi cek kembali data sebelum modeling final."
    )


def aggregate_file_to_city_year(file_path: Path) -> tuple[pd.DataFrame, dict]:
    print("\nMembaca file:")
    print(file_path)

    df = pd.read_csv(file_path)
    validate_columns(df, file_path)

    raw_rows = len(df)

    df = clean_weather_df(df)

    if df.empty:
        raise ValueError(f"File {file_path.name} kosong setelah filter tahun.")

    province_values = df["province"].dropna().unique()

    if len(province_values) == 0:
        province_name = file_path.stem
    else:
        province_name = province_values[0]

    validate_missing_by_province(df, province_name)

    city_count = df["city_regency"].nunique()
    expected_min_rows = city_count * EXPECTED_HOURLY_ROWS_PER_LOCATION

    is_complete = raw_rows >= expected_min_rows

    if not is_complete:
        print(
            f"WARNING: File {file_path.name} kemungkinan belum lengkap. "
            f"Rows: {raw_rows}, expected minimal: {expected_min_rows}"
        )

    city_year_df = (
        df.groupby(
            [
                "year",
                "province",
                "city_regency",
                "latitude",
                "longitude",
                "timezone",
            ],
            as_index=False,
        )
        .agg(
            avg_temperature=("temperature_2m", "mean"),
            avg_humidity=("relative_humidity_2m", "mean"),
            total_precipitation=("precipitation", "sum"),
            total_rainfall=("rain", "sum"),
            total_et0=("et0_fao_evapotranspiration", "sum"),
            avg_soil_moisture_0_to_7cm=("soil_moisture_0_to_7cm", "mean"),
            avg_soil_moisture_7_to_28cm=("soil_moisture_7_to_28cm", "mean"),
            avg_soil_moisture_28_to_100cm=("soil_moisture_28_to_100cm", "mean"),
            hourly_records=("time", "count"),
        )
    )

    city_year_df["avg_soil_moisture"] = city_year_df[
        [
            "avg_soil_moisture_0_to_7cm",
            "avg_soil_moisture_7_to_28cm",
            "avg_soil_moisture_28_to_100cm",
        ]
    ].mean(axis=1)

    summary = {
        "file_name": file_path.name,
        "province": province_name,
        "raw_rows": raw_rows,
        "city_count": city_count,
        "expected_min_rows": expected_min_rows,
        "is_complete_by_rows": is_complete,
        "city_year_rows": len(city_year_df),
    }

    return city_year_df, summary


def aggregate_city_to_province_year(city_year_df: pd.DataFrame) -> pd.DataFrame:
    province_year_df = (
        city_year_df.groupby(["year", "province"], as_index=False)
        .agg(
            avg_temperature=("avg_temperature", "mean"),
            avg_humidity=("avg_humidity", "mean"),
            total_precipitation=("total_precipitation", "mean"),
            total_rainfall=("total_rainfall", "mean"),
            total_et0=("total_et0", "mean"),
            avg_soil_moisture_0_to_7cm=("avg_soil_moisture_0_to_7cm", "mean"),
            avg_soil_moisture_7_to_28cm=("avg_soil_moisture_7_to_28cm", "mean"),
            avg_soil_moisture_28_to_100cm=("avg_soil_moisture_28_to_100cm", "mean"),
            avg_soil_moisture=("avg_soil_moisture", "mean"),
            city_count=("city_regency", "nunique"),
            total_hourly_records=("hourly_records", "sum"),
        )
    )

    province_year_df = province_year_df.sort_values(
        ["year", "province"]
    ).reset_index(drop=True)

    return province_year_df


def validate_outputs(city_year_df: pd.DataFrame, province_year_df: pd.DataFrame) -> None:
    print("\n================ VALIDASI OUTPUT ================")

    print(f"Total city-year rows: {len(city_year_df)}")
    print(f"Total province-year rows: {len(province_year_df)}")

    province_count = province_year_df["province"].nunique()
    print(f"Total provinsi yang sudah available: {province_count}")

    print("\nProvinsi yang sudah masuk transform:")
    print(
        province_year_df.groupby("province")["year"]
        .nunique()
        .reset_index(name="year_count")
        .to_string(index=False)
    )

    print("\nJumlah city per province-year:")
    print(
        city_year_df.groupby(["year", "province"])["city_regency"]
        .nunique()
        .reset_index(name="city_count")
        .to_string(index=False)
    )

    missing_city = city_year_df.isna().sum()
    missing_city = missing_city[missing_city > 0]

    if not missing_city.empty:
        print("\nWARNING missing value di city-year:")
        print(missing_city.to_string())

    missing_province = province_year_df.isna().sum()
    missing_province = missing_province[missing_province > 0]

    if not missing_province.empty:
        print("\nWARNING missing value di province-year:")
        print(missing_province.to_string())
    else:
        print("\nTidak ada missing value di province-year.")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = get_weather_files()

    if not files:
        raise FileNotFoundError(f"Tidak ada file weather final di folder: {INPUT_DIR}")

    print("Total file provinsi final yang ditemukan:", len(files))

    city_year_parts = []
    summaries = []

    for file_path in files:
        city_year_df, summary = aggregate_file_to_city_year(file_path)
        city_year_parts.append(city_year_df)
        summaries.append(summary)

    final_city_year_df = pd.concat(city_year_parts, ignore_index=True)

    final_city_year_df = final_city_year_df.sort_values(
        ["year", "province", "city_regency"]
    ).reset_index(drop=True)

    final_province_year_df = aggregate_city_to_province_year(final_city_year_df)

    validate_outputs(final_city_year_df, final_province_year_df)

    final_city_year_df.to_csv(OUTPUT_CITY_PATH, index=False)
    final_province_year_df.to_csv(OUTPUT_PROVINCE_PATH, index=False)
    pd.DataFrame(summaries).to_csv(OUTPUT_SUMMARY_PATH, index=False)

    print("\nOutput transform available berhasil disimpan:")
    print(OUTPUT_CITY_PATH)
    print(OUTPUT_PROVINCE_PATH)
    print(OUTPUT_SUMMARY_PATH)


if __name__ == "__main__":
    main()