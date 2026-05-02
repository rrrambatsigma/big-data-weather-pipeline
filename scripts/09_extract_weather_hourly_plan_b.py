import re
import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parents[1]

LOCATION_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_coordinates_final.csv"

OUTPUT_DIR = BASE_DIR / "data" / "raw" / "weather_plan_b"
OUTPUT_BY_PROVINCE_DIR = OUTPUT_DIR / "by_province"

FAILED_PATH = OUTPUT_DIR / "weather_plan_b_failed_locations.csv"
LOG_PATH = OUTPUT_DIR / "weather_plan_b_extraction_log.csv"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2020-01-01"
END_DATE = "2024-12-31"

# 2020-01-01 s/d 2024-12-31 hourly = 43.848 rows per lokasi
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

ALL_WEATHER_COLUMNS = MAIN_WEATHER_VARIABLES + SOIL_MOISTURE_VARIABLES

SOIL_MODEL_NAME = "era5_land"

# Jeda dipercepat, tapi masih cukup aman agar tidak terlalu sering kena 429
REQUEST_SLEEP_SECONDS = 10       # jeda antara request weather utama dan soil moisture
LOCATION_SLEEP_SECONDS = 15      # jeda antar kab/kot dalam provinsi
PROVINCE_SLEEP_SECONDS = 60      # jeda antar provinsi kalau ada request baru/gagal

MAX_RETRIES = 12

# DKI Jakarta sering tidak punya soil moisture karena urban/pesisir/kepulauan.
# Data weather utama tetap valid, jadi soil moisture boleh kosong khusus provinsi ini.
SOIL_OPTIONAL_PROVINCES = ["DKI Jakarta", "Sulawesi Utara"]

REQUIRED_LOCATION_COLUMNS = [
    "province",
    "city_regency",
    "geocoding_query",
    "latitude",
    "longitude",
    "timezone",
    "country_code",
]


def slugify(value: str) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value


def get_timezone(row: pd.Series) -> str:
    timezone = row.get("timezone", "auto")

    if pd.isna(timezone) or str(timezone).strip() == "":
        return "auto"

    return str(timezone).strip()


def validate_location_file(locations: pd.DataFrame) -> None:
    missing_columns = [
        col for col in REQUIRED_LOCATION_COLUMNS
        if col not in locations.columns
    ]

    if missing_columns:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing_columns}")

    if locations.empty:
        raise ValueError("File plan_b_location_coordinates_final.csv kosong.")

    non_id = locations[locations["country_code"] != "ID"]

    if not non_id.empty:
        raise ValueError(
            "Masih ada lokasi dengan country_code bukan ID. "
            "Jangan lanjut extract weather sebelum dibersihkan."
        )

    missing_latlon = locations[
        locations["latitude"].isna() | locations["longitude"].isna()
    ]

    if not missing_latlon.empty:
        raise ValueError(
            "Masih ada lokasi dengan latitude/longitude kosong. "
            "Jangan lanjut extract weather sebelum dibersihkan."
        )

    duplicated = locations[
        locations.duplicated(subset=["province", "city_regency"], keep=False)
    ]

    if not duplicated.empty:
        print("\nWARNING: Ada duplikasi province-city_regency:")
        print(duplicated[["province", "city_regency"]].to_string(index=False))

    print("\nJumlah lokasi per provinsi:")
    print(locations.groupby("province")["city_regency"].nunique().to_string())

    print(f"\nTotal lokasi Plan B: {len(locations)}")


def request_open_meteo(params: dict, max_retries: int = MAX_RETRIES) -> dict:
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                ARCHIVE_URL,
                params=params,
                timeout=240,
            )

            if response.status_code == 429:
                wait_time = min(120 * attempt, 1200)

                print(
                    f"  Kena 429 Too Many Requests. "
                    f"Tunggu {wait_time} detik sebelum retry..."
                )

                time.sleep(wait_time)
                continue

            if response.status_code in [500, 502, 503, 504]:
                wait_time = min(60 * attempt, 600)

                print(
                    f"  Server error {response.status_code}. "
                    f"Tunggu {wait_time} detik sebelum retry..."
                )

                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as error:
            last_error = error
            wait_time = min(60 * attempt, 600)

            print(f"  Retry {attempt}/{max_retries} gagal: {error}")
            print(f"  Menunggu {wait_time} detik sebelum mencoba lagi...")

            time.sleep(wait_time)

    raise RuntimeError(
        f"Gagal request ke Open-Meteo setelah {max_retries} percobaan. "
        f"Error terakhir: {last_error}"
    )


def validate_response(data: dict, data_type: str, location_name: str) -> None:
    if "hourly" not in data:
        raise ValueError(
            f"Response {data_type} tidak memiliki key 'hourly' "
            f"untuk {location_name}: {data}"
        )


def fetch_hourly_data(
    row: pd.Series,
    variables: list[str],
    data_type: str,
    model_name: str | None = None,
) -> pd.DataFrame:
    location_name = f"{row['province']} - {row['city_regency']}"

    params = {
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": ",".join(variables),
        "timezone": get_timezone(row),
    }

    if model_name:
        params["models"] = model_name

    data = request_open_meteo(params=params, max_retries=MAX_RETRIES)
    validate_response(data, data_type=data_type, location_name=location_name)

    hourly_df = pd.DataFrame(data["hourly"])

    if "time" not in hourly_df.columns:
        raise ValueError(f"Kolom time tidak ditemukan pada {data_type}: {location_name}")

    return hourly_df


def add_location_columns(weather_df: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    weather_df.insert(0, "province", row["province"])
    weather_df.insert(1, "city_regency", row["city_regency"])
    weather_df.insert(2, "geocoding_query", row["geocoding_query"])
    weather_df.insert(3, "latitude", row["latitude"])
    weather_df.insert(4, "longitude", row["longitude"])
    weather_df.insert(5, "timezone", get_timezone(row))
    weather_df.insert(6, "source", "Open-Meteo Historical Weather API")
    weather_df.insert(7, "extraction_plan", "plan_b_top_kabkot_indonesia")

    return weather_df


def fetch_weather_for_location(row: pd.Series) -> pd.DataFrame:
    location_name = f"{row['province']} - {row['city_regency']}"

    print(f"  Mengambil weather utama: {location_name}")

    main_df = fetch_hourly_data(
        row=row,
        variables=MAIN_WEATHER_VARIABLES,
        data_type="main weather",
        model_name=None,
    )

    time.sleep(REQUEST_SLEEP_SECONDS)

    print(f"  Mengambil soil moisture ERA5-Land: {location_name}")

    soil_df = fetch_hourly_data(
        row=row,
        variables=SOIL_MOISTURE_VARIABLES,
        data_type="soil moisture",
        model_name=SOIL_MODEL_NAME,
    )

    merged_df = pd.merge(
        main_df,
        soil_df,
        on="time",
        how="left",
    )

    merged_df = add_location_columns(merged_df, row)

    return merged_df


def check_missing_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    total_rows = len(df)

    print(f"\nCek missing value {label}:")
    for col in columns:
        if col in df.columns:
            missing_count = df[col].isna().sum()
            print(f"{col}: {missing_count} missing dari {total_rows} rows")
        else:
            print(f"{col}: kolom tidak ditemukan")


def is_missing_allowed_for_province(province: str, missing_weather: pd.Series) -> bool:
    if missing_weather.empty:
        return True

    if province not in SOIL_OPTIONAL_PROVINCES:
        return False

    only_soil_missing = all(
        col in SOIL_MOISTURE_VARIABLES
        for col in missing_weather.index
    )

    return only_soil_missing


def is_existing_output_valid(
    output_path: Path,
    expected_location_count: int,
    province: str,
) -> bool:
    if not output_path.exists():
        return False

    try:
        df = pd.read_csv(output_path)

        expected_min_rows = expected_location_count * EXPECTED_HOURLY_ROWS_PER_LOCATION

        if len(df) < expected_min_rows:
            print(f"\nExisting file tidak lengkap: {output_path}")
            print(f"Rows sekarang: {len(df)}")
            print(f"Expected minimal rows: {expected_min_rows}")
            return False

        required_columns = [
            "province",
            "city_regency",
            "time",
            *ALL_WEATHER_COLUMNS,
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"\nExisting file kolomnya tidak lengkap: {output_path}")
            print(f"Missing columns: {missing_columns}")
            return False

        missing_weather = df[ALL_WEATHER_COLUMNS].isna().sum()
        missing_weather = missing_weather[missing_weather > 0]

        if not missing_weather.empty:
            if is_missing_allowed_for_province(province, missing_weather):
                print(f"\nExisting file punya missing soil moisture, tapi diizinkan untuk {province}:")
                print(missing_weather.to_string())
                return True

            print("\nExisting file punya missing value di variabel utama/soil:")
            print(missing_weather.to_string())
            return False

        return True

    except Exception as error:
        print(f"\nGagal membaca existing output {output_path}: {error}")
        return False


def backup_incomplete_output(output_path: Path) -> None:
    if not output_path.exists():
        return

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = output_path.with_suffix(f".incomplete_{timestamp}.csv")

    output_path.rename(backup_path)

    print("\nFile lama tidak valid, dipindahkan menjadi backup:")
    print(backup_path)


def append_log(log_rows: list[dict]) -> None:
    if not log_rows:
        return

    log_df = pd.DataFrame(log_rows)

    if LOG_PATH.exists():
        existing_log = pd.read_csv(LOG_PATH)
        final_log = pd.concat([existing_log, log_df], ignore_index=True)
    else:
        final_log = log_df

    final_log.to_csv(LOG_PATH, index=False)


def save_failed_locations(failed_rows: list[dict]) -> None:
    if not failed_rows:
        return

    failed_df = pd.DataFrame(failed_rows)

    if FAILED_PATH.exists():
        existing_failed = pd.read_csv(FAILED_PATH)
        final_failed = pd.concat([existing_failed, failed_df], ignore_index=True)
        final_failed = final_failed.drop_duplicates(
            subset=["province", "city_regency", "latitude", "longitude"],
            keep="last",
        )
    else:
        final_failed = failed_df

    final_failed.to_csv(FAILED_PATH, index=False)


def remove_resolved_failed_locations(success_keys: set[tuple[str, str]]) -> None:
    if not FAILED_PATH.exists():
        return

    failed_df = pd.read_csv(FAILED_PATH)

    if failed_df.empty:
        return

    failed_df["_key"] = list(zip(failed_df["province"], failed_df["city_regency"]))

    failed_df = failed_df[~failed_df["_key"].isin(success_keys)].drop(columns=["_key"])

    if failed_df.empty:
        FAILED_PATH.unlink()
    else:
        failed_df.to_csv(FAILED_PATH, index=False)


def extract_one_province(
    province: str,
    province_locations: pd.DataFrame,
) -> tuple[str, list[dict], list[dict]]:
    province_slug = slugify(province)
    output_path = OUTPUT_BY_PROVINCE_DIR / f"weather_plan_b_{province_slug}_2020_2024.csv"
    temp_output_path = OUTPUT_BY_PROVINCE_DIR / f"weather_plan_b_{province_slug}_2020_2024.tmp.csv"

    expected_location_count = province_locations["city_regency"].nunique()

    if is_existing_output_valid(output_path, expected_location_count, province):
        print(f"\nSKIP: {province} sudah punya output valid:")
        print(output_path)
        return "skipped", [], []

    if output_path.exists():
        backup_incomplete_output(output_path)

    if temp_output_path.exists():
        print("\nMenghapus temp file lama:")
        print(temp_output_path)
        temp_output_path.unlink()

    print("\n==================================================")
    print(f"Extract province: {province}")
    print(f"Total lokasi: {len(province_locations)}")
    print("==================================================")

    province_weather = []
    failed_rows = []
    log_rows = []
    success_keys = set()

    for _, row in tqdm(
        province_locations.iterrows(),
        total=len(province_locations),
        desc=f"Extract {province}",
    ):
        location_name = f"{row['province']} - {row['city_regency']}"

        try:
            print(f"\nProcessing: {location_name}")

            weather_df = fetch_weather_for_location(row)
            province_weather.append(weather_df)

            success_keys.add((row["province"], row["city_regency"]))

            log_rows.append({
                "province": row["province"],
                "city_regency": row["city_regency"],
                "status": "success",
                "rows": len(weather_df),
                "reason": "",
            })

            print(f"OK: {location_name} | rows: {len(weather_df)}")

            time.sleep(LOCATION_SLEEP_SECONDS)

        except Exception as error:
            failed_rows.append({
                "province": row["province"],
                "city_regency": row["city_regency"],
                "geocoding_query": row.get("geocoding_query"),
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "timezone": get_timezone(row),
                "reason": str(error),
            })

            log_rows.append({
                "province": row["province"],
                "city_regency": row["city_regency"],
                "status": "failed",
                "rows": 0,
                "reason": str(error),
            })

            print(f"FAILED: {location_name} | {error}")

            time.sleep(LOCATION_SLEEP_SECONDS)

    if not province_weather:
        print(f"\nWARNING: Tidak ada data berhasil untuk provinsi {province}")
        return "failed", failed_rows, log_rows

    province_df = pd.concat(province_weather, ignore_index=True)

    province_df.to_csv(temp_output_path, index=False)

    expected_min_rows = expected_location_count * EXPECTED_HOURLY_ROWS_PER_LOCATION

    if len(province_df) < expected_min_rows:
        print("\nWARNING: Output provinsi belum lengkap.")
        print(f"Rows actual: {len(province_df)}")
        print(f"Rows expected minimal: {expected_min_rows}")
        print(f"Temp output disimpan di: {temp_output_path}")
        return "failed", failed_rows, log_rows

    missing_weather = province_df[ALL_WEATHER_COLUMNS].isna().sum()
    missing_weather = missing_weather[missing_weather > 0]

    if not missing_weather.empty:
        print("\nWARNING: Output provinsi punya missing value.")
        print(missing_weather.to_string())

        if is_missing_allowed_for_province(province, missing_weather):
            print(
                f"\nINFO: Missing value hanya soil moisture dan diizinkan untuk {province}. "
                "File tetap disimpan sebagai output final."
            )
        else:
            print(f"Temp output disimpan di: {temp_output_path}")
            return "failed", failed_rows, log_rows

    temp_output_path.replace(output_path)

    remove_resolved_failed_locations(success_keys)

    print(f"\nOutput provinsi valid disimpan:")
    print(output_path)
    print(f"Total rows provinsi: {len(province_df)}")

    check_missing_columns(
        province_df,
        MAIN_WEATHER_VARIABLES,
        label=f"weather utama - {province}",
    )

    check_missing_columns(
        province_df,
        SOIL_MOISTURE_VARIABLES,
        label=f"soil moisture - {province}",
    )

    return "extracted", failed_rows, log_rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_BY_PROVINCE_DIR.mkdir(parents=True, exist_ok=True)

    print("Membaca file koordinat final Plan B:")
    print(LOCATION_PATH)

    locations = pd.read_csv(LOCATION_PATH)
    validate_location_file(locations)

    locations = locations.sort_values(["province", "city_regency"]).reset_index(drop=True)

    all_failed_rows = []

    provinces = locations["province"].dropna().unique().tolist()

    print("\nDaftar provinsi yang akan diproses:")
    for province in provinces:
        print(f"- {province}")

    for province in provinces:
        province_locations = locations[locations["province"] == province].copy()

        status, failed_rows, log_rows = extract_one_province(
            province=province,
            province_locations=province_locations,
        )

        all_failed_rows.extend(failed_rows)

        save_failed_locations(failed_rows)
        append_log(log_rows)

        if status == "skipped":
            print(f"\nSKIPPED province: {province}")
            print("Tidak perlu istirahat karena tidak ada request ke Open-Meteo.")
            continue

        if status == "extracted":
            print(f"\nDONE province: {province}")
            print(f"\nIstirahat antar provinsi: {PROVINCE_SLEEP_SECONDS} detik")
            time.sleep(PROVINCE_SLEEP_SECONDS)

        else:
            print(f"\nNOT FULLY DONE province: {province}")
            print(f"\nIstirahat setelah gagal: {PROVINCE_SLEEP_SECONDS} detik")
            time.sleep(PROVINCE_SLEEP_SECONDS)

    print("\nExtraction Plan B selesai.")
    print(f"Log disimpan di: {LOG_PATH}")

    if FAILED_PATH.exists():
        print(f"Ada lokasi gagal. File disimpan di: {FAILED_PATH}")
    else:
        print("Tidak ada lokasi gagal.")

    print("\nOutput per provinsi ada di:")
    print(OUTPUT_BY_PROVINCE_DIR)


if __name__ == "__main__":
    main()